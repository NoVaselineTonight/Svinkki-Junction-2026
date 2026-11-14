# Handoff: how to continue this work

Written 13 Nov 2026, about 22:15, for whoever picks this up next (a teammate or their AI agent).
Everything needed is in this repository except three things that are deliberately not in git:
the dataset, the built database, and the API key.

## Where things stand

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

Updated 14 Nov 2026, about 09:30 UTC, by agent-d (local session with the dataset and the key; the AI side.
The GUI is agent-c's). Detail, figures and what was not solved: `.devloop/WAVE5.md`.

- **The coach was measured, and it was weak.** 180 conversations asked through the real app with the live
  model and scored by independent judges: helpful 1.88 of 3, and 50 of 180 left the customer with little or
  nothing. The owner's own example ("what would a trip to China for four cost?" answered with "I can't
  estimate, what do you expect it to cost?") was the commonest failure.
- **After this wave:** helpful 2.65, personal 2.66, actionable 2.07; 3 of 180 weak; nothing unsafe found in
  the boundary cases. Run with Claude Opus 5.5, live, on the real dataset.
- **It estimates and calculates.** `general_estimate` registers a rough range from the model's general
  knowledge (shown as such, and listed under "What the AI saw"); `calculate`, `project_savings` and
  `loan_payment` do the sums by code. The number check still removes any amount that is neither the
  customer's data nor a registered estimate nor a calculated figure; the model first gets one chance to put
  it right.
- **It looks further back.** New tools for the last 12 to 24 months: the balance path and what changed, the
  season ahead on last year's pace, one category's story, why a month was expensive, low points and cushion,
  pay rhythm, a year of receipts, how the customer shops, grocery cut ideas (`app/trends.py`,
  `app/cashflow.py`, `app/receipts.py`).
- **It stops repeating itself.** The picture of the customer is a ranked pool of findings (`app/findings.py`);
  what a reply used is remembered for the conversation and shown to the model as "already told".
- **Payday is the customer's usual pay day** (was a month too late for many). Safe to spend, can-I-afford
  and the forecast are less gloomy for customers paid on the 15th; the picture says when pay has come late.
- **With the model on, the model answers** follow-ups, "help", "what can you do", messages that mention a
  partner or a friend, and requests for a payment (it says no in one sentence and offers what it can; the
  tool that prepares a money move is withheld for that message). Another customer's id and attempts to read
  the instructions are still refused before the model. (`docs/SECURITY_PLAN.md` was updated to this routing
  in the afternoon.)
- **Slower and longer:** a plan takes about 10 to 15 seconds and 100 to 160 words; a lookup 4 to 6 seconds.
- **The new tools have no card in the web app.** Their figures are in the answer text.
- **The question bank is in the repo** (`.devloop/coach-bank/`): 180 conversations, the judging rubric and a
  runner. A live run makes about 240 paid model turns.
- Tests: `Ran 872 tests ... OK`.

Updated 14 Nov 2026, about 05:00 UTC, by agent-a (cloud session: no dataset, no key, tests and a headless browser on the test data only):

- **The coach knows the customer.** With the AI model on, each turn carries a short, checked picture of the
  customer (`coach.customer_snapshot`: last month, usual month, biggest categories, balance and payday, saving
  opportunities, goal, moves, challenge). The prompt now asks for: the answer, what it means for this customer,
  one concrete next step with a euro figure from their data; two to four sentences; no generic tips; no
  comparison with other people unless asked. The snapshot's figures count as verified in the number check, and
  its lines are in "What the AI saw" (`what_the_coach_knows`). Coach turns use effort `medium`.
- **Model.** Default is Claude Opus 5.5. A choice saved by the earlier build (it was Haiku) is no longer read,
  so the demo starts on Opus; choose again in Settings if you want another model.
- **NOT checked live.** No key exists in the cloud. The new prompt has only met the fake HTTP layer. Before a
  demo, ask five questions with a key ("How much do I earn?", "How am I doing?", "Can I afford a 300 euro
  jacket?", "Where can I save?", "hi") and read the answers: personal, 2 to 4 sentences, no peers. If answers
  come back replaced by "a checked answer" too often, the number check is rejecting the model's wording: look
  at the server log line "coach: ... path failed" and at `numbers_grounded`.
- **Without a model** answers add one sentence about the customer's own previous month ("That is €20 more than
  in July.") or usual month; coaching questions ("where can I cut back", "give me a tip", "am I spending too
  much", "save for a trip to Japan", "Miten minulla menee?") are understood.
- **Start page re-done (owner, 14 Nov):** account card, question box, six tiles "I can help with", link
  "Everything I can do"; check-in, quiz and "Worth a look" are closed rows under "For you"; "Your things" and
  "Conversations" only appear when they hold something. Looked at in a headless browser at phone width on the
  test data (all tiles and rows clicked, no console errors); not seen by a person on the real data.
- **agent-c's claims** on web/, tests/ and the docs were released under the stale rule after 5.5 hours of
  silence (the release went through about 8 minutes after the REQUEST, not the full 10). Its branch
  `agent-c/start-page-layout` was never pushed; if it exists on the owner's machine it will conflict with
  `web/app.js` `showHome`. Keep main's version unless the owner prefers the other.
- **Finnish without a model** now covers latest and biggest purchases, the last purchase, challenges, patterns,
  the comparisons (when asked) and tool errors; no question in the Finnish "What can I ask?" list falls back to
  English any more (`coach._fi_lead2`, `tests/test_finnish_replies.py`).
- The start page greets with the customer's own month ("You kept €735 in August. What shall we look at?"), and
  an answer of "nothing spent" no longer shows an empty €0 card.
- **Goal date kept:** a goal planned with a date stores the date and the monthly amount (`state.set_goal`
  takes `deadline` as YYYY-MM or YYYY-MM-DD); "Your things" says "€0 of €3,000 saved, by June 2027", the goal view
  shows "By" and "Needs about", and the coach is told the date.
- **Tool-only conversations are kept:** opening the quiz, the check-in, the afford form, what-if, compare,
  challenge or "Worth a look" in a conversation stores the tool's name as a turn (`POST /api/conversation/tool`),
  so the conversation is listed and reopens with the card drawn fresh. Tool turns are not sent to the model.
- **Prompt fix after a self-check:** the coach prompt's own example tip used a worked-out figure that the number
  check deletes. The prompt now says: use amounts exactly as given, never work out a new one, call a tool for a
  figure you lack. Tests pin that the example and five typical personal sentences pass the check.
- Overdrawn accounts are worded ("Your account is €3,800.00 overdrawn", no "minus", no "-2.7 months");
  "how much do I have left", "how much have I saved" are understood; "move up to €0" is gone.
- The coach's picture of the customer also holds their spending habits (busiest weekday, the days after
  payday), charges that repeat every month (category and amount, never the merchant) and what the grocery
  receipts show (biggest group, treats a month, most-bought product; marked as simulated).
- The welcome screen no longer says "I never move money" (untrue since in-app moves); a check-in for a week
  without a payday shows what was spent instead of "€0 in"; the status of the minor evaluation findings is
  written at the top of the Minor list in `docs/EVALUATION.md` (open: D13, D14, D15).
- **Notes (new):** "Remember that ..." / "Muista, että ..." is kept by the app itself (no model call), listed
  under "Your things" as a Note with "Forget this", and the newest six go into the coach's picture of the
  customer, labelled as the customer's own words and never instructions. A note that trips the prompt guardrail
  is refused; "remember I pay my mum 100 a month" is a note, not a refused payment. `tests/test_notes.py`.
- Without a model, "How can I save more?" now says whether the ideas cover what the customer's goal needs each
  month. A sweep of 3,588 rule-based answers (every help question, every test customer) found and fixed the last
  Finnish defects: "miinus 3 800 €", "-2,7 kuukauden", and "Onko ... tavallista?" not being treated as a
  comparison. Known gap: a FOUND spending pattern asked about in Finnish is still answered in English with a
  note, because `tests/test_wave3_http.py` (W14) pins that reply; change both together if you want it in Finnish.
- The coach's picture now carries the figures it would otherwise have to work out (what a usual month leaves,
  what a goal still needs, how many months that is at the usual leftover), so those sentences pass the number check.
