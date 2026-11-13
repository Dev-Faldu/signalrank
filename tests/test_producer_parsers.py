import producer as P


def _row(n, **at):
    r = [""] * n
    for k, v in at.items():
        r[int(k[1:])] = v
    return "\t".join(r)


def test_parse_events():
    line = _row(61, c0="123", c5="USAGOV", c7="USA", c25="1", c26="190", c28="19", c29="4", c30="-10.0",
                c31="3", c32="1", c33="3", c34="-7.9", c51="3", c52="Senatobia, Mississippi, United States",
                c53="US", c56="34.6", c57="-89.9", c59="20261020000000", c60="https://example.com/a")
    (e,) = list(P.parse_events(line))
    assert e["event_id"] == 123 and e["cameo_root"] == "19" and e["goldstein"] == -10.0
    assert e["added_ts"] == "2026-10-20 00:00:00" and e["geo_country"] == "US" and e["lat"] == 34.6


def test_parse_events_skips_short_rows():
    assert list(P.parse_events("a\tb\tc")) == []


def test_parse_mentions_language():
    en = _row(16, c0="1", c2="20261020000000", c4="cnn.com", c5="https://cnn.com/x", c11="80", c12="3000", c13="1.5")
    fr = _row(16, c0="1", c2="20261020000000", c4="lemonde.fr", c5="https://lemonde.fr/x", c14="srclc:fra; eng:Moses 2.0")
    a, b = list(P.parse_mentions(en + "\n" + fr))
    assert a["lang"] == "eng" and b["lang"] == "fra" and a["doc_tone"] == 1.5


def test_parse_gkg_themes_deduped():
    line = _row(27, c1="20261020000000", c4="https://x.com/a", c7="TAX;WB_1;TAX;")
    (g,) = list(P.parse_gkg(line))
    assert g["themes"] == ["TAX", "WB_1"] and g["url"] == "https://x.com/a"
