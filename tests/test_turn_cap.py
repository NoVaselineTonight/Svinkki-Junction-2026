"""A Claude coach turn has a hard cap that includes its last request; after it the built-in rules answer.

Every fake request takes its whole timeout (a slow service) and asks for another tool, so only the cap
can end the turn. Time is a fake clock that moves only while a request runs. No network.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture as fx  # noqa: E402
import fixture_claude as fc  # noqa: E402

QUESTION = "How much did I spend on taxis last month?"


class SlowClaude(fc.FakeClaude):
    """Each request uses its whole timeout on a fake clock, then answers from the script."""

    def __init__(self, script, clock):
        super().__init__(script)
        self.clock, self.timeouts = clock, []

    def __call__(self, req, *args, **kwargs):
        t = kwargs.get("timeout", args[1] if len(args) > 1 else None)
        self.timeouts.append(t)
        self.clock[0] += float(t)
        return super().__call__(req, *args, **kwargs)


class TurnCapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        cls.coach = coach

    def run_slow(self):
        clock = [1000.0]
        fake = SlowClaude([fc.cl_call("get_spend", {"period": "last_month", "label": "Taxi"})], clock)
        with fc.patched_claude(fake), mock.patch("time.monotonic", lambda: clock[0]):
            r = self.coach.chat(QUESTION, [], fx.make_ctx(fx.A_CID))
        return r, fake, clock[0] - 1000.0

    def test_cap_values(self):
        self.assertEqual(self.coach.TURN_SECONDS, 60)
        self.assertEqual(self.coach.COACH_TIMEOUT, 45)

    def test_requests_together_stay_within_the_turn_cap(self):
        _r, fake, elapsed = self.run_slow()
        self.assertGreaterEqual(len(fake.timeouts), 2, fake.timeouts)
        self.assertLessEqual(sum(fake.timeouts), self.coach.TURN_SECONDS, fake.timeouts)
        self.assertLessEqual(elapsed, self.coach.TURN_SECONDS)
        self.assertTrue(all(t <= self.coach.COACH_TIMEOUT for t in fake.timeouts), fake.timeouts)

    def test_built_in_rules_answer_after_the_cap(self):
        r, _fake, _elapsed = self.run_slow()
        self.assertEqual(r["mode"], "offline")
        self.assertEqual(r.get("notice"), self.coach.AI_OFFLINE_NOTICE)
        self.assertTrue(r["reply"])


if __name__ == "__main__":
    unittest.main()
