"""Embedding in S-mobiili: host-to-app identity handover, sessions inside a cross-site iframe,
the frame-ancestors allow-list, and CSRF safety once the cookie is SameSite=None."""
import os
import re
import time
import unittest
from unittest import mock

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

HDR = "X-Svinkki-Session"
POOL_CID = "CUST00005"      # put into the demo pool for these tests only
OUTSIDER = "CUST00004"      # a real customer who is neither a persona nor in the demo pool


def _demo_secret():
    import app.embed as embed
    return embed.DEMO_HOST_SECRET


class EmbedCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        con = fx.open_db()
        try:
            con.execute("INSERT OR IGNORE INTO demo_pool VALUES (?)", (POOL_CID,))
            con.commit()
        finally:
            con.close()
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        con = fx.open_db()
        try:
            con.execute("DELETE FROM demo_pool WHERE cid = ?", (POOL_CID,))
            con.commit()
        finally:
            con.close()

    def anon(self):
        return self.server.client()

    def handover(self, cid, secret=None, headers=None):
        hdrs = {"Authorization": "Bearer " + (secret if secret is not None else _demo_secret())}
        hdrs.update(headers or {})
        return self.anon().post("/api/host/handover", {"customer_id": cid}, headers=hdrs)

    def token(self, cid=fx.A_CID):
        r = self.handover(cid)
        self.assertEqual(r.status, 200, r.text)
        return r.json["token"]

    def exchange(self, token, client=None, extra=None):
        body = {"token": token}
        body.update(extra or {})
        return (client or self.anon()).post("/api/embed/session", body)


class HandoverTests(EmbedCase):
    def test_handover_then_exchange_gives_a_session_and_the_token_dies(self):
        tok = self.token(fx.A_CID)
        self.assertNotIn(fx.A_CID, tok)
        c = self.anon()
        r = self.exchange(tok, c)
        self.assertEqual(r.status, 200, r.text)
        self.assertTrue(r.json["session"])
        self.assertEqual(c.get("/api/me").json["name"], fx.A_NAME)
        # single use: the same token never works again, not even from another client
        self.assertEqual(self.exchange(tok).status, 400)
        self.assertEqual(self.exchange(tok, c).status, 400)

    def test_expired_token_is_refused(self):
        import app.embed as embed
        tok = self.token()
        with mock.patch.object(embed.time, "time", return_value=time.time() + embed.TOKEN_TTL_SECONDS + 5):
            self.assertEqual(self.exchange(tok).status, 400)
        self.assertEqual(self.exchange(tok).status, 400)   # an expired try also burns it

    def test_bad_signature_is_refused(self):
        tok = self.token()
        payload, sig = tok.split(".")
        forged = payload + "." + ("A" if sig[0] != "A" else "B") + sig[1:]
        self.assertEqual(self.exchange(forged).status, 400)
        # a token signed by another server instance (another key) is refused
        import app.embed as embed
        other = embed.Handovers().issue(fx.A_CID, fx.A_NAME)
        self.assertEqual(self.exchange(other).status, 400)
        for junk in ("", "x", "a.b.c", 5, None, "." * 3, "x" * 500):
            self.assertEqual(self.exchange(junk).status, 400, junk)
        # the genuine token still works after the forgeries
        self.assertEqual(self.exchange(tok).status, 200)

    def test_host_secret_is_required(self):
        self.assertEqual(self.anon().post("/api/host/handover", {"customer_id": fx.A_CID}).status, 403)
        self.assertEqual(self.handover(fx.A_CID, secret="wrong").status, 403)
        self.assertEqual(self.handover(fx.A_CID, secret="").status, 403)

    def test_demo_secret_only_from_this_computer(self):
        for headers in ({"X-Forwarded-For": "203.0.113.9"}, {"Host": "demo.example.com"}):
            self.assertEqual(self.handover(fx.A_CID, headers=headers).status, 403, headers)

    def test_a_real_secret_from_the_environment_replaces_the_demo_one(self):
        with mock.patch.dict(os.environ, {"SVINKKI_HOST_SECRET": "a-real-secret-0123456789"}):
            self.assertEqual(self.handover(fx.A_CID).status, 403)
            r = self.handover(fx.A_CID, secret="a-real-secret-0123456789",
                              headers={"X-Forwarded-For": "203.0.113.9"})
            self.assertEqual(r.status, 200, r.text)

    def test_unknown_customer_is_refused(self):
        for cid in (OUTSIDER, "CUST99999", "", None, 7, "x" * 200, "' OR 1=1 --"):
            self.assertEqual(self.handover(cid).status, 400, cid)

    def test_every_persona_and_a_pool_customer_can_be_handed_over(self):
        con = fx.open_db()
        try:
            cids = [r[0] for r in con.execute("SELECT cid FROM personas")]
        finally:
            con.close()
        for cid in cids:
            self.assertEqual(self.handover(cid).status, 200, cid)
        c = self.anon()
        self.assertEqual(self.exchange(self.token(POOL_CID), c).status, 200)
        me = c.get("/api/me").json
        self.assertTrue(me["is_random"])
        self.assertNotIn(POOL_CID, str(me))

    def test_customer_id_in_the_exchange_or_a_request_is_ignored(self):
        c = self.anon()
        r = self.exchange(self.token(fx.A_CID), c, extra={"customer_id": fx.B_CID, "cid": fx.B_CID})
        self.assertEqual(r.status, 200)
        sid = r.json["session"]
        self.assertEqual(c.get("/api/me?cid=%s&customer_id=%s" % (fx.B_CID, fx.B_CID)).json["name"], fx.A_NAME)
        bare = self.anon()
        self.assertEqual(bare.get("/api/me?cid=" + fx.B_CID, headers={HDR: sid}).json["name"], fx.A_NAME)


