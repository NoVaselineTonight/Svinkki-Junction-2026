"""Ask the coach every conversation in the question bank and store the answers.

    python .devloop/coach-bank/run_bank.py live  NAME      # the AI model answers (real, paid calls with your key)
    python .devloop/coach-bank/run_bank.py offline NAME    # the built-in rules answer (free)
    options: --ids G-001,M-035   only these conversations
             --sample 30         a fixed random sample
             --threads 6         customers asked in parallel (one thread per demo customer)

The app runs in this process on a free port, against the database the app is configured for (SVINKKI_DB, or
data/svinkki.db) and a state file of its own, so the demo's own state is not touched. Every conversation starts
from a clean customer state. Results go to data/coach-runs/NAME.json (data/ is git-ignored: the answers hold
figures from the dataset). Judge a run with RUBRIC.md.
"""
import glob
import http.cookiejar
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

if len(sys.argv) < 3 or sys.argv[1] not in ("live", "offline"):
    sys.exit(__doc__)
mode, run_name = sys.argv[1], sys.argv[2]
args = sys.argv[3:]


def opt(flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


ids = set(opt("--ids").split(",")) if opt("--ids") else None
sample = int(opt("--sample", "0"))
threads = int(opt("--threads", "6"))

out_dir = os.path.join(REPO, "data", "coach-runs")
os.makedirs(out_dir, exist_ok=True)
state_db = os.path.join(out_dir, "state-%s.db" % run_name)
for ext in ("", "-wal", "-shm"):
    try:
        os.remove(state_db + ext)
    except OSError:
        pass
os.environ["SVINKKI_STATE_DB"] = state_db
if mode == "offline":       # no key can reach the app
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
        os.environ.pop(k, None)
    os.environ["SVINKKI_AI_KEY_FILE"] = os.path.join(out_dir, "no-such-key.txt")
    os.environ["SVINKKI_ENV_FILE"] = os.path.join(out_dir, "no-such.env")
sys.path.insert(0, REPO)
os.chdir(REPO)

import app.server as server  # noqa: E402

server.RATE_CHAT = server.RATE_OTHER = 100000

bank = []
for f in sorted(glob.glob(os.path.join(HERE, "bank_*.json"))):
    with open(f, encoding="utf-8") as fh:
        bank.extend(json.load(fh))
if ids:
    bank = [b for b in bank if b["id"] in ids]
if sample:
    random.Random(7).shuffle(bank)
    bank = sorted(bank[:sample], key=lambda b: b["id"])


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, timeout=240):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=timeout) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"null")
            except Exception:
                return e.code, None
        except Exception as e:  # noqa: BLE001
            return 0, {"error": type(e).__name__}


httpd = server.make_server(host="127.0.0.1", port=0)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d" % httpd.server_address[1]
CONSENT = {"analysis": True, "ai": True, "benchmarks": True, "suggestions": True}
results, lock = [], threading.Lock()
out_path = os.path.join(out_dir, run_name + ".json")


def save():
    with lock:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sorted(results, key=lambda r: r["id"]), f, ensure_ascii=False, indent=1, default=str)


def run_persona(name, items):
    c = Client(base)
    st, ps = c.call("GET", "/api/demo/personas")
    tok = [p["id"] for p in ps if p["name"].startswith(name)][0]
    c.call("POST", "/api/demo/login", {"id": tok})
    for b in items:
        c.call("POST", "/api/consent", CONSENT)
        c.call("POST", "/api/privacy/erase", {})
        c.call("POST", "/api/consent", CONSENT)
        conv, turns = None, []
        for q in b["turns"]:
            t0 = time.time()
            st, r = c.call("POST", "/api/chat", {"message": q[:2000], "conversation_id": conv})
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
        print("%s %s done (%d turns)" % (name, b["id"], len(turns)), flush=True)


by_persona = {}
for b in bank:
    by_persona.setdefault(b["persona"], []).append(b)
sem = threading.Semaphore(threads)


def guarded(name, items):
    with sem:
        run_persona(name, items)


ts = [threading.Thread(target=guarded, args=(n, it)) for n, it in by_persona.items()]
t0 = time.time()
[t.start() for t in ts]
[t.join() for t in ts]
save()
modes = {}
for r in results:
    for t in r["turns"]:
        modes[t.get("mode") or "error"] = modes.get(t.get("mode") or "error", 0) + 1
print("DONE %d conversations, %d turns, %.0fs, modes=%s, file=%s" % (
    len(results), sum(len(r["turns"]) for r in results), time.time() - t0, modes, out_path))
httpd.shutdown()
