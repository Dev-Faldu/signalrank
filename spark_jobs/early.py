"""Single implementation of the early-coverage feature logic.

Used by the batch job (02_build_features.py) and by the streaming scorer, so a
model sees exactly the same feature definitions offline and online.
"""
from pyspark.sql import functions as F

from features import EARLY_MIN, HORIZON_H

EVENT_COLS = ["actor1_code", "actor1_country", "actor2_code", "actor2_country", "is_root_event",
              "cameo_root", "cameo_code", "quad_class", "goldstein", "num_mentions_export",
              "num_sources_export", "avg_tone", "geo_type", "geo_name", "geo_country", "lat", "lon",
              "source_url"]


def dedupe_events(ev):
    """One row per event, anchored (t0) at first appearance in GDELT."""
    return ev.groupBy("event_id").agg(
        F.min("added_ts").alias("t0"),
        *[F.first(c, ignorenulls=True).alias(c) for c in EVENT_COLS])


def with_offsets(mn, ev, horizon_min):
    return (mn.join(ev.select("event_id", "t0"), "event_id")
              .withColumn("dt_min", (F.col("mention_ts").cast("long") - F.col("t0").cast("long")) / 60.0)
              .where((F.col("dt_min") >= 0) & (F.col("dt_min") < horizon_min))
              .withColumn("src", F.col("source_name")))


def early_features(ev, m, gk):
    """ev: deduped events (with t0); m: mentions with dt_min in [0, horizon); gk: gkg(url, themes)."""
    early = m.where(F.col("dt_min") < EARLY_MIN)
    feat = early.groupBy("event_id").agg(
        F.count("*").alias("m_1h"),
        F.sum((F.col("dt_min") < 15).cast("int")).alias("m_15m"),
        F.countDistinct("src").alias("src_1h"),
        F.countDistinct("lang").alias("lang_1h"),
        F.sum((F.col("lang") != "eng").cast("int")).alias("nonen_1h"),
        F.countDistinct("url").alias("art_1h"),
        F.avg("doc_tone").alias("tone_mean_1h"),
        F.coalesce(F.stddev("doc_tone"), F.lit(0.0)).alias("tone_std_1h"),
        F.avg("confidence").alias("conf_mean_1h"),
        F.avg("doc_len").alias("doclen_mean_1h"))
    th = (early.select("event_id", "url").dropDuplicates().join(gk, "url", "left")
          .groupBy("event_id")
          .agg(F.array_distinct(F.flatten(F.collect_list("themes"))).alias("themes_1h")))
    df = (ev.join(feat, "event_id").join(th, "event_id", "left")
            .withColumn("themes_1h", F.coalesce("themes_1h", F.array().cast("array<string>")))
            .withColumn("themes_1h", F.expr("filter(themes_1h, x -> x != '')"))
            .withColumn("n_themes_1h", F.size("themes_1h"))
            .withColumn("has_actor1_country", (F.coalesce("actor1_country", F.lit("")) != "").cast("int"))
            .withColumn("has_actor2_country", (F.coalesce("actor2_country", F.lit("")) != "").cast("int"))
            .withColumn("has_geo", (F.coalesce("geo_country", F.lit("")) != "").cast("int"))
            .withColumn("cameo_root", F.coalesce("cameo_root", F.lit("NA")))
            .withColumn("geo_country", F.coalesce("geo_country", F.lit("NA")))
            .withColumn("actor1_country", F.coalesce("actor1_country", F.lit("NA")))
            .withColumn("is_root_event", F.coalesce("is_root_event", F.lit(0))))
    return df


def label_table(m):
    """Spread after the early window: publishers that were NOT among the first-hour publishers."""
    early_src = m.where(F.col("dt_min") < EARLY_MIN).select("event_id", "src").dropDuplicates()
    late_src = m.where(F.col("dt_min") >= EARLY_MIN).select("event_id", "src").dropDuplicates()
    new_src = (late_src.join(early_src, ["event_id", "src"], "left_anti")
               .groupBy("event_id").agg(F.count("*").alias("new_src_48h")))
    tot = m.groupBy("event_id").agg(F.count("*").alias("m_48h"), F.countDistinct("src").alias("src_48h"),
                                    F.countDistinct("lang").alias("lang_48h"))
    return tot.join(new_src, "event_id", "left").fillna({"new_src_48h": 0})


def add_publisher_prior(feats, m, prior, g):
    """Serving-time version of the publisher-reach prior (final table from all training days)."""
    p = prior.select(F.col("src").alias("psrc"), F.col("prior"), F.col("known"))
    pp = (m.where(F.col("dt_min") < EARLY_MIN).select("event_id", "src").dropDuplicates()
          .join(p, F.col("src") == F.col("psrc"), "left")
          .groupBy("event_id").agg(F.avg(F.coalesce("prior", F.lit(g))).alias("pub_prior_mean"),
                                   F.max(F.coalesce("prior", F.lit(g))).alias("pub_prior_max"),
                                   F.avg(F.coalesce("known", F.lit(0)).cast("double")).alias("pub_known_frac")))
    return feats.join(pp, "event_id", "left").fillna({"pub_prior_mean": g, "pub_prior_max": g, "pub_known_frac": 0.0})
