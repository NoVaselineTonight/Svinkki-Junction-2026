"""Averages as material for the coach: "what is typical for people like me?".

Compares the one customer in the sandbox with precomputed group statistics (never fewer than 20
customers, never individual rows). Pure standard library. The three data sources are injectable:

    bench_many(group_keys, metrics) -> {metric: {group_key, n, p25, median, p75, mean}}
    bench_meta(metric=None)         -> {metric, name, unit, description} or a list of them
    customer_metrics(conn, today)   -> {metric: value} for the customer in `conn`

They default to the functions of the same names in app.db (imported lazily).
"""
from __future__ import annotations

import re

MIN_GROUP = 20
NOTE = ("Averages are computed once from all customers. Only group statistics of at least 20 people are "
        "used; nobody's individual data is shown.")

# ---------------------------------------------------------------------------- topics
TOPICS = {
    "overview": {
        "title": "Overview",
        "metrics": ["income", "spent", "regular", "unexpected", "everyday", "savings"],
        "keywords": ["overview", "overall", "in general", "in total", "total spending", "income", "salary",
                     "baskets", "everything", "my money"],
    },
    "taxi": {
        "title": "Taxis",
        "metrics": ["label:Taxi", "visits:Taxi", "ticket:Taxi", "users:Taxi"],
        "keywords": ["taxi", "cab", "uber", "bolt", "ride"],
    },
    "night_out": {
        "title": "Nights out",
        "metrics": ["night_out", "night_out_count", "night_out_cost", "night_out_items"],
        "keywords": ["night out", "nights out", "going out", "nightlife", "club", "clubbing", "pub", "pubs",
                     "bar", "bars", "drinks", "drinking", "beer", "party", "partying"],
    },
    "dining_out": {
        "title": "Dining out",
        "metrics": ["group:dining_out", "label:Restaurant", "visits:Restaurant", "ticket:Restaurant",
                    "label:Fast food", "visits:Fast food"],
        "keywords": ["dining out", "dining", "eating out", "eat out", "restaurant", "fast food", "takeaway",
                     "take away", "take-away", "lunch", "dinner", "cafe", "cafes", "burger", "food out",
                     "food delivery"],
    },
    "groceries": {
        "title": "Groceries",
        "metrics": ["label:Groceries", "visits:Groceries", "ticket:Groceries", "group:food_total"],
        "keywords": ["groceries", "grocery", "supermarket", "food shopping", "food budget", "food",
                     "weekly shop"],
    },
    "transport": {
        "title": "Transport",
        "metrics": ["group:transport", "label:Public transport", "label:Fuel", "label:Parking"],
        "keywords": ["transport", "transportation", "commute", "commuting", "public transport", "bus", "train",
                     "tram", "metro", "fuel", "petrol", "gas", "diesel", "parking", "car costs", "travel card"],
    },
    "shopping": {
        "title": "Shopping",
        "metrics": ["group:shopping", "label:Clothing", "label:Electronics", "label:Shopping", "label:Hobbies"],
        "keywords": ["shopping", "clothes", "clothing", "fashion", "electronics", "gadgets", "hobby", "hobbies",
                     "books", "retail"],
    },
    "travel": {
        "title": "Travel",
        "metrics": ["group:travel", "label:Flights", "label:Hotels", "label:Travel agency", "label:Car rental"],
        "keywords": ["travel", "travelling", "traveling", "holiday", "holidays", "vacation", "vacations",
                     "trip", "trips", "flight", "flights", "hotel", "hotels", "airline"],
    },
    "health": {
        "title": "Health",
        "metrics": ["group:health", "label:Pharmacy", "label:Doctor", "label:Dentist"],
        "keywords": ["health", "healthcare", "pharmacy", "medicine", "medicines", "doctor", "doctors",
                     "dentist", "dentists", "medical"],
    },
    "home": {
        "title": "Home",
        "metrics": ["group:home", "label:Housing", "label:Utilities", "label:Home improvement",
                    "label:Furniture", "housing_share"],
        "keywords": ["home", "housing", "rent", "mortgage payment", "utilities", "electricity", "furniture",
                     "home improvement", "diy", "household", "bills"],
    },
    "entertainment": {
        "title": "Entertainment and sports",
        "metrics": ["label:Entertainment", "label:Cinema", "label:Events", "label:Gym & sports"],
        "keywords": ["entertainment", "cinema", "movies", "movie", "concert", "concerts", "events", "gym",
                     "sports", "sport", "fitness", "streaming", "subscriptions", "fun"],
    },
    "habits": {
        "title": "Spending habits",
        "metrics": ["weekend_share", "payday_week_share", "small_spend", "small_count", "big_count_year"],
        "keywords": ["habit", "habits", "weekend", "weekends", "payday", "pay day", "small purchases",
                     "small buys", "big purchases", "big buys", "impulse", "spending pattern",
                     "spending patterns", "spending style"],
    },
    "money_health": {
        "title": "Money health",
        "metrics": ["surplus", "savings_rate", "buffer_months", "overdraft_month_share", "invests",
                    "housing_share", "everyday_share"],
        "keywords": ["money health", "financial health", "surplus", "left over", "leftover", "savings rate",
                     "saving rate", "save", "saving", "savings", "buffer", "rainy day", "emergency fund",
                     "overdraft", "below zero", "negative balance", "invest", "investing", "investments"],
    },
}
TOPIC_ORDER = ["overview", "taxi", "night_out", "dining_out", "groceries", "transport", "shopping", "travel",
               "health", "home", "entertainment", "habits", "money_health"]
