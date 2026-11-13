"""Read-only access to the built database and the per-customer sandbox.

Isolation (SR-2, SR-8): `sandbox()` copies ONE customer's rows (never after `today`) into a fresh
in-memory database. Everything the app and the model run happens on that copy, so other customers'
rows are physically absent. `safe_select()` additionally restricts what SQL may run there.
"""
from __future__ import annotations

import os
import random
import re
import sqlite3
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_DB = "data/svinkki.db"

SANDBOX_COLUMNS = ("d", "ts", "amount", "balance", "type", "category", "mcc", "merchant",
                   "label", "basket", "context")


def data_db_path() -> str:
    try:
        from app import config  # type: ignore
        return str(config.db_path())
    except Exception:
        p = os.environ.get("SVINKKI_DB") or _DEFAULT_DB
        pp = Path(p)
        return str(pp if pp.is_absolute() else _REPO / pp)


def _ro() -> sqlite3.Connection:
    """Open the built database read-only (a fresh connection per call)."""
    path = Path(data_db_path()).resolve()
    if not path.exists():
        raise FileNotFoundError("database not built: run python -m app.ingest")
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def list_personas() -> list[dict]:
    conn = _ro()
    try:
        rows = conn.execute("SELECT cid, name, blurb FROM personas ORDER BY rowid").fetchall()
        return [{"cid": r["cid"], "name": r["name"], "blurb": r["blurb"]} for r in rows]
    finally:
        conn.close()


def customer_exists(cid) -> bool:
    if not isinstance(cid, str) or not cid:
        return False
    conn = _ro()
    try:
        return conn.execute("SELECT 1 FROM customers WHERE cid = ?", (cid,)).fetchone() is not None
    finally:
        conn.close()


def profile(cid) -> dict:
    """Coarse profile only: age band and postal area. No exact age, no postal code."""
    conn = _ro()
    try:
        r = conn.execute("SELECT age_band, area FROM customers WHERE cid = ?", (cid,)).fetchone()
        if r is None:
            return {"age_band": "", "area": ""}
        return {"age_band": r["age_band"] or "", "area": r["area"] or ""}
    finally:
        conn.close()


def _apply_overrides(mem, overrides) -> None:
    """Apply the customer's remembered categories to the in-memory copy (before it turns read-only).
    Merchant overrides first, then single-transaction overrides, so the more specific one wins."""
    from app import classify
    ordered = sorted((o for o in overrides if isinstance(o, dict)),
                     key=lambda o: (0 if o.get("scope") == "merchant" else 1, o.get("id") or 0))
    for o in ordered:
        label = o.get("label")
        if label not in classify.ALL_LABELS:
            continue
        context = o.get("context") or ""
        if context not in ("", "night_out"):
            context = ""
        if o.get("scope") == "tx" and isinstance(o.get("tx_id"), int):
            rows = mem.execute("SELECT id, type, category, amount FROM tx WHERE id = ?",
                               (o["tx_id"],)).fetchall()
        elif o.get("scope") == "merchant" and o.get("merchant"):
            rows = mem.execute("SELECT id, type, category, amount FROM tx WHERE merchant = ?",
                               (o["merchant"],)).fetchall()
        else:
            continue
        for rid, typ, cat, amount in rows:
            basket = o.get("basket") or classify.basket_for(typ, label, cat, amount)
            mem.execute("UPDATE tx SET label = ?, basket = ?, context = ? WHERE id = ?",
                        (label, basket, context, rid))


