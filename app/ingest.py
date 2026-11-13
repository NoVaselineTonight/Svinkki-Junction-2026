"""Build data/svinkki.db from the S-Pankki CSV folder.

    python -m app.ingest [--data-dir DIR] [--out PATH] [--customers N]

Streams the big transaction CSV once (it is sorted by customer), classifies every row, writes the
`tx`, `customers`, `bench`, `personas` and `meta` tables to a temp file and replaces the target
atomically. The dataset itself never enters the repository (data/ is git-ignored).
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from app import classify

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = "C:/Users/onnik/Desktop/Junction-2026-S-pankki-filtered"
DEFAULT_TODAY = "2026-09-24"
BATCH = 50_000
MIN_GROUP = 20

TX_FILE = "tx_junction_transactions.csv"
CUSTOMER_FILE = "tx_customers_junction.csv"
MORTGAGE_FILE = "mtg_tx_customer_link_and_final_mtg_infio.csv"

_MONTHS = {m: f"{i:02d}" for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}

SCHEMA = """
CREATE TABLE tx (cid TEXT, d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT,
                 mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT);
CREATE TABLE customers (cid TEXT PRIMARY KEY, postal TEXT, age INTEGER, age_band TEXT, area TEXT);
CREATE TABLE bench (group_key TEXT, metric TEXT, n INTEGER, p25 REAL, median REAL, p75 REAL,
                    mean REAL, PRIMARY KEY (group_key, metric));
CREATE TABLE bench_meta (metric TEXT PRIMARY KEY, name TEXT, unit TEXT, description TEXT);
CREATE TABLE demo_pool (cid TEXT PRIMARY KEY);
CREATE TABLE personas (cid TEXT PRIMARY KEY, name TEXT, blurb TEXT);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


# --------------------------------------------------------------------------- config helpers

def _cfg(fn: str, env: str, default: str) -> str:
    try:
        from app import config  # type: ignore
        return str(getattr(config, fn)())
    except Exception:
        return os.environ.get(env) or default


def _data_dir() -> str:
    return _cfg("data_dir", "SVINKKI_DATA_DIR", DEFAULT_DATA_DIR)


def _today() -> str:
    return _cfg("today", "SVINKKI_TODAY", DEFAULT_TODAY)


def _default_out() -> str:
    try:
        from app import config  # type: ignore
        return str(config.db_path())
    except Exception:
        p = Path(os.environ.get("SVINKKI_DB") or "data/svinkki.db")
        return str(p if p.is_absolute() else _REPO / p)


# --------------------------------------------------------------------------- small helpers

def convert_ts(raw: str, fallback_date: str) -> str:
    """'03OCT24:09:04:04' -> '2024-10-03 09:04:04'. Falls back to midnight of tx_date."""
    try:
        return f"20{raw[5:7]}-{_MONTHS[raw[2:5]]}-{raw[0:2]} {raw[8:]}"
    except (KeyError, IndexError):
        return fallback_date + " 00:00:00"


def age_band(age) -> str:
    if age is None:
        return ""
    if age < 25:
        return "18-24"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    if age < 65:
        return "55-64"
    return "65+"


def _open_csv(path):
    return open(path, "r", encoding="utf-8-sig", newline="")


def _read_customers(data_dir: str) -> dict:
    out = {}
    with _open_csv(os.path.join(data_dir, CUSTOMER_FILE)) as f:
        for r in csv.DictReader(f):
            cid = r["customer_id"].strip()
            postal = (r.get("customer_postal_code") or "").strip()
            try:
                age = int(float(r.get("customer_age") or ""))
            except ValueError:
                age = None
            out[cid] = (postal, age)
    return out


def _read_mortgage(data_dir: str) -> dict:
    """cid -> final decision, when the optional mortgage file is present."""
    path = os.path.join(data_dir, MORTGAGE_FILE)
    out = {}
    if os.path.exists(path):
        with _open_csv(path) as f:
            for r in csv.DictReader(f):
                out[r["customer_id"].strip()] = (r.get("final_decision") or "").strip()
    return out


