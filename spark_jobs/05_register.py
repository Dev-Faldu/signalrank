"""Job 05 - make sure the champion is in the MLflow Model Registry with alias `champion`,
and check it can be loaded back through the registry URI."""
import pathlib
import sys
import mlflow
from mlflow import MlflowClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
mlflow.set_tracking_uri(f"sqlite:///{ROOT/'mlflow.db'}")
c = MlflowClient()
NAME = "signalrank-champion"
versions = c.search_model_versions(f"name='{NAME}'")
if not versions:
    sys.exit("no registered version found - run spark_jobs/03_train.py first")
latest = max(versions, key=lambda v: int(v.version))
c.set_registered_model_alias(NAME, "champion", latest.version)
print(f"{NAME} v{latest.version} -> alias 'champion' (run {latest.run_id})")
if "--verify" in sys.argv:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.master("local[1]").getOrCreate()
    m = mlflow.spark.load_model(f"models:/{NAME}@champion")
    print("loaded from registry:", [type(s).__name__ for s in m.stages][-1])
