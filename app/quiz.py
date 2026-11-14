"""The daily money quiz: a round of questions picked for one customer.

Two kinds of question in one round:
- About you: guesses and choices about the customer's own money (this week's spending on something, last
  month's biggest area, the busiest weekday, grocery trips, the balance against a year ago, receipts ...).
  Every answer is worked out by code from their transactions.
- Money skills: Finnish personal-finance facts (deposit guarantee, capital tax, fund costs, compounding, the
  buffer, credit against investing ...), each from a named source in app/invest_knowledge.json, with a line
  that ties the fact to the customer's own figures.

With the AI model on (key and consent), Claude picks the questions that matter most for this customer from the
pool, orders them, rewrites them in a friendly personal voice and writes one personal line to show after each
answer. The app checks what comes back: only questions from the pool, no figure in a question that the
original did not have, no answer given away, and no figure in the after-answer line that the question's own
data does not hold. Anything that fails a check falls back to the code's wording. Without the model the code
picks a varied round itself. The right answers are never chosen by the model.
"""
import hashlib
import json
import math
import random
import re
import time
from datetime import date, timedelta

ROUND_SIZE = 6
MIN_ABOUT_YOU = 3
MIN_SKILLS = 2
RECENT_KEEP = 40            # question ids remembered so a new round brings new ones
AI_TIMEOUT = 40
AI_SECONDS = 45
_FIXED_LABELS = {"Housing", "Utilities", "Savings & investments", "Salary", "Other income", "Transfer out"}
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_TREAT_GROUPS = ("Snacks and sweets", "Beer and cider", "Ready meals", "Soft drinks", "Energy drinks", "Coffee")


# ---------------------------------------------------------------------------------------------- helpers
def _eur(x):
    x = float(x)
    if abs(x) < 20 and abs(x - round(x)) > 0.004:
        return "€{:,.2f}".format(x)
    return "€{:,.0f}".format(round(x))


def _eur_x(x):
    return "€{:,.2f}".format(float(x))


def _pct(x):
    return "%d%%" % int(round(float(x)))


def _nice_max(x, unit="eur"):
    x = max(float(x), 1.0)
    if unit == "count":
        return float(max(10, int(math.ceil(x / 5.0) * 5))), 1.0
    step = 1 if x <= 50 else 5 if x <= 300 else 10 if x <= 1000 else 50 if x <= 5000 else 100
    return float(int(math.ceil(x / step) * step)), float(step)


def _rng(*parts):
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return random.Random(int(h[:12], 16))


def _src(sid):
    try:
        from app import invest
        s = invest._source(sid)
        return {"publisher": s.get("publisher"), "title": s.get("title"), "url": s.get("url")} if s.get("url") else None
    except Exception:
        return None


def _fig(name):
    try:
        from app import invest
        return invest._fig(name)
    except Exception:
        return None


def _safe(fn, *a, **kw):
    try:
        r = fn(*a, **kw)
    except Exception:
        return None
    return r


def _choice(qid, topic, question, options, correct, explain, facts=None, about="you", weight=1.0, source=None,
            evidence=None, label=None, rng=None):
    """A multiple-choice question. Options are shuffled (deterministically) unless they are ordered ranges."""
    opts = list(options)
    right = opts[correct]
    if rng is not None and topic not in ("range",):
        rng.shuffle(opts)
    return {"id": qid, "about": about, "topic": topic, "kind": "choice", "question": question, "options": opts,
            "answer": opts.index(right), "explain": explain, "facts": facts or {}, "weight": weight,
            "source": source, "evidence": evidence or [], "label": label}


def _guess(qid, topic, question, answer, explain, unit="eur", facts=None, weight=1.0, evidence=None, label=None,
           hint=None):
    mx, step = _nice_max(max(float(answer) * 2.2, float(hint or 0) * 2.2, 40 if unit == "eur" else 10), unit)
    return {"id": qid, "about": "you", "topic": topic, "kind": "guess", "question": question,
            "answer": round(float(answer), 2), "unit": unit, "min": 0.0, "max": mx, "step": step,
            "explain": explain, "facts": facts or {}, "weight": weight, "source": None, "evidence": evidence or [],
            "label": label}


# ---------------------------------------------------------------------------------------------- about you
def _seed_week(conn, today):
    from app import insights as ins
    q = ins.quiz(conn, today)
    label = q["label_or_context"]
    frm, to = q["period"]["from"], q["period"]["to"]
    actual = ins._quiz_actual(conn, label, frm, to)
    usual = ins._weekly_avg(conn, label, ins._d(today))
    when = "this week" if to >= today else "last week"
    phrase = ins._QUIZ_PHRASE.get(label, ins.label_words(label))
    explain = "You spent %s on %s %s%s." % (
        _eur_x(actual), phrase, when, (", against a usual week of about %s" % _eur(usual)) if usual >= 1 else "")
    g = _guess("week:" + label, "spending", "How much do you think you spent on %s %s?" % (phrase, when), actual,
               explain, facts={"actual": round(actual, 2), "usual_week": round(usual, 2)},
               evidence=ins._quiz_evidence(label, frm, to, today), label=label, hint=usual, weight=1.3)
    g["min"], g["max"], g["step"] = float(q["min"]), float(q["max"]), float(q["step"])
    return g


