import sys, json
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5"); sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5/tests")
import fixture as fx; fx.get()
import test_presentation as tp
from app import coach, grounding as g, db
for q in ("how much fuel do I buy", "Where is my money leaking?"):
    c = fx.make_ctx(fx.A_CID, consent=tp.OFF); c.cid, c.memory, c.bench_lookup = fx.A_CID, {}, db.bench
    r = coach._run_offline(q, c)
    print(r["reply"]); print(json.dumps(r["results"], default=str)[:2500])
    t = g.build_table([(r["tool"], r["args"], x) for x in r["results"]], today=fx.TODAY)
    for f in t.figs:
        if f["value"] in (3.1, 50.0, 1.82) or 1.8 < f["value"] < 1.9 or 2.9 < f["value"] < 3.2: print(f)
