"""Architecture diagram for the report / slides / README."""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = pathlib.Path(__file__).resolve().parent / "artifacts"
OUT.mkdir(exist_ok=True)
fig, ax = plt.subplots(figsize=(11.5, 5.6))
ax.set_xlim(0, 115); ax.set_ylim(0, 56); ax.axis("off")
C = {"src": "#e9eef5", "batch": "#dbe9f6", "stream": "#fde8df", "serve": "#e6f3e6", "ml": "#f3e8fa"}
EDGE = "#3b4a5a"


def box(x, y, w, h, title, sub="", c="src"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6", fc=C[c], ec=EDGE, lw=1.1))
    ax.text(x + w / 2, y + h * (.64 if sub else .5), title, ha="center", va="center", fontsize=9.5, fontweight="bold", color="#17212b")
    if sub:
        ax.text(x + w / 2, y + h * .27, sub, ha="center", va="center", fontsize=7.4, color="#3b4a5a")


def arrow(a, b, rad=0, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=11, lw=1.3, color=EDGE,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls))


ax.text(1, 54, "SignalRank - system architecture", fontsize=13, fontweight="bold", color="#17212b")
box(1, 22, 17, 14, "GDELT 2.0", "events | mentions | GKG\n15-minute zipped CSV", "src")
# batch lane
ax.text(24, 49, "BATCH LAYER (Spark)", fontsize=8.5, color="#335c81", fontweight="bold")
box(24, 38, 18, 9, "Parquet lake", "01_ingest: 11 GB -> 0.2 GB", "batch")
box(46, 38, 18, 9, "Features + label", "02_build_features", "batch")
box(68, 38, 18, 9, "Publisher prior", "02b out-of-fold encoding", "ml")
box(46, 26, 18, 9, "Train & compare", "03_train: LR | GBT (MLlib)", "ml")
box(68, 26, 18, 9, "MLflow", "tracking + model registry", "ml")
# stream lane
ax.text(24, 19.5, "STREAMING LAYER", fontsize=8.5, color="#c4552d", fontweight="bold")
box(24, 8, 18, 9, "Kafka", "topic gdelt.records", "stream")
box(46, 8, 22, 9, "Structured Streaming", "ripe events -> features -> score", "stream")
# serving
box(92, 30, 21, 9, "Scored-event store", "Parquet (data/serving)", "serve")
box(92, 17, 21, 9, "FastAPI", "/predict  /top  /stats  /model", "serve")
box(92, 4, 21, 9, "Streamlit dashboard", "What matters now", "serve")
arrow((18, 31), (24, 42.5)); arrow((42, 42.5), (46, 42.5)); arrow((64, 42.5), (68, 42.5))
arrow((55, 38), (55, 35)); arrow((77, 38), (77, 35), ); arrow((64, 30.5), (68, 30.5))
arrow((18, 27), (24, 13)); arrow((42, 12.5), (46, 12.5))
arrow((68, 12.5), (92, 33), rad=-.25); arrow((86, 28), (92, 22), rad=0)
arrow((74, 26), (62, 17.3), rad=.25, ls="--")
ax.text(72.5, 20, "champion model", fontsize=7, color="#3b4a5a")
arrow((102.5, 30), (102.5, 26)); arrow((102.5, 17), (102.5, 13))
ax.text(86, 2, "Airflow DAG schedules the batch layer; Docker Compose runs Kafka, MLflow, API, UI, scorer.", fontsize=7.4, color="#3b4a5a", ha="right")
fig.savefig(OUT / "fig_architecture.png", dpi=170, bbox_inches="tight", facecolor="white")