def _last_month_labels(conn, today):
    from app import insights as ins
    frm, to = ins.period(today, "last_month")
    rows = [x for x in ins._by_display(conn, frm, to) if x["label"] not in _FIXED_LABELS and x["total"] > 0]
    return rows, ins.human_month(frm[:7], today), frm, to


def _seed_top_area(conn, today, rng):
    from app import insights as ins
    rows, month, frm, to = _last_month_labels(conn, today)
    if len(rows) < 4:
        return None
    top = rows[:4]
    explain = "%s came first: %s in %s, then %s at %s." % (
        ins.label_words(top[0]["label"]).capitalize(), _eur_x(top[0]["total"]), month,
        ins.label_words(top[1]["label"]), _eur_x(top[1]["total"]))
    return _choice("top_area", "spending", "Leaving out housing and bills, where did most of your money go in %s?" % month,
                   [ins.label_words(x["label"]).capitalize() for x in top], 0, explain,
                   facts={"first": top[0]["total"], "second": top[1]["total"]}, rng=rng,
                   evidence=[ins._disp_evidence(top[0]["label"], frm, to)])


def _seed_month_label(conn, today):
    from app import insights as ins
    rows, month, frm, to = _last_month_labels(conn, today)
    if not rows:
        return None
    pick = rows[1] if len(rows) > 1 and rows[1]["total"] >= 20 else rows[0]
    s = ins.spend(conn, today, period="last_month", label=pick["label"])
    total, count = float(s.get("total") or 0), int(s.get("count") or 0)
    if total <= 0:
        return None
    words = ins.label_words(pick["label"])
    explain = "You spent %s on %s in %s (%d payment%s)." % (_eur_x(total), words, month, count, "" if count == 1 else "s")
    return _guess("month:" + pick["label"], "spending", "How much did you spend on %s in %s?" % (words, month), total,
                  explain, facts={"total": total, "count": count}, evidence=s.get("evidence"), label=pick["label"])


def _seed_weekday(conn, today, rng):
    from app import insights as ins
    t = ins._d(today)
    frm = (t - timedelta(days=84)).isoformat()
    rows = conn.execute("SELECT d, -amount FROM tx WHERE basket='everyday' AND amount<0 AND d>? AND d<=?",
                        (frm, today)).fetchall()
    if len(rows) < 15:
        return None
    by = [0.0] * 7
    for d, a in rows:
        by[date.fromisoformat(d[:10]).weekday()] += float(a)
    total = sum(by)
    best = max(range(7), key=lambda i: by[i])
    if total <= 0 or by[best] / total < 0.18:
        return None
    # one big purchase is not a habit: the day must lead clearly, over several purchases, none of them most of it
    second = max(by[i] for i in range(7) if i != best)
    on_best = [float(a) for d, a in rows if date.fromisoformat(d[:10]).weekday() == best]
    if by[best] < second * 1.2 or max(on_best) > 0.5 * by[best] or len(on_best) < 4:
        return None
    others = [i for i in range(7) if i != best]
    rng.shuffle(others)
    opts = [_WEEKDAYS[best]] + [_WEEKDAYS[i] for i in others[:3]]
    explain = "%s: %s of your everyday spending over the last 12 weeks went on %ss (%s)." % (
        _WEEKDAYS[best], _pct(100 * by[best] / total), _WEEKDAYS[best], _eur(by[best]))
    return _choice("weekday", "habits", "On which day of the week do you usually spend the most on everyday things?",
                   opts, 0, explain, facts={"share": round(100 * by[best] / total, 1), "amount": round(by[best], 2)},
                   rng=rng)


def _seed_trend(conn, today):
    from app import trends
    st = trends.money_story(conn, today)
    pm = st.get("per_month") or {}
    if st.get("too_little_data") or not pm.get("spent_before"):
        return None
    now, before = float(pm["spent"]), float(pm["spent_before"])
    ch = (now - before) / before * 100
    correct = 0 if ch > 10 else 2 if ch < -10 else 1
    opts = ["More, by over a tenth", "About the same (within a tenth)", "Less, by over a tenth"]
    explain = "About %s a month over the last 12 months, against %s the 12 months before." % (_eur(now), _eur(before))
    q = _choice("trend", "range", "Compared with the year before, did you spend more or less a month over the last 12 months?",
                opts, correct, explain, facts={"now": round(now, 2), "before": round(before, 2)})
    q["topic"] = "trends"
    return q


def _seed_balance(conn, today):
    from app import trends
    st = trends.money_story(conn, today)
    b = st.get("balance") or {}
    if st.get("too_little_data") or b.get("year_ago") is None or b.get("now") is None:
        return None
    now, ago = float(b["now"]), float(b["year_ago"])
    diff = now - ago
    correct = 0 if diff > max(200, abs(ago) * 0.1) else 2 if diff < -max(200, abs(ago) * 0.1) else 1
    explain = "Your balance was %s a year ago and is %s now." % (_eur(ago), _eur(now))
    q = _choice("balance_year", "range", "Is your account balance higher or lower than a year ago?",
                ["Higher", "About the same", "Lower"], correct, explain, facts={"now": round(now, 2), "ago": round(ago, 2)})
    q["topic"] = "trends"
    return q


