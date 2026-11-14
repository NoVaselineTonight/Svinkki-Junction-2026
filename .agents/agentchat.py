#!/usr/bin/env python3
"""
agentchat - coordination for multiple AI agents working in one GitHub repo.

The chat is one GitHub issue (see .agents/config.json). Every agent reads and
writes it through this script. File claims are computed from the chat history
with one deterministic rule (earliest claim wins), so every agent and the CI
check always agree on who owns which file.

Requires: python3 (3.8+), git, gh (logged in: `gh auth login`).

Run `python3 .agents/agentchat.py help` for commands.
"""
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
DEFAULT_CONFIG = {
    "chat_issue": 1,          # issue number used as the chat room
    "recent": 100,            # how many messages `read` and session start show
    "sync_ttl_seconds": 15,   # how long a local copy of the chat counts as fresh
    "stale_minutes": 30,      # claim considered stale after owner is silent this long
    "protected_branches": ["main", "master"],
}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,38}$")
HEADER_RE = re.compile(r"^\[(?P<agent>[A-Za-z0-9][A-Za-z0-9_.-]*)\]\s+(?P<type>[A-Z]+)\b(?P<rest>.*)$")
TYPES = ["CLAIM", "RELEASE", "REQUEST", "INFO", "QUESTION", "PROGRESS", "BLOCKED", "DONE"]
SAY_TYPES = ["REQUEST", "INFO", "QUESTION", "PROGRESS", "BLOCKED"]


# --------------------------------------------------------------------------- utils

def die(msg, code=1):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception as e:  # noqa
            die("agentchat: cannot parse %s: %s" % (CONFIG_PATH, e))
    if os.environ.get("AGENTCHAT_ISSUE"):
        cfg["chat_issue"] = int(os.environ["AGENTCHAT_ISSUE"])
    return cfg


CFG = load_config()


def run(cmd, input_text=None, check=True, cwd=None):
    p = subprocess.run(cmd, input=input_text, capture_output=True, text=True, cwd=cwd)
    if check and p.returncode != 0:
        raise RuntimeError("%s failed (%d): %s" % (" ".join(cmd), p.returncode, (p.stderr or p.stdout).strip()))
    return p


def git(*args, check=True):
    return run(["git"] + list(args), check=check).stdout.strip()


def repo_root():
    try:
        return Path(git("rev-parse", "--show-toplevel"))
    except Exception:
        return None


def state_dir():
    """Per-worktree private state (not committed)."""
    try:
        d = Path(git("rev-parse", "--absolute-git-dir")) / "agentchat"
    except Exception:
        d = Path(tempfile.gettempdir()) / "agentchat-state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json_atomic(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp%d" % os.getpid())
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def agent_name(required=True):
    name = os.environ.get("AGENT_NAME", "").strip()
    if not name:
        name = git("config", "--get", "agentchat.name", check=False)
    if name and not NAME_RE.match(name):
        die("agentchat: invalid agent name %r (letters, digits, - _ . only)" % name)
    if required and not name:
        die(
            "agentchat: no agent name set.\n"
            "  Run: python3 .agents/agentchat.py setup --name <agent-name>\n"
            "  (or export AGENT_NAME=<agent-name>). Ask the human which name to use."
        )
    return name


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)


# --------------------------------------------------------------------------- paths

def norm_path(p, root=None):
    """Repo-relative POSIX path. Directories end with '/'. Returns None if invalid."""
    p = p.strip().strip("`'\"")
    if not p:
        return None
    is_dir = p.endswith("/")
    if root is not None and os.path.isabs(p):
        try:
            p = os.path.relpath(os.path.realpath(p), os.path.realpath(str(root)))
        except ValueError:
            return None
    p = p.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p in ("", ".") and is_dir:
        return None  # claiming the whole repo is not allowed
    parts = [x for x in p.split("/") if x not in ("", ".")]
    if not parts or ".." in parts or os.path.isabs(p):
        return None
    p = "/".join(parts)
    if is_dir or (root is not None and (Path(root) / p).is_dir()):
        p += "/"
    return p


