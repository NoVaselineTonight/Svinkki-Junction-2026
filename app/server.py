"""HTTP server: static files, session handling, JSON API.

No business logic here: validate, authorise, call insights/coach, serialise.
Python standard library only.
"""
import argparse
import datetime
import hashlib
import http.server
import json
import mimetypes
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
from collections import deque
from types import SimpleNamespace

from . import classify, config, db, money, state

COOKIE = "svinkki_sid"
MAX_BODY = 16 * 1024
MAX_BODY_EXPLAIN = 24 * 1024   # /api/explain only: a pasted document
MAX_BODY_PINS = 256 * 1024     # /api/pins only: a kept card (the card itself is capped at 200 kB)
EXPLAIN_MIN, EXPLAIN_MAX = 40, 6000
MAX_MESSAGE = 2000
SESSION_IDLE_SECONDS = 2 * 60 * 60
HISTORY_TURNS = 20
RATE_CHAT = 60
RATE_OTHER = 300
RATE_WINDOW = 60.0
SUGGESTION_LIMITS = {"off": 0, "few": 1, "normal": 3}
MAX_ITEM_CHARS = 80
MAX_PRICE = 1_000_000
MAX_USED_GROUPS = 6
USED_ROWS = 20
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors *")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain; charset=utf-8",
    ".webmanifest": "application/manifest+json",
}

NO_MONEY_MESSAGES = {
    "accept": "Noted. I saved your choice.",
    "dismiss": "Okay, I will not suggest this again. No money was moved.",
    "snooze": "Okay, I will remind you later. No money was moved.",
}

