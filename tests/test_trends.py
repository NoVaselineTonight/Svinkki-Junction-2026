"""app/trends.py: money_story, season_outlook, category_story, explain_month.

Most tests build a tiny in-memory `tx` table (so every figure can be checked by hand); a few run
against customer A of the invented population (known to the cent through the fixture oracle).
"""
import os as _os
import sqlite3
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx


def _conn(rows, opening=3000.0):
    """rows: (d, amount, basket, label, context). Balance is the running sum from `opening`."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, "
              "mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
    bal = opening
    for i, (d, amt, basket, label, ctx) in enumerate(sorted(rows, key=lambda r: r[0])):
        bal = round(bal + amt, 2)
        c.execute("INSERT INTO tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (d, d + "T12:00:00", amt, bal, "", "", "", "", label, basket, ctx or "", i))
    c.commit()
    return c


def _months(first, last):
    y, m = int(first[:4]), int(first[5:])
    while "%04d-%02d" % (y, m) <= last:
        yield "%04d-%02d" % (y, m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


TODAY = "2026-09-20"


def story_rows(heavy=True, night=False):
    """Oct 2024 to Sep 2026 (up to TODAY). Salary 1,400 on the 15th, rent 800 on the 2nd, groceries at 60 a trip
    (5 trips a month, 14 in Oct 2025 to Feb 2026 when `heavy`), fast food 20 a month until Aug 2025 and 80 after."""
    rows = []
    for ym in _months("2024-10", "2026-09"):
        n = 14 if heavy and "2025-10" <= ym <= "2026-02" else 5
        rows.append((ym + "-15", 1400.0, "income", "Salary", ""))
        rows.append((ym + "-02", -800.0, "regular", "Housing", ""))
        for k in range(n):
            rows.append(("%s-%02d" % (ym, 3 + 2 * k), -60.0, "everyday", "Groceries", ""))
        rows.append((ym + "-20", -(20.0 if ym <= "2025-08" else 80.0), "everyday", "Fast food", ""))
        if night:
            rows.append((ym + "-25", -30.0, "everyday", "Taxi", "night_out"))
    return [r for r in rows if r[0] <= TODAY]


def spike_rows():
    """Sep 2025 to Aug 2026 flat: salary 2,000 (1st), rent 700 (2nd), groceries 300 (5th). March 2026 has a
    900 sofa; May 2026 has no rent row. Plus three rows in Sep 2026."""
    rows = []
    for ym in _months("2025-09", "2026-09"):
        rows.append((ym + "-01", 2000.0, "income", "Salary", ""))
        if ym != "2026-05":
            rows.append((ym + "-02", -700.0, "regular", "Housing", ""))
        rows.append((ym + "-05", -300.0, "everyday", "Groceries", ""))
    rows.append(("2026-03-12", -900.0, "unexpected", "Furniture", ""))
    return [r for r in rows if r[0] <= "2026-09-15"]


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app.trends as tr
        cls.tr = tr
        cls.rows = story_rows()
        cls.conn = _conn(cls.rows)
        cls.res = tr.money_story(cls.conn, TODAY)

    def test_balance_path(self):
        b = self.res["balance"]
        total = 3000.0 + sum(r[1] for r in self.rows)
        self.assertAlmostEqual(b["now"], total, 2)
        ago = 3000.0 + sum(r[1] for r in self.rows if r[0] <= "2025-09-20")
        self.assertAlmostEqual(b["year_ago"], ago, 2)
        self.assertAlmostEqual(b["change"], total - ago, 2)
        self.assertEqual(self.res["window"], {"from": "2025-09-01", "to": "2026-08-31", "months": 12})
        self.assertLess(b["lowest"]["amount"], b["highest"]["amount"])

    def test_months_more_out_and_kept(self):
        r = self.res
        self.assertEqual(r["months_more_out"], 5)                       # Oct 2025 to Feb 2026: 1,720 out, 1,400 in
        self.assertAlmostEqual(r["kept"]["this_window"], 12 * 1400 - (1180 * 7 + 1720 * 5), 2)   # -60
        self.assertNotIn("window_before", r["kept"])          # 11 months against 12: only per-month figures compare
        self.assertAlmostEqual(r["kept"]["per_month_window_before"], 280.0, 2)
        self.assertEqual(r["kept"]["months_window_before"], 11)
        self.assertAlmostEqual(r["per_month"]["income"], 1400.0, 2)
        self.assertAlmostEqual(r["per_month"]["spent"], 16860 / 12, 2)
        self.assertAlmostEqual(r["per_month"]["spent_before"], 1120.0, 2)

    def test_risers_and_groceries_driver(self):
        r = self.res
        self.assertEqual([x["label"] for x in r["risers"]], ["Groceries", "Fast food"])
        self.assertAlmostEqual(r["risers"][0]["now"], 525.0, 2)   # (7 x 300 + 5 x 840) / 12
        self.assertAlmostEqual(r["risers"][0]["before"], 300.0, 2)
        self.assertAlmostEqual(r["risers"][1]["now"], 80.0, 2)
        g = r["groceries"]
        self.assertEqual((g["trips_now"], g["trips_before"]), (8.8, 5.0))   # 105 trips / 12
        self.assertAlmostEqual(g["basket_now"], 60.0, 2)
        self.assertEqual(r["fallers"], [])

    def test_highlights_carry_the_figures(self):
        hl = self.res["highlights"]
        self.assertTrue(2 <= len(hl) <= 5)
        joined = " ".join(hl)
        for token in ("a year ago", "5 of the last 12", "€525", "€300", "8.8 trips", "up from 5", "not because baskets"):
            self.assertIn(token, joined)
        self.assertEqual(self.res["text"], " ".join(hl[:2]))
        self.assertTrue(self.res["explain"])
        self.assertNotIn("median", self.res["text"])

    def test_thin_data_and_empty_table(self):
        empty = _conn([])
        for fn, args in ((self.tr.money_story, ()), (self.tr.season_outlook, ()),
                         (self.tr.explain_month, ())):
            r = fn(empty, TODAY, *args)
            self.assertTrue(r["too_little_data"], fn.__name__)
            self.assertEqual(r["highlights"], [])
        three = _conn([r for r in story_rows() if r[0] >= "2026-05-01"])
        self.assertTrue(self.tr.money_story(three, TODAY)["too_little_data"])
        self.assertTrue(self.tr.category_story(three, TODAY, "Groceries")["too_little_data"])

    def test_negative_balance_wording(self):
        rows = [r for r in story_rows() if r[0] >= "2025-06-01"]
        low = _conn(rows, opening=-3000.0)
        r = self.tr.money_story(low, TODAY)
        self.assertLess(r["balance"]["now"], 0)
        self.assertRegex(" ".join(r["highlights"]), r"€[\d,]+ below zero")
        self.assertNotIn("−", " ".join(r["highlights"]))
        self.assertNotIn("-€", " ".join(r["highlights"]))

    def test_missing_rent_is_not_a_cheap_month(self):
        rows = [r for r in story_rows() if not (r[3] == "Housing" and r[0].startswith("2026-03"))]
        c = _conn(rows)
        r = self.tr.money_story(c, TODAY)
        # plain mean of what was spent (a missing rent month is a month without rent paid; C1-D4)
        self.assertAlmostEqual(r["per_month"]["spent"], (16860 - 800) / 12, 2)


class SeasonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app.trends as tr
        cls.tr = tr
        cls.rows = story_rows()
        cls.conn = _conn(cls.rows)
        cls.res = tr.season_outlook(cls.conn, TODAY)

    def test_last_year_and_year_before(self):
        r = self.res
        self.assertEqual(r["months"], ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02"])
        ly = r["last_year"]
        self.assertEqual((ly["from"], ly["to"]), ("2025-10", "2026-02"))
        self.assertAlmostEqual(ly["spent"], 5 * 1720, 2)
        self.assertAlmostEqual(ly["income"], 5 * 1400, 2)
        self.assertAlmostEqual(ly["gap"], 1600.0, 2)
        self.assertAlmostEqual(ly["groceries"], 4200.0, 2)
        self.assertAlmostEqual(r["year_before"]["gap"], -1400.0, 2)

    def test_balance_and_label(self):
        r = self.res
        now = 3000.0 + sum(x[1] for x in self.rows)
        self.assertAlmostEqual(r["balance_now"], now, 2)
        self.assertAlmostEqual(r["if_repeated"], now - 1600.0, 2)
        # the year before had no winter bump, so the groceries rise is a one-year trend, not a season (C2-D1)
        self.assertIsNone(r["season_vs_rest"])
        self.assertTrue(r["relevant"])

    def test_highlights(self):
        hl = self.res["highlights"]
        self.assertTrue(2 <= len(hl) <= 5)
        self.assertIn("Last October to February you spent €8,600, €1,600 more than the €7,000 of income that came in",
                      hl[0])
        self.assertIn("€4,200", hl[0])
        self.assertIn("you kept €1,400", hl[1])
        self.assertNotIn("the rest of the year", " ".join(hl))
        self.assertEqual(self.res["text"], " ".join(hl[:2]))

    def test_flat_year_is_not_relevant(self):
        c = _conn(story_rows(heavy=False))
        r = self.tr.season_outlook(c, TODAY)
        self.assertFalse(r["relevant"])
        self.assertLess(r["last_year"]["gap"], 300)
        self.assertIsNone(r["season_vs_rest"])
        self.assertTrue(len(r["highlights"]) >= 2)

    def test_months_ahead_is_capped(self):
        self.assertEqual(len(self.tr.season_outlook(self.conn, TODAY, 9)["months"]), 6)

    def test_not_enough_history(self):
        c = _conn([r for r in story_rows() if r[0] >= "2026-01-01"])
        self.assertTrue(self.tr.season_outlook(c, TODAY)["too_little_data"])


class CategoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app.trends as tr
        cls.tr = tr
        cls.conn = _conn(story_rows(night=True))

    def test_groceries(self):
        r = self.tr.category_story(self.conn, TODAY, "Groceries")
        self.assertEqual(r["label"], "Groceries")
        self.assertEqual(len(r["monthly"]), 23)
        self.assertEqual(r["monthly"][-1], {"m": "2026-08", "total": 300.0, "count": 5})
        self.assertEqual(r["now"], {"per_month": 525.0, "trips": 8.8, "basket": 60.0})
        self.assertEqual(r["before"], {"per_month": 300.0, "trips": 5.0, "basket": 60.0})
        self.assertEqual(r["change_pct"], 75)
        self.assertEqual(r["driver"], "trips")
        self.assertEqual(r["peak"], {"m": "2025-10", "total": 840.0, "count": 14})
        self.assertAlmostEqual(r["share_of_spending"]["now"], 6300 / (16860 + 12 * 30), 3)   # the night rows add 30 a month
        self.assertEqual(r["same_month_last_year"], {"m": "2026-08", "now": 300.0, "year_before": 300.0})

    def test_highlights(self):
        r = self.tr.category_story(self.conn, TODAY, "groceries")
        hl = " ".join(r["highlights"])
        self.assertTrue(2 <= len(r["highlights"]) <= 5)
        for token in ("€525", "€300", "75% more", "about 8.8 a month instead of 5", "still about €60", "October 2025: €840 over 14 trips"):
            self.assertIn(token, hl)

    def test_basket_driver(self):
        rows = [r for r in story_rows(heavy=False) if r[3] != "Groceries"]
        for ym in _months("2024-10", "2026-08"):
            rows.append((ym + "-05", -(100.0 if ym >= "2025-09" else 60.0), "everyday", "Groceries", ""))
        r = self.tr.category_story(_conn(rows), TODAY, "Groceries")
        self.assertEqual(r["driver"], "basket")
        self.assertEqual((r["now"]["trips"], r["before"]["trips"]), (1.0, 1.0))

    def test_combined_and_night_out(self):
        r = self.tr.category_story(self.conn, TODAY, "Dining out")
        self.assertEqual(r["label"], "Dining out")
        self.assertEqual(r["now"]["per_month"], 80.0)                  # only Fast food exists in these rows
        n = self.tr.category_story(self.conn, TODAY, "Night out")
        self.assertEqual(n["now"]["per_month"], 30.0)
        self.assertEqual(n["now"]["trips"], 1.0)

    def test_unknown_label(self):
        for bad in ("Yachts", "", "Salary"):
            with self.assertRaises(ValueError):
                self.tr.category_story(self.conn, TODAY, bad)

    def test_housing_uses_the_median(self):
        rows = [r for r in story_rows() if not (r[3] == "Housing" and r[0][:7] in ("2026-03", "2026-04"))]
        r = self.tr.category_story(_conn(rows), TODAY, "Housing")
        self.assertEqual(r["now"]["per_month"], 800.0)


class ExplainMonthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app.trends as tr
        cls.tr = tr
        cls.conn = _conn(spike_rows())

    def test_default_is_the_spike(self):
        r = self.tr.explain_month(self.conn, "2026-09-15")
        self.assertEqual(r["month"], "2026-03")
        self.assertEqual(r["spent"], 1900.0)
        self.assertEqual(r["usual"], 1075.0)             # rent 700 (median), groceries 300, sofa 900 / 12
        self.assertEqual(r["difference"], 825.0)
        self.assertEqual(r["drivers"], [{"label": "Furniture", "amount": 900.0, "above_usual": 825.0}])
        self.assertEqual(r["biggest_purchase"], {"label": "Furniture", "amount": 900.0, "d": "2026-03-12"})
        self.assertEqual(r["missing_bills"], [])
        self.assertIn("month", r["cheapest_month"])

    def test_highlights(self):
        r = self.tr.explain_month(self.conn, "2026-09-15")
        hl = r["highlights"]
        self.assertTrue(2 <= len(hl) <= 5)
        self.assertIn("March 2026 stood out: you spent €1,900, about €825 above your usual €1,075.", hl[0])
        self.assertIn("furniture (€825 above usual)", hl[1])
        self.assertEqual(r["text"], " ".join(hl[:2]))

    def test_missing_rent_month(self):
        r = self.tr.explain_month(self.conn, "2026-09-15", month="2026-05")
        self.assertEqual(r["missing_bills"], ["Housing"])
        self.assertEqual(r["spent"], 300.0)
        self.assertIn("no housing payment in May 2026", " ".join(r["highlights"]))
        self.assertNotIn("Housing", [d["label"] for d in r["drivers"]])

    def test_named_month_wording_and_top(self):
        r = self.tr.explain_month(self.conn, "2026-09-15", month="2026-03", top=1)
        self.assertTrue(r["highlights"][0].startswith("In March 2026 you spent"))
        self.assertEqual(len(r["drivers"]), 1)

    def test_bad_month(self):
        with self.assertRaises(ValueError):
            self.tr.explain_month(self.conn, "2026-09-15", month="March")
        self.assertTrue(self.tr.explain_month(self.conn, "2026-09-15", month="2024-01")["too_little_data"])
        self.assertTrue(self.tr.explain_month(self.conn, "2026-09-15", month="2026-09")["too_little_data"])


class CustomerATests(unittest.TestCase):
    """Customer A of the invented population: every figure is known to the cent through the oracle."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.trends as tr
        cls.tr = tr
        cls.conn = fx.sandbox()

    def test_money_story_matches_the_oracle(self):
        r = self.tr.money_story(self.conn, fx.TODAY)
        self.assertAlmostEqual(r["balance"]["now"], fx.balance_at(fx.A_CID), 2)
        full = [m for m in fx.month_list(fx.A_CID) if m[0] < fx.TODAY[:7]]
        win = full[-12:]
        self.assertAlmostEqual(r["per_month"]["income"], sum(m[1] for m in win) / 12, 2)
        more_out = sum(1 for m in win if m[2] + m[3] > m[1])
        self.assertEqual(r["months_more_out"], more_out)
        self.assertTrue(2 <= len(r["highlights"]) <= 5)
        self.assertTrue(r["evidence"] and r["explain"])

    def test_dining_out_is_restaurants_plus_fast_food(self):
        r = self.tr.category_story(self.conn, fx.TODAY, "Dining out")
        self.assertAlmostEqual(r["now"]["per_month"], 48.00 + 9.90 + 11.50, 2)     # restaurants + fast food (the 11.50 kebab is fast food too)
        with self.assertRaises(ValueError):
            self.tr.category_story(self.conn, fx.TODAY, "Yachts")

    def test_night_out_is_63_50_a_month(self):
        r = self.tr.category_story(self.conn, fx.TODAY, "Night out")
        self.assertAlmostEqual(r["now"]["per_month"], 63.50, 2)

    def test_explain_month_and_season_run(self):
        r = self.tr.explain_month(self.conn, fx.TODAY)
        self.assertGreaterEqual(len(r["highlights"]), 2)
        s = self.tr.season_outlook(self.conn, fx.TODAY)
        self.assertIn("relevant", s)


if __name__ == "__main__":
    unittest.main()