- The model's reply is tidied before it is shown (`coach.tidy_model_text`): headings, emoji, stray `*emphasis*`
  and "Headline:" labels go; bold and bullets stay (the app renders them); an answer over 110 words is cut at a
  sentence end unless the customer asked for detail. Yesterday's `data/state.db` was checked to open with today's
  code (the notes table is added on first use; an old goal without a date reads as before).
- Tests: `Ran 761 tests ... OK`.

Updated 14 Nov 2026, about 01:00, by agent-c (main coding agent after agent-a):

- **Money can move in the demo, with permission.** The coach or a check-in suggestion offers a move to the
  customer's own S-Bank savings account or an S-Bank fund; an approval card must be tapped before anything
  moves (`app/money.py`, `/api/money/*`, `tests/test_money.py`). Payments and transfers out are still refused.
- **Start page:** a simulated S-Bank account card at the top (balance, savings and investments, safe to spend;
  tap for transactions and "Move money"), then the check-in, the weekly quiz and "Worth a look" as cards.
- **No unasked comparisons (owner, 14 Nov):** answers about the customer's own money never compare with other
  people unless the message asks for it (`coach.compare_requested`). The model only sees the comparison tools
  then; alerts and the quiz compare with the customer's own usual spending only.
- **Evaluation fixes (agent-b's `.devloop/eval-1.md`):** MAJ-1 (late unpaid bills dropped from safe to spend),
  MAJ-2 (payday guessed too early), MAJ-3 (unclear period or category answered silently), MAJ-4 (spending more
  reported as saving), MAJ-5 ("yes, it fits" for payday loans, crypto, gambling), MAJ-6 (check-in suggesting
  more than is safe), MAJ-8 (income questions) are fixed. MAJ-7 and MAJ-9 were fixed earlier (D5, D4).
  MAJ-10 (safe to spend vs. forecast) now shares the payday rule with the forecast; not re-evaluated.
- Tests: 650 pass.

Updated 14 Nov 2026, early morning, by agent-a.

- `main` holds the whole prototype.
- **The app now works like an AI assistant app.** Login, a one-button welcome, then a front page:
  "New conversation", earlier conversations, and "Your things" (savings goal, challenge, kept
  answers), which appear once created in a conversation. Answers are one short bubble; the card
  and the transactions used sit behind "Details" and "Transactions". "What can I ask?" lists
  everything the coach can do. Settings has "Reset demo", which takes everything back to the start.
- **Claude answers live.** Checked on 14 Nov with Claude Haiku 5.5 through the HTTP API as the
  persona Veeti: 21 questions including follow-ups ("and the month before?", "why?"), a goal
  saved by saying "ok set it", receipts, Finnish, mortgage and small talk. The model chosen in
  Settings is remembered in `data/ai_settings.json`.
- **Answers are short.** An independent review (152 turns) scored brevity 4 of 10; after the
  rewrite the built-in replies have a median of 17 words and none is over 45. Looked-up amounts
  keep their cents (EUR 92.85); estimates and comparisons are whole euros.
- **Receipts.** `app/receipts.py` turns every grocery payment (Prisma, S-market, Alepa, Sale) and
  fuel payment (ABC) into a simulated receipt whose lines add up to the payment to the cent. The
  coach can use them: what do I buy most, how much do I spend on a product, show my receipts,
  read a pasted receipt. The answers say the lines are simulated. The receipts of the six demo
  customers are also written to `data/receipts/` (one JSON, one CSV per customer; git-ignored,
  rebuilt by `python -m app.ingest` or `python -m app.receipts`).
- **The owner's steer (13 Nov):** privacy and security are a plus in the judging, not a
  requirement, so they must not block a usable function. The number check is therefore lenient by
  default (it removes a sentence with a euro amount the code did not produce;
  `SVINKKI_STRICT_NUMBERS=1` brings the strict check back).
- **Branding.** S-Pankki gave permission to use their name and logo in the demo and the pitch deck.
  The logo is the S mark followed by the word "Vinkki" (`web/brand/`).
- Tests: `python -m unittest discover -s tests` printed `Ran 655 tests ... OK` at the last run (14 Nov, about 02:00).
- Evaluation: `docs/EVALUATION.md` (verdict: iterate). Its five major findings (number check,
  quiz labels, baskets under 150 euros, area data reaching the model, Finnish questions) are fixed
  on `main`; some minor ones are open.
- Pitch deck: https://claude.ai/artifact/SyUgwmLNJXvXCqqHrvUMmq (private to the owner; share it
  from its Share menu). Four slides: basics, advanced functions, example chats, technology.

