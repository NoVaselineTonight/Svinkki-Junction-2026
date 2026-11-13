"""Insight calculations, checked against numbers computed independently from the fixture generator.

Acceptance: M4 (numbers), M6, M8, M9, M11, S1, S5; plan: SR-10, SR-11, SR-13, SR-14, SR-15, V7, V9, V10.
"""
import json
import math
import re
import statistics
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

TODAY = fx.TODAY
A = fx.A_CID


def spent_and_surplus_ok(income, spent, surplus, r1_spent, savings):
    """The contract does not say whether the investment deposit counts as spending.
    Accepted readings: spent excludes savings (surplus before or after savings), or spent includes savings."""
    readings = [
        (r1_spent, income - r1_spent),
        (r1_spent, income - r1_spent - savings),
        (r1_spent + savings, income - r1_spent - savings),
    ]
    return any(abs(spent - s) <= 0.02 and abs(surplus - u) <= 0.02 for s, u in readings)


class InsightCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.insights as ins
        import app.db as db
        cls.ins = ins
        cls.db = db
        cls.conn = db.sandbox(A, TODAY)

    def run_evidence(self, ev, conn=None):
        return self.ins.transactions(conn or self.conn, TODAY, **fx.evidence_kwargs(ev))

    def assertTraceable(self, result):
        self.assertTrue(result.get("evidence"), "SR-11: every figure needs evidence")
        for ev in result["evidence"]:
            self.assertIn("title", ev)            # from/to are optional: transactions() treats a missing bound as open
            self.run_evidence(ev)                 # every filter must be accepted by transactions()
        self.assertIsInstance(result.get("explain"), str)
        self.assertTrue(result["explain"].strip())


class PeriodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.insights as ins
        cls.period = staticmethod(ins.period)

    def p(self, today, name):
        return tuple(self.period(today, name))

    def test_this_and_last_week_start_on_monday(self):
        self.assertEqual(self.p("2026-09-24", "this_week"), ("2026-09-21", "2026-09-24"))   # Thursday
        self.assertEqual(self.p("2026-09-24", "last_week"), ("2026-09-14", "2026-09-20"))
        self.assertEqual(self.p("2026-09-21", "this_week"), ("2026-09-21", "2026-09-21"))   # Monday itself
        self.assertEqual(self.p("2026-09-27", "this_week"), ("2026-09-21", "2026-09-27"))   # Sunday belongs to that week
        self.assertEqual(self.p("2026-09-20", "last_week"), ("2026-09-07", "2026-09-13"))
        self.assertEqual(self.p("2026-01-01", "this_week"), ("2025-12-29", "2026-01-01"))   # across a year boundary

    def test_this_and_last_month(self):
        self.assertEqual(self.p("2026-09-24", "this_month"), ("2026-09-01", "2026-09-24"))
        self.assertEqual(self.p("2026-09-24", "last_month"), ("2026-08-01", "2026-08-31"))
        self.assertEqual(self.p("2026-03-31", "last_month"), ("2026-02-01", "2026-02-28"))
        self.assertEqual(self.p("2024-03-31", "last_month"), ("2024-02-01", "2024-02-29"))  # leap year
        self.assertEqual(self.p("2026-01-15", "last_month"), ("2025-12-01", "2025-12-31"))

    def test_named_month_and_year_to_date(self):
        self.assertEqual(self.p("2026-09-24", "2026-06"), ("2026-06-01", "2026-06-30"))
        self.assertEqual(self.p("2026-09-24", "2024-02"), ("2024-02-01", "2024-02-29"))
        self.assertEqual(self.p("2026-09-24", "ytd"), ("2026-01-01", "2026-09-24"))

    def test_rolling_windows_end_at_today_and_have_the_right_length(self):
        for name, months in (("last_3_months", 3), ("last_12_months", 12)):
            frm, to = self.p("2026-09-24", name)
            self.assertLessEqual(to, "2026-09-24", name)
            self.assertLess(frm, to)
            days = (__import__("datetime").date.fromisoformat(to) - __import__("datetime").date.fromisoformat(frm)).days
            self.assertGreaterEqual(days, months * 28 - 35, name)
            self.assertLessEqual(days, months * 31 + 35, name)

    def test_unknown_period_is_rejected(self):
        with self.assertRaises((ValueError, KeyError)):
            self.period("2026-09-24", "next_century")