def covers(holder, path):
    """True if claim `holder` covers `path` (same file, or holder is a parent dir)."""
    return holder == path or (holder.endswith("/") and path.startswith(holder))


def overlaps(a, b):
    return covers(a, b) or covers(b, a)


# --------------------------------------------------------------------------- messages

def parse_message(body):
    lines = (body or "").strip().splitlines()
    if not lines:
        return None
    m = HEADER_RE.match(lines[0].strip())
    if not m or m.group("type") not in TYPES:
        return None
    fields = {}
    for line in lines[1:]:
        mm = re.match(r"^\s*([a-z_]+)\s*:\s*(.*)$", line)
        if mm and mm.group(1) not in fields:
            fields[mm.group(1)] = mm.group(2).strip()
    return {"agent": m.group("agent"), "type": m.group("type"), "rest": m.group("rest").strip(), "fields": fields}


def split_files(value):
    if not value:
        return []
    return [x for x in re.split(r"[,\s]+", value) if x]


def compute_state(comments):
    """
    Replay the chat in order and return:
      active:   list of {agent, path, comment_id, created_at, task}
      verdicts: {comment_id: ("granted", None) | ("rejected", [conflicting claims])}
      last_seen:{agent: created_at of their last message}
    Rule: a CLAIM is granted only if NONE of its paths overlap an active claim of
    another agent at that moment. Otherwise the whole CLAIM is rejected.
    """
    active, verdicts, last_seen = [], {}, {}
    for c in sorted(comments, key=lambda c: (c["created_at"], int(c["id"]))):
        msg = parse_message(c["body"])
        if not msg:
            continue
        agent = msg["agent"]
        last_seen[agent] = c["created_at"]
        if msg["type"] == "CLAIM":
            paths = [norm_path(p) for p in split_files(msg["fields"].get("files"))]
            if not paths or any(p is None for p in paths):
                verdicts[c["id"]] = ("rejected", "invalid or missing files: line")
                continue
            conflicts = [a for a in active if a["agent"] != agent and any(overlaps(a["path"], p) for p in paths)]
            if conflicts:
                verdicts[c["id"]] = ("rejected", conflicts)
                continue
            verdicts[c["id"]] = ("granted", None)
            for p in paths:
                if not any(a["agent"] == agent and covers(a["path"], p) for a in active):
                    active.append({"agent": agent, "path": p, "comment_id": c["id"],
                                   "created_at": c["created_at"], "task": msg["fields"].get("task", "")})
        elif msg["type"] == "RELEASE":
            owner = msg["fields"].get("owner", agent).strip() or agent
            raw = split_files(msg["fields"].get("files"))
            if not raw or "*" in raw:
                active = [a for a in active if a["agent"] != owner]
            else:
                rel = [p for p in (norm_path(x) for x in raw) if p]
                active = [a for a in active if not (a["agent"] == owner and any(covers(r, a["path"]) for r in rel))]
    return active, verdicts, last_seen


def holder_of(active, path):
    return [a for a in active if overlaps(a["path"], path)]


def is_mine(active, agent, path):
    return any(a["agent"] == agent and covers(a["path"], path) for a in active)


# --------------------------------------------------------------------------- backend

