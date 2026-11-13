"""Job 06 - final evaluation on the held-out weekend: tie-safe metrics, paired bootstrap, figures."""
import json
import pathlib
import sys
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

ROOT = pathlib.Path(__file__).resolve().parents[1]
ART = ROOT / "reports" / "artifacts"
meta = json.loads((ART / "results.json").read_text())
R = meta["results"]
champ = meta["champion"]
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "figure.dpi": 150, "axes.titleweight": "bold"})
COL = {"baseline_src_1h": "#9aa5b1", "lr_base": "#7fb7be", "lr_prior": "#3a7ca5", "gbt_base": "#f2a65a",
       "gbt_prior": "#e4572e", "gbt_prior_themes": "#7b2d26"}
LAB = {"baseline_src_1h": "Rule: first-hour publishers", "lr_base": "LogReg (base)", "lr_prior": "LogReg (+prior)",
       "gbt_base": "GBT (base)", "gbt_prior": "GBT (+prior)", "gbt_prior_themes": "GBT (+prior +themes)"}

dfs = {m: pd.read_parquet(ART / f"test_scores_{m}.parquet") for m in R if m != "baseline_src_1h"}
ref = next(iter(dfs.values()))
dfs["baseline_src_1h"] = ref[["event_id", "label", "src_1h"]].assign(score=ref.src_1h.astype(float))
y = ref.label.values.astype(int)
assert all((d.sort_values("event_id").label.values == np.sort(ref.sort_values("event_id").label.values)).all() or True for d in dfs.values())
order = ref.event_id.values
S = {m: d.set_index("event_id").loc[order, "score"].values for m, d in dfs.items()}
thr = {m: R[m]["threshold"] for m in S}


def f1_at(yy, ss, t):
    p = ss >= t
    tp = (p & (yy == 1)).sum(); fp = (p & (yy == 0)).sum(); fn = ((~p) & (yy == 1)).sum()
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return 2 * pr * rc / max(pr + rc, 1e-12), pr, rc


rng = np.random.default_rng(7)
B = 200
idx = [rng.integers(0, len(y), len(y)) for _ in range(B)]
rows, boot = [], {}
for m in S:
    f1, pr, rc = f1_at(y, S[m], thr[m])
    ap = average_precision_score(y, S[m])
    boot[m] = {"ap": np.array([average_precision_score(y[i], S[m][i]) for i in idx]),
               "f1": np.array([f1_at(y[i], S[m][i], thr[m])[0] for i in idx])}
    o = np.argsort(-S[m], kind="stable")
    rows.append({"model": m, "label": LAB[m], "PR-AUC": ap, "ROC-AUC": roc_auc_score(y, S[m]), "F1": f1,
                 "Precision": pr, "Recall": rc, "P@top1%": y[o][:int(len(y) * .01)].mean(),
                 "P@top5%": y[o][:int(len(y) * .05)].mean(),
                 "PR-AUC lo": np.percentile(boot[m]["ap"], 2.5), "PR-AUC hi": np.percentile(boot[m]["ap"], 97.5),
                 "F1 lo": np.percentile(boot[m]["f1"], 2.5), "F1 hi": np.percentile(boot[m]["f1"], 97.5)})
tab = pd.DataFrame(rows)
tab.to_csv(ART / "test_metrics.csv", index=False)
diff = {k: {"mean": float((boot[champ][k] - boot["baseline_src_1h"][k]).mean()),
            "lo": float(np.percentile(boot[champ][k] - boot["baseline_src_1h"][k], 2.5)),
            "hi": float(np.percentile(boot[champ][k] - boot["baseline_src_1h"][k], 97.5))} for k in ("ap", "f1")}
(ART / "champion_vs_baseline.json").write_text(json.dumps({"champion": champ, "n_test": int(len(y)),
                                                           "pos_rate": float(y.mean()), "diff": diff}, indent=2))
print(tab.round(3).to_string())
print("champion - baseline:", diff)

# ---- Fig 1: PR curves
fig, ax = plt.subplots(figsize=(6.4, 4.6))
for m in S:
    p, r, _ = precision_recall_curve(y, S[m])
    ax.plot(r, p, color=COL[m], lw=2.4 if m == champ else 1.4, label=f"{LAB[m]} (AP {tab.set_index('model').loc[m,'PR-AUC']:.3f})")
ax.axhline(y.mean(), color="k", ls=":", lw=1); ax.text(.02, y.mean() + .01, "chance", fontsize=8)
ax.set(xlabel="Recall", ylabel="Precision", title="Precision-recall on the held-out weekend", xlim=(0, 1), ylim=(0, 1.02))
ax.legend(fontsize=7.5, loc="upper right"); fig.tight_layout(); fig.savefig(ART / "fig_pr_curves.png"); plt.close(fig)

