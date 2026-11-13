import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "spark_jobs", ROOT / "streaming", ROOT / "api"):
    sys.path.insert(0, str(p))
