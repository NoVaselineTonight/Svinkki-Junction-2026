"""Tool registry the coach can call. Read-only; no tool takes a customer id.

call(name, args, ctx) never raises: bad input returns {"error": "..."}.
ctx needs: conn, today, profile, consent, settings, bench_lookup.
"""
import re

LABELS = [
    "Housing", "Utilities", "Groceries", "Restaurant", "Fast food", "Bar", "Taxi",
    "Public transport", "Fuel", "Parking", "Pharmacy", "Doctor", "Dentist", "Other health",
    "Home improvement", "Electronics", "Furniture", "Clothing", "Hobbies", "Books", "Shopping",
    "Events", "Cinema", "Gym & sports", "Entertainment", "Flights", "Hotels", "Travel agency",
    "Car rental", "Travel", "Savings & investments", "Salary", "Other income", "Transfer out",
    "Other",
]
LABEL_CHOICES = LABELS + ["Dining out", "Night out"]
BASKETS = ["regular", "unexpected", "everyday", "savings", "income", "transfer"]
PERIOD_NAMES = ["this_week", "last_week", "this_month", "last_month", "last_3_months",
                "last_12_months", "ytd"]
TYPES = ["purchase", "salary", "other_income", "housing_payment", "utilities_payment",
         "investment_deposit", "investment_withdrawal", "salary_sweep"]
DINING = ["Restaurant", "Fast food"]

_PERIOD_DESC = ("Period: one of " + ", ".join(PERIOD_NAMES) + ", or a month as YYYY-MM.")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

try:
    from app import averages as _averages
    AVERAGE_TOPICS = list(_averages.TOPIC_ORDER)
except Exception:  # pragma: no cover
    _averages = None
    AVERAGE_TOPICS = ["overview"]

TOOLS = [
    {
        "name": "get_spend",
        "description": "Total spending for a period, optionally for one label (e.g. Taxi, Groceries, "
                       "Restaurant), 'Dining out' (Restaurant plus Fast food), 'Night out', or a basket. "
                       "Returns total, purchase count and a breakdown by label. When the customer has allowed "
                       "comparisons, a `peer` object holds a ready-made sentence comparing the figure with people "
                       "of a similar age. For richer comparisons (typical amounts, visits, share of people who use "
                       "something), use get_averages.",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "description": _PERIOD_DESC},
            "label": {"type": "string", "enum": LABEL_CHOICES, "description": "Spending label."},
            "basket": {"type": "string", "enum": ["regular", "unexpected", "everyday"]},
        }},
    },
    {
        "name": "get_overview",
        "description": "Where the money went in one month: income, spending in the three baskets, "
                       "surplus, top labels and comparison with the customer's own average.",
        "parameters": {"type": "object", "properties": {
            "month": {"type": "string", "description": "Month as YYYY-MM. Omit for the last full month."},
        }},
    },
    {
        "name": "get_baskets",
        "description": "Split of spending into the three baskets (regular essentials, unexpected "
                       "necessities, everyday spending) for a period, with the rules.",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "description": _PERIOD_DESC},
        }},
    },
    {
        "name": "get_safe_to_spend",
        "description": "How much the customer can safely spend per day and per week until the next "
                       "payday, after upcoming bills, a buffer for unexpected necessities and planned savings.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "simulate_what_if",
        "description": "What-if: how much would be saved by cutting spending in some labels or baskets "
                       "by a percentage. Targets: a label, 'Dining out', 'Night out' or a basket name.",
        "parameters": {"type": "object", "properties": {
            "changes": {"type": "array", "description": "List of cuts.", "items": {
                "type": "object", "properties": {
                    "target": {"type": "string", "description": "Label, 'Dining out', 'Night out', or basket."},
                    "pct": {"type": "number", "description": "Percent to cut, 0 to 100."},
                }, "required": ["target", "pct"]}},
            "months": {"type": "integer", "description": "Months to project, 1 to 60. Default 12."},
        }, "required": ["changes"]},
    },
    {
        "name": "get_spender_type",
        "description": "What kind of spender the customer is, with traits and spending shares.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_save_more",
        "description": "Concrete ideas for saving more, with estimated monthly savings from the customer's own data.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "check_mortgage",
        "description": "Home-loan readiness check against the published-style rule (not a credit decision). "
                       "Optionally test a specific home price and equity in euros.",
        "parameters": {"type": "object", "properties": {
            "price": {"type": "number", "description": "Home price in euros."},
            "equity": {"type": "number", "description": "Own equity in euros."},
        }},
    },
    {
        "name": "get_benchmarks",
        "description": "Compare the customer with anonymous peers of a similar age (groups of at least 20). "
                       "Needs the customer's peer-comparison consent.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_averages",
        "description": "What is typical for people like the customer (same age band, groups of at least 20) on "
                       "one topic: monthly amounts, visits per month, average ticket and the share of people "
                       "who use it, next to the customer's own figures. Returns ready-made `sentence` strings "
                       "and a `headline`; quote them, never invent an average. Needs the customer's "
                       "peer-comparison consent.",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string", "enum": AVERAGE_TOPICS,
                      "description": "Topic to compare. Omit for an overview."},
        }},
    },
    {
        "name": "get_invest_education",
        "description": "General education about investing (buffer, time horizon, diversification, costs). "
                       "Never specific products.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "plan_goal",
        "description": "Time to reach a savings goal, at a given or typical monthly saving.",
        "parameters": {"type": "object", "properties": {
            "target_amount": {"type": "number", "description": "Goal in euros."},
            "monthly": {"type": "number", "description": "Euros saved per month. Optional."},
            "starting_amount": {"type": "number", "description": "Euros already set aside for this goal. Default 0."},
        }, "required": ["target_amount"]},
    },
    {
        "name": "list_transactions",
        "description": "List the customer's transactions (at most 50) with optional filters.",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "description": _PERIOD_DESC},
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD."},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD."},
            "label": {"type": "string", "enum": LABEL_CHOICES},
            "basket": {"type": "string", "enum": BASKETS},
            "type": {"type": "string", "enum": TYPES},
            "limit": {"type": "integer", "description": "Rows, 1 to 50."},
        }},
    },
    {
        "name": "explore_my_data",
        "description": "Run one read-only SQL SELECT on the customer's own transactions. The only table is "
                       "tx with columns: d (date YYYY-MM-DD), ts (timestamp), amount (signed euros, spending "
                       "is negative), balance, type, category, mcc, merchant, label, basket, context "
                       "('night_out' or ''). At most 50 rows come back.",
        "parameters": {"type": "object", "properties": {
            "sql": {"type": "string", "description": "A single SELECT statement on table tx."},
        }, "required": ["sql"]},
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}


