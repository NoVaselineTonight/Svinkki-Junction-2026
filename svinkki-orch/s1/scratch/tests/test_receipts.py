"""Receipts as material for the coach: the simulated receipts, the four tools, the offline router, the model view,
the goal flow in Claude mode, the what-if validation and the demo reset.

The fixture customer A has Groceries purchases; nothing here reads the real database or reaches a model.
"""
import os as _os
import sys as _sys
import unittest
from unittest import mock

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc

A = fx.A_CID
FI_RECEIPT = """PRISMA ESPOO
Kotimaista kevytmaito 1 l 1,29
Ruispalat 330 g 2,59
Banaani kg 1,89 A
Energiajuoma 0,5 l 1,89
YHTEENSÄ 7,66
"""


def ctx_for(cid=A, **extra):
    c = fx.make_ctx(cid)
    c.cid = cid
    c.memory = {}
    for k, v in extra.items():
        setattr(c, k, v)
    return c


class ReceiptFunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import receipts
        cls.r = receipts
        cls.ctx = ctx_for()

    def test_every_receipt_adds_up_to_the_payment_to_the_cent(self):
        res = self.r.receipts(self.ctx.conn, fx.TODAY, "last_3_months", habit_seed=A, limit=100)
        self.assertGreater(res["count"], 0)
        for rc in res["receipts"]:
            cents = sum(int(round(ln["line_total"] * 100)) for ln in rc["lines"])
            self.assertEqual(cents, int(round(rc["total"] * 100)), rc["tx_id"])
            self.assertTrue(rc["simulated"])
        self.assertIn("Simulated", res["note"])

    def test_receipts_are_deterministic(self):
        a = self.r.receipts(self.ctx.conn, fx.TODAY, "last_3_months", habit_seed=A, limit=100)
        b = self.r.receipts(self.ctx.conn, fx.TODAY, "last_3_months", habit_seed=A, limit=100)
        self.assertEqual(a, b)

    def test_insight_groups_add_up_to_the_total(self):
        res = self.r.receipt_insights(self.ctx.conn, fx.TODAY, "last_3_months", habit_seed=A)
        self.assertGreater(res["receipt_count"], 0)
        self.assertAlmostEqual(sum(g["total"] for g in res["by_group"]), res["total"], places=2)

    def test_product_habit_known_and_unknown(self):
        res = self.r.product_habit(self.ctx.conn, fx.TODAY, "milk", "last_3_months", habit_seed=A)
        self.assertIsNotNone(res["matched"])
        self.assertIn("milk", res["text"])
        none = self.r.product_habit(self.ctx.conn, fx.TODAY, "zorblax", "last_3_months", habit_seed=A)
        self.assertIsNone(none["matched"])
        self.assertIn("could not match", none["text"])

    def test_parse_finnish_receipt(self):
        res = self.r.parse_receipt_text(FI_RECEIPT)
        self.assertEqual(res["store"], "Prisma")
        self.assertEqual(len(res["lines"]), 4)
        self.assertEqual(res["total"], 7.66)
        self.assertEqual(res["lines_total"], 7.66)
        self.assertTrue(res["matches_total"])

    def test_parse_too_short_text_is_refused(self):
        with self.assertRaises(ValueError):
            self.r.parse_receipt_text("maito")


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.tools as tools
        cls.tools = tools
        cls.ctx = ctx_for()

    def test_get_receipts(self):
        res = self.tools.call("get_receipts", {"period": "last_3_months", "limit": 2}, self.ctx)
        self.assertEqual(res["card"], "receipts")
        self.assertLessEqual(len(res["receipts"]), 2)
        self.assertGreater(res["count"], 0)

    def test_get_receipts_bad_input_is_an_error_not_a_traceback(self):
        for bad in ({"limit": 99}, {"limit": "x"}, {"period": "someday"}):
            res = self.tools.call("get_receipts", bad, self.ctx)
            self.assertEqual(res["card"], "error", bad)
            self.assertIn("error", res)

    def test_receipt_insights(self):
        res = self.tools.call("receipt_insights", {}, self.ctx)
        self.assertEqual(res["card"], "receipt_insights")
        self.assertTrue(res["highlights"])

    def test_product_habit(self):
        res = self.tools.call("product_habit", {"query": "coffee"}, self.ctx)
        self.assertEqual(res["card"], "product_habit")
        for bad in ({}, {"query": "x"}, {"query": "y" * 41}, {"query": 5}):
            self.assertEqual(self.tools.call("product_habit", bad, self.ctx)["card"], "error", bad)

    def test_read_receipt_reads_no_transactions(self):
        ctx = ctx_for(conn=fx.closed_conn())          # a closed connection would fail if it were touched
        res = self.tools.call("read_receipt", {"text": FI_RECEIPT}, ctx)
        self.assertEqual(res["card"], "receipt_parsed")
        self.assertEqual(res["total"], 7.66)
        for bad in ({"text": "short"}, {"text": "x" * 8001}, {}):
            self.assertEqual(self.tools.call("read_receipt", bad, ctx)["card"], "error")

    def test_tools_are_declared(self):
        names = {t["name"] for t in self.tools.TOOLS}
        self.assertTrue({"get_receipts", "receipt_insights", "product_habit", "read_receipt"} <= names)
        for t in self.tools.TOOLS:
            if t["name"] in ("get_receipts", "receipt_insights", "product_habit"):
                self.assertIn("simulated", t["description"].lower())


class ModelViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach
        cls.coach = coach

    def test_model_view_of_receipts_is_small_the_card_keeps_everything(self):
        line = {"name": "Maito", "group": "dairy", "qty": 1, "unit": "kpl", "unit_price": 1.0, "line_total": 1.0}
        rcs = [{"tx_id": 100 + i, "store": "Prisma", "d": "2026-08-%02d" % (i + 1), "total": 20.0,
                "lines": [dict(line) for _ in range(20)], "simulated": True} for i in range(9)]
        res = {"card": "receipts", "count": 9, "shown": 9, "total": 180.0, "receipts": rcs, "note": "n",
               "evidence": [{"title": "x"}]}
        view = self.coach._model_view(res)
        self.assertEqual(len(view["receipts"]), 5)
        self.assertEqual(view["receipts_left_out"], 4)
        self.assertTrue(all(len(r["lines"]) == 12 and r["lines_left_out"] == 8 for r in view["receipts"]))
        self.assertNotIn("card", view)
        self.assertEqual(len(res["receipts"]), 9)
        self.assertEqual(len(res["receipts"][0]["lines"]), 20)

    def test_merchant_id_in_text_is_masked_and_no_doubled_wording(self):
        out = self.coach.anonymise({"note": "paid MRC-ABC123 here"})
        self.assertNotIn("MRC-ABC123", out["note"])
        out = self.coach.anonymise({"note": "your postal area 00510 is in your area"})
        self.assertNotIn("your your", out["note"])


