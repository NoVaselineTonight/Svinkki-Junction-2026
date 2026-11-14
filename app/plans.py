"""Savings plans, home-page widgets and next steps: the sums and the data shapes (Contract C of the judges' round).

Everything here is worked out by code from the customer's own figures. `preview` is pure (no I/O). The widget
builders read a sandbox connection `conn` through app.insights and app.trends. The state store is only touched by
app/server.py. Every text exists in English and Finnish (`x` and `x_fi`).

The coach tool `propose_plan` (same shape as app/invest.py) returns a plan_offer card and saves nothing.
"""
import calendar
import datetime
import math

TARGET_MAX = 1_000_000
MAX_MONTHS = 600          # a plan longer than 50 years is a typing error
MAX_POINTS = 36
MIN_MOVE = 5.0            # app.money.MIN_AMOUNT
MAX_NAME = 60


# --------------------------------------------------------------------------- small helpers

def _date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v)[:10])


def _add_months(d, n):
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    m += 1
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _parse_deadline(v):
    """'YYYY-MM-DD' or 'YYYY-MM' (the last day of that month) -> date. ValueError otherwise."""
    s = str(v or "")
    try:
        if len(s) == 7:
            y, m = int(s[:4]), int(s[5:7])
            return datetime.date(y, m, calendar.monthrange(y, m)[1])
        if len(s) == 10:
            return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    raise ValueError("deadline must be YYYY-MM or YYYY-MM-DD")


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(name + " must be a number")
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(name + " out of range")
    return v


def eur(v):
    """English money: whole euros from 20 up, cents below (and for a figure that is not whole)."""
    v = float(v or 0)
    if abs(v) >= 20 or round(v, 2) == round(v):
        return "€{:,.0f}".format(v)
    return "€{:,.2f}".format(v)


def eur_fi(v):
    """Finnish money: '1 583 €', '92,85 €' (no-break spaces)."""
    v = float(v or 0)
    s = "{:,.0f}".format(v) if (abs(v) >= 20 or round(v, 2) == round(v)) else "{:,.2f}".format(v)
    s = s.replace(",", " ") if "." not in s else s.replace(",", " ").replace(".", ",")
    return s + " €"


def _months_between(a, b):
    return (b.year - a.year) * 12 + b.month - a.month


def _ym(d):
    return "%04d-%02d" % (d.year, d.month)


# --------------------------------------------------------------------------- the plan maths

STATUS_TEXT = {
    "done": ("Goal reached", "Tavoite saavutettu"),
    "ahead": ("Ahead of plan", "Edellä suunnitelmaa"),
    "on_track": ("On track", "Aikataulussa"),
    "behind": ("A little behind", "Hieman jäljessä"),
    "not_started": ("Not started yet", "Ei vielä aloitettu"),
}


def _note(monthly, leftover):
    """One plain sentence on how the monthly amount sits against what a usual month leaves: (en, fi)."""
    if leftover is None or monthly is None or monthly <= 0:
        return "", ""
    if leftover <= 0:
        return ("A usual month leaves little over, so this would need a trim somewhere.",
                "Tavallisesta kuukaudesta jää vähän yli, joten tämä vaatisi karsimista jostakin.")
    r = monthly / leftover
    if r > 1.0:
        return ("That is more than a usual month leaves you, so it would need a trim somewhere.",
                "Se on enemmän kuin tavallisesta kuukaudesta jää, joten se vaatisi karsimista jostakin.")
    for top, en, fi in (
            (0.12, "a small part of", "pieni osa siitä,"),
            (0.2, "about a fifth of", "noin viidennes siitä,"),
            (0.28, "about a quarter of", "noin neljännes siitä,"),
            (0.4, "about a third of", "noin kolmannes siitä,"),
            (0.6, "about half of", "noin puolet siitä,"),
            (0.85, "most of", "suurin osa siitä,"),
            (1.0, "nearly all of", "lähes kaikki siitä,")):
        if r <= top:
            return ("That is %s what a usual month leaves you." % en,
                    "Se on %s mitä tavallisesta kuukaudesta jää." % fi)
    return "", ""


