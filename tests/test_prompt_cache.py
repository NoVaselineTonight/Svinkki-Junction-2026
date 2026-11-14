"""Prompt caching of the coach's Claude requests (app/llm_claude.py).

Three cache_control breakpoints at most (the API allows 4):
1. the shared rules block (system[0]): tools + rules, the same for every customer;
2. the per-customer block (system[-1]): read again on every round of a turn and on the next turn,
   and still read on the last round, where tool_choice "none" invalidates only the messages cache;
3. top-level automatic caching (body["cache_control"]) for the growing message history, so round
   N+1 reads everything round N sent. Only for requests that declare tools (a conversation); a
   one-off request such as explaining a pasted text would only pay the cache-write premium.
"""
import copy
import json
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc

EPH = {"type": "ephemeral"}
TOOLS = [{"name": "get_spend", "description": "Total spending.",
          "parameters": {"type": "object", "properties": {"period": {"type": "string"}}}}]


def breakpoints(body):
    """Every cache_control in the request body, top level included."""
    count = [1 if "cache_control" in body else 0]

    def rec(x):
        if isinstance(x, dict):
            if "cache_control" in x:
                count[0] += 1
            for v in x.values():
                rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)
    for k, v in body.items():
        if k != "cache_control":
            rec(v)
    return count[0]


class RequestShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.llm_claude as lc
        cls.lc = lc

    def send(self, system, messages, tools=TOOLS, **kw):
        fake = fc.FakeClaude([fc.cl_text("ok")])
        with fc.patched_claude(fake):
            self.lc.create(system, messages, tools, fc.FAKE_KEY, "claude-opus-5-5", **kw)
        return fake.requests[0]

    def test_rules_customer_block_and_history_are_each_cacheable(self):
        msgs = [{"role": "user", "content": "hi"}]
        body = self.send(["Rules.", "Customer lines."], msgs)
        self.assertEqual(body["system"][0]["cache_control"], EPH)
        self.assertEqual(body["system"][1]["cache_control"], EPH)
        self.assertEqual(body["cache_control"], EPH)        # automatic: the end of the message history
        self.assertLessEqual(breakpoints(body), 4)
        self.assertEqual(breakpoints(body), 3)

    def test_last_round_without_tools_keeps_the_same_markers(self):
        body = self.send(["Rules.", "Customer lines."], [{"role": "user", "content": "hi"}], allow_tools=False)
        self.assertEqual(body["tool_choice"], {"type": "none"})
        self.assertEqual(body["system"][1]["cache_control"], EPH)
        self.assertEqual(body["cache_control"], EPH)

    def test_one_system_block_is_marked_once(self):
        body = self.send("Rules.", [{"role": "user", "content": "hi"}])
        self.assertEqual(len(body["system"]), 1)
        self.assertEqual(body["system"][0]["cache_control"], EPH)
        self.assertEqual(breakpoints(body), 2)

    def test_a_one_off_request_without_tools_does_not_cache_its_unique_tail(self):
        body = self.send("Explain rules.", [{"role": "user", "content": "a pasted letter " * 20}], tools=[])
        self.assertNotIn("cache_control", body)
        self.assertEqual(breakpoints(body), 1)

    def test_the_callers_messages_are_not_changed(self):
        msgs = [{"role": "user", "content": "hi"},
                {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "get_spend", "input": {}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}]}]
        before = copy.deepcopy(msgs)
        body = self.send(["Rules.", "Customer lines."], msgs)
        self.assertEqual(msgs, before)
        self.assertEqual(body["messages"], before)       # no marker inside the messages: they never pile up


class CoachTurnTests(unittest.TestCase):
    """A multi-round coach turn: every round sends the same cacheable prefix, byte for byte."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        cls.coach = coach

    def test_every_round_of_a_turn_reuses_the_cached_prefix(self):
        import app.tools as tools
        args = {}
        for t in tools.TOOLS:
            if t["name"] == "get_spend":
                props = t["parameters"].get("properties", {})
                args = {k: v for k, v in {"period": "last_month", "label": "Taxi"}.items() if k in props}
        fake = fc.FakeClaude([fc.cl_call("get_spend", args), fc.cl_text("You spent some on taxis.")])
        with fc.patched_claude(fake):
            self.coach.chat("How much did I spend on taxis last month?", [], fx.make_ctx(fx.A_CID))
        reqs = [r for r in fake.requests if r]
        self.assertGreaterEqual(len(reqs), 2, "the turn should take two rounds")
        first, second = reqs[0], reqs[1]
        for body in (first, second):
            self.assertEqual(body["system"][0]["cache_control"], EPH)
            self.assertEqual(body["system"][-1]["cache_control"], EPH)
            self.assertEqual(body["cache_control"], EPH)
            self.assertLessEqual(breakpoints(body), 4)
        # the prefix round 2 can read: same tools, same system, round 1's messages unchanged at the front
        self.assertEqual(json.dumps(first["tools"]), json.dumps(second["tools"]))
        self.assertEqual(json.dumps(first["system"]), json.dumps(second["system"]))
        n = len(first["messages"])
        self.assertEqual(json.dumps(first["messages"]), json.dumps(second["messages"][:n]))


if __name__ == "__main__":
    unittest.main()
