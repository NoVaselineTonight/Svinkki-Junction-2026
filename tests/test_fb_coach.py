"""Judges' feedback round, lane COACH: two short sentences under a picture, a coach that proposes a plan,
and Finnish everywhere (app/coach.py, app/voice.py)."""
import os as _os
import sys as _sys
import types
import unittest
from unittest import mock

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.db as db
        cls.coach, cls.db = coach, db

    def ctx(self, ai=False, ui_lang=None, cid=fx.A_CID):
        ctx = fx.make_ctx(cid, consent=dict(fx.ALL_CONSENT, ai=ai))
        ctx.memory, ctx.cid, ctx.bench_lookup = {}, cid, self.db.bench
        if ui_lang:
            ctx.ui_lang = ui_lang
        return ctx


LONG = ("You spent a lot on taxis in August. That is more than your usual month by a fair margin and it adds up. "
        "Most of it came on weekend nights when the bus does not run. A night bus could cover some of those rides. "
        "If you swapped three taxi rides a month you would keep a little more each month. "
        "That money could go to a small buffer for surprises. Would you like me to work out a plan?")


LONGER = LONG.replace(" Would you like me to work out a plan?", " ") + " ".join(
    ["This is a plain sentence about money that goes on."] * 8) + " Would you like me to work out a plan?"


class TheCut(Base):
    # Limits raised in the owner's eval (14 Nov): with a card about 80 words (answer, meaning, one step).
    def test_with_a_card_the_text_is_about_80_words(self):
        out = self.coach.tidy_model_text(LONGER, "how are my taxis", card=True)
        self.assertLessEqual(len(out.split()), self.coach.CARD_MAX_WORDS + 5, out)
        self.assertTrue(out.startswith("You spent a lot on taxis in August."))
        self.assertTrue(out.endswith("?"), "a short closing question is kept")

    def test_a_full_short_answer_with_a_step_is_not_cut(self):
        self.assertEqual(self.coach.tidy_model_text(LONG, "how are my taxis", card=True), LONG)

    def test_without_a_card_the_text_is_about_110_words(self):
        long = " ".join(["This is a plain sentence about money that goes on."] * 20)
        out = self.coach.tidy_model_text(long, "hello", card=False)
        self.assertLessEqual(len(out.split()), self.coach.NO_CARD_MAX_WORDS + 10)
        self.assertGreater(len(out.split()), 80)

    def test_detail_asked_gets_more_room_but_still_cut_with_a_card(self):
        long = " ".join(["This is a plain sentence about money that goes on."] * 20)
        out = self.coach.tidy_model_text(long, "explain it in detail", card=True)
        self.assertLessEqual(len(out.split()), self.coach.CARD_DETAIL_WORDS)
        self.assertGreater(len(out.split()), self.coach.CARD_MAX_WORDS)

    def test_a_short_answer_is_left_alone_and_card_none_keeps_old_behaviour(self):
        t = "You spent €92.85 on taxis. Night buses would cut that."
        self.assertEqual(self.coach.tidy_model_text(t, "taxis", card=True), t)
        self.assertEqual(self.coach.tidy_model_text(t, "taxis"), t)

    def test_turn_has_card(self):
        c = self.coach
        self.assertTrue(c.turn_has_card([("get_spend", {}, {"total": 1})]))
        self.assertFalse(c.turn_has_card([("calculate", {}, {"no_card": True})]))
        self.assertFalse(c.turn_has_card([("get_spend", {}, {"error": "x"})]))
        self.assertFalse(c.turn_has_card([]))

    def test_the_model_answer_is_cut_in_a_real_turn(self):
        ctx = self.ctx(ai=True)
        fake = fc.FakeClaude([fc.cl_call("get_spend", {"period": "last_month", "label": "Taxi"}), fc.cl_text(LONGER)])
        with fc.patched_claude(fake):
            r = self.coach.chat("How much did I spend on taxis?", [], ctx)
        self.assertTrue(r["cards"], r)
        self.assertLessEqual(len(r["reply"].split()), self.coach.CARD_MAX_WORDS + 5, r["reply"])


class ChartsCostNoTokens(Base):
    def test_chart_and_caption_are_not_in_the_model_view(self):
        res = {"total": 12.5, "card": "spend", "chart": {"kind": "bars", "series": [{"value": 3}]},
               "caption": "You spent 12.5", "caption_fi": "Käytit 12,5",
               "nested": {"chart": {"kind": "line"}, "keep": 1}}
        view = self.coach._model_view(res)
        for k in ("chart", "caption", "caption_fi"):
            self.assertNotIn(k, view)
        self.assertNotIn("chart", view["nested"])
        self.assertEqual(view["nested"]["keep"], 1)
        self.assertIn("chart", res, "the card the app gets keeps the chart")


