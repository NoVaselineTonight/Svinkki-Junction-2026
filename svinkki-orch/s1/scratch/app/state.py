"""Writable app state in data/state.db: consent, settings, suggestion intents, quiz payloads, goal,
category overrides ("what Svinkki has learned"), the active challenge and quiz results."""
import datetime
import json
import math
import os
import re
import secrets
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
MAX_CONVERSATIONS = 30
MAX_TURNS = 80
MAX_TURN_BYTES = 300_000
MAX_PINS = 20
MAX_PIN_BYTES = 200_000
TITLE_CHARS = 60
_PIN_TYPE_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_PIN_ID_RE = re.compile(r"^pin:([0-9]{1,18})$")
_last_ts = [0.0]

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
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, cid TEXT NOT NULL, title TEXT NOT NULL,
                                         created REAL, updated REAL);
CREATE INDEX IF NOT EXISTS conversations_cid ON conversations(cid);
CREATE TABLE IF NOT EXISTS turns(conv_id TEXT NOT NULL, n INTEGER NOT NULL, data TEXT NOT NULL, ts REAL,
                                 PRIMARY KEY(conv_id, n));
CREATE TABLE IF NOT EXISTS pins(id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT NOT NULL, title TEXT NOT NULL,
                                card TEXT NOT NULL, created REAL);
CREATE INDEX IF NOT EXISTS pins_cid ON pins(cid);
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT NOT NULL, text TEXT NOT NULL,
                                 created REAL);
CREATE INDEX IF NOT EXISTS notes_cid ON notes(cid);
CREATE TABLE IF NOT EXISTS money_proposals(id TEXT PRIMARY KEY, cid TEXT NOT NULL, data TEXT NOT NULL,
                                           status TEXT NOT NULL, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS money_proposals_cid ON money_proposals(cid);
CREATE TABLE IF NOT EXISTS money_moves(id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT NOT NULL,
                                       d TEXT NOT NULL, ts TEXT NOT NULL, amount REAL NOT NULL,
                                       dest TEXT NOT NULL, proposal_id TEXT NOT NULL UNIQUE, created REAL);
CREATE INDEX IF NOT EXISTS money_moves_cid ON money_moves(cid);
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
                  "quiz_results", "pins", "notes", "money_proposals", "money_moves"):
            conn.execute(f"DELETE FROM {t} WHERE cid=?", (cid,))
        conn.execute("DELETE FROM turns WHERE conv_id IN (SELECT id FROM conversations WHERE cid=?)",
                     (cid,))
        conn.execute("DELETE FROM conversations WHERE cid=?", (cid,))
    _run(go)


def reset_all() -> None:
    """Demo reset: forget every customer's choices, goals, learned categories, quizzes, challenges and
    in-app money moves (the demo balance goes back to what the dataset says).

    The AI key and the chosen model are not app state and are kept."""
    def go(conn):
        for t in ("consent", "settings", "intents", "quiz", "goal", "challenge", "overrides",
                  "quiz_results", "conversations", "turns", "pins", "notes", "money_proposals", "money_moves"):
            conn.execute(f"DELETE FROM {t}")
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
    goal = {"name": stored.get("name", ""), "target": stored.get("target", 0.0),
            "saved": stored.get("saved", 0.0)}
    # A goal planned with a date keeps the date and the monthly amount it needs.
    if stored.get("deadline"):
        goal["deadline"] = stored["deadline"]
    if stored.get("monthly_needed"):
        goal["monthly_needed"] = stored["monthly_needed"]
    return goal


_DEADLINE_RE = re.compile(r"\d{4}-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?")


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
    deadline = d.get("deadline")
    if deadline not in (None, ""):
        if not isinstance(deadline, str) or not _DEADLINE_RE.fullmatch(deadline):
            raise ValueError("deadline must be YYYY-MM or YYYY-MM-DD")
        goal["deadline"] = deadline
        if d.get("monthly_needed") not in (None, ""):
            goal["monthly_needed"] = _money(d.get("monthly_needed"), "monthly_needed")
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


# ---------------------------------------------------------------------------
# Conversations, turns and kept answers (pins)
# ---------------------------------------------------------------------------

def _now():
    """time.time(), but never equal to or below the previous value, so 'newest first' is stable."""
    t = time.time()
    if t <= _last_ts[0]:
        t = _last_ts[0] + 1e-6
    _last_ts[0] = t
    return t