class TransactionsTests(InsightCase):
    def test_filters_return_the_known_rows(self):
        r = self.ins.transactions(self.conn, TODAY, frm="2026-08-01", to="2026-08-31", label="Taxi")
        self.assertEqual(r["count"], 3)
        self.assertAlmostEqual(abs(r["total"]), 62.10, places=2)
        self.assertEqual(sorted(abs(x["amount"]) for x in r["rows"]), [14.20, 19.90, 28.00])
        for row in r["rows"]:
            for key in ("d", "ts", "amount", "label", "basket", "context", "category", "merchant"):
                self.assertIn(key, row)
        self.assertFalse(r["truncated"])

    def test_context_basket_and_type_filters(self):
        r = self.ins.transactions(self.conn, TODAY, frm="2026-08-01", to="2026-08-31", context="night_out")
        self.assertEqual(r["count"], 3)
        self.assertAlmostEqual(abs(r["total"]), 63.50, places=2)
        r = self.ins.transactions(self.conn, TODAY, frm="2026-06-01", to="2026-06-30", basket="unexpected")
        self.assertEqual(r["count"], 1)
        self.assertAlmostEqual(abs(r["total"]), 600.00, places=2)
        r = self.ins.transactions(self.conn, TODAY, frm="2026-08-01", to="2026-08-31", type="salary")
        self.assertEqual(r["count"], 1)
        self.assertAlmostEqual(r["rows"][0]["amount"], 3000.00, places=2)

    def test_rows_after_today_are_never_returned(self):
        r = self.ins.transactions(self.conn, TODAY, frm="2026-09-25", to="2026-09-30")
        self.assertEqual(r["count"], 0)
        self.assertEqual(r["rows"], [])
        r = self.ins.transactions(self.conn, TODAY, frm="2026-09-01", to="2026-12-31", label="Taxi")
        self.assertNotIn(77.77, [abs(x["amount"]) for x in r["rows"]])

    def test_limit_marks_truncation(self):
        r = self.ins.transactions(self.conn, TODAY, limit=2)
        self.assertEqual(len(r["rows"]), 2)
        self.assertTrue(r["truncated"])
        r = self.ins.transactions(self.conn, TODAY, limit=100000)
        self.assertLessEqual(len(r["rows"]), 500, "result sets stay bounded (the 50-row tool cap is tested in test_coach)")

    def test_free_text_and_filters_are_parameterised(self):
        for kw in ({"q": "x' OR '1'='1"}, {"label": "Taxi' OR '1'='1"}, {"basket": "regular' --"}):
            r = self.ins.transactions(self.conn, TODAY, **kw)
            self.assertEqual(r["count"], 0, kw)


class SpendTests(InsightCase):
    def test_taxis_last_month(self):
        r = self.ins.spend(self.conn, TODAY, period="last_month", label="Taxi")
        want, n = fx.spend(A, "2026-08-01", "2026-08-31", "Taxi")
        self.assertEqual((want, n), (62.10, 3))                   # sanity: the generator is what we think
        self.assertEqual(fx.pfrom(r["period"]), ("2026-08-01", "2026-08-31"))
        self.assertAlmostEqual(r["total"], want, places=2)
        self.assertEqual(r["count"], n)
        self.assertAlmostEqual(sum(x["total"] for x in r["by_label"]), r["total"], places=2)
        self.assertEqual(round(r["total"], 2), r["total"])
        self.assertTraceable(r)

    def test_night_out_context(self):
        r = self.ins.spend(self.conn, TODAY, period="last_month", context="night_out")
        want, n = fx.spend(A, "2026-08-01", "2026-08-31", context="night_out")
        self.assertEqual((want, n), (63.50, 3))
        self.assertAlmostEqual(r["total"], want, places=2)
        self.assertEqual(r["count"], n)

    def test_other_labels_baskets_and_periods_match_the_oracle(self):
        cases = [
            dict(period="last_month", label="Groceries"), dict(period="last_month", label="Restaurant"),
            dict(period="last_month", label="Fast food"), dict(period="last_month", label="Pharmacy"),
            dict(period="last_month", basket="everyday"), dict(period="last_month", basket="regular"),
            dict(period="this_month", label="Groceries"), dict(period="this_month", label="Taxi"),
            dict(period="this_week", label="Taxi"), dict(period="last_week", label="Taxi"),
            dict(period="last_week", label="Fast food"), dict(period="2026-06", label="Electronics"),
            dict(period="2026-06", basket="unexpected"),
        ]
        for kw in cases:
            with self.subTest(**kw):
                frm, to = fx.pfrom(self.ins.period(TODAY, kw["period"]))
                want, n = fx.spend(A, frm, to, labels=kw.get("label"), basket=kw.get("basket"))
                r = self.ins.spend(self.conn, TODAY, **kw)
                self.assertAlmostEqual(r["total"], want, places=2)
                self.assertEqual(r["count"], n)

    def test_known_hand_values(self):
        self.assertAlmostEqual(self.ins.spend(self.conn, TODAY, period="this_week", label="Taxi")["total"], 19.90, places=2)
        self.assertAlmostEqual(self.ins.spend(self.conn, TODAY, period="last_week", label="Taxi")["total"], 28.00, places=2)
        self.assertAlmostEqual(self.ins.spend(self.conn, TODAY, period="2026-06", label="Electronics")["total"], 600.00, places=2)
        # the 77.77 taxi on 30 September lies after "today" and must not count
        self.assertAlmostEqual(self.ins.spend(self.conn, TODAY, period="this_month", label="Taxi")["total"], 62.10, places=2)

    def test_no_matching_rows_gives_zero_not_an_error(self):
        r = self.ins.spend(self.conn, TODAY, period="last_month", label="Doctor")
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["count"], 0)

    def test_empty_customer_does_not_crash(self):
        empty = self.db.sandbox("CUST99999", TODAY)
        r = self.ins.spend(empty, TODAY, period="last_month", label="Taxi")
        self.assertEqual(r["total"], 0)

    def test_evidence_total_equals_the_number_it_supports(self):
        for kw in (dict(period="last_month", label="Taxi"), dict(period="last_month", context="night_out"),
                   dict(period="last_month", basket="everyday"), dict(period="this_week", label="Taxi")):
            with self.subTest(**kw):
                r = self.ins.spend(self.conn, TODAY, **kw)
                hits = [self.run_evidence(ev) for ev in r["evidence"]]
                self.assertTrue(any(abs(abs(h["total"]) - r["total"]) <= 0.01 and h["count"] == r["count"] for h in hits),
                                "no evidence filter reproduces total %s / count %s: %r" % (
                                    r["total"], r["count"], [(h["total"], h["count"]) for h in hits]))