def _fake_plans():
    """A stand-in for app/plans.py (written by another agent): TOOLS, TOOL_NAMES, call."""
    mod = types.ModuleType("app.plans")
    mod.TOOLS = [{"name": "propose_plan", "description": "A ready savings plan.",
                  "parameters": {"type": "object", "properties": {"name": {"type": "string"},
                                                                   "target": {"type": "number"},
                                                                   "monthly": {"type": "number"}},
                                "required": ["name", "target"]}}]
    mod.TOOL_NAMES = {"propose_plan"}

    def call(name, args, ctx):
        return {"card": "plan_offer", "name": args.get("name"), "target": args.get("target"),
                "monthly": args.get("monthly") or 50.0, "months": 20, "series": [], "fits": True,
                "chart": {"kind": "line"}, "caption": "x",
                "widget": {"type": "plan", "params": {"name": args.get("name"), "target": args.get("target")}}}
    mod.call = call
    return mod


class PlanTool(Base):
    def setUp(self):
        import app
        self._old = getattr(app, "plans", None)
        self.fake = _fake_plans()
        _sys.modules["app.plans"] = self.fake
        app.plans = self.fake

    def tearDown(self):
        import app
        _sys.modules.pop("app.plans", None)
        if self._old is not None:
            app.plans = self._old
            _sys.modules["app.plans"] = self._old
        else:
            try:
                del app.plans
            except AttributeError:
                pass

    def test_the_tool_is_declared_and_called(self):
        names = [t["name"] for t in self.coach._declared_tools(self.ctx(ai=True))]
        self.assertIn("propose_plan", names)
        self.assertIn("get_investment_plan", names)
        res = self.coach.call_tool("propose_plan", {"name": "Buffer", "target": 1000}, self.ctx(ai=True))
        self.assertEqual(res["card"], "plan_offer")

    def test_the_plan_card_comes_first_and_yes_says_tap_the_button(self):
        ctx = self.ctx(ai=True)
        fake = fc.FakeClaude([
            fc.cl_calls(("get_save_more", {}), ("propose_plan", {"name": "Buffer", "target": 1000, "monthly": 50})),
            fc.cl_text("I'd start small. Your plan is ready, add it to your home page with one tap.\n"
                       "NEXT: Show me the plan | Another way")])
        with fc.patched_claude(fake):
            r = self.coach.chat("How could I save?", [], ctx)
        self.assertEqual(r["cards"][0]["type"], "plan_offer")
        self.assertIn("propose_plan", r["tools_used"])
        hist = [{"role": "user", "text": "How could I save?"}, {"role": "assistant", "text": r["reply"]}]
        yes = self.coach.chat("yes", hist, self.ctx_same(ctx))
        self.assertIn("Add to home page", yes["reply"])
        self.assertNotRegex(yes["reply"].lower(), r"\bsaved\b(?!\s*yet)|done")
        self.assertFalse(any(c["type"] == "goal_saved" for c in yes["cards"]))

    def ctx_same(self, ctx):
        ctx.consent = dict(ctx.consent, ai=False) if isinstance(ctx.consent, dict) else ctx.consent
        return ctx

    def test_yes_in_finnish_after_a_plan(self):
        ctx = self.ctx(ai=False, ui_lang="fi")
        ctx.memory["_turn"] = 1
        self.coach._remember(ctx, "propose_plan", {}, {}, {"card": "plan_offer"})
        ctx.memory["_turn"] = 2
        r = self.coach.chat("joo", [], ctx)
        self.assertIn("Lisää etusivulle", r["reply"])
        self.assertIn("Mitään ei ole vielä tallennettu", r["reply"])


