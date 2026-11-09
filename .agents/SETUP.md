# Human setup (once, ~5 min)

1. Copy everything in this kit into the repo root and push it to `main`:
   `AGENTS.md CLAUDE.md GEMINI.md .agents/ .githooks/ .claude/settings.json .github/workflows/agent-coordination.yml`
   (If you already have `.claude/settings.json` or `CLAUDE.md`, merge instead of overwriting.)
2. Create the chat issue: `gh issue create --title "Agent Coordination" --body "Agent chat. Do not post by hand."`
   If it is not #1, put its number in `.agents/config.json` (`chat_issue`).
3. GitHub → Settings → Branches → add a rule for `main`:
   - Require a pull request before merging
   - Require status checks to pass → select `claims` (appears after the first PR runs the workflow)
   - Do not allow bypassing
4. For EACH agent: give it its own clone or worktree, then in it run
   `gh auth login` (if not done) and
   `python3 .agents/agentchat.py setup --name agent-a`   (agent-b, agent-c, ...)
   This sets the agent's identity and turns on the git hooks for that clone.
5. Start the agents. Tell each one: "Read AGENTS.md and follow it exactly."

Notes
- Requires: git, python3 (3.8+), gh. On Windows, use Git Bash; if `python3` isn't found, edit the
  `.githooks/*` files and `.claude/settings.json` to say `python`.
- GitHub limits content creation to roughly 80 posts/minute and 500/hour per account. Every commit,
  push and message is a post. If agents share one GitHub account, that budget is shared. Use separate
  accounts/tokens per agent if you expect heavy traffic.
- Agent names must be unique: letters, digits, - _ . only. Branches must be `<name>/<task>`.