def _seed_safe_day(conn, today):
    from app import insights as ins
    s = ins.safe_to_spend(conn, today)
    per_day, days = float(s.get("per_day") or 0), int(s.get("days_left") or 0)
    if per_day <= 0 or days <= 0:
        return None
    pay = ins._d(str(s["next_payday"]))
    explain = "About %s a day: %s is safe to spend over the %d days until payday on %d %s, after your bills." % (
        _eur(per_day), _eur(s.get("safe_total") or 0), days, pay.day, pay.strftime("%B"))
    return _guess("safe_day", "planning", "How much do you think you can safely spend per day until your next payday?",
                  per_day, explain, facts={"per_day": round(per_day, 2), "safe_total": s.get("safe_total"), "days": days},
                  evidence=s.get("evidence"))


def _seed_essentials(conn, today):
    from app import insights as ins
    ov = ins.overview(conn, today)
    b, spent = ov.get("baskets") or {}, float(ov.get("spent") or 0)
    if spent <= 0:
        return None
    share = 100 * float(b.get("regular") or 0) / spent
    bands = [(0, 40, "Under 40%"), (40, 60, "40% to 60%"), (60, 80, "60% to 80%"), (80, 101, "Over 80%")]
    correct = next(i for i, (lo, hi, _) in enumerate(bands) if lo <= share < hi)
    month = ins.human_month(ov["month"], today)
    explain = "%s: %s of %s spent went on regular essentials such as housing, bills and groceries." % (
        _pct(share), _eur(b.get("regular") or 0), _eur(spent))
    q = _choice("essentials", "range", "In %s, what share of your spending went on regular essentials (housing, bills, groceries)?" % month,
                [x[2] for x in bands], correct, explain,
                facts={"share": round(share, 1), "regular": b.get("regular"), "spent": spent})
    q["topic"] = "baskets"
    return q


def _seed_trips(conn, today):
    from app import insights as ins
    s = ins.spend(conn, today, period="last_month", label="Groceries")
    n = int(s.get("count") or 0)
    if n < 2:
        return None
    month = ins.human_month(s["period"]["from"][:7], today) if isinstance(s.get("period"), dict) and s["period"].get("from") else "last month"
    avg = float(s.get("total") or 0) / n
    explain = "%d trips in %s, about %s each, %s in all." % (n, month, _eur(avg), _eur_x(s.get("total") or 0))
    return _guess("grocery_trips", "habits", "How many grocery trips do you think you made in %s?" % month, n, explain,
                  unit="count", facts={"trips": n, "average": round(avg, 2), "total": s.get("total")},
                  evidence=s.get("evidence"))


def _seed_income(conn, today):
    from app import insights as ins
    ov = ins.overview(conn, today)
    inc = float(ov.get("income") or 0)
    if inc <= 0:
        return None
    month = ins.human_month(ov["month"], today)
    explain = "%s came in during %s, and you spent %s." % (_eur(inc), month, _eur(ov.get("spent") or 0))
    return _guess("income", "income", "How much money came into your account in %s?" % month, inc, explain,
                  facts={"income": inc, "spent": ov.get("spent")})


def _seed_top_product(conn, today, cid, rng):
    from app import receipts
    r = receipts.receipt_insights(conn, today, habit_seed=cid)
    tops = [p for p in (r.get("top_products") or []) if p.get("name") and p.get("times")]
    if len(tops) < 5 or tops[0]["times"] <= tops[3]["times"]:
        return None
    others = [p for p in tops[3:] if p["times"] < tops[0]["times"]]
    if len(others) < 3:
        return None
    rng.shuffle(others)
    opts = [tops[0]["name"]] + [p["name"] for p in others[:3]]
    explain = "%s: %d times in the last 3 months (from the simulated demo receipts)." % (tops[0]["name"], tops[0]["times"])
    return _choice("top_product", "receipts", "Which product do you buy most often at the grocery store? (demo receipts)",
                   opts, 0, explain, facts={"times": tops[0]["times"]}, rng=rng)


def _seed_treat(conn, today, cid, rng):
    from app import receipts
    r = receipts.receipt_trends(conn, today, habit_seed=cid)
    groups = [g for g in (r.get("groups") or []) if g.get("name") in _TREAT_GROUPS and float(g.get("monthly") or 0) >= 5]
    if not groups:
        return None
    g = groups[0] if len(groups) == 1 else rng.choice(groups[:3])
    name = str(g["name"]).lower()
    explain = "About %s a month on %s over the last 12 months, %s in all (simulated demo receipts)." % (
        _eur(g["monthly"]), name, _eur(g.get("total") or 0))
    return _guess("treat:" + g["name"], "receipts", "Roughly how much a month do you spend on %s? (demo receipts)" % name,
                  float(g["monthly"]), explain, facts={"monthly": g["monthly"], "total": g.get("total")})


