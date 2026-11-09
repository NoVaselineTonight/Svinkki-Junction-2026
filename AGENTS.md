# Multi-Agent Coordination Protocol

Several AI agents work in this repo at the same time. This protocol is ENFORCED by tooling:
git hooks block commits and pushes that break it, CI blocks PRs that break it, and (for Claude Code)
edits to unclaimed files are blocked before they happen. Do not try to work around it.

All coordination goes through ONE tool: `python3 .agents/agentchat.py`
(the chat itself is GitHub issue #1, but never post to it by hand).

## 0. First thing in every session
```bash
python3 .agents/agentchat.py status
```
If it says no agent name is set: STOP and ask the human for your agent name, then run
`python3 .agents/agentchat.py setup --name <name>`.

## 1. The golden rule
**You may only change files you have claimed. Claim BEFORE you touch anything.**
Creating, editing, deleting, renaming, formatting, regenerating: all count. Lockfiles and configs too.

## 2. Workflow (mandatory order)
1. Read the chat: `python3 .agents/agentchat.py read` (last 100 messages) and `... claims`.
2. Branch from latest main. Branch MUST be `<your-name>/<task>`:
   `git fetch origin && git switch -c <your-name>/<task> origin/main`
3. Claim every file/dir you will change (dirs end with `/`):
   `python3 .agents/agentchat.py claim src/api/auth.ts src/api/routes.ts --task "add login API"`
   - `CLAIM GRANTED` → you may edit those files, nothing else.
   - `CLAIM REFUSED` / `CLAIM LOST` → someone else has them. Do NOT edit them. Pick other work, or
     `python3 .agents/agentchat.py say REQUEST "@agent-b please release src/db.ts when done"`.
   - Earliest claim always wins. Never argue, never retry the same claim in a loop.
4. Need another file mid-task? Claim it first (step 3), then edit it.
5. Commit often. Every commit and push is posted to the chat automatically.
6. Report everything else yourself with `say`:
   - `say INFO "..."` – BEFORE merging any change other agents depend on: changed function
     signature, API shape, schema, new dependency, new top-level folder, renamed/moved file.
   - `say PROGRESS "..."` – milestones, test results, what you are about to do next.
   - `say BLOCKED "..."` – stuck, failing tests you can't fix, waiting on someone.
   - `say QUESTION "@agent-x ..."` – ask another agent. Answer questions to you with `say INFO`.
7. Check for messages: `python3 .agents/agentchat.py new` before every commit and at least every
   10 minutes. If a message mentions `@<your-name>`, respond before continuing.
8. Finish:
   ```bash
   git fetch origin && git rebase origin/main     # conflicts in files you don't own: STOP, say QUESTION
   # run the tests
   git push -u origin HEAD
   gh pr create --fill
   gh pr merge --squash --delete-branch            # only if CI passes
   python3 .agents/agentchat.py done --summary "what changed, 1-3 lines" --pr <url>
   ```
   `done` posts DONE and releases all your claims. Release as soon as you are merged.
   Abandoning a task? `python3 .agents/agentchat.py release --all` and `say INFO` why.

## 3. Rules
- Never push to `main`. Never force-push anyone else's branch. (Hooks block both.)
- Small tasks, short claims. Hot shared files (`package.json`, lockfiles, configs, routers, shared
  types): claim, change, merge, release immediately.
- Do not bypass hooks (`--no-verify`, editing via shell to dodge the edit check, etc.). CI catches
  it anyway and your PR will be blocked.
- Stale claims: if an agent has been silent 30+ min, `say REQUEST "@agent-x ..."`; if still no reply
  after 10 min: `release --all --owner agent-x --reason "stale 40 min, no reply"`. The tool refuses
  if the owner is not actually stale.
- Keep messages short. One message per event. Don't spam.

## 4. Command reference
| Command | What it does |
|---|---|
| `status` | Your name, branch, claims, unread count |
| `read [-n N]` | Last N messages (default 100) |
| `new` | Only messages you haven't seen |
| `claims` | All active claims, plus stale owners |
| `claim <paths> --task "..."` | Claim files/dirs |
| `release <paths>` / `release --all` | Release your claims |
| `say <REQUEST\|INFO\|QUESTION\|PROGRESS\|BLOCKED> "msg"` | Post a message |
| `done --summary "..." --pr <url>` | Post DONE and release everything |
| `check <paths>` | Exit 0 if you hold all of them |
