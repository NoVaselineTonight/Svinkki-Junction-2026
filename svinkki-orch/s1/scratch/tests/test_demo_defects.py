"""Defects a judge could hit in the demo, without an AI model (the built-in rules answer).

1. A range of months ("between June and August", "June-August", "kesä-elokuussa") is answered for the whole
   range; a range the rules cannot read is said, not quietly narrowed to one month. "the last N months" and
   "viimeiset 3 kuukautta" are periods.
2. "How much on coffee": coffee from the (simulated) grocery receipts, and an honest word that cafés cannot be
   told apart from restaurants and fast food in the data.
4. "Should I buy bitcoin?" is an investing question with a plain, safe answer, not a purchase whose price is asked.
5. "Did Anna pay me back?" is English, and says the data does not name senders.
"""
import re
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

TODAY = fx.TODAY          # 2026-09-24


def _eur_en(x):
    return "€{:,.2f}".format(x)


def _eur_fi(x):
    return "{:,.2f}".format(x).replace(",", " ").replace(".", ",") + " €"


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.db as db
        cls.coach, cls.db = coach, db

    def ask(self, q, cid=fx.A_CID):
        ctx = fx.make_ctx(cid, consent=dict(fx.ALL_CONSENT, ai=False))
        ctx.memory, ctx.cid, ctx.bench_lookup = {}, cid, self.db.bench
        return self.coach.chat(q, [], ctx)


class MonthRangeParsing(Base):
    def span(self, q):
        return self.coach.span_from_text(q, TODAY)

    def test_ranges_of_months(self):
        for q in ("what did i spend at restaurants between june and august 2026",
                  "what did i spend at restaurants between June and August",
                  "restaurants from June to August", "restaurants june-august", "restaurants June – August",
                  "jun to aug", "from june 2026 to august"):
            with self.subTest(q=q):
                sp = self.span(q)
                self.assertIsNotNone(sp)
                self.assertEqual(sp[:3], ("dates", "2026-06-01", "2026-08-31"))
                self.assertIn("June to August", sp[3])

    def test_range_over_new_year_and_to_this_month(self):
        self.assertEqual(self.span("from december to february")[:3], ("dates", "2025-12-01", "2026-02-28"))
        sp = self.span("between july and september")
        self.assertEqual(sp[:3], ("dates", "2026-07-01", TODAY))
        self.assertIn("so far", sp[3])

    def test_since_and_last_n_months(self):
        self.assertEqual(self.span("taxis since june")[:3], ("dates", "2026-06-01", TODAY))
        sp = self.span("how much did I spend in the last 6 months")
        self.assertEqual(sp[0], "dates")
        self.assertEqual(sp[2], TODAY)
        self.assertEqual(sp[1], "2026-03-25")
        self.assertIn("last 6 months", sp[3])
        # 3 and 12 months stay the named periods
        self.assertIsNone(self.span("groceries in the last 3 months"))
        self.assertEqual(self.coach.period_from_text("groceries in the last 3 months", TODAY), "last_3_months")

    def test_unreadable_range_is_flagged_and_one_month_is_not_a_range(self):
        self.assertEqual(self.span("restaurants between 1 june and 15 august"), ("unclear",))
        self.assertIsNone(self.span("restaurants in june"))
        self.assertIsNone(self.span("how much did I spend last month"))

    def test_finnish_ranges_become_english_ranges(self):
        for q in ("paljonko ravintoloihin kesä-elokuussa", "paljonko ravintoloihin kesäkuusta elokuuhun",
                  "paljonko ravintoloihin kesäkuu–elokuu"):
            with self.subTest(q=q):
                en = self.coach.fi_to_en(q)
                self.assertIsNotNone(en)
                self.assertIn("from june to august", en)
        self.assertIn("last 3 months", self.coach.fi_to_en("paljonko ruokaan viimeiset 3 kuukautta"))
        self.assertIn("last 6 months", self.coach.fi_to_en("paljonko ruokaan viimeiset kuusi kuukautta"))


