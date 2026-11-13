# Handoff: how to continue this work

Written 13 Nov 2026, about 22:15, for whoever picks this up next (a teammate or their AI agent).
Everything needed is in this repository except three things that are deliberately not in git:
the dataset, the built database, and the API key.

## Where things stand

Updated 13 Nov 2026, about 23:00, by agent-b (a teammate's session that picked this up).

- `main` holds the whole prototype.
- The app runs and is tested: `python -m unittest discover -s tests` printed
  `Ran 419 tests ... OK` at the last run (Python 3.12 on Linux and 3.13 on Windows both work).
- **Claude is now the AI model** (step 1 below is done in code): `app/llm_claude.py`, a Claude turn
  in `app/coach.py`, the text explainer, and a block "AI model (demo setup)" in Settings where the
  key is saved and the model chosen. It is tested against a fake HTTP layer only.
  **No real Claude answer has been seen yet**, because the machine it was written on had no key.
  The one thing checked live: a made-up key gets `HTTP 401 (authentication_error)` from the real
  service, so the address and headers are right.
- Without a key the chat answers with built-in rules ("offline" mode), as before.
- The independent evaluation was re-run: `.devloop/eval-1.md`. Verdict: no blocker, 10 major and
  22 minor defects. The numbers are right; the weak spots are safe-to-spend around rent day and
  payday, the built-in chat outside its English example phrasings, and "can I afford" saying yes
  to investments and loans.

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
- `agent-a` (this session) holds claims on `app/ web/ tests/ scripts/ docs/ .devloop/` and the
  top-level documents. If agent-a has been silent for 30 minutes, the protocol lets you take the
  claims over: `python .agents/agentchat.py release --all --owner agent-a --reason "session ended"`.
- The contract for the code is in three files: `.devloop/STATE.md` (first build),
  `.devloop/WAVE2.md` and `.devloop/WAVE3.md` (added features). `docs/SECURITY_PLAN.md` is binding
  for anything touching data or the AI model.
- The partner's brief is in `CHALLENGE_DESCRIPTION.md`. Keep it in front of you: the mentors judge
  against it. Core first (talk with your own money, three baskets, safe to spend, what-if,
  benchmarks), extras second.

## Next steps, in order

0. **Do this first: one live Claude call.** Create `claude_api_key.txt` (or paste the key in
   Settings, "AI model (demo setup)", on http://localhost:8000), press "Test the key", then ask the
   chat three questions with AI consent on and read the answers. If the request is rejected, the
   reply says which HTTP status and error type came back; the request is built in
   `app/llm_claude.py` (`create`).
1. **Claude as the AI model.** DONE in code by agent-b, as specified below, with these choices:
   a refusal, a cut-off reply, any HTTP error or a turn longer than 100 seconds falls back to the
   built-in rules (no server-side model fallback is used); the tools and the rules prompt are
   marked cacheable; the model choice is remembered in `data/ai_settings.json`; the setup endpoints
   are `GET|POST /api/demo/ai` and `POST /api/demo/ai/test`, refused unless the browser is on the
   same computer and no proxy or tunnel is in between. The original specification:
   - New `app/llm_claude.py`: Messages API over `urllib` (the project has no dependencies by
     design). `POST https://api.anthropic.com/v1/messages`, headers `x-api-key`,
     `anthropic-version: 2026-10-21`, `content-type: application/json`. Body: `model`,
     `max_tokens` (16000), `system`, `messages`, `tools` (`name`, `description`, `input_schema`),
     `output_config: {"effort": "low"}`. Do not send `temperature`. Tool loop: append the
     assistant's whole `content` list unchanged (it can include thinking blocks), then a user
     message with `tool_result` blocks (`tool_use_id`, `content`). Check `stop_reason`
     (`tool_use`, `end_turn`, `refusal`, `max_tokens`) before reading content.
   - Default model `claude-opus-5-5`; let the demo Settings choose `claude-sonnet-5-5` or
     `claude-haiku-5-5` (the cheap option) and remember the choice.
   - `app/config.py`: read the key from env `ANTHROPIC_API_KEY`, else from the file named by
     `SVINKKI_AI_KEY_FILE` (default `claude_api_key.txt`). Provider is Claude when a Claude key
     exists, else Gemini when a Gemini key exists, else the built-in rules.
   - **Before any code reads the key file, make the tests safe**: `tests/fixture.py` must set
     `SVINKKI_AI_KEY_FILE` to a path that does not exist and `ANTHROPIC_API_KEY` to empty, or the
     test suite will call the real API with the real key. Check this first.
   - `app/coach.py`: a Claude turn next to the Gemini turn, same anonymising, same rule that every
     figure in a reply must come from a tool result, same fallback to built-in rules on any error.
     `app/explain.py`: use Claude for the text explainer too.
   - Demo Settings: a block "AI model (demo setup)" where the key can be replaced and the model
     chosen. The server writes the key to the git-ignored file, never returns it (show only that
     one is set and its last four characters), accepts the request only from localhost, and never
     logs it.
   - Tests with a fake HTTP layer; then one live call to confirm the key works.
2. Read the evaluation report and fix its blockers and majors, then re-run the tests.
3. Pitch deck: https://claude.ai/artifact/SyUgwmLNJXvXCqqHrvUMmq (private to the owner; share it
   from its Share menu). 15 slides planned, 14 written. Missing: the "status" slide (what works
   today: test count, evaluation verdict, what is not verified). The production slide's cost
   figures are for Gemini and should be redone for Claude (list prices per million tokens on
   3 Nov 2026: Haiku 5.5 $0.10 in / $0.50 out, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20; a chat turn
   is about 10,000 input tokens across two calls).
4. Junction deadlines: draft submission on the Junction Platform by Friday 23:59, final by Sunday
   10:00 with a public video of at most two minutes, live peer review Sunday 10:30 to 14:00.

## Known gaps, stated plainly

- No AI model has answered a real question yet. Everything shown so far is the built-in rules.
- The user interface was checked by eye on Home, Chat, Settings and the consent screen at phone
  width. The screens added last (text explainer sheet, goal card, patterns card, leak finder,
  payday plan, area) were not looked at in a browser.
- Repeating charges and investment withdrawals are rare in the synthetic data, so "forgotten
  subscriptions" and "savings leakage" usually have nothing to show.
- The legal mapping in the security plan has not been reviewed by anyone with legal training.
