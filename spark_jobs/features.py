"""Feature definitions shared by the batch job, the streaming scorer and the API.

Early-coverage features only use information available within EARLY_MIN minutes
of the event first appearing in GDELT. The label (see 02_build_features.py) uses
the following 48 hours.
"""
EARLY_MIN = 60
HORIZON_H = 48
HASH_DIM = 256

NUMERIC = [
    "m_1h", "m_15m", "src_1h", "lang_1h", "nonen_1h", "art_1h",
    "tone_mean_1h", "tone_std_1h", "conf_mean_1h", "doclen_mean_1h",
    "goldstein", "avg_tone", "quad_class", "is_root_event", "geo_type",
    "has_actor1_country", "has_actor2_country", "has_geo",
    "num_mentions_export", "num_sources_export", "n_themes_1h",
]
CATEGORICAL = ["cameo_root", "geo_country", "actor1_country"]
THEMES_COL = "themes_1h"

LABEL_COL = "new_src_48h"   # distinct NEW publishers picking the story up after the first hour (hours 1-48)
POS_THRESHOLD = 3          # "matters" = at least 3 new publishers join after the early window
TRAIN_DAYS = ["20261020", "20261021", "20261022"]
VAL_DAYS = ["20261023"]
TEST_DAYS = ["20261024", "20261025"]   # weekend -> deliberate distribution shift
TOP_CATS = 40


def cap_categoricals(df, vocab):
    """Map rare category values to OTHER (vocab learned on the training split only)."""
    from pyspark.sql import functions as F
    for c in CATEGORICAL:
        df = df.withColumn(c, F.when(F.col(c).isin(vocab[c]), F.col(c)).otherwise(F.lit("OTHER")))
    # MLlib rejects NaN/null: missing numerics (e.g. tone with no scored article) -> 0
    return df.fillna(0.0, subset=[c for c in NUMERIC if c in df.columns])

PRIOR_K = 20               # smoothing strength of the publisher-reach prior
NUMERIC_PRIOR = ["pub_prior_mean", "pub_prior_max", "pub_known_frac"]
