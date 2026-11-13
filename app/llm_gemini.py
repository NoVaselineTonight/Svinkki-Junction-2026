"""Minimal Gemini REST client with function calling (urllib only).

The API key is only ever placed in the request header. It is never logged,
printed or included in an exception message.
"""
import json
import socket
import urllib.error
import urllib.request

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiError(Exception):
    """Any failure talking to Gemini: HTTP error, timeout, blocked or empty reply."""


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
        raise GeminiError("Gemini request timed out")
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise GeminiError("Gemini request timed out")
        raise GeminiError("Gemini request failed (network)")
    except OSError:
        raise GeminiError("Gemini request failed (network)")


def generate(system, contents, tools, api_key, model, http_post=None, timeout=20):
    """Call generateContent and return the parsed response dict.

    tools: list of {"name", "description", "parameters"} declarations (may be empty).
    Raises GeminiError on any failure.
    """
    if not api_key:
        raise GeminiError("No API key")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": list(tools)}]
    url = BASE_URL.format(model=model)
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    post = http_post or _default_post
    try:
        status, raw = post(url, headers, json.dumps(body).encode("utf-8"), timeout)
    except GeminiError:
        raise
    except Exception:
        raise GeminiError("Gemini request failed")
    if status != 200:
        raise GeminiError("Gemini returned HTTP %s" % status)
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception:
        raise GeminiError("Gemini returned unreadable JSON")
    if not isinstance(data, dict):
        raise GeminiError("Gemini returned an unexpected reply")
    fb = data.get("promptFeedback") or {}
    if fb.get("blockReason"):
        raise GeminiError("Gemini blocked the request (%s)" % fb.get("blockReason"))
    cands = data.get("candidates") or []
    if not cands:
        raise GeminiError("Gemini returned no candidates")
    content = cands[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        raise GeminiError("Gemini returned an empty reply (%s)" % cands[0].get("finishReason", "unknown"))
    return data
