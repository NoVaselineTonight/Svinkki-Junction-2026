import sys, json
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5")
from tests import fixture
env = fixture.get()
from app import tools, coach
ctx = fixture.make_ctx()
for name, args in [("get_spend", {"label": "Taxi", "period": "last_month"}), ("get_overview", {}),
                   ("calculate", {"items":[{"label":"x","expression":"12*3"}]})]:
    r = tools.call(name, args, ctx)
    print(name, json.dumps(coach._model_view(r), default=str)[:1500])
snap, data = coach.customer_snapshot(ctx)
print("\n".join(snap)[:2500])
print(json.dumps(data, default=str)[:3000])