def _series(today, saved, target, monthly, months):
    """Cumulative planned amount per month: the current month is the start (planned = actual = saved), then each
    month up to the deadline. At most MAX_POINTS points, thinned evenly when the plan is long."""
    idx = list(range(months + 1))
    if len(idx) > MAX_POINTS:
        idx = sorted({round(k * months / (MAX_POINTS - 1)) for k in range(MAX_POINTS)})
    first = datetime.date(today.year, today.month, 1)
    out = []
    for i in idx:
        planned = target if i >= months else min(target, saved + monthly * i)
        out.append({"ym": _ym(_add_months(first, i)), "planned": round(float(planned), 2),
                    "actual": round(float(saved), 2) if i == 0 else None})
    return out


def preview(target, monthly=None, deadline=None, today=None, saved=0, usual_leftover=None, name=None,
            can_move=None):
    """The 'plan data' of Contract C. Works out the missing one of monthly/deadline (the deadline wins when both
    are given). ValueError for a bad target, monthly or deadline. Nothing is stored."""
    t = _date(today or datetime.date.today())
    target = _num(target, "target")
    if not 1 <= target <= TARGET_MAX:
        raise ValueError("target must be between 1 and %d" % TARGET_MAX)
    saved = max(0.0, _num(saved or 0, "saved"))
    remaining = max(0.0, target - saved)
    dl = None
    if deadline not in (None, ""):
        dl = _parse_deadline(deadline)
        if dl <= t:
            raise ValueError("deadline must be in the future")
    if monthly in (None, ""):
        monthly = None
    else:
        monthly = _num(monthly, "monthly")
        if monthly < 1:
            raise ValueError("monthly must be at least 1")
    pace = monthly
    if remaining <= 0:
        months, monthly, dl = 0, 0.0, None
    elif dl is not None:
        months = max(1, _months_between(t, dl))
        if months > MAX_MONTHS:
            raise ValueError("deadline too far away")
        needed = float(math.ceil(remaining / months))
        pace = float(math.ceil(monthly)) if monthly is not None else needed   # the pace the plan was made with
        monthly = max(pace, needed)
    elif monthly is not None:
        monthly = float(math.ceil(monthly))
        months = int(math.ceil(remaining / monthly))
        if months > MAX_MONTHS:
            raise ValueError("monthly too small for this target")
        monthly = float(min(monthly, math.ceil(remaining)))
        dl = _add_months(t, months)
        pace = monthly
    else:
        raise ValueError("a monthly amount or a deadline is needed")

    # where the plan should be today, had it been followed since the start: what is still to come at the
    # monthly pace is what must be left, so expected = target - monthly * months_left (no start date needed)
    if remaining <= 0:
        status = "done"
    else:
        expected = target - pace * months
        slack = saved - max(0.0, expected)
        if saved <= 0 and expected <= 0:
            status = "not_started"
        elif slack >= monthly:
            status = "ahead"
        elif slack > -0.5 * monthly:
            status = "on_track"
        else:
            status = "behind"
    st_en, st_fi = STATUS_TEXT[status]

    left = None
    if usual_leftover is not None:
        try:
            left = round(float(usual_leftover), 2)
        except (TypeError, ValueError):
            left = None
    fits = (monthly <= left) if (left is not None and remaining > 0) else None
    note, note_fi = _note(monthly, left) if remaining > 0 else ("", "")

    next_move = None
    if can_move is not None and remaining > 0:
        try:
            cap = max(0.0, float(can_move))
        except (TypeError, ValueError):
            cap = 0.0
        want = monthly
        if status == "behind":
            want = max(monthly, max(0.0, target - pace * months) - saved)
        amount = float(int(min(want, math.ceil(remaining), cap)))
        if amount >= MIN_MOVE:
            next_move = {"amount": amount, "ok": True,
                         "text": "You can move %s now." % eur(amount),
                         "text_fi": "Voit siirtää nyt %s." % eur_fi(amount)}
        else:
            next_move = {"amount": 0.0, "ok": False,
                         "text": "Nothing can be moved safely before payday.",
                         "text_fi": "Mitään ei voi siirtää turvallisesti ennen palkkapäivää."}

    return {"name": (str(name).strip()[:MAX_NAME] if name else ""), "target": round(target, 2),
            "saved": round(saved, 2), "monthly": monthly, "deadline": dl.isoformat() if dl else None,
            "months_left": months, "pct": int(min(100, round(100.0 * saved / target))),
            "status": status, "status_text": st_en, "status_text_fi": st_fi,
            "series": _series(t, saved, target, monthly, months) if remaining > 0 else
            [{"ym": _ym(t), "planned": round(target, 2), "actual": round(saved, 2)}],
            "next_move": next_move, "usual_leftover": left, "fits": fits, "note": note, "note_fi": note_fi}