def _month_complete(month: str, today: str) -> bool:
    y, m = int(month[:4]), int(month[5:7])
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return (nxt - timedelta(days=1)).isoformat() <= today


# --------------------------------------------------------------------------- shared per-customer metrics

GROUPS = {
    "dining_out": ["Restaurant", "Fast food"],
    "going_out": ["Restaurant", "Fast food", "Bar", "Events", "Cinema", "Entertainment"],
    "transport": ["Public transport", "Fuel", "Taxi", "Parking"],
    "health": ["Pharmacy", "Doctor", "Dentist", "Other health"],
    "home": ["Home improvement", "Electronics", "Furniture"],
    "shopping": ["Clothing", "Hobbies", "Books", "Shopping"],
    "travel": ["Flights", "Hotels", "Travel agency", "Car rental", "Travel"],
    "food_total": ["Groceries", "Restaurant", "Fast food"],
}
NON_SPENDING_LABELS = frozenset({"Savings & investments", "Salary", "Other income", "Transfer out"})
SMALL_LIMIT = 10.0       # EUR, a "small" purchase is below this
BIG_LIMIT = 500.0        # EUR, a "big" purchase is at least this
PAYDAY_DAYS = 7          # everyday spending 0..7 days after a salary payment
# Metrics where "no activity" means 0 (so every customer in a group contributes); all others are
# skipped for a customer when they cannot be computed (for example a share with zero income).
_ZERO_FILL = frozenset({"income", "regular", "unexpected", "everyday", "savings", "night_out"})
_ZERO_FILL_PREFIX = ("label:", "visits:", "users:")

_complete_cache: dict = {}
_ord_cache: dict = {}


def _complete(month: str, today: str) -> bool:
    k = (month, today)
    v = _complete_cache.get(k)
    if v is None:
        v = _complete_cache[k] = _month_complete(month, today)
    return v


def _ordinal(day: str) -> int:
    v = _ord_cache.get(day)
    if v is None:
        v = _ord_cache[day] = date.fromisoformat(day).toordinal()
    return v


def is_zero_fill(metric: str) -> bool:
    return metric in _ZERO_FILL or metric.startswith(_ZERO_FILL_PREFIX)


