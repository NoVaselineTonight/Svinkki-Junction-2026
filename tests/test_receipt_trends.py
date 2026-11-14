"""Longer receipt views: the highlight ranking (B2), receipt_trends, basket_profile and cut_ideas.

Everything runs on the invented population (customer A is known to the cent); nothing reads the real dataset.
Where a test needs particular receipt lines, `_receipts_in` is replaced by a handful of hand-made receipts.
"""
import os as _os
import sqlite3
import sys as _sys
import unittest
from datetime import date, timedelta
from unittest import mock

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

A = fx.A_CID
TODAY = fx.TODAY          # 2026-09-24


def _add_months(d, n):
    idx = d.year * 12 + (d.month - 1) + n
    y, m = divmod(idx, 12)
    return date(y, m + 1, min(d.day, 28))


def _from_of(months):
    t = date.fromisoformat(TODAY)
    return (_add_months(t, -months) + timedelta(days=1)).isoformat()


def _whole_window(months):
    """basket_profile counts "last N months" as the N last FULL calendar months (as trends.category_story does)."""
    t = date.fromisoformat(TODAY)
    to = t.replace(day=1) - timedelta(days=1)
    return _add_months(to.replace(day=1), -(months - 1)).isoformat(), to.isoformat()


def _fake(i, d, lines):
    """A grocery receipt from (group, name, qty, line_total) tuples."""
    ls = [{"name": n, "group": g, "qty": q, "unit": "kpl", "unit_price": round(t / q, 2),
           "line_total": t, "essential": False} for g, n, q, t in lines]
    total = round(sum(x["line_total"] for x in ls), 2)
    return {"tx_id": i, "store": "S-market", "kind": "grocery", "d": d, "ts": d + " 17:30:00", "total": total,
            "lines": ls, "bonus": {"rate_pct": 3, "amount": 0.0, "label": "Bonus estimate"}, "simulated": True}


def _habit_receipts(beer=0.0, snacks=0.0, energy=0.0, ready=0.0, soft=0.0, n=6):
    """n receipts in the last 3 months, each with a big pantry line plus an equal share of each group's euros."""
    out = []
    for k in range(n):
        d = (date.fromisoformat(TODAY) - timedelta(days=5 + 10 * k)).isoformat()
        lines = [("pantry", "Riisi 1 kg", 1, 40.0)]
        for g, nm, euros in (("alcohol_mild", "Olut 0,5 l tölkki", beer), ("snacks_sweets", "Perunalastut 175 g", snacks),
                             ("energy_drinks", "Energiajuoma 0,5 l", energy), ("ready_meals", "Lasagne 400 g", ready),
                             ("soft_drinks", "Cola 1,5 l", soft)):
            if euros:
                lines.append((g, nm, 1, round(euros / n, 2)))
        out.append(_fake(1000 + k, d, lines))
    return out


def _grocery_oracle(frm, to=TODAY, label="Groceries"):
    """The grocery (or fuel) payments of customer A in [frm, to], straight from the generator."""
    return [r for r in fx.rows_for(A) if r["label"] == label and r["type"] == "purchase" and r["amount"] < 0
            and frm <= r["d"] <= to]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import receipts
        cls.r = receipts
        cls.conn = fx.sandbox(A)


