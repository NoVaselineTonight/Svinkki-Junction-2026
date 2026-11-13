"""Wave 3 over HTTP and through the coach: /api/explain, /api/purchase-insight, /api/patterns, /api/goal-plan,
goals in chat, pattern follow-up, explain routing.

Acceptance: W12 to W15; plan: SR-1, SR-6, SR-10, SR-16, SR-17, SR-18, SR-22, V5, V17.
"""
import io
import json
import logging
import re
import sys
import time
import unittest
from types import SimpleNamespace

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_wave2 as f2
import fixture_wave3 as f3

TODAY = fx.TODAY
A = fx.A_CID
AMOUNT = re.compile(r"€\s*\d|\d[\d\s.,]*\s*(?:€|eur\b|euroa?\b)", re.I)
SETTINGS = {"checkin_frequency": "monthly", "suggestion_level": "few", "quiz": "weekly",
            "monthly_saving_target": 0, "challenges": "off"}


class capture_logs:
    """Everything the process writes to stdout, stderr and the logging module (same approach as V17)."""

    def __enter__(self):
        self.buf = io.StringIO()
        self.old = (sys.stdout, sys.stderr)
        sys.stdout = sys.stderr = self.buf
        self.handler = logging.StreamHandler(self.buf)
        root = logging.getLogger()
        self.level = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(self.handler)
        return self

    def __exit__(self, *exc):
        time.sleep(0.4)
        logging.getLogger().removeHandler(self.handler)
        logging.getLogger().setLevel(self.level)
        sys.stdout, sys.stderr = self.old
        return False

    @property
    def text(self):
        return self.buf.getvalue()


class Http3Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self._clients = []

    def tearDown(self):
        for c in self._clients:
            try:
                c.post("/api/privacy/erase", {})
            except Exception:                                  # noqa: BLE001
                pass

    def session(self, who="A", consent=True, **overrides):
        c = fx.session(self.server, who, consent, **overrides)
        self._clients.append(c)
        return c

    def anon(self):
        c = self.server.client()
        self._clients.append(c)
        return c

    def set_settings(self, c, **kw):
        body = dict(SETTINGS)
        body.update(kw)
        r = c.post("/api/settings", body)
        self.assertEqual(r.status, 200, r.text)
        return r.json