assert set(TOPIC_ORDER) == set(TOPICS)

_KW_RES = {}


def _kw_re(kw):
    r = _KW_RES.get(kw)
    if r is None:
        r = _KW_RES[kw] = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?:s|es)?(?![a-z0-9])")
    return r


def topic_for(text):
    """Map free text ("taxis", "a night out", "eating out") to a topic key, or None."""
    s = re.sub(r"\s+", " ", str(text or "").lower().replace("_", " ").replace("-", " ")).strip()
    if not s:
        return None
    if s.replace(" ", "_") in TOPICS:
        return s.replace(" ", "_")
    best = None  # (score, -order, key)
    for order, key in enumerate(TOPIC_ORDER):
        for kw in TOPICS[key]["keywords"]:
            k = kw.replace("-", " ")
            if _kw_re(k).search(s):
                score = len(k)
                if best is None or (score, -order) > (best[0], best[1]):
                    best = (score, -order, key)
    return best[2] if best else None


def topic_catalogue():
    return [{"key": k, "title": TOPICS[k]["title"]} for k in TOPIC_ORDER]


# ---------------------------------------------------------------------------- units and wording
_FALLBACK_UNIT = {
    "savings_rate": "share", "night_out": "eur_per_month", "night_out_count": "count_per_month",
    "night_out_cost": "eur", "night_out_items": "count", "weekend_share": "share",
    "payday_week_share": "share", "small_spend": "eur_per_month", "small_count": "count_per_month",
    "big_count_year": "count_per_year", "overdraft_month_share": "share", "buffer_months": "months",
    "invests": "share", "housing_share": "share", "everyday_share": "share",
}
_SHARE_MEAN = ("users:", "invests")          # typical = mean (a share of customers), not the median
_NO_DIRECTION = ("users:", "invests")
_TOLERANCE = {"eur_per_month": 5.0, "eur": 3.0, "count_per_month": 0.2, "count_per_year": 0.5,
              "share": 0.03, "months": 0.3, "count": 0.3}
_FLOOR = {"eur_per_month": 25.0, "eur": 15.0, "count_per_month": 1.0, "count_per_year": 3.0,
          "share": 0.10, "months": 1.0, "count": 2.0}

