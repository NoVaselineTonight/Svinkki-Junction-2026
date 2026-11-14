"""The long view of a customer's money: balance path, seasons, one category over time, one unusual month.

Four read-only functions over a sandbox connection `conn` (table `tx`, one customer, rows up to `today`):

    money_story(conn, today, months=12)            how am I doing over time
    season_outlook(conn, today, months_ahead=5)    the same coming months last year, and what a repeat does
    category_story(conn, today, label, months=24)  one category: trips, basket size, peak, season
    explain_month(conn, today, month=None, top=3)  why was a month high (or low)

Every result carries `highlights` (2 to 5 plain sentences with their figures), `text` (the first one or
two joined), `explain` and `evidence`. With fewer than 6 full months of data a result has an empty
`highlights` list and `"too_little_data": true`. "Full months" are the months before today's month.
Spending is the three spending baskets (as in app.insights); savings deposits are counted separately.
Fixed bills (Housing, Utilities) are averaged as the median of the months they appear in, because
some months simply have no rent row (bug B3): a plain average would understate them.
"""
from __future__ import annotations

import statistics
from datetime import date

from . import insights as ins
from .insights import _d, _ev, _add_months, _month_start, _median, _MON_FULL

MIN_MONTHS = 6
FIXED_BILLS = ("Housing", "Utilities")
_COMBINED = {"dining out": ("Restaurant", "Fast food")}
_SPEND = ins._SPEND_SQL
_LABEL = "COALESCE(NULLIF(label,''),'Other')"


# --------------------------------------------------------------------------- small helpers

def _e(x):
    """Whole euros with a thousands comma and the euro sign in front: €1,234."""
    return "€{:,.0f}".format(abs(round(float(x or 0.0))))


def _bal(x):
    """A balance in a sentence: €2,228, or €425 below zero."""
    return "%s below zero" % _e(x) if round(float(x)) < 0 else _e(x)


def _n(x):
    """A count per month with one decimal, no trailing .0: 14.7, 9.5, 5."""
    v = round(float(x), 1)
    return "%d" % v if v == int(v) else "%.1f" % v


def _r(x):
    return round(float(x or 0.0) + 0.0, 2)


def _day(d):
    x = _d(d)
    return "%d %s %d" % (x.day, _MON_FULL[x.month], x.year)


def _month_name(ym):
    return _MON_FULL[int(str(ym)[5:7])]


def _ym(d):
    return "%04d-%02d" % (d.year, d.month)


def _shift_ym(ym, n):
    d = _add_months(date(int(ym[:4]), int(ym[5:7]), 1), n)
    return _ym(d)


def _month_bounds(ym):
    s = date(int(ym[:4]), int(ym[5:7]), 1)
    return s.isoformat(), ins._month_end(s).isoformat()


def _finish(res, highlights, explain, evidence=None):
    res["highlights"] = list(highlights)
    res["text"] = " ".join(highlights[:2])
    res["explain"] = explain
    res["evidence"] = evidence or []
    return res


def _thin(res, why):
    res["too_little_data"] = True
    res["highlights"] = []
    res["text"] = ""
    res["explain"] = why
    res["evidence"] = []
    return res


def _full_months(conn, today):
    """Full calendar months before today's month that the data covers, oldest first ("YYYY-MM")."""
    return [a[:7] for a, _b in ins._month_list(conn, _d(today), 120)]


def _monthly(conn, today):
    """{ym: {"income", "spent", "saved"}} (one pass over the rows up to today)."""
    out = {}
    for r in conn.execute(
            "SELECT substr(d,1,7) m, "
            "SUM(CASE WHEN basket='income' THEN amount ELSE 0 END), "
            "SUM(CASE WHEN basket IN ('regular','unexpected','everyday') AND amount<0 THEN -amount ELSE 0 END), "
            "SUM(CASE WHEN basket='savings' THEN -amount ELSE 0 END) "
            "FROM tx WHERE d<=? GROUP BY m", (str(today),)):
        out[r[0]] = {"income": r[1] or 0.0, "spent": r[2] or 0.0, "saved": r[3] or 0.0}
    return out