class OverviewTests(InsightCase):
    def test_august_figures(self):
        frm, to = fx.month_bounds("2026-08")
        r = self.ins.overview(self.conn, TODAY, month="2026-08")
        self.assertEqual(r["month"], "2026-08")
        self.assertAlmostEqual(r["income"], 3000.00, places=2)
        want = {b: fx.spend(A, frm, to, basket=b)[0] for b in ("regular", "unexpected", "everyday", "savings")}
        self.assertEqual(want["savings"], 200.00)
        self.assertEqual(want["unexpected"], 0)
        for b, v in want.items():
            self.assertAlmostEqual(r["baskets"][b], v, places=2, msg=b)
        r1 = want["regular"] + want["unexpected"] + want["everyday"]
        self.assertTrue(spent_and_surplus_ok(r["income"], r["spent"], r["surplus"], r1, want["savings"]),
                        "spent=%s surplus=%s (expected spent %s excl. savings)" % (r["spent"], r["surplus"], r1))
        self.assertTraceable(r)

    def test_june_has_the_unexpected_appliance(self):
        r = self.ins.overview(self.conn, TODAY, month="2026-06")
        self.assertAlmostEqual(r["baskets"]["unexpected"], 600.00, places=2)

    def test_baskets_sum_equals_all_outflows(self):
        for ym in ("2026-08", "2026-06", "2025-03"):
            frm, to = fx.month_bounds(ym)
            r = self.ins.overview(self.conn, TODAY, month=ym)
            total_out, _ = fx.spend(A, frm, to)
            got = sum(r["baskets"][b] for b in ("regular", "unexpected", "everyday", "savings"))
            self.assertAlmostEqual(got, total_out, places=2, msg=ym)

    def test_shapes(self):
        r = self.ins.overview(self.conn, TODAY, month="2026-08")
        self.assertIsInstance(r["top_labels"], list)
        self.assertIsInstance(r["vs_average"], dict)
        json.dumps(r)

    def test_basket_evidence_reproduces_the_basket_totals(self):
        r = self.ins.overview(self.conn, TODAY, month="2026-08")
        checked = 0
        for ev in r["evidence"]:
            res = self.run_evidence(ev)
            self.assertIn("total", res)
            only_basket = ev.get("basket") and not (ev.get("label") or ev.get("context") or ev.get("type"))
            if only_basket and ev["basket"] in r["baskets"]:
                self.assertAlmostEqual(abs(res["total"]), r["baskets"][ev["basket"]], places=2, msg=ev["basket"])
                checked += 1
        self.assertGreaterEqual(checked, 1, "overview evidence must let the user open at least one basket")


