"""Job 02 - build the modelling table: one row per event.

features = what is visible EARLY_MIN minutes after first sighting (early.py)
label    = how widely the story spreads in the next 48 h (distinct publishers)
"""
import sys
import pathlib
from pyspark.sql import functions as F

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import LAKE, get_spark
from features import HORIZON_H
from early import dedupe_events, with_offsets, early_features, label_table

START, END = "2026-10-20 00:00:00", "2026-10-26 00:00:00"  # events first seen in this window get labels

if __name__ == "__main__":
    spark = get_spark("signalrank-features", mem="5g")
    ev = dedupe_events(spark.read.parquet(str(LAKE / "events")))
    ev = ev.where((F.col("t0") >= START) & (F.col("t0") < END))
    mn = spark.read.parquet(str(LAKE / "mentions"))
    gk = spark.read.parquet(str(LAKE / "gkg")).select("url", "themes")

    m = with_offsets(mn, ev, HORIZON_H * 60)
    df = (early_features(ev, m, gk).join(label_table(m), "event_id")
          .withColumn("day", F.date_format("t0", "yyyyMMdd")))
    out = str(LAKE / ("features" if len(sys.argv) < 2 else sys.argv[1]))
    df.write.mode("overwrite").parquet(out)
    n = spark.read.parquet(out)
    print("rows", n.count())
    n.groupBy("day").count().orderBy("day").show()
    spark.stop()
