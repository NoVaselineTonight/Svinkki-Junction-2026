"""Live check of the Claude path: the real server, in-process, as Veeti on the real data.

Measures every Claude request (model, wall time, stop_reason, usage) and every chat turn (reply, mode,
notice, raw model text, latency, tool calls, what the AI saw). Results are written OUTSIDE the repository
(answers are built on the dataset): --out, default C:/Users/onnik/Desktop/svinkki-orch/live-check/.

Money: every live turn is appended to the shared live_budget.log BEFORE it is made, and the run refuses to
go past --budget turns for this agent. --dry runs the same plan with no key (built-in rules, nothing billed).
The key is never printed, logged or written anywhere by this script.

    python .devloop/live-check/harness.py --dry
    python .devloop/live-check/harness.py --plan opus          # the DEMO.md questions on the default model
    python .devloop/live-check/harness.py --plan others        # latency on Sonnet 5.5 and Haiku 5.5
"""
import argparse
import http.cookiejar
import io
import json
import os
import sys
import threading
import time
import urllib.request

ROOT = r"C:/Users/onnik/Desktop/TEMU claude/workspace/Svinkki-Junction-2026"
ORCH = "C:/Users/onnik/Desktop/svinkki-orch"
AGENT = "agent-c"
BUDGET_LOG = ORCH + "/live_budget.log"
KEY_FILE = "C:/Users/onnik/Desktop/challenge-1/claude_api_key.txt"

# USD per million tokens (claude-api skill, cached 2026-11-03): input, output, cache read, 5-minute cache write.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}

# Each conversation is a list of questions; a new conversation starts where the demo goes back home.
PLANS = {
    "car": [("claude-opus-5-5", [["Make me a plan to save up for a car"], ["I want to buy a car by summer 2027, how?"], ["Tee minulle suunnitelma säästää autoon"], ["I want to save for a new sofa"]])],
    "opus": [("claude-opus-5-5", [
        ["How much did I spend on taxis last month?", "and the month before?", "Can I afford a 300 euro jacket?",
         "What do I buy most?", "Show my last receipt",
         "I want to go to Japan in 2027", "3000 euros", "ok set it"],
        ["Paljonko käytin takseihin viime kuussa?"],
        ["Where can I save?"],
        ["Remember that my rent goes up to 950 in January"],
        ["Can I afford a 300 euro payday loan?"],
    ])],
    "others": [
        ("claude-sonnet-5-5", [["How much did I spend on taxis last month?"], ["Can I afford a 300 euro jacket?"],
                               ["Where can I save?"]]),
        ("claude-haiku-5-5", [["How much did I spend on taxis last month?"], ["Can I afford a 300 euro jacket?"],
                              ["Where can I save?"]]),
    ],
}


def setup_env(dry, run_name):
    os.makedirs(ORCH, exist_ok=True)
    state_db = "%s/state-%s-%s.db" % (ORCH, AGENT, run_name)
    ai_file = "%s/ai-%s-%s.json" % (ORCH, AGENT, run_name)
    for p in (state_db, ai_file):
        if os.path.exists(p):
            os.remove(p)                       # a clean demo state for Veeti every run
    os.environ.update({
        "SVINKKI_DB": "C:/Users/onnik/Desktop/challenge-1/data/svinkki.db",
        "SVINKKI_STATE_DB": state_db,
        "SVINKKI_AI_SETTINGS_FILE": ai_file,
        "SVINKKI_AI_KEY_FILE": "/nonexistent" if dry else KEY_FILE,
        "SVINKKI_ENV_FILE": "/nonexistent",
        "ANTHROPIC_API_KEY": "",
        "GEMINI_API_KEY": "",
        "SVINKKI_TODAY": "2026-09-26",
    })


def budget_used():
    try:
        with open(BUDGET_LOG, encoding="utf-8") as f:
            return sum(1 for line in f if line.startswith(AGENT + ","))
    except OSError:
        return 0


