"""Chart blocks and one-line captions for tool results (Contract B).

attach(card, res, args, ctx, ins) adds "chart", "caption" and "caption_fi" to a tool result. Every figure in a
chart or caption is read from the result itself (or from the same database the result came from), never from the
model. A builder that has too little data returns nothing; attach never raises.

chart = {"kind": bars|hbars|line|split|progress, "unit": eur|count|pct, "series": [...], "legend": {...}|None,
         "target": number|None, "now": number|None}
point = {"ym", "label", "label_fi", "value", "value2", "tone": main|muted|good|warn, "mark"}
"""
import calendar
import datetime as _dt
import math
import re

NB = " "
# The contract asks for cents on a single looked-up total ("€92.85"), but tests/test_result_text.py pins the
# house rule "whole euros from 20 up" for every string of a tool result. Set True to follow the contract.
EXACT_SPEND = True     # a looked-up spending total keeps its cents, like the answer and the card's key figure
_TONES = ("main", "muted", "good", "warn")

# ---------------------------------------------------------------- words
MONTHS_EN = ("", "January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December")
MONTHS_FI_IN = ("", "tammikuussa", "helmikuussa", "maaliskuussa", "huhtikuussa", "toukokuussa", "kesäkuussa",
                "heinäkuussa", "elokuussa", "syyskuussa", "lokakuussa", "marraskuussa", "joulukuussa")
MONTHS_FI_TO = ("", "tammikuuhun", "helmikuuhun", "maaliskuuhun", "huhtikuuhun", "toukokuuhun", "kesäkuuhun",
                "heinäkuuhun", "elokuuhun", "syyskuuhun", "lokakuuhun", "marraskuuhun", "joulukuuhun")
MONTHS_SHORT_EN = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Finnish labels for categories (shown as chart row names)
LABEL_FI = {
    "Taxi": "Taksit", "Groceries": "Ruokakauppa", "Restaurant": "Ravintolat", "Fast food": "Pikaruoka",
    "Fuel": "Polttoaine", "Housing": "Asuminen", "Utilities": "Laskut", "Bar": "Baarit",
    "Public transport": "Joukkoliikenne", "Parking": "Pysäköinti", "Pharmacy": "Apteekki", "Doctor": "Lääkäri",
    "Dentist": "Hammaslääkäri", "Other health": "Muu terveys", "Home improvement": "Kodin kunnostus",
    "Electronics": "Elektroniikka", "Furniture": "Huonekalut", "Clothing": "Vaatteet", "Hobbies": "Harrastukset",
    "Books": "Kirjat", "Shopping": "Ostokset", "Events": "Tapahtumat", "Cinema": "Elokuvat",
    "Gym & sports": "Kuntoilu", "Entertainment": "Viihde", "Flights": "Lennot", "Hotels": "Hotellit",
    "Travel agency": "Matkatoimisto", "Car rental": "Autonvuokraus", "Travel": "Matkailu",
    "Savings & investments": "Säästöt ja sijoitukset", "Salary": "Palkka", "Other income": "Muut tulot",
    "Transfer out": "Siirrot", "Other": "Muut", "Dining out": "Ulkona syöminen", "Night out": "Ilta ulkona",
    "regular": "Perusmenot", "unexpected": "Odottamattomat menot", "everyday": "Arkikulutus",
    "savings": "Säästöt", "income": "Tulot",
}
# "on <noun>" in English
_EN_ON = {"Taxi": "taxis", "Groceries": "groceries", "Restaurant": "restaurants", "Fast food": "fast food",
          "Bar": "bars", "Fuel": "fuel", "Public transport": "public transport", "Housing": "housing",
          "Dining out": "eating out", "Night out": "nights out", "Utilities": "bills", "Cinema": "cinema",
          "Clothing": "clothes", "Hobbies": "hobbies"}
# "where the money went" in Finnish, illative ("Takseihin meni ...")
_FI_ILL = {"Taxi": "Takseihin", "Groceries": "Ruokaostoksiin", "Restaurant": "Ravintoloihin",
           "Fast food": "Pikaruokaan", "Bar": "Baareihin", "Fuel": "Polttoaineeseen",
           "Public transport": "Joukkoliikenteeseen", "Housing": "Asumiseen", "Dining out": "Ulkona syömiseen",
           "Night out": "Iltoihin ulkona", "Utilities": "Laskuihin", "Cinema": "Elokuviin",
           "Clothing": "Vaatteisiin", "Hobbies": "Harrastuksiin", "Parking": "Pysäköintiin",
           "Pharmacy": "Apteekkiin", "Entertainment": "Viihteeseen", "Shopping": "Ostoksiin"}
