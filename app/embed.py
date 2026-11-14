"""Embedding Svinkki in a host app (S-mobiili): identity handover and frame-ancestor policy.

The host has already authenticated its customer. Its backend asks Svinkki, server to server and
with a shared host secret, for a short-lived, single-use, signed handover token for that customer.
The host opens Svinkki with the token in the URL fragment (never sent to a server, never in a
Referer); the app posts it once to /api/embed/session and gets a session. The token then is dead.

The token carries no customer id: it is a random id plus an expiry, signed with a key that lives
only in this process. The customer it stands for is kept here, in memory, until it is used.

Python standard library only.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time

from . import config, db

TOKEN_TTL_SECONDS = 60
MAX_PENDING = 1000

# Demo only. A real host sets SVINKKI_HOST_SECRET; with this default the handover endpoint
# accepts calls only from this computer (see server.ep_host_handover).
DEMO_HOST_SECRET = "svinkki-demo-host-secret-NOT-FOR-PRODUCTION"

# The local host demo (python -m app.host_demo) runs on port 8031 of 127.0.0.1, a different
# site from http://localhost:8030, so the embedded case is really cross-site.
DEFAULT_FRAME_ANCESTORS = "'self' http://127.0.0.1:8031 http://localhost:8031"
_SOURCE_RE = re.compile(r"^(?:'self'|'none'|https?://[A-Za-z0-9.\-\[\]:]+|https?://\*\.[A-Za-z0-9.\-]+(?::\d+)?)$")


def host_secret():
    return config.get("SVINKKI_HOST_SECRET") or DEMO_HOST_SECRET


def using_demo_secret():
    return host_secret() == DEMO_HOST_SECRET


def frame_ancestors():
    """The CSP frame-ancestors sources: SVINKKI_FRAME_ANCESTORS (space or comma separated)
    or the default. Anything that is not a plain origin, 'self' or 'none' is dropped, so a typo
    cannot inject another CSP directive. An empty result means 'self'."""
    raw = config.get("SVINKKI_FRAME_ANCESTORS") or DEFAULT_FRAME_ANCESTORS
    out = []
    for src in re.split(r"[\s,]+", raw):
        if src and _SOURCE_RE.match(src) and src not in out:
            out.append(src.rstrip("/"))
    if "'none'" in out:
        return "'none'"
    return " ".join(out) or "'self'"


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Handovers:
    """Pending handover tokens: issue, then redeem exactly once before they expire."""

    def __init__(self, ttl=TOKEN_TTL_SECONDS):
        self._key = secrets.token_bytes(32)   # per process: a restart kills every pending token
        self._ttl = ttl
        self._lock = threading.Lock()
        self._pending = {}                    # jti -> {"cid", "name", "exp"}

    def _sign(self, payload):
        return _b64(hmac.new(self._key, payload.encode("ascii"), hashlib.sha256).digest())

    def issue(self, cid, name, now=None):
        now = time.time() if now is None else now
        jti = secrets.token_urlsafe(18)
        exp = int(now + self._ttl)
        payload = _b64(json.dumps({"j": jti, "e": exp}, separators=(",", ":")).encode("ascii"))
        with self._lock:
            self._purge(now)
            if len(self._pending) >= MAX_PENDING:
                return None
            self._pending[jti] = {"cid": cid, "name": name, "exp": exp}
        return "%s.%s" % (payload, self._sign(payload))

    def redeem(self, token, now=None):
        """The {cid, name} the token stands for, or None. A redeemed token is gone for good."""
        now = time.time() if now is None else now
        if not isinstance(token, str) or len(token) > 400 or token.count(".") != 1:
            return None
        payload, sig = token.split(".")
        if not hmac.compare_digest(sig.encode("ascii", "replace"), self._sign(payload).encode("ascii")):
            return None
        try:
            data = json.loads(_unb64(payload).decode("ascii"))
            jti, exp = data["j"], int(data["e"])
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return None
        with self._lock:
            entry = self._pending.pop(jti, None)   # popped even when expired: never usable again
        if entry is None or now > exp or now > entry["exp"]:
            return None
        return {"cid": entry["cid"], "name": entry["name"]}

    def _purge(self, now):
        for k in [k for k, v in self._pending.items() if now > v["exp"]]:
            del self._pending[k]


def demo_customer(cid, personas):
    """The display name for a customer the demo host may hand over, or None.

    Only the demo personas and the random-customer pool the picker draws from are allowed.
    `personas` is the server's persona map (token -> {cid, name})."""
    if not isinstance(cid, str) or not cid or len(cid) > 64:
        return None
    for p in personas.values():
        if p.get("cid") == cid:
            return p.get("name") or "Customer"
    try:
        conn = db._ro()
        try:
            hit = conn.execute("SELECT 1 FROM demo_pool WHERE cid = ?", (cid,)).fetchone()
        finally:
            conn.close()
    except Exception:
        hit = None
    if hit is None:
        return None
    return "Customer %d" % (1000 + secrets.randbelow(9000))
