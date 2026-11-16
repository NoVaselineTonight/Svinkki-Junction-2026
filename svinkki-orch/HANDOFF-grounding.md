# Handoff: continuing agent-s5's number-grounding work (merged in PR 43)

State on main: app/grounding.py builds a per-turn figure table (tool results, customer snapshot,
earlier answers, the customer's message). The model writes slots {{fN}}; coach.chat() fills them via
grounding.render (EN/FI formatting) and returns reply["figures"]. Digits the model types itself pass
only if they equal a figure that fits the sentence (income vs spending, category, period). The four
wrong sentences from the brief are rejected (tests in tests/test_grounding.py, test_wave4.py).
Live: 6/6 Opus turns wrote slots, nothing dropped (svinkki-orch/live-check/s5.json).

reply["figures"] item shape:
  {"id","start","end","text","label","unit":"money|percent|count|number","value","written":"slot|digits",
   "source":{"kind":"tool|snapshot|earlier_answer|customer_message","tool","call","path","args",
             "evidence":[filter dicts, same shape as reply["evidence"]]}}
start/end are offsets into reply["reply"].

Open work, best value first:
1. Tappable figures (web/app.js): wrap each figures[i] span in the answer bubble in a button; on tap
   show label + source and list the transactions using source.evidence (same code path as
   "Transactions used"). Static test in tests/test_web_ux.py style. Biggest "originality" win.
2. Docs: replace TODO(grounding) placeholders on branch agent-s6/docs (README x2, SECURITY_PLAN SR-12/SR-10,
   SUBMISSION, HANDOFF) with the paragraph above.
3. Known gaps: an all-category total quoted in a one-category sentence ("€1,621 on taxis") is not caught;
   small counts 0-12 are free ("3 payments" when it was 4 passes). Fix in grounding._fits.
4. Token cost: the "figures" listing about doubles number-heavy tool results; cap or compress if cost matters.
Rules: claim files first (AGENTS.md); python -m unittest discover -s tests must pass; no live calls
without SVINKKI_AI_KEY_FILE pointing at the key and a line in svinkki-orch/live_budget.log (14 of 40 left).