_WEEKDAY = {"Mon": ("Mondays", "ma", "Maanantai"), "Tue": ("Tuesdays", "ti", "Tiistai"),
            "Wed": ("Wednesdays", "ke", "Keskiviikko"), "Thu": ("Thursdays", "to", "Torstai"),
            "Fri": ("Fridays", "pe", "Perjantai"), "Sat": ("Saturdays", "la", "Lauantai"),
            "Sun": ("Sundays", "su", "Sunnuntai")}
_GROUP_FI = {"meat_fish": "Liha ja kala", "pantry": "Kuivatuotteet", "fruit_veg": "Hedelmät ja vihannekset",
             "dairy": "Maito ja munat", "alcohol_mild": "Olut ja siideri", "household": "Kotitalous",
             "bread": "Leipä", "snacks_sweets": "Herkut", "hygiene": "Henkilökohtainen hoito",
             "soft_drinks": "Virvoitusjuomat", "ready_meals": "Valmisruoat", "frozen": "Pakasteet",
             "pet": "Lemmikit", "energy_drinks": "Energiajuomat", "alcohol_strong": "Vahvat alkoholijuomat",
             "other": "Muut", "baby": "Vauvatuotteet", "coffee_tea": "Kahvi ja tee", "tobacco": "Tupakka"}
_TRAIT_FI = {"Kept after spending": "Jäi käteen", "Social spending": "Seurustelu", "Housing": "Asuminen",
             "Groceries": "Ruokakauppa", "Travel": "Matkailu", "Going out": "Ulkona", "Kept": "Jäi käteen"}
_PERIOD_WORDS = {"today": ("today", "tänään"), "yesterday": ("yesterday", "eilen"),
                 "last_night": ("last night", "viime yönä"), "this_week": ("this week", "tällä viikolla"),
                 "last_week": ("last week", "viime viikolla")}
_METRIC_FI = {"income": "Kuukausitulot", "regular": "Perusmenot", "unexpected": "Odottamattomat menot",
              "everyday": "Arkikulutus", "savings": "Säästöt"}


def label_fi(label):
    s = str(label or "")
    return LABEL_FI.get(s) or LABEL_FI.get(s.capitalize()) or LABEL_FI.get(s.lower())


# ---------------------------------------------------------------- numbers
def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _r(x):
    return round(float(x), 2)


def _group3(n, sep):
    return "{:,}".format(int(n)).replace(",", sep)


def money_en(x, exact=False):
    """'€92.85', '€1,583' (whole euros from 20 up, cents below, always cents when exact)."""
    v = float(x)
    a = abs(v)
    if exact or a < 20:
        whole, cents = divmod(int(round(a * 100)), 100)
        s = "%s.%02d" % ("{:,}".format(whole), cents)
    else:
        s = "{:,}".format(int(a + 0.5))
    return ("-" if v < 0 and s.strip("0.,") else "") + "€" + s


def money_fi(x, exact=False):
    """'92,85 €', '1 583 €' (non-breaking spaces, comma for cents)."""
    v = float(x)
    a = abs(v)
    if exact or a < 20:
        whole, cents = divmod(int(round(a * 100)), 100)
        s = "%s,%02d" % (_group3(whole, NB), cents)
    else:
        s = _group3(int(a + 0.5), NB)
    return ("-" if v < 0 and s.strip("0, " + NB) else "") + s + NB + "€"


def pct_en(x):
    return "%d%%" % int(round(float(x)))


def pct_fi(x):
    return "%d%s%%" % (int(round(float(x))), NB)


def _plural(n, one, many):
    return one if n == 1 else many


# ---------------------------------------------------------------- dates
def _ym_parts(ym):
    return int(ym[:4]), int(ym[5:7])