# ---------------------------------------------------------------- helpers
def _num(v, lo=None, hi=None, name="value"):
    if isinstance(v, bool):
        raise ValueError("%s must be a number" % name)
    if isinstance(v, str):
        s = v.strip().replace(" ", "").replace(",", ".")
        s = s.replace("€", "")
        v = float(s)
    v = float(v)
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("%s must be finite" % name)
    if lo is not None and v < lo:
        raise ValueError("%s is too small" % name)
    if hi is not None and v > hi:
        raise ValueError("%s is too large" % name)
    return v


def _period(v, default=None):
    if v in (None, ""):
        return default
    v = str(v).strip().lower().replace(" ", "_")
    if v in PERIOD_NAMES or _MONTH_RE.match(v):
        return v
    raise ValueError("unknown period")


def _label(v):
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    for lab in LABEL_CHOICES:
        if lab.lower() == s:
            return lab
    alias = {"dining": "Dining out", "eating out": "Dining out", "restaurants": "Restaurant",
             "taxis": "Taxi", "night_out": "Night out", "fast_food": "Fast food"}
    if s in alias:
        return alias[s]
    raise ValueError("unknown label")


def _basket(v, allowed=BASKETS):
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s in allowed:
        return s
    raise ValueError("unknown basket")


def _merge_spend(parts, period):
    """Combine several insights.spend results (used for Dining out)."""
    total = round(sum(p.get("total", 0) or 0 for p in parts), 2)
    count = sum(p.get("count", 0) or 0 for p in parts)
    by = []
    ev = []
    for p in parts:
        by.extend(p.get("by_label") or [])
        ev.extend(p.get("evidence") or [])
    return {"period": parts[0].get("period"), "total": total, "count": count, "by_label": by,
            "evidence": ev,
            "explain": "Dining out is Restaurant plus Fast food purchases in the period."}


def _expand_targets(changes):
    out = []
    for c in changes:
        if not isinstance(c, dict):
            raise ValueError("each change needs target and pct")
        t = str(c.get("target", "")).strip()
        pct = _num(c.get("pct"), 0, 100, "pct")
        tl = t.lower()
        if tl in ("dining out", "dining", "eating out"):
            for lab in DINING:
                out.append({"target": lab, "pct": pct})
        elif tl in ("night out", "night_out"):
            out.append({"target": "night_out", "pct": pct})
        elif tl in BASKETS:
            out.append({"target": tl, "pct": pct})
        else:
            out.append({"target": _label(t), "pct": pct})
    if not out:
        raise ValueError("no changes given")
    return out[:10]