def _by_label(conn, today, extra_sql="", params=()):
    """{label: {ym: (total, count)}} over spending rows (money out only)."""
    out = {}
    sql = ("SELECT %s, substr(d,1,7), SUM(-amount), COUNT(*) FROM tx WHERE d<=? AND amount<0 AND %s %s "
           "GROUP BY 1, 2" % (_LABEL, _SPEND, extra_sql))
    for lab, m, tot, n in conn.execute(sql, (str(today),) + tuple(params)):
        out.setdefault(lab, {})[m] = (tot or 0.0, n or 0)
    return out


def _label_avg(label, per_month, months):
    """Average euros a month of one label over `months`; fixed bills use the median of months present."""
    if not months:
        return 0.0
    if label in FIXED_BILLS:
        vals = [per_month[m][0] for m in months if m in per_month]
        return _median(vals)
    return sum(per_month[m][0] for m in months if m in per_month) / len(months)


def _avgs(lm, months):
    return {lab: _label_avg(lab, pm, months) for lab, pm in lm.items()}


def _balances(conn, today):
    """[(d, end-of-day balance)] oldest first."""
    out = {}
    for d, b in conn.execute("SELECT d, balance FROM tx WHERE d<=? ORDER BY ts, rowid", (str(today),)):
        out[d] = b
    return sorted(out.items())


def _balance_on(bal, d):
    last = None
    for day, b in bal:
        if day > d:
            break
        last = b
    return last


def _spend_evidence(frm, to, title):
    return ins._spend_filters(frm, to, title)


# --------------------------------------------------------------------------- T1 money_story

