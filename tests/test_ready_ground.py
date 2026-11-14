"""Demo-ready grounding fixes: the unit of a calculated figure, counts that are not euros, sloppy slots, 112,
slot ids the model never saw, number formats, the percentages of get_invest_facts."""
import unittest

from app import grounding as g
from app import invest


def _calc(label, expr, value):
    return {"results": [{"label": label, "expression": expr, "value": value, "rounded": float(round(value)),
                         "rounded_up": float(round(value) + 1)}], "no_card": True}


def _table():
    return g.FigureTable("2026-09-26")


def _ids(table, tool, args, view):
    n = len(table.figs)
    table.add_result(tool, args, view, raw=view)
    return [f["id"] for f in table.figs[n:]]


class CalculateUnit(unittest.TestCase):
    def test_money_times_twelve_stays_money(self):
        t = _table()
        _ids(t, "get_spend", {"period": "last_month"}, {"total": 92.85})
        (fid,) = _ids(t, "calculate", {}, _calc("taxi at August pace, per year", "92.85 * 12", 1114.2))
        self.assertEqual(t.get(fid)["unit"], "money")
        r = g.render("Taxis would come to about {{%s}} a year." % fid, t)
        self.assertEqual(r["text"], "Taxis would come to about €1,114 a year.")
        r = g.render("Taksit tulisivat noin {{%s}} vuodessa." % fid, t, "fi")
        self.assertEqual(r["text"], "Taksit tulisivat noin 1 114 € vuodessa.")

    def test_ten_percent_of_income_is_money_not_a_percentage(self):
        t = _table()
        _ids(t, "get_spend", {"period": "last_month"}, {"income": 2151.0})
        (fid,) = _ids(t, "calculate", {}, _calc("10% of usual monthly income", "2151.0 * 0.1", 215.1))
        self.assertEqual(t.get(fid)["unit"], "money")
        self.assertEqual(g.fmt(t.get(fid)), "€215")

    def test_per_day_and_per_year_labels_do_not_make_a_plain_number(self):
        t = _table()
        _ids(t, "get_spend", {"period": "last_month"}, {"total": 1520.0})
        (fid,) = _ids(t, "calculate", {}, _calc("about a day", "1520.0 / 30", 50.67))
        self.assertEqual(g.fmt(t.get(fid)), "€51")
        (fid,) = _ids(t, "calculate", {}, _calc("vuodessa", "1520.0 * 12", 18240.0))
        self.assertEqual(t.get(fid)["unit"], "money")

    def test_money_over_money_is_a_count_or_a_share(self):
        t = _table()
        _ids(t, "get_spend", {"period": "last_month"}, {"total": 3000.0, "income": 200.5})
        (a,) = _ids(t, "calculate", {}, _calc("months to reach the goal", "3000.0 / 200.5", 14.96))
        self.assertEqual(t.get(a)["unit"], "number")
        (b,) = _ids(t, "calculate", {}, _calc("share of income, percent", "200.5 / 3000.0 * 100", 6.68))
        self.assertEqual(t.get(b)["unit"], "percent")

    def test_sum_of_exact_figures_is_exact(self):
        t = _table()
        _ids(t, "get_spend", {"period": "last_month"}, {"total": 1186.7})
        _ids(t, "get_spend", {"period": "last_month"}, {"total": 149.21})
        (fid,) = _ids(t, "calculate", {}, _calc("food in total", "1186.7 + 149.21", 1335.91))
        self.assertTrue(t.get(fid)["exact"])
        self.assertEqual(g.fmt(t.get(fid)), "€1,335.91")
        self.assertEqual(g.fmt(t.get(fid), "fi"), "1 335,91 €")

    def test_product_is_not_exact(self):
        t = _table()
        _ids(t, "get_spend", {"period": "last_month"}, {"total": 1186.7})
        (fid,) = _ids(t, "calculate", {}, _calc("a year", "1186.7 * 12", 14240.4))
        self.assertFalse(t.get(fid)["exact"])


class Counts(unittest.TestCase):
    def test_trips_are_counts_not_euros(self):
        t = _table()
        ids = _ids(t, "get_category_story", {"label": "Groceries"}, {"now": {"trips": 8.2, "basket": 70.0}})
        trips = [t.get(i) for i in ids if t.get(i)["label"].startswith("now.trips")][0]
        self.assertEqual(trips["unit"], "count")
        self.assertEqual(g.fmt(trips), "8.2")
        r = g.render("You shop about {{%s}} times a month." % trips["id"], t)
        self.assertEqual(r["text"], "You shop about 8.2 times a month.")

    def test_weekday_dict_under_a_trips_key(self):
        t = _table()
        ids = _ids(t, "grocery_basket_profile", {}, {"weekday_trips": {"Monday": 13, "Friday": 20}})
        self.assertEqual({t.get(i)["unit"] for i in ids}, {"count"})

    def test_shops_and_times_keys(self):
        t = _table()
        ids = _ids(t, "grocery_basket_profile", {}, {"middle_shops": 42, "times_at_lidl": 9})
        self.assertEqual({t.get(i)["unit"] for i in ids}, {"count"})

    def test_year_ago_balance_is_money(self):
        t = _table()
        (fid, *_rest) = _ids(t, "get_money_story", {}, {"balance": {"year_ago": 2856.3}})
        self.assertEqual(t.get(fid)["unit"], "money")


