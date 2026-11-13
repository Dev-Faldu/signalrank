# SignalRank - reproducible pipeline.   `make all` runs data -> features -> train -> score
PY ?= python
START ?= 2026-10-20
DAYS ?= 8
ALLDAYS = 20261020 20261021 20261022 20261023 20261024 20261025 20261026 20261027

.PHONY: all data lake features prior train register score evaluate api dashboard kafka stream replay test clean
all: data lake features prior train register score evaluate

data:        ## download GDELT 2.0 15-minute files (about 3.4 GB zipped / 11 GB raw)
	$(PY) ingest/download_gdelt.py --start $(START) --days $(DAYS) --out data/raw
lake:        ## raw CSV zips -> partitioned Parquet
	$(PY) spark_jobs/01_ingest.py --days $(ALLDAYS)
features:    ## one row per event: first-hour features + 48 h label
	$(PY) spark_jobs/02_build_features.py
prior:       ## leakage-safe publisher-reach prior
	$(PY) spark_jobs/02b_publisher_prior.py
train:       ## compare models, log to MLflow, export champion
	$(PY) spark_jobs/03_train.py
register:    ## put the champion in the MLflow model registry
	$(PY) spark_jobs/05_register.py
score:       ## seed the serving store with the held-out test day
	$(PY) spark_jobs/04_score_batch.py 20261025
evaluate:    ## tie-safe metrics, bootstrap CIs, figures for the report
	$(PY) spark_jobs/06_evaluate.py
api:
	uvicorn api.main:app --port 8000
dashboard:
	SIGNALRANK_API=http://localhost:8000 streamlit run app/dashboard.py
kafka:
	docker compose up -d --wait kafka
	docker compose exec -T kafka kafka-topics --bootstrap-server kafka:29092 --create --if-not-exists --topic gdelt.records --partitions 1 --replication-factor 1
stream:      ## Spark Structured Streaming scorer (needs Kafka)
	$(PY) streaming/stream_scorer.py
replay:      ## replay 6 h of held-out data into Kafka
	$(PY) streaming/producer.py replay --start 20261025120000 --end 20261025180000 --interval-sec 3
test:
	pytest -q tests
mlflow-ui:
	mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000