class Backend:
    """GitHub issue backend. Set AGENTCHAT_FAKE_DB=<file.json> to use a local fake (tests)."""

    def __init__(self):
        self.fake = os.environ.get("AGENTCHAT_FAKE_DB")
        self.issue = CFG["chat_issue"]

    def fetch(self, since=None):
        if self.fake:
            db = read_json(Path(self.fake), {"comments": []})
            out = db["comments"]
            return [c for c in out if not since or c["updated_at"] >= since]
        url = "repos/{owner}/{repo}/issues/%d/comments?per_page=100" % self.issue
        if since:
            url += "&since=" + since
        p = run(["gh", "api", "--paginate", url, "--jq",
                 ".[] | {id: .id, created_at: .created_at, updated_at: .updated_at, body: .body, user: .user.login} | @json"],
                check=False)
        if p.returncode != 0:
            raise RuntimeError("gh api failed: " + (p.stderr or p.stdout).strip())
        res = []
        for line in p.stdout.splitlines():
            line = line.strip()
            if line:
                res.append(json.loads(line))
        return res

    def post(self, body):
        if self.fake:
            path = Path(self.fake)
            db = read_json(path, {"comments": [], "next_id": 1})
            cid = db.get("next_id", 1)
            db["next_id"] = cid + 1
            ts = os.environ.get("AGENTCHAT_FAKE_TIME") or now_iso()
            c = {"id": cid, "created_at": ts, "updated_at": ts, "body": body, "user": "fake"}
            db["comments"].append(c)
            write_json_atomic(path, db)
            return c
        last = None
        for attempt in range(4):
            p = run(["gh", "api", "-X", "POST", "repos/{owner}/{repo}/issues/%d/comments" % self.issue,
                     "--input", "-"], input_text=json.dumps({"body": body}), check=False)
            if p.returncode == 0:
                c = json.loads(p.stdout)
                return {"id": c["id"], "created_at": c["created_at"], "updated_at": c["updated_at"],
                        "body": c["body"], "user": c.get("user", {}).get("login")}
            last = (p.stderr or p.stdout).strip()
            time.sleep(2 * (attempt + 1))
        raise RuntimeError("could not post to chat: " + last)


BACKEND = Backend()


def cache_path():
    return state_dir() / ("chat-%d.json" % CFG["chat_issue"])


def load_cache():
    return read_json(cache_path(), {"comments": {}, "max_updated": None, "synced_at": 0})


def sync(force=False):
    """Bring the local copy of the chat up to date. Returns sorted comment list."""
    cache = load_cache()
    if force or time.time() - cache.get("synced_at", 0) > CFG["sync_ttl_seconds"]:
        flush_outbox()
        cache = load_cache()
        new = BACKEND.fetch(since=cache.get("max_updated"))
        for c in new:
            cache["comments"][str(c["id"])] = c
            if not cache["max_updated"] or c["updated_at"] > cache["max_updated"]:
                cache["max_updated"] = c["updated_at"]
        cache["synced_at"] = time.time()
        write_json_atomic(cache_path(), cache)
    return sorted(cache["comments"].values(), key=lambda c: (c["created_at"], int(c["id"])))


def remember(c):
    cache = load_cache()
    cache["comments"][str(c["id"])] = c
    write_json_atomic(cache_path(), cache)


def post(body, queue_on_fail=False):
    try:
        c = BACKEND.post(body)
        remember(c)
        return c
    except Exception as e:
        if not queue_on_fail:
            raise
        ob = state_dir() / "outbox.jsonl"
        with ob.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"body": body}) + "\n")
        sys.stderr.write("agentchat: posting failed, queued for retry (%s)\n" % e)
        return None


def flush_outbox():
    ob = state_dir() / "outbox.jsonl"
    if not ob.exists():
        return
    lines = [l for l in ob.read_text(encoding="utf-8").splitlines() if l.strip()]
    ob.unlink()
    for i, line in enumerate(lines):
        try:
            c = BACKEND.post(json.loads(line)["body"])
            remember(c)
        except Exception:
            with ob.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines[i:]) + "\n")
            return


def header(agent, typ):
    return "[%s] %s" % (agent, typ)


def fmt_comment(c):
    t = c["created_at"].replace("T", " ").replace("Z", "")
    body = c["body"].strip()
    return "%s  %s" % (t, body.replace("\n", "\n" + " " * 21))


def fmt_claims(active, me=None):
    if not active:
        return "  (no active claims)"
    out = []
    for a in active:
        mark = " <- you" if me and a["agent"] == me else ""
        out.append("  %-28s %-14s since %s%s" % (a["path"], a["agent"], a["created_at"], mark))
    return "\n".join(out)


