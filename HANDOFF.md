# Handoff: how to continue this work

Written 13 Nov 2026, about 22:15, for whoever picks this up next (a teammate or their AI agent).
Everything needed is in this repository except three things that are deliberately not in git:
the dataset, the built database, and the API key.

## Where things stand

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
- Tests: `Ran 716 tests ... OK`.

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
   needs Git LFS, or use "Download raw file" in the browser). The team worked on a filtered copy
   that drops customers who move their salary out right after payday and customers with little
   activity. The unfiltered dataset also works: the demo personas and the random-customer login
   only use active main-bank customers either way; only the group averages differ slightly.
2. Point the app at the folder and build the database (about 30 seconds):
   ```bash
   export SVINKKI_DATA_DIR="/path/to/Junction-2026-S-pankki"
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
   which predates the one-conversation screen and needs the same update as `DEMO.md`).
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
- Finnish: common questions get a Finnish-only answer; alerts, challenge, area, comparisons,
  patterns and the quiz still answer in English with a short Finnish note when no AI model is
  connected. With Claude connected the model answers in Finnish.
- Conversations that contain only tool cards (quiz, check-in, the afford form) are not stored,
  so they do not appear on the front page.
- Gemini support is still in the code but has never been tried live.
- Repeating charges and investment withdrawals are rare in the synthetic data, so "forgotten
  subscriptions" and "savings leakage" usually have nothing to show.
- Login is a demo picker. The legal mapping in the security plan has not been reviewed by anyone
  with legal training.
