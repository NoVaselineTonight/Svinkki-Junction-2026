"""In-app money moves (owner decision, 14 Nov 2026) and the evaluation majors fixed with them.

Money may move in the demo, but only: inside S-mobiili (own savings account, S-Bank funds), only after the
customer approves one exact proposal, once, within 15 minutes, and never more than is safe to spend before
payday. The coach (rules or AI model) can only propose.
"""
import unittest

import fixture as fx


class MoneyBase(unittest.TestCase):
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

    def money(self, c=None):
        r = (c or self.a).get("/api/money")
        self.assertEqual(r.status, 200, r.text[:200])
        return r.json

    def amount(self):
        avail = self.money()["available"]
        if avail < 10:
            self.skipTest("persona A has nothing safe to move at the fixture date")
        return float(int(min(50, avail // 2)))

    def balance(self, c=None):
        return (c or self.a).get("/api/safe-to-spend").json["balance"]

    def propose(self, dest="savings", amount=None, c=None):
        r = (c or self.a).post("/api/money/propose", {"dest": dest, "amount": amount if amount is not None else self.amount()})
        self.assertEqual(r.status, 200, r.text[:200])
        return r.json

    def confirm(self, prop, approve=True, c=None, **over):
        body = {"proposal_id": prop["id"], "approve": approve, "amount": prop["amount"], "dest": prop["dest"]}
        body.update(over)
        return (c or self.a).post("/api/money/confirm", body)


class ApprovalTests(MoneyBase):
    def test_a_proposal_moves_nothing_and_an_approval_moves_it_once(self):
        before, count = self.balance(), self.a.get("/api/transactions").json["count"]
        prop = self.propose()["proposal"]
        self.assertIn("approve", prop["note"].lower())
        self.assertAlmostEqual(self.balance(), before, places=2, msg="a proposal must not move money")
        r = self.confirm(prop)
        self.assertEqual(r.status, 200, r.text)
        self.assertTrue(r.json["moved"])
        self.assertIn("S-mobiili", r.json["message"])
        self.assertAlmostEqual(self.balance(), before - prop["amount"], places=2)
        self.assertEqual(self.a.get("/api/transactions").json["count"], count + 1)
        held = self.money()["holdings"]
        self.assertEqual([(h["id"], h["amount"]) for h in held], [("savings", prop["amount"])])
        things = self.a.get("/api/home").json["things"]
        self.assertIn("money:savings", [t["id"] for t in things])
        again = self.confirm(prop)
        self.assertFalse(again.json["moved"])
        self.assertAlmostEqual(self.balance(), before - prop["amount"], places=2, msg="approved twice")

    def test_cancel_wrong_amount_wrong_destination_and_forged_ids_move_nothing(self):
        before = self.balance()
        p1 = self.propose()["proposal"]
        self.assertFalse(self.confirm(p1, amount=p1["amount"] + 1).json["moved"])
        self.assertFalse(self.confirm(p1, dest="fund_index").json["moved"])
        self.assertTrue(self.confirm(p1, approve=False).json["ok"])
        self.assertFalse(self.confirm(p1).json["moved"], "a cancelled offer cannot be approved later")
        self.assertFalse(self.confirm({"id": "made-up", "amount": 10, "dest": "savings"}).json["moved"])
        for bad in ({"proposal_id": p1["id"], "approve": "yes"}, {"proposal_id": 5, "approve": True},
                    {"approve": True}):
            self.assertEqual(self.a.post("/api/money/confirm", bad).status, 400, bad)
        self.assertAlmostEqual(self.balance(), before, places=2)

    def test_another_customer_cannot_approve_my_proposal(self):
        prop = self.propose()["proposal"]
        b = fx.session(self.server, "B")
        before_b = self.balance(b)
        self.assertFalse(self.confirm(prop, c=b).json["moved"])
        self.assertAlmostEqual(self.balance(b), before_b, places=2)
        self.assertTrue(self.confirm(prop).json["moved"], "the owner can still approve it")

    def test_an_expired_proposal_cannot_be_approved(self):
        prop = self.propose()["proposal"]

        def age(conn):
            conn.execute("UPDATE money_proposals SET created = created - 3600 WHERE id=?", (prop["id"],))
        self.state._run(age)
        r = self.confirm(prop)
        self.assertFalse(r.json["moved"])
        self.assertIn("expired", r.json["message"].lower())

    def test_only_in_app_destinations_and_never_more_than_is_safe(self):
        for dest in ("FI2112345600000785", "external", "", None, "savings; DROP"):
            self.assertEqual(self.a.post("/api/money/propose", {"dest": dest, "amount": 10}).status, 400, dest)
        for amount in ("10", True, None):
            self.assertEqual(self.a.post("/api/money/propose", {"dest": "savings", "amount": amount}).status, 400)
        too_much = self.money()["available"] + 100
        r = self.propose(amount=too_much)
        self.assertFalse(r["ok"])
        self.assertRegex(r["message"].lower(), r"at most|nothing can be moved")
        self.assertFalse(self.propose(amount=1)["ok"], "below the minimum")

    def test_fund_moves_carry_a_risk_note_and_erase_and_reset_clear_moves(self):
        prop = self.propose(dest="fund_index")["proposal"]
        self.assertTrue(prop["risk"])
        self.assertTrue(self.confirm(prop).json["moved"])
        self.assertEqual(self.money()["holdings"][0]["id"], "fund_index")
        self.state.reset_all()
        self.assertEqual(self.state.list_moves(fx.A_CID), [])


class CoachMoneyTests(MoneyBase):
    def chat(self, msg):
        r = self.a.post("/api/chat", {"message": msg})
        self.assertEqual(r.status, 200, r.text[:300])
        return r.json

    def test_the_coach_only_proposes(self):
        self.amount()
        before = self.balance()
        r = self.chat("Move 20 euros to my savings account")
        self.assertIn("money_proposal", [c.get("type") for c in r["cards"]])
        self.assertRegex(r["reply"].lower(), r"nothing moves until you approve")
        self.assertAlmostEqual(self.balance(), before, places=2)

    def test_risky_purchases_never_fit(self):
        for q in ("Can I afford a 300 euro payday loan?", "Can I afford 500 euros of bitcoin?",
                  "Can I afford a 100 euro casino night?"):
            with self.subTest(q=q):
                r = self.chat(q)
                self.assertNotRegex(r["reply"].lower(), r"\bfits\b|^yes")
                card = next(c for c in r["cards"] if c.get("type") == "afford")
                self.assertEqual(card["data"]["verdict"], "caution")

    def test_spending_more_costs_and_income_and_unclear_periods(self):
        r = self.chat("What if I spend 20% more on restaurants?")
        self.assertNotIn("save", r["reply"].lower())
        self.assertIn("more a month", r["reply"].lower())
        r = self.chat("How much did I earn last month?")
        self.assertRegex(r["reply"], r"came in")
        r = self.chat("How much did I spend on taxis in the last 10 days?")
        self.assertIn("last 10 days", r["reply"])
        r = self.chat("How much did I spend on unicorns last month?")
        self.assertIn("don't have a category", r["reply"])


class CheckinCapTests(MoneyBase):
    def test_set_aside_suggestions_never_exceed_what_is_safe_to_move(self):
        r = self.a.get("/api/checkin").json
        avail = self.money()["available"]
        for s in (r.get("checkin") or {}).get("suggestions") or []:
            if s.get("kind") in ("save_surplus", "build_buffer"):
                self.assertLessEqual(s["amount"], avail + 0.01)
                self.assertIn("approve", s["detail"])


class SafeToSpendFixTests(unittest.TestCase):
    """MAJ-1 and MAJ-2 on a hand-built account: moves are capped by safe to spend, so it must not be generous."""

    def account(self, rows):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, "
                     "mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
        bal = 0.0
        for i, (d, amt, typ, label, basket) in enumerate(sorted(rows)):
            bal += amt
            conn.execute("INSERT INTO tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (d, d + " 12:00:00", amt, round(bal, 2), typ, label, None, None, label, basket, None, i + 1))
        return conn

    def months(self, n=6, end=(2026, 9)):
        y, m = end
        out = []
        for _ in range(n):
            out.append((y, m))
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        return list(reversed(out))

    def test_MAJ1_a_late_unpaid_rent_still_counts(self):
        from app import insights
        rows = []
        for y, m in self.months(end=(2026, 8)):
            rows.append(("%04d-%02d-01" % (y, m), 2500.0, "salary", "Salary", "income"))
            rows.append(("%04d-%02d-05" % (y, m), -800.0, "housing_payment", "Housing", "regular"))
        rows.append(("2026-09-01", 2500.0, "salary", "Salary", "income"))      # September rent not paid yet
        conn = self.account(rows)
        s = insights.safe_to_spend(conn, "2026-09-10")
        self.assertIn(800.0, [b["expected"] for b in s["upcoming_bills"]], "the late rent was dropped")

    def test_MAJ2_paid_this_month_means_next_payday_is_next_month(self):
        from app import insights
        rows = []
        for i, (y, m) in enumerate(self.months(end=(2026, 8))):
            day = 15 if i % 2 else 28                                            # alternating salary day
            rows.append(("%04d-%02d-%02d" % (y, m, day), 2500.0, "salary", "Salary", "income"))
        rows.append(("2026-09-12", 2500.0, "salary", "Salary", "income"))     # September already paid
        conn = self.account(rows)
        s = insights.safe_to_spend(conn, "2026-09-14")
        self.assertGreaterEqual(s["next_payday"], "2026-10-01")


class NoUnaskedComparisonTests(MoneyBase):
    """Owner, 14 Nov 2026: comparisons with other people only when the customer asks for one."""

    def chat(self, msg):
        r = self.a.post("/api/chat", {"message": msg})
        self.assertEqual(r.status, 200, r.text[:300])
        return r.json

    PEER = r"people your age|most people|most customers|people like you|compar|turn on comparisons"

    def test_own_questions_get_no_comparison(self):
        for q in ("How much do I earn?", "How much did I earn last month?", "How much did I spend on taxis last month?",
                  "How much did I spend on groceries last month?", "What is my balance?"):
            with self.subTest(q=q):
                r = self.chat(q)
                self.assertNotRegex(r["reply"].lower(), self.PEER)
                for c in r["cards"]:
                    self.assertNotIn("peer", c.get("data") or {}, q)

    def test_a_comparison_is_given_when_asked(self):
        r = self.chat("How do I compare with people my age?")
        self.assertIn(r["tools_used"], (["get_benchmarks"], ["get_averages"]))

    def test_alerts_and_quiz_do_not_compare_with_others(self):
        for a in (self.a.get("/api/alerts").json.get("alerts") or []):
            self.assertNotRegex(str(a).lower(), r"people your age|most people|people of your age")
        q = self.a.get("/api/quiz").json
        if q.get("quiz_id"):
            r = self.a.post("/api/quiz/answer", {"quiz_id": q["quiz_id"], "guess": 10}).json
            self.assertNotIn("peer", r)


class AccountCardTests(MoneyBase):
    """The simulated bank account shown at the top of the start page."""

    def test_account_shows_the_balance_and_follows_an_approved_move(self):
        a = self.a.get("/api/account").json
        self.assertTrue(a["simulated"])
        self.assertAlmostEqual(a["current"]["balance"], self.balance(), places=2)
        self.assertRegex(a["current"]["number"], r"^FI\*\* \*{4} \*{4} \d{4}$")
        saved0 = a["savings"]["balance"]
        prop = self.propose()["proposal"]
        self.assertAlmostEqual(self.a.get("/api/account").json["current"]["balance"], a["current"]["balance"],
                               places=2, msg="a proposal alone changes nothing")
        self.assertTrue(self.confirm(prop).json["moved"])
        b = self.a.get("/api/account").json
        self.assertAlmostEqual(b["current"]["balance"], a["current"]["balance"] - prop["amount"], places=2)
        self.assertAlmostEqual(b["savings"]["balance"], saved0 + prop["amount"], places=2)
        self.assertIn("S-Bank savings account", [x["name"] for x in b["savings"]["parts"]])

    def test_account_reveals_no_ids_and_needs_a_session(self):
        text = self.a.get("/api/account").text
        self.assertNotRegex(text, r"CUST\d{5}|MX\d{5}")
        b = fx.session(self.server, "B")
        self.assertNotEqual(b.get("/api/account").json["current"]["number"],
                            self.a.get("/api/account").json["current"]["number"])
        self.assertIn(self.server.client().get("/api/account").status, (401, 403))


if __name__ == "__main__":
    unittest.main()
