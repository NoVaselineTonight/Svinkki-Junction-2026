"""Savings plans, home-page widgets, next steps and the request language (Contract C)."""
import os as _os
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx

fx.get()
from app import plans  # noqa: E402

TODAY = "2026-09-24"


class PreviewMaths(unittest.TestCase):
    def test_deadline_gives_monthly(self):
        p = plans.preview(1200, deadline="2027-09-24", today=TODAY)
        self.assertEqual(p["months_left"], 12)
        self.assertEqual(p["monthly"], 100.0)
        self.assertEqual(p["deadline"], "2027-09-24")
        self.assertLessEqual(len(p["series"]), 36)
        self.assertEqual(p["series"][-1]["planned"], 1200.0)
        self.assertEqual(p["series"][0]["actual"], 0.0)

    def test_monthly_gives_deadline(self):
        p = plans.preview(1000, monthly=300, today=TODAY)
        self.assertEqual(p["months_left"], 4)
        self.assertEqual(p["deadline"], "2027-01-24")
        self.assertEqual(p["series"][-1]["planned"], 1000.0)

    def test_saved_and_status(self):
        self.assertEqual(plans.preview(1000, monthly=100, today=TODAY, saved=1000)["status"], "done")
        self.assertEqual(plans.preview(1000, monthly=100, today=TODAY)["status"], "not_started")
        # twelve months to go at 100 a month with only 100 saved of 1200: behind
        p = plans.preview(1200, monthly=100, deadline="2027-03-24", today=TODAY, saved=100)
        self.assertEqual(p["status"], "behind")      # the plan was made at 100 a month; 6 months left
        self.assertEqual(p["monthly"], 184.0)        # what it takes now
        self.assertEqual(plans.preview(1200, monthly=100, deadline="2027-09-24", today=TODAY,
                                       saved=900)["status"], "ahead")
        self.assertEqual(plans.preview(1200, deadline="2027-09-24", today=TODAY, saved=600)["status"], "on_track")

    def test_fits_and_note(self):
        p = plans.preview(1200, monthly=100, today=TODAY, usual_leftover=300)
        self.assertTrue(p["fits"])
        self.assertIn("third", p["note"])
        self.assertIn("kolmannes", p["note_fi"])
        self.assertFalse(plans.preview(1200, monthly=400, today=TODAY, usual_leftover=300)["fits"])
        self.assertIsNone(plans.preview(1200, monthly=100, today=TODAY)["fits"])

    def test_validation(self):
        for kw in ({"target": 0, "monthly": 10}, {"target": 2_000_000, "monthly": 10},
                   {"target": 100, "monthly": 0}, {"target": 100, "deadline": "2026-01-01"},
                   {"target": 100}, {"target": "x", "monthly": 5}, {"target": 100, "monthly": 1e-9},
                   {"target": 1_000_000, "monthly": 1}):
            with self.assertRaises(ValueError, msg=str(kw)):
                plans.preview(today=TODAY, **kw)

    def test_long_plan_is_thinned(self):
        p = plans.preview(100000, monthly=300, today=TODAY)
        self.assertLessEqual(len(p["series"]), 36)
        self.assertEqual(p["series"][-1]["planned"], 100000.0)

    def test_next_move(self):
        p = plans.preview(1000, monthly=100, today=TODAY, can_move=250)
        self.assertEqual(p["next_move"]["amount"], 100.0)
        self.assertTrue(p["next_move"]["ok"])
        self.assertFalse(plans.preview(1000, monthly=100, today=TODAY, can_move=2)["next_move"]["ok"])


class _Base(unittest.TestCase):
    PER_VISITOR = False

    @classmethod
    def setUpClass(cls):
        fx.use_fresh_state()
        import app.server as server
        cls.srv_mod = server
        cls.old = server.PER_VISITOR_STATE
        server.PER_VISITOR_STATE = cls.PER_VISITOR
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.srv_mod.PER_VISITOR_STATE = cls.old

    def setUp(self):
        import app.state as state
        state.reset_all()
        self.c = fx.session(self.server, "A")


