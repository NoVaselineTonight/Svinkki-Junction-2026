# Handoff from agent-s (lead) — 14 Nov 2026, ~11:55 UTC

The owner stopped agent-s and its workers (agent-s1..s6). All their claims are released. This
file is for the agents that continue (agent-d, agent-c or a new one). Deadline: Sun 15 Nov 10:00
Finnish time (08:00 UTC). AGENTS.md rules apply: claim before editing, PRs only, suite must pass.

## Merged on main by agent-s's team (PRs 30, 31, 33-40, 43)
- 30 CI: `.github/workflows/tests.yml` runs the suite on every PR; dataset default `dataset/` (no personal path).
- 31, 34 Claude turn: absolute deadline per request; whole turn hard-capped at 60 s (45 s per request); rules answer after.
- 33, 37 Payload: explore_my_data runs on a copy without the merchant column; model gets <=25 tx rows, no
  receipt ts/tx_id, no merchant_ref; listed first names masked to [name]; Gemini anonymised; guardrail: airport-style
  "did I pay" not refused, IBAN transfer gets money refusal, long payment orders refused, true REFUSAL_MONEY_FI.
- 35, 40 Web: Back button (History API), Home keeps results + shows fetch errors, answer source label
  ("On-device rules" / model name), cents on cards, model follow-ups, progress + 70 s client timeout, keyboard-safe
  composer, tap instead of hover, cards for the PR-29 tool types.
- 36 S-mobiili host demo: `python -m app.server --port 8030` then `python -m app.host_demo`, open
  http://127.0.0.1:8031. Signed single-use handover token, SameSite=None cookie or X-Svinkki-Session header,
  CSP frame-ancestors from SVINKKI_FRAME_ANCESTORS.
- 39 Prompt caching: per-customer block + history cached; warm Opus turn ~$0.019 -> ~$0.013 (measured live).
- 38, 43 Number grounding: app/grounding.py; model writes {{fN}} slots filled by code; reply["figures"] with sources.
  The brief's four wrong sentences are rejected. Live 6/6 Opus turns wrote slots, nothing dropped.
  Details and open work: C:/Users/onnik/Desktop/svinkki-orch/HANDOFF-grounding.md

## Live measurements (Veeti, real data; files in C:/Users/onnik/Desktop/svinkki-orch/live-check/)
Opus 5.5 (default): median 6.5 s, max 13 s over 12 demo turns, ~$0.034/turn before caching. Sonnet ~3.5 s,
Haiku ~3.8 s. Nothing broke. Live budget: 26 of 40 turns used (svinkki-orch/live_budget.log).

## UNFINISHED — do these, in this order
1. **Demo defects (MAJOR, nearly done):** branch `agent-s1/demo-defects-wip` (pushed; on top of main after PR 43).
   coach.py +351, tests/test_demo_defects.py. Fixes without a model: month ranges ("between June and August",
   "kesä-elokuussa"), "last N months", coffee (receipts + restaurants/fast food, honest that cafés can't be
   identified), "Should I buy bitcoin?" / "Which fund should I buy?" (invest facts, not a price question),
   "Did Anna pay me back?" (English, lists non-salary inflows). Worked on the real data. NOT done: the full suite.
   To finish: `git fetch && git switch -c <you>/demo-defects origin/agent-s1/demo-defects-wip`, claim app/coach.py
   and tests/test_demo_defects.py, `python -m unittest discover -s tests`, fix any failure, rebase on main, PR.
   Patch notes: svinkki-orch/s1-coach-patch.md.
2. **Evaluator MAJORs still open** (full report: ask the owner; summary here; screenshots svinkki-orch/eval1/):
   - "did I pay 12 for a ticket to the airport?" (offline) answers last month's total. Route "did I pay N for X"
     to payments near N; say none found or list closest (Veeti: Fast food €11.58 on 1 Jul). coach.py.
   - Check-in suggestion "Review the days your balance went below zero?" -> "Show me" replies only "Noted. I saved
     your choice." Should show the negative-balance days (Veeti: Mar/Apr/May/Jul/Aug 2026, low −€424.63).
     Look at the check-in suggestion handling in app/server.py and web/app.js.
   MINOR: payday-loan afford card shows "Left a day after it €18.76" (a loan is not spending); payday text says
   "above €230" vs card "€239"; spending cards titled "Spending" not the category; Finnish answers keep English
   cards; host-frame input placeholder cut off.
3. **Docs:** branch `agent-s6/docs` (pushed, no PR) updates README, DEMO, HANDOFF, submission/*, SECURITY_PLAN
   from measured facts. Fill placeholders TODO(tests), TODO(cost), TODO(grounding), TODO(defects); it does not yet
   cover PRs 39-43 (caching cost, progress UI, deploy, daily quiz, grounding). Rebase, fill, PR.
4. **Final evaluation:** a fresh agent that built nothing repeats the repro strings, clicks DEMO.md at 390x844,
   scores the five criteria. Round 1 scores (main 3a96ad5, no key): literacy 7, AI originality 5, mobile UX 8,
   feasibility 7, S-mobiili 8.
5. Nice-to-have (skipped): tappable figures using reply["figures"]; cheap model for simple questions; glossary.

## Owner's to-do (not for agents)
Record the video, team names, make the repo public (git history still has an old personal path), deck link,
rotate the API key.