class SloppySlots(unittest.TestCase):
    def setUp(self):
        self.t = _table()
        self.fid = _ids(self.t, "get_spend", {"period": "last_month"}, {"total": 92.85})[0]

    def test_normalised(self):
        for bad in ("{{%s}*", "{%s}}", "{{ %s }", "{{%s", "{%s}", "{{%s}}"):
            raw = bad % self.fid
            r = g.render("You spent %s on taxis last month." % raw, self.t)
            self.assertNotIn("{", r["text"], raw)
            self.assertNotIn("}", r["text"], raw)
            self.assertEqual(r["text"], "You spent €92.85 on taxis last month.", raw)
        self.assertEqual(g.check("You spent {{%s}* on taxis last month." % self.fid, self.t), [])

    def test_never_leaves_braces(self):
        r = g.render("Hello there. Your number is {{ nonsense }} today.", self.t)
        self.assertNotIn("{{", r["text"])


class Emergency(unittest.TestCase):
    def test_112_is_kept(self):
        t = _table()
        r = g.render("Please call 112 right now. I am here with you.", t)
        self.assertEqual(r["violations"], [])
        self.assertIn("112", r["text"])
        r = g.render("Soita heti numeroon 112. Olen tässä.", t, "fi")
        self.assertEqual(r["violations"], [])
        self.assertIn("112", r["text"])

    def test_other_numbers_still_removed(self):
        t = _table()
        r = g.render("Call 116 123 or 0800 now.", t)
        self.assertTrue(r["violations"])


class SlotsNeverShown(unittest.TestCase):
    def test_unlisted_id_is_a_violation(self):
        t = _table()
        shown = _ids(t, "get_spend", {"period": "last_month"}, {"total": 92.85})[0]
        hidden = t._add(500.0, "money", "something never listed", {"kind": "tool", "tool": "x"})
        r = g.render("You spent {{%s}} on taxis last month." % hidden, t)
        self.assertEqual([v["reason"] for v in r["violations"]], ["unknown_slot"])
        r = g.render("You spent {{%s}} on taxis last month." % shown, t)
        self.assertEqual(r["violations"], [])

    def test_snapshot_slots_count_as_shown(self):
        t = _table()
        tagged = t.add_snapshot(["Right now: account balance €1,928 safe to spend."])
        fid = g.slots(tagged[0])[0][0]
        r = g.render("You have {{%s}} in your account." % fid, t)
        self.assertEqual(r["violations"], [])

    def test_text_results_count_as_shown(self):
        t = _table()
        view = t.add_result("get_money_story", {}, {"text": "You kept €1,234.50 last month."})
        fid = g.slots(view["text"])[0][0]
        r = g.render("You kept {{%s}} last month." % fid, t)
        self.assertEqual(r["violations"], [])


class Formats(unittest.TestCase):
    def test_number_grouping(self):
        self.assertEqual(g.fmt_number(2496), "2,496")
        self.assertEqual(g.fmt_number(2496, "fi"), "2 496")
        self.assertEqual(g.fmt_number(8.5, "fi"), "8,5")
        self.assertEqual(g.fmt_number(2026), "2026")

    def test_small_percent_keeps_decimals(self):
        self.assertEqual(g.fmt_percent(0.01), "0.01%")
        self.assertEqual(g.fmt_percent(0.01, "fi"), "0,01 %")
        self.assertEqual(g.fmt_percent(14.6), "15%")
        self.assertEqual(g.fmt_percent(0), "0%")

    def test_yearly_total_has_no_stray_cents(self):
        t = _table()
        (fid,) = _ids(t, "get_spend", {"period": {"from": "2025-09-01", "to": "2026-08-31"}}, {"total": 7175.78})
        self.assertEqual(g.fmt(t.get(fid)), "€7,176")


class InvestFacts(unittest.TestCase):
    def test_rates_are_registered_and_listed(self):
        t = _table()
        res = invest.facts("debt_first")
        view = t.add_result("get_invest_facts", {"topic": "debt_first"}, res, raw=res)
        pcts = {round(f["value"], 2) for f in t.figs if f["unit"] == "percent"}
        self.assertIn(14.6, pcts)
        self.assertIn(7.64, pcts)
        self.assertTrue(any(k.startswith("f") for k in view["figures"]))
        self.assertIn("overdraft_rate_pct", view["figures"])      # the tool's own entries are kept
        r = g.render("Its card credit costs about 14.6% a year, against 7.64% for new consumer credit.", t)
        self.assertEqual(r["violations"], [])
        fid = [f["id"] for f in t.figs if f["unit"] == "percent" and abs(f["value"] - 14.6) < 1e-9][0]
        r = g.render("Its card credit costs about {{%s}} a year." % fid, t)
        self.assertEqual(r["violations"], [])
        self.assertIn("%", r["text"])


class FlatSnapshotSearch(unittest.TestCase):
    def test_same_first_match_as_the_walk(self):
        data = {"a": {"x": 10.5, "evidence": {"id": 1}}, "b": [{"y": 92.85}, {"y": 92.85}], "_skip": {"z": 7},
                "c": {"share": 0.4}}
        flat = g._flatten(data)
        for value, unit in ((92.85, "money"), (10.5, "money"), (40, "percent"), (7, "money"), (5, "money")):
            self.assertEqual(g._find_flat(flat, value, unit), g._find_in(data, value, unit))


if __name__ == "__main__":
    unittest.main()