# --------------------------------------------------------------------------- seen-tracking

def seen_path(agent):
    return state_dir() / ("seen-%s.json" % agent)


def unseen_messages(agent, comments, mark=True):
    sp = seen_path(agent)
    seen = read_json(sp, {"ids": []})
    seen_ids = set(seen["ids"])
    new = [c for c in comments if str(c["id"]) not in seen_ids]
    if mark:
        write_json_atomic(sp, {"ids": [str(c["id"]) for c in comments][-5000:]})
    return new


def is_from(agent, c):
    m = parse_message(c["body"])
    return bool(m and m["agent"] == agent)


# --------------------------------------------------------------------------- commands

def cmd_setup(args):
    name = None
    if "--name" in args:
        name = args[args.index("--name") + 1]
    if not name:
        die("usage: agentchat.py setup --name <agent-name>")
    if not NAME_RE.match(name):
        die("invalid name: letters, digits, - _ . only")
    root = repo_root()
    if not root:
        die("run setup inside the git repo")
    git("config", "extensions.worktreeConfig", "true")
    git("config", "--worktree", "agentchat.name", name)
    git("config", "core.hooksPath", ".githooks")
    for h in (root / ".githooks").glob("*"):
        h.chmod(0o755)
    (root / ".agents" / "agentchat.py").chmod(0o755)
    print("agent name: %s (this worktree)" % name)
    print("git hooks:  .githooks enabled")
    if not BACKEND.fake:
        p = run(["gh", "api", "user", "--jq", ".login"], check=False)
        if p.returncode != 0:
            die("gh cannot reach GitHub (not logged in?). Run: gh auth login")
        print("github:     " + p.stdout.strip())
    comments = sync(force=True)
    active, _, _ = compute_state(comments)
    print("chat:       issue #%d, %d messages" % (CFG["chat_issue"], len(comments)))
    print("claims:\n" + fmt_claims(active, name))
    print("\nNext: python3 .agents/agentchat.py claim <files...> --task \"<what you will do>\"")


def cmd_read(args):
    n = CFG["recent"]
    if "-n" in args:
        n = int(args[args.index("-n") + 1])
    comments = sync(force=True)
    for c in comments[-n:]:
        print(fmt_comment(c))
    me = agent_name(required=False)
    if me:
        unseen_messages(me, comments, mark=True)


def cmd_new(args):
    me = agent_name()
    comments = sync(force=True)
    new = [c for c in unseen_messages(me, comments) if not is_from(me, c)]
    if not new:
        print("(no new messages)")
    for c in new:
        print(fmt_comment(c))


def cmd_claims(args):
    comments = sync(force=True)
    active, _, last_seen = compute_state(comments)
    me = agent_name(required=False)
    print("Active claims:")
    print(fmt_claims(active, me))
    stale = stale_owners(active, last_seen)
    if stale:
        print("\nStale (owner silent > %d min): %s" % (CFG["stale_minutes"], ", ".join(sorted(stale))))


def stale_owners(active, last_seen):
    out = set()
    now = _dt.datetime.now(_dt.timezone.utc)
    for a in active:
        ls = last_seen.get(a["agent"])
        if ls and (now - parse_iso(ls)).total_seconds() > CFG["stale_minutes"] * 60:
            out.add(a["agent"])
    return out


def pop_opt(args, flag, default=""):
    if flag in args:
        i = args.index(flag)
        if i + 1 >= len(args):
            die("missing value for " + flag)
        val = args[i + 1]
        del args[i:i + 2]
        return val
    return default


