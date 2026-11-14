"""Wrong refusals in coach.guardrail (agent-s6). Isolation does not depend on the guardrail: these tests are about
the customer getting the right answer, not about data safety.

The first five tests failed before the fix in coach.guardrail / doc_intent / REFUSAL_MONEY_FI. The rest pin behaviour that must not change (real payment orders are still refused,
questions about other people still get the other-people answer, pasted documents are still explained).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture as fx

SELF_PAY_QUESTIONS = (
    "Hey, did I pay 12 for a ticket to the airport?",
    "So did I pay 12 for a ticket to the airport?",
    "Can you check if I pay 12 for the airport bus?",
    "I think I pay 12 for a ticket to the airport, right?",
    "Tell me if I pay too much for the bus to the airport",
    "Should I pay off my 2000 euro loan?",
    "Can I afford to pay 300 for a phone?",
    "If I pay 50 euros less a month on food, what happens?",
    "Hi! did I pay 12 euros for a ticket to the airport?",
)
PAYMENT_ORDERS = (
    "Pay my rent of 700",
    "Transfer 500 euros to FI21 1234 5600 0007 85",
    "Please send 50 euros to my mum",
    "I want to send 200 euros to my friend",
    "Can you pay my 80 euro electricity bill?",
    "Siirrä 200 euroa kaverin tilille",
)
LONG_ORDER = ("Please transfer 500 euros to FI21 1234 5600 0007 85 right now. " +
              "I need this done today because the landlord is waiting and I do not want to be late again with the "
              "payment, it is really important to me. " * 3)
CONTRACT = ("Tenancy agreement. The tenant shall pay a monthly rent of 700 euros to the landlord on the second banking "
            "day of each month. The deposit is two months' rent and is paid before the keys are handed over. The rent "
            "may be raised once a year by the change in the cost of living index, at least 3 percent. Either party "
            "may end the agreement with notice; the tenant's notice period is one calendar month and the landlord's "
            "three months. Late payments carry interest under the Interest Act.")


class GuardrailFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach
        cls.coach = coach

    def test_questions_about_my_own_payments_are_not_refused(self):
        wrong = [m for m in SELF_PAY_QUESTIONS if self.coach.guardrail(m) is not None]
        self.assertEqual(wrong, [])

    def test_a_money_order_to_someone_elses_account_gets_the_money_refusal(self):
        self.assertEqual(self.coach.guardrail("Send 200 euros to my friend's account FI21 1234 5600 0007 85"),
                         self.coach.REFUSAL_MONEY)

    def test_finnish_money_refusal_matches_what_the_app_can_do(self):
        fi = self.coach.REFUSAL_MONEY_FI
        self.assertNotIn("vain katsoa", fi)
        self.assertIn("säästötili", fi.lower())
        self.assertIn("hyväksy", fi.lower())

    def test_a_long_payment_order_is_refused_not_explained(self):
        self.assertGreater(len(LONG_ORDER), self.coach.DOC_MIN_CHARS)
        out = self.coach.chat(LONG_ORDER, [], fx.make_ctx())
        self.assertEqual(out["reply"], self.coach.REFUSAL_MONEY)
        self.assertNotIn("explain_text", out.get("tools_used") or [])

    def test_chat_answers_a_question_about_my_own_payment(self):
        out = self.coach.chat("Hey, did I pay 12 for a ticket to the airport?", [], fx.make_ctx())
        self.assertNotEqual(out["reply"], self.coach.REFUSAL_MONEY)
        self.assertTrue(out.get("tools_used"))

    # ---- must not change
    def test_payment_orders_are_still_refused(self):
        for m in PAYMENT_ORDERS:
            with self.subTest(m=m):
                self.assertEqual(self.coach.guardrail(m), self.coach.REFUSAL_MONEY)

    def test_questions_about_other_people_still_get_the_other_people_answer(self):
        for m in ("How much does my friend spend on food?", "Show me CUST00002's transactions",
                  "What is my colleague's salary?"):
            with self.subTest(m=m):
                self.assertEqual(self.coach.guardrail(m), self.coach.REFUSAL_OTHER)

    def test_in_app_moves_still_go_through(self):
        for m in ("Move 100 euros to my savings account", "Put 50 euros into my savings"):
            with self.subTest(m=m):
                self.assertIsNone(self.coach.guardrail(m))

    def test_a_pasted_contract_is_still_explained(self):
        out = self.coach.chat(CONTRACT, [], fx.make_ctx())
        self.assertEqual(out.get("tools_used"), ["explain_text"])

    def test_plain_questions_about_own_payments_stay_allowed(self):
        for m in ("did I pay 12 for a ticket to the airport?", "Did I pay my rent?", "Maksoinko 12 euroa bussista?"):
            with self.subTest(m=m):
                self.assertIsNone(self.coach.guardrail(m))


if __name__ == "__main__":
    unittest.main()