# ---------------------------------------------------------------------------------------------
class ExplainEndpointTests(Http3Case):
    def test_SR1_explain_needs_a_session(self):
        r = self.anon().post("/api/explain", {"text": f3.LOAN_FI})
        self.assertEqual(r.status, 401)

    def test_W12_works_before_analysis_consent(self):
        c = self.session("A", consent=False)
        r = c.post("/api/explain", {"text": f3.LOAN_FI})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json["mode"], "offline", "no AI consent, so no model")
        self.assertEqual(r.json["language"], "fi")
        self.assertTrue(r.json["terms"])

    def test_SR16_too_short_too_long_and_missing_text_are_400(self):
        c = self.session("A")
        for body in ({"text": "short"}, {"text": "x" * 39}, {"text": "lainan korko " * 600}, {"text": "a " * 4000},
                     {}, {"text": 12345}, {"text": None}):
            r = c.post("/api/explain", body)
            self.assertEqual(r.status, 400, (str(body)[:40], r.text[:120]))
            self.assertIn("error", r.json)
            self.assertNotRegex(r.text, r'Traceback|File "|\.py"')

    def test_W12_text_up_to_6000_characters_is_accepted_over_http(self):
        c = self.session("A")
        text = ("lainan korko " * 600)[:6000]
        r = c.post("/api/explain", {"text": text})
        self.assertEqual(r.status, 200, r.text[:200])

    def test_SR6_ai_consent_off_gives_offline_even_with_a_key(self):
        c = self.session("A", ai=False)
        fake = fx.FakeGemini([fx.gem_text(json.dumps({"summary": "x", "key_points": [], "terms": [], "watch_out": []}))])
        with fx.patched_gemini(fake):
            r = c.post("/api/explain", {"text": f3.LOAN_FI})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json["mode"], "offline")
        self.assertEqual(fake.calls, 0, "no AI consent: the model must not be called")

    def test_SR22_with_ai_consent_the_model_gets_no_personal_details(self):
        c = self.session("A")
        pasted = "%s Henkilötunnus %s, tili %s, sähköposti %s, puhelin %s." % (
            f3.LOAN_FI, f3.HETU, f3.IBAN, f3.EMAIL, f3.PHONE)
        reply = json.dumps({"summary": "Lainan selitys.", "key_points": ["Korko 6,2 %."],
                            "terms": [{"term": "euribor", "meaning": "Viitekorko."}], "watch_out": []})
        fake = fx.FakeGemini([fx.gem_text(reply)])
        with fx.patched_gemini(fake):
            r = c.post("/api/explain", {"text": pasted})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json["mode"], "gemini")
        self.assertGreaterEqual(r.json["redactions"], 4)
        body = fake.all_text()
        for secret in (f3.HETU, f3.IBAN, f3.EMAIL, f3.PHONE, "123 4567"):
            self.assertNotIn(secret, body)
        self.assertNotIn(f3.HETU, r.text)

    def test_V17_pasted_text_is_never_logged(self):
        c = self.session("A")
        marker = "QUOKKAMARKER88213"
        pasted = "%s Huomio %s ja henkilötunnus %s." % (f3.LOAN_FI, marker, f3.HETU)
        with capture_logs() as logs:
            c.post("/api/explain", {"text": pasted})
            c.post("/api/explain", {"text": "x" * 7000 + marker})
            fake = fx.FakeGemini([fx.gem_text("not json")])
            with fx.patched_gemini(fake):
                c.post("/api/explain", {"text": pasted})
        self.assertNotIn(marker, logs.text)
        self.assertNotIn(f3.HETU, logs.text)
        self.assertNotIn("avausmaksu", logs.text.lower(), "no part of the pasted text in logs")


# ---------------------------------------------------------------------------------------------
class GatingTests(Http3Case):
    GET = ["/api/purchase-insight", "/api/patterns"]
    POST = [("/api/goal-plan", {"name": "Japan", "target": 3000, "deadline": "2027"})]

    def test_SR1_new_endpoints_return_401_without_a_session(self):
        c = self.anon()
        for path in self.GET:
            self.assertEqual(c.get(path).status, 401, path)
        for path, body in self.POST:
            self.assertEqual(c.post(path, body).status, 401, path)

    def test_SR6_new_endpoints_return_403_consent_required_without_analysis_consent(self):
        c = self.session("A", consent=False)
        for path in self.GET:
            r = c.get(path)
            self.assertEqual(r.status, 403, path)
            self.assertEqual(r.json.get("error"), "consent_required", path)
        for path, body in self.POST:
            r = c.post(path, body)
            self.assertEqual(r.status, 403, path)
            self.assertEqual(r.json.get("error"), "consent_required", path)


