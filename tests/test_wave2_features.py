"""Wave 2 pure features (app/features.py), learning in the Python layer, insights period additions, area.

Acceptance: W1 to W11; plan: SR-10, SR-11, SR-22/23 (no merchant id, no postal code in results).
Expected values come from the invented rows (tests/fixture.py and tests/fixture_wave2.py), never from app code.
"""
import datetime as dt
import json
import re
import unittest
from pathlib import Path

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_wave2 as f2

TODAY = fx.TODAY
A = fx.A_CID
D = fx.D_CID
MERCHANT_ID = re.compile(r"\bMX\d{3,}\b|MRC-")
SCOLD = re.compile(r"\b(fail|failed|failing|bad|disappoint\w*)\b|should have|you should(n't)? have", re.I)


def dump(obj):
    return json.dumps(obj, default=str)


def all_text(obj):
    """Every string inside a JSON-like object, joined."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(all_text(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(all_text(v) for v in obj)
    return ""


class FeatureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.features as features
        import app.insights as ins
        import app.db as db
        cls.features, cls.ins, cls.db = features, ins, db

    def assertExplained(self, r):
        self.assertIsInstance(r.get("explain"), str)
        self.assertTrue(r["explain"].strip())
        self.assertIsInstance(r.get("evidence"), list)
        json.dumps(r)                                             # serialisable


# ---------------------------------------------------------------------------------------------
class AffordTests(FeatureCase):
    def setUp(self):
        self.conn = fx.sandbox(A)
        self.base = self.features.afford(self.conn, TODAY, "jacket", 300.0)

    def test_W1_safe_total_follows_the_safe_to_spend_identity(self):
        s = self.ins.safe_to_spend(self.conn, TODAY)
        self.assertAlmostEqual(s["balance"], fx.balance_at(A), places=2)
        want = s["balance"] - s["bills_total"] - s["unexpected_buffer"] - s["planned_savings"]
        self.assertAlmostEqual(self.base["safe_total"], want, delta=0.02)
        self.assertAlmostEqual(self.base["safe_total"], s["safe_total"], delta=0.02)
        self.assertEqual(self.base["next_payday"], "2026-10-15")
        self.assertIn(self.base["days_left"], (21, 22))
        self.assertExplained(self.base)

    def test_W1_after_is_safe_total_minus_price(self):
        for price in (1.0, 300.0, 5000.0, 99999.0):
            r = self.features.afford(self.conn, TODAY, "thing", price)
            self.assertAlmostEqual(r["after"], r["safe_total"] - price, delta=0.01)
            self.assertAlmostEqual(r["price"], price, places=2)

    def test_W1_verdict_boundaries(self):
        s, days = self.base["safe_total"], self.base["days_left"]
        self.assertGreater(s - 30 * days, 0, "fixture premise: A can afford a lot")

        def verdict(price):
            return self.features.afford(self.conn, TODAY, "thing", round(price, 2))["verdict"]

        self.assertEqual(verdict(s + 0.01), "no")
        self.assertEqual(verdict(s), "tight")                      # after = 0: not negative, under 10 a day
        self.assertEqual(verdict(s - 5 * days), "tight")
        self.assertEqual(verdict(s - 10 * days + 0.05), "tight")   # just under 10 EUR a day
        self.assertEqual(verdict(s - 10 * days), "yes")            # exactly 10 a day is not under 10
        self.assertEqual(verdict(s - 30 * days), "yes")
        self.assertEqual(verdict(10.0), "yes")
        for price in (10.0, s - 5 * days, s + 1):
            r = self.features.afford(self.conn, TODAY, "thing", round(price, 2))
            self.assertTrue(r["verdict_text"].strip())
            self.assertLessEqual(len(r["alternatives"]), 2)
            for a in r["alternatives"]:
                self.assertIsInstance(a, str)

    def test_W1_share_of_safe_and_typical_month_share(self):
        s = self.base["safe_total"]
        price = 300.0
        self.assertTrue(f2.share_matches(self.base["share_of_safe"], price / s), self.base["share_of_safe"])
        months = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
        avg = sum(fx.spend(A, *fx.month_bounds(m), basket="everyday")[0] for m in months) / 6.0
        self.assertTrue(f2.share_matches(self.base["typical_month_share"], price / avg, tol=0.01),
                        (self.base["typical_month_share"], price / avg))

    def test_W1_share_of_safe_is_none_when_nothing_is_safe(self):
        conn = fx.sandbox(D)
        r = self.features.afford(conn, TODAY, "coat", 100.0)
        self.assertLessEqual(r["safe_total"], 0)
        self.assertIsNone(r["share_of_safe"])
        self.assertEqual(r["verdict"], "no")

    def test_W1_no_goal_gives_no_goal_effect(self):
        self.assertIsNone(self.base["goal_effect"])

    def test_W1_goal_effect_uses_the_saving_target(self):
        goal = {"name": "flat", "target": 20000.0, "saved": 5000.0}
        for price, target in ((300.0, 300.0), (900.0, 450.0), (150.0, 1000.0)):
            r = self.features.afford(self.conn, TODAY, "thing", price, goal=goal, monthly_saving_target=target)
            ge = r["goal_effect"]
            self.assertIsNotNone(ge)
            self.assertAlmostEqual(ge["monthly_saving"], target, places=2)
            self.assertAlmostEqual(ge["delay_days"], price / target * 30.44, delta=1.0)
            self.assertIn("flat", ge["delay_text"].lower())
            self.assertExplained(r)

    def test_W1_goal_effect_without_target_uses_income_minus_spending(self):
        goal = {"name": "flat", "target": 20000.0, "saved": 5000.0}
        r = self.features.afford(self.conn, TODAY, "thing", 600.0, goal=goal, monthly_saving_target=0.0)
        ge = r["goal_effect"]
        months = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
        rows = {m[0]: m for m in fx.month_list(A)}
        inc = sum(rows[m][1] for m in months) / 6.0
        spent = sum(rows[m][2] for m in months) / 6.0
        savings = sum(rows[m][3] for m in months) / 6.0
        # whether the monthly 200 EUR deposit counts as spending is a reading; accept either.
        candidates = (inc - spent, inc - spent - savings)
        self.assertTrue(any(abs(ge["monthly_saving"] - c) <= 1.0 for c in candidates), (ge, candidates))
        self.assertAlmostEqual(ge["delay_days"], 600.0 / ge["monthly_saving"] * 30.44, delta=1.0)

    def test_W1_no_regular_saving_gives_no_delay_number(self):
        conn = fx.sandbox(D)
        months = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
        rows = {m[0]: m for m in fx.month_list(D)}
        net = sum(rows[m][1] - rows[m][2] for m in months) / 6.0
        self.assertLessEqual(net, 0, "fixture premise: D saves nothing")
        goal = {"name": "flat", "target": 20000.0, "saved": 100.0}
        r = self.features.afford(conn, TODAY, "coat", 100.0, goal=goal, monthly_saving_target=0.0)
        self.assertIsNone(r["goal_effect"]["delay_days"])
        self.assertTrue(r["goal_effect"]["delay_text"].strip())


# ---------------------------------------------------------------------------------------------
class LeaksTests(FeatureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = f2.leak_rows()
        cls.conn = f2.make_conn(cls.rows)

    def setUp(self):
        self.r = self.features.leaks(self.conn, TODAY, months=3)
        self.frm, self.to = fx.pfrom(self.r["period"])

    def test_shape_and_serialisable(self):
        self.assertExplained(self.r)
        for k in ("small", "by_weekday", "by_hour", "peak", "payday_week", "subscriptions", "headline"):
            self.assertIn(k, self.r)
        span = f2.days_between(self.frm, self.to)
        self.assertTrue(85 <= span <= 125, (self.frm, self.to))
        self.assertLessEqual(self.to, TODAY)

    def test_W3_small_purchases_under_ten(self):
        want = [r for r in f2.outflows(self.rows, self.frm, self.to) if -r["amount"] < 10]
        self.assertGreater(len(want), 0)
        s = self.r["small"]
        self.assertEqual(s["threshold"], 10)
        self.assertEqual(s["count"], len(want))
        self.assertAlmostEqual(s["total"], round(-sum(r["amount"] for r in want), 2), places=2)
        n_months = len({r["d"][:7] for r in f2.outflows(self.rows, self.frm, self.to)})
        self.assertGreater(s["per_month"], 0)
        self.assertGreaterEqual(n_months, 1)
        self.assertIn("Fast food", all_text(s["top_labels"]) + dump(s["top_labels"]))

    def test_W3_exactly_ten_euro_is_not_small(self):
        tens = [r for r in f2.outflows(self.rows, self.frm, self.to) if -r["amount"] == 10.0]
        self.assertTrue(tens)
        want = [r for r in f2.outflows(self.rows, self.frm, self.to) if -r["amount"] < 10]
        self.assertNotIn(10.0, [-r["amount"] for r in want])
        self.assertEqual(self.r["small"]["count"], len(want))

    def test_W3_weekday_and_hour_totals_sum_to_everyday_spending(self):
        everyday = f2.outflows(self.rows, self.frm, self.to, basket="everyday")
        total = round(-sum(r["amount"] for r in everyday), 2)
        self.assertEqual(len(self.r["by_weekday"]), 7)
        self.assertEqual([x["day"] for x in self.r["by_weekday"]], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        self.assertEqual(len(self.r["by_hour"]), 24)
        self.assertEqual([x["hour"] for x in self.r["by_hour"]], list(range(24)))
        self.assertAlmostEqual(sum(x["total"] for x in self.r["by_weekday"]), total, delta=0.02)
        self.assertAlmostEqual(sum(x["total"] for x in self.r["by_hour"]), total, delta=0.02)
        self.assertEqual(sum(x["count"] for x in self.r["by_weekday"]), len(everyday))
        for i, x in enumerate(self.r["by_weekday"]):
            want = round(-sum(r["amount"] for r in everyday
                              if dt.date.fromisoformat(r["d"]).weekday() == i), 2)
            self.assertAlmostEqual(x["total"], want, delta=0.01, msg=x["day"])
        for x in self.r["by_hour"]:
            want = round(-sum(r["amount"] for r in everyday if int(r["ts"][11:13]) == x["hour"]), 2)
            self.assertAlmostEqual(x["total"], want, delta=0.01, msg=x["hour"])

    def test_W3_payday_week_share_zero_to_seven_days_inclusive(self):
        everyday = f2.outflows(self.rows, self.frm, self.to, basket="everyday")
        salaries = [r["d"] for r in self.rows if r["type"] == "salary"]
        inside = [r for r in everyday if any(0 <= f2.days_between(s, r["d"]) <= 7 for s in salaries)]
        total = -sum(r["amount"] for r in everyday)
        got_in = -sum(r["amount"] for r in inside)
        self.assertGreater(got_in, 0)
        # day 22 (7 days after payday) is inside, day 23 is outside: the books on the 22nd count, clothing on the 23rd does not
        self.assertTrue(any(r["d"].endswith("-22") for r in inside))
        self.assertFalse(any(r["d"].endswith("-23") for r in inside))
        pw = self.r["payday_week"]
        self.assertTrue(f2.share_matches(pw["share"], got_in / total), (pw["share"], got_in / total))
        self.assertAlmostEqual(pw["total"], round(got_in, 2), delta=0.02)
        self.assertTrue(pw["text"].strip())

    def test_W3_repeating_charges_found_and_frequent_shops_are_not(self):
        subs = self.r["subscriptions"]
        flat = [s for s in subs if abs(s["amount"] - 12.99) < 0.01]
        self.assertEqual(len(flat), 1, subs)
        self.assertEqual(flat[0]["every"], "month")
        self.assertGreaterEqual(flat[0]["months_seen"], 3)
        self.assertAlmostEqual(flat[0]["yearly"], 12.99 * 12, delta=1.0)
        self.assertTrue(flat[0]["text"].strip())
        self.assertTrue(flat[0]["last_seen"])
        creep = [s for s in subs if 12.99 <= s["amount"] <= 14.99 and s is not flat[0]]
        self.assertEqual(len(creep), 1, subs)
        for s in subs:
            self.assertNotAlmostEqual(s["amount"], 60.0, delta=1.0, msg="grocery shop visited four times a month")
            self.assertNotAlmostEqual(s["amount"], 4.50, delta=0.1, msg="coffee three times a month")
        self.assertEqual(len(subs), 2, subs)

    def test_SR_no_merchant_id_anywhere_and_merchant_ref_is_opaque(self):
        text = dump(self.r)
        self.assertIsNone(MERCHANT_ID.search(text), "merchant id leaked into leaks result")
        ids = {r["merchant"] for r in self.rows if r["merchant"]}
        for s in self.r["subscriptions"]:
            self.assertTrue(s["merchant_ref"])
            self.assertNotIn(s["merchant_ref"], ids)
            self.assertLessEqual(len(s["merchant_ref"]), 24)
            for mid in ids:
                self.assertNotIn(mid, s["merchant_ref"])

    def test_W3_no_repeating_charge_says_so_plainly(self):
        conn = f2.make_conn(f2.base_rows())
        r = self.features.leaks(conn, TODAY, months=3)
        self.assertEqual(r["subscriptions"], [])
        self.assertTrue(r["headline"].strip())
        self.assertExplained(r)

    def test_W3_on_the_known_customer(self):
        conn = fx.sandbox(A)
        r = self.features.leaks(conn, TODAY, months=3)
        frm, to = fx.pfrom(r["period"])
        everyday = fx.spend(A, frm, to, basket="everyday")[0]
        self.assertAlmostEqual(sum(x["total"] for x in r["by_weekday"]), everyday, delta=0.02)
        self.assertAlmostEqual(sum(x["total"] for x in r["by_hour"]), everyday, delta=0.02)
        # small purchases: 9.90 fast food every month (everyday); the 3.10 bus ticket (regular) is a reading
        lo = sum(1 for x in fx.rows_for(A) if x["cents"] < 0 and x["d"] <= TODAY and frm <= x["d"] <= to
                 and x["cents"] > -1000 and x["basket"] == "everyday")
        hi = sum(1 for x in fx.rows_for(A) if x["cents"] < 0 and x["d"] <= TODAY and frm <= x["d"] <= to
                 and x["cents"] > -1000 and x["type"] == "purchase")
        self.assertGreaterEqual(r["small"]["count"], lo)
        self.assertLessEqual(r["small"]["count"], hi)
        for sub in r["subscriptions"]:     # a monthly 49.90 clothing shop is a legitimate repeat; groceries (4 a month) are not
            self.assertNotEqual(sub["label"], "Groceries")
            self.assertNotEqual(sub["label"], "Taxi")
        self.assertIsNone(MERCHANT_ID.search(dump(r)))
        self.assertIsNone(re.search(r"MX\d{5}", dump(r)))


# ---------------------------------------------------------------------------------------------
class AlertsTests(FeatureCase):
    PROFILE = {"age_band": "25-34", "area": "00"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = f2.leak_rows()
        cls.conn = f2.make_conn(cls.rows)

    def kinds(self, r, kind):
        return [a for a in r["alerts"] if a["kind"] == kind]

    def test_W4_sixty_percent_above_own_usual_is_flagged_with_both_numbers(self):
        r = self.features.alerts(self.conn, TODAY)
        self.assertExplained(r)
        own = [a for a in self.kinds(r, "above_own_usual") if "restaurant" in (a["title"] + a["detail"]).lower()]
        self.assertEqual(len(own), 1, r["alerts"])
        text = own[0]["title"] + " " + own[0]["detail"]
        self.assertTrue(fx.text_has_amount(text, 480.0), text)
        self.assertTrue(fx.text_has_amount(text, 300.0), text)
        self.assertIn(own[0]["severity"], ("info", "notice"))
        for k in ("id", "kind", "title", "detail", "amount", "evidence"):
            self.assertIn(k, own[0])

    def test_W4_ten_percent_rise_is_not_flagged(self):
        r = self.features.alerts(self.conn, TODAY)
        for a in self.kinds(r, "above_own_usual"):
            self.assertNotIn("clothing", (a["title"] + a["detail"]).lower())

    def test_W4_price_creep_on_a_repeating_charge(self):
        r = self.features.alerts(self.conn, TODAY)
        creep = self.kinds(r, "price_creep")
        self.assertEqual(len(creep), 1, r["alerts"])
        text = creep[0]["title"] + " " + creep[0]["detail"]
        self.assertTrue(fx.text_has_amount(text, 12.99), text)
        self.assertTrue(fx.text_has_amount(text, 14.99), text)

    def test_W4_peer_alerts_only_with_a_bench_lookup(self):
        r = self.features.alerts(self.conn, TODAY, profile=self.PROFILE)
        self.assertEqual(self.kinds(r, "above_peers"), [])
        calls = []

        def lookup(keys, metric, *a, **k):
            calls.append((tuple(keys), metric))
            if metric.startswith("label:"):
                return {"group_key": keys[-1], "n": 25, "p25": 20.0, "median": 40.0, "p75": 60.0, "mean": 45.0}
            return None

        r = self.features.alerts(self.conn, TODAY, profile=self.PROFILE, bench_lookup=lookup)
        peers = self.kinds(r, "above_peers")
        self.assertGreaterEqual(len(peers), 1, r["alerts"])
        self.assertTrue(any(m.startswith("label:") for _, m in calls))
        for keys, _ in calls:
            self.assertTrue(any(k == "all" for k in keys), "groups are tried down to the whole population")
        for a in peers:
            self.assertTrue(a["title"].strip() and a["detail"].strip())
        json.dumps(r)

    def test_W4_never_more_than_five_alerts(self):
        def lookup(keys, metric, *a, **k):
            if metric.startswith("label:"):
                return {"group_key": keys[-1], "n": 30, "p25": 20.0, "median": 40.0, "p75": 60.0, "mean": 45.0}
            return None

        r = self.features.alerts(self.conn, TODAY, profile=self.PROFILE, bench_lookup=lookup)
        self.assertLessEqual(len(r["alerts"]), 5)
        self.assertGreaterEqual(len(r["alerts"]), 3, [(a["kind"], a["title"]) for a in r["alerts"]])
        ids = [a["id"] for a in r["alerts"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_W4_calm_customer_gets_nothing_odd(self):
        r = self.features.alerts(fx.sandbox(A), TODAY)
        self.assertEqual(self.kinds(r, "above_peers"), [])
        self.assertEqual(self.kinds(r, "price_creep"), [])
        self.assertLessEqual(len(r["alerts"]), 5)
        self.assertIsNone(re.search(r"MX\d{5}|CUST\d", dump(r)))


# ---------------------------------------------------------------------------------------------
class SavingsLeakageTests(FeatureCase):
    def conn_with(self, *withdrawals):
        return f2.make_conn(f2.base_rows() + list(withdrawals))

    def test_W5_two_withdrawals_before_payday_flag(self):
        conn = self.conn_with(f2.withdrawal("2026-07-08", 400), f2.withdrawal("2026-08-10", 300))
        r = self.features.savings_leakage(conn, TODAY)
        self.assertEqual(r["count"], 2)
        self.assertAlmostEqual(r["total"], 700.0, places=2)
        self.assertEqual(r["month_end_count"], 2)
        self.assertTrue(r["flag"])
        self.assertEqual(sorted(w["days_before_payday"] for w in r["withdrawals"]), [5, 7])
        for w in r["withdrawals"]:
            self.assertIn("balance_before", w)
            self.assertGreater(w["balance_before"], 100)
        self.assertTrue(r["text"].strip())
        self.assertExplained(r)

    def test_W5_one_withdrawal_does_not_flag(self):
        r = self.features.savings_leakage(self.conn_with(f2.withdrawal("2026-08-10", 300)), TODAY)
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["month_end_count"], 1)
        self.assertFalse(r["flag"])

    def test_W5_mid_cycle_withdrawals_with_healthy_balance_do_not_count(self):
        r = self.features.savings_leakage(
            self.conn_with(f2.withdrawal("2026-07-26", 300), f2.withdrawal("2026-08-26", 300)), TODAY)
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["month_end_count"], 0)
        self.assertFalse(r["flag"])
        self.assertEqual(sorted(w["days_before_payday"] for w in r["withdrawals"]), [20, 20])

    def test_W5_one_before_payday_one_mid_cycle_does_not_flag(self):
        r = self.features.savings_leakage(
            self.conn_with(f2.withdrawal("2026-07-26", 300), f2.withdrawal("2026-08-10", 300)), TODAY)
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["month_end_count"], 1)
        self.assertFalse(r["flag"])

    def test_W5_low_balance_before_withdrawals_flags(self):
        r = self.features.savings_leakage(
            self.conn_with(f2.withdrawal("2026-07-26", 300, balance_after=350.0),
                           f2.withdrawal("2026-08-26", 300, balance_after=360.0)), TODAY)
        self.assertEqual(r["month_end_count"], 2)
        self.assertTrue(r["flag"])
        for w in r["withdrawals"]:
            self.assertLess(w["balance_before"], 100)

    def test_W5_customer_without_withdrawals(self):
        r = self.features.savings_leakage(fx.sandbox(A), TODAY)
        self.assertEqual((r["count"], r["total"], r["flag"]), (0, 0, False))
        self.assertEqual(r["withdrawals"], [])


# ---------------------------------------------------------------------------------------------
class ChallengeTests(FeatureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = fx.sandbox(A)
        cls.res = cls.features.challenge_options(cls.conn, TODAY)

    # independent oracle -------------------------------------------------------------------
    @staticmethod
    def _rows(opt, frm, to):
        lab = opt.get("label")
        night = opt.get("context") == "night_out" or (lab and lab.lower().replace("_", " ") == "night out")
        out = []
        for r in fx.rows_for(A):
            if r["cents"] >= 0 or r["d"] > TODAY or not (frm <= r["d"] <= to):
                continue
            if night:
                if r["context"] != "night_out":
                    continue
            elif lab and r["label"] != lab:
                continue
            out.append(r)
        return out

    def _figure(self, opt, frm, to):
        kind = opt["kind"]
        if kind == "under_amount":
            return round(-sum(r["cents"] for r in self._rows(opt, frm, to)) / 100.0, 2)
        if kind in ("fewer_times", "none_this_week"):
            return len(self._rows(opt, frm, to))
        if kind == "free_days":
            busy = {r["d"] for r in fx.rows_for(A) if r["cents"] < 0 and r["basket"] == "everyday"
                    and r["d"] <= TODAY and frm <= r["d"] <= to}
            last = min(to, TODAY)
            days = (dt.date.fromisoformat(last) - dt.date.fromisoformat(frm)).days + 1
            return days - len(busy)
        raise AssertionError("unknown kind %r" % kind)

    def _met(self, opt, current):
        if opt["kind"] == "free_days":
            return current >= opt["target"]
        return current <= opt["target"]

    # tests --------------------------------------------------------------------------------
    def test_W6_shape_count_and_period(self):
        opts = self.res["options"]
        self.assertTrue(self.res["explain"].strip())
        self.assertGreaterEqual(len(opts), 1, "A has real habits, so there is something to offer")
        self.assertLessEqual(len(opts), 3)
        mon, sun = "2026-09-21", "2026-09-27"
        for o in opts:
            self.assertEqual(fx.pfrom(o["period"]), (mon, sun))
            self.assertIn(o["kind"], ("under_amount", "fewer_times", "free_days", "none_this_week"))
            self.assertIn(o["difficulty"], ("easy", "medium"))
            for k in ("id", "title", "why", "target", "unit", "baseline", "label", "context", "evidence"):
                self.assertIn(k, o)
        self.assertEqual(len({o["id"] for o in opts}), len(opts))

    def test_W6_every_target_was_met_in_at_least_three_of_the_last_eight_weeks(self):
        for o in self.res["options"]:
            met = 0
            for k in range(1, 9):
                frm, to = fx.week_bounds(TODAY, k)
                if self._met(o, self._figure(o, frm, to)):
                    met += 1
            self.assertGreaterEqual(met, 3, "not easy enough: %r met in %d of 8 weeks" % (o["title"], met))

    def test_W6_no_zero_target_for_a_habit_done_more_than_once_a_week(self):
        for o in self.res["options"]:
            counts = []
            for k in range(1, 9):
                frm, to = fx.week_bounds(TODAY, k)
                counts.append(len(self._rows(o, frm, to)) if o["kind"] != "free_days" else 0)
            usual = sum(counts) / 8.0
            if o["kind"] in ("under_amount", "free_days"):
                self.assertGreater(o["target"], 0, o)
            if o["target"] == 0 or o["kind"] == "none_this_week":
                self.assertLessEqual(usual, 1.0, "zero target only for something done once a week or less: %r" % o)

    def test_W6_ids_are_stable_within_a_week(self):
        again = self.features.challenge_options(self.conn, "2026-09-25")
        self.assertEqual([o["id"] for o in again["options"]], [o["id"] for o in self.res["options"]])

    def test_W6_texts_never_scold(self):
        for o in self.res["options"]:
            self.assertIsNone(SCOLD.search(o["title"] + " " + o["why"]), o)

    def test_W6_progress_matches_the_oracle(self):
        for o in self.res["options"]:
            ch = dict(o, accepted_at="2026-09-21T09:00:00")
            p = self.features.challenge_progress(self.conn, TODAY, ch)
            for k in ("id", "title", "target", "unit", "current", "remaining", "days_left", "status", "text", "evidence"):
                self.assertIn(k, p)
            self.assertEqual(p["id"], o["id"])
            want = self._figure(o, "2026-09-21", TODAY)
            self.assertAlmostEqual(p["current"], want, delta=0.01, msg=o["title"])
            self.assertIn(p["days_left"], (3, 4))
            self.assertIn(p["status"], ("on_track", "done", "missed", "at_risk"))
            if self._met(o, want):
                self.assertIn(p["status"], ("on_track", "done"), (o, p))
            else:
                self.assertIn(p["status"], ("missed", "at_risk"), (o, p))
            self.assertIsNone(SCOLD.search(p["text"]), p["text"])
            self.assertTrue(p["text"].strip())

    def test_W6_a_missed_challenge_is_kind(self):
        conn = fx.sandbox(A, "2026-09-28")
        ch = {"id": "x1", "kind": "under_amount", "title": "Keep taxis under 5 euros this week", "why": "easy",
              "target": 5.0, "unit": "EUR", "baseline": 30.0, "difficulty": "easy", "label": "Taxi", "context": "",
              "period": {"from": "2026-09-21", "to": "2026-09-27"}, "evidence": [],
              "accepted_at": "2026-09-21T09:00:00"}
        p = self.features.challenge_progress(conn, "2026-09-28", ch)
        self.assertAlmostEqual(p["current"], 19.90, places=2)
        self.assertEqual(p["status"], "missed")
        self.assertIsNone(SCOLD.search(p["text"]), p["text"])
        self.assertTrue(p["text"].strip())

    def test_W6_customer_without_habits_gets_no_invented_ones(self):
        conn = f2.make_conn(f2.base_rows())
        r = self.features.challenge_options(conn, TODAY)
        self.assertLessEqual(len(r["options"]), 3)
        for o in r["options"]:
            self.assertNotEqual(o.get("label"), "Taxi", "no taxi habit exists")


# ---------------------------------------------------------------------------------------------
class QuizStatsTests(FeatureCase):
    @staticmethod
    def h(*pairs):
        out = []
        for i, (g, a) in enumerate(pairs):
            out.append({"at": "2026-09-%02dT10:00:00" % (i + 1), "label": "Taxi", "guess": g, "actual": a})
        return out

    @staticmethod
    def acc(g, a):
        return max(0.0, 100 - 100 * abs(g - a) / max(a, 10))

    def test_W7_empty_history(self):
        r = self.features.quiz_stats([])
        self.assertEqual(r["count"], 0)
        self.assertIsNone(r["awareness_score"])
        self.assertIsNone(r["trend"])
        self.assertEqual(r["points"], [])
        self.assertTrue(r["text"].strip())

    def test_W7_accuracy_formula(self):
        hist = self.h((40, 50), (5, 0), (100, 20), (50, 50), (8, 12))
        r = self.features.quiz_stats(hist)
        self.assertEqual(r["count"], 5)
        self.assertEqual(len(r["points"]), 5)
        for p, (g, a) in zip(r["points"], [(40, 50), (5, 0), (100, 20), (50, 50), (8, 12)]):
            self.assertAlmostEqual(p["accuracy"], self.acc(g, a), delta=0.6)
            self.assertEqual((p["guess"], p["actual"]), (g, a))
            self.assertIn("at", p)
            self.assertIn("label", p)
        self.assertAlmostEqual(r["points"][0]["accuracy"], 80.0, delta=0.6)
        self.assertAlmostEqual(r["points"][1]["accuracy"], 50.0, delta=0.6)      # actual 0 uses a floor of 10
        self.assertEqual(round(r["points"][2]["accuracy"]), 0)                    # clamped at 0

    def test_W7_score_is_mean_of_last_five(self):
        pairs = [(10, 100), (20, 100), (90, 100), (80, 100), (100, 100), (70, 100), (95, 100)]
        r = self.features.quiz_stats(self.h(*pairs))
        want = sum(self.acc(g, a) for g, a in pairs[-5:]) / 5.0
        self.assertAlmostEqual(r["awareness_score"], want, delta=0.6)
        self.assertEqual(r["count"], 7)
        self.assertIsNotNone(r["best"])
        self.assertTrue(0 <= r["awareness_score"] <= 100)

    def test_W7_trend_needs_four_answers(self):
        self.assertIsNone(self.features.quiz_stats(self.h((10, 100), (50, 100), (90, 100)))["trend"])
        self.assertIsNotNone(self.features.quiz_stats(self.h((10, 100), (90, 100), (90, 100), (90, 100)))["trend"])

    def test_W7_trend_directions(self):
        up = self.features.quiz_stats(self.h((10, 100), (90, 100), (90, 100), (90, 100)))
        self.assertEqual(up["trend"], "improving")
        down = self.features.quiz_stats(self.h((90, 100), (10, 100), (10, 100), (10, 100)))
        self.assertEqual(down["trend"], "slipping")
        flat = self.features.quiz_stats(self.h(*[(80, 100)] * 6))
        self.assertEqual(flat["trend"], "steady")
        long_up = self.features.quiz_stats(self.h((10, 100), (10, 100), (10, 100), (90, 100), (90, 100), (90, 100)))
        self.assertEqual(long_up["trend"], "improving")


# ---------------------------------------------------------------------------------------------
class ForecastTests(FeatureCase):
    def test_W10_window_ends_on_the_next_payday_and_identities_hold(self):
        conn = fx.sandbox(A)
        r = self.features.forecast(conn, TODAY)
        self.assertEqual(r["to"], "2026-10-15")
        self.assertEqual(r["from"], TODAY)
        self.assertAlmostEqual(r["start_balance"], fx.balance_at(A), places=2)
        pts = r["points"]
        self.assertGreaterEqual(len(pts), 21)
        days = [p["d"] for p in pts]
        self.assertEqual(days, sorted(set(days)), "one point per day, in order")
        self.assertGreaterEqual(days[0], TODAY)
        self.assertLessEqual(days[0], "2026-09-25")
        self.assertEqual(days[-1], "2026-10-15")
        for a, b in zip(days, days[1:]):
            self.assertEqual(f2.days_between(a, b), 1)
        self.assertAlmostEqual(r["end_balance"], pts[-1]["balance"], places=2)
        low = min(pts, key=lambda p: p["balance"])
        self.assertAlmostEqual(r["lowest"]["balance"], low["balance"], places=2)
        self.assertEqual(r["lowest"]["d"], low["d"]) if sum(1 for p in pts if p["balance"] == low["balance"]) == 1 else None
        self.assertEqual(r["goes_negative"], any(p["balance"] < 0 for p in pts))
        self.assertFalse(r["goes_negative"])
        self.assertIsNone(r["first_negative"])
        self.assertTrue(r["text"].strip())
        self.assertExplained(r)

    def test_W10_the_rent_is_an_event_on_its_due_date_and_lowers_the_balance(self):
        r = self.features.forecast(fx.sandbox(A), TODAY)
        by = {p["d"]: p for p in r["points"]}
        self.assertIn("2026-10-02", by)
        rent = [e for e in by["2026-10-02"]["events"] if "housing" in e["label"].lower() or "rent" in e["label"].lower()]
        self.assertTrue(rent, by["2026-10-02"]["events"])
        self.assertAlmostEqual(abs(rent[0]["amount"]), 900.0, delta=0.01)
        prev = by["2026-10-01"]["balance"]
        self.assertLessEqual(by["2026-10-02"]["balance"], prev - 900.0 + 0.01)
        self.assertLessEqual(r["end_balance"], r["start_balance"] - 900.0 + 0.01)

    def test_W10_goes_negative_matches_the_points_for_an_overdrawn_customer(self):
        r = self.features.forecast(fx.sandbox(D), TODAY)
        negs = [p for p in r["points"] if p["balance"] < 0]
        self.assertTrue(negs, "D is below zero")
        self.assertTrue(r["goes_negative"])
        self.assertEqual(r["first_negative"], negs[0]["d"])
        self.assertAlmostEqual(r["lowest"]["balance"], min(p["balance"] for p in r["points"]), places=2)
        self.assertLess(r["lowest"]["balance"], 0)
        self.assertEqual(r["to"], "2026-09-25")
        self.assertTrue(r["text"].strip())

    def test_W10_days_argument_and_cap(self):
        conn = fx.sandbox(A)
        r = self.features.forecast(conn, TODAY, days=5)
        self.assertEqual(r["to"], "2026-09-29")
        r = self.features.forecast(conn, TODAY, days=400)
        self.assertLessEqual(f2.days_between(TODAY, r["to"]), 45)


# ---------------------------------------------------------------------------------------------
class PaydayPlanTests(FeatureCase):
    KEYS = {"regular", "unexpected", "savings", "everyday"}

    def cents(self, plan):
        return sum(round(l["amount"] * 100) for l in plan["lines"])

    def test_W11_four_lines_sum_to_the_salary_to_the_cent(self):
        p = self.features.payday_plan(fx.sandbox(A), TODAY)
        self.assertEqual({l["key"] for l in p["lines"]}, self.KEYS)
        self.assertEqual(len(p["lines"]), 4)
        self.assertEqual(p["next_payday"], "2026-10-15")
        self.assertAlmostEqual(p["expected_salary"], 3000.0, places=2)
        self.assertEqual(self.cents(p), round(p["expected_salary"] * 100))
        for l in p["lines"]:
            for k in ("name", "amount", "share", "why"):
                self.assertIn(k, l)
            self.assertTrue(l["why"].strip())
        by = {l["key"]: l for l in p["lines"]}
        self.assertGreater(by["regular"]["amount"], 900.0)
        self.assertGreater(by["everyday"]["amount"], 0)
        self.assertAlmostEqual(p["everyday_per_day"] * 7, p["everyday_per_week"], delta=0.1)
        self.assertIsNone(p["goal_line"])
        self.assertTrue(p["text"].strip())
        self.assertExplained(p)

    def test_W11_usual_deposit_is_the_savings_line_without_a_target(self):
        p = self.features.payday_plan(fx.sandbox(A), TODAY)
        self.assertAlmostEqual({l["key"]: l for l in p["lines"]}["savings"]["amount"], 200.0, places=2)

    def test_W11_the_saving_target_is_used_when_set(self):
        p = self.features.payday_plan(fx.sandbox(A), TODAY, monthly_saving_target=350.0)
        by = {l["key"]: l for l in p["lines"]}
        self.assertAlmostEqual(by["savings"]["amount"], 350.0, places=2)
        self.assertEqual(self.cents(p), round(p["expected_salary"] * 100))

    def test_W11_goal_line(self):
        goal = {"name": "flat", "target": 12000.0, "saved": 2000.0}
        p = self.features.payday_plan(fx.sandbox(A), TODAY, goal=goal, monthly_saving_target=500.0)
        gl = p["goal_line"]
        self.assertIsNotNone(gl)
        self.assertEqual(gl["name"], "flat")
        self.assertAlmostEqual(gl["months_to_goal"], 10000.0 / 500.0, delta=1.01)

    def test_W11_negative_remainder_zeroes_savings_and_says_so(self):
        rows = f2.base_rows(salary=1000.0, housing=900.0)
        conn = f2.make_conn(rows)
        p = self.features.payday_plan(conn, TODAY, monthly_saving_target=100.0)
        by = {l["key"]: l for l in p["lines"]}
        self.assertEqual(by["savings"]["amount"], 0)
        self.assertLess(by["everyday"]["amount"], 0)
        self.assertEqual(self.cents(p), round(p["expected_salary"] * 100))
        self.assertRegex(p["text"].lower(), r"not enough|short|more than|exceed|over|doesn't|does not|cannot|can't|"
                                            r"no room|nothing left|negative|below|tight|isn't enough")


# ---------------------------------------------------------------------------------------------
class InsightsTimeWindowTests(FeatureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        rows = f2.base_rows(first=(2026, 8), last=(2026, 9))
        for d, t in (("2026-09-23", "17:59:59"), ("2026-09-23", "18:00:00"), ("2026-09-23", "23:30:00"),
                     ("2026-09-24", "05:59:59"), ("2026-09-24", "06:00:00")):
            rows.append(f2.row(d, "Taxi", -{"17:59:59": 11.0, "18:00:00": 12.0, "23:30:00": 13.0,
                                            "05:59:59": 14.0, "06:00:00": 15.0}[t], merchant="MX30121", time=t))
        cls.conn = f2.make_conn(rows)
        cls.amounts = {r["ts"][11:]: -r["amount"] for r in rows if r["label"] == "Taxi"}

    def test_W9_period_today_yesterday_last_night(self):
        p = self.ins.period(TODAY, "today")
        self.assertEqual((str(p[0])[:10], str(p[1])[:10]), (TODAY, TODAY))
        p = self.ins.period(TODAY, "yesterday")
        self.assertEqual((str(p[0])[:10], str(p[1])[:10]), ("2026-09-23", "2026-09-23"))
        p = self.ins.period(TODAY, "last_night")
        self.assertTrue(str(p[0]).startswith("2026-09-23"), p)
        self.assertTrue(str(p[1]).startswith("2026-09-24"), p)
        if len(str(p[0])) > 10:
            self.assertIn("18:00:00", str(p[0]))
            self.assertIn("06:00:00", str(p[1]))

    def test_W9_transactions_ts_window_is_inclusive_start_exclusive_end(self):
        r = self.ins.transactions(self.conn, TODAY, label="Taxi",
                                  ts_from="2026-09-23 18:00:00", ts_to="2026-09-24 06:00:00")
        got = sorted(x["ts"][11:] for x in r["rows"])
        self.assertEqual(got, ["05:59:59", "18:00:00", "23:30:00"])
        self.assertEqual(r["count"], 3)
        want = sum(self.amounts[t] for t in got)
        self.assertAlmostEqual(abs(r["total"]), want, places=2)

    def test_W9_spend_accepts_the_same_window(self):
        want = sum(self.amounts[t] for t in ("18:00:00", "23:30:00", "05:59:59"))
        s = self.ins.spend(self.conn, TODAY, "last_night", label="Taxi")
        self.assertAlmostEqual(s["total"], want, places=2)
        self.assertEqual(s["count"], 3)
        s = self.ins.spend(self.conn, TODAY, "this_month", label="Taxi",
                           ts_from="2026-09-23 18:00:00", ts_to="2026-09-24 06:00:00")
        self.assertAlmostEqual(s["total"], want, places=2)
        self.assertEqual(s["count"], 3)

    def test_W9_transactions_rows_carry_an_id(self):
        r = self.ins.transactions(self.conn, TODAY, label="Taxi")
        for x in r["rows"]:
            self.assertIn("id", x)
            self.assertIsInstance(x["id"], int)


# ---------------------------------------------------------------------------------------------
class LearningPythonLayerTests(FeatureCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        fx.use_fresh_state()
        import app.state as state
        cls.state = state

    def setUp(self):
        self.state.erase(A)

    tearDown = setUp

    def sandbox(self):
        return self.db.sandbox(A, TODAY, overrides=self.state.list_overrides(A))

    def one_row(self, where):
        conn = fx.sandbox(A)
        return dict(conn.execute("SELECT * FROM tx WHERE " + where + " ORDER BY d LIMIT 1").fetchone())

    def test_W2_tx_override_changes_label_basket_and_context_of_one_row(self):
        kebab = self.one_row("label='Fast food' AND context='night_out' AND d BETWEEN '2026-08-01' AND '2026-08-31'")
        self.assertAlmostEqual(kebab["amount"], -11.50, places=2)
        self.state.add_override(A, {"scope": "tx", "tx_id": kebab["id"], "label": "Restaurant", "context": ""})
        conn = self.sandbox()
        row = dict(conn.execute("SELECT * FROM tx WHERE id=?", (kebab["id"],)).fetchone())
        self.assertEqual((row["label"], row["context"], row["basket"]), ("Restaurant", "", "everyday"))
        other = conn.execute("SELECT count(*) FROM tx WHERE label='Fast food' AND context='night_out'").fetchone()[0]
        base = fx.sandbox(A).execute("SELECT count(*) FROM tx WHERE label='Fast food' AND context='night_out'").fetchone()[0]
        self.assertEqual(other, base - 1)
        # a new session (a new sandbox from stored state) still sees it
        again = dict(self.sandbox().execute("SELECT * FROM tx WHERE id=?", (kebab["id"],)).fetchone())
        self.assertEqual(again["label"], "Restaurant")
        # the transactions view returns the new label
        shown = self.ins.transactions(self.sandbox(), TODAY, frm="2026-08-01", to="2026-08-31", label="Restaurant")
        self.assertIn(kebab["id"], [x["id"] for x in shown["rows"]])

    def test_W2_moving_a_row_moves_the_amount_between_baskets(self):
        g = self.one_row("label='Groceries' AND merchant<>'' AND d BETWEEN '2026-08-01' AND '2026-08-31'")
        amt = -g["amount"]
        before = self.ins.baskets(fx.sandbox(A), TODAY, "2026-08")
        self.state.add_override(A, {"scope": "tx", "tx_id": g["id"], "label": "Clothing", "context": ""})
        after = self.ins.baskets(self.sandbox(), TODAY, "2026-08")
        b0 = {b["key"]: b["total"] for b in before["baskets"]}
        b1 = {b["key"]: b["total"] for b in after["baskets"]}
        self.assertAlmostEqual(b1["regular"], b0["regular"] - amt, places=2)
        self.assertAlmostEqual(b1["everyday"], b0["everyday"] + amt, places=2)
        keys = [k for k in ("regular", "unexpected", "everyday", "savings") if k in b0]
        self.assertAlmostEqual(sum(b1[k] for k in keys), sum(b0[k] for k in keys), places=2)
        frm, to = fx.month_bounds("2026-08")
        self.assertAlmostEqual(sum(b1[k] for k in keys), fx.spend(A, frm, to)[0], places=2)

    def test_W2_apply_to_merchant_changes_every_purchase_of_that_merchant(self):
        taxis = [r for r in fx.rows_for(A) if r["merchant"] == "MX30121" and r["cents"] < 0 and r["d"] <= TODAY]
        self.assertGreater(len(taxis), 20)
        base_clothing = fx.sandbox(A).execute("SELECT count(*) FROM tx WHERE label='Clothing'").fetchone()[0]
        self.state.add_override(A, {"scope": "merchant", "merchant": "MX30121", "label": "Clothing", "context": ""})
        conn = self.sandbox()
        self.assertEqual(conn.execute("SELECT count(*) FROM tx WHERE label='Clothing'").fetchone()[0],
                         base_clothing + len(taxis))
        self.assertEqual(conn.execute("SELECT count(*) FROM tx WHERE label='Taxi'").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM tx WHERE merchant='MX30121' AND context<>''").fetchone()[0], 0)

    def test_W2_removal_undoes_and_erase_clears(self):
        g = self.one_row("label='Groceries' AND merchant<>''")
        ov = self.state.add_override(A, {"scope": "tx", "tx_id": g["id"], "label": "Clothing", "context": ""})
        self.assertEqual(len(self.state.list_overrides(A)), 1)
        self.assertEqual(dict(self.sandbox().execute("SELECT label FROM tx WHERE id=?", (g["id"],)).fetchone())["label"], "Clothing")
        self.state.remove_override(A, ov["id"])
        self.assertEqual(self.state.list_overrides(A), [])
        self.assertEqual(dict(self.sandbox().execute("SELECT label FROM tx WHERE id=?", (g["id"],)).fetchone())["label"], "Groceries")
        self.state.add_override(A, {"scope": "tx", "tx_id": g["id"], "label": "Clothing", "context": ""})
        self.state.set_goal(A, {"name": "flat", "target": 1000.0, "saved": 10.0})
        self.state.add_quiz_result(A, {"at": "2026-09-20T10:00:00", "label": "Taxi", "guess": 5.0, "actual": 6.0})
        self.state.erase(A)
        self.assertEqual(self.state.list_overrides(A), [])
        self.assertIsNone(self.state.get_goal(A))
        self.assertEqual(self.state.quiz_history(A), [])
        self.assertIsNone(self.state.get_challenge(A))

    def test_W2_another_customers_overrides_do_not_apply(self):
        g = self.one_row("label='Groceries' AND merchant<>''")
        self.state.add_override(A, {"scope": "tx", "tx_id": g["id"], "label": "Clothing", "context": ""})
        self.assertEqual(self.state.list_overrides(fx.B_CID), [])
        self.state.erase(fx.B_CID)


# ---------------------------------------------------------------------------------------------
class AreaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.area as area
        cls.area = area
        path = fx.REPO / "app" / "paavo.json"
        cls.keys = []
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            cls.keys = cls._postal_keys(data)

    @staticmethod
    def _postal_keys(data):
        found = []
        pat = re.compile(r"^\d{5}$")

        def walk(o, depth):
            if depth > 3:
                return
            if isinstance(o, dict):
                for k, v in o.items():
                    if pat.match(str(k)):
                        found.append(str(k))
                    elif isinstance(v, (dict, list)):
                        walk(v, depth + 1)
            elif isinstance(o, list):
                for v in o[:50]:
                    if isinstance(v, dict):
                        for key in ("postal", "postal_code", "postcode", "zip", "code", "posti_alue"):
                            if pat.match(str(v.get(key, ""))):
                                found.append(str(v[key]))
        walk(data, 0)
        return found

    def test_W8_unknown_postal_code_gives_no_rows_and_a_note(self):
        r = self.area.area_context("99999")
        self.assertEqual(r["rows"], [])
        self.assertTrue(str(r["note"]).strip())
        self.assertNotIn("99999", json.dumps(r))

    def test_W8_known_postal_code_rows_are_complete_and_hide_the_code(self):
        if not self.keys:
            self.skipTest("app/paavo.json missing or no five-digit postal key found: area rows not testable")
        postal = self.keys[0]
        r = self.area.area_context(postal)
        self.assertTrue(r["rows"], "known postal code %s gave no rows" % postal)
        for row in r["rows"]:
            for k in ("name", "value", "unit", "text"):
                self.assertIn(k, row)
            self.assertTrue(str(row["text"]).strip())
            self.assertTrue(str(row["name"]).strip())
        for k in ("area_name", "year", "source", "url", "explain"):
            self.assertIn(k, r)
        self.assertNotIn(postal, json.dumps(r), "the postal code must not appear in the result (SR-22, SR-23)")

    def test_W8_compare_with_customer_figures(self):
        if not self.keys:
            self.skipTest("app/paavo.json missing or no five-digit postal key found")
        r = self.area.area_context(self.keys[0], {"monthly_income": 3000.0, "housing_cost": 900.0})
        self.assertIsInstance(r["compare"], list)
        json.dumps(r)


if __name__ == "__main__":
    unittest.main()
