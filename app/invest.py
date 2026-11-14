"""Investment guidance for the coach: a plan worked out from the customer's own figures, on principles and
figures taken from named Finnish sources (app/invest_knowledge.json), never from the model's memory.

Two tools for the model:
- get_investment_plan: what this customer could do, in order, with amounts worked out by code: stop paying for
  an overdraft, hold a buffer in the right place, invest regularly for the long term, put idle money to work.
- get_invest_facts: what the sources say on one topic (index funds, short-term funds, taxes, costs, crypto,
  leverage ...), each statement with its source.

The knowledge file holds every outside figure with its source and date. Nothing here is a promise of return,
and the plan is general guidance on the customer's own data, not a suitability assessment.
"""
import json
import math
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_CACHE = {}

DISCLAIMER = ("Worked out from your own account and from the named sources. It is general guidance, not a "
              "personal investment recommendation under the law: it does not know your other assets, loans or "
              "plans. Fund values go up and down and past returns are no guarantee.")


def knowledge():
    """The curated knowledge file: sources, facts, figures and products."""
    if "k" not in _CACHE:
        try:
            with open(os.path.join(_HERE, "invest_knowledge.json"), encoding="utf-8") as f:
                _CACHE["k"] = json.load(f)
        except (OSError, ValueError):
            _CACHE["k"] = {"sources": {}, "facts": [], "figures": {}, "products": []}
    return _CACHE["k"]


def _fig(name):
    """A figure's value from the knowledge file, or None."""
    f = (knowledge().get("figures") or {}).get(name)
    try:
        return float(f["value"]) if isinstance(f, dict) else None
    except (KeyError, TypeError, ValueError):
        return None


def savings_rate(amount):
    """The savings account's yearly interest (percent) for a balance of `amount`: the rate is tiered by balance."""
    f = (knowledge().get("figures") or {}).get("savings_account_tiers")
    if not isinstance(f, dict):
        return None
    rate = None
    try:
        for floor, pct in f.get("tiers") or []:
            if float(amount) >= float(floor):
                rate = float(pct)
        return rate if rate is not None else float(f["value"])
    except (KeyError, TypeError, ValueError):
        return None


def _fig_info(name):
    f = (knowledge().get("figures") or {}).get(name)
    return dict(f) if isinstance(f, dict) else None


def _source(sid):
    s = (knowledge().get("sources") or {}).get(sid) or {}
    return {"id": sid, "publisher": s.get("publisher"), "title": s.get("title"), "url": s.get("url")}


def _facts(topics, limit=6):
    """Statements on any of the topics, in file order, each with the name of its source."""
    want = set(topics)
    out = []
    for f in knowledge().get("facts") or []:
        if want & set(f.get("topics") or []):
            src = _source(f.get("source"))
            out.append({"id": f.get("id"), "text": f.get("text"), "says": src.get("publisher"),
                        "source": f.get("source")})
            if len(out) >= limit:
                break
    return out


def _products(kinds=None):
    out = []
    for p in knowledge().get("products") or []:
        if kinds and p.get("kind") not in kinds:
            continue
        out.append({k: v for k, v in p.items() if v is not None})
    return out


def _eur(x):
    return "€{:,.0f}".format(round(float(x)))


def _pct(x):
    return ("%.2f" % float(x)).rstrip("0").rstrip(".") + "%"


