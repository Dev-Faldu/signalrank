"""Job 03 - train & compare models with Spark MLlib; track everything in MLflow.

Runs:  rule baseline (first-hour publishers) | LR numeric | LR + themes | GBT numeric | GBT + themes
Chronological split (train 20-22 Oct, val 23 Oct, test 24-25 Oct = weekend).
The champion (best validation PR-AUC) is registered in the MLflow Model Registry
and exported to models/champion for the API + streaming scorer.
"""
import json
import shutil
import sys
import pathlib
import numpy as np
import mlflow
import mlflow.spark
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression, GBTClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import (StringIndexer, OneHotEncoder, HashingTF, VectorAssembler,
                                StandardScaler)
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import LAKE, MODELS, ROOT, ARTIFACTS, get_spark
from features import (NUMERIC, NUMERIC_PRIOR, CATEGORICAL, THEMES_COL, HASH_DIM, POS_THRESHOLD,
                      TRAIN_DAYS, VAL_DAYS, TEST_DAYS, TOP_CATS, LABEL_COL, cap_categoricals)

ARTIFACTS.mkdir(parents=True, exist_ok=True)
mlflow.set_tracking_uri(f"sqlite:///{ROOT/'mlflow.db'}")
mlflow.set_experiment("signalrank")
spark = get_spark("signalrank-train", mem="5g")

df = (spark.read.parquet(str(LAKE / "features_v2"))
      .withColumn("label", (F.col(LABEL_COL) >= POS_THRESHOLD).cast("double")))
vocab = {}
tr0 = df.where(F.col("day").isin(TRAIN_DAYS))
for c in CATEGORICAL:
    vocab[c] = [r[0] for r in tr0.groupBy(c).count().orderBy(F.desc("count")).limit(TOP_CATS).collect()]
df = cap_categoricals(df, vocab)
train = df.where(F.col("day").isin(TRAIN_DAYS))
val = df.where(F.col("day").isin(VAL_DAYS))
test = df.where(F.col("day").isin(TEST_DAYS))
n_pos = train.where("label=1").count(); n_all = train.count()
POS_W = float(min(8.0, (n_all - n_pos) / n_pos))   # moderate re-weighting; threshold tuned on val
train = train.withColumn("w", F.when(F.col("label") == 1, POS_W).otherwise(1.0)).cache()
print("train", n_all, "pos rate", n_pos / n_all, "val", val.count(), "test", test.count())


def stages(kind, use_prior, use_themes):
    st, cols = [], list(NUMERIC) + (list(NUMERIC_PRIOR) if use_prior else [])
    for c in CATEGORICAL:
        st.append(StringIndexer(inputCol=c, outputCol=f"{c}_ix", handleInvalid="keep"))
    if kind == "lr":
        st.append(OneHotEncoder(inputCols=[f"{c}_ix" for c in CATEGORICAL],
                                outputCols=[f"{c}_oh" for c in CATEGORICAL], handleInvalid="keep"))
        cols += [f"{c}_oh" for c in CATEGORICAL]
    else:
        cols += [f"{c}_ix" for c in CATEGORICAL]
    if use_themes:
        st.append(HashingTF(inputCol=THEMES_COL, outputCol="themes_tf", numFeatures=HASH_DIM, binary=True))
        cols.append("themes_tf")
    st.append(VectorAssembler(inputCols=cols, outputCol="raw", handleInvalid="keep"))
    if kind == "lr":
        st.append(StandardScaler(inputCol="raw", outputCol="features", withMean=False, withStd=True))
        st.append(LogisticRegression(featuresCol="features", labelCol="label", weightCol="w",
                                     regParam=0.01, elasticNetParam=0.0, maxIter=60))
    else:
        st.append(GBTClassifier(featuresCol="raw", labelCol="label", weightCol="w", maxIter=40,
                                maxDepth=5, maxBins=64, stepSize=0.15, subsamplingRate=0.8, seed=7))
    return Pipeline(stages=st)


def scores(model, d):
    p = model.transform(d).select("event_id", "day", "label", "src_1h",
                                  vector_to_array("probability")[1].alias("score"))
    return p.toPandas()


def pr_auc(y, s):
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, s))


def best_f1(y, s):
    """F1-optimal threshold, evaluated at unique score values only (tie-safe)."""
    from sklearn.metrics import precision_recall_curve
    p, r, t = precision_recall_curve(y, s)
    f1 = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-12)
    i = int(np.argmax(f1))
    return float(f1[i]), float(t[i])