class BasketsTests(InsightCase):
    def test_three_baskets_with_rules_and_evidence(self):
        frm, to = fx.month_bounds("2026-08")
        r = self.ins.baskets(self.conn, TODAY, period="last_month")
        by = {b["key"]: b for b in r["baskets"]}
        for key in ("regular", "unexpected", "everyday"):
            self.assertIn(key, by)
            self.assertAlmostEqual(by[key]["total"], fx.spend(A, frm, to, basket=key)[0], places=2, msg=key)
            self.assertTrue(by[key]["name"])
            self.assertTrue(by[key]["evidence"], key)       # one filter object or a list of them
            self.assertLessEqual(sum(t["total"] for t in by[key]["top"]), by[key]["total"] + 0.011)
        if "savings" in by:
            self.assertAlmostEqual(by["savings"]["total"], 200.00, places=2)
        self.assertEqual(by["regular"]["top"][0]["label"], "Housing")
        self.assertAlmostEqual(by["regular"]["top"][0]["total"], 900.00, places=2)
        self.assertIsInstance(r["rules"], str)
        self.assertGreater(len(r["rules"]), 40)
        self.assertTrue(r["explain"])

    def test_shares_are_proportional_to_totals(self):
        r = self.ins.baskets(self.conn, TODAY, period="last_month")
        core = [b for b in r["baskets"] if b["key"] in ("regular", "everyday", "unexpected", "savings")]
        for a in core:
            self.assertGreaterEqual(a["share"], 0)
        ordered_by_total = [b["key"] for b in sorted(core, key=lambda b: -b["total"])]
        ordered_by_share = [b["key"] for b in sorted(core, key=lambda b: -b["share"])]
        self.assertEqual(ordered_by_share[:2], ordered_by_total[:2])
        unit = max(b["share"] for b in core)
        self.assertTrue(unit <= 1.0001 or unit <= 100.0001, "share is a fraction or a percentage")
        total_share = sum(b["share"] for b in r["baskets"] if b["key"] in ("regular", "unexpected", "everyday", "savings", "transfer"))
        self.assertTrue(abs(total_share - 1) < 0.02 or abs(total_share - 100) < 2, total_share)

    def test_every_basket_opens_to_exactly_its_transactions(self):
        r = self.ins.baskets(self.conn, TODAY, period="last_month")
        for b in r["baskets"]:
            if b["key"] not in ("regular", "unexpected", "everyday", "savings"):
                continue
            evs = b["evidence"] if isinstance(b["evidence"], list) else [b["evidence"]]
            hits = [self.run_evidence(ev) for ev in evs]
            self.assertTrue(any(abs(abs(h["total"]) - b["total"]) <= 0.01 for h in hits),
                            "basket %s total %s not reproduced by %r" % (b["key"], b["total"], [h["total"] for h in hits]))


class SafeToSpendTests(InsightCase):
    def test_identity_and_balance_for_a_comfortable_customer(self):
        r = self.ins.safe_to_spend(self.conn, TODAY)
        self.assertAlmostEqual(r["balance"], fx.balance_at(A), places=2)
        self.assertEqual(r["next_payday"], "2026-10-15")
        self.assertIn(r["days_left"], (21, 22))
        self.assertGreaterEqual(r["bills_total"], 0)
        self.assertGreaterEqual(r["unexpected_buffer"], 0)
        self.assertGreaterEqual(r["planned_savings"], 0)
        self.assertAlmostEqual(r["safe_total"],
                               r["balance"] - r["bills_total"] - r["unexpected_buffer"] - r["planned_savings"], delta=0.02)
        self.assertAlmostEqual(r["per_day"], r["safe_total"] / r["days_left"], delta=0.01)
        self.assertAlmostEqual(r["per_week"], r["per_day"] * 7, delta=0.1)
        self.assertEqual(r["status"], "ok")
        self.assertTraceable(r)

    def test_upcoming_bills_include_the_rent_before_payday(self):
        r = self.ins.safe_to_spend(self.conn, TODAY)
        self.assertAlmostEqual(sum(b["expected"] for b in r["upcoming_bills"]), r["bills_total"], delta=0.02)
        housing = [b for b in r["upcoming_bills"] if "housing" in b["label"].lower()]
        self.assertTrue(housing, "the 900 EUR rent due on 2 October is before the 15 October payday")
        self.assertAlmostEqual(sum(b["expected"] for b in housing), 900.00, delta=0.01)
        for b in r["upcoming_bills"]:
            self.assertTrue(TODAY <= b["due"] <= r["next_payday"], b)

    def test_customer_below_zero_is_over(self):
        conn = self.db.sandbox(fx.D_CID, TODAY)
        r = self.ins.safe_to_spend(conn, TODAY)
        self.assertLess(fx.balance_at(fx.D_CID), 0)
        self.assertAlmostEqual(r["balance"], fx.balance_at(fx.D_CID), places=2)
        self.assertLess(r["safe_total"], 0)
        self.assertEqual(r["status"], "over")
        self.assertEqual(r["next_payday"], "2026-09-25")
        self.assertAlmostEqual(r["safe_total"],
                               r["balance"] - r["bills_total"] - r["unexpected_buffer"] - r["planned_savings"], delta=0.02)


