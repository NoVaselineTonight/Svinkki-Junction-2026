import sys, os
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5")
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5/tests")
import fixture as fx
fx.get()
import test_presentation as tp
from app import coach, grounding as g, db
n = bad = 0
seen = set()
for cid in tp.CUSTOMERS:
    for q in tp.QUESTIONS + [it["question"] for lang in ("en", "fi") for gg in coach.help_groups(lang) for it in gg["items"]]:
        c = fx.make_ctx(cid, consent=tp.OFF)
        c.cid, c.memory, c.bench_lookup = cid, {}, db.bench
        r = coach._run_offline(q, c)
        results = [x for x in r.get("results") or [] if isinstance(x, dict)]
        calls = [(r.get("tool") or "x", r.get("args") or {}, x) for x in results]
        text = r["reply"]
        n += 1
        spans = g.ungrounded_spans(text, calls, q, today=fx.TODAY)
        if spans:
            bad += 1
            t = g.build_table(calls, message=q, today=fx.TODAY)
            vs = g.check(text, t)
            key = tuple(v["detail"][:60] for v in vs)
            if key in seen: continue
            seen.add(key)
            print("---", r.get("tool"), "|", q[:50]); print(text)
            for v in vs: print("   >>", v["reason"], v["detail"][:200])
print("replies", n, "flagged", bad)
