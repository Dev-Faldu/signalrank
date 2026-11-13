"""SignalRank model-serving API (FastAPI).

GET  /health         liveness + model info
GET  /model          model card: metrics, threshold, top features
POST /predict        score one event from its first-hour features
POST /predict/batch  score many events
GET  /top            highest-ranked recently scored events ("what matters now")
GET  /stats          aggregates for the dashboard (trend, countries, themes of the day)

The model is the Spark MLlib PipelineModel exported by spark_jobs/03_train.py,
so the API scores with exactly the pipeline that was evaluated.
"""
import json
import os
import pathlib
import sys
import threading
from typing import List, Optional

import pyarrow.dataset as ds
import pyarrow.compute as pc
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

ROOT = pathlib.Path(os.environ.get("SIGNALRANK_ROOT", pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "spark_jobs"))
MODEL_DIR = ROOT / "models" / "champion"
SCORED = ROOT / "data" / "serving" / "scored"

app = FastAPI(title="SignalRank API", version="1.0",
              description="Predict which news events will matter, from their first hour of coverage (GDELT 2.0).")

_state = {"spark": None, "model": None, "meta": None}
_lock = threading.Lock()


def _meta():
    if _state["meta"] is None:
        _state["meta"] = json.loads((MODEL_DIR / "meta.json").read_text())
    return _state["meta"]


def _model():
    with _lock:
        if _state["model"] is None:
            from pyspark.sql import SparkSession
            from pyspark.ml import PipelineModel
            _state["spark"] = (SparkSession.builder.appName("signalrank-api").master("local[1]")
                               .config("spark.driver.memory", "1g").config("spark.ui.enabled", "false")
                               .config("spark.sql.shuffle.partitions", "2")
                               .config("spark.ui.showConsoleProgress", "false").getOrCreate())
            _state["model"] = PipelineModel.load(str(MODEL_DIR / "pipeline"))
    return _state["spark"], _state["model"]


class EventFeatures(BaseModel):
    """What is known one hour after an event first appears in GDELT."""
    m_1h: int = Field(1, ge=0, description="mentions in first hour")
    m_15m: int = Field(1, ge=0, description="mentions in first 15 minutes")
    src_1h: int = Field(1, ge=0, description="distinct publishers in first hour")
    lang_1h: int = Field(1, ge=0, description="distinct source languages in first hour")
    nonen_1h: int = Field(0, ge=0, description="non-English mentions in first hour")
    art_1h: int = Field(1, ge=0, description="distinct articles in first hour")
    tone_mean_1h: float = 0.0
    tone_std_1h: float = 0.0
    conf_mean_1h: float = Field(50.0, ge=0, le=100)
    doclen_mean_1h: float = 3000.0
    goldstein: float = Field(0.0, ge=-10, le=10)
    avg_tone: float = 0.0
    quad_class: int = Field(1, ge=1, le=4)
    is_root_event: int = Field(0, ge=0, le=1)
    geo_type: int = Field(0, ge=0, le=5)
    num_mentions_export: int = Field(1, ge=0)
    num_sources_export: int = Field(1, ge=0)
    pub_prior_mean: float = Field(0.22, description="mean historical reach prior of first-hour publishers")
    pub_prior_max: float = Field(0.22, description="max historical reach prior of first-hour publishers")
    pub_known_frac: float = Field(0.0, ge=0, le=1, description="share of first-hour publishers with >=5 training events")
    cameo_root: str = Field("19", description="CAMEO root code, e.g. '14' protest, '19' fight")
    geo_country: str = Field("US", description="FIPS country code of the action location")
    actor1_country: str = Field("NA", description="Actor1 country code or NA")
    actor2_country: Optional[str] = None
    themes: List[str] = Field(default_factory=list, description="GKG themes seen in first-hour articles")


class Prediction(BaseModel):
    score: float
    important: bool
    threshold: float
    model: str