def money_story(conn, today, months=12):
    """The long view: balance path, months with more out than in, biggest changes by category."""
    t = _d(today)
    months = max(1, min(int(months or 12), 36))
    res = {"window": None}
    full = _full_months(conn, today)
    if len(full) < MIN_MONTHS:
        return _thin(res, "Less than %d full months of data, too little for a long view." % MIN_MONTHS)

    win = full[-months:]
    before = full[-2 * months:-months] if len(full) > months else []
    if len(before) < 3:
        before = []
    mo = _monthly(conn, today)
    lm = _by_label(conn, today)
    frm, to = _month_bounds(win[0])[0], _month_bounds(win[-1])[1]
    res["window"] = {"from": frm, "to": to, "months": len(win)}

    # balance path
    bal = _balances(conn, today)
    ref = _add_months(t, -months).isoformat()
    first_day = bal[0][0] if bal else None
    now = bal[-1][1] if bal else 0.0
    year_ago = _balance_on(bal, ref) if first_day and first_day <= ref else None
    inwin = [(d, b) for d, b in bal if d >= frm] or bal
    hi_b = max(b for _, b in inwin)
    lo_b = min(b for _, b in inwin)
    hi = min((x for x in inwin if x[1] == hi_b), key=lambda x: x[0])
    lo = min((x for x in inwin if x[1] == lo_b), key=lambda x: x[0])
    at_low = sum(1 for _, b in inwin if b <= lo[1] + 0.5) if lo[1] < 0 else 0
    res["balance"] = {
        "now": _r(now), "year_ago": None if year_ago is None else _r(year_ago),
        "change": None if year_ago is None else _r(now - year_ago),
        "highest": {"amount": _r(hi[1]), "d": hi[0]}, "lowest": {"amount": _r(lo[1]), "d": lo[0]},
        "basis": "end-of-day balances: the highest and lowest are the closing balance of a day",
        "times_at_lowest": at_low}

    # per-month figures, this window against the one before
    avg_now, avg_bef = _avgs(lm, win), _avgs(lm, before)
    inc_now = sum(mo.get(m, {}).get("income", 0.0) for m in win) / len(win)
    spent_now = sum(mo.get(m, {}).get("spent", 0.0) for m in win) / len(win)
    res["per_month"] = {"spent": _r(spent_now), "income": _r(inc_now)}
    if before:
        res["per_month"]["spent_before"] = _r(sum(mo.get(m, {}).get("spent", 0.0) for m in before) / len(before))
        res["per_month"]["income_before"] = _r(sum(mo.get(m, {}).get("income", 0.0) for m in before) / len(before))
    more_out = [m for m in win if mo.get(m, {}).get("spent", 0.0) + mo.get(m, {}).get("saved", 0.0)
                > mo.get(m, {}).get("income", 0.0)]
    res["months_more_out"] = len(more_out)
    def _kept(ms):
        return sum(mo.get(m, {}).get("income", 0.0) - mo.get(m, {}).get("spent", 0.0) for m in ms)
    kept = {"this_window": _r(_kept(win)), "months_this_window": len(win), "per_month_this_window": _r(_kept(win) / len(win))}
    if before:
        kept["months_window_before"] = len(before)
        kept["per_month_window_before"] = _r(_kept(before) / len(before))
        if len(before) == len(win):
            kept["window_before"] = _r(_kept(before))
        kept["note"] = ("Compare the per-month figures: the earlier window holds %d months, this one %d."
                        % (len(before), len(win)))
    res["kept"] = kept
    res["saved_in_window"] = _r(sum(mo.get(m, {}).get("saved", 0.0) for m in win))

    # risers and fallers by label (at least €15 a month and 25 %)
    risers, fallers = [], []
    if before:
        for lab in set(avg_now) | set(avg_bef):
            a, b = avg_now.get(lab, 0.0), avg_bef.get(lab, 0.0)
            d = a - b
            if abs(d) < 15 or (b > 0 and abs(d) / b < 0.25):
                continue
            item = {"label": lab, "now": _r(a), "before": _r(b)}
            (risers if d > 0 else fallers).append((abs(d), item))
        risers = [i for _, i in sorted(risers, key=lambda x: -x[0])[:3]]
        fallers = [i for _, i in sorted(fallers, key=lambda x: -x[0])[:3]]
    res["risers"], res["fallers"] = risers, fallers

    # groceries: trips and basket size
    groc = None
    g = lm.get("Groceries")
    if g and before:
        def stats(ms):
            tot = sum(g[m][0] for m in ms if m in g)
            n = sum(g[m][1] for m in ms if m in g)
            return tot / len(ms), n / len(ms), (tot / n if n else 0.0)
        pn, tn, bn = stats(win)
        pb, tb, bb = stats(before)
        groc = {"now": _r(pn), "before": _r(pb), "trips_now": round(tn, 1), "trips_before": round(tb, 1),
                "basket_now": _r(bn), "basket_before": _r(bb)}
        res["groceries"] = groc

    # sentences
    span = "a year ago" if months == 12 else "%d months ago" % months
    hl = []
    if year_ago is not None:
        hl.append("Your balance went from %s %s to %s now." % (_bal(year_ago), span, _bal(now)))
    else:
        hl.append("Your balance is %s now." % _bal(now))
    n = len(win)
    if more_out:
        hl.append("In %d of the last %d months more went out than came in." % (len(more_out), n))
    else:
        hl.append("In none of the last %d months did more go out than came in." % n)
    if groc and abs(groc["now"] - groc["before"]) >= 15 and groc["before"] > 0 \
            and abs(groc["now"] - groc["before"]) / groc["before"] >= 0.25:
        d_trips = (groc["trips_now"] - groc["trips_before"]) * groc["basket_before"]
        d_basket = (groc["basket_now"] - groc["basket_before"]) * groc["trips_now"]
        up = groc["now"] > groc["before"]
        if abs(d_trips) >= abs(d_basket):
            why = ("because you shop %s often (%s trips a month, %s from %s), not because baskets got %s"
                   % ("more" if up else "less", _n(groc["trips_now"]), "up" if up else "down", _n(groc["trips_before"]),
                      "bigger" if up else "smaller"))
        else:
            why = ("because each shop is %s (about %s, %s from %s)"
                   % ("bigger" if up else "smaller", _e(groc["basket_now"]), "up" if up else "down",
                      _e(groc["basket_before"])))
        hl.append("Groceries %s to about %s a month from %s, %s." % (
            "rose" if up else "fell", _e(groc["now"]), _e(groc["before"]), why))
    elif risers:
        r0 = risers[0]
        hl.append("%s rose to about %s a month from %s." % (ins.label_title(r0["label"]), _e(r0["now"]), _e(r0["before"])))
    elif fallers:
        f0 = fallers[0]
        hl.append("%s fell to about %s a month from %s." % (ins.label_title(f0["label"]), _e(f0["now"]), _e(f0["before"])))
    if lo[1] < 0:
        s = "At its lowest your account was %s (%s)" % (_bal(lo[1]), _day(lo[0]))
        if at_low >= 2:
            s += ", and it was that low on %d days" % at_low
        hl.append(s + ".")
    if len(hl) < 5 and len(risers) > 1 and not (groc and hl[2:3] and hl[2].startswith("Groceries")):
        r1 = risers[1]
        hl.append("%s also went up, to about %s a month from %s." % (ins.label_title(r1["label"]), _e(r1["now"]), _e(r1["before"])))
    if len(hl) < 5 and fallers and not (len(hl) > 2 and "fell" in hl[2]):
        f0 = fallers[0]
        hl.append("%s went down, to about %s a month from %s." % (ins.label_title(f0["label"]), _e(f0["now"]), _e(f0["before"])))
    if res["saved_in_window"] >= 1:
        hl.insert(1, "Of the money kept over these %d months, %s went into savings and investments." % (
            n, _e(res["saved_in_window"])))
    explain = ("Balance from the account rows (end of day); the last %d full months against the %s before them. "
               "Fixed bills use the median of the months they appear in." % (n, "months" if before else "(no earlier months)"))
    return _finish(res, hl[:5], explain, _spend_evidence(frm, to, "last %d months" % n))