class MonthRangeReplies(Base):
    def test_english_range_answers_the_whole_range(self):
        total, n = fx.spend(fx.A_CID, "2026-06-01", "2026-08-31", labels=["Restaurant"])
        june, _ = fx.spend(fx.A_CID, "2026-06-01", "2026-06-30", labels=["Restaurant"])
        self.assertNotAlmostEqual(total, june)
        for q in ("what did i spend at restaurants between june and august 2026",
                  "how much did I spend on restaurants from June to August?", "restaurants june-august"):
            with self.subTest(q=q):
                r = self.ask(q)
                self.assertEqual(r["tools_used"], ["get_spend"], r["reply"])
                self.assertIn(_eur_en(total), r["reply"])
                self.assertIn("June to August", r["reply"])
                self.assertNotRegex(r["reply"], r"\bin June\b")

    def test_finnish_range_answers_the_whole_range(self):
        total, n = fx.spend(fx.A_CID, "2026-06-01", "2026-08-31", labels=["Restaurant"])
        for q in ("paljonko ravintoloihin kesä-elokuussa", "paljonko käytin ravintoloihin kesäkuusta elokuuhun"):
            with self.subTest(q=q):
                r = self.ask(q)
                self.assertEqual(r["tools_used"], ["get_spend"], r["reply"])
                self.assertIn(_eur_fi(total), r["reply"])
                self.assertIn("kesäkuusta elokuuhun", r["reply"])
                self.assertNotIn("englanniksi", r["reply"])

    def test_overview_question_over_a_range(self):
        total, n = fx.spend(fx.A_CID, "2026-06-01", "2026-08-31", baskets=["regular", "unexpected", "everyday"])
        r = self.ask("where did my money go between june and august")
        self.assertIn(_eur_en(total), r["reply"])
        self.assertIn("June to August", r["reply"])

    def test_unreadable_range_is_said(self):
        r = self.ask("how much did i spend on restaurants between 1 june and 15 august")
        self.assertRegex(r["reply"], r"^I couldn't read that time span")

    def test_last_n_months(self):
        r = self.ask("how much did I spend on groceries in the last 6 months")
        self.assertEqual(r["tools_used"], ["get_spend"], r["reply"])
        self.assertIn("over the last 6 months", r["reply"])
        r = self.ask("paljonko ruokaan viimeiset 3 kuukautta")
        self.assertIn("viimeisen 3 kuukauden", r["reply"])
        self.assertNotIn("viime kuussa", r["reply"])


class Coffee(Base):
    def test_coffee_without_a_verb_is_understood(self):
        r = self.ask("how much on coffee in the last 3 months")
        self.assertEqual(r["tools_used"], ["product_habit"], r["reply"])
        self.assertIn("simulated", r["reply"])
        self.assertRegex(r["reply"], r"cafés .*restaurants or fast food")
        dining, _ = fx.spend(fx.A_CID, "2026-06-25", TODAY, labels=["Restaurant", "Fast food"])
        self.assertIn(_eur_en(dining), r["reply"])

    def test_coffee_in_finnish(self):
        r = self.ask("paljonko kahviin viimeiset 3 kuukautta")
        self.assertEqual(r["tools_used"], ["product_habit"], r["reply"])
        self.assertIn("kahvia", r["reply"])
        self.assertIn("kahvilat", r["reply"])
        self.assertNotIn("englanniksi", r["reply"])

    def test_cafes_are_said_to_be_restaurants_and_fast_food(self):
        total, _ = fx.spend(fx.A_CID, "2026-08-01", "2026-08-31", labels=["Restaurant", "Fast food"])
        r = self.ask("how much did I spend on cafes last month")
        self.assertEqual(r["tools_used"], ["get_spend"], r["reply"])
        self.assertRegex(r["reply"], r"^Cafés have no category of their own")
        self.assertIn(_eur_en(total), r["reply"])


class Bitcoin(Base):
    def test_should_i_buy_bitcoin(self):
        r = self.ask("Should I buy bitcoin?")
        self.assertEqual(r["tools_used"], ["get_invest_education"], r["reply"])
        self.assertNotRegex(r["reply"].lower(), r"how much does|tell me the price|what does .* cost")
        self.assertRegex(r["reply"].lower(), r"high-risk")
        self.assertRegex(r["reply"].lower(), r"not investment advice")
        self.assertRegex(r["reply"].lower(), r"buffer|months of costs")

    def test_should_i_buy_bitcoin_in_finnish(self):
        r = self.ask("Pitäisikö minun ostaa bitcoinia?")
        self.assertEqual(r["tools_used"], ["get_invest_education"], r["reply"])
        self.assertRegex(r["reply"], r"riskisijoitus")
        self.assertNotIn("englanniksi", r["reply"])

    def test_a_priced_bitcoin_purchase_still_gets_caution(self):
        r = self.ask("Can I afford 500 euros of bitcoin?")
        self.assertEqual(r["tools_used"], ["can_i_afford"], r["reply"])
        self.assertNotIn("of bitcoin can", r["reply"])


class PaidMeBack(Base):
    def test_anna_is_a_name_in_english(self):
        self.assertFalse(self.coach.is_finnish("Did Anna pay me back?"))
        self.assertFalse(self.coach.is_finnish("Has Anna sent the money yet?"))
        self.assertTrue(self.coach.is_finnish("Anna minulle vinkki"))
        self.assertTrue(self.coach.is_finnish("Anna minulle haaste"))

    def test_did_anna_pay_me_back(self):
        r = self.ask("Did Anna pay me back?")
        self.assertEqual(r["tools_used"], ["list_transactions"], r["reply"])
        self.assertRegex(r["reply"], r"^Your bank data doesn't show who sent a payment, so I can't tell whether Anna")
        self.assertNotRegex(r["reply"], r"Käytit|last month")

    def test_finnish_imperative_still_works(self):
        self.assertEqual(self.ask("Anna vinkki")["tools_used"], ["get_save_more"])


if __name__ == "__main__":
    unittest.main()