# Endpoints that work without analysis consent (everything else is a data endpoint).
NO_CONSENT_PATHS = {
    "/api/demo/personas", "/api/demo/login", "/api/demo/random", "/api/logout", "/api/me",
    "/api/consent", "/api/settings", "/api/privacy/erase", "/api/demo/reset",
    "/api/explain",   # explaining a pasted text looks at no transactions, so it needs a session only
    "/api/demo/ai", "/api/demo/ai/test",   # demo setup of the AI model: reads no customer data
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _hash_prefix(sid):
    if not sid:
        return "-"
    return hashlib.sha256(sid.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Session store (in memory)
# ---------------------------------------------------------------------------

class Sessions:
    def __init__(self):
        self._lock = threading.Lock()
        self._s = {}

    def create(self, cid, name):
        sid = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._purge(now)
            self._s[sid] = {"cid": cid, "name": name, "last": now, "history": [],
                            "ai_payload": None, "memory": {}, "hits": {"chat": deque(), "other": deque()}}
        return sid

    def get(self, sid):
        if not sid:
            return None
        now = time.time()
        with self._lock:
            s = self._s.get(sid)
            if s is None:
                return None
            if now - s["last"] > SESSION_IDLE_SECONDS:
                del self._s[sid]
                return None
            s["last"] = now
            return s

    def delete(self, sid):
        with self._lock:
            self._s.pop(sid, None)

    def clear(self):
        """Drop every session (the demo reset)."""
        with self._lock:
            self._s.clear()

    def _purge(self, now):
        for k in [k for k, v in self._s.items() if now - v["last"] > SESSION_IDLE_SECONDS]:
            del self._s[k]


class RateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._anon = {}

    def allow(self, hits, bucket, now=None):
        now = time.time() if now is None else now
        limit = RATE_CHAT if bucket == "chat" else RATE_OTHER
        with self._lock:
            q = hits[bucket]
            while q and now - q[0] > RATE_WINDOW:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def anon_hits(self, key):
        with self._lock:
            if len(self._anon) > 5000:
                self._anon.clear()
            return self._anon.setdefault(key, {"chat": deque(), "other": deque()})


# ---------------------------------------------------------------------------
# Server object holding shared state
# ---------------------------------------------------------------------------

class SvinkkiServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr):
        super().__init__(addr, Handler)
        self.sessions = Sessions()
        self.limiter = RateLimiter()
        self._persona_lock = threading.Lock()
        self.persona_tokens = {}   # opaque token -> {cid, name, blurb}
        self.persona_list = []     # [{id, name, blurb}]
        self._load_personas()

    def _load_personas(self):
        with self._persona_lock:
            if self.persona_list:
                return
            try:
                personas = db.list_personas()
            except Exception:
                return
            tokens, out = {}, []
            for p in personas:
                tok = secrets.token_urlsafe(12)
                tokens[tok] = {"cid": p["cid"], "name": p.get("name", ""), "blurb": p.get("blurb", "")}
                out.append({"id": tok, "name": p.get("name", ""), "blurb": p.get("blurb", "")})
            self.persona_tokens, self.persona_list = tokens, out


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

def _num(v, name, lo=None, hi=None, allow_none=False):
    if v is None and allow_none:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise ApiError(400, "invalid_" + name)
    if lo is not None and v < lo or hi is not None and v > hi:
        raise ApiError(400, "invalid_" + name)
    return float(v)


def _short_str(v, name, maxlen=100, allow_none=True):
    if v is None or v == "":
        if allow_none:
            return None
        raise ApiError(400, "invalid_" + name)
    if not isinstance(v, str) or len(v) > maxlen:
        raise ApiError(400, "invalid_" + name)
    return v


def _iso_date(v, name):
    """A real calendar date as YYYY-MM-DD, or None when absent. Anything else is a 400."""
    if v is None or v == "":
        return None
    if not isinstance(v, str) or len(v) != 10:
        raise ApiError(400, "invalid_" + name)
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        raise ApiError(400, "invalid_" + name)
    return v


def _ts(v, name):
    """A timestamp as 'YYYY-MM-DD HH:MM:SS', or None when absent. Anything else is a 400."""
    if v is None or v == "":
        return None
    if not isinstance(v, str) or not _TS_RE.match(v):
        raise ApiError(400, "invalid_" + name)
    try:
        dt = datetime.datetime.fromisoformat(v.replace(" ", "T"))
    except ValueError:
        raise ApiError(400, "invalid_" + name)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "Svinkki"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):  # silence default logging
        pass

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def _dispatch(self, method):
        t0 = time.time()
        self._status = 0
        self._sid = None
        self._extra_headers = []
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        try:
            try:
                self._route(method, path, parsed.query)
            except ApiError as e:
                self._send_json(e.status, {"error": e.message})
            except Exception as e:  # SR-18: one generic handler
                sys.stderr.write("handler error: %s\n" % type(e).__name__)
                try:
                    self._send_json(500, {"error": "server_error"})
                except Exception:
                    pass
        finally:
            ms = int((time.time() - t0) * 1000)
            sys.stderr.write("%s %s %s %s %dms sid=%s\n" % (
                time.strftime("%Y-%m-%dT%H:%M:%S"), method, path[:120], self._status, ms,
                _hash_prefix(self._sid)))

    # -- output ------------------------------------------------------------
    def _common_headers(self, api):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store" if api else "no-cache")
        for k, v in self._extra_headers:
            self.send_header(k, v)

    def _send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self._status = status
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._common_headers(True)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_bytes(self, status, ctype, body):
        self._status = status
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._common_headers(False)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # -- input -------------------------------------------------------------
    def _cookie_sid(self):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return None

    def _read_json(self, max_body=MAX_BODY):
        te = self.headers.get("Transfer-Encoding")
        cl = self.headers.get("Content-Length")
        if te:
            raise ApiError(400, "bad_request")
        if cl is None:
            return {}
        try:
            n = int(cl)
        except ValueError:
            raise ApiError(400, "bad_request")
        if n < 0:
            raise ApiError(400, "bad_request")
        if n > max_body:
            left = min(n, 1 << 20)  # drain a bounded amount so the client sees our reply
            while left > 0:
                chunk = self.rfile.read(min(left, 65536))
                if not chunk:
                    break
                left -= len(chunk)
            raise ApiError(400, "body_too_large")
        raw = self.rfile.read(n) if n else b""
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "invalid_json")
        if not isinstance(data, dict):
            raise ApiError(400, "invalid_json")
        return data

    def _drain_body(self):
        try:
            left = min(int(self.headers.get("Content-Length") or 0), 1 << 20)
        except ValueError:
            return
        while left > 0:
            chunk = self.rfile.read(min(left, 65536))
            if not chunk:
                break
            left -= len(chunk)

    # -- routing -----------------------------------------------------------
    def _route(self, method, path, query):
        if not path.startswith("/api/"):
            if method not in ("GET", "HEAD"):
                raise ApiError(405, "method_not_allowed")
            return self._static(path)

        route = ROUTES.get(path)
        if route is None:
            raise ApiError(404, "not_found")
        verb, fn = route
        verbs = verb.split("|")
        if method not in verbs and not (method == "HEAD" and "GET" in verbs):
            raise ApiError(405, "method_not_allowed")

        srv = self.server
        sid = self._cookie_sid()
        session = srv.sessions.get(sid)
        self._sid = sid if session else None

        # rate limit (per session; per client address for anonymous calls)
        hits = session["hits"] if session else srv.limiter.anon_hits(self.client_address[0])
        bucket = "chat" if path in ("/api/chat", "/api/explain", "/api/demo/ai/test") else "other"
        if not srv.limiter.allow(hits, bucket):
            self._drain_body()   # so the client sees our reply instead of a reset connection
            raise ApiError(429, "rate_limited")

        limit = (MAX_BODY_EXPLAIN if path == "/api/explain"
                 else MAX_BODY_PINS if path == "/api/pins" else MAX_BODY)
        body = self._read_json(limit) if method == "POST" else {}
        query_d = {k: v[-1] for k, v in urllib.parse.parse_qs(query, keep_blank_values=False).items()}

        req = SimpleNamespace(handler=self, srv=srv, session=session, sid=sid,
                              body=body, query=query_d, path=path, conn=None)
        public = path in ("/api/demo/personas", "/api/demo/login", "/api/demo/random", "/api/logout")
        if not public and session is None:
            raise ApiError(401, "not_logged_in")
        try:
            if session is not None and path not in NO_CONSENT_PATHS:
                req.cid = session["cid"]
                req.consent = state.get_consent(req.cid)
                if not req.consent.get("analysis"):
                    raise ApiError(403, "consent_required")
                req.settings = state.get_settings(req.cid)
                req.today = config.today()
                req.conn = db.sandbox(req.cid, req.today, state.list_overrides(req.cid),
                                      state.list_moves(req.cid))  # SR-2
            elif session is not None:
                req.cid = session["cid"]
            result = fn(req)
        except ValueError:
            raise ApiError(400, "invalid_request")
        finally:
            if req.conn is not None:
                try:
                    req.conn.close()
                except Exception:
                    pass
        self._send_json(200, result)

    # -- static files ------------------------------------------------------
    def _static(self, path):
        web_root = os.path.realpath(os.path.join(config.repo_root(), "web"))
        try:
            rel = urllib.parse.unquote(path, errors="strict")
        except UnicodeDecodeError:
            raise ApiError(404, "not_found")
        if "\x00" in rel or "\\" in rel:
            raise ApiError(404, "not_found")
        parts = [p for p in rel.split("/") if p]
        if any(p in (".", "..") for p in parts):
            raise ApiError(404, "not_found")
        if not parts:
            parts = ["index.html"]
        full = os.path.realpath(os.path.join(web_root, *parts))
        try:
            inside = os.path.commonpath([web_root, full]) == web_root
        except ValueError:
            inside = False
        if not inside or not os.path.isfile(full):
            raise ApiError(404, "not_found")
        ext = os.path.splitext(full)[1].lower()
        ctype = CONTENT_TYPES.get(ext) or mimetypes.types_map.get(ext) or "application/octet-stream"
        with open(full, "rb") as f:
            data = f.read()
        self._send_bytes(200, ctype, data)

    # helpers used by endpoint functions
    def set_cookie(self, sid):
        self._extra_headers.append(
            ("Set-Cookie", "%s=%s; HttpOnly; SameSite=Lax; Path=/" % (COOKIE, sid)))

    def clear_cookie(self):
        self._extra_headers.append(
            ("Set-Cookie", "%s=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0" % COOKIE))


# ---------------------------------------------------------------------------
# Endpoints. Each takes `req` and returns a JSON-serialisable object.
# ---------------------------------------------------------------------------

def _insights():
    from . import insights
    return insights


def ep_personas(req):
    req.srv._load_personas()
    return req.srv.persona_list


