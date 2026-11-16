"""A goal planned with a date keeps the date: stored, shown under Your things, kept when the goal is edited,
and known to the coach."""
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx


class GoalDeadlineStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        import app.state as state
        cls.state = state

    def setUp(self):
        self.state.reset_all()

    def test_deadline_and_monthly_amount_are_stored(self):
        self.state.set_goal(fx.A_CID, {"name": "Japan", "target": 3000, "saved": 0, "deadline": "2027-06",
                                       "monthly_needed": 334})
        g = self.state.get_goal(fx.A_CID)
        self.assertEqual(g["deadline"], "2027-06")
        self.assertEqual(g["monthly_needed"], 334)

    def test_goal_without_a_date_looks_as_before(self):
        self.state.set_goal(fx.A_CID, {"name": "Buffer", "target": 1000, "saved": 50})
        self.assertEqual(self.state.get_goal(fx.A_CID), {"name": "Buffer", "target": 1000.0, "saved": 50.0})

    def test_a_bad_date_is_refused(self):
        for bad in ("June 2027", "2027", "2027-13", "2027-06-40", 202706, "2027-06; DROP TABLE goal"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.state.set_goal(fx.A_CID, {"name": "Japan", "target": 3000, "deadline": bad})
        self.assertIsNone(self.state.get_goal(fx.A_CID))

    def test_a_full_day_is_accepted(self):
        self.state.set_goal(fx.A_CID, {"name": "Japan", "target": 3000, "deadline": "2027-06-30"})
        self.assertEqual(self.state.get_goal(fx.A_CID)["deadline"], "2027-06-30")


class GoalDeadlineHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()
        import app.state as state
        cls.state = state

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.state.reset_all()
        self.a = fx.session(self.server, "A")

    def say(self, msg, conv=None):
        body = {"message": msg}
        if conv:
            body["conversation_id"] = conv
        r = self.a.post("/api/chat", body)
        self.assertEqual(r.status, 200, r.text[:200])
        return r.json

    def test_goal_saved_in_chat_shows_its_date_on_the_start_page_and_survives_an_edit(self):
        r1 = self.say("I am saving 3000 euros for Japan by June 2027")
        r2 = self.say("yes, save it", r1["conversation_id"])
        self.assertIn("Saved", r2["reply"])
        g = self.a.get("/api/goal").json["goal"]
        self.assertEqual(g["deadline"][:7], "2027-06")
        self.assertGreater(g["monthly_needed"], 0)
        things = self.a.get("/api/home").json["things"]
        goal = next(t for t in things if t["kind"] == "goal")
        self.assertIn("by June 2027", goal["summary"])
        self.assertNotRegex(goal["summary"], r"\d{4}-\d{2}")
        # editing the name and the amounts in Your things keeps the date
        r = self.a.post("/api/goal", {"name": "Japan trip", "target": 3500, "saved": 100})
        self.assertEqual(r.status, 200)
        g2 = self.a.get("/api/goal").json["goal"]
        self.assertEqual((g2["name"], g2["target"], g2["saved"], g2["deadline"]), ("Japan trip", 3500.0, 100.0, g["deadline"]))
        self.assertNotIn("monthly_needed", g2, "the old monthly amount does not fit the new target")
        # a rename alone keeps the monthly amount
        self.a.post("/api/goal", {"name": "Japan", "target": 3500, "saved": 100, "monthly_needed": 350})
        self.a.post("/api/goal", {"name": "Japan 2027", "target": 3500, "saved": 100})
        self.assertEqual(self.a.get("/api/goal").json["goal"]["monthly_needed"], 350)

    def test_goal_made_in_the_editor_has_no_date_and_no_by_text(self):
        self.assertEqual(self.a.post("/api/goal", {"name": "Buffer", "target": 1000}).status, 200)
        goal = next(t for t in self.a.get("/api/home").json["things"] if t["kind"] == "goal")
        self.assertNotIn(" by ", goal["summary"])

    def test_a_bad_date_from_the_client_is_a_400(self):
        r = self.a.post("/api/goal", {"name": "Japan", "target": 3000, "deadline": "soon"})
        self.assertEqual(r.status, 400)


class GoalDeadlineCoachTests(unittest.TestCase):
    def test_the_coach_is_told_the_date_in_words(self):
        fx.get()
        import app.coach as coach
        ctx = fx.make_ctx(fx.A_CID)
        ctx.goal = {"name": "Japan", "target": 3000.0, "saved": 0.0, "deadline": "2027-06"}
        lines, data = coach.customer_snapshot(ctx)
        text = "\n".join(lines)
        self.assertIn("Japan, target €3,000, nothing set aside so far, by June 2027", text)
        self.assertEqual(data["goal"]["deadline"], "2027-06")

    def test_the_goal_view_shows_the_date(self):
        with open(_os.path.join(fx.REPO, "web", "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("['By', fmtMonth(String(g.deadline).slice(0, 7))]", js)


if __name__ == "__main__":
    unittest.main()
