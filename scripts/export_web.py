"""Export everything the static web frontend needs (no server required):
  web/data/model.json     GBT trees + categorical index maps  -> scored in the browser
  web/data/snapshot.json  top scored events, hourly stats, model card
Run after training + scoring:  python scripts/export_web.py
"""
import json, pathlib, re, sys
import numpy as np, pandas as pd
import pyarrow.dataset as ds

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "spark_jobs"))
OUT = ROOT / "web" / "data"; OUT.mkdir(parents=True, exist_ok=True)
meta = json.loads((ROOT / "models/champion/meta.json").read_text())

# ---------- model -> JSON ----------
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
spark = SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false").getOrCreate()
pm = PipelineModel.load(str(ROOT / "models/champion/pipeline"))
idx = [s for s in pm.stages if s.__class__.__name__ == "StringIndexerModel"]
cats = {s.getInputCol(): list(s.labelsArray[0]) for s in idx}
asm = [s for s in pm.stages if s.__class__.__name__ == "VectorAssembler"][0]
gbt = pm.stages[-1]
feat_order = asm.getInputCols()
lines = gbt.toDebugString.splitlines()
trees, cur, stack = [], None, []


def parse_cond(s):
    m = re.match(r"\(feature (\d+) <= ([^)]+)\)", s)
    if m: return {"f": int(m.group(1)), "op": "le", "v": float(m.group(2))}
    m = re.match(r"\(feature (\d+) in \{([^}]*)\}\)", s)
    if m: return {"f": int(m.group(1)), "op": "in", "v": [float(x) for x in m.group(2).split(",") if x.strip()]}
    raise ValueError(s)


def build(tree_lines):
    """tree_lines: (depth, text). Returns nested node."""
    pos = 0
    def node(depth):
        nonlocal pos
        d, t = tree_lines[pos]; pos += 1
        if t.startswith("Predict:"):
            return {"p": float(t.split(":")[1])}
        n = parse_cond(t[len("If "):])
        n["l"] = node(depth + 1)
        d2, t2 = tree_lines[pos]; assert t2.startswith("Else"), t2; pos += 1
        n["r"] = node(depth + 1)
        return n
    return node(0)


tl = None
for ln in lines:
    s = ln.strip()
    if s.startswith("Tree "):
        if tl is not None: trees.append(build(tl))
        tl = []
    elif tl is not None and (s.startswith("If ") or s.startswith("Else ") or s.startswith("Predict:")):
        tl.append((len(ln) - len(ln.lstrip()), s if not s.startswith("Else") else "Else"))
trees.append(build(tl))
w = [float(x) for x in gbt.treeWeights]
assert len(trees) == len(w) == 40
model = {"features": feat_order, "categories": cats, "weights": w, "trees": trees,
         "threshold": meta["threshold"], "vocab": meta["vocab"], "champion": meta["champion"]}
(OUT / "model.json").write_text(json.dumps(model, separators=(",", ":")))

# parity fixtures: Spark probability for 300 real scored rows, for the JS check
feat = pd.read_parquet(ROOT / "data/lake/features_v2").query("day == '20261025'").sample(300, random_state=1)
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F
from features import cap_categoricals
sdf = cap_categoricals(spark.createDataFrame(feat.drop(columns=["themes_1h"]).assign(themes_1h=[list(x) for x in feat.themes_1h])), meta["vocab"])
sc = pm.transform(sdf).select("event_id", vector_to_array("probability")[1].alias("p")).toPandas().set_index("event_id").p
rows = []
for _, r in sdf.toPandas().iterrows():
    rows.append({"in": {k: (r[k].item() if hasattr(r[k], "item") else r[k]) for k in feat_order_cols} if False else None})
fx = sdf.toPandas()
cols = [c for c in meta["numeric"]] + meta["categorical"]
fixtures = [{"x": {c: (float(r[c]) if c in meta["numeric"] else str(r[c])) for c in cols}, "p": float(sc[r["event_id"]])}
            for _, r in fx.head(300).iterrows()]
(OUT / "parity_fixtures.json").write_text(json.dumps(fixtures))
print("model: trees", len(trees), "features", len(feat_order), "size KB", (OUT / "model.json").stat().st_size // 1024)

# ---------- snapshot ----------
sc_df = ds.dataset(str(ROOT / "data/serving/scored"), format="parquet").to_table().to_pandas()
latest = sc_df.t0.max()
win = sc_df[sc_df.t0 >= latest - pd.Timedelta(hours=36)].sort_values("score", ascending=False)
top = win.drop_duplicates("source_url").head(400)
top = top.assign(t0=top.t0.dt.strftime("%Y-%m-%d %H:%M"))
cols = ["t0", "source_url", "geo_name", "geo_country", "lat", "lon", "cameo_root", "goldstein", "avg_tone", "m_1h", "src_1h", "lang_1h", "score"]
ev = json.loads(top[cols].round({"score": 4, "goldstein": 1, "avg_tone": 1, "lat": 3, "lon": 3}).to_json(orient="records"))
w2 = win.assign(h=win.t0.dt.floor("1h"))
hourly = (w2.groupby("h").agg(n=("score", "size"), imp=("predicted_important", "sum"), mean=("score", "mean")).reset_index())
hourly["h"] = hourly.h.dt.strftime("%Y-%m-%d %H:00")
imp = win[win.predicted_important == 1]
tm = pd.read_csv(ROOT / "reports/artifacts/test_metrics.csv")
snap = {
    "as_of": str(latest), "window_hours": 36, "n_scored": int(len(win)), "n_flagged": int(len(imp)),
    "threshold": meta["threshold"], "champion": meta["champion"], "events": ev,
    "hourly": json.loads(hourly.round(4).to_json(orient="records")),
    "countries": imp.groupby("geo_country").size().sort_values(ascending=False).head(12).to_dict(),
    "types": imp.groupby("cameo_root").size().sort_values(ascending=False).head(10).to_dict(),
    "importance": meta["top_features"][:12],
    "metrics": json.loads(tm.round(4).to_json(orient="records")),
    "vs_baseline": json.loads((ROOT / "reports/artifacts/champion_vs_baseline.json").read_text()),
    "buckets": json.loads(pd.read_csv(ROOT / "reports/artifacts/by_first_hour_publishers.csv").round(4).to_json(orient="records")),
    "parity": json.loads((ROOT / "reports/artifacts/stream_parity.json").read_text()),
    "data_size": json.loads((ROOT / "reports/artifacts/data_size.json").read_text()),
}
(OUT / "snapshot.json").write_text(json.dumps(snap, separators=(",", ":")))
print("snapshot events", len(ev), "KB", (OUT / "snapshot.json").stat().st_size // 1024, "as_of", latest)
spark.stop()
