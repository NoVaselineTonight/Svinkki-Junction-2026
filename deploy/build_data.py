"""Build the demo database for a hosted copy of Svinkki, from the organisers' public dataset.

    python -m deploy.build_data --out data/svinkki.db [--pool 300] [--source-dir DIR] [--keep-work]

The challenge dataset is not stored in this repository. This script fetches it from the organisers' public
repository (https://github.com/hackjunction/Junction-2026-S-pankki ; the transactions file comes from Git LFS
and is checked against the size and SHA-256 in its pointer), leaves out the customers listed in
deploy/removed_customers.txt exactly as the team's own copy does, runs the normal `app.ingest`, and then slims
the result: the six demo customers and `--pool` customers for the "Try as a random customer" login keep their
transactions, everyone else's are removed. Group statistics (the `bench` tables) are computed from ALL
customers before the slimming, so comparisons are the same as on the full database.

`--source-dir` uses CSV files already on disk (the organisers' unfiltered files) instead of downloading.
`--pool 0` keeps every customer (about 540 MB instead of about 40 MB).
Standard library only. Needs about 1.2 GB of free disk while it runs.
"""
import argparse
import hashlib
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request

REPO = "hackjunction/Junction-2026-S-pankki"
BRANCH = "main"
RAW = "https://raw.githubusercontent.com/%s/%s/" % (REPO, BRANCH)
LFS = "https://media.githubusercontent.com/media/%s/%s/" % (REPO, BRANCH)
TX = "tx_junction_transactions.csv"
CUSTOMERS = "tx_customers_junction.csv"
MTG_LINK = "mtg_tx_customer_link_and_final_mtg_infio.csv"
MTG_HISTORY = "mtg_negotiation_history.csv"
SMALL = (CUSTOMERS, MTG_LINK, MTG_HISTORY)
HERE = os.path.dirname(os.path.abspath(__file__))
POOL_SEED = 2026


def log(msg):
    print("[build_data] " + msg, flush=True)


