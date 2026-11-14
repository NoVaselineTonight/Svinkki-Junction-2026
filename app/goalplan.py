"""A personal savings plan for a goal (a car, a trip, a home deposit), decided by code from the customer's own data.

One call does what used to take the model three (general_estimate, plan_goal_by_date, propose_plan) and gives a
concrete answer instead of a generic one:

- the price: the customer's figure, or a rough Finnish estimate for common goals (said to be an estimate);
- where the money comes from: their usual monthly leftover (last 6 full months) plus named cuts in their own
  biggest flexible categories, each "from X to Y a month";
- the decision: one monthly amount to put aside on payday and the month the goal is reached, or, with a date,
  what that date needs and whether their money can carry it (and the realistic date if not);
- a cheaper option when the plan is long.

The result is a plan_offer card (app/plans.py shape), so the customer can keep it with one tap. Nothing is saved.
"""
import datetime
import math
import re

from . import plans

LOOKBACK_MONTHS = 6
LEFTOVER_SHARE = 0.8          # keep a fifth of the usual leftover as a margin for the unexpected
MIN_CUT = 8.0                 # a cut worth naming frees at least this much a month
MAX_CUTS = 4
LONG_PLAN_MONTHS = 36

# How much of a category can realistically go, and what to do. Essentials (housing, bills, health, public
# transport) are never cut. Groceries only gently, and only when the flexible areas are not enough.
CUTS = {
    "Taxi": (0.5, "take the bus or walk for every other taxi trip", "kulje joka toinen taksimatka bussilla tai kävellen"),
    "Night out": (0.35, "one night out less a month", "yksi ilta ulkona vähemmän kuussa"),
    "Bar": (0.35, "one bar evening less a month", "yksi baari-ilta vähemmän kuussa"),
    "Restaurant": (0.3, "cook at home instead of every third restaurant meal", "kokkaa kotona joka kolmannen ravintola-aterian sijaan"),
    "Fast food": (0.4, "skip two fast-food meals in five", "jätä kaksi pikaruoka-ateriaa viidestä väliin"),
    "Clothing": (0.4, "buy clothes only when something wears out", "osta vaatteita vain kun vanha kuluu loppuun"),
    "Electronics": (0.5, "pause gadget purchases while you save", "pidä tauko elektroniikkaostoista säästön ajan"),
    "Entertainment": (0.3, "drop one paid entertainment habit", "luovu yhdestä maksullisesta viihteestä"),
    "Hobbies": (0.2, "trim hobby spending a little", "karsi harrastusmenoja vähän"),
    "Events": (0.4, "pick fewer paid events", "valitse vähemmän maksullisia tapahtumia"),
    "Cinema": (0.3, "go to the cinema a little less", "käy elokuvissa hieman harvemmin"),
    "Travel agency": (0.5, "postpone the next package trip", "siirrä seuraavaa valmismatkaa"),
    "Books": (0.4, "use the library for some books", "lainaa osa kirjoista kirjastosta"),
    "Furniture": (0.6, "pause furniture purchases", "pidä tauko huonekaluostoista"),
    "Home improvement": (0.4, "postpone non-urgent home projects", "siirrä kiireettömiä kotiprojekteja"),
    "Parking": (0.3, "park less in paid spots", "pysäköi harvemmin maksullisille paikoille"),
    "Fuel": (0.15, "combine car trips", "yhdistä automatkoja"),
    "Gaming": (0.4, "pause game purchases", "pidä tauko pelien ostamisesta"),
    "Streaming": (0.3, "keep one streaming service, not several", "pidä yksi suoratoistopalvelu, ei useampaa"),
    "Alcohol": (0.3, "buy a third less alcohol", "osta kolmannes vähemmän alkoholia"),
    "Tobacco": (0.3, "cut down on tobacco", "vähennä tupakkaa"),
    "Gifts": (0.3, "set a budget for gifts", "aseta lahjoille budjetti"),
    "Beauty": (0.3, "space out beauty treatments", "harvenna kauneushoitoja"),
    "Online shopping": (0.4, "wait a week before online orders", "odota viikko ennen verkko-ostoksia"),
}
GROCERY_CUT = (0.1, "plan the week's meals before shopping", "suunnittele viikon ateriat ennen kauppaan menoa")