# ---------------------------------------------------------------------------------------------
class DataEndpointTests(Http3Case):
    def test_W13_purchase_insight_returns_the_documented_shape(self):
        c = self.session("A")
        r = c.get("/api/purchase-insight")
        self.assertEqual(r.status, 200, r.text)
        for k in ("tx", "habit", "text", "equivalents", "note", "explain", "evidence"):
            self.assertIn(k, r.json)
        self.assertTrue(r.json["tx"]["d"] <= TODAY)

    def test_W13_suggestion_level_off_returns_no_text(self):
        c = self.session("A")
        self.set_settings(c, suggestion_level="off")
        r = c.get("/api/purchase-insight")
        self.assertEqual(r.status, 200, r.text)
        self.assertIsNone(r.json.get("text"))

    def test_W14_patterns_shape_and_limit(self):
        c = self.session("A")
        r = c.get("/api/patterns")
        self.assertEqual(r.status, 200, r.text)
        self.assertIn("patterns", r.json)
        self.assertLessEqual(len(r.json["patterns"]), 3)
        self.assertNotRegex(r.text, r"CUST\d{5}|MX\d{5}")

    def test_W15_goal_plan_computes_and_uses_the_stored_goal(self):
        c = self.session("A")
        r = c.post("/api/goal-plan", {"name": "Japan", "target": 3000, "deadline": "2027"})
        self.assertEqual(r.status, 200, r.text)
        d = r.json
        self.assertEqual(d["needs"], [])
        import math
        exact = (3000 - d["saved"]) / d["months_left"]          # M13: one rounding, up to whole euros
        self.assertEqual(d["monthly_needed"], float(math.ceil(round(exact, 6))))
        self.assertTrue(exact <= d["monthly_needed"] < exact + 1)
        self.assertEqual(d["saved"], 0)
        self.assertEqual(c.post("/api/goal", {"name": "Japan", "target": 3000, "saved": 500}).status, 200)
        r2 = c.post("/api/goal-plan", {"name": "Japan", "target": 3000, "deadline": "2027"})
        self.assertEqual(r2.json["saved"], 500)
        exact2 = 2500 / r2.json["months_left"]
        self.assertEqual(r2.json["monthly_needed"], float(math.ceil(round(exact2, 6))))
        self.assertTrue(exact2 <= r2.json["monthly_needed"] < exact2 + 1)

    def test_W15_goal_plan_without_target_asks_for_it(self):
        c = self.session("A")
        r = c.post("/api/goal-plan", {"name": "Japan", "deadline": "2027"})
        self.assertEqual(r.status, 200, r.text)
        self.assertIn("target", r.json["needs"])
        self.assertIsNone(r.json["monthly_needed"])
        self.assertNotRegex(r.json["text"], AMOUNT)

    def test_SR16_goal_plan_rejects_bad_input(self):
        c = self.session("A")
        for body in ({"name": "Japan", "target": -5, "deadline": "2027"},
                     {"name": "x" * 1000, "target": 3000, "deadline": "2027"},
                     {"name": "Japan", "target": "lots", "deadline": "2027"},
                     {"name": "Japan", "target": 3000, "deadline": "someday"},
                     {"target": 3000, "deadline": "2027"}):
            r = c.post("/api/goal-plan", body)
            self.assertEqual(r.status, 400, (str(body)[:60], r.text[:120]))
            self.assertIn("error", r.json)
            self.assertNotRegex(r.text, r'Traceback|File "|\.py"')