def cmd_claim(args):
    me = agent_name()
    args = list(args)
    task = pop_opt(args, "--task")
    if not task:
        die('usage: agentchat.py claim <file|dir/>... --task "<what you will do>"')
    root = repo_root()
    paths = []
    for raw in args:
        p = norm_path(raw, root)
        if not p:
            die("invalid path: %r (must be inside the repo, no '..', not the whole repo)" % raw)
        paths.append(p)
    if not paths:
        die("list at least one file or directory")
    comments = sync(force=True)
    active, _, _ = compute_state(comments)
    conflicts = [a for a in active if a["agent"] != me and any(overlaps(a["path"], p) for p in paths)]
    if conflicts:
        die("CLAIM REFUSED - already held:\n" + fmt_claims(conflicts) +
            "\nDo NOT edit these. Work on something else, or ask:\n"
            "  python3 .agents/agentchat.py say REQUEST \"@%s please release <file> when done\"" % conflicts[0]["agent"], 3)
    todo = [p for p in paths if not is_mine(active, me, p)]
    if not todo:
        print("You already hold: " + ", ".join(paths))
        return
    branch = git("rev-parse", "--abbrev-ref", "HEAD", check=False)
    body = "%s\ntask: %s\nfiles: %s\nbranch: %s" % (header(me, "CLAIM"), task, ", ".join(todo), branch)
    c = post(body)
    # Re-read: someone may have claimed the same thing a moment earlier.
    comments = sync(force=True)
    _, verdicts, _ = compute_state(comments)
    v = verdicts.get(c["id"])
    if v and v[0] == "granted":
        print("CLAIM GRANTED: " + ", ".join(todo))
        print("You may now edit these files. Nothing else.")
        return
    post("%s\nclaim %s withdrawn: another agent claimed first" % (header(me, "INFO"), c["id"]), queue_on_fail=True)
    detail = fmt_claims(v[1]) if v and isinstance(v[1], list) else str(v[1] if v else "unknown")
    die("CLAIM LOST - another agent claimed first:\n" + detail + "\nDo NOT edit these files.", 3)


def cmd_release(args):
    me = agent_name()
    args = list(args)
    owner = pop_opt(args, "--owner")
    reason = pop_opt(args, "--reason")
    all_ = "--all" in args
    args = [a for a in args if a != "--all"]
    root = repo_root()
    if all_:
        files = "*"
    else:
        ps = [norm_path(a, root) for a in args]
        if not ps or any(p is None for p in ps):
            die("usage: agentchat.py release <files...> | --all   [--owner <agent> --reason \"...\"]")
        files = ", ".join(ps)
    if owner and owner != me:
        comments = sync(force=True)
        active, _, last_seen = compute_state(comments)
        if owner not in stale_owners(active, last_seen):
            die("Refused: %s is not stale. Only release another agent's claim if they have been silent > %d min." %
                (owner, CFG["stale_minutes"]))
        if not reason:
            die("--reason is required when releasing someone else's claim")
    body = "%s\nfiles: %s" % (header(me, "RELEASE"), files)
    if owner and owner != me:
        body += "\nowner: %s\nreason: %s" % (owner, reason)
    post(body)
    print("Released: " + files)


def cmd_say(args):
    me = agent_name()
    if len(args) < 2 or args[0].upper() not in SAY_TYPES:
        die("usage: agentchat.py say <%s> \"message\"" % "|".join(SAY_TYPES))
    typ = args[0].upper()
    text = " ".join(args[1:]).strip()
    if not text:
        die("empty message")
    post("%s\n%s" % (header(me, typ), text))
    print("posted " + typ)


def cmd_done(args):
    me = agent_name()
    args = list(args)
    pr = pop_opt(args, "--pr")
    summary = pop_opt(args, "--summary")
    if not summary:
        die('usage: agentchat.py done --summary "what changed" [--pr <url>]')
    body = "%s\nsummary: %s" % (header(me, "DONE"), summary)
    if pr:
        body += "\npr: %s" % pr
    post(body)
    post("%s\nfiles: *" % header(me, "RELEASE"))
    print("DONE posted, all your claims released.")


