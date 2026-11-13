"""Wave 2 features: affordability, leak finder, alerts, savings leakage, micro-challenges, quiz stats.

Pure functions. Every function that reads transactions takes a sandbox connection `conn` (table `tx`,
one customer, read-only) and `today` ("YYYY-MM-DD"). Money is computed here, in code, never by the
model: spending is positive, rounded to 2 decimals. Results carry `explain` and `evidence`.
Standard library only; no file or network access.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime, timedelta

from . import insights as ins

_DAYS_PER_MONTH = 30.44
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_WEEKDAYS_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_NUM_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
              "eleven", "twelve"]
_DISP = ins._DISP_SQL
_SMALL = 10.0
# everyday shops that are visited again and again are never treated as subscriptions
_FREQUENT_SHOPS = {"Groceries", "Fuel", "Restaurant", "Fast food", "Bar", "Taxi", "Parking", "Pharmacy"}


# --------------------------------------------------------------------------- helpers

_r = ins._r
_eur = ins._eur
_eur0 = ins._eur0
_d = ins._d


def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return []


def _has_data(conn):
    return bool(_rows(conn, "SELECT 1 FROM tx LIMIT 1"))


def _words(n):
    n = int(n)
    return _NUM_WORDS[n] if 0 <= n < len(_NUM_WORDS) else str(n)


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "x"


def _ref(merchant):
    return hashlib.sha256(("svinkki:" + str(merchant)).encode("utf-8")).hexdigest()[:8]


def _median(xs):
    return ins._median(xs)


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def _ym(d):
    return d.year * 12 + d.month - 1


def _ev(title, frm=None, to=None, **kw):
    return ins._ev(title, frm, to, **kw)


def _label_ev(label, frm, to, title=None):
    return ins._disp_evidence(label, frm, to, title or label)


# --------------------------------------------------------------------------- repeating charges

def _repeaters(conn, t, n_months, tol, min_seen):
    """Merchants charged about once a month: in at least `min_seen` of the last `n_months` full months,
    one charge in (nearly) every month it appears, amounts within `tol` of their median and charged on
    similar days of the month. Returns a list of dicts, biggest yearly cost first."""
    months = ins._month_list(conn, t, n_months)
    if len(months) < 3:
        return []
    frm, to = months[0][0], months[-1][1]
    rows = _rows(conn,
                 "SELECT merchant, d, -amount, COALESCE(NULLIF(label,''),'Other') FROM tx "
                 "WHERE type='purchase' AND amount<0 AND merchant IS NOT NULL AND merchant<>'' "
                 "AND d>=? AND d<=? ORDER BY d", (frm, to))
    by = {}
    for m, d, amt, lab in rows:
        by.setdefault(m, []).append((str(d)[:10], float(amt), lab))
    found = []
    for m, items in by.items():
        per = {}
        for d, amt, lab in items:
            per.setdefault(d[:7], []).append(amt)
        seen = len(per)
        if seen < min_seen:
            continue
        singles = sum(1 for v in per.values() if len(v) == 1)
        if singles < 0.8 * seen or any(len(v) > 2 for v in per.values()):
            continue
        amts = [a for _, a, _ in items]
        med = _median(amts)
        if med <= 0 or any(abs(a - med) > tol * med for a in amts):
            continue
        days = [int(d[8:10]) for d, _, _ in items]
        mday = _median(days)
        if any(abs(x - mday) > 7 for x in days):
            continue
        labs = [lab for _, _, lab in items]
        label = max(set(labs), key=labs.count)
        if label in _FREQUENT_SHOPS:
            continue
        found.append({"merchant": m, "label": label, "months_seen": seen, "window": (frm, to),
                      "median": med})
    # full history up to today for each merchant (latest charge, price history)
    for f in found:
        hist = _rows(conn, "SELECT d, -amount FROM tx WHERE merchant=? AND type='purchase' AND amount<0 "
                           "AND d<=? ORDER BY d", (f["merchant"], t.isoformat()))
        f["history"] = [(str(d)[:10], float(a)) for d, a in hist]
        f["last_seen"] = f["history"][-1][0]
        f["amount"] = f["history"][-1][1]
    found.sort(key=lambda f: -f["amount"])
    return found


# --------------------------------------------------------------------------- afford

def _span_words(days):
    if days < 1.5:
        return "a day"
    if days < 14:
        return "%s days" % _words(round(days))
    if days < 60:
        w = max(2, round(days / 7.0))
        return "%s weeks" % _words(w)
    months = max(2, round(days / _DAYS_PER_MONTH))
    return "%s months" % _words(months)


def _the_item(item, price):
    """"the €300 jacket" from an item name and its price (an article in the name is dropped)."""
    name = re.sub(r"^(a|an|the|my|your|some)\s+", "", str(item or "").strip(), flags=re.I) or "purchase"
    return "the %s %s" % (_eur0(price), name) if price > 0 else "the %s" % name


def afford(conn, today, item, price, goal=None, monthly_saving_target=0.0):
    t = _d(today)
    try:
        price = max(0.0, float(price))
    except (TypeError, ValueError):
        price = 0.0
    item = str(item or "it").strip()[:80] or "it"
    try:
        target = max(0.0, float(monthly_saving_target or 0.0))
    except (TypeError, ValueError):
        target = 0.0
    s = ins.safe_to_spend(conn, today, target)
    safe_total = float(s["safe_total"])
    days_left = max(1, int(s["days_left"]))
    after = safe_total - price
    per_day_after = after / days_left
    if after < 0:
        verdict = "no"
    elif per_day_after < 10:
        verdict = "tight"
    else:
        verdict = "yes"
    share = (price / safe_total) if safe_total > 0 else None
    m6 = ins._month_list(conn, t, 6)
    avg = ins._avg_flows(conn, m6)
    ev_avg = float(avg["baskets"]["everyday"])
    typical = (price / ev_avg) if ev_avg > 0 else None
    nxt = s.get("next_payday")
    until = ("until payday on %s" % ins.human_range(nxt, None, today)) if nxt else "over the next %d days" % days_left
    thing = _the_item(item, price)
    if verdict == "yes" and share is not None and share > 0.5:
        text = "It fits, but %s takes most of your spending money %s: about %s a day would be left.%s" % (
            thing, until, _eur0(per_day_after),
            " Waiting until after %s is easier." % ins.human_range(nxt, None, today) if nxt else "")
    elif verdict == "yes":
        text = "Yes, %s fits. You would still have about %s a day %s." % (thing, _eur0(per_day_after), until)
    elif verdict == "tight":
        text = "It is possible but tight: after %s you would have only about %s a day %s." % (
            thing, _eur0(max(0.0, per_day_after)), until)
    elif safe_total <= 0:
        # already short: say so once, and do not call the existing gap the price (D9)
        if safe_total < 0 and price > 0:
            text = "You are already about %s short %s, so this %s purchase would add to that." % (
                _eur0(-safe_total), until, _eur(price))
        elif safe_total < 0:
            text = "You are already about %s short %s." % (_eur0(-safe_total), until)
        else:
            text = "You have nothing safe left to spend %s, so this %s purchase would put you short." % (
                until, _eur(price))
    else:
        text = "Not comfortably: %s is %s more than the %s you can safely spend %s." % (
            thing, _eur0(-after), _eur0(max(0.0, safe_total)), until)

    goal_effect = None
    if isinstance(goal, dict) and goal.get("name"):
        gname = re.sub(r"^(my|your)\s+", "", str(goal["name"]).strip(), flags=re.I)
        ms = target if target > 0 else float(avg.get("kept") or 0.0)
        if ms > 0:
            dd = price / ms * _DAYS_PER_MONTH
            dtext = "delays your %s by about %s" % (gname, _span_words(dd)) if price > 0 \
                else "does not change your %s" % gname
            goal_effect = {"name": str(goal["name"]), "monthly_saving": _r(ms), "delay_days": _r(dd),
                           "delay_text": dtext}
        else:
            goal_effect = {"name": str(goal["name"]), "monthly_saving": _r(ms), "delay_days": None,
                           "delay_text": "your %s has no regular saving yet, so this does not move it" % gname}
    alternatives = []
    if verdict != "yes" and price > 0:
        if nxt:
            alternatives.append("Wait until payday on %s and decide then." % ins.human_range(nxt, None, today))
        alternatives.append("Split it over two months: about %s now and %s next month." % (
            _eur0(price / 2), _eur0(price / 2)))
    alternatives = alternatives[:2]
    ev = list(s.get("evidence") or [])
    return {
        "item": item, "price": _r(price), "safe_total": _r(safe_total), "days_left": days_left,
        "next_payday": nxt, "after": _r(after), "per_day_after": _r(per_day_after), "verdict": verdict,
        "verdict_text": text, "share_of_safe": None if share is None else round(share, 3),
        "typical_month_share": None if typical is None else round(typical, 3),
        "goal_effect": goal_effect, "alternatives": alternatives,
        "explain": "Safe-to-spend is your balance minus bills before payday, a buffer for unexpected costs and "
                   "planned savings (%s); the price is taken off it." % _eur0(safe_total),
        "evidence": ev,
    }


# --------------------------------------------------------------------------- leaks

def leaks(conn, today, months=3):
    t = _d(today)
    try:
        months = max(1, min(12, int(months)))
    except (TypeError, ValueError):
        months = 3
    frm_d = ins._add_months(ins._month_start(t), -months)
    first = ins._scalar(conn, "SELECT MIN(d) FROM tx", default=None)
    if first is not None and _d(first) > frm_d:
        frm_d = _d(first)
    frm, to = frm_d.isoformat(), t.isoformat()
    per_len = max(1.0, ((t - frm_d).days + 1) / _DAYS_PER_MONTH)
    empty = {"period": {"from": frm, "to": to},
             "small": {"threshold": 10, "count": 0, "total": 0.0, "per_month": 0.0, "top_labels": []},
             "by_weekday": [{"day": d, "total": 0.0, "count": 0} for d in _WEEKDAYS],
             "by_hour": [{"hour": h, "total": 0.0, "count": 0} for h in range(24)],
             "peak": {"day": None, "hour_range": None, "text": "Not enough everyday spending yet to see a pattern."},
             "payday_week": {"share": None, "total": 0.0, "text": "No payday seen yet, so no payday-week figure."},
             "subscriptions": [], "headline": "Not enough data yet to look for leaks.",
             "explain": "Leaks are found from your everyday purchases and repeating charges.", "evidence": []}
    if not _has_data(conn):
        return empty
    rows = _rows(conn,
                 "SELECT d, ts, -amount, %s FROM tx WHERE basket='everyday' AND amount<0 AND d>=? AND d<=?" % _DISP,
                 (frm, to))
    # small purchases
    small = [(float(a), lab) for d, ts, a, lab in rows if a < _SMALL]
    small_total = sum(a for a, _ in small)
    labs = {}
    for a, lab in small:
        e = labs.setdefault(lab, [0.0, 0])
        e[0] += a
        e[1] += 1
    top = [{"label": k, "total": _r(v[0]), "count": v[1]}
           for k, v in sorted(labs.items(), key=lambda kv: -kv[1][0])[:3]]
    # weekday and hour
    wd = [[0.0, 0] for _ in range(7)]
    hr = [[0.0, 0] for _ in range(24)]
    for d, ts, a, lab in rows:
        try:
            w = _d(d).weekday()
        except ValueError:
            continue
        wd[w][0] += float(a)
        wd[w][1] += 1
        try:
            h = int(str(ts)[11:13])
            if 0 <= h < 24:
                hr[h][0] += float(a)
                hr[h][1] += 1
        except ValueError:
            pass
    by_weekday = [{"day": _WEEKDAYS[i], "total": _r(wd[i][0]), "count": wd[i][1]} for i in range(7)]
    by_hour = [{"hour": i, "total": _r(hr[i][0]), "count": hr[i][1]} for i in range(24)]
    peak = dict(empty["peak"])
    total_all = sum(float(a) for _, _, a, _ in rows)
    if rows and total_all > 0:
        pd_i = max(range(7), key=lambda i: wd[i][0])
        ph = max(range(24), key=lambda i: hr[i][0])
        peak = {"day": _WEEKDAYS[pd_i], "hour_range": "%02d:00-%02d:00" % (ph, (ph + 1) % 24),
                "text": "Most of your everyday spending happens on %ss (%s of it), and the busiest hour is %02d:00 to %02d:00." % (
                    _WEEKDAYS_FULL[pd_i], ins._pct_text(wd[pd_i][0] / total_all), ph, (ph + 1) % 24)}
    # payday week
    pay_from = (frm_d - timedelta(days=7)).isoformat()
    paydays = sorted({_d(r[0]) for r in _rows(conn, "SELECT d FROM tx WHERE type='salary' AND d>=? AND d<=?",
                                              (pay_from, to))})
    pw = dict(empty["payday_week"])
    if paydays and total_all > 0:
        in_week = 0.0
        for d, ts, a, lab in rows:
            dd = _d(d)
            if any(0 <= (dd - p).days <= 7 for p in paydays):
                in_week += float(a)
        share = in_week / total_all
        pw = {"share": round(share, 3), "total": _r(in_week),
              "text": "%s of your everyday spending (%s) lands in the 8 days after payday; an even spread would be about 26%%." % (
                  ins._pct_text(share), _eur0(in_week))}
    # subscriptions
    subs = []
    for f in _repeaters(conn, t, 6, 0.20, 3):
        amt, first_amt = f["amount"], f["history"][0][1]
        txt = "%s a month on %s, seen in %d of the last 6 months (about %s a year); last charged %s." % (
            _eur(amt), ins.label_words(f["label"]), f["months_seen"], _eur0(amt * 12),
            ins.human_range(f["last_seen"], None, today))
        lo = min(a for _, a in f["history"])
        if amt > lo * 1.02:
            txt += " It was %s earlier." % _eur(lo)
        subs.append({"merchant_ref": _ref(f["merchant"]), "label": f["label"], "amount": _r(amt),
                     "every": "month", "months_seen": f["months_seen"], "yearly": _r(amt * 12),
                     "last_seen": f["last_seen"], "text": txt})
    if small_total > 0:
        head = "Small purchases under €10 add up to %s a month (%d of them %s)." % (
            _eur0(small_total / per_len), len(small), ins.human_period(frm, to, today))
    else:
        head = "No small purchases under €10 to speak of %s." % ins.human_period(frm, to, today)
    if subs:
        sub_total = sum(s["yearly"] for s in subs)
        head += " %d repeating charge%s cost about %s a year." % (len(subs), "" if len(subs) == 1 else "s", _eur0(sub_total))
    ev = [_ev("Everyday spending", frm, to, basket="everyday")]
    for top_l in top[:2]:
        pass
    return {
        "period": {"from": frm, "to": to},
        "small": {"threshold": 10, "count": len(small), "total": _r(small_total),
                  "per_month": _r(small_total / per_len), "top_labels": top},
        "by_weekday": by_weekday, "by_hour": by_hour, "peak": peak, "payday_week": pw,
        "subscriptions": subs, "headline": head,
        "explain": "Built from your everyday purchases %s; repeating charges are the same merchant about once a "
                   "month at a similar price, in at least 3 of the last 6 months." % ins.human_period(frm, to, today),
        "evidence": ev,
    }


# --------------------------------------------------------------------------- alerts

def _month_totals(conn, ym_from_to, where):
    frm, to = ym_from_to
    v = ins._scalar(conn, "SELECT -SUM(amount) FROM tx WHERE %s AND d>=? AND d<=?" % where, (frm, to))
    return float(v or 0.0)


def _creep_months(conn, t, type_, label):
    """Housing / Utilities: latest full month vs the closest month at least six months earlier."""
    months = ins._month_list(conn, t, 14)
    tot = []
    for a, b in months:
        tot.append((a, b, _month_totals(conn, (a, b), "type='%s'" % type_)))
    paid = [x for x in tot if x[2] > 0]
    if len(paid) < 2:
        return None
    last = paid[-1]
    ly = _ym(_d(last[0]))
    older = [x for x in paid if ly - _ym(_d(x[0])) >= 6]
    if not older:
        return None
    # compare with the highest earlier month so a seasonal swing is not read as a price rise
    ref = max(older, key=lambda x: x[2])
    return last, ref


def alerts(conn, today, profile=None, bench_lookup=None):
    t = _d(today)
    out = []
    if not _has_data(conn):
        return {"alerts": [], "explain": "There is no transaction history yet to compare against.", "evidence": []}
    months = ins._month_list(conn, t, 7)
    flagged_labels = set()
    if len(months) >= 4:
        last = months[-1]
        prior = months[:-1][-6:]
        ym = last[0][:7]
        cur = {r["label"]: r for r in ins._by_display(conn, last[0], last[1])}
        avg = ins._avg_display_map(conn, prior)
        present = {}
        for a, b in prior:
            for r in ins._by_display(conn, a, b):
                present[r["label"]] = present.get(r["label"], 0) + 1
        found = []
        for lab, r in cur.items():
            if lab == "Night out":
                pass
            usual = avg.get(lab, 0.0)
            if usual <= 0 or present.get(lab, 0) < 4:
                continue
            c = float(r["total"])
            if c >= usual * 1.4 and c - usual >= 25:
                found.append((c - usual, lab, c, usual))
        found.sort(reverse=True)
        for diff, lab, c, usual in found[:2]:
            sev = "notice" if (c >= usual * 2 and diff >= 50) else "info"
            flagged_labels.add(lab)
            mname = ins.human_month(ym, today)
            out.append({"id": "above_own_usual:%s:%s" % (_slug(lab), ym), "kind": "above_own_usual",
                        "severity": sev,
                        "title": "%s: %s in %s, %s your usual %s" % (
                            lab, _eur0(c), mname, ins.ratio_words(c, usual), _eur0(usual)),
                        "detail": "Your average for %s over the six months before was %s a month; "
                                  "%s is %s more." % (ins.label_words(lab), _eur0(usual), mname, _eur0(diff)),
                        "amount": _r(diff),
                        "evidence": [_label_ev(lab, last[0], last[1], "%s, %s" % (lab, mname))]})
        # peers
        if bench_lookup is not None:
            keys = ins._group_keys(profile)
            pf = []
            for lab, r in cur.items():
                if lab in flagged_labels or lab == "Night out" or float(r["total"]) < 50:
                    continue
                try:
                    res = bench_lookup(list(keys), "label:" + lab)
                except Exception:
                    res = None
                if not res or int(res.get("n") or 0) < ins.MIN_GROUP or not res.get("median"):
                    continue
                med = float(res["median"])
                c = float(r["total"])
                if med >= 10 and c >= med * 1.4 and c - med >= 25:
                    pf.append((c - med, lab, c, med, res))
            pf.sort(reverse=True)
            for diff, lab, c, med, res in pf[:1]:
                who = ins._peer_group_words(res.get("group_key"))
                mname = ins.human_month(ym, today)
                out.append({"id": "above_peers:%s:%s" % (_slug(lab), ym), "kind": "above_peers", "severity": "info",
                            "title": "%s: %s in %s, %s what %s spend (%s)" % (
                                lab, _eur0(c), mname, ins.ratio_words(c, med), ins.peer_near(res.get("group_key")),
                                _eur0(med)),
                            "detail": "The typical monthly figure comes from %d customers in that group. It is a yardstick, "
                                      "not a target." % int(res["n"]),
                            "amount": _r(diff),
                            "evidence": [_label_ev(lab, last[0], last[1], "%s, %s" % (lab, mname))]})
    # price creep: repeating charges
    for f in _repeaters(conn, t, 12, 0.5, 5)[:20]:
        hist = f["history"]
        ld, la = _d(hist[-1][0]), hist[-1][1]
        ref = None
        for d, a in hist:
            if (ld - _d(d)).days >= 175:
                ref = (d, a)
        if ref and la >= ref[1] * 1.10 and la - ref[1] >= 0.5:
            out.append({"id": "price_creep:%s" % _ref(f["merchant"]), "kind": "price_creep", "severity": "notice",
                        "title": "A repeating %s charge went from %s in %s to %s now" % (
                            ins.label_words(f["label"]), _eur(ref[1]), ins.human_range(ref[0], None, today),
                            _eur(la)),
                        "detail": "That is %s more a month, about %s more a year." % (
                            _eur(la - ref[1]), _eur0((la - ref[1]) * 12)),
                        "amount": _r((la - ref[1]) * 12),
                        "evidence": [_label_ev(f["label"], ref[0], hist[-1][0],
                                               "%s charges, %s to %s" % (
                                                   f["label"], ins.human_range(ref[0], None, today),
                                                   ins.human_range(hist[-1][0], None, today)))]})
    for type_, lab in (("housing_payment", "Housing"), ("utilities_payment", "Utilities")):
        if lab in flagged_labels:
            continue
        r = _creep_months(conn, t, type_, lab)
        if not r:
            continue
        last, ref = r
        la, ra = last[2], ref[2]
        thr = 5 if lab == "Utilities" else 1
        if la >= ra * 1.10 and la - ra >= thr:
            lm, rm = last[0][:7], ref[0][:7]
            out.append({"id": "price_creep:%s:%s" % (_slug(lab), lm), "kind": "price_creep", "severity": "notice",
                        "title": "%s: %s in %s, up from %s in %s" % (
                            lab, _eur0(la), ins.human_month(lm, today), _eur0(ra), ins.human_month(rm, today)),
                        "detail": "That is %s more a month than six months before." % _eur0(la - ra),
                        "amount": _r((la - ra) * 12),
                        "evidence": [_ev("%s payments" % lab, ref[0], last[1], type=type_)]})
    out.sort(key=lambda a: (0 if a["severity"] == "notice" else 1, -a["amount"]))
    out = out[:5]
    ev = [e for a in out for e in a["evidence"]]
    explain = ("Each alert compares one figure with your own usual level%s." %
               (" or with people of your age" if bench_lookup is not None else ""))
    if not out:
        explain = "Nothing stands out: no category is far above your usual level and no repeating charge has crept up."
    return {"alerts": out, "explain": explain, "evidence": ev}


# --------------------------------------------------------------------------- savings leakage

def savings_leakage(conn, today, months=6):
    t = _d(today)
    try:
        months = max(1, min(24, int(months)))
    except (TypeError, ValueError):
        months = 6
    frm = ins._add_months(ins._month_start(t), -months).isoformat()
    to = t.isoformat()
    base = {"withdrawals": [], "count": 0, "total": 0.0, "month_end_count": 0, "flag": False,
            "text": "No investment withdrawals %s." % ins.human_period(frm, to, today),
            "explain": "A withdrawal counts when it falls in the 10 days before payday or when the balance before it "
                       "was under €100.",
            "evidence": [_ev("Investment withdrawals", frm, to, type="investment_withdrawal")]}
    rows = _rows(conn, "SELECT d, amount, balance FROM tx WHERE type='investment_withdrawal' AND d>=? AND d<=? "
                       "ORDER BY ts, rowid", (frm, to))
    if not rows:
        return base
    sal = sorted({_d(r[0]) for r in _rows(conn, "SELECT d FROM tx WHERE type='salary' AND d<=?", (to,))})
    usual = ins._usual_payday(conn, t)
    items = []
    flagged = 0
    for d, amt, bal in rows:
        dd = _d(d)
        nxt = next((p for p in sal if p > dd), None)
        if nxt is None and usual is not None:
            nxt = ins._next_payday(dd, usual)
        dbp = (nxt - dd).days if nxt else None
        a = abs(float(amt or 0.0))
        before = (float(bal) - float(amt or 0.0)) if bal is not None else None
        hit = (dbp is not None and dbp <= 10) or (before is not None and before < 100)
        flagged += 1 if hit else 0
        items.append({"d": str(d)[:10], "amount": _r(a), "days_before_payday": dbp,
                      "balance_before": None if before is None else _r(before)})
    total = sum(i["amount"] for i in items)
    flag = flagged >= 2
    if flag:
        text = ("%d of your %d investment withdrawals since %s came in the 10 days before payday or when your balance "
                "was under €100 (%s in all). That looks like savings covering the end of the month." % (
                    flagged, len(items), ins.human_range(frm, None, today), _eur0(sum(
                        i["amount"] for i in items
                        if (i["days_before_payday"] is not None and i["days_before_payday"] <= 10)
                        or (i["balance_before"] is not None and i["balance_before"] < 100)))))
    else:
        text = ("You took %s out of investments %s, and it does not look like it is covering the end of the month."
                % (_eur0(total), ins.human_period(frm, to, today)))
    base.update({"withdrawals": items, "count": len(items), "total": _r(total), "month_end_count": flagged,
                 "flag": flag, "text": text})
    return base


# --------------------------------------------------------------------------- challenges

_NOUN = {"Restaurant": "restaurant visits", "Fast food": "fast food orders", "Bar": "bar visits",
         "Taxi": "taxi rides", "Night out": "nights out", "Cinema": "cinema visits", "Events": "event tickets",
         "Clothing": "clothing purchases", "Entertainment": "entertainment purchases",
         "Hobbies": "hobby purchases", "Books": "book purchases", "Shopping": "shopping purchases",
         "Dining out": "meals out"}
_PLURAL = {"Restaurant": "restaurants", "Fast food": "fast food", "Bar": "bars", "Taxi": "taxis",
           "Night out": "nights out", "Cinema": "the cinema", "Events": "events", "Clothing": "clothes",
           "Hobbies": "hobbies", "Shopping": "shopping", "Books": "books", "Entertainment": "entertainment", "Dining out": "eating out",
           "Electronics": "electronics"}
_DISCRETIONARY = ("Restaurant", "Fast food", "Bar", "Taxi", "Events", "Cinema", "Entertainment", "Clothing",
                  "Shopping", "Hobbies", "Electronics")
_DINING = ("Restaurant", "Fast food")
_DISC_SQL = "(context='night_out' OR label IN (%s))" % ", ".join("'%s'" % x for x in _DISCRETIONARY)
_FREE_TITLE = {"Taxi": "A taxi-free week", "Fast food": "A fast-food-free week", "Bar": "A bar-free week",
               "Restaurant": "A restaurant-free week", "Clothing": "A clothes-shopping-free week",
               "Night out": "A week without a night out"}


def _plural(label):
    return _PLURAL.get(label, label.lower())


def _noun(label):
    return _NOUN.get(label, "%s purchases" % label.lower())


def _week_bounds(t):
    mon = t - timedelta(days=t.weekday())
    return mon, mon + timedelta(days=6)


def _is_night(label, context):
    return label == "Night out" or context == "night_out"


def _where_label(label, context):
    if _is_night(label, context):
        return "context='night_out'", ()
    if label == "Dining out":
        return "label IN (?, ?) AND (context IS NULL OR context<>'night_out')", _DINING
    return "label=? AND (context IS NULL OR context<>'night_out')", (label,)


def _spent_in(conn, label, context, frm, to):
    w, p = _where_label(label, context)
    r = _rows(conn, "SELECT COALESCE(-SUM(amount),0), COUNT(*) FROM tx WHERE basket='everyday' AND amount<0 "
                    "AND d>=? AND d<=? AND " + w, (frm, to) + tuple(p))
    return (float(r[0][0]), int(r[0][1])) if r else (0.0, 0)


def challenge_options(conn, today):
    t = _d(today)
    mon, sun = _week_bounds(t)
    empty = lambda why: {"options": [], "explain": why}
    if not _has_data(conn):
        return empty("There is not enough history yet to suggest a challenge.")
    # D13: with fewer than 3 days of the week left, offer next week's challenge instead
    next_week = (sun - t).days + 1 < 3
    p_mon, p_sun = (mon + timedelta(days=7), sun + timedelta(days=7)) if next_week else (mon, sun)
    first = _d(ins._scalar(conn, "SELECT MIN(d) FROM tx", default=today))
    weeks = [mon - timedelta(days=7 * i) for i in range(8, 0, -1)]
    weeks = [w for w in weeks if w >= first]
    if len(weeks) < 5:
        return empty("Your history is still short, so I will wait until I have at least five weeks to build a "
                     "challenge from your own habits.")
    w0, wend = weeks[0], weeks[-1] + timedelta(days=6)
    n = len(weeks)
    rows = _rows(conn, "SELECT d, %s AS lab, -amount FROM tx WHERE basket='everyday' AND amount<0 AND d>=? AND d<=? "
                       "AND %s" % (_DISP, _DISC_SQL), (w0.isoformat(), wend.isoformat()))
    tot, cnt = {}, {}
    days_with = set()
    for d, lab, a in rows:
        dd = _d(d)
        wi = (dd - w0).days // 7
        if not 0 <= wi < n:
            continue
        for bucket in ((lab, "Dining out") if lab in _DINING else (lab,)):
            tot.setdefault(bucket, [0.0] * n)[wi] += float(a)
            cnt.setdefault(bucket, [0] * n)[wi] += 1
        days_with.add(dd)
    ev_from, ev_to = w0.isoformat(), wend.isoformat()
    cands = []   # (met, kind_rank, option)
    mk_period = {"from": p_mon.isoformat(), "to": p_sun.isoformat()}

    def make(kind, label, title, why, target, unit, baseline, met, evidence, context=""):
        wid = "%s-%s-%s" % (kind, _slug(label), p_mon.isoformat())
        if next_week:
            title = title.replace("this week", "next week")
        return {"id": wid, "kind": kind, "title": title, "why": why, "target": target, "unit": unit,
                "baseline": baseline, "difficulty": "easy" if met >= 5 else "medium", "label": label,
                "context": context, "period": dict(mk_period), "evidence": evidence}, met

    def fits(opt):
        # only offer what is still comfortably reachable this week
        return challenge_progress(conn, today, opt)["status"] == "on_track"

    order = {"none_this_week": 0, "under_amount": 1, "fewer_times": 2}
    for lab in tot:
        totals, counts = tot[lab], cnt[lab]
        present = sum(1 for c in counts if c > 0)
        zero = n - present
        mc = _mean(counts)
        mt = _mean(totals)
        ctx = "night_out" if lab == "Night out" else ""
        if lab == "Dining out":
            ev = [_label_ev(x, ev_from, ev_to, "%s, last %d weeks" % (ins.label_words(x).capitalize(), n))
                  for x in _DINING]
        else:
            ev = [_label_ev(lab, ev_from, ev_to, "%s, last %d weeks" % (ins.label_words(lab).capitalize(), n))]
        picks = []
        # under_amount: about 20 % under the usual level; when the customer is very regular and that level was
        # not reached in 3 weeks, settle for the lowest level that was, as long as it is still a real saving
        if present >= 4 and mt >= 15:
            step = 5 if mt >= 30 else 1
            T = math.ceil(0.8 * mt / step) * step
            while T >= 10 and T <= 0.97 * mt and mt - T >= 3:
                met = sum(1 for x in totals if x < T)
                if met >= 3:
                    opt = make("under_amount", lab, "Keep %s under %s this week" % (_plural(lab), _eur0(T)),
                               "You usually spend about %s a week on %s and stayed under %s in %d of the last %d weeks." % (
                                   _eur0(mt), _plural(lab), _eur0(T), met, n),
                               float(T), "EUR", _r(mt), met, ev, ctx)
                    if fits(opt[0]):
                        picks.append(opt)
                        break
                T += step
        # fewer_times
        if present >= 4 and mc >= 2.5 and lab != "Night out":
            N = max(1, int(round(mc)) - 1)
            while N < mc - 0.4:
                met = sum(1 for c in counts if c <= N)
                if met >= 3:
                    opt = make("fewer_times", lab, "Keep %s to %d this week" % (_noun(lab), N),
                               "You usually have about %s %s a week and kept it to %d or fewer in %d of the last %d weeks." % (
                                   _words(round(mc)) if round(mc) <= 12 else round(mc), _noun(lab), N, met, n),
                               N, "purchases", round(mc, 2), met, ev, ctx)
                    if fits(opt[0]):
                        picks.append(opt)
                        break
                N += 1
        # none_this_week
        if present >= 3 and zero >= 3 and mc <= 1.3 and lab != "Night out":
            title = _FREE_TITLE.get(lab, "A week without %s" % _plural(lab))
            opt = make("none_this_week", lab, title,
                       "You went without %s in %d of the last %d weeks." % (_noun(lab), zero, n),
                       0, "purchases", round(mc, 2), zero, ev, ctx)
            if fits(opt[0]):
                picks.append(opt)
        if picks:
            best = max(picks, key=lambda p: (p[1], -order[p[0]["kind"]]))
            cands.append((best[1], order[best[0]["kind"]], best[0]))
    # free_days: the highest number reached in 3 of the weeks that still fits this week
    fd = [0] * n
    for i, w in enumerate(weeks):
        fd[i] = sum(1 for k in range(7) if (w + timedelta(days=k)) not in days_with)
    have = sum(1 for x in fd if x >= 1)
    # a day-count target is only fair with most of the week still ahead, so it is offered early in the week only
    if have >= 5 and _mean(fd) >= 1.0 and ((sun - t).days >= 4 or next_week):
        for N in range(sorted(fd, reverse=True)[2], 0, -1):
            met = sum(1 for x in fd if x >= N)
            opt, _m = make("free_days", "Everyday spending",
                           "%s day%s with no everyday spending this week" % (_words(N).capitalize(), "" if N == 1 else "s"),
                           "You usually have about %s days a week with no everyday purchases and reached %d in %d of the last %d weeks." % (
                               _words(round(_mean(fd))) if round(_mean(fd)) <= 12 else round(_mean(fd)), N, met, n),
                           N, "days", round(_mean(fd), 2), met,
                           [_ev("Everyday spending, last %d weeks" % n, ev_from, ev_to, basket="everyday")])
            if met >= 3 and fits(opt):
                cands.append((met, 3, opt))
                break
    ok = sorted(cands, key=lambda x: (-min(x[0], 5), x[1], x[2]["label"]))
    chosen, kinds, fam = [], {}, set()
    for met, rank, opt in ok:
        if kinds.get(opt["kind"], 0) >= 2:
            continue
        f = "dining" if opt["label"] in ("Restaurant", "Fast food", "Dining out") else opt["label"]
        if f in fam:
            continue
        fam.add(f)
        chosen.append(opt)
        kinds[opt["kind"]] = kinds.get(opt["kind"], 0) + 1
        if len(chosen) == 3:
            break
    if not chosen:
        return empty("I did not find a habit in your last %d weeks that would make a fair, easy challenge." % n)
    return {"options": chosen,
            "explain": "Built from your own last %d full weeks: each target is one you already reached in at least 3 "
                       "of them, so it is meant to be easy." % n}


def _free_days_so_far(conn, frm_d, last_d):
    c = 0
    d = frm_d
    while d <= last_d:
        n = ins._scalar(conn, "SELECT COUNT(*) FROM tx WHERE basket='everyday' AND amount<0 AND d=? AND " + _DISC_SQL,
                        (d.isoformat(),), default=0)
        if not n:
            c += 1
        d += timedelta(days=1)
    return c


def challenge_progress(conn, today, challenge):
    t = _d(today)
    ch = challenge or {}
    kind = ch.get("kind") or "under_amount"
    mon, sun = _week_bounds(t)
    per = ch.get("period") or {}
    try:
        frm_d, to_d = _d(per.get("from")), _d(per.get("to"))
    except (ValueError, TypeError):
        frm_d, to_d = mon, sun
    label, context = ch.get("label") or "", ch.get("context") or ""
    try:
        target = float(ch.get("target") or 0)
    except (TypeError, ValueError):
        target = 0.0
    title = ch.get("title") or "Your challenge"
    ended = t > to_d
    upto = min(t, to_d).isoformat()
    days_left = max(0, (to_d - t).days)
    baseline = ch.get("baseline")
    cid = ch.get("id")
    ev = [_label_ev(label, frm_d.isoformat(), to_d.isoformat(),
                    "This week: %s" % (ins.label_words(label) if label else "everyday spending"))] \
        if kind != "free_days" else [_ev("Everyday spending this week", frm_d.isoformat(), to_d.isoformat(), basket="everyday")]
    unit = ch.get("unit") or ("EUR" if kind == "under_amount" else "days" if kind == "free_days" else "purchases")
    pl = _plural(label) if label else "everyday spending"
    nn = _noun(label) if label else "purchases"

    def out(current, remaining, status, text):
        return {"id": cid, "title": title, "target": ch.get("target"), "unit": unit,
                "current": _r(current) if kind == "under_amount" else current,
                "remaining": _r(remaining) if kind == "under_amount" else remaining,
                "days_left": days_left, "status": status, "text": text, "evidence": ev}

    if t < frm_d:       # a challenge for next week: nothing counts yet
        return out(0, ch.get("target") or 0, "on_track",
                   "This challenge starts on Monday %s. Nothing counts until then." % ins.human_range(
                       frm_d.isoformat(), None, today))

    if kind == "free_days":
        last_done = to_d if ended else t - timedelta(days=1)
        cur = _free_days_so_far(conn, frm_d, last_done) if last_done >= frm_d else 0
        need = max(0, int(target) - cur)
        avail = 0 if ended else (to_d - t).days + 1
        if cur >= target:
            return out(cur, 0, "done", "Done: you have had %d day%s with no everyday spending. Nicely managed." % (
                cur, "" if cur == 1 else "s"))
        if ended or need > avail:
            return out(cur, need, "missed",
                       "Not this time, and that is fine. You still had %d spend-free day%s this week." % (
                           cur, "" if cur == 1 else "s"))
        if need == avail:
            return out(cur, need, "at_risk", "You have %d spend-free day%s so far; every remaining day counts, and "
                                              "it is completely fine either way." % (cur, "" if cur == 1 else "s"))
        return out(cur, need, "on_track", "%d of %d spend-free days so far, with %d day%s still to go. You are on track." % (
            cur, int(target), avail, "" if avail == 1 else "s"))

    euros, count = _spent_in(conn, label, context, frm_d.isoformat(), upto)
    if kind == "under_amount":
        cur, rem = euros, max(0.0, target - euros)
        if euros >= target:
            better = baseline is not None and euros < float(baseline)
            return out(cur, 0, "missed", "Not this time, and that is fine. You spent %s on %s%s." % (
                _eur0(euros), pl, ", still less than your usual %s" % _eur0(baseline) if better else ""))
        if ended:
            return out(cur, rem, "done", "Done: %s on %s, under your %s. Well done." % (_eur0(euros), pl, _eur0(target)))
        if euros >= 0.8 * target:
            return out(cur, rem, "at_risk", "%s spent on %s so far, %s left before %s. Close, and fine either way." % (
                _eur0(euros), pl, _eur0(rem), _eur0(target)))
        return out(cur, rem, "on_track", "%s spent on %s so far, with %s to spare this week. You are on track." % (
            _eur0(euros), pl, _eur0(rem)))
    # fewer_times and none_this_week count purchases
    N = int(target)
    cur, rem = count, max(0, N - count)
    if count > N:
        better = baseline is not None and count < float(baseline) + 0.0001 and N > 0
        return out(cur, 0, "missed", "Not this time, and that is fine. You had %d %s this week%s." % (
            count, nn, ", about your usual" if better else ""))
    if ended:
        if N == 0:
            return out(cur, 0, "done", "Done: a whole week without %s. Nicely done." % nn)
        return out(cur, rem, "done", "Done: %d %s this week, within your %d. Well done." % (count, nn, N))
    if N == 0:
        return out(cur, 0, "on_track", "No %s so far this week. Keep it going." % nn)
    if count == N:
        return out(cur, 0, "at_risk", "You are at %d of %d %s, so this is the last one that fits. Fine either way." % (
            count, N, nn))
    return out(cur, rem, "on_track", "%d of %d %s so far, so %d more fit. You are on track." % (count, N, nn, rem))


# --------------------------------------------------------------------------- quiz stats

def _accuracy(guess, actual):
    return max(0.0, 100.0 - 100.0 * abs(guess - actual) / max(actual, 10.0))


def quiz_stats(history):
    pts = []
    for h in history or []:
        try:
            g, a = float(h["guess"]), float(h["actual"])
        except (KeyError, TypeError, ValueError):
            continue
        pts.append({"at": str(h.get("at", "")), "label": h.get("label"), "guess": _r(g), "actual": _r(a),
                    "accuracy": round(_accuracy(g, a), 1)})
    pts.sort(key=lambda p: p["at"])
    n = len(pts)
    if n == 0:
        return {"count": 0, "awareness_score": None, "trend": None, "points": [], "best": None,
                "text": "No quiz answers yet. Try one and I will track how close your guesses get."}
    score = int(round(_mean(p["accuracy"] for p in pts[-5:])))
    trend = None
    if n >= 4:
        last3 = _mean(p["accuracy"] for p in pts[-3:])
        prev = _mean(p["accuracy"] for p in pts[-6:-3])
        diff = last3 - prev
        trend = "improving" if diff > 5 else "slipping" if diff < -5 else "steady"
    best = max(pts, key=lambda p: (p["accuracy"], p["at"]))
    text = "Your awareness score is %d out of 100, from your last %d answer%s." % (
        score, min(5, n), "" if min(5, n) == 1 else "s")
    if trend == "improving":
        text += " Your guesses are getting closer."
    elif trend == "steady":
        text += " It has been steady lately."
    elif trend == "slipping":
        text += " It dipped a little lately, which is normal when spending shifts."
    elif n < 4:
        text += " A few more answers will show a trend."
    return {"count": n, "awareness_score": score, "trend": trend, "points": pts, "best": best, "text": text}


# --------------------------------------------------------------------------- forecast

def _payday_window(conn, t, days):
    """(next_payday or None, last day of the window, whether the window ends on payday)."""
    pay = ins._usual_payday(conn, t)
    if days is not None:
        try:
            n = max(1, min(45, int(days)))
        except (TypeError, ValueError):
            n = 14
        return (ins._next_payday(t, pay) if pay is not None else None), t + timedelta(days=n), False
    if pay is None:
        return None, t + timedelta(days=30), False
    nxt = ins._next_payday(t, pay)
    return nxt, min(nxt, t + timedelta(days=45)), True


def forecast(conn, today, monthly_saving_target=0.0, days=None):
    t = _d(today)
    nxt, end, to_payday = _payday_window(conn, t, days)
    nd = max(1, (end - t).days)
    start = ins._balance(conn)
    if not _has_data(conn):
        return {"from": t.isoformat(), "to": end.isoformat(), "start_balance": 0.0, "points": [],
                "lowest": {"d": t.isoformat(), "balance": 0.0}, "goes_negative": False, "first_negative": None,
                "end_balance": 0.0, "text": "There is no transaction history yet, so I cannot forecast your balance.",
                "explain": "The forecast needs your past bills and spending.", "evidence": []}
    try:
        target = max(0.0, float(monthly_saving_target or 0.0))
    except (TypeError, ValueError):
        target = 0.0
    win_end = end if to_payday else end + timedelta(days=1)       # events due before this date
    m3 = ins._month_list(conn, t, 3)
    m6 = ins._month_list(conn, t, 6)
    ev_by = {}

    def add(due, label, amount):
        d = max(_d(due), t + timedelta(days=1))
        ev_by.setdefault(d, []).append({"label": label, "amount": _r(-amount)})

    for lab, typ in (("Housing", "housing_payment"), ("Utilities", "utilities_payment")):
        for e in ins._expected_events(conn, t, "type='%s'" % typ, m3, win_end):
            add(e["due"], lab, e["expected"])
    for e in ins._expected_events(conn, t, "type='investment_deposit'", m6, win_end):
        add(e["due"], "Planned saving", e["expected"])
    if target > 0:
        add(end.isoformat(), "Saving target", target * nd / 30.0)
    # typical spending per weekday: average of the last 8 weeks
    since = (t - timedelta(days=56)).isoformat()
    wk = [0.0] * 7
    for d, a in _rows(conn, "SELECT d, -amount FROM tx WHERE type='purchase' AND amount<0 AND basket IN "
                            "('regular','everyday') AND d>=? AND d<?", (since, t.isoformat())):
        wk[_d(d).weekday()] += float(a)
    wk = [x / 8.0 for x in wk]
    bal = start
    points = []
    for i in range(1, nd + 1):
        d = t + timedelta(days=i)
        events = ev_by.get(d, [])
        bal += sum(e["amount"] for e in events) - wk[d.weekday()]
        points.append({"d": d.isoformat(), "balance": _r(bal), "events": events})
    low = min(points, key=lambda p: p["balance"]) if points else {"d": t.isoformat(), "balance": _r(start)}
    neg = [p for p in points if p["balance"] < 0]
    first_neg = neg[0]["d"] if neg else None
    until = "payday on %s" % ins.human_range(nxt, None, today) if to_payday and nxt else "the next %d days" % nd
    if start < 0:
        # the balance is already negative: it does not "dip", it stays below (D10)
        rec = next((p for p in points if p["balance"] >= 0), None)
        head = "Your balance is already %s below zero and at your usual pace stays below until " % _eur0(-start)
        if rec:
            text = head + "%s." % ins.human_range(rec["d"], None, today)
        elif to_payday and nxt:
            text = head + "payday on %s." % ins.human_range(nxt, None, today)
        else:
            text = ("Your balance is already %s below zero and at your usual pace stays below zero for "
                    "the next %d days." % (_eur0(-start), nd))
    elif neg:
        text = "At your usual pace you would dip below zero around %s, about %s short." % (
            ins.human_range(first_neg, None, today), _eur0(-low["balance"]))
    else:
        floor = math.floor(low["balance"] / 10.0) * 10
        text = "At your usual pace your balance stays above %s until %s." % (_eur0(floor), until)
    return {"from": t.isoformat(), "to": end.isoformat(), "start_balance": _r(start), "points": points,
            "lowest": {"d": low["d"], "balance": _r(low["balance"])}, "goes_negative": bool(neg),
            "first_negative": first_neg, "end_balance": points[-1]["balance"] if points else _r(start),
            "text": text,
            "explain": "Starts from your balance now, takes off expected bills and planned savings on their usual days "
                       "and your typical spending for each weekday (average of the last 8 weeks).",
            "evidence": [_ev("Latest transactions", (t - timedelta(days=14)).isoformat(), t.isoformat()),
                         _ev("Spending, last 8 weeks", since, t.isoformat(), basket="everyday"),
                         _ev("Spending, last 8 weeks", since, t.isoformat(), basket="regular")]}


# --------------------------------------------------------------------------- payday plan

def payday_plan(conn, today, goal=None, monthly_saving_target=0.0):
    t = _d(today)
    empty = {"next_payday": None, "expected_salary": 0.0, "lines": [], "everyday_per_week": None,
             "everyday_per_day": None, "goal_line": None,
             "text": "I have not seen a salary yet, so I cannot suggest a split. This is a plan, not a transfer.",
             "explain": "The plan splits your usual salary using your own past bills, spending and savings.",
             "evidence": []}
    if not _has_data(conn):
        return empty
    pay = ins._usual_payday(conn, t)
    nxt = ins._next_payday(t, pay) if pay is not None else None
    m6 = ins._month_list(conn, t, 6)
    sal = []
    for a, b in m6:
        v = ins._scalar(conn, "SELECT SUM(amount) FROM tx WHERE type='salary' AND d>=? AND d<=?", (a, b))
        if v and v > 0:
            sal.append(float(v))
    if not sal:
        return empty
    salary = _r(_median(sal))
    m3 = ins._month_list(conn, t, 3)
    reg = _median([_month_totals(conn, m, "basket='regular'") for m in m3]) if m3 else 0.0
    unexp = ins._avg_where(conn, ins._month_list(conn, t, 12), "basket='unexpected'")
    try:
        target = max(0.0, float(monthly_saving_target or 0.0))
    except (TypeError, ValueError):
        target = 0.0
    dep = 0.0
    if m6:
        dep = (ins._scalar(conn, "SELECT -SUM(amount) FROM tx WHERE type='investment_deposit' AND d>=? AND d<=?",
                           (m6[0][0], m6[-1][1])) or 0.0) / len(m6)
    # D20: when the balance is forecast to be below zero on payday, the plan first covers that gap
    shortfall = 0.0
    if nxt is not None:
        fc = forecast(conn, today, monthly_saving_target)
        if fc.get("to") == nxt.isoformat() and float(fc.get("end_balance") or 0.0) < 0:
            shortfall = -float(fc["end_balance"])
    left = salary - reg - unexp - shortfall
    if shortfall > 0:
        sav, why_s = 0.0, "Nothing is set aside while your balance is forecast to be below zero on payday."
    elif target > 0:
        sav, why_s = target, "Your saving target."
    elif dep > 0:
        sav, why_s = dep, "What you usually put into investments each month."
    else:
        s10 = 0.1 * left
        if left > 0 and (left - s10) / _DAYS_PER_MONTH >= 15:
            sav, why_s = s10, "10% of what is left after bills and the buffer."
        else:
            sav, why_s = 0.0, "Not enough left over for a regular saving yet."
    if left - sav < 0:
        sav, why_s = 0.0, "Set to zero because the month does not cover the basics."
    reg_r, unexp_r, sav_r, sf_r = _r(reg), _r(unexp), _r(sav), _r(shortfall)
    ev_r = _r(salary - sf_r - reg_r - unexp_r - sav_r)
    # when the basics alone are more than the salary, everyday goes negative; the gap is also reported
    gap_r = _r(-ev_r) if ev_r < 0 else 0.0

    def share(x):
        return round(x / salary, 3) if salary > 0 else None

    lines = []
    if sf_r > 0:
        lines.append({"key": "shortfall", "name": "Cover the shortfall", "amount": sf_r, "share": share(sf_r),
                      "why": "Your balance is forecast to be %s below zero on payday, so this goes first." % _eur0(sf_r)})
    lines += [
        {"key": "regular", "name": "Regular essentials", "amount": reg_r, "share": share(reg_r),
         "why": "Housing, utilities, groceries and other basics, based on your last 3 full months."},
        {"key": "unexpected", "name": "Unexpected necessities", "amount": unexp_r, "share": share(unexp_r),
         "why": "Your average monthly unexpected costs, so the buffer refills."},
        {"key": "savings", "name": "Savings", "amount": sav_r, "share": share(sav_r), "why": why_s},
        {"key": "everyday", "name": "Everyday spending", "amount": ev_r, "share": share(ev_r),
         "why": "What is left for choices like eating out and hobbies."},
    ]
    per_day = ev_r / _DAYS_PER_MONTH
    gl = None
    if isinstance(goal, dict) and goal.get("name"):
        try:
            remaining = max(0.0, float(goal.get("target") or 0) - float(goal.get("saved") or 0))
        except (TypeError, ValueError):
            remaining = 0.0
        gl = {"name": str(goal["name"]), "amount": sav_r,
              "months_to_goal": round(remaining / sav_r, 1) if sav_r > 0 else None}
    when = " on %s" % ins.human_range(nxt, None, today) if nxt else ""
    sf_text = ("First %s covers the gap your balance is forecast to have on payday. " % _eur0(sf_r)) if sf_r > 0 else ""
    if gap_r > 0:
        items = "%sregular bills (%s) and the unexpected buffer (%s)" % (
            ("the shortfall (%s), " % _eur0(sf_r)) if sf_r > 0 else "", _eur0(reg_r), _eur0(unexp_r))
        text = ("Your expected salary of %s%s does not cover the basics: %s come to %s more than that. "
                "This is a plan, not a transfer." % (_eur0(salary), when, items, _eur0(gap_r)))
    else:
        text = sf_text + ("Of your expected %s salary%s: %s regular essentials, %s for unexpected costs, %s savings and %s "
                "everyday (about %s a day). This is a plan, not a transfer." % (
                    _eur0(salary), when, _eur0(reg_r), _eur0(unexp_r), _eur0(sav_r), _eur0(ev_r), _eur0(per_day)))
    ev = []
    if m3:
        ev.append(_ev("Regular essentials, last 3 months", m3[0][0], m3[-1][1], basket="regular"))
    ev.append(_ev("Salary payments", m6[0][0], m6[-1][1], type="salary") if m6 else _ev("Salary payments", type="salary"))
    return {"next_payday": nxt.isoformat() if nxt else None, "expected_salary": salary, "lines": lines,
            "everyday_per_week": _r(per_day * 7), "everyday_per_day": _r(per_day), "goal_line": gl,
            "shortfall": _r(sf_r + gap_r), "not_covered": gap_r,
            "text": text,
            "explain": "Your usual salary is split into regular essentials (the typical month of the last 3), the unexpected "
                       "buffer (12-month average), savings and what remains for everyday spending.",
            "evidence": ev}


# --------------------------------------------------------------------------- purchase insight

_ORD = ["zeroth", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]
_PURCHASE_NOUN = {"Fast food": "fast-food", "Night out": "night-out", "Gym & sports": "gym and sports",
                  "Events": "event", "Hobbies": "hobby", "Books": "book", "Home improvement": "home-improvement",
                  "Other": ""}
_ESSENTIAL_NOTE = "Essentials like rent, utilities and groceries are not annualised, because they are not a habit to trim."
_ITEM_NOTE = ("Item-level detail (what was in the basket) needs receipt data, which the challenge dataset does not "
              "contain.")


def _ordinal(n):
    return _ORD[n] if 0 <= n < len(_ORD) else "%dth" % n


def _round_text(x):
    """Round a yearly figure for wording: nearest 10 from 100 up, nearest 5 below."""
    return round(x / 10.0) * 10 if x >= 100 else round(x / 5.0) * 5


def purchase_insight(conn, today, tx_id=None):
    t = _d(today)
    base = {"tx": None, "habit": None, "text": None, "equivalents": [], "note": _ITEM_NOTE,
            "explain": "The latest purchase is compared with how often you buy the same kind of thing.",
            "evidence": []}
    sel = ("SELECT id, d, ts, -amount, %s, basket, COALESCE(NULLIF(label,''),'Other') FROM tx "
           "WHERE type='purchase' AND amount<0" % _DISP)
    if tx_id is not None:
        if isinstance(tx_id, bool):
            return base
        try:
            tx_id = int(tx_id)
        except (TypeError, ValueError):
            return base
        rows = _rows(conn, sel + " AND id=?", (tx_id,))
    else:
        rows = _rows(conn, sel + " ORDER BY ts DESC, id DESC LIMIT 1")
    if not rows:
        base["note"] = "There is no purchase to look at yet. " + _ITEM_NOTE
        return base
    rid, rd, rts, amt, lab, basket, base_lab = rows[0]
    td = _d(rd)
    display = str(lab)
    # the base category is the name (house rule m18); "Night out" is only a tag on it
    night_tag = display == "Night out" and str(base_lab) != "Night out"
    txd = {"id": rid, "d": str(rd)[:10], "label": str(base_lab) if night_tag else display,
           "display_label": display, "amount": _r(amt)}
    if night_tag:
        txd["tag"] = "night out"
    mon = td - timedelta(days=td.weekday())
    wk = _rows(conn, "SELECT COUNT(*) FROM tx WHERE type='purchase' AND amount<0 AND d>=? AND ts<=? AND "
                     + _DISP + "=?", (mon.isoformat(), str(rts), display))
    times = max(1, int(wk[0][0]) if wk else 1)
    habit = {"label": display, "times_this_week": times, "per_week": None, "avg_amount": None,
             "monthly": None, "yearly": None}
    out = dict(base)
    out["tx"] = txd
    out["habit"] = habit
    if basket == "regular":
        out["note"] = _ESSENTIAL_NOTE + " " + _ITEM_NOTE
        out["explain"] = "Regular essentials are not turned into a yearly figure."
        return out
    first = ins._scalar(conn, "SELECT MIN(d) FROM tx", default=None)
    weeks_avail = min(8, (mon - _d(first)).days // 7) if first is not None else 0
    if weeks_avail < 4:
        out["note"] = "There are not yet four full weeks of history to see a habit. " + _ITEM_NOTE
        return out
    w_from = (mon - timedelta(days=7 * weeks_avail)).isoformat()
    w_to = (mon - timedelta(days=1)).isoformat()
    r = _rows(conn, "SELECT COUNT(*), COALESCE(SUM(-amount),0) FROM tx WHERE type='purchase' AND amount<0 AND "
                    "d>=? AND d<=? AND " + _DISP + "=?", (w_from, w_to, display))
    cnt, tot = (int(r[0][0]), float(r[0][1])) if r else (0, 0.0)
    ev = [_label_ev(display, w_from, w_to, "%s, last %d weeks" % (display, weeks_avail))]
    if cnt == 0:
        out["note"] = ("This kind of purchase has not appeared in the last %d weeks, so there is no habit to project. %s"
                       % (weeks_avail, _ITEM_NOTE))
        out["evidence"] = ev
        return out
    per_week = cnt / float(weeks_avail)
    avg_amount = tot / cnt
    yearly = per_week * avg_amount * 52
    monthly = yearly / 12.0
    habit.update({"per_week": round(per_week, 2), "avg_amount": _r(avg_amount), "monthly": _r(monthly),
                  "yearly": _r(yearly)})
    noun = _PURCHASE_NOUN.get(str(base_lab) if night_tag else display, (str(base_lab) if night_tag else display).lower())
    if yearly < 50:
        out["note"] = "This is a small, occasional purchase, so I do not turn it into a yearly figure. " + _ITEM_NOTE
        out["evidence"] = ev
        return out
    if times >= 2:
        lead = "That was your %s%s purchase this week." % (_ordinal(times), (" " + noun) if noun else "")
    elif noun:
        lead = "That was %s %s purchase of %s." % ("an" if noun[0] in "aeiou" else "a", noun, _eur0(amt))
    else:
        lead = "That was a purchase of %s." % _eur0(amt)
    if per_week >= 1:
        pace = "At this pace it is about %s a year." % _eur0(_round_text(yearly))
    else:
        gap_w = round(1 / per_week)
        pace = "You usually make one about every %s weeks, which comes to about %s a year." % (
            _words(gap_w) if gap_w <= 12 else gap_w, _eur0(_round_text(yearly)))
    if night_tag:
        lead = lead[:-1] + ", on a night out."
    out["text"] = "%s %s" % (lead, pace)
    eq = []
    m6 = ins._month_list(conn, t, 6)
    ev_avg = float(ins._avg_flows(conn, m6)["baskets"]["everyday"]) if m6 else 0.0
    if basket == "everyday" and ev_avg > 0:
        eq.append("Each month this habit is about %s, around %s of your everyday spending." % (
            _eur0(monthly), ins._pct_text(monthly / ev_avg)))
    try:
        per_day = float(ins.safe_to_spend(conn, today)["per_day"])
    except Exception:
        per_day = 0.0
    if per_day >= 5 and yearly / per_day >= 2:
        eq.append("A year of it equals about %s of your safe-to-spend at %s a day." % (
            _span_words(yearly / per_day), _eur0(per_day)))
    out["equivalents"] = eq[:2]
    out["explain"] = ("Counts your %s purchases over the last %d full weeks (%.1f a week, %s each on average) and "
                      "multiplies by 52." % (_PURCHASE_NOUN.get(display, display.lower()), weeks_avail, per_week,
                                             _eur(avg_amount)))
    out["evidence"] = ev
    return out


# --------------------------------------------------------------------------- patterns

_PARTS = (("morning", "mornings"), ("day", "afternoons"), ("evening", "evenings"), ("night", "nights"))


def _part_of(h):
    if 6 <= h < 11:
        return 0
    if 11 <= h < 17:
        return 1
    if 17 <= h < 23:
        return 2
    return 3


def _parse_ts(ts, d):
    try:
        return datetime.fromisoformat(str(ts)[:19].replace("T", " "))
    except ValueError:
        try:
            x = _d(d)
            return datetime(x.year, x.month, x.day, 12, 0, 0)
        except ValueError:
            return None


def _top_extra(mine, other, k=2):
    """Labels that make up the extra: average per occurrence in the slot minus the same on other days."""
    diffs = sorted(((v - other.get(lab, 0.0), lab) for lab, v in mine.items()), reverse=True)
    return [(lab, dv) for dv, lab in diffs if dv >= 2][:k]


def patterns(conn, today, weeks=12):
    t = _d(today)
    try:
        weeks = max(4, min(26, int(weeks)))
    except (TypeError, ValueError):
        weeks = 12
    empty = {"patterns": [], "explain": "Patterns need at least six weeks of everyday spending to compare."}
    if not _has_data(conn):
        return empty
    mon = t - timedelta(days=t.weekday())
    first = _d(ins._scalar(conn, "SELECT MIN(d) FROM tx", default=today))
    n_w = min(weeks, (mon - first).days // 7)
    if n_w < 6:
        return empty
    w0 = mon - timedelta(days=7 * n_w)
    frm, to = w0.isoformat(), (mon - timedelta(days=1)).isoformat()
    raw = _rows(conn, "SELECT d, ts, -amount, %s FROM tx WHERE basket='everyday' AND amount<0 AND d>=? AND d<=?" % _DISP,
                (frm, to))
    items = []   # (datetime, slot_date, part, amount, label)
    for d, ts, a, lab in raw:
        dt = _parse_ts(ts, d)
        if dt is None:
            continue
        slot_date = dt.date()
        if dt.hour < 6:
            slot_date -= timedelta(days=1)       # late night belongs to the evening that started it
        if slot_date < w0 or slot_date >= mon:
            continue
        items.append((dt, slot_date, _part_of(dt.hour), float(a), lab))
    if not items:
        return empty
    ev_all = [_ev("Everyday spending, last %d weeks" % n_w, frm, to, basket="everyday")]
    found = []

    # ---- time peak
    slot_tot, slot_cnt, slot_lab = {}, {}, {}
    for dt, sd, part, a, lab in items:
        key = (sd.weekday(), part)
        wi = (sd - w0).days // 7
        slot_tot.setdefault(key, {})
        slot_tot[key][wi] = slot_tot[key].get(wi, 0.0) + a
        slot_cnt[key] = slot_cnt.get(key, 0) + 1
        e = slot_lab.setdefault(key, {})
        e[lab] = e.get(lab, 0.0) + a
    best = None
    for (wd, part), per in slot_tot.items():
        if len(per) < 6:
            continue
        slot_avg = sum(per.values()) / n_w
        other_sum = sum(sum(slot_tot.get((w2, part), {}).values()) for w2 in range(7) if w2 != wd)
        other_avg = other_sum / (6.0 * n_w)
        if other_avg <= 0:
            continue
        diff = slot_avg - other_avg
        if slot_avg >= 1.3 * other_avg and diff >= 15 and (best is None or diff > best[0]):
            best = (diff, wd, part, slot_avg, other_avg)
    if best:
        diff, wd, part, slot_avg, other_avg = best
        key = (wd, part)
        uplift = int(round((slot_avg / other_avg - 1) * 100))
        pname = _PARTS[part][1]
        wdn = _WEEKDAYS_FULL[wd]
        mine = {k: v / n_w for k, v in slot_lab.get(key, {}).items()}
        oth = {}
        for w2 in range(7):
            if w2 != wd:
                for k, v in slot_lab.get((w2, part), {}).items():
                    oth[k] = oth.get(k, 0.0) + v / (6.0 * n_w)
        why = []
        tops = _top_extra(mine, oth)
        if tops:
            why.append("The extra comes mostly from %s on an average %s %s." % (
                " and ".join("%s (about %s more)" % (lab.lower(), _eur0(dv)) for lab, dv in tops), wdn, pname[:-1]))
        typ_cnt = slot_cnt.get(key, 0) / float(n_w)
        oth_cnt = sum(slot_cnt.get((w2, part), 0) for w2 in range(7) if w2 != wd) / (6.0 * n_w)
        why.append("A %s %s usually has %.1f purchases, against %.1f in the same part of other days." % (
            wdn, pname[:-1], typ_cnt, oth_cnt))
        why.append("Your %s %s average %s against %s on other days, and it showed up in %d of the last %d weeks." % (
            wdn, pname, _eur0(slot_avg), _eur0(other_avg), len(slot_tot[key]), n_w))
        found.append({"id": "time_peak:%s-%s" % (_WEEKDAYS[wd].lower(), _PARTS[part][0]), "kind": "time_peak",
                      "title": "%s %s" % (wdn, pname), "uplift_pct": uplift,
                      "text": "I noticed your spending is %s on %s %s." % (ins.higher_words(uplift), wdn, pname),
                      "question": "Want to hear why?", "why": why[:3],
                      "evidence": ev_all + [_ev("%s %s" % (wdn, pname), frm, to, basket="everyday")]})

    # ---- after payday
    daily, labs_day = {}, {}
    for dt, sd, part, a, lab in items:
        dd = dt.date()
        daily[dd] = daily.get(dd, 0.0) + a
        m = labs_day.setdefault(dd, {})
        m[lab] = m.get(lab, 0.0) + a
    ndays = (mon - w0).days
    daily_avg = sum(daily.values()) / ndays if ndays else 0.0
    sal = sorted({_d(r[0]) for r in _rows(conn, "SELECT d FROM tx WHERE type='salary' AND d>=? AND d<=?",
                                          ((w0 - timedelta(days=3)).isoformat(), to))})
    post_days, paydays_used = set(), []
    for p in sal:
        span = [p + timedelta(days=k) for k in (1, 2, 3)]
        if span[0] < w0 or span[-1] >= mon:
            continue
        paydays_used.append(p)
        post_days.update(span)
    if len(paydays_used) >= 2 and daily_avg > 0:
        post_avg = sum(daily.get(d, 0.0) for d in post_days) / len(post_days)
        if post_avg >= 1.4 * daily_avg and post_avg - daily_avg >= 5:
            uplift = int(round((post_avg / daily_avg - 1) * 100))
            above = sum(1 for p in paydays_used
                        if sum(daily.get(p + timedelta(days=k), 0.0) for k in (1, 2, 3)) / 3.0 > daily_avg)
            lab_post, lab_all = {}, {}
            for d, m in labs_day.items():
                for k, v in m.items():
                    lab_all[k] = lab_all.get(k, 0.0) + v
                    if d in post_days:
                        lab_post[k] = lab_post.get(k, 0.0) + v
            tops = _top_extra({k: v / len(post_days) for k, v in lab_post.items()},
                              {k: v / ndays for k, v in lab_all.items()})
            why = []
            if tops:
                why.append("The extra comes mostly from %s per day." % " and ".join(
                    "%s (about %s more)" % (lab.lower(), _eur0(dv)) for lab, dv in tops))
            why.append("It was above your daily average after %d of the last %d paydays." % (above, len(paydays_used)))
            why.append("In the 3 days after payday you spend about %s a day, against %s on an average day." % (
                _eur0(post_avg), _eur0(daily_avg)))
            found.append({"id": "after_payday", "kind": "after_payday", "title": "The days after payday",
                          "uplift_pct": uplift,
                          "text": "I noticed your everyday spending is %s in the 3 days after payday." % (
                              ins.higher_words(uplift)),
                          "question": "Want to hear why?", "why": why[:3],
                          "evidence": ev_all + [_ev("Salary payments", frm, to, type="salary")]})

    # ---- bursts
    seq = sorted(items, key=lambda x: x[0])
    occasions = []
    i = 0
    while i < len(seq):
        j = i
        while j + 1 < len(seq) and (seq[j + 1][0] - seq[i][0]).total_seconds() <= 7200:
            j += 1
        if j - i + 1 >= 3:
            occasions.append(seq[i:j + 1])
            i = j + 1
        else:
            i += 1
    if len(occasions) >= 4:
        burst_days = {o[0][0].date() for o in occasions}
        b_avg = sum(daily.get(d, 0.0) for d in burst_days) / len(burst_days)
        other_days = [v for d, v in daily.items() if d not in burst_days]
        o_avg = sum(other_days) / len(other_days) if other_days else 0.0
        uplift = int(round((b_avg / o_avg - 1) * 100)) if o_avg > 0 else None
        sizes = [len(o) for o in occasions]
        totals = [sum(x[3] for x in o) for o in occasions]
        lab_c, wdc = {}, {}
        for o in occasions:
            for x in o:
                lab_c[x[4]] = lab_c.get(x[4], 0) + 1
            wdc[o[0][0].weekday()] = wdc.get(o[0][0].weekday(), 0) + 1
        top_l = sorted(lab_c.items(), key=lambda kv: (-kv[1], kv[0]))[:2]
        top_wd = sorted(wdc.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        why = ["A burst usually has %.1f purchases adding up to about %s." % (_mean(sizes), _eur0(_mean(totals))),
               "Most of the purchases in them are %s." % " and ".join("%s (%d)" % (k.lower(), v) for k, v in top_l),
               "%d of the %d bursts started on a %s." % (top_wd[1], len(occasions), _WEEKDAYS_FULL[top_wd[0]])]
        found.append({"id": "burst", "kind": "burst", "title": "Purchases close together", "uplift_pct": uplift,
                      "text": "On %d occasions in the last %d weeks you made 3 or more everyday purchases within two hours."
                              % (len(occasions), n_w),
                      "question": "Want to hear why?", "why": why[:3], "evidence": ev_all})
    found = found[:3]
    if not found:
        return {"patterns": [],
                "explain": "Compared your everyday spending by weekday and time of day, the days after payday and "
                           "purchases close together over the last %d weeks; nothing stands out clearly." % n_w}
    return {"patterns": found,
            "explain": ("Built from your everyday purchases in the last %d full weeks. A pattern is shown only when "
                        "the difference is large and repeated: a weekday and time of day at least 30%% and %s above the "
                        "same time on other days (in six or more weeks), the 3 days after payday at least 40%% above "
                        "your daily average, or three purchases within two hours on four or more occasions." % (
                            n_w, _eur0(15)))}


# --------------------------------------------------------------------------- goal plan

def _parse_deadline(deadline):
    """Return (date, bare_year) or (None, False)."""
    if deadline is None:
        return None, False
    m = re.fullmatch(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", str(deadline).strip())
    if not m:
        return None, False
    y = int(m.group(1))
    try:
        if m.group(2) is None:
            return date(y, 6, 30), True
        mo = int(m.group(2))
        if not 1 <= mo <= 12:
            return None, False
        if m.group(3) is None:
            return date(y, mo, ins._last_day(y, mo)), False
        return date(y, mo, int(m.group(3))), False
    except ValueError:
        return None, False


def _months_between(a, b):
    n = (b.year - a.year) * 12 + (b.month - a.month)
    if b.day < a.day:
        n -= 1
    return max(1, n)


def goal_plan(conn, today, name, target=None, deadline=None, saved=0.0, monthly_saving_target=0.0):
    t = _d(today)
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:80] or "your goal"
    try:
        tgt = float(target) if target is not None else None
    except (TypeError, ValueError):
        tgt = None
    if tgt is not None and (math.isnan(tgt) or math.isinf(tgt) or tgt <= 0):
        tgt = None
    try:
        sv = max(0.0, float(saved or 0.0))
    except (TypeError, ValueError):
        sv = 0.0
    try:
        mst = max(0.0, float(monthly_saving_target or 0.0))
    except (TypeError, ValueError):
        mst = 0.0
    dl, bare = _parse_deadline(deadline)
    past = dl is not None and dl <= t
    needs = []
    if tgt is None:
        needs.append("target")
    if dl is None or past:
        needs.append("deadline")
    out = {"name": name, "target": None if tgt is None else _r(tgt),
           "deadline": dl.isoformat() if (dl and not past) else None,
           "months_left": None, "saved": _r(sv), "monthly_needed": None, "current_monthly_saving": None,
           "gap": None, "feasible": None, "needs": needs, "text": "", "ways": [],
           "goal": {"name": name, "target": _r(tgt), "saved": _r(sv)} if tgt is not None else None,
           "explain": "The monthly amount is the part of the target still to save divided by the whole months left.",
           "evidence": []}
    if needs:
        out["no_card"] = True      # nothing to show as a card while the amount or the date is still missing
        if len(needs) == 2:
            out["text"] = "How much would %s cost, and by when do you want it? A rough figure and a year is enough." % name
        elif needs == ["target"]:
            out["text"] = "How much would %s cost? Give me a rough figure and I will work out the monthly saving." % name
        elif past:
            out["text"] = "That date has already passed. By when do you want to reach %s? A year or a month is enough." % _eur0(tgt)
        else:
            out["text"] = "By when do you want to reach %s for %s? A year or a month is enough." % (_eur0(tgt), name)
        return out
    months_left = _months_between(t, dl)
    remaining = max(0.0, tgt - sv)
    needed = float(math.ceil(round(remaining / months_left, 6)))    # one rounding (up) in the text and the fields
    m6 = ins._month_list(conn, t, 6)
    if mst > 0:
        current, src = mst, "your saving target"
    elif m6:
        current = float(ins._avg_flows(conn, m6)["kept"])
        src = "what you keep after spending, averaged over the last %d months" % len(m6)
    else:
        current, src = 0.0, "no history yet"
    gap = float(math.ceil(round(max(0.0, needed - max(0.0, current)), 6)))
    feasible = current >= needed
    ways = []
    if gap > 0:
        ideas = sorted(ins.save_more(conn, today).get("ideas") or [], key=lambda i: -float(i["saved_monthly"]))
        acc = 0.0
        for idea in ideas:
            ways.append({"title": idea["title"], "saved_monthly": _r(idea["saved_monthly"])})
            acc += float(idea["saved_monthly"])
            if acc >= gap or len(ways) == 3:
                break
    lead = "To have %s for %s by %s" % (_eur0(tgt), name, ins.human_month(dl.strftime("%Y-%m"), today))
    if sv > 0:
        lead += " (you have %s already)" % _eur0(sv)
    if remaining <= 0:
        text = "You have already reached %s for %s." % (_eur0(tgt), name)
    else:
        text = "%s you need to put aside about %s a month for %d month%s." % (
            lead, _eur0(needed), months_left, "" if months_left == 1 else "s")
        if m6 or mst > 0:
            if feasible:
                text += " That fits: you currently set aside or keep about %s a month (%s)." % (_eur0(current), src)
            elif current > 0.005:
                text += " You currently set aside or keep about %s a month (%s), so about %s a month is missing." % (
                    _eur0(current), src, _eur0(gap))
            else:
                text += " You are not keeping anything after spending right now, so the whole amount is missing."
    if bare:
        text += " You said just a year, so I used 30 June %d." % dl.year
    out.update({"months_left": months_left, "monthly_needed": _r(needed), "current_monthly_saving": _r(current),
                "gap": _r(gap), "feasible": bool(feasible), "text": text, "ways": ways,
                "explain": "Monthly saving needed = (%s target minus %s saved) divided by %d whole months left. "
                           "Current saving is %s." % (_eur0(tgt), _eur0(sv), months_left, src),
                "evidence": [_ev("Income", m6[0][0], m6[-1][1], type="salary")] if m6 else []})
    return out
