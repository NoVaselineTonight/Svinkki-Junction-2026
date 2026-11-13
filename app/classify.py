"""Transaction classification: MCC labels, baskets and night-out context.

This module is the single source of truth for how a transaction is labelled and which basket it
belongs to. It has no I/O and uses only the standard library.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

# --------------------------------------------------------------------------- labels

MCC_LABELS = {
    # groceries
    "5411": "Groceries", "5499": "Groceries", "5422": "Groceries", "5451": "Groceries",
    "5812": "Restaurant", "5814": "Fast food", "5813": "Bar",
    "4121": "Taxi", "4111": "Public transport",
    "5541": "Fuel", "5542": "Fuel", "7523": "Parking",
    "5912": "Pharmacy", "8011": "Doctor", "8021": "Dentist", "8099": "Other health",
    "5200": "Home improvement", "5251": "Home improvement",
    "5732": "Electronics", "5734": "Electronics", "5712": "Furniture",
    "5651": "Clothing", "5691": "Clothing",
    "5941": "Hobbies", "5945": "Hobbies", "5942": "Books", "5999": "Shopping",
    "7922": "Events", "7832": "Cinema",
    "7991": "Entertainment", "7996": "Entertainment", "7999": "Gym & sports",
    "4722": "Travel agency", "4511": "Flights", "7011": "Hotels", "7512": "Car rental",
}

# Used when a purchase has no MCC (about 5 % of purchases): label from the CSV category.
CATEGORY_FALLBACK = {
    "Groceries": "Groceries",
    "Restaurants": "Restaurant",
    "Transportation": "Other",
    "Utilities": "Utilities",
    "Entertainment": "Entertainment",
    "Health": "Other health",
    "Home & Tech": "Other",
    "Housing": "Housing",
    "Lifestyle": "Shopping",
    "Travel": "Travel",
    "Salary": "Salary",
    "Other Income": "Other income",
    "Invest Deposit": "Savings & investments",
    "Invest Withdraw": "Savings & investments",
}

TYPE_LABELS = {
    "housing_payment": "Housing",
    "utilities_payment": "Utilities",
    "salary": "Salary",
    "other_income": "Other income",
    "investment_deposit": "Savings & investments",
    "investment_withdrawal": "Savings & investments",
    "salary_sweep": "Transfer out",
}

ALL_LABELS = [
    "Housing", "Utilities", "Groceries", "Restaurant", "Fast food", "Bar", "Taxi",
    "Public transport", "Fuel", "Parking", "Pharmacy", "Doctor", "Dentist", "Other health",
    "Home improvement", "Electronics", "Furniture", "Clothing", "Hobbies", "Books", "Shopping",
    "Events", "Cinema", "Gym & sports", "Entertainment", "Flights", "Hotels", "Travel agency",
    "Car rental", "Travel", "Savings & investments", "Salary", "Other income", "Transfer out",
    "Other",
]

# --------------------------------------------------------------------------- baskets

UNEXPECTED_THRESHOLD = 150.0      # EUR, single purchase, for the unexpected-necessity labels
BIG_PURCHASE_THRESHOLD = 500.0    # EUR, any purchase in the Health or Home & Tech categories

REGULAR_LABELS = frozenset(
    {"Housing", "Utilities", "Groceries", "Public transport", "Fuel", "Pharmacy"})
UNEXPECTED_LABELS = frozenset(
    {"Doctor", "Dentist", "Other health", "Home improvement", "Electronics", "Furniture"})
BIG_PURCHASE_CATEGORIES = frozenset({"Health", "Home & Tech"})

BASKETS = ("regular", "unexpected", "everyday", "savings", "income", "transfer")
SPENDING_BASKETS = ("regular", "unexpected", "everyday")

BASKET_RULES_TEXT = (
    "Regular essentials are the bills and needs that come back every month: rent or mortgage, "
    "utilities, groceries, public transport, fuel and pharmacy. "
    "Unexpected necessities are things you did not plan but often cannot skip: doctor, dentist and "
    "other health costs, home repairs, electronics and furniture when a single purchase is "
    "EUR 150 or more, and any other health or home and tech purchase of EUR 500 or more. "
    "Everyday spending is everything else you choose to buy: eating out, bars, taxis, shopping, "
    "hobbies, entertainment, travel. "
    "Money you put into investments counts as savings, not spending."
)

# --------------------------------------------------------------------------- night out

NIGHT_ANCHOR_LABEL = "Bar"
NIGHT_OUT_LABELS = frozenset({"Restaurant", "Fast food", "Bar", "Taxi"})
NIGHT_START_HOUR = 18   # a night out runs from 18:00 ...
NIGHT_END_HOUR = 6      # ... to 06:00 the next morning


@lru_cache(maxsize=4096)
def _previous_day(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


def night_key(ts: str) -> str | None:
    """Return the evening date a timestamp 'YYYY-MM-DD HH:MM:SS' belongs to, or None by day."""
    hour = int(ts[11:13])
    if hour >= NIGHT_START_HOUR:
        return ts[:10]
    if hour < NIGHT_END_HOUR:
        return _previous_day(ts[:10])
    return None


def night_out_flags(ts_list, label_list) -> list[bool]:
    """Context pass for ONE customer. Inputs are aligned lists of purchase timestamps and labels.

    A purchase is part of a night out when its label is Restaurant, Fast food, Bar or Taxi, it falls
    between 18:00 and 06:00, and at least one Bar purchase falls in the same evening window.
    Order of the inputs does not matter.
    """
    anchors = set()
    keys = [None] * len(label_list)
    for i, label in enumerate(label_list):
        if label in NIGHT_OUT_LABELS:
            k = night_key(ts_list[i])
            keys[i] = k
            if k is not None and label == NIGHT_ANCHOR_LABEL:
                anchors.add(k)
    return [k is not None and k in anchors for k in keys]


# --------------------------------------------------------------------------- classification

_label_cache: dict[tuple, str] = {}


def label_for(tx_type: str, category: str, mcc: str) -> str:
    """Fine-grained label for one transaction."""
    key = (tx_type, category, mcc)
    got = _label_cache.get(key)
    if got is not None:
        return got
    if tx_type in TYPE_LABELS:
        label = TYPE_LABELS[tx_type]
    elif mcc and mcc in MCC_LABELS:
        label = MCC_LABELS[mcc]
    else:
        label = CATEGORY_FALLBACK.get(category, "Other")
    _label_cache[key] = label
    return label


def basket_for(tx_type: str, label: str, category: str, amount: float) -> str:
    """Basket for one transaction. `amount` is signed (outflows negative)."""
    if tx_type in ("salary", "other_income"):
        return "income"
    if tx_type == "investment_deposit":
        return "savings"
    if tx_type in ("investment_withdrawal", "salary_sweep"):
        return "transfer"
    if amount >= 0:
        return "income"  # refunds and unknown inflows are income-side
    size = -amount
    if label in UNEXPECTED_LABELS and size >= UNEXPECTED_THRESHOLD:
        return "unexpected"
    if category in BIG_PURCHASE_CATEGORIES and size >= BIG_PURCHASE_THRESHOLD:
        return "unexpected"
    if label in REGULAR_LABELS:
        return "regular"
    return "everyday"


def classify(tx_type: str, category: str, mcc: str, amount: float) -> tuple[str, str]:
    """(label, basket) for one transaction. Context (night out) needs `night_out_flags`."""
    label = label_for(tx_type, category, mcc)
    return label, basket_for(tx_type, label, category, amount)


def display_label(label: str, context: str) -> str:
    """Label as the UI and tools report it: night-out purchases are shown as 'Night out'."""
    return "Night out" if context == "night_out" else label
