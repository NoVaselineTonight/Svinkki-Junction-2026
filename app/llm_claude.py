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
_RETRY_STATUS = (429, 500, 502, 503, 529)
MAX_RETRIES = 2
MAX_RETRY_AFTER = 5.0
RETRY_PAUSE = 0.6
MIN_REQUEST_SECONDS = 3.0   # with less time than this left before the deadline, a request is not started


class ClaudeError(Exception):
    """Any failure talking to Claude: HTTP error, timeout, refusal, cut-off or empty reply."""


_LAST_RETRY_AFTER = [None]   # the retry-after header of the last HTTP error (default transport only)


def _retry_pause(headers):
    """Seconds to wait before a retry: the retry-after header up to MAX_RETRY_AFTER, else RETRY_PAUSE."""
    v = None
    if isinstance(headers, dict):
        for k, x in headers.items():
            if str(k).lower() == "retry-after":
                v = x
    try:
        return max(0.0, min(float(v), MAX_RETRY_AFTER))
    except (TypeError, ValueError):
        return RETRY_PAUSE


def _default_post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        _LAST_RETRY_AFTER[0] = (e.headers.get("retry-after") if getattr(e, "headers", None) else None)
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


def _time_left(deadline):
    return None if deadline is None else deadline - time.monotonic()


def create(system, messages, tools, api_key, model, http_post=None, timeout=TIMEOUT,
           allow_tools=True, max_tokens=MAX_TOKENS, effort=EFFORT, deadline=None):
    """POST /v1/messages and return the parsed message dict.

    system: text, or a list of texts (the first is the part that is the same for everyone, the last
    the per-customer part; both are marked cacheable, see below). messages: list of {"role", "content"}. tools: list of {"name", "description",
    "parameters"} declarations (may be empty); "parameters" is sent as `input_schema`.
    allow_tools=False keeps the declarations (the history may hold tool calls) but tells the model
    to answer in text. deadline: an absolute time.monotonic() value. Each attempt then waits at most the
    time left (never more than timeout), a retry that would end after it is not made, and with less than
    MIN_REQUEST_SECONDS left no request is started. Raises ClaudeError on any failure, a refusal or a
    cut-off reply, and when the deadline is reached.
    """
    if not api_key:
        raise ClaudeError("No API key")
    parts = [str(p) for p in ([system] if isinstance(system, str) else list(system)) if p]
    blocks = [{"type": "text", "text": p} for p in parts]
    # Prompt caching, 5-minute entries, at most 3 of the 4 breakpoints the API allows:
    # 1. tools + the first system block, the same for every customer;
    # 2. the last system block (the per-customer lines, thousands of tokens), read again on every
    #    round of a turn and on the next turn. It also survives the last round's tool_choice "none",
    #    which invalidates only the messages cache;
    # 3. top-level automatic caching for the message history (below), so each round reads what the
    #    round before sent. Markers never go inside `messages`, so they cannot pile up past 4.
    for i in {0, len(blocks) - 1} if blocks else ():
        blocks[i]["cache_control"] = {"type": "ephemeral"}
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": blocks,
        "messages": messages,
        "output_config": {"effort": effort},
    }
    if tools:
        # A conversation with tools runs several rounds. A one-off request (no tools, such as explaining
        # a pasted text) would only pay the cache-write premium on a tail nobody reads again.
        body["cache_control"] = {"type": "ephemeral"}
        body["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                          "input_schema": t.get("parameters") or {"type": "object", "properties": {}}}
                         for t in tools]
        if not allow_tools:
            body["tool_choice"] = {"type": "none"}
    headers = {"content-type": "application/json", "x-api-key": api_key, "anthropic-version": API_VERSION}
    post = http_post or _default_post
    payload = json.dumps(body).encode("utf-8")
    status, raw = 0, b""
    for attempt in range(MAX_RETRIES + 1):
        _LAST_RETRY_AFTER[0] = None
        wait = timeout
        left = _time_left(deadline)
        if left is not None:
            if left < MIN_REQUEST_SECONDS:
                raise ClaudeError("Claude turn took too long")
            wait = min(timeout, left)
        try:
            res = post(API_URL, headers, payload, wait)
            status, raw = res[0], res[1]
            if len(res) > 2 and isinstance(res[2], dict):      # a transport may also hand back the headers
                _LAST_RETRY_AFTER[0] = {str(k).lower(): v for k, v in res[2].items()}.get("retry-after")
        except ClaudeError:
            raise
        except Exception:
            raise ClaudeError("Claude request failed")
        if status not in _RETRY_STATUS or attempt >= MAX_RETRIES:
            break
        pause = _retry_pause({"retry-after": _LAST_RETRY_AFTER[0]})
        left = _time_left(deadline)
        if left is not None and left - pause < MIN_REQUEST_SECONDS:
            break                               # no time for another try: report the busy status
        time.sleep(pause)
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
