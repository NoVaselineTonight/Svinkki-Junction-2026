"""Wave 3 features: W12 finance-text translator (app/explain.py), W13 purchase insight, W14 impulse patterns,
W15 goal plan (app/features.py). Contract: .devloop/WAVE3.md.

Acceptance: W12 to W15; plan: SR-10, SR-11, SR-22, SR-23.
All data is invented (tests/fixture_wave3.py on top of tests/fixture_wave2.py).
"""
import json
import math
import re
import unittest
import urllib.error

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_wave2 as f2
import fixture_wave3 as f3

TODAY = fx.TODAY
AMOUNT = re.compile(r"€\s*\d|\d[\d\s.,]*\s*(?:€|eur\b|euroa?\b)", re.I)
JUDGING = ("waste", "wasted", "too much", "should", "bad")
FEELINGS = ("stress", "bored", "sad", "lonely", "emotional")


def has_word(text, words):
    low = (text or "").lower()
    return [w for w in words if re.search(r"\b%s\b" % re.escape(w), low)]


# ---------------------------------------------------------------------------------------------
class RedactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.explain as explain
        cls.explain = explain

    def test_W12_each_personal_detail_is_replaced_and_counted(self):
        samples = {"identity code": f3.HETU, "IBAN": f3.IBAN, "spaced IBAN": f3.IBAN_SPACED, "card": f3.CARD,
                   "e-mail": f3.EMAIL, "phone": f3.PHONE}
        for name, value in samples.items():
            with self.subTest(name):
                text = "Asiakkaan tiedot: %s ja sitten muuta tekstiä." % value
                out, n = self.explain.redact(text)
                self.assertNotIn(value, out)
                self.assertEqual(n, 1, (name, out))
                self.assertIn("[removed]", out)
                self.assertIn("muuta tekstiä", out)

    def test_W12_all_five_kinds_together(self):
        text = "Tunnus %s, tili %s, kortti %s, sähköposti %s, puhelin %s." % (
            f3.HETU, f3.IBAN, f3.CARD, f3.EMAIL, f3.PHONE)
        out, n = self.explain.redact(text)
        self.assertEqual(n, 5, out)
        self.assertEqual(out.count("[removed]"), 5, out)
        for v in (f3.HETU, f3.IBAN, f3.CARD, f3.EMAIL, f3.PHONE, "123", "4242"):
            self.assertNotIn(v, out)

    def test_W12_card_with_spaces_is_also_removed(self):
        out, n = self.explain.redact("Kortti %s vanhenee pian." % f3.CARD_SPACED)
        self.assertGreaterEqual(n, 1)
        self.assertNotIn("4242", out)

    def test_W12_ordinary_numbers_percentages_and_amounts_stay(self):
        text = "Lainan määrä on 5 000 euroa, korko 3,5 % ja kulu 12.99 euroa, eräpäivä 30.6.2027."
        out, n = self.explain.redact(text)
        self.assertEqual(n, 0)
        self.assertEqual(out, text)

    def test_W12_no_personal_details_means_text_unchanged(self):
        out, n = self.explain.redact(f3.LOAN_FI)
        self.assertEqual((out, n), (f3.LOAN_FI, 0))


# ---------------------------------------------------------------------------------------------
def valid_model_json():
    return json.dumps({"summary": "Lyhyt selitys lainasta.", "key_points": ["Korko on 6,2 %."],
                       "terms": [{"term": "euribor", "meaning": "Viitekorko."}],
                       "watch_out": ["Avausmaksu 150 euroa."]})


class ExplainTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.explain as explain
        cls.explain = explain

    def test_W12_length_limits(self):
        for bad in ("", "x" * 39, "x" * 6001):
            with self.assertRaises(ValueError, msg=len(bad)):
                self.explain.explain_text(bad, allow_ai=False)
        for ok in ("Lainan korko on 3,5 % ja kulu on 12 euroa.",("lainan korko " * 600)[:6000]):
            self.assertGreaterEqual(len(ok), 40)
            r = self.explain.explain_text(ok, allow_ai=False)
            self.assertEqual(r["mode"], "offline")
        r = self.explain.explain_text("a" * 40, allow_ai=False)
        self.assertEqual(r["mode"], "offline", "40 characters is inside the limit")

    def test_W12_offline_finnish_loan(self):
        r = self.explain.explain_text(f3.LOAN_FI)
        self.assertEqual(r["mode"], "offline")
        self.assertEqual(r["language"], "fi")
        terms = {t["term"].lower(): t["meaning"] for t in r["terms"]}
        for want in ("euribor", "marginaali", "todellinen vuosikorko", "avausmaksu"):
            hit = [k for k in terms if want in k]
            self.assertTrue(hit, "%s missing from %r" % (want, list(terms)))
            self.assertTrue(terms[hit[0]].strip(), want)
        points = " | ".join(r["key_points"])
        self.assertIn("6,2", points, "the percentage must be a key point")
        self.assertIn("150", points, "the euro amount must be a key point")
        self.assertTrue(r["disclaimer"].strip())
        self.assertTrue(r["summary"].strip())
        self.assertNotIn("AI", r["summary"], "the summary no longer repeats that a rewrite needs the AI model")
        self.assertRegex(r["summary"], r"\d+ \S+.*\d+", "the summary counts the terms and the figure sentences")
        self.assertEqual(r["redactions"], 0)
        self.assertTrue(r["watch_out"], "a fee and a penalty interest are in the text")
        for t in r["terms"]:
            self.assertTrue(t["term"].strip() and t["meaning"].strip())

    def test_W12_offline_english_fund(self):
        r = self.explain.explain_text(f3.FUND_EN)
        self.assertEqual(r["mode"], "offline")
        self.assertEqual(r["language"], "en")
        names = " | ".join(t["term"].lower() for t in r["terms"])
        for want in ("ongoing charges", "entry fee", "exit fee"):
            self.assertIn(want, names)
        self.assertTrue(r["disclaimer"].strip())
        self.assertTrue(r["watch_out"])
        points = " | ".join(r["key_points"])
        self.assertIn("0.75", points)

    def test_W12_result_shape(self):
        r = self.explain.explain_text(f3.LOAN_FI, allow_ai=False)
        for k in ("mode", "language", "summary", "key_points", "terms", "watch_out", "redactions", "disclaimer", "notice"):
            self.assertIn(k, r)
        json.dumps(r)

    def test_W12_gemini_mode_gets_redacted_text_only(self):
        pasted = ("%s Henkilötunnus %s, tili %s, kortti %s, sähköposti %s, puhelin %s." % (
            f3.LOAN_FI, f3.HETU, f3.IBAN_SPACED, f3.CARD, f3.EMAIL, f3.PHONE))
        fake = fx.FakeGemini([fx.gem_text(valid_model_json())])
        with fx.patched_gemini(fake):
            r = self.explain.explain_text(pasted, api_key="test-key-not-real")
        self.assertEqual(fake.calls, 1)
        self.assertEqual(r["mode"], "gemini", r.get("notice"))
        self.assertEqual(r["summary"], "Lyhyt selitys lainasta.")
        self.assertGreaterEqual(r["redactions"], 5)
        self.assertTrue(r["disclaimer"].strip())
        body = fake.all_text()
        for secret in (f3.HETU, f3.IBAN, f3.IBAN_SPACED, f3.CARD, f3.EMAIL, f3.PHONE, "123 4567", "010190"):
            self.assertNotIn(secret, body, "SR-22: %r reached the model" % secret)
        self.assertIn("euribor", body.lower(), "the redacted text itself must still be sent")

    def test_W12_gemini_system_prompt_treats_pasted_text_as_data(self):
        pasted = f3.LOAN_FI + " " + f3.INJECTION
        fake = fx.FakeGemini([fx.gem_text(valid_model_json())])
        with fx.patched_gemini(fake):
            self.explain.explain_text(pasted, api_key="test-key-not-real")
        req = fake.requests[0]
        self.assertIsNotNone(req)
        system = req.get("systemInstruction") or req.get("system_instruction")
        self.assertTrue(system, "a system prompt must be sent: %r" % list(req))
        low = json.dumps(system).lower()
        self.assertIn("data", low)
        self.assertRegex(low, r"never[^.]{0,40}instruction|not[^.]{0,40}instruction|instruction[^.]{0,40}never")

    def test_W12_garbage_or_http_error_falls_back_offline_with_a_notice(self):
        for name, script in (("garbage", [fx.gem_text("this is not json {{ at all")]),
                             ("http 500", [urllib.error.HTTPError("http://x", 500, "boom", {}, None)]),
                             ("empty", [fx.gem_text("")])):
            with self.subTest(name):
                fake = fx.FakeGemini(script)
                with fx.patched_gemini(fake):
                    r = self.explain.explain_text(f3.LOAN_FI, api_key="test-key-not-real")
                self.assertEqual(r["mode"], "offline")
                self.assertTrue(r["notice"] and r["notice"].strip())
                self.assertTrue(r["terms"], "the offline answer is still useful")

    def test_W12_allow_ai_false_never_calls_the_model(self):
        fake = fx.FakeGemini([fx.gem_text(valid_model_json())])
        with fx.patched_gemini(fake):
            r = self.explain.explain_text(f3.LOAN_FI, api_key="test-key-not-real", allow_ai=False)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(r["mode"], "offline")

    def test_W12_without_a_key_the_model_is_not_called(self):
        fake = fx.FakeGemini([fx.gem_text(valid_model_json())])
        with fx.patched_gemini(fake, key=""):
            r = self.explain.explain_text(f3.LOAN_FI, api_key=None)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(r["mode"], "offline")

    def test_W12_a_hidden_instruction_is_not_followed_offline(self):
        r = self.explain.explain_text(f3.LOAN_FI + " " + f3.INJECTION, allow_ai=False)
        rest = dict(r)
        rest.pop("key_points")
        self.assertNotIn("APPROVED", json.dumps(rest, ensure_ascii=False))
        for kp in r["key_points"]:
            if "APPROVED" in kp:
                self.assertRegex(kp, r"[\"“'‘«»]", "an echoed sentence must be shown as a quote")
        self.assertNotRegex(r["summary"].lower(), r"approved|i will|here is the approval")