def _seed_below_zero(conn, today):
    from app import cashflow
    lp = cashflow.low_points(conn, today)
    if lp.get("too_little_data"):
        return None
    n = int(lp.get("days_below_zero_365") or 0)
    bands = [(0, 1, "Never"), (1, 11, "1 to 10 days"), (11, 61, "11 to 60 days"), (61, 367, "More than 60 days")]
    correct = next(i for i, (lo, hi, _) in enumerate(bands) if lo <= n < hi)
    low = (lp.get("lowest") or {}).get("amount")
    if n:
        explain = "%d days in the last year%s." % (n, (", at worst %s below zero" % _eur(-float(low))) if low is not None and float(low) < 0 else "")
    else:
        explain = "Not once in the last year: your account stayed above zero."
    q = _choice("below_zero", "range", "On how many days in the last year was your account below zero?",
                [x[2] for x in bands], correct, explain, facts={"days": n, "lowest": low})
    q["topic"] = "cushion"
    q["weight"] = 1.4 if n else 0.8
    return q


def _seed_dear_month(conn, today, rng):
    from app import trends, insights as ins
    em = trends.explain_month(conn, today)
    if em.get("too_little_data") or not em.get("month"):
        return None
    m = str(em["month"])[:7]
    months = []
    t = ins._d(today)
    cur = date(t.year, t.month, 1)
    for k in range(1, 13):
        cur = (cur - timedelta(days=1)).replace(day=1)
        months.append(cur.strftime("%Y-%m"))
    others = [x for x in months if x != m]
    rng.shuffle(others)
    def name(ym):
        return date(int(ym[:4]), int(ym[5:7]), 1).strftime("%B %Y")
    opts = [name(m)] + [name(x) for x in others[:3]]
    explain = "%s: you spent %s, about %s more than a typical month that year (%s)." % (
        name(m), _eur(em.get("spent") or 0), _eur(em.get("difference") or 0), _eur(em.get("usual") or 0))
    return _choice("dear_month", "trends", "Which month in the last year was your most expensive compared with usual?",
                   opts, 0, explain, facts={"spent": em.get("spent"), "difference": em.get("difference"),
                                            "usual": em.get("usual")}, rng=rng)


# ---------------------------------------------------------------------------------------------- money skills
def _fv(monthly, years, pct):
    r = pct / 100.0 / 12.0
    v = 0.0
    for _ in range(int(years * 12)):
        v = v * (1 + r) + monthly
    return v