## Get it running on a new machine

Python 3.13, nothing to install.

1. Dataset: download https://github.com/hackjunction/Junction-2026-S-pankki (the transactions file
   needs Git LFS, or use "Download raw file" in the browser) and put the CSV files in `dataset/` in the
   repository root (git-ignored), or set `SVINKKI_DATA_DIR`. The team worked on a filtered copy
   that drops customers who move their salary out right after payday and customers with little
   activity. The unfiltered dataset also works: the demo personas and the random-customer login
   only use active main-bank customers either way; only the group averages differ slightly.
2. Build the database (about 30 seconds):
   ```bash
   python -m app.ingest
   ```
3. Start it and open http://localhost:8000:
   ```bash
   python -m app.server
   ```

More detail: `README.md`. Demo script: `DEMO.md`.

## The API key

- The key is NOT in git. On the original machine it is in `claude_api_key.txt` in the repo root
  (git-ignored, one line). On a new machine, create that file yourself with the key the team
  shares privately. Never paste a key into a commit, an issue, a pull request or a chat with an
  agent that logs to GitHub.
- The key was pasted into an AI chat on 13 Nov. Rotate it after the hackathon.

## How work is organised

- `AGENTS.md` is binding: every agent claims files before editing, works on a branch named
  `<agent-name>/<task>`, never pushes to `main`, and merges through a pull request.
  First command in a new clone: `python .agents/agentchat.py status`. If it says no agent name is
  set, pick one (`agent-b`, for example) with `python .agents/agentchat.py setup --name agent-b`.