class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach
        cls.coach = coach
        cls.ctx = ctx_for()

    def tool(self, q):
        r = self.coach.route(q, self.ctx)
        return r[0] if r else None

    def test_receipt_questions_english(self):
        cases = {
            "show my receipts": "get_receipts", "my last receipt": "get_receipts",
            "what did I buy at Prisma": "get_receipts", "show my grocery receipts for last month": "get_receipts",
            "what do I buy most": "receipt_insights", "what is in my shopping basket": "receipt_insights",
            "analyse my receipts": "receipt_insights", "where does my grocery money go": "receipt_insights",
            "how much do I spend on treats": "receipt_insights",
            "how much do I spend on energy drinks": "product_habit", "how often do I buy coffee": "product_habit",
            "how much beer do I buy": "product_habit", "how much do I spend on sweets": "product_habit",
            "how much do I spend on milk": "product_habit", "how much do I spend on candy": "product_habit",
        }
        for q, tool in cases.items():
            self.assertEqual(self.tool(q), tool, q)

    def test_receipt_questions_finnish(self):
        cases = {"näytä kuittini": "get_receipts", "mitä ostin Prismasta": "get_receipts",
                 "mitä ostan eniten": "receipt_insights", "analysoi kuittini": "receipt_insights",
                 "paljonko käytän energiajuomiin": "product_habit", "kuinka usein ostan kahvia": "product_habit"}
        for q, tool in cases.items():
            r = self.coach.route(q, self.ctx)
            self.assertEqual(r[0], tool, q)
            self.assertEqual(r[2].get("lang"), "fi", q)

    def test_query_and_period_are_passed(self):
        r = self.coach.route("how much do I spend on energy drinks", self.ctx)
        self.assertIn("energy", r[1]["query"])
        r = self.coach.route("show my grocery receipts for last month", self.ctx)
        self.assertEqual(r[1].get("period"), "last_month")
        self.assertEqual(self.coach.route("my last receipt", self.ctx)[1].get("limit"), 1)

    def test_spending_labels_still_go_to_get_spend(self):
        for q in ("How much did I spend on taxis last month?", "How much did I spend on groceries last month?",
                  "How much did I spend on restaurants last month?", "How much did I spend on bars last night?"):
            self.assertEqual(self.tool(q), "get_spend", q)
        self.assertEqual(self.tool("Show me my three baskets"), "get_baskets")

    def test_unknown_product_does_not_become_a_product_question(self):
        self.assertNotEqual(self.tool("how much do I spend on zorblax"), "product_habit")

    def test_pasted_receipts(self):
        for q in ("Receipt:\n" + FI_RECEIPT, "kuitti: " + FI_RECEIPT, "read this receipt\n" + FI_RECEIPT, FI_RECEIPT):
            r = self.coach.route(q, self.ctx)
            self.assertEqual(r[0], "read_receipt", q[:20])
            self.assertIn("PRISMA", r[1]["text"].upper())
        self.assertEqual(self.coach.route("receipt:", self.ctx)[2].get("ask_receipt"), True)
        self.assertNotEqual(self.tool("milk 1,29\nbread 2,59"), "read_receipt")      # fewer than 3 lines

    def test_help_questions_route_and_group_exists(self):
        for lang in ("en", "fi"):
            groups = self.coach.help_groups(lang)
            g = [x for x in groups if x["title"] in ("My receipts", "Kuittini")]
            self.assertEqual(len(g), 1, lang)
            self.assertEqual(len(g[0]["items"]), 3)
            for it in g[0]["items"]:
                self.assertIn(self.tool(it["question"]), ("get_receipts", "receipt_insights", "product_habit"),
                              it["question"])
        help_card = self.coach.help_turn("help")["cards"][0]["data"]["groups"]
        self.assertTrue(any(x["title"] == "My receipts" for x in help_card))


class ReplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach
        cls.coach = coach

    def ask(self, q):
        ctx = ctx_for()
        out = self.coach.chat(q, [], ctx)
        results = [c["data"] for c in out["cards"]]
        return out, results

    def test_built_in_replies_pass_the_number_check(self):
        for q in ("how often do I buy milk", "show my receipts", "what do I buy most",
                  "Receipt:\n" + FI_RECEIPT, "how much do I spend on zorblax"):
            out, results = self.ask(q)
            for strict in (False, True):
                self.assertTrue(self.coach.numbers_grounded(out["reply"], results, q, strict=strict),
                                (q[:20], strict, out["reply"], self.coach.ungrounded_spans(out["reply"], results, q, strict)))

    def test_replies_are_short_and_say_simulated(self):
        out, _ = self.ask("show my receipts")
        self.assertIn("simulated", out["reply"])
        out, _ = self.ask("how often do I buy milk")
        self.assertIn("simulated", out["reply"])
        out, _ = self.ask("Receipt:\n" + FI_RECEIPT)
        self.assertNotIn("simulated", out["reply"])
        self.assertIn("4 lines from Prisma", out["reply"])

    def test_receipt_that_does_not_add_up_says_so(self):
        bad = FI_RECEIPT.replace("7,66", "9,99")
        out, _ = self.ask("Receipt:\n" + bad)
        self.assertIn("do not add up", out["reply"])

    def test_pasted_receipt_never_reaches_the_model(self):
        fake = fc.FakeClaude([fc.cl_text("should not be used")])
        ctx = ctx_for()
        with fc.patched_claude(fake):
            out = self.coach.chat("Receipt:\n" + FI_RECEIPT, [], ctx)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(out["tools_used"], ["read_receipt"])
        self.assertEqual(out["history_user"][:16], "[pasted receipt,")