def log_budget(model, question):
    with open(BUDGET_LOG, "a", encoding="utf-8") as f:
        f.write("%s, %s, %s\n" % (AGENT, model, question.replace("\n", " ")[:120]))


class Tee(io.TextIOBase):
    """stderr copy, so the coach's fallback line ('claude path failed (...)') is kept per turn."""
    def __init__(self, inner):
        self.inner, self.lines, self._lock = inner, [], threading.Lock()

    def write(self, s):
        with self._lock:
            self.lines.append(s)
        return self.inner.write(s)

    def flush(self):
        self.inner.flush()


def cost(model, usage):
    p = PRICES.get(model)
    if not p or not usage:
        return 0.0
    return (usage.get("input_tokens", 0) * p[0] + usage.get("output_tokens", 0) * p[1] +
            usage.get("cache_read_input_tokens", 0) * p[2] + usage.get("cache_creation_input_tokens", 0) * p[3]) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", choices=sorted(PLANS), default="opus")
    ap.add_argument("--dry", action="store_true", help="no key: built-in rules, nothing billed")
    ap.add_argument("--budget", type=int, default=18, help="max live turns for this agent (all runs together)")
    ap.add_argument("--port", type=int, default=8040)
    ap.add_argument("--out", default=ORCH + "/live-check")
    args = ap.parse_args()
    run_name = args.plan + ("-dry" if args.dry else "")
    setup_env(args.dry, run_name)
    sys.path.insert(0, ROOT)
    from app import coach, llm_claude, server     # imported after the environment is set

    requests_log = []
    real_create = llm_claude.create

    def create(system, messages, tools, api_key, model, **kw):
        t0 = time.monotonic()
        rec = {"model": model, "timeout": kw.get("timeout"), "effort": kw.get("effort"),
               "allow_tools": kw.get("allow_tools", True), "n_messages": len(messages)}
        try:
            msg = real_create(system, messages, tools, api_key, model, **kw)
        except Exception as e:
            rec.update(wall=round(time.monotonic() - t0, 2), error="%s: %s" % (type(e).__name__, str(e)[:160]))
            requests_log.append(rec)
            raise
        rec.update(wall=round(time.monotonic() - t0, 2), stop_reason=msg.get("stop_reason"),
                   answered_by=msg.get("model"), usage=msg.get("usage") or {},
                   tool_uses=[u.get("name") for u in llm_claude.tool_uses(msg)],
                   text=llm_claude.text_of(msg)[:3000])
        requests_log.append(rec)
        return msg

    llm_claude.create = create
    raw_texts = []
    real_tidy = coach.tidy_model_text

    def tidy(text, message="", card=None):
        raw_texts.append(str(text or ""))
        return real_tidy(text, message, card)

    coach.tidy_model_text = tidy
    tee = Tee(sys.stderr)
    sys.stderr = tee

    srv = server.make_server("127.0.0.1", args.port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % args.port
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def api(path, body=None, timeout=400):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method="POST" if data is not None else "GET",
                                     headers={"content-type": "application/json", "origin": base})
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "null")

    personas = api("/api/demo/personas")
    veeti = next(p for p in personas if p["name"].startswith("Veeti"))
    api("/api/demo/login", {"id": veeti["id"]})
    api("/api/consent", {"analysis": True, "ai": True, "benchmarks": True, "suggestions": True})

    turns = []
    os.makedirs(args.out, exist_ok=True)
    for model, convs in PLANS[args.plan]:
        os.environ["CLAUDE_MODEL"] = model     # read at call time; the fresh settings file holds no choice
        for conv in convs:
            conv_id = None
            for q in conv:
                if not args.dry:
                    if budget_used() >= args.budget:
                        print("BUDGET REACHED (%d turns): stopping before %r" % (args.budget, q))
                        break
                    log_budget(model, q)
                r0, t0, e0, x0 = len(requests_log), time.monotonic(), len(tee.lines), len(raw_texts)
                err = None
                try:
                    res = api("/api/chat", {"message": q, "conversation_id": conv_id} if conv_id else {"message": q})
                except Exception as e:
                    res, err = {}, "%s: %s" % (type(e).__name__, str(e)[:200])
                total = round(time.monotonic() - t0, 2)
                conv_id = res.get("conversation_id") or conv_id
                reqs = requests_log[r0:]
                try:
                    saw = api("/api/privacy/ai-payload")
                except Exception:
                    saw = None
                usage = {k: sum((r.get("usage") or {}).get(k, 0) or 0 for r in reqs)
                         for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                   "cache_creation_input_tokens")}
                raw = raw_texts[x0:]
                reply = res.get("reply", "")
                t = {"model": model, "question": q, "reply": reply, "mode": res.get("mode"),
                     "notice": res.get("notice"), "latency_s": total, "n_requests": len(reqs),
                     "requests": reqs, "tools_used": res.get("tools_used"), "usage": usage,
                     "cost_usd": round(sum(cost(r["model"], r.get("usage")) for r in reqs), 5),
                     "model_raw_text": raw[-1] if raw else None,
                     "raw_equals_shown": (raw[-1].strip() == reply.strip()) if raw else None,
                     "repair": (saw or {}).get("repair") if isinstance(saw, dict) else None,
                     "stderr": "".join(l for l in "".join(tee.lines[e0:]).splitlines(True) if "coach:" in l).strip() or None, "http_error": err,
                     "what_the_ai_saw": saw}
                turns.append(t)
                print("[%s] %-45s %6.1fs req=%d mode=%s notice=%s cost=$%.4f" % (
                    model, q[:45], total, len(reqs), t["mode"], bool(t["notice"]), t["cost_usd"]))
                print("    -> " + reply.replace("\n", " ")[:300])
                with open(os.path.join(args.out, run_name + ".json"), "w", encoding="utf-8") as f:
                    json.dump(turns, f, ensure_ascii=False, indent=1, default=str)
            else:
                continue
            break
    srv.shutdown()
    write_summary(turns, os.path.join(args.out, run_name + ".md"))
    print("written:", os.path.join(args.out, run_name + ".json"))


