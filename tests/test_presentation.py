"""Presentation of the built-in replies (the evaluator's Part A): small talk and follow-ups, Finnish replies, the
biggest purchases, receipt wording, "stop" what-ifs, the Finnish fallback, saving a goal by saying yes, reply
length, banned words and the number check over every template.

Nothing here reads the real database or reaches a model: the AI consent is off and the key file does not exist.
These tests never depend on the wording of `text` / `headline` / `explain` fields inside results.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture as fx

NO_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "no-such-key-file.txt")
CUSTOMERS = (fx.A_CID, fx.B_CID, fx.D_CID)
OFF = {"analysis": True, "ai": False, "benchmarks": True, "suggestions": True}

QUESTIONS = [
    "How much did I spend on taxis last month?", "How much did I spend at bars last night?",
    "What kind of spender am I?", "How could I save more?", "What is safe for me to spend this week?",
    "How much could I save if I reduced dining out by 20%?", "What kind of mortgage can I get approved for?",
    "What should I invest in?", "Where did my money go?", "What did I spend in August?", "Show me my three baskets",
    "What are my regular essentials this month?", "How much went to everyday spending last month?",
    "Will I make it to payday?", "Can I afford a 300 euro jacket?", "How should I split my next salary?",
    "What if I stopped taking taxis?", "What if I cut everyday spending by 10%?",
    "How do I compare with others my age?", "What do people typically spend on taxis?", "What is my area like?",
    "Where is my money leaking?", "Do I have any forgotten subscriptions?", "Is anything unusual in my spending?",
    "What were my biggest purchases?", "Give me a challenge", "How good are my spending guesses?",
    "Do I have any spending patterns?", "Explain this:", "Show my last receipt", "Show my receipts",
    "What do I buy most?", "How much do I spend on energy drinks?", "how much fuel do I buy",
    "Show my latest transactions", "Tell me about my last purchase", "Can you transfer money for me?", "taxis",
    "how much on food", "groceries last month", "spent too much?", "am i broke", "can i buy a ps5",
    "can I afford a 600e phone", "how much do i spend on coffee", "what's my balance", "when is payday",
    "how much did I spend yesterday", "how much do I earn", "what's the weather tomorrow", "asdkjh qwe", "hi",
    "thanks!", "help", "Receipt:\nMaito 1,29\nRuisleipa 2,49\nMonster Energy 1,99\nBanaani 0,89\nYhteensa 6,66",
    "Paljonko käytin takseihin viime kuussa?", "Mihin rahani menivät?", "Millainen kuluttaja olen?",
    "Paljonko voin turvallisesti käyttää tällä viikolla?", "Riittävätkö rahani palkkapäivään?",
    "Paljonko säästäisin, jos vähentäisin ulkona syömistä 20 %?", "Miten voisin säästää enemmän?",
    "Minkä kokoisen asuntolainan voisin saada?", "Mihin minun kannattaisi sijoittaa?", "Missä rahani vuotavat?",
    "Mitä ostan eniten?", "Paljonko käytän energiajuomiin?", "Näytä kolme koriani",
    "Onko minulla varaa 300 euron takkiin?", "Voitko siirtää rahaa puolestani?", "kiitos", "paljonko ruokaan",
]
BANNED = re.compile(r"\bquery\b|\brows?\b|\bcards?\b|\bbuttons?\b|\b\d{4}-\d{2}-\d{2}\b|-\s?€|€0\.00|"
                    r"Tässä vastaus englanniksi", re.I)


def sentences(s):
    return [x for x in re.split(r"(?<=[.!?])\s+", s.strip()) if x.strip()]


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        cls._old = os.environ.get("SVINKKI_AI_KEY_FILE")
        os.environ["SVINKKI_AI_KEY_FILE"] = NO_KEY_FILE
        from app import coach, db
        cls.coach, cls.db = coach, db

    @classmethod
    def tearDownClass(cls):
        if cls._old is None:
            os.environ.pop("SVINKKI_AI_KEY_FILE", None)
        else:
            os.environ["SVINKKI_AI_KEY_FILE"] = cls._old

    def ctx(self, cid=fx.A_CID, **extra):
        c = fx.make_ctx(cid, consent=OFF)
        c.cid = cid
        c.memory = {}
        c.bench_lookup = self.db.bench
        for k, v in extra.items():
            setattr(c, k, v)
        return c

    def talk(self, ctx, *messages):
        """A conversation on one ctx (memory kept), as the server runs it; returns every turn's output."""
        hist, outs = [], []
        for m in messages:
            out = self.coach.chat(m, list(hist), ctx)
            hist += [{"role": "user", "content": m}, {"role": "assistant", "content": out["reply"]}]
            outs.append(out)
        return outs


