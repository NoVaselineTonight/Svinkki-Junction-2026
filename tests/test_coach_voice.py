"""The coach knows the customer: a checked snapshot goes to the model, its figures may be quoted,
answers without a model get one sentence about the customer's own earlier months, and nothing in it
compares the customer with other people.
"""
import json
import re
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc

A = fx.A_CID
PEER_WORDS = re.compile(r"other people|others|peers?|your age|average person|most people|median|percentile", re.I)


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
        for k, v in over.items():
            setattr(c, k, v)
        return c

    def run_claude(self, script, message="How much do I earn?", ctx=None, history=None):
        fake = fc.FakeClaude(script)
        with fc.patched_claude(fake):
            r = self.coach.chat(message, history or [], ctx or self.ctx())
        return r, fake


class SnapshotTests(_Base):
    def test_snapshot_has_the_customers_own_month_balance_and_ideas(self):
        lines, data = self.coach.customer_snapshot(self.ctx())
        text = "\n".join(lines)
        self.assertIn("income €3,000", text)
        self.assertIn("spending €1,571", text)
        self.assertIn("housing €900", text)
        self.assertIn("next payday 15 Oct", text)
        self.assertIn("Saving opportunities", text)
        self.assertIn("not set a savings goal", text)
        self.assertEqual(set(data) & set(self.coach.SNAPSHOT_TOOLS), set(self.coach.SNAPSHOT_TOOLS))

    def test_snapshot_never_holds_ids_merchants_peers_or_iso_dates_in_its_lines(self):
        for c in fx.CUSTOMERS:
            with self.subTest(cid=c["cid"]):
                lines, data = self.coach.customer_snapshot(self.ctx(c["cid"]))
                text = "\n".join(lines)
                blob = text + json.dumps(data, default=str)
                self.assertNotRegex(blob, r"CUST\d{5}")
                self.assertNotRegex(blob, r"MX\d{5}|MRC-")
                self.assertNotIn(c["postal"], blob)
                self.assertNotRegex(text, PEER_WORDS)
                self.assertNotRegex(text, r"\d{4}-\d{2}-\d{2}")
                self.assertNotRegex(text, r"€-|-€", "a negative amount is worded, never signed")
                self.assertNotIn('"peer"', json.dumps(data, default=str))

    def test_goal_holdings_and_challenge_are_in_the_snapshot_when_they_exist(self):
        ctx = self.ctx(goal={"name": "Japan", "target": 3000.0, "saved": 250.0},
                       holdings=[{"id": "savings", "name": "S-Bank savings account", "kind": "savings", "amount": 120.0}],
                       challenge={"title": "No taxis this week"})
        lines, data = self.coach.customer_snapshot(ctx)
        text = "\n".join(lines)
        self.assertIn("Japan, target €3,000, €250 set aside", text)
        self.assertIn("€120 in S-Bank savings account", text)
        self.assertIn("No taxis this week", text)
        self.assertEqual(data["goal"]["target"], 3000.0)

    def test_snapshot_survives_a_broken_connection(self):
        ctx = self.ctx(conn=fx.closed_conn())
        lines, data = self.coach.customer_snapshot(ctx)
        self.assertIsInstance(lines, list)
        self.assertFalse(set(data) & set(self.coach.SNAPSHOT_TOOLS))


class ModelTurnTests(_Base):
    def test_snapshot_is_sent_in_the_customer_block_not_the_cached_rules(self):
        _, fake = self.run_claude([fc.cl_text("Hello")], message="hi")
        system = fake.requests[0]["system"]
        self.assertEqual(system[0]["text"], self.coach.SYSTEM_PROMPT)
        self.assertNotIn("€3,000", system[0]["text"])
        self.assertIn(self.coach.SNAPSHOT_TITLE, system[1]["text"])
        self.assertIn("income €3,000", system[1]["text"])
        self.assertNotIn("cache_control", system[1])
        self.assertNotRegex(fake.all_text(), r"CUST\d{5}")

    def test_coach_turn_asks_for_medium_effort(self):
        _, fake = self.run_claude([fc.cl_text("Hello")], message="hi")
        self.assertEqual(fake.requests[0]["output_config"], {"effort": "medium"})

    def test_a_figure_from_the_snapshot_counts_as_verified(self):
        r, _ = self.run_claude([fc.cl_text("You bring in about €3,000 a month and spent €1,571 in August, "
                                           "so €1,229 was left over.")])
        self.assertEqual(r["mode"], "claude")
        self.assertNotIn("notice", r)
        self.assertIn("€1,229", r["reply"])

    def test_an_invented_figure_is_still_caught(self):
        r, _ = self.run_claude([fc.cl_text("You bring in about €9,876 a month.")])
        self.assertNotIn("9,876", r["reply"])
        self.assertTrue(r.get("notice"))

    def test_payload_shows_what_the_coach_was_told_and_no_private_key(self):
        r, _ = self.run_claude([fc.cl_text("Hello")], message="hi")
        p = r["ai_payload"]
        self.assertTrue(p["what_the_coach_knows"])
        self.assertIn("income €3,000", "\n".join(p["what_the_coach_knows"]))
        self.assertNotIn("_snapshot", p)

    def test_suggestions_off_is_told_to_the_model(self):
        ctx = self.ctx()
        ctx.settings = dict(ctx.settings, suggestion_level="off")
        _, fake = self.run_claude([fc.cl_text("Hello")], message="hi", ctx=ctx)
        self.assertIn("suggestions off", fake.requests[0]["system"][1]["text"])