# ---------------------------------------------------------------- tools
PEER_HINT = "Turn on comparisons in Settings to see how this compares with people like you."


def _peer_target(lab, basket):
    """What to look up in the peer statistics, or None when there is no matching statistic."""
    if lab and basket:
        return None
    if lab == "Dining out":
        return list(DINING)
    if lab == "Night out":
        return "night_out"
    if lab:
        return lab
    return basket


def _with_peer(res, lab, basket, ctx, ins):
    target = _peer_target(lab, basket)
    if target is None or not isinstance(res, dict):
        return res
    res = dict(res)
    if not (ctx.consent or {}).get("benchmarks"):
        res["peer_hint"] = PEER_HINT
        return res
    try:
        peer = ins.peer_compare(res.get("total") or 0.0, res.get("period") or {}, target,
                                getattr(ctx, "profile", None), getattr(ctx, "bench_lookup", None))
    except Exception:
        peer = None
    if peer:
        res["peer"] = peer
    return res


def _t_get_spend(args, ctx, ins):
    period = _period(args.get("period"), "last_month")
    lab = _label(args.get("label"))
    basket = _basket(args.get("basket"), ("regular", "unexpected", "everyday"))
    if lab == "Dining out":
        parts = [ins.spend(ctx.conn, ctx.today, period=period, label=l, basket=basket) for l in DINING]
        res = _merge_spend(parts, period)
    elif lab == "Night out":
        res = ins.spend(ctx.conn, ctx.today, period=period, context="night_out", basket=basket)
    else:
        res = ins.spend(ctx.conn, ctx.today, period=period, label=lab, basket=basket)
    return _with_peer(res, lab, basket, ctx, ins), "spend"


def _t_get_overview(args, ctx, ins):
    m = args.get("month")
    if m in (None, ""):
        return ins.overview(ctx.conn, ctx.today), "overview"
    m = str(m).strip()
    if not _MONTH_RE.match(m):
        raise ValueError("month must be YYYY-MM")
    return ins.overview(ctx.conn, ctx.today, month=m), "overview"


def _t_get_baskets(args, ctx, ins):
    return ins.baskets(ctx.conn, ctx.today, period=_period(args.get("period"), "last_month")), "baskets"


def _t_get_safe(args, ctx, ins):
    return ins.safe_to_spend(ctx.conn, ctx.today), "safe_to_spend"


def _t_what_if(args, ctx, ins):
    ch = args.get("changes")
    if not isinstance(ch, list):
        raise ValueError("changes must be a list")
    months = int(_num(args.get("months", 12), 1, 60, "months"))
    return ins.what_if(ctx.conn, ctx.today, _expand_targets(ch), months=months), "what_if"


def _t_spender(args, ctx, ins):
    return ins.spender_type(ctx.conn, ctx.today), "spender_type"


def _t_save_more(args, ctx, ins):
    return ins.save_more(ctx.conn, ctx.today), "save_more"


def _t_mortgage(args, ctx, ins):
    price = args.get("price")
    equity = args.get("equity")
    price = None if price in (None, "") else _num(price, 1, 50_000_000, "price")
    equity = None if equity in (None, "") else _num(equity, 0, 50_000_000, "equity")
    return ins.mortgage(ctx.conn, ctx.today, price=price, equity=equity), "mortgage"


def _t_benchmarks(args, ctx, ins):
    if not (ctx.consent or {}).get("benchmarks"):
        return {"error": "benchmark consent is off"}, "benchmarks"
    return ins.benchmarks(ctx.conn, ctx.today, ctx.profile, ctx.bench_lookup), "benchmarks"


def _t_averages(args, ctx, ins):
    if not (ctx.consent or {}).get("benchmarks"):
        return {"error": "benchmark consent is off"}, "averages"
    if _averages is None:
        raise RuntimeError("averages unavailable")
    topic = args.get("topic")
    if topic not in (None, ""):
        topic = str(topic).strip()
        if topic not in _averages.TOPICS:
            topic = _averages.topic_for(topic)
            if topic is None:
                raise ValueError("unknown topic")
    res = _averages.averages(ctx.conn, ctx.today, getattr(ctx, "profile", None), topic or None,
                             bench_many=getattr(ctx, "bench_many", None),
                             bench_meta=getattr(ctx, "bench_meta", None),
                             customer_metrics=getattr(ctx, "customer_metrics", None))
    return res, "averages"


def _t_invest(args, ctx, ins):
    return ins.invest_education(ctx.conn, ctx.today), "invest"