def iso_time(ts) -> str:
    return datetime.datetime.fromtimestamp(ts or 0).astimezone().isoformat(timespec="seconds")


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def human_date(ts) -> str:
    d = datetime.datetime.fromtimestamp(ts or 0)
    return "%d %s %d" % (d.day, _MONTHS[d.month - 1], d.year)


def make_title(text) -> str:
    """First user message cut to 60 characters at a word boundary; a pasted receipt is 'A receipt'."""
    s = " ".join(str(text or "").split())
    if s.lower().startswith("[pasted receipt"):
        return "A receipt"
    if not s:
        return "New conversation"
    if len(s) <= TITLE_CHARS:
        return s
    cut = s[:TITLE_CHARS]
    if not s[TITLE_CHARS].isspace():
        i = cut.rfind(" ")
        if i > 0:
            cut = cut[:i]
    return cut.rstrip()


def goal_updated(cid):
    row = _run(lambda c: c.execute("SELECT updated FROM goal WHERE cid=?", (cid,)).fetchone())
    return row[0] if row else None


def conversation_history(cid, conv_id, turns=20):
    """The stored conversation as chat history [{role, content}] (last `turns` turns), or None when
    the id is not this customer's."""
    if not isinstance(conv_id, str) or not conv_id or len(conv_id) > 100:
        return None

    def go(conn):
        if not conn.execute("SELECT 1 FROM conversations WHERE id=? AND cid=?", (conv_id, cid)).fetchone():
            return None
        return conn.execute("SELECT data FROM turns WHERE conv_id=? ORDER BY n DESC LIMIT ?",
                            (conv_id, int(turns))).fetchall()
    rows = _run(go)
    if rows is None:
        return None
    out = []
    for (raw,) in reversed(rows):
        t = json.loads(raw)
        if t.get("tool"):      # a tool card the customer opened: nothing was said, so nothing for the model
            continue
        out.append({"role": "user", "content": t.get("h") or t.get("user") or ""})
        out.append({"role": "assistant", "content": str(t.get("reply", ""))})
    return out


def add_turn(cid, conv_id, turn, title_source) -> str:
    """Store one turn. Without a known conversation id of this customer a new conversation is created
    (titled from title_source). Returns the conversation id."""
    if not isinstance(turn, dict):
        raise ValueError("turn must be an object")
    data = json.dumps(turn, ensure_ascii=False, default=str)
    if len(data.encode("utf-8")) > MAX_TURN_BYTES:
        slim = dict(turn)
        slim["cards"] = []
        slim["used"] = []
        data = json.dumps(slim, ensure_ascii=False, default=str)

    def go(conn):
        now = _now()
        if isinstance(conv_id, str) and conv_id and len(conv_id) <= 100 and conn.execute(
                "SELECT 1 FROM conversations WHERE id=? AND cid=?", (conv_id, cid)).fetchone():
            target = conv_id
            conn.execute("UPDATE conversations SET updated=? WHERE id=?", (now, target))
        else:
            target = secrets.token_urlsafe(16)
            conn.execute("INSERT INTO conversations(id, cid, title, created, updated) VALUES(?,?,?,?,?)",
                         (target, cid, make_title(title_source), now, now))
        n = (conn.execute("SELECT MAX(n) FROM turns WHERE conv_id=?", (target,)).fetchone()[0] or 0) + 1
        conn.execute("INSERT INTO turns(conv_id, n, data, ts) VALUES(?,?,?,?)", (target, n, data, now))
        conn.execute("DELETE FROM turns WHERE conv_id=? AND n<=?", (target, n - MAX_TURNS))
        old = conn.execute("SELECT id FROM conversations WHERE cid=? ORDER BY updated DESC, rowid DESC "
                           "LIMIT -1 OFFSET ?", (cid, MAX_CONVERSATIONS)).fetchall()
        for (oid,) in old:
            conn.execute("DELETE FROM turns WHERE conv_id=?", (oid,))
            conn.execute("DELETE FROM conversations WHERE id=?", (oid,))
        return target
    return _run(go)


