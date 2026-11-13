# Working agreement (Team 10)

* `main` is protected in spirit: nobody pushes to it directly.
* One branch per issue: `feat/<area>-<short-name>` (e.g. `feat/serving-top-endpoint`).
* Open a pull request, link the issue (`Closes #12`), and get **one teammate's review** before merging.
* Commit under your own GitHub account; small commits with messages that say *why*.
* Run `make test` before opening a PR.
* Weekly sync: agree the next 3 issues per person; update the board.

## Areas and suggested owners (rebalance as you like - the guideline asks for similar-sized contributions)

| Area | What | Files |
|---|---|---|
| A. Data & batch | GDELT download, Parquet lake, features, label, publisher prior, Airflow DAG | `ingest/`, `spark_jobs/01*, 02*`, `dags/` |
| B. Modelling & MLOps | models, ablations, MLflow tracking/registry, evaluation, tests | `spark_jobs/03*, 05*, 06*`, `tests/`, `MLproject` |
| C. Serving & UI | Kafka producer, Structured Streaming scorer, FastAPI, Streamlit, Docker Compose, demo | `streaming/`, `api/`, `app/`, `docker/`, `docker-compose.yml` |

Everyone writes their own section of the report and presents their own part (see `docs/CONTRIBUTIONS.md`).