# label -> (visits noun, verb, ticket noun, "use it at all" phrase, money noun)
_LABEL_INFO = {
    "Taxi": ("taxi rides", "take", "a taxi ride", "use taxis at all", "taxis"),
    "Restaurant": ("restaurant visits", "make", "a restaurant visit", "eat at restaurants", "restaurants"),
    "Fast food": ("fast food purchases", "make", "a fast food purchase", "buy fast food", "fast food"),
    "Bar": ("bar visits", "make", "a bar visit", "go to bars", "bars"),
    "Groceries": ("grocery trips", "make", "a grocery trip", "buy groceries", "groceries"),
    "Public transport": ("public transport trips", "make", "a public transport trip", "use public transport",
                         "public transport"),
    "Fuel": ("fuel stops", "make", "a fuel stop", "buy fuel", "fuel"),
    "Parking": ("parking payments", "make", "a parking payment", "pay for parking", "parking"),
    "Pharmacy": ("pharmacy visits", "make", "a pharmacy visit", "visit pharmacies", "pharmacies"),
    "Doctor": ("doctor visits", "make", "a doctor visit", "pay for doctor visits", "doctors"),
    "Dentist": ("dentist visits", "make", "a dentist visit", "pay for dentist visits", "dentists"),
    "Clothing": ("clothing purchases", "make", "a clothing purchase", "buy clothes", "clothing"),
    "Electronics": ("electronics purchases", "make", "an electronics purchase", "buy electronics",
                    "electronics"),
    "Furniture": ("furniture purchases", "make", "a furniture purchase", "buy furniture", "furniture"),
    "Home improvement": ("home improvement purchases", "make", "a home improvement purchase",
                         "spend on home improvement", "home improvement"),
    "Hobbies": ("hobby purchases", "make", "a hobby purchase", "spend on hobbies", "hobbies"),
    "Shopping": ("shopping purchases", "make", "a shopping purchase", "go shopping", "general shopping"),
    "Cinema": ("cinema visits", "make", "a cinema visit", "go to the cinema", "cinema"),
    "Events": ("event tickets", "buy", "an event ticket", "buy event tickets", "events"),
    "Gym & sports": ("gym and sports payments", "make", "a gym or sports payment", "pay for gym or sports",
                     "gym and sports"),
    "Entertainment": ("entertainment purchases", "make", "an entertainment purchase", "spend on entertainment",
                      "entertainment"),
    "Flights": ("flight purchases", "make", "a flight", "buy flights", "flights"),
    "Hotels": ("hotel bookings", "make", "a hotel booking", "book hotels", "hotels"),
    "Travel agency": ("travel agency bookings", "make", "a travel agency booking", "use travel agencies",
                      "travel agencies"),
    "Car rental": ("car rentals", "make", "a car rental", "rent cars", "car rental"),
    "Housing": ("housing payments", "make", "a housing payment", "pay housing costs", "housing"),
    "Utilities": ("utility payments", "make", "a utility payment", "pay utilities", "utilities"),
}
_GROUP_NOUN = {
    "dining_out": "dining out (restaurants and fast food)", "going_out": "going out",
    "transport": "transport", "health": "health care", "home": "home and household",
    "shopping": "shopping", "travel": "travel", "food_total": "food in total (groceries plus dining out)",
}