class SmallTalkAndFollowUpTests(_Base):
    def test_canned_replies(self):
        cases = {"hi": self.coach.GREETING_EN, "Hello!": self.coach.GREETING_EN, "moi": self.coach.GREETING_FI,
                 "thanks!": self.coach.THANKS_EN, "Thank you": self.coach.THANKS_EN, "kiitos": self.coach.THANKS_FI,
                 "ok": self.coach.ACK_EN}
        for q, want in cases.items():
            with self.subTest(q):
                out = self.talk(self.ctx(), q)[0]
                self.assertEqual(out["reply"], want)
                self.assertEqual(out["tools_used"], [])
                self.assertEqual(out["cards"], [])

    def test_out_of_scope_gibberish_and_help_text(self):
        r = self.talk(self.ctx(), "what's the weather tomorrow")[0]["reply"]
        self.assertIn("not the weather", r)
        self.assertEqual(self.talk(self.ctx(), "asdkjh qwe")[0]["reply"], self.coach.GIBBERISH_EN)
        r = self.talk(self.ctx(), "tell me something about the colour of the sky please")[0]["reply"]
        self.assertEqual(r, self.coach.HELP_TEXT)
        self.assertLess(len(r.split()), 30)

    def test_new_routes(self):
        cases = {"what's my balance": ("get_safe_to_spend", "balance"), "when is payday": ("get_safe_to_spend", "payday"),
                 "how much do I earn": ("check_mortgage", "income"), "am i broke": ("get_safe_to_spend", None),
                 "how much on food": ("_food", None)}
        for q, (tool, view) in cases.items():
            with self.subTest(q):
                r = self.coach.route(q, self.ctx())
                self.assertEqual(r[0], tool)
                self.assertEqual(r[2].get("view"), view)

    def test_balance_payday_income_food_replies(self):
        ctx = self.ctx()
        safe = self.coach.tools.call("get_safe_to_spend", {}, ctx)
        out = self.talk(ctx, "what's my balance")[0]
        self.assertTrue(fx.text_has_amount(out["reply"], safe["balance"]), out["reply"])
        self.assertTrue(out["reply"].startswith("You have "))
        out = self.talk(ctx, "when is payday")[0]
        self.assertRegex(out["reply"], r"^Your next payday is \d{1,2} [A-Z][a-z]{2}, in \d+ days?\.$")
        self.assertIn(str(safe["days_left"]), out["reply"])
        out = self.talk(ctx, "how much do I earn")[0]
        self.assertEqual(out["cards"], [], "no mortgage card for an income question")
        out = self.talk(ctx, "how much on food")[0]
        self.assertEqual(out["tools_used"], ["get_spend"])
        d = out["cards"][0]["data"]
        labels = [x["label"] for x in d["by_label"]]
        self.assertEqual(labels, ["Groceries", "Dining out"])
        self.assertAlmostEqual(d["total"], sum(x["total"] for x in d["by_label"]), places=2)
        self.assertTrue(fx.text_has_amount(out["reply"], d["total"]), out["reply"])

    def test_the_month_before_then_why(self):
        ctx = self.ctx()
        o1, o2, o3 = self.talk(ctx, "How much did I spend on taxis last month?", "and the month before?", "why?")
        self.assertEqual(o1["tools_used"], ["get_spend"])
        self.assertEqual(o2["tools_used"], ["get_spend"])
        self.assertEqual(o2["cards"][0]["data"]["period"]["from"], "2026-07-01")
        self.assertIn("taxis", o2["reply"])
        self.assertIn("July", o2["reply"])
        self.assertEqual(o3["tools_used"], [])
        self.assertTrue(o3["reply"])
        self.assertNotEqual(o3["reply"], self.coach.HELP_TEXT)
        self.assertLessEqual(len(sentences(o3["reply"])), 1)

    def test_what_about_another_label_and_finnish_enta(self):
        ctx = self.ctx()
        _, o2 = self.talk(ctx, "How much did I spend on taxis last month?", "what about restaurants?")
        self.assertIn("restaurants", o2["reply"])
        ctx = self.ctx()
        _, o2 = self.talk(ctx, "Paljonko käytin ravintoloihin tässä kuussa?", "entä viime kuussa?")
        self.assertEqual(o2["tools_used"], ["get_spend"])
        self.assertEqual(o2["cards"][0]["data"]["period"]["name"], "last_month")
        self.assertIn("viime kuussa", o2["reply"])

    def test_bare_amount_after_asking_for_a_price(self):
        ctx = self.ctx()
        o1, o2 = self.talk(ctx, "Can I afford it?", "250")
        self.assertEqual(o1["tools_used"], [])
        self.assertIn("?", o1["reply"])
        self.assertEqual(o2["tools_used"], ["can_i_afford"])
        self.assertEqual(o2["cards"][0]["data"]["price"], 250.0)

    def test_a_bare_amount_without_a_question_is_not_a_purchase(self):
        self.assertNotIn("can_i_afford", self.talk(self.ctx(), "250")[0]["tools_used"])


