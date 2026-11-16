"""app.llm_claude.create honours an absolute deadline, so a whole coach turn can have a real cap."""
import json
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm_claude as lc  # noqa: E402

OK = json.dumps({"type": "message", "role": "assistant", "model": "claude-opus-5-5", "stop_reason": "end_turn",
                 "content": [{"type": "text", "text": "Hello"}], "usage": {}}).encode()
BUSY = json.dumps({"type": "error", "error": {"type": "overloaded_error"}}).encode()


class Transport:
    """A fake transport that records the timeout of every attempt and answers from a script."""
    def __init__(self, *replies):
        self.replies, self.timeouts = list(replies), []

    def __call__(self, url, headers, body, timeout):
        self.timeouts.append(timeout)
        return self.replies.pop(0)


def call(post, **kw):
    return lc.create("Rules.", [{"role": "user", "content": "hi"}], [], "key", "claude-opus-5-5",
                     http_post=post, **kw)


class DeadlineTests(unittest.TestCase):
    def test_no_deadline_keeps_the_timeout(self):
        t = Transport((200, OK))
        call(t, timeout=60)
        self.assertEqual(t.timeouts, [60])

    def test_request_waits_at_most_the_time_left(self):
        t = Transport((200, OK))
        call(t, timeout=60, deadline=time.monotonic() + 20)
        self.assertEqual(len(t.timeouts), 1)
        self.assertLessEqual(t.timeouts[0], 20)
        self.assertGreater(t.timeouts[0], 15)

    def test_timeout_stays_the_ceiling_when_the_deadline_is_far(self):
        t = Transport((200, OK))
        call(t, timeout=30, deadline=time.monotonic() + 500)
        self.assertEqual(t.timeouts, [30])

    def test_no_request_is_started_after_the_deadline(self):
        t = Transport((200, OK))
        with self.assertRaises(lc.ClaudeError) as cm:
            call(t, timeout=60, deadline=time.monotonic() + 1)
        self.assertEqual(t.timeouts, [])
        self.assertIn("too long", str(cm.exception))

    def test_no_retry_that_would_end_after_the_deadline(self):
        t = Transport((529, BUSY), (200, OK))
        with mock.patch.object(lc.time, "sleep") as sleep:
            with self.assertRaises(lc.ClaudeError) as cm:
                call(t, timeout=60, deadline=time.monotonic() + lc.MIN_REQUEST_SECONDS + 0.2)
        self.assertEqual(len(t.timeouts), 1)
        sleep.assert_not_called()
        self.assertIn("529", str(cm.exception))

    def test_retry_still_happens_with_time_to_spare(self):
        t = Transport((529, BUSY), (200, OK))
        with mock.patch.object(lc.time, "sleep"):
            out = call(t, timeout=60, deadline=time.monotonic() + 100)
        self.assertEqual(lc.text_of(out), "Hello")
        self.assertEqual(len(t.timeouts), 2)


if __name__ == "__main__":
    unittest.main()