class B2RankingTests(_Base):
    def _texts(self, recs):
        with mock.patch.object(self.r, "_receipts_in", return_value=recs):
            res = self.r.receipt_insights(self.conn, TODAY, "last_3_months", habit_seed=A)
        return res["highlights"]

    def test_the_big_extra_group_is_heard_and_the_tiny_one_is_not(self):
        # energy drinks: 3 receipts, EUR 2.37 in 3 months (about 0.79 a month); beer: EUR 531 (177 a month)
        recs = _habit_receipts(beer=531.0, energy=2.37, n=6)
        for rc in recs[3:]:                     # energy only on the first three receipts
            rc["lines"] = [ln for ln in rc["lines"] if ln["group"] != "energy_drinks"]
            rc["total"] = round(sum(ln["line_total"] for ln in rc["lines"]), 2)
        text = " ".join(self._texts(recs))
        self.assertIn("Beer and cider", text)
        self.assertIn("€177 a month", text)
        self.assertNotIn("You bought energy drinks", text)

    def test_extras_are_ranked_by_euros_a_month(self):
        # energy 30 (10 a month), snacks 60 (20 a month), beer 150 (50 a month); only two extras fit
        hl = self._texts(_habit_receipts(beer=150.0, snacks=60.0, energy=30.0))
        text = " ".join(hl)
        self.assertLessEqual(len(hl), 4)
        self.assertIn("Beer and cider", text)
        self.assertIn("Snacks and sweets", text)
        self.assertNotIn("energy drinks", text)
        self.assertLess(text.index("Beer and cider"), text.index("Snacks and sweets"))

    def test_a_group_under_the_floor_is_left_out_even_with_room(self):
        # 12 EUR over 3 months = 4 a month: under the 5 a month floor
        hl = self._texts(_habit_receipts(soft=12.0))
        self.assertNotIn("Soft drinks", " ".join(hl))

    def test_deterministic(self):
        recs = _habit_receipts(beer=150.0, snacks=60.0, energy=30.0)
        self.assertEqual(self._texts(recs), self._texts(recs))


class ReceiptTrendsTests(_Base):
    def test_totals_equal_the_grocery_payments(self):
        for key, months in (("last_12_months", 12), ("last_24_months", 24)):
            res = self.r.receipt_trends(self.conn, TODAY, key, habit_seed=A)
            pays = _grocery_oracle(_from_of(months))
            self.assertEqual(res["receipt_count"], len(pays), key)
            self.assertAlmostEqual(res["total"], round(-sum(p["amount"] for p in pays), 2), places=2)
            listed = sum(g["total"] for g in res["groups"]) + res["other_groups"]["total"]
            self.assertAlmostEqual(listed, res["total"], places=2)
            self.assertAlmostEqual(sum(g["share"] for g in res["groups"]), 1 - res["other_groups"]["total"] / res["total"],
                                   delta=0.01)
            self.assertEqual(res["period"]["months"], float(months))

    def test_groups_carry_euros_per_month_and_receipts(self):
        res = self.r.receipt_trends(self.conn, TODAY, "last_12_months", habit_seed=A)
        self.assertTrue(res["groups"])
        for g in res["groups"]:
            self.assertAlmostEqual(g["monthly"], g["total"] / 12.0, delta=0.01)
            self.assertGreaterEqual(g["monthly"], 5.0)
            self.assertLessEqual(g["receipts"], res["receipt_count"])
            self.assertGreaterEqual(g["items"], g["receipts"])
        self.assertEqual([g["total"] for g in res["groups"]], sorted((g["total"] for g in res["groups"]), reverse=True))

    def test_half_years_cover_the_period(self):
        res = self.r.receipt_trends(self.conn, TODAY, "last_24_months", habit_seed=A)
        halves = res["half_years"]
        self.assertEqual(len(halves), 4)
        self.assertEqual(halves[0]["from"], _from_of(24))
        self.assertEqual(halves[-1]["to"], TODAY)
        for h in halves:
            self.assertAlmostEqual(h["months"], 6.0, places=1)
        # a half year's euros a month times its months is that half's grocery payments
        a, b = halves[-1]["from"], halves[-1]["to"]
        want = -sum(p["amount"] for p in _grocery_oracle(a, b))
        self.assertAlmostEqual(halves[-1]["grocery_monthly"] * halves[-1]["months"], want, delta=0.05)

    def test_fuel_matches_the_fuel_payments(self):
        res = self.r.receipt_trends(self.conn, TODAY, "last_12_months", habit_seed=A)
        pays = _grocery_oracle(_from_of(12), label="Fuel")
        paid = -sum(p["amount"] for p in pays)
        self.assertEqual(res["fuel"]["fills"], len(pays))
        # the fuel lines are most of each payment; the rest is a coffee or a wash at the station
        self.assertLessEqual(res["fuel"]["total"], round(paid, 2))
        self.assertGreater(res["fuel"]["total"], 0.8 * paid)
        self.assertGreater(res["fuel"]["litres"], 0)
        self.assertTrue(1.5 < res["fuel"]["avg_price_per_litre"] < 2.2)
        self.assertAlmostEqual(res["fuel"]["monthly"], res["fuel"]["total"] / 12.0, delta=0.01)

    def test_says_simulated_and_never_claims_a_rising_share(self):
        res = self.r.receipt_trends(self.conn, TODAY, "last_12_months", habit_seed=A)
        self.assertIn("Simulated", res["note"])
        self.assertIn("simulated", res["text"])
        self.assertTrue(res["highlights"])
        for h in res["highlights"]:
            self.assertRegex(h, r"€\d")
            for word in ("rising", "rose", "growing", "increas", "price"):
                self.assertNotIn(word, h.lower())

    def test_other_periods_are_refused(self):
        with self.assertRaises(ValueError):
            self.r.receipt_trends(self.conn, TODAY, "last_3_months", habit_seed=A)

    def test_deterministic(self):
        a = self.r.receipt_trends(self.conn, TODAY, "last_12_months", habit_seed=A)
        b = self.r.receipt_trends(self.conn, TODAY, "last_12_months", habit_seed=A)
        self.assertEqual(a, b)