class WidgetsApi(_Base):
    def test_empty_then_goal_is_first_widget(self):
        r = self.c.get("/api/widgets")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json["widgets"], [])
        self.assertIn("plan", r.json["can_add"])
        self.c.post("/api/goal", {"name": "Trip", "target": 900, "saved": 100})
        ws = self.c.get("/api/widgets").json["widgets"]
        self.assertEqual(ws[0]["id"], "goal")
        self.assertEqual(ws[0]["type"], "plan")
        self.assertGreater(ws[0]["data"]["target"], 0)
        self.assertEqual(ws[0]["data"]["saved"], 100)

    def test_create_plan_becomes_goal_then_extra(self):
        r = self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Bike", "target": 600, "monthly": 100}})
        self.assertEqual(r.status, 200, r.text[:200])
        self.assertEqual(r.json["widget"]["id"], "goal")
        g = self.c.get("/api/goal").json["goal"]
        self.assertEqual((g["name"], g["target"], g["monthly_needed"]), ("Bike", 600, 100))
        self.assertIn("Bike", self.c.get("/api/home").text)
        r = self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Laptop", "target": 1200,
                                                                    "deadline": "2027-09-24"}})
        wid = r.json["widget"]["id"]
        self.assertRegex(wid, r"^w\d+$")
        self.assertEqual(r.json["widget"]["data"]["monthly"], 100.0)
        ws = self.c.get("/api/widgets").json["widgets"]
        self.assertEqual([w["id"] for w in ws], ["goal", wid])

    def test_update_and_remove(self):
        self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Bike", "target": 600, "monthly": 100}})
        r = self.c.post("/api/widgets/update", {"id": "goal", "params": {"name": "Road bike", "target": 800,
                                                                          "monthly": 200}})
        self.assertEqual(r.status, 200, r.text[:200])
        self.assertEqual(r.json["widget"]["data"]["target"], 800)
        self.assertEqual(self.c.get("/api/goal").json["goal"]["name"], "Road bike")
        w = self.c.post("/api/widgets", {"type": "plan", "params": {"name": "X", "target": 300,
                                                                    "monthly": 50}}).json["widget"]
        r = self.c.post("/api/widgets/update", {"id": w["id"], "params": {"target": 500}})
        self.assertEqual(r.json["widget"]["data"]["target"], 500)
        self.assertEqual(self.c.post("/api/widgets/remove", {"id": w["id"]}).json, {"ok": True})
        self.assertEqual(self.c.post("/api/widgets/remove", {"id": w["id"]}).status, 404)
        self.assertEqual(self.c.post("/api/widgets/remove", {"id": "goal"}).json, {"ok": True})
        self.assertIsNone(self.c.get("/api/goal").json["goal"])

    def test_other_widgets_and_limits(self):
        for t in ("safe", "baskets"):
            r = self.c.post("/api/widgets", {"type": t})
            self.assertEqual(r.status, 200, r.text[:300])
            self.assertEqual(r.json["widget"]["type"], t)
            self.assertEqual(self.c.post("/api/widgets", {"type": t}).status, 400)
        r = self.c.post("/api/widgets", {"type": "category", "params": {"label": "Groceries", "limit": 400}})
        self.assertEqual(r.status, 200, r.text[:300])
        d = r.json["widget"]["data"]
        self.assertEqual(d["limit"], 400)
        self.assertTrue(d["caption"] and d["caption_fi"])
        self.assertEqual(self.c.post("/api/widgets", {"type": "category", "params": {"label": "Salary"}}).status, 400)
        can = self.c.get("/api/widgets").json["can_add"]
        self.assertNotIn("safe", can)
        self.assertIn("category", can)
        for i in range(5):
            self.c.post("/api/widgets", {"type": "category", "params": {"label": "Taxi"}})
        self.assertEqual(self.c.post("/api/widgets", {"type": "category", "params": {"label": "Fuel"}}).status, 400)
        self.assertEqual(self.c.get("/api/widgets").json["can_add"], [])

    def test_bad_plans(self):
        for params in ({"name": "", "target": 100, "monthly": 10}, {"name": "a", "target": -5, "monthly": 10},
                       {"name": "a", "target": 100}, {"name": "a", "target": 100, "deadline": "2020-01-01"}):
            self.assertEqual(self.c.post("/api/widgets", {"type": "plan", "params": params}).status, 400)

    def test_preview_saves_nothing(self):
        r = self.c.post("/api/plan/preview", {"name": "Trip", "target": 900, "monthly": 100})
        self.assertEqual(r.status, 200, r.text[:200])
        for k in ("fits", "note", "note_fi", "series", "monthly", "deadline", "next_move"):
            self.assertIn(k, r.json)
        self.assertIsNone(self.c.get("/api/goal").json["goal"])
        self.assertEqual(self.c.post("/api/plan/preview", {"target": 0, "monthly": 5}).status, 400)

    def test_move_goal_confirm_grows_saved(self):
        self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Bike", "target": 600, "monthly": 100}})
        avail = self.c.get("/api/money").json["available"]
        if avail < 10:
            self.skipTest("nothing safe to move for this persona today")
        bal0 = self.c.get("/api/account").json["current"]["balance"]
        r = self.c.post("/api/widgets/move", {"id": "goal", "amount": 10})
        self.assertTrue(r.json["ok"], r.text[:200])
        p = r.json["proposal"]
        self.assertEqual(p["widget_id"], "goal")
        r = self.c.post("/api/money/confirm", {"proposal_id": p["id"], "approve": True, "amount": p["amount"],
                                               "dest": p["dest"]})
        self.assertTrue(r.json["moved"])
        d = self.c.get("/api/widgets").json["widgets"][0]["data"]
        self.assertEqual(d["saved"], 10)
        self.assertEqual(self.c.get("/api/goal").json["goal"]["saved"], 10)
        self.assertAlmostEqual(self.c.get("/api/account").json["current"]["balance"], bal0 - 10, places=2)
        self.assertEqual(self.c.post("/api/widgets/move", {"id": "w999", "amount": 10}).status, 404)

    def test_move_extra_plan(self):
        self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Bike", "target": 600, "monthly": 100}})
        w = self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Laptop", "target": 900,
                                                                    "monthly": 100}}).json["widget"]
        if self.c.get("/api/money").json["available"] < 10:
            self.skipTest("nothing safe to move for this persona today")
        p = self.c.post("/api/widgets/move", {"id": w["id"], "amount": 10}).json["proposal"]
        self.c.post("/api/money/confirm", {"proposal_id": p["id"], "approve": True, "amount": p["amount"],
                                           "dest": p["dest"]})
        ws = self.c.get("/api/widgets").json["widgets"]
        self.assertEqual(ws[1]["data"]["saved"], 10)
        self.assertEqual(ws[0]["data"]["saved"], 0)

    def test_money_propose_defaults_to_savings(self):
        if self.c.get("/api/money").json["available"] < 10:
            self.skipTest("nothing safe to move")
        r = self.c.post("/api/money/propose", {"amount": 10})
        self.assertTrue(r.json["ok"], r.text[:200])
        self.assertEqual(r.json["proposal"]["dest"], "savings")
        self.assertEqual(self.c.post("/api/money/propose", {"dest": "elsewhere", "amount": 10}).status, 400)


