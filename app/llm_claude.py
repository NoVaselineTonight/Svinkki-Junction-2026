"""Minimal Claude (Anthropic Messages API) client with tool use (urllib only).

The API key is only ever placed in the request header. It is never logged, printed or
included in an exception message.
"""
import json
import socket
import urllib.error
import urllib.request

URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"


class ClaudeError(Exception):
    """Any failure talking to Claude: HTTP error, timeout, refusal or empty reply."""


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


def _parse(raw):
    try:
        return json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception:
        return None


def generate(system, messages, tools, api_key, model, http_post=None, timeout=60, max_tokens=16000):
    """POST one Messages request and return the parsed response dict.

    tools: project declarations {"name", "description", "parameters"} (may be empty).
    Raises ClaudeError on any failure.
    """
    if not api_key:
        raise ClaudeError("No API key")
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "output_config": {"effort": "low"},
    }
    if tools:
        body["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                          "input_schema": t.get("parameters") or t.get("input_schema")
                          or {"type": "object", "properties": {}}} for t in tools]
    headers = {"x-api-key": api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
    post = http_post or _default_post
    try:
        status, raw = post(URL, headers, json.dumps(body).encode("utf-8"), timeout)
    except ClaudeError:
        raise
    except (socket.timeout, TimeoutError):
        raise ClaudeError("Claude request timed out")
    except Exception:
        raise ClaudeError("Claude request failed")
    data = _parse(raw)
    if not isinstance(status, int) or status >= 400:
        etype = ""
        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            etype = str(data["error"].get("type") or "")[:60]
        raise ClaudeError("Claude returned HTTP %s%s" % (status, (" (%s)" % etype) if etype else ""))
    if not isinstance(data, dict):
        raise ClaudeError("Claude returned unreadable JSON")
    if data.get("stop_reason") == "refusal":
        raise ClaudeError("Claude declined the request")
    content = data.get("content")
    if not isinstance(content, list) or not content:
        raise ClaudeError("Claude returned an empty reply")
    if data.get("stop_reason") == "max_tokens":
        usable = any(isinstance(b, dict) and (b.get("type") == "tool_use"
                                              or (b.get("type") == "text" and str(b.get("text") or "").strip()))
                     for b in content)
        if not usable:
            raise ClaudeError("Claude ran out of tokens before answering")
    return data