class BasketProfileTests(_Base):
    def test_counts_match_the_known_shops(self):
        res = self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A)
        pays = _grocery_oracle(*_whole_window(12))
        amounts = [-p["amount"] for p in pays]
        n = len(amounts)
        self.assertEqual(res["trips"], n)
        self.assertAlmostEqual(res["total"], round(sum(amounts), 2), places=2)
        self.assertAlmostEqual(res["average_basket"], sum(amounts) / n, delta=0.01)
        self.assertAlmostEqual(res["trips_per_month"], n / 12.0, delta=0.01)
        # 62.40+ and 75.25 are big shops (two of five); the 10.00 shop is the only small top-up
        self.assertEqual(res["big_shops"]["count"], sum(1 for a in amounts if a >= 60))
        self.assertEqual(res["small_topups"]["count"], sum(1 for a in amounts if a < 25))
        self.assertEqual(res["big_shops"]["count"] + res["small_topups"]["count"] + res["middle_shops"], n)
        self.assertAlmostEqual(res["big_shops"]["share"], 0.4, delta=0.03)

    def test_most_expensive_weekday_and_time(self):
        res = self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A)
        pays = _grocery_oracle(*_whole_window(12))
        top = max(pays, key=lambda p: (-p["amount"], p["d"]))
        self.assertEqual(res["most_expensive"]["amount"], round(-top["amount"], 2))
        self.assertEqual(res["most_expensive"]["d"], top["d"])
        self.assertEqual(res["most_expensive"]["amount"], 75.25)
        wd = {}
        for p in pays:
            k = date.fromisoformat(p["d"]).strftime("%A")
            wd[k] = wd.get(k, 0) + 1
        self.assertEqual(res["busiest_weekday"]["trips"], max(wd.values()))
        self.assertEqual(res["weekday_trips"], wd)
        self.assertEqual(sum(res["weekday_trips"].values()), len(pays))
        self.assertEqual(res["busiest_time"]["name"], "in the afternoon")      # four of five shops are at 17:30

    def test_busiest_and_quietest_month_use_whole_months(self):
        res = self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A)
        m = res["months"]
        # every whole month holds five shops, so there is nothing to call busiest or quietest
        self.assertIsNone(m)

    def test_change_against_the_period_before(self):
        res = self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A)
        ch = res["change"]
        self.assertIsNotNone(ch)
        self.assertEqual(ch["driver"], "none")           # five shops every month, both years
        self.assertAlmostEqual(ch["trips_per_month_before"], res["trips_per_month"], delta=0.3)

    def test_highlights_hold_their_figures(self):
        res = self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A)
        text = " ".join(res["highlights"])
        self.assertIn("grocery trips a month", text)
        self.assertIn("€75", text)
        self.assertIn("big shops of €60 or more", text)
        self.assertIn("top-ups under €25", text)
        self.assertEqual(text, res["text"])
        self.assertNotRegex(text, r"\d{4}-\d{2}-\d{2}")

    def test_trips_not_baskets_when_trips_change(self):
        """Fewer, same-size trips in the latest period: the change is put down to trips."""
        conn = _tx_conn()
        for m in range(-23, -11):                 # the 12 months before: 3 trips a month at 70
            for day in (3, 10, 17):
                _add_pay(conn, _month_day(m, day), 70.0)
        for m in range(-11, 1):                   # the latest 12 months: 5 trips a month at 70
            for day in (2, 6, 10, 14, 18):
                _add_pay(conn, _month_day(m, day), 70.0)
        res = self.r.basket_profile(conn, TODAY, "last_12_months", habit_seed=A)
        self.assertEqual(res["change"]["driver"], "trips")
        text = " ".join(res["highlights"])
        self.assertIn("not with bigger baskets", text)
        self.assertGreater(res["trips_per_month"], res["change"]["trips_per_month_before"])

    def test_deterministic(self):
        a = self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A)
        self.assertEqual(a, self.r.basket_profile(self.conn, TODAY, "last_12_months", habit_seed=A))