def compute_metrics(rows, today: str) -> dict:
    """THE definition of every per-customer metric (used by the ingest pass and by
    db.customer_metrics, so the two can never drift apart).

    rows: sequence of (d, ts, amount, balance, type, label, basket, context) for ONE customer,
    sorted by ts. Rows after `today` are ignored. Only complete calendar months count.
    Returns {"metrics": {name: value}, "months": k, "last": {key: amount of last full month},
    "demo": bool (main-bank, very active customer)}.
    A metric that cannot be computed for this customer is absent; absent zero-fill metrics
    (see is_zero_fill) mean 0."""
    today = str(today)
    months = defaultdict(lambda: defaultdict(float))
    seen = set()
    overdraft = set()
    cnt = defaultdict(int)          # label -> purchases
    tot = defaultdict(float)        # label -> EUR
    nights = defaultdict(lambda: [0.0, 0])   # evening date -> [EUR, purchases]
    eve_total = eve_weekend = eve_payday = 0.0
    small_sum = 0.0
    small_cnt = big_cnt = purchases = 0
    invests = sweep = False
    sal_months = set()
    house_months = set()
    n_tx = 0
    last_salary = None
    last_balance = None
    spending = classify.SPENDING_BASKETS
    for d, ts, amount, balance, typ, label, basket, ctx in rows:
        if d > today:
            continue
        last_balance = balance
        n_tx += 1
        day = ts[:10]
        if typ == "salary":
            last_salary = _ordinal(day)
        elif typ == "salary_sweep":
            sweep = True
        mm = ts[:7]
        if not _complete(mm, today):
            continue
        seen.add(mm)
        if typ == "salary":
            sal_months.add(mm)
        elif typ == "housing_payment":
            house_months.add(mm)
        if balance < 0:
            overdraft.add(mm)
        m = months[mm]
        if basket == "income":
            m["income"] += amount
        elif basket == "savings":
            m["savings"] += -amount
            if amount < 0:
                invests = True
        elif basket in spending:
            a = -amount
            m[basket] += a
            m["label:" + label] += a
            cnt[label] += 1
            tot[label] += a
            if ctx:
                m["night_out"] += a
                nk = classify.night_key(ts)
                if nk is not None:
                    nt = nights[nk]
                    nt[0] += a
                    nt[1] += 1
            if typ == "purchase":
                purchases += 1
                if a < SMALL_LIMIT:
                    small_sum += a
                    small_cnt += 1
                elif a >= BIG_LIMIT:
                    big_cnt += 1
            if basket == "everyday":
                o = _ordinal(day)
                eve_total += a
                if (o + 6) % 7 >= 4:
                    eve_weekend += a
                if last_salary is not None and 0 <= o - last_salary <= PAYDAY_DAYS:
                    eve_payday += a
    complete = sorted(seen)
    if not complete:
        return {"metrics": {}, "months": 0, "last": {}, "demo": False}
    k = len(complete)
    avg = {}
    keys = set()
    for mm in complete:
        keys.update(months[mm].keys())
    for key in keys:
        avg[key] = sum(months[mm].get(key, 0.0) for mm in complete) / k
    spent = avg.get("regular", 0.0) + avg.get("unexpected", 0.0) + avg.get("everyday", 0.0)
    avg["spent"] = spent
    inc = avg.get("income", 0.0)
    if inc > 0:
        avg["savings_rate"] = (inc - spent) / inc
        avg["housing_share"] = avg.get("label:Housing", 0.0) / inc
        avg["everyday_share"] = avg.get("everyday", 0.0) / inc
    avg["surplus"] = inc - spent - avg.get("savings", 0.0)
    for label, c in cnt.items():
        avg["visits:" + label] = c / k
        avg["ticket:" + label] = tot[label] / c
        avg["users:" + label] = 1.0
    for g, labels_ in GROUPS.items():
        avg["group:" + g] = sum(avg.get("label:" + lb, 0.0) for lb in labels_)
    # nights out (a night belongs to the month of its evening date)
    full = [v for nk, v in nights.items() if _complete(nk[:7], today)]
    avg["night_out_count"] = len(full) / k
    if full:
        avg["night_out_cost"] = sum(v[0] for v in full) / len(full)
        avg["night_out_items"] = sum(v[1] for v in full) / len(full)
    if eve_total > 0:
        avg["weekend_share"] = eve_weekend / eve_total
        avg["payday_week_share"] = eve_payday / eve_total
    avg["small_spend"] = small_sum / k
    avg["small_count"] = small_cnt / k
    avg["big_count_year"] = big_cnt * 12.0 / k
    avg["overdraft_month_share"] = len(overdraft) / k
    reg = avg.get("regular", 0.0)
    if reg > 0 and last_balance is not None:
        avg["buffer_months"] = last_balance / reg
    avg["invests"] = 1.0 if invests else 0.0
    out_flow = spent + avg.get("savings", 0.0)
    demo = (len(sal_months) >= 22 and len(house_months) >= 20 and not sweep
            and purchases / k >= 25 and n_tx >= 600 and inc > 0
            and 0.7 * inc <= out_flow <= 1.3 * inc)
    return {"metrics": avg, "months": k, "last": dict(months[complete[-1]]), "demo": demo}


# --------------------------------------------------------------------------- metric catalogue

_NOUN = {"Taxi": "Taxi rides", "Restaurant": "Restaurant visits", "Fast food": "Fast food orders",
         "Bar": "Bar visits", "Cinema": "Cinema visits", "Groceries": "Grocery shops",
         "Public transport": "Public transport trips", "Fuel": "Fuel stops",
         "Flights": "Flight bookings", "Hotels": "Hotel stays", "Pharmacy": "Pharmacy visits"}

