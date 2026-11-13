"""Claude as the AI model: config, client, coach tool loop, demo AI settings endpoints.

Acceptance: M3, M5; plan: SR-10, SR-12, SR-22, SR-23, SR-25. No real API is ever called: urllib.request.urlopen
is replaced by a fake and the key file/env are pointed at temp paths. claude_api_key.txt is never read.
"""
import io
import json
import logging
import os
import re
import socket
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture as fx

TODAY = fx.TODAY
A = fx.A_CID
KEY = "sk-ant-api03-FAKEFAKEFAKEFAKE-test9876"
ALLOWED_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


def tool_args(tool_name, **want):
    import app.tools as tools
    for t in tools.TOOLS:
        if t["name"] == tool_name:
            props = t["parameters"].get("properties", {})
            return {k: v for k, v in want.items() if k in props}
    raise AssertionError("tool %s not registered" % tool_name)


def c_text(text, stop="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": stop, "usage": {"input_tokens": 1, "output_tokens": 1}}


def c_tool(name, args, tid="toolu_01ABC", thinking=True):
    content = []
    if thinking:
        content.append({"type": "thinking", "thinking": "I should look this up.", "signature": "sig-xyz-123"})
    content.append({"type": "tool_use", "id": tid, "name": name, "input": args})
    return {"id": "msg_0", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": content, "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}}


def http_error(code):
    return urllib.error.HTTPError("https://api.anthropic.com/v1/messages", code, "err", {}, io.BytesIO(b'{"error":{"message":"x"}}'))


class FakeClaude(fx.FakeGemini):
    def __init__(self, script):
        super().__init__(script)
        self.headers = []

    def __call__(self, req, *a, **k):
        self.headers.append({kk.lower(): v for kk, v in req.header_items()})
        return super().__call__(req, *a, **k)


class claude_env:
    """Set a fake Claude key (or none), route urlopen to the fake, restore everything afterwards."""

    def __init__(self, fake=None, key=KEY, pop_key=False):
        self.fake, self.key, self.pop_key = fake, key, pop_key
        self.saved = None
        self.patches = []

    def __enter__(self):
        self.saved = os.environ.get("ANTHROPIC_API_KEY")
        if self.pop_key:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self.key
        if self.fake is not None:
            p = mock.patch("urllib.request.urlopen", self.fake)
            p.start()
            self.patches.append(p)
            try:
                import app.llm_claude as lc
                if hasattr(lc, "urlopen"):
                    p2 = mock.patch.object(lc, "urlopen", self.fake)
                    p2.start()
                    self.patches.append(p2)
            except ImportError:
                pass
        return self.fake

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        if self.saved is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self.saved
        return False


class capture_logs:
    def __enter__(self):
        self.buf = io.StringIO()
        self.old = (sys.stdout, sys.stderr)
        sys.stdout = sys.stderr = self.buf
        self.h = logging.StreamHandler(self.buf)
        logging.getLogger().addHandler(self.h)
        return self

    def __exit__(self, *exc):
        time.sleep(0.4)
        logging.getLogger().removeHandler(self.h)
        sys.stdout, sys.stderr = self.old
        return False

    @property
    def text(self):
        return self.buf.getvalue()


def restore_env(saved):
    for n, v in saved.items():
        if v is None:
            os.environ.pop(n, None)
        else:
            os.environ[n] = v