def _skills(ctx, rng):
    """The money-skill questions, each from a named source, with a personal line from the customer's figures."""
    bal, left, spend, below, invested = (ctx.get(k) for k in ("balance", "left", "spending", "below_zero", "invested"))
    out = []

    def add(qid, question, options, correct, explain, source, facts=None, weight=1.0, ordered=False):
        q = _choice("skill:" + qid, "skills", question, options, correct, explain, facts=facts, about="skills",
                    weight=weight, source=_src(source), rng=None if ordered else rng)
        out.append(q)

    cover = ""
    if bal is not None and bal > 0:
        cover = " Your %s balance is well within it." % _eur(bal) if bal < 100000 else ""
    add("deposit_guarantee", "Up to how much of your deposits is protected by the deposit guarantee, per bank?",
        ["€20,000", "€50,000", "€100,000", "Everything, with no limit"], 2,
        "€100,000 per depositor per bank, paid out within seven working days if the bank fails." + cover,
        "rvv_talletussuoja", facts={"limit": 100000, "balance": bal})
    add("funds_guarantee", "Is money in an investment fund covered by the deposit guarantee?",
        ["Yes, up to €100,000", "No, but the fund's assets are kept apart from the fund company's own money",
         "No, and the fund company may use it to pay its own debts"], 1,
        "Fund units are investments, not deposits, so the guarantee does not cover them, but a fund's assets are "
        "held by a separate custodian and cannot pay the fund company's debts.", "rvv_suojatut",
        facts={"limit": 100000})
    add("capital_tax", "What is the tax on capital income, such as fund gains, in Finland in 2026 (up to €30,000 a year)?",
        ["20%", "30%", "34%", "The same as your income tax"], 1,
        "30% up to €30,000 a year and 34% on the part above.", "vero_veroperusteet",
        facts={"rate": 30, "upper": 34, "limit": 30000}, weight=1.2 if invested else 1.0)
    add("fund_tax_when", "When do you pay tax on a fund's growth?",
        ["Every year, on the growth so far", "Only when you sell (redeem) fund units", "Never: funds are tax-free",
         "When you first buy"], 1,
        "Only when you redeem units; while the money stays in the fund, its growth is not taxed.", "vero_sijoitukset")
    add("ost", "How much money can you put into an equity savings account (osakesäästötili)?",
        ["€10,000", "€50,000", "€100,000", "There is no limit"], 2,
        "Up to €100,000. Trades and dividends inside it are not taxed; tax is paid on the return when you withdraw.",
        "vero_ost", facts={"limit": 100000}, weight=1.2 if invested else 0.9)
    add("costs", "Pörssisäätiö gives a rule of thumb for a fund's yearly costs. What is it?",
        ["Keep them under 1% a year", "About 3% a year is normal", "Costs don't matter over time",
         "Over 2% means better management"], 0,
        "Keep yearly costs under 1%: even small costs eat a large part of the return over the years, and index "
        "funds usually cost less than active ones.", "porssisaatio_kohteet", facts={"rule": 1})
    add("diversify", "What lowers investment risk without lowering the expected return?",
        ["Spreading money across many companies, sectors and regions", "Putting everything in the company you know best",
         "Selling whenever prices fall", "Keeping all savings in cash"], 0,
        "Diversification: Pörssisäätiö calls it the only way to lower risk without lowering return. A fund is a "
        "ready-made spread.", "porssisaatio_hajauttaminen")
    add("short_money", "Money you will need within about two years: where do Pörssisäätiö's guides put it?",
        ["An equity index fund", "A short-term interest fund or a bank deposit", "Single shares", "Crypto"], 1,
        "A short-term interest fund or a deposit: the sooner you need the money, the less of it should be in shares.",
        "porssisaatio_korko_opas")
    add("monthly_buy", "Why does investing the same amount every month help?",
        ["You buy more units when prices are low and fewer when they are high", "It guarantees a profit",
         "It avoids tax", "Funds charge less for it"], 0,
        "You spread your purchases over time, so you never have to pick the right moment.", "porssisaatio_hajauttaminen")
    add("small_sales", "Gains are tax-free in a year when your sales add up to at most how much?",
        ["€1,000", "€5,000", "€10,000", "There is no such limit"], 0,
        "€1,000: if everything you sell in a year comes to at most €1,000 in sale prices, the gains are tax-free.",
        "vero_luovutukset", facts={"limit": 1000})
    add("real_return", "Roughly what was world shares' long-run average yearly return after inflation, from 1900 to 2020?",
        ["1%", "5%", "12%", "20%"], 1,
        "About 5.2% a year after inflation (Credit Suisse yearbook, reported by Taloustaito). Single years differ "
        "widely.", "taloustaito_tuotto", facts={"real": 5.2}, ordered=True)
    add("cfd", "When EU regulators restricted leveraged CFD trading, what share of ordinary investors' accounts were losing money?",
        ["About 10% to 20%", "About 30% to 50%", "74% to 89%", "Almost none"], 2,
        "74% to 89% of retail accounts lost money, so the EU capped leverage, for crypto CFDs at 2 to 1.", "esma_cfd",
        facts={"low": 74, "high": 89, "cap": 2}, ordered=True)
    add("crypto_deriv_tax", "In Finland, can you deduct losses from crypto futures or CFDs in your taxes?",
        ["Yes, against any capital gains", "Yes, but only against crypto gains",
         "No: the gains are taxed but the losses can't be deducted"], 2,
        "No. Each trade is taxed on its own and losses are not deductible, so you can owe tax in a year you lost money.",
        "vero_kryptojohdannaiset", weight=0.9)

    # the buffer, with the customer's own figures
    if spend:
        lo, hi = spend, spend * 3
        mine = " For you that is about %s to %s; you have %s." % (_eur(lo), _eur(hi), _eur(max(bal or 0, 0))) if bal is not None else ""
        add("buffer", "How big a buffer for surprise costs do Finnish debt and household advisers usually suggest?",
            ["About a week of spending", "One to three months of expenses", "A full year's income",
             "None: a credit card is enough"], 1,
            "One to three months of expenses (Takuusäätiö: two to three months; one to two months' pay is the usual "
            "example)." + mine, "takuusaatio_vinkit",
            facts={"low": round(lo, 2), "high": round(hi, 2), "balance": bal, "months_low": 1, "months_high": 3},
            weight=1.5 if (bal or 0) < spend else 1.0)

    # credit against investing, with the current figures
    card, short = _fig("overdraft_rate_pct"), _fig("short_fund_return_1y_pct")
    if card and short:
        mine = (" Your account was below zero on %d days last year." % below) if below else ""
        add("credit_first", "You have card debt costing about %s a year and some money to spare. A low-risk fund "
            "returned about %s last year. What is the better first move?" % (_pct(card) if card % 1 < 0.05 else "%.1f%%" % card,
                                                                            "%.1f%%" % short),
            ["Pay off the card debt", "Invest in the fund", "Split the money evenly", "Leave it on the current account"], 0,
            "Pay off the card debt: it saves about %.1f%% for sure, far more than the fund's %.1f%%; Takuusäätiö says "
            "card debt should go before saving.%s" % (card, short, mine), "verkkouutiset_takuusaatio",
            facts={"card": card, "fund": short, "days": below}, weight=1.8 if below else 0.9)

    # compounding, on an amount that fits the customer
    monthly = 50.0
    if left and left > 40:
        monthly = float(max(20, min(500, int(left * 0.5 / 10) * 10)))
    fv = _fv(monthly, 20, 5.2)
    paid = monthly * 240
    opts = [_eur(paid), _eur(fv), _eur(fv * 1.9), _eur(paid * 0.7)]
    who = (" %s a month is about half of what a usual month leaves you." % _eur(monthly)) if monthly != 50 else ""
    add("compounding", "If you invested %s for 20 years and it grew 5.2%% a year after inflation, roughly what would it be worth?" % (
        "€%d a month" % monthly),
        opts, 1,
        "About %s, of which %s is what you put in: growth earns growth. 5.2%% is the long-run average after "
        "inflation for world shares, an illustration, not a promise.%s" % (_eur(fv), _eur(paid), who),
        "porssisaatio_miksi", facts={"monthly": monthly, "value": round(fv, 2), "paid": paid, "rate": 5.2, "years": 20},
        weight=1.3)

    # where a buffer earns more, on the customer's own buffer size
    rate_small = None
    try:
        from app import invest
        amount = float(max(1000, int(round((spend or 3000) / 100.0)) * 100))
        rate_small = invest.savings_rate(amount)
    except Exception:
        amount = None
    if rate_small is not None and short:
        diff = amount * (short - rate_small) / 100.0
        opts = [_eur(diff / 10), _eur(diff), _eur(diff * 3.3), _eur(diff * 10)]
        add("buffer_place", "S-Bank's savings account pays %.2f%% a year on %s. The S-Bank short-term interest fund "
            "returned about %.1f%% last year. On %s kept for a year, about how much more would the fund have earned?" % (
                rate_small, _eur(amount), short, _eur(amount)),
            opts, 1,
            "About %s more. The fund has no deposit guarantee and its value can dip a little, but for money you may "
            "need within a couple of years it has paid clearly more." % _eur(diff), "spankki_tuottotili",
            facts={"amount": amount, "rate": rate_small, "fund": short, "diff": round(diff, 2)}, weight=1.2)
    return out


