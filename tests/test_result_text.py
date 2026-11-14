"""House rules for the text inside tool results (what a customer reads on a card).

For three fixture customers every tool is run through tools.call and every string in the result is
checked: no "€0.00", no minus sign in front of money, no ISO dates in sentences, no identifiers in
backticks or "kind:", no "median of N customers", no "Groceries purchases", no "Events was", no
percentage above 100 followed by "above", and money over EUR 20 is always whole euros.
"""
import os as _os
import re
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

# keys whose values are data (dates, ids, filters), not sentences
DATA_KEYS = {"from", "to", "d", "ts", "date", "due", "next_payday", "deadline", "created", "updated",
             "ts_from", "ts_to", "last_seen", "first_negative", "id", "at", "quiz_id"}

ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
MONEY = re.compile(r"€\s?(\d[\d,]*)(\.\d+)?")
PLURAL_WAS = re.compile(r"\b(events|hobbies|groceries|restaurants|taxis|bars|clothes|books|purchases|utilities|"
                        r"transfers|savings)\s+was\b", re.I)
OVER_100_ABOVE = re.compile(r"(?<![\d.])(1\d\d|[2-9]\d\d|\d{4,})\s?%\s+above")

CALLS = [
    ("get_spend", {"period": "last_month"}),
    ("get_spend", {"period": "last_month", "label": "Taxi"}),
    ("get_spend", {"period": "last_3_months", "label": "Groceries"}),
    ("get_spend", {"period": "last_night", "label": "Bar"}),
    ("get_spend", {"period": "last_month", "label": "Fuel"}),
    ("get_overview", {}),
    ("get_baskets", {}),
    ("get_safe_to_spend", {}),
    ("simulate_what_if", {"changes": [{"target": "everyday", "pct": 10}]}),
    ("simulate_what_if", {"changes": [{"target": "Dining out", "pct": 20}]}),
    ("get_spender_type", {}),
    ("get_save_more", {}),
    ("check_mortgage", {}),
    ("check_mortgage", {"price": 200000}),
    ("get_benchmarks", {}),
    ("get_averages", {}),
    ("get_averages", {"topic": "taxi"}),
    ("get_invest_education", {}),
    ("plan_goal", {"target_amount": 3000}),
    ("plan_goal_by_date", {"name": "Japan", "target": 3000, "deadline": "2027-06"}),
    ("plan_goal_by_date", {"name": "Japan"}),
    ("list_transactions", {"limit": 5}),
    ("can_i_afford", {"item": "jacket", "price": 300}),
    ("can_i_afford", {"item": "phone", "price": 20000}),
    ("find_leaks", {}),
    ("get_alerts", {}),
    ("check_savings_leakage", {}),
    ("get_challenge", {}),
    ("get_area_context", {}),
    ("get_balance_forecast", {}),
    ("get_payday_plan", {}),
    ("get_purchase_insight", {}),
    ("get_patterns", {}),
    ("get_receipts", {}),
    ("receipt_insights", {}),
    ("product_habit", {"query": "beer"}),
    ("product_habit", {"query": "fuel"}),
    ("read_receipt", {"text": "Maito 1,29\nLeipa 2,50\nMuovikassi 0,20\nEnergiajuoma 1,99\nYhteensä 5,98"}),
]


