"""Chart blocks and captions on tool results (Contract B): well-formed, figures equal the result's own."""
import json
import math
import os as _os
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fixture as fx

fx.get()
from app import charts, tools  # noqa: E402

KINDS = ("bars", "hbars", "line", "split", "progress")
TONES = ("main", "muted", "good", "warn")


def check_chart(tc, ch):
    tc.assertIn(ch["kind"], KINDS)
    tc.assertIn(ch["unit"], ("eur", "count", "pct"))
    s = ch["series"]
    if ch["kind"] in ("bars", "line"):
        tc.assertTrue(2 <= len(s) <= 12)
    elif ch["kind"] == "hbars":
        tc.assertTrue(2 <= len(s) <= 6)
    elif ch["kind"] == "split":
        tc.assertTrue(2 <= len(s) <= 5)
    for p in s:
        tc.assertTrue(math.isfinite(p["value"]))
        tc.assertIn(p["tone"], TONES)
        tc.assertIsInstance(p["mark"], bool)
        if ch["kind"] in ("hbars", "split"):
            tc.assertTrue(p["label"] and p["label_fi"], p)
        else:
            tc.assertTrue(p["ym"] or p["label"])
    if ch["kind"] in ("bars", "line") and all(p["ym"] for p in s):
        tc.assertEqual([p["ym"] for p in s], sorted(p["ym"] for p in s))     # oldest first
    json.dumps(ch)