class WhatIfTests(InsightCase):
    def test_twenty_percent_off_restaurants_is_a_fifth_of_the_baseline(self):
        r = self.ins.what_if(self.conn, TODAY, [{"target": "Restaurant", "pct": 20}], months=12)
        self.assertAlmostEqual(r["baseline_monthly"], 48.00, delta=0.01)        # 16.00 lunch + 32.00 dinner every month
        self.assertAlmostEqual(r["saved_monthly"], 0.2 * r["baseline_monthly"], delta=0.01)
        self.assertAlmostEqual(r["saved_monthly"], 9.60, delta=0.01)
        self.assertAlmostEqual(r["new_monthly"], r["baseline_monthly"] - r["saved_monthly"], delta=0.01)
        self.assertEqual(r["months"], 12)
        self.assertAlmostEqual(r["saved_total"], r["saved_monthly"] * 12, delta=0.12)
        self.assertEqual(len(r["lines"]), 1)
        line = r["lines"][0]
        self.assertEqual(line["target"], "Restaurant")
        self.assertAlmostEqual(line["saved"], line["baseline"] * 0.2, delta=0.01)
        self.assertTraceable(r)

    def test_night_out_and_basket_targets(self):
        r = self.ins.what_if(self.conn, TODAY, [{"target": "night_out", "pct": 50}], months=6)
        self.assertAlmostEqual(r["lines"][0]["baseline"], 63.50, delta=0.01)
        self.assertAlmostEqual(r["saved_monthly"], 31.75, delta=0.01)
        self.assertEqual(r["months"], 6)
        self.assertAlmostEqual(r["saved_total"], 31.75 * 6, delta=0.1)
        r = self.ins.what_if(self.conn, TODAY, [{"target": "everyday", "pct": 10}])
        self.assertAlmostEqual(r["lines"][0]["baseline"], 205.40, delta=0.01)
        self.assertAlmostEqual(r["saved_monthly"], 20.54, delta=0.01)

    def test_several_changes_add_up(self):
        r = self.ins.what_if(self.conn, TODAY, [{"target": "Restaurant", "pct": 50}, {"target": "Taxi", "pct": 10}], months=12)
        self.assertEqual(len(r["lines"]), 2)
        self.assertAlmostEqual(r["saved_monthly"], 24.00 + 6.21, delta=0.02)
        self.assertAlmostEqual(sum(l["saved"] for l in r["lines"]), r["saved_monthly"], delta=0.02)
        self.assertAlmostEqual(r["new_monthly"], r["baseline_monthly"] - r["saved_monthly"], delta=0.02)

    def test_zero_and_full_cuts(self):
        r = self.ins.what_if(self.conn, TODAY, [{"target": "Taxi", "pct": 0}])
        self.assertEqual(r["saved_monthly"], 0)
        r = self.ins.what_if(self.conn, TODAY, [{"target": "Taxi", "pct": 100}])
        self.assertAlmostEqual(r["saved_monthly"], 62.10, delta=0.01)
        self.assertAlmostEqual(r["lines"][0]["new"], 0, delta=0.01)


class SpenderTypeAndSaveMoreTests(InsightCase):
    def test_spender_type_shape(self):
        r = self.ins.spender_type(self.conn, TODAY)
        for key in ("type", "title", "summary"):
            self.assertTrue(str(r[key]).strip(), key)
        self.assertIsInstance(r["traits"], list)
        self.assertTrue(r["traits"])
        for t in r["traits"]:
            self.assertTrue({"name", "value", "note"} <= set(t))
        self.assertIsInstance(r["shares"], dict)
        for v in r["shares"].values():
            self.assertIsInstance(v, (int, float))
            self.assertGreaterEqual(v, 0)
        self.assertTraceable(r)
        json.dumps(r)

    def test_save_more_ideas_are_real_and_bounded(self):
        r = self.ins.save_more(self.conn, TODAY)
        self.assertTrue(r["ideas"])
        monthly_target = {"Restaurant": 48.00, "Taxi": 62.10, "night_out": 63.50, "Bar": 24.00, "Fast food": 21.40}
        for idea in r["ideas"]:
            self.assertTrue(idea["title"])
            self.assertGreater(idea["saved_monthly"], 0)
            if idea["target"] in monthly_target:
                self.assertLessEqual(idea["saved_monthly"], monthly_target[idea["target"]] + 0.01, idea)
        months = fx.month_list(A)
        surplus_r1 = [inc - sp for _, inc, sp, _ in months]
        surplus_r2 = [inc - sp - sv for _, inc, sp, sv in months]
        v = r["surplus_avg"]
        self.assertTrue(min(surplus_r1) - 0.01 <= v <= max(surplus_r1) + 0.01 or
                        min(surplus_r2) - 0.01 <= v <= max(surplus_r2) + 0.01,
                        "surplus_avg %s is outside the monthly surpluses seen in the data" % v)
        self.assertTraceable(r)


