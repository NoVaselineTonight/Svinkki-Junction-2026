"""Minimal Claude Messages API client with tool use (urllib only).

The API key is only ever placed in the request header. It is never logged,
printed or included in an exception message.
"""
import json
import socket
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
MAX_TOKENS = 16000
EFFORT = "low"
TIMEOUT = 45
# Statuses worth one more try: the service was busy, not the request wrong.
_RETRY_STATUS = (500, 502, 503, 529)
RETRY_PAUSE = 0.6


class ClaudeError(Exception):
    """Any failure talking to Claude: HTTP error, timeout, refusal, cut-off or empty reply."""


def _default_post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()
        except Exception:
            return e.code, b""
    except (socket.timeout, TimeoutError):
        raise ClaudeError("Claude request timed out")
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise ClaudeError("Claude request timed out")
        raise ClaudeError("Claude request failed (network)")
    except OSError:
        raise ClaudeError("Claude request failed (network)")


def _error_type(raw):
    """The API's error type (for example authentication_error). Never the message text."""
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        t = (data.get("error") or {}).get("type")
        if isinstance(t, str) and t.replace("_", "").isalnum():
            return t[:60]
    except Exception:
        pass
    return ""


def create(system, messages, tools, api_key, model, http_post=None, timeout=TIMEOUT,
           allow_tools=True, max_tokens=MAX_TOKENS, effort=EFFORT):
    """POST /v1/messages and return the parsed message dict.

    system: text, or a list of texts (the first is the part that is the same for everyone; it is
    marked cacheable). messages: list of {"role", "content"}. tools: list of {"name", "description",
    "parameters"} declarations (may be empty); "parameters" is sent as `input_schema`.
    allow_tools=False keeps the declarations (the history may hold tool calls) but tells the model
    to answer in text. Raises ClaudeError on any failure, a refusal or a cut-off reply.
    """
    if not api_key:
        raise ClaudeError("No API key")
    parts = [str(p) for p in ([system] if isinstance(system, str) else list(system)) if p]
    blocks = [{"type": "text", "text": p} for p in parts]
    if blocks:
        # Tools and the first block are the same for every customer, so that prefix is cacheable.
        blocks[0]["cache_control"] = {"type": "ephemeral"}
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": blocks,
        "messages": messages,
        "output_config": {"effort": effort},
    }
    if tools:
        body["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                          "input_schema": t.get("parameters") or {"type": "object", "properties": {}}}
                         for t in tools]
        if not allow_tools:
            body["tool_choice"] = {"type": "none"}
    headers = {"content-type": "application/json", "x-api-key": api_key, "anthropic-version": API_VERSION}
    post = http_post or _default_post
    payload = json.dumps(body).encode("utf-8")
    status, raw = 0, b""
    for attempt in (0, 1):
        try:
            status, raw = post(API_URL, headers, payload, timeout)
        except ClaudeError:
            raise
        except Exception:
            raise ClaudeError("Claude request failed")
        if status not in _RETRY_STATUS or attempt:
            break
        time.sleep(RETRY_PAUSE)
    if status != 200:
        kind = _error_type(raw)
        raise ClaudeError("Claude returned HTTP %s%s" % (status, (" (%s)" % kind) if kind else ""))
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception:
        raise ClaudeError("Claude returned unreadable JSON")
    if not isinstance(data, dict) or data.get("type") != "message":
        raise ClaudeError("Claude returned an unexpected reply")
    stop = data.get("stop_reason")
    if stop == "refusal":
        raise ClaudeError("Claude declined the request")
    if stop == "max_tokens":
        raise ClaudeError("Claude's reply was cut off")
    if stop not in ("end_turn", "tool_use", "stop_sequence"):
        raise ClaudeError("Claude stopped unexpectedly (%s)" % str(stop)[:40])
    if not isinstance(data.get("content"), list) or not data["content"]:
        raise ClaudeError("Claude returned an empty reply")
    return data


def tool_uses(message):
    """The tool_use blocks of a reply, in order."""
    return [b for b in message.get("content") or [] if isinstance(b, dict) and b.get("type") == "tool_use"]


def text_of(message):
    """The visible text of a reply (thinking blocks are not text)."""
    return "".join(b.get("text", "") for b in message.get("content") or []
                   if isinstance(b, dict) and b.get("type") == "text").strip()


def ping(api_key, model, http_post=None, timeout=20):
    """One tiny request to check that the key and model work. Returns the model id that answered."""
    msg = create("Reply with the single word: ok", [{"role": "user", "content": "ping"}], [], api_key, model,
                 http_post=http_post, timeout=timeout, max_tokens=2000)
    return str(msg.get("model") or model)
