import pytest

pyspark = pytest.importorskip("pyspark")


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false")
         .config("spark.sql.shuffle.partitions", "2").config("spark.sql.session.timeZone", "UTC").getOrCreate())
    yield s
    s.stop()


def test_cap_categoricals_and_fill(spark):
    from features import cap_categoricals, NUMERIC, CATEGORICAL
    row = {c: 1.0 for c in NUMERIC}
    row.update({c: "RARE" for c in CATEGORICAL}); row["tone_std_1h"] = float("nan")
    df = spark.createDataFrame([row])
    out = cap_categoricals(df, {c: ["US"] for c in CATEGORICAL}).first()
    assert all(out[c] == "OTHER" for c in CATEGORICAL) and out["tone_std_1h"] == 0.0


def test_early_features_window_and_counts(spark):
    """Mentions after the 60-minute cut-off must not leak into the features."""
    import datetime as dt
    from early import dedupe_events, with_offsets, early_features
    t0 = dt.datetime(2026, 10, 20, 12, 0)
    ddl = ("event_id long, added_ts timestamp, actor1_code string, actor1_country string, actor2_code string, "
           "actor2_country string, is_root_event int, cameo_root string, cameo_code string, quad_class int, "
           "goldstein double, num_mentions_export int, num_sources_export int, avg_tone double, geo_type int, "
           "geo_name string, geo_country string, lat double, lon double, source_url string")
    ev = spark.createDataFrame([dict(event_id=1, added_ts=t0, actor1_code=None, actor1_country="US", actor2_code=None,
                                     actor2_country=None, is_root_event=1, cameo_root="14", cameo_code="141", quad_class=3,
                                     goldstein=-2.0, num_mentions_export=1, num_sources_export=1, avg_tone=-1.0, geo_type=3,
                                     geo_name="X", geo_country="US", lat=1.0, lon=1.0, source_url="u")], schema=ddl)
    mk = lambda mins, src, lang="eng": dict(event_id=1, mention_ts=t0 + dt.timedelta(minutes=mins), source_name=src,
                                              url=f"http://{src}/{mins}", confidence=80, doc_len=1000, doc_tone=-1.0, lang=lang)
    mn = spark.createDataFrame([mk(5, "a"), mk(20, "b", "fra"), mk(59, "a"), mk(61, "c"), mk(300, "d")])
    gk = spark.createDataFrame([("http://a/5", ["T1", "T2"])], ["url", "themes"])
    m = with_offsets(mn, dedupe_events(ev), 48 * 60)
    r = early_features(dedupe_events(ev), m, gk).first()
    assert r["m_1h"] == 3 and r["src_1h"] == 2 and r["m_15m"] == 1 and r["nonen_1h"] == 1
    assert sorted(r["themes_1h"]) == ["T1", "T2"]