def strings(o, key="", skip=DATA_KEYS):
    """(key, string) for every string in a result, leaving out the data keys."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k in skip:
                continue
            yield from strings(v, str(k), skip)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from strings(v, key, skip)
    elif isinstance(o, str):
        yield key, o


class ResultTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import tools
        cls.tools = tools
        cls.results = {}
        for cid in (fx.A_CID, fx.B_CID, fx.D_CID):
            ctx = fx.make_ctx(cid)
            ctx.cid = cid
            ctx.memory = {}
            ctx.goal = None
            ctx.quiz_history = []
            ctx.challenge = None
            ctx.settings = dict(ctx.settings, challenges="on")
            ctx.explain = None
            ctx.remember = None
            from app import db
            ctx.bench_lookup = db.bench
            cls.results[cid] = [(name, args, tools.call(name, args, ctx)) for name, args in CALLS]

    def each(self):
        for cid, items in self.results.items():
            for name, args, res in items:
                for key, s in strings(res):
                    yield cid, name, args, key, s

    def fail_on(self, rx, what):
        bad = ["%s %s %s: %r" % (cid, name, key, s[:140]) for cid, name, args, key, s in self.each()
               if rx.search(s)]
        self.assertEqual(bad, [], "%s in result text:\n%s" % (what, "\n".join(bad[:8])))

    def test_every_tool_gave_a_result_for_every_customer(self):
        ok = 0
        for cid, items in self.results.items():
            for name, args, res in items:
                self.assertIsInstance(res, dict, (cid, name))
                if "error" not in res:
                    ok += 1
        self.assertGreater(ok, 3 * 25, "most calls should work on the fixture customers")

    def test_no_zero_euros_with_cents_and_no_minus_before_money(self):
        self.fail_on(re.compile(r"€0\.00"), "'€0.00'")
        self.fail_on(re.compile(r"[-−–]\s?€"), "a minus sign before money")

    def test_no_iso_dates_in_sentences(self):
        self.fail_on(ISO_DATE, "an ISO date")

    def test_no_identifiers_or_internal_words(self):
        self.fail_on(re.compile(r"`"), "a backticked identifier")
        self.fail_on(re.compile(r"\bkind:"), "'kind:'")
        self.fail_on(re.compile(r"median of \d"), "'median of N'")
        self.fail_on(re.compile(r"\bGroceries purchases\b"), "'Groceries purchases'")
        self.fail_on(PLURAL_WAS, "a plural noun with 'was'")

    def test_percentages_above_100_are_worded(self):
        self.fail_on(OVER_100_ABOVE, "a percentage above 100 followed by 'above'")

    def test_money_over_20_is_whole_euros_and_never_mixes_formats(self):
        bad = []
        for cid, name, args, key, s in self.each():
            for m in MONEY.finditer(s):
                whole = float(m.group(1).replace(",", ""))
                cents = m.group(2)
                if whole >= 20 and cents:
                    bad.append("%s %s %s: %r" % (cid, name, key, m.group(0)))
        self.assertEqual(bad, [], "amounts from EUR 20 are whole euros:\n%s" % "\n".join(bad[:8]))

    def test_periods_never_carry_the_current_year_or_a_to_range_in_a_sentence(self):
        year = fx.TODAY[:4]
        pat = re.compile(r"\b\d{1,2}(?:-\d{1,2})? (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) " + year)
        pat2 = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|"
                          r"December) " + year)
        self.fail_on(pat, "a date with the current year")
        self.fail_on(pat2, "a month with the current year")

    def test_receipts_say_demo_once_and_keep_remainder_lines_out_of_the_top(self):
        for cid, items in self.results.items():
            for name, args, res in items:
                if name == "get_receipts" and "error" not in res:
                    for rc in res["receipts"]:
                        self.assertNotIn("simulated", rc["bonus"]["label"].lower(), cid)
                    self.assertEqual(res.get("label"), "Demo receipts")
                if name == "receipt_insights" and "error" not in res:
                    names = [p["name"] for p in res["top_products"]]
                    self.assertNotIn("Muovikassi", names)
                    self.assertNotIn("Pantti", names)
                    hl = res["highlights"]
                    if res["top_products"] and hl:
                        self.assertIn(res["top_products"][0]["name"], hl[0], cid)
                    self.assertNotIn("simulated", res["bonus"]["note"].lower())
                    text = " ".join(hl).lower()
                    self.assertNotIn("muovikassi", text)
                    self.assertNotIn("pantti", text)


class WordingHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import insights
        cls.ins = insights

    def test_money_follows_the_house_rule(self):
        m = self.ins.money
        self.assertEqual(m(1234.56), "€1,235")
        self.assertEqual(m(20), "€20")
        self.assertEqual(m(19.99), "€19.99")
        self.assertEqual(m(7.91), "€7.91")
        self.assertEqual(m(10), "€10")
        self.assertEqual(m(0), "nothing")
        self.assertEqual(m(0.001), "nothing")
        self.assertEqual(m(-457.5), "€458")       # the sign is worded by the sentence, never written
        self.assertEqual(self.ins._eur0(11.28), "€11")
        self.assertEqual(self.ins._eur0(0.4), "€0.40")

    def test_percentages_above_100_are_worded(self):
        r = self.ins.ratio_words
        self.assertEqual(r(221, 118), "almost double")           # 87% above is worded from 75% up (LEAD-L10)
        self.assertEqual(r(150, 118), "27% above")
        self.assertEqual(r(236, 118), "about double")
        self.assertEqual(r(263, 118), "more than double")
        self.assertEqual(r(93, 17), "about 5 times")
        self.assertEqual(self.ins.higher_words(40), "about 40% higher")
        self.assertEqual(self.ins.higher_words(150), "more than double")

    def test_periods_are_worded_without_the_current_year(self):
        p = self.ins.human_period
        t = fx.TODAY                                  # a Thursday, 2026-09-24
        self.assertEqual(p("2026-08-01", "2026-08-31", t), "in August")
        self.assertEqual(p("2025-08-01", "2025-08-31", t), "in August 2025")
        self.assertEqual(p("2026-09-01", t, t), "this month so far")
        self.assertEqual(p(t, t, t), "today")
        self.assertEqual(p("2026-09-23", "2026-09-23", t), "yesterday")
        self.assertEqual(p("2026-09-10", "2026-09-10", t), "on 10 Sep")
        self.assertEqual(p("2026-06-25", t, t), "over the last 3 months")
        self.assertEqual(p("2026-06-01", t, t), "over the last 4 months")
        self.assertEqual(p("2026-01-01", t, t), "this year so far")
        self.assertEqual(p("2026-09-14", "2026-09-17", t), "from 14 to 17 Sep")
        self.assertEqual(p("2026-08-20", "2026-09-05", t), "from 20 Aug to 5 Sep")
        self.assertEqual(self.ins.human_range("2026-08-01", "2026-08-31"), "August 2026")   # unchanged without today
        self.assertEqual(self.ins.human_month("2026-08", t), "August")
        self.assertEqual(self.ins.human_month("2026-08"), "August 2026")

    def test_category_nouns_are_lower_case_inside_sentences(self):
        self.assertEqual(self.ins.label_words("Taxi"), "taxis")
        self.assertEqual(self.ins.label_words("Groceries"), "groceries")
        self.assertEqual(self.ins.label_words("Fuel"), "fuel")
        self.assertEqual(self.ins.label_title("Groceries"), "Grocery")
        self.assertEqual(self.ins.target_words("everyday"), "everyday spending")
        self.assertEqual(self.ins.target_words("night_out"), "nights out")


class FuelAgreementTests(unittest.TestCase):
    """A payment the customer labels Fuel that is not a card purchase is counted by the spending answers and
    the alerts (5 payments) but has no receipt (4 receipts). Each text says what it counts."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        import fixture_wave2 as f2
        from app import insights, receipts, features
        cls.ins, cls.rc, cls.ft = insights, receipts, features
        rows = f2.base_rows()
        for y, m in f2.months():
            for day in (3, 11, 23):
                rows.append(f2.row("%04d-%02d-%02d" % (y, m, day), "Fuel", -60.0, merchant="MX30541"))
        # the customer called a utilities bill "Fuel"
        rows.append(f2.row("2026-08-07", "Fuel", -41.68, time="17:59:43", type="utilities_payment"))
        cls.conn = f2.make_conn(rows)
        cls.today = f2.TODAY

    def test_spend_counts_every_payment_labelled_fuel(self):
        r = self.ins.spend(self.conn, self.today, "last_month", label="Fuel")
        self.assertEqual(r["count"], 4)
        self.assertAlmostEqual(r["total"], 3 * 60.0 + 41.68, places=2)
        self.assertIn("4 outgoing payments for fuel in August", r["explain"])

    def test_receipts_say_what_they_do_not_cover(self):
        r = self.rc.receipts(self.conn, self.today, "last_month", habit_seed="CUSTX")
        self.assertEqual(r["fuel_count"], 3)
        self.assertAlmostEqual(r["fuel_total"], 180.0, places=2)
        self.assertEqual(r["without_receipt"]["Fuel"]["count"], 1)
        self.assertAlmostEqual(r["without_receipt"]["Fuel"]["total"], 41.68, places=2)
        self.assertIn("1 payment labelled fuel (€42) is not a card purchase", r["explain"])
        ri = self.rc.receipt_insights(self.conn, self.today, "last_month", habit_seed="CUSTX")
        self.assertEqual(ri["fuel"]["other_payments"]["count"], 1)
        self.assertTrue(any("1 other payment labelled fuel" in h for h in ri["highlights"]), ri["highlights"])


if __name__ == "__main__":
    unittest.main()
