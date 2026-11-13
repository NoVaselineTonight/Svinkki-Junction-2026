"""Shared test fixture for the Svinkki test suite.

Everything here is invented by code (deterministic, seeded). No row is copied from the real
dataset (SR-31) and nothing here needs the network.

The module builds, once per test process:
  * CSV files in the exact input format of STATE.md section 5.7 (UTF-8 with BOM, timestamps such
    as 03OCT24:09:04:04) in a temp folder,
  * a database through app.ingest.build,
  * the environment variables SVINKKI_DB, SVINKKI_STATE_DB, SVINKKI_TODAY, SVINKKI_DATA_DIR, empty
    GEMINI_API_KEY and ANTHROPIC_API_KEY, and SVINKKI_ENV_FILE / SVINKKI_AI_KEY_FILE pointing at
    files that do not exist, so no real key can reach the tests.

It also gives the tests an independent "oracle": the generator knows, for every row it writes, the
label, basket and context the row should end up with, so expected numbers are computed here and
never by calling the code under test.

Test modules must call get() before importing anything from app.* so the environment is in place.
"""
import atexit
import csv
import datetime as _dt
import http.client
import http.cookiejar
import io
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TODAY = "2026-09-24"            # a Thursday; this week = 2026-09-21 .. 2026-09-24
FIRST_MONTH = (2024, 10)
LAST_MONTH = (2026, 9)          # data runs to the end of September, i.e. after TODAY

A_CID = "CUST00001"
B_CID = "CUST00002"
D_CID = "CUST00003"
A_NAME = "Testa, 31"
B_NAME = "Testb, 29"
D_NAME = "Testd, 22"
A_POSTAL = "00510"
A_AGE = 31

MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

ALL_CONSENT = {"analysis": True, "ai": True, "benchmarks": True, "suggestions": True}

# label -> (csv category, mcc, merchant id, expected basket, transaction type)
SPEC = {
    "Salary": ("Salary", "", "", "income", "salary"),
    "Housing": ("Housing", "", "", "regular", "housing_payment"),
    "Utilities": ("Utilities", "", "", "regular", "utilities_payment"),
    "Groceries": ("Groceries", "5411", "MX10011", "regular", "purchase"),
    "Restaurant": ("Restaurants", "5812", "MX20012", "everyday", "purchase"),
    "Fast food": ("Restaurants", "5814", "MX20014", "everyday", "purchase"),
    "Bar": ("Restaurants", "5813", "MX20013", "everyday", "purchase"),
    "Taxi": ("Transportation", "4121", "MX30121", "everyday", "purchase"),
    "Public transport": ("Transportation", "4111", "MX30111", "regular", "purchase"),
    "Fuel": ("Transportation", "5541", "MX30541", "regular", "purchase"),
    "Pharmacy": ("Health", "5912", "MX40912", "regular", "purchase"),
    "Doctor": ("Health", "8011", "MX48011", "unexpected", "purchase"),
    "Electronics": ("Home & Tech", "5732", "MX50732", "unexpected", "purchase"),
    "Clothing": ("Lifestyle", "5651", "MX60651", "everyday", "purchase"),
    "Savings & investments": ("Invest Deposit", "", "", "savings", "investment_deposit"),
}
MCC_TO_LABEL = {v[1]: k for k, v in SPEC.items() if v[1]}


# ---------------------------------------------------------------------------------------------
# The invented population
# ---------------------------------------------------------------------------------------------

def band_of(age):
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"
    if age <= 54:
        return "45-54"
    if age <= 64:
        return "55-64"
    return "65+"