class GoalSaveTests(_Base):
    def test_yes_saves_the_goal_through_ctx(self):
        saved = []

        def save_goal(name, target, deadline=None, monthly_needed=None):
            saved.append((name, target, deadline, monthly_needed))
            return {"name": name, "target": target, "saved": 0}

        ctx = self.ctx(save_goal=save_goal)
        o1, o2 = self.talk(ctx, "I want to go to Japan in 2027", "3000 euros")
        self.assertEqual([c["type"] for c in o1["cards"]], [], "no card while the plan needs an amount")
        self.assertEqual(saved, [], "the planning turns never store a goal")
        hist = [{"role": "user", "content": "3000 euros"}, {"role": "assistant", "content": o2["reply"]}]
        o3 = self.coach.chat("ok set it", hist, ctx)
        self.assertIn("goal_plan", [c["type"] for c in o2["cards"]])
        self.assertTrue(o2["reply"].rstrip().endswith("?"), "the plan ends by offering to save it")
        plan = [c["data"] for c in o2["cards"] if c["type"] == "goal_plan"][0]
        self.assertEqual(len(saved), 1)
        name, target, deadline, monthly = saved[0]
        self.assertEqual((name, target), ("Japan", 3000.0))
        self.assertEqual(deadline, plan["deadline"])
        card = [c for c in o3["cards"] if c["type"] == "goal_saved"]
        self.assertEqual(len(card), 1)
        self.assertEqual(set(card[0]["data"]), {"name", "target", "monthly_needed", "deadline"})
        self.assertEqual(card[0]["data"]["target"], 3000.0)
        self.assertGreaterEqual(card[0]["data"]["monthly_needed"], plan["monthly_needed"])
        self.assertRegex(o3["reply"], r"^Done, Japan is saved: €3,000 by June 2027, about €\d+ a month\.")
        self.assertEqual(len(sentences(o3["reply"])), 2)

    def test_yes_without_a_plan_or_with_no_saves_nothing(self):
        saved = []
        ctx = self.ctx(save_goal=lambda **k: saved.append(k))
        self.talk(ctx, "ok set it")
        ctx = self.ctx(save_goal=lambda **k: saved.append(k))
        self.talk(ctx, "I want to go to Japan in 2027", "3000 euros", "no, don't save it")
        self.assertEqual(saved, [])

    def test_without_a_save_hook_no_offer(self):
        o1, o2 = self.talk(self.ctx(), "I want to go to Japan in 2027", "3000 euros")
        self.assertNotIn("save it as your goal", o2["reply"])


class FinnishTests(_Base):
    def test_B2_finnish_reply_is_only_the_finnish_lead(self):
        english = re.compile(r"\b(you|your|the|spent|would|month|payday)\b", re.I)
        for q in ("Paljonko käytin takseihin viime kuussa?", "Mihin rahani menivät?", "Millainen kuluttaja olen?",
                  "Paljonko voin turvallisesti käyttää tällä viikolla?", "Riittävätkö rahani palkkapäivään?",
                  "Paljonko säästäisin, jos vähentäisin ulkona syömistä 20 %?", "Miten voisin säästää enemmän?",
                  "Minkä kokoisen asuntolainan voisin saada?", "Mihin minun kannattaisi sijoittaa?",
                  "Missä rahani vuotavat?", "Näytä kolme koriani", "Onko minulla varaa 300 euron takkiin?",
                  "Voitko siirtää rahaa puolestani?", "paljonko ruokaan"):
            with self.subTest(q):
                out = self.talk(self.ctx(), q)[0]
                self.assertNotRegex(out["reply"], english, out["reply"])
                self.assertNotIn("englanniksi", out["reply"])

    def test_B6_finnish_fallback(self):
        out = self.talk(self.ctx(), "mitä kuuluu kissallesi tänään")[0]
        self.assertEqual(out["reply"], self.coach.HELP_TEXT_FI)


