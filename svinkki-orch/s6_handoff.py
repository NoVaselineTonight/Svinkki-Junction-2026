import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:90]
    s = s.replace(old, new)


rep('''## Where things stand

''', '''## Where things stand

Updated 14 Nov 2026, afternoon, by agent-s6 (documents brought in line with the build; agent-s is the lead of
this round, agents s1 to s6 build). Merged since the morning, newest first:

- **What the model receives is trimmed and listed** (PRs 33, 37): at most 25 transaction rows without the time
  of day, receipts without ids, no merchant reference; `explore_my_data` runs on a copy without a merchant
  column; listed first names in the customer's words become `[name]`; the Gemini path is anonymised too. The
  table is in README, "What the model receives", and in `docs/SECURITY_PLAN.md` SR-22.
- **Guardrail**: questions about the customer's own payments are no longer refused; a payment order to
  someone's IBAN gets the payment refusal; a long message that starts as a payment order is refused instead of
  explained; the Finnish payment refusal says what the app can really do.
- **S-mobiili embedding** (PR 36): `python -m app.server --port 8030`, then `python -m app.host_demo`, open
  http://127.0.0.1:8031. Signed single-use handover token, iframe sessions, `SVINKKI_HOST_SECRET`,
  `SVINKKI_FRAME_ANCESTORS`. README, "Inside S-mobiili".
- **Web UX** (PR 35): Back button through the History API, Home keeps results and shows load errors, the
  answer's source under each answer ("On-device rules" or the model's name), cents on looked-up amounts,
  the model's own follow-up questions.
- **A Claude turn is capped at 60 s** (PR 34), every request included; then the built-in rules answer.
- **Investment guidance from named Finnish sources** (PR 32): `app/invest.py`, `app/invest_knowledge.json`.
- **CI** (PR 30): the unit tests run on every PR and push to `main`. `SVINKKI_DATA_DIR` defaults to
  `dataset/` in the repository root.
- **Measured live** on 14 Nov (real dataset, Veeti, warm cache): Opus 5.5 median 6.5 s, slowest 13 s, about
  $0.034 a turn over 12 demo turns; Sonnet 5.5 about 3.5 s and Haiku 5.5 about 3.8 s on 3 turns each.
- `DEMO.md` figures were re-checked on the real dataset without a key on 14 Nov (step 7 is now about €35 a day
  until payday on 15 October).
- TODO(grounding): the slot-based number check (agent-s5, `app/grounding.py` merged in PR 38 but not yet used
  by the coach).
- TODO(defects): agent-s1's demo defects. Seen while checking the docs, not fixed: without a model, "Which fund
  should I buy?" is read as a price question ("How much does the Which fund cost?").
- TODO(tests): test count.

''')

rep('''Another customer's id and attempts to read
  the instructions are still refused before the model. `docs/SECURITY_PLAN.md` describes the older, stricter
  routing and has not been updated.''',
'''Another customer's id and attempts to read
  the instructions are still refused before the model. (`docs/SECURITY_PLAN.md` was updated to this routing
  in the afternoon.)''')

rep('''1. Dataset: download https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file
   needs Git LFS, or use "Download raw file" in the browser).''',
'''1. Dataset: download https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file
   needs Git LFS, or use "Download raw file" in the browser) and put the CSV files in `dataset/` in the
   repository root (git-ignored), or set `SVINKKI_DATA_DIR`.''')

rep('''2. Point the app at the folder and build the database (about 30 seconds):
   ```bash
   export SVINKKI_DATA_DIR="/path/to/Junction-2026-S-pankki"
   python -m app.ingest
   ```''',
'''2. Build the database (about 30 seconds):
   ```bash
   python -m app.ingest
   ```''')

rep('''2. Record the two-minute video for the final submission (script: `submission/VIDEO_SCRIPT.md`,
   which predates the one-conversation screen and needs the same update as `DEMO.md`).''',
'''2. Record the two-minute video for the final submission (script: `submission/VIDEO_SCRIPT.md`,
   updated on 14 Nov to the current front page and figures).''')

rep('''- Conversations that contain only tool cards (quiz, check-in, the afford form) are not stored,
  so they do not appear on the front page.
''', '')

rep('''- Finnish: common questions get a Finnish-only answer; alerts, challenge, area, comparisons,
  patterns and the quiz still answer in English with a short Finnish note when no AI model is
  connected. With Claude connected the model answers in Finnish.''',
'''- Finnish without a model: a found spending pattern asked about in Finnish is still answered in English
  with a note (pinned by `tests/test_wave3_http.py`, W14). With Claude connected the model answers in Finnish.''')

rep('''- Gemini support is still in the code but has never been tried live.''',
'''- Gemini support is still in the code but has never been tried live.
- The S-mobiili integration is shown with a local stand-in; the handover secret in the code is a demo secret.
- Investment plans are close to regulated advice; not reviewed by compliance.''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
