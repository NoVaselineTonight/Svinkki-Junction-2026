"""A coach that is useful: it estimates what it can estimate, lets code do the sums, keeps the number check
honest about where each amount came from, and does not repeat the same finding in one conversation.

The owner's example: "I'd like to travel to China with my family. What would a 4 person trip cost?" used to be
answered with "I can't estimate the cost myself. What would you expect the trip to cost?".
"""
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc

A = fx.A_CID


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.tools as tools
        cls.coach, cls.tools = coach, tools

    def ctx(self, cid=A, **over):
        c = fx.make_ctx(cid)
        c.memory = {}
        c.cid = cid
        for k, v in over.items():
            setattr(c, k, v)
        return c

    def run_claude(self, script, message, ctx=None, history=None):
        fake = fc.FakeClaude(script)
        with fc.patched_claude(fake):
            r = self.coach.chat(message, history or [], ctx or self.ctx())
        return r, fake


CHINA = "I'd like to travel to China with my family. What would a 4 person trip cost?"
EST = {"what": "two weeks in China for a family of four", "low": 6000, "high": 9000,
       "basis": "summer, mid-range hotels, flights from Helsinki",
       "parts": [{"label": "flights", "low": 2800, "high": 4000}, {"label": "hotels", "low": 1500, "high": 2500}]}