def add_months(ym, n):
    y, m = _ym_parts(ym)
    k = y * 12 + (m - 1) + n
    return "%04d-%02d" % (k // 12, k % 12 + 1)


def month_bounds(ym):
    y, m = _ym_parts(ym)
    return "%s-01" % ym, "%s-%02d" % (ym, calendar.monthrange(y, m)[1])


def month_en(ym, year=False):
    y, m = _ym_parts(ym)
    return MONTHS_EN[m] + (" %d" % y if year else "")


def month_fi_in(ym, year=False):
    y, m = _ym_parts(ym)
    return MONTHS_FI_IN[m] + (" %d" % y if year else "")


def day_en(d):
    d = str(d)[:10]
    return "%d %s" % (int(d[8:10]), MONTHS_SHORT_EN[int(d[5:7])])


def day_fi(d):
    d = str(d)[:10]
    return "%d.%d." % (int(d[8:10]), int(d[5:7]))


def when_phrase(frm, to, name=None, today=None):
    """(english, finnish) lower-case phrase for a period: 'in August' / 'elokuussa'."""
    frm, to = str(frm)[:10], str(to)[:10]
    if name in _PERIOD_WORDS:
        return _PERIOD_WORDS[name]
    if frm[:7] == to[:7] and frm[8:10] == "01":
        if to == month_bounds(to[:7])[1]:
            return "in " + month_en(to[:7]), month_fi_in(to[:7])
        if today and str(today)[:10] == to:
            return "so far in " + month_en(to[:7]), "tähän mennessä " + month_fi_in(to[:7])
    return "from %s to %s" % (day_en(frm), day_en(to)), "ajalla %s–%s" % (day_fi(frm), day_fi(to))


def _cap(s):
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------- chart blocks
def pt(label=None, value=0.0, ym=None, label_fi_=None, value2=None, tone="main", mark=False):
    v = _num(value)
    if v is None:
        raise ValueError("value")
    v2 = None if value2 is None else _num(value2)
    if label_fi_ is None and label is not None:
        label_fi_ = label_fi(label)
    return {"ym": ym, "label": label, "label_fi": label_fi_, "value": _r(v),
            "value2": None if v2 is None else _r(v2), "tone": tone if tone in _TONES else "main",
            "mark": bool(mark)}


def _legend(v=None, vfi=None, v2=None, v2fi=None):
    if not (v or v2):
        return None
    return {"value": v, "value_fi": vfi, "value2": v2, "value2_fi": v2fi}


def _chart(kind, unit, series, legend=None, target=None, now=None):
    """Assemble and check a block; None when the data is too thin to draw."""
    series = [p for p in (series or []) if p]
    if kind in ("bars", "line"):
        series = series[-12:]
        need = 2
    elif kind == "hbars":
        series = series[:6]
        need = 2
    elif kind == "split":
        series = [p for p in series if p["value"] > 0][:5]
        need = 2
    else:
        need = 0
    if len(series) < need:
        return None
    if kind != "progress" and not any(p["value"] or (p["value2"] or 0) for p in series):
        return None
    if kind in ("hbars", "split"):
        for p in series:
            p["label_fi"] = p["label_fi"] or p["label"]
    t = _num(target)
    n = _num(now)
    return {"kind": kind, "unit": unit, "series": series, "legend": legend,
            "target": None if t is None else _r(t), "now": None if n is None else _r(n)}


def bars(series, unit="eur", legend=None, target=None):
    return _chart("bars", unit, series, legend, target)


def hbars(series, unit="eur", legend=None):
    return _chart("hbars", unit, series, legend)


def line(series, unit="eur", legend=None, target=None):
    return _chart("line", unit, series, legend, target)


def split(series, unit="eur"):
    return _chart("split", unit, series)


def progress(now, target, unit="eur"):
    if _num(now) is None or not _num(target) or float(target) <= 0:
        return None
    return _chart("progress", unit, [], None, target, now)


# ---------------------------------------------------------------- helpers over a result
def _g(d, *path):
    for k in path:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return None
    return d


def _today(ctx):
    return str(getattr(ctx, "today", None) or "")[:10]


def _months_back(end_ym, n):
    return [add_months(end_ym, -i) for i in range(n - 1, -1, -1)]


# ---------------------------------------------------------------- 1. spend
def _spend_total(ins, ctx, frm, to, lab, basket):
    from app import tools as T
    period = (frm, to)
    if lab == "Dining out":
        parts = [ins.spend(ctx.conn, ctx.today, period=period, label=l, basket=basket) for l in T.DINING]
        return sum(p.get("total", 0) or 0 for p in parts)
    if lab == "Night out":
        return ins.spend(ctx.conn, ctx.today, period=period, context="night_out", basket=basket)["total"]
    return ins.spend(ctx.conn, ctx.today, period=period, label=lab, basket=basket)["total"]


def b_spend(res, args, ctx, ins):
    from app import tools as T
    total, count = _num(res.get("total")), int(res.get("count") or 0)
    per = res.get("period") or {}
    if total is None or not count or not per.get("from"):
        return None, None, None
    lab = T._label(args.get("label"))
    basket = T._basket(args.get("basket"), ("regular", "unexpected", "everyday"))
    frm, to = str(per["from"])[:10], str(per["to"])[:10]
    en_w, fi_w = when_phrase(frm, to, per.get("name") if isinstance(per.get("name"), str) else None, _today(ctx))
    n = count
    pays_en = "%d %s" % (n, _plural(n, "payment", "payments"))
    pays_fi = "%d %s" % (n, _plural(n, "maksu", "maksua"))
    if lab:
        noun = _EN_ON.get(lab, lab.lower())
        en = "%s on %s %s, %s." % (money_en(total, EXACT_SPEND), noun, en_w, pays_en)
        if lab in _FI_ILL:
            fi = "%s meni %s %s, %s." % (_FI_ILL[lab], fi_w, money_fi(total, EXACT_SPEND), pays_fi)
        else:
            fi = "%s %s: %s, %s." % (label_fi(lab) or lab, fi_w, money_fi(total, EXACT_SPEND), pays_fi)
    else:
        en = "%s spent %s, %s." % (money_en(total, EXACT_SPEND), en_w, pays_en)
        fi = "Menoja %s %s, %s." % (fi_w, money_fi(total, EXACT_SPEND), pays_fi)
    chart = None
    days = (_dt.date.fromisoformat(to) - _dt.date.fromisoformat(frm)).days + 1
    if days >= 25:
        end = min(to[:7], _today(ctx)[:7])
        single = en_w.startswith(("in ", "so far in ")) and frm[:7] == to[:7]
        series = []
        for ym in _months_back(end, 6):
            a, b = month_bounds(ym)
            b = min(b, _today(ctx) or b)
            v = _spend_total(ins, ctx, a, b, lab, basket)
            series.append(pt(None, v, ym=ym, mark=(single and ym == to[:7])))
        chart = bars(series)
    return chart, en, fi


# ---------------------------------------------------------------- 2. safe to spend and affordability
def b_safe(res, args, ctx, ins):
    safe = _num(res.get("safe_total"))
    if safe is None:
        return None, None, None
    parts = [("Bills before payday", "Laskut ennen palkkapäivää", res.get("bills_total"), "muted"),
             ("Buffer for surprises", "Puskuri yllätyksiin", res.get("unexpected_buffer"), "muted"),
             ("Planned savings", "Suunnitellut säästöt", res.get("planned_savings"), "main"),
             ("Safe to spend", "Turvallisesti käytettävissä", safe, "good")]
    series = [pt(a, v, label_fi_=b, tone=t) for a, b, v, t in parts if (_num(v) or 0) > 0]
    pay = res.get("next_payday")
    if safe <= 0:
        return split(series), "Nothing is safe to spend until payday%s." % (
            " on " + day_en(pay) if pay else ""), "Turvallista käyttövaraa ei ole palkkapäivään%s." % (
            " (" + day_fi(pay) + ")" if pay else "")
    en = "%s is safe to spend%s." % (money_en(safe), " until payday on " + day_en(pay) if pay else "")
    fi = "%s on turvallisesti käytettävissä%s." % (money_fi(safe), " palkkapäivään " + day_fi(pay) + " asti" if pay else "")
    return split(series), en, fi


def b_afford(res, args, ctx, ins):
    price, safe, after = _num(res.get("price")), _num(res.get("safe_total")), _num(res.get("after"))
    if price is None or safe is None or after is None or safe <= 0 or price <= 0:
        return None, None, None
    if after >= 0:
        series = [pt("Price", price, label_fi_="Hinta", tone="warn" if res.get("verdict") not in ("yes",) else "main"),
                  pt("Left after", after, label_fi_="Jää jäljelle", tone="good")]
        en = "A %s purchase leaves %s of your %s safe to spend." % (money_en(price), money_en(after), money_en(safe))
        fi = "Hinta %s, jäljelle jää %s turvallisesta %s käyttövarasta." % (money_fi(price), money_fi(after), money_fi(safe))
    else:
        series = [pt("Safe to spend", safe, label_fi_="Turvallisesti käytettävissä", tone="good"),
                  pt("Over by", -after, label_fi_="Yli", tone="warn")]
        en = "A %s purchase is %s more than your %s safe to spend." % (money_en(price), money_en(-after), money_en(safe))
        fi = "Hinta %s ylittää turvallisen käyttövaran %s verran (%s)." % (money_fi(price), money_fi(-after), money_fi(safe))
    return split(series), en, fi


# ---------------------------------------------------------------- 3. overview and baskets
def _flow_split(f, when_en, when_fi):
    inc = _num(f.get("income")) or 0.0
    reg, une, eve = (_num(f["baskets"].get(k)) or 0.0 for k in ("regular", "unexpected", "everyday"))
    saved = max(_num(f.get("saved")) or 0.0, 0.0)
    surplus = _num(f.get("surplus"))
    if surplus is None:
        return None, None, None
    series = [pt("Regular essentials", reg, label_fi_="Perusmenot", tone="muted"),
              pt("Unexpected", une, label_fi_="Odottamattomat", tone="warn"),
              pt("Everyday", eve, label_fi_="Arkikulutus", tone="main"),
              pt("Saved", saved, label_fi_="Säästetty", tone="good")]
    if surplus > 0:
        series.append(pt("Left over", surplus, label_fi_="Jäi yli", tone="good"))
        en = "%s, %s was left over after spending and saving." % (_cap(when_en), money_en(surplus))
        fi = "%s jäi yli %s menojen ja säästöjen jälkeen." % (_cap(when_fi), money_fi(surplus))
    elif surplus < -0.005:
        en = "%s you spent %s more than came in." % (_cap(when_en), money_en(-surplus))
        fi = "%s menoja oli %s enemmän kuin tuloja." % (_cap(when_fi), money_fi(-surplus))
    else:
        en = "%s nothing was left over." % _cap(when_en)
        fi = "%s mitään ei jäänyt yli." % _cap(when_fi)
    if not inc and not any(p["value"] for p in series):
        return None, None, None
    return split(series), en, fi


def b_overview(res, args, ctx, ins):
    per = res.get("period") or {}
    en_w, fi_w = when_phrase(per.get("from", res.get("month", "") + "-01"), per.get("to", ""), None, _today(ctx))
    f = {"income": res.get("income"), "baskets": res.get("baskets") or {}, "saved": res.get("saved"),
         "surplus": res.get("surplus")}
    return _flow_split(f, en_w, fi_w)


def b_baskets(res, args, ctx, ins):
    per = res.get("period") or {}
    if not per.get("from"):
        return None, None, None
    f = ins._flows(ctx.conn, per["from"], per["to"])
    en_w, fi_w = when_phrase(per["from"], per["to"], None, _today(ctx))
    return _flow_split(f, en_w, fi_w)


# ---------------------------------------------------------------- 4. the long view
def b_explain_month(res, args, ctx, ins):
    spent, usual, diff, ym = _num(res.get("spent")), _num(res.get("usual")), _num(res.get("difference")), res.get("month")
    if None in (spent, usual, diff) or not ym:
        return None, None, None
    above = diff >= 0
    key = "above_usual" if above else "below_usual"
    series = [pt(d.get("label"), d.get(key), tone="warn" if above else "good")
              for d in (res.get("drivers") or []) if _num(d.get(key)) is not None]
    en = "In %s you spent %s, about %s %s your usual %s." % (
        month_en(ym), money_en(spent), money_en(abs(diff)), "above" if above else "below", money_en(usual))
    fi = "%s kulutit %s, noin %s %s tavallisesta %s." % (
        _cap(month_fi_in(ym)), money_fi(spent), money_fi(abs(diff)), "yli" if above else "alle", money_fi(usual))
    fi = fi.replace(" yli tavallisesta", " enemmän kuin tavallisesti").replace(" alle tavallisesta", " vähemmän kuin tavallisesti")
    leg = _legend("above usual" if above else "below usual", "yli tavallisen" if above else "alle tavallisen")
    return hbars(series, legend=leg), en, fi


def b_season(res, args, ctx, ins):
    ly = res.get("last_year")
    if not isinstance(ly, dict) or not ly.get("from") or _num(ly.get("spent")) is None or _num(ly.get("income")) is None:
        return None, None, None
    from app import trends
    mo = trends._monthly(ctx.conn, ctx.today)
    series, ym = [], str(ly["from"])[:7]
    while ym <= str(ly["to"])[:7] and len(series) < 12:
        m = mo.get(ym, {})
        series.append(pt(None, m.get("spent", 0.0), ym=ym, value2=m.get("income", 0.0)))
        ym = add_months(ym, 1)
    en = "Over the same months last year you spent %s and earned %s." % (money_en(ly["spent"]), money_en(ly["income"]))
    fi = "Samoina kuukausina viime vuonna kulutit %s ja ansaitsit %s." % (money_fi(ly["spent"]), money_fi(ly["income"]))
    return bars(series, legend=_legend("Spent", "Menot", "Income", "Tulot")), en, fi


def b_money_story(res, args, ctx, ins):
    from app import trends
    bal, win = res.get("balance"), res.get("window")
    if not isinstance(bal, dict) or not isinstance(win, dict) or _num(bal.get("now")) is None:
        return None, None, None
    balances = trends._balances(ctx.conn, ctx.today)
    end = str(win["to"])[:7]
    series = []
    for ym in _months_back(end, min(int(win.get("months") or 12), 12)):
        v = trends._balance_on(balances, month_bounds(ym)[1])
        if v is not None:
            series.append(pt(None, v, ym=ym, mark=(ym == end)))
    now, ago = bal["now"], _num(bal.get("year_ago"))
    months = int(win.get("months") or 12)
    if ago is not None and months == 12:
        en = "Your balance was %s a year ago and is %s now." % (money_en(ago), money_en(now))
        fi = "Saldosi oli vuosi sitten %s ja on nyt %s." % (money_fi(ago), money_fi(now))
    else:
        en = "Your balance is %s now." % money_en(now)
        fi = "Saldosi on nyt %s." % money_fi(now)
    return line(series), en, fi


def b_category_story(res, args, ctx, ins):
    rows = [r for r in (res.get("monthly") or []) if isinstance(r, dict) and _num(r.get("total")) is not None]
    series = [pt(None, r["total"], ym=r["m"]) for r in rows[-12:]]
    now, before = _g(res, "now", "per_month"), _g(res, "before", "per_month")
    lab = str(res.get("label") or "")
    if _num(now) is None:
        return bars(series), None, None
    noun = _EN_ON.get(lab, lab.lower())
    if _num(before) is not None:
        word = "up from" if now >= before else "down from"
        en = "You spend about %s a month on %s now, %s %s." % (money_en(now), noun, word, money_en(before))
        fi = "%s kuluu nyt noin %s kuukaudessa, aiemmin %s." % (label_fi(lab) or lab, money_fi(now), money_fi(before))
    else:
        en = "You spend about %s a month on %s now." % (money_en(now), noun)
        fi = "%s kuluu nyt noin %s kuukaudessa." % (label_fi(lab) or lab, money_fi(now))
    return bars(series), en, fi


def _lowest_by_month(res, ctx):
    from app import trends
    win = res.get("window") or {}
    if not win.get("from"):
        return []
    frm = str(win["from"])[:10]
    low = {}
    for d, b in trends._balances(ctx.conn, ctx.today):
        if d >= frm:
            low[d[:7]] = min(b, low.get(d[:7], b))
    return sorted(low.items())


def b_low_points(res, args, ctx, ins):
    if res.get("too_little_data"):
        return None, None, None
    lo = _g(res, "lowest", "amount")
    series = [pt(None, v, ym=ym, tone="warn" if v < 0 else "main") for ym, v in _lowest_by_month(res, ctx)]
    ch = bars(series)       # a month below zero carries a negative value (tone warn)
    if _num(lo) is None:
        return ch, None, None
    if lo < 0:
        en = "The lowest your balance got was %s below zero." % money_en(-lo)
        fi = "Saldosi alin kohta oli %s nollan alapuolella." % money_fi(-lo)
    else:
        en = "Your balance stayed above zero; the lowest was %s." % money_en(lo)
        fi = "Saldosi pysyi nollan yläpuolella; alin kohta oli %s." % money_fi(lo)
    return ch, en, fi


def b_income_profile(res, args, ctx, ins):
    from app import trends
    if res.get("too_little_data"):
        return None, None, None
    mo = trends._monthly(ctx.conn, ctx.today)
    full = trends._full_months(ctx.conn, ctx.today)[-12:]
    series = [pt(None, mo.get(m, {}).get("income", 0.0), ym=m) for m in full]
    avg, day = _num(res.get("average_now")), res.get("usual_day")
    if avg is None:
        return bars(series), None, None
    en = "Your pay is about %s a month%s." % (money_en(avg), ", usually on the %s" % _ordinal(day) if day else "")
    fi = "Palkkasi on noin %s kuukaudessa%s." % (money_fi(avg), ", yleensä %d. päivä" % int(day) if day else "")
    return bars(series), en, fi


def _ordinal(n):
    n = int(n)
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


# ---------------------------------------------------------------- 5. what-if, ideas, comparisons
def b_what_if(res, args, ctx, ins):
    base, new, sm, st = (_num(res.get(k)) for k in ("baseline_monthly", "new_monthly", "saved_monthly", "saved_total"))
    months = int(res.get("months") or 12)
    if None in (base, new, sm):
        return None, None, None
    series = [pt("Now", base, label_fi_="Nyt", tone="main"), pt("After", new, label_fi_="Muutoksen jälkeen", tone="good" if sm >= 0 else "warn")]
    if sm >= 0:
        en = "You would save %s a month%s." % (money_en(sm), ", %s over %d months" % (money_en(st), months) if st is not None else "")
        fi = "Säästäisit %s kuukaudessa%s." % (money_fi(sm), ", yhteensä %s %d kuukaudessa" % (money_fi(st), months) if st is not None else "")
    else:
        en = "This would cost you %s more a month." % money_en(-sm)
        fi = "Tämä maksaisi %s enemmän kuukaudessa." % money_fi(-sm)
    return bars(series), en, fi


def _idea_fi(title):
    t = str(title)
    m = re.match(r"^Trim (\w+) spending by (\d+)%$", t)
    if m:
        return "Karsi %s-kulutusta %s %%" % ({"everyday": "arki"}.get(m.group(1), m.group(1)), m.group(2))
    m = re.match(r"^Spend (\d+)% less on (.+)$", t)
    if m:
        lab = m.group(2)
        fi = label_fi(lab.capitalize()) or next((v for k, v in LABEL_FI.items() if k.lower() == lab.lower()), None)
        return "Käytä %s %% vähemmän: %s" % (m.group(1), fi.lower()) if fi else None
    return {"Trim nights out by a quarter": "Karsi iltoja ulkona neljänneksellä",
            "Move your leftover on payday": "Siirrä ylijäämä säästöön palkkapäivänä",
            "Cook at home one meal in five": "Laita kotona joka viides ateria"}.get(t)


def b_save_more(res, args, ctx, ins):
    ideas = [i for i in (res.get("ideas") or []) if isinstance(i, dict) and (_num(i.get("saved_monthly")) or 0) > 0]
    ideas.sort(key=lambda i: -i["saved_monthly"])
    series = [pt(i.get("title"), i["saved_monthly"], label_fi_=_idea_fi(i.get("title")),
                 tone="good") for i in ideas[:6]]
    if not ideas:
        return None, None, None
    top = ideas[0]["saved_monthly"]
    en = "The biggest idea frees about %s a month." % money_en(top)
    fi = "Suurin keino vapauttaa noin %s kuukaudessa." % money_fi(top)
    return hbars(series, legend=_legend("a month", "kuukaudessa")), en, fi


def b_leaks(res, args, ctx, ins):
    rows = [r for r in (res.get("by_weekday") or []) if isinstance(r, dict) and _num(r.get("total")) is not None]
    if not rows:
        return None, None, None
    top = max(rows, key=lambda r: r["total"])
    series = [pt(r["day"], r["total"], label_fi_=_WEEKDAY.get(r["day"], (0, r["day"]))[1],
                 mark=(r is top)) for r in rows]
    names = _WEEKDAY.get(top["day"])
    if not names:
        return bars(series), None, None
    en = "%s are your biggest spending day: %s." % (names[0], money_en(top["total"]))
    fi = "%s on suurin kulutuspäiväsi: %s." % (names[2], money_fi(top["total"]))
    return bars(series), en, fi


def b_spender(res, args, ctx, ins):
    traits = [t for t in (res.get("traits") or []) if isinstance(t, dict) and _num(t.get("value")) is not None]
    series = [pt(t.get("name"), t["value"], label_fi_=_TRAIT_FI.get(t.get("name")), tone="good" if t.get("note") == "Kept" or t.get("name") == "Kept after spending" else "main")
              for t in traits[:6]]
    kept = _g(res, "shares", "kept")
    months = int(res.get("months") or 6)
    if _num(kept) is None:
        return hbars(series, "pct"), None, None
    p = float(kept) * 100
    if p >= 0:
        en = "You kept about %s of your income over the last %d months." % (pct_en(p), months)
        fi = "Käteen jäi noin %s tuloistasi viimeisten %d kuukauden aikana." % (pct_fi(p), months)
    else:
        en = "You spent about %s more than you earned over the last %d months." % (pct_en(-p), months)
        fi = "Kulutit noin %s enemmän kuin ansaitsit viimeisten %d kuukauden aikana." % (pct_fi(-p), months)
    return hbars(series, "pct", legend=_legend("share of income", "osuus tuloista")), en, fi


def _you_typical(rows, key_typ):
    out = []
    for r in rows:
        if not isinstance(r, dict) or str(r.get("unit")) not in ("eur", "eur_per_month"):
            continue
        you, typ = _num(r.get("you")), _num(r.get(key_typ))
        if you is None or typ is None:
            continue
        met = str(r.get("metric") or "")
        fi = _METRIC_FI.get(met) or (label_fi(met[6:]) if met.startswith("label:") else None)
        out.append((r, you, typ, fi))
    return out


def _compare(res, key_typ):
    items = _you_typical(res.get("rows") or [], key_typ)[:6]
    if not items:
        return None, None, None
    series = [pt(r.get("name"), you, label_fi_=fi, value2=typ, tone="main") for r, you, typ, fi in items]
    r0, you, typ, fi0 = items[0]
    en = "%s: you %s, people like you %s." % (r0.get("name"), money_en(you), money_en(typ))
    fi = "%s: sinä %s, vastaavat %s." % (fi0, money_fi(you), money_fi(typ)) if fi0 else \
        "Sinä %s, vastaavat %s." % (money_fi(you), money_fi(typ))
    return hbars(series, legend=_legend("You", "Sinä", "Typical", "Tyypillinen")), en, fi


def b_averages(res, args, ctx, ins):
    return _compare(res, "typical")


def b_benchmarks(res, args, ctx, ins):
    return _compare(res, "median")


def b_receipt_insights(res, args, ctx, ins):
    groups = [g for g in (res.get("by_group") or []) if isinstance(g, dict) and _num(g.get("total")) is not None]
    if not groups:
        return None, None, None
    series = [pt(g.get("name"), g["total"], label_fi_=_GROUP_FI.get(g.get("group")), tone="main") for g in groups[:6]]
    top, total = groups[0], _num(res.get("total"))
    per = _g(res, "period", "label") or "over the last 3 months"
    if total:
        en = "%s was the biggest part: %s of %s %s." % (top.get("name"), money_en(top["total"]), money_en(total), per)
        fi = "Suurin ryhmä oli %s: %s kaikista %s ostoksista." % (_GROUP_FI.get(top.get("group"), top.get("name")),
                                                                  money_fi(top["total"]), money_fi(total))
    else:
        en = "%s was the biggest part: %s." % (top.get("name"), money_en(top["total"]))
        fi = "Suurin ryhmä oli %s: %s." % (_GROUP_FI.get(top.get("group"), top.get("name")), money_fi(top["total"]))
    return hbars(series), en, fi


def b_goal_plan(res, args, ctx, ins):
    if res.get("needs"):
        return None, None, None
    target, monthly, n = _num(res.get("target")), _num(res.get("monthly_needed")), res.get("months_left")
    saved = _num(res.get("saved")) or 0.0
    if not target or not monthly or not n or int(n) < 2 or not res.get("deadline"):
        return None, None, None
    n = int(n)
    start = _today(ctx)[:7]
    idx = list(range(1, n + 1))
    if n > 12:
        idx = sorted({max(1, round(n * k / 12)) for k in range(1, 13)})
    series = [pt(None, min(saved + monthly * i, target), ym=add_months(start, i), mark=(i == n)) for i in idx]
    dl = str(res["deadline"])
    dy, dm = int(dl[:4]), int(dl[5:7]) if len(dl) >= 7 else 12
    en = "Put aside %s a month and you reach %s by %s %d." % (money_en(monthly), money_en(target), MONTHS_EN[dm], dy)
    fi = "Laita sivuun %s kuukaudessa, niin saat %s kasaan %s %d mennessä." % (
        money_fi(monthly), money_fi(target), MONTHS_FI_TO[dm], dy)
    return line(series, target=target), en, fi


_BUILDERS = {
    "spend": b_spend, "safe_to_spend": b_safe, "afford": b_afford, "overview": b_overview, "baskets": b_baskets,
    "explain_month": b_explain_month, "season_outlook": b_season, "money_story": b_money_story,
    "category_story": b_category_story, "low_points": b_low_points, "income_profile": b_income_profile,
    "what_if": b_what_if, "save_more": b_save_more, "leaks": b_leaks, "spender_type": b_spender,
    "averages": b_averages, "benchmarks": b_benchmarks, "receipt_insights": b_receipt_insights,
    "goal_plan": b_goal_plan,
}


def attach(card, res, args, ctx, ins):
    """Add chart, caption and caption_fi to a tool result. Never raises; an unknown card or thin data adds nothing."""
    fn = _BUILDERS.get(card)
    if fn is None or not isinstance(res, dict) or "error" in res or "chart" in res:
        return res
    try:
        chart, en, fi = fn(res, args or {}, ctx, ins)
    except Exception:
        return res
    out = dict(res)
    if chart:
        out["chart"] = chart
    if en and fi:
        out["caption"], out["caption_fi"] = en, fi
    return out