class PromptTests(_Base):
    def test_prompt_asks_for_a_personal_answer_and_a_concrete_step(self):
        p = self.coach.SYSTEM_PROMPT
        for bit in ("personal money coach", "What you know about this customer", "one concrete next step",
                    "Two to four short sentences", "never lecture", "no generic tips",
                    "grocery receipts", "Never compare the customer with other people unless they ask"):
            self.assertIn(bit, p)
        self.assertNotIn("Stay under about 45 words", p)
        self.assertNotIn("Keep replies to one or two sentences", p)

    def test_prompt_holds_no_customer_data(self):
        self.assertNotRegex(self.coach.SYSTEM_PROMPT, r"€3,000|€1,571")


class OfflineNoteTests(_Base):
    def ask(self, q, ctx=None):
        return self.coach.chat(q, [], ctx or self.ctx(consent=dict(fx.ALL_CONSENT, ai=False)))

    def test_category_answer_adds_the_customers_own_previous_month(self):
        r = self.ask("How much did I spend on taxis last month?")
        self.assertTrue(fx.text_has_amount(r["reply"], 62.10), r["reply"])
        self.assertRegex(r["reply"], r"(than|as) in July\.|In July you spent nothing")
        self.assertNotRegex(r["reply"], PEER_WORDS)

    def test_the_note_matches_the_two_months(self):
        ctx = self.ctx()
        now = self.tools.call("get_spend", {"label": "Taxi", "period": "2026-08"}, ctx)["total"]
        prev = self.tools.call("get_spend", {"label": "Taxi", "period": "2026-07"}, ctx)["total"]
        note, extra = self.coach._personal_note("get_spend", {"total": now}, {"label": "Taxi", "period": "2026-08"},
                                                {}, ctx)
        diff = round(now - prev, 2)
        if abs(diff) < max(5.0, 0.1 * prev):
            self.assertIn("about the same as in July", note)
        else:
            self.assertIn("more" if diff > 0 else "less", note)
        self.assertEqual(extra["compared_with_your_previous_month"]["total"], prev)

    def test_month_still_running_gets_no_comparison(self):
        note, extra = self.coach._personal_note("get_spend", {"total": 10.0}, {"label": "Taxi", "period": "this_month"},
                                                {}, self.ctx())
        self.assertEqual((note, extra), ("", None))

    def test_overview_says_how_the_month_compares_with_the_usual_one(self):
        r = self.ask("How am I doing?")
        self.assertRegex(r["reply"], r"You spent €100 less than in your usual month\.")

    def test_finnish_answer_gets_a_finnish_note(self):
        r = self.ask("Paljonko käytin takseihin viime kuussa?")
        self.assertRegex(r["reply"], r"heinäkuussa")
        self.assertNotIn("That is", r["reply"])

    def test_no_note_when_suggestions_are_off(self):
        ctx = self.ctx(consent=dict(fx.ALL_CONSENT, ai=False))
        ctx.settings = dict(ctx.settings, suggestion_level="off")
        r = self.ask("How much did I spend on taxis last month?", ctx)
        self.assertNotIn("July", r["reply"])

    def test_replies_stay_within_three_sentences_and_sixty_words(self):
        for q in ("How much did I spend on taxis last month?", "How am I doing?",
                  "How much did I spend on groceries in August?", "What did I spend last month?"):
            for c in fx.CUSTOMERS[:8]:
                with self.subTest(q=q, cid=c["cid"]):
                    r = self.ask(q, self.ctx(c["cid"], consent=dict(fx.ALL_CONSENT, ai=False)))
                    self.assertLessEqual(len(r["reply"].split()), 60, r["reply"])
                    self.assertLessEqual(len(re.findall(r"[.!?](?:\s|$)", r["reply"])), 3, r["reply"])


class ModelChoiceTests(_Base):
    def test_a_choice_saved_by_the_earlier_build_does_not_hold_the_coach_on_the_cheapest_model(self):
        import app.config as config
        path = config.ai_settings_file()
        _os.makedirs(_os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"claude_model": "claude-haiku-5-5"}, f)
        self.addCleanup(lambda: _os.path.exists(path) and _os.remove(path))
        self.assertEqual(config.claude_model(), "claude-opus-5-5")
        config.set_claude_model("claude-sonnet-5-5")
        self.assertEqual(config.claude_model(), "claude-sonnet-5-5", "a choice made now is kept")


if __name__ == "__main__":
    unittest.main()