- Check `python .agents/agentchat.py claims` before you start. If an agent holding claims has been
  silent for 30 minutes, the protocol lets you take them over:
  `python .agents/agentchat.py release --all --owner <agent> --reason "session ended"`.
- The contract for the code is in three files: `.devloop/STATE.md` (first build),
  `.devloop/WAVE2.md` and `.devloop/WAVE3.md` (added features). `docs/SECURITY_PLAN.md` is binding
  for anything touching data or the AI model.
- The partner's brief is in `CHALLENGE_DESCRIPTION.md`. Keep it in front of you: the mentors judge
  against it. Core first (talk with your own money, three baskets, safe to spend, what-if,
  benchmarks), extras second.

## Next steps, in order

1. Rehearse `DEMO.md` once from a clean start (`python -m app.server`, log in as Veeti).
2. Record the two-minute video for the final submission (script: `submission/VIDEO_SCRIPT.md`,
   updated on 14 Nov to the current front page and figures).
3. Fill in the team name and members on the first slide of the deck.
4. Open minor findings in `docs/EVALUATION.md`, if time allows.
5. Junction deadlines: final submission by Sunday 10:00 with a public video of at most two
   minutes, live peer review Sunday 10:30 to 14:00.

**A warning about tests and the key.** An empty `ANTHROPIC_API_KEY` does not switch Claude off:
the app then reads `claude_api_key.txt`. The test fixture points the key file at a path that does
not exist, so the suite is safe. Any other script you run against the app will make real, paid
calls unless you do the same: `SVINKKI_AI_KEY_FILE=/nonexistent python your_script.py`.

## Known gaps, stated plainly

- Receipt lines are simulated. Nothing in the dataset says what was in a basket.
- With Claude the wording of a reply varies and sometimes runs to three sentences (mortgage); the
  figures come from the app. In the default lenient mode a percentage or a plain number the model
  invents is not caught, only euro amounts are.
- Looked at in a browser at phone width: login, welcome, front page, an answer with its card,
  "What can I ask?", Settings, saving a goal and seeing it under "Your things". Not clicked
  through in a browser after the last wording changes: the receipt cards, "Reset demo" (its
  endpoint is covered by tests), the what-if sliders, the text explainer, erase.
- Finnish without a model: a found spending pattern asked about in Finnish is still answered in English
  with a note (pinned by `tests/test_wave3_http.py`, W14). With Claude connected the model answers in Finnish.
- Gemini support is still in the code but has never been tried live.
- The S-mobiili integration is shown with a local stand-in; the handover secret in the code is a demo secret.
- Investment plans are close to regulated advice; not reviewed by compliance.
- Repeating charges and investment withdrawals are rare in the synthetic data, so "forgotten
  subscriptions" and "savings leakage" usually have nothing to show.
- Login is a demo picker. The legal mapping in the security plan has not been reviewed by anyone
  with legal training.