class GoalFlowClaudeTests(unittest.TestCase):
    """The model may ask for the price in plain text without calling plan_goal_by_date: nothing was then kept for
    the next turn. The coach now rebuilds the pending goal from the last exchange."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach
        cls.coach = coach

    def run_flow(self, script):
        ctx = ctx_for()
        fake = fc.FakeClaude(script)
        q1 = "I want to go to Japan in 2027"
        with fc.patched_claude(fake):
            r1 = self.coach.chat(q1, [], ctx)
            hist = [{"role": "user", "content": q1}, {"role": "assistant", "content": r1["reply"]}]
            before = fake.calls
            r2 = self.coach.chat("3000", hist, ctx)
        return r1, r2, fake.calls - before

    def test_text_only_question_then_amount_gives_the_plan(self):
        ask = "That sounds great. Roughly how much do you think the trip will cost?"
        r1, r2, calls = self.run_flow([fc.cl_text(ask)])
        self.assertEqual(r1["mode"], "claude")
        self.assertEqual(r2["tools_used"], ["plan_goal_by_date"])
        self.assertEqual(calls, 0)
        self.assertIn("Japan", r2["reply"])

    def test_tool_call_question_then_amount_gives_the_plan(self):
        ask = "Roughly how much do you think it will cost?"
        r1, r2, _ = self.run_flow([fc.cl_call("plan_goal_by_date", {"name": "Japan", "deadline": "2027"}),
                                   fc.cl_text(ask)])
        self.assertEqual(r2["tools_used"], ["plan_goal_by_date"])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_what_if_pct_out_of_range_is_400(self):
        c = fx.session(self.server, "A")
        for pct in (150, -10, 100.5):
            r = c.post("/api/what-if", {"changes": [{"target": "Taxi", "pct": pct}]})
            self.assertEqual(r.status, 400, pct)
        r = c.post("/api/what-if", {"changes": [{"target": "Taxi", "pct": 20}]})
        self.assertEqual(r.status, 200, r.text)

    def test_bad_period_and_month_are_400_not_500(self):
        c = fx.session(self.server, "A")
        self.assertEqual(c.get("/api/baskets?period=nonsense").status, 400)
        self.assertEqual(c.get("/api/overview?month=nonsense").status, 400)

    def test_chat_over_http_returns_a_receipts_card(self):
        c = fx.session(self.server, "A")
        r = c.post("/api/chat", {"message": "show my receipts"})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json["tools_used"], ["get_receipts"])
        self.assertEqual(r.json["cards"][0]["type"], "receipts")

    def test_demo_reset_ends_every_session_and_forgets_consent(self):
        c1 = fx.session(self.server, "A")
        c2 = fx.session(self.server, "B")
        self.assertEqual(c1.get("/api/me").status, 200)
        r = c1.post("/api/demo/reset", {})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json, {"ok": True})
        self.assertEqual(c1.get("/api/me").status, 401, "the caller's old cookie is dead")
        self.assertEqual(c2.get("/api/me").status, 401, "so is every other session")
        fresh = self.server.client()
        fx.login_as(fresh, fx.A_NAME)
        me = fresh.get("/api/me")
        self.assertEqual(me.status, 200)
        consent = (me.json.get("consent") or {})
        self.assertFalse(consent.get("analysis"), me.text)

    def test_demo_reset_needs_a_session(self):
        self.assertEqual(self.server.client().post("/api/demo/reset", {}).status, 401)


if __name__ == "__main__":
    unittest.main()