# ---------------------------------------------------------------------------------------------
class ChatWave3Tests(Http3Case):
    def chat(self, c, msg, conversation_id=None):
        body = {"message": msg}
        if conversation_id:     # a follow-up belongs to the conversation the first answer started
            body["conversation_id"] = conversation_id
        r = c.post("/api/chat", body)
        self.assertEqual(r.status, 200, r.text)
        return r.json

    def goal_card(self, r):
        cards = [x for x in r["cards"] if x["type"] == "goal_plan"]
        return cards[0]["data"] if cards else None

    def oracle(self, target, deadline):
        import app.features as features
        return features.goal_plan(fx.sandbox(A), TODAY, "Japan", target, deadline)

    def run_goal_flow(self, first, second):
        c = self.session("A")
        r1 = self.chat(c, first)
        self.assertEqual(r1["mode"], "offline")
        self.assertIn("plan_goal_by_date", r1["tools_used"])
        self.assertIn("?", r1["reply"], "it asks for the amount")
        self.assertNotRegex(r1["reply"], AMOUNT, "SR-10: no price may be invented")
        card1 = self.goal_card(r1)
        if card1 is not None:
            self.assertIsNone(card1["monthly_needed"])
        r2 = self.chat(c, second, r1.get("conversation_id"))
        data = self.goal_card(r2)
        self.assertIsNotNone(data, [x["type"] for x in r2["cards"]])
        want = self.oracle(3000.0, "2027")
        self.assertAlmostEqual(data["target"], 3000.0, places=2)
        self.assertAlmostEqual(data["monthly_needed"], want["monthly_needed"], delta=0.011)
        self.assertTrue(fx.text_has_amount(r2["reply"], want["monthly_needed"], abs_tol=1.0), r2["reply"])
        self.assertIsNone(c.get("/api/goal").json["goal"], "the chat never stores a goal")

    def test_W15_english_goal_asks_for_amount_then_plans(self):
        self.run_goal_flow("I want to go to Japan in 2027", "about 3000")

    def test_W15_finnish_goal_asks_for_amount_then_plans(self):
        self.run_goal_flow("Haluan Japaniin 2027", "noin 3000 euroa")

    def test_W15_other_phrasings_use_the_goal_tool(self):
        c = self.session("A")
        for msg in ("save for a car by June 2027", "I need 3000 for a trip next summer"):
            with self.subTest(msg):
                r = self.chat(c, msg)
                self.assertIn("plan_goal_by_date", r["tools_used"], r["tools_used"])
                self.assertIsNone(c.get("/api/goal").json["goal"])

    def test_W15_a_pending_goal_belongs_to_its_session_only(self):
        a = self.session("A")
        self.chat(a, "I want to go to Japan in 2027")
        b = self.session("B")
        r = self.chat(b, "about 3000")
        card = self.goal_card(r)
        self.assertTrue(card is None or card.get("monthly_needed") is None,
                        "another session's pending goal leaked: %r" % card)
        self.assertNotIn("plan_goal_by_date", r["tools_used"])
        self.assertIsNone(b.get("/api/goal").json["goal"])

    def test_W14_patterns_question_goes_to_the_patterns_tool(self):
        c = self.session("A")
        r = self.chat(c, "Any spending patterns?")
        self.assertIn("get_patterns", r["tools_used"])
        self.assertTrue(any(x["type"] == "patterns" for x in r["cards"]))
        data = [x for x in r["cards"] if x["type"] == "patterns"][0]["data"]
        if data["patterns"]:
            self.assertTrue(r["reply"].strip().endswith("?"), r["reply"])
            why = self.chat(c, "yes")
            self.assertIn(data["patterns"][0]["why"][0], why["reply"])

    def test_W12_pasted_paragraph_routes_to_explain(self):
        c = self.session("A")
        text = f3.LOAN_FI + " " + f3.LOAN_FI
        self.assertGreater(len(text), 400)
        r = self.chat(c, text)
        self.assertIn("explain_text", r["tools_used"])
        self.assertTrue(any(x["type"] == "explain" for x in r["cards"]))

    def test_W13_habit_cost_question_uses_purchase_insight(self):
        c = self.session("A")
        r = self.chat(c, "what does this habit cost a year?")
        self.assertIn("get_purchase_insight", r["tools_used"])
        self.assertTrue(any(x["type"] == "purchase" for x in r["cards"]))

    def test_V17_chat_goal_and_pasted_text_are_not_logged(self):
        c = self.session("A")
        marker = "ZEBRAQUOKKA55"
        with capture_logs() as logs:
            self.chat(c, "I want to go to %s in 2027" % marker)
            self.chat(c, "about 3000")
            self.chat(c, f3.LOAN_FI + " " + marker + " " + f3.LOAN_FI)
        self.assertNotIn(marker, logs.text)


