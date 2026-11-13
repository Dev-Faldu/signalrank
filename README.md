# SignalRank — predicting which news events will matter

DATA 226 group project, Team 10 (Sreeram Achutuni, Dev Dhiren Faldu, Pranav Sharma).
Predict, from the **first hour** of coverage, which GDELT 2.0 events will keep spreading (≥ 3 *new* publishers in hours 1–48).

| | |
|---|---|
| Data | GDELT 2.0 Events + Mentions + GKG, 20–27 Oct 2026: 2,304 files, **11.5 GB** uncompressed (3.6 GB zipped), 3.97 M rows |
| Batch | Spark → partitioned Parquet (0.4 GB) → features/label → MLlib LR vs GBT |
| Streaming | Kafka (KRaft) → Spark Structured Streaming scorer (same feature code as batch) |
| Tracking | MLflow tracking + model registry (`signalrank-champion@champion`) |
| Serving | FastAPI (`/predict`, `/predict/batch`, `/top`, `/stats`, `/model`, `/health`) |
| UI | Streamlit "What matters now" (ranked events, map, trends, what-if) |
| Held-out result (24–25 Oct, weekend) | **PR-AUC 0.585 / F1 0.569** vs rule baseline 0.474 / 0.512 (95% CIs in report) |

Full write-up: [`docs/SignalRank_Final_Report.pdf`](docs/SignalRank_Final_Report.pdf). Architecture: `reports/artifacts/fig_architecture.png`.

## Quick start

```bash
pip install -r requirements.txt            # Python 3.12, Java 17+/21 for Spark
make all                                   # download -> parquet -> features -> prior -> train -> register -> score -> evaluate
uvicorn api.main:app --port 8000           # API docs at http://localhost:8000/docs
SIGNALRANK_API=http://localhost:8000 streamlit run app/dashboard.py
make mlflow-ui                             # http://localhost:5000
```
Docker: `docker compose up -d kafka kafka-init mlflow api dashboard`; streaming demo: `docker compose --profile stream up scorer replay`.
Without Docker: `make kafka`, `make stream` (terminal 1), `make replay` (terminal 2).

## Layout
```
ingest/download_gdelt.py      resumable parallel downloader (constructed 15-min URLs)
spark_jobs/01_ingest.py       zips -> typed, pruned Parquet
spark_jobs/early.py           THE feature logic (shared by batch + streaming)
spark_jobs/02_build_features.py, 02b_publisher_prior.py   features, label, out-of-fold publisher prior
spark_jobs/03_train.py        model comparison, MLflow logging, champion export
spark_jobs/04_score_batch.py, 05_register.py, 06_evaluate.py
streaming/producer.py         Kafka producer (replay | live)
streaming/stream_scorer.py    Structured Streaming scorer
api/main.py  app/dashboard.py
dags/signalrank_daily.py      Airflow DAG (syntax-checked only)
tests/                        pytest: parsers, no-look-ahead features, API contract
```

## Notes on rigor
* Chronological split (train 20–22 Oct, val 23, test 24–25 weekend); champion chosen on validation only.
* The publisher prior is out-of-fold by day for training rows (no label leakage).
* Streaming vs batch parity: 12,202 replayed events, identical features, max score difference 0.0 (`reports/artifacts/stream_parity.json`).
* Honest limits: one week of data on a 2-core machine; live-polling mode implemented but results come from replay; Airflow DAG not executed on a scheduler.

## Team workflow
See `CONTRIBUTING.md`; `scripts/create_github_issues.sh` creates the starter issue board on your repo. Commit under your own accounts.

## Web frontend (glassmorphic, deployable to Vercel)
See `web/README.md`. Static snapshot + in-browser scoring with the real GBT; the full live stack (Spark, Kafka, FastAPI) is unchanged.
