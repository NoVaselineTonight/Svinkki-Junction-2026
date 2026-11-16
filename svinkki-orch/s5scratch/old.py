import sys, os
os.environ["SVINKKI_AI_KEY_FILE"] = "/nonexistent"; os.environ["ANTHROPIC_API_KEY"] = ""
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5")
from app import coach
sys.path.insert(0, r"C:/Users/onnik/Desktop/svinkki-s5/tests")
from test_grounding import CALLS, TODAY
from app import grounding as g
res = [c[2] for c in CALLS]
for s in ["You spent €2,336 on taxis last month.", "Käytit takseihin 450 euroa viime kuussa.",
          "You spent 450 on taxis, which is 45% of your income.", "You spend €92.85 on taxis every week.",
          "You spent €92.85 on taxis last month."]:
    print("old:", coach.numbers_grounded(s, res, ""), " new:", g.numbers_grounded(s, CALLS, "", today=TODAY), " ", s)