# Rough prices in Finland today: (keywords, en name, fi name, low, mid, high, what it assumes en, fi).
ESTIMATES = [
    (r"\bnew car\b|\buusi auto\b|\buuteen autoon\b", "a new car", "uusi auto", 22000, 30000, 40000,
     "a new mid-size car", "uusi keskikokoinen auto"),
    (r"\belectric car\b|\bev\b|\bsähköauto", "an electric car", "sähköauto", 15000, 25000, 40000,
     "a used or basic new electric car", "käytetty tai perusmallin uusi sähköauto"),
    (r"motorcycle|motorbike|moottoripyör", "a motorcycle", "moottoripyörä", 3000, 6000, 10000,
     "a used mid-size motorcycle", "käytetty keskikokoinen moottoripyörä"),
    (r"\bcar\b|\bauto\w*", "a car", "auto", 5000, 8000, 12000,
     "a reliable used car, a few years old", "luotettava, muutaman vuoden vanha käytetty auto"),
    (r"e-?bike|electric bike|sähköpyör", "an e-bike", "sähköpyörä", 1500, 2500, 4000,
     "a good commuter e-bike", "hyvä työmatkasähköpyörä"),
    (r"\bbike\b|bicycle|polkupyör|\bpyör", "a bike", "polkupyörä", 400, 800, 1500,
     "a decent new bike", "kunnon uusi polkupyörä"),
    (r"deposit|down ?payment|first home|own home|apartment|flat|house|asunto|omistusasun|käsiraha|koti\b",
     "a home deposit", "asunnon käsiraha", 10000, 20000, 35000,
     "10% of a 200,000 euro home plus transfer tax", "10 % 200 000 euron asunnosta ja varainsiirtovero"),
    (r"wedding|häät|häihin", "a wedding", "häät", 5000, 12000, 25000,
     "a wedding for about 80 guests", "noin 80 vieraan häät"),
    (r"laptop|computer|\bpc\b|läppär|tietokone", "a laptop", "kannettava tietokone", 600, 1200, 2000,
     "a good mid-range laptop", "hyvä keskitason kannettava"),
    (r"phone|iphone|puhelin", "a phone", "puhelin", 400, 900, 1400, "a recent mid- to high-end phone",
     "uusehko keski- tai huippuluokan puhelin"),
    (r"japan|japani|australia|usa|america|thailand|thaimaa|new york|asia|aasia", "a long-haul trip", "kaukomatka",
     2000, 3000, 4500, "two weeks for one person, flights and hotels included",
     "kaksi viikkoa yhdelle, lennot ja hotellit mukaan lukien"),
    (r"trip|holiday|vacation|travel|journey|matka|loma", "a trip", "matka", 800, 1500, 2500,
     "a week in Europe for one person", "viikko Euroopassa yhdelle"),
    (r"sofa|couch|furniture|sohva|huonekal", "furniture", "huonekalut", 500, 1200, 2500,
     "a new sofa or similar", "uusi sohva tai vastaava"),
    (r"driving licen[cs]e|ajokort", "a driving licence", "ajokortti", 1500, 2200, 3000,
     "driving school and tests for a car licence", "autokoulu ja kokeet B-korttiin"),
]
BUFFER_RE = r"buffer|emergency|rainy day|safety net|puskuri|hätävara|pahan päivän"

_MONTHS_EN = ("", "January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December")
_MONTHS_FI = ("", "tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu",
              "syyskuu", "lokakuu", "marraskuu", "joulukuu")

