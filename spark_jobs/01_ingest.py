"""Job 01 - raw GDELT CSV zips -> typed, column-pruned, partitioned Parquet.

GDELT files are tab-delimited, header-less, zipped. Spark cannot read .zip, so
each UTC day is unzipped to a scratch folder, converted by Spark, and the scratch
folder is deleted. Only the columns the project needs are kept; the GKG table
(~90% of the raw bytes) is reduced to id/time/source/url/themes/tone.
"""
import argparse
import shutil
import zipfile
import sys
import pathlib
from pyspark.sql import functions as F

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import RAW, STAGE, LAKE, get_spark


def unzip_day(kind, day, dest):
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted((RAW / kind).glob(f"{day}*.zip"))
    for f in files:
        with zipfile.ZipFile(f) as z:
            z.extractall(dest)
    return len(files)


def rd(spark, path):
    return (spark.read.option("sep", "\t").option("quote", "\u0000")
            .option("mode", "PERMISSIVE").csv(str(path) + "/*"))


def ts(col):
    return F.to_timestamp(col, "yyyyMMddHHmmss")


def convert_events(spark, day):
    d = STAGE / "export" / day
    unzip_day("export", day, d)
    df = rd(spark, d)
    out = df.select(
        F.col("_c0").cast("long").alias("event_id"),
        F.col("_c5").alias("actor1_code"), F.col("_c7").alias("actor1_country"),
        F.col("_c15").alias("actor2_code"), F.col("_c17").alias("actor2_country"),
        F.col("_c25").alias("is_root_event").cast("int"),
        F.col("_c28").alias("cameo_root"), F.col("_c26").alias("cameo_code"),
        F.col("_c29").cast("int").alias("quad_class"),
        F.col("_c30").cast("double").alias("goldstein"),
        F.col("_c31").cast("int").alias("num_mentions_export"),
        F.col("_c32").cast("int").alias("num_sources_export"),
        F.col("_c33").cast("int").alias("num_articles_export"),
        F.col("_c34").cast("double").alias("avg_tone"),
        F.col("_c51").cast("int").alias("geo_type"),
        F.col("_c52").alias("geo_name"), F.col("_c53").alias("geo_country"),
        F.col("_c56").cast("double").alias("lat"), F.col("_c57").cast("double").alias("lon"),
        ts(F.col("_c59")).alias("added_ts"), F.col("_c60").alias("source_url"),
    ).where(F.col("event_id").isNotNull())
    out.write.mode("overwrite").parquet(str(LAKE / "events" / f"day={day}"))
    shutil.rmtree(d, ignore_errors=True)


def convert_mentions(spark, day):
    d = STAGE / "mentions" / day
    unzip_day("mentions", day, d)
    df = rd(spark, d)
    out = df.select(
        F.col("_c0").cast("long").alias("event_id"),
        ts(F.col("_c2")).alias("mention_ts"),
        F.col("_c3").cast("int").alias("mention_type"),
        F.col("_c4").alias("source_name"), F.col("_c5").alias("url"),
        F.col("_c11").cast("int").alias("confidence"),
        F.col("_c12").cast("int").alias("doc_len"),
        F.col("_c13").cast("double").alias("doc_tone"),
        F.regexp_extract(F.col("_c14"), r"srclc:([a-z]+)", 1).alias("lang_raw"),
    ).where(F.col("event_id").isNotNull())
    out = out.withColumn("lang", F.when(F.col("lang_raw") == "", "eng").otherwise(F.col("lang_raw"))).drop("lang_raw")
    out.write.mode("overwrite").parquet(str(LAKE / "mentions" / f"day={day}"))
    shutil.rmtree(d, ignore_errors=True)


def convert_gkg(spark, day):
    d = STAGE / "gkg" / day
    unzip_day("gkg", day, d)
    df = rd(spark, d)
    tone = F.split(F.col("_c15"), ",")
    out = df.select(
        F.col("_c0").alias("gkg_id"), ts(F.col("_c1")).alias("gkg_ts"),
        F.col("_c3").alias("source_name"), F.col("_c4").alias("url"),
        F.array_distinct(F.split(F.col("_c7"), ";")).alias("themes"),
        tone.getItem(0).cast("double").alias("tone"),
        tone.getItem(1).cast("double").alias("pos"),
        tone.getItem(2).cast("double").alias("neg"),
        tone.getItem(3).cast("double").alias("polarity"),
        tone.getItem(6).cast("int").alias("wordcount"),
    ).where(F.col("url").isNotNull())
    out.write.mode("overwrite").parquet(str(LAKE / "gkg" / f"day={day}"))
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", nargs="+", required=True, help="YYYYMMDD ...")
    ap.add_argument("--tables", nargs="+", default=["events", "mentions", "gkg"])
    a = ap.parse_args()
    spark = get_spark("signalrank-ingest")
    fn = {"events": convert_events, "mentions": convert_mentions, "gkg": convert_gkg}
    for day in a.days:
        for t in a.tables:
            fn[t](spark, day)
            print("converted", t, day, flush=True)
    spark.stop()
