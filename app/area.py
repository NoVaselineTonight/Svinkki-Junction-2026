"""Public area context from Statistics Finland's Paavo open data (CC BY 4.0).

The data lives in paavo.json (public area statistics only; it holds no customer data).
area_context() never puts the postal code in what it returns, so the code cannot reach the
AI model or the UI through this module.
"""
import json
from pathlib import Path

_PATH = Path(__file__).with_name("paavo.json")
_cache = None


def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _eur(x, step=10):
    return "€{:,.0f}".format(round(x / step) * step)


def _pct(x):
    return "{:.0f}%".format(x * 100)


def _empty(note, data):
    return {"area_name": None, "year": None, "source": data.get("source"), "url": data.get("url"),
            "rows": [], "compare": [], "note": note,
            "explain": "No public area statistics are available for this area."}


def area_context(postal: str, customer: dict | None = None) -> dict:
    data = _load()
    areas = data.get("areas") or {}
    if not areas:
        return _empty("The public area statistics file is not available, so there is nothing to show.", data)
    a = areas.get(str(postal or "").strip())
    if not a:
        return _empty("Statistics Finland does not publish figures for this postal code area "
                      "(for example a PO box or very small area), so there is nothing to show.", data)

    year = a.get("income_year") or a.get("population_year")
    rows = []

    def add(key, name, value, unit, text):
        if value is not None:
            rows.append({"key": key, "name": name, "value": value, "unit": unit, "text": text})

    mi, ai = a.get("median_income"), a.get("average_income")
    iy = a.get("income_year")
    if mi is not None:
        add("median_income", "Median income", mi, "EUR/year",
            f"The median income of people living here was {_eur(mi, 100)} a year in {iy}, "
            f"about {_eur(mi / 12)} a month.")
    if ai is not None:
        add("average_income", "Average income", ai, "EUR/year",
            f"The average income of people living here was {_eur(ai, 100)} a year in {iy}, "
            f"about {_eur(ai / 12)} a month.")
    ty = a.get("tenure_year")
    add("owner_occupied_share", "Owner-occupied homes", a.get("owner_occupied_share"), "share",
        f"{_pct(a['owner_occupied_share']) if a.get('owner_occupied_share') is not None else ''} "
        f"of households here live in a home they own ({ty}).")
    add("rented_share", "Rented homes", a.get("rented_share"), "share",
        f"{_pct(a['rented_share']) if a.get('rented_share') is not None else ''} "
        f"of households here live in a rented home ({ty}).")
    fa = a.get("average_floor_area")
    add("average_floor_area", "Average dwelling size", fa, "m2",
        f"The average dwelling here is {fa:.0f} square metres ({a.get('dwellings_year')})." if fa is not None else "")
    pop = a.get("population")
    add("population", "Residents", pop, "people",
        f"About {pop:,} people live in this area ({a.get('population_year')})." if pop is not None else "")
    age = a.get("average_age")
    add("average_age", "Average age", age, "years",
        f"The average age of residents is {age:.1f} years ({a.get('population_year')})." if age is not None else "")

    compare = []
    if customer and mi is not None:
        inc = customer.get("monthly_income")
        hc = customer.get("housing_cost")
        if inc:
            compare.append({"name": "Monthly income", "you": round(inc), "area": round(mi / 12),
                            "text": f"Your monthly income here is {_eur(inc)}; a typical resident has about "
                                    f"{_eur(mi / 12)} a month."})
        if inc and hc is not None and inc > 0:
            compare.append({"name": "Housing cost share of income", "you": round(hc / inc, 3), "area": None,
                            "text": f"Your housing cost of {_eur(hc)} is {_pct(hc / inc)} of your monthly income."})

    note = (f"Source: Statistics Finland, Paavo open data by postal code area, licence CC BY 4.0. "
            f"Reference year {iy} for income, {a.get('population_year')} for population, households "
            f"and dwellings. Area incomes are yearly disposable income of all residents aged 18 or over; your "
            f"figure is what arrives on this account now, so the comparison is rough context, not a ranking. "
            f"This is public area data and involves no other customer's bank data.")
    explain = ("These are public statistics about everyone who lives in the area, not about this bank's "
               "customers. Income is yearly disposable money income of residents aged 18 or over; "
               "home ownership is the share of households.")
    return {"area_name": a.get("name"), "year": year, "source": data.get("source"), "url": data.get("url"),
            "rows": rows, "compare": compare, "note": note, "explain": explain}
