"""Finnish without an AI model: the tools that used to answer in English with a note now answer in Finnish."""
import re
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

ENGLISH = re.compile(r"\b(you|your|the|and|month|spent|purchases?|income|switched)\b", re.I)
NOTE = "englanniksi"


class FinnishReplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.db as db
        cls.coach, cls.db = coach, db

    def ask(self, q, cid=fx.A_CID, **settings):
        ctx = fx.make_ctx(cid, consent=dict(fx.ALL_CONSENT, ai=False))
        ctx.memory, ctx.cid, ctx.bench_lookup = {}, cid, self.db.bench
        ctx.settings = dict(ctx.settings, **settings)
        return self.coach.chat(q, [], ctx)

    def check(self, q, tool, must, **settings):
        r = self.ask(q, **settings)
        self.assertEqual(r["tools_used"], [tool], r["reply"])
        self.assertNotIn(NOTE, r["reply"])
        self.assertNotRegex(r["reply"], ENGLISH)
        self.assertRegex(r["reply"], must)
        self.assertNotRegex(r["reply"], r"€\d", "Finnish money has the euro sign after the amount")
        self.assertNotRegex(r["reply"], r"\d{4}-\d{2}-\d{2}")
        return r

    def test_latest_transactions(self):
        self.check("Näytä viimeisimmät tapahtumat", "list_transactions", r"^Viimeisimmät: .*\d+,\d\d € \(\d{1,2}\.\d{1,2}\.\)")

    def test_biggest_purchases(self):
        self.check("Mitkä olivat suurimmat ostokseni viime kuussa?", "explore_my_data",
                   r"^Suurimmat ostoksesi viime kuussa: asuminen 900,00 € \(2\.8\.\)")

    def test_last_purchase(self):
        self.check("Mikä oli viimeisin ostokseni?", "get_purchase_insight", r"^Viimeisin ostoksesi: \w+, \d+,\d\d €\.")

    def test_challenge_off_and_on(self):
        self.check("Anna minulle haaste", "get_challenge", r"Haasteet ovat pois päältä")
        r = self.ask("Anna minulle haaste", challenges="on")
        self.assertNotIn(NOTE, r["reply"])
        self.assertRegex(r["reply"], r"haaste|Haaste")

    def test_patterns_when_nothing_stands_out(self):
        self.check("Onko kulutuksessani kuvioita?", "get_patterns", r"12 viikkoa")

    def test_comparison_when_asked(self):
        self.check("Vertaa minua muihin ikäisiini", "get_benchmarks", r"^Tulosi ovat .* useimmilla ikäisilläsi")
        self.check("Paljonko ihmiset yleensä käyttävät takseihin?", "get_averages",
                   r"^Käytät takseihin noin \d+ € kuukaudessa, .*useimmat ikäisesi")

    def test_area_without_data_is_said_in_finnish(self):
        self.check("Millainen on asuinalueeni?", "get_area_context", r"asuinalue")

    def test_saving_ideas_have_no_english_word_in_them(self):
        for c in fx.CUSTOMERS[:10]:
            with self.subTest(cid=c["cid"]):
                r = self.ask("Miten voisin säästää enemmän?", cid=c["cid"])
                self.assertNotRegex(r["reply"], r"surplus|night_out|everyday")
                self.assertNotIn(NOTE, r["reply"])

    def test_coaching_questions_are_understood(self):
        self.assertEqual(self.ask("Miten minulla menee?")["tools_used"], ["get_overview"])
        self.assertEqual(self.ask("Anna vinkki")["tools_used"], ["get_save_more"])
        r = self.ask("Haluan säästää matkaan Japaniin")
        self.assertEqual(r["tools_used"], ["make_savings_plan"])
        self.assertNotIn("My goal", r["reply"])

    def test_no_finnish_help_question_falls_back_to_english(self):
        for g in self.coach.help_groups("fi"):
            for it in g["items"]:
                with self.subTest(q=it["question"]):
                    self.assertNotIn(NOTE, self.ask(it["question"])["reply"])


class FinnishSweepTests(unittest.TestCase):
    """Every Finnish question in the help list, for every test customer: Finnish, and no signed money."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.db as db
        cls.rows = []
        qs = [it["question"] for g in coach.help_groups("fi") for it in g["items"]] + [
            "Mikä on saldoni?", "Onko minulla varaa 300 euron takkiin?", "Mihin minun kannattaisi sijoittaa?",
            "Riittävätkö rahani palkkapäivään?", "Paljonko tienaan?"]
        for c in fx.CUSTOMERS:
            for q in qs:
                if coach.note_intent(q):
                    continue
                ctx = fx.make_ctx(c["cid"], consent=dict(fx.ALL_CONSENT, ai=False))
                ctx.memory, ctx.cid, ctx.bench_lookup = {}, c["cid"], db.bench
                cls.rows.append((c["cid"], q, coach.chat(q, [], ctx)["reply"]))

    def test_none_falls_back_to_english(self):
        """One known gap: a FOUND spending pattern is still worded in English (W14 pins that reply)."""
        for cid, q, r in self.rows:
            if q == "Onko kulutuksessani kuvioita?" and r.rstrip().endswith("(Vastaan tähän vielä englanniksi.)"):
                continue
            with self.subTest(cid=cid, q=q):
                self.assertNotIn(NOTE, r)

    def test_no_signed_or_negative_figures(self):
        for cid, q, r in self.rows:
            with self.subTest(cid=cid, q=q):
                self.assertNotRegex(r, r"\bmiinus \d|(?<![\d–])-\d|€-|-€")

    def test_overdrawn_balance_is_worded(self):
        hit = [r for _c, q, r in self.rows if q == "Mikä on saldoni?" and "miinuksella" in r]
        self.assertTrue(hit, "the fixture has a customer below zero")
        self.assertRegex(hit[0], r"^Tilisi on [\d ]+,\d\d € miinuksella\.")

    def test_is_it_normal_is_a_comparison_and_unusual_is_not(self):
        import app.coach as coach
        self.assertTrue(coach.compare_requested("Onko taksikulutukseni tavallista?"))
        self.assertFalse(coach.compare_requested("Onko tässä kuussa jotain epätavallista?"))
        self.assertEqual(coach.route("Onko taksikulutukseni tavallista?", fx.make_ctx(fx.A_CID))[0], "get_averages")


class EnglishCoachingQuestions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        cls.coach = coach

    def route(self, q):
        r = self.coach.route(q, fx.make_ctx(fx.A_CID))
        return r[0] if r else None

    def test_tips_and_cut_back(self):
        for q in ("where can I cut back?", "give me a tip", "what should I do with my money?", "help me save"):
            with self.subTest(q=q):
                self.assertEqual(self.route(q), "get_save_more")

    def test_am_i_spending_too_much_is_the_overview(self):
        self.assertEqual(self.route("am I spending too much?"), "get_overview")

    def test_saving_for_something_starts_a_goal(self):
        for q in ("I want to save for a trip to Japan", "Help me save for a new bike", "I'd like to start saving for a car"):
            with self.subTest(q=q):
                self.assertEqual(self.route(q), "make_savings_plan")

    def test_analyse_my_groceries_reads_the_receipts(self):
        self.assertEqual(self.route("analyse my groceries"), "receipt_insights")


if __name__ == "__main__":
    unittest.main()