def ep_login(req):
    req.srv._load_personas()
    tok = req.body.get("id")
    persona = req.srv.persona_tokens.get(tok) if isinstance(tok, str) else None
    if persona is None:
        raise ApiError(400, "unknown_persona")
    if req.sid:
        req.srv.sessions.delete(req.sid)  # avoid session fixation
    sid = req.srv.sessions.create(persona["cid"], persona["name"])
    req.handler._sid = sid
    req.handler.set_cookie(sid)
    return {"ok": True}


def ep_random(req):
    """Demo only: log in as a random customer from the pool of active main-bank customers.

    The server picks the customer; the client never sends or sees a customer id (SR-1).
    """
    try:
        cid = db.random_demo_customer()
    except Exception:
        cid = None
    if not cid:
        raise ApiError(404, "no_demo_pool")
    if req.sid:
        req.srv.sessions.delete(req.sid)  # avoid session fixation
    # The display number is random too, so it reveals nothing about the customer id.
    name = "Customer %d" % (1000 + secrets.randbelow(9000))
    sid = req.srv.sessions.create(cid, name)
    req.handler._sid = sid
    req.handler.set_cookie(sid)
    return {"ok": True}


def ep_logout(req):
    if req.sid:
        req.srv.sessions.delete(req.sid)
    req.handler.clear_cookie()
    return {"ok": True}


def ep_demo_reset(req):
    """Demo reset: every customer's choices are forgotten and every session ends. The AI key stays."""
    state.reset_all()
    req.srv.sessions.clear()
    req.handler.clear_cookie()
    return {"ok": True}


def ep_me(req):
    cid = req.session["cid"]
    try:
        age_band = db.profile(cid).get("age_band")
    except Exception:
        age_band = None
    return {"name": req.session["name"], "age_band": age_band, "today": config.today(),
            "is_random": str(req.session["name"]).startswith("Customer "),
            "consent": state.get_consent(cid), "settings": state.get_settings(cid),
            "ai_available": bool(config.ai_provider())}


# -- demo setup of the AI model -------------------------------------------------------------
# The key is written to a git-ignored file and never returned or logged (SR-25). Changing the
# setup is only possible from the computer the server runs on.
_LOCAL_ADDRS = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
_LOCAL_NAMES = ("localhost", "127.0.0.1", "::1")
_PROXY_HEADERS = ("X-Forwarded-For", "X-Forwarded-Host", "X-Real-IP", "Forwarded", "Via")


def _is_local(handler):
    """True only for a browser on this computer talking to the server directly (no proxy or tunnel)."""
    if handler.client_address[0] not in _LOCAL_ADDRS:
        return False
    hdrs = handler.headers
    if any(hdrs.get(h) for h in _PROXY_HEADERS):
        return False
    try:
        if (urllib.parse.urlsplit("//" + (hdrs.get("Host") or "")).hostname or "") not in _LOCAL_NAMES:
            return False
        origin = hdrs.get("Origin")
        if origin and (urllib.parse.urlsplit(origin).hostname or "") not in _LOCAL_NAMES:
            return False
    except ValueError:
        return False
    return True


def _ai_status(req):
    local = _is_local(req.handler)
    key = config.claude_api_key()
    return {"provider": config.ai_provider() or "offline",
            "key_set": bool(key),
            "key_last4": key[-4:] if (key and local) else "",
            "key_source": ("environment" if config.claude_key_from_env() else "file") if key else "",
            "model": config.claude_model(),
            "models": [{"id": m, "label": label} for m, label in config.CLAUDE_MODELS],
            "editable": local}


def ep_ai_setup(req):
    if req.handler.command != "POST":
        return _ai_status(req)
    if not _is_local(req.handler):
        raise ApiError(403, "local_only")
    model, key = req.body.get("model"), req.body.get("key")
    if model is None and key is None:
        raise ApiError(400, "invalid_request")
    if model is not None and model not in [m for m, _ in config.CLAUDE_MODELS]:
        raise ApiError(400, "invalid_model")
    if key is not None:
        key = key.strip() if isinstance(key, str) else ""
        if not config.valid_claude_key(key):
            raise ApiError(400, "invalid_key")
    try:
        if key is not None:
            config.set_claude_api_key(key)
        if model is not None:
            config.set_claude_model(model)
    except OSError:
        raise ApiError(500, "could_not_save")
    return _ai_status(req)


def ep_ai_test(req):
    """One tiny request to Claude with the saved key and model. Sends no customer data."""
    if not _is_local(req.handler):
        raise ApiError(403, "local_only")
    from . import llm_claude
    key = config.claude_api_key()
    if not key:
        return {"ok": False, "error": "No Claude key is saved."}
    try:
        return {"ok": True, "model": llm_claude.ping(key, config.claude_model())}
    except llm_claude.ClaudeError as e:
        return {"ok": False, "error": str(e)}


def ep_consent(req):
    try:
        consent = state.set_consent(req.session["cid"], req.body)
    except ValueError:
        raise ApiError(400, "invalid_consent")
    return {"consent": consent}


def ep_settings(req):
    try:
        settings = state.set_settings(req.session["cid"], req.body)
    except ValueError:
        raise ApiError(400, "invalid_settings")
    return {"settings": settings}


def ep_overview(req):
    month = _short_str(req.query.get("month"), "month", 20)
    try:
        return _insights().overview(req.conn, req.today, month=month)
    except ValueError:
        raise ApiError(400, "invalid_month")


def ep_baskets(req):
    period = _short_str(req.query.get("period"), "period", 20) or "last_month"
    try:
        return _insights().baskets(req.conn, req.today, period=period)
    except ValueError:
        raise ApiError(400, "invalid_period")


def ep_safe(req):
    return _insights().safe_to_spend(
        req.conn, req.today, monthly_saving_target=req.settings.get("monthly_saving_target", 0))


def ep_what_if(req):
    changes = req.body.get("changes")
    if not isinstance(changes, list) or not changes or len(changes) > 10:
        raise ApiError(400, "invalid_changes")
    clean = []
    for c in changes:
        if not isinstance(c, dict):
            raise ApiError(400, "invalid_changes")
        target = _short_str(c.get("target"), "target", 60, allow_none=False)
        kind, val = _insights()._resolve_target(target)
        known = {l.lower() for l in classify.ALL_LABELS}
        if kind == "labels" and not all(str(v).lower() in known for v in val):
            raise ApiError(400, "invalid_target")
        clean.append({"target": target, "pct": _num(c.get("pct"), "pct", 0, 100)})
    months = req.body.get("months", 12)
    months = int(_num(months, "months", 1, 120))
    try:
        return _insights().what_if(req.conn, req.today, clean, months=months)
    except ValueError:
        raise ApiError(400, "invalid_changes")