TOOLS = [
    {
        "name": "make_savings_plan",
        "description": "THE tool for saving towards something: 'make me a plan to save for a car', 'help me save for "
                       "a trip', 'I want to buy a sofa', 'how do I get a deposit together', with or without a price "
                       "or a date. One call does everything by code from the customer's own data: it estimates the "
                       "price when none is given (common goals), takes their usual monthly leftover, picks concrete "
                       "cuts in their own biggest flexible categories (from X to Y euros a month each), and decides "
                       "one monthly amount and the month the goal is reached (or, with a date, whether that date "
                       "works and the realistic one if not), plus a cheaper option when the plan is long. Returns "
                       "a plan_offer card with the chart and the cuts; it saves nothing. Call it FIRST and ALONE "
                       "for these questions (no general_estimate, plan_goal_by_date or propose_plan before or after "
                       "it), then answer with its `decision` (or `decision_fi`).",
        "parameters": {"type": "object", "properties": {
            "goal": {"type": "string", "description": "What they save for, their own words, e.g. 'car', 'Japan trip'."},
            "target": {"type": "number", "description": "Price in euros, only if they gave one."},
            "deadline": {"type": "string", "description": "YYYY, YYYY-MM or YYYY-MM-DD, only if they gave a date."},
            "estimate": {"type": "number", "description": "Only for a goal the built-in list cannot price (it says "
                                                          "so): your realistic Finnish price in euros."}},
            "required": ["goal"]},
    },
]
TOOL_NAMES = {t["name"] for t in TOOLS}


def _ym_add(d, n):
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    return y, m + 1


def _when_en(d, n):
    y, m = _ym_add(d, n)
    return "%s %d" % (_MONTHS_EN[m], y)


def _when_fi(d, n):
    y, m = _ym_add(d, n)
    return "%sssa %d" % (_MONTHS_FI[m], y)


def _eur(v):
    return plans.eur(round(float(v)))


def _eur_fi(v):
    return plans.eur_fi(round(float(v)))


def _label_fi(label):
    if label in plans.LABEL_FI:
        return plans.LABEL_FI[label]
    try:
        from . import charts
        return charts.label_fi(label) or label
    except Exception:
        return label


def _label_en(label):
    try:
        from . import insights as ins
        return ins.label_words(label)
    except Exception:
        return label.lower()


def estimate_price(goal):
    """(en name, fi name, low, mid, high, basis en, basis fi) for a common goal, or None."""
    s = str(goal or "").lower()
    for rx, en, fi, lo, mid, hi, b_en, b_fi in ESTIMATES:
        if re.search(rx, s):
            return en, fi, lo, mid, hi, b_en, b_fi
    return None


def _deadline(v, today):
    s = str(v or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}", s):
        s = s + "-06"       # a bare year: mid-year, the same as plan_goal_by_date
    if re.fullmatch(r"\d{4}-\d{2}", s) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        d = plans._parse_deadline(s[:7] if len(s) == 10 else s)
        if len(s) == 10:
            d = datetime.date.fromisoformat(s)
        return d if d > today else None
    raise ValueError("deadline must be YYYY, YYYY-MM or YYYY-MM-DD")


def picture(conn, today):
    """The customer's usual month over the last full months: income, spending, leftover and the flexible
    categories with their monthly averages, biggest first."""
    from . import insights as ins
    ms = ins._month_list(conn, today, LOOKBACK_MONTHS)
    if not ms:
        return None
    f = ins._avg_flows(conn, ms)
    by = ins._avg_display_map(conn, ms)
    return {"months": len(ms), "income": float(f["income"]), "spent": float(f["spent"]),
            "already_saving": float(f.get("saved") or 0.0), "leftover": float(f["surplus"]),
            "categories": sorted(((k, float(v)) for k, v in by.items() if v and v > 0), key=lambda kv: -kv[1])}