def _population():
    people = []

    def add(postal, age, kind="gen"):
        people.append({"postal": postal, "age": age, "kind": kind})

    add(A_POSTAL, A_AGE, "A")            # CUST00001
    add("00520", 29, "B")                # CUST00002
    add("00130", 22, "D")                # CUST00003, often below zero
    for i in range(20):                  # 25-34: 22 in all with A and B
        postal = "00%03d" % (550 + i) if i < 2 else "20%03d" % (100 + i)
        add(postal, 25 + (i % 10))
    for i in range(20):                  # 35-44: exactly 20, all in area 33
        add("33%03d" % (100 + i), 35 + (i % 10))
    for i, age in enumerate((45, 50, 54)):
        add("40%03d" % (100 + i), age)
    add("90100", 19)
    add("90101", 24)
    add("50100", 55)
    add("50101", 64)
    add("70100", 67)
    add("70101", 80)
    out = []
    for n, p in enumerate(people, start=1):
        cid = "CUST%05d" % n
        out.append({"cid": cid, "n": n, "postal": p["postal"], "age": p["age"], "kind": p["kind"],
                    "band": band_of(p["age"]), "area": p["postal"][:2]})
    return out


CUSTOMERS = _population()
CUSTOMER_COUNT = len(CUSTOMERS)           # 52
BY_CID = {c["cid"]: c for c in CUSTOMERS}


def group_cids(key):
    """Customers in a bench group key: all, age:<band>, age:<band>|area:<area>."""
    if key == "all":
        return [c["cid"] for c in CUSTOMERS]
    parts = key.split("|")
    band = parts[0].split(":", 1)[1]
    area = parts[1].split(":", 1)[1] if len(parts) > 1 else None
    return [c["cid"] for c in CUSTOMERS if c["band"] == band and (area is None or c["area"] == area)]


# ---------------------------------------------------------------------------------------------
# Row generation (amounts in cents)
# ---------------------------------------------------------------------------------------------

def _months():
    y, m = FIRST_MONTH
    while (y, m) <= LAST_MONTH:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


MONTHS = list(_months())


def _weekday_in(y, m, weekday, lo, hi):
    for d in range(lo, hi + 1):
        if _dt.date(y, m, d).weekday() == weekday:
            return d
    raise AssertionError("no such weekday")


def friday_of_month(y, m):
    return _weekday_in(y, m, 4, 16, 22)


def wednesday_of_month(y, m):
    return _weekday_in(y, m, 2, 6, 12)


def _params(c):
    kind, n = c["kind"], c["n"]
    base = dict(payday=15, housing_day=2, gdays=(4, 11, 18, 25), nomcc=None, lunch=None, dinner=None,
                ffood=None, night=None, taxi_w=None, taxi_eve=None, pharm=None, transit=None,
                fuel=None, clothing=None, invest=0, start=300000, salary_sec=0, extras=[],
                late_snack=None, doctor_every=0)
    if kind == "A":
        base.update(
            salary=300000, salary_sec=4, housing=90000, utils=(4000, 5550, 3000),
            groceries=lambda idx: [6240 + 110 * (idx % 3), 4810, 7525, 5430], nomcc=1000,
            lunch=1600, dinner=3200, ffood=990, night=(2400, 1150, 2800), taxi_w=1420,
            taxi_eve=1990, pharm=(1840, 2260), transit=310, fuel=4500, clothing=4990,
            invest=20000, start=250000,
            extras=[(_dt.datetime(2026, 6, 20, 14, 0, 0), "Electronics", 60000),
                    (_dt.datetime(2026, 9, 30, 10, 0, 0), "Taxi", 7777)])
    elif kind == "B":
        base.update(
            salary=260000, housing=70000, utils=(3000, 4500, 2500),
            groceries=lambda idx: [5000, 5000, 5000, 5000], dinner=2500, taxi_w=1200,
            late_snack=(1100, 1500), start=100000)
    elif kind == "D":
        base.update(
            salary=150000, payday=25, housing=90000, housing_day=3, utils=(4000, 5000, 3000),
            groceries=lambda idx: [7500, 7500, 7500, 7500], gdays=(4, 11, 18, 22),
            lunch=4000, dinner=6000, ffood=1500, taxi_w=2000, pharm=(2500, None),
            clothing=6000, fuel=6000, start=10000)
    else:
        rng = random.Random(5000 + n)
        salary = rng.randrange(20, 52) * 10000
        housing = int(salary * 0.28 / 1000) * 1000
        utils = tuple(rng.randrange(25, 60) * 100 for _ in range(3))
        base.update(
            salary=salary, housing=housing, utils=utils,
            groceries=(lambda idx, n=n: [random.Random(n * 100 + idx * 4 + k).randrange(3000, 9000)
                                         for k in range(4)]),
            lunch=rng.choice([None, 1400, 1800]), dinner=rng.choice([2200, 3000, 4200]),
            ffood=rng.choice([None, 900]), taxi_w=rng.choice([None, 1300, 2100]),
            night=(2200, 1100, 2600) if rng.random() < 0.5 else None,
            pharm=(rng.randrange(8, 30) * 100, None), transit=rng.choice([None, 280]),
            invest=rng.choice([0, 10000, 20000]), start=rng.randrange(10, 80) * 10000,
            doctor_every=rng.choice([0, 0, 6]))
    return base


