"""Fake Claude (the Messages API), injected at the urllib layer. Nothing here needs the network.

Use together with fixture.get(), which already points the key file and .env at files that do
not exist, so the only key the code can see is the fake one set by patched_claude.
"""
import io
import json
import os
import urllib.error
from unittest import mock

FAKE_KEY = "sk-ant-test-" + "x" * 30 + "LAST"   # shaped like a key, opens nothing


def cl_text(text, model="claude-opus-5-5", stop_reason="end_turn"):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": model,
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason,
            "usage": {"input_tokens": 10, "output_tokens": 5}}


def cl_call(name, args=None, tool_id="toolu_test_1", thinking=True):
    """A reply that asks for one tool, preceded (as the real model does) by a thinking block."""
    content = []
    if thinking:
        content.append({"type": "thinking", "thinking": "", "signature": "sig-abc"})
    content.append({"type": "tool_use", "id": tool_id, "name": name, "input": args or {}})
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": content, "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5}}


def cl_calls(*pairs):
    """A reply that asks for several tools at once: cl_calls(("get_spend", {...}), ("get_overview", {}))."""
    content = [{"type": "thinking", "thinking": "", "signature": "sig-abc"}]
    for i, (name, args) in enumerate(pairs):
        content.append({"type": "tool_use", "id": "toolu_test_%d" % (i + 1), "name": name, "input": args or {}})
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": content, "stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5}}


def cl_refusal():
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": "refusal",
            "stop_details": {"type": "refusal", "category": None, "explanation": "declined"}}


def http_error(status, error_type="api_error", message="details that must not be shown"):
    body = json.dumps({"type": "error", "error": {"type": error_type, "message": message}}).encode("utf-8")
    return urllib.error.HTTPError("https://api.anthropic.com/v1/messages", status, "error", {}, io.BytesIO(body))


class _FakeHTTPResponse(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}

    def getcode(self):
        return 200

    def info(self):
        return self.headers


class FakeClaude:
    """Stands in for urllib.request.urlopen. The last scripted item repeats forever."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.urls = []
        self.headers = []      # one dict per call, header names in lower case
        self.raw = []
        self.requests = []

    def __call__(self, req, *args, **kwargs):
        self.calls += 1
        self.urls.append(getattr(req, "full_url", str(req)))
        data = getattr(req, "data", None)
        self.raw.append(data or b"")
        try:
            self.headers.append({k.lower(): v for k, v in req.header_items()})
        except Exception:                          # noqa: BLE001
            self.headers.append({})
        try:
            self.requests.append(json.loads(data.decode("utf-8")) if data else None)
        except Exception:                          # noqa: BLE001
            self.requests.append(None)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return _FakeHTTPResponse(json.dumps(item).encode("utf-8"))

    def all_text(self):
        return "\n".join(r.decode("utf-8", "replace") for r in self.raw)


class patched_claude:
    """Context manager: set a (fake) Claude key and route all urllib.request.urlopen calls to the fake."""

    def __init__(self, fake, key=FAKE_KEY):
        self.fake = fake
        self.key = key
        self._patches = []
        self._old = None

    def __enter__(self):
        self._old = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = self.key
        import app.llm_claude as lc
        for p in (mock.patch("urllib.request.urlopen", self.fake), mock.patch.object(lc, "RETRY_PAUSE", 0)):
            p.start()
            self._patches.append(p)
        return self.fake

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        os.environ["ANTHROPIC_API_KEY"] = self._old if self._old is not None else ""
        return False