def cmd_status(args):
    me = agent_name()
    comments = sync(force=True)
    active, _, _ = compute_state(comments)
    mine = [a for a in active if a["agent"] == me]
    print("You are %s on branch %s" % (me, git("rev-parse", "--abbrev-ref", "HEAD", check=False)))
    print("Your claims:\n" + fmt_claims(mine, me))
    new = [c for c in unseen_messages(me, comments, mark=False) if not is_from(me, c)]
    print("Unread messages: %d (run: python3 .agents/agentchat.py new)" % len(new))


def check_paths(me, paths, force=True):
    comments = sync(force=force)
    active, _, _ = compute_state(comments)
    bad = [p for p in paths if not is_mine(active, me, p)]
    if bad and not force:
        # About to block: refresh so the explanation (who holds it) is current.
        active, _, _ = compute_state(sync(force=True))
        bad = [p for p in paths if not is_mine(active, me, p)]
    return [(p, holder_of(active, p)) for p in bad], active


def explain_bad(bad):
    lines = []
    for p, holders in bad:
        if holders:
            lines.append("  %s  -> held by %s" % (p, ", ".join(sorted({h["agent"] for h in holders}))))
        else:
            lines.append("  %s  -> nobody holds it, claim it first" % p)
    return "\n".join(lines)


def cmd_check(args):
    me = agent_name()
    root = repo_root()
    paths = [norm_path(a, root) for a in args]
    bad, _ = check_paths(me, [p for p in paths if p])
    if bad:
        die("Not claimed by %s:\n%s" % (me, explain_bad(bad)), 1)
    print("ok")


# --------------------------------------------------------------------------- git hooks

def in_rebase():
    gd = Path(git("rev-parse", "--absolute-git-dir"))
    return (gd / "rebase-merge").exists() or (gd / "rebase-apply").exists()


def cmd_git_pre_commit(args):
    me = agent_name()
    out = run(["git", "diff", "--cached", "--name-only", "--no-renames", "-z"]).stdout
    files = [f for f in out.split("\0") if f]
    if not files:
        return
    try:
        bad, _ = check_paths(me, files)
    except Exception as e:
        die("COMMIT BLOCKED: could not read the coordination chat (%s).\nFix network/gh auth and retry." % e)
    if bad:
        die("COMMIT BLOCKED: you (%s) staged files you have not claimed:\n%s\n\n"
            "Claim them first:  python3 .agents/agentchat.py claim <file> --task \"...\"\n"
            "Or unstage them:   git restore --staged <file>" % (me, explain_bad(bad)))


def cmd_git_post_commit(args):
    if in_rebase():
        return
    me = agent_name(required=False)
    if not me:
        return
    sha = git("rev-parse", "--short", "HEAD")
    subject = git("log", "-1", "--format=%s")
    branch = git("rev-parse", "--abbrev-ref", "HEAD", check=False)
    files = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", "HEAD", check=False).splitlines()
    shown = ", ".join(files[:15]) + (" (+%d more)" % (len(files) - 15) if len(files) > 15 else "")
    post("%s\ncommit %s on %s: %s\nfiles: %s" % (header(me, "PROGRESS"), sha, branch, subject, shown),
         queue_on_fail=True)


def cmd_git_pre_push(args):
    me = agent_name()
    protected = set(CFG["protected_branches"])
    pushed = []
    for line in sys.stdin.read().splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, _ = parts
        br = remote_ref.replace("refs/heads/", "", 1)
        if set(local_sha) == {"0"}:
            continue  # branch deletion
        if br in protected:
            die("PUSH BLOCKED: never push directly to %s. Push your branch and open a PR." % br)
        if not br.startswith(me + "/"):
            die("PUSH BLOCKED: your branches must be named %s/<task> (got %s).\n"
                "  git branch -m %s/<task>" % (me, br, me))
        pushed.append(br)
    if pushed:
        post("%s\npushed %s" % (header(me, "PROGRESS"), ", ".join(pushed)), queue_on_fail=True)


# --------------------------------------------------------------------------- Claude Code hooks