def _generate(c):
    p = _params(c)
    cid = c["cid"]
    rows = []
    seq = [0]

    def add(when, label, cents, merchant=None, mcc=None, context="", category=None):
        spec = SPEC[label]
        seq[0] += 1
        signed = cents if label == "Salary" else -cents
        rows.append({
            "cid": cid, "dt": when, "seq": seq[0], "cents": signed,
            "d": when.strftime("%Y-%m-%d"), "ts": when.strftime("%Y-%m-%d %H:%M:%S"),
            "type": spec[4], "category": spec[0] if category is None else category,
            "mcc": spec[1] if mcc is None else mcc,
            "merchant": spec[2] if merchant is None else merchant,
            "label": label, "basket": spec[3], "context": context,
        })

    for idx, (y, m) in enumerate(MONTHS):
        def at(day, hh, mi, sec=0):
            return _dt.datetime(y, m, day, hh, mi, sec)

        add(at(p["payday"], 8, 0, p["salary_sec"]), "Salary", p["salary"])
        add(at(p["housing_day"], 6, 0), "Housing", p["housing"])
        for day, amt in zip((5, 12, 20), p["utils"]):
            add(at(day, 7, 0), "Utilities", amt)
        for day, amt in zip(p["gdays"], p["groceries"](idx)):
            add(at(day, 17, 30), "Groceries", amt)
        if p["nomcc"]:
            add(at(8, 10, 0), "Groceries", p["nomcc"], merchant="", mcc="")
        if p["lunch"]:
            add(at(wednesday_of_month(y, m), 12, 30), "Restaurant", p["lunch"])
        if p["dinner"]:
            add(at(10, 19, 30), "Restaurant", p["dinner"])
        if p["ffood"]:
            add(at(14, 13, 0), "Fast food", p["ffood"])
        if p["taxi_w"]:
            add(at(wednesday_of_month(y, m), 8, 10), "Taxi", p["taxi_w"])
        if p["taxi_eve"]:
            add(at(24, 17, 0), "Taxi", p["taxi_eve"])
        if p["night"]:
            bar, kebab, taxi = p["night"]
            f = at(friday_of_month(y, m), 21, 30)
            nxt = f + _dt.timedelta(days=1)
            add(f, "Bar", bar, context="night_out")
            add(nxt.replace(hour=1, minute=10), "Fast food", kebab, context="night_out")
            add(nxt.replace(hour=1, minute=40), "Taxi", taxi, context="night_out")
        if p["late_snack"]:        # same small hours, but no bar anywhere: NOT a night out
            kebab, taxi = p["late_snack"]
            add(at(20, 1, 10), "Fast food", kebab)
            add(at(20, 1, 40), "Taxi", taxi)
        if p["pharm"]:
            add(at(13, 15, 0), "Pharmacy", p["pharm"][0])
            if p["pharm"][1]:
                add(at(28, 10, 0), "Pharmacy", p["pharm"][1])
        if p["transit"]:
            add(at(3, 8, 0), "Public transport", p["transit"])
        if p["fuel"]:
            add(at(13, 18, 30), "Fuel", p["fuel"])
        if p["clothing"]:
            add(at(23, 15, 0), "Clothing", p["clothing"])
        if p["invest"]:
            add(at(16, 9, 0), "Savings & investments", p["invest"])
        if p["doctor_every"] and idx % p["doctor_every"] == 3:
            add(at(21, 11, 0), "Doctor", 18000)
    for when, label, cents in p["extras"]:
        add(when, label, cents)

    rows.sort(key=lambda r: (r["dt"], r["seq"]))
    bal = p["start"]
    for r in rows:
        bal += r["cents"]
        r["balance_cents"] = bal
    for r in rows:
        r["amount"] = r["cents"] / 100.0
        r["balance"] = r["balance_cents"] / 100.0
    return rows, p


