import sys
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5"); sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5/tests")
import fixture as fx; fx.get()
from app import coach, grounding as g, tools
ctx = fx.make_ctx(fx.A_CID)
t = g.FigureTable(fx.TODAY)
coach._customer_block(ctx, t)
r = tools.call("get_spend", {"period": "last_month", "label": "Taxi"}, ctx); t.add_result("get_spend", {}, r, raw=r)
s = "You spent €3,000 on taxis last month."
for c in t.candidates("money", 3000):
    print(c["id"], c["group"], c["categories"], c["span"], c["rate"], c["source"].get("tool"), c["source"].get("path"), "|", g.fits(c, s, "You spent ", " on taxis last month.", fx.TODAY))
