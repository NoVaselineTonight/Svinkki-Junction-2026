"""A ranked pool of things one customer's own data shows right now.

The coach is handed this pool before every answer (app/coach.py, customer_snapshot) and can ask for it with the
get_findings tool. Each finding is one ready sentence with the figures it holds, a stable id, and a score. The
pool is what keeps answers personal and varied: findings already told in a conversation sink to the bottom.

Every sentence comes from a calculation in app/trends.py, app/cashflow.py or app/receipts.py; nothing is
worded or worked out here except the ranking.
"""
import math
import re

_MONEY = re.compile(r"€\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?")

# (source, weights for its sentences in order). Higher = said earlier. Chosen so that what threatens the
# customer's balance comes first, then what changed, then habits and receipts.
_WEIGHTS = {
    "season": (5.5, 3.6, 3.3),
    "long_view": (5.0, 4.4, 3.4, 3.0, 2.8),
    "low_points": (4.8, 4.0, 3.1, 2.9),
    "cushion": (2.6, 2.3, 2.0),            # the same view for someone who never goes below zero
    "unusual_month": (3.0, 2.4),
    "receipts": (2.7, 2.3, 2.1),
    "cut_idea": (2.6, 2.2),
    "basket": (2.5, 2.0, 1.8),
    "pay": (2.2, 2.0),
}
SAID_FACTOR = 0.3


def figures(text):
    """The euro amounts written in a sentence, as floats."""
    out = []
    for m in _MONEY.finditer(str(text or "")):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if m.group(2):
            v += float("0." + m.group(2))
        out.append(round(v, 2))
    return out


def _safe(fn, *args, **kw):
    try:
        r = fn(*args, **kw)
    except Exception:
        return {}
    return r if isinstance(r, dict) else {}


def _sentences(res):
    return [str(h).strip() for h in (res.get("highlights") or []) if isinstance(h, str) and h.strip()]


def pool(conn, today, habit_seed=None, goal=None):
    """Every finding, unranked: a list of {id, kind, text, figures, base, simulated}."""
    out = []

    def add(kind, texts, simulated=False):
        w = _WEIGHTS[kind]
        for i, t in enumerate(texts[:len(w)]):
            out.append({"id": "%s:%d" % (kind, i + 1), "kind": kind, "text": t, "figures": figures(t),
                        "base": w[i], "simulated": simulated})

    urgent = False
    try:
        from app import trends
    except ImportError:
        trends = None
    try:
        from app import cashflow
    except ImportError:
        cashflow = None
    try:
        from app import receipts
    except ImportError:
        receipts = None

    if cashflow is not None:
        lp = _safe(cashflow.low_points, conn, today)
        try:
            below = float(lp.get("days_below_zero_365") or 0)
        except (TypeError, ValueError):
            below = 0.0
        try:
            urgent = lp.get("buffer_months") is not None and float(lp["buffer_months"]) < 1.0
        except (TypeError, ValueError):
            urgent = False
        add("low_points" if below > 0 else "cushion", _sentences(lp))
        add("pay", _sentences(_safe(cashflow.income_profile, conn, today)))
    if trends is not None:
        so = _safe(trends.season_outlook, conn, today)
        if so.get("relevant", True):
            add("season", _sentences(so))
        add("long_view", _sentences(_safe(trends.money_story, conn, today)))
        add("unusual_month", _sentences(_safe(trends.explain_month, conn, today)))
    if receipts is not None:
        for kind, name, period in (("receipts", "receipt_trends", "last_12_months"),
                                   ("basket", "basket_profile", "last_12_months")):
            fn = getattr(receipts, name, None)
            if fn is not None:
                add(kind, _sentences(_safe(fn, conn, today, period=period, habit_seed=habit_seed)),
                    simulated=(kind == "receipts"))
        fn = getattr(receipts, "cut_ideas", None)
        if fn is not None:
            ideas = [i for i in (_safe(fn, conn, today, habit_seed=habit_seed).get("ideas") or []) if isinstance(i, dict)]
            texts = []
            for i in ideas:
                t = " ".join(str(x).strip() for x in (i.get("title"), i.get("detail")) if x).strip()
                if t:
                    texts.append(t if t.endswith((".", "!", "?")) else t + ".")
            add("cut_idea", texts, simulated=True)
    for f in out:
        boost = min(1.0, math.log10(max(f["figures"] or [0]) + 1.0) / 5.0)
        f["score"] = round((f["base"] + boost) * (1.3 if urgent and f["kind"] in ("low_points", "season") else 1.0), 2)
    return out


def rank(items, exclude=()):
    said = set(exclude or ())
    out = []
    for f in items:
        g = dict(f)
        g["said"] = g["id"] in said
        if g["said"]:
            g["score"] = round(g["score"] * SAID_FACTOR, 2)
        out.append(g)
    out.sort(key=lambda g: (-g["score"], g["id"]))
    return out


def findings(conn, today, limit=6, exclude=(), habit_seed=None, goal=None):
    """The `limit` most important findings, those not yet told first."""
    ranked = rank(pool(conn, today, habit_seed=habit_seed, goal=goal), exclude)[:max(1, int(limit))]
    items = [{"id": f["id"], "kind": f["kind"], "text": f["text"], "figures": f["figures"], "score": f["score"],
              "said": f["said"], "simulated": f["simulated"]} for f in ranked]
    fresh = [f["text"] for f in items if not f["said"]]
    res = {"findings": items, "highlights": fresh[:4], "text": " ".join(fresh[:2]),
           "explain": "Worked out from your own transactions and receipts; the most important first."}
    if any(f["simulated"] for f in items):
        res["note"] = "Findings from grocery receipts use receipt lines simulated for the demo."
    if not items:
        res["too_little_data"] = True
    return res