class NextSteps(_Base):
    def test_without_goal(self):
        r = self.c.get("/api/next-steps")
        self.assertEqual(r.status, 200, r.text[:300])
        steps = r.json["steps"]
        self.assertLessEqual(len(steps), 3)
        kinds = [s["kind"] for s in steps]
        self.assertIn("start_plan", kinds)
        s0 = steps[0]
        for k in ("id", "kind", "title", "title_fi", "why", "why_fi", "figure", "action"):
            self.assertIn(k, s0)
        self.assertEqual(s0["action"]["type"], "create_widget")
        self.assertEqual(s0["action"]["widget"]["params"]["name"], "Buffer")
        fi = self.c.get("/api/next-steps", headers={"X-Svinkki-Lang": "fi"}).json["steps"][0]
        self.assertEqual(fi["action"]["widget"]["params"]["name"], "Puskuri")
        # creating the plan makes the step go away
        self.c.post("/api/widgets", s0["action"]["widget"])
        self.assertNotIn("start_plan", [s["kind"] for s in self.c.get("/api/next-steps").json["steps"]])

    def test_with_goal_moves_carry_widget_id(self):
        self.c.post("/api/goal", {"name": "Trip", "target": 5000, "saved": 0})
        for s in self.c.get("/api/next-steps").json["steps"]:
            self.assertNotEqual(s["kind"], "start_plan")
            if s["action"]["type"] == "move":
                self.assertEqual(s["action"]["widget_id"], "goal")

    def test_dismiss(self):
        first = self.c.get("/api/next-steps").json["steps"]
        self.assertTrue(first)
        self.assertEqual(self.c.post("/api/next-steps/dismiss", {"id": first[0]["id"]}).json, {"ok": True})
        again = [s["id"] for s in self.c.get("/api/next-steps").json["steps"]]
        self.assertNotIn(first[0]["id"], again)
        self.assertEqual(self.c.post("/api/next-steps/dismiss", {}).status, 400)

    def test_suggestions_off(self):
        c = fx.session(self.server, "A", suggestions=False)
        self.assertEqual(c.get("/api/next-steps").json["steps"], [])


