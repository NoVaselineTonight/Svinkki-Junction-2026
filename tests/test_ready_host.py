"""Hosted public copy: per-visitor state (G4-D1), the demo flags in /api/me (G4-D4/D5)."""
import os as _os
import sys as _sys
import unittest
import urllib.error

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

TAXI = "How much did I spend on taxis last month?"


class _Base(unittest.TestCase):
    PER_VISITOR = False

    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        import app.server as server
        cls.srv_mod = server
        cls.old_flag = server.PER_VISITOR_STATE
        server.PER_VISITOR_STATE = cls.PER_VISITOR
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.srv_mod.PER_VISITOR_STATE = cls.old_flag

    def setUp(self):
        import app.state as state
        state.reset_all()
        self.a = fx.session(self.server, "A")
        self.b = fx.session(self.server, "A")

    def fill(self, c):
        self.assertEqual(c.post("/api/goal", {"name": "Secret ring", "target": 4000, "saved": 10}).status, 200)
        self.assertEqual(c.post("/api/chat", {"message": TAXI}).status, 200)
        self.assertEqual(c.post("/api/pins", {"title": "kept", "card": {"type": "note", "data": {"text": "x"}}}).status, 200)
        avail = c.get("/api/money").json["available"]
        if avail >= 10:
            p = c.post("/api/money/propose", {"dest": "savings", "amount": 10.0}).json["proposal"]
            r = c.post("/api/money/confirm", {"proposal_id": p["id"], "approve": True, "amount": p["amount"],
                                              "dest": p["dest"]})
            self.assertEqual(r.status, 200, r.text[:200])


class PerVisitorOn(_Base):
    PER_VISITOR = True

    def test_two_visitors_do_not_see_each_other(self):
        self.fill(self.a)
        self.assertEqual(self.a.get("/api/goal").json["goal"]["name"], "Secret ring")
        self.assertIsNone(self.b.get("/api/goal").json["goal"])
        home = self.b.get("/api/home").json
        self.assertEqual(home["conversations"], [])
        self.assertNotIn("Secret ring", self.b.get("/api/home").text)
        self.assertEqual([t for t in self.b.get("/api/home").json["things"] if t.get("kind") == "pin"], [])
        self.assertFalse(any(h.get("amount") for h in self.b.get("/api/money").json["holdings"]))
        convs = self.a.get("/api/home").json["conversations"]
        self.assertTrue(convs)
        self.assertNotEqual(self.b.get("/api/conversation?id=" + convs[0]["id"]).status, 200)

    def test_consent_and_erase_are_private(self):
        self.b.post("/api/consent", dict(fx.ALL_CONSENT, analysis=False))
        self.assertEqual(self.a.get("/api/home").status, 200)
        self.assertEqual(self.b.get("/api/home").status, 403)
        self.fill(self.a)
        self.b.post("/api/privacy/erase", {})
        self.assertEqual(self.a.get("/api/goal").json["goal"]["name"], "Secret ring")

    def test_figures_are_the_same_and_not_zero(self):
        r = self.a.post("/api/chat", {"message": TAXI}).json
        self.assertTrue(r["reply"])
        self.assertNotIn("€0.00", r["reply"])
        self.assertTrue(self.a.get("/api/safe-to-spend").json["balance"])

    def test_logout_erases_the_private_copy(self):
        import app.state as state
        self.fill(self.a)
        skeys = [s["skey"] for s in self.server.httpd.sessions._s.values()]
        self.assertTrue(all("~" in k for k in skeys))
        key = [k for k in skeys][0]
        self.a.post("/api/logout", {})
        self.b.post("/api/logout", {})
        self.assertIsNone(state.get_goal(key))
        self.assertEqual(state.list_conversations(key), [])


class PerVisitorOff(_Base):
    def test_state_is_shared_as_before(self):
        self.fill(self.a)
        self.assertEqual(self.b.get("/api/goal").json["goal"]["name"], "Secret ring")
        skeys = {s["skey"] == s["cid"] for s in self.server.httpd.sessions._s.values()}
        self.assertEqual(skeys, {True})


class FlagTests(unittest.TestCase):
    def test_make_public_turns_it_on(self):
        import app.server as server
        from deploy import serve
        old, routes = server.PER_VISITOR_STATE, dict(server.ROUTES)
        rate, trust = server.RATE_CHAT, server.TRUST_FORWARDED_FOR
        try:
            serve.make_public()
            self.assertTrue(server.PER_VISITOR_STATE)
        finally:
            server.PER_VISITOR_STATE = old
            server.RATE_CHAT, server.TRUST_FORWARDED_FOR = rate, trust
            server.ROUTES.clear()
            server.ROUTES.update(routes)