_FIXED = {
    "income": ("Income per month", "eur_per_month",
               "Average monthly money in (salary and other income) over complete months."),
    "regular": ("Regular essentials per month", "eur_per_month",
                "Average monthly spending in the regular basket: housing, utilities, groceries, public transport, fuel and pharmacy."),
    "unexpected": ("Unexpected necessities per month", "eur_per_month",
                   "Average monthly spending in the unexpected basket: large health, home and tech purchases."),
    "everyday": ("Everyday spending per month", "eur_per_month",
                 "Average monthly spending in the everyday basket: everything that is neither regular nor unexpected."),
    "savings": ("Investment deposits per month", "eur_per_month",
                "Average monthly amount moved into investments over complete months."),
    "savings_rate": ("Savings rate", "share",
                     "Income minus spending, divided by income, from monthly averages; customers with no income are skipped."),
    "night_out": ("Night-out spending per month", "eur_per_month",
                  "Average monthly spending on purchases that belong to a night out (a session anchored on a bar purchase)."),
    "night_out_count": ("Nights out per month", "count_per_month",
                        "Average number of nights out per month, where all night-out purchases of one evening window count as one night."),
    "night_out_cost": ("Cost of a night out", "eur",
                       "Average total spent on one night out; only customers with at least one night out count."),
    "night_out_items": ("Purchases per night out", "count",
                        "Average number of purchases in one night out; only customers with at least one night out count."),
    "weekend_share": ("Weekend share of everyday spending", "share",
                      "Share of everyday-basket spending made on Friday, Saturday or Sunday."),
    "payday_week_share": ("Payday-week share of everyday spending", "share",
                          "Share of everyday-basket spending made within 7 days after a salary payment."),
    "small_spend": ("Small purchases total per month", "eur_per_month",
                    "Average monthly sum of purchases under 10 EUR."),
    "small_count": ("Small purchases per month", "count_per_month",
                    "Average number of purchases under 10 EUR per month."),
    "big_count_year": ("Big purchases per year", "count_per_year",
                       "Number of purchases of 500 EUR or more, scaled to 12 months."),
    "spent": ("Total spending per month", "eur_per_month",
              "Average monthly spending across the regular, unexpected and everyday baskets."),
    "surplus": ("Surplus per month", "eur_per_month",
                "Average monthly income minus spending minus investment deposits."),
    "overdraft_month_share": ("Months with a negative balance", "share",
                              "Share of complete months in which the balance went below zero at least once."),
    "buffer_months": ("Buffer in months", "months",
                      "Latest balance divided by average monthly regular-basket spending; customers with no regular spending are skipped."),
    "invests": ("Share who invest", "share",
                "1 if the customer made any investment deposit in the complete months, else 0."),
    "housing_share": ("Housing share of income", "share",
                      "Average monthly housing spending divided by average monthly income; customers with no income are skipped."),
    "everyday_share": ("Everyday share of income", "share",
                       "Average monthly everyday-basket spending divided by average monthly income; customers with no income are skipped."),
}
_GROUP_NAMES = {"dining_out": "Dining out", "going_out": "Going out", "transport": "Transport",
                "health": "Health", "home": "Home and tech", "shopping": "Shopping",
                "travel": "Travel", "food_total": "Food in total"}


def metric_info(metric: str):
    """(name, unit, description) for a bench metric key, or None if unknown."""
    if metric in _FIXED:
        return _FIXED[metric]
    fam, _, rest = metric.partition(":")
    if fam == "label":
        return (f"{rest} spending per month", "eur_per_month",
                f"Average monthly amount spent on {rest} purchases over complete months.")
    if fam == "visits":
        return (f"{_NOUN.get(rest, rest + ' purchases')} per month", "count_per_month",
                f"Average number of {rest} purchases per month over complete months.")
    if fam == "ticket":
        return (f"Average {rest} purchase", "eur",
                f"The customer's average amount of one {rest} purchase; only customers with at least one count.")
    if fam == "users":
        return (f"Share who use {rest}", "share",
                f"1 if the customer made at least one {rest} purchase in the complete months, else 0, so the mean is the share of customers.")
    if fam == "group" and rest in GROUPS:
        return (f"{_GROUP_NAMES[rest]} spending per month", "eur_per_month",
                f"Average monthly spending on {', '.join(GROUPS[rest])} combined.")
    return None


def _meta_rows(bench_rows):
    out = []
    for metric in sorted({r[1] for r in bench_rows}):
        info = metric_info(metric) or (metric, "count", f"Group statistic {metric}.")
        out.append((metric,) + tuple(info))
    return out