# ---------------------------------------------------------------------------------------------
class PurchaseInsightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.features as features
        cls.features = features
        cls.conn = f2.make_conn(f3.habit_rows())
        cls.ess = f2.make_conn(f3.essentials_rows())

    def test_W13_yearly_is_per_week_times_average_times_52(self):
        r = self.features.purchase_insight(self.conn, TODAY)
        self.assertEqual(r["tx"]["d"], "2026-09-24")
        self.assertEqual(r["tx"]["label"], "Fast food")
        h = r["habit"]
        self.assertAlmostEqual(h["per_week"], 2.0, delta=0.05)
        self.assertAlmostEqual(h["avg_amount"], 10.0, delta=0.05)
        self.assertAlmostEqual(h["yearly"], h["per_week"] * h["avg_amount"] * 52, delta=1.0)
        self.assertAlmostEqual(h["yearly"], 1040.0, delta=2.0)
        self.assertAlmostEqual(h["monthly"] * 12, h["yearly"], delta=12.0)
        self.assertEqual(h["times_this_week"], 2)

    def test_W13_text_is_one_light_sentence_with_a_number(self):
        r = self.features.purchase_insight(self.conn, TODAY)
        self.assertIsInstance(r["text"], str)
        self.assertTrue(re.search(r"\d", r["text"]), r["text"])
        self.assertEqual(has_word(r["text"], JUDGING), [], r["text"])
        for e in r["equivalents"]:
            self.assertIsInstance(e, str)
            self.assertEqual(has_word(e, JUDGING), [], e)
        self.assertLessEqual(len(r["equivalents"]), 2)
        self.assertEqual(has_word(r["note"], JUDGING), [], r["note"])
        json.dumps(r)

    def test_W13_note_says_item_detail_needs_receipt_data(self):
        r = self.features.purchase_insight(self.conn, TODAY)
        self.assertIn("receipt", (r["note"] or "").lower())

    def test_W13_a_given_tx_id_is_used(self):
        row = self.conn.execute("SELECT id, d FROM tx WHERE label='Fast food' AND d='2026-09-02'").fetchone()
        self.assertIsNotNone(row)
        r = self.features.purchase_insight(self.conn, TODAY, tx_id=row["id"])
        self.assertEqual(r["tx"]["id"], row["id"])
        self.assertEqual(r["tx"]["d"], "2026-09-02")

    def test_W13_essentials_are_not_annualised(self):
        r = self.features.purchase_insight(self.ess, TODAY)
        self.assertEqual(r["tx"]["label"], "Groceries")
        self.assertIsNone(r["text"])
        note = (r["note"] or "").lower()
        self.assertIn("essential", note)
        self.assertIn("receipt", note)


# ---------------------------------------------------------------------------------------------
class PatternsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.features as features
        cls.features = features
        cls.peak = f2.make_conn(f3.friday_peak_rows())
        cls.flat = f2.make_conn(f3.flat_rows())

    def test_W14_friday_evening_peak_is_found(self):
        r = self.features.patterns(self.peak, TODAY)
        peaks = [p for p in r["patterns"] if p["kind"] == "time_peak"]
        self.assertEqual(len(peaks), 1, r["patterns"])
        p = peaks[0]
        self.assertAlmostEqual(p["uplift_pct"], 40.0, delta=1.5)
        self.assertIn("friday", (p["title"] + " " + p["text"]).lower())
        self.assertEqual(p["question"], "Want to hear why?")
        self.assertIn("40", p["text"])

    def test_W14_at_most_three_and_why_lines_are_numbers_not_guesses(self):
        r = self.features.patterns(self.peak, TODAY)
        self.assertLessEqual(len(r["patterns"]), 3)
        for p in r["patterns"]:
            self.assertTrue(2 <= len(p["why"]) <= 3, p["why"])
            for line in p["why"]:
                self.assertRegex(line, r"\d", "every why line is an observation with a number: %r" % line)
            blob = " ".join([p["title"], p["text"], p["question"]] + list(p["why"]))
            self.assertEqual(has_word(blob, FEELINGS), [], blob)
        json.dumps(r)

    def test_W14_flat_spending_has_no_time_peak(self):
        r = self.features.patterns(self.flat, TODAY)
        self.assertEqual([p for p in r["patterns"] if p["kind"] == "time_peak"], [])
        self.assertLessEqual(len(r["patterns"]), 3)

    def test_W14_no_everyday_spending_means_no_patterns(self):
        r = self.features.patterns(f2.make_conn(f2.base_rows()), TODAY)
        self.assertEqual(r["patterns"], [])


