"""Demo-ready fixes in the calculation modules: the figures a customer sees must be true."""
import os as _os
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

A = fx.A_CID


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.insights as ins
        import app.invest as invest
        import app.features as features
        import app.explain as explain
        import app.tools as tools
        cls.ins, cls.invest, cls.features, cls.explain, cls.tools = ins, invest, features, explain, tools
        cls.conn = fx.sandbox()
        cls.today = fx.TODAY


class InvestProjection(_Base):
    def test_fv_split_counts_only_what_goes_into_the_fund(self):
        v, paid = self.invest._fv_split(20.0, 30.0, 63, 10, 5.2)
        self.assertAlmostEqual(paid, 20 * 63 + 30 * (120 - 63), 2)
        # all 30 a month for 10 years is the old (wrong) figure; the real fund holds clearly less
        self.assertLess(v, self.invest._future_value(30.0, 10, 5.2))
        self.assertGreater(v, self.invest._future_value(20.0, 10, 5.2))
        v2, paid2 = self.invest._fv_split(30.0, 30.0, 0, 10, 5.2)
        self.assertAlmostEqual(v2, self.invest._future_value(30.0, 10, 5.2), 2)
        self.assertAlmostEqual(paid2, 3600.0, 2)

    def test_plan_projection_matches_the_split(self):
        p = self.invest.plan(self.conn, self.today, monthly=30)
        st = {s["id"]: s for s in p["steps"]}["invest_monthly"]
        if st["monthly_to_buffer"] and st["monthly_to_long_term"]:
            for row in st["projection"]:
                v, paid = self.invest._fv_split(st["monthly_to_long_term"], st["monthly_total"],
                                                st.get("months_to_buffer"), row["years"], st["planning_return_pct"])
                self.assertAlmostEqual(row["value_at_end"], v, 2)
                self.assertAlmostEqual(row["paid_in"], paid, 2)
                self.assertLess(row["paid_in"], st["monthly_total"] * 12 * row["years"] + 0.01)
            self.assertIn("only what goes into the index fund", st["what"])

    def test_nothing_left_sends_it_all_to_the_buffer(self):
        s = dict(self.invest.situation(self.conn, self.today))
        real = self.invest.situation
        s.update({"left_monthly": -50.0, "balance": 100.0})
        self.invest.situation = lambda c, t: dict(s)
        try:
            p = self.invest.plan(self.conn, self.today)
        finally:
            self.invest.situation = real
        st = {x["id"]: x for x in p["steps"]}["invest_monthly"]
        self.assertEqual(st["monthly_to_long_term"], 0.0)
        self.assertEqual(st["monthly_to_buffer"], st["monthly_total"])
        self.assertNotIn("projection", st)


class SafeToSpend(_Base):
    def test_per_week_never_exceeds_the_total(self):
        r = self.ins.safe_to_spend(self.conn, self.today)
        self.assertAlmostEqual(r["per_week"], r["per_day"] * min(7, r["days_left"]), delta=0.1)
        if r["days_left"] < 7 and r["safe_total"] > 0:
            self.assertLessEqual(r["per_week"], r["safe_total"] + 0.01)
        self.assertIn("late_case", r)

    def test_late_case_uses_the_later_date(self):
        r = self.ins.safe_to_spend(self.conn, self.today)
        lc = r["late_case"]
        if lc:
            self.assertGreater(lc["days"], r["days_left"])
            self.assertAlmostEqual(lc["per_day"], lc["safe_total"] / lc["days"], delta=0.02)


class CheckIn(_Base):
    def test_weekly_checkin_does_not_offer_to_move_the_money(self):
        for f in ("weekly", "biweekly"):
            kinds = [s["kind"] for s in self.ins.checkin(self.conn, self.today, f)["suggestions"]]
            self.assertNotIn("save_surplus", kinds)

    def test_in_word(self):
        self.assertEqual(self.ins._in_word("last month"), "last month")
        self.assertEqual(self.ins._in_word("the last two weeks"), "in the last two weeks")

    def test_ratio_words_house_style(self):
        self.assertEqual(self.ins.ratio_words(221, 118), "almost double")
        self.assertEqual(self.ins.ratio_words(150, 118), "27% above")


class Small(_Base):
    def test_on_is_not_a_finnish_word(self):
        self.assertEqual(self.explain._language("Turn on the card, then on Monday go on"), "en")

    def test_project_savings_lump_sum_compounds_once_a_year(self):
        r, _ = self.tools._t_project_savings({"monthly": 0, "start": 100, "years": 2, "annual_return_pct": 10}, None, None)
        self.assertAlmostEqual(r["value_at_end"], 121.0, 2)
        self.assertAlmostEqual(r["without_compounding"], 120.0, 2)

    def test_loan_has_no_left_a_day_figures(self):
        r = self.features.afford(self.conn, self.today, "payday loan of", 500)
        self.assertEqual(r["risk"], "loan")
        self.assertIsNone(r["per_day_after"])
        self.assertIsNone(r["goal_effect"])
        self.assertNotIn("loan of is", r["verdict_text"])

    def test_overdraft_note_does_not_say_not_found(self):
        self.assertNotIn("not found", self.invest.knowledge()["figures"]["overdraft_rate_pct"]["note"])


if __name__ == "__main__":
    unittest.main()