class MortgageTests(InsightCase):
    def test_numbers_follow_the_published_rule(self):
        r = self.ins.mortgage(self.conn, TODAY)
        self.assertAlmostEqual(r["monthly_income"], 3000.00, delta=0.5)
        self.assertAlmostEqual(r["max_loan"], 3000.00 / 0.01841, delta=1.0)
        self.assertAlmostEqual(r["max_price_with_15pct_equity"], (3000.00 / 0.01841) / 0.85, delta=2.0)
        self.assertGreater(r["equity_needed"], 0)
        self.assertIsNone(r["check"])
        self.assertIsInstance(r["rule"], str)
        self.assertIn("0.01841", r["rule"])
        self.assertTraceable(r)

    def test_disclaimer_is_not_a_promise(self):
        r = self.ins.mortgage(self.conn, TODAY)
        low = r["disclaimer"].lower()
        self.assertTrue(low.strip())
        self.assertTrue(any(w in low for w in ("not a", "no promise", "not an", "does not", "cannot", "guarantee", "decision")), low)
        self.assertNotRegex(low, r"you will (be approved|get)")

    def test_check_for_a_price_and_equity(self):
        r = self.ins.mortgage(self.conn, TODAY, price=200000, equity=40000)["check"]
        self.assertAlmostEqual(r["price"], 200000, delta=0.01)
        self.assertAlmostEqual(r["loan"], 160000, delta=0.01)
        self.assertTrue(abs(r["ltv"] - 0.8) < 0.001 or abs(r["ltv"] - 80) < 0.1, r["ltv"])
        self.assertAlmostEqual(r["required_income"], 160000 * 0.01841, delta=0.05)
        self.assertTrue(r["income_ok"])       # needs 2,945.60 and earns 3,000
        self.assertTrue(r["equity_ok"])       # 20 percent, above the 15 percent applicants put in

    def test_check_fails_when_income_and_equity_are_too_low(self):
        r = self.ins.mortgage(self.conn, TODAY, price=300000, equity=20000)["check"]
        self.assertAlmostEqual(r["loan"], 280000, delta=0.01)
        self.assertAlmostEqual(r["required_income"], 280000 * 0.01841, delta=0.05)
        self.assertFalse(r["income_ok"])
        self.assertFalse(r["equity_ok"])


class QuizTests(InsightCase):
    PERIOD = ("2026-09-21", "2026-09-24")

    def expected(self, q):
        frm, to = fx.pfrom(q["period"])
        key = q["label_or_context"]
        low = key.lower().replace("_", " ")
        if low == "night out":
            return fx.spend(A, frm, to, context="night_out")[0]
        if low in ("dining out", "eating out"):
            return fx.spend(A, frm, to, labels=("Restaurant", "Fast food", "Bar"))[0]
        known = {v for v in fx.SPEC}
        self.assertIn(key, known, "quiz asks about %r, which is not a label the fixture knows" % key)
        return fx.spend(A, frm, to, labels=key)[0]

    def test_quiz_question_shape_and_period(self):
        q = self.ins.quiz(self.conn, TODAY, seed=1)
        for key in ("quiz_id", "label_or_context", "question", "period", "min", "max", "step"):
            self.assertIn(key, q)
        self.assertLess(q["min"], q["max"])
        self.assertGreater(q["step"], 0)
        self.assertEqual(fx.pfrom(q["period"]), self.PERIOD, "M9: the quiz is about this week")
        self.assertTrue(q["question"].strip())

    def test_quiz_is_reproducible_for_a_seed(self):
        a = self.ins.quiz(self.conn, TODAY, seed=7)
        b = self.ins.quiz(self.conn, TODAY, seed=7)
        self.assertEqual(a["label_or_context"], b["label_or_context"])
        self.assertEqual(a["quiz_id"], b["quiz_id"])

    def test_answer_reveals_the_true_figure(self):
        seen = set()
        for seed in range(12):
            q = self.ins.quiz(self.conn, TODAY, seed=seed)
            seen.add(q["label_or_context"])
            with self.subTest(seed=seed, what=q["label_or_context"]):
                a = self.ins.quiz_answer(self.conn, TODAY, q["quiz_id"], 100.0)
                self.assertAlmostEqual(a["actual"], self.expected(q), places=2)
                self.assertAlmostEqual(a["guess"], 100.0, places=2)
                self.assertAlmostEqual(abs(a["diff"]), abs(100.0 - a["actual"]), delta=0.011)
                self.assertTrue(str(a["verdict"]).strip())
                self.assertTrue(str(a["tip"]).strip())
                self.assertTrue(a["evidence"])
        self.assertGreaterEqual(len(seen), 2, "different seeds should ask about different things")

    def test_evidence_for_the_answer_opens_the_same_total(self):
        q = self.ins.quiz(self.conn, TODAY, seed=3)
        a = self.ins.quiz_answer(self.conn, TODAY, q["quiz_id"], 10.0)
        hits = [self.run_evidence(ev) for ev in a["evidence"]]
        self.assertTrue(any(abs(abs(h["total"]) - a["actual"]) <= 0.01 for h in hits))

    def test_bad_quiz_id_is_rejected(self):
        with self.assertRaises((ValueError, KeyError)):
            self.ins.quiz_answer(self.conn, TODAY, "no-such-quiz", 5.0)


