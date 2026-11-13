"""Writable app state in data/state.db: consent, settings, suggestion intents, quiz payloads."""
import json
import os
import sqlite3
import threading
import time

from . import config

CONSENT_KEYS = ("analysis", "ai", "benchmarks", "suggestions")
SETTING_ENUMS = {
    "checkin_frequency": ("off", "weekly", "biweekly", "monthly"),
    "suggestion_level": ("off", "few", "normal"),
    "quiz": ("off", "weekly"),
}
SETTING_DEFAULTS = {
    "checkin_frequency": "monthly",
    "suggestion_level": "few",
    "quiz": "weekly",
    "monthly_saving_target": 0,
}
INTENT_ACTIONS = ("accept", "dismiss", "snooze")

_lock = threading.Lock()
_ready = set()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consent(cid TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS settings(cid TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS intents(cid TEXT, suggestion_id TEXT, action TEXT, ts REAL,
                                   PRIMARY KEY(cid, suggestion_id));
CREATE TABLE IF NOT EXISTS quiz(cid TEXT, quiz_id TEXT, payload TEXT, ts REAL,
                                PRIMARY KEY(cid, quiz_id));
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
        for t in ("consent", "settings", "intents", "quiz"):
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