# metric -> template. {you}/{typ} are formatted values, {who}/{Who} the group in words.
_TEMPLATES = {
    "income": "You earn about {you} a month; {who} typically earn {typ}.",
    "spent": "You spend about {you} a month in total; {who} typically spend {typ}.",
    "regular": "Your regular essentials come to about {you} a month; for {who} it is typically {typ}.",
    "unexpected": "Unexpected necessities cost you about {you} a month; for {who} it is typically {typ}.",
    "everyday": "You spend about {you} a month on everyday things; {who} typically spend {typ}.",
    "savings": "You put about {you} a month into savings or investments; {who} typically put {typ}.",
    "surplus": "You have about {you} left over each month; {who} typically have {typ}.",
    "savings_rate": "You keep about {you} of your income; {who} typically keep {typ}.",
    "night_out": "Nights out cost you about {you} a month; {who} typically spend {typ}.",
    "night_out_count": "You go out about {you} times a month; {who} about {typ}.",
    "night_out_cost": "A night out costs you about {you} on average; for {who} it is typically {typ}.",
    "night_out_items": "On a night out you make about {you} purchases; {who} typically make {typ}.",
    "weekend_share": "{you} of your spending happens at weekends; for {who} it is typically {typ}.",
    "payday_week_share": "{you} of your spending falls in the week after payday; for {who} it is typically {typ}.",
    "small_spend": "You spend about {you} a month on small purchases; {who} typically spend {typ}.",
    "small_count": "You make about {you} small purchases a month; {who} typically make {typ}.",
    "big_count_year": "You make about {you} big purchases a year; {who} typically make {typ}.",
    "overdraft_month_share": "Your balance goes below zero in {you} of months; for {who} it is typically {typ}.",
    "buffer_months": "Your balance would cover about {you} months of regular costs; for {who} it is typically {typ}.",
    "housing_share": "Housing takes {you} of your income; for {who} it is typically {typ}.",
    "everyday_share": "Everyday spending is {you} of your spending; for {who} it is typically {typ}.",
}
_FALLBACK_NAME = {
    "income": "Monthly income", "spent": "Total spending", "regular": "Regular essentials",
    "unexpected": "Unexpected necessities", "everyday": "Everyday spending", "savings": "Put into savings",
    "surplus": "Money left over", "savings_rate": "Share of income kept", "night_out": "Nights out",
    "night_out_count": "Nights out per month", "night_out_cost": "Cost of a night out",
    "night_out_items": "Purchases per night out", "weekend_share": "Spending at weekends",
    "payday_week_share": "Spending in payday week", "small_spend": "Small purchases",
    "small_count": "Number of small purchases", "big_count_year": "Big purchases a year",
    "overdraft_month_share": "Months below zero", "buffer_months": "Buffer in months",
    "invests": "People who invest", "housing_share": "Housing share of income",
    "everyday_share": "Everyday share of spending",
}


def _label_info(label):
    if label in _LABEL_INFO:
        return _LABEL_INFO[label]
    low = label.lower()
    return ("%s purchases" % low, "make", "a %s purchase" % low, "spend on %s" % low, low)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _fmt_eur(v):
    """House rule R1: whole euros from EUR 20, cents below, never a minus sign (the sentence words it)."""
    from app import insights
    return insights.money(v, zero="€0")


def _fmt_num(v):
    v = float(v)
    return "{:.0f}".format(v) if abs(v) >= 10 else "{:.1f}".format(v)


def _fmt_pct(v):
    return "{:.0f}%".format(100.0 * float(v))


_COUNT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "eleven", "twelve"]


def _freq(v):
    """A count per month as words: "about 3 times a month", "about once every two or three months"."""
    v = float(v)
    if v >= 1.5:
        return "about %d times a month" % round(v)
    if v >= 0.67:
        return "about once a month"
    if v <= 0:
        return "not at all"
    interval = 1.0 / v
    if interval > 12:
        return "less than once a year"
    lo, hi = int(interval), int(interval) + (0 if interval == int(interval) else 1)
    if lo == 1:
        return "about once every month or two"
    if lo == hi:
        return "about once every %s months" % _COUNT_WORDS[lo]
    return "about once every %s or %s months" % (_COUNT_WORDS[lo], _COUNT_WORDS[hi])


def _fmt(unit, v):
    if not _is_num(v):
        return None
    if unit in ("eur_per_month", "eur"):
        return _fmt_eur(v)
    if unit == "share":
        return _fmt_pct(v)
    return _fmt_num(v)


def _who(group_key):
    """Plain words for a group key; an area code never appears."""
    parts = str(group_key or "").split("|")
    band = next((p[4:] for p in parts if p.startswith("age:")), None)
    area = any(p.startswith("area:") for p in parts)
    if band and area:
        return "people aged %s in your area" % band
    if band:
        return "people aged %s" % band
    return "all customers"


def _mask(group_key):
    return "|".join("area:*" if p.startswith("area:") else p for p in str(group_key or "").split("|"))


def _cap(s):
    return s[:1].upper() + s[1:]


