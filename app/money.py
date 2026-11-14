"""In-app money moves for the demo: saving and investing inside S-mobiili, always after approval.

Rules (owner decision, 14 Nov 2026; replaces "nothing moves" for the demo):
- Money only moves between the customer's own S-Bank current account and their own S-Bank savings
  account or an S-Bank fund. There is no destination outside S-mobiili, and no way to name one.
- The coach (built-in rules or the AI model) can only *propose* a move. A proposal moves nothing.
- A move happens only when the customer approves that exact proposal in the app: the approval names
  the proposal id, the amount and the destination, and must arrive within 15 minutes. Each proposal
  can be approved once.
- A move can never take more than what is safe to spend until payday, so bills are never touched.
- The data is synthetic; a move is recorded in the demo's own state, not at a real bank.
"""
import datetime
import secrets

from app import insights as ins
from app import state

MIN_AMOUNT = 5.0
MAX_AMOUNT = 50_000.0
FROM_ACCOUNT = "Your S-Bank current account"

DESTINATIONS = {
    "savings": {
        "name": "S-Bank savings account", "kind": "savings",
        "about": "Your own savings account in S-mobiili. You can move the money back at any time.",
        "risk": None,
    },
    "fund_index": {
        "name": "S-Bank global index fund", "kind": "fund",
        "about": "A fund that follows shares across the world. Suits money you can leave for five years or more.",
        "risk": "Fund value goes up and down; you can get back less than you put in.",
    },
    "fund_interest": {
        "name": "S-Bank short-term interest fund", "kind": "fund",
        "about": "A low-risk fund for money you may need within a year or two.",
        "risk": "Low risk, but the value can still dip a little.",
    },
}
DEST_IDS = tuple(DESTINATIONS)


class MoneyError(ValueError):
    """A move that is not allowed; the message is safe to show to the customer."""


def destinations():
    return [{"id": k, "name": v["name"], "kind": v["kind"], "about": v["about"], "risk": v["risk"]}
            for k, v in DESTINATIONS.items()]


def dest_from_text(text):
    """Map free words ('savings', 'index fund', 'interest fund', 'fund') to a destination id, else None."""
    s = str(text or "").lower()
    if s in DESTINATIONS:
        return s
    if any(w in s for w in ("interest fund", "korkorahasto", "short-term", "low risk", "low-risk", "bond")):
        return "fund_interest"
    if any(w in s for w in ("index", "equity", "global", "world", "osake", "indeksi", "fund", "rahasto",
                            "invest", "sijoit", "shares", "stocks", "etf")):
        return "fund_index"
    if any(w in s for w in ("saving", "säästö", "buffer", "puskuri", "set aside", "put aside")):
        return "savings"
    return None


def available(conn, today):
    """What can be moved now: what is safe to spend until payday (bills and the buffer are kept back)."""
    s = ins.safe_to_spend(conn, today)
    return max(0.0, float(s.get("safe_total") or 0.0)), s


def holdings(cid):
    """Money moved into each in-app destination so far (no fund price changes in the demo)."""
    out = {}
    for m in state.list_moves(cid):
        out[m["dest"]] = out.get(m["dest"], 0.0) + float(m["amount"])
    return [{"id": k, "name": DESTINATIONS[k]["name"], "kind": DESTINATIONS[k]["kind"], "amount": round(v, 2)}
            for k, v in out.items() if k in DESTINATIONS]


def _eur(v):
    v = float(v)
    return "€{:,.0f}".format(v) if round(v, 2) == round(v) else "€{:,.2f}".format(v)


def propose(conn, today, cid, dest, amount, reason="", source="chat", widget_id=None):
    """Create a pending proposal. Moves nothing. Returns the proposal the customer is asked to approve."""
    if dest not in DESTINATIONS:
        raise MoneyError("I can only move money to your S-Bank savings account or an S-Bank fund in S-mobiili.")
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise MoneyError("Tell me how much to move, in euros.")
    if amount != amount or amount < MIN_AMOUNT:
        raise MoneyError("The smallest amount I can move is %s." % _eur(MIN_AMOUNT))
    if amount > MAX_AMOUNT:
        raise MoneyError("That is more than can be moved in one go here.")
    cap, s = available(conn, today)
    if amount > cap + 0.004:
        if cap < MIN_AMOUNT:
            raise MoneyError("Nothing can be moved safely before payday: your balance is needed for bills and "
                             "a small buffer.")
        raise MoneyError("I can move at most %s now: the rest of your balance is needed for bills before payday."
                         % _eur(int(cap)))
    d = DESTINATIONS[dest]
    pid = secrets.token_urlsafe(12)
    prop = {
        "id": pid, "dest": dest, "amount": amount, "kind": d["kind"],
        "from": FROM_ACCOUNT, "to": d["name"], "about": d["about"], "risk": d["risk"],
        "reason": str(reason or "")[:200], "source": source, "available": round(cap, 2),
        "balance_after": round(float(s.get("balance") or 0.0) - amount, 2),
        "prompt": "Move %s from your current account to your %s?" % (_eur(amount), d["name"]),
        "note": "Nothing moves until you approve. The money stays in S-mobiili.",
        "expires_in_s": state.PROPOSAL_TTL_S,
    }
    if widget_id:   # a move into a savings plan on the home page: confirming it grows that plan's "saved"
        prop["widget_id"] = str(widget_id)[:20]
    state.save_proposal(cid, pid, prop)
    return prop


def confirm(conn, today, cid, pid, approve, amount=None, dest=None):
    """The customer's answer to one proposal. Only an explicit approval of the same amount and destination
    moves money, once."""
    if not isinstance(pid, str) or not pid or len(pid) > 64:
        raise MoneyError("I couldn't match that approval, so nothing was moved. Ask me again and I'll make a new offer.")
    got = state.get_proposal(cid, pid)
    if got is None:
        raise MoneyError("I couldn't match that approval, so nothing was moved. Ask me again and I'll make a new offer.")
    prop = got["data"]
    if got["status"] != "pending":
        raise MoneyError({"done": "This move was already made.", "cancelled": "This move was cancelled.",
                          "expired": "This offer has expired. Ask again and I will make a new one."}
                         .get(got["status"], "I couldn't match that approval, so nothing was moved. Ask me again and I'll make a new offer."))
    if approve is not True:
        state.take_proposal(cid, pid, "cancelled")
        return {"ok": True, "moved": False, "message": "Okay, nothing was moved."}
    try:
        same_amount = abs(float(amount) - float(prop["amount"])) < 0.005
    except (TypeError, ValueError):
        same_amount = False
    if not same_amount or dest != prop["dest"]:
        raise MoneyError("That doesn't match the offer I made, so nothing was moved. Ask me again and I'll make a new one.")
    cap, _ = available(conn, today)
    if float(prop["amount"]) > cap + 0.004:
        state.take_proposal(cid, pid, "cancelled")
        raise MoneyError("Your balance has changed and %s is no longer safe to move, so nothing was moved."
                         % _eur(prop["amount"]))
    if not state.take_proposal(cid, pid, "done"):
        raise MoneyError("This offer has expired or was already used. Ask again and I will make a new one.")
    now = datetime.datetime.now().strftime("%H:%M:%S")
    state.add_move(cid, str(today), "%s %s" % (today, now), prop["amount"], prop["dest"], pid)
    return {"ok": True, "moved": True, "amount": prop["amount"], "to": prop["to"], "dest": prop["dest"],
            "message": "Done: %s moved to your %s. It stays in S-mobiili, and you can see it under Your things."
                       % (_eur(prop["amount"]), prop["to"])}