# --------------------------------------------------------------------------- T2 season_outlook

def season_outlook(conn, today, months_ahead=5):
    """The same coming calendar months a year ago (and two years ago) and what a repeat does to the balance."""
    t = _d(today)
    n = max(1, min(int(months_ahead or 5), 6))
    res = {"months": []}
    full = _full_months(conn, today)
    nxt = _ym(_add_months(_month_start(t), 1))
    coming = [_shift_ym(nxt, i) for i in range(n)]
    res["months"] = coming
    last = [_shift_ym(m, -12) for m in coming]
    if len(full) < MIN_MONTHS or not all(m in full for m in last):
        return _thin(res, "Not a full year of data for the coming months, so there is nothing to compare with.")
    mo = _monthly(conn, today)
    lm = _by_label(conn, today)

    def block(ms):
        sp = sum(mo.get(m, {}).get("spent", 0.0) for m in ms)
        inc = sum(mo.get(m, {}).get("income", 0.0) for m in ms)
        sv = sum(mo.get(m, {}).get("saved", 0.0) for m in ms)
        return {"from": ms[0], "to": ms[-1], "spent": _r(sp), "income": _r(inc), "saved": _r(sv),
                "gap": _r(sp + sv - inc)}

    ly = block(last)
    ly["groceries"] = _r(sum(lm.get("Groceries", {}).get(m, (0.0, 0))[0] for m in last))
    res["last_year"] = ly
    before = [_shift_ym(m, -12) for m in last]
    yb = block(before) if all(m in full for m in before) else None
    if yb:
        res["year_before"] = {k: yb[k] for k in ("from", "to", "spent", "income", "gap")}

    # which label is highest in these months compared with the rest of that year
    rest = [m for m in (_shift_ym(last[0], i) for i in range(12)) if m in full and m not in last]
    season_vs_rest, best = None, 0.0
    # a season only counts when the same months also stood out the year before (else it is a one-year trend)
    rest_b = [_shift_ym(m, -12) for m in rest]
    two_years = all(m in full for m in before) and len([m for m in rest_b if m in full]) >= 2
    rest_b = [m for m in rest_b if m in full]
    if len(rest) >= 2 and two_years:
        for lab, pm in lm.items():
            s_avg = _label_avg(lab, pm, last)
            r_avg = _label_avg(lab, pm, rest)
            sb_avg = _label_avg(lab, pm, before)
            rb_avg = _label_avg(lab, pm, rest_b)
            if not (rb_avg > 0 and sb_avg - rb_avg >= 10 and sb_avg / rb_avg > 1.2):
                continue
            # a cost that simply stopped part-way (paid in three of five months) is not a season either: it must
            # have been paid in nearly every one of these months, in both years
            need = max(1, len(last) - 1)
            if (sum(1 for m in last if pm.get(m, (0.0, 0))[0] > 0) < need
                    or sum(1 for m in before if pm.get(m, (0.0, 0))[0] > 0) < need):
                continue
            if r_avg > 0 and s_avg - r_avg >= 20 and s_avg / r_avg > 1.3 and s_avg - r_avg > best:
                best = s_avg - r_avg
                season_vs_rest = {"label": lab, "season_monthly": _r(s_avg), "rest_monthly": _r(r_avg)}
    res["season_vs_rest"] = season_vs_rest

    bal = _balances(conn, today)
    now = bal[-1][1] if bal else 0.0
    res["balance_now"] = _r(now)
    res["if_repeated"] = _r(now - ly["gap"])
    res["lowest_seen"] = _r(min((b for _, b in bal), default=0.0))
    res["relevant"] = bool(ly["gap"] > 300 or season_vs_rest is not None)

    span = _month_name(last[0]) if n == 1 else "%s to %s" % (_month_name(last[0]), _month_name(last[-1]))
    hl = []
    sv = " and put %s aside" % _e(ly["saved"]) if ly["saved"] >= 1 else ""
    if ly["gap"] > 0:
        s = "Last %s you spent %s%s,%s %s more than the %s of income that came in" % (
            span, _e(ly["spent"]), sv, " together" if sv else "", _e(ly["gap"]), _e(ly["income"]))
        s += ", and groceries alone came to %s." % _e(ly["groceries"]) if ly["groceries"] >= 100 else "."
    else:
        s = "Last %s you spent %s%s against %s of income, so you kept %s." % (
            span, _e(ly["spent"]), sv, _e(ly["income"]), _e(-ly["gap"]))
    hl.append(s)
    if yb:
        if yb["gap"] > 0:
            hl.append("The year before, the same months had %s more going out than coming in." % _e(yb["gap"]))
        else:
            hl.append("The year before, you kept %s over the same months." % _e(-yb["gap"]))
    if ly["gap"] > 0:
        if res["if_repeated"] < 0:
            s = "If these months go the same way, your %s would not cover it: you would end up about %s." % (
                _e(now) if now >= 0 else _bal(now), _bal(res["if_repeated"]))
        else:
            s = "If these months go the same way, your %s would shrink to about %s." % (_bal(now), _bal(res["if_repeated"]))
    else:
        s = "If these months go the same way, your %s would grow to about %s." % (_bal(now), _bal(res["if_repeated"]))
    hl.append(s)
    if res["lowest_seen"] < 0:
        hl.append("The lowest your account has been is %s." % _bal(res["lowest_seen"]))
    if season_vs_rest:
        hl.append("In these months your %s spending runs at about %s a month, against %s the rest of the year." % (
            ins.label_words(season_vs_rest["label"]), _e(season_vs_rest["season_monthly"]),
            _e(season_vs_rest["rest_monthly"])))
    explain = ("The same calendar months a year earlier (and two years earlier when there is data), with today's "
               "balance. A pace to be aware of, not a forecast.")
    return _finish(res, hl[:5], explain, _spend_evidence(_month_bounds(last[0])[0], _month_bounds(last[-1])[1],
                                                         "%s last year" % span))


