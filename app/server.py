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
import secrets
import sys
import threading
import time
import urllib.parse
from collections import deque
from types import SimpleNamespace

from . import config, db, state

COOKIE = "svinkki_sid"
MAX_BODY = 16 * 1024
MAX_MESSAGE = 2000
SESSION_IDLE_SECONDS = 2 * 60 * 60
HISTORY_TURNS = 20
RATE_CHAT = 60
RATE_OTHER = 300
RATE_WINDOW = 60.0
SUGGESTION_LIMITS = {"off": 0, "few": 1, "normal": 3}

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
    "accept": "Noted. I saved your intention. No money was moved: Svinkki cannot move money, "
              "so you decide when and how to set it aside.",
    "dismiss": "Okay, I will not suggest this again. No money was moved.",
    "snooze": "Okay, I will remind you later. No money was moved.",
}

# Endpoints that work without analysis consent (everything else is a data endpoint).
NO_CONSENT_PATHS = {
    "/api/demo/personas", "/api/demo/login", "/api/demo/random", "/api/logout", "/api/me",
    "/api/consent", "/api/settings", "/api/privacy/erase",
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
                            "ai_payload": None, "hits": {"chat": deque(), "other": deque()}}
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

    def _read_json(self):
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
        if n > MAX_BODY:
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
        if method != verb and not (method == "HEAD" and verb == "GET"):
            raise ApiError(405, "method_not_allowed")

        srv = self.server
        sid = self._cookie_sid()
        session = srv.sessions.get(sid)
        self._sid = sid if session else None

        # rate limit (per session; per client address for anonymous calls)
        hits = session["hits"] if session else srv.limiter.anon_hits(self.client_address[0])
        bucket = "chat" if path == "/api/chat" else "other"
        if not srv.limiter.allow(hits, bucket):
            raise ApiError(429, "rate_limited")

        body = self._read_json() if verb == "POST" else {}
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
                req.conn = db.sandbox(req.cid, req.today)  # SR-2
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


def ep_me(req):
    cid = req.session["cid"]
    try:
        age_band = db.profile(cid).get("age_band")
    except Exception:
        age_band = None
    return {"name": req.session["name"], "age_band": age_band, "today": config.today(),
            "is_random": str(req.session["name"]).startswith("Customer "),
            "consent": state.get_consent(cid), "settings": state.get_settings(cid),
            "ai_available": bool(config.gemini_api_key())}


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
    return _insights().overview(req.conn, req.today, month=month)


def ep_baskets(req):
    period = _short_str(req.query.get("period"), "period", 20) or "last_month"
    return _insights().baskets(req.conn, req.today, period=period)


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
        clean.append({"target": target, "pct": _num(c.get("pct"), "pct", -100, 100)})
    months = req.body.get("months", 12)
    months = int(_num(months, "months", 1, 120))
    return _insights().what_if(req.conn, req.today, clean, months=months)


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
    result = _insights().quiz(req.conn, req.today)
    state.save_quiz(req.cid, str(result["quiz_id"]), result)
    return result


def ep_quiz_answer(req):
    quiz_id = req.body.get("quiz_id")
    if not isinstance(quiz_id, str) or not quiz_id or len(quiz_id) > 200:
        raise ApiError(400, "invalid_quiz_id")
    guess = _num(req.body.get("guess"), "guess", 0, 1e9)
    if state.load_quiz(req.cid, quiz_id) is None:
        raise ApiError(404, "unknown_quiz")
    if req.consent.get("benchmarks"):
        return _insights().quiz_answer(req.conn, req.today, quiz_id, guess,
                                       profile=db.profile(req.cid), bench_lookup=db.bench)
    return _insights().quiz_answer(req.conn, req.today, quiz_id, guess)


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
    checkin["suggestions"] = suggestions
    return {"due": True, "checkin": checkin}


def ep_suggestion_action(req):
    sid = req.body.get("id")
    action = req.body.get("action")
    if not isinstance(sid, str) or not sid or len(sid) > 100:
        raise ApiError(400, "invalid_id")
    if action not in state.INTENT_ACTIONS:
        raise ApiError(400, "invalid_action")
    if not req.consent.get("suggestions"):
        raise ApiError(403, "consent_required")
    state.record_intent(req.cid, sid, action)
    return {"ok": True, "message": NO_MONEY_MESSAGES[action]}


def ep_transactions(req):
    q = req.query
    try:
        limit = int(q.get("limit", 50))
    except ValueError:
        raise ApiError(400, "invalid_limit")
    limit = max(1, min(limit, 50))
    kw = {k: _short_str(q.get(k), k, 100) for k in ("label", "basket", "context", "type", "q")}
    frm = _iso_date(q.get("from"), "from")
    to = _iso_date(q.get("to"), "to")
    return _insights().transactions(req.conn, req.today, frm=frm, to=to, limit=limit, **kw)


def ep_chat(req):
    from . import coach
    msg = req.body.get("message")
    if not isinstance(msg, str):
        raise ApiError(400, "invalid_message")
    msg = msg.strip()
    if not msg or len(msg) > MAX_MESSAGE:
        raise ApiError(400, "invalid_message")
    session = req.session
    ctx = SimpleNamespace(conn=req.conn, today=req.today, profile=db.profile(req.cid),
                          consent=dict(req.consent), settings=dict(req.settings),
                          bench_lookup=db.bench)
    history = list(session["history"])
    result = coach.chat(msg, history, ctx)
    session["ai_payload"] = result.pop("ai_payload", None)
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": str(result.get("reply", ""))})
    session["history"] = history[-2 * HISTORY_TURNS:]
    return result


def ep_ai_payload(req):
    return req.session.get("ai_payload")


def ep_erase(req):
    state.erase(req.session["cid"])
    req.session["history"] = []
    req.session["ai_payload"] = None
    return {"ok": True}


ROUTES = {
    "/api/demo/personas": ("GET", ep_personas),
    "/api/demo/login": ("POST", ep_login),
    "/api/demo/random": ("POST", ep_random),
    "/api/logout": ("POST", ep_logout),
    "/api/me": ("GET", ep_me),
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
    mode = "Gemini available" if config.gemini_api_key() else "offline coach (no API key)"
    print("Svinkki on http://%s:%d  [%s]" % (args.host, srv.server_address[1], mode))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
