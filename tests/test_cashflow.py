"""app/cashflow.py (low_points, income_profile) and the payday rule in app/insights.py.

Tiny in-memory `tx` tables are built inside the tests so every expected number can be checked by hand.
"""
import re
import sqlite3
import unittest

import fixture as fx

SAL = "salary"


def make(rows):
    """rows: (d, amount, type, balance) -> an in-memory `tx` table like the sandbox (spending rows are
    'purchase' in basket 'regular' so they count as spending)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, "
                 "mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
    for i, (d, amt, typ, bal) in enumerate(sorted(rows, key=lambda r: r[0])):
        basket = "income" if amt > 0 else "regular"
        conn.execute("INSERT INTO tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (d, d + "T12:00:00", amt, bal, typ, "", "", "", "Salary" if typ == SAL else "Other",
                      basket, "", i))
    conn.commit()
    return conn


def salaries(days_by_month, amount=2500.0):
    """days_by_month: {(y, m): day} -> salary rows with a flat balance (balance is irrelevant to payday)."""
    return [("%04d-%02d-%02d" % (y, m, d), amount, SAL, 1000.0) for (y, m), d in days_by_month.items()]


def months(y1, m1, y2, m2):
    out, y, m = [], y1, m1
    while (y, m) <= (y2, m2):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


class PaydayRuleTests(unittest.TestCase):
    """The next payday as `insights._usual_payday` and `_next_payday` work it out."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import insights
        cls.ins = insights

    def nxt(self, rows, today):
        conn = make(rows)
        t = self.ins._d(today)
        pay = self.ins._usual_payday(conn, t)
        return pay, (self.ins._next_payday(t, pay, conn).isoformat() if pay is not None else None)

    def test_pure_15th(self):
        rows = salaries({m: 15 for m in months(2026, 1, 2026, 8)})
        self.assertEqual(self.nxt(rows, "2026-09-03"), (15, "2026-09-15"))

    def test_pure_month_end(self):
        rows = salaries({(y, m): self.ins._last_day(y, m) for y, m in months(2026, 1, 2026, 8)})
        pay, nxt = self.nxt(rows, "2026-09-10")
        self.assertEqual((pay, nxt), ("eom", "2026-09-30"))

    def test_mostly_15th_with_two_month_end_and_this_month_paid(self):
        """The bug: Apr-Jun on the 15th, Jul 29 and Aug 31 at month end, Sep 15 paid: next is 15 Oct, not 31 Oct."""
        days = {m: 15 for m in months(2025, 10, 2026, 6)}
        days[(2026, 7)] = 29
        days[(2026, 8)] = 31
        days[(2026, 9)] = 15
        pay, nxt = self.nxt(salaries(days), "2026-09-26")
        self.assertEqual(pay, 15)
        self.assertEqual(nxt, "2026-10-15")

    def test_salary_already_in_this_month(self):
        rows = salaries({m: 15 for m in months(2026, 1, 2026, 9)})
        self.assertEqual(self.nxt(rows, "2026-09-20")[1], "2026-10-15")

    def test_no_salary_yet_this_month_before_the_usual_day(self):
        rows = salaries({m: 15 for m in months(2026, 1, 2026, 8)})
        self.assertEqual(self.nxt(rows, "2026-09-10")[1], "2026-09-15")

    def test_usual_day_passed_without_pay_means_month_end_not_next_month(self):
        rows = salaries({m: 15 for m in months(2026, 1, 2026, 8)})
        self.assertEqual(self.nxt(rows, "2026-09-20")[1], "2026-09-30")

    def test_month_end_only_wins_with_a_majority(self):
        days = {m: 15 for m in months(2026, 1, 2026, 4)}
        days.update({(2026, 5): 31, (2026, 6): 30})
        self.assertEqual(self.nxt(salaries(days), "2026-07-02")[0], 15)
        days2 = {m: 31 if m[1] in (1, 3, 5, 7) else 15 for m in months(2026, 1, 2026, 8)}
        days2.update({(2026, 2): 28, (2026, 4): 30, (2026, 6): 30, (2026, 8): 31})
        self.assertEqual(self.nxt(salaries(days2), "2026-09-02")[0], "eom")

    def test_no_salary_at_all(self):
        conn = make([("2026-01-05", -20.0, "purchase", 10.0)])
        self.assertIsNone(self.ins._usual_payday(conn, self.ins._d("2026-02-01")))

    def test_safe_to_spend_uses_the_corrected_payday(self):
        days = {m: 15 for m in months(2025, 10, 2026, 6)}
        days.update({(2026, 7): 29, (2026, 8): 31, (2026, 9): 15})
        s = self.ins.safe_to_spend(make(salaries(days)), "2026-09-26")
        self.assertEqual(s["next_payday"], "2026-10-15")
        self.assertEqual(s["days_left"], 19)
        self.assertEqual(s["payday_may_be_late_days"], 16)