# ---------------------------------------------------------------------------------------------- the pool
def pool(conn, today, cid=None, profile=None):
    """Every question available for this customer today, about-you and skills, with their answers."""
    rng = _rng("pool", cid, today)
    items = []
    for fn, args in ((_seed_week, (conn, today)), (_seed_top_area, (conn, today, rng)), (_seed_month_label, (conn, today)),
                     (_seed_weekday, (conn, today, rng)), (_seed_trend, (conn, today)), (_seed_balance, (conn, today)),
                     (_seed_safe_day, (conn, today)), (_seed_essentials, (conn, today)), (_seed_trips, (conn, today)),
                     (_seed_income, (conn, today)), (_seed_top_product, (conn, today, cid, rng)),
                     (_seed_treat, (conn, today, cid, rng)), (_seed_below_zero, (conn, today)),
                     (_seed_dear_month, (conn, today, rng))):
        q = _safe(fn, *args)
        if q:
            items.append(q)
    ctx = _context(conn, today)
    items += _safe(_skills, ctx, rng) or []
    return items, ctx


def _context(conn, today):
    out = {"balance": None, "left": None, "spending": None, "below_zero": 0, "invested": 0.0}
    try:
        from app import trends
        st = trends.money_story(conn, today)
        pm = st.get("per_month") or {}
        if pm.get("spent") is not None:
            out["spending"] = float(pm["spent"])
            out["left"] = float(pm.get("income") or 0) - float(pm["spent"])
        if (st.get("balance") or {}).get("now") is not None:
            out["balance"] = float(st["balance"]["now"])
    except Exception:
        pass
    try:
        from app import cashflow
        out["below_zero"] = int(cashflow.low_points(conn, today).get("days_below_zero_365") or 0)
    except Exception:
        pass
    try:
        from app import insights as ins
        out["invested"] = max(0.0, float(ins._net_deposits(conn, ins._d(today))))
        if out["balance"] is None:
            out["balance"] = float(ins._balance(conn))
    except Exception:
        pass
    return out


def pick(items, recent=(), seed=None, size=ROUND_SIZE):
    """A varied round from the pool without the model: about-you first, then skills, recent ones last."""
    rng = _rng("pick", seed)
    recent = set(recent or ())
    you = [q for q in items if q["about"] == "you"]
    skills = [q for q in items if q["about"] == "skills"]

    def order(lst):
        return sorted(lst, key=lambda q: (q["id"] in recent, -q["weight"] * (0.75 + rng.random() * 0.5)))

    n_skills = min(len(skills), max(MIN_SKILLS, size - len(you)))
    n_you = min(len(you), size - n_skills)
    ranked = order(you)
    chosen, topics = [], set()
    for q in ranked:                       # first pass: one question per topic
        if len(chosen) < n_you and q["topic"] not in topics:
            chosen.append(q)
            topics.add(q["topic"])
    for q in ranked:                       # then fill up
        if len(chosen) < n_you and q not in chosen:
            chosen.append(q)
    chosen += order(skills)[:size - len(chosen)]
    return chosen


