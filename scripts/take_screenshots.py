"""Capture real screenshots of the running dashboard, API docs and MLflow UI (Playwright / Chromium)."""
import pathlib
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(__file__).resolve().parents[1] / "reports" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 980}, device_scale_factor=2)
    pg.goto("http://localhost:8501"); pg.wait_for_selector("text=what matters now", timeout=60000); pg.wait_for_timeout(4000)
    pg.screenshot(path=OUT / "dashboard_ranked.png")
    for name, f in (("Map", "dashboard_map"), ("Trends", "dashboard_trends")):
        pg.get_by_role("tab", name=name).click(); pg.wait_for_timeout(3500); pg.screenshot(path=OUT / f"{f}.png")
    pg.get_by_role("tab", name="Try an event").click(); pg.wait_for_timeout(1500)
    pg.get_by_role("button", name="Score this event").click(); pg.wait_for_selector("text=Importance score", timeout=90000); pg.wait_for_timeout(1500)
    pg.screenshot(path=OUT / "dashboard_try.png")
    pg2 = b.new_page(viewport={"width": 1280, "height": 1000}, device_scale_factor=2)
    pg2.goto("http://localhost:8000/docs"); pg2.wait_for_timeout(2500); pg2.screenshot(path=OUT / "api_docs.png")
    try:
        pg3 = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        pg3.goto("http://localhost:5000/#/experiments/1", timeout=30000); pg3.wait_for_timeout(5000); pg3.screenshot(path=OUT / "mlflow_runs.png")
    except Exception as e:
        print("mlflow shot skipped:", e)
    b.close()
print(sorted(x.name for x in OUT.iterdir()))