def _t_goal(args, ctx, ins):
    target = _num(args.get("target_amount"), 1, 50_000_000, "target_amount")
    monthly = args.get("monthly")
    monthly = None if monthly in (None, "") else _num(monthly, 1, 10_000_000, "monthly")
    if monthly is None:
        try:
            tgt = float((ctx.settings or {}).get("monthly_saving_target") or 0)
        except (TypeError, ValueError):
            tgt = 0
        monthly = tgt if tgt > 0 else None
    start = args.get("starting_amount")
    start = 0.0 if start in (None, "") else _num(start, 0, 50_000_000, "starting_amount")
    return ins.goal(ctx.conn, ctx.today, target, monthly, starting_amount=start), "goal"


def _t_list_tx(args, ctx, ins):
    frm = args.get("from_date")
    to = args.get("to_date")
    per = _period(args.get("period"))
    if per and not (frm or to):
        frm, to = ins.period(ctx.today, per)
    for d in (frm, to):
        if d not in (None, "") and not _DATE_RE.match(str(d)):
            raise ValueError("dates must be YYYY-MM-DD")
    lab = _label(args.get("label"))
    ctxf = None
    labels = [lab]
    if lab == "Night out":
        labels, ctxf = [None], "night_out"
    elif lab == "Dining out":
        labels = DINING
    basket = _basket(args.get("basket"))
    typ = args.get("type")
    if typ not in (None, "") and typ not in TYPES:
        raise ValueError("unknown type")
    limit = int(_num(args.get("limit", 50), 1, 50, "limit"))
    results = [ins.transactions(ctx.conn, ctx.today, frm=frm or None, to=to or None, label=l, basket=basket,
                                context=ctxf, type=typ or None, limit=limit) for l in labels]
    if len(results) == 1:
        res = results[0]
    else:
        rows = sorted([r for x in results for r in x.get("rows", [])],
                      key=lambda r: r.get("ts") or r.get("d") or "", reverse=True)[:limit]
        res = {"count": sum(x.get("count", 0) for x in results),
               "total": round(sum(x.get("total", 0) or 0 for x in results), 2),
               "rows": rows, "truncated": any(x.get("truncated") for x in results)}
    f = {"title": "Transactions", "from": frm, "to": to}
    if lab and lab not in ("Dining out", "Night out"):
        f["label"] = lab
    if ctxf:
        f["context"] = ctxf
    if basket:
        f["basket"] = basket
    if typ:
        f["type"] = typ
    res = dict(res)
    res.setdefault("evidence", [f] if lab != "Dining out" else
                   [dict(f, label=l, title="Dining out: " + l) for l in DINING])
    return res, "transactions"


def _t_explore(args, ctx, ins):
    from app import db
    sql = args.get("sql")
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 1000:
        raise ValueError("sql must be a short SELECT statement")
    try:
        res = db.safe_select(ctx.conn, sql)
    except ValueError:
        return {"error": "only a single read-only SELECT on table tx is allowed"}, "table"
    res = dict(res)
    res["explain"] = "Result of your read-only query on your own transactions."
    return res, "table"


_DISPATCH = {
    "get_spend": _t_get_spend, "get_overview": _t_get_overview, "get_baskets": _t_get_baskets,
    "get_safe_to_spend": _t_get_safe, "simulate_what_if": _t_what_if, "get_spender_type": _t_spender,
    "get_save_more": _t_save_more, "check_mortgage": _t_mortgage, "get_benchmarks": _t_benchmarks, "get_averages": _t_averages,
    "get_invest_education": _t_invest, "plan_goal": _t_goal, "list_transactions": _t_list_tx,
    "explore_my_data": _t_explore,
}


def call(name, args, ctx):
    """Run a tool. Never raises; returns {"error": ...} on any problem."""
    fn = _DISPATCH.get(name) if isinstance(name, str) else None
    if fn is None:
        return {"error": "unknown tool", "card": "error"}
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return {"error": "arguments must be an object", "card": "error"}
    # No tool accepts a customer id; drop any attempt silently.
    args = {k: v for k, v in args.items() if str(k).lower() not in ("cid", "customer_id", "customer")}
    try:
        try:
            from app import insights
        except ImportError:
            insights = None
        res, card = fn(args, ctx, insights)
    except (ValueError, TypeError, KeyError, OverflowError) as e:
        return {"error": "bad arguments: %s" % str(e)[:80], "card": "error"}
    except Exception:
        return {"error": "the tool failed", "card": "error"}
    if not isinstance(res, dict):
        return {"error": "the tool returned nothing", "card": "error"}
    res = dict(res)
    res["card"] = "error" if "error" in res else card
    return res
