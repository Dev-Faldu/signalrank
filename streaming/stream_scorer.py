"""Spark Structured Streaming scorer.

Kafka topic (JSON records) --> foreachBatch:
   1. append the micro-batch to a rolling Parquet "hot" store (events / mentions / gkg)
   2. take events that have now been visible for >= 60 min of *data time* ("ripe")
   3. build early features with the SAME code as the batch job (early.py)
   4. score with the registered champion PipelineModel and append to data/serving/scored

Data time (max mention timestamp seen) drives the logic, so a replay of historic
intervals and the live GDELT feed behave identically.
"""
import json
import sys
import pathlib
from pyspark.ml.functions import vector_to_array
from pyspark.ml import PipelineModel
from pyspark.sql import functions as F, types as T

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "spark_jobs"))
from common import ROOT, MODELS, SERVING, HOT, KAFKA_PKG, get_spark
from early import dedupe_events, with_offsets, early_features, add_publisher_prior
from features import EARLY_MIN, cap_categoricals
import os

BOOT = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "gdelt.records")

SCHEMA = T.StructType([
    T.StructField("t", T.StringType()),
    T.StructField("event_id", T.LongType()), T.StructField("added_ts", T.StringType()),
    T.StructField("actor1_code", T.StringType()), T.StructField("actor1_country", T.StringType()),
    T.StructField("actor2_code", T.StringType()), T.StructField("actor2_country", T.StringType()),
    T.StructField("is_root_event", T.IntegerType()), T.StructField("cameo_code", T.StringType()),
    T.StructField("cameo_root", T.StringType()), T.StructField("quad_class", T.IntegerType()),
    T.StructField("goldstein", T.DoubleType()), T.StructField("num_mentions_export", T.IntegerType()),
    T.StructField("num_sources_export", T.IntegerType()), T.StructField("avg_tone", T.DoubleType()),
    T.StructField("geo_type", T.IntegerType()), T.StructField("geo_name", T.StringType()),
    T.StructField("geo_country", T.StringType()), T.StructField("lat", T.DoubleType()),
    T.StructField("lon", T.DoubleType()), T.StructField("source_url", T.StringType()),
    T.StructField("mention_ts", T.StringType()), T.StructField("source_name", T.StringType()),
    T.StructField("url", T.StringType()), T.StructField("confidence", T.IntegerType()),
    T.StructField("doc_len", T.IntegerType()), T.StructField("doc_tone", T.DoubleType()),
    T.StructField("lang", T.StringType()),
    T.StructField("gkg_ts", T.StringType()), T.StructField("themes", T.ArrayType(T.StringType())),
])

spark = get_spark("signalrank-stream", mem="3g", packages=KAFKA_PKG)
meta = json.loads((MODELS / "champion" / "meta.json").read_text())
model = PipelineModel.load(str(MODELS / "champion" / "pipeline"))
THR = meta["threshold"]
USE_PRIOR = "pub_prior_mean" in meta["numeric"]
if USE_PRIOR:
    PRIOR = spark.read.parquet(str(MODELS / "source_prior")).cache()
    PRIOR_BASE = float((MODELS / "source_prior_base.txt").read_text())
SERVING.mkdir(parents=True, exist_ok=True)
HOT.mkdir(parents=True, exist_ok=True)
EV_COLS = ["event_id", "added_ts", "actor1_code", "actor1_country", "actor2_code", "actor2_country",
           "is_root_event", "cameo_code", "cameo_root", "quad_class", "goldstein", "num_mentions_export",
           "num_sources_export", "avg_tone", "geo_type", "geo_name", "geo_country", "lat", "lon", "source_url"]
MN_COLS = ["event_id", "mention_ts", "source_name", "url", "confidence", "doc_len", "doc_tone", "lang"]
GK_COLS = ["url", "gkg_ts", "themes"]


def process(batch, batch_id):
    if batch.rdd.isEmpty():
        return
    rec = batch.select(F.from_json(F.col("value").cast("string"), SCHEMA).alias("r")).select("r.*").cache()
    n = {}
    for t, name, cols in (("e", "events", EV_COLS), ("m", "mentions", MN_COLS), ("g", "gkg", GK_COLS)):
        d = rec.where(F.col("t") == t).select(*cols)
        n[name] = d.count()
        if n[name]:
            d.write.mode("append").parquet(str(HOT / name))
    rec.unpersist()

    ev = (spark.read.parquet(str(HOT / "events")).withColumn("added_ts", F.to_timestamp("added_ts")))
    mn = (spark.read.parquet(str(HOT / "mentions")).withColumn("mention_ts", F.to_timestamp("mention_ts")))
    gk = spark.read.parquet(str(HOT / "gkg")).select("url", "themes")
    wm = mn.agg(F.max("mention_ts")).first()[0]
    if wm is None:
        return
    ev = dedupe_events(ev)
    ripe = ev.where((F.col("t0") <= F.expr(f"timestamp'{wm}' - interval {EARLY_MIN} minutes")) &
                    (F.col("t0") >= F.expr(f"timestamp'{wm}' - interval 8 hours")))
    done = SERVING / "scored"
    if done.exists():
        ripe = ripe.join(spark.read.parquet(str(done)).select("event_id"), "event_id", "left_anti")
    m = with_offsets(mn, ripe, EARLY_MIN)
    feats = early_features(ripe, m, gk)
    if USE_PRIOR:
        feats = add_publisher_prior(feats, m, PRIOR, PRIOR_BASE)
    feats = cap_categoricals(feats, meta["vocab"])
    scored = (model.transform(feats)
              .withColumn("score", vector_to_array("probability")[1])
              .withColumn("predicted_important", (F.col("score") >= THR).cast("int"))
              .withColumn("scored_at_batch", F.lit(int(batch_id)))
              .select("event_id", "t0", "source_url", "geo_name", "geo_country", "lat", "lon", "cameo_root",
                      "goldstein", "avg_tone", "actor1_country", "m_1h", "src_1h", "lang_1h", "score",
                      "predicted_important", "scored_at_batch"))
    k = scored.count()
    if k:
        scored.write.mode("append").parquet(str(done))
    print(f"batch {batch_id}: ingested {n} | watermark {wm} | newly scored {k}", flush=True)


if __name__ == "__main__":
    stream = (spark.readStream.format("kafka")
              .option("kafka.bootstrap.servers", BOOT).option("subscribe", TOPIC)
              .option("startingOffsets", os.environ.get("STARTING_OFFSETS", "earliest"))
              .option("maxOffsetsPerTrigger", 400000).option("failOnDataLoss", "false").load())
    q = (stream.writeStream.foreachBatch(process).trigger(processingTime="5 seconds")
         .option("checkpointLocation", str(HOT) + "_ckpt").start())
    q.awaitTermination()
