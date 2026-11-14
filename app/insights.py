"""Every calculation behind the Svinkki coach.

All functions take a sandbox connection `conn` (an in-memory sqlite3 database holding one
customer's rows in table `tx`) and `today` ("YYYY-MM-DD"). Money is computed here, in code, never by
the model. Spending is reported as positive numbers rounded to 2 decimals. Every result carries
`evidence` (filter objects accepted by `transactions()`) and `explain` (one plain sentence).
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import statistics
import zlib
from collections import Counter
from datetime import date, timedelta

SPEND_BASKETS = ("regular", "unexpected", "everyday")
BASKET_NAMES = {
    "regular": "Regular essentials",
    "unexpected": "Unexpected necessities",
    "everyday": "Everyday spending",
    "savings": "Savings",
}
NIGHT_LABELS = ("Restaurant", "Fast food", "Taxi", "Bar")
RATE_PER_EURO = 0.01841        # required monthly income per euro of loan (25 y, 6 % stress, 35 %)
MIN_EQUITY = 0.15

_SPEND_SQL = "basket IN ('regular','unexpected','everyday')"
_DISP_SQL = "CASE WHEN context='night_out' THEN 'Night out' ELSE COALESCE(NULLIF(label,''),'Other') END"

_VOCAB = [
    "Housing", "Utilities", "Groceries", "Restaurant", "Fast food", "Bar", "Taxi", "Public transport",
    "Fuel", "Parking", "Pharmacy", "Doctor", "Dentist", "Other health", "Home improvement",
    "Electronics", "Furniture", "Clothing", "Hobbies", "Books", "Shopping", "Events", "Cinema",
    "Gym & sports", "Entertainment", "Flights", "Hotels", "Travel agency", "Car rental", "Travel",
    "Savings & investments", "Salary", "Other income", "Transfer out", "Other",
]
_ALIASES = {
    "restaurants": ["Restaurant"], "restaurant": ["Restaurant"], "cafe": ["Restaurant"],
    "dining": ["Restaurant", "Fast food"], "dining out": ["Restaurant", "Fast food"],
    "eating out": ["Restaurant", "Fast food"], "food out": ["Restaurant", "Fast food"],
    "fast food": ["Fast food"], "takeaway": ["Fast food"], "kebab": ["Fast food"],
    "taxi": ["Taxi"], "taxis": ["Taxi"], "cab": ["Taxi"], "cabs": ["Taxi"],
    "bar": ["Bar"], "bars": ["Bar"], "pub": ["Bar"], "pubs": ["Bar"], "alcohol": ["Bar"],
    "groceries": ["Groceries"], "grocery": ["Groceries"], "supermarket": ["Groceries"],
    "fuel": ["Fuel"], "petrol": ["Fuel"], "gas": ["Fuel"],
    "clothes": ["Clothing"], "clothing": ["Clothing"],
    "health": ["Pharmacy", "Doctor", "Dentist", "Other health"],
    "rent": ["Housing"], "housing": ["Housing"], "utilities": ["Utilities"], "bills": ["Housing", "Utilities"],
    "transport": ["Public transport", "Taxi", "Fuel", "Parking"],
    "travel": ["Flights", "Hotels", "Travel agency", "Car rental", "Travel"],
    "holiday": ["Flights", "Hotels", "Travel agency", "Car rental", "Travel"],
    "sports": ["Gym & sports"], "gym": ["Gym & sports"],
}
_NIGHT_KEYS = {"night out", "nights out", "night_out", "going out", "night"}
_BASKET_KEYS = {
    "regular": "regular", "regular essentials": "regular", "essentials": "regular",
    "unexpected": "unexpected", "unexpected necessities": "unexpected",
    "everyday": "everyday", "everyday spending": "everyday", "savings": "savings",
}


# --------------------------------------------------------------------------- small helpers

def _d(s):
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])


def _r(x):
    return round(float(x or 0.0) + 0.0, 2)


def money(x, zero="nothing"):
    """Money in a sentence (house rule R1): whole euros from EUR 20 up, cents below, "nothing" for zero.

    The sign is dropped on purpose: word a negative in the sentence ("EUR 458 more than came in")."""
    v = round(abs(float(x or 0.0)), 2)
    if v == 0:
        return zero
    if v >= 20 or v == int(v):
        return "€{:,.0f}".format(v)
    return "€{:,.2f}".format(v)


def _eur(x):
    """An exact amount (a price, a payment, a total): whole euros from EUR 20, cents below."""
    return money(x)


def _eur0(x):
    """An estimate (per month, per day, a yearly pace): always whole euros, cents only below EUR 1."""
    v = round(abs(float(x or 0.0)), 2)
    if 0 < v < 1:
        return "€{:.2f}".format(v)
    return money(round(v))


_LABEL_WORDS = {
    "taxi": "taxis", "restaurant": "restaurants", "bar": "bars", "night out": "nights out",
    "dining out": "dining out", "gym & sports": "gym and sports", "cinema": "the cinema",
    "savings & investments": "savings and investments", "other": "other spending",
    "transfer out": "transfers out", "doctor": "doctor visits", "dentist": "dentist visits",
    "clothing": "clothes", "event": "events", "hobby": "hobbies",
}
_LABEL_TITLES = {"groceries": "Grocery", "gym & sports": "Gym and sports", "savings & investments": "Savings",
                 "night out": "Night out", "dining out": "Dining out"}


def label_words(label):
    """A category as a lower-case noun inside a sentence (house rule R9): "taxis", "fuel", "groceries"."""
    s = str(label or "").strip()
    return _LABEL_WORDS.get(s.lower(), s.lower())


def target_words(name):
    """A what-if or filter target as words: a basket name, "nights out" or a category noun."""
    k = str(name or "").strip().lower().replace("_", " ")
    if k in _NIGHT_KEYS:
        return "nights out"
    if k in _BASKET_KEYS:
        return BASKET_NAMES[_BASKET_KEYS[k]].lower()
    return label_words(name)


def label_title(label):
    """A category as an adjective at the start of a title: "Grocery purchases", "Fuel purchases"."""
    s = str(label or "").strip()
    return _LABEL_TITLES.get(s.lower(), s[:1].upper() + s[1:])


def higher_words(uplift_pct):
    """"about 40% higher", and from double upwards "more than double" / "about 3 times as high"."""
    try:
        r = 1.0 + float(uplift_pct) / 100.0
    except (TypeError, ValueError):
        return "higher"
    if r < 2.0:
        return "about %d%% higher" % round(float(uplift_pct))
    if r < 2.15:
        return "about double"
    if r < 3.0:
        return "more than double"
    return "about %d times as high" % round(r)


def ratio_words(value, base):
    """How `value` compares with `base` as words (house rule R3), to follow with the base figure.

    Below double it stays a percentage ("88% above"); from double it is worded."""
    try:
        r = float(value) / float(base)
    except (TypeError, ValueError, ZeroDivisionError):
        return "above"
    if r < 2.0:
        return "%d%% above" % round((r - 1) * 100)
    if r < 2.15:
        return "about double"
    if r < 3.0:
        return "more than double"
    return "about %d times" % round(r)


def _last_day(y, m):
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def _add_months(d, n):
    idx = d.year * 12 + (d.month - 1) + n
    y, m = divmod(idx, 12)
    m += 1
    return date(y, m, min(d.day, _last_day(y, m)))


def _month_start(d):
    return d.replace(day=1)


def _month_end(d):
    return d.replace(day=_last_day(d.year, d.month))


def _median(xs):
    xs = list(xs)
    return float(statistics.median(xs)) if xs else 0.0


def _one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def _scalar(conn, sql, params=(), default=0.0):
    row = conn.execute(sql, params).fetchone()
    if row is None or row[0] is None:
        return default
    return row[0]


def _ev(title, frm=None, to=None, **kw):
    out = {"title": title}
    if frm:
        out["from"] = frm
    if to:
        out["to"] = to
    for k, v in kw.items():
        if v is not None:
            out[k] = v
    return out


def _spend_filters(frm, to, when=None):
    """One evidence filter per spending basket; each title names its basket ("Regular essentials, August")."""
    return [_ev("%s, %s" % (BASKET_NAMES[b], when) if when else BASKET_NAMES[b], frm, to, basket=b)
            for b in SPEND_BASKETS]


def months_span(frm, to, today=None):
    """Whole months as words: "March to August" (one month: "August"); the year only when it is not this one."""
    try:
        a, b = _d(frm), _d(to)
    except (ValueError, TypeError):
        return "%s to %s" % (frm, to)
    first = human_month("%d-%02d" % (a.year, a.month), today)
    if (a.year, a.month) == (b.year, b.month):
        return first
    return "%s to %s" % (first, human_month("%d-%02d" % (b.year, b.month), today))


def _when(frm, to, today):
    """A period as a title suffix without a preposition: "August", "last 6 months", "21-24 Sep"."""
    try:
        t = _d(today)
        a, b = _d(frm), _d(to)
    except (ValueError, TypeError):
        return str(frm)
    if b == t and (b - a).days >= 50:
        return human_period(frm, to, today).replace("over the ", "")
    return human_range(a, b, today)


_MON_FULL = ["", "January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
_MON_SHORT = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def human_range(frm, to=None, today=None):
    """Human wording for a date or date range, for user-facing text only (machine fields stay ISO).

    A whole calendar month -> "August 2026"; within one month -> "21-24 Sep 2026";
    across months -> "1 Aug to 15 Sep 2026"; across years -> "28 Dec 2025 to 3 Jan 2026".
    With `today` the current year is left out ("August", "21-24 Sep"). For a sentence prefer
    human_period, which also picks the preposition and the relative wording."""
    try:
        a = _d(frm)
        b = _d(to) if to else a
        ty = _d(today).year if today else None
    except (ValueError, TypeError):
        return "%s to %s" % (frm, to) if to else str(frm)

    def yr(d):
        return "" if ty is not None and d.year == ty else " %d" % d.year
    if a == b:
        return "%d %s%s" % (a.day, _MON_SHORT[a.month], yr(a))
    if a.day == 1 and b == _month_end(a):
        return "%s%s" % (_MON_FULL[a.month], yr(a))
    if a.year == b.year and a.month == b.month:
        return "%d-%d %s%s" % (a.day, b.day, _MON_SHORT[a.month], yr(a))
    if a.year == b.year:
        return "%d %s to %d %s%s" % (a.day, _MON_SHORT[a.month], b.day, _MON_SHORT[b.month], yr(b))
    return "%d %s%s to %d %s%s" % (a.day, _MON_SHORT[a.month], yr(a), b.day, _MON_SHORT[b.month], yr(b))


def human_month(ym, today=None):
    """"2026-08" -> "August 2026" ("August" when `today` is given and it is the same year)."""
    try:
        y, m = int(str(ym)[:4]), int(str(ym)[5:7])
        name = _MON_FULL[m]
    except (ValueError, IndexError):
        return str(ym)
    try:
        if today and _d(today).year == y:
            return name
    except (ValueError, TypeError):
        pass
    return "%s %d" % (name, y)


def human_period(frm, to=None, today=None):
    """A period as a phrase for a sentence, preposition included (house rule R2).

    "in August", "last month", "this month so far", "over the last 4 months", "today", "yesterday",
    "on 25 Sep", "from 21 to 24 Sep". The current year is never written; other years are."""
    try:
        a = _d(frm)
        b = _d(to) if to else a
        t = _d(today) if today else None
    except (ValueError, TypeError):
        return "in " + human_range(frm, to)
    if t is not None:
        if a == b == t:
            return "today"
        if a == b == t - timedelta(days=1):
            return "yesterday"
        first = _month_start(t)
        if a == first and b == t and b < _month_end(t):
            return "this month so far"
        mon = t - timedelta(days=t.weekday())
        if a == mon and b == t and a != b:
            return "this week so far"
        if a == mon - timedelta(days=7) and b == mon - timedelta(days=1):
            return "last week"
        if a == date(t.year, 1, 1) and b == t and a != b:
            return "this year so far"
        days = (b - a).days + 1
        if b == t and days >= 50:
            n = max(2, int(round(days / DAYS_PER_MONTH)))
            return "over the last %d months" % n
    r = human_range(a, b, today)
    if a == b:
        return "on " + r
    if a.day == 1 and b == _month_end(a):
        return "in " + r
    return "from " + (r if " to " in r else r.replace("-", " to ", 1))


def _pct_text(x):
    return "{:.0f}%".format(100.0 * x)


# --------------------------------------------------------------------------- periods

def period(today, name):
    """Return (from, to) as ISO strings for a named period or a "YYYY-MM" month."""
    t = _d(today)
    key = str(name or "last_month").strip().lower().replace(" ", "_").replace("-", "_")
    mon = t - timedelta(days=t.weekday())
    if key == "today":
        a, b = t, t
    elif key == "yesterday":
        a = b = t - timedelta(days=1)
    elif key == "last_night":     # yesterday 18:00 up to today 06:00 (see period_ts)
        a, b = t - timedelta(days=1), t
    elif key == "this_week":
        a, b = mon, t
    elif key == "last_week":
        a, b = mon - timedelta(days=7), mon - timedelta(days=1)
    elif key in ("last_2_weeks", "last_two_weeks"):
        a, b = mon - timedelta(days=14), mon - timedelta(days=1)
    elif key == "this_month":
        a, b = _month_start(t), t
    elif key == "last_month":
        first = _add_months(_month_start(t), -1)
        a, b = first, _month_end(first)
    elif key in ("last_3_months", "last_6_months", "last_12_months"):
        n = int(key.split("_")[1])
        a, b = _add_months(t, -n) + timedelta(days=1), t
    elif key in ("ytd", "this_year", "year_to_date"):
        a, b = date(t.year, 1, 1), t
    elif re.fullmatch(r"\d{4}_\d{2}", key):
        first = date(int(key[:4]), int(key[5:7]), 1)
        a, b = first, min(_month_end(first), t)
        if b < a:
            b = a
    else:
        raise ValueError("unknown period: %s" % name)
    return a.isoformat(), b.isoformat()


def period_ts(today, name):
    """(ts_from, ts_to) for periods that are not whole days (`last_night`), else None.
    ts_from is inclusive and ts_to exclusive, both 'YYYY-MM-DD HH:MM:SS'."""
    key = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key != "last_night":
        return None
    t = _d(today)
    return ("%s 18:00:00" % (t - timedelta(days=1)).isoformat(), "%s 06:00:00" % t.isoformat())


def _resolve_period(today, p):
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return str(p[0]), str(p[1])
    return period(today, p)


def _month_list(conn, t, n):
    """Up to n full calendar months before the current month that the customer's data covers.
    Oldest first. Each item: (from, to) ISO strings."""
    first = _scalar(conn, "SELECT MIN(d) FROM tx", default=None)
    if first is None:
        return []
    fd = _d(first)
    cur = _month_start(t)
    out = []
    for i in range(n, 0, -1):
        ms = _add_months(cur, -i)
        if ms < _month_start(fd):
            continue
        if ms == _month_start(fd) and fd.day > 15:
            continue
        out.append((ms.isoformat(), _month_end(ms).isoformat()))
    return out


def _span(months):
    return (months[0][0], months[-1][1]) if months else (None, None)


# --------------------------------------------------------------------------- targets and filters

def _resolve_target(name):
    """Map a label / basket / "night_out" / friendly word to ('context'|'basket'|'labels', value)."""
    raw = str(name or "").strip()
    key = raw.lower().replace("_", " ")
    if key in _NIGHT_KEYS:
        return "context", "night_out"
    if key in _BASKET_KEYS:
        return "basket", _BASKET_KEYS[key]
    if key in _ALIASES:
        return "labels", list(_ALIASES[key])
    for v in _VOCAB:
        if v.lower() == key:
            return "labels", [v]
    if key.endswith("s") and key[:-1] in _ALIASES:
        return "labels", list(_ALIASES[key[:-1]])
    return "labels", [raw]


def _target_sql(target):
    kind, val = target
    if kind == "context":
        return "context='night_out'", ()
    if kind == "basket":
        return "basket=?", (val,)
    marks = ",".join("?" for _ in val)
    return "label COLLATE NOCASE IN (%s)" % marks, tuple(val)


def _target_filters(target, frm, to, title):
    kind, val = target
    if kind == "context":
        return [_ev(title, frm, to, context="night_out")]
    if kind == "basket":
        return [_ev(title, frm, to, basket=val)]
    return [_ev("%s (%s)" % (title, v) if len(val) > 1 else title, frm, to, label=v) for v in val]


def _target_matches(target, label, context, basket):
    kind, val = target
    if kind == "context":
        return context == "night_out"
    if kind == "basket":
        return basket == val
    return (label or "").lower() in [v.lower() for v in val]


def _disp_sql(label):
    return "%s = ?" % _DISP_SQL, (label,)


def _disp_evidence(label, frm, to, title=None):
    title = title or label
    if label == "Night out":
        return _ev(title, frm, to, context="night_out")
    return _ev(title, frm, to, label=label, context="none")


# --------------------------------------------------------------------------- transactions

def transactions(conn, today, frm=None, to=None, label=None, basket=None, context=None, type=None,
                 q=None, limit=50, ts_from=None, ts_to=None):
    where = ["d<=?"]
    params = [str(today)[:10]]
    if ts_from:
        where.append("ts>=?")
        params.append(str(ts_from)[:19])
    if ts_to:
        where.append("ts<?")
        params.append(str(ts_to)[:19])
    if frm:
        where.append("d>=?")
        params.append(str(frm)[:10])
    if to:
        where.append("d<=?")
        params.append(str(to)[:10])
    if label:
        sql, p = _target_sql(_resolve_target(label))
        where.append(sql)
        params.extend(p)
    if basket:
        b = _BASKET_KEYS.get(str(basket).lower(), str(basket).lower())
        where.append("basket=?")
        params.append(b)
    if context is not None and str(context) != "":
        c = str(context).lower()
        if c in ("none", "not_night_out", "normal"):
            where.append("(context IS NULL OR context='')")
        else:
            where.append("context=?")
            params.append(c)
    if type:
        where.append("type=?")
        params.append(str(type))
    if q:
        where.append("(merchant LIKE ? OR label LIKE ? OR category LIKE ?)")
        like = "%" + str(q) + "%"
        params.extend([like, like, like])
    wsql = " AND ".join(where)
    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        limit = 50
    agg = _one(conn, "SELECT COUNT(*), COALESCE(SUM(amount),0), "
                     "COALESCE(-SUM(CASE WHEN amount<0 THEN amount END),0) FROM tx WHERE " + wsql, params)
    rows = conn.execute(
        "SELECT d, ts, amount, label, basket, context, category, merchant, %s, id FROM tx WHERE %s "
        "ORDER BY ts DESC, rowid DESC LIMIT ?" % (_DISP_SQL, wsql), params + [limit]).fetchall()
    out = [{"d": r[0], "ts": r[1], "amount": _r(r[2]), "label": r[3], "basket": r[4],
            "context": r[5] or "", "category": r[6], "merchant": r[7], "display_label": r[8],
            "id": r[9]}
           for r in rows]
    return {"count": int(agg[0]), "total": _r(agg[1]), "spent": _r(agg[2]), "rows": out,
            "truncated": int(agg[0]) > len(out)}


# --------------------------------------------------------------------------- core aggregates

def _by_display(conn, frm, to, group="display"):
    col = _DISP_SQL if group == "display" else "COALESCE(NULLIF(label,''),'Other')"
    rows = conn.execute(
        "SELECT %s AS lab, -SUM(amount), COUNT(*) FROM tx WHERE %s AND d>=? AND d<=? "
        "GROUP BY lab ORDER BY -SUM(amount) DESC, lab" % (col, _SPEND_SQL), (frm, to)).fetchall()
    return [{"label": r[0], "total": _r(r[1]), "count": int(r[2])} for r in rows]


def _flows(conn, frm, to):
    """Income, spending baskets, net savings and surplus in a date range."""
    base = {}
    for b in SPEND_BASKETS:
        base[b] = _r(_scalar(conn, "SELECT -SUM(amount) FROM tx WHERE basket=? AND d>=? AND d<=?",
                             (b, frm, to)))
    income = _scalar(conn, "SELECT SUM(amount) FROM tx WHERE type IN ('salary','other_income') "
                           "AND d>=? AND d<=?", (frm, to))
    deposits = _scalar(conn, "SELECT -SUM(amount) FROM tx WHERE type='investment_deposit' "
                             "AND d>=? AND d<=?", (frm, to))
    withdrawals = _scalar(conn, "SELECT SUM(amount) FROM tx WHERE type='investment_withdrawal' "
                                "AND d>=? AND d<=?", (frm, to))
    spent = base["regular"] + base["unexpected"] + base["everyday"]
    net_saved = deposits - withdrawals
    return {
        "income": _r(income), "spent": _r(spent), "saved": _r(net_saved),
        "baskets": {"regular": base["regular"], "unexpected": base["unexpected"],
                    "everyday": base["everyday"], "savings": _r(deposits)},
        "surplus": _r(income - spent - net_saved),
        "kept": _r(income - spent),
    }


def _avg_flows(conn, months):
    """Monthly averages of _flows over the given month list (zeros when empty)."""
    n = len(months)
    keys = ("income", "spent", "saved", "surplus", "kept")
    tot = {k: 0.0 for k in keys}
    bk = {k: 0.0 for k in ("regular", "unexpected", "everyday", "savings")}
    for a, b in months:
        f = _flows(conn, a, b)
        for k in keys:
            tot[k] += f[k]
        for k in bk:
            bk[k] += f["baskets"][k]
    div = n or 1
    out = {k: _r(v / div) for k, v in tot.items()}
    out["baskets"] = {k: _r(v / div) for k, v in bk.items()}
    out["months"] = n
    return out


def _avg_display_map(conn, months, group="display"):
    """Average monthly spend per label over the months. Returns dict label -> avg."""
    if not months:
        return {}
    frm, to = _span(months)
    col = _DISP_SQL if group == "display" else "COALESCE(NULLIF(label,''),'Other')"
    parts = " OR ".join("(d>=? AND d<=?)" for _ in months)
    params = [x for m in months for x in m]
    rows = conn.execute("SELECT %s, -SUM(amount) FROM tx WHERE %s AND (%s) GROUP BY 1"
                        % (col, _SPEND_SQL, parts), params).fetchall()
    return {r[0]: float(r[1]) / len(months) for r in rows}


def _avg_display_map_basket(conn, months, basket):
    if not months:
        return {}
    parts = " OR ".join("(d>=? AND d<=?)" for _ in months)
    rows = conn.execute("SELECT %s, -SUM(amount) FROM tx WHERE basket=? AND (%s) GROUP BY 1" % (_DISP_SQL, parts),
                        [basket] + [x for m in months for x in m]).fetchall()
    return {r[0]: float(r[1]) / len(months) for r in rows}


def _avg_where(conn, months, where, params=()):
    """Average monthly spend over months for rows matching an extra SQL condition."""
    if not months:
        return 0.0
    parts = " OR ".join("(d>=? AND d<=?)" for _ in months)
    allp = list(params) + [x for m in months for x in m]
    v = _scalar(conn, "SELECT -SUM(amount) FROM tx WHERE %s AND %s AND (%s)" % (_SPEND_SQL, where, parts), allp)
    return float(v) / len(months)


def _balance(conn):
    row = _one(conn, "SELECT balance FROM tx ORDER BY ts DESC, rowid DESC LIMIT 1")
    return float(row[0]) if row and row[0] is not None else 0.0


def _rules_text():
    # Always short: one sentence per basket (the classify text may be longer).
    return ("Regular essentials are the bills and basics you need every month, like housing, utilities and groceries. "
            "Unexpected necessities are costs you cannot plan or often cannot skip, like doctor, dentist and other health costs, home repairs, and bigger electronics or furniture. "
            "Everyday spending is everything else you choose to buy.")


# --------------------------------------------------------------------------- spend

def spend(conn, today, period="last_month", label=None, basket=None, context=None,
          ts_from=None, ts_to=None):
    frm, to = _resolve_period(today, period)
    if ts_from is None and ts_to is None and isinstance(period, str):
        pts = period_ts(today, period)
        if pts:
            ts_from, ts_to = pts
    where, params = "", []
    if ts_from:
        where += " AND ts>=?"
        params.append(str(ts_from)[:19])
    if ts_to:
        where += " AND ts<?"
        params.append(str(ts_to)[:19])
    target = None
    if label:
        target = _resolve_target(label)
        sql, p = _target_sql(target)
        where += " AND " + sql
        params += list(p)
    if basket:
        where += " AND basket=?"
        params.append(_BASKET_KEYS.get(str(basket).lower(), str(basket).lower()))
    if context:
        c = str(context).lower()
        if c in ("none", "not_night_out"):
            where += " AND (context IS NULL OR context='')"
        else:
            where += " AND context=?"
            params.append(c)
    # a basket filter of 'savings' must be allowed to see savings rows
    base_sql = _SPEND_SQL
    if basket and str(basket).lower() in ("savings",):
        base_sql = "basket='savings'"
    row = _one(conn, "SELECT COALESCE(-SUM(amount),0), COUNT(*) FROM tx WHERE %s AND d>=? AND d<=? %s"
               % (base_sql, where), [frm, to] + params)
    total, count = float(row[0]), int(row[1])
    group = "raw" if (target and target[0] == "labels") else "display"
    col = _DISP_SQL if group == "display" else "COALESCE(NULLIF(label,''),'Other')"
    rows = conn.execute(
        "SELECT %s AS lab, -SUM(amount), COUNT(*) FROM tx WHERE %s AND d>=? AND d<=? %s GROUP BY lab "
        "ORDER BY -SUM(amount) DESC, lab" % (col, base_sql, where), [frm, to] + params).fetchall()
    by_label = [{"label": r[0], "total": _r(r[1]), "count": int(r[2])} for r in rows]

    nice = (str(label) if label else "everything")
    if label:
        names = target[1] if target[0] == "labels" else [str(label)]
        nice = " + ".join(names) if target[0] == "labels" else str(label)
    night = None
    note = ""
    if target and target[0] == "labels" and any(v in NIGHT_LABELS for v in target[1]):
        nr = _one(conn, "SELECT COALESCE(-SUM(amount),0), COUNT(*) FROM tx WHERE %s AND d>=? AND d<=? "
                        "AND context='night_out' %s" % (base_sql, where), [frm, to] + params)
        night = {"total": _r(nr[0]), "count": int(nr[1])}
        if night["count"]:
            note = " %s of this was on a night out." % _eur(night["total"])
    if label:
        evidence = _target_filters(target, frm, to, "%s purchases" % label_title(str(label)))
        if basket:
            for e in evidence:
                e["basket"] = str(basket).lower()
    elif basket:
        evidence = [_ev("%s spending" % BASKET_NAMES.get(str(basket).lower(), basket), frm, to,
                        basket=str(basket).lower())]
    else:
        evidence = _spend_filters(frm, to, _when(frm, to, today))
    if context and str(context).lower() == "night_out" and not label:
        evidence = [_ev("Night out spending", frm, to, context="night_out")]
    if ts_from or ts_to:
        for e in evidence:
            if ts_from:
                e["ts_from"] = str(ts_from)[:19]
            if ts_to:
                e["ts_to"] = str(ts_to)[:19]
    last_night = isinstance(period, str) and period.strip().lower().replace(" ", "_") == "last_night"
    if last_night:
        for e in evidence:
            e["title"] = "%s, last night" % (label_words(label).capitalize() if label else e["title"])
    when = "last night" if last_night else human_period(frm, to, today)
    if count == 0:
        explain = "No matching spending %s." % when
    else:
        what = label_words(label) if label else "everything"
        explain = "Added up %d outgoing payment%s for %s %s.%s" % (
            count, "" if count == 1 else "s", what, when, note)
    res = {"period": {"from": frm, "to": to, "name": period if isinstance(period, str) else "custom"},
           "total": _r(total), "count": count, "by_label": by_label, "evidence": evidence,
           "explain": explain}
    if night is not None:
        res["night_out_part"] = night
    return res


# --------------------------------------------------------------------------- overview and baskets

def overview(conn, today, month=None):
    t = _d(today)
    frm, to = period(today, month or "last_month")
    f = _flows(conn, frm, to)
    spent = f["spent"]
    prev = _month_list(conn, _month_start(_d(frm)), 6)
    avg = _avg_flows(conn, prev)
    labels = _by_display(conn, frm, to)
    top = [{"label": x["label"], "total": x["total"], "count": x["count"],
            "share": _r(x["total"] / spent) if spent else 0.0,
            "evidence": _disp_evidence(x["label"], frm, to)} for x in labels[:5]]
    vs = {}
    for k in ("regular", "unexpected", "everyday"):
        vs[k] = {"this": f["baskets"][k], "average": avg["baskets"][k],
                 "diff": _r(f["baskets"][k] - avg["baskets"][k])}
    vs["spent"] = {"this": spent, "average": avg["spent"], "diff": _r(spent - avg["spent"])}
    vs["months_in_average"] = avg["months"]
    mname = human_month(frm[:7], today)
    evidence = _spend_filters(frm, to, mname)
    evidence.append(_ev("Income, %s" % mname, frm, to, type="salary"))
    if not _scalar(conn, "SELECT COUNT(*) FROM tx WHERE d>=? AND d<=?", (frm, to)):
        explain = "There are no transactions in %s." % mname
    else:
        saved_part = " and %s put into savings" % _eur(f["saved"]) if f["saved"] > 0.005 else ""
        if f["surplus"] >= 0:
            left = "leaves %s" % _eur(f["surplus"]) if f["surplus"] > 0.005 else "leaves nothing"
        else:
            left = "leaves you %s short" % _eur(f["surplus"])
        explain = ("Income %s minus spending %s%s %s for %s. Spending is the regular, unexpected and "
                   "everyday baskets together." % (_eur(f["income"]), _eur(spent), saved_part, left, mname))
    return {"month": frm[:7], "period": {"from": frm, "to": to}, "income": f["income"],
            "baskets": f["baskets"], "spent": spent, "saved": f["saved"], "surplus": f["surplus"],
            "top_labels": top, "vs_average": vs, "evidence": evidence, "explain": explain}


def baskets(conn, today, period="last_month"):
    frm, to = _resolve_period(today, period)
    f = _flows(conn, frm, to)
    totals = dict(f["baskets"])
    denom = sum(totals.values())
    out = []
    for key in ("regular", "unexpected", "everyday", "savings"):
        sql_b = "basket=?"
        rows = conn.execute(
            "SELECT %s AS lab, ABS(SUM(amount)) FROM tx WHERE %s AND d>=? AND d<=? GROUP BY lab "
            "ORDER BY ABS(SUM(amount)) DESC, lab LIMIT 5" % (_DISP_SQL, sql_b), (key, frm, to)).fetchall()
        out.append({"key": key, "name": BASKET_NAMES[key], "total": _r(totals[key]),
                    "share": _r(totals[key] / denom) if denom else 0.0,
                    "top": [{"label": r[0], "total": _r(r[1])} for r in rows],
                    "evidence": _ev("%s, %s" % (BASKET_NAMES[key], _when(frm, to, today)), frm, to, basket=key)})
    explain = ("Every outgoing payment %s is placed in exactly one basket by fixed rules; "
               "shares are of the %s that went out in total." % (human_period(frm, to, today), _eur(denom)))
    if not denom:
        explain = "No outgoing payments %s." % human_period(frm, to, today)
    return {"period": {"from": frm, "to": to}, "baskets": out, "rules": _rules_text(),
            "explain": explain, "evidence": [b["evidence"] for b in out]}


# --------------------------------------------------------------------------- safe to spend

def _usual_payday(conn, t):
    """'eom', a day of month (int), or None when no salary has been seen.

    The most common day over the last 12 months of salaries (all of them when there are none that
    recent). Month end wins only when MORE THAN HALF of the salaries came in the last four days of a
    month; otherwise it is the most common ordinary day (a customer paid on the 15th in 18 of 24
    months is "the 15th", even when the last two salaries came at month end). When that day has passed
    and the salary has not come, `_next_payday` expects it at month end, see there."""
    since = _add_months(t, -12).isoformat()
    rows = conn.execute("SELECT d FROM tx WHERE type='salary' AND d>=? AND d<=? ORDER BY d",
                        (since, t.isoformat())).fetchall()
    if not rows:
        rows = conn.execute("SELECT d FROM tx WHERE type='salary' AND d<=? ORDER BY d",
                            (t.isoformat(),)).fetchall()
    if not rows:
        return None
    ds = [_d(r[0]) for r in rows]
    eom = sum(1 for x in ds if x.day >= _last_day(x.year, x.month) - 3)
    cnt = Counter(x.day for x in ds if x.day < _last_day(x.year, x.month) - 3)
    if eom * 2 > len(ds) or not cnt:
        return "eom"
    return sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _payday_on(y, m, pay):
    last = _last_day(y, m)
    return date(y, m, last if pay == "eom" else min(pay, last))


def _next_payday(t, pay, conn=None):
    """Next payday after t. With `conn`: a salary already received this month moves it to next month,
    and when the usual day has passed without salary the pay is expected at the end of this month
    (pay comes late now and then, almost never a whole month late)."""
    cand = _payday_on(t.year, t.month, pay)
    paid = conn is not None and _scalar(conn, "SELECT COUNT(*) FROM tx WHERE type='salary' AND d>=? AND d<=?",
                                        (_month_start(t).isoformat(), t.isoformat()), default=0) > 0
    if conn is not None and not paid and pay != "eom" and cand <= t:
        eom = _payday_on(t.year, t.month, "eom")
        if eom > t:
            return eom
    if cand <= t or paid:
        nm = _add_months(_month_start(t), 1)
        cand = _payday_on(nm.year, nm.month, pay)
    return cand


def _payday_latest(nxt, pay):
    """The latest likely date for a payday that is a day of month: the end of that month; else None."""
    if nxt is None or pay in (None, "eom"):
        return None
    last = _payday_on(nxt.year, nxt.month, "eom")
    return last if last > nxt else None


def _expected_events(conn, t, where, months, win_end):
    """Predict payments of a recurring kind (rows matching `where`) due in [t, win_end).
    Uses the usual count per month, median amount and median day of month from `months`."""
    if not months:
        return []
    per = {}
    for a, b in months:
        rows = conn.execute("SELECT d, -amount FROM tx WHERE %s AND d>=? AND d<=? ORDER BY d" % where,
                            (a, b)).fetchall()
        per[a[:7]] = [(_d(r[0]).day, float(r[1])) for r in rows]
    counts = [len(per[a[:7]]) for a, _ in months]
    c = int(round(_median(counts)))
    need = 2 if len(months) >= 2 else 1
    series = []
    for k in range(c):
        picks = [lst[k] for lst in per.values() if len(lst) > k]
        if len(picks) < need:
            continue
        series.append((int(round(_median(p[0] for p in picks))), _median(p[1] for p in picks)))
    paid_now = _scalar(conn, "SELECT COUNT(*) FROM tx WHERE %s AND d>=? AND d<=?" % where,
                       (_month_start(t).isoformat(), t.isoformat()), default=0)
    events = []
    cur = _month_start(t)
    while cur <= win_end:
        for k, (day, amt) in enumerate(series):
            due = date(cur.year, cur.month, min(day, _last_day(cur.year, cur.month)))
            if cur == _month_start(t) and k < paid_now:
                continue
            if due < t:
                if cur != _month_start(t):
                    continue
                due = t          # late this month and not paid yet: still expected (MAJ-1)
            if due >= win_end:
                continue
            events.append({"expected": _r(amt), "due": due.isoformat()})
        cur = _add_months(cur, 1)
    events.sort(key=lambda e: e["due"])
    return events


def safe_to_spend(conn, today, monthly_saving_target=0):
    t = _d(today)
    balance = _balance(conn)
    pay = _usual_payday(conn, t)
    if pay is None:
        nxt = None
        win_end = t + timedelta(days=30)
        days_left = 30
    else:
        nxt = _next_payday(t, pay, conn)
        win_end = nxt
        days_left = max(1, (nxt - t).days)
    m3 = _month_list(conn, t, 3)
    bills = []
    for lab, typ in (("Housing", "housing_payment"), ("Utilities", "utilities_payment")):
        for e in _expected_events(conn, t, "type='%s'" % typ, m3, win_end):
            bills.append({"label": lab, "expected": e["expected"], "due": e["due"]})
    bills.sort(key=lambda b: (b["due"], b["label"]))
    bills_total = sum(b["expected"] for b in bills)

    m12 = _month_list(conn, t, 12)
    unexpected_avg = _avg_where(conn, m12, "basket='unexpected'")
    buffer = unexpected_avg * days_left / 30.0

    m6 = _month_list(conn, t, 6)
    dep_events = _expected_events(conn, t, "type='investment_deposit'", m6, win_end)
    planned_dep = sum(e["expected"] for e in dep_events)
    try:
        target_part = max(0.0, float(monthly_saving_target or 0)) * days_left / 30.0
    except (TypeError, ValueError):
        target_part = 0.0
    planned = planned_dep + target_part

    safe_total = balance - bills_total - buffer - planned
    per_day = safe_total / days_left
    per_week = per_day * 7
    if safe_total < 0:
        status = "over"
    elif per_day < 10:
        status = "tight"
    else:
        status = "ok"
    ev = [_ev("Latest transactions", None, None)]
    ev[0]["from"] = (t - timedelta(days=14)).isoformat()
    ev[0]["to"] = t.isoformat()
    bs, be = _span(m3)
    if bs:
        ev.append(_ev("Past housing payments", bs, be, type="housing_payment"))
        ev.append(_ev("Past utilities payments", bs, be, type="utilities_payment"))
    if m12:
        ev.append(_ev("Unexpected necessities, last 12 months", m12[0][0], m12[-1][1], basket="unexpected"))
    if m6 and planned_dep:
        ev.append(_ev("Past investment deposits", m6[0][0], m6[-1][1], type="investment_deposit"))
    working = [
        "Balance now: %s" % _eur(balance),
        "minus regular bills before payday: %s" % _eur(bills_total),
        "minus buffer for unexpected necessities: %s" % _eur0(buffer),
        "minus planned savings: %s" % _eur(planned),
        "equals safe to spend: %s over %d days" % (_eur(safe_total), days_left),
    ]
    plan_part = " and %s of planned savings" % _eur(planned) if planned > 0.005 else ""
    if safe_total >= 0:
        result_part = "leaves %s" % _eur(safe_total) if safe_total > 0.005 else "leaves nothing"
    else:
        result_part = "leaves you %s short" % _eur(safe_total)
    explain = ("Your balance %s minus %s of bills expected before payday%s, minus a %s buffer for unexpected "
               "necessities%s %s for %d days." % (
                   _eur(balance), _eur(bills_total),
                   " on %s" % human_range(nxt, None, today) if nxt else " (no payday seen, assuming 30 days)",
                   _eur0(buffer), plan_part, result_part, days_left))
    return {
        "balance": _r(balance), "next_payday": nxt.isoformat() if nxt else None, "days_left": days_left,
        "upcoming_bills": bills, "bills_total": _r(bills_total), "unexpected_buffer": _r(buffer),
        "planned_savings": _r(planned), "safe_total": _r(safe_total), "per_day": _r(per_day),
        "per_week": _r(per_week), "status": status, "working": working,
        "payday_may_be_late_days": (lambda x: (x - nxt).days if x else 0)(_payday_latest(nxt, pay)),
        "evidence": ev, "explain": explain,
    }


# --------------------------------------------------------------------------- what if

def _norm_pct(p):
    """A percentage is a percentage: 0.5 means half a percent. A cut is 0..100; an increase is negative
    (-20 = spend 20% more, -100 = double), down to -1000. Anything else is an error."""
    try:
        p = float(p)
    except (TypeError, ValueError):
        return 0.0
    if p != p or p < -1000 or p > 100:
        raise ValueError("pct must be between -1000 and 100")
    return p


def what_if(conn, today, changes, months=12):
    t = _d(today)
    try:
        months = max(1, int(months))
    except (TypeError, ValueError):
        months = 12
    ms = _month_list(conn, t, 6)
    n = len(ms)
    parsed = []
    for c in (changes or []):
        if not isinstance(c, dict):
            continue
        name = str(c.get("target", "")).strip()
        if not name:
            continue
        parsed.append((name, _resolve_target(name), _norm_pct(c.get("pct", 0))))
    base = [0.0] * len(parsed)
    saved = [0.0] * len(parsed)
    union_base = 0.0
    union_saved = 0.0
    if n and parsed:
        parts = " OR ".join("(d>=? AND d<=?)" for _ in ms)
        rows = conn.execute("SELECT -amount, label, context, basket FROM tx WHERE %s AND (%s)"
                            % (_SPEND_SQL, parts), [x for m in ms for x in m]).fetchall()
        for amt, lab, ctx, bsk in rows:
            hit = [i for i, (_, tg, _p) in enumerate(parsed) if _target_matches(tg, lab, ctx, bsk)]
            if not hit:
                continue
            union_base += amt
            union_saved += amt * max(parsed[i][2] for i in hit) / 100.0
            for i in hit:
                base[i] += amt
                saved[i] += amt * parsed[i][2] / 100.0
    div = n or 1
    lines = []
    evidence = []
    frm, to = _span(ms)
    for i, (name, tg, pct) in enumerate(parsed):
        b, s = base[i] / div, saved[i] / div
        lines.append({"target": name, "pct": _r(pct), "baseline": _r(b), "new": _r(b - s), "saved": _r(s)})
        if frm:
            evidence.extend(_target_filters(tg, frm, to, "%s, last %d months" % (
                target_words(name).capitalize(), n)))
    ub, us = union_base / div, union_saved / div
    saved_monthly = _r(us)
    if not n:
        explain = "Not enough past months to work out a monthly average, so nothing to simulate."
    elif not parsed:
        explain = "No changes were given, so nothing was simulated."
    else:
        groups = []
        for l in lines:        # neighbouring cuts of the same size read as one ("restaurants and fast food by 20%")
            if groups and groups[-1][0] == l["pct"]:
                groups[-1][1].append(target_words(l["target"]))
            else:
                groups.append((l["pct"], [target_words(l["target"])]))
        desc = ", ".join("%s by %s%%" % (" and ".join(names), "%g" % abs(pct)) for pct, names in groups)
        over = "a year" if months == 12 else "over %d months" % months
        if us < 0:
            explain = ("Based on your last %d full months (%s), spending more on %s would cost about %s more a "
                       "month, %s %s." % (n, months_span(frm, to, today), desc, _eur0(-saved_monthly),
                                          _eur0(-us * months), over))
        else:
            explain = ("Based on your last %d full months (%s), cutting %s would save about %s a month, %s %s." % (
                n, months_span(frm, to, today), desc, _eur0(saved_monthly), _eur0(us * months), over))
    return {"baseline_monthly": _r(ub), "new_monthly": _r(ub - us), "saved_monthly": saved_monthly,
            "saved_total": _r(us * months), "months": months, "lines": lines,
            "direction": "increase" if us < 0 else "cut",
            "evidence": evidence, "explain": explain}


# --------------------------------------------------------------------------- spender type

_SOCIAL = ("Night out", "Restaurant", "Fast food", "Bar", "Events", "Cinema", "Entertainment")
_TRAVEL = ("Flights", "Hotels", "Travel agency", "Car rental", "Travel")
_HOME = ("Groceries", "Home improvement", "Furniture", "Electronics")


def _kept_text(kept):
    """What is left each month, worded so a negative never needs a minus sign."""
    if kept > 0.005:
        return "You keep about %s a month after spending." % _eur0(kept)
    if kept < -0.005:
        return "You spend about %s a month more than you earn." % _eur0(kept)
    return "You keep nothing a month after spending."


def spender_type(conn, today):
    t = _d(today)
    ms = _month_list(conn, t, 6)
    frm, to = _span(ms)
    avg = _avg_flows(conn, ms)
    lab = _avg_display_map(conn, ms)
    income = avg["income"]
    if not ms or income <= 0:
        return {"type": "Not enough data", "title": "Not enough data yet",
                "summary": "There is not enough income history in the last six months to describe a spending style.",
                "traits": [], "shares": {}, "evidence": [],
                "explain": "A spender type needs at least one full month with income."}
    social = sum(lab.get(k, 0.0) for k in _SOCIAL) / income
    travel = sum(lab.get(k, 0.0) for k in _TRAVEL) / income
    home = sum(lab.get(k, 0.0) for k in _HOME) / income
    groceries = lab.get("Groceries", 0.0) / income
    housing = lab.get("Housing", 0.0) / income
    spent_share = avg["spent"] / income
    kept_share = avg["kept"] / income
    saved_share = avg["saved"] / income
    shares = {"spent": _r(spent_share), "kept": _r(kept_share), "saved_invested": _r(saved_share),
              "housing": _r(housing), "groceries": _r(groceries), "social": _r(social),
              "travel": _r(travel), "home": _r(home)}
    if spent_share >= 0.97:
        typ, title = "Stretched", "Stretched: spending takes nearly all of your income"
        why = "you spent %s of your income" % _pct_text(spent_share)
    elif kept_share >= 0.20:
        typ, title = "Saver", "Saver: you keep a good share of what you earn"
        why = "you kept %s of your income (saved, invested or left over)" % _pct_text(kept_share)
    elif social >= 0.12:
        typ, title = "Social spender", "Social spender: eating out and nights out stand out"
        why = "restaurants, bars, nights out and events took %s of your income" % _pct_text(social)
    elif travel >= 0.08:
        typ, title = "Explorer", "Explorer: travel is a big part of your spending"
        why = "flights, hotels and other travel took %s of your income" % _pct_text(travel)
    elif home >= 0.22:
        typ, title = "Home-maker", "Home-maker: your money goes to home and groceries"
        why = "groceries and home items took %s of your income" % _pct_text(home)
    else:
        typ, title = "Balanced", "Balanced: no single area dominates"
        why = "no area was unusually large (you kept %s, social spending %s)" % (
            _pct_text(kept_share), _pct_text(social))
    summary = "Over the last %d months %s." % (len(ms), why)
    traits = [
        {"name": "Kept after spending", "value": _r(100 * kept_share), "note": "Kept"},
        {"name": "Social spending", "value": _r(100 * social), "note": "Going out"},
        {"name": "Housing", "value": _r(100 * housing), "note": "Housing"},
        {"name": "Groceries", "value": _r(100 * groceries), "note": "Groceries"},
        {"name": "Travel", "value": _r(100 * travel), "note": "Travel"},
    ]
    evidence = _spend_filters(frm, to, "last %d months" % len(ms))
    explain = ("Compared your average monthly spending in each area with your average monthly income of %s "
               "over the last %d full months (%s). %s Rules, checked in "
               "order: Stretched if spending is 97%% of income or more, Saver if you keep 20%% or more, Social "
               "spender if social spending is 12%% or more, Explorer if travel is 8%% or more, Home-maker if "
               "groceries and home items are 22%% or more, otherwise Balanced." % (
                   _eur(income), len(ms), months_span(frm, to, today), _kept_text(avg["kept"])))
    return {"type": typ, "title": title, "summary": summary, "traits": traits, "shares": shares,
            "why": why, "months": len(ms), "evidence": evidence, "explain": explain}


# --------------------------------------------------------------------------- save more

def save_more(conn, today):
    t = _d(today)
    ms = _month_list(conn, t, 6)
    frm, to = _span(ms)
    if not ms:
        return {"ideas": [], "surplus_avg": 0.0, "evidence": [],
                "explain": "There is not enough history to suggest savings yet."}
    avg = _avg_flows(conn, ms)
    lab = _avg_display_map(conn, ms)
    ideas = []
    night = lab.get("Night out", 0.0)
    if night >= 5:
        s = night * 0.25
        ideas.append({"title": "Trim nights out by a quarter",
                      "detail": ("You spend about %s a month on nights out (bar, food and taxi together). "
                                 "A quarter less is %s a month." % (_eur0(night), _eur0(s))),
                      "saved_monthly": _r(s), "target": "night_out",
                      "evidence": _ev("Nights out", frm, to, context="night_out")})
    eat = lab.get("Restaurant", 0.0) + lab.get("Fast food", 0.0)
    groc = lab.get("Groceries", 0.0)
    if eat >= 10:
        s = eat * 0.2
        ratio = " (groceries: %s a month)" % _eur0(groc) if groc else ""
        ideas.append({"title": "Cook at home one meal in five",
                      "detail": ("Restaurants and fast food outside nights out cost you about %s a month%s. "
                                 "Replacing one in five of those meals with home cooking saves up to %s a "
                                 "month." % (_eur0(eat), ratio, _eur0(s))),
                      "saved_monthly": _r(s), "target": "Restaurant",
                      "evidence": [_ev("Restaurants", frm, to, label="Restaurant", context="none"),
                                   _ev("Fast food", frm, to, label="Fast food", context="none")]})
    everyday_avg = avg["baskets"]["everyday"]
    if everyday_avg >= 20:
        s = everyday_avg * 0.05
        ideas.append({"title": "Trim everyday spending by 5%",
                      "detail": ("Everyday spending averages %s a month. A small 5%% trim across it is about "
                                 "%s a month, without giving up anything big." % (_eur0(everyday_avg), _eur0(s))),
                      "saved_monthly": _r(s), "target": "everyday",
                      "evidence": _ev("Everyday spending", frm, to, basket="everyday")})
    lab_every = _avg_display_map_basket(conn, ms, "everyday")
    top = [(k, v) for k, v in sorted(lab_every.items(), key=lambda kv: -kv[1])
           if k not in ("Housing", "Utilities", "Groceries", "Night out", "Restaurant", "Fast food", "Other",
                        "Transfer out", "Doctor", "Dentist", "Pharmacy", "Other health", "Public transport")]
    if top and top[0][1] >= 20:
        k, v = top[0]
        s = v * 0.15
        ideas.append({"title": "Spend 15%% less on %s" % label_words(k),
                      "detail": ("Your biggest flexible area after food and going out is %s, about %s a month. "
                                 "Cutting it by 15%% frees %s a month." % (label_words(k), _eur0(v), _eur0(s))),
                      "saved_monthly": _r(s), "target": k,
                      "evidence": _ev(k, frm, to, label=k)})
    surplus = avg["surplus"]
    if surplus >= 20:
        ideas.append({"title": "Move your leftover on payday",
                      "detail": ("Across the last %d months you kept about %s a month after spending and "
                                 "investing. Moving it to savings on payday, before it gets spent, puts it to "
                                 "work." % (len(ms), _eur0(surplus))),
                      "saved_monthly": _r(surplus), "target": "surplus",
                      "evidence": _ev("Income", frm, to, type="salary")})
    ideas.sort(key=lambda i: -i["saved_monthly"])
    ideas = ideas[:4]
    evidence = [i["evidence"] for i in ideas if isinstance(i["evidence"], dict)]
    for i in ideas:
        if isinstance(i["evidence"], list):
            evidence.extend(i["evidence"])
    if not ideas:
        explain = "Nothing stands out as easy to trim in the last %d months." % len(ms)
    else:
        explain = ("Each idea is a share of your own average monthly spend over the last %d full months "
                   "(%s); the ideas overlap, so do not add them together." % (len(ms), months_span(frm, to, today)))
    return {"ideas": ideas, "surplus_avg": _r(surplus), "evidence": evidence, "explain": explain}


# --------------------------------------------------------------------------- mortgage

_MORTGAGE_DISCLAIMER = (
    "This is a readiness check against the bank's lending rule as seen in the dataset, not a loan "
    "decision or a promise. A real decision depends on the bank's full assessment, your other loans, "
    "the property and the rates at the time.")


def _net_deposits(conn, t):
    dep = _scalar(conn, "SELECT -SUM(amount) FROM tx WHERE type='investment_deposit' AND d<=?", (t.isoformat(),))
    wd = _scalar(conn, "SELECT SUM(amount) FROM tx WHERE type='investment_withdrawal' AND d<=?", (t.isoformat(),))
    return float(dep) - float(wd)


def mortgage(conn, today, price=None, equity=None):
    t = _d(today)
    ms = _month_list(conn, t, 6)
    avg = _avg_flows(conn, ms)
    income = avg["income"]
    balance = _balance(conn)
    deposits = _net_deposits(conn, t)
    savings_now = balance + deposits
    monthly_saving = avg["kept"]       # average surplus plus deposits (income minus spending)
    max_loan = income / RATE_PER_EURO if income > 0 else 0.0
    max_price = max_loan / (1 - MIN_EQUITY)
    equity_needed = MIN_EQUITY * max_price
    gap = equity_needed - savings_now
    if gap <= 0:
        months_to = 0
    elif monthly_saving > 0:
        months_to = int(math.ceil(gap / monthly_saving))
    else:
        months_to = None
    check = None
    try:
        price = float(price) if price not in (None, "") else None
    except (TypeError, ValueError):
        price = None
    try:
        equity = float(equity) if equity not in (None, "") else None
    except (TypeError, ValueError):
        equity = None
    if price and price > 0:
        given = equity is not None
        eq = min(max(equity, 0.0), price) if given else MIN_EQUITY * price
        loan = price - eq
        req_income = loan * RATE_PER_EURO
        equity_ok = (eq >= MIN_EQUITY * price - 0.005) if given else (savings_now >= eq)
        check = {"price": _r(price), "loan": _r(loan), "ltv": _r(loan / price), "equity": _r(eq),
                 "equity_source": "given" if given else "15% of the price assumed",
                 "required_income": _r(req_income), "income_ok": income >= req_income,
                 "equity_ok": bool(equity_ok)}
    rule = "Assumes a 25-year loan, a 6% test rate and payments of at most 35% of income."
    ev = []
    if ms:
        ev = [_ev("Income, last %d months" % len(ms), ms[0][0], ms[-1][1], type="salary"),
              _ev("Other income", ms[0][0], ms[-1][1], type="other_income"),
              _ev("Investment deposits", None, None, type="investment_deposit")]
    if income <= 0:
        explain = "No income was seen in the last full months, so the rule cannot be applied."
    else:
        explain = ("Your average monthly income of %s supports a loan of up to %s under the rule, which is a "
                   "price of about %s with 15%% equity. Approved applicants in the dataset typically put in "
                   "15%% equity." % (_eur(income), _eur0(max_loan), _eur0(max_price)))
    return {"monthly_income": _r(income), "max_loan": _r(max_loan),
            "max_price_with_15pct_equity": _r(max_price), "equity_needed": _r(equity_needed),
            "account_balance": _r(balance),   # money in the account; savings_now adds net investment deposits
            "savings_now": _r(savings_now), "monthly_saving": _r(monthly_saving),
            "months_to_equity": months_to, "rule": rule, "check": check,
            "disclaimer": _MORTGAGE_DISCLAIMER, "evidence": ev, "explain": explain}


# --------------------------------------------------------------------------- quiz

def _b64(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode()).decode().rstrip("=")


def _unb64(s):
    pad = "=" * (-len(str(s)) % 4)
    return json.loads(base64.urlsafe_b64decode(str(s) + pad).decode())


# The quiz only asks about everyday spending the customer can steer. Never health, groceries,
# housing, utilities, fuel or pharmacy (D2).
_QUIZ_ALLOWED = ("Restaurant", "Fast food", "Bar", "Taxi", "Shopping", "Clothing", "Entertainment",
                 "Events", "Cinema", "Hobbies", "Dining out", "Night out")
_QUIZ_PHRASE = {"Restaurant": "restaurants", "Taxi": "taxis", "Night out": "nights out",
                "Fast food": "fast food", "Bar": "bars", "Dining out": "eating out",
                "Clothing": "clothes"}
_QUIZ_DINING = ("Restaurant", "Fast food")
_WEEKDAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _quiz_where(label):
    """(sql, params) selecting one quiz label; 'Dining out' is Restaurant + Fast food outside nights out."""
    if label == "Dining out":
        return ("label IN (?, ?) AND COALESCE(context,'')<>'night_out'", _QUIZ_DINING)
    return _disp_sql(label)


def _quiz_evidence(label, frm, to, today=None):
    title = "%s, %s" % (label_words(label).capitalize(), human_range(frm, to, today))
    if label == "Dining out":
        return [_ev("%s (%s)" % (title, label_words(v)), frm, to, label=v, context="none") for v in _QUIZ_DINING]
    return [_disp_evidence(label, frm, to, title)]


def _quiz_actual(conn, label, frm, to):
    sql, p = _quiz_where(label)
    return float(_scalar(conn, "SELECT -SUM(amount) FROM tx WHERE %s AND d>=? AND d<=? AND %s"
                         % (_SPEND_SQL, sql), [frm, to] + list(p)))


def _nice_ceil(x):
    step = 1 if x <= 50 else 5 if x <= 300 else 10 if x <= 1000 else 50
    return int(math.ceil(x / step) * step), step


def _weekly_avg(conn, label, t, weeks=12):
    mon = t - timedelta(days=t.weekday())
    frm = (mon - timedelta(days=7 * weeks)).isoformat()
    to = (mon - timedelta(days=1)).isoformat()
    return _quiz_actual(conn, label, frm, to) / weeks


def _usual_same_days(conn, label, week_start, days, weeks=8):
    """Average spending on `label` over the first `days` days of each of the `weeks` weeks before the
    week starting `week_start`: like with like for a week that is not finished (D14)."""
    ws = _d(week_start)
    total = 0.0
    for k in range(1, weeks + 1):
        a = ws - timedelta(days=7 * k)
        total += _quiz_actual(conn, label, a.isoformat(), (a + timedelta(days=days - 1)).isoformat())
    return total / weeks


def quiz(conn, today, seed=None):
    t = _d(today)
    chosen = None
    for pname in ("this_week", "last_week"):
        frm, to = period(today, pname)
        cands = sorted(x["label"] for x in _by_display(conn, frm, to)
                       if x["label"] in _QUIZ_ALLOWED and x["total"] > 0)
        if cands:
            key = str(seed) if seed is not None else str(today)
            idx = (abs(int(seed)) if isinstance(seed, (int, float)) and not isinstance(seed, bool)
                   else zlib.crc32(key.encode())) % len(cands)
            chosen = (cands[idx], frm, to, pname)
            break
    if chosen is None:
        # nothing steerable bought lately: ask about the steerable area this customer uses most
        frm, to = period(today, "last_week")
        best, best_v = "Restaurant", 0.0
        for lab in _QUIZ_ALLOWED:
            v = _weekly_avg(conn, lab, t)
            if v > best_v:
                best, best_v = lab, v
        chosen = (best, frm, to, "last_week")
    label, frm, to, pname = chosen
    actual = _quiz_actual(conn, label, frm, to)
    base = _weekly_avg(conn, label, t)
    mx, step = _nice_ceil(max(base * 3, actual * 1.25, 40))
    phrase = _QUIZ_PHRASE.get(label, label.lower())
    when = "this week" if pname == "this_week" else "last week"
    return {"quiz_id": _b64({"l": label, "f": frm, "t": to}), "label_or_context": label,
            "question": "How much do you think you spent on %s %s?" % (phrase, when),
            "period": {"from": frm, "to": to}, "min": 0, "max": mx, "step": step}


def quiz_answer(conn, today, quiz_id, guess, profile=None, bench_lookup=None):
    try:
        q = _unb64(quiz_id)
        label, frm, to = str(q["l"]), str(q["f"]), str(q["t"])
        date.fromisoformat(frm)
        date.fromisoformat(to)
    except Exception:
        raise ValueError("unknown quiz")
    try:
        guess = float(guess)
    except (TypeError, ValueError):
        raise ValueError("guess must be a number")
    t = _d(today)
    actual = _quiz_actual(conn, label, frm, to)
    diff = guess - actual
    tol = max(2.0, 0.10 * actual)
    ad = abs(diff)
    if ad <= tol:
        verdict = "Spot on! You were within %s." % _eur0(tol)
    elif ad <= max(5.0, 0.25 * actual):
        verdict = "Very close, only %s %s." % (_eur(ad), "too high" if diff > 0 else "too low")
    elif ad <= max(10.0, 0.5 * actual):
        verdict = "In the ballpark, %s %s." % (_eur(ad), "too high" if diff > 0 else "too low")
    else:
        verdict = "Quite far off: you guessed %s %s than the real figure." % (
            _eur0(ad), "more" if diff > 0 else "less")
    phrase_l = _QUIZ_PHRASE.get(label, label.lower())
    partial = t <= _d(to)          # the quiz week is not finished: compare like with like (D14)
    if partial:
        elapsed = max(1, (min(t, _d(to)) - _d(frm)).days + 1)
        base = _usual_same_days(conn, label, frm, elapsed)
        span = ("on Monday" if elapsed == 1 else
                "from Monday to %s" % _WEEKDAYS_LONG[(_d(frm) + timedelta(days=elapsed - 1)).weekday()])
        same = "your usual %s %s (average of the last 8 weeks)" % (_eur0(base), span)
        if base > 0 and actual > base * 1.2 and actual - base >= 3:
            tip = ("So far this week you have spent %s, which is %s more than %s. If the rest of the week "
                   "stays at your usual pace, you would end the week above your usual." % (
                       _eur0(actual), _eur0(actual - base), same))
        elif base > 0 and actual < base * 0.8:
            tip = ("So far this week you have spent %s, which is %s less than %s. It is early, but a good "
                   "start; staying near that pace would keep your %s down." % (
                       _eur0(actual), _eur0(base - actual), same, phrase_l))
        elif actual > 0 and base > 0:
            tip = "So far this week you have spent %s on %s, about the same as %s." % (
                _eur0(actual), phrase_l, same)
        elif actual > 0:
            tip = ("So far this week you have spent %s on %s; you usually spend nothing on it over the "
                   "same days." % (_eur0(actual), phrase_l))
        else:
            tip = "So far this week you have spent nothing on %s." % phrase_l
    else:
        base = _weekly_avg(conn, label, t)
        monthly = actual * 52 / 12.0
        if base > 0 and actual > base * 1.2 and actual - base >= 3:
            tip = ("That is %s more than your usual %s a week. If you matched your usual week, you would keep "
                   "about %s a month." % (_eur0(actual - base), _eur0(base), _eur0((actual - base) * 52 / 12.0)))
        elif base > 0 and actual < base * 0.8:
            tip = ("That is %s less than your usual %s a week, a good week. Keeping that up would save about %s "
                   "a month." % (_eur0(base - actual), _eur0(base), _eur0((base - actual) * 52 / 12.0)))
        elif actual > 0:
            tip = ("At this pace %s costs you about %s a month. Trimming it by a fifth would save about %s a "
                   "year." % (label_words(label), _eur0(monthly), _eur0(actual * 0.2 * 52)))
        else:
            tip = "You spent nothing on %s in this period. Tracking small categories like this is how patterns show up." % label_words(label)
    out = {"actual": _r(actual), "guess": _r(guess), "diff": _r(diff), "verdict": verdict, "tip": tip,
           "label_or_context": label, "period": {"from": frm, "to": to},
           "evidence": _quiz_evidence(label, frm, to, today)}
    if profile is not None and bench_lookup is not None:
        peer = peer_compare(actual, {"from": frm, "to": to},
                            list(_QUIZ_DINING) if label == "Dining out" else label, profile, bench_lookup)
        if peer:
            out["peer"] = peer
    return out


# --------------------------------------------------------------------------- check-in

def _buffer_info(conn, t):
    ms = _month_list(conn, t, 6)
    essentials = _avg_where(conn, ms, "basket='regular'")
    bal = _balance(conn)
    months = (bal / essentials) if essentials > 0 else None
    return bal, essentials, months


def _checkin_period(today, frequency):
    t = _d(today)
    mon = t - timedelta(days=t.weekday())
    if frequency == "weekly":
        return (mon - timedelta(days=7)).isoformat(), (mon - timedelta(days=1)).isoformat(), "last week"
    if frequency == "biweekly":
        return (mon - timedelta(days=14)).isoformat(), (mon - timedelta(days=1)).isoformat(), "the last two weeks"
    a, b = period(today, "last_month")
    return a, b, "last month"


def _surplus_when(frequency, frm, to, today=None):
    if frequency == "monthly":
        return "in %s" % human_month(str(frm)[:7], today)
    return human_period(frm, to, today)


def checkin(conn, today, frequency="monthly"):
    t = _d(today)
    if frequency not in ("weekly", "biweekly", "monthly"):
        frequency = "monthly"
    frm, to, word = _checkin_period(today, frequency)
    f = _flows(conn, frm, to)
    days = (_d(to) - _d(frm)).days + 1
    prev_to = (_d(frm) - timedelta(days=1)).isoformat()
    prev_frm = (_d(frm) - timedelta(days=days)).isoformat()
    prev_spent = _flows(conn, prev_frm, prev_to)["spent"]
    labels = _by_display(conn, frm, to)
    highlights = []
    if labels:
        highlights.append("Biggest area: %s, %s." % (labels[0]["label"], _eur(labels[0]["total"])))
    if prev_spent > 0 and f["spent"] > 0:
        d = f["spent"] - prev_spent
        highlights.append("You spent %s %s than in the period before." % (
            _eur0(abs(d)), "more" if d > 0 else "less"))
    big = _one(conn, "SELECT -amount, label, d FROM tx WHERE %s AND d>=? AND d<=? ORDER BY amount LIMIT 1"
               % _SPEND_SQL, (frm, to))
    if big and big[0] and big[0] >= 100 and big[1] not in ("Housing", "Utilities"):
        highlights.append("Largest single purchase: %s on %s (%s)." % (
            _eur0(big[0]), human_range(big[2], None, today), big[1]))
    nrow = _one(conn, "SELECT COALESCE(-SUM(amount),0), COUNT(*) FROM tx WHERE context='night_out' "
                      "AND d>=? AND d<=?", (frm, to))
    if nrow[1]:
        highlights.append("Nights out added up to %s." % _eur0(nrow[0]))
    adj = {"weekly": "weekly", "biweekly": "two-week", "monthly": "monthly"}[frequency]
    no_salary = (frequency != "monthly" and not _scalar(
        conn, "SELECT COUNT(*) FROM tx WHERE type='salary' AND d>=? AND d<=?", (frm, to), default=0))
    if no_salary:
        # D18: a short period without a payday is not a deficit; leave income out of the headline
        first = _scalar(conn, "SELECT MIN(d) FROM tx", default=None)
        windows = []
        for k in range(1, 9):
            wf, wt = _d(frm) - timedelta(days=days * k), _d(frm) - timedelta(days=days * (k - 1) + 1)
            if first and wf.isoformat() >= str(first):
                windows.append(_flows(conn, wf.isoformat(), wt.isoformat())["spent"])
        unit = "week" if frequency == "weekly" else "two weeks"
        if len(windows) >= 3:
            usual = sum(windows) / len(windows)
            gap = f["spent"] - usual
            if abs(gap) <= max(5.0, 0.1 * usual):
                cmp_text = "about your usual %s (%s)" % (unit, _eur0(usual))
            else:
                cmp_text = "%s %s than your usual %s (%s)" % (
                    _eur0(abs(gap)), "more" if gap > 0 else "less", unit, _eur0(usual))
            headline = "Your %s check-in (%s): you spent %s, %s. No salary arrived in this period." % (
                adj, _when(frm, to, today), _eur0(f["spent"]), cmp_text)
        else:
            headline = "Your %s check-in (%s): you spent %s. No salary arrived in this period." % (
                adj, _when(frm, to, today), _eur0(f["spent"]))
    else:
        if f["surplus"] >= 0:
            tail = ", leaving %s" % _eur0(f["surplus"]) if f["surplus"] > 0.005 else ", leaving nothing"
        else:
            tail = ", which is %s more than came in" % _eur0(f["surplus"])
        headline = ("Your %s check-in (%s): you earned %s and spent %s%s." % (
            adj, _when(frm, to, today), _eur0(f["income"]), _eur0(f["spent"]), tail))
    if not _scalar(conn, "SELECT COUNT(*) FROM tx WHERE d>=? AND d<=?", (frm, to), default=0):
        headline = "Your %s check-in (%s): there were no transactions in this period." % (
            adj, _when(frm, to, today))

    sugg = []
    # review overdraft
    low = _one(conn, "SELECT MIN(balance), COUNT(DISTINCT d) FROM tx WHERE balance<0 AND d>=? AND d<=?", (frm, to))
    if low and low[0] is not None:
        sugg.append({"id": "review_overdraft:%s" % frm, "kind": "review_overdraft",
                     "title": "Review the days your balance went below zero?",
                     "detail": ("Your balance was below zero on %d day%s, at worst %s below zero. Would you like "
                                "to look at what drove it?" % (low[1], "" if low[1] == 1 else "s", _eur(low[0]))),
                     "amount": _r(abs(low[0])), "action_label": "Show me"})
    # save surplus
    if f["surplus"] >= 20:
        amt = float(round(f["surplus"]))
        sugg.append({"id": "save_surplus:%s" % frm, "kind": "save_surplus",
                     "title": "You had a %s surplus %s. Would you like to set it aside?" % (
                         _eur0(amt), _surplus_when(frequency, frm, to, today)),
                     "detail": ("You had %s left over after spending and saving in %s. You could set it aside "
                                "as a buffer or put it toward investing: your choice. This only records your "
                                "intention; nothing moves automatically." % (_eur0(amt), word)),
                     "amount": _r(amt), "action_label": "Set aside %s" % _eur0(amt)})
    # trim category
    ms = _month_list(conn, t, 6)
    if ms:
        avgmap = _avg_display_map(conn, ms)
        scale = days / 30.44
        best = None
        for x in conn.execute(
                "SELECT %s AS lab, -SUM(amount) FROM tx WHERE basket='everyday' AND d>=? AND d<=? GROUP BY lab"
                % _DISP_SQL, (frm, to)).fetchall():
            usual = avgmap.get(x[0], 0.0) * scale
            over = float(x[1]) - usual
            if usual >= 5 and over >= 15 and float(x[1]) >= 1.25 * usual:
                if best is None or over > best[1]:
                    best = (x[0], over, float(x[1]), usual)
        if best:
            sugg.append({"id": "trim_category:%s:%s" % (best[0], frm), "kind": "trim_category",
                         "title": "Aim for your usual %s level?" % best[0].lower(),
                         "detail": ("%s came to %s in %s, about %s more than you usually spend. Would you "
                                    "like to aim for your usual level next time?" % (
                                        best[0], _eur0(best[2]), word, _eur0(best[1]))),
                         "amount": _r(best[1]), "action_label": "Aim for %s" % _eur0(best[3])})
    # buffer
    bal, essentials, bmonths = _buffer_info(conn, t)
    if bmonths is not None and bmonths < 1 and f["surplus"] >= 10:
        short = essentials - bal
        amt = float(math.floor(min(f["surplus"], short)))
        if amt >= 10:
            sugg.append({"id": "build_buffer:%s" % frm, "kind": "build_buffer",
                         "title": "Start a small buffer?",
                         "detail": ("Your balance covers about %.1f months of regular costs. Would you like to "
                                    "put %s toward a first month of cover?" % (max(bmonths, 0), _eur0(amt))),
                         "amount": _r(amt), "action_label": "Build buffer"})
    prio = {"save_surplus": 0, "review_overdraft": 1, "trim_category": 2, "build_buffer": 3}
    sugg.sort(key=lambda s: prio[s["kind"]])
    sugg = sugg[:3]
    evidence = _spend_filters(frm, to, _when(frm, to, today))
    evidence.append(_ev("Income, %s" % _when(frm, to, today), frm, to, type="salary"))
    return {"period": {"from": frm, "to": to, "frequency": frequency}, "headline": headline,
            "income": f["income"], "spent": f["spent"], "surplus": f["surplus"], "saved": f["saved"],
            "baskets": f["baskets"], "highlights": highlights, "suggestions": sugg,
            "evidence": evidence,
            "explain": ("Income minus spending minus money put into investments %s; suggestions "
                        "are worked out from those totals and your usual spending." % human_period(frm, to, today))}


# --------------------------------------------------------------------------- peer comparison

DAYS_PER_MONTH = 30.44
MIN_GROUP = 20
_NIGHT_METRIC_KEYS = {"night_out", "night out", "nights out"}


def _group_keys(profile):
    profile = profile or {}
    band, area = profile.get("age_band"), profile.get("area")
    keys = []
    if band and area:
        keys.append("age:%s|area:%s" % (band, area))
    if band:
        keys.append("age:%s" % band)
    keys.append("all")
    return keys


def _peer_metric(name):
    n = str(name or "").strip()
    low = n.lower().replace("_", " ")
    if low in _NIGHT_METRIC_KEYS:
        return "night_out"
    if low in SPEND_BASKETS:
        return low
    return "label:" + n


def _peer_group_words(key):
    parts = str(key or "").split("|")
    band = next((p[4:] for p in parts if p.startswith("age:")), None)
    area = any(p.startswith("area:") for p in parts)
    if band and area:
        return "people aged %s in your area" % band
    if band:
        return "people aged %s" % band
    return "customers"


def peer_near(key):
    """The peer group in everyday words (house rule R5): "most people your age nearby"."""
    who = _peer_group_words(key)
    return ("most people your age nearby" if who.endswith("in your area") else
            "most people your age" if who.startswith("people aged") else "most customers")


def peer_compare(total, period, target, profile, bench_lookup):
    """Place one spending figure next to the peer figure for the same length of time.

    Only group statistics are read (median and mean over at least 20 customers); nothing about any
    individual customer is fetched or computed. `target` is a label, "night_out", a basket key or a
    list of labels (their means are summed and the result is marked approximate).
    Returns None when no group of at least 20 customers exists.
    """
    if bench_lookup is None:
        return None
    try:
        frm, to = _d(period["from"]), _d(period["to"])
        you = float(total)
    except (KeyError, TypeError, ValueError):
        return None
    days = (to - frm).days + 1
    if days <= 0:
        return None
    factor = days / DAYS_PER_MONTH
    keys = _group_keys(profile)
    is_list = isinstance(target, (list, tuple))
    names = list(target) if is_list else [target]
    if not names:
        return None
    found = []
    group_key = None
    for nm in names:
        try:
            res = bench_lookup([group_key] if group_key else list(keys), _peer_metric(nm))
        except Exception:
            res = None
        if not res or int(res.get("n") or 0) < MIN_GROUP:
            return None
        if res.get("mean") is None or (not is_list and res.get("median") is None):
            return None
        group_key = res.get("group_key")
        found.append(res)
    n = min(int(r["n"]) for r in found)
    if n < MIN_GROUP:
        return None
    mean = sum(float(r["mean"]) for r in found) * factor
    if is_list:
        typical, basis = mean, "mean"
    else:
        typical, basis = float(found[0]["median"]) * factor, "median"
    typical, mean = _r(typical), _r(mean)
    diff = _r(you - typical)
    if abs(diff) <= 5.0 or abs(diff) <= 0.10 * typical:
        direction = "about the same"
    else:
        direction = "more" if diff > 0 else "less"
    if 28 <= days <= 31:
        span = "in a month"
    elif days == 7:
        span = "in a week"
    elif days == 1:
        span = "in a day"
    else:
        span = "over %d days" % days
    who = _peer_group_words(group_key)
    near = peer_near(group_key)
    stat = "%s of %d customers" % ("average" if basis == "mean" else "median", n)
    if direction == "about the same":
        sentence = "That is about the same as %s spend %s." % (near, span)
    else:
        sentence = "That is %s %s than %s spend %s." % (_eur0(abs(diff)), direction, near, span)
    # the area digits are masked: the comparison is shown to the model and the UI without a postal code
    masked = "|".join("area:*" if q.startswith("area:") else q for q in str(group_key).split("|"))
    desc = "All customers" if who == "customers" else who[0].upper() + who[1:]
    out = {"group": {"key": masked, "n": n, "description": desc},
           "peer_typical": typical, "peer_mean": mean, "you": _r(you), "diff": diff,
           "direction": direction, "basis": basis, "sentence": sentence,
           "explain": "Compared with the typical (%s) figure for %d customers (%s), scaled to the same length "
                      "of time." % ("average" if basis == "mean" else "median", n, who)}
    if is_list:
        out["approximate"] = True
    return out


# --------------------------------------------------------------------------- open data (Statistics Finland)

_OPEN_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "open_data.json")
_OPEN_DATA = {"loaded": False, "data": None}
_OPEN_AGE = {"18-24": "17-24", "25-34": "25-34", "35-44": "35-44", "45-54": "45-54", "55-64": "55-64",
             "65+": "65-74"}
_OPEN_ROWS = [
    ("Groceries", "01", ["Groceries"]),
    ("Restaurants and hotels", "11", ["Restaurant", "Fast food", "Bar", "Hotels"]),
    ("Housing and utilities", "04", ["Housing", "Utilities"]),
    ("Transport", "07", ["Public transport", "Fuel", "Taxi", "Parking"]),
    ("Clothing", "03", ["Clothing"]),
    ("Health", "06", ["Pharmacy", "Doctor", "Dentist", "Other health"]),
]


def _load_open_data():
    if not _OPEN_DATA["loaded"]:
        _OPEN_DATA["loaded"] = True
        try:
            with open(_OPEN_DATA_PATH, encoding="utf-8") as f:
                _OPEN_DATA["data"] = json.load(f)
        except (OSError, ValueError):
            _OPEN_DATA["data"] = None
    return _OPEN_DATA["data"]


def _open_data_block(raw, profile):
    od = _load_open_data()
    if not od:
        return None
    try:
        band = (profile or {}).get("age_band")
        gkey = _OPEN_AGE.get(band, "SSS")
        groups = od["age_groups"]
        if gkey not in groups:
            gkey = "SSS"
        nat = groups[gkey]["per_consumption_unit"]
        rows = []
        for name, code, labels in _OPEN_ROWS:
            if code not in nat:
                continue
            you = sum(float(raw.get(l, 0.0) or 0.0) for l in labels)
            rows.append({"name": name, "you": _r(you), "national": float(nat[code]),
                         "categories_used": list(labels)})
        return {
            "source": od.get("source"), "year": od.get("year"), "url": od.get("url"),
            "unit": od.get("unit"), "age_group": gkey,
            "note": ("The national figures are %s survey averages per consumption unit for all households "
                     "in the age group %s, not bank-account data, so they are a rough yardstick. Your figures "
                     "are your own monthly averages from your transactions." % (od.get("year"), gkey)),
            "rows": rows,
        }
    except (KeyError, TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- benchmarks

_BENCH_METRICS = [
    ("income", "Monthly income", "eur"), ("regular", "Regular essentials", "eur"),
    ("unexpected", "Unexpected necessities", "eur"), ("everyday", "Everyday spending", "eur"),
    ("savings", "Put into savings", "eur"), ("savings_rate", "Share of income kept", "ratio"),
    ("label:Groceries", "Groceries", "eur"), ("label:Restaurant", "Restaurants", "eur"),
    ("label:Fast food", "Fast food", "eur"), ("label:Taxi", "Taxis", "eur"),
    ("label:Clothing", "Clothing", "eur"), ("night_out", "Nights out", "eur"),
]


def _group_description(key):
    if not key:
        return "Peer group"
    who = _peer_group_words(key)
    return who[:1].upper() + who[1:]


def benchmarks(conn, today, profile, bench_lookup):
    t = _d(today)
    profile = profile or {}
    band, area = profile.get("age_band"), profile.get("area")
    keys = []
    if band and area:
        keys.append("age:%s|area:%s" % (band, area))
    if band:
        keys.append("age:%s" % band)
    keys.append("all")
    ms = _month_list(conn, t, 12)
    avg = _avg_flows(conn, ms)
    raw = _avg_display_map(conn, ms, group="raw")
    night = _avg_where(conn, ms, "context='night_out'")
    mine = {"income": avg["income"], "regular": avg["baskets"]["regular"],
            "unexpected": avg["baskets"]["unexpected"], "everyday": avg["baskets"]["everyday"],
            "savings": avg["baskets"]["savings"],
            "savings_rate": (avg["kept"] / avg["income"]) if avg["income"] > 0 else None,
            "night_out": night}
    for k, v in raw.items():
        mine["label:" + k] = v
    group = None
    rows = []
    for metric, name, unit in _BENCH_METRICS:
        you = mine.get(metric, 0.0)
        res = None
        try:
            res = bench_lookup(list(keys), metric) if bench_lookup else None
        except Exception:
            res = None
        if res is not None and (res.get("n") or 0) < 20:
            res = None
        row = {"metric": metric, "name": name, "unit": unit,
               "you": None if you is None else (_r(100 * you) / 100.0 if unit == "ratio" else _r(you)),
               "median": None, "p25": None, "p75": None, "position": None}
        if res is not None:
            if group is None:
                group = {"key": res.get("group_key"), "n": int(res.get("n")),
                         "description": _group_description(res.get("group_key"))}
            row.update({"median": res.get("median"), "p25": res.get("p25"), "p75": res.get("p75"),
                        "group_key": res.get("group_key")})
            if unit == "ratio":
                for kk in ("median", "p25", "p75"):
                    row[kk] = round(float(row[kk]), 4)
                if row["you"] is not None:
                    row["you"] = round(float(you), 4)
            else:
                for kk in ("median", "p25", "p75"):
                    row[kk] = _r(row[kk])
            yv = you if you is not None else None
            if yv is not None:
                row["position"] = ("below" if yv < row["p25"] else "above" if yv > row["p75"] else "typical")
        rows.append(row)
    if group is None:
        group = {"key": None, "n": 0, "description": "No peer group of at least 20 customers was available."}
        explain = ("No peer group of at least 20 customers is available for your profile, so only your own "
                   "monthly averages are shown.")
    else:
        explain = ("Your monthly average over the last %d full months is placed against the typical figure "
                   "(median) and the range from the 25th to the 75th percentile for %d customers (%s); only "
                   "group statistics are used, never individual customers." % (
                       len(ms), group["n"], group["description"].lower()))
    frm, to = _span(ms)
    evidence = _spend_filters(frm, to, "last %d months" % len(ms)) if ms else []
    out = {"group": group, "rows": rows, "explain": explain, "evidence": evidence}
    od = _open_data_block(raw, profile)
    if od:
        out["open_data"] = od
    return out


# --------------------------------------------------------------------------- investing education

def invest_education(conn, today):
    t = _d(today)
    bal, essentials, bmonths = _buffer_info(conn, t)
    ms = _month_list(conn, t, 6)
    avg = _avg_flows(conn, ms)
    surplus = avg["surplus"]
    buffer_months = round(bmonths, 1) if bmonths is not None else None
    buffer_ok = bool(bmonths is not None and bmonths >= 3)
    pts = []
    if buffer_months is None:
        pts.append("Buffer first: before investing, keep three to six months of regular costs in easy-access "
                   "savings. There is not enough history to say where you stand.")
    elif buffer_ok:
        pts.append("Buffer first: your balance covers about %.1f months of regular costs, which is in the "
                   "usual three to six month range, so this step looks covered." % buffer_months)
    else:
        pts.append("Buffer first: your balance covers about %.1f months of regular costs. Many people aim for "
                   "three to six months in easy-access money before investing, so building that comes first."
                   % buffer_months)
    if surplus > 0:
        pts.append("Your surplus: after spending and saving you keep about %s a month on average. Deciding a "
                   "fixed amount to move on payday works better than investing what happens to be left."
                   % _eur0(surplus))
    else:
        pts.append("Your surplus: you are not keeping much after spending on average, so freeing up room "
                   "through the savings ideas comes before investing.")
    if avg["saved"] > 0:
        pts.append("You already put about %s a month into savings and investments; keep that regular." % _eur0(avg["saved"]))
    pts += [
        "Time horizon: money you may need within a few years belongs in savings. Investing suits money you can "
        "leave alone for five years or more.",
        "Diversification: spreading money across many companies, sectors and regions lowers the damage when one "
        "of them does badly. Putting everything in one thing is the main avoidable risk.",
        "Costs: fees and charges are paid every year and compound over time, so compare the total yearly cost "
        "before choosing anything.",
        "Risk: values go up and down and you can lose part of what you put in. Only invest money you can leave "
        "untouched through a bad year, and never borrow to invest.",
    ]
    ev = []
    if ms:
        ev = [_ev("Regular essentials", ms[0][0], ms[-1][1], basket="regular"),
              _ev("Investment deposits", None, None, type="investment_deposit")]
    return {"buffer_months": buffer_months, "buffer_ok": buffer_ok, "surplus_avg": _r(surplus), "points": pts,
            "disclaimer": ("This is general information, not investment advice. Svinkki does not recommend "
                           "specific funds, shares or products."),
            "evidence": ev,
            "explain": ("Buffer = current balance divided by your average monthly regular costs; surplus = "
                        "income minus spending and savings, averaged over the last %d full months." % len(ms))}


# --------------------------------------------------------------------------- goal

def goal(conn, today, target_amount, monthly=None, starting_amount=0.0):
    t = _d(today)
    try:
        target = float(target_amount)
    except (TypeError, ValueError):
        raise ValueError("target_amount must be a number")
    ms = _month_list(conn, t, 6)
    avg = _avg_flows(conn, ms)
    try:
        already = max(0.0, float(starting_amount or 0.0))
    except (TypeError, ValueError):
        raise ValueError("starting_amount must be a number")
    if monthly in (None, ""):
        mo = avg["kept"]
        basis = "your average monthly saving capacity (income minus spending) of %s" % _eur0(mo)
    else:
        mo = float(monthly)
        basis = "a monthly amount of %s" % _eur0(mo)
    ev = [_ev("Investment deposits", None, None, type="investment_deposit")]
    gap = target - already
    if gap <= 0:
        return {"months": 0, "date": t.isoformat(), "monthly": _r(mo), "target": _r(target),
                "already_saved": _r(already), "evidence": ev,
                "explain": "The starting amount of %s already covers the %s goal." % (_eur(already), _eur(target))}
    if mo <= 0:
        return {"months": None, "date": None, "monthly": _r(mo), "target": _r(target),
                "already_saved": _r(already), "evidence": ev,
                "explain": ("You are not keeping anything after spending each month (income minus spending is %s), "
                            "so the goal cannot be reached yet." % ("below zero" if mo < -0.005 else "zero"))}
    months = int(math.ceil(gap / mo))
    when = _add_months(t, months)
    return {"months": months, "date": when.isoformat(), "monthly": _r(mo), "target": _r(target),
            "already_saved": _r(already), "evidence": ev,
            "assumed_monthly": monthly in (None, ""),
            "explain": ("%s%s still to go at %s takes %d months, around %s. A different monthly amount "
                        "changes the date." % (_eur0(gap), " (after %s already saved)" % _eur(already) if already > 0 else "",
                                               basis, months, human_month(when.strftime("%Y-%m"), today)))}
