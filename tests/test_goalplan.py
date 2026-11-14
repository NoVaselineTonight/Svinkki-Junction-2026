"""make_savings_plan: a concrete, personal savings plan decided by code (owner's request, 14 Nov)."""
import unittest

from app import coach, goalplan

TODAY = "2026-09-26"


class FakeCtx:
    """goalplan.picture is replaced in these tests, so no database connection is needed."""
    def __init__(self, conn):
        self.conn, self.today, self.goal = conn, TODAY, None


class PlanDecisionTests(unittest.TestCase):
    def setUp(self):
        self._pic = goalplan.picture

    def tearDown(self):
        goalplan.picture = self._pic

    def use(self, leftover, cats, saving=0.0, spent=2000.0):
        goalplan.picture = lambda conn, t: {"months": 6, "income": spent + leftover, "spent": spent,
                                            "already_saving": saving, "leftover": leftover,
                                            "categories": sorted(cats.items(), key=lambda kv: -kv[1])}

    def test_car_without_price_gets_an_estimate_cuts_and_a_date(self):
        self.use(12.0, {"Housing": 900, "Clothing": 103, "Hobbies": 103, "Taxi": 39, "Entertainment": 67})
        r = goalplan.build(None, TODAY, "car")
        self.assertEqual(r["target"], 8000)
        self.assertTrue(r["estimate"])
        labels = [c["label"] for c in r["cuts"]]
        self.assertIn("Clothing", labels)
        self.assertIn("Taxi", labels)
        self.assertNotIn("Housing", labels)              # essentials are never cut
        self.assertGreater(r["monthly"], 0)
        self.assertEqual(r["monthly"], round(r["monthly"]))
        self.assertTrue(r["months"] and r["deadline"])
        self.assertIn("My plan: put", r["decision"])
        self.assertIn("clothes", r["decision"])
        self.assertIn("auto", r["decision_fi"])
        self.assertTrue(r["cheaper"])                     # a long plan offers the cheaper car
        self.assertEqual(r["widget"]["type"], "plan")

    def test_big_leftover_needs_no_cuts(self):
        self.use(2000.0, {"Restaurant": 400})
        r = goalplan.build(None, TODAY, "car")
        self.assertEqual(r["cuts"], [])
        self.assertEqual(r["monthly"], 1600)            # 80 % of the leftover, the rest is a margin
        self.assertEqual(r["months"], 5)

    def test_a_date_that_fits_uses_only_what_it_needs(self):
        self.use(2000.0, {"Restaurant": 400})
        r = goalplan.build(None, TODAY, "Japan", target=3000, deadline="2027-06")
        self.assertTrue(r["fits"])
        self.assertEqual(r["monthly"], 334)
        self.assertTrue(r["decision"].startswith("Yes"))
        self.assertIn("€334 of what you usually have left (last 6 months)", r["decision"])

    def test_a_date_that_does_not_fit_gives_the_realistic_one(self):
        self.use(-80.0, {"Restaurant": 257, "Fast food": 148})
        r = goalplan.build(None, TODAY, "car", deadline="2027-06")
        self.assertFalse(r["fits"])
        self.assertIn("more than your money can carry", r["decision"])
        self.assertIn("cover that first", r["decision"])
        self.assertGreater(r["months"], 9)

    def test_unknown_goal_without_price_asks_the_model_for_an_estimate(self):
        self.use(500.0, {})
        r = goalplan.build(None, TODAY, "pony")
        self.assertIn("estimate", r["error"])
        r = goalplan.build(None, TODAY, "pony", estimate=2500)
        self.assertEqual(r["target"], 2500)

    def test_tool_call_returns_a_plan_offer_card(self):
        self.use(300.0, {"Restaurant": 200})
        r = goalplan.call("make_savings_plan", {"goal": "sofa"}, FakeCtx(None))
        self.assertEqual(r["card"], "plan_offer")
        self.assertEqual(goalplan.call("make_savings_plan", {}, FakeCtx(None))["card"], "error")


class RoutingTests(unittest.TestCase):
    def route(self, q):
        r = coach.route(q, {"today": TODAY})
        return r and r[0], r and r[1]

    def test_plan_requests_go_to_the_personal_plan(self):
        for q, goal in (("Make me a plan to save up for a car", "car"), ("I want to buy a car, help me save for it", "car"),
                        ("Tee minulle suunnitelma säästää autoon", "car"), ("Help me save for a new bike", "bike")):
            with self.subTest(q=q):
                tool, args = self.route(q)
                self.assertEqual(tool, "make_savings_plan")
                self.assertEqual(args["goal"], goal)

    def test_other_questions_keep_their_tools(self):
        self.assertEqual(self.route("How can I save more?")[0], "get_save_more")
        self.assertEqual(self.route("Can I afford a 300 euro jacket?")[0], "can_i_afford")
        self.assertEqual(self.route("I want to save 3000 for a trip to Japan by June 2027")[0], "plan_goal_by_date")


if __name__ == "__main__":
    unittest.main()