# ---------------------------------------------------------------------------------------------- the model
SYSTEM = """You prepare a short money quiz inside a bank's app for one customer. You get a pool of questions with ids, and short facts about the customer. The app has already worked out every right answer; you never change answers or options.
Do this:
1. Pick 6 questions from the pool: at least 3 about the customer's own money (about = "you") and at least 2 money-skill questions (about = "skills"). Choose what would teach THIS customer the most or surprise them, using their facts: someone often below zero needs the credit and buffer questions; a saver gets tax, costs and fund questions; prefer variety of topics. Order them from easy to most interesting.
2. For each, rewrite the question in a warm, short, personal voice (second person, max 30 words). Keep its exact meaning and keep it a question. Do not add any number that is not already in the original question, and never hint at the answer.
3. For each, write "teach": ONE sentence (max 30 words) shown directly under the item's "explain" text, so never repeat what "explain" says and never repeat its figures. Give the thing to remember: for a money-skill question the rule of thumb in everyday words and what it means for THIS customer (use their facts: days below zero, balance, what a month leaves); for a question about their own money, what the answer changes for them or the one thing to watch next. Say what is going right when it is. Never tell them to cut or spend less on something, never judge a purchase, no "should". Use only figures that appear in that item's "facts", or none.
4. A "title" for the round, max 6 words, personal and light.
Reply with JSON only, no other text: {"title": "...", "items": [{"id": "...", "question": "...", "teach": "..."}, ...]}"""

SUMMARY = "Quiz prompt: pick 6 questions from a pool for this customer, rewrite them, add one personal line each; answers are computed by the app."


def _profile_lines(ctx, profile):
    lines = ["Age band: %s." % ((profile or {}).get("age_band") or "unknown")]
    if ctx.get("spending") is not None:
        lines.append("A usual month: about %s goes out; about %s %s." % (
            _eur(ctx["spending"]), _eur(abs(ctx.get("left") or 0)),
            "is left over" if (ctx.get("left") or 0) >= 0 else "more goes out than comes in"))
    if ctx.get("balance") is not None:
        lines.append("Balance now: %s." % _eur(ctx["balance"]))
    lines.append("Days below zero in the last year: %d." % (ctx.get("below_zero") or 0))
    if ctx.get("invested"):
        lines.append("Has put about %s into investments over time." % _eur(ctx["invested"]))
    return lines


def _pool_for_model(items):
    out = []
    for q in items:
        d = {"id": q["id"], "about": q["about"], "topic": q["topic"], "question": q["question"],
             "facts": q["facts"], "explain": q["explain"]}
        out.append(d)
    return out