# --------------------------------------------------------------------------- T3 category_story

def _resolve_label(conn, today, label):
    """(target, display name) for a label that exists in the customer's spending rows, or ValueError."""
    raw = str(label or "").strip()
    if not raw:
        raise ValueError("label is required")
    key = raw.lower().replace("_", " ")
    existing = {r[0] for r in conn.execute(
        "SELECT DISTINCT %s FROM tx WHERE d<=? AND %s" % (_LABEL, _SPEND), (str(today),))}
    if key in ins._NIGHT_KEYS:
        n = conn.execute("SELECT COUNT(*) FROM tx WHERE d<=? AND context='night_out' AND %s" % _SPEND,
                         (str(today),)).fetchone()[0]
        if n:
            return ("context", "night_out"), "Night out"
        raise ValueError("unknown label: %s" % raw)
    if key in _COMBINED:
        have = [x for x in _COMBINED[key] if x in existing]
        if have:
            return ("labels", have), "Dining out"
        raise ValueError("unknown label: %s" % raw)
    low = {x.lower(): x for x in existing}
    if key in low:
        return ("labels", [low[key]]), low[key]
    kind, val = ins._resolve_target(raw)
    if kind == "labels":
        have = [low[v.lower()] for v in val if v.lower() in low]
        if have:
            return ("labels", have), (have[0] if len(have) == 1 else raw[:1].upper() + raw[1:])
    raise ValueError("unknown label: %s" % raw)


