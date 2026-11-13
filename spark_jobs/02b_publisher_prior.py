"""Job 02b - publisher-reach prior (a leakage-safe target encoding).

For every publisher: how often did events it covered *in their first hour* turn
out to be important (>= POS_THRESHOLD new publishers after hour 1)?  Smoothed toward the
global rate.  An event's features are the mean / max prior of the publishers that
covered it in its first hour.

Leakage control: training-day events use priors computed from the OTHER training
days only (out-of-fold by day); validation / test events use all training days.
The final table (all training days) is saved for the API + streaming scorer.
"""
import sys
import pathlib
from pyspark.sql import functions as F

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import LAKE, MODELS, get_spark
from features import EARLY_MIN, POS_THRESHOLD, LABEL_COL, TRAIN_DAYS, PRIOR_K
from early import with_offsets

spark = get_spark("signalrank-prior", mem="5g")
base = spark.read.parquet(str(LAKE / "features")).select("event_id", "t0", "day", LABEL_COL)
base = base.withColumn("y", (F.col(LABEL_COL) >= POS_THRESHOLD).cast("int"))
mn = spark.read.parquet(str(LAKE / "mentions"))
pairs = (with_offsets(mn, base.select("event_id", "t0"), EARLY_MIN)
         .select("event_id", "src").dropDuplicates().join(base.select("event_id", "day", "y"), "event_id"))
pairs.cache()

tr = pairs.where(F.col("day").isin(TRAIN_DAYS))
g = tr.agg(F.avg("y")).first()[0]
per_day = tr.groupBy("src", "day").agg(F.count("*").alias("n_d"), F.sum("y").alias("p_d"))
tot = tr.groupBy("src").agg(F.count("*").alias("n"), F.sum("y").alias("p"))

# fold-aware stats: train rows exclude their own day, val/test rows use everything
pd_ = (pairs.join(tot, "src", "left").join(per_day, ["src", "day"], "left")
       .withColumn("n_use", F.coalesce("n", F.lit(0)) - F.when(F.col("day").isin(TRAIN_DAYS), F.coalesce("n_d", F.lit(0))).otherwise(0))
       .withColumn("p_use", F.coalesce("p", F.lit(0)) - F.when(F.col("day").isin(TRAIN_DAYS), F.coalesce("p_d", F.lit(0))).otherwise(0))
       .withColumn("prior", (F.col("p_use") + PRIOR_K * F.lit(g)) / (F.col("n_use") + PRIOR_K))
       .withColumn("known", (F.col("n_use") >= 5).cast("int")))
agg = pd_.groupBy("event_id").agg(F.avg("prior").alias("pub_prior_mean"), F.max("prior").alias("pub_prior_max"),
                                  F.avg("known").alias("pub_known_frac"))
feats = spark.read.parquet(str(LAKE / "features"))
out = feats.join(agg, "event_id", "left").fillna({"pub_prior_mean": g, "pub_prior_max": g, "pub_known_frac": 0.0})
out.write.mode("overwrite").parquet(str(LAKE / "features_v2"))

# final table for serving (all training days)
final = tot.withColumn("prior", (F.col("p") + PRIOR_K * F.lit(g)) / (F.col("n") + PRIOR_K)).withColumn("known", (F.col("n") >= 5).cast("int"))
final.select("src", "n", "prior", "known").write.mode("overwrite").parquet(str(MODELS / "source_prior"))
with open(MODELS / "source_prior_base.txt", "w") as f:
    f.write(str(g))
print("global pos rate", g, "publishers", final.count(), "feature rows", spark.read.parquet(str(LAKE / "features_v2")).count())
spark.stop()