def ep_spender(req):
    return _insights().spender_type(req.conn, req.today)


def ep_benchmarks(req):
    if not req.consent.get("benchmarks"):
        raise ApiError(403, "consent_required")
    return _insights().benchmarks(req.conn, req.today, db.profile(req.cid), db.bench)


def ep_averages(req):
    if not req.consent.get("benchmarks"):
        raise ApiError(403, "consent_required")
    from . import averages
    topic = _short_str(req.query.get("topic"), "topic", 40)
    return averages.averages(req.conn, req.today, db.profile(req.cid), topic=topic or None)


def ep_mortgage(req):
    price = _num(req.body.get("price"), "price", 0, 1e8, allow_none=True)
    equity = _num(req.body.get("equity"), "equity", 0, 1e8, allow_none=True)
    return _insights().mortgage(req.conn, req.today, price=price, equity=equity)


def ep_quiz(req):
    if req.settings.get("quiz") == "off":
        raise ApiError(404, "quiz_off")
    ins = _insights()
    if req.query.get("another") in ("1", "true", "yes"):
        history = state.quiz_history(req.cid)
        last = history[-1].get("label") if history else None
        result = ins.quiz(req.conn, req.today, seed=1)
        for seed in range(2, 14):
            if result.get("label_or_context") != last:
                break
            result = ins.quiz(req.conn, req.today, seed=seed)
    else:
        result = ins.quiz(req.conn, req.today)
    state.save_quiz(req.cid, str(result["quiz_id"]), result)
    return result


def ep_quiz_answer(req):
    quiz_id = req.body.get("quiz_id")
    if not isinstance(quiz_id, str) or not quiz_id or len(quiz_id) > 200:
        raise ApiError(400, "invalid_quiz_id")
    guess = _num(req.body.get("guess"), "guess", 0, 1e9)
    if state.load_quiz(req.cid, quiz_id) is None:
        raise ApiError(404, "unknown_quiz")
    try:
        if req.consent.get("benchmarks"):
            res = _insights().quiz_answer(req.conn, req.today, quiz_id, guess,
                                          profile=db.profile(req.cid), bench_lookup=db.bench)
        else:
            res = _insights().quiz_answer(req.conn, req.today, quiz_id, guess)
    except ValueError:
        raise ApiError(400, "invalid_quiz_id")
    try:
        state.add_quiz_result(req.cid, {
            "at": datetime.datetime.now().replace(microsecond=0).isoformat(),
            "label": str(res.get("label_or_context") or "")[:80],
            "guess": guess, "actual": res.get("actual", 0)})
    except ValueError:
        pass
    return res


def ep_checkin(req):
    freq = req.settings.get("checkin_frequency", "monthly")
    if freq == "off":
        return {"due": False, "checkin": None}
    checkin = _insights().checkin(req.conn, req.today, frequency=freq)
    suggestions = list(checkin.get("suggestions") or [])
    limit = SUGGESTION_LIMITS.get(req.settings.get("suggestion_level", "few"), 0)
    if not req.consent.get("suggestions") or limit == 0:
        suggestions = []
    else:
        done = state.get_intents(req.cid)
        suggestions = [s for s in suggestions
                       if done.get(s.get("id")) not in ("accept", "dismiss")][:limit]
    checkin["suggestions"] = _money_suggestions(req, suggestions)
    return {"due": True, "checkin": checkin}


_MONEY_KINDS = ("save_surplus", "build_buffer")


def _money_suggestions(req, suggestions):
    """MAJ-6: a set-aside suggestion never offers more than is safe to move before payday, and says how the
    move works. Below 20 euros it is dropped."""
    out = []
    cap = None
    for s in suggestions:
        if s.get("kind") in _MONEY_KINDS:
            if cap is None:
                cap = money.available(req.conn, req.today)[0]
            amt = float(int(min(float(s.get("amount") or 0), cap)))
            if amt < 20:
                continue
            s = dict(s)
            word = "buffer" if s["kind"] == "build_buffer" else "savings"
            first = str(s.get("detail") or "").split(". You could")[0].split(". Would you")[0].rstrip(".")
            s.update({"amount": amt, "dest": "savings",
                      "title": "Move %s to your S-Bank savings account?" % _money_text(amt),
                      "detail": ("%s. You can move up to %s now without touching money needed for bills before "
                                 "payday. I will show you the move and ask you to approve it first; the money "
                                 "stays in S-mobiili." % (first, _money_text(int(cap)))),
                      "action_label": "Move %s to %s" % (_money_text(amt), word)})
        out.append(s)
    return out


def ep_suggestion_action(req):
    sid = req.body.get("id")
    action = req.body.get("action")
    if not isinstance(sid, str) or not sid or len(sid) > 100:
        raise ApiError(400, "invalid_id")
    if action not in state.INTENT_ACTIONS:
        raise ApiError(400, "invalid_action")
    if not req.consent.get("suggestions"):
        raise ApiError(403, "consent_required")
    if action == "accept" and sid.split(":", 1)[0] in _MONEY_KINDS:
        # Accepting a set-aside suggestion does not move money: it opens an approval for that exact move.
        current = ep_checkin(req).get("checkin") or {}
        sug = next((x for x in (current.get("suggestions") or []) if x.get("id") == sid), None)
        if sug is None:
            return {"ok": False, "message": "This suggestion is no longer available."}
        try:
            prop = money.propose(req.conn, req.today, req.cid, "savings", sug["amount"],
                                 sug.get("title", ""), "checkin:" + sid)
        except money.MoneyError as e:
            return {"ok": False, "message": str(e)}
        return {"ok": True, "proposal": prop,
                "message": "Here is the move. Nothing happens until you approve it."}
    state.record_intent(req.cid, sid, action)
    return {"ok": True, "message": NO_MONEY_MESSAGES[action]}


# ---------------------------------------------------------------------------
# In-app money moves: propose (anyone in the app, including the coach), confirm (only the customer)
# ---------------------------------------------------------------------------

def ep_money(req):
    cap, s = money.available(req.conn, req.today)
    return {"holdings": money.holdings(req.cid), "destinations": money.destinations(),
            "available": round(cap, 2), "balance": s.get("balance"), "next_payday": s.get("next_payday")}