def removed_ids():
    out = set()
    with open(os.path.join(HERE, "removed_customers.txt"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line)
    return out


def _get(url, dest, expect_size=None, expect_sha256=None, tries=3):
    """Download url to dest (streamed). Checks size and SHA-256 when given. Raises on any mismatch."""
    last = None
    for attempt in range(1, tries + 1):
        try:
            h = hashlib.sha256()
            n = 0
            req = urllib.request.Request(url, headers={"User-Agent": "svinkki-demo-build"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    h.update(chunk)
                    n += len(chunk)
            if expect_size is not None and n != expect_size:
                raise IOError("size %d, expected %d" % (n, expect_size))
            if expect_sha256 is not None and h.hexdigest() != expect_sha256:
                raise IOError("checksum mismatch")
            return n
        except Exception as e:  # noqa: BLE001
            last = e
            log("download failed (%s), attempt %d of %d: %s" % (os.path.basename(dest), attempt, tries, type(e).__name__))
            time.sleep(3 * attempt)
    raise SystemExit("[build_data] could not download %s: %s" % (url, last))


def parse_pointer(text):
    """(sha256, size) from a Git LFS pointer file, or None when the text is not a pointer."""
    oid = size = None
    for line in text.splitlines():
        if line.startswith("oid sha256:"):
            oid = line.split(":", 1)[1].strip()
        elif line.startswith("size "):
            try:
                size = int(line.split()[1])
            except ValueError:
                return None
    return (oid, size) if oid and size else None


def fetch(work):
    """The organisers' four CSV files into `work`. Returns the folder."""
    src = os.path.join(work, "source")
    os.makedirs(src, exist_ok=True)
    for name in SMALL:
        n = _get(RAW + name, os.path.join(src, name))
        log("fetched %s (%s bytes)" % (name, format(n, ",")))
    ptr_path = os.path.join(src, TX + ".pointer")
    _get(RAW + TX, ptr_path)
    with open(ptr_path, encoding="utf-8", errors="replace") as f:
        ptr = parse_pointer(f.read(2000))
    if ptr is None:       # the file is in plain git after all
        os.replace(ptr_path, os.path.join(src, TX))
        log("fetched %s (plain file)" % TX)
    else:
        os.remove(ptr_path)
        log("fetching %s from Git LFS (%s bytes)" % (TX, format(ptr[1], ",")))
        _get(LFS + TX, os.path.join(src, TX), expect_size=ptr[1], expect_sha256=ptr[0])
        log("fetched and verified %s" % TX)
    return src


def _first_field(line):
    return line.split(",", 1)[0].strip().strip('"').lstrip("﻿")


def filter_dataset(src, dst, removed):
    """Copy the dataset from src to dst without the removed customers (and their mortgage applications)."""
    os.makedirs(dst, exist_ok=True)
    counts = {}
    for name in (CUSTOMERS, TX):          # customer id is the first column
        kept = dropped = 0
        with open(os.path.join(src, name), encoding="utf-8", newline="") as fin, \
                open(os.path.join(dst, name), "w", encoding="utf-8", newline="") as fout:
            fout.write(fin.readline())    # header, byte order mark included
            for line in fin:
                if _first_field(line) in removed:
                    dropped += 1
                else:
                    fout.write(line)
                    kept += 1
        counts[name] = (kept, dropped)
    import csv
    keep_mtg = set()
    with open(os.path.join(src, MTG_LINK), encoding="utf-8-sig", newline="") as fin, \
            open(os.path.join(dst, MTG_LINK), "w", encoding="utf-8-sig", newline="") as fout:
        rd = csv.DictReader(fin)
        wr = csv.DictWriter(fout, fieldnames=rd.fieldnames, lineterminator="\n")
        wr.writeheader()
        kept = dropped = 0
        for row in rd:
            if row.get("customer_id") in removed:
                dropped += 1
            else:
                wr.writerow(row)
                keep_mtg.add(row.get("mortgage_customer_id"))
                kept += 1
        counts[MTG_LINK] = (kept, dropped)
    with open(os.path.join(src, MTG_HISTORY), encoding="utf-8-sig", newline="") as fin, \
            open(os.path.join(dst, MTG_HISTORY), "w", encoding="utf-8-sig", newline="") as fout:
        rd = csv.DictReader(fin)
        wr = csv.DictWriter(fout, fieldnames=rd.fieldnames, lineterminator="\n")
        wr.writeheader()
        kept = dropped = 0
        for row in rd:
            if row.get("mortgage_customer_id") in keep_mtg:
                wr.writerow(row)
                kept += 1
            else:
                dropped += 1
        counts[MTG_HISTORY] = (kept, dropped)
    for name, (kept, dropped) in counts.items():
        log("filtered %s: %s rows kept, %s left out" % (name, format(kept, ","), format(dropped, ",")))
    return counts


def slim(db_path, pool):
    """Keep the transactions of the six demo customers and `pool` random-login customers; remove the rest.
    The group statistics stay as they were computed from everyone."""
    conn = sqlite3.connect(db_path)
    try:
        personas = [r[0] for r in conn.execute("SELECT cid FROM personas ORDER BY rowid")]
        everyone = sorted(r[0] for r in conn.execute("SELECT cid FROM demo_pool"))
        rest = [c for c in everyone if c not in set(personas)]
        chosen = random.Random(POOL_SEED).sample(rest, min(pool, len(rest)))
        keep = set(personas) | set(chosen)
        conn.execute("CREATE TEMP TABLE keep (cid TEXT PRIMARY KEY)")
        conn.executemany("INSERT INTO keep VALUES (?)", [(c,) for c in sorted(keep)])
        before = conn.execute("SELECT COUNT(*) FROM tx").fetchone()[0]
        conn.execute("DELETE FROM tx WHERE cid NOT IN (SELECT cid FROM keep)")
        conn.execute("DELETE FROM customers WHERE cid NOT IN (SELECT cid FROM keep)")
        conn.execute("DELETE FROM demo_pool WHERE cid NOT IN (SELECT cid FROM keep)")
        after = conn.execute("SELECT COUNT(*) FROM tx").fetchone()[0]
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('slim', ?)",
                     ("%d demo customers and %d random-login customers kept of %d; statistics from all" % (
                         len(personas), len(chosen), len(everyone)),))
        conn.commit()
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()
    log("slimmed: %s of %s transaction rows kept (%d customers), %.0f MB" % (
        format(after, ","), format(before, ","), len(keep), os.path.getsize(db_path) / 1e6))
    return len(keep)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m deploy.build_data", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("data", "svinkki.db"))
    ap.add_argument("--pool", type=int, default=int(os.environ.get("SVINKKI_DEMO_POOL", "300")),
                    help="random-login customers to keep; 0 keeps everyone")
    ap.add_argument("--source-dir", default=None, help="the organisers' CSV files, already on disk")
    ap.add_argument("--fetch-only", default=None, metavar="DIR",
                    help="only download the organisers' files into DIR (for a cached build step), then stop")
    ap.add_argument("--keep-work", action="store_true", help="do not delete the working folder")
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.fetch_only:
        dest = os.path.abspath(args.fetch_only)
        os.makedirs(dest, exist_ok=True)
        src = fetch(dest)
        for name in os.listdir(src):          # the files themselves, directly in DIR
            os.replace(os.path.join(src, name), os.path.join(dest, name))
        os.rmdir(src)
        log("dataset fetched into %s in %.0f s" % (dest, time.time() - t0))
        return 0
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    work = tempfile.mkdtemp(prefix="svinkki_build_", dir=os.path.dirname(out))
    try:
        src = os.path.abspath(args.source_dir) if args.source_dir else fetch(work)
        filtered = os.path.join(work, "filtered")
        filter_dataset(src, filtered, removed_ids())
        sys.path.insert(0, os.path.dirname(HERE))
        from app import ingest
        os.environ.setdefault("SVINKKI_ENV_FILE", os.path.join(work, "no.env"))
        log("building the database (the usual app.ingest)")
        rc = ingest.main(["--data-dir", filtered, "--out", out])
        if rc:
            raise SystemExit("[build_data] ingest failed with code %s" % rc)
        if args.pool > 0:
            slim(out, args.pool)
    finally:
        if not args.keep_work:
            shutil.rmtree(work, ignore_errors=True)
    conn = sqlite3.connect(out)
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM personas ORDER BY rowid")]
        n_tx = conn.execute("SELECT COUNT(*) FROM tx").fetchone()[0]
    finally:
        conn.close()
    log("done in %.0f s: %s, %s rows, demo customers: %s" % (time.time() - t0, out, format(n_tx, ","), ", ".join(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