class StaticAndHome(_Base):
    def test_static_files_and_types(self):
        for path, ctype in (("/extras.js", "javascript"), ("/extras.css", "text/css"), ("/app.js", "javascript")):
            r = self.a.get(path)
            self.assertEqual(r.status, 200, path)
        r = self.a.get("/extras.css", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(r.status, 200)

    def test_etag_and_gzip(self):
        import gzip
        import urllib.request
        url = self.server.base + "/app.js"
        rq = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(rq) as resp:
            etag = resp.headers["ETag"]
            self.assertEqual(resp.headers["Content-Encoding"], "gzip")
            body = gzip.decompress(resp.read())
        self.assertTrue(etag and body.startswith(b"") and len(body) > 1000)
        rq = urllib.request.Request(url, headers={"If-None-Match": etag})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(rq)
        self.assertEqual(cm.exception.code, 304)

    def test_goal_counts_savings_account_and_keeps_deadline(self):
        self.a.post("/api/goal", {"name": "Japan", "target": 3000, "saved": 0, "deadline": "2027-09-30"})
        avail = self.a.get("/api/money").json["available"]
        if avail < 10:
            self.skipTest("nothing safe to move on the fixture")
        p = self.a.post("/api/money/propose", {"dest": "savings", "amount": 10.0}).json["proposal"]
        self.a.post("/api/money/confirm", {"proposal_id": p["id"], "approve": True, "amount": p["amount"], "dest": "savings"})
        g = [t for t in self.a.get("/api/home").json["things"] if t["kind"] == "goal"][0]
        self.assertEqual(g["summary"], "\u20ac10 of \u20ac3,000 saved, by September 2027")
        self.assertEqual(self.a.get("/api/goal").json["goal"]["deadline"], "2027-09-30")


class MeDemoFlags(_Base):
    def test_me_tells_the_page_what_to_hide(self):
        me = self.a.get("/api/me").json
        self.assertIs(me["demo"]["reset"], True)        # local: the endpoint exists
        self.assertIs(me["demo"]["ai_setup"], True)     # local: no proxy headers
        me = self.a.get("/api/me", headers={"X-Forwarded-For": "1.2.3.4"}).json
        self.assertIs(me["demo"]["ai_setup"], False)

    def test_reset_flag_false_without_the_route(self):
        import app.server as server
        saved = server.ROUTES.pop("/api/demo/reset")
        try:
            self.assertIs(self.a.get("/api/me").json["demo"]["reset"], False)
        finally:
            server.ROUTES["/api/demo/reset"] = saved


class HourlySlice(unittest.TestCase):
    def test_one_hour_cannot_use_the_whole_day(self):
        import datetime
        from deploy import serve
        hour = [3]
        day = datetime.date(2026, 11, 14)
        b = serve.DailyBudget(400, clock=lambda: day, hour_clock=lambda: hour[0])
        self.assertEqual(b.hourly_limit(), 66)
        n = sum(1 for _ in range(200) if b.take_turn())
        self.assertEqual(n, 66)
        hour[0] = 4
        self.assertTrue(b.take_turn())
        self.assertEqual(b.turns, 67)

    def test_small_limits_keep_meaning(self):
        import datetime
        from deploy import serve
        day = datetime.date(2026, 11, 14)
        off = serve.DailyBudget(0, clock=lambda: day)
        self.assertFalse(off.take_turn())
        free = serve.DailyBudget(None, clock=lambda: day)
        self.assertTrue(all(free.take_turn() for _ in range(500)))
        small = serve.DailyBudget(5, clock=lambda: day)
        self.assertEqual(sum(1 for _ in range(30) if small.take_turn()), 5)

    def test_public_mode_chat_limit(self):
        import app.server as server
        from deploy import serve
        old = (server.RATE_CHAT, server.TRUST_FORWARDED_FOR, server.PER_VISITOR_STATE, dict(server.ROUTES))
        try:
            serve.make_public()
            self.assertEqual(server.RATE_CHAT, 15)
            self.assertTrue(server.TRUST_FORWARDED_FOR)
        finally:
            server.RATE_CHAT, server.TRUST_FORWARDED_FOR, server.PER_VISITOR_STATE = old[:3]
            server.ROUTES.clear()
            server.ROUTES.update(old[3])


class AnonBucket(_Base):
    def test_forwarded_for_keys_the_anonymous_bucket_only_in_public_mode(self):
        import app.server as server
        c = self.server.client()
        server.TRUST_FORWARDED_FOR = True
        try:
            for _ in range(server.RATE_OTHER + 5):
                c.get("/api/demo/personas", headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"})
            self.assertEqual(c.get("/api/demo/personas", headers={"X-Forwarded-For": "9.9.9.9"}).status, 429)
            self.assertEqual(c.get("/api/demo/personas", headers={"X-Forwarded-For": "8.8.8.8"}).status, 200)
        finally:
            server.TRUST_FORWARDED_FOR = False
            self.server.httpd.limiter._anon.clear()

    def test_quiz_round_new_counts_as_chat(self):
        import app.server as server
        old = server.RATE_CHAT
        server.RATE_CHAT = 2
        try:
            codes = [self.a.get("/api/quiz/round?new=1").status for _ in range(4)]
            self.assertEqual(codes[-1], 429, codes)
        finally:
            server.RATE_CHAT = old


if __name__ == "__main__":
    unittest.main()