def category_story(conn, today, label, months=24):
    """One category over time: monthly totals and trips, this year against the one before, peak, season."""
    t = _d(today)
    months = max(1, min(int(months or 24), 36))
    target, name = _resolve_label(conn, today, label)
    res = {"label": name}
    full = _full_months(conn, today)
    if len(full) < MIN_MONTHS:
        return _thin(res, "Less than %d full months of data, too little for a category story." % MIN_MONTHS)
    where, params = ins._target_sql(target)
    lm = _by_label(conn, today, "AND " + where, params)
    pm = {}                                   # ym -> (total, count) over every matching label
    for per in lm.values():
        for m, (tot, n) in per.items():
            a, b = pm.get(m, (0.0, 0))
            pm[m] = (a + tot, b + n)
    fixed = name in FIXED_BILLS
    shown = full[-months:]
    res["monthly"] = [{"m": m, "total": _r(pm.get(m, (0.0, 0))[0]), "count": pm.get(m, (0.0, 0))[1]} for m in shown]
    win = full[-12:]
    before = full[-24:-12] if len(full) > 12 else []
    if len(before) < 3:
        before = []

    def stats(ms):
        if fixed:
            vals = [pm[m][0] for m in ms if m in pm]
            per_m = _median(vals)
        else:
            per_m = sum(pm.get(m, (0.0, 0))[0] for m in ms) / len(ms)
        tot = sum(pm.get(m, (0.0, 0))[0] for m in ms)
        cnt = sum(pm.get(m, (0.0, 0))[1] for m in ms)
        return {"per_month": _r(per_m), "trips": round(cnt / len(ms), 1), "basket": _r(tot / cnt if cnt else 0.0),
                "total": tot}
    now_s = stats(win)
    bef_s = stats(before) if before else None
    res["now"] = {k: now_s[k] for k in ("per_month", "trips", "basket")}
    res["before"] = {k: bef_s[k] for k in ("per_month", "trips", "basket")} if bef_s else None
    change_pct = None
    driver = None
    if bef_s and bef_s["per_month"] > 0:
        change_pct = round((now_s["per_month"] - bef_s["per_month"]) / bef_s["per_month"] * 100)
        d_trips = (now_s["trips"] - bef_s["trips"]) * bef_s["basket"]
        d_basket = (now_s["basket"] - bef_s["basket"]) * now_s["trips"]
        driver = "trips" if abs(d_trips) >= abs(d_basket) else "basket"
    res["change_pct"], res["driver"] = change_pct, driver

    pos = [x for x in res["monthly"] if x["total"] > 0]
    res["peak"] = dict(max(pos, key=lambda x: x["total"])) if pos else None
    res["lowest_month"] = dict(min(pos, key=lambda x: x["total"])) if pos else None

    # share of all spending
    mo = _monthly(conn, today)
    share = {}
    for key, ms, st in (("now", win, now_s), ("before", before, bef_s)):
        if ms and st:
            tot_sp = sum(mo.get(m, {}).get("spent", 0.0) for m in ms)
            share[key] = round(st["total"] / tot_sp, 3) if tot_sp else 0.0
    res["share_of_spending"] = share

    # the latest full month against the same month a year before
    last_m = full[-1]
    ly = _shift_ym(last_m, -12)
    res["same_month_last_year"] = ({"m": last_m, "now": _r(pm.get(last_m, (0.0, 0))[0]),
                                    "year_before": _r(pm.get(ly, (0.0, 0))[0])} if ly in full else None)

    # season: November to February against the rest, only when the difference is over 30 %
    season = None
    s_m = [m for m in full if int(m[5:]) in (11, 12, 1, 2)]
    r_m = [m for m in full if int(m[5:]) not in (11, 12, 1, 2)]
    if len(s_m) >= 3 and len(r_m) >= 3:
        s_avg = sum(pm.get(m, (0.0, 0))[0] for m in s_m) / len(s_m)
        r_avg = sum(pm.get(m, (0.0, 0))[0] for m in r_m) / len(r_m)
        if (r_avg > 0 and abs(s_avg / r_avg - 1) > 0.3) or (r_avg == 0 and s_avg > 0):
            season = {"months": "November to February", "season_monthly": _r(s_avg), "rest_monthly": _r(r_avg)}
    res["season"] = season

    # sentences
    words = ins.label_words(name)
    grocery = name == "Groceries"
    trip_w = "trips" if grocery else "purchases"
    hl = []
    if bef_s and change_pct is not None and abs(change_pct) >= 10:
        hl.append("You spend about %s a month on %s now, %s from %s (%d%% %s)." % (
            _e(now_s["per_month"]), words, "up" if change_pct > 0 else "down", _e(bef_s["per_month"]),
            abs(change_pct), "more" if change_pct > 0 else "less"))
    elif bef_s and change_pct is not None:
        hl.append("You spend about %s a month on %s now, about the same as before (%s)." % (
            _e(now_s["per_month"]), words, _e(bef_s["per_month"])))
    else:
        hl.append("You spend about %s a month on %s." % (_e(now_s["per_month"]), words))
    if bef_s and now_s["trips"] and abs(change_pct or 0) >= 10 and driver == "trips":
        hl.append("It is mostly the number of %s, about %s a month instead of %s; an average one is %s%s." % (
            trip_w, _n(now_s["trips"]), _n(bef_s["trips"]),
            "still about " if abs(now_s["basket"] - bef_s["basket"]) < 5 else "about ", _e(now_s["basket"])))
    elif bef_s and abs(change_pct or 0) >= 10 and driver == "basket":
        hl.append("It is mostly the size of each purchase, about %s instead of %s; you make about %s a month." % (
            _e(now_s["basket"]), _e(bef_s["basket"]), _n(now_s["trips"])))
    else:
        hl.append("That is about %s %s a month, an average one is about %s." % (
            _n(now_s["trips"]), trip_w, _e(now_s["basket"])))
    pk = res["peak"]
    if pk:
        unit = ("trip" if grocery else "purchase") + ("" if pk["count"] == 1 else "s")
        hl.append("The peak was %s: %s over %d %s." % (ins.human_month(pk["m"]), _e(pk["total"]), pk["count"], unit))
    if "before" in share and "now" in share and abs(share["now"] - share["before"]) >= 0.02:
        hl.append("It is about %d%% of your spending now, against %d%% before." % (
            round(share["now"] * 100), round(share["before"] * 100)))
    if season and len(hl) < 5:
        hl.append("From November to February it runs at about %s a month, against %s the rest of the year." % (
            _e(season["season_monthly"]), _e(season["rest_monthly"])))
    explain = ("Monthly totals and purchase counts for %s over the full months; the last 12 against the 12 before. "
               "A purchase is one transaction." % words)
    ev = ins._target_filters(target, _month_bounds(win[0])[0], _month_bounds(win[-1])[1], "%s, last 12 months" % name)
    return _finish(res, hl[:5], explain, ev)


