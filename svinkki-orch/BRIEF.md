# Shared brief for agent-s workers (Svinkki, Junction 2026)

You are a worker in a multi-agent round led by **agent-s** (the lead). The lead plans, reviews and
merges; you build. Final submission is Sun 15 Nov 2026 10:00 Finnish time (08:00 UTC): `main` must stay
demoable at all times. Small PRs.

## The project
Repo `NoVaselineTonight/Svinkki-Junction-2026`. Svinkki is a mobile-first web app (Python 3.13 stdlib
server + vanilla JS in `web/`) for the S-Pankki "Personal Economic Trainer" challenge: a customer chats
with their own bank data; the coach is Claude with tools, built-in rules answer without a key.
Read in your worktree before you start: `AGENTS.md` (binding), `CHALLENGE_DESCRIPTION.md`, `README.md`,
`HANDOFF.md`, `DEMO.md`, `.devloop/WAVE5.md` (what agent-d changed this morning: general_estimate,
calculate, repair round, findings, usual payday). Skim `docs/EVALUATION.md` and `docs/SECURITY_PLAN.md`
if your task touches data or the model. Judging criteria: financial literacy, originality of AI
integration, mobile UX, feasibility, S-mobiili integration.

## Environment (hard rules)
- Windows, Git Bash. `python`, never `python3`. Standard library only, no new dependencies, no build step.
- Tests: `python -m unittest discover -s tests` (about 876 tests, 75-120 s). Run the full suite before
  every push. Every fix lands with a test that FAILED before the fix. Say in your report that you saw it fail.
- Your worktree has no database or key. For anything that runs the app on real data set
  `SVINKKI_DB=C:/Users/onnik/Desktop/challenge-1/data/svinkki.db` and
  `SVINKKI_STATE_DB=C:/Users/onnik/Desktop/svinkki-orch/state-<your-name>.db` (your own; never touch
  `challenge-1/data/state.db`), and `SVINKKI_AI_SETTINGS_FILE=C:/Users/onnik/Desktop/svinkki-orch/ai-<your-name>.json`.
  Use your own port: 8000 + your number * 10 (agent-s3 -> 8030).
- **Money:** live Claude calls cost money. Unless your task says you have a live budget, run EVERY
  script and server with `SVINKKI_AI_KEY_FILE=/nonexistent` and `ANTHROPIC_API_KEY=` (empty). Without a key the
  built-in rules answer and nothing is billed. If you do have a budget, use
  `SVINKKI_AI_KEY_FILE=C:/Users/onnik/Desktop/challenge-1/claude_api_key.txt`, and append ONE line per live chat
  turn to `C:/Users/onnik/Desktop/svinkki-orch/live_budget.log` (`agent, model, question`) BEFORE making it;
  stop when your allotment is used. The whole team has 40 turns in total.
  Never print, log, echo, cat or commit the key or any part of it.
- Demo date 2026-09-26 (the default `SVINKKI_TODAY`), demo persona Veeti (log in as Veeti in the picker,
  or see how `app/server.py` logs in a persona).

## Coordination (enforced by git hooks and CI; do not work around it)
- Your worktree is already created, on branch `agent-sN/<task>` from origin/main, with your agent name set.
  First command: `python .agents/agentchat.py status` and confirm the name is yours. If not, run
  `python .agents/agentchat.py setup --name <your-name>`.
- Claim every file BEFORE editing it: `python .agents/agentchat.py claim <paths> --task "..."`. Only edit
  files you hold. Claim specific files, not whole directories, so others can work beside you. If refused,
  do not edit; tell the lead in your report.
- Other agents are active (agent-c on decks/web, agent-d may come back). Check `python .agents/agentchat.py
  claims` first. `app/coach.py` is the bottleneck: only claim it when your task says so. Do not split or
  refactor coach.py.
- Commit often with clear messages; end each commit message with the line
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Finish a PR: `git fetch origin && git rebase origin/main`, run the full suite, `git push -u origin HEAD`,
  `gh pr create --fill` (or with a short body ending with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`), wait for CI with `gh pr checks <n> --watch`.
  **Do NOT merge and do NOT run `agentchat done`.** The lead reviews and merges, then releases your claims.
  Post one `python .agents/agentchat.py say PROGRESS "..."` when your PR is open.
- If you stop to wait for something (a file held by someone else, a review), end your turn with a clear
  report; the lead will message you to continue.

## Report format (your final message to the lead)
1. PR URL(s) and CI state. 2. What changed, file by file, one line each. 3. Tests: count, time, OK or
not, and which new tests you saw fail before the fix. 4. What you RAN (and on what data) versus what you
only READ. 5. Live turns used (if any). 6. Anything open, risky or not verified. Be plain; do not claim what
you did not run.