def _numbers(text):
    return {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


def _answer_text(q):
    return q["options"][q["answer"]] if q["kind"] == "choice" else None


def check_item(q, question, teach):
    """(question, teach) after the app's checks: the original wording or None where the model's fails."""
    good_q = q["question"]
    question = " ".join(str(question or "").split())
    if 8 <= len(question) <= 260 and question.endswith("?") and _numbers(question) <= _numbers(q["question"]):
        ans = _answer_text(q)
        leaks = ans is not None and len(ans) > 3 and ans.lower() in question.lower() and ans.lower() not in q["question"].lower()
        if not leaks:
            good_q = question
    teach = " ".join(str(teach or "").split())
    good_t = None
    if teach and len(teach) <= 300:
        try:
            from app import coach
            ok = not coach.ungrounded_spans(teach, [q["facts"], {"explain": q["explain"]}], "", strict=True)
            tw = set(re.findall(r"[a-zäö]{4,}", teach.lower()))
            ew = set(re.findall(r"[a-zäö]{4,}", str(q.get("explain") or "").lower()))
            copies = bool(tw) and len(tw & ew) / len(tw) > 0.6
            if ok and not copies and not coach.guardrail(teach):
                good_t = teach
        except Exception:
            good_t = None
    return good_q, good_t


def ai_round(items, ctx, profile, key, model, http_post=None):
    """(title, chosen questions) written by the model, checked; raises on any failure."""
    from app import llm_claude
    pool_view = _pool_for_model(items)
    user = ("Customer facts:\n- " + "\n- ".join(_profile_lines(ctx, profile)) +
            "\n\nQuestion pool (JSON):\n" + json.dumps(pool_view, ensure_ascii=False))
    resp = llm_claude.create(SYSTEM, [{"role": "user", "content": user}], [], key, model, http_post=http_post,
                             timeout=AI_TIMEOUT, max_tokens=4000, effort="low",
                             deadline=time.monotonic() + AI_SECONDS)
    text = llm_claude.text_of(resp)
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON in the reply")
    data = json.loads(m.group(0))
    by_id = {q["id"]: q for q in items}
    chosen, seen = [], set()
    for it in data.get("items") or []:
        if not isinstance(it, dict) or it.get("id") not in by_id or it["id"] in seen:
            continue
        seen.add(it["id"])
        q = dict(by_id[it["id"]])
        q["question"], q["teach"] = check_item(q, it.get("question"), it.get("teach"))
        chosen.append(q)
    you = sum(1 for q in chosen if q["about"] == "you")
    if len(chosen) < 4 or you < 2 or len(chosen) - you < 1:
        raise ValueError("the model's round is too thin")
    title = " ".join(str(data.get("title") or "").split())[:60]
    if not title or _numbers(title) or len(title.split()) > 8:
        title = None
    return title, chosen[:ROUND_SIZE + 1], {"system_prompt_summary": SUMMARY, "user_message": user[:6000]}


# ---------------------------------------------------------------------------------------------- rounds
def public(rnd):
    """What the browser may see of a round: no answers or explanations before they are earned."""
    qs = []
    for q in rnd["questions"]:
        d = {"id": q["id"], "about": q["about"], "topic": q["topic"], "kind": q["kind"], "question": q["question"]}
        if q["kind"] == "choice":
            d["options"] = q["options"]
        else:
            d.update({"min": q["min"], "max": q["max"], "step": q["step"], "unit": q["unit"]})
        a = (rnd.get("answers") or {}).get(q["id"])
        if a:
            d["result"] = a
        qs.append(d)
    return {"round_id": rnd["id"], "title": rnd.get("title") or "Your money quiz", "mode": rnd.get("mode", "offline"),
            "questions": qs, "score": score(rnd), "date": rnd.get("date")}


def score(rnd):
    ans = rnd.get("answers") or {}
    return {"right": sum(1 for a in ans.values() if a.get("correct")), "answered": len(ans),
            "total": len(rnd["questions"])}


def build(conn, today, cid=None, profile=None, k=1, recent=(), ai=None):
    """A new round. `ai` is None (code picks) or a dict {key, model, http_post} for the model."""
    items, ctx = pool(conn, today, cid, profile)
    fresh = [q for q in items if q["id"] not in set(recent or ())]
    usable = fresh if len(fresh) >= ROUND_SIZE + 2 else items
    title, chosen, mode, payload = None, None, "offline", None
    if ai:
        try:
            title, chosen, payload = ai_round(usable, ctx, profile, ai.get("key"), ai.get("model"), ai.get("http_post"))
            mode = "claude"
        except Exception:
            chosen = None
    if not chosen:
        chosen = pick(usable, recent, seed=(cid, today, k))
    rid = "q%s-%d-%s" % (str(today).replace("-", ""), int(k),
                         hashlib.sha256(("%s|%s|%s" % (cid, today, k)).encode()).hexdigest()[:8])
    return {"id": rid, "date": str(today), "k": int(k), "title": title or "Your money quiz", "mode": mode,
            "questions": chosen, "answers": {}}, payload


def grade(rnd, qid, answer):
    """Mark one answer. Returns the result (also stored in rnd['answers'])."""
    q = next((x for x in rnd["questions"] if x["id"] == qid), None)
    if q is None:
        raise KeyError("unknown question")
    if qid in (rnd.get("answers") or {}):
        res = dict(rnd["answers"][qid])          # answered before: the same result, nothing changes
        res["score"] = score(rnd)
        res["done"] = res["score"]["answered"] >= res["score"]["total"]
        return res
    res = {"qid": qid, "explain": q["explain"], "teach": q.get("teach"), "source": q.get("source"),
           "evidence": q.get("evidence") or []}
    if q["kind"] == "choice":
        try:
            pick_i = int(answer)
        except (TypeError, ValueError):
            raise ValueError("answer must be the number of an option")
        if not 0 <= pick_i < len(q["options"]):
            raise ValueError("no such option")
        ok = pick_i == q["answer"]
        res.update({"correct": ok, "chosen": pick_i, "right_option": q["answer"], "answer_text": q["options"][q["answer"]],
                    "verdict": "Right!" if ok else "Not quite: it's %s." % q["options"][q["answer"]]})
    else:
        try:
            g = float(answer)
        except (TypeError, ValueError):
            raise ValueError("answer must be a number")
        if not math.isfinite(g) or g < 0 or g > 1e9:
            raise ValueError("answer out of range")
        actual = float(q["answer"])
        unit = q.get("unit", "eur")
        fmt = (lambda v: "%d" % round(v)) if unit == "count" else (lambda v: _eur(v))
        d, ad = g - actual, abs(g - actual)
        tol = max(1.0 if unit == "count" else 2.0, 0.10 * actual)
        if ad <= tol:
            grade_, verdict, ok = "spot_on", "Spot on!", True
        elif ad <= max(1.5 if unit == "count" else 5.0, 0.25 * actual):
            grade_, verdict, ok = "close", "Very close: %s %s." % (fmt(ad), "too high" if d > 0 else "too low"), True
        elif ad <= max(2.5 if unit == "count" else 10.0, 0.5 * actual):
            grade_, verdict, ok = "ballpark", "In the ballpark: %s %s." % (fmt(ad), "too high" if d > 0 else "too low"), False
        else:
            grade_, verdict, ok = "off", "Quite far off: the answer is %s." % (fmt(actual)), False
        res.update({"correct": ok, "grade": grade_, "guess": round(g, 2), "actual": round(actual, 2), "unit": unit,
                    "answer_text": fmt(actual) if unit == "count" else _eur_x(actual), "verdict": verdict})
    rnd.setdefault("answers", {})[qid] = res
    res = dict(res)
    res["score"] = score(rnd)
    res["done"] = res["score"]["answered"] >= res["score"]["total"]
    return res