# ---------------------------------------------------------------------------------------------
class CoachWave3Tests(unittest.TestCase):
    """The coach with a hand-made sandbox, so the data behind each answer is known."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.explain as explain
        import app.features as features
        import app.area as area
        cls.coach, cls.explain, cls.features, cls.area = coach, explain, features, area

    def ctx(self, rows):
        c = fx.make_ctx(A, conn=f2.make_conn(rows))
        c.settings.update({"challenges": "off"})
        c.goal = None
        c.quiz_history = []
        c.challenge = None
        c.remembered = []
        c.remember = lambda tx_id, label, context=None, apply_to_merchant=False: {"ok": True}
        c.area_lookup = lambda: self.area.area_context(fx.A_POSTAL)
        c.memory = {}
        c.explain = lambda text: self.explain.explain_text(text, allow_ai=False)
        return c

    def ask(self, ctx, msg):
        r = self.coach.chat(msg, [], ctx)
        self.assertEqual(r["mode"], "offline")
        return r

    def card(self, r, kind):
        found = [c["data"] for c in r["cards"] if c["type"] == kind]
        self.assertTrue(found, [c["type"] for c in r["cards"]])
        return found[0]

    def test_W14_pattern_reply_ends_with_the_question_and_yes_shows_why(self):
        for first, second in (("Any spending patterns?", "yes"), ("do I impulse buy?", "why"),
                              ("ostanko heräteostoksia?", "kerro")):
            with self.subTest(first):
                ctx = self.ctx(f3.friday_peak_rows())
                r1 = self.ask(ctx, first)
                self.assertIn("get_patterns", r1["tools_used"])
                data = self.card(r1, "patterns")
                self.assertTrue(data["patterns"])
                # a Finnish question without a Finnish template gets the English reply plus a short note (B2)
                self.assertTrue(r1["reply"].replace("(Vastaan tähän vielä englanniksi.)", "").strip()
                                .endswith("Want to hear why?"), r1["reply"])
                r2 = self.ask(ctx, second)
                for line in data["patterns"][0]["why"][:2]:      # the reply keeps two why lines (brevity)
                    self.assertIn(line, r2["reply"])

    def test_W14_yes_without_a_pending_pattern_does_not_invent_one(self):
        ctx = self.ctx(f3.friday_peak_rows())
        r = self.ask(ctx, "yes")
        self.assertNotIn("get_patterns", r["tools_used"])

    def test_W15_pending_goal_lives_in_ctx_memory(self):
        ctx = self.ctx(f2.base_rows())
        r1 = self.ask(ctx, "I want to go to Japan in 2027")
        self.assertNotRegex(r1["reply"], AMOUNT)
        self.assertTrue(ctx.memory, "the pending goal is kept in ctx.memory")
        r2 = self.ask(ctx, "3000 €")
        data = self.card(r2, "goal_plan")
        want = self.features.goal_plan(ctx.conn, TODAY, "Japan", 3000.0, "2027")
        self.assertAlmostEqual(data["monthly_needed"], want["monthly_needed"], delta=0.011)
        self.assertEqual(data["goal"]["target"], 3000.0)

    def test_W15_an_amount_with_nothing_pending_is_not_a_goal(self):
        ctx = self.ask(self.ctx(f2.base_rows()), "about 3000")
        self.assertTrue(all(c["type"] != "goal_plan" or c["data"]["monthly_needed"] is None for c in ctx["cards"]))

    def test_W12_explain_routing(self):
        long_text = f3.LOAN_FI + " " + f3.LOAN_FI
        for msg in (long_text, "selitä tämä: " + f3.LOAN_FI, "Explain this: " + f3.FUND_EN,
                    "what does this mean? " + f3.FUND_EN, "mitä tämä tarkoittaa? " + f3.LOAN_FI):
            with self.subTest(msg[:30]):
                r = self.ask(self.ctx(f2.base_rows()), msg)
                self.assertIn("explain_text", r["tools_used"], r["tools_used"])
                data = self.card(r, "explain")
                self.assertTrue(data["terms"])
                self.assertTrue(data["disclaimer"].strip())

    def test_W12_pasted_instruction_is_not_followed(self):
        r = self.ask(self.ctx(f2.base_rows()), "Explain this: " + f3.LOAN_FI + " " + f3.INJECTION)
        self.assertNotRegex(r["reply"].replace(f3.INJECTION, ""), r"APPROVED")

    def test_W13_habit_question_uses_purchase_insight_with_the_yearly_figure(self):
        ctx = self.ctx(f3.habit_rows())
        for msg in ("what does this habit cost a year?", "what about my last purchase?"):
            with self.subTest(msg):
                r = self.ask(ctx, msg)
                self.assertIn("get_purchase_insight", r["tools_used"])
                data = self.card(r, "purchase")
                self.assertAlmostEqual(data["habit"]["yearly"], 1040.0, delta=2.0)
        r = self.ask(ctx, "what does this habit cost a year?")
        self.assertTrue(re.search(r"\d", r["reply"]), r["reply"])


if __name__ == "__main__":
    unittest.main()