class HeaderSessionTests(EmbedCase):
    def test_header_session_is_accepted_like_the_cookie(self):
        r = self.exchange(self.token(fx.A_CID))
        sid = r.json["session"]
        bare = self.anon()                       # no cookie at all: third-party cookies blocked
        self.assertEqual(bare.get("/api/me").status, 401)
        r = bare.get("/api/me", headers={HDR: sid})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json["name"], fx.A_NAME)
        r = bare.post("/api/consent", fx.ALL_CONSENT, headers={HDR: sid})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(bare.post("/api/logout", {}, headers={HDR: sid}).status, 200)
        self.assertEqual(bare.get("/api/me", headers={HDR: sid}).status, 401)

    def test_a_wrong_header_session_is_not_logged_in(self):
        self.assertEqual(self.anon().get("/api/me", headers={HDR: "nope"}).status, 401)


class CookieTests(EmbedCase):
    def _cookies(self, headers=None):
        c = self.anon()
        r = c.post("/api/embed/session", {"token": self.token()}, headers=headers)
        self.assertEqual(r.status, 200, r.text)
        out = {}
        for h in r.set_cookies():
            out[h.split("=", 1)[0]] = h
        return out, r.json["session"]

    def test_cookie_works_in_a_cross_site_iframe_on_a_secure_origin(self):
        for headers in (None, {"Host": "localhost:8030"}, {"X-Forwarded-Proto": "https"}):
            cks, sid = self._cookies(headers)
            ck = cks["svinkki_xsid"]
            self.assertTrue(ck.startswith("svinkki_xsid=%s;" % sid), headers)
            self.assertRegex(ck, r"(?i);\s*SameSite=None", headers)
            self.assertRegex(ck, r"(?i);\s*Secure", headers)
            self.assertRegex(ck, r"(?i);\s*HttpOnly", headers)
            self.assertRegex(ck, r"(?i);\s*Partitioned", headers)
            # the first-party cookie stays Lax, for the app opened directly and plain clients
            self.assertRegex(cks["svinkki_sid"], r"(?i)SameSite=Lax")
        # a browser in the iframe that sends only the cross-site cookie is logged in
        r = self.anon().get("/api/me", headers={"Cookie": "svinkki_xsid=" + sid})
        self.assertEqual(r.status, 200, r.text)

    def test_plain_http_on_another_host_keeps_only_lax(self):
        # a Secure cookie would be dropped on plain http (a phone on the LAN)
        cks, _ = self._cookies({"Host": "192.168.1.20:8000"})
        self.assertNotIn("svinkki_xsid", cks)
        self.assertRegex(cks["svinkki_sid"], r"(?i)SameSite=Lax")

    def test_picker_login_gets_the_same_cookies(self):
        c = self.anon()
        p = fx.personas(c)[0]
        r = c.post("/api/demo/login", {"id": p["id"]})
        names = [h.split("=", 1)[0] for h in r.set_cookies()]
        self.assertIn("svinkki_xsid", names)
        self.assertNotIn("session", r.json)      # the picker never hands the id to JavaScript
        r = c.post("/api/logout", {})
        self.assertTrue(any(h.startswith("svinkki_xsid=;") and "Max-Age=0" in h for h in r.set_cookies()))