# ---------------------------------------------------------------------------------------------
class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.config as config
        cls.config = config

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keyfile = Path(self.tmp.name) / "key.txt"
        self.saved = {n: os.environ.get(n) for n in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "SVINKKI_AI_KEY_FILE", "SVINKKI_AI_SETTINGS")}
        os.environ["SVINKKI_AI_KEY_FILE"] = str(self.keyfile)
        os.environ["SVINKKI_AI_SETTINGS"] = str(Path(self.tmp.name) / "settings.json")
        os.environ["ANTHROPIC_API_KEY"] = ""
        os.environ["GEMINI_API_KEY"] = ""

    def tearDown(self):
        restore_env(self.saved)
        self.tmp.cleanup()

    def test_env_wins_even_when_empty(self):
        self.keyfile.write_text("sk-ant-from-file\n", encoding="utf-8")
        os.environ["ANTHROPIC_API_KEY"] = ""
        self.assertEqual(self.config.claude_api_key(), "")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-from-env"
        self.assertEqual(self.config.claude_api_key(), "sk-ant-from-env")

    def test_file_first_line_when_env_undefined(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.keyfile.write_text("sk-ant-from-file\nsecond line\n", encoding="utf-8")
        self.assertEqual(self.config.claude_api_key(), "sk-ant-from-file")

    def test_no_env_and_no_file_is_empty(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertEqual(self.config.claude_api_key(), "")

    def test_provider_preference(self):
        self.assertEqual(self.config.ai_provider(), "none")
        os.environ["GEMINI_API_KEY"] = "g-key"
        self.assertEqual(self.config.ai_provider(), "gemini")
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-x"
        self.assertEqual(self.config.ai_provider(), "claude")
        os.environ["GEMINI_API_KEY"] = ""
        self.assertEqual(self.config.ai_provider(), "claude")

    def test_model_default_and_allowed(self):
        self.assertEqual(self.config.claude_model(), "claude-opus-5-5")
        self.assertIn(self.config.claude_model(), ALLOWED_MODELS)


# ---------------------------------------------------------------------------------------------
class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.llm_claude as lc
        cls.lc = lc

    def gen(self, script):
        fake = FakeClaude(script)
        tools = [{"name": "get_spend", "description": "d", "parameters": {"type": "object", "properties": {"period": {"type": "string"}}}}]
        with claude_env(fake):
            out = self.lc.generate("SYSTEM TEXT", [{"role": "user", "content": "hi"}], tools, KEY, "claude-opus-5-5")
        return out, fake

    def test_request_shape(self):
        out, fake = self.gen([c_text("hello")])
        self.assertIsInstance(out, dict)
        self.assertEqual(fake.urls[0], "https://api.anthropic.com/v1/messages")
        h = fake.headers[0]
        self.assertEqual(h["x-api-key"], KEY)
        self.assertEqual(h["anthropic-version"], "2026-10-21")
        self.assertEqual(h["content-type"], "application/json")
        body = fake.requests[0]
        self.assertEqual(body["model"], "claude-opus-5-5")
        self.assertIn("max_tokens", body)
        self.assertEqual(body["system"], "SYSTEM TEXT")
        self.assertEqual(body["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(body["output_config"], {"effort": "low"})
        for forbidden in ("temperature", "top_p", "top_k"):
            self.assertNotIn(forbidden, body)
        self.assertEqual([t["name"] for t in body["tools"]], ["get_spend"])
        for t in body["tools"]:
            self.assertEqual(set(t), {"name", "description", "input_schema"})
        self.assertNotIn(KEY, fake.raw[0].decode("utf-8"), "the key travels only in the header")

    def test_errors_raise_claude_error(self):
        cases = {"http500": http_error(500), "http401": http_error(401), "timeout": socket.timeout("timed out"),
                 "urlerror": urllib.error.URLError("down"), "refusal": c_text("no", stop="refusal"),
                 "empty": {"id": "m", "type": "message", "role": "assistant", "content": [], "stop_reason": "end_turn"}}
        for name, item in cases.items():
            with self.subTest(name):
                with self.assertRaises(self.lc.ClaudeError):
                    self.gen([item])

    def test_bad_json_raises_claude_error(self):
        def bad(req, *a, **k):
            return fx._FakeHTTPResponse(b"<html>not json")
        with claude_env(bad):
            with self.assertRaises(self.lc.ClaudeError):
                self.lc.generate("s", [{"role": "user", "content": "x"}], [], KEY, "claude-opus-5-5")


# ---------------------------------------------------------------------------------------------
class ClaudeCoachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.tools as tools
        cls.coach, cls.tools = coach, tools

    def setUp(self):
        self.ctx = fx.make_ctx(A)
        self.args = tool_args("get_spend", period="last_month", label="Taxi")

    def run_chat(self, script, message="How much did I spend on taxis last month?", ctx=None):
        fake = FakeClaude(script)
        with claude_env(fake):
            r = self.coach.chat(message, [], ctx or self.ctx)
        return r, fake

    def clean(self, fake):
        text = fake.all_text()
        self.assertTrue(text)
        self.assertNotRegex(text, r"CUST\d{5}")
        for c in fx.CUSTOMERS:
            self.assertNotIn(c["postal"], text)
        self.assertNotRegex(text, r"MX\d{5}")
        self.assertNotRegex(text, r'(?i)"age"\s*:\s*\d')
        self.assertNotRegex(text, r"(?i)\bage\W{0,6}31\b|\b31[- ]years?|\baged 31")
        self.assertNotIn("Testa", text)
        self.assertNotIn(KEY, text, "the key appears only in the x-api-key header")

    def test_tool_loop_echoes_content_and_returns_tool_number(self):
        first = c_tool("get_spend", self.args)
        r, fake = self.run_chat([first, c_text("You spent €62.10 on taxis last month.")])
        self.assertEqual(r["mode"], "claude")
        self.assertIn("get_spend", r["tools_used"])
        self.assertTrue(fx.text_has_amount(r["reply"], 62.10), r["reply"])
        self.assertEqual(fake.calls, 2)
        second = fake.requests[1]["messages"]
        assistant = [m for m in second if m["role"] == "assistant"][-1]
        self.assertEqual(assistant["content"], first["content"], "the assistant content, thinking block included, is sent back verbatim")
        last = second[-1]
        self.assertEqual(last["role"], "user")
        self.assertIsInstance(last["content"], list)
        results = [b for b in last["content"] if b.get("type") == "tool_result"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tool_use_id"], "toolu_01ABC")
        self.assertIn("62.1", json.dumps(results[0]["content"]))
        for h in fake.headers:
            self.assertEqual(h["x-api-key"], KEY)
        self.assertTrue(r["cards"])
        self.assertTrue(r["evidence"])

    def test_payload_is_clean_even_for_transaction_rows(self):
        lt = tool_args("list_transactions", label="Taxi")
        r, fake = self.run_chat([c_tool("list_transactions", lt), c_text("Here are your taxi rides.")], message="List my taxi rides")
        self.assertGreaterEqual(fake.calls, 2)
        self.clean(fake)

    def test_tools_are_declared_without_identity_parameters(self):
        _, fake = self.run_chat([c_text("hi")], message="hi")
        body = fake.requests[0]
        self.assertEqual(sorted(t["name"] for t in body["tools"]), sorted(t["name"] for t in self.tools.TOOLS))
        self.assertTrue(body["system"])
        self.assertNotIn("customer", json.dumps([t["input_schema"] for t in body["tools"]]).lower())

    def test_invented_amount_is_not_returned(self):
        r, _ = self.run_chat([c_tool("get_spend", self.args), c_text("You spent €999.99 on taxis last month.")])
        self.assertNotIn("999.99", r["reply"])
        r, _ = self.run_chat([c_text("You spent about €123.45 on taxis.")])
        self.assertNotIn("123.45", r["reply"])

    def test_claude_errors_fall_back_to_the_built_in_rules_and_say_so(self):
        for name, item in (("500", http_error(500)), ("401", http_error(401)),
                           ("refusal", c_text("I can't help", stop="refusal"))):
            with self.subTest(name):
                r, _ = self.run_chat([item])
                self.assertEqual(r["mode"], "offline")
                self.assertTrue(fx.text_has_amount(r["reply"], 62.10), r["reply"])
                self.assertRegex(r["reply"].lower(), r"ai model|unavailable|not available|offline|couldn't reach|could not reach")
                self.assertNotIn(KEY, json.dumps(r, default=str))

    def test_no_ai_consent_means_no_request(self):
        ctx = fx.make_ctx(A, consent={"analysis": True, "ai": False, "benchmarks": True, "suggestions": True})
        r, fake = self.run_chat([c_text("never")], ctx=ctx)
        self.assertEqual(fake.calls, 0)
        self.assertEqual(r["mode"], "offline")
        self.assertTrue(fx.text_has_amount(r["reply"], 62.10))

    def test_explore_tool_attacks_through_claude_change_nothing(self):
        props, required = {}, []
        for x in self.tools.TOOLS:
            if x["name"] == "explore_my_data":
                props, required = x["parameters"].get("properties", {}), x["parameters"].get("required", [])
        p = (required or list(props))[0]
        before = self.ctx.conn.execute("SELECT count(*), round(sum(amount),2) FROM tx").fetchone()
        script = [c_tool("explore_my_data", {p: "DROP TABLE tx"}, "t1", False),
                  c_tool("explore_my_data", {p: "SELECT * FROM customers"}, "t2", False),
                  c_tool("explore_my_data", {p: "SELECT * FROM tx LIMIT 5"}, "t3", False),
                  c_text("done")]
        r, fake = self.run_chat(script, message="run queries")
        after = self.ctx.conn.execute("SELECT count(*), round(sum(amount),2) FROM tx").fetchone()
        self.assertEqual(tuple(before), tuple(after))
        self.clean(fake)


# ---------------------------------------------------------------------------------------------
class AiSettingsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.keyfile = Path(self.tmp.name) / "claude_key.txt"
        self.settings = Path(self.tmp.name) / "ai_settings.json"
        self.saved = {n: os.environ.get(n) for n in ("ANTHROPIC_API_KEY", "SVINKKI_AI_KEY_FILE", "SVINKKI_AI_SETTINGS")}
        os.environ["SVINKKI_AI_KEY_FILE"] = str(self.keyfile)
        os.environ["SVINKKI_AI_SETTINGS"] = str(self.settings)
        os.environ.pop("ANTHROPIC_API_KEY", None)           # undefined, so the key file is consulted
        self.server = fx.Server()
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            try:
                c.post("/api/privacy/erase", {})
            except Exception:                                  # noqa: BLE001
                pass
        self.server.stop()
        restore_env(self.saved)
        self.tmp.cleanup()

    def sess(self):
        c = fx.session(self.server, "A")
        self.clients.append(c)
        return c

    def test_both_endpoints_need_a_session(self):
        c = self.server.client()
        self.assertIn(c.get("/api/demo/ai").status, (401, 403))
        self.assertIn(c.post("/api/demo/ai", {"model": "claude-haiku-5-5"}).status, (401, 403))
        self.assertIn(c.post("/api/demo/ai", {"clear_key": True}).status, (401, 403))

    def test_get_shape_and_no_key_by_default(self):
        c = self.sess()
        r = c.get("/api/demo/ai")
        self.assertEqual(r.status, 200)
        j = r.json
        for k in ("provider", "model", "key_set", "key_hint", "models"):
            self.assertIn(k, j)
        self.assertIs(j["key_set"], False)
        self.assertEqual(j["provider"], "none")
        self.assertEqual(j["model"], "claude-opus-5-5")
        self.assertEqual(sorted(j["models"]), sorted(ALLOWED_MODELS))
        self.assertIs(c.get("/api/me").json["ai_available"], False)

    def test_model_change_validates_and_persists_across_servers(self):
        c = self.sess()
        r = c.post("/api/demo/ai", {"model": "claude-haiku-5-5"})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(c.get("/api/demo/ai").json["model"], "claude-haiku-5-5")
        for bad in ("gpt-5", "", 5, None, "claude-opus-5-5; drop"):
            self.assertEqual(c.post("/api/demo/ai", {"model": bad}).status, 400, bad)
        self.assertEqual(c.get("/api/demo/ai").json["model"], "claude-haiku-5-5")
        self.server.stop()
        self.server = fx.Server()
        c2 = self.sess()
        self.assertEqual(c2.get("/api/demo/ai").json["model"], "claude-haiku-5-5", "persisted in SVINKKI_AI_SETTINGS")
        self.assertTrue(self.settings.exists())

    def test_key_is_written_hidden_validated_and_cleared(self):
        c = self.sess()
        with capture_logs() as logs:
            r = c.post("/api/demo/ai", {"key": KEY})
            self.assertEqual(r.status, 200, r.text)
            self.assertNotIn(KEY, r.text)
            g = c.get("/api/demo/ai")
            me = c.get("/api/me")
        self.assertNotIn(KEY, g.text)
        self.assertNotIn(KEY, me.text)
        self.assertNotIn(KEY, logs.text, "the key must not reach the logs")
        self.assertNotIn(KEY[8:-4], logs.text)
        self.assertEqual(self.keyfile.read_text(encoding="utf-8").strip().splitlines()[0], KEY)
        j = g.json
        self.assertIs(j["key_set"], True)
        self.assertEqual(j["provider"], "claude")
        shown = re.sub(r"[^A-Za-z0-9]", "", j["key_hint"] or "")
        self.assertLessEqual(len(shown), 4)
        self.assertNotIn(KEY[:-4], j["key_hint"] or "")
        self.assertIs(me.json["ai_available"], True)
        for bad in ("sk-wrong-" + "x" * 20, "abc", "", "sk-ant-" + "x" * 300, 12345, None, ["sk-ant-x"]):
            rb = c.post("/api/demo/ai", {"key": bad})
            self.assertEqual(rb.status, 400, repr(bad)[:30])
            self.assertNotIn(KEY, rb.text)
        self.assertEqual(self.keyfile.read_text(encoding="utf-8").strip().splitlines()[0], KEY, "a rejected key changes nothing")
        r = c.post("/api/demo/ai", {"clear_key": True})
        self.assertEqual(r.status, 200)
        self.assertIs(c.get("/api/demo/ai").json["key_set"], False)
        self.assertIs(c.get("/api/me").json["ai_available"], False)
        self.assertFalse(self.keyfile.exists() and self.keyfile.read_text(encoding="utf-8").strip())

    def test_chat_uses_claude_when_a_key_is_set(self):
        c = self.sess()
        c.post("/api/demo/ai", {"key": KEY})
        args = tool_args("get_spend", period="last_month", label="Taxi")
        fake = FakeClaude([c_tool("get_spend", args), c_text("You spent €62.10 on taxis last month.")])
        with mock.patch("urllib.request.urlopen", fake):
            r = c.post("/api/chat", {"message": "How much did I spend on taxis last month?"})
        self.assertEqual(r.status, 200, r.text)
        self.assertEqual(r.json["mode"], "claude")
        self.assertTrue(fx.text_has_amount(r.json["reply"], 62.10))
        self.assertNotIn(KEY, r.text)
        seen = c.get("/api/privacy/ai-payload")
        self.assertNotIn(KEY, seen.text)
        self.assertNotRegex(seen.text, r"CUST\d{5}")


if __name__ == "__main__":
    unittest.main()