def write_summary(turns, path):
    def cut(s, n=160):
        s = " ".join(str(s or "").split())
        return s if len(s) <= n else s[:n - 1] + "..."
    lines = ["| # | model | question | latency s | req | per-request s | in / out / cache r / cache w | cost $ | mode | number check | reply |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, t in enumerate(turns, 1):
        u = t["usage"]
        check = "notice: " + cut(t["notice"], 80) if t["notice"] else ("repaired: " + t["repair"] if t["repair"] else "ok")
        if t["raw_equals_shown"] is False and not t["notice"]:
            check += " (tidied)"
        lines.append("| %d | %s | %s | %.1f | %d | %s | %d / %d / %d / %d | %.4f | %s | %s | %s |" % (
            i, t["model"].replace("claude-", ""), cut(t["question"], 50), t["latency_s"], t["n_requests"],
            " ".join("%.1f" % r["wall"] for r in t["requests"]), u["input_tokens"], u["output_tokens"],
            u["cache_read_input_tokens"], u["cache_creation_input_tokens"], t["cost_usd"], t["mode"],
            check.replace("|", "/"), cut(t["reply"]).replace("|", "/")))
    by = {}
    for t in turns:
        by.setdefault(t["model"], []).append(t)
    lines += ["", "| model | turns | median s | max s | mean cost $ | total $ |", "|---|---|---|---|---|---|"]
    for m, ts in by.items():
        lat = sorted(t["latency_s"] for t in ts)
        med = lat[len(lat) // 2] if len(lat) % 2 else (lat[len(lat) // 2 - 1] + lat[len(lat) // 2]) / 2
        tot = sum(t["cost_usd"] for t in ts)
        lines.append("| %s | %d | %.1f | %.1f | %.4f | %.4f |" % (m, len(ts), med, lat[-1], tot / len(ts), tot))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
