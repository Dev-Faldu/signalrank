"""Job 04 - batch-score a day of events with the champion model -> data/serving/scored.

Seeds the API / dashboard so they work before the streaming scorer is started.
Default: 25 Oct 2026 (held-out test day, never seen in training).
"""
import json
import shutil
import sys
import pathlib
from pyspark.ml import PipelineModel
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import LAKE, MODELS, SERVING, get_spark
from features import cap_categoricals

day = sys.argv[1] if len(sys.argv) > 1 else "20261025"
spark = get_spark("signalrank-score", mem="3g")
meta = json.loads((MODELS / "champion" / "meta.json").read_text())
model = PipelineModel.load(str(MODELS / "champion" / "pipeline"))
df = cap_categoricals(spark.read.parquet(str(LAKE / "features_v2")).where(F.col("day") == day), meta["vocab"])
out = (model.transform(df).withColumn("score", vector_to_array("probability")[1])
       .withColumn("predicted_important", (F.col("score") >= meta["threshold"]).cast("int"))
       .withColumn("scored_at_batch", F.lit(-1))
       .select("event_id", "t0", "source_url", "geo_name", "geo_country", "lat", "lon", "cameo_root",
               "goldstein", "avg_tone", "actor1_country", "m_1h", "src_1h", "lang_1h", "score",
               "predicted_important", "scored_at_batch"))
dst = SERVING / "scored"
shutil.rmtree(dst, ignore_errors=True)
out.write.mode("overwrite").parquet(str(dst))
print("scored", spark.read.parquet(str(dst)).count(), "events for", day)
spark.stop()