class ReplyShapeTests(_Base):
    def test_B3_biggest_purchases_come_biggest_first(self):
        ctx = self.ctx()
        out = self.talk(ctx, "What were my biggest purchases?")[0]
        data = out["cards"][0]["data"]
        self.assertEqual(data["columns"], ["Date", "What", "Amount"])
        amounts = [r[2] for r in data["rows"]]
        self.assertTrue(amounts)
        self.assertEqual(amounts, sorted(amounts, reverse=True))
        for r in data["rows"]:
            self.assertRegex(r[0], r"^\d{1,2} [A-Z][a-z]{2}( \d{4})?$")
        self.assertTrue(out["reply"].startswith("Your biggest purchases last month: "))
        self.assertTrue(fx.text_has_amount(out["reply"], amounts[0]), out["reply"])

    def test_B4_receipt_sentence_follows_the_counts(self):
        r = self.coach.render
        base = {"period": {"from": "2026-08-01", "to": "2026-08-31"}, "card": "receipts"}
        one = {"store": "ABC", "kind": "fuel", "chain": "ABC", "d": "2026-08-23", "total": 54.12}
        both = dict(base, count=6, grocery_count=2, grocery_total=131.19, fuel_count=4, fuel_total=221.29,
                    total=352.48, receipts=[one] * 5)
        txt = r("get_receipts", both, {}, {"today": "2026-09-24"})
        self.assertIn("6 simulated demo receipts in August: 2 from grocery stores (€131.19) and 4 from ABC fuel "
                      "(€221.29)", txt)
        groc = dict(base, count=3, grocery_count=3, grocery_total=90.5, fuel_count=0, fuel_total=0, total=90.5,
                    receipts=[{"store": "Prisma", "kind": "grocery", "d": "2026-08-02", "total": 30.0}] * 3)
        txt = r("get_receipts", groc, {}, {"today": "2026-09-24"})
        self.assertIn("3 from grocery stores", txt)
        self.assertNotIn("fuel", txt)
        last = dict(base, count=14, grocery_count=10, fuel_count=4, receipts=[
            {"store": "S-market", "kind": "grocery", "d": "2026-09-19", "total": 93.04}])
        self.assertEqual(r("get_receipts", last, {"limit": 1}, {"today": "2026-09-24"}),
                         "Your last simulated demo receipt is from S-market on 19 Sep, €93.04.")
        fuel = dict(last, receipts=[dict(one, store="ABC Laaksola", d="2026-09-24",
                                         fuel={"litres": 29.75, "price_per_litre": 1.819})])
        self.assertEqual(r("get_receipts", fuel, {"limit": 1}, {"today": "2026-09-24"}),
                         "Your last simulated demo receipt is from ABC Laaksola on 24 Sep: 30 litres, €54.12.")
        self.assertEqual(r("get_receipts", dict(base, count=0, receipts=[]), {}, {}), "No receipts in this period.")

    def test_B5_stop_means_all_of_it(self):
        for q in ("What if I stopped taking taxis?", "what if I quit taxis", "what if I gave up taxis",
                  "no more taxis, what would I save?"):
            with self.subTest(q):
                r = self.coach.route(q, self.ctx())
                self.assertEqual(r[0], "simulate_what_if")
                self.assertEqual(r[1]["changes"][0]["pct"], 100.0)
        out = self.talk(self.ctx(), "What if I stopped taking taxis?")[0]
        d = out["cards"][0]["data"]
        self.assertAlmostEqual(d["saved_monthly"], d["baseline_monthly"], places=2)
        self.assertTrue(out["reply"].startswith("If you stopped taking taxis you'd save about "), out["reply"])
        self.assertTrue(fx.text_has_amount(out["reply"], round(d["saved_monthly"])), out["reply"])
        out = self.talk(self.ctx(), "What if I cut taxis?")[0]
        self.assertTrue(out["reply"].startswith("A 20% cut in taxis would save about "), out["reply"])

    def test_money_and_period_style(self):
        out = self.talk(self.ctx(), "How much did I spend on taxis last month?")[0]
        d = out["cards"][0]["data"]
        self.assertTrue(fx.text_has_amount(out["reply"], d["total"]), "a looked-up total keeps its cents")
        if d["count"] > 1:
            self.assertIn("(%d payments)" % d["count"], out["reply"])
        self.assertNotIn("across", out["reply"])
        out = self.talk(self.ctx(), "What is safe for me to spend this week?")[0]
        d = out["cards"][0]["data"]
        if d["safe_total"] > 0:
            self.assertIn("€{:,.0f} this week".format(d["per_week"]), out["reply"])
            self.assertNotIn("2026", out["reply"], "the current year is left out")


