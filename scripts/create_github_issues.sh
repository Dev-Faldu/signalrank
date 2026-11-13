#!/usr/bin/env bash
# Creates the project's starter issues on YOUR GitHub repo (run once, from the repo root, after `gh auth login`).
# Assign each issue to the teammate who takes it:  gh issue edit <n> --add-assignee <login>
set -euo pipefail
mk() { gh issue create --title "$1" --body "$2" --label "$3" >/dev/null && echo "created: $1"; }
for l in data modelling serving docs; do gh label create "$l" --force >/dev/null 2>&1 || true; done

mk "Download GDELT 2.0 window (8 days, >10 GB raw)" "Resumable parallel downloader for export/mentions/gkg. Acceptance: 2,016 files, checksum log." data
mk "Parquet lake: typed, column-pruned, partitioned by day" "Spark job converting zips -> Parquet. Acceptance: row counts per day logged." data
mk "Early-coverage features + 48h growth label (early.py)" "One implementation shared by batch and streaming. Acceptance: unit test proving no look-ahead past 60 min." data
mk "Publisher-reach prior (out-of-fold target encoding)" "Leakage-safe encoding; document the fold scheme in the report." data
mk "Airflow DAG for the daily batch refresh" "download -> parquet -> features -> retrain -> score." data
mk "Model comparison: rule baseline vs LogReg vs GBT (+prior, +themes)" "Chronological split, PR-AUC and F1, MLflow runs for each." modelling
mk "MLflow tracking + model registry + MLproject entry points" "Reproducibility requirement: 'mlflow run .' and registry alias 'champion'." modelling
mk "Held-out evaluation with bootstrap CIs + error analysis" "Weekend test split; late-bloomer analysis; figures for the report." modelling
mk "Test suite (parsers, feature leakage, API)" "pytest in CI." modelling
mk "Kafka producer: replay + live GDELT polling" "JSON records on topic gdelt.records." serving
mk "Spark Structured Streaming scorer" "foreachBatch: hot store -> ripe events -> features -> score." serving
mk "FastAPI: /predict, /predict/batch, /top, /stats, /model, /health" "Pydantic validation, OpenAPI docs." serving
mk "Streamlit 'What matters now' dashboard" "Ranked table, map, trends, try-an-event form." serving
mk "Docker Compose stack (Kafka, MLflow, API, UI, scorer)" "One command demo." serving
mk "Final report (research-paper style)" "Abstract, intro, related work, data, methods, results, deployment, limitations, contributions." docs
mk "Presentation + live demo script" "10-15 min; contributions slide; rehearse the demo." docs