# --------------------------------------------------------------------------- T5 explain_month

def explain_month(conn, today, month=None, top=3):
    """Why a month cost what it did: its own usual, the labels above (or below) it, the biggest purchase."""
    top = max(1, min(int(top or 3), 6))
    res = {"month": month}
    if month is not None:
        s = str(month).strip()
        try:
            y, m = int(s[:4]), int(s[5:7])
            if len(s) != 7 or s[4] != "-" or not 1 <= m <= 12:
                raise ValueError
        except ValueError:
            raise ValueError("month must look like 2025-12") from None
        month = s
        res["month"] = month
    full = _full_months(conn, today)
    if len(full) < MIN_MONTHS:
        return _thin(res, "Less than %d full months of data, too little to say what is usual." % MIN_MONTHS)
    if month is not None and month not in full:
        return _thin(res, "%s is not a full month in the data." % ins.human_month(month))
    mo = _monthly(conn, today)
    lm = _by_label(conn, today)
    usual_l = _avgs(lm, full)
    usual_total = sum(usual_l.values())
    present = {lab: sum(1 for m in full if m in lm.get(lab, {})) for lab in FIXED_BILLS}

    def adjusted(m):
        """Spending of month m with a missing fixed bill filled in by its usual amount."""
        sp = mo.get(m, {}).get("spent", 0.0)
        for lab in FIXED_BILLS:
            if lab in lm and m not in lm[lab]:
                sp += usual_l.get(lab, 0.0)
        return sp
    adj = {m: adjusted(m) for m in full}
    mean = statistics.fmean(adj.values())
    sd = statistics.pstdev(adj.values())
    z = {m: ((adj[m] - mean) / sd if sd > 0 else 0.0) for m in full}
    last12 = full[-12:]
    cheapest = min(last12, key=lambda m: (z[m], m))
    named = month is not None
    if not named:
        month = max(last12, key=lambda m: (z[m], m))
    res["month"] = month
    spent = mo.get(month, {}).get("spent", 0.0)
    diff = spent - usual_total
    res["spent"], res["usual"], res["difference"] = _r(spent), _r(usual_total), _r(diff)
    res["z"] = round(z[month], 2)

    pm_month = {lab: per[month][0] for lab, per in lm.items() if month in per}
    deltas = []
    for lab in set(pm_month) | set(usual_l):
        amt = pm_month.get(lab, 0.0)
        if lab in FIXED_BILLS and lab not in pm_month:
            continue                                   # a missing bill is reported below, not as a saving
        deltas.append((amt - usual_l.get(lab, 0.0), lab, amt))
    up = diff >= 0
    key = "above_usual" if up else "below_usual"
    chosen = sorted((x for x in deltas if (x[0] > 0 if up else x[0] < 0)), key=lambda x: -abs(x[0]))
    chosen = [x for x in chosen if abs(x[0]) >= 1][:top]
    res["kind"] = "expensive" if up else "cheap"
    res["drivers"] = [{"label": lab, "amount": _r(amt), key: _r(abs(d))} for d, lab, amt in chosen]

    frm, to = _month_bounds(month)
    row = conn.execute(
        "SELECT %s, -amount, d FROM tx WHERE d BETWEEN ? AND ? AND d<=? AND amount<0 AND %s AND %s NOT IN (?,?) "
        "ORDER BY amount ASC, d ASC LIMIT 1" % (_LABEL, _SPEND, _LABEL), (frm, to, str(today)) + FIXED_BILLS).fetchone()
    res["biggest_purchase"] = {"label": row[0], "amount": _r(row[1]), "d": row[2]} if row else None
    missing = [lab for lab in FIXED_BILLS if lab in lm and month not in lm[lab] and present[lab] >= 0.8 * len(full)]
    res["missing_bills"] = missing
    ch = cheapest
    res["cheapest_month"] = {"month": ch, "spent": _r(mo.get(ch, {}).get("spent", 0.0)),
                             "missing_bills": [lab for lab in FIXED_BILLS if lab in lm and ch not in lm[lab]
                                               and present[lab] >= 0.8 * len(full)]}

    name = ins.human_month(month)
    hl = []
    lead_in = "In %s" % name if named else "%s stood out:" % name
    s = "%s you spent %s, about %s %s your usual %s." % (
        lead_in, _e(spent), _e(abs(diff)), "above" if diff >= 0 else "below", _e(usual_total))
    hl.append(s)
    if chosen:
        parts = ["%s (%s %s%s)" % (ins.label_words(lab), _e(abs(d)), "above" if up else "below",
                                   " usual" if i == 0 else "") for i, (d, lab, _a) in enumerate(chosen)]
        lead = "Most of the extra was" if up else "Most of the saving was"
        hl.append("%s %s." % (lead, ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]))
    if res["biggest_purchase"]:
        bp = res["biggest_purchase"]
        hl.append("Your biggest single purchase that month was %s on %s, on %s." % (
            _e(bp["amount"]), ins.label_words(bp["label"]), "%d %s" % (_d(bp["d"]).day, _month_name(bp["d"]))))
    if missing:
        hl.append("There is no %s payment in %s, so it looks cheaper than it really was." % (
            " or ".join(ins.label_words(x) for x in missing), name))
    if len(hl) < 2:
        hl.append("In an average month you spend about %s." % _e(usual_total))
    explain = ("Spending that month against your own usual month over all full months; fixed bills use the "
               "median of the months they appear in. Unusual means furthest from your average.")
    ev = ins._spend_filters(frm, to, name)
    return _finish(res, hl[:5], explain, ev)