def _sentence(metric, name, unit, you, typ, who, mean):
    """One plain sentence for a row. `you` and `typ` are raw numbers (you may be None)."""
    fy, ft = _fmt(unit, you), _fmt(unit, typ)
    kind, _, rest = metric.partition(":")
    if kind == "users":
        _, _, _, use, _ = _label_info(rest)
        s = "%s of people like you %s." % (_fmt_pct(typ), use)
        if _is_num(you):
            s += " You are one of them." if you >= 0.5 else " You are not one of them."
        return s
    if metric == "invests":
        s = "%s of people like you put money into investments." % _fmt_pct(typ)
        if _is_num(you):
            s += " You are one of them." if you >= 0.5 else " You are not one of them."
        return s
    if fy is None:
        return "For %s, %s is typically %s." % (who, name.lower(), ft)
    if kind == "label":
        m_noun = _label_info(rest)[4]
        return "You spend about %s a month on %s; %s typically spend %s." % (fy, m_noun, who, ft)
    if kind == "visits":
        noun, verb, thing, _, _ = _label_info(rest)
        if _is_num(you) and _is_num(typ):
            fyw, ftw = _freq(you), _freq(typ)
            if fyw == ftw:
                return "You and %s both %s %s %s." % (who, verb, thing, fyw)
            return "You %s %s %s; %s %s." % (verb, thing, fyw, who, ftw)
        return "%s %s %s %s." % (_cap(who), verb, thing, _freq(typ)) if _is_num(typ) else "No figure yet."
    if metric == "surplus" and _is_num(you) and you < 0:
        return "You spend about %s a month more than you earn; %s typically have %s left over." % (fy, who, ft)
    if kind == "ticket":
        t = _label_info(rest)[2]
        return "%s costs you about %s on average; for %s it is typically %s." % (_cap(t), fy, who, ft)
    if kind == "group":
        noun = _GROUP_NOUN.get(rest, rest.replace("_", " "))
        return "You spend about %s a month on %s; %s typically spend %s." % (fy, noun, who, ft)
    tpl = _TEMPLATES.get(metric)
    if tpl:
        s = tpl.format(you=fy, typ=ft, who=who, Who=_cap(who))
        return _cap(s) if s[:1].islower() else s
    unit_words = {"eur_per_month": " a month", "count_per_month": " a month", "count_per_year": " a year",
                  "months": " months"}.get(unit, "")
    return "%s: you %s%s; for %s it is typically %s%s." % (name, fy, unit_words, who, ft, unit_words)


def _direction(metric, unit, you, typ):
    if any(metric.startswith(p) for p in _NO_DIRECTION) or not (_is_num(you) and _is_num(typ)):
        return None
    diff = float(you) - float(typ)
    tol = max(_TOLERANCE.get(unit, 0.0), 0.10 * abs(float(typ)))
    if abs(diff) <= tol:
        return "about the same"
    return "more" if diff > 0 else "less"


def _score(row):
    you, typ = row.get("you"), row.get("typical")
    if not (_is_num(you) and _is_num(typ)) or row.get("direction") in (None, "about the same"):
        return 0.0
    return abs(you - typ) / max(abs(typ), _FLOOR.get(row.get("unit"), 1.0))


# ---------------------------------------------------------------------------- data sources
def _default_sources(bench_many, bench_meta, customer_metrics):
    if bench_many is None or bench_meta is None or customer_metrics is None:
        from app import db
        bench_many = bench_many or db.bench_many
        bench_meta = bench_meta or db.bench_meta
        customer_metrics = customer_metrics or db.customer_metrics
    return bench_many, bench_meta, customer_metrics


def _catalogue(bench_meta):
    try:
        cat = bench_meta(None)
    except Exception:
        return {}
    if isinstance(cat, dict):
        cat = [cat] if "metric" in cat else list(cat.values())
    out = {}
    for m in cat or []:
        if isinstance(m, dict) and m.get("metric"):
            out[m["metric"]] = m
    return out


def _meta_for(metric, cat, bench_meta):
    m = cat.get(metric)
    if m is None:
        try:
            m = bench_meta(metric)
        except Exception:
            m = None
    m = m if isinstance(m, dict) else {}
    kind, _, rest = metric.partition(":")
    unit = m.get("unit")
    if not unit:
        unit = {"label": "eur_per_month", "group": "eur_per_month", "visits": "count_per_month",
                "ticket": "eur", "users": "share"}.get(kind) or _FALLBACK_UNIT.get(metric, "eur_per_month")
    name = m.get("name")
    if not name:
        if kind == "label":
            name = _label_info(rest)[4].capitalize()
        elif kind in ("visits", "ticket", "users", "group"):
            name = "%s: %s" % (kind.capitalize(), rest.replace("_", " "))
        else:
            name = _FALLBACK_NAME.get(metric, metric.replace("_", " ").capitalize())
    return name, unit


