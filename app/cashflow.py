"""Cash flow facts for one customer: how low the account has been, and how pay arrives.

Two tools, both `(conn, today)` like everything in app/insights.py: `low_points` (days below zero, the
limit the account stops at, the lowest point of each pay cycle, long waits for pay, how many months the
balance covers) and `income_profile` (the usual payday, range and average of salary, longest wait,
other income, the next payday). Money is computed here, never by the model. Every result carries
`highlights` (2 to 5 plain sentences, each with its figures), `text` (the first two joined) and
`explain`. With no salary or under three months of data the result has `too_little_data: true` and no
highlights. Read-only; never raises on an empty table.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from . import insights as ins

LIMIT_TOLERANCE = 0.5       # rows within this many euros of the lowest balance count as "at the limit"
LIMIT_MONTHS = 3            # reached in this many different months: it looks like a limit
LONG_GAP_DAYS = 35
MIN_DATA_DAYS = 89          # under about three months of data: too little


# --------------------------------------------------------------------------- small helpers

def _money(x):
    """A balance or amount in a sentence: €1,234, whole euros (cents only under €20), no sign."""
    return ins.money(x, zero="€0")


def _below_zero(x):
    return "%s below zero" % _money(x)


def _day(d, today):
    """"15 December"; the year is added only for dates more than a year back."""
    d = ins._d(d)
    name = "%d %s" % (d.day, ins._MON_FULL[d.month])
    if (ins._d(today) - d).days > 365:
        name += " %d" % d.year
    return name


def _days(n):
    return "%d day%s" % (n, "" if n == 1 else "s")


def _ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suf)


def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:       # a missing or unreadable table is "no data", never an error
        return []


def _salary_dates(conn, t):
    rows = _rows(conn, "SELECT DISTINCT d FROM tx WHERE type='salary' AND d<=? ORDER BY d", (t.isoformat(),))
    return [ins._d(r[0]) for r in rows]


def _first_day(conn):
    rows = _rows(conn, "SELECT MIN(d) FROM tx")
    return ins._d(rows[0][0]) if rows and rows[0][0] else None


def _too_little(kind, why, extra=None):
    out = {"too_little_data": True, "highlights": [], "text": "",
           "explain": "Not enough history to say anything about %s: %s." % (kind, why)}
    out.update(extra or {})
    return out


def _enough_data(conn, t):
    """(first day, salary dates) or None when there is no salary or under about three months of rows."""
    first = _first_day(conn)
    sal = _salary_dates(conn, t)
    if first is None or not sal or (t - first).days < MIN_DATA_DAYS:
        return None
    return first, sal


# --------------------------------------------------------------------------- low points

def _balance_by_day(conn, t):
    """({day: balance after the day's last row}, [(day, balance)] in order)."""
    rows = _rows(conn, "SELECT d, balance FROM tx WHERE d<=? ORDER BY d, ts, rowid", (t.isoformat(),))
    byday, flat = {}, []
    for d, b in rows:
        if b is None:
            continue
        dd = ins._d(d)
        byday[dd] = float(b)
        flat.append((dd, float(b)))
    return byday, flat


def _carry(byday, start, end):
    """[(day, balance at the end of that day)] for each calendar day start..end, carrying the balance over
    days without rows. Days before the first known balance are left out."""
    prior = [d for d in byday if d < start]
    cur = byday[max(prior)] if prior else None
    out = []
    day = start
    while day <= end:
        if day in byday:
            cur = byday[day]
        if cur is not None:
            out.append((day, cur))
        day += timedelta(days=1)
    return out


def _usual_spending(conn, t):
    ms = ins._month_list(conn, t, 12)
    return float(ins._avg_where(conn, ms, "1=1")) if ms else 0.0


def low_points(conn, today, months=12):
    """Days below zero, the limit, the lowest point of each pay cycle, long waits for pay, the cushion."""
    t = ins._d(today)
    try:
        months = max(1, min(24, int(months)))
    except (TypeError, ValueError):
        months = 12
    ok = _enough_data(conn, t)
    if ok is None:
        return _too_little("your lowest points", "I need a salary and about three months of transactions",
                           {"days_below_zero_365": 0, "days_below_zero": 0, "by_month": {}, "cycle_lows": [],
                            "long_gaps": []})
    first, sal = ok
    byday, flat = _balance_by_day(conn, t)
    if not flat:
        return _too_little("your lowest points", "there are no balances")
    start = max(ins._add_months(t, -months) + timedelta(days=1), first)
    series = _carry(byday, start, t)

    below = [d for d, b in series if b < 0]
    by_month = dict(sorted(Counter(d.strftime("%Y-%m") for d in below).items()))
    balance_now = flat[-1][1]

    low_amt, low_day = min(((b, d) for d, b in flat), key=lambda x: (x[0], x[1]))
    at_limit = [d for d, b in flat if b <= low_amt + LIMIT_TOLERANCE]
    days_at = sorted(set(at_limit))
    months_at = sorted({d.strftime("%Y-%m") for d in days_at})
    looks_like_limit = low_amt < 0 and len(months_at) >= LIMIT_MONTHS

    # lowest point of each of the last 6 completed pay cycles (salary to the next salary)
    cycles = []
    for a, b in zip(sal, sal[1:]):
        inside = [(bal, d) for d, bal in flat if a <= d < b]
        if not inside:
            continue
        lo, d_lo = min(inside, key=lambda x: (x[0], x[1]))
        cycles.append({"from": a.isoformat(), "to": b.isoformat(), "low": ins._r(lo),
                       "d": d_lo.isoformat(), "days_before_pay": (b - d_lo).days})
    cycle_lows = cycles[-6:]

    # long waits for pay inside the window
    long_gaps = []
    for a, b in zip(sal, sal[1:]):
        n = (b - a).days
        if n > LONG_GAP_DAYS and b >= start:
            dz = sum(1 for d, bal in _carry(byday, a, b - timedelta(days=1)) if bal < 0)
            long_gaps.append({"from": a.isoformat(), "to": b.isoformat(), "days": n, "days_below_zero": dz})

    usual_month = _usual_spending(conn, t)
    buffer_months = balance_now / usual_month if usual_month > 0 and balance_now > 0 else None

    # ---- sentences
    hl = []
    span_txt = "in the last year" if months == 12 else "in the last %d months" % months
    ever_below = low_amt < 0
    if below:
        hl.append("Your account was below zero on %s %s." % (_days(len(below)), span_txt))
    elif ever_below:
        hl.append("Your account has stayed above zero %s." % span_txt)
    else:
        data_months = max(1, round((t - first).days / 30.44))
        hl.append("Your account has not gone below zero in the %d months I can see." % data_months)
    if ever_below:
        if looks_like_limit:
            hl.append("The lowest your account has been is %s, reached in %d different months, "
                      "which looks like your limit." % (_below_zero(low_amt), len(months_at)))
        else:
            hl.append("The lowest your account has been is %s, on %s." % (_below_zero(low_amt), _day(low_day, t)))
    else:
        hl.append("The lowest your account has been is %s, on %s." % (_money(low_amt), _day(low_day, t)))
    typical = None
    lows_neg = [c for c in cycle_lows if c["low"] < 0]
    if ever_below and len(cycle_lows) >= 4 and lows_neg:
        dbp = [c["days_before_pay"] for c in cycle_lows]
        if max(dbp) <= 10:
            typical = [min(dbp), max(dbp)]
            if typical[0] == typical[1]:
                hl.append("The lowest point of a pay cycle usually comes %s before payday." % _days(typical[0]))
            else:
                hl.append("The lowest point of a pay cycle usually comes %d to %d days before payday." % tuple(typical))
    if long_gaps:
        g = max(long_gaps, key=lambda x: (x["days"], x["from"]))
        s = "Between %s and %s there were %d days without pay" % (_day(g["from"], t), _day(g["to"], t), g["days"])
        if g["days_below_zero"]:
            s += ", and you were below zero on %d of them" % g["days_below_zero"]
        hl.append(s + ".")
    if buffer_months is not None and len(hl) < 5:
        bm = round(buffer_months) if buffer_months >= 3 else round(buffer_months, 1)
        bm_txt = ("%d" % bm) if float(bm).is_integer() else ("%.1f" % bm)
        hl.append("Your balance of %s covers about %s months of your usual spending of %s a month."
                  % (_money(balance_now), bm_txt, _money(usual_month)))
    hl = hl[:5]

    explain = ("Counted from the balance at the end of each day over the last %s; the limit is the lowest balance "
               "ever seen, and a limit only when it was reached in %d or more different months to within "
               "€0.50; pay cycles run from one salary to the next." % (
                   "year" if months == 12 else "%d months" % months, LIMIT_MONTHS))
    return {
        "too_little_data": False,
        "months": months, "window": {"from": start.isoformat(), "to": t.isoformat()},
        "days_below_zero_365": len(below), "days_below_zero": len(below), "by_month": by_month,
        "lowest": {"amount": ins._r(low_amt), "d": low_day.isoformat()},
        "limit_seen": ins._r(low_amt) if low_amt < 0 else None,
        "limit_looks_real": looks_like_limit,
        "days_at_limit": len(days_at) if low_amt < 0 else 0,
        "months_at_limit": len(months_at) if low_amt < 0 else 0,
        "cycle_lows": cycle_lows, "typical_days_before_pay": typical,
        "buffer_months": ins._r(buffer_months) if buffer_months is not None else None,
        "balance_now": ins._r(balance_now), "usual_month": ins._r(usual_month),
        "long_gaps": long_gaps,
        "highlights": hl, "text": " ".join(hl[:2]), "explain": explain,
    }


# --------------------------------------------------------------------------- income profile

def _is_month_end(d):
    return d.day >= ins._last_day(d.year, d.month) - 3


def income_profile(conn, today):
    """When pay comes, how steady it is, other income, and the next payday (corrected rule)."""
    t = ins._d(today)
    ok = _enough_data(conn, t)
    if ok is None:
        return _too_little("your income", "I need a salary and about three months of transactions",
                           {"salaries": 0, "next_payday": None})
    srows = _rows(conn, "SELECT d, amount FROM tx WHERE type='salary' AND d<=? ORDER BY d, ts, rowid",
                  (t.isoformat(),))
    sal = [(ins._d(r[0]), float(r[1])) for r in srows]
    dates = sorted({d for d, _ in sal})
    n = len(sal)
    usual = ins._usual_payday(conn, t)
    if usual == "eom":
        on_usual = sum(1 for d, _ in sal if _is_month_end(d))
    else:
        on_usual = sum(1 for d, _ in sal if d.day == usual)
    month_end = sum(1 for d, _ in sal if _is_month_end(d))
    amounts = [a for _, a in sal]

    this_start = ins._month_start(t)
    cur_start = ins._add_months(this_start, -12)
    now_a = [a for d, a in sal if cur_start <= d < this_start]
    before_a = [a for d, a in sal if d < cur_start]
    avg_now = sum(now_a) / len(now_a) if now_a else None
    avg_before = sum(before_a) / len(before_a) if before_a else None

    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    longest = None
    if gaps:
        i = max(range(len(gaps)), key=lambda k: (gaps[k], k))
        longest = {"from": dates[i].isoformat(), "to": dates[i + 1].isoformat(), "days": gaps[i]}
    long_gaps = [{"from": a.isoformat(), "to": b.isoformat(), "days": (b - a).days}
                 for a, b in zip(dates, dates[1:]) if (b - a).days > LONG_GAP_DAYS]

    other = [{"d": r[0], "amount": ins._r(r[1])} for r in _rows(
        conn, "SELECT d, amount FROM tx WHERE type='other_income' AND amount>0 AND d<=? ORDER BY d, ts, rowid",
        (t.isoformat(),))][-6:]

    paid_this_month = any(this_start <= d <= t for d in dates)
    nxt = ins._next_payday(t, usual, conn)
    latest = ins._payday_latest(nxt, usual)
    days_to = (nxt - t).days

    # ---- sentences
    hl = []
    when = "at the end of the month" if usual == "eom" else "on the %s" % _ordinal(usual)
    if min(amounts) == max(amounts):
        rng = "always %s" % _money(min(amounts))
    else:
        rng = "between %s and %s" % (_money(min(amounts)), _money(max(amounts)))
    hl.append("You are usually paid %s (%d of the last %d times), %s." % (when, on_usual, n, rng))
    if longest and longest["days"] > LONG_GAP_DAYS:
        if usual != "eom" and month_end:
            lead = ("Sometimes pay comes at the end of the month instead (%d of %d times), and the longest "
                    "wait was " % (month_end, n))
        else:
            lead = "The longest wait between salaries was "
        hl.append("%s%d days, from %s to %s." % (lead, longest["days"], _day(longest["from"], t),
                                                   _day(longest["to"], t)))
    elif usual != "eom" and month_end:
        hl.append("Sometimes pay comes at the end of the month instead (%d of %d times); the longest wait "
                  "between salaries was %s." % (month_end, n, _days(longest["days"] if longest else 0)))
    elif longest:
        hl.append("Your pay arrives steadily: the longest wait between salaries was %s." % _days(longest["days"]))
    late_txt = ", and it may come as late as %s" % _day(latest, t) if latest else ""
    if paid_this_month:
        hl.append("This month's salary has arrived; your next payday is most likely %s, %s away%s."
                  % (_day(nxt, t), _days(days_to), late_txt))
    else:
        hl.append("Your next payday is most likely %s, %s away%s." % (_day(nxt, t), _days(days_to), late_txt))
    if avg_now is not None and avg_before is not None:
        if abs(avg_now - avg_before) < 20:
            hl.append("Your salary has stayed about the same: %s a month over the last 12 months, %s before that."
                      % (_money(avg_now), _money(avg_before)))
        else:
            hl.append("Your salary averages %s a month over the last 12 months, compared with %s before that."
                      % (_money(avg_now), _money(avg_before)))
    if other and len(hl) < 5:
        bits = ["%s on %s" % (_money(o["amount"]), _day(o["d"], t)) for o in other[-2:]]
        hl.append("Besides salary you received %s." % " and ".join(bits))
    hl = hl[:5]
    if len(hl) < 2:      # a single salary: say what little there is
        hl.append("Your next payday is most likely %s." % _day(nxt, t))

    explain = ("From your salary payments: the usual day is the most common day over the last 12 months "
               "(month end counts only when most salaries came then). Once the usual day has passed without "
               "pay, the next payday is expected at the end of the month.")
    return {
        "too_little_data": False,
        "usual_day": usual, "on_usual_day": on_usual, "salaries": n, "month_end": month_end,
        "range": [ins._r(min(amounts)), ins._r(max(amounts))],
        "average_now": ins._r(avg_now) if avg_now is not None else None,
        "average_before": ins._r(avg_before) if avg_before is not None else None,
        "longest_gap": longest, "long_gaps": long_gaps, "other_income": other,
        "paid_this_month": paid_this_month,
        "next_payday": nxt.isoformat(), "days_to_payday": days_to,
        "payday_may_be_late_days": (latest - nxt).days if latest else 0,
        "highlights": hl, "text": " ".join(hl[:2]), "explain": explain,
    }
