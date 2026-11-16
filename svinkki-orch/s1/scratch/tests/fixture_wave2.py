"""Extra invented rows for the wave 2 tests (W1 to W11). Built here, never copied from the dataset (SR-31).

`make_conn(rows)` builds an in-memory sandbox shaped like app.db.sandbox output (table `tx` with the
columns of STATE.md 5.1 minus cid, plus an integer `id`), so features can be tested against rows whose
every number is known. The oracle helpers below work from the row list only, never from app code.
"""
import datetime as _dt
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

TODAY = "2026-09-24"      # Thursday, same as tests/fixture.py

_COLS = ("d", "ts", "amount", "balance", "type", "category", "mcc", "merchant", "label", "basket", "context", "id")

# label -> (category, mcc, basket)
LABELS = {
    "Salary": ("Salary", "", "income"),
    "Housing": ("Housing", "", "regular"),
    "Utilities": ("Utilities", "", "regular"),
    "Groceries": ("Groceries", "5411", "regular"),
    "Restaurant": ("Restaurants", "5812", "everyday"),
    "Fast food": ("Restaurants", "5814", "everyday"),
    "Bar": ("Restaurants", "5813", "everyday"),
    "Taxi": ("Transportation", "4121", "everyday"),
    "Clothing": ("Lifestyle", "5651", "everyday"),
    "Hobbies": ("Lifestyle", "5941", "everyday"),
    "Books": ("Lifestyle", "5942", "everyday"),
    "Entertainment": ("Entertainment", "7999", "everyday"),
    "Other": ("Lifestyle", "", "everyday"),
    "Pharmacy": ("Health", "5912", "regular"),
    "Fuel": ("Transportation", "5541", "regular"),
    "Savings & investments": ("Invest Withdraw", "", "savings"),
}

_merchant_counter = [70000]


def fresh_merchant():
    _merchant_counter[0] += 1
    return "MX%d" % _merchant_counter[0]


def row(d, label, amount, merchant="", time="12:00:00", type="purchase", context="", balance=None, basket=None):
    """amount is signed (negative = money out)."""
    cat, mcc, bsk = LABELS[label]
    return {"d": d, "ts": "%s %s" % (d, time), "amount": float(amount), "type": type, "category": cat,
            "mcc": mcc if merchant else "", "merchant": merchant, "label": label,
            "basket": basket or bsk, "context": context, "balance": balance}


def months(first=(2025, 12), last=(2026, 9)):
    y, m = first
    while (y, m) <= last:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def ym(y, m):
    return "%04d-%02d" % (y, m)


def base_rows(salary=3000.0, housing=900.0, first=(2025, 12), last=(2026, 9), payday=15):
    """Salary on the 15th, rent on the 2nd, utilities on the 5th, four grocery shops of 60 (one merchant)."""
    out = []
    for y, m in months(first, last):
        d = lambda day: "%04d-%02d-%02d" % (y, m, day)      # noqa: E731
        out.append(row(d(payday), "Salary", salary, time="08:00:00", type="salary"))
        out.append(row(d(2), "Housing", -housing, time="06:00:00", type="housing_payment"))
        out.append(row(d(5), "Utilities", -100.0, time="07:00:00", type="utilities_payment"))
        for day in (4, 11, 18, 25):
            out.append(row(d(day), "Groceries", -60.0, merchant="MX10011", time="17:30:00"))
    return out


def leak_rows():
    """The 'S' customer: a flat 12.99 subscription, a subscription creeping 12.99 -> 14.99, small
    coffee purchases (3 a month, one merchant, so NOT repeating charges), a 10.00 purchase (not under
    10), a 60 % restaurant spike (300 -> 480) in August 2026 and a 10 % clothing rise in August 2026."""
    out = base_rows()
    for y, m in months():
        d = lambda day: "%04d-%02d-%02d" % (y, m, day)      # noqa: E731
        out.append(row(d(7), "Entertainment", -12.99, merchant="MX99001", time="09:00:00"))
        if (y, m) >= (2026, 2):
            amt = 12.99 if (y, m) <= (2026, 4) else 14.99
            out.append(row(d(9), "Entertainment", -amt, merchant="MX99002", time="09:30:00"))
        for day in (9, 19, 27):
            out.append(row(d(day), "Fast food", -4.50, merchant="MX70001", time="08:15:00"))
        out.append(row(d(12), "Other", -10.00, merchant=fresh_merchant(), time="13:00:00"))
        rest = 480.0 if (y, m) == (2026, 8) else 300.0
        clo = 110.0 if (y, m) == (2026, 8) else 100.0
        out.append(row(d(20), "Restaurant", -rest, merchant=fresh_merchant(), time="19:30:00"))
        out.append(row(d(23), "Clothing", -clo, merchant=fresh_merchant(), time="15:00:00"))
        out.append(row(d(21), "Hobbies", -50.0, merchant=fresh_merchant(), time="16:00:00"))
        out.append(row(d(22), "Books", -40.0, merchant=fresh_merchant(), time="16:30:00"))
        out.append(row(d(13), "Pharmacy", -30.0, merchant=fresh_merchant(), time="15:00:00"))
        out.append(row(d(14), "Fuel", -60.0, merchant=fresh_merchant(), time="18:00:00"))
    return out


def withdrawal(d, amount, balance_after=None, time="10:00:00"):
    return row(d, "Savings & investments", abs(amount), time=time, type="investment_withdrawal",
               balance=balance_after, basket="savings")


def make_conn(rows, today=TODAY, start_balance=5000.0):
    """In-memory sandbox. Rows after today are dropped, like app.db.sandbox does."""
    rows = [dict(r) for r in rows if r["d"] <= today]
    rows.sort(key=lambda r: r["ts"])
    bal = start_balance
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, "
                 "mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
    for i, r in enumerate(rows, start=1):
        if r.get("balance") is None:
            bal = round(bal + r["amount"], 2)
            r["balance"] = bal
        else:
            bal = r["balance"]
        r["id"] = i
        conn.execute("INSERT INTO tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(r[c] for c in _COLS))
    conn.commit()
    return conn


# ---------------------------------------------------------------------------------------------
# Oracle helpers over a row list
# ---------------------------------------------------------------------------------------------

def outflows(rows, frm, to, basket=None, label=None, today=TODAY):
    return [r for r in rows if r["amount"] < 0 and r["type"] == "purchase" and frm <= r["d"] <= to
            and r["d"] <= today and (basket is None or r["basket"] == basket)
            and (label is None or r["label"] == label)]


def month_total(rows, ymonth, label=None, basket=None):
    return round(-sum(r["amount"] for r in rows if r["amount"] < 0 and r["d"][:7] == ymonth
                      and (label is None or r["label"] == label)
                      and (basket is None or r["basket"] == basket)), 2)


def share_matches(value, expected_fraction, tol=0.005):
    """A share may be given as a fraction (0..1) or as a percentage (0..100)."""
    if value is None:
        return False
    return abs(value - expected_fraction) <= tol or abs(value - expected_fraction * 100) <= tol * 100


def days_between(a, b):
    return (_dt.date.fromisoformat(b) - _dt.date.fromisoformat(a)).days
