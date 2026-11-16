"""Run the suite with coach's number check swapped for app.grounding (scratch; coach.py untouched)."""
import os, re, sys, unittest
os.environ["SVINKKI_AI_KEY_FILE"] = "/nonexistent"; os.environ["ANTHROPIC_API_KEY"] = ""
REPO = r"C:/Users/onnik/Desktop/svinkki-s5"
sys.path.insert(0, REPO); sys.path.insert(0, REPO + "/tests")
import fixture as fx; fx.get()
from app import coach, grounding as g

def spans(text, tool_results, user_message="", strict=None):
    calls = [("result", {}, r) for r in (tool_results or []) if isinstance(r, (dict, list))]
    return g.ungrounded_spans(text, calls, user_message or "", today=os.environ.get("SVINKKI_TODAY"))

def grounded(text, tool_results, user_message="", strict=None):
    return not spans(text, tool_results, user_message, strict)

def keep(text, results, message):
    calls = [("result", {}, r) for r in (results or []) if isinstance(r, (dict, list))]
    t = g.build_table(calls, message=message or "", today=os.environ.get("SVINKKI_TODAY"))
    r = g.render(text, t)
    return r["text"] if r["ok"] else ""

coach.ungrounded_spans, coach.numbers_grounded, coach._keep_grounded_sentences = spans, grounded, keep
suite = unittest.defaultTestLoader.discover(REPO + "/tests")
res = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
print("ran", res.testsRun, "failures", len(res.failures), "errors", len(res.errors))
for t, tb in res.failures + res.errors:
    last = [l for l in tb.strip().splitlines() if l.strip()][-1]
    print("FAIL", t.id(), "|", last[:220])