def _to_df(spark, items: List[EventFeatures]):
    from pyspark.sql import functions as F
    from features import cap_categoricals, NUMERIC, NUMERIC_PRIOR
    rows = []
    for i, e in enumerate(items):
        d = e.model_dump()
        th = [t for t in d.pop("themes") if t]
        d.update(event_id=i, themes_1h=th, n_themes_1h=len(th),
                 has_actor1_country=int(d["actor1_country"] not in (None, "", "NA")),
                 has_actor2_country=int(bool(d["actor2_country"])),
                 has_geo=int(d["geo_country"] not in (None, "", "NA")))
        d.pop("actor2_country")
        rows.append({k: (v if k == "event_id" or isinstance(v, (str, list)) else float(v)) for k, v in d.items()})
    from pyspark.sql import types as T
    fields = []
    for k, v in rows[0].items():
        t = (T.LongType() if k == "event_id" else T.ArrayType(T.StringType()) if k == "themes_1h"
             else T.StringType() if isinstance(v, str) else T.DoubleType())
        fields.append(T.StructField(k, t))
    df = spark.createDataFrame(rows, schema=T.StructType(fields))
    for c in NUMERIC + NUMERIC_PRIOR:  # make dtypes match training
        df = df.withColumn(c, F.col(c).cast("double"))
    return cap_categoricals(df, _meta()["vocab"])


def _score(items: List[EventFeatures]) -> List[Prediction]:
    from pyspark.ml.functions import vector_to_array
    from pyspark.sql import functions as F
    spark, model = _model()
    meta = _meta()
    out = (model.transform(_to_df(spark, items)).select("event_id", vector_to_array("probability")[1].alias("p"))
           .orderBy("event_id").collect())
    return [Prediction(score=float(r.p), important=bool(r.p >= meta["threshold"]),
                       threshold=meta["threshold"], model=meta["champion"]) for r in out]


@app.get("/health")
def health():
    n = 0
    if SCORED.exists():
        n = ds.dataset(str(SCORED), format="parquet").count_rows()
    return {"status": "ok", "model": _meta()["champion"], "threshold": _meta()["threshold"],
            "scored_events_available": n}


@app.get("/model")
def model_card():
    m = _meta()
    return {k: m[k] for k in ("champion", "threshold", "pos_threshold", "results", "top_features",
                              "train_rows", "train_pos_rate")}


@app.post("/predict", response_model=Prediction)
def predict(e: EventFeatures):
    return _score([e])[0]


@app.post("/predict/batch", response_model=List[Prediction])
def predict_batch(items: List[EventFeatures]):
    if not items or len(items) > 5000:
        raise HTTPException(400, "send between 1 and 5000 events")
    return _score(items)


def _table():
    if not SCORED.exists():
        raise HTTPException(503, "no scored events yet - run spark_jobs/04_score_batch.py or the streaming scorer")
    return ds.dataset(str(SCORED), format="parquet").to_table()


def _recent(hours: float):
    t = _table()
    ts = t["t0"]
    latest = pc.max(ts).as_py()
    import datetime as dt
    cutoff = latest - dt.timedelta(hours=hours)
    return t.filter(pc.greater_equal(ts, cutoff)), latest


@app.get("/top")
def top(n: int = Query(20, ge=1, le=500), hours: float = Query(24, gt=0, le=168),
        country: Optional[str] = None, dedupe: bool = True):
    """Highest-scoring events among those first seen in the last `hours` of data time.

    One article often yields several GDELT events; with dedupe=true only the
    best-scoring event per source article is returned."""
    t, latest = _recent(hours)
    if country:
        t = t.filter(pc.equal(t["geo_country"], country))
    t = t.sort_by([("score", "descending")])
    if dedupe:
        df = t.to_pandas().drop_duplicates("source_url").head(n)
        rows = df.astype(object).where(df.notna(), None).to_dict("records")
        for r in rows:
            r["t0"] = r["t0"].isoformat()
        return {"as_of": str(latest), "events": rows}
    return {"as_of": str(latest), "events": t.slice(0, n).to_pylist()}


@app.get("/stats")
def stats(hours: float = Query(24, gt=0, le=168)):
    import pandas as pd
    t, latest = _recent(hours)
    df = t.select(["t0", "score", "predicted_important", "geo_country", "cameo_root", "src_1h"]).to_pandas()
    hourly = (df.set_index("t0").resample("1h").agg(score_mean=("score", "mean"), n=("score", "size"),
                                                     important=("predicted_important", "sum")).reset_index())
    hourly["score_mean"] = hourly["score_mean"].fillna(0.0)
    hourly["t0"] = hourly["t0"].astype(str)
    ctry = (df[df.predicted_important == 1].groupby("geo_country").size().sort_values(ascending=False).head(10))
    return {"as_of": str(latest), "n_events": int(len(df)), "n_important": int(df.predicted_important.sum()),
            "hourly": hourly.to_dict("records"), "top_countries": ctry.to_dict(),
            "top_event_types": (df[df.predicted_important == 1].groupby("cameo_root").size()
                                .sort_values(ascending=False).head(8).to_dict())}