# --------------------------------------------------------------------------- facts about the customer

def usual_leftover(conn, today):
    """(income - spending) in a usual month over the last 12 full months, or None. The same definition the
    coach's customer picture uses."""
    pm = _per_month(conn, today)
    if pm is None:
        return None
    return round(pm[0] - pm[1], 2)


def _per_month(conn, today):
    """(income, spending) in a usual month, or None when the history is too short."""
    try:
        from . import trends
        r = trends.money_story(conn, today, months=12)
    except Exception:
        return None
    if not isinstance(r, dict) or r.get("too_little_data") or not (r.get("window") or {}).get("months"):
        return None
    pm = r.get("per_month") or {}
    if pm.get("income") is None or pm.get("spent") is None:
        return None
    return float(pm["income"]), float(pm["spent"])


def small_monthly(left, ideas=()):
    """A small monthly amount this customer's month can carry: voice.small_step when it exists, else the same
    rule here (best specific idea rounded down to fives, else a fifth of the usual leftover; 10 to 200)."""
    try:
        from . import voice
        return float(voice.small_step(left, ideas)["monthly"])
    except Exception:
        pass
    best = 0.0
    for i in ideas or ():
        try:
            if not str(i.get("title") or "").lower().startswith("trim everyday"):
                best = max(best, float(i.get("saved_monthly") or 0))
        except (TypeError, ValueError, AttributeError):
            continue
    try:
        spare = float(left or 0)
    except (TypeError, ValueError):
        spare = 0.0
    m = min(best, 200.0) if best >= 10 else (min(spare * 0.2, 200.0) if spare >= 50 else 10.0)
    return float(max(10, int(m // 5) * 5))


# --------------------------------------------------------------------------- chart blocks (Contract B)

def _pt(label, label_fi, value, tone, mark=False):
    return {"ym": None, "label": label, "label_fi": label_fi, "value": round(float(value), 2), "value2": None,
            "tone": tone, "mark": mark}


def _chart(kind, series, target=None, now=None, legend=None):
    return {"kind": kind, "unit": "eur", "series": series, "legend": legend, "target": target, "now": now}


def safe_data(conn, today, monthly_saving_target=0, cache=None):
    from . import insights as ins
    s = cache if cache is not None else ins.safe_to_spend(conn, today, monthly_saving_target=monthly_saving_target)
    total = float(s.get("safe_total") or 0.0)
    per_day = float(s.get("per_day") or 0.0)
    bal, bills, buf = float(s.get("balance") or 0.0), float(s.get("bills_total") or 0.0), \
        float(s.get("unexpected_buffer") or 0.0)
    planned = float(s.get("planned_savings") or 0.0)
    chart = None
    if total > 0.5 and bal > 0:
        parts = []
        if bills > 0.005:
            parts.append(_pt("Bills until payday", "Laskut ennen palkkapäivää", bills, "muted"))
        if buf > 0.005:
            parts.append(_pt("Buffer for surprises", "Puskuri yllätyksiin", buf, "muted"))
        if planned > 0.005:
            parts.append(_pt("Planned savings", "Suunnitellut säästöt", planned, "muted"))
        parts.append(_pt("Safe to spend", "Käyttövara", total, "good", True))
        if len(parts) >= 2:
            chart = _chart("split", parts)
    if total > 0.5:
        cap = "%s is safe to spend until payday, about %s a day." % (eur(total), eur(per_day))
        cap_fi = "Palkkapäivään asti on käytettävissä %s, noin %s päivässä." % (
            eur_fi(total), eur_fi(per_day))
    else:
        cap = "Nothing extra is safe to spend until payday."
        cap_fi = "Palkkapäivään asti ei ole varaa ylimääräiseen."
    return {"safe_total": round(total, 2), "per_day": round(per_day, 2), "days_left": s.get("days_left"),
            "next_payday": s.get("next_payday"), "balance": round(bal, 2), "bills_total": round(bills, 2),
            "buffer": round(buf, 2), "chart": chart, "caption": cap, "caption_fi": cap_fi}


LABEL_FI = {"Groceries": "Ruokakauppa", "Restaurant": "Ravintolat", "Fast food": "Pikaruoka", "Taxi": "Taksit",
            "Fuel": "Polttoaine", "Housing": "Asuminen", "Night out": "Iltamenot", "Clothing": "Vaatteet",
            "Public transport": "Joukkoliikenne", "Pharmacy": "Apteekki", "Utilities": "Laskut",
            "Electronics": "Elektroniikka", "Bar": "Baarit", "Doctor": "Lääkäri"}


def valid_label(label):
    """True when `label` names a spending category the customer can track (never income)."""
    from . import classify, insights as ins
    if not isinstance(label, str) or not label.strip() or len(label) > 40:
        return False
    if label.strip().lower() in ("salary", "other income", "income"):
        return False
    kind, val = ins._resolve_target(label)
    if kind != "labels":
        return True
    known = {l.lower() for l in classify.ALL_LABELS}
    return all(str(v).lower() in known for v in val)


def category_data(conn, today, label, limit=None):
    from . import insights as ins
    t = _date(today)
    first = datetime.date(t.year, t.month, 1)
    months = []
    for i in range(5, -1, -1):          # five full months, then this month so far
        d = _add_months(first, -i) if i else first
        months.append((d, "this_month" if i == 0 else _ym(d)))
    pts = []
    for d, per in months:
        try:
            v = float(ins.spend(conn, today, period=per, label=label).get("total") or 0.0)
        except ValueError:
            v = 0.0
        pts.append((d, v))
    nm = ins.label_title(label)
    full = [v for _, v in pts[:-1]]
    usual = round(sum(full) / len(full), 2) if full else 0.0
    cur = pts[-1][1]
    lim = None if limit in (None, "") else round(float(limit), 2)
    label_fi = LABEL_FI.get(str(label).strip().title(), LABEL_FI.get(str(label).strip(), str(label).strip()))
    chart = None
    if any(v > 0 for v in full) and len(pts) >= 2:
        chart = _chart("bars", [{"ym": _ym(d), "label": None, "label_fi": None, "value": round(v, 2),
                                  "value2": None, "tone": "main" if i == len(pts) - 1 else "muted",
                                  "mark": i == len(pts) - 1} for i, (d, v) in enumerate(pts)],
                       target=lim if lim else usual)
    if lim:
        cap = "%s: %s so far this month, against your %s limit." % (str(label).strip().title(), eur(cur), eur(lim))
        cap_fi = "%s: %s tässä kuussa, rajasi on %s." % (label_fi, eur_fi(cur), eur_fi(lim))
    else:
        cap = "%s: %s so far this month, usually about %s." % (str(label).strip().title(), eur(cur), eur(usual))
        cap_fi = "%s: %s tässä kuussa, tavallisesti noin %s." % (label_fi, eur_fi(cur), eur_fi(usual))
    return {"label": str(label).strip(), "label_fi": label_fi, "month_total": round(cur, 2), "usual": usual,
            "limit": lim, "chart": chart, "caption": cap, "caption_fi": cap_fi}


def baskets_data(conn, today):
    from . import insights as ins
    ov = ins.overview(conn, today)
    b = ov.get("baskets") or {}
    income = float(ov.get("income") or 0.0)
    spent = float(ov.get("spent") or 0.0)
    saved = float(ov.get("saved") or 0.0)
    surplus = float(ov.get("surplus") or 0.0)
    reg, une, eve = (float(b.get(k) or 0.0) for k in ("regular", "unexpected", "everyday"))
    parts = []
    for lab, fi, v, tone in (("Regular bills and food", "Säännölliset", reg, "main"),
                             ("Unexpected", "Odottamattomat", une, "warn"),
                             ("Everyday", "Arki", eve, "main"),
                             ("Put aside", "Säästöön", saved, "good"),
                             ("Left over", "Jäi yli", max(0.0, surplus), "good")):
        if v > 0.005:
            parts.append(_pt(lab, fi, v, tone))
    chart = _chart("split", parts) if len(parts) >= 2 and spent > 0 else None
    if spent > 0:
        cap = "Last month you spent %s of your %s income." % (eur(spent), eur(income))
        cap_fi = "Viime kuussa kulutit %s tuloistasi %s." % (eur_fi(spent), eur_fi(income))
    else:
        cap, cap_fi = "No spending to show for last month yet.", "Viime kuulta ei ole vielä menoja näytettäväksi."
    return {"period": str(ov.get("month") or ""), "regular": round(reg, 2), "unexpected": round(une, 2),
            "everyday": round(eve, 2), "income": round(income, 2), "chart": chart, "caption": cap,
            "caption_fi": cap_fi}


# --------------------------------------------------------------------------- next steps

IDEA_FI = {
    "night_out": ("Trim nights out by a quarter", "Vähennä iltamenoja neljänneksellä", "nights out",
                  "iltamenoissa"),
    "Restaurant": ("Cook at home one meal in five", "Laita kotona yksi ateria viidestä", "eating out",
                   "ravintola- ja pikaruokamenoissa"),
    "everyday": ("Trim everyday spending by 5%", "Leikkaa arkimenoja viisi prosenttia", "everyday spending",
                 "arkimenoissa"),
    "surplus": ("Move your leftover on payday", "Siirrä yli jäävä raha säästöön palkkapäivänä",
                "my leftover", "yli jäävässä rahassa"),
}


def _idea_step(ideas):
    """The best specific saving idea as a step, or None."""
    usable = [i for i in ideas or () if float(i.get("saved_monthly") or 0) >= 10]
    specific = [i for i in usable if not str(i.get("title") or "").lower().startswith("trim everyday")]
    pool = specific or usable
    if not pool:
        return None
    best = max(pool, key=lambda i: float(i.get("saved_monthly") or 0))
    amt = float(int(float(best["saved_monthly"])))
    key = str(best.get("target") or "")
    en_t, fi_t, en_a, fi_a = IDEA_FI.get(key, (str(best["title"]), None, key or "this", None))
    if fi_t is None:   # a category idea made by app.insights: "Spend 15% less on <label>"
        fi_name = LABEL_FI.get(key) or key
        try:
            from . import charts as _charts       # the fuller table of Finnish category names
            fi_name = _charts.label_fi(key) or fi_name
        except Exception:
            pass
        fi_t = "Pienennä menoa: %s" % str(fi_name).lower()
        fi_a = ("menoluokassa " + str(fi_name).lower()) if key else "tässä"
        en_t = str(best["title"])
        en_a = str(best.get("target") or "this").lower()
    return {"id": "idea:%s" % (key or "any")[:40], "kind": "idea",
            "title": en_t, "title_fi": fi_t,
            "why": "About %s a month, from your own spending." % eur(amt),
            "why_fi": "Noin %s kuukaudessa, omista menoistasi." % eur_fi(amt),
            "figure": {"value": amt, "unit": "eur"},
            "action": {"type": "ask",
                       "message": "How could I save about %s a month on %s?" % (eur(amt), en_a),
                       "message_fi": "Miten voisin säästää noin %s kuukaudessa %s?" % (eur_fi(amt), fi_a),
                       "label": "Show me how", "label_fi": "Näytä miten"}}


def next_steps(lang, has_plan, plan_views, leftover_month, safe_total, ideas, balance, per_month,
               usual_left, small_monthly, goal_id, dismissed=()):
    """Up to three proposals, best first, each worked out by code. Inputs are plain numbers and lists, so this
    is a pure function:
      plan_views    [{"id", "name", "status", "next_move"}] for every plan the customer has
      leftover_month  last month's surplus (after spending and savings), or None
      safe_total    what is safe to move before payday (a move never goes above it), or None
      ideas         insights.save_more()["ideas"]
      balance, per_month=(income, spending) or None, usual_left, small_monthly (voice.small_step monthly)
      goal_id       id of the plan a loose leftover goes to ("goal" or a widget id), or None
    """
    steps = []
    room = max(0.0, float(safe_total or 0.0))
    spend = per_month[1] if per_month else None

    if not has_plan and spend and spend > 0:
        target = float(max(100, int(math.ceil(spend / 50.0)) * 50))
        monthly = float(min(small_monthly or 10, target))
        n = int(math.ceil(target / monthly))
        steps.append({
            "id": "start_plan", "kind": "start_plan",
            "title": "Start a safety buffer", "title_fi": "Aloita turvapuskuri",
            "why": "One month of spending, %s, set aside means a surprise bill stays small. At %s a month you "
                   "would have it in about %d months." % (eur(target), eur(monthly), n),
            "why_fi": "Yhden kuukauden menot, %s, sivuun: yllättävä lasku ei kaada kuukautta. "
                      "%s kuussa se on koossa noin %d kuukaudessa." % (eur_fi(target), eur_fi(monthly), n),
            "figure": {"value": target, "unit": "eur"},
            "action": {"type": "create_widget",
                       "widget": {"type": "plan", "params": {"name": "Puskuri" if lang == "fi" else "Buffer",
                                                              "target": target, "monthly": monthly}},
                       "label": "Start this plan", "label_fi": "Aloita tämä suunnitelma"}})

    moved_to = set()
    for pv in plan_views:
        nm = pv.get("next_move") or {}
        if pv.get("status") == "behind" and nm.get("ok") and room >= MIN_MOVE:
            amt = float(int(min(float(nm["amount"]), room)))
            if amt < MIN_MOVE:
                continue
            room -= amt
            moved_to.add(pv["id"])
            steps.append({
                "id": "move:%s" % pv["id"], "kind": "move",
                "title": "Catch up on %s" % pv["name"], "title_fi": "Kuro kiinni: %s" % pv["name"],
                "why": "You are a little behind. Moving %s now gets you back on schedule." % eur(amt),
                "why_fi": "Olet hieman jäljessä. Siirtämällä nyt %s pääset takaisin aikatauluun." % eur_fi(amt),
                "figure": {"value": amt, "unit": "eur"},
                "action": {"type": "move", "widget_id": pv["id"], "amount": amt,
                           "label": "Move %s" % eur(amt), "label_fi": "Siirrä %s" % eur_fi(amt)}})
            break

    if leftover_month is not None and leftover_month >= 20 and room >= 20 and goal_id not in moved_to:
        amt = float(int(round(min(leftover_month, room * 0.5 if room > 100 else room))))
        if amt >= 20:
            room -= amt
            steps.append({
                "id": "move:leftover", "kind": "move",
                "title": "Put last month's leftover to work", "title_fi": "Pane viime kuun jäämä töihin",
                "why": "You had %s left over last month. Moving %s now keeps it from being spent by accident." % (
                    eur(leftover_month), eur(amt)),
                "why_fi": "Viime kuussa jäi yli %s. Siirtämällä %s nyt se ei kulu vahingossa." % (
                    eur_fi(leftover_month), eur_fi(amt)),
                "figure": {"value": amt, "unit": "eur"},
                "action": {"type": "move", "widget_id": goal_id, "amount": amt,
                           "label": "Move %s to savings" % eur(amt), "label_fi": "Siirrä %s säästöön" % eur_fi(amt)}})

    if any(x["id"] == "move:leftover" for x in steps):   # the same advice, already a one-tap move above
        ideas = [i for i in ideas or () if i.get("target") != "surplus"]
    idea = _idea_step(ideas)
    if idea:
        steps.append(idea)

    if balance and spend and spend > 0 and balance > 3 * spend:
        months = int(balance // spend)
        idle = float(int((balance - 3 * spend) // 100 * 100))
        if idle >= 100:
            steps.append({
                "id": "idle_money", "kind": "idle_money",
                "title": "Your spare money could work harder", "title_fi": "Ylimääräiset rahasi voisivat tehdä enemmän",
                "why": "Your balance covers about %d months of spending. Three months is a good cushion; the rest "
                       "could earn more." % months,
                "why_fi": "Saldosi riittää noin %d kuukauden menoihin. Kolme kuukautta on hyvä turva; loput voisivat "
                          "tuottaa enemmän." % months,
                "figure": {"value": idle, "unit": "eur"},
                "action": {"type": "ask", "message": "Where should my spare money go?",
                           "message_fi": "Minne laittaisin ylimääräiset rahani?",
                           "label": "Ask Svinkki", "label_fi": "Kysy Svinkiltä"}})
    skip = set(dismissed or ())
    return [s for s in steps if s["id"] not in skip][:3]


# --------------------------------------------------------------------------- the coach tool

TOOLS = [
    {
        "name": "propose_plan",
        "description": "Put a ready savings plan in front of the customer: a name, a target amount, and either a "
                       "monthly amount or a date. Returns a plan_offer card with the month-by-month chart, the "
                       "date or monthly amount worked out by code, and whether the monthly amount fits a usual "
                       "month. It SAVES NOTHING: the customer taps 'Add this plan' to keep it on their home page. "
                       "Use it when they want to save for something, or when a small regular saving is the right "
                       "next step. Pass the figures they named; do not invent a target.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "What the plan is for, their own words (a trip, a buffer)."},
            "target": {"type": "number", "description": "The amount to reach, in euros."},
            "monthly": {"type": "number", "description": "Euros a month, if they named it."},
            "deadline": {"type": "string", "description": "YYYY-MM or YYYY-MM-DD, if they named a date."}},
            "required": ["name", "target"]},
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}


def _clean_name(v):
    s = " ".join("".join(ch if ch.isprintable() else " " for ch in str(v or "")).split())
    if not s:
        raise ValueError("name is required")
    return s[:MAX_NAME]


def offer(conn, today, name, target, monthly=None, deadline=None):
    """The plan_offer card data for a plan that is not stored yet."""
    name = _clean_name(name)
    left = usual_leftover(conn, today)
    p = preview(target, monthly=monthly, deadline=deadline, today=today, saved=0, usual_leftover=left, name=name)
    params = {"name": name, "target": p["target"], "monthly": p["monthly"], "deadline": p["deadline"]}
    return {"name": name, "target": p["target"], "monthly": p["monthly"], "deadline": p["deadline"],
            "months": p["months_left"], "series": p["series"], "fits": p["fits"], "note": p["note"],
            "note_fi": p["note_fi"], "usual_leftover": p["usual_leftover"],
            "widget": {"type": "plan", "params": params}}


def call(name, args, ctx):
    """Run one of the tools. Never raises; returns {"error": ...} on any problem."""
    args = args if isinstance(args, dict) else {}
    try:
        if name != "propose_plan":
            return {"error": "unknown tool", "card": "error"}
        res = offer(ctx.conn, ctx.today, args.get("name"), args.get("target"), args.get("monthly"),
                    args.get("deadline"))
    except (ValueError, TypeError, KeyError) as e:
        return {"error": "bad arguments: %s" % str(e)[:160], "card": "error"}
    except Exception:
        return {"error": "the tool failed", "card": "error"}
    res = dict(res)
    res["card"] = "plan_offer"
    return res