class EstimateTests(_Base):
    def test_the_prompt_tells_the_coach_to_estimate_and_never_to_hand_the_question_back(self):
        p = self.coach.SYSTEM_PROMPT
        for bit in ("Your general knowledge of the world", "give a realistic estimate yourself",
                    "Never answer that you cannot estimate", "never ask them what it will cost",
                    "general_estimate", "calculate"):
            self.assertIn(bit, p)
        self.assertNotIn("never suggest a number", p)
        d = {t["name"]: t for t in self.tools.TOOLS}["plan_goal_by_date"]["description"]
        self.assertNotIn("never suggest a price", d)
        self.assertIn("general_estimate", d)

    def test_general_estimate_returns_a_range_a_middle_and_says_where_it_comes_from(self):
        r = self.tools.call("general_estimate", EST, self.ctx())
        self.assertEqual((r["low"], r["high"], r["mid"]), (6000.0, 9000.0, 7500.0))
        self.assertIn("general knowledge", r["source"])
        self.assertIn("€6,000 to €9,000", r["text"])
        self.assertEqual(len(r["parts"]), 2)
        self.assertTrue(r["no_card"])

    def test_general_estimate_refuses_nonsense(self):
        for bad in ({"what": "x", "low": 1, "high": 2, "basis": ""},                 # nothing named
                    {"what": "a car", "low": 100, "high": 5000, "basis": "used"},    # a range too wide to be useful
                    {"what": "a car", "low": -5, "high": 10, "basis": "used"},
                    {"what": "a car", "low": 1, "high": 10 ** 9, "basis": "used"}):
            with self.subTest(bad=bad):
                self.assertIn("error", self.tools.call("general_estimate", bad, self.ctx()))

    def test_the_china_question_gets_an_estimate_tied_to_the_customers_money(self):
        """The whole turn through the fake model: estimate, sum by code, answer. Nothing is removed."""
        ctx = self.ctx()
        _, data = self.coach.customer_snapshot(ctx)
        left = round(data["usual_month"]["income"] - data["usual_month"]["spending"])
        answer = ("A two-week trip to China for four would cost roughly €6,000 to €9,000, so plan on about €7,500. "
                  "That is a rough estimate. At the about €{:,} a month your usual month leaves, it is about "
                  "{} months of saving.").format(left, -(-7500 // left))
        r, fake = self.run_claude([fc.cl_call("general_estimate", EST),
                                   fc.cl_call("calculate", {"items": [{"label": "months", "expression": "7500 / %d" % left}]}),
                                   fc.cl_text(answer)], message=CHINA, ctx=self.ctx())
        self.assertEqual(r["mode"], "claude")
        self.assertEqual(r["reply"], answer)
        self.assertNotIn("notice", r)
        self.assertEqual(r["tools_used"], ["general_estimate", "calculate"])
        self.assertEqual(r["cards"], [])                    # helper tools add no card
        self.assertIn("general_estimate", [t["name"] for t in fake.requests[0]["tools"]])
        calc = [x for x in fake.requests[2]["messages"][-1]["content"] if x.get("type") == "tool_result"][0]
        self.assertNotIn("error", calc["content"])

    def test_an_amount_that_is_neither_data_nor_a_registered_estimate_is_still_removed(self):
        r, _ = self.run_claude([fc.cl_call("general_estimate", EST),
                                fc.cl_text("It would cost roughly €6,000 to €9,000. Your flights alone were €12,345 last year."),
                                fc.cl_text("It would cost roughly €6,000 to €9,000. Your flights alone were €12,345 last year.")],
                               message=CHINA)
        self.assertNotIn("12,345", r["reply"])
        self.assertIn("€6,000 to €9,000", r["reply"])
        self.assertIn("notice", r)


class CalculateTests(_Base):
    def known(self, *values):
        kn = [float(v) for v in values]
        return lambda v: abs(v) < 1 or (v == int(v) and v <= 366) or any(abs(v - k) < 0.01 for k in kn)

    def test_sums_are_done_by_code(self):
        ctx = self.ctx(calc_known=self.known(7500, 307))
        r = self.tools.call("calculate", {"items": [{"label": "months", "expression": "7500 / 307"},
                                                    {"label": "a fifth", "expression": "7,500 * 20%"},
                                                    {"label": "per person", "expression": "(7500 - 307) / 4"}]}, ctx)
        vals = {x["label"]: x for x in r["results"]}
        self.assertEqual(vals["months"]["value"], 24.43)
        self.assertEqual(vals["months"]["rounded_up"], 25.0)
        self.assertEqual(vals["a fifth"]["value"], 1500.0)
        self.assertEqual(vals["per person"]["value"], 1798.25)

    def test_an_invented_amount_is_rejected_and_code_is_never_run(self):
        ctx = self.ctx(calc_known=self.known(307))
        r = self.tools.call("calculate", {"items": [{"label": "bad", "expression": "5000 * 2"},
                                                    {"label": "evil", "expression": "__import__('os').system('x')"},
                                                    {"label": "zero", "expression": "307 / 0"},
                                                    {"label": "pow", "expression": "307 ** 99"}]}, ctx)
        for x in r["results"]:
            self.assertIn("error", x, x)
            self.assertNotIn("value", x)
        self.assertIn("general_estimate", r["results"][0]["error"])

    def test_what_counts_as_known_in_a_turn(self):
        known = self.coach._calc_known("I have 2,400 euros saved", [{"role": "assistant", "text": "It costs about €7,500."}],
                                       {"usual_month": {"difference": 307.0}},
                                       [("get_spend", {}, {"total": 92.85})])
        for v in (2400, 7500, 307, 92.85, 12, 52, 365, 0.2):
            self.assertTrue(known(v), v)
        for v in (5000, 1234.5, 99999):
            self.assertFalse(known(v), v)

    def test_a_figure_from_an_earlier_answer_may_be_used_again(self):
        """Turn two refers back to the estimate of turn one without calling a tool again."""
        hist = [{"role": "user", "text": CHINA},
                {"role": "assistant", "text": "A trip like that would cost roughly €6,000 to €9,000, so plan on about €7,500."}]
        r, _ = self.run_claude([fc.cl_text("Yes: the €7,500 for the trip is the figure to save towards.")],
                               message="so that's the number to aim for?", history=hist)
        self.assertEqual(r["reply"], "Yes: the €7,500 for the trip is the figure to save towards.")
        self.assertNotIn("notice", r)


class MoneyMathTests(_Base):
    def test_project_savings(self):
        r = self.tools.call("project_savings", {"monthly": 50, "years": 20, "annual_return_pct": 5}, self.ctx())
        self.assertEqual(r["paid_in"], 12000.0)
        self.assertEqual(r["without_return"], 12000.0)
        self.assertTrue(20000 < r["value_at_end"] < 21000, r["value_at_end"])      # 50 a month, 5 %, 20 years
        self.assertEqual(r["growth"], round(r["value_at_end"] - 12000.0, 2))
        self.assertIn("not a promise", r["text"])
        plain = self.tools.call("project_savings", {"monthly": 200, "years": 2, "target": 3000}, self.ctx())
        self.assertEqual((plain["value_at_end"], plain["months_to_target"]), (4800.0, 15))

    def test_loan_payment(self):
        r = self.tools.call("loan_payment", {"amount": 150000, "years": 25, "rate_pct": 4, "compare_rates_pct": [6]}, self.ctx())
        self.assertTrue(785 < r["monthly_payment"] < 800, r["monthly_payment"])     # the textbook annuity: 791.76
        self.assertEqual(r["total_interest"], round(r["total_paid"] - 150000, 2))
        self.assertEqual(len(r["compare"]), 1)
        self.assertGreater(r["compare"][0]["difference_per_month"], 150)
        self.assertIn("not a loan offer", r["text"])
        zero = self.tools.call("loan_payment", {"amount": 1200, "years": 1, "rate_pct": 0}, self.ctx())
        self.assertEqual((zero["monthly_payment"], zero["total_interest"]), (100.0, 0.0))


class SaveGoalTests(_Base):
    def test_a_goal_is_saved_only_after_a_complete_plan(self):
        saved = []
        ctx = self.ctx(save_goal=lambda **kw: saved.append(kw))
        r = self.tools.call("save_goal", {}, ctx)
        self.assertIn("error", r)
        self.assertEqual(saved, [])
        plan = self.tools.call("plan_goal_by_date", {"name": "China", "target": 7500, "deadline": "2027-06"}, ctx)
        self.assertNotIn("error", plan)
        r = self.tools.call("save_goal", {}, ctx)
        self.assertTrue(r["saved"])
        self.assertEqual((saved[0]["name"], saved[0]["target"], saved[0]["deadline"][:7]), ("China", 7500.0, "2027-06"))
        self.assertIn("June 2027", r["text"])
        self.assertIn("error", self.tools.call("save_goal", {}, ctx))      # the plan is used up

    def test_the_prompt_forbids_claiming_a_goal_is_saved(self):
        self.assertIn("Never say a goal is saved, set or created unless save_goal returned", self.coach.SYSTEM_PROMPT)


class FindingsTests(_Base):
    def test_the_pool_holds_ready_sentences_with_their_figures_and_stable_ids(self):
        from app import findings
        ctx = self.ctx()
        pool = findings.pool(ctx.conn, ctx.today, habit_seed=A)
        self.assertGreaterEqual(len(pool), 4)
        self.assertEqual(len({f["id"] for f in pool}), len(pool))
        for f in pool:
            self.assertTrue(f["text"].strip())
            self.assertEqual(f["figures"], findings.figures(f["text"]))
            self.assertNotRegex(f["text"], r"\d{4}-\d{2}-\d{2}|CUST|MRC-")
        again = findings.pool(self.ctx().conn, ctx.today, habit_seed=A)
        self.assertEqual([f["id"] for f in pool], [f["id"] for f in again])

    def test_what_was_told_sinks_to_the_bottom(self):
        from app import findings
        ctx = self.ctx()
        first = findings.findings(ctx.conn, ctx.today, limit=3, habit_seed=A)["findings"]
        top = first[0]["id"]
        second = findings.findings(ctx.conn, ctx.today, limit=3, exclude=[top], habit_seed=A)["findings"]
        self.assertNotEqual(second[0]["id"], top)
        self.assertFalse(any(f["said"] for f in first))

    def test_the_picture_keeps_new_findings_and_told_ones_apart(self):
        ctx = self.ctx()
        lines, data = self.coach.customer_snapshot(ctx)
        sec = data["_sections"]
        fresh = lines[sec["core"]:sec["core"] + sec["fresh"]]
        self.assertTrue(fresh)
        told_one = next(f for f in data["findings"] if any(x >= 50 for x in f["figures"]))
        amount = next(x for x in told_one["figures"] if x >= 50)
        self.coach.mark_said(ctx, "Here it is: €{:,.0f}.".format(amount), data)
        self.assertIn(told_one["id"], ctx.memory["said"])
        lines2, data2 = self.coach.customer_snapshot(ctx)
        sec2 = data2["_sections"]
        self.assertGreaterEqual(sec2["told"], 1)
        told = lines2[sec2["core"] + sec2["fresh"]:sec2["core"] + sec2["fresh"] + sec2["told"]]
        self.assertIn(told_one["text"], told)
        self.assertNotIn(told_one["text"], lines2[sec2["core"]:sec2["core"] + sec2["fresh"]])

    def test_the_model_is_shown_the_groups_under_their_own_titles(self):
        ctx = self.ctx()
        ctx.memory["said"] = ["long_view:1"]
        _, fake = self.run_claude([fc.cl_text("Hello")], message="hi", ctx=ctx)
        system = fake.requests[0]["system"][1]["text"]
        self.assertIn(self.coach.SNAPSHOT_TITLE, system)
        self.assertIn(self.coach.FINDINGS_FRESH_TITLE, system)
        self.assertIn(self.coach.FINDINGS_TOLD_TITLE, system)
        self.assertLess(system.index(self.coach.FINDINGS_FRESH_TITLE), system.index(self.coach.FINDINGS_TOLD_TITLE))
        self.assertIn("Today is", system)

    def test_get_findings_tool(self):
        r = self.tools.call("get_findings", {"limit": 3}, self.ctx())
        self.assertNotIn("error", r)
        self.assertEqual(len(r["findings"]), 3)
        self.assertTrue(r["highlights"])


class LongViewToolTests(_Base):
    def test_every_new_tool_answers_for_the_test_customers(self):
        calls = [("get_money_story", {}), ("get_season_outlook", {}), ("get_category_story", {"label": "Groceries"}),
                 ("explain_month", {}), ("get_low_points", {}), ("get_income_profile", {}),
                 ("receipt_trends", {}), ("grocery_basket_profile", {}), ("grocery_cut_ideas", {})]
        for c in fx.CUSTOMERS[:3]:
            for name, args in calls:
                with self.subTest(cid=c["cid"], tool=name):
                    r = self.tools.call(name, args, self.ctx(c["cid"]))
                    self.assertNotIn("error", r, r)
                    self.assertIn("highlights", r)
        self.assertIn("error", self.tools.call("get_category_story", {"label": "No such label"}, self.ctx()))
        self.assertIn("error", self.tools.call("explain_month", {"month": "last month"}, self.ctx()))

    def test_the_new_tools_are_declared_to_the_model(self):
        names = {t["name"] for t in self.tools.TOOLS}
        for n in ("general_estimate", "calculate", "project_savings", "loan_payment", "save_goal", "get_money_story",
                  "get_season_outlook", "get_category_story", "explain_month", "get_low_points", "get_income_profile",
                  "receipt_trends", "grocery_basket_profile", "grocery_cut_ideas", "get_findings"):
            self.assertIn(n, names)
        self.assertEqual(names, self.tools.TOOL_NAMES)
        self.assertEqual(names, set(self.tools._DISPATCH))

    def test_one_definition_of_the_usual_month(self):
        """The picture's usual month is income and spending over the same 12 full months (the long view)."""
        ctx = self.ctx()
        lines, data = self.coach.customer_snapshot(ctx)
        story = self.tools.call("get_money_story", {"months": 12}, self.ctx())
        self.assertEqual(data["usual_month"]["income"], story["per_month"]["income"])
        self.assertEqual(data["usual_month"]["spending"], story["per_month"]["spent"])
        self.assertEqual(sum(1 for x in lines if x.startswith("Their usual month")), 1)


class WordingTests(_Base):
    def test_finnish_money_is_written_the_finnish_way(self):
        f = self.coach.fi_money_format
        self.assertEqual(f("Käytit €1,107.64 ja €77.42, noin €30 kuussa."),
                         "Käytit 1 107,64 € ja 77,42 €, noin 30 € kuussa.")
        r, _ = self.run_claude([fc.cl_call("get_spend", {"period": "last_month", "label": "Taxi"}),
                                fc.cl_text("Käytit takseihin €62.10 viime kuussa.")],
                               message="Paljonko käytin takseihin viime kuussa?")
        self.assertIn("62,10 €", r["reply"])
        self.assertNotIn("notice", r)

    def test_a_follow_up_to_a_comparison_keeps_the_comparison_tools(self):
        hist = [{"role": "user", "text": "Do others my age spend more on food?"}, {"role": "assistant", "text": "Yes."}]
        _, fake = self.run_claude([fc.cl_text("Hello")], message="and on medicine?", history=hist)
        self.assertIn("get_averages", [t["name"] for t in fake.requests[0]["tools"]])
        _, fake = self.run_claude([fc.cl_text("Hello")], message="How much did I spend on taxis last month?")
        self.assertNotIn("get_averages", [t["name"] for t in fake.requests[0]["tools"]])
        self.assertIn("did not ask to be compared", fake.requests[0]["system"][1]["text"])
        for q in ("Kuluttaako muut mun ikäiset enemmän ruokaan?", "Is my grocery bill high for one person?",
                  "onko se paljon?"):
            self.assertTrue(self.coach.compare_requested(q), q)

    def test_help_goes_to_the_model_and_keeps_the_list_of_examples(self):
        r, fake = self.run_claude([fc.cl_text("I can look at where your money goes. Shall we start there?")],
                                  message="what can you do")
        self.assertEqual(fake.calls, 1)
        self.assertEqual(r["mode"], "claude")
        self.assertEqual([c["type"] for c in r["cards"]], ["help"])

    def test_a_follow_up_goes_to_the_model_when_it_is_on(self):
        ctx = self.ctx()
        r1, _ = self.run_claude([fc.cl_call("get_spend", {"period": "last_month", "label": "Taxi"}),
                                 fc.cl_text("You spent €62.10 on taxis last month.")],
                                message="How much did I spend on taxis last month?", ctx=ctx)
        hist = [{"role": "user", "text": "How much did I spend on taxis last month?"},
                {"role": "assistant", "text": r1["reply"]}]
        r2, fake = self.run_claude([fc.cl_text("The month before was about the same.")],
                                   message="and the month before?", ctx=ctx, history=hist)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(r2["mode"], "claude")


if __name__ == "__main__":
    unittest.main()