def list_conversations(cid, limit=MAX_CONVERSATIONS) -> list:
    rows = _run(lambda c: c.execute(
        "SELECT id, title, updated, (SELECT COUNT(*) FROM turns WHERE conv_id=conversations.id) "
        "FROM conversations WHERE cid=? ORDER BY updated DESC, rowid DESC LIMIT ?",
        (cid, int(limit))).fetchall())
    return [{"id": r[0], "title": r[1], "updated": iso_time(r[2]), "turns": r[3]} for r in rows]


def get_conversation(cid, conv_id):
    """The whole conversation for display, or None when the id is not this customer's."""
    if not isinstance(conv_id, str) or not conv_id or len(conv_id) > 100:
        return None

    def go(conn):
        head = conn.execute("SELECT id, title, created, updated FROM conversations WHERE id=? AND cid=?",
                            (conv_id, cid)).fetchone()
        if not head:
            return None
        return head, conn.execute("SELECT data, ts FROM turns WHERE conv_id=? ORDER BY n",
                                  (conv_id,)).fetchall()
    res = _run(go)
    if res is None:
        return None
    head, rows = res
    turns = []
    for raw, ts in rows:
        t = json.loads(raw)
        turn = {"user": t.get("user", ""), "reply": t.get("reply", ""), "cards": t.get("cards") or [],
                "used": t.get("used") or [], "mode": t.get("mode"), "notice": t.get("notice"),
                "ts": iso_time(ts)}
        if t.get("tool"):
            turn["tool"] = t["tool"]
        turns.append(turn)
    return {"id": head[0], "title": head[1], "created": iso_time(head[2]), "updated": iso_time(head[3]),
            "turns": turns}


def delete_conversation(cid, conv_id) -> bool:
    if not isinstance(conv_id, str) or not conv_id or len(conv_id) > 100:
        return False

    def go(conn):
        if not conn.execute("SELECT 1 FROM conversations WHERE id=? AND cid=?", (conv_id, cid)).fetchone():
            return False
        conn.execute("DELETE FROM turns WHERE conv_id=?", (conv_id,))
        conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        return True
    return _run(go)


def _pin_row_id(pin_id):
    m = _PIN_ID_RE.match(pin_id) if isinstance(pin_id, str) else None
    return int(m.group(1)) if m else None


def add_pin(cid, title, card) -> dict:
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80:
        raise ValueError("invalid title")
    title = title.strip()
    if not isinstance(card, dict):
        raise ValueError("card must be an object")
    ctype = card.get("type")
    if not isinstance(ctype, str) or not _PIN_TYPE_RE.match(ctype):
        raise ValueError("invalid card type")
    if not isinstance(card.get("data"), dict):
        raise ValueError("card data must be an object")
    raw = json.dumps(card, ensure_ascii=False)
    if len(raw.encode("utf-8")) > MAX_PIN_BYTES:
        raise ValueError("card too large")

    def go(conn):
        now = _now()
        cur = conn.execute("INSERT INTO pins(cid, title, card, created) VALUES(?,?,?,?)",
                           (cid, title, raw, now))
        conn.execute("DELETE FROM pins WHERE cid=? AND id NOT IN "
                     "(SELECT id FROM pins WHERE cid=? ORDER BY id DESC LIMIT ?)", (cid, cid, MAX_PINS))
        return {"id": "pin:%d" % cur.lastrowid, "title": title, "created": iso_time(now)}
    return _run(go)


def list_pins(cid) -> list:
    """Newest first. The card itself is not loaded, only its type."""
    rows = _run(lambda c: c.execute(
        "SELECT id, title, created, card FROM pins WHERE cid=? ORDER BY id DESC", (cid,)).fetchall())
    out = []
    for rid, title, created, raw in rows:
        try:
            ctype = json.loads(raw).get("type") or ""
        except ValueError:
            ctype = ""
        out.append({"id": "pin:%d" % rid, "title": title, "created_ts": created,
                    "created": iso_time(created), "card_type": ctype})
    return out


def get_pin(cid, pin_id):
    rid = _pin_row_id(pin_id)
    if rid is None:
        return None
    row = _run(lambda c: c.execute("SELECT id, title, card, created FROM pins WHERE id=? AND cid=?",
                                   (rid, cid)).fetchone())
    if not row:
        return None
    return {"id": "pin:%d" % row[0], "title": row[1], "card": json.loads(row[2]),
            "created": iso_time(row[3])}