class FinnishInterface(Base):
    def test_an_english_chip_in_the_finnish_app_gets_a_finnish_answer(self):
        for q in ("How am I doing?", "What's safe to spend this week?", "How can I save more?"):
            with self.subTest(q):
                r = self.coach.chat(q, [], self.ctx(ui_lang="fi"))
                self.assertEqual(r["lang"], "fi", r["reply"])
                self.assertNotIn("englanniksi", r["reply"])
                self.assertNotRegex(r["reply"], r"\b(?:You|your|spent|earned)\b", r["reply"])

    def test_without_the_finnish_app_english_stays_english(self):
        r = self.coach.chat("How am I doing?", [], self.ctx())
        self.assertEqual(r["lang"], "en")

    def test_small_talk_and_refusals_follow_the_app_language(self):
        c = self.ctx(ui_lang="fi")
        self.assertIn("Selvä", self.coach.chat("ok", [], c)["reply"])
        self.assertIn("En voi", self.coach.chat("Pay 50 euros to John", [], c)["reply"])

    def test_the_model_is_told_to_answer_in_finnish(self):
        ctx = self.ctx(ai=True, ui_lang="fi")
        fake = fc.FakeClaude([fc.cl_text("Hei! Katsoin tilisi.\nNEXT: Kerro lisää | Mitä teen nyt")])
        with fc.patched_claude(fake):
            self.coach.chat("hello", [], ctx)
        system = fake.requests[0]["system"]
        text = " ".join(b["text"] for b in system) if isinstance(system, list) else str(system)
        self.assertIn("set to Finnish", text)
        ctx2 = self.ctx(ai=True)
        fake2 = fc.FakeClaude([fc.cl_text("Hi there.")])
        with fc.patched_claude(fake2):
            self.coach.chat("hello", [], ctx2)
        system2 = fake2.requests[0]["system"]
        text2 = " ".join(b["text"] for b in system2) if isinstance(system2, list) else str(system2)
        self.assertNotIn("set to Finnish", text2)


class SpokenFinnish(Base):
    def route(self, q):
        return self.coach.route(q, self.ctx())

    def test_spoken_forms_route_like_the_written_ones(self):
        for q, tool in (("Mihin mun rahat menee?", "get_overview"), ("Mitä mun pitäisi tehdä?", "get_save_more"),
                        ("Milloin eläke tulee?", "get_safe_to_spend"), ("Mikä on indeksirahasto?", "get_invest_education"),
                        ("Haluan alkaa säästää", "get_save_more")):
            with self.subTest(q):
                r = self.route(q)
                self.assertIsNotNone(r)
                self.assertEqual(r[0], tool)
                self.assertEqual(r[2].get("lang"), "fi")

    def test_fi_to_en_normalises(self):
        self.assertEqual(self.coach.fi_to_en("Mihin mun rahat menee?"), "where did my money go?")
        self.assertIn("and the month before", self.coach.fi_to_en("entä sitä edellisenä?"))

    def test_thanks_and_miss_line(self):
        c = self.ctx()
        self.assertEqual(self.coach.chat("Kiitos avusta!", [], c)["reply"], self.coach.THANKS_FI)
        miss = self.coach.chat("mitä kuuluu kissallesi tänään", [], c)["reply"]
        self.assertTrue(miss.startswith("Tuota en vielä osaa ilman tekoälyä."), miss)

    def test_the_replies_that_used_to_say_vastaan_englanniksi(self):
        for q in ("Millainen on asuinalueeni?", "Onko tässä kuussa jotain epätavallista?", "Onko tämä normaalia?",
                  "Siirrä 50 euroa säästötilille", "Onko kulutuksessani kuvioita?"):
            with self.subTest(q):
                r = self.coach.chat(q, [], self.ctx())
                self.assertNotIn("englanniksi", r["reply"], r["reply"])
                self.assertNotRegex(r["reply"], r"\b(?:You|your|typical resident|Here's)\b", r["reply"])

    def test_the_money_move_in_finnish(self):
        res = {"card": "money_proposal", "proposal": {"amount": 50.0, "to": "S-Bank savings account"}}
        reply = self.coach.fi_lead("propose_money_move", res, {}, {})
        self.assertIn("Tein siirtoehdotuksen: 50", reply)
        self.assertIn("Mitään ei siirry ennen kuin hyväksyt sen", reply)
        err = self.coach.chat("Siirrä 50 euroa säästötilille", [], self.ctx())["reply"]
        self.assertNotIn("englanniksi", err)


class Prompt(Base):
    def test_the_prompt_asks_for_a_complete_short_answer_a_plan_and_finnish(self):
        p = self.coach.SYSTEM_PROMPT
        for bit in ("answer to EVERY part", "the one concrete thing you would do", "General knowledge counts",
                    "Money is tight", "make_savings_plan", "propose_plan", "add it to their home page with one tap",
                    "Never say a plan is saved", "the app's controls", "Omat asiasi"):
            if bit == "the app's controls":
                continue
            self.assertIn(bit, p)
        self.assertNotIn("may take up to about 110 words", p)
        self.assertIn("Never end on an open question", p)


if __name__ == "__main__":
    unittest.main()
