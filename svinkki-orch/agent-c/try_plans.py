import os
import sys

sys.path.insert(0, sys.argv[1])
os.environ["SVINKKI_DB"] = "C:/Users/onnik/Desktop/challenge-1/data/svinkki.db"
from app import db, goalplan  # noqa: E402

ps = db.list_personas()
for idx, g, tgt, dl, f in ((3, "car", None, "2027-06", False), (3, "savings", 500, None, False),
                           (3, "emergency buffer", None, None, False), (3, "savings", 500, None, True),
                           (2, "home deposit", None, None, False)):
    conn = db.sandbox(ps[idx]["cid"], "2026-09-26", [], [])
    r = goalplan.build(conn, "2026-09-26", g, tgt, dl, faster=f)
    print(ps[idx]["name"], g, dl, "faster" if f else "", "->", r.get("monthly"), r.get("months"))
    print("   ", r.get("decision") or r)