class CheckinTests(InsightCase):
    def test_monthly_checkin_covers_last_month(self):
        r = self.ins.checkin(self.conn, TODAY, frequency="monthly")
        self.assertEqual(fx.pfrom(r["period"]), fx.month_bounds("2026-08"))
        frm, to = fx.month_bounds("2026-08")
        r1 = fx.spend(A, frm, to, baskets=("regular", "unexpected", "everyday"))[0]
        self.assertAlmostEqual(r["income"], 3000.00, places=2)
        self.assertTrue(spent_and_surplus_ok(r["income"], r["spent"], r["surplus"], r1, 200.00),
                        "spent=%s surplus=%s" % (r["spent"], r["surplus"]))
        self.assertTrue(r["headline"].strip())
        self.assertIsInstance(r["highlights"], list)
        self.assertTrue(all(isinstance(h, str) for h in r["highlights"]))
        self.assertTrue(r["evidence"])

    def test_weekly_checkin_figures_match_its_own_period(self):
        r = self.ins.checkin(self.conn, TODAY, frequency="weekly")
        frm, to = fx.pfrom(r["period"])
        self.assertLess(frm, to)
        self.assertLessEqual(to, TODAY)
        r1 = fx.spend(A, frm, to, baskets=("regular", "unexpected", "everyday"))[0]
        sv = fx.spend(A, frm, to, basket="savings")[0]
        self.assertAlmostEqual(r["income"], fx.income(A, frm, to), places=2)
        self.assertTrue(spent_and_surplus_ok(r["income"], r["spent"], r["surplus"], r1, sv),
                        "spent=%s surplus=%s expected %s" % (r["spent"], r["surplus"], r1))

    def test_suggestions_are_well_formed_and_offer_the_surplus(self):
        r = self.ins.checkin(self.conn, TODAY, frequency="monthly")
        self.assertTrue(r["suggestions"], "a customer with a clear surplus gets a suggestion")
        ids = [s["id"] for s in r["suggestions"]]
        self.assertEqual(len(ids), len(set(ids)))
        for s in r["suggestions"]:
            for key in ("id", "kind", "title", "detail", "amount", "action_label"):
                self.assertIn(key, s)
            self.assertIsInstance(s["id"], str)
            self.assertTrue(s["title"].strip() and s["action_label"].strip())
            if isinstance(s["amount"], (int, float)):
                self.assertGreaterEqual(s["amount"], 0)
                self.assertLessEqual(s["amount"], r["surplus"] + 1.0, "amounts may be rounded to whole euros, not inflated")
        self.assertTrue(any(isinstance(s["amount"], (int, float)) and s["amount"] > 0 for s in r["suggestions"]))
        for s in r["suggestions"]:
            for bad in ("transfer completed", "moved", "has been sent"):
                self.assertNotIn(bad, (s["title"] + " " + s["detail"]).lower())


class BenchmarkInsightTests(InsightCase):
    PROFILE = {"age_band": "25-34", "area": "00"}

    def bm(self, profile=None, lookup=None):
        return self.ins.benchmarks(self.conn, TODAY, profile or self.PROFILE, lookup or self.db.bench)

    def test_small_group_is_widened_to_the_age_band(self):
        r = self.bm()                                  # 25-34 in area 00 has only 4 customers
        self.assertEqual(r["group"]["key"], "age:25-34")
        self.assertGreaterEqual(r["group"]["n"], 20)
        self.assertTrue(str(r["group"]["description"]).strip())
        blob = json.dumps(r)
        self.assertNotIn(fx.A_POSTAL, blob)
        self.assertNotIn("CUST", blob)

    def test_group_of_exactly_twenty_is_allowed(self):
        r = self.bm({"age_band": "35-44", "area": "33"})
        self.assertEqual(r["group"]["key"], "age:35-44|area:33")
        self.assertEqual(r["group"]["n"], 20)

    def test_widens_all_the_way_to_everyone(self):
        for profile in ({"age_band": "45-54", "area": "40"}, {"age_band": "65+", "area": "70"},
                        {"age_band": "25-34", "area": "20"}, {"age_band": "99", "area": "zz"}):
            r = self.bm(profile)
            if profile["age_band"] == "25-34":
                self.assertEqual(r["group"]["key"], "age:25-34", profile)      # 18 in area 20, 22 in the band
            else:
                self.assertEqual(r["group"]["key"], "all", profile)
            self.assertGreaterEqual(r["group"]["n"], 20)

    def test_keys_are_tried_narrow_to_wide(self):
        calls = []

        def spy(keys, metric):
            calls.append(list(keys))
            return None

        r = self.bm(lookup=spy)
        self.assertTrue(calls)
        for keys in calls:
            self.assertEqual(keys, ["age:25-34|area:00", "age:25-34", "all"])
        grp = r.get("group")
        self.assertTrue(grp is None or grp.get("key") is None or grp.get("n", 0) == 0, "no group of 20 -> no benchmark group: %r" % grp)
        for row in r.get("rows", []):
            for stat in ("median", "p25", "p75"):
                self.assertIsNone(row.get(stat), "no peer statistics may be shown without a group of 20")

    def test_rows_compare_you_with_the_group_by_statistics_only(self):
        r = self.bm()
        by = {row["metric"]: row for row in r["rows"]}
        self.assertIn("income", by)
        row = by["income"]
        self.assertAlmostEqual(row["you"], 3000.00, delta=0.5)
        want = statistics.median(fx.salary_of(c) for c in fx.group_cids("age:25-34"))
        self.assertAlmostEqual(row["median"], want, delta=0.01)
        self.assertLessEqual(row["p25"], row["median"])
        self.assertLessEqual(row["median"], row["p75"])
        self.assertTrue(row["name"])
        self.assertTrue(r["explain"])
        for row in r["rows"]:
            self.assertEqual(set(row) & {"cid", "customer", "customers"}, set())