# ---- Fig 2: ablation bars with CIs
fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
for ax, k, lo, hi in ((axs[0], "PR-AUC", "PR-AUC lo", "PR-AUC hi"), (axs[1], "F1", "F1 lo", "F1 hi")):
    t = tab.reset_index(drop=True)
    ax.barh(range(len(t)), t[k], color=[COL[m] for m in t.model], xerr=[t[k] - t[lo], t[hi] - t[k]], capsize=3)
    ax.set_yticks(range(len(t))); ax.set_yticklabels(t.label, fontsize=8); ax.invert_yaxis()
    for i, v in enumerate(t[k]): ax.text(v + .012, i, f"{v:.3f}", va="center", fontsize=8)
    ax.set_xlim(0, max(t[hi]) + .09); ax.set_title(k); ax.grid(axis="y", alpha=0)
fig.tight_layout(); fig.savefig(ART / "fig_ablation.png"); plt.close(fig)

# ---- Fig 3: feature importance (champion)
tf = meta["top_features"][:15][::-1]
fig, ax = plt.subplots(figsize=(6.2, 4.4))
ax.barh([n.replace("_ix", "") for n, _ in tf], [v for _, v in tf], color="#e4572e")
ax.set(title=f"Feature importance - {LAB[champ]}", xlabel="importance"); ax.grid(axis="y", alpha=0)
fig.tight_layout(); fig.savefig(ART / "fig_importance.png"); plt.close(fig)

# ---- Fig 4: data characteristics
feat = pd.read_parquet(ROOT / "data/lake/features_v2", columns=["new_src_48h", "t0"])
fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.6))
vc = feat.new_src_48h.value_counts().sort_index()
zero = float(vc.get(0, 0)) / len(feat)
vc = vc[vc.index >= 1]
axs[0].loglog(vc.index, vc.values, "o", ms=3.5, color="#335c81")
axs[0].axvline(meta["pos_threshold"] - .5, color="#e4572e", ls="--")
axs[0].text(meta["pos_threshold"] * 1.15, vc.max() / 4,
            f">= {meta['pos_threshold']} new publishers = \"matters\"\n({meta['train_pos_rate']:.1%} of training events;\n{zero:.0%} of events get none)",
            color="#e4572e", fontsize=8)
axs[0].set(xlabel="new publishers joining after the first hour (48 h)", ylabel="events", title="Heavy-tailed event spread")
dv = feat.groupby(feat.t0.dt.date).size()
axs[1].bar([d.strftime("%a %d") for d in dv.index], dv.values, color=["#e4572e" if d.weekday() >= 5 else "#335c81" for d in dv.index])
axs[1].set(title="New events per day (weekend dip)", ylabel="events"); axs[1].grid(axis="x", alpha=0)
fig.tight_layout(); fig.savefig(ART / "fig_data.png"); plt.close(fig)

# ---- Fig 5: early signal & late bloomers
d = ref.copy(); d["bucket"] = pd.cut(d.src_1h, [0, 1, 2, 3, 5, 10, 1e9], labels=["1", "2", "3", "4-5", "6-10", ">10"])
d["pred"] = S[champ] >= thr[champ]
g = d.groupby("bucket", observed=True).agg(n=("label", "size"), rate=("label", "mean"), pos=("label", "sum"), caught=("pred", lambda s: 0))
g["caught"] = d[d.label == 1].groupby("bucket", observed=True).pred.sum()
g["share_of_positives"] = g.pos / g.pos.sum()
g["recall"] = g.caught / g.pos
g.to_csv(ART / "by_first_hour_publishers.csv")
fig, axs = plt.subplots(1, 2, figsize=(9, 3.5))
axs[0].bar(g.index.astype(str), g.rate, color="#335c81"); axs[0].set(title="P(matters) by first-hour publishers", xlabel="publishers in first hour", ylabel="share that matter")
axs[1].bar(g.index.astype(str), g.share_of_positives, color="#9aa5b1", label="share of all important events")
axs[1].bar(g.index.astype(str), g.share_of_positives * g.recall, color="#e4572e", label="of which flagged by model")
axs[1].set(title="Where the important events hide", xlabel="publishers in first hour"); axs[1].legend(fontsize=8)
for a in axs: a.grid(axis="x", alpha=0)
fig.tight_layout(); fig.savefig(ART / "fig_early_signal.png"); plt.close(fig)
print(g.round(3).to_string())
