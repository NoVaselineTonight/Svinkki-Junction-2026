"""The daily money quiz (app/quiz.py, /api/quiz/round): a round of questions picked for each customer, about
their own money and Finnish money skills, with the right answers worked out by code, and the AI model only
choosing, ordering and wording them.

The owner's complaint: the quiz had two questions, both the same kind, and was not personal.
"""
import json
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
        import app.quiz as quiz
        cls.quiz = quiz

    def pool(self, cid=A):
        return self.quiz.pool(fx.sandbox(cid), fx.TODAY, cid, {"age_band": "25-34"})


class PoolTests(_Base):
    def test_the_pool_is_varied_and_every_answer_is_valid(self):
        for c in fx.CUSTOMERS[:4]:
            with self.subTest(cid=c["cid"]):
                items, _ = self.pool(c["cid"])
                you = [q for q in items if q["about"] == "you"]
                skills = [q for q in items if q["about"] == "skills"]
                self.assertGreaterEqual(len(you), 6)
                self.assertGreaterEqual(len(skills), 12)
                self.assertGreaterEqual(len({q["topic"] for q in you}), 4)
                self.assertEqual(len({q["id"] for q in items}), len(items))
                for q in items:
                    self.assertTrue(q["question"].endswith("?") or q["question"].endswith("receipts)"), q["question"])
                    self.assertTrue(q["explain"])
                    if q["kind"] == "choice":
                        self.assertGreaterEqual(len(q["options"]), 3, q["id"])
                        self.assertEqual(len(set(q["options"])), len(q["options"]), q["id"])
                        self.assertTrue(0 <= q["answer"] < len(q["options"]))
                    else:
                        self.assertLessEqual(q["min"], q["answer"], q["id"])
                        self.assertGreaterEqual(q["max"], q["answer"], q["id"])
                    self.assertNotRegex(json.dumps(q), r"CUST\d|MRC-")

    def test_answers_about_you_come_from_the_customers_own_data(self):
        from app import insights as ins
        items, _ = self.pool()
        by = {q["id"]: q for q in items}
        trips = by["grocery_trips"]
        self.assertEqual(trips["answer"], ins.spend(fx.sandbox(), fx.TODAY, period="last_month", label="Groceries")["count"])
        inc = by["income"]
        self.assertEqual(inc["answer"], ins.overview(fx.sandbox(), fx.TODAY)["income"])
        ess = by["essentials"]       # customer A: 1,365.75 of 1,571.15 is regular essentials, over 80%
        self.assertEqual(ess["options"][ess["answer"]], "Over 80%")
        week = next(q for q in items if q["id"].startswith("week:"))
        self.assertTrue(week["evidence"])

    def test_skill_questions_name_a_source_and_use_the_customers_figures(self):
        items, ctx = self.pool()
        skills = [q for q in items if q["about"] == "skills"]
        for q in skills:
            self.assertTrue(q["source"] and q["source"]["url"].startswith("https://"), q["id"])
        by = {q["id"]: q for q in skills}
        self.assertEqual(by["skill:deposit_guarantee"]["options"][by["skill:deposit_guarantee"]["answer"]], "€100,000")
        self.assertEqual(by["skill:capital_tax"]["options"][by["skill:capital_tax"]["answer"]], "30%")
        buf = by["skill:buffer"]
        self.assertIn("for you that is about", buf["explain"].lower())
        comp = by["skill:compounding"]
        right = comp["options"][comp["answer"]]
        self.assertEqual(right, self.quiz._eur(comp["facts"]["value"]))
        self.assertGreater(comp["facts"]["value"], comp["facts"]["paid"])

    def test_someone_often_below_zero_gets_the_credit_question_weighted_up(self):
        items, ctx = self.pool(fx.D_CID)          # D is permanently below zero
        self.assertGreater(ctx["below_zero"], 300)
        credit = next(q for q in items if q["id"] == "skill:credit_first")
        self.assertGreater(credit["weight"], 1.5)
        self.assertIn("below zero", credit["explain"])