class AcrossAllRepliesTests(_Base):
    """Every built-in reply for the full question list, for three fixture customers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rows = []
        for cid in CUSTOMERS:
            for q in QUESTIONS + [it["question"] for lang in ("en", "fi") for g in cls.coach.help_groups(lang)
                                  for it in g["items"]]:
                c = fx.make_ctx(cid, consent=OFF)
                c.cid, c.memory, c.bench_lookup = cid, {}, cls.db.bench
                out = cls.coach.chat(q, [], c)
                c2 = fx.make_ctx(cid, consent=OFF)
                c2.cid, c2.memory, c2.bench_lookup = cid, {}, cls.db.bench
                r = cls.coach._run_offline(q, c2)
                cls.rows.append((cid, q, out, r))

    def test_no_reply_over_three_sentences_or_sixty_words(self):
        for cid, q, out, _r in self.rows:
            with self.subTest(cid=cid, q=q[:40]):
                self.assertLessEqual(len(sentences(out["reply"])), 3, out["reply"])
                self.assertLessEqual(len(out["reply"].split()), 60, out["reply"])

    def test_no_banned_words(self):
        for cid, q, out, _r in self.rows:
            with self.subTest(cid=cid, q=q[:40]):
                self.assertNotRegex(out["reply"], BANNED)

    def test_number_check_accepts_every_template(self):
        for cid, q, _out, r in self.rows:
            results = [x for x in r.get("results") or [] if isinstance(x, dict)]
            results += [v for v in (r.get("hints") or {}).values() if isinstance(v, dict)]   # e.g. the fuel receipts
            for strict in (False, True):
                with self.subTest(cid=cid, q=q[:40], strict=strict):
                    self.assertTrue(self.coach.numbers_grounded(r["reply"], results, q, strict=strict),
                                    (r["reply"], self.coach.ungrounded_spans(r["reply"], results, q, strict)))

    def test_rounded_whole_euros_are_grounded_but_other_figures_are_not(self):
        res = [{"total": 92.85, "per_week": 354.94, "max_loan": 122501.9}]
        for t in ("€93", "€355", "€122,502", "about €122,500"):
            self.assertTrue(self.coach.numbers_grounded(t, res, "", strict=True), t)
        for t in ("€94", "€356", "€122,600", "€123,000"):
            self.assertFalse(self.coach.numbers_grounded(t, res, "", strict=False), t)


class HelpGroupTests(_Base):
    def test_one_list_same_wording_as_the_web(self):
        js = open(os.path.join(fx.REPO, "web", "app.js"), encoding="utf-8").read()
        block = js[js.index("var ASK_GROUPS = ["):]
        block = block[:block.index("];") + 1]
        titles = re.findall(r"title: '([^']+)'", block)
        groups, cur = [], None
        for line in block.splitlines():
            t = re.search(r"title: '([^']+)'", line)
            if t:
                cur = (t.group(1), [])
                groups.append(cur)
            for q in re.findall(r"\{ q: '([^']+)' \}", line):
                cur[1].append(q.replace("\\'", "'"))
        self.assertEqual(len(groups), len(titles))
        mine = [(g["title"], [it["question"] for it in g["items"]]) for g in self.coach.help_groups("en")]
        self.assertEqual(mine, groups)
        for lang in ("en", "fi"):
            hg = self.coach.help_groups(lang)
            self.assertLessEqual(len(hg), 7)
            self.assertTrue(all(len(g["items"]) <= 5 for g in hg))
            self.assertEqual(len(hg), len(groups))

    def test_every_question_routes(self):
        for lang in ("en", "fi"):
            for g in self.coach.help_groups(lang):
                for it in g["items"]:
                    with self.subTest(it["question"]):
                        self.assertIsNotNone(self.coach.route(it["question"], self.ctx()))


class PromptTests(_Base):
    def test_house_rules_are_in_the_system_prompt(self):
        p = self.coach.SYSTEM_PROMPT
        for bit in ("whole euros from €20", "never mix", "last month", "more than double", "(2 payments)",
                    "most people your age nearby", "Answer first", "lower case",
                    "Never mention buttons, cards or the screen", "\"query\" or \"rows\""):
            self.assertIn(bit, p)
        self.assertNotIn("button on the card", p)


if __name__ == "__main__":
    unittest.main()
