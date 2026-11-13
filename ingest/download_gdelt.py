"""Download GDELT 2.0 15-minute files (export / mentions / gkg) for a time window.

Resumable (skips files that already exist), parallel, polite retries.

    python ingest/download_gdelt.py --start 2026-10-20 --days 7 --out data/raw
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import pathlib
import sys
import time

import requests

BASE = "https://data.gdeltproject.org/gdeltv2"
KINDS = {"export": "export.CSV.zip", "mentions": "mentions.CSV.zip", "gkg": "gkg.csv.zip"}


def stamps(start: dt.datetime, days: int):
    t = start
    end = start + dt.timedelta(days=days)
    while t < end:
        yield t.strftime("%Y%m%d%H%M%S")
        t += dt.timedelta(minutes=15)


def fetch(session, kind, stamp, out: pathlib.Path):
    dest = out / kind / f"{stamp}.{KINDS[kind]}"
    if dest.exists() and dest.stat().st_size > 0:
        return "skip", 0
    url = f"{BASE}/{stamp}.{KINDS[kind]}"
    for attempt in range(4):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 404:
                return "missing", 0  # GDELT occasionally skips an interval
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.rename(dest)
            return "ok", len(r.content)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return "fail", 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    start = dt.datetime.strptime(a.start, "%Y-%m-%d")
    jobs = [(k, s) for s in stamps(start, a.days) for k in KINDS]
    stats = {"ok": 0, "skip": 0, "missing": 0, "fail": 0}
    nbytes = 0
    t0 = time.time()
    with requests.Session() as sess, cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(fetch, sess, k, s, out) for k, s in jobs]
        for i, f in enumerate(cf.as_completed(futs), 1):
            st, n = f.result()
            stats[st] += 1
            nbytes += n
            if i % 200 == 0 or i == len(futs):
                print(f"{i}/{len(futs)} {stats} {nbytes/1e9:.2f} GB zipped "
                      f"{time.time()-t0:.0f}s", flush=True)
    print("done", stats)
    sys.exit(1 if stats["fail"] else 0)


if __name__ == "__main__":
    main()