def metrics(y, s, thr):
    from sklearn.metrics import roc_auc_score
    pred = s >= thr
    tp = float((pred & (y == 1)).sum()); fp = float((pred & (y == 0)).sum()); fn = float(((~pred) & (y == 1)).sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    out = {"pr_auc": pr_auc(y, s), "roc_auc": float(roc_auc_score(y, s)),
           "precision": prec, "recall": rec, "f1": 2 * prec * rec / max(prec + rec, 1e-12)}
    o = np.argsort(-s)
    for frac in (0.01, 0.05):
        k = int(len(y) * frac); out[f"precision_at_top{int(frac*100)}pct"] = float(y[o][:k].mean())
    return out


results = {}
RUNS = [("lr_base", "lr", False, False), ("lr_prior", "lr", True, False),
        ("gbt_base", "gbt", False, False), ("gbt_prior", "gbt", True, False),
        ("gbt_prior_themes", "gbt", True, True)]

# ---- rule baseline: score = distinct publishers in first hour --------------
with mlflow.start_run(run_name="baseline_src_1h"):
    pv = val.select("label", F.col("src_1h").cast("double").alias("score")).toPandas()
    pt = test.select("label", F.col("src_1h").cast("double").alias("score")).toPandas()
    f, thr = best_f1(pv.label.values, pv.score.values)
    mv, mt = metrics(pv.label.values, pv.score.values, thr), metrics(pt.label.values, pt.score.values, thr)
    mlflow.log_params({"model": "rule", "feature": "src_1h", "threshold": thr, "pos_threshold": POS_THRESHOLD})
    mlflow.log_metrics({f"val_{k}": v for k, v in mv.items()}); mlflow.log_metrics({f"test_{k}": v for k, v in mt.items()})
    results["baseline_src_1h"] = {"val": mv, "test": mt, "threshold": thr}
    print("baseline", mv, mt, flush=True)

best = None
for name, kind, pri, th in RUNS:
    with mlflow.start_run(run_name=name) as run:
        pipe = stages(kind, pri, th)
        model = pipe.fit(train)
        pv, pt = scores(model, val), scores(model, test)
        f, thr = best_f1(pv.label.values, pv.score.values)
        mv, mt = metrics(pv.label.values, pv.score.values, thr), metrics(pt.label.values, pt.score.values, thr)
        mlflow.log_params({"model": kind, "use_publisher_prior": pri, "use_themes": th, "pos_weight": POS_W, "threshold": thr,
                           "pos_threshold": POS_THRESHOLD, "n_train": n_all, "hash_dim": HASH_DIM,
                           "train_days": ",".join(TRAIN_DAYS), "val_days": ",".join(VAL_DAYS),
                           "test_days": ",".join(TEST_DAYS)})
        mlflow.log_metrics({f"val_{k}": v for k, v in mv.items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in mt.items()})
        results[name] = {"val": mv, "test": mt, "threshold": thr, "run_id": run.info.run_id,
                         "use_prior": pri, "use_themes": th}
        print(name, "VAL", mv, "TEST", mt, flush=True)
        if best is None or mv["pr_auc"] > results[best]["val"]["pr_auc"]:
            best = name; best_model = model; best_pt = pt; best_pv = pv
        # keep per-model score dumps for the report (small)
        pt.assign(model=name).to_parquet(ARTIFACTS / f"test_scores_{name}.parquet")

# ---- champion: register + export --------------------------------------------
print("champion:", best)
with mlflow.start_run(run_name=f"champion_{best}"):
    mlflow.log_params({"champion": best, "threshold": results[best]["threshold"]})
    mlflow.log_metrics({f"test_{k}": v for k, v in results[best]["test"].items()})
    try:
        mlflow.spark.log_model(best_model, artifact_path="model", registered_model_name="signalrank-champion")
    except Exception as e:  # registry export is best-effort; the exported copy below is what serving uses
        print("mlflow.spark.log_model failed:", repr(e)[:300])

dst = MODELS / "champion"
shutil.rmtree(dst, ignore_errors=True)
best_model.write().overwrite().save(str(dst / "pipeline"))
# feature importance (GBT) or coefficients (LR) with names
last = best_model.stages[-1]
attrs = best_model.transform(val.limit(5)).schema[best_model.stages[-1].getFeaturesCol()].metadata["ml_attr"]["attrs"]
names = [a["name"] for t in attrs.values() for a in t] if isinstance(attrs, dict) else []
idx_to_name = {}
for t in attrs.values():
    for a in t:
        idx_to_name[a["idx"]] = a["name"]
imp = last.featureImportances.toArray() if hasattr(last, "featureImportances") else np.abs(last.coefficients.toArray())
top = sorted(((idx_to_name.get(i, str(i)), float(v)) for i, v in enumerate(imp)), key=lambda x: -x[1])[:25]
meta = {"champion": best, "numeric": NUMERIC + (NUMERIC_PRIOR if results[best]["use_prior"] else []), "categorical": CATEGORICAL, "themes_col": THEMES_COL,
        "vocab": vocab, "threshold": results[best]["threshold"], "pos_threshold": POS_THRESHOLD,
        "results": results, "top_features": top, "pos_weight": POS_W,
        "train_rows": n_all, "train_pos_rate": n_pos / n_all}
(dst / "meta.json").write_text(json.dumps(meta, indent=2))
(ARTIFACTS / "results.json").write_text(json.dumps(meta, indent=2))
spark.stop()
