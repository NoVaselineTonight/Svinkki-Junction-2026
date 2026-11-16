import sys, json
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5"); sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5/tests")
import fixture as fx; fx.get()
from app import coach, tools, grounding as g
ctx = fx.make_ctx(fx.A_CID); ctx.memory = {}
snap, data = coach.customer_snapshot(ctx)
t = g.FigureTable(fx.TODAY)
lines = t.add_snapshot(snap, data)
print("\n".join(lines[:6]))
calls = []
for name, args in [("get_spend", {"label": "Taxi", "period": "last_month"}), ("get_safe_to_spend", {}), ("get_save_more", {}),
                   ("general_estimate", {"what": "a week in Japan for two", "low": 3000, "high": 5000, "basis": "flights and hotels"}),
                   ("plan_goal_by_date", {"amount": 4000, "deadline": "2027-06"}), ("get_money_story", {})]:
    r = tools.call(name, args, ctx)
    v = t.add_result(name, args, coach._model_view(r), raw=r)
    calls.append((name, args, r))
    js = json.dumps(v, ensure_ascii=False, default=str)
    print("\n==", name, len(json.dumps(coach._model_view(r), ensure_ascii=False, default=str)), "->", len(js))
    print(js[:900])
print(len(t.figs), "figures")
print("=========== SENTENCES")
for s in [
 "You spent €62.10 on taxis last month, €28 of it on a night out.",
 "That's 3 rides, so roughly €21 each.",
 "You can safely spend €30,439 until payday on 15 October, which is about €1,449 a day.",
 "A week in Japan for two would cost roughly €3,000 to €5,000, and at your usual leftover of about €1,379 a month that's about 3 months of saving.",
 "Your balance grew from €17,323 a year ago to €31,469 now.",
 "Trimming nights out by a quarter would free about €16 a month.",
 "Over the last 6 months you kept 44% of your income.",
 "Käytit takseihin 62,10 € elokuussa, siitä 28 € illanvietolla.",
 "Tavallinen kuukausi jättää sinulle noin 1 379 €.",
 "You spent €1,621 on taxis last month.",
 "Your income is €1,379 a month.",
 "You spend €62.10 on taxis every week.",
 "Your usual month leaves about €1,379 every week.",
 "Bills of €996 are due before payday on 17 October.",
]:
    r = g.render(s, t)
    print(("OK  " if not r["violations"] else "BAD ") + s, "->", r["text"] if not r["violations"] else [v["detail"][:120] for v in r["violations"]])
