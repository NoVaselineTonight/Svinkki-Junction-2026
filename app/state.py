"""Writable app state in data/state.db: consent, settings, suggestion intents, quiz payloads, goal,
category overrides ("what Svinkki has learned"), the active challenge and quiz results."""
import json
import math
import os
import sqlite3
import threading
import time

from . import classify, config

CONSENT_KEYS = ("analysis", "ai", "benchmarks", "suggestions")
SETTING_ENUMS = {
    "checkin_frequency": ("off", "weekly", "biweekly", "monthly"),
    "suggestion_level": ("off", "few", "normal"),
    "quiz": ("off", "weekly"),
    "challenges": ("off", "on"),
}
SETTING_DEFAULTS = {
    "checkin_frequency": "monthly",
    "suggestion_level": "few",
    "quiz": "weekly",
    "challenges": "off",
    "monthly_saving_target": 0,
}
INTENT_ACTIONS = ("accept", "dismiss", "snooze")
MAX_OVERRIDES = 200
MAX_QUIZ_RESULTS = 500
OVERRIDE_SCOPES = ("tx", "merchant")

_lock = threading.Lock()
_ready = set()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consent(cid TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS settings(cid TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS intents(cid TEXT, suggestion_id TEXT, action TEXT, ts REAL,
                                   PRIMARY KEY(cid, suggestion_id));
CREATE TABLE IF NOT EXISTS quiz(cid TEXT, quiz_id TEXT, payload TEXT, ts REAL,
                                PRIMARY KEY(cid, quiz_id));
CREATE TABLE IF NOT EXISTS goal(cid TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS challenge(cid TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS overrides(id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT NOT NULL,
                                     data TEXT NOT NULL, created REAL);
CREATE INDEX IF NOT EXISTS overrides_cid ON overrides(cid);
CREATE TABLE IF NOT EXISTS quiz_results(id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT NOT NULL,
                                        data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS quiz_results_cid ON quiz_results(cid);
"""


def _connect() -> sqlite3.Connection:
    path = config.state_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    if path not in _ready or not os.path.exists(path):
        conn.executescript(_SCHEMA)
        conn.commit()
        _ready.add(path)
    return conn


def _run(fn):
    with _lock:
        conn = _connect()
        try:
            res = fn(conn)
            conn.commit()
            return res
        finally:
            conn.close()


def _load(conn, table, cid):
    row = conn.execute(f"SELECT data FROM {table} WHERE cid=?", (cid,)).fetchone()
    return json.loads(row[0]) if row else {}


def get_consent(cid) -> dict:
    stored = _run(lambda c: _load(c, "consent", cid))
    return {k: bool(stored.get(k, False)) for k in CONSENT_KEYS}


def set_consent(cid, d: dict) -> dict:
    if not isinstance(d, dict):
        raise ValueError("consent must be an object")
    for k, v in d.items():
        if k not in CONSENT_KEYS:
            raise ValueError("unknown consent key")
        if not isinstance(v, bool):
            raise ValueError("consent values must be true or false")

    def go(conn):
        cur = _load(conn, "consent", cid)
        cur.update(d)
        full = {k: bool(cur.get(k, False)) for k in CONSENT_KEYS}
        conn.execute("INSERT OR REPLACE INTO consent VALUES(?,?,?)",
                     (cid, json.dumps(full), time.time()))
        return full
    return _run(go)


def get_settings(cid) -> dict:
    stored = _run(lambda c: _load(c, "settings", cid))
    out = dict(SETTING_DEFAULTS)
    for k in SETTING_DEFAULTS:
        if k in stored:
            out[k] = stored[k]
    return out


def set_settings(cid, d: dict) -> dict:
    if not isinstance(d, dict):
        raise ValueError("settings must be an object")
    clean = {}
    for k, v in d.items():
        if k not in SETTING_DEFAULTS:
            raise ValueError("unknown setting")
        if k in SETTING_ENUMS:
            if not isinstance(v, str) or v not in SETTING_ENUMS[k]:
                raise ValueError("invalid value for " + k)
            clean[k] = v
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("monthly_saving_target must be a number")
            if v != v or v < 0 or v > 100000:
                raise ValueError("monthly_saving_target out of range")
            clean[k] = round(float(v), 2)

    def go(conn):
        cur = _load(conn, "settings", cid)
        cur.update(clean)
        conn.execute("INSERT OR REPLACE INTO settings VALUES(?,?,?)",
                     (cid, json.dumps(cur), time.time()))
        out = dict(SETTING_DEFAULTS)
        out.update({k: cur[k] for k in SETTING_DEFAULTS if k in cur})
        return out
    return _run(go)


def record_intent(cid, suggestion_id, action) -> None:
    if action not in INTENT_ACTIONS:
        raise ValueError("invalid action")
    if not isinstance(suggestion_id, str) or not suggestion_id or len(suggestion_id) > 100:
        raise ValueError("invalid suggestion id")
    _run(lambda c: c.execute("INSERT OR REPLACE INTO intents VALUES(?,?,?,?)",
                             (cid, suggestion_id, action, time.time())))


def get_intents(cid) -> dict:
    """{suggestion_id: action} for this customer (extra helper used by the server)."""
    rows = _run(lambda c: c.execute(
        "SELECT suggestion_id, action FROM intents WHERE cid=?", (cid,)).fetchall())
    return {r[0]: r[1] for r in rows}


def erase(cid) -> None:
    def go(conn):
        for t in ("consent", "settings", "intents", "quiz", "goal", "challenge", "overrides",
                  "quiz_results"):
            conn.execute(f"DELETE FROM {t} WHERE cid=?", (cid,))
    _run(go)


def save_quiz(cid, quiz_id, payload) -> None:
    if not isinstance(quiz_id, str) or not quiz_id:
        raise ValueError("invalid quiz id")
    data = json.dumps(payload)

    def go(conn):
        conn.execute("DELETE FROM quiz WHERE cid=? AND ts < ?", (cid, time.time() - 7 * 86400))
        conn.execute("INSERT OR REPLACE INTO quiz VALUES(?,?,?,?)", (cid, quiz_id, data, time.time()))
    _run(go)


def load_quiz(cid, quiz_id):
    row = _run(lambda c: c.execute("SELECT payload FROM quiz WHERE cid=? AND quiz_id=?",
                                   (cid, str(quiz_id))).fetchone())
    return json.loads(row[0]) if row else None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _money(v, name, hi=1e9):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(name + " must be a number")
    v = float(v)
    if not math.isfinite(v) or v < 0 or v > hi:
        raise ValueError(name + " out of range")
    return round(v, 2)


def _text(v, name, maxlen, allow_empty=False):
    if v is None or v == "":
        if allow_empty:
            return ""
        raise ValueError(name + " is required")
    if not isinstance(v, str) or len(v) > maxlen:
        raise ValueError(name + " is invalid")
    return v


# ---------------------------------------------------------------------------
# Savings goal
# ---------------------------------------------------------------------------

def get_goal(cid):
    stored = _run(lambda c: _load(c, "goal", cid))
    if not stored:
        return None
    return {"name": stored.get("name", ""), "target": stored.get("target", 0.0),
            "saved": stored.get("saved", 0.0)}


def set_goal(cid, d):
    if d is None:
        _run(lambda c: c.execute("DELETE FROM goal WHERE cid=?", (cid,)))
        return None
    if not isinstance(d, dict):
        raise ValueError("goal must be an object")
    goal = {"name": _text(d.get("name"), "name", 60).strip(),
            "target": _money(d.get("target"), "target"),
            "saved": _money(d.get("saved", 0), "saved")}
    if not goal["name"] or goal["target"] <= 0:
        raise ValueError("goal needs a name and a target above zero")
    _run(lambda c: c.execute("INSERT OR REPLACE INTO goal VALUES(?,?,?)",
                             (cid, json.dumps(goal), time.time())))
    return goal


# ---------------------------------------------------------------------------
# Category overrides
# ---------------------------------------------------------------------------

def _iso(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts or 0))


def _override_view(row_id, data, created):
    return {"id": row_id, "scope": data.get("scope"), "tx_id": data.get("tx_id"),
            "merchant": data.get("merchant"), "label": data.get("label"),
            "basket": data.get("basket"), "context": data.get("context", ""),
            "created": _iso(created)}


def list_overrides(cid) -> list:
    rows = _run(lambda c: c.execute(
        "SELECT id, data, created FROM overrides WHERE cid=? ORDER BY id", (cid,)).fetchall())
    return [_override_view(r[0], json.loads(r[1]), r[2]) for r in rows]


def add_override(cid, d) -> dict:
    if not isinstance(d, dict):
        raise ValueError("override must be an object")
    scope = d.get("scope")
    if scope not in OVERRIDE_SCOPES:
        raise ValueError("invalid scope")
    label = d.get("label")
    if not isinstance(label, str) or label not in classify.ALL_LABELS:
        raise ValueError("invalid label")
    basket = d.get("basket")
    if basket in (None, ""):
        basket = None
    elif not isinstance(basket, str) or basket not in classify.BASKETS:
        raise ValueError("invalid basket")
    context = d.get("context") or ""
    if context not in ("", "night_out"):
        raise ValueError("invalid context")
    rec = {"scope": scope, "label": label, "basket": basket, "context": context,
           "tx_id": None, "merchant": None}
    if scope == "tx":
        tx_id = d.get("tx_id")
        if isinstance(tx_id, bool) or not isinstance(tx_id, int) or tx_id < 0:
            raise ValueError("invalid tx_id")
        rec["tx_id"] = tx_id
        if d.get("merchant") not in (None, ""):
            rec["merchant"] = _text(d.get("merchant"), "merchant", 100)
    else:
        rec["merchant"] = _text(d.get("merchant"), "merchant", 100)

    def go(conn):
        existing = conn.execute("SELECT id, data FROM overrides WHERE cid=?", (cid,)).fetchall()
        same = []
        for rid, raw in existing:
            old = json.loads(raw)
            if old.get("scope") == scope and (
                    (scope == "tx" and old.get("tx_id") == rec["tx_id"]) or
                    (scope == "merchant" and old.get("merchant") == rec["merchant"])):
                same.append(rid)
        if len(existing) - len(same) >= MAX_OVERRIDES:
            raise ValueError("too many overrides")
        for rid in same:
            conn.execute("DELETE FROM overrides WHERE id=? AND cid=?", (rid, cid))
        now = time.time()
        cur = conn.execute("INSERT INTO overrides(cid, data, created) VALUES(?,?,?)",
                           (cid, json.dumps(rec), now))
        return _override_view(cur.lastrowid, rec, now)
    return _run(go)


def remove_override(cid, override_id) -> None:
    if isinstance(override_id, bool) or not isinstance(override_id, int):
        raise ValueError("invalid id")
    _run(lambda c: c.execute("DELETE FROM overrides WHERE id=? AND cid=?", (override_id, cid)))


# ---------------------------------------------------------------------------
# Challenge
# ---------------------------------------------------------------------------

def get_challenge(cid):
    return _run(lambda c: _load(c, "challenge", cid)) or None


def set_challenge(cid, d) -> None:
    if d is None:
        _run(lambda c: c.execute("DELETE FROM challenge WHERE cid=?", (cid,)))
        return
    if not isinstance(d, dict):
        raise ValueError("challenge must be an object")
    data = json.dumps(d)
    if len(data) > 8000:
        raise ValueError("challenge too large")
    _run(lambda c: c.execute("INSERT OR REPLACE INTO challenge VALUES(?,?,?)",
                             (cid, data, time.time())))


# ---------------------------------------------------------------------------
# Quiz results
# ---------------------------------------------------------------------------

def add_quiz_result(cid, d) -> None:
    if not isinstance(d, dict):
        raise ValueError("result must be an object")
    rec = {"at": _text(d.get("at"), "at", 40), "label": _text(d.get("label"), "label", 80),
           "guess": _money(d.get("guess"), "guess"), "actual": _money(d.get("actual"), "actual")}

    def go(conn):
        conn.execute("INSERT INTO quiz_results(cid, data) VALUES(?,?)", (cid, json.dumps(rec)))
        conn.execute(
            "DELETE FROM quiz_results WHERE cid=? AND id NOT IN "
            "(SELECT id FROM quiz_results WHERE cid=? ORDER BY id DESC LIMIT ?)",
            (cid, cid, MAX_QUIZ_RESULTS))
    _run(go)


def quiz_history(cid) -> list:
    rows = _run(lambda c: c.execute(
        "SELECT data FROM quiz_results WHERE cid=? ORDER BY id", (cid,)).fetchall())
    return [json.loads(r[0]) for r in rows]