def sandbox(cid, today: str, overrides=None) -> sqlite3.Connection:
    """In-memory database with table `tx` holding only this customer's rows with d <= today.

    The extra integer column `id` (last) is the row's rowid in the main table. `overrides` (the
    customer's remembered categories, from app.state.list_overrides) are applied before the
    connection becomes read-only."""
    cols = ", ".join(SANDBOX_COLUMNS)
    src = _ro()
    try:
        rows = src.execute(
            f"SELECT {cols}, rowid FROM tx WHERE cid = ? AND d <= ? ORDER BY ts, rowid",
            (cid, str(today))).fetchall()
    finally:
        src.close()
    mem = sqlite3.connect(":memory:", check_same_thread=False)
    mem.execute(
        "CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, "
        "mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
    mem.executemany(f"INSERT INTO tx VALUES ({', '.join('?' * (len(SANDBOX_COLUMNS) + 1))})",
                    [tuple(r) for r in rows])
    mem.execute("CREATE INDEX tx_d ON tx(d)")
    mem.execute("CREATE INDEX tx_id ON tx(id)")
    if overrides:
        _apply_overrides(mem, overrides)
    mem.commit()
    mem.execute("PRAGMA query_only = ON")   # the sandbox is read-only from here on
    mem.row_factory = sqlite3.Row
    return mem


def tx_merchant(cid, tx_id):
    """Merchant id of ONE of this customer's own transactions, or None when the row does not exist
    or belongs to someone else. For server-side use only: it never goes to a client or a model."""
    if isinstance(tx_id, bool) or not isinstance(tx_id, int):
        return None
    conn = _ro()
    try:
        r = conn.execute("SELECT merchant FROM tx WHERE rowid = ? AND cid = ?",
                         (tx_id, cid)).fetchone()
        if r is None:
            return None
        return r["merchant"] or None
    finally:
        conn.close()


def postal_code(cid):
    """The customer's postal code, for the area lookup only (never shown to a model)."""
    conn = _ro()
    try:
        r = conn.execute("SELECT postal FROM customers WHERE cid = ?", (cid,)).fetchone()
        return (r["postal"] or None) if r is not None else None
    finally:
        conn.close()


def bench(group_keys: list[str], metric: str) -> dict | None:
    """First group in `group_keys` that has statistics for `metric` (n >= 20 by construction)."""
    conn = _ro()
    try:
        for key in group_keys:
            r = conn.execute(
                "SELECT group_key, n, p25, median, p75, mean FROM bench "
                "WHERE group_key = ? AND metric = ? AND n >= 20", (key, metric)).fetchone()
            if r is not None:
                return {k: r[k] for k in ("group_key", "n", "p25", "median", "p75", "mean")}
        return None
    finally:
        conn.close()


def bench_meta(metric: str | None = None):
    """Catalogue of bench metrics: one {metric, name, unit, description} (None if unknown), or the
    full list when called without an argument."""
    conn = _ro()
    try:
        cols = "metric, name, unit, description"
        if metric is not None:
            r = conn.execute(f"SELECT {cols} FROM bench_meta WHERE metric = ?", (metric,)).fetchone()
            return None if r is None else {k: r[k] for k in r.keys()}
        return [{k: r[k] for k in r.keys()}
                for r in conn.execute(f"SELECT {cols} FROM bench_meta ORDER BY metric")]
    finally:
        conn.close()


def bench_many(group_keys: list[str], metrics: list[str]) -> dict:
    """{metric: {group_key, n, p25, median, p75, mean}} using, per metric, the first group in
    `group_keys` that has it. Metrics with no group are left out."""
    conn = _ro()
    try:
        out = {}
        for metric in metrics:
            for key in group_keys:
                r = conn.execute(
                    "SELECT group_key, n, p25, median, p75, mean FROM bench "
                    "WHERE group_key = ? AND metric = ? AND n >= 20", (key, metric)).fetchone()
                if r is not None:
                    out[metric] = {k: r[k] for k in ("group_key", "n", "p25", "median", "p75", "mean")}
                    break
        return out
    finally:
        conn.close()


def customer_metrics(conn, today) -> dict:
    """The per-customer metrics of one sandbox connection, computed by the same function the
    ingest pass uses (app.ingest.compute_metrics), so they compare directly with `bench`."""
    from app import ingest
    rows = conn.execute("SELECT d, ts, amount, balance, type, label, basket, context FROM tx "
                        "ORDER BY ts, rowid").fetchall()
    res = ingest.compute_metrics([tuple(r) for r in rows], str(today))
    out = dict(res["metrics"])
    if res["months"]:
        for lab in ingest.classify.ALL_LABELS:   # absent zero-fill metrics mean 0
            for fam in ("label:", "visits:", "users:"):
                if lab not in ingest.NON_SPENDING_LABELS:
                    out.setdefault(fam + lab, 0.0)
        for m in ("income", "regular", "unexpected", "everyday", "savings", "night_out"):
            out.setdefault(m, 0.0)
    return out


def demo_pool_size() -> int:
    conn = _ro()
    try:
        return conn.execute("SELECT COUNT(*) FROM demo_pool").fetchone()[0]
    finally:
        conn.close()


def random_demo_customer(exclude=None):
    """A uniformly random customer id from the demo pool (main-bank, very active customers)."""
    conn = _ro()
    try:
        ids = [r[0] for r in conn.execute("SELECT cid FROM demo_pool")]
    finally:
        conn.close()
    if exclude:
        ids = [c for c in ids if c not in exclude]
    return random.SystemRandom().choice(ids) if ids else None


# --------------------------------------------------------------------------- safe_select

_MAX_SQL_LEN = 2000
_ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_DENIED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile", "edit"})


def _authorizer(action, arg1, arg2, dbname, source):
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_RECURSIVE:      # recursive CTEs: read-only
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        # arg1 = table (or a CTE name), arg2 = column. The sandbox only holds `tx`; never allow
        # system tables or the pragma_* table-valued functions.
        name = (arg1 or "").lower()
        if name.startswith(("sqlite_", "pragma_")):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION:
        if (arg2 or "").lower() in _DENIED_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY                  # PRAGMA, ATTACH, writes, DDL, transactions...


def safe_select(conn, sql: str, max_rows: int = 50, timeout_s: float = 2.0) -> dict:
    """Run ONE read-only SELECT on a sandbox connection.

    Returns {"columns": [...], "rows": [[...], ...], "truncated": bool}.
    Raises ValueError for anything that is not a single SELECT, for denied operations, for a query
    that runs too long, and for SQL errors.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("Empty query")
    if len(sql) > _MAX_SQL_LEN:
        raise ValueError("Query too long")
    text = sql.strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not _ALLOWED_START.match(text):
        raise ValueError("Only a single SELECT query is allowed")
    # Multiple statements make sqlite3 raise ProgrammingError below, which we map to ValueError.
    max_rows = max(1, min(int(max_rows), 500))

    deadline = time.monotonic() + float(timeout_s)
    state = {"timed_out": False}

    def _progress():
        if time.monotonic() > deadline:
            state["timed_out"] = True
            return 1
        return 0

    old_length = conn.getlimit(sqlite3.SQLITE_LIMIT_LENGTH)
    try:
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100_000)
        conn.set_authorizer(_authorizer)
        conn.set_progress_handler(_progress, 1000)
        try:
            cur = conn.execute(text)
            columns = [c[0] for c in (cur.description or [])]
            if not columns:
                raise ValueError("Only a single SELECT query is allowed")
            fetched = cur.fetchmany(max_rows + 1)
        except sqlite3.ProgrammingError:
            raise ValueError("Only a single SELECT query is allowed") from None
        except sqlite3.DatabaseError as exc:
            if state["timed_out"]:
                raise ValueError("Query took too long") from None
            msg = str(exc)
            if "not authorized" in msg or "authoriz" in msg:
                raise ValueError("That operation is not allowed") from None
            raise ValueError("Query failed: " + msg[:120]) from None
        truncated = len(fetched) > max_rows
        rows = []
        for r in fetched[:max_rows]:
            rows.append([("<blob>" if isinstance(v, (bytes, bytearray, memoryview)) else v)
                         for v in tuple(r)])
        return {"columns": columns, "rows": rows, "truncated": truncated}
    finally:
        conn.set_progress_handler(None, 0)
        conn.set_authorizer(None)
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_length)