def remove_pin(cid, pin_id) -> bool:
    rid = _pin_row_id(pin_id)
    if rid is None:
        return False
    return bool(_run(lambda c: c.execute("DELETE FROM pins WHERE id=? AND cid=?", (rid, cid)).rowcount))


# --------------------------------------------------------------------------- in-app money moves
# A proposal is created when the coach (or a check-in suggestion) offers to move money. Nothing moves
# until the customer approves that exact proposal: take_proposal() flips it from "pending" exactly once.

PROPOSAL_TTL_S = 15 * 60


def save_proposal(cid, pid, data) -> None:
    _run(lambda c: c.execute("INSERT INTO money_proposals VALUES(?,?,?,?,?)",
                             (pid, cid, json.dumps(data), "pending", time.time())))


def get_proposal(cid, pid):
    row = _run(lambda c: c.execute("SELECT data, status, created FROM money_proposals WHERE id=? AND cid=?",
                                   (pid, cid)).fetchone())
    if not row:
        return None
    data = json.loads(row[0])
    status = row[1]
    if status == "pending" and time.time() - row[2] > PROPOSAL_TTL_S:
        status = "expired"
    return {"data": data, "status": status, "created": row[2]}


def take_proposal(cid, pid, new_status) -> bool:
    """Atomically move a fresh pending proposal to `new_status`. False if it was not pending or expired."""
    cutoff = time.time() - PROPOSAL_TTL_S
    def go(conn):
        cur = conn.execute("UPDATE money_proposals SET status=? WHERE id=? AND cid=? AND status='pending' "
                           "AND created>=?", (new_status, pid, cid, cutoff))
        return cur.rowcount == 1
    return _run(go)


def add_move(cid, d, ts, amount, dest, proposal_id) -> int:
    def go(conn):
        cur = conn.execute("INSERT INTO money_moves(cid, d, ts, amount, dest, proposal_id, created) "
                           "VALUES(?,?,?,?,?,?,?)", (cid, d, ts, float(amount), dest, proposal_id, time.time()))
        return cur.lastrowid
    return _run(go)


def list_moves(cid) -> list:
    rows = _run(lambda c: c.execute("SELECT id, d, ts, amount, dest FROM money_moves WHERE cid=? ORDER BY ts, id",
                                    (cid,)).fetchall())
    return [{"id": r[0], "d": r[1], "ts": r[2], "amount": r[3], "dest": r[4]} for r in rows]


# ---------------------------------------------------------------------------
# Notes the customer asked the coach to remember
# ---------------------------------------------------------------------------
MAX_NOTES = 20
NOTE_CHARS = 200
_NOTE_ID_RE = re.compile(r"note:(\d{1,12})")


def add_note(cid, text) -> dict:
    """Keep one short note in the customer's own words. The newest MAX_NOTES are kept."""
    if not isinstance(text, str):
        raise ValueError("invalid note")
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in text).split())
    if not 3 <= len(text) <= NOTE_CHARS:
        raise ValueError("a note is 3 to %d characters" % NOTE_CHARS)

    def go(conn):
        now = _now()
        cur = conn.execute("INSERT INTO notes(cid, text, created) VALUES(?,?,?)", (cid, text, now))
        conn.execute("DELETE FROM notes WHERE cid=? AND id NOT IN "
                     "(SELECT id FROM notes WHERE cid=? ORDER BY id DESC LIMIT ?)", (cid, cid, MAX_NOTES))
        return {"id": "note:%d" % cur.lastrowid, "text": text, "created": iso_time(now)}
    return _run(go)


def list_notes(cid) -> list:
    """Newest first."""
    rows = _run(lambda c: c.execute("SELECT id, text, created FROM notes WHERE cid=? ORDER BY id DESC",
                                    (cid,)).fetchall())
    return [{"id": "note:%d" % r[0], "text": r[1], "created": iso_time(r[2]), "created_ts": r[2]} for r in rows]


def remove_note(cid, note_id) -> bool:
    m = _NOTE_ID_RE.fullmatch(note_id) if isinstance(note_id, str) else None
    if not m:
        return False
    rid = int(m.group(1))
    return bool(_run(lambda c: c.execute("DELETE FROM notes WHERE id=? AND cid=?", (rid, cid)).rowcount))