class CsrfTests(EmbedCase):
    def test_cross_site_post_with_the_cookie_is_refused(self):
        c = fx.session(self.server, "A", True)
        own = self.server.base
        r = c.post("/api/settings", {"quiz": "off"}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status, 403)
        r = c.post("/api/privacy/erase", {}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(r.status, 403)
        r = c.post("/api/logout", {}, headers={"Origin": "null"})
        self.assertEqual(r.status, 403)
        self.assertEqual(c.get("/api/me").status, 200)          # still logged in
        # the app itself (also inside the iframe) posts with its own origin
        r = c.post("/api/consent", fx.ALL_CONSENT, headers={"Origin": own, "Sec-Fetch-Site": "same-origin"})
        self.assertEqual(r.status, 200, r.text)

    def test_cross_site_login_is_refused(self):
        c = self.anon()
        p = fx.personas(c)[0]
        r = c.post("/api/demo/login", {"id": p["id"]}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status, 403)
        r = c.post("/api/embed/session", {"token": self.token()}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status, 403)


class FrameAncestorTests(EmbedCase):
    def _fa(self, path="/"):
        csp = fx.raw_get(self.server.base, path).header("Content-Security-Policy") or ""
        m = re.search(r"frame-ancestors([^;]*)", csp)
        self.assertTrue(m, csp)
        return m.group(1).split()

    def test_default_allows_self_and_the_local_host_demo_only(self):
        for path in ("/", "/api/me", "/embed"):
            fa = self._fa(path)
            self.assertNotIn("*", fa, path)
            self.assertIn("'self'", fa, path)
            self.assertIn("http://127.0.0.1:8031", fa, path)

    def test_allow_list_from_the_environment(self):
        env = {"SVINKKI_FRAME_ANCESTORS": "https://s-mobiili.example, https://*.s-pankki.fi;script-src * 'unsafe-inline'"}
        with mock.patch.dict(os.environ, env):
            fa = self._fa()
            csp = fx.raw_get(self.server.base, "/").header("Content-Security-Policy")
        self.assertEqual(fa, ["https://s-mobiili.example"])
        self.assertNotIn("unsafe-inline", csp)
        self.assertEqual(len(re.findall(r"script-src", csp)), 1)


class EmbedPageTests(EmbedCase):
    def test_embed_page_loads_embed_js_before_app_js(self):
        r = fx.raw_get(self.server.base, "/embed")
        self.assertEqual(r.status, 200)
        self.assertIn("text/html", r.header("Content-Type"))
        self.assertLess(r.text.index('src="embed.js"'), r.text.index('src="app.js"'))
        js = fx.raw_get(self.server.base, "/embed.js")
        self.assertEqual(js.status, 200)
        self.assertIn(HDR, js.text)
        self.assertNotIn("embed.js", fx.raw_get(self.server.base, "/").text)   # the normal demo is unchanged


class HostDemoTests(EmbedCase):
    """python -m app.host_demo: the S-mobiili stand-in gets a handover and opens the app with it."""

    def setUp(self):
        import threading
        import app.host_demo as host_demo
        self.host = host_demo.HostServer(("127.0.0.1", 0), self.server.base, self.server.base)
        threading.Thread(target=self.host.serve_forever, daemon=True).start()
        self.hbase = "http://127.0.0.1:%d" % self.host.server_address[1]

    def tearDown(self):
        self.host.shutdown()
        self.host.server_close()

    def test_host_opens_the_app_with_a_fragment_token(self):
        h = fx.Client(self.hbase)
        page = h.get("/")
        self.assertEqual(page.status, 200)
        self.assertIn('id="svinkki"', page.text)
        self.assertIn("frame-src " + self.server.base, page.header("Content-Security-Policy"))
        names = h.get("/api/customers").json["customers"]
        self.assertIn(fx.A_NAME, names)
        r = h.post("/api/open-svinkki", {"customer": fx.A_NAME})
        self.assertEqual(r.status, 200, r.text)
        prefix = self.server.base + "/embed#handover="
        self.assertTrue(r.json["src"].startswith(prefix), r.json)
        c = self.anon()
        self.assertEqual(self.exchange(r.json["src"][len(prefix):], c).status, 200)
        self.assertEqual(c.get("/api/me").json["name"], fx.A_NAME)
        self.assertEqual(h.post("/api/open-svinkki", {"customer": "Nobody"}).status, 400)
        self.assertEqual(h.post("/api/open-svinkki", {"customer": fx.A_NAME},
                                headers={"Origin": "https://evil.example"}).status, 403)


if __name__ == "__main__":
    unittest.main()