# ---------------------------------------------------------------------------- main entry
def averages(conn, today, profile, topic=None, bench_many=None, bench_meta=None, customer_metrics=None):
    """Compare the customer with the typical person in their group on one topic."""
    from app import insights
    bench_many, bench_meta, customer_metrics = _default_sources(bench_many, bench_meta, customer_metrics)
    key = None
    if topic in (None, ""):
        key = "overview"
    else:
        key = topic if topic in TOPICS else topic_for(topic)
        if key is None:
            raise ValueError("unknown topic")
    spec = TOPICS[key]
    metrics = list(spec["metrics"])
    group_keys = insights._group_keys(profile)
    try:
        stats = bench_many(list(group_keys), list(metrics)) or {}
    except Exception:
        stats = {}
    try:
        mine = customer_metrics(conn, today) or {}
    except Exception:
        mine = {}
    cat = _catalogue(bench_meta)

    rows = []
    for metric in metrics:
        st = stats.get(metric)
        if not isinstance(st, dict):
            continue
        try:
            n = int(st.get("n") or 0)
        except (TypeError, ValueError):
            continue
        if n < MIN_GROUP:
            continue
        use_mean = any(metric.startswith(p) for p in _SHARE_MEAN)
        typ = st.get("mean") if use_mean else st.get("median")
        if not _is_num(typ):
            continue
        if metric.startswith("users:") and float(typ) >= 0.95:
            continue       # "100% of people use taxis" says nothing; the row is left out
        name, unit = _meta_for(metric, cat, bench_meta)
        you = mine.get(metric)
        you = round(float(you), 4 if unit == "share" else 2) if _is_num(you) else None
        who = _who(st.get("group_key"))
        digits = 4 if unit == "share" else 2

        def rnd(v):
            return round(float(v), digits) if _is_num(v) else None
        typ = rnd(typ)
        row = {"metric": metric, "name": name, "unit": unit, "you": you, "typical": typ,
               "mean": rnd(st.get("mean")), "p25": rnd(st.get("p25")), "p75": rnd(st.get("p75")), "n": n,
               "direction": _direction(metric, unit, you, typ),
               "sentence": _sentence(metric, name, unit, you, typ, who, st.get("mean")),
               "_gk": st.get("group_key")}
        rows.append(row)

    group_counts = {}
    group_n = {}
    for r in rows:
        group_counts[r["_gk"]] = group_counts.get(r["_gk"], 0) + 1
        group_n[r["_gk"]] = min(group_n.get(r["_gk"], r["n"]), r["n"])
    gkey = None
    if group_counts:
        order = {k: i for i, k in enumerate(group_keys)}
        gkey = max(group_counts, key=lambda k: (group_counts[k], -order.get(k, 99)))
    for r in rows:
        r.pop("_gk", None)
    n_group = group_n.get(gkey, 0)

    if gkey is None:
        group = {"key": None, "n": 0, "description": "No group of at least 20 people was available."}
        explain = ("No comparison group of at least 20 people is available for this topic, so I cannot "
                   "compare you with others here.")
        headline = "I have no comparison for %s: no group of at least 20 people is available." % \
                   spec["title"].lower()
    else:
        who = _who(gkey)
        group = {"key": _mask(gkey), "n": n_group, "description": _cap(who) if who != "all customers"
                 else "All customers"}
        explain = ("Your own figures come from your transactions. They are placed next to the typical "
                   "(median) figure of %s (%d people at least); for shares of people who use something, "
                   "the share is shown. Only group statistics are used." % (who, min(r["n"] for r in rows)))
        best = max(rows, key=_score)
        if _score(best) > 0:
            headline = best["sentence"]
        else:
            headline = "On %s you are about in line with %s." % (spec["title"].lower(), who)
    return {"topic": key, "title": spec["title"], "group": group, "rows": rows, "headline": headline,
            "topics": topic_catalogue(), "note": NOTE, "explain": explain, "evidence": []}