def _enter(path):
    """Work from `path`. Claude Code starts hooks in the project folder, which for a session in a git
    worktree is the main checkout: the agent name, the repo root and the claims would be the wrong ones."""
    try:
        if path and os.path.isdir(path):
            os.chdir(path)
    except OSError:
        pass


def _common_git_dir():
    """The repository's shared .git folder: the same for the main checkout and every worktree of it."""
    out = git("rev-parse", "--git-common-dir", check=False)
    return os.path.normcase(os.path.realpath(os.path.join(os.getcwd(), out))) if out else None


def hook_input():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    _enter(data.get("cwd"))
    return data


def cmd_hook_session_start(args):
    hook_input()
    me = agent_name(required=False)
    out = []
    if not me:
        out.append("COORDINATION: No agent name is set for this worktree. Before doing ANY work, ask the human "
                   "for your agent name, then run: python3 .agents/agentchat.py setup --name <name>")
        print("\n".join(out))
        return
    try:
        comments = sync(force=True)
    except Exception as e:
        print("COORDINATION: could not read the chat (%s). Fix `gh auth login` before editing anything." % e)
        return
    active, _, _ = compute_state(comments)
    out.append("COORDINATION (read AGENTS.md). You are agent '%s'. You may only edit files you have claimed." % me)
    out.append("Active claims:\n" + fmt_claims(active, me))
    out.append("Last %d chat messages (issue #%d):" % (CFG["recent"], CFG["chat_issue"]))
    for c in comments[-CFG["recent"]:]:
        out.append(fmt_comment(c))
    unseen_messages(me, comments, mark=True)
    print("\n".join(out))


def edited_paths_from_hook(data):
    ti = data.get("tool_input") or {}
    paths = []
    for k in ("file_path", "notebook_path", "path"):
        if ti.get(k):
            paths.append(ti[k])
    for e in ti.get("edits") or []:
        if isinstance(e, dict) and e.get("file_path"):
            paths.append(e["file_path"])
    return paths


def cmd_hook_pre_edit(args):
    data = hook_input()
    # The edited file decides which worktree (and so which agent) this is: go to its nearest existing folder,
    # but only when that folder belongs to this same repository. Files elsewhere are not our business.
    base, ours = os.getcwd(), _common_git_dir()
    for p in edited_paths_from_hook(data):
        d = os.path.dirname(p if os.path.isabs(p) else os.path.join(data.get("cwd") or base, p))
        while d and not os.path.isdir(d) and os.path.dirname(d) != d:
            d = os.path.dirname(d)
        _enter(d)
        if not ours or _common_git_dir() != ours:
            _enter(base)
        break
    me = agent_name(required=False)
    if not me:
        die("BLOCKED: no agent name set. Ask the human for your name, then run "
            "python3 .agents/agentchat.py setup --name <name>", 2)
    root = repo_root()
    rel = []
    for p in edited_paths_from_hook(data):
        ap = os.path.realpath(p if os.path.isabs(p) else os.path.join(data.get("cwd") or os.getcwd(), p))
        if root and not ap.startswith(os.path.realpath(str(root)) + os.sep):
            continue  # outside the repo: not our business
        n = norm_path(ap, root)
        if n and not n.startswith(".git/"):
            rel.append(n.rstrip("/"))
    if not rel:
        return
    try:
        bad, _ = check_paths(me, rel, force=False)
    except Exception as e:
        die("BLOCKED: cannot read the coordination chat (%s). Fix gh auth / network first." % e, 2)
    if bad:
        die("BLOCKED: you (%s) have not claimed:\n%s\n"
            "Claim first: python3 .agents/agentchat.py claim <file> --task \"...\"\n"
            "If someone else holds it, do NOT edit it. Post a REQUEST or work on something else."
            % (me, explain_bad(bad)), 2)


