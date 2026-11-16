import sys
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5"); sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5/tests")
import fixture as fx; fx.get()
from app import coach, grounding as g
ctx = fx.make_ctx(fx.A_CID); ctx.memory = {}
snap, data = coach.customer_snapshot(ctx)
for mode in ("data-as-result", "lines"):
    t = g.build_table([("result", {}, data)], today=fx.TODAY) if mode == "data-as-result" else g.build_table(snapshot_lines=snap, snapshot_data=data, today=fx.TODAY)
    for s in ["You bring in about €3,000 a month and usually spend around €1,671.",
              "Moving your leftover of about €1,129 on payday would get you to Japan by June 2027.",
              "After your usual spending about €1,379 a month is left.",
              "Treats come to about €27 a month on your receipts, which are simulated for this demo."]:
        print(mode, [v["detail"][:110] for v in g.check(s, t)] or "OK", "|", s[:50])
