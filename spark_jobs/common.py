"""Shared helpers: Spark session + project paths."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
STAGE = ROOT / "data" / "stage"
LAKE = ROOT / "data" / "lake"          # partitioned Parquet "data lake"
MODELS = ROOT / "models"
ARTIFACTS = ROOT / "reports" / "artifacts"


def get_spark(app="signalrank", mem="4g", cores=2, packages=None):
    from pyspark.sql import SparkSession
    os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)
    b = (SparkSession.builder.appName(app).master(f"local[{cores}]")
            .config("spark.driver.memory", mem)
            .config("spark.sql.shuffle.partitions", "16")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.showConsoleProgress", "false")
            .config("spark.local.dir", str(ROOT / "data" / "spark_tmp")))
    if packages:
        b = b.config("spark.jars.packages", packages)
    return b.getOrCreate()


SERVING = pathlib.Path(os.environ.get("SIGNALRANK_SERVING", ROOT / "data" / "serving"))   # scored events (API / dashboard)
HOT = pathlib.Path(os.environ.get("SIGNALRANK_HOT", ROOT / "data" / "hot"))               # rolling store of streamed records
KAFKA_PKG = "org.apache.spark:spark-sql-kafka-0-10_2.13:4.2.0"