def cmd_hook_post_tool(args):
    hook_input()
    me = agent_name(required=False)
    if not me:
        return
    try:
        comments = sync(force=False)
    except Exception:
        return
    new = [c for c in unseen_messages(me, comments) if not is_from(me, c)]
    if not new:
        return
    text = "NEW COORDINATION MESSAGES (from other agents):\n" + "\n".join(fmt_comment(c) for c in new[-30:])
    mentions = [c for c in new if ("@" + me) in c["body"]]
    if mentions:
        text += "\n\n%d message(s) mention @%s. Respond with agentchat.py say ... before continuing." % (len(mentions), me)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))


def cmd_hook_stop(args):
    data = hook_input()
    if data.get("stop_hook_active"):
        return
    me = agent_name(required=False)
    if not me:
        return
    try:
        comments = sync(force=True)
    except Exception:
        return
    active, _, _ = compute_state(comments)
    mine = [a for a in active if a["agent"] == me]
    if mine:
        print(json.dumps({"decision": "block", "reason":
            "You still hold claims:\n%s\nBefore stopping, either finish and run "
            "`python3 .agents/agentchat.py done --summary \"...\" --pr <url>`, or post why you keep them: "
            "`python3 .agents/agentchat.py say BLOCKED \"...\"` (or PROGRESS). Then you may stop." % fmt_claims(mine, me)}))


# --------------------------------------------------------------------------- CI

def cmd_ci_check_pr(args):
    """Fail if a PR from an agent branch touches files that agent has not claimed."""
    branch = os.environ.get("GITHUB_HEAD_REF") or git("rev-parse", "--abbrev-ref", "HEAD")
    base = os.environ.get("GITHUB_BASE_REF") or "main"
    agent = branch.split("/", 1)[0] if "/" in branch else ""
    comments = sync(force=True)
    active, _, last_seen = compute_state(comments)
    known_agents = set(last_seen)
    if agent not in known_agents:
        print("Branch %s does not belong to a known agent; skipping claim check (human PR)." % branch)
        return
    out = run(["git", "diff", "--name-only", "--no-renames", "origin/%s...HEAD" % base]).stdout
    files = [f for f in out.splitlines() if f]
    bad = [(f, holder_of(active, f)) for f in files if not is_mine(active, agent, f)]
    if bad:
        die("PR touches files %s has not claimed:\n%s" % (agent, explain_bad(bad)))
    print("All %d changed files are claimed by %s." % (len(files), agent))


def cmd_help(args):
    print(__doc__)
    print("""Commands (python3 .agents/agentchat.py <command>):
  setup --name <name>            one-time per worktree: set identity, enable git hooks
  status                         your claims + unread count
  read [-n N]                    last N chat messages (default %d)
  new                            only messages you have not seen yet
  claims                         all active claims
  claim <paths...> --task "..."  claim files/dirs (dirs end with /). Earliest claim wins.
  release <paths...> | --all     release your claims
  release --all --owner X --reason "..."   take over a STALE agent's claims
  say <TYPE> "message"           TYPE = %s
  done --summary "..." [--pr URL]  post DONE and release everything
  check <paths...>               exit 0 if you hold all of them""" % (CFG["recent"], "|".join(SAY_TYPES)))


COMMANDS = {
    "setup": cmd_setup, "read": cmd_read, "new": cmd_new, "claims": cmd_claims, "claim": cmd_claim,
    "release": cmd_release, "say": cmd_say, "done": cmd_done, "status": cmd_status, "check": cmd_check,
    "git-pre-commit": cmd_git_pre_commit, "git-post-commit": cmd_git_post_commit, "git-pre-push": cmd_git_pre_push,
    "hook-session-start": cmd_hook_session_start, "hook-pre-edit": cmd_hook_pre_edit,
    "hook-post-tool": cmd_hook_post_tool, "hook-stop": cmd_hook_stop,
    "ci-check-pr": cmd_ci_check_pr, "help": cmd_help,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        cmd_help([])
        sys.exit(0 if len(sys.argv) < 2 else 1)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except RuntimeError as e:
        die("agentchat: " + str(e))


if __name__ == "__main__":
    main()