def _round10(x):
    return float(int(float(x) // 10) * 10)


def _future_value(monthly, years, annual_pct, start=0.0):
    r = annual_pct / 100.0 / 12.0
    v = float(start)
    for _ in range(int(round(years * 12))):
        v = v * (1 + r) + monthly
    return v


def _fv_split(to_long, amount, months_to_buffer, years, annual_pct):
    """Value and paid-in of what really goes into the fund: `to_long` a month until the buffer is full, then `amount`."""
    r = annual_pct / 100.0 / 12.0
    v = paid = 0.0
    for m in range(int(round(years * 12))):
        add = amount if (months_to_buffer is not None and m >= months_to_buffer) else to_long
        v = v * (1 + r) + add
        paid += add
    return v, paid


def _horizon_years(age_band):
    a = str(age_band or "")
    m = re.match(r"(\d+)", a)
    age = int(m.group(1)) if m else 35
    if age < 35:
        return 30
    if age < 45:
        return 25
    if age < 55:
        return 15
    if age < 65:
        return 10
    return 7


def situation(conn, today):
    """The customer's figures the plan is built on (all from their own transactions)."""
    from app import insights as ins
    t = ins._d(today)
    bal, essentials, _ = ins._buffer_info(conn, t)
    out = {"balance": round(float(bal), 2), "regular_costs_monthly": round(float(essentials), 2)}
    try:
        from app import trends
        story = trends.money_story(conn, today, months=12)
        pm = story.get("per_month") or {}
        if pm.get("income") is not None and pm.get("spent") is not None and not story.get("too_little_data"):
            out["income_monthly"] = round(float(pm["income"]), 2)
            out["spending_monthly"] = round(float(pm["spent"]), 2)
            inv_m = round(float(story.get("saved_in_window") or 0.0) / 12.0, 2)
            out["already_investing_monthly"] = inv_m
            out["left_monthly"] = round(float(pm["income"]) - float(pm["spent"]) - inv_m, 2)
            out["months_in_average"] = 12
    except Exception:
        pass
    if "left_monthly" not in out:
        avg = ins._avg_flows(conn, ins._month_list(conn, t, 6))
        out.update({"income_monthly": round(float(avg["income"]), 2), "spending_monthly": round(float(avg["spent"]), 2),
                    "left_monthly": round(float(avg["income"]) - float(avg["spent"]), 2), "months_in_average": 6})
    try:
        from app import cashflow
        lp = cashflow.low_points(conn, today)
        out["days_below_zero_last_year"] = int(lp.get("days_below_zero_365") or 0)
        low = (lp.get("lowest") or {}).get("amount")
        if low is not None and float(low) < 0:
            out["lowest_balance"] = round(float(low), 2)
    except Exception:
        out["days_below_zero_last_year"] = 0
    try:
        out["invested_so_far"] = round(max(0.0, float(ins._net_deposits(conn, t))), 2)
    except Exception:
        out["invested_so_far"] = 0.0
    try:
        ideas = [i for i in (ins.save_more(conn, today).get("ideas") or []) if i.get("saved_monthly")]
        if ideas:
            out["best_saving_idea"] = {"title": str(ideas[0].get("title")), "monthly": round(float(ideas[0]["saved_monthly"]), 2)}
    except Exception:
        pass
    spend = out.get("spending_monthly") or 0.0
    out["buffer_months"] = round(max(out["balance"], 0.0) / spend, 1) if spend > 0 else None
    return out


def plan(conn, today, monthly=None, age_band=None, holdings=None):
    """An ordered investment plan for this customer. `monthly` is what they say they want to invest, if given."""
    s = situation(conn, today)
    od_rate, cc_rate = _fig("overdraft_rate_pct"), _fig("consumer_credit_rate_pct")
    short_ret, short_fee = _fig("short_fund_return_1y_pct"), _fig("short_fund_charges_pct")
    eq_ret, term_rate = _fig("equity_planning_return_pct"), _fig("term_deposit_rate_pct")
    b_lo, b_hi = _fig("buffer_months_low") or 1.0, _fig("buffer_months_high") or 3.0
    spend = s.get("spending_monthly") or 0.0
    left = s.get("left_monthly") or 0.0
    bal = max(s["balance"], 0.0)
    held = sum(float(h.get("amount") or 0) for h in (holdings or []) if isinstance(h, dict))
    target_lo, target_hi = b_lo * spend, b_hi * spend
    keep = max(target_lo, min(bal + held, target_hi))
    sav_rate = savings_rate(keep)
    steps, sources = [], []

    def use(*ids):
        for i in ids:
            if i and i not in sources:
                sources.append(i)

    # 1. an overdraft costs more than any sound investment earns
    days = s.get("days_below_zero_last_year") or 0
    if days >= 10:
        st = {"id": "overdraft_first", "title": "Stop paying for the overdraft",
              "what": "Your account was below zero on %d days in the last year%s." % (
                  days, (", down to %s below zero" % _eur(-s["lowest_balance"])) if s.get("lowest_balance") else "")}
        if od_rate is not None:
            cmp_ = (" A low-risk short-term interest fund returned %s over the last year." % _pct(short_ret)) if short_ret is not None else ""
            avg = (" (new consumer credit in Finland averaged %s)" % _pct(cc_rate)) if cc_rate is not None else ""
            st["why"] = ("Being below zero is borrowing, and credit is dear: S-Bank's card credit costs about %s a "
                         "year%s.%s Money that keeps you above zero saves that interest for sure, which no investment "
                         "can match without far more risk. So the first euros go to a cushion, not a fund."
                         % (_pct(od_rate), avg, cmp_))
            st["credit_rate_pct"] = od_rate
            use((_fig_info("overdraft_rate_pct") or {}).get("source"), (_fig_info("consumer_credit_rate_pct") or {}).get("source"))
        if s.get("lowest_balance"):
            st["cushion_needed"] = round(-s["lowest_balance"], 2)
        for f in _facts(["debt_first"], 1):
            st["source_says"] = f["text"]
            use(f["source"])
        steps.append(st)

    # 2. the buffer, and where to keep it
    if spend > 0:
        covered = bal + held >= target_lo
        st = {"id": "buffer", "title": "Buffer: %s to %s months of spending" % (("%g" % b_lo), ("%g" % b_hi)),
              "target_low": round(target_lo, 2), "target_high": round(target_hi, 2), "have_now": round(bal + held, 2),
              "covered": bool(covered)}
        st["what"] = ("Your spending is about %s a month, so a buffer of %s to %s. You have %s%s." % (
            _eur(spend), _eur(target_lo), _eur(target_hi), _eur(bal + held),
            ", which covers it" if covered else ", so about %s is missing to the lower end" % _eur(target_lo - bal - held)))
        if sav_rate is not None and short_ret is not None:
            diff = (short_ret - sav_rate) / 100.0 * keep
            better = diff > 0
            st["where"] = ("Where to keep it: on %s the S-Bank savings account pays %s a year (its rate rises only "
                           "from 5,000 euros). The S-Bank short-term interest fund returned %s over the last 12 "
                           "months%s, about %s a year %s on that sum. The fund has no deposit guarantee and its value "
                           "can dip a little; the money can be taken out at any time.%s" % (
                               _eur(keep), _pct(sav_rate), _pct(short_ret),
                               (" after charges of about %s" % _pct(short_fee)) if short_fee is not None else "",
                               _eur(abs(diff)), "more" if better else "less",
                               (" A fixed-term deposit paid %s on average but locks the money, so it suits a sum with "
                                "a known date, not a buffer." % _pct(term_rate)) if term_rate is not None else ""))
            st["savings_account_rate_pct"], st["short_fund_return_1y_pct"] = sav_rate, short_ret
            st["yearly_difference_on_buffer"] = round(diff, 2)
            st["rates_compared_on"] = round(keep, 2)
            st["better_place"] = ("S-Bank short-term interest fund" if better else "S-Bank savings account")
            st["recommendation"] = ("Keep the buffer in the %s, not on the current account." % st["better_place"])
            use((_fig_info("savings_account_tiers") or {}).get("source"), (_fig_info("short_fund_return_1y_pct") or {}).get("source"),
                (_fig_info("term_deposit_rate_pct") or {}).get("source"))
        for f in _facts(["savings_vs_fund"], 2):
            st.setdefault("source_says", [])
            st["source_says"].append(f["text"])
            use(f["source"])
        for f in _facts(["buffer"], 2):
            st.setdefault("source_says", [])
            st["source_says"].append(f["text"])
            use(f["source"])
        steps.append(st)
    else:
        covered = True

    # 3. regular long-term investing: how much, and split with the buffer while it is being built
    idea = s.get("best_saving_idea")
    basis = None
    if monthly is not None and float(monthly) > 0:
        amount, basis = float(monthly), "the amount you named"
    elif left >= 20:
        amount = _round10(left * (0.8 if covered else 0.6)) or 10.0
        basis = "about %d%% of the %s a usual month leaves you" % (80 if covered else 60, _eur(left))
    elif idea:
        amount = max(10.0, _round10(min(idea["monthly"], 100.0)))
        basis = "what \"%s\" would free (about %s a month): a usual month leaves you nothing today" % (
            idea["title"][0].lower() + idea["title"][1:], _eur(idea["monthly"]))
    else:
        amount, basis = 10.0, "a small start: a usual month leaves you nothing today"
    if covered:
        to_buffer, to_long = 0.0, amount
    elif left <= 0 and not (monthly is not None and float(monthly) > 0):
        to_buffer, to_long = amount, 0.0
    else:
        to_buffer = _round10(amount / 2.0) or amount
        to_long = amount - to_buffer
    years = _horizon_years(age_band)
    st = {"id": "invest_monthly", "title": "Invest every month for the long term", "monthly_total": amount,
          "basis": basis, "monthly_to_buffer": to_buffer, "monthly_to_long_term": to_long, "horizon_years": years}
    if not covered and to_buffer > 0:
        missing = max(target_lo - bal - held, 0.0)
        months = int(math.ceil(missing / to_buffer)) if to_buffer > 0 else None
        st["months_to_buffer"] = months
        if to_long <= 0:
            st["what"] = ("%s a month (%s), all of it into the buffer until it reaches %s (about %d months). Only "
                          "then does regular investing in an index fund start." % (_eur(amount), basis, _eur(target_lo), months or 0))
        else:
            st["what"] = ("%s a month in all (%s): %s into the buffer until it reaches %s (about %d months), and %s into "
                      "a low-cost global equity index fund from the start. When the buffer is full the whole %s goes "
                      "to the index fund." % (_eur(amount), basis, _eur(to_buffer), _eur(target_lo), months or 0,
                                              _eur(to_long), _eur(amount)))
    else:
        st["what"] = "%s a month (%s) into a low-cost global equity index fund." % (_eur(amount), basis)
    if eq_ret is not None and (covered or to_long > 0):
        long_amount = amount if covered else to_long
        mtb = None if covered else st.get("months_to_buffer")
        proj = []
        for y in sorted({10, 20, years}):
            val, paid = _fv_split(long_amount, amount, mtb, y, eq_ret)
            proj.append({"years": y, "paid_in": round(paid, 2), "value_at_end": round(val, 2)})
        st["projection"] = proj
        st["planning_return_pct"] = eq_ret
        last = proj[-1]
        if covered or mtb is None:
            counts = "%s a month" % _eur(long_amount)
        else:
            counts = "%s a month in the fund, rising to %s once the buffer is full" % (_eur(long_amount), _eur(amount))
        st["projection_counts"] = "The figure counts only what goes into the index fund, not the buffer."
        st["what"] += " " + st["projection_counts"]
        st["illustration"] = ("World equities have returned about %s a year after inflation over the long run. At that "
                              "pace %s for %d years would be about %s in the fund in today's money, of which %s paid in "
                              "(the buffer is not counted). An illustration, not a promise: single years and decades "
                              "differ widely." % (
                                  _pct(eq_ret), counts, last["years"], _eur(last["value_at_end"]),
                                  _eur(last["paid_in"])))
        st["first_amount_to_long_term"] = long_amount
        use((_fig_info("equity_planning_return_pct") or {}).get("source"))
    for f in _facts(["monthly_saving", "index_funds", "time_horizon"], 3):
        st.setdefault("source_says", [])
        st["source_says"].append(f["text"])
        use(f["source"])
    steps.append(st)

    # 4. money sitting idle above the buffer
    idle = bal + held - target_hi
    if spend > 0 and idle >= 1000:
        lump = float(int(idle // 100) * 100)
        idle_rate = savings_rate(bal)
        st = {"id": "idle_money", "title": "Put idle money to work", "idle_above_buffer": round(idle, 2), "amount": lump,
              "what": ("You hold about %s more than the upper end of the buffer. On a savings account that balance "
                       "earns %s, and nothing on the current account. Sort it by when you need it: money with a known "
                       "date within a year or two into a fixed-term deposit%s or the short-term interest fund%s; money "
                       "you will not need for five years or more into the global index fund, all at once or in equal "
                       "parts over some months." % (
                           _eur(lump), ("%s a year" % _pct(idle_rate)) if idle_rate is not None else "little",
                           (" (%s on average)" % _pct(term_rate)) if term_rate is not None else "",
                           (" (%s over the last year)" % _pct(short_ret)) if short_ret is not None else ""))}
        for f in _facts(["time_horizon", "lump_sum"], 2):
            st.setdefault("source_says", [])
            st["source_says"].append(f["text"])
            use(f["source"])
        steps.append(st)

    if s.get("invested_so_far"):
        steps.append({"id": "already_investing", "title": "What you already do",
                      "what": "You have put about %s into investments through this account so far; keep it regular."
                              % _eur(s["invested_so_far"])})

    order = [x["title"] for x in steps]
    highlights = [x["what"] for x in steps if x.get("what")][:4]
    res = {"situation": s, "steps": steps, "order": order, "highlights": highlights,
           "text": " ".join(highlights[:2]),
           "products": _products(), "sources": [_source(i) for i in sources if i],
           "as_of": knowledge().get("as_of"), "disclaimer": DISCLAIMER}
    return res


TOPICS = ("order", "debt_first", "buffer", "savings_vs_fund", "short_term_funds", "index_funds", "costs",
          "diversification", "time_horizon", "monthly_saving", "returns", "taxes", "equity_savings_account",
          "deposit_guarantee", "risk", "crypto", "leverage_derivatives", "lump_sum", "borrowing_to_invest")


def facts(topic):
    """What the sources say on one topic, with the figures and products that belong to it."""
    topic = str(topic or "").strip().lower()
    if topic not in TOPICS:
        raise ValueError("topic must be one of: " + ", ".join(TOPICS))
    fs = _facts([topic], 8)
    figs = {k: v for k, v in (knowledge().get("figures") or {}).items()
            if isinstance(v, dict) and topic in (v.get("topics") or [])}
    kinds = {"short_term_funds": ("short-term fixed income fund", "savings account"),
             "savings_vs_fund": ("short-term fixed income fund", "savings account"),
             "index_funds": ("equity index fund",), "costs": ("equity index fund",)}.get(topic)
    src = []
    for f in fs:
        if f["source"] and f["source"] not in src:
            src.append(f["source"])
    for v in figs.values():
        if v.get("source") and v["source"] not in src:
            src.append(v["source"])
    return {"topic": topic, "statements": fs, "figures": figs, "products": _products(kinds) if kinds else [],
            "sources": [_source(i) for i in src], "as_of": knowledge().get("as_of"),
            "highlights": [f["text"] for f in fs[:4]], "text": " ".join(f["text"] for f in fs[:2]),
            "disclaimer": DISCLAIMER}


TOOLS = [
    {
        "name": "get_investment_plan",
        "description": "What this person could do with their money, in order, worked out from their own figures on "
                       "principles from named Finnish sources (Pörssisäätiö, Finanssivalvonta, Suomen Pankki, "
                       "Verohallinto and others): stop paying for an overdraft, hold a buffer and where to keep it "
                       "(savings account against a short-term fixed income fund, with current rates), how much to "
                       "invest each month and how to split it, what it could grow to, and what to do with idle "
                       "money. Returns `steps` with amounts, `products` (the S-Bank funds that can be bought here and "
                       "well-known examples for comparison), `sources` and a `disclaimer`. Use it for every question "
                       "about investing, where to put savings, funds, 'what should I invest in', 'how should I "
                       "invest', 'is a fund better than a savings account'. Recommend from it plainly, name the "
                       "source in a few words, and never invent a product, a rate or a return.",
        "parameters": {"type": "object", "properties": {
            "monthly": {"type": "number", "description": "Euros a month they say they want to invest, if they named an amount."}}},
    },
    {
        "name": "get_invest_facts",
        "description": "What the named Finnish and EU sources say on one investing topic, each statement with its "
                       "source, plus current figures: " + ", ".join(TOPICS) + ". Use it to explain a concept or a "
                       "risk with facts: what an index fund or a short-term fixed income fund is, costs, taxes, the "
                       "equity savings account, the deposit guarantee, crypto, leverage and derivatives (who loses "
                       "and how much can be lost), investing with borrowed money. Quote the statements; name the "
                       "source in a few words.",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string", "enum": list(TOPICS)}}, "required": ["topic"]},
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}


def call(name, args, ctx):
    """Run one of the tools. Never raises; returns {"error": ...} on any problem."""
    args = args if isinstance(args, dict) else {}
    try:
        if name == "get_investment_plan":
            m = args.get("monthly")
            m = None if m in (None, "") else float(m)
            if m is not None and not 0 < m <= 1_000_000:
                raise ValueError("monthly out of range")
            res = plan(ctx.conn, ctx.today, monthly=m,
                       age_band=(getattr(ctx, "profile", None) or {}).get("age_band"),
                       holdings=getattr(ctx, "holdings", None))
            card = "invest_plan"
        elif name == "get_invest_facts":
            res = facts(args.get("topic"))
            card = "invest_facts"
        else:
            return {"error": "unknown tool", "card": "error"}
    except (ValueError, TypeError, KeyError) as e:
        return {"error": "bad arguments: %s" % str(e)[:160], "card": "error"}
    except Exception:
        return {"error": "the tool failed", "card": "error"}
    res = dict(res)
    res["card"] = card
    return res