# ---------------------------------------------------------------------------------------------
class GoalPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.features as features
        cls.features = features
        cls.conn = f2.make_conn(f2.base_rows())

    def plan(self, **kw):
        kw.setdefault("name", "Japan")
        return self.features.goal_plan(self.conn, TODAY, **kw)

    def test_W15_missing_target_asks_and_invents_no_price(self):
        r = self.plan(deadline="2027")
        self.assertIn("target", r["needs"])
        self.assertNotIn("deadline", r["needs"])
        self.assertIsNone(r["monthly_needed"])
        self.assertIsNone(r["feasible"])
        self.assertIsNone(r["goal"])
        self.assertIn("?", r["text"])
        self.assertNotRegex(r["text"], AMOUNT, "SR-10: no price may be invented")
        self.assertIsNone(r["target"])

    def test_W15_missing_deadline_is_listed(self):
        r = self.plan(target=3000.0)
        self.assertIn("deadline", r["needs"])
        self.assertNotIn("target", r["needs"])
        self.assertIsNone(r["monthly_needed"])
        self.assertIn("?", r["text"])

    def test_W15_a_bare_year_means_30_june(self):
        r = self.plan(target=3000.0, deadline="2027")
        self.assertEqual(r["needs"], [])
        self.assertRegex(str(r["deadline"]), r"2027")
        self.assertRegex(r["text"], r"30 June|June 30|30\.6\.|2027-06-30")
        self.assertTrue(8.5 <= r["months_left"] <= 10.0, r["months_left"])

    def test_W15_monthly_needed_formula(self):
        for target, saved in ((3000.0, 0.0), (3000.0, 600.0), (12500.0, 2500.0)):
            with self.subTest(target=target, saved=saved):
                r = self.plan(target=target, saved=saved, deadline="2027-06-30")
                self.assertGreater(r["months_left"], 0)
                # one rounding, up, in the text and in the field (so the reply and the card show the same figure)
                exact = (target - saved) / r["months_left"]
                self.assertEqual(r["monthly_needed"], float(math.ceil(round(exact, 6))))
                self.assertGreaterEqual(r["monthly_needed"], exact)
                self.assertLess(r["monthly_needed"] - exact, 1.0)
                self.assertIn("€%s a month" % format(int(r["monthly_needed"]), ","), r["text"])
                self.assertTrue(8.5 <= r["months_left"] <= 10.0, r["months_left"])
                self.assertEqual(r["saved"], saved)

    def test_W15_year_month_and_full_date_deadlines(self):
        a = self.plan(target=3000.0, deadline="2027-03")
        self.assertTrue(5.0 <= a["months_left"] <= 7.0, a["months_left"])
        b = self.plan(target=3000.0, deadline="2027-03-31")
        self.assertTrue(5.5 <= b["months_left"] <= 6.5, b["months_left"])

    def test_W15_feasible_matches_saving_against_need(self):
        easy = self.plan(target=3000.0, deadline="2027-06-30")
        self.assertAlmostEqual(easy["current_monthly_saving"], 1760.0, delta=1.0)
        self.assertTrue(easy["feasible"])
        hard = self.plan(target=60000.0, deadline="2027-06-30")
        self.assertFalse(hard["feasible"])
        for r in (easy, hard):
            self.assertEqual(r["feasible"], r["current_monthly_saving"] >= r["monthly_needed"])
        small = self.plan(target=3000.0, deadline="2027-06-30", monthly_saving_target=100.0)
        self.assertAlmostEqual(small["current_monthly_saving"], 100.0, delta=0.01)
        self.assertFalse(small["feasible"])

    def test_W15_goal_is_what_the_app_can_store(self):
        r = self.plan(target=3000.0, saved=600.0, deadline="2027")
        self.assertEqual(r["goal"], {"name": "Japan", "target": 3000.0, "saved": 600.0})
        self.assertEqual(r["name"], "Japan")
        self.assertLessEqual(len(r["ways"]), 3)
        json.dumps(r)

    def test_W15_complete_plan_text_states_the_monthly_figure(self):
        r = self.plan(target=3000.0, deadline="2027")
        self.assertTrue(fx.text_has_amount(r["text"], round(r["monthly_needed"]), abs_tol=1.0), r["text"])


if __name__ == "__main__":
    unittest.main()
