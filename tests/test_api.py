import pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "models/champion/meta.json").exists(), reason="train the model first")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and "model" in r


def test_predict_is_monotone_in_first_hour_publishers(client):
    lo = client.post("/predict", json={"src_1h": 1, "m_1h": 1, "m_15m": 1}).json()["score"]
    hi = client.post("/predict", json={"src_1h": 25, "m_1h": 60, "m_15m": 30, "lang_1h": 6}).json()["score"]
    assert 0 <= lo < hi <= 1


def test_predict_validation(client):
    assert client.post("/predict", json={"quad_class": 9}).status_code == 422


def test_batch_and_top(client):
    r = client.post("/predict/batch", json=[{"src_1h": 1}, {"src_1h": 30, "m_1h": 80}])
    assert r.status_code == 200 and len(r.json()) == 2
    t = client.get("/top", params={"n": 5})
    if t.status_code == 200:
        ev = t.json()["events"]
        assert len(ev) <= 5 and all(a["score"] >= b["score"] for a, b in zip(ev, ev[1:]))