_ROWS = {}
_PARAMS = {}
for _c in CUSTOMERS:
    _ROWS[_c["cid"]], _PARAMS[_c["cid"]] = _generate(_c)
TOTAL_ROWS = sum(len(v) for v in _ROWS.values())


def rows_for(cid):
    return _ROWS[cid]


def salary_of(cid):
    return _PARAMS[cid]["salary"] / 100.0


# ---------------------------------------------------------------------------------------------
# The oracle: expected values computed from the generator only
# ---------------------------------------------------------------------------------------------

def month_bounds(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    first = _dt.date(y, m, 1)
    nxt = _dt.date(y + (m == 12), m % 12 + 1, 1)
    return first.isoformat(), (nxt - _dt.timedelta(days=1)).isoformat()


def week_bounds(today, weeks_back=0):
    d = _dt.date.fromisoformat(today)
    monday = d - _dt.timedelta(days=d.weekday()) - _dt.timedelta(days=7 * weeks_back)
    if weeks_back == 0:
        return monday.isoformat(), d.isoformat()
    return monday.isoformat(), (monday + _dt.timedelta(days=6)).isoformat()


def spend(cid, frm, to, labels=None, basket=None, context=None, baskets=None):
    """Positive spending: sum of -amount over outflow rows that match. Rows after TODAY excluded."""
    if isinstance(labels, str):
        labels = [labels]
    cents = 0
    n = 0
    for r in _ROWS[cid]:
        if r["cents"] >= 0 or r["d"] > TODAY or not (frm <= r["d"] <= to):
            continue
        if labels is not None and r["label"] not in labels:
            continue
        if basket is not None and r["basket"] != basket:
            continue
        if baskets is not None and r["basket"] not in baskets:
            continue
        if context is not None and r["context"] != context:
            continue
        cents -= r["cents"]
        n += 1
    return round(cents / 100.0, 2), n


def income(cid, frm, to):
    cents = sum(r["cents"] for r in _ROWS[cid]
                if r["cents"] > 0 and r["d"] <= TODAY and frm <= r["d"] <= to)
    return round(cents / 100.0, 2)


def balance_at(cid, today=TODAY):
    last = [r for r in _ROWS[cid] if r["d"] <= today][-1]
    return last["balance"]


def month_list(cid):
    """(ym, income, spent_excl_savings, savings) for every month that has visible rows."""
    out = []
    for y, m in MONTHS:
        ym = "%04d-%02d" % (y, m)
        frm, to = month_bounds(ym)
        sp, _ = spend(cid, frm, to, baskets=("regular", "unexpected", "everyday"))
        sv, _ = spend(cid, frm, to, basket="savings")
        out.append((ym, income(cid, frm, to), sp, sv))
    return out


# ---------------------------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------------------------

def _fmt_ts(d):
    return "%02d%s%02d:%02d:%02d:%02d" % (d.day, MON[d.month - 1], d.year % 100, d.hour, d.minute, d.second)


def write_csvs(directory, interleaved=False):
    """interleaved=False: rows grouped by customer and sorted by time (the usual export shape).
    interleaved=True: all customers mixed together in time order (a stress variant)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tx_path = directory / "tx_junction_transactions.csv"
    cu_path = directory / "tx_customers_junction.csv"
    everything = [r for rows in _ROWS.values() for r in rows]
    if interleaved:
        everything.sort(key=lambda r: (r["dt"], r["cid"], r["seq"]))
    else:
        everything.sort(key=lambda r: (r["cid"], r["dt"], r["seq"]))
    with open(tx_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "bank_account_id", "tx_date", "tx_timestamp", "category",
                    "tx_amount_eur", "balance_after_eur", "transaction_type", "merchant_id", "mcc_code"])
        for r in everything:
            w.writerow([r["cid"], "ACC%05d" % BY_CID[r["cid"]]["n"], r["d"], _fmt_ts(r["dt"]),
                        r["category"], "%.2f" % r["amount"], "%.2f" % r["balance"], r["type"],
                        r["merchant"], r["mcc"]])
    with open(cu_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "customer_postal_code", "customer_age"])
        for c in CUSTOMERS:
            w.writerow([c["cid"], c["postal"], c["age"]])
    return tx_path, cu_path


# ---------------------------------------------------------------------------------------------
# Environment and database
# ---------------------------------------------------------------------------------------------

_env = None
_err = None


def _build():
    tmp = Path(tempfile.mkdtemp(prefix="svinkki_test_"))
    csv_dir = tmp / "csv"
    write_csvs(csv_dir)
    db_path = tmp / "svinkki.db"
    state_path = tmp / "state.db"
    os.environ["SVINKKI_DATA_DIR"] = str(csv_dir)
    os.environ["SVINKKI_DB"] = str(db_path)
    os.environ["SVINKKI_STATE_DB"] = str(state_path)
    os.environ["SVINKKI_TODAY"] = TODAY
    os.environ["GEMINI_API_KEY"] = ""
    # The suite must never reach a real AI service with a real key: no .env, no key file, no key
    # in the environment. Tests that exercise a model set a fake key and a fake HTTP layer.
    os.environ["SVINKKI_ENV_FILE"] = str(tmp / "no.env")
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["CLAUDE_MODEL"] = ""
    os.environ["SVINKKI_AI_KEY_FILE"] = str(tmp / "no_such_key.txt")
    os.environ["SVINKKI_AI_SETTINGS_FILE"] = str(tmp / "ai_settings.json")
    import app.ingest as ingest
    result = ingest.build(str(csv_dir), str(db_path))
    con = sqlite3.connect(str(db_path))
    try:
        ingest_personas = [dict(zip(("cid", "name", "blurb"), r))
                           for r in con.execute("SELECT cid, name, blurb FROM personas")]
        # The picker must offer the customers whose history the tests know exactly.
        for cid, name in ((A_CID, A_NAME), (B_CID, B_NAME), (D_CID, D_NAME)):
            con.execute("INSERT OR REPLACE INTO personas(cid, name, blurb) VALUES (?,?,?)",
                        (cid, name, "Invented fixture customer"))
        con.commit()
    finally:
        con.close()
    env = SimpleNamespace(tmp=tmp, csv_dir=csv_dir, db_path=db_path, state_path=state_path,
                          build_result=result, ingest_personas=ingest_personas)
    atexit.register(lambda: shutil.rmtree(str(tmp), ignore_errors=True))
    return env


def get():
    """Build (once) and return the environment. Re-raises the first failure for every caller."""
    global _env, _err
    if _err is not None:
        raise _err
    if _env is None:
        try:
            _env = _build()
        except BaseException as exc:      # noqa: BLE001 - cached so each test class fails cleanly
            _err = exc
            raise
    return _env


def use_fresh_state():
    """Point the writable state store at a new empty file (consent and settings start empty)."""
    env = get()
    path = env.tmp / ("state_%d.db" % random.randrange(10 ** 9))
    os.environ["SVINKKI_STATE_DB"] = str(path)
    return path


def open_db():
    return sqlite3.connect(str(get().db_path))


def sandbox(cid=A_CID, today=TODAY):
    get()
    import app.db as db
    return db.sandbox(cid, today)


def make_ctx(cid=A_CID, consent=None, conn=None, today=TODAY):
    get()
    import app.db as db
    return SimpleNamespace(
        conn=conn if conn is not None else db.sandbox(cid, today), today=today,
        profile=db.profile(cid), consent=dict(consent or ALL_CONSENT),
        settings={"checkin_frequency": "monthly", "suggestion_level": "few", "quiz": "weekly",
                  "monthly_saving_target": 0})


def closed_conn():
    c = sqlite3.connect(":memory:")
    c.close()
    return c


# ---------------------------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------------------------

_INVALID = object()


class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body
        self._json = None

    @property
    def text(self):
        return self.body.decode("utf-8", "replace")

    @property
    def valid_json(self):
        return self._parse() is not _INVALID

    @property
    def json(self):
        v = self._parse()
        if v is _INVALID:
            raise AssertionError("response is not JSON (status %s): %r" % (self.status, self.text[:200]))
        return v

    def _parse(self):
        if self._json is None:
            try:
                self._json = json.loads(self.body.decode("utf-8"))
            except Exception:                      # noqa: BLE001
                self._json = _INVALID
        return self._json

    def header(self, name):
        return self.headers.get(name)

    def set_cookies(self):
        return self.headers.get_all("Set-Cookie") or []


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Client:
    """A tiny cookie-keeping HTTP client."""

    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect)

    def request(self, method, path, body=None, headers=None, raw=None, timeout=30):
        data = None
        hdrs = {}
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=hdrs)
        try:
            r = self.opener.open(req, timeout=timeout)
            return Resp(r.status, r.headers, r.read())
        except urllib.error.HTTPError as e:
            return Resp(e.code, e.headers, e.read())

    def get(self, path, headers=None):
        return self.request("GET", path, headers=headers)

    def post(self, path, body=None, headers=None, raw=None):
        return self.request("POST", path, body=body if raw is None else None, headers=headers, raw=raw)

    def sid(self):
        for c in self.jar:
            if c.name == "svinkki_sid":
                return c.value
        return None


def raw_get(base, path, headers=None, method="GET"):
    """A request whose path is sent exactly as given (no client-side normalisation)."""
    host, port = base.replace("http://", "").split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=15)
    try:
        conn.request(method, path, headers=headers or {})
        r = conn.getresponse()
        return Resp(r.status, r.msg, r.read())
    finally:
        conn.close()


class Server:
    def __init__(self):
        get()
        import app.server as server
        self.httpd = server.make_server(host="127.0.0.1", port=0)
        self.port = self.httpd.server_address[1]
        self.base = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:                          # noqa: BLE001
            pass

    def client(self):
        return Client(self.base)


def personas(client):
    r = client.get("/api/demo/personas")
    assert r.status == 200, "personas endpoint returned %s" % r.status
    return r.json


def login(client, persona_index=0):
    ps = personas(client)
    r = client.post("/api/demo/login", {"id": ps[persona_index]["id"]})
    assert r.status == 200, "login failed: %s %s" % (r.status, r.text[:200])
    return ps[persona_index]


def login_as(client, name):
    ps = personas(client)
    for p in ps:
        if p["name"] == name:
            r = client.post("/api/demo/login", {"id": p["id"]})
            assert r.status == 200, "login failed: %s %s" % (r.status, r.text[:200])
            return p
    raise AssertionError("persona %r not offered by /api/demo/personas (got %r)" % (name, [p["name"] for p in ps]))


def consent_all(client, **overrides):
    body = dict(ALL_CONSENT)
    body.update(overrides)
    r = client.post("/api/consent", body)
    assert r.status == 200, "consent failed: %s %s" % (r.status, r.text[:200])
    return r.json


def session(server, who="A", consent=True, **consent_overrides):
    c = server.client()
    login_as(c, {"A": A_NAME, "B": B_NAME, "D": D_NAME}[who])
    if consent:
        consent_all(c, **consent_overrides)
    return c


# ---------------------------------------------------------------------------------------------
# Fake Gemini (the REST generateContent endpoint), injected at the urllib layer
# ---------------------------------------------------------------------------------------------

class _FakeHTTPResponse(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}

    def getcode(self):
        return 200

    def info(self):
        return self.headers


def gem_call(name, args=None):
    return {"candidates": [{"content": {"role": "model", "parts": [
        {"functionCall": {"name": name, "args": args or {}}}]}, "finishReason": "STOP"}]}


def gem_text(text):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}]}


class FakeGemini:
    """Stands in for urllib.request.urlopen. The last scripted item repeats forever."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.urls = []
        self.raw = []
        self.requests = []

    def __call__(self, req, *args, **kwargs):
        self.calls += 1
        url = getattr(req, "full_url", str(req))
        data = getattr(req, "data", None)
        self.urls.append(url)
        self.raw.append(data or b"")
        try:
            self.requests.append(json.loads(data.decode("utf-8")) if data else None)
        except Exception:                          # noqa: BLE001
            self.requests.append(None)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return _FakeHTTPResponse(json.dumps(item).encode("utf-8"))

    def all_text(self):
        return "\n".join(r.decode("utf-8", "replace") for r in self.raw)


class patched_gemini:
    """Context manager: set a (fake) key and route all urllib.request.urlopen calls to the fake."""

    def __init__(self, fake, key="test-key-not-real"):
        self.fake = fake
        self.key = key
        self._patches = []
        self._old = None

    def __enter__(self):
        self._old = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = self.key
        p = mock.patch("urllib.request.urlopen", self.fake)
        p.start()
        self._patches.append(p)
        try:
            import app.llm_gemini as lg
            if hasattr(lg, "urlopen"):
                p2 = mock.patch.object(lg, "urlopen", self.fake)
                p2.start()
                self._patches.append(p2)
        except ImportError:
            pass
        return self.fake

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()
        os.environ["GEMINI_API_KEY"] = self._old if self._old is not None else ""
        return False


# ---------------------------------------------------------------------------------------------
# Small assertion helpers shared by test modules
# ---------------------------------------------------------------------------------------------

import re as _re

_NUM = _re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text):
    out = []
    for m in _NUM.findall(text or ""):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def text_has_amount(text, value, abs_tol=0.005, rel_tol=0.0):
    for n in numbers_in(text):
        if abs(n - value) <= max(abs_tol, abs(value) * rel_tol):
            return True
    return False


def contains_number(obj, value, tol=0.005):
    """True if any number anywhere inside a JSON-like object equals value."""
    if isinstance(obj, bool):
        return False
    if isinstance(obj, (int, float)):
        return abs(obj - value) <= tol
    if isinstance(obj, dict):
        return any(contains_number(v, value, tol) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(contains_number(v, value, tol) for v in obj)
    return False


def pfrom(p):
    """Period as dict {from,to} or 2-sequence -> (from, to)."""
    if isinstance(p, dict):
        return p["from"], p["to"]
    return tuple(p)


def evidence_kwargs(ev):
    kw = {}
    if ev.get("from"):
        kw["frm"] = ev["from"]
    if ev.get("to"):
        kw["to"] = ev["to"]
    for k in ("label", "basket", "context", "type"):
        if ev.get(k):
            kw[k] = ev[k]
    return kw
