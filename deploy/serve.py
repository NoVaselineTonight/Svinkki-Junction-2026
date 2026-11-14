"""Entry point for a hosted copy of the demo:  python -m deploy.serve

It starts the ordinary server (app.server) with what a host needs and a public address requires, without
changing the app itself:

- Port and address. The port comes from PORT (what hosting platforms set), else SVINKKI_PORT, else 8000. The
  server listens on all addresses when PORT is set, otherwise on 127.0.0.1; SVINKKI_HOST overrides.
- A cap on what the AI model can cost. SVINKKI_AI_DAILY_TURNS (default 400) is the number of customer
  questions a day (UTC) the model may answer. After that the built-in rules answer, and the reply says the AI
  is offline. 0 switches the model off; "off" removes the cap. A second cap, eight requests per turn,
  catches anything else that would call the model (the text explainer, a runaway loop).
- With SVINKKI_PUBLIC=1 the "Reset demo" endpoint is removed: on a public address anybody could otherwise
  wipe every visitor's demo state.

The key itself is read by the app on every request from ANTHROPIC_API_KEY (or the key file): switching the
key on the host needs no code change. See docs/DEPLOY.md.
"""
import datetime
import os
import sys
import threading

DEFAULT_DAILY_TURNS = 400
REQUESTS_PER_TURN = 8


class DailyBudget:
    """Counts model turns and requests per UTC day. Thread-safe. `limit` None means no cap."""

    def __init__(self, limit, clock=None, hour_clock=None):
        self.limit = limit
        self._clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc).date())
        self._hour_clock = hour_clock or (lambda: datetime.datetime.now(datetime.timezone.utc).hour)
        self._hour = None
        self.hour_turns = 0
        self._lock = threading.Lock()
        self._day = None
        self.turns = 0
        self.requests = 0

    def _roll(self):
        today = self._clock()
        if today != self._day:
            self._day, self.turns, self.requests = today, 0, 0
        hour = self._hour_clock()
        if hour != self._hour or today != getattr(self, "_hour_day", None):
            self._hour, self._hour_day, self.hour_turns = hour, today, 0

    def hourly_limit(self):
        """At most this many turns in one clock hour, so one abuser cannot switch the AI off for the day."""
        return None if self.limit is None else max(20, self.limit // 6)

    def take_turn(self):
        """True when one more customer question may go to the model today."""
        with self._lock:
            self._roll()
            if self.limit is not None and self.turns >= self.limit:
                return False
            hourly = self.hourly_limit()
            if hourly is not None and self.hour_turns >= hourly:
                return False
            self.turns += 1
            self.hour_turns += 1
            return True

    def take_request(self):
        """True when one more request to the model is allowed today (the backstop)."""
        with self._lock:
            self._roll()
            if self.limit is not None and self.requests >= self.limit * REQUESTS_PER_TURN:
                return False
            self.requests += 1
            return True

    def left(self):
        with self._lock:
            self._roll()
            if self.limit is None:
                return None
            left = max(self.limit - self.turns, 0)
            return min(left, max(self.hourly_limit() - self.hour_turns, 0))


def daily_limit(value):
    """SVINKKI_AI_DAILY_TURNS as a number of turns, or None for no cap. Unreadable values mean the default."""
    v = str(value if value is not None else "").strip().lower()
    if v in ("off", "none", "unlimited"):
        return None
    try:
        return max(int(v), 0)
    except ValueError:
        return DEFAULT_DAILY_TURNS


def install_budget(budget):
    """Put the cap in front of the model. Nothing in app/ is edited: the two functions every model call goes
    through are wrapped. A call over the cap fails the way an unreachable model does, so the coach answers
    with its built-in rules and tells the customer."""
    from app import coach, llm_claude
    turn, create = coach._claude_turn, llm_claude.create

    def capped_turn(message, history, ctx, key):
        if not budget.take_turn():
            raise llm_claude.ClaudeError("the demo's daily AI budget is used up")
        return turn(message, history, ctx, key)

    def capped_create(*args, **kwargs):
        if not budget.take_request():
            raise llm_claude.ClaudeError("the demo's daily AI budget is used up")
        return create(*args, **kwargs)

    capped_turn._svinkki_budget = capped_create._svinkki_budget = budget
    coach._claude_turn = capped_turn
    llm_claude.create = capped_create
    return budget


def make_public():
    """Remove what must not be reachable by anybody on a public address."""
    from app import server
    removed = [p for p in ("/api/demo/reset",) if server.ROUTES.pop(p, None) is not None]
    server.TRUST_FORWARDED_FOR = True   # behind the host's proxy the peer address is the proxy
    server.RATE_CHAT = 15               # one visitor cannot use up the day's AI in a few minutes
    server.PER_VISITOR_STATE = True   # every login gets a private copy of the persona's state
    return removed


def address(env):
    """(host, port) for this environment."""
    hosted = bool(str(env.get("PORT", "")).strip())
    try:
        port = int(env.get("PORT") or env.get("SVINKKI_PORT") or 8000)
    except ValueError:
        port = 8000
    host = (env.get("SVINKKI_HOST") or ("0.0.0.0" if hosted else "127.0.0.1")).strip()
    return host, port


def main(argv=None):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import server
    env = os.environ
    host, port = address(env)
    limit = daily_limit(env.get("SVINKKI_AI_DAILY_TURNS", DEFAULT_DAILY_TURNS))
    install_budget(DailyBudget(limit))
    removed = make_public() if str(env.get("SVINKKI_PUBLIC", "")).strip().lower() in ("1", "true", "yes") else []
    print("deploy: AI turns a day: %s; public mode: %s" % (
        "no cap" if limit is None else limit, ("on, removed " + ", ".join(removed)) if removed else "off"), flush=True)
    return server.main(["--host", host, "--port", str(port)])


if __name__ == "__main__":
    main()