class RoundTests(_Base):
    def test_a_round_mixes_your_money_and_money_skills(self):
        rnd, payload = self.quiz.build(fx.sandbox(), fx.TODAY, A, {}, k=1)
        qs = rnd["questions"]
        self.assertEqual(len(qs), self.quiz.ROUND_SIZE)
        self.assertGreaterEqual(sum(1 for q in qs if q["about"] == "you"), self.quiz.MIN_ABOUT_YOU)
        self.assertGreaterEqual(sum(1 for q in qs if q["about"] == "skills"), self.quiz.MIN_SKILLS)
        self.assertIsNone(payload)
        self.assertEqual(rnd["mode"], "offline")

    def test_a_new_round_brings_new_questions(self):
        r1, _ = self.quiz.build(fx.sandbox(), fx.TODAY, A, {}, k=1)
        ids1 = [q["id"] for q in r1["questions"]]
        r2, _ = self.quiz.build(fx.sandbox(), fx.TODAY, A, {}, k=2, recent=ids1)
        self.assertFalse(set(ids1) & {q["id"] for q in r2["questions"]})
        self.assertNotEqual(r1["id"], r2["id"])

    def test_the_public_view_hides_answers_until_they_are_given(self):
        rnd, _ = self.quiz.build(fx.sandbox(), fx.TODAY, A, {}, k=1)
        view = json.dumps(self.quiz.public(rnd))
        for q in rnd["questions"]:
            self.assertNotIn(q["explain"], view)
        for q in self.quiz.public(rnd)["questions"]:
            self.assertNotIn("answer", q)
            self.assertNotIn("facts", q)

    def test_grading_choice_and_guess(self):
        rnd, _ = self.quiz.build(fx.sandbox(), fx.TODAY, A, {}, k=1)
        ch = next(q for q in rnd["questions"] if q["kind"] == "choice")
        wrong = (ch["answer"] + 1) % len(ch["options"])
        r = self.quiz.grade(rnd, ch["id"], wrong)
        self.assertFalse(r["correct"])
        self.assertIn(ch["options"][ch["answer"]], r["verdict"])
        again = self.quiz.grade(rnd, ch["id"], ch["answer"])        # answered once: the first answer stands
        self.assertFalse(again["correct"])
        guess = {"id": "g", "about": "you", "topic": "t", "kind": "guess", "question": "?", "answer": 100.0,
                 "unit": "eur", "min": 0, "max": 300, "step": 5, "explain": "x", "facts": {}}
        r2 = {"questions": [guess], "answers": {}}
        self.assertEqual(self.quiz.grade(r2, "g", 105)["grade"], "spot_on")
        r3 = {"questions": [guess], "answers": {}}
        self.assertEqual(self.quiz.grade(r3, "g", 120)["grade"], "close")
        r4 = {"questions": [guess], "answers": {}}
        res = self.quiz.grade(r4, "g", 300)
        self.assertEqual((res["grade"], res["correct"], res["done"]), ("off", False, True))
        for bad in ("lots", -5, float("inf")):
            with self.assertRaises(ValueError):
                self.quiz.grade({"questions": [guess], "answers": {}}, "g", bad)
        with self.assertRaises(KeyError):
            self.quiz.grade({"questions": [guess], "answers": {}}, "nope", 1)


