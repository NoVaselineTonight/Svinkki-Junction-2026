"""A stand-in for S-mobiili that embeds Svinkki, from another site (python -m app.host_demo).

Run the app first (python -m app.server --port 8030), then this (port 8031), and open
http://127.0.0.1:8031. The page is a phone-width S-mobiili shell with a "Svinkki" tab. The
"bank" has already authenticated its customer (a demo persona, Veeti by default), so its backend
asks Svinkki, server to server and with the shared host secret, for a single-use handover token
and opens the app at http://localhost:8030/embed#handover=<token>. 127.0.0.1 and localhost are
different sites, so the iframe is really cross-site, as S-mobiili would be.

Python standard library only. Demo only: the host's own "login" is a persona switcher.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.server

from . import config, db, embed

FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/host.js": ("host.js", "text/javascript; charset=utf-8"),
    "/host.css": ("host.css", "text/css; charset=utf-8"),
    "/s-mark.svg": (os.path.join("..", "brand", "s-mark.svg"), "image/svg+xml"),
}
MAX_BODY = 1024


class HostServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, app_url, app_api):
        super().__init__(addr, HostHandler)
        self.app_url = app_url.rstrip("/")      # what the browser opens (the iframe)
        self.app_api = app_api.rstrip("/")      # what this backend calls, server to server
        self.customers = []                     # [(name, cid)]: the bank knows its customers

    def load_customers(self):
        if not self.customers:
            self.customers = [(p["name"], p["cid"]) for p in db.list_personas()]
        return self.customers


class HostHandler(http.server.BaseHTTPRequestHandler):
    server_version = "S-mobiili-demo"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
                         "connect-src 'self'; frame-src %s; base-uri 'self'; form-action 'self'; "
                         "frame-ancestors 'none'" % _origin(self.server.app_url))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, "application/json; charset=utf-8", json.dumps(obj).encode("utf-8"))

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/customers":
            names = [n for n, _ in self.server.load_customers()]
            return self._json(200, {"customers": names, "default": _default(names)})
        if path not in FILES:
            return self._json(404, {"error": "not_found"})
        name, ctype = FILES[path]
        with open(os.path.join(config.repo_root(), "web", "host", name), "rb") as f:
            self._send(200, ctype, f.read())

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/open-svinkki":
            return self._json(404, {"error": "not_found"})
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).netloc != (self.headers.get("Host") or ""):
            return self._json(403, {"error": "cross_site_request"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, MAX_BODY)) or b"{}") if 0 < n <= MAX_BODY else {}
        except ValueError:
            body = {}
        names = dict(self.server.load_customers())
        who = body.get("customer") if isinstance(body, dict) else None
        cid = names.get(who) if isinstance(who, str) else None
        if cid is None:
            return self._json(400, {"error": "unknown_customer"})
        req = urllib.request.Request(
            self.server.app_api + "/api/host/handover", method="POST",
            data=json.dumps({"customer_id": cid}).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + embed.host_secret()})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                token = json.loads(r.read().decode("utf-8"))["token"]
        except (urllib.error.URLError, ValueError, KeyError) as e:
            sys.stderr.write("handover failed: %s\n" % type(e).__name__)
            return self._json(502, {"error": "svinkki_unavailable"})
        # The token goes in the fragment: never sent to a server, never in a Referer.
        return self._json(200, {"src": self.server.app_url + "/embed#handover=" + token})


def _origin(url):
    u = urllib.parse.urlsplit(url)
    return "%s://%s" % (u.scheme, u.netloc)


def _default(names):
    for n in names:
        if n.lower().startswith("veeti"):
            return n
    return names[0] if names else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="S-mobiili host demo that embeds Svinkki")
    ap.add_argument("--port", type=int, default=8031)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--app", default=None,
                    help="Svinkki as the browser sees it (default http://localhost:8030)")
    ap.add_argument("--app-api", default=None,
                    help="Svinkki as this backend calls it (default http://127.0.0.1:<app port>)")
    args = ap.parse_args(argv)
    app_url = args.app or config.get("SVINKKI_EMBED_APP_URL") or "http://localhost:8030"
    port = urllib.parse.urlsplit(app_url).port or 80
    app_api = args.app_api or "http://127.0.0.1:%d" % port
    srv = HostServer((args.host, args.port), app_url, app_api)
    print("S-mobiili host demo on http://%s:%d  (embeds %s%s)" % (
        args.host, srv.server_address[1], app_url,
        "; DEMO host secret" if embed.using_demo_secret() else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
