"""Airflow DAG: daily refresh of the SignalRank batch layer.

download yesterday's GDELT -> Parquet -> features -> (weekly) retrain -> score.
Each task shells out to the same Makefile-level scripts used for the manual run,
so the DAG adds scheduling / retries, not new logic.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/signalrank"
default_args = {"owner": "team10", "retries": 2, "retry_delay": timedelta(minutes=10)}

with DAG("signalrank_daily", start_date=datetime(2026, 10, 20), schedule="0 3 * * *",
         catchup=False, default_args=default_args, tags=["data226", "gdelt"]) as dag:
    download = BashOperator(
        task_id="download_gdelt",
        bash_command=f"cd {PROJECT} && python ingest/download_gdelt.py --start {{{{ ds }}}} --days 1 --out data/raw")
    lake = BashOperator(
        task_id="to_parquet",
        bash_command=f"cd {PROJECT} && python spark_jobs/01_ingest.py --days {{{{ ds_nodash }}}}")
    features = BashOperator(
        task_id="build_features",
        bash_command=f"cd {PROJECT} && python spark_jobs/02_build_features.py && python spark_jobs/02b_publisher_prior.py")
    train = BashOperator(
        task_id="retrain_weekly",
        bash_command=f"cd {PROJECT} && python spark_jobs/03_train.py && python spark_jobs/05_register.py",
        trigger_rule="all_success")
    score = BashOperator(task_id="score", bash_command=f"cd {PROJECT} && python spark_jobs/04_score_batch.py {{{{ ds_nodash }}}}")

    download >> lake >> features >> train >> score