class ModelTests(_Base):
    def test_the_model_picks_and_words_the_round_and_the_app_checks_it(self):
        items, ctx = self.pool()
        by = {q["id"]: q for q in items}
        pick = ["grocery_trips", "essentials", "income", "skill:deposit_guarantee", "skill:capital_tax", "top_area"]
        reply = {"title": "Your August, in six questions", "items": [
            {"id": "grocery_trips", "question": "Quick one: how many times did you pop to the grocery store in August?",
             "teach": "Fewer, bigger shops are often cheaper per meal."},
            {"id": "essentials", "question": "In August, what share of your spending went on the must-haves?",
             "teach": "With 87% on essentials, there is little room for surprises."},       # 87 is in its explain
            {"id": "income", "question": "Did you get about €9,999 last month?",                  # adds a figure
             "teach": "You earned €12,345."},                                                       # invents a figure
            {"id": "skill:deposit_guarantee", "question": "Is it €100,000 that the guarantee covers?",  # gives it away
             "teach": "Your savings are safe up to that limit at each bank."},
            {"id": "skill:capital_tax", "question": "How much tax do fund gains pay in Finland?", "teach": ""},
            {"id": "not-in-pool", "question": "?", "teach": ""},
            {"id": "top_area", "question": "Which area is your big spending area?", "teach": "Plan that day."},
        ]}
        fake = fc.FakeClaude([fc.cl_text(json.dumps(reply))])
        with fc.patched_claude(fake):
            rnd, payload = self.quiz.build(fx.sandbox(), fx.TODAY, A, {"age_band": "25-34"}, k=1,
                                           ai={"key": fc.FAKE_KEY, "model": "claude-opus-5-5"})
        self.assertEqual(fake.calls, 1)
        self.assertEqual(rnd["mode"], "claude")
        self.assertEqual(rnd["title"], "Your August, in six questions")
        self.assertEqual([q["id"] for q in rnd["questions"]], pick)
        q = {x["id"]: x for x in rnd["questions"]}
        self.assertEqual(q["grocery_trips"]["question"], reply["items"][0]["question"])
        self.assertEqual(q["essentials"]["teach"], reply["items"][1]["teach"])
        self.assertEqual(q["income"]["question"], by["income"]["question"])          # figure added: original kept
        self.assertIsNone(q["income"]["teach"])                                        # invented figure: dropped
        self.assertEqual(q["skill:deposit_guarantee"]["question"], by["skill:deposit_guarantee"]["question"])
        for x in rnd["questions"]:                                                      # answers never from the model
            self.assertEqual((x["answer"], x.get("options")), (by[x["id"]]["answer"], by[x["id"]].get("options")))
        sent = fake.requests[0]
        self.assertEqual(sent["tools"] if "tools" in sent else [], [])
        self.assertIn("grocery_trips", sent["messages"][0]["content"])
        self.assertNotRegex(json.dumps(sent), r"CUST\d")
        self.assertIn("Quiz prompt", payload["system_prompt_summary"])

    def test_a_failing_or_thin_model_reply_falls_back_to_the_codes_round(self):
        for script in ([fc.http_error(500)] * 4, [fc.cl_text("Sure! Here are some questions.")],
                       [fc.cl_text(json.dumps({"items": [{"id": "income", "question": "x?"}]}))]):
            with fc.patched_claude(fc.FakeClaude(script)):
                rnd, payload = self.quiz.build(fx.sandbox(), fx.TODAY, A, {}, k=1,
                                               ai={"key": fc.FAKE_KEY, "model": "claude-opus-5-5"})
            self.assertEqual(rnd["mode"], "offline")
            self.assertEqual(len(rnd["questions"]), self.quiz.ROUND_SIZE)
            self.assertIsNone(payload)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        cls.srv = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()

    def test_a_round_is_made_once_a_day_answered_and_resumed(self):
        c = fx.session(self.srv, "A", ai=False)
        r = c.get("/api/quiz/round")
        self.assertEqual(r.status, 200, r.text[:200])
        rd = r.json
        self.assertEqual(len(rd["questions"]), 6)
        self.assertEqual(rd["score"], {"right": 0, "answered": 0, "total": 6})
        self.assertEqual(c.get("/api/quiz/round").json["round_id"], rd["round_id"])       # the same round today
        q = rd["questions"][0]
        ans = 0 if q["kind"] == "choice" else q["max"] / 2
        a = c.post("/api/quiz/round/answer", {"round_id": rd["round_id"], "qid": q["id"], "answer": ans})
        self.assertEqual(a.status, 200, a.text[:200])
        self.assertIn("explain", a.json)
        self.assertEqual(a.json["score"]["answered"], 1)
        again = c.get("/api/quiz/round").json
        self.assertIn("result", again["questions"][0])
        self.assertEqual(again["score"]["answered"], 1)
        new = c.get("/api/quiz/round?new=1").json
        self.assertNotEqual(new["round_id"], rd["round_id"])
        self.assertFalse({x["id"] for x in new["questions"]} & {x["id"] for x in rd["questions"]})

    def test_bad_requests_and_other_customers(self):
        c = fx.session(self.srv, "A", ai=False)
        rd = c.get("/api/quiz/round").json
        q = rd["questions"][0]
        for body, code in (({"round_id": rd["round_id"], "qid": "nope", "answer": 1}, 404),
                           ({"round_id": "round:latest", "qid": q["id"], "answer": 1}, 404),
                           ({"round_id": "x" * 300, "qid": q["id"], "answer": 1}, 400),
                           ({"round_id": rd["round_id"], "qid": q["id"], "answer": "lots"}, 400)):
            with self.subTest(body=str(body)[:60]):
                self.assertEqual(c.post("/api/quiz/round/answer", body).status, code)
        b = fx.session(self.srv, "B", ai=False)            # B cannot answer A's round
        self.assertEqual(b.post("/api/quiz/round/answer", {"round_id": rd["round_id"], "qid": q["id"], "answer": 0}).status, 404)

    def test_quiz_off(self):
        c = fx.session(self.srv, "A", ai=False)
        c.post("/api/settings", {"quiz": "off"})
        self.assertEqual(c.get("/api/quiz/round").status, 404)
        c.post("/api/settings", {"quiz": "weekly"})

    def test_the_web_app_uses_the_round(self):
        with open(_os.path.join(str(fx.REPO), "web", "app.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("function quizRoundCard(rd)", js)
        self.assertIn("api('/api/quiz/round')", js)
        self.assertIn("'/api/quiz/round/answer'", js)
        self.assertIn("'Daily quiz'", js)


if __name__ == "__main__":
    unittest.main()
