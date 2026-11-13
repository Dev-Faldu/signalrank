"""Kafka producer: publish GDELT 15-minute updates as JSON records.

replay mode : replays already-downloaded intervals from data/raw (fast, reproducible demo)
live mode   : polls GDELT's lastupdate.txt every 60 s and publishes each new interval

    python streaming/producer.py replay --start 20261025000000 --end 20261025060000 --interval-sec 2
    python streaming/producer.py live
"""
import argparse
import datetime as dt
import io
import json
import os
import pathlib
import time
import zipfile

import requests
from kafka import KafkaProducer

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE = "https://data.gdeltproject.org/gdeltv2"
TOPIC = os.environ.get("KAFKA_TOPIC", "gdelt.records")
BOOT = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")


def iso(s):
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:{s[12:14]}" if s and len(s) >= 14 else None


def fnum(x, cast=float):
    try:
        return cast(x)
    except (TypeError, ValueError):
        return None


def parse_events(text):
    for line in text.splitlines():
        c = line.split("\t")
        if len(c) < 61:
            continue
        yield {"t": "e", "event_id": fnum(c[0], int), "added_ts": iso(c[59]),
               "actor1_code": c[5] or None, "actor1_country": c[7] or None,
               "actor2_code": c[15] or None, "actor2_country": c[17] or None,
               "is_root_event": fnum(c[25], int), "cameo_code": c[26] or None, "cameo_root": c[28] or None,
               "quad_class": fnum(c[29], int), "goldstein": fnum(c[30]),
               "num_mentions_export": fnum(c[31], int), "num_sources_export": fnum(c[32], int),
               "avg_tone": fnum(c[34]), "geo_type": fnum(c[51], int), "geo_name": c[52] or None,
               "geo_country": c[53] or None, "lat": fnum(c[56]), "lon": fnum(c[57]), "source_url": c[60]}


def parse_mentions(text):
    import re
    for line in text.splitlines():
        c = line.split("\t")
        if len(c) < 15:
            continue
        m = re.search(r"srclc:([a-z]+)", c[14])
        yield {"t": "m", "event_id": fnum(c[0], int), "mention_ts": iso(c[2]), "source_name": c[4],
               "url": c[5], "confidence": fnum(c[11], int), "doc_len": fnum(c[12], int),
               "doc_tone": fnum(c[13]), "lang": m.group(1) if m else "eng"}


def parse_gkg(text):
    for line in text.splitlines():
        c = line.split("\t")
        if len(c) < 16:
            continue
        yield {"t": "g", "url": c[4], "gkg_ts": iso(c[1]),
               "themes": sorted(set(t for t in c[7].split(";") if t))}


PARSERS = {"export.CSV.zip": parse_events, "mentions.CSV.zip": parse_mentions, "gkg.csv.zip": parse_gkg}


def read_interval(stamp):
    out = []
    for suffix, parser in PARSERS.items():
        local = RAW / suffix.split(".")[0] / f"{stamp}.{suffix}"
        if local.exists():
            data = local.read_bytes()
        else:
            r = requests.get(f"{BASE}/{stamp}.{suffix}", timeout=60)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            data = r.content
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
        out.extend(parser(text))
    return out


def publish(prod, stamp):
    recs = read_interval(stamp)
    for r in recs:
        prod.send(TOPIC, json.dumps(r).encode())
    prod.flush()
    print(f"{stamp}: published {len(recs)} records", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["replay", "live"])
    ap.add_argument("--start"), ap.add_argument("--end")
    ap.add_argument("--interval-sec", type=float, default=2.0)
    a = ap.parse_args()
    prod = KafkaProducer(bootstrap_servers=BOOT, linger_ms=50, batch_size=1 << 18)
    if a.mode == "replay":
        t, end = (dt.datetime.strptime(x, "%Y%m%d%H%M%S") for x in (a.start, a.end))
        while t < end:
            publish(prod, t.strftime("%Y%m%d%H%M%S"))
            t += dt.timedelta(minutes=15)
            time.sleep(a.interval_sec)
    else:
        last = None
        while True:
            try:
                txt = requests.get(f"{BASE}/lastupdate.txt", timeout=30).text
                stamp = txt.split()[2].rsplit("/", 1)[-1][:14]
                if stamp != last:
                    publish(prod, stamp)
                    last = stamp
            except Exception as e:
                print("poll error:", e, flush=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