def _tx_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, mcc TEXT, "
                 "merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
    conn.execute("INSERT INTO tx VALUES ('2024-10-02', '2024-10-02 06:00:00', -900, 0, 'purchase', '', '', 'x', "
                 "'Housing', 'regular', '', 1)")
    return conn


def _month_day(offset, day):
    """A date `offset` months from today's month (day clipped to 28), as an ISO string."""
    t = date.fromisoformat(TODAY)
    return _add_months(date(t.year, t.month, 1), offset).replace(day=min(day, 28)).isoformat()


def _add_pay(conn, d, amount, hour=17, label="Groceries"):
    n = conn.execute("SELECT COUNT(*) FROM tx").fetchone()[0] + 1
    conn.execute("INSERT INTO tx VALUES (?, ?, ?, 0, 'purchase', '', '', 'm', ?, 'regular', '', ?)",
                 (d, "%s %02d:00:00" % (d, hour), -amount, label, n))


class CutIdeasTests(_Base):
    def _ideas(self, recs, conn=None):
        with mock.patch.object(self.r, "_receipts_in", return_value=recs):
            return self.r.cut_ideas(conn or self.conn, TODAY, "last_3_months", habit_seed=A)

    def test_ranked_by_saving_and_small_ideas_dropped(self):
        # a month's worth (3 months): beer 90 (30 a month), snacks 120 (40), ready meals 60 (20), soft drinks 12 (4)
        res = self._ideas(_habit_receipts(beer=90.0, snacks=120.0, ready=60.0, soft=12.0))
        ids = [i["id"] for i in res["ideas"]]
        self.assertEqual(ids, ["snacks_sweets", "beer_cider", "ready_meals"])
        saved = [i["saved_monthly"] for i in res["ideas"]]
        self.assertEqual(saved, sorted(saved, reverse=True))
        self.assertTrue(all(s >= 5.0 for s in saved))
        self.assertGreaterEqual(len(res["ideas"]), 2)
        self.assertLessEqual(len(res["ideas"]), 4)
        by = {i["id"]: i for i in res["ideas"]}
        self.assertAlmostEqual(by["snacks_sweets"]["monthly_now"], 40.0, places=2)
        self.assertAlmostEqual(by["snacks_sweets"]["saved_monthly"], 20.0, places=2)
        # ready meals: half of them cooked at 40% of the price saves 0.5 * 0.6 of the 20 a month
        self.assertAlmostEqual(by["ready_meals"]["saved_monthly"], 6.0, places=2)
        self.assertIn("40%", by["ready_meals"]["basis"])
        # beer: the customer's own average line (15.00 a receipt) times half the purchases (1 a month / 2)
        self.assertAlmostEqual(by["beer_cider"]["saved_monthly"], 15.0 * 1.0, delta=0.01)
        for i in res["ideas"]:
            self.assertEqual(set(i), {"id", "title", "detail", "monthly_now", "saved_monthly", "basis"})
            self.assertRegex(i["detail"], r"€\d")
        self.assertEqual(res["highlights"], [i["detail"] for i in res["ideas"]])

    def test_floor_drops_every_small_idea(self):
        res = self._ideas(_habit_receipts(soft=12.0, snacks=18.0, ready=20.0))
        self.assertEqual(res["ideas"], [])
        self.assertEqual(res["highlights"], [])

    def test_at_most_four_ideas(self):
        conn = _tx_conn()
        for m in (-2, -1, 0):                      # a fifth idea: eight small top-ups a month (saves 52)
            for j in range(8):
                _add_pay(conn, _month_day(m, 2 + 3 * j), 12.0)
        res = self._ideas(_habit_receipts(beer=300.0, snacks=300.0, ready=300.0, soft=300.0, energy=300.0), conn=conn)
        self.assertEqual(len(res["ideas"]), 4)          # five candidates, the four that save most are kept
        self.assertNotIn("ready_meals", [i["id"] for i in res["ideas"]])

    def test_top_up_trips_from_the_payments(self):
        conn = _tx_conn()
        for m in (-2, -1, 0):                      # eight 12 EUR top-ups a month for three months
            for j in range(8):
                _add_pay(conn, _month_day(m, 2 + 3 * j), 12.0)
        res = self._ideas(_habit_receipts(beer=0.0, snacks=0.0, ready=0.0), conn=conn)
        ids = [i["id"] for i in res["ideas"]]
        self.assertIn("top_up_trips", ids)
        idea = [i for i in res["ideas"] if i["id"] == "top_up_trips"][0]
        self.assertAlmostEqual(idea["saved_monthly"], 12.0 * 52.0 / 12.0, delta=0.01)
        self.assertAlmostEqual(idea["monthly_now"], 96.0, delta=0.5)
        self.assertIn("€12", idea["detail"])

    def test_few_top_ups_are_not_an_idea(self):
        res = self._ideas(_habit_receipts(snacks=120.0))        # customer A has one small top-up a month
        self.assertNotIn("top_up_trips", [i["id"] for i in res["ideas"]])

    def test_real_receipts_for_a_customer(self):
        res = self.r.cut_ideas(self.conn, TODAY, "last_3_months", habit_seed=A)
        saved = [i["saved_monthly"] for i in res["ideas"]]
        self.assertEqual(saved, sorted(saved, reverse=True))
        self.assertIn("Simulated", res["note"])
        a = self.r.cut_ideas(self.conn, TODAY, "last_3_months", habit_seed=A)
        self.assertEqual(res, a)