def _cut_options(categories):
    out = []
    for label, avg in categories:
        rule = CUTS.get(label)
        if not rule:
            continue
        freed = math.floor(avg * rule[0])
        if freed >= MIN_CUT:
            out.append({"label": label, "label_fi": _label_fi(label), "now": round(avg), "to": round(avg) - freed,
                        "saves": float(freed), "how": rule[1], "how_fi": rule[2]})
    out.sort(key=lambda c: -c["saves"])
    for label, avg in categories:
        if label == "Groceries":
            freed = math.floor(avg * GROCERY_CUT[0])
            if freed >= MIN_CUT:
                out.append({"label": label, "label_fi": _label_fi(label), "now": round(avg), "to": round(avg) - freed,
                            "saves": float(freed), "how": GROCERY_CUT[1], "how_fi": GROCERY_CUT[2]})
    return out


def build(conn, today, goal, target=None, deadline=None, saved=0.0, estimate=None):
    t = plans._date(today)
    goal = " ".join(str(goal or "").split())[:plans.MAX_NAME]
    if not goal:
        raise ValueError("goal is required")
    pic = picture(conn, t)
    if pic is None:
        return {"error": "there is not enough account history to plan from yet"}

    # 1. the price
    est = None
    if target in (None, "", 0):
        target = None
        if re.search(BUFFER_RE, goal.lower()):
            target = float(max(500, math.ceil(pic["spent"] * 3 / 100.0) * 100))
            est = {"what": "a buffer of three months' spending", "what_fi": "kolmen kuukauden menojen puskuri",
                   "low": target, "high": target, "basis": "three times your usual monthly spending",
                   "basis_fi": "kolme kertaa tavalliset kuukausimenosi", "own_data": True}
        else:
            e = estimate_price(goal)
            if e:
                target = float(e[3])
                est = {"what": e[0], "what_fi": e[1], "low": e[2], "high": e[4], "basis": e[5], "basis_fi": e[6]}
            elif estimate not in (None, "", 0):
                target = plans._num(estimate, "estimate")
                est = {"what": goal, "what_fi": goal, "low": None, "high": None, "basis": "a rough estimate",
                       "basis_fi": "karkea arvio"}
            else:
                return {"error": "no built-in price for this goal: call again with `estimate`, your realistic "
                                 "Finnish price in euros", "needs": ["estimate"]}
    target = plans._num(target, "target")
    if not 1 <= target <= plans.TARGET_MAX:
        raise ValueError("target out of range")
    saved = max(0.0, float(saved or 0))
    remaining = max(0.0, target - saved)
    dl = _deadline(deadline, t)

    # 2. where the money comes from
    left = pic["leftover"]
    deficit = max(0.0, -left)
    from_leftover = float(math.floor(max(0.0, left) * LEFTOVER_SHARE / 10.0) * 10)
    options = _cut_options(pic["categories"])
    months_to_dl = plans._months_between(t, dl) if dl else None
    needed = float(math.ceil(remaining / months_to_dl)) if dl else None

    chosen, freed = [], 0.0
    for c in options:
        have = from_leftover + freed - deficit
        if dl is not None and have >= needed:
            break
        if dl is None and len(chosen) >= MAX_CUTS:
            break
        if dl is None and c["label"] == "Groceries" and from_leftover - deficit + freed >= remaining / 24.0:
            continue      # groceries only when the flexible areas leave a goal more than two years away
        if dl is None and from_leftover - deficit >= remaining / 12.0:
            break         # the leftover alone reaches it within a year: no cuts needed
        chosen.append(c)
        freed += c["saves"]
        if len(chosen) >= MAX_CUTS + (1 if dl is not None else 0):
            break
    monthly_max = from_leftover + freed - deficit

    if remaining <= 0:
        return {"error": "the goal is already reached"}
    if monthly_max < plans.MIN_MOVE:
        monthly_max = 0.0

    # 3. the decision
    if dl is not None:
        fits = monthly_max >= needed
        if fits:
            # only as many cuts as the date needs
            monthly = needed
        else:
            monthly = monthly_max
        months = months_to_dl if fits else (int(math.ceil(remaining / monthly)) if monthly > 0 else None)
    else:
        fits = monthly_max > 0
        monthly = float(math.floor(monthly_max)) if monthly_max > 0 else 0.0
        months = int(math.ceil(remaining / monthly)) if monthly > 0 else None
    if months is not None and months > plans.MAX_MONTHS:
        months = None

    cheaper = None
    if est and est.get("low") and est["low"] < target and months and months > LONG_PLAN_MONTHS and monthly > 0:
        cm = int(math.ceil(max(0.0, est["low"] - saved) / monthly))
        cheaper = {"target": float(est["low"]), "months": cm, "when": _when_en(t, cm), "when_fi": _when_fi(t, cm)}

    # 4. the words: a short decision (the card lists every cut with what to do)
    monthly = float(math.floor(monthly))
    goal_fi = est["what_fi"] if (est and not est.get("own_data")) else goal
    used_leftover = min(from_leftover, monthly) if from_leftover > 0 else 0.0
    your = goal if re.match(r"(?i)(a|an|the|my|your|our)\b", goal) else "your " + goal
    if est and not est.get("own_data"):
        price_en = "I priced it at about %s (%s); change it if you know the price." % (_eur(target), est["basis"])
        price_fi = "Arvioin hinnaksi noin %s (%s); muuta, jos tiedät hinnan." % (_eur_fi(target), est["basis_fi"])
    elif est:
        price_en = "Target %s: %s." % (_eur(target), est["basis"])
        price_fi = "Tavoite %s: %s." % (_eur_fi(target), est["basis_fi"])
    else:
        price_en, price_fi = "Target %s." % _eur(target), "Tavoite %s." % _eur_fi(target)
    parts_en = (["%s of your usual leftover" % _eur(used_leftover)] if used_leftover > 0 else []) + [
        "%s %s less" % (_label_en(c["label"]), _eur(c["saves"])) for c in chosen]
    parts_fi = (["%s tavallisesta ylijäämästäsi" % _eur_fi(used_leftover)] if used_leftover > 0 else []) + [
        "%s %s vähemmän" % (_label_fi(c["label"]).lower(), _eur_fi(c["saves"])) for c in chosen]
    src_en = "It comes from " + ", ".join(parts_en) + "." if parts_en else ""
    src_fi = "Rahat tulevat näin: " + ", ".join(parts_fi) + "." if parts_fi else ""
    if deficit > 0 and chosen:
        src_en += " Today about %s more goes out than comes in a month, so the cuts cover that first." % _eur(deficit)
        src_fi += " Nyt kuussa menee noin %s enemmän kuin tulee, joten säästöt kattavat ensin sen." % _eur_fi(deficit)

    if monthly <= 0 or months is None:
        decision = ("%s Your usual month leaves nothing over and your spending has no flexible areas big enough "
                    "to free money, so a plan for %s would not hold yet. Start with a small buffer instead." % (
                        price_en, your))
        decision_fi = ("%s Tavallisesta kuukaudestasi ei jää mitään yli, eikä menoissasi ole joustavia kohtia, "
                       "joten suunnitelma (%s) ei vielä kestäisi. Aloita pienestä puskurista." % (price_fi, goal_fi))
    else:
        when, when_fi = _when_en(t, months), _when_fi(t, months)
        if dl is not None and fits:
            head = "Yes, %s by %s works: put %s aside every payday for %d months." % (
                your, _when_en(t, months_to_dl), _eur(monthly), months_to_dl)
            head_fi = "Onnistuu: laita %s sivuun joka palkkapäivä %d kuukauden ajan, niin %s on koossa %s." % (
                _eur_fi(monthly), months_to_dl, goal_fi, _when_fi(t, months_to_dl))
        elif dl is not None:
            head = ("%s by %s would need %s a month, more than your money can carry. My plan: %s a month, "
                    "and you have it in %s." % (your[:1].upper() + your[1:], _when_en(t, months_to_dl),
                                                _eur(needed), _eur(monthly), when))
            head_fi = ("Jotta %s olisi koossa %s, tarvitsisit %s kuussa, enemmän kuin rahasi kestävät. "
                       "Suunnitelmani: %s kuussa, niin se on koossa %s." % (
                           goal_fi, _when_fi(t, months_to_dl), _eur_fi(needed), _eur_fi(monthly), when_fi))
        else:
            head = "My plan: put %s aside every payday and you have %s in %s (%d months)." % (
                _eur(monthly), your, when, months)
            head_fi = "Suunnitelmani: laita %s sivuun joka palkkapäivä, niin %s on koossa %s (%d kk)." % (
                _eur_fi(monthly), goal_fi, when_fi, months)
        decision = " ".join(x for x in (head, src_en, price_en) if x)
        decision_fi = " ".join(x for x in (head_fi, src_fi, price_fi) if x)
        if cheaper:
            decision += " A %s option would be ready in %s." % (_eur(cheaper["target"]), cheaper["when"])
            decision_fi += " %s vaihtoehto olisi koossa %s." % (_eur_fi(cheaper["target"]), cheaper["when_fi"])

    out = {"goal": goal, "target": round(target, 2), "estimate": est, "saved": round(saved, 2),
           "usual_income": round(pic["income"]), "usual_spending": round(pic["spent"]),
           "usual_leftover": round(left), "from_leftover": from_leftover, "cuts": chosen,
           "cuts_total": freed, "monthly": monthly, "months": months, "fits": bool(fits),
           "needed_for_date": needed, "cheaper": cheaper,
           "decision": decision, "decision_fi": decision_fi, "text": decision, "text_fi": decision_fi,
           "explain": ("Leftover, spending and categories are your own monthly averages over the last %d full "
                       "months. %d%% of the leftover goes to the plan, the rest stays as a margin. Each cut is a "
                       "share of that category's own average." % (pic["months"], int(LEFTOVER_SHARE * 100)))}
    if monthly > 0 and months:
        p = plans.preview(target, monthly=monthly, today=t, saved=saved, usual_leftover=monthly_max, name=goal)
        reach = p["deadline"] if (dl is None or not fits) else dl.isoformat()
        out.update({"name": goal, "deadline": reach, "series": p["series"],
                    "note": price_en, "note_fi": price_fi,
                    "widget": {"type": "plan", "params": {"name": goal, "target": round(target, 2),
                                                          "monthly": monthly, "deadline": reach}}})
    else:
        out["no_card"] = True
    return out


def call(name, args, ctx):
    """Run the tool. Never raises; returns {"error": ...} on any problem."""
    args = args if isinstance(args, dict) else {}
    try:
        if name != "make_savings_plan":
            return {"error": "unknown tool", "card": "error"}
        goal = args.get("goal") or args.get("name")
        saved = 0.0
        g = getattr(ctx, "goal", None)
        if isinstance(g, dict) and str(g.get("name") or "").strip().lower() == str(goal or "").strip().lower():
            try:
                saved = max(0.0, float(g.get("saved") or 0))
            except (TypeError, ValueError):
                saved = 0.0
        res = build(ctx.conn, ctx.today, goal, args.get("target"), args.get("deadline"), saved=saved,
                    estimate=args.get("estimate"))
    except (ValueError, TypeError, KeyError) as e:
        return {"error": "bad arguments: %s" % str(e)[:160], "card": "error"}
    except Exception:
        return {"error": "the tool failed", "card": "error"}
    res = dict(res)
    if "error" not in res and not res.get("no_card"):
        res["card"] = "plan_offer"
    elif "error" not in res:
        res["card"] = "table"
    return res
