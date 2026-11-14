"""Live eval loop for the coach: ask, judge, summarise, with a hard money budget across all runs.

    python .devloop/coach-bank/eval_loop.py run   NAME [--banks bank_data,bank_goals,bank_messy] [--ids A,B]
    python .devloop/coach-bank/eval_loop.py judge NAME
    python .devloop/coach-bank/eval_loop.py report NAME [OTHER]     # scores, issues, worst; OTHER = compare
    python .devloop/coach-bank/eval_loop.py spent

Every Claude request (the coach's and the judge's) is priced from its `usage` and added to
data/coach-runs/ledger.json BEFORE the next request starts; nothing new starts once the ledger reaches
EVAL_BUDGET_USD (default 50). Answers stay in data/coach-runs/ (git-ignored: they hold dataset figures).

Environment: SVINKKI_DB (the built database), SVINKKI_AI_KEY_FILE (one-line key file), SVINKKI_TODAY.
"""
import glob
import http.cookiejar
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "data", "coach-runs")
os.makedirs(OUT, exist_ok=True)
LEDGER = os.path.join(OUT, "ledger.json")
BUDGET = float(os.environ.get("EVAL_BUDGET_USD", "50"))
JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "claude-opus-5-5")
# USD per million tokens: input, output, cache read, 5-minute cache write (claude-api skill, cached 2026-11-03)
PRICES = {"claude-opus-5-5": (4.00, 20.00, 0.20, 5.00), "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
          "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125)}
_lock = threading.Lock()


def _load_ledger():
    """The ledger, or a fresh one when it does not exist yet. A ledger that cannot be read stops everything:
    starting again from zero would let the runs spend past the budget."""
    if not os.path.exists(LEDGER):
        return {"total": 0.0, "by_run": {}}
    for _ in range(50):
        try:
            with open(LEDGER, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            time.sleep(0.1)       # another process is replacing it this instant
    raise SystemExit("ledger %s cannot be read: fix it by hand before spending more" % LEDGER)


def spent():
    return _load_ledger()["total"]


class _FileLock:
    """One process at a time updates the ledger (several runs may be going at once)."""
    def __enter__(self):
        self.path = LEDGER + ".lock"
        for _ in range(600):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() - os.path.getmtime(self.path) > 30:
                    os.remove(self.path)       # left behind by a killed process
                time.sleep(0.05)
        raise SystemExit("ledger lock %s is stuck" % self.path)

    def __exit__(self, *exc):
        os.close(self.fd)
        os.remove(self.path)


def charge(run, kind, model, usage):
    p = PRICES.get(model, PRICES["claude-opus-5-5"])
    u = usage or {}
    cost = (u.get("input_tokens", 0) * p[0] + u.get("output_tokens", 0) * p[1] +
            u.get("cache_read_input_tokens", 0) * p[2] + u.get("cache_creation_input_tokens", 0) * p[3]) / 1e6
    with _lock, _FileLock():
        led = _load_ledger()
        led["total"] = round(led["total"] + cost, 6)
        r = led["by_run"].setdefault(run, {})
        r[kind] = round(r.get(kind, 0.0) + cost, 6)
        tmp = LEDGER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(led, f, indent=1)
        os.replace(tmp, LEDGER)        # atomic: a reader never sees half a file
    return cost


class BudgetReached(Exception):
    pass


def guard():
    if spent() >= BUDGET:
        raise BudgetReached("budget of $%.2f reached ($%.2f spent)" % (BUDGET, spent()))


def _setup(run):
    state_db = os.path.join(OUT, "state-%s.db" % run)
    for ext in ("", "-wal", "-shm"):
        try:
            os.remove(state_db + ext)
        except OSError:
            pass
    os.environ["SVINKKI_STATE_DB"] = state_db
    os.environ.setdefault("SVINKKI_TODAY", "2026-09-26")
    os.environ["SVINKKI_ENV_FILE"] = os.path.join(OUT, "no-such.env")
    os.environ["SVINKKI_AI_SETTINGS_FILE"] = os.path.join(OUT, "ai-%s.json" % run)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    from app import llm_claude
    real = llm_claude.create

    def priced(system, messages, tools, api_key, model, **kw):
        guard()
        msg = real(system, messages, tools, api_key, model, **kw)
        charge(run, "coach", model, msg.get("usage"))
        return msg

    llm_claude.create = priced
    return llm_claude, real


def load_bank(names, ids=None):
    bank = []
    for n in names:
        for f in sorted(glob.glob(os.path.join(HERE, n + ".json"))):
            with open(f, encoding="utf-8") as fh:
                bank.extend(json.load(fh))
    if ids:
        bank = [b for b in bank if b["id"] in ids]
    return bank


def cmd_run(run, banks, ids=None, threads=6):
    _setup(run)
    import app.server as server
    server.RATE_CHAT = server.RATE_OTHER = 100000
    bank = load_bank(banks, ids)
    httpd = server.make_server(host="127.0.0.1", port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % httpd.server_address[1]
    results, lock = [], threading.Lock()
    out_path = os.path.join(OUT, run + ".json")
    consent = {"analysis": True, "ai": True, "benchmarks": True, "suggestions": True}
    stop = threading.Event()

    def call(opener, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "Origin": base})
        try:
            with opener.open(req, timeout=300) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, None
        except Exception as e:  # noqa: BLE001
            return 0, {"error": type(e).__name__}

    def save():
        with lock:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(sorted(results, key=lambda r: r["id"]), f, ensure_ascii=False, indent=1, default=str)

    def persona(name, items):
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        _, ps = call(op, "GET", "/api/demo/personas")
        tok = [p["id"] for p in ps if p["name"].startswith(name)][0]
        call(op, "POST", "/api/demo/login", {"id": tok})
        for b in items:
            if stop.is_set() or spent() >= BUDGET:
                stop.set()
                return
            call(op, "POST", "/api/consent", consent)
            call(op, "POST", "/api/privacy/erase", {})
            call(op, "POST", "/api/consent", consent)
            conv, turns = None, []
            for q in b["turns"]:
                t0 = time.time()
                st, r = call(op, "POST", "/api/chat", {"message": q[:2000], "conversation_id": conv})
                dt = round(time.time() - t0, 1)
                if st != 200 or not isinstance(r, dict):
                    turns.append({"q": q, "error": "HTTP %s %r" % (st, r), "s": dt})
                    continue
                conv = r.get("conversation_id") or conv
                turns.append({"q": q, "reply": r.get("reply"), "mode": r.get("mode"), "notice": r.get("notice"),
                              "tools": r.get("tools_used"), "cards": [x.get("type") for x in r.get("cards") or []],
                              "s": dt})
            rec = {k: b.get(k) for k in ("id", "category", "lang", "persona", "needs", "outside_knowledge")}
            rec["turns"] = turns
            with lock:
                results.append(rec)
            save()
            print("%s %s (%d turns, $%.2f spent)" % (name, b["id"], len(turns), spent()), flush=True)

    by = {}
    for b in bank:
        by.setdefault(b["persona"], []).append(b)
    sem = threading.Semaphore(threads)

    def guarded(n, it):
        with sem:
            persona(n, it)

    ts = [threading.Thread(target=guarded, args=kv) for kv in by.items()]
    t0 = time.time()
    [t.start() for t in ts]
    [t.join() for t in ts]
    save()
    httpd.shutdown()
    modes = {}
    for r in results:
        for t in r["turns"]:
            modes[t.get("mode") or "error"] = modes.get(t.get("mode") or "error", 0) + 1
    print("RUN %s: %d conversations, %.0fs, modes=%s, run cost $%.2f, total $%.2f%s" % (
        run, len(results), time.time() - t0, modes, _load_ledger()["by_run"].get(run, {}).get("coach", 0),
        spent(), " (BUDGET STOP)" if stop.is_set() else ""))


JUDGE_SYSTEM = None


def cmd_judge(run, batch=6, threads=5):
    llm, real = _setup(run + "-judge")
    with open(os.path.join(HERE, "RUBRIC.md"), encoding="utf-8") as f:
        rubric = f.read().split("## Output")[0]
    system = rubric + (
        "\n## Output\nReply with ONLY a JSON array, one object per conversation, in the order given: "
        '{"id", "helpful", "personal", "actionable", "clear", "issues", "reason", "fix"}. No prose, no code fence.')
    with open(os.path.join(OUT, run + ".json"), encoding="utf-8") as f:
        convs = json.load(f)
    path = os.path.join(OUT, run + ".scores.json")
    try:
        with open(path, encoding="utf-8") as f:
            done = {s["id"]: s for s in json.load(f)}
    except (OSError, ValueError):
        done = {}
    todo = [c for c in convs if c["id"] not in done]
    key = open(os.environ["SVINKKI_AI_KEY_FILE"], encoding="utf-8").read().strip()
    lock = threading.Lock()
    batches = [todo[i:i + batch] for i in range(0, len(todo), batch)]
    sem = threading.Semaphore(threads)

    def one(b):
        with sem:
            if spent() >= BUDGET:
                return
            slim = [{k: c.get(k) for k in ("id", "category", "lang", "persona", "needs", "outside_knowledge")} |
                    {"turns": [{k: t.get(k) for k in ("q", "reply", "mode", "notice", "tools", "cards", "error")}
                               for t in c["turns"]]} for c in b]
            msg = None
            for attempt in range(2):
                try:
                    msg = real(system, [{"role": "user", "content": json.dumps(slim, ensure_ascii=False)}], [],
                               key, JUDGE_MODEL, effort="medium", max_tokens=16000, timeout=240)
                    break
                except Exception as e:  # noqa: BLE001
                    print("judge retry:", type(e).__name__, str(e)[:120], flush=True)
            if not msg:
                return
            charge(run, "judge", JUDGE_MODEL, msg.get("usage"))
            text = llm.text_of(msg)
            m = re.search(r"\[.*\]", text, re.S)
            try:
                scores = json.loads(m.group(0)) if m else []
            except ValueError:
                scores = []
            with lock:
                for s in scores:
                    if isinstance(s, dict) and s.get("id"):
                        done[s["id"]] = s
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(sorted(done.values(), key=lambda s: s["id"]), f, ensure_ascii=False, indent=1)
            print("judged %d (%d/%d), $%.2f spent" % (len(scores), len(done), len(convs), spent()), flush=True)

    ts = [threading.Thread(target=one, args=(b,)) for b in batches]
    [t.start() for t in ts]
    [t.join() for t in ts]
    print("JUDGED %s: %d/%d, judge cost $%.2f, total $%.2f" % (
        run, len(done), len(convs), _load_ledger()["by_run"].get(run, {}).get("judge", 0), spent()))


def _scores(run):
    with open(os.path.join(OUT, run + ".scores.json"), encoding="utf-8") as f:
        return {s["id"]: s for s in json.load(f)}


def cmd_report(run, other=None):
    sc = _scores(run)
    with open(os.path.join(OUT, run + ".json"), encoding="utf-8") as f:
        convs = {c["id"]: c for c in json.load(f)}
    dims = ("helpful", "personal", "actionable", "clear")

    def means(ss):
        ss = list(ss)
        return {d: round(sum(float(s.get(d) or 0) for s in ss) / max(1, len(ss)), 2) for d in dims}

    groups = {}
    for i, s in sc.items():
        groups.setdefault(i.split("-")[0], []).append(s)
    print("RUN", run, "n=%d" % len(sc), "all", means(sc.values()))
    for g, ss in sorted(groups.items()):
        print("   ", g, "n=%d" % len(ss), means(ss))
    iss = {}
    for s in sc.values():
        for x in s.get("issues") or []:
            iss[x] = iss.get(x, 0) + 1
    print("issues:", sorted(iss.items(), key=lambda kv: -kv[1]))
    lat = [t.get("s", 0) for c in convs.values() for t in c["turns"]]
    modes = {}
    for c in convs.values():
        for t in c["turns"]:
            modes[t.get("mode") or "error"] = modes.get(t.get("mode") or "error", 0) + 1
    lat.sort()
    print("latency median %.1fs p90 %.1fs, modes %s" % (lat[len(lat) // 2], lat[int(len(lat) * .9)], modes))
    print("helpful<=1:", sum(1 for s in sc.values() if float(s.get("helpful") or 0) <= 1))
    if other:
        o = _scores(other)
        common = sorted(set(o) & set(sc))
        print("vs", other, "on %d common:" % len(common), means(o[i] for i in common), "->",
              means(sc[i] for i in common))
        worse = [i for i in common if sum(float(sc[i].get(d) or 0) for d in dims) <
                 sum(float(o[i].get(d) or 0) for d in dims) - 1]
        print("got worse by 2+:", worse)
    print("spent total $%.2f of $%.2f" % (spent(), BUDGET))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)

    def opt(flag, default=None):
        return a[a.index(flag) + 1] if flag in a else default

    if a[0] == "run":
        cmd_run(a[1], opt("--banks", "bank_data,bank_goals,bank_messy").split(","),
                set(opt("--ids").split(",")) if opt("--ids") else None)
    elif a[0] == "judge":
        cmd_judge(a[1])
    elif a[0] == "report":
        cmd_report(a[1], a[2] if len(a) > 2 and not a[2].startswith("-") else None)
    elif a[0] == "spent":
        print(json.dumps(_load_ledger(), indent=1))