class ThinDataTests(_Base):
    def test_no_receipts_in_the_period_gives_empty_highlights(self):
        conn = fx.sandbox(A, "2024-10-01")          # nothing has been bought yet
        for fn, p in ((self.r.receipt_trends, "last_12_months"), (self.r.basket_profile, "last_12_months"),
                      (self.r.cut_ideas, "last_3_months"), (self.r.receipt_trends, "last_24_months")):
            res = fn(conn, "2024-10-01", p, habit_seed=A)
            self.assertEqual(res["highlights"], [], fn.__name__)
            self.assertIsInstance(res["text"], str)
            self.assertTrue(res["text"])

    def test_insights_with_no_receipts_still_answers(self):
        conn = fx.sandbox(A, "2024-10-01")
        res = self.r.receipt_insights(conn, "2024-10-01", "last_3_months", habit_seed=A)
        self.assertTrue(res["highlights"])

    def test_a_customer_with_a_few_weeks_of_data_is_not_diluted(self):
        conn = _tx_conn()
        conn.execute("DELETE FROM tx WHERE label = 'Housing'")        # the data starts with the first shop
        for j in range(6):
            _add_pay(conn, _month_day(-1, 3 + 4 * j), 50.0)           # six shops of 50 in one month
        res = self.r.basket_profile(conn, TODAY, "last_12_months", habit_seed=A)
        self.assertEqual(res["trips"], 6)
        self.assertGreater(res["trips_per_month"], 1.0)               # not 6 / 12
        self.assertIsNone(res["change"])


class ToolSignatureTests(_Base):
    def test_same_leading_arguments_as_receipt_insights(self):
        import inspect
        base = list(inspect.signature(self.r.receipt_insights).parameters)
        for fn in (self.r.receipt_trends, self.r.basket_profile, self.r.cut_ideas):
            self.assertEqual(list(inspect.signature(fn).parameters), base)


if __name__ == "__main__":
    unittest.main()