class Tool(unittest.TestCase):
    def test_propose_plan_saves_nothing(self):
        ctx = fx.make_ctx()
        res = plans.call("propose_plan", {"name": "Trip", "target": 1200, "monthly": 100}, ctx)
        self.assertEqual(res["card"], "plan_offer")
        self.assertEqual(res["months"], 12)
        self.assertEqual(res["widget"]["type"], "plan")
        self.assertEqual(res["widget"]["params"]["name"], "Trip")
        self.assertIn("note_fi", res)
        self.assertEqual(plans.call("propose_plan", {"name": "x", "target": -1}, ctx)["card"], "error")
        self.assertIn("propose_plan", plans.TOOL_NAMES)


class PerVisitor(_Base):
    PER_VISITOR = True

    def test_widgets_are_private(self):
        b = fx.session(self.server, "A")
        self.c.post("/api/widgets", {"type": "plan", "params": {"name": "Secret", "target": 500, "monthly": 50}})
        self.c.post("/api/widgets", {"type": "safe"})
        self.assertEqual(b.get("/api/widgets").json["widgets"], [])
        self.assertNotIn("Secret", b.get("/api/widgets").text)
        self.assertEqual(len(self.c.get("/api/widgets").json["widgets"]), 2)


class Lang(_Base):
    def test_lang_header_reaches_ctx(self):
        import app.coach as coach
        seen = []
        orig = coach.chat

        def spy(msg, history, ctx):
            seen.append(getattr(ctx, "ui_lang", None))
            return orig(msg, history, ctx)
        coach.chat = spy
        try:
            self.c.post("/api/chat", {"message": "hello"}, headers={"X-Svinkki-Lang": "fi"})
            self.c.post("/api/chat", {"message": "hello"})
            self.c.post("/api/chat", {"message": "hello", "lang": "fi"})
        finally:
            coach.chat = orig
        self.assertEqual(seen, ["fi", "en", "fi"])


if __name__ == "__main__":
    unittest.main()