# --------------------------------------------------------------------------- per-customer pass

def _process_customer(cid, rows, today):
    """rows: list of [d, ts, amount, balance, type, category, mcc, merchant]. Returns
    (db_tuples, stats). Adds label, basket, context."""
    rows.sort(key=lambda r: r[1])
    n = len(rows)
    labels = [None] * n
    baskets = [None] * n
    for i, r in enumerate(rows):
        lab, bas = classify.classify(r[4], r[5], r[6], r[2])
        labels[i] = lab
        baskets[i] = bas
    purchase_idx = [i for i, r in enumerate(rows) if r[4] == "purchase"]
    flags = classify.night_out_flags([rows[i][1] for i in purchase_idx],
                                     [labels[i] for i in purchase_idx])
    context = [""] * n
    for i, fl in zip(purchase_idx, flags):
        if fl:
            context[i] = "night_out"

    negative = 0
    min_balance = None
    for r in rows:
        bal = r[3]
        if bal < 0:
            negative += 1
        if min_balance is None or bal < min_balance:
            min_balance = bal
    out = [(cid, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], labels[i], baskets[i], context[i])
           for i, r in enumerate(rows)]
    res = compute_metrics([(r[0], r[1], r[2], r[3], r[4], labels[i], baskets[i], context[i])
                           for i, r in enumerate(rows)], today)
    stats = {"avg": res["metrics"], "months": res["months"], "neg_frac": negative / n if n else 0.0,
             "min_balance": min_balance if min_balance is not None else 0.0,
             "last": res["last"], "demo": res["demo"]}
    return out, stats


# --------------------------------------------------------------------------- benchmarks

def _quantiles(vals):
    vals = sorted(vals)
    if len(vals) >= 2:
        q = statistics.quantiles(vals, n=4, method="inclusive")
        return q[0], q[1], q[2]
    return vals[0], vals[0], vals[0]


def _build_bench(cstats: dict, customers: dict):
    groups = defaultdict(list)       # group_key -> [avg dict]
    for cid, st in cstats.items():
        if not st["avg"]:
            continue
        postal, age = customers.get(cid, ("", None))
        band = age_band(age)
        if not band:
            continue
        area = postal[:2]
        groups["all"].append(st["avg"])
        groups["age:" + band].append(st["avg"])
        if area:
            groups[f"age:{band}|area:{area}"].append(st["avg"])
    rows = []
    for key, avgs in groups.items():
        if len(avgs) < MIN_GROUP:
            continue
        metrics = set()
        for a in avgs:
            metrics.update(a.keys())
        for metric in sorted(metrics):
            if is_zero_fill(metric):
                vals = [a.get(metric, 0.0) for a in avgs]
            else:
                vals = [a[metric] for a in avgs if metric in a]
            if len(vals) < MIN_GROUP:
                continue
            p25, med, p75 = _quantiles(vals)
            rows.append((key, metric, len(vals), round(p25, 4), round(med, 4), round(p75, 4),
                         round(sum(vals) / len(vals), 4)))
    return rows


# --------------------------------------------------------------------------- personas

_NAMES = ["Veeti", "Aino", "Mikko", "Joonas", "Helmi", "Pentti"]