def ep_money_propose(req):
    b = req.body
    dest = b.get("dest")
    if not isinstance(dest, str) or dest not in money.DEST_IDS:
        raise ApiError(400, "invalid_destination")   # no free-form destination exists
    amount = b.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ApiError(400, "invalid_amount")
    reason = b.get("reason")
    reason = reason[:200] if isinstance(reason, str) else ""
    try:
        prop = money.propose(req.conn, req.today, req.cid, dest, amount, reason, "app")
    except money.MoneyError as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "proposal": prop}


def ep_money_confirm(req):
    """The only way money moves: the customer approves one proposal, naming its amount and destination."""
    b = req.body
    pid, approve = b.get("proposal_id"), b.get("approve")
    if not isinstance(pid, str) or not isinstance(approve, bool):
        raise ApiError(400, "invalid_request")
    got = state.get_proposal(req.cid, pid) if 0 < len(pid) <= 64 else None
    try:
        res = money.confirm(req.conn, req.today, req.cid, pid, approve, b.get("amount"), b.get("dest"))
    except money.MoneyError as e:
        return {"ok": False, "moved": False, "message": str(e)}
    src = str(((got or {}).get("data") or {}).get("source") or "")
    if res.get("moved") and src.startswith("checkin:"):
        state.record_intent(req.cid, src[len("checkin:"):], "accept")
    return res


def ep_transactions(req):
    q = req.query
    try:
        limit = int(q.get("limit", 50))
    except ValueError:
        raise ApiError(400, "invalid_limit")
    if limit < 1:
        raise ApiError(400, "invalid_limit")
    limit = min(limit, 50)
    kw = {k: _short_str(q.get(k), k, 100) for k in ("label", "basket", "context", "type", "q")}
    frm = _iso_date(q.get("from"), "from")
    to = _iso_date(q.get("to"), "to")
    ts_from = _ts(q.get("ts_from"), "ts_from")
    ts_to = _ts(q.get("ts_to"), "ts_to")
    return _insights().transactions(req.conn, req.today, frm=frm, to=to, limit=limit,
                                    ts_from=ts_from, ts_to=ts_to, **kw)


def _used_title(ev, kw, groups):
    """The title of one "transactions used" group; two groups never share a title (the second one is
    told apart by what it filters on: its category, basket, type or kind of spending)."""
    title = str(ev.get("title") or "Transactions")[:120]
    taken = {g["title"] for g in groups}
    if title not in taken:
        return title
    for k in ("label", "basket", "type", "context", "q"):
        if kw.get(k):
            cand = ("%s (%s)" % (title, str(kw[k]).replace("_", " ").lower()))[:120]
            if cand not in taken:
                return cand
    n = 2
    while ("%s (%d)" % (title, n))[:120] in taken:
        n += 1
    return ("%s (%d)" % (title, n))[:120]