class InvestAndGoalTests(InsightCase):
    PRODUCTS = ("bitcoin", "ethereum", "nokia", "tesla", "nordea", "ishares", "vanguard", "s&p 500",
                "msci", "amundi", "nvidia", "s-pankki fund", "op-rahasto")

    def test_invest_education_is_general_only(self):
        r = self.ins.invest_education(self.conn, TODAY)
        self.assertIsInstance(r["buffer_months"], (int, float))
        self.assertGreaterEqual(r["buffer_months"], 0)
        self.assertIsInstance(r["buffer_ok"], bool)
        self.assertIsInstance(r["surplus_avg"], (int, float))
        self.assertTrue(r["points"])
        text = " ".join(r["points"]).lower() + " " + r["disclaimer"].lower()
        for word in self.PRODUCTS:
            self.assertNotIn(word, text)
        self.assertIn("not", r["disclaimer"].lower())
        self.assertRegex(r["disclaimer"].lower(), r"advice|recommend|guidance|educat")

    def test_goal_with_a_given_monthly_amount(self):
        r = self.ins.goal(self.conn, TODAY, 10000, monthly=500)
        self.assertEqual(r["months"], 20)
        self.assertAlmostEqual(r["monthly"], 500, places=2)
        self.assertTrue(str(r["date"]).strip())
        self.assertTrue(r["explain"])

    def test_goal_without_a_monthly_amount_uses_the_surplus(self):
        r = self.ins.goal(self.conn, TODAY, 12000)
        self.assertGreater(r["monthly"], 0)
        self.assertLess(abs(r["months"] - 12000 / r["monthly"]), 1.01)


class EveryResultIsSerialisableAndExplained(InsightCase):
    def test_json_round_trip_and_two_decimals(self):
        results = [
            self.ins.spend(self.conn, TODAY, period="last_month", label="Taxi"),
            self.ins.overview(self.conn, TODAY, month="2026-08"),
            self.ins.baskets(self.conn, TODAY, period="last_month"),
            self.ins.safe_to_spend(self.conn, TODAY),
            self.ins.what_if(self.conn, TODAY, [{"target": "Taxi", "pct": 30}]),
            self.ins.spender_type(self.conn, TODAY),
            self.ins.save_more(self.conn, TODAY),
            self.ins.mortgage(self.conn, TODAY),
            self.ins.checkin(self.conn, TODAY),
            self.ins.invest_education(self.conn, TODAY),
        ]
        for r in results:
            json.dumps(r)
        self.assertEqual(results[0]["total"], round(results[0]["total"], 2))

    def test_evidence_and_explain_on_every_result_that_promises_them(self):
        for name, r in (
            ("spend", self.ins.spend(self.conn, TODAY, period="last_month", label="Taxi")),
            ("overview", self.ins.overview(self.conn, TODAY, month="2026-08")),
            ("baskets", self.ins.baskets(self.conn, TODAY, period="last_month")),
            ("safe_to_spend", self.ins.safe_to_spend(self.conn, TODAY)),
            ("what_if", self.ins.what_if(self.conn, TODAY, [{"target": "Taxi", "pct": 30}])),
            ("spender_type", self.ins.spender_type(self.conn, TODAY)),
            ("save_more", self.ins.save_more(self.conn, TODAY)),
            ("mortgage", self.ins.mortgage(self.conn, TODAY)),
        ):
            with self.subTest(name):
                self.assertTrue(str(r.get("explain", "")).strip(), "explain missing")
                if name != "baskets":
                    self.assertTraceable(r)

    def test_every_evidence_filter_opens_without_error_and_returns_rows_when_it_supports_a_number(self):
        for r in (self.ins.spend(self.conn, TODAY, period="last_month", label="Taxi"),
                  self.ins.overview(self.conn, TODAY, month="2026-08"),
                  self.ins.safe_to_spend(self.conn, TODAY),
                  self.ins.what_if(self.conn, TODAY, [{"target": "Restaurant", "pct": 20}]),
                  self.ins.save_more(self.conn, TODAY)):
            for ev in r["evidence"]:
                res = self.run_evidence(ev)
                self.assertIn("count", res)
                self.assertIn("rows", res)


if __name__ == "__main__":
    unittest.main()