def _pick_personas(cstats: dict, customers: dict, mortgage: dict):
    """Choose 6 real customers by rule. Returns list of (cid, name, blurb)."""
    info = {}
    for cid, st in cstats.items():
        a = st["avg"]
        age = customers.get(cid, ("", None))[1]
        if not a or age is None or st["months"] < 3 or not st.get("demo"):
            continue
        spent = a.get("spent", 0.0)
        eat = a.get("label:Restaurant", 0.0) + a.get("label:Fast food", 0.0) + a.get("label:Bar", 0.0)
        info[cid] = {"age": age, "income": a.get("income", 0.0), "spent": spent,
                     "eat_share": eat / spent if spent > 0 else 0.0,
                     "save": a.get("savings", 0.0) / a["income"] if a.get("income", 0) > 0 else 0.0,
                     "neg": st["neg_frac"], "minbal": st["min_balance"], "months": st["months"]}
    if not info:    # tiny test builds may have no pool member: fall back to everyone
        for cid, st in cstats.items():
            a = st["avg"]
            age = customers.get(cid, ("", None))[1]
            if not a or age is None or st["months"] < 3:
                continue
            spent = a.get("spent", 0.0)
            eat = a.get("label:Restaurant", 0.0) + a.get("label:Fast food", 0.0) + a.get("label:Bar", 0.0)
            info[cid] = {"age": age, "income": a.get("income", 0.0), "spent": spent,
                         "eat_share": eat / spent if spent > 0 else 0.0,
                         "save": a.get("savings", 0.0) / a["income"] if a.get("income", 0) > 0 else 0.0,
                         "neg": st["neg_frac"], "minbal": st["min_balance"], "months": st["months"]}
    used = set()
    chosen = []

    def pick(cands, key, reverse=True):
        cands = [c for c in cands if c not in used]
        if not cands:
            return None
        cands.sort(key=lambda c: (key(c), c), reverse=reverse)
        used.add(cands[0])
        return cands[0]

    def median_income(cs):
        v = sorted(info[c]["income"] for c in cs)
        return v[len(v) // 2] if v else 0.0

    def fallback():
        return pick(list(info), lambda c: info[c]["months"])

    young = [c for c in info if 18 <= info[c]["age"] <= 24]
    # The first persona drives the demo, so prefer someone whose last full month has a taxi ride,
    # a night out and a positive surplus: the demo questions then have something to show.
    def demo_ready(c):
        last = cstats[c]["last"]
        spent = last.get("regular", 0.0) + last.get("unexpected", 0.0) + last.get("everyday", 0.0)
        return (last.get("label:Taxi", 0.0) > 0 and last.get("night_out", 0.0) > 0
                and last.get("income", 0.0) - spent - last.get("savings", 0.0) > 50)
    c = pick([c for c in young if demo_ready(c)], lambda c: info[c]["eat_share"])         or pick(young, lambda c: info[c]["eat_share"]) or fallback()
    chosen.append((c, "Eats out and goes out a lot; a young adult starting to live on their own."))
    saver = [c for c in info if 25 <= info[c]["age"] <= 34 and info[c]["income"] > 0]
    c = pick(saver, lambda c: info[c]["save"]) or fallback()
    chosen.append((c, "Sets money aside every month and wants to know how fast the goals can be reached."))
    earner = [c for c in info if 35 <= info[c]["age"] <= 54]
    c = pick(earner, lambda c: info[c]["income"]) or fallback()
    chosen.append((c, "Family-age high earner with a large, steady income and bigger bills."))
    c = pick(list(info), lambda c: (info[c]["neg"], -info[c]["minbal"])) or fallback()
    chosen.append((c, "Often runs close to or below zero before payday; safe-to-spend matters here."))
    applicants = [c for c in info if mortgage.get(c) == "approved"] or \
                 [c for c in info if c in mortgage]
    target = median_income(applicants)
    c = pick(applicants, lambda c: -abs(info[c]["income"] - target)) or fallback()
    chosen.append((c, "Thinking about buying a first home; applied for a mortgage."))
    seniors = [c for c in info if info[c]["age"] >= 65]
    target = median_income(seniors)
    c = pick(seniors, lambda c: -abs(info[c]["income"] - target)) or fallback()
    chosen.append((c, "Retired or close to it, with steady, careful spending."))
    out = []
    for (cid, blurb), first in zip(chosen, _NAMES):
        if cid is None:
            continue
        out.append((cid, f"{first}, {info[cid]['age']}", blurb))
    return out


# --------------------------------------------------------------------------- build

def build(data_dir: str, out_path: str, limit_customers: int | None = None) -> dict:
    t0 = time.time()
    today = _today()
    data_dir = str(data_dir)
    out_path = str(out_path)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp_path = out_path + ".tmp"
    for p in (tmp_path, tmp_path + "-journal"):
        if os.path.exists(p):
            os.remove(p)

    print(f"[ingest] reading customers from {data_dir}", flush=True)
    customers = _read_customers(data_dir)
    mortgage = _read_mortgage(data_dir)

    conn = sqlite3.connect(tmp_path)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.executescript(SCHEMA)
    insert_sql = "INSERT INTO tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"

    cstats = {}
    total_rows = 0
    batch = []
    seen = set()

    def flush_customer(cid, rows):
        nonlocal total_rows, batch
        if cid in seen:
            print(f"[ingest] warning: rows of {cid} are not contiguous in the CSV", flush=True)
        seen.add(cid)
        out, stats = _process_customer(cid, rows, today)
        cstats[cid] = stats
        batch.extend(out)
        total_rows += len(out)
        if len(batch) >= BATCH:
            conn.executemany(insert_sql, batch)
            batch = []

    tx_path = os.path.join(data_dir, TX_FILE)
    print(f"[ingest] streaming {tx_path}", flush=True)
    cur_cid, cur_rows, read = None, [], 0
    next_report = 500_000
    done_early = False
    with _open_csv(tx_path) as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            cid = row[0]
            if cid != cur_cid:
                if cur_cid is not None:
                    flush_customer(cur_cid, cur_rows)
                    if limit_customers is not None and len(seen) >= limit_customers:
                        cur_rows, cur_cid, done_early = [], None, True
                        break
                cur_cid, cur_rows = cid, []
            try:
                amount = float(row[5])
                balance = float(row[6]) if row[6] != "" else 0.0
            except ValueError:
                continue
            cur_rows.append([row[2], convert_ts(row[3], row[2]), amount, balance, row[7],
                             row[4], row[9], row[8]])
            read += 1
            if read >= next_report:
                print(f"[ingest]   {read:,} rows read, {len(seen):,} customers, "
                      f"{time.time() - t0:.0f}s", flush=True)
                next_report += 500_000
        if cur_cid is not None and not done_early:
            flush_customer(cur_cid, cur_rows)
    if batch:
        conn.executemany(insert_sql, batch)
        batch = []
    print(f"[ingest] {total_rows:,} rows loaded, indexing...", flush=True)
    conn.execute("CREATE INDEX tx_cid_d ON tx(cid, d)")

    cust_rows = []
    for cid in sorted(cstats):
        postal, age = customers.get(cid, ("", None))
        cust_rows.append((cid, postal, age, age_band(age), postal[:2]))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", cust_rows)

    print("[ingest] computing benchmarks and personas", flush=True)
    bench_rows = _build_bench(cstats, customers)
    conn.executemany("INSERT INTO bench VALUES (?,?,?,?,?,?,?)", bench_rows)
    conn.executemany("INSERT INTO bench_meta VALUES (?,?,?,?)", _meta_rows(bench_rows))
    pool = sorted(c for c, st in cstats.items() if st.get("demo"))
    conn.executemany("INSERT INTO demo_pool VALUES (?)", [(c,) for c in pool])
    print(f"[ingest] demo pool: {len(pool)} customers qualify", flush=True)
    personas = _pick_personas(cstats, customers, mortgage)
    conn.executemany("INSERT INTO personas VALUES (?,?,?)", personas)

    conn.executemany("INSERT INTO meta VALUES (?,?)", [
        ("today", today), ("built_at", datetime.now().isoformat(timespec="seconds")),
        ("rows", str(total_rows)), ("customers", str(len(cstats))),
        ("demo_pool", str(len(pool)))])
    conn.commit()
    conn.execute("ANALYZE")
    conn.commit()
    conn.close()
    os.replace(tmp_path, out_path)
    seconds = round(time.time() - t0, 1)
    print(f"[ingest] done: {len(cstats):,} customers, {total_rows:,} rows, "
          f"{len(bench_rows):,} bench rows, {len(personas)} personas, {seconds}s -> {out_path}",
          flush=True)
    return {"customers": len(cstats), "rows": total_rows, "seconds": seconds}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.ingest",
                                 description="Build the Svinkki database from the CSV folder.")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--customers", type=int, default=None, help="only the first N customers")
    args = ap.parse_args(argv)
    result = build(args.data_dir or _data_dir(), args.out or _default_out(), args.customers)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