def _used_groups(conn, today, evidence):
    """The transactions behind each evidence filter of a chat turn (W9)."""
    ins = _insights()
    groups, seen = [], set()
    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue
        kw = {}
        for k in ("label", "basket", "context", "type", "q"):
            v = ev.get(k)
            if isinstance(v, str) and v:
                kw[k] = v[:100]
        for src, dst in (("from", "frm"), ("to", "to"), ("ts_from", "ts_from"), ("ts_to", "ts_to")):
            v = ev.get(src)
            if isinstance(v, str) and v:
                kw[dst] = v
        key = json.dumps(kw, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        try:
            res = ins.transactions(conn, today, limit=USED_ROWS, **kw)
        except Exception:
            continue
        groups.append({"title": _used_title(ev, kw, groups),
                       "count": res["count"], "total": res["total"], "spent": res["spent"],
                       "rows": res["rows"], "truncated": res["truncated"]})
        if len(groups) >= MAX_USED_GROUPS:
            break
    return groups


def _apply_override(req, conn, tx_id, label, context, apply_to_merchant):
    """Remember a category for one of the customer's own transactions (or its merchant)."""
    if isinstance(tx_id, bool) or not isinstance(tx_id, int) or tx_id < 1:
        raise ApiError(400, "invalid_tx_id")
    if not isinstance(label, str) or label not in classify.ALL_LABELS:
        raise ApiError(400, "invalid_label")
    if context in (None, False):
        context = ""
    if context is True:
        context = "night_out"
    if context not in ("", "night_out"):
        raise ApiError(400, "invalid_context")
    # the sandbox only holds this customer's rows, so a foreign id is simply "not found"
    if conn.execute("SELECT 1 FROM tx WHERE id = ?", (tx_id,)).fetchone() is None:
        raise ApiError(404, "not_found")
    merchant = db.tx_merchant(req.cid, tx_id)   # looked up here; the client never sends it
    if apply_to_merchant and merchant is None:
        raise ApiError(400, "no_merchant")
    rec = {"scope": "merchant" if apply_to_merchant else "tx", "tx_id": tx_id,
           "merchant": merchant, "label": label, "context": context}
    try:
        ov = state.add_override(req.cid, rec)
    except ValueError as e:
        if "too many" in str(e):
            raise ApiError(400, "too_many_overrides")
        raise ApiError(400, "invalid_override")
    if apply_to_merchant:
        affected = conn.execute("SELECT COUNT(*) FROM tx WHERE merchant = ?", (merchant,)).fetchone()[0]
    else:
        affected = 1
    return ov, int(affected)


def _override_public(conn, ov):
    """Override as shown to the client: no merchant id."""
    out = {"id": ov["id"], "scope": ov["scope"], "label": ov["label"],
           "context": ov.get("context") or "", "created": ov.get("created")}
    if ov["scope"] == "tx":
        out["tx_id"] = ov.get("tx_id")
        r = conn.execute("SELECT d, amount FROM tx WHERE id = ?", (ov.get("tx_id"),)).fetchone()
        out["description"] = ("One purchase on %s (%.2f EUR)" % (r[0], abs(r[1]))) if r else "One purchase"
    else:
        n = conn.execute("SELECT COUNT(*) FROM tx WHERE merchant = ?", (ov.get("merchant"),)).fetchone()[0]
        out["description"] = "Every purchase from the same merchant (%d so far)" % n
    return out


def _customer_figures(req):
    """{"monthly_income", "housing_cost"} for the area comparison, or None."""
    ins = _insights()
    try:
        income = float(ins.mortgage(req.conn, req.today).get("monthly_income") or 0)
        housing = ins.spend(req.conn, req.today, period="last_3_months", label="Housing")
        cost = float(housing.get("total") or 0) / 3.0
    except Exception:
        return None
    if income <= 0:
        return None
    return {"monthly_income": income, "housing_cost": cost}


def ep_chat(req):
    from . import coach
    msg = req.body.get("message")
    if not isinstance(msg, str):
        raise ApiError(400, "invalid_message")
    msg = msg.strip()
    if not msg or len(msg) > MAX_MESSAGE:
        raise ApiError(400, "invalid_message")
    session = req.session
    changed = {"v": False}
    # the conversation lives in the state store: an unknown or foreign id starts a new one
    conv_id = req.body.get("conversation_id")
    history = state.conversation_history(req.cid, conv_id) if isinstance(conv_id, str) else None
    if history is None:
        conv_id, history = None, []
    mems = session.setdefault("conv_memory", {})
    memory = mems.setdefault(conv_id, {}) if conv_id else {}

    def remember(tx_id, label, context=None, apply_to_merchant=False):
        ov, affected = _apply_override(req, req.conn, tx_id, label, context, bool(apply_to_merchant))
        changed["v"] = True
        return {"override": _override_public(req.conn, ov), "affected": affected}

    def area_lookup():
        if not req.consent.get("benchmarks"):
            return None
        from . import area
        return area.area_context(db.postal_code(req.cid) or "", _customer_figures(req))

    def explain(text):
        return _run_explain(text, req.consent)

    def propose_money(dest, amount, reason=""):
        """The coach can only create a proposal; the customer approves it in the app (POST /api/money/confirm)."""
        return money.propose(req.conn, req.today, req.cid, dest, amount, reason, "chat")

    def save_goal(name, target, deadline=None, monthly_needed=None):
        """'Yes, save it' after a goal plan in the chat: the same validation as POST /api/goal."""
        return state.set_goal(req.cid, {"name": name, "target": target, "saved": 0})

    ctx = SimpleNamespace(cid=req.cid,   # only the seed of the simulated receipts; no tool returns it
                          conn=req.conn, today=req.today, profile=db.profile(req.cid),
                          consent=dict(req.consent), settings=dict(req.settings),
                          bench_lookup=db.bench, goal=state.get_goal(req.cid),
                          quiz_history=state.quiz_history(req.cid),
                          challenge=state.get_challenge(req.cid),
                          area_lookup=area_lookup, remember=remember,
                          explain=explain, save_goal=save_goal, memory=memory,
                          propose_money=propose_money, holdings=money.holdings(req.cid))
    result = coach.chat(msg, history, ctx)
    session["ai_payload"] = result.pop("ai_payload", None)
    conn = req.conn
    if changed["v"]:   # a remembered category changes what the answer's rows look like
        conn = db.sandbox(req.cid, req.today, state.list_overrides(req.cid), state.list_moves(req.cid))
    try:
        result["used"] = _used_groups(conn, req.today, result.get("evidence"))
    finally:
        if conn is not req.conn:
            conn.close()
    # a pasted document never goes into the history that is sent to the AI model on later turns
    shown = result.pop("history_user", None) or msg
    turn = {"user": msg, "reply": str(result.get("reply", "")), "cards": result.get("cards") or [],
            "used": result.get("used") or [], "mode": result.get("mode"), "notice": result.get("notice"),
            "h": shown}
    new_id = state.add_turn(req.cid, conv_id, turn, shown)
    if new_id not in mems:   # a new conversation takes over the memory built during this turn
        mems[new_id] = memory
        while len(mems) > state.MAX_CONVERSATIONS:
            mems.pop(next(iter(mems)))
    result["conversation_id"] = new_id
    return result


def ep_home(req):
    cid = req.cid
    things = []
    goal = state.get_goal(cid)
    if goal:
        things.append({"id": "goal", "kind": "goal", "title": goal["name"],
                       "summary": "%s of %s saved" % (_money_text(goal["saved"]), _money_text(goal["target"])),
                       "updated": state.iso_time(state.goal_updated(cid))})
    stored = state.get_challenge(cid)
    if stored:
        view = _challenge_view(req, stored)
        things.append({"id": "challenge", "kind": "challenge",
                       "title": (view or stored).get("title") or "Your challenge",
                       "summary": str((view or {}).get("text") or "")})
    target = _saving_target(req)
    if target > 0:
        things.append({"id": "target", "kind": "target", "title": "Monthly saving target",
                       "summary": "%s a month" % _money_text(target)})
    n = len(state.list_overrides(cid))
    if n:
        things.append({"id": "learned", "kind": "learned", "title": "What I have learned",
                       "summary": "%d correction%s" % (n, "" if n == 1 else "s")})
    pts = _features().quiz_stats(state.quiz_history(cid)).get("points") or []
    if pts:
        close = sum(1 for p in pts if p.get("accuracy", 0) >= 80)
        things.append({"id": "quiz", "kind": "quiz", "title": "Quiz score",
                       "summary": "%d of %d guess%s %s close" % (
                           close, len(pts), "" if len(pts) == 1 else "es", "was" if len(pts) == 1 else "were")})
    for hd in money.holdings(cid):
        things.append({"id": "money:" + hd["id"], "kind": "money", "title": hd["name"],
                       "summary": "%s %s in S-mobiili" % (_money_text(hd["amount"]),
                                                          "saved" if hd["kind"] == "savings" else "invested")})
    for p in state.list_pins(cid):
        things.append({"id": p["id"], "kind": "pin", "title": p["title"],
                       "summary": "Kept " + state.human_date(p["created_ts"]),
                       "card_type": p["card_type"], "updated": p["created"]})
    return {"name": req.session.get("name", ""), "things": things,
            "conversations": state.list_conversations(cid)}


def _money_text(v):
    """Euro sign first, thousands comma, no decimals when whole."""
    v = float(v or 0)
    return "€{:,.0f}".format(v) if round(v, 2) == round(v) else "€{:,.2f}".format(v)


def ep_conversation(req):
    conv = state.get_conversation(req.cid, req.query.get("id"))
    if conv is None:
        raise ApiError(404, "not_found")
    return conv


def ep_conversation_delete(req):
    conv_id = req.body.get("id")
    if not isinstance(conv_id, str) or not conv_id:
        raise ApiError(400, "invalid_id")
    if not state.delete_conversation(req.cid, conv_id):
        raise ApiError(404, "not_found")
    req.session.get("conv_memory", {}).pop(conv_id, None)
    return {"ok": True}


def ep_pins(req):
    try:
        return state.add_pin(req.cid, req.body.get("title"), req.body.get("card"))
    except ValueError:
        raise ApiError(400, "invalid_pin")


def ep_pin(req):
    pin = state.get_pin(req.cid, req.query.get("id"))
    if pin is None:
        raise ApiError(404, "not_found")
    return pin


def ep_pins_remove(req):
    pid = req.body.get("id")
    if not isinstance(pid, str) or not pid:
        raise ApiError(400, "invalid_id")
    if not state.remove_pin(req.cid, pid):
        raise ApiError(404, "not_found")
    return {"ok": True}


def _run_explain(text, consent):
    """explain_text with the AI model only when AI consent is on and a key is configured (SR-4)."""
    from . import explain
    provider = config.ai_provider()
    claude = provider == "claude"
    key = config.claude_api_key() if claude else config.gemini_api_key()
    allow = bool((consent or {}).get("ai")) and bool(key)
    model = (config.claude_model() if claude else config.gemini_model()) if allow else None
    return explain.explain_text(text, api_key=key if allow else None, model=model, allow_ai=allow,
                                provider=provider or "gemini")


def ep_explain(req):
    text = req.body.get("text")
    if not isinstance(text, str):
        raise ApiError(400, "invalid_text")
    text = text.strip()
    if not EXPLAIN_MIN <= len(text) <= EXPLAIN_MAX:
        raise ApiError(400, "invalid_text")
    return _run_explain(text, state.get_consent(req.session["cid"]))   # the text is never logged


def ep_ai_payload(req):
    return req.session.get("ai_payload")


def ep_erase(req):
    state.erase(req.session["cid"])
    req.session["history"] = []
    req.session["ai_payload"] = None
    req.session.setdefault("memory", {}).clear()
    req.session.setdefault("conv_memory", {}).clear()
    return {"ok": True}


def _features():
    from . import features
    return features


def _saving_target(req):
    try:
        return float(req.settings.get("monthly_saving_target") or 0)
    except (TypeError, ValueError):
        return 0.0


def ep_afford(req):
    item = req.body.get("item")
    if not isinstance(item, str) or not item.strip() or len(item) > MAX_ITEM_CHARS:
        raise ApiError(400, "invalid_item")
    price = _num(req.body.get("price"), "price")
    if not 0 < price <= MAX_PRICE:
        raise ApiError(400, "invalid_price")
    return _features().afford(req.conn, req.today, item.strip(), price,
                              goal=state.get_goal(req.cid),
                              monthly_saving_target=_saving_target(req))


def ep_goal(req):
    if req.handler.command != "POST":
        return {"goal": state.get_goal(req.cid)}
    if req.body.get("clear") is True:
        return {"goal": state.set_goal(req.cid, None)}
    d = {k: req.body.get(k) for k in ("name", "target", "saved")}
    if d["saved"] is None:
        d["saved"] = 0
    try:
        return {"goal": state.set_goal(req.cid, d)}
    except ValueError:
        raise ApiError(400, "invalid_goal")


def ep_purchase_insight(req):
    tx_id = None
    raw = req.query.get("tx_id")
    if raw not in (None, ""):
        try:
            tx_id = int(raw)
        except ValueError:
            raise ApiError(400, "invalid_tx_id")
        if tx_id < 1:
            raise ApiError(400, "invalid_tx_id")
    elif req.settings.get("suggestion_level") == "off" or not req.consent.get("suggestions"):
        return {"text": None, "tx": None, "habit": None, "equivalents": [], "note": None,
                "explain": "Suggestions are switched off, so no note about the latest purchase is shown.",
                "evidence": []}
    return _features().purchase_insight(req.conn, req.today, tx_id)


def ep_patterns(req):
    return _features().patterns(req.conn, req.today)


def ep_goal_plan(req):
    b = req.body
    name = b.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        raise ApiError(400, "invalid_name")
    name = name.strip()
    target = _num(b.get("target"), "target", 0.01, 50_000_000, allow_none=True)
    deadline = b.get("deadline")
    if deadline in (None, ""):
        deadline = None
    elif not isinstance(deadline, str) or not re.fullmatch(r"\d{4}(-(0[1-9]|1[0-2])(-\d{2})?)?", deadline):
        raise ApiError(400, "invalid_deadline")
    saved = 0.0
    goal = state.get_goal(req.cid)
    if isinstance(goal, dict) and str(goal.get("name") or "").strip().lower() == name.lower():
        try:
            saved = max(0.0, float(goal.get("saved") or 0))
        except (TypeError, ValueError):
            saved = 0.0
    return _features().goal_plan(req.conn, req.today, name, target, deadline, saved=saved,
                                 monthly_saving_target=_saving_target(req))


def ep_leaks(req):
    try:
        months = int(req.query.get("months", "3"))
    except ValueError:
        raise ApiError(400, "invalid_months")
    if not 1 <= months <= 12:
        raise ApiError(400, "invalid_months")
    return _features().leaks(req.conn, req.today, months=months)


def ep_alerts(req):
    if req.settings.get("suggestion_level") == "off" or not req.consent.get("suggestions"):
        return {"alerts": []}
    feat = _features()
    if req.consent.get("benchmarks"):
        res = feat.alerts(req.conn, req.today, db.profile(req.cid), db.bench)
    else:
        res = feat.alerts(req.conn, req.today)
    res = dict(res)
    alerts = list(res.get("alerts") or [])
    leak = feat.savings_leakage(req.conn, req.today)
    if leak.get("flag"):
        alerts.append({"id": "savings_leak", "kind": "savings_leak", "severity": "notice",
                       "title": "Savings are covering the end of the month",
                       "detail": leak.get("text", ""), "amount": leak.get("total"),
                       "evidence": leak.get("evidence") or []})
    res["alerts"] = alerts
    return res


def ep_savings_leakage(req):
    return _features().savings_leakage(req.conn, req.today)


def ep_forecast(req):
    return _features().forecast(req.conn, req.today, monthly_saving_target=_saving_target(req))


def ep_payday_plan(req):
    return _features().payday_plan(req.conn, req.today, goal=state.get_goal(req.cid),
                                   monthly_saving_target=_saving_target(req))


def ep_overrides(req):
    if req.handler.command != "POST":
        return {"overrides": [_override_public(req.conn, o) for o in state.list_overrides(req.cid)]}
    b = req.body   # any merchant or customer id sent by the client is ignored
    ov, affected = _apply_override(req, req.conn, b.get("tx_id"), b.get("label"), b.get("context"),
                                   b.get("apply_to_merchant") is True)
    conn = db.sandbox(req.cid, req.today, state.list_overrides(req.cid), state.list_moves(req.cid))
    try:
        return {"override": _override_public(conn, ov), "affected": affected}
    finally:
        conn.close()


def ep_overrides_remove(req):
    oid = req.body.get("id")
    if isinstance(oid, bool) or not isinstance(oid, int):
        raise ApiError(400, "invalid_id")
    state.remove_override(req.cid, oid)
    return {"ok": True}


def _challenge_view(req, stored):
    if not stored:
        return None
    try:
        return _features().challenge_progress(req.conn, req.today, stored)
    except Exception:
        return None


def ep_challenge(req):
    enabled = req.settings.get("challenges") == "on"
    if req.handler.command != "POST":
        active = _challenge_view(req, state.get_challenge(req.cid))
        options = []
        if enabled:
            options = list(_features().challenge_options(req.conn, req.today).get("options") or [])
        return {"enabled": enabled, "active": active, "options": options}
    if req.body.get("stop") is True:
        state.set_challenge(req.cid, None)
        return {"active": None}
    if not enabled:
        raise ApiError(403, "challenges_off")
    wanted = req.body.get("id")
    if not isinstance(wanted, str) or not wanted or len(wanted) > 200:
        raise ApiError(400, "invalid_id")
    options = _features().challenge_options(req.conn, req.today).get("options") or []
    chosen = next((o for o in options if o.get("id") == wanted), None)
    if chosen is None:
        raise ApiError(400, "unknown_challenge")
    stored = dict(chosen)
    stored["accepted_at"] = datetime.datetime.now().replace(microsecond=0).isoformat()
    state.set_challenge(req.cid, stored)
    return {"active": _challenge_view(req, stored)}


def ep_quiz_stats(req):
    return _features().quiz_stats(state.quiz_history(req.cid))


def ep_area(req):
    if not req.consent.get("benchmarks"):
        raise ApiError(403, "consent_required")
    from . import area
    return area.area_context(db.postal_code(req.cid) or "", _customer_figures(req))


NOT_OFFERED = ("Salary", "Other income")


def ep_labels(req):
    return {"labels": [l for l in classify.ALL_LABELS if l not in NOT_OFFERED]}


ROUTES = {
    "/api/demo/personas": ("GET", ep_personas),
    "/api/demo/login": ("POST", ep_login),
    "/api/demo/random": ("POST", ep_random),
    "/api/logout": ("POST", ep_logout),
    "/api/demo/reset": ("POST", ep_demo_reset),
    "/api/me": ("GET", ep_me),
    "/api/demo/ai": ("GET|POST", ep_ai_setup),
    "/api/demo/ai/test": ("POST", ep_ai_test),
    "/api/consent": ("POST", ep_consent),
    "/api/settings": ("POST", ep_settings),
    "/api/overview": ("GET", ep_overview),
    "/api/baskets": ("GET", ep_baskets),
    "/api/safe-to-spend": ("GET", ep_safe),
    "/api/what-if": ("POST", ep_what_if),
    "/api/spender-type": ("GET", ep_spender),
    "/api/benchmarks": ("GET", ep_benchmarks),
    "/api/averages": ("GET", ep_averages),
    "/api/mortgage": ("POST", ep_mortgage),
    "/api/quiz": ("GET", ep_quiz),
    "/api/quiz/answer": ("POST", ep_quiz_answer),
    "/api/checkin": ("GET", ep_checkin),
    "/api/suggestions/action": ("POST", ep_suggestion_action),
    "/api/transactions": ("GET", ep_transactions),
    "/api/chat": ("POST", ep_chat),
    "/api/home": ("GET", ep_home),
    "/api/money": ("GET", ep_money),
    "/api/money/propose": ("POST", ep_money_propose),
    "/api/money/confirm": ("POST", ep_money_confirm),
    "/api/conversation": ("GET", ep_conversation),
    "/api/conversation/delete": ("POST", ep_conversation_delete),
    "/api/pins": ("POST", ep_pins),
    "/api/pin": ("GET", ep_pin),
    "/api/pins/remove": ("POST", ep_pins_remove),
    "/api/afford": ("POST", ep_afford),
    "/api/goal": ("GET|POST", ep_goal),
    "/api/explain": ("POST", ep_explain),
    "/api/purchase-insight": ("GET", ep_purchase_insight),
    "/api/patterns": ("GET", ep_patterns),
    "/api/goal-plan": ("POST", ep_goal_plan),
    "/api/leaks": ("GET", ep_leaks),
    "/api/alerts": ("GET", ep_alerts),
    "/api/savings-leakage": ("GET", ep_savings_leakage),
    "/api/forecast": ("GET", ep_forecast),
    "/api/payday-plan": ("GET", ep_payday_plan),
    "/api/overrides": ("GET|POST", ep_overrides),
    "/api/overrides/remove": ("POST", ep_overrides_remove),
    "/api/challenge": ("GET|POST", ep_challenge),
    "/api/quiz/stats": ("GET", ep_quiz_stats),
    "/api/area": ("GET", ep_area),
    "/api/labels": ("GET", ep_labels),
    "/api/privacy/ai-payload": ("GET", ep_ai_payload),
    "/api/privacy/erase": ("POST", ep_erase),
}


# ---------------------------------------------------------------------------

def make_server(host="127.0.0.1", port=0):
    return SvinkkiServer((host, port))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Svinkki server")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    port = args.port if args.port is not None else config.port()
    srv = make_server(args.host, port)
    provider = config.ai_provider()
    mode = {"claude": "Claude available (%s)" % config.claude_model(),
            "gemini": "Gemini available"}.get(provider, "offline coach (no API key)")
    print("Svinkki on http://%s:%d  [%s]" % (args.host, srv.server_address[1], mode))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