def limit_rows():
    """Salary on the 15th Jan-Aug; from February a 1,000 purchase on the 10th takes the balance to
    -477.62 (the limit), the next salary brings it back to 522.38."""
    rows = [("2026-01-15", 1000.0, SAL, 522.38)]
    for m in range(2, 9):
        rows.append(("2026-%02d-10" % m, -1000.0, "purchase", -477.62))
        rows.append(("2026-%02d-15" % m, 1000.0, SAL, 522.38))
    rows.append(("2026-09-10", -1000.0, "purchase", -477.62))
    return rows


class LowPointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import cashflow
        cls.cf = cashflow

    def test_days_below_zero_limit_and_months(self):
        r = self.cf.low_points(make(limit_rows()), "2026-09-12")
        self.assertFalse(r["too_little_data"])
        # Feb..Aug: the 10th to the 14th = 5 days each (35), plus 10-12 Sept = 3
        self.assertEqual(r["days_below_zero_365"], 38)
        self.assertEqual(r["by_month"]["2026-03"], 5)
        self.assertEqual(r["by_month"]["2026-09"], 3)
        self.assertEqual(r["limit_seen"], -477.62)
        self.assertEqual(r["days_at_limit"], 8)
        self.assertEqual(r["months_at_limit"], 8)
        self.assertTrue(r["limit_looks_real"])

    def test_limit_wording_and_lowest_sentence(self):
        r = self.cf.low_points(make(limit_rows()), "2026-09-12")
        self.assertEqual(r["highlights"][0], "Your account was below zero on 38 days in the last year.")
        self.assertIn("The lowest your account has been is €478 below zero", r["highlights"][1])
        self.assertIn("8 different months, which looks like your limit", r["highlights"][1])
        self.assertTrue(r["text"].startswith(r["highlights"][0]))
        self.assertGreaterEqual(len(r["highlights"]), 2)
        self.assertLessEqual(len(r["highlights"]), 5)

    def test_cycle_lows_come_a_few_days_before_payday(self):
        r = self.cf.low_points(make(limit_rows()), "2026-09-12")
        self.assertEqual(len(r["cycle_lows"]), 6)
        for c in r["cycle_lows"]:
            self.assertEqual(c["low"], -477.62)
            self.assertEqual(c["days_before_pay"], 5)
        self.assertEqual(r["typical_days_before_pay"], [5, 5])
        self.assertTrue(any("5 days before payday" in h for h in r["highlights"]))

    def test_limit_is_not_claimed_for_two_months(self):
        rows = [("2026-01-15", 1000.0, SAL, 800.0), ("2026-02-10", -1300.0, "purchase", -500.0),
                ("2026-02-15", 1000.0, SAL, 500.0), ("2026-03-10", -1000.0, "purchase", -500.0),
                ("2026-03-15", 1000.0, SAL, 500.0), ("2026-04-10", -600.0, "purchase", -100.0),
                ("2026-04-15", 1000.0, SAL, 900.0)]
        r = self.cf.low_points(make(rows), "2026-05-02")
        self.assertEqual(r["months_at_limit"], 2)
        self.assertFalse(r["limit_looks_real"])
        self.assertNotIn("looks like your limit", " ".join(r["highlights"]))
        self.assertIn("€500 below zero", r["highlights"][1])

    def test_long_pay_gap_with_days_below_zero(self):
        rows = [("2026-01-15", 1000.0, SAL, 1500.0), ("2026-02-15", 1000.0, SAL, 1800.0),
                ("2026-03-15", 1000.0, SAL, 500.0), ("2026-03-20", -700.0, "purchase", -200.0),
                ("2026-04-30", 1000.0, SAL, 800.0), ("2026-05-15", 1000.0, SAL, 1800.0)]
        r = self.cf.low_points(make(rows), "2026-05-20")
        self.assertEqual(len(r["long_gaps"]), 1)
        g = r["long_gaps"][0]
        self.assertEqual((g["from"], g["to"], g["days"]), ("2026-03-15", "2026-04-30", 46))
        self.assertEqual(g["days_below_zero"], 12 + 29)       # 20-31 March, 1-29 April
        self.assertTrue(any("Between 15 March and 30 April there were 46 days without pay, "
                            "and you were below zero on 41 of them" in h for h in r["highlights"]))

    def test_never_below_zero_gets_positive_facts(self):
        rows = []
        for m in range(1, 9):
            rows.append(("2026-%02d-15" % m, 2000.0, SAL, 3000.0 + m))
            rows.append(("2026-%02d-20" % m, -300.0, "purchase", 2700.0 + m))
        r = self.cf.low_points(make(rows), "2026-09-05")
        self.assertEqual(r["days_below_zero_365"], 0)
        self.assertIsNone(r["limit_seen"])
        text = " ".join(r["highlights"])
        self.assertIn("The lowest your account has been is €2,701, on 20 January.", text)
        self.assertIn("covers about", text)
        self.assertIn("has not gone below zero", text)
        self.assertNotIn("limit", text)

    def test_no_minus_sign_before_money(self):
        for rows, today in ((limit_rows(), "2026-09-12"),):
            r = self.cf.low_points(make(rows), today)
            for h in r["highlights"]:
                self.assertIsNone(re.search(r"[-−–]\s?€", h), h)

    def test_empty_and_thin_data_never_raise(self):
        empty = make([])
        for fn in (self.cf.low_points, self.cf.income_profile):
            r = fn(empty, "2026-09-12")
            self.assertTrue(r["too_little_data"])
            self.assertEqual(r["highlights"], [])
        no_salary = make([("2026-01-05", -20.0, "purchase", 10.0), ("2026-08-05", -20.0, "purchase", -10.0)])
        self.assertTrue(self.cf.low_points(no_salary, "2026-09-12")["too_little_data"])
        short = make([("2026-08-15", 2000.0, SAL, 2000.0), ("2026-09-01", -50.0, "purchase", 1950.0)])
        self.assertTrue(self.cf.low_points(short, "2026-09-12")["too_little_data"])
        self.assertTrue(self.cf.income_profile(short, "2026-09-12")["too_little_data"])


class IncomeProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import cashflow
        cls.cf = cashflow

    def veeti_like(self):
        days = {m: 15 for m in months(2025, 10, 2026, 6)}
        days.update({(2026, 7): 29, (2026, 8): 31, (2026, 9): 15})
        rows = salaries(days)
        rows[0] = (rows[0][0], 2035.0, SAL, 1000.0)
        rows[1] = (rows[1][0], 2865.0, SAL, 1000.0)
        rows.append(("2026-03-08", 965.05, "other_income", 1000.0))
        return rows

    def test_usual_day_range_and_next_payday(self):
        r = self.cf.income_profile(make(self.veeti_like()), "2026-09-26")
        self.assertEqual(r["usual_day"], 15)
        self.assertEqual(r["salaries"], 12)
        self.assertEqual(r["on_usual_day"], 10)
        self.assertEqual(r["month_end"], 2)         # 29 Jul and 31 Aug are in the last four days
        self.assertEqual(r["range"], [2035.0, 2865.0])
        self.assertEqual(r["next_payday"], "2026-10-15")
        self.assertTrue(r["paid_this_month"])
        self.assertEqual(r["other_income"], [{"d": "2026-03-08", "amount": 965.05}])

    def test_sentences(self):
        r = self.cf.income_profile(make(self.veeti_like()), "2026-09-26")
        self.assertEqual(r["highlights"][0],
                         "You are usually paid on the 15th (10 of the last 12 times), between €2,035 and €2,865.")
        text = " ".join(r["highlights"])
        self.assertIn("15 October, 19 days away", text)
        self.assertIn("as late as 31 October", text)
        self.assertIn("€965 on 8 March", text)
        self.assertGreaterEqual(len(r["highlights"]), 2)
        self.assertLessEqual(len(r["highlights"]), 5)
        self.assertEqual(r["text"], " ".join(r["highlights"][:2]))
        self.assertTrue(r["explain"])

    def test_no_salary_yet_this_month_and_the_usual_day_has_passed(self):
        rows = salaries({m: 15 for m in months(2026, 1, 2026, 8)})
        r = self.cf.income_profile(make(rows), "2026-09-26")
        self.assertFalse(r["paid_this_month"])
        self.assertEqual(r["next_payday"], "2026-09-30")
        self.assertEqual(r["days_to_payday"], 4)

    def test_pure_month_end_customer(self):
        rows = salaries({(y, m): __import__("calendar").monthrange(y, m)[1] for y, m in months(2026, 1, 2026, 8)})
        r = self.cf.income_profile(make(rows), "2026-09-10")
        self.assertEqual(r["usual_day"], "eom")
        self.assertEqual(r["next_payday"], "2026-09-30")
        self.assertIn("at the end of the month", r["highlights"][0])

    def test_longest_wait(self):
        days = {m: 15 for m in months(2026, 1, 2026, 8)}
        days[(2026, 4)] = 30
        r = self.cf.income_profile(make(salaries(days)), "2026-09-03")
        self.assertEqual(r["longest_gap"], {"from": "2026-03-15", "to": "2026-04-30", "days": 46})
        self.assertIn("46 days, from 15 March to 30 April", " ".join(r["highlights"]))


class FixtureCustomerTests(unittest.TestCase):
    """The functions work on every invented customer, including the one who is permanently below zero."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import cashflow, db
        cls.cf, cls.db = cashflow, db

    def test_all_fixture_customers(self):
        for cid in (fx.A_CID, fx.B_CID, fx.D_CID):
            conn = self.db.sandbox(cid, fx.TODAY)
            lp = self.cf.low_points(conn, fx.TODAY)
            ip = self.cf.income_profile(conn, fx.TODAY)
            for r in (lp, ip):
                self.assertIn("highlights", r)
                self.assertIn("explain", r)
                if not r["too_little_data"]:
                    self.assertTrue(2 <= len(r["highlights"]) <= 5, (cid, r["highlights"]))
            if not ip["too_little_data"]:
                self.assertTrue(ip["usual_day"] == "eom" or isinstance(ip["usual_day"], int))
                self.assertTrue(ip["next_payday"] > fx.TODAY)
        d = self.cf.low_points(self.db.sandbox(fx.D_CID, fx.TODAY), fx.TODAY)
        self.assertGreater(d["days_below_zero_365"], 0)


if __name__ == "__main__":
    unittest.main()