class ChartTests(unittest.TestCase):
    def call(self, name, args=None, cid=fx.A_CID):
        ctx = fx.make_ctx(cid)
        import app.db as db
        ctx.memory, ctx.cid, ctx.bench_lookup = {}, cid, db.bench
        res = tools.call(name, args or {}, ctx)
        self.assertNotIn("error", res, res)
        return res

    def both(self, res):
        self.assertTrue(res.get("caption") and res.get("caption_fi"), res.get("card"))
        self.assertLessEqual(len(res["caption"].split()), 22)
        return res["caption"], res["caption_fi"]

    def test_money_formats(self):
        self.assertEqual(charts.money_en(92.85, True), "€92.85")
        self.assertEqual(charts.money_en(1583.2), "€1,583")
        self.assertEqual(charts.money_en(7.416), "€7.42")
        self.assertEqual(charts.money_fi(92.85, True), "92,85 €")
        self.assertEqual(charts.money_fi(1583.2), "1 583 €")
        self.assertEqual(charts.money_fi(19.5), "19,50 €")
        self.assertEqual(charts.money_fi(20.4), "20 €")

    def test_spend_bars_and_caption(self):
        res = self.call("get_spend", {"label": "Groceries", "period": "2026-08"})
        ch = res["chart"]
        check_chart(self, ch)
        self.assertEqual(ch["kind"], "bars")
        self.assertEqual(len(ch["series"]), 6)
        marked = [p for p in ch["series"] if p["mark"]]
        self.assertEqual([p["ym"] for p in marked], ["2026-08"])
        self.assertAlmostEqual(marked[0]["value"], res["total"], places=2)
        en, fi = self.both(res)
        self.assertIn(charts.money_en(res["total"], charts.EXACT_SPEND), en)
        self.assertIn(charts.money_fi(res["total"], charts.EXACT_SPEND), fi)
        self.assertIn("elokuussa", fi)

    def test_spend_taxi_wording(self):
        res = self.call("get_spend", {"label": "Taxi", "period": "last_month"})
        en, fi = self.both(res)
        self.assertIn("on taxis in August", en)
        self.assertTrue(fi.startswith("Takseihin meni elokuussa"))

    def test_spend_dining_out_history_matches(self):
        res = self.call("get_spend", {"label": "Dining out", "period": "2026-08"})
        if res.get("chart"):
            marked = [p for p in res["chart"]["series"] if p["mark"]][0]
            self.assertAlmostEqual(marked["value"], res["total"], places=2)

    def test_spend_no_chart_for_one_day(self):
        res = self.call("get_spend", {"period": "yesterday"})
        self.assertNotIn("chart", res)

    def test_safe_split(self):
        res = self.call("get_safe_to_spend")
        ch = res["chart"]
        check_chart(self, ch)
        self.assertEqual(ch["kind"], "split")
        good = [p for p in ch["series"] if p["tone"] == "good"]
        self.assertAlmostEqual(good[0]["value"], res["safe_total"], places=2)
        self.assertAlmostEqual(sum(p["value"] for p in ch["series"]), res["balance"], delta=0.05)
        en, fi = self.both(res)
        self.assertIn(charts.money_en(res["safe_total"]), en)
        self.assertIn(charts.money_fi(res["safe_total"]), fi)

    def test_afford_split(self):
        res = self.call("can_i_afford", {"item": "phone", "price": 100})
        ch = res.get("chart")
        self.assertTrue(ch)
        check_chart(self, ch)
        vals = {p["label"]: p["value"] for p in ch["series"]}
        self.assertAlmostEqual(vals["Price"], 100.0)
        self.assertAlmostEqual(vals["Left after"], res["after"], places=2)
        self.both(res)

    def test_overview_and_baskets_split(self):
        res = self.call("get_overview", {"month": "2026-08"})
        ch = res["chart"]
        check_chart(self, ch)
        self.assertAlmostEqual(sum(p["value"] for p in ch["series"]), res["income"], delta=0.1)
        en, fi = self.both(res)
        self.assertIn("August", en)
        self.assertIn("Elokuussa", fi)
        b = self.call("get_baskets", {"period": "last_month"})
        check_chart(self, b["chart"])
        self.both(b)

    def test_explain_month(self):
        res = self.call("explain_month", {"month": "2026-07"})
        ch = res.get("chart")
        if ch:
            check_chart(self, ch)
            self.assertEqual(ch["kind"], "hbars")
            for p, d in zip(ch["series"], res["drivers"]):
                self.assertAlmostEqual(p["value"], d.get("above_usual", d.get("below_usual")), places=2)
        en, fi = self.both(res)
        self.assertIn(charts.money_en(res["spent"]), en)
        self.assertIn(charts.money_fi(res["usual"]), fi)

    def test_long_view_cards(self):
        for name, args, kind in (("get_money_story", {}, "line"), ("get_category_story", {"label": "Groceries"}, "bars"),
                                 ("get_low_points", {}, "bars"), ("get_income_profile", {}, "bars"),
                                 ("get_season_outlook", {}, "bars")):
            res = self.call(name, args)
            if res.get("too_little_data") or res.get("relevant") is False:
                continue
            ch = res.get("chart")
            self.assertTrue(ch, name)
            check_chart(self, ch)
            self.assertEqual(ch["kind"], kind, name)

    def test_money_story_caption_has_balance(self):
        res = self.call("get_money_story")
        if res.get("chart"):
            self.assertIn(charts.money_en(res["balance"]["now"]), res["caption"])
            self.assertIn(charts.money_fi(res["balance"]["now"]), res["caption_fi"])

    def test_what_if_two_bars(self):
        res = self.call("simulate_what_if", {"changes": [{"target": "Restaurant", "pct": 20}]})
        ch = res["chart"]
        check_chart(self, ch)
        self.assertEqual([p["value"] for p in ch["series"]], [res["baseline_monthly"], res["new_monthly"]])
        en, fi = self.both(res)
        self.assertIn(charts.money_en(res["saved_monthly"]), en)

    def test_ideas_and_habits(self):
        for name in ("get_save_more", "find_leaks", "get_spender_type"):
            res = self.call(name)
            if res.get("chart"):
                check_chart(self, res["chart"])
                self.both(res)

    def test_comparisons(self):
        for name in ("get_benchmarks", "get_averages"):
            res = self.call(name)
            ch = res.get("chart")
            if ch:
                check_chart(self, ch)
                self.assertTrue(all(p["value2"] is not None for p in ch["series"]))
                self.both(res)

    def test_goal_line(self):
        res = self.call("plan_goal_by_date", {"name": "Trip", "target": 1500, "deadline": "2027-05-31"})
        if res.get("needs"):
            return
        ch = res["chart"]
        check_chart(self, ch)
        self.assertEqual(ch["kind"], "line")
        self.assertEqual(ch["target"], 1500.0)
        self.assertLessEqual(max(p["value"] for p in ch["series"]), 1500.0)
        en, fi = self.both(res)
        self.assertIn("toukokuuhun 2027", fi)

    def test_finnish_money_style(self):
        for name, args in (("get_spend", {"label": "Taxi"}), ("get_safe_to_spend", {}), ("get_overview", {})):
            fi = self.call(name, args)["caption_fi"]
            self.assertNotIn("€" + "1", fi)            # no euro sign in front
            self.assertIn(" €", fi)

    def test_error_and_unknown_cards_untouched(self):
        self.assertEqual(charts.attach("nope", {"a": 1}, {}, None, None), {"a": 1})
        res = tools.call("get_spend", {"label": "bogus"}, fx.make_ctx())
        self.assertNotIn("chart", res)

    def test_existing_fields_unchanged(self):
        ctx = fx.make_ctx()
        res = tools.call("get_safe_to_spend", {}, ctx)
        from app import insights
        plain = insights.safe_to_spend(ctx.conn, ctx.today)
        for k, v in plain.items():
            self.assertEqual(res[k], v)


if __name__ == "__main__":
    unittest.main()
