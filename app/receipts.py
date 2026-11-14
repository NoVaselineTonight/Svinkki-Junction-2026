"""Simulated S Group receipts for the demo, and what can be learned from them.

The challenge data has payment amounts only, no items. For the demo every grocery purchase gets a
deterministic, plausible receipt: the same transaction always yields the same lines, and the lines
add up to the payment to the cent. Everything here is labelled as simulated. A real version would
read the customer's S Group purchase data with their consent.

The product catalogue and its prices are ILLUSTRATIVE: typical 2026 shelf prices in euros, not
claims about any store or chain.

Results follow the house style of app/features.py: spending is positive, money is rounded to the
cent, and every result carries `explain` and `evidence`. Wording is light and factual.

Public functions:
  receipt_for(tx_row, habit_seed=None, monthly_grocery=None) -> dict | None
  receipts(conn, today, period="last_month", habit_seed=None, limit=20) -> dict
  receipt_insights(conn, today, period="last_3_months", habit_seed=None) -> dict
  product_habit(conn, today, query, period="last_3_months", habit_seed=None) -> dict
  receipt_trends(conn, today, period="last_12_months", habit_seed=None) -> dict   (12 or 24 months)
  basket_profile(conn, today, period="last_12_months", habit_seed=None) -> dict   (real payments only)
  cut_ideas(conn, today, period="last_3_months", habit_seed=None) -> dict
  parse_receipt_text(text) -> dict
  build_dataset(db_path=None, out_dir=None, today=None) -> list   (also: python -m app.receipts)

Two kinds of receipt exist: "grocery" (label Groceries: Prisma, S-market, Alepa, Sale) and "fuel"
(label Fuel: a fictional ABC station, one fuel line plus sometimes a shop line). Fuel receipts never
count in the grocery figures. When data/receipts/receipts.json exists and holds the customer
(habit_seed = customer id) the stored receipts are read; the on-the-fly generator gives the same
result because it is deterministic.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import re
import sqlite3
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from . import insights as ins

SIM_NOTE = ("Simulated receipt lines for the demo: the challenge data has payment amounts only. "
            "A real version would read your S Group purchase data, with your consent.")
DEMO_LABEL = "Demo receipts"       # the one tag a receipt card carries
PASTE_NOTE = "Read from the text you pasted."

GROUP_NAMES = {
    "dairy": "Dairy and eggs", "bread": "Bread", "meat_fish": "Meat and fish",
    "fruit_veg": "Fruit and vegetables", "pantry": "Pantry", "ready_meals": "Ready meals",
    "snacks_sweets": "Snacks and sweets", "soft_drinks": "Soft drinks",
    "energy_drinks": "Energy drinks", "coffee_tea": "Coffee and tea",
    "alcohol_mild": "Beer and cider", "household": "Household", "hygiene": "Personal care",
    "baby": "Baby", "pet": "Pets", "frozen": "Frozen", "fuel": "Fuel", "car": "Car care",
    "other": "Other",
}
TREAT_GROUPS = ("snacks_sweets", "soft_drinks", "energy_drinks", "alcohol_mild")

# (group, name, price EUR, unit, essential). Illustrative prices only.
_CATALOGUE_ROWS = [
    ("dairy", "Kotimaista kevytmaito 1 l", 1.29, "kpl", True),
    ("dairy", "Kotimaista täysmaito 1 l", 1.35, "kpl", True),
    ("dairy", "Rasvaton maito 1 l", 1.25, "kpl", True),
    ("dairy", "Maustamaton jogurtti 1 kg", 2.19, "kpl", True),
    ("dairy", "Mansikkajogurtti 1 kg", 2.39, "kpl", False),
    ("dairy", "Kananmunat 10 kpl", 3.19, "kpl", True),
    ("dairy", "Juustoviipaleet 270 g", 3.49, "kpl", True),
    ("dairy", "Voi 500 g", 5.29, "kpl", True),
    ("dairy", "Kasvirasvalevite 400 g", 2.89, "kpl", True),
    ("dairy", "Ruokakerma 2 dl", 1.69, "kpl", True),
    ("dairy", "Rahka 250 g", 1.29, "kpl", False),
    ("dairy", "Raejuusto 400 g", 2.35, "kpl", True),
    ("dairy", "Kaurajuoma 1 l", 1.69, "kpl", True),
    ("bread", "Ruispalat 330 g", 2.59, "kpl", True),
    ("bread", "Paahtoleipä 500 g", 2.19, "kpl", True),
    ("bread", "Täysjyväleipä 500 g", 2.89, "kpl", True),
    ("bread", "Sämpylät 6 kpl", 2.79, "kpl", True),
    ("bread", "Patonki 175 g", 1.59, "kpl", False),
    ("bread", "Pulla 6 kpl", 3.49, "kpl", False),
    ("bread", "Näkkileipä 200 g", 2.29, "kpl", True),
    ("meat_fish", "Jauheliha 400 g", 4.79, "kpl", True),
    ("meat_fish", "Broilerin rintafilee 600 g", 8.49, "kpl", True),
    ("meat_fish", "Kinkkuleikkele 140 g", 1.99, "kpl", True),
    ("meat_fish", "Nakit 270 g", 2.39, "kpl", False),
    ("meat_fish", "Lenkkimakkara 400 g", 3.29, "kpl", False),
    ("meat_fish", "Lohifilee 300 g", 6.99, "kpl", True),
    ("meat_fish", "Savulohi 150 g", 4.49, "kpl", False),
    ("meat_fish", "Grillimakkara 400 g", 3.49, "kpl", False),
    ("meat_fish", "Broilerin koivet 900 g", 4.99, "kpl", True),
    ("meat_fish", "Tonnikalasäilyke 150 g", 1.79, "kpl", True),
    ("meat_fish", "Possun ulkofilee kg", 12.90, "kg", True),
    ("fruit_veg", "Banaani kg", 1.89, "kg", True),
    ("fruit_veg", "Kurkku kg", 2.99, "kg", True),
    ("fruit_veg", "Tomaatti kg", 3.99, "kg", True),
    ("fruit_veg", "Omena kg", 2.99, "kg", True),
    ("fruit_veg", "Peruna 2 kg", 2.49, "kpl", True),
    ("fruit_veg", "Porkkana 1 kg", 1.49, "kpl", True),
    ("fruit_veg", "Sipuli kg", 1.49, "kg", True),
    ("fruit_veg", "Appelsiini kg", 2.69, "kg", True),
    ("fruit_veg", "Avokado kpl", 1.29, "kpl", True),
    ("fruit_veg", "Salaattisekoitus 150 g", 2.19, "kpl", True),
    ("fruit_veg", "Paprika kg", 5.49, "kg", True),
    ("fruit_veg", "Viinirypäleet kg", 5.99, "kg", False),
    ("fruit_veg", "Sitruuna kpl", 0.59, "kpl", False),
    ("pantry", "Spagetti 500 g", 1.29, "kpl", True),
    ("pantry", "Riisi 1 kg", 2.49, "kpl", True),
    ("pantry", "Vehnäjauho 1 kg", 1.49, "kpl", True),
    ("pantry", "Sokeri 1 kg", 1.79, "kpl", True),
    ("pantry", "Rypsiöljy 1 l", 3.49, "kpl", True),
    ("pantry", "Tomaattimurska 400 g", 0.99, "kpl", True),
    ("pantry", "Kaurahiutaleet 1 kg", 1.99, "kpl", True),
    ("pantry", "Mysli 750 g", 3.79, "kpl", False),
    ("pantry", "Maapähkinävoi 350 g", 3.49, "kpl", False),
    ("pantry", "Mansikkahillo 400 g", 2.39, "kpl", False),
    ("pantry", "Ketsuppi 500 g", 2.29, "kpl", False),
    ("pantry", "Majoneesi 265 g", 2.49, "kpl", False),
    ("pantry", "Kikherne 400 g", 1.09, "kpl", True),
    ("pantry", "Kauramaito-jauhe 500 g", 2.95, "kpl", False),
    ("ready_meals", "Lihapullat ja perunamuusi 400 g", 3.99, "kpl", False),
    ("ready_meals", "Lasagne 400 g", 3.49, "kpl", False),
    ("ready_meals", "Kasvissosekeitto 500 g", 2.99, "kpl", False),
    ("ready_meals", "Sushiboksi 8 kpl", 6.90, "kpl", False),
    ("ready_meals", "Grillikana kokonainen", 7.49, "kpl", False),
    ("ready_meals", "Salaattiboksi 300 g", 3.99, "kpl", False),
    ("snacks_sweets", "Maitosuklaalevy 200 g", 2.99, "kpl", False),
    ("snacks_sweets", "Perunalastut 175 g", 2.49, "kpl", False),
    ("snacks_sweets", "Karkkipussi 300 g", 3.49, "kpl", False),
    ("snacks_sweets", "Pähkinäsekoitus 200 g", 2.99, "kpl", False),
    ("snacks_sweets", "Kaurakeksit 200 g", 1.79, "kpl", False),
    ("snacks_sweets", "Salmiakkipussi 280 g", 3.19, "kpl", False),
    ("snacks_sweets", "Popcorn 100 g", 1.49, "kpl", False),
    ("snacks_sweets", "Kinuskikarkit 150 g", 1.99, "kpl", False),
    ("snacks_sweets", "Proteiinipatukka 55 g", 1.99, "kpl", False),
    ("snacks_sweets", "Tortillachipsit 200 g", 2.69, "kpl", False),
    ("snacks_sweets", "Suklaapatukka 45 g", 1.29, "kpl", False),
    ("soft_drinks", "Cola 1,5 l", 2.29, "kpl", False),
    ("soft_drinks", "Limonadi 1,5 l", 1.89, "kpl", False),
    ("soft_drinks", "Appelsiinimehu 1 l", 2.19, "kpl", False),
    ("soft_drinks", "Kivennäisvesi 1,5 l", 1.19, "kpl", False),
    ("soft_drinks", "Tuoremehu 1 l", 2.89, "kpl", False),
    ("soft_drinks", "Cola 0,33 l tölkki", 1.39, "kpl", False),
    ("soft_drinks", "Jäätee 1,5 l", 2.19, "kpl", False),
    ("soft_drinks", "Kivennäisvesi 0,5 l", 1.19, "kpl", False),
    ("energy_drinks", "Energiajuoma 0,5 l", 1.89, "kpl", False),
    ("energy_drinks", "Energiajuoma sokeriton 0,5 l", 1.89, "kpl", False),
    ("energy_drinks", "Energiajuoma 0,25 l", 1.59, "kpl", False),
    ("energy_drinks", "Energiajuoma 4 x 0,5 l", 6.49, "kpl", False),
    ("coffee_tea", "Rainbow kahvi 500 g", 4.99, "kpl", True),
    ("coffee_tea", "Pikakahvi 200 g", 5.49, "kpl", True),
    ("coffee_tea", "Kahvikapselit 10 kpl", 3.99, "kpl", False),
    ("coffee_tea", "Musta tee 20 pss", 2.49, "kpl", False),
    ("coffee_tea", "Vihreä tee 20 pss", 2.79, "kpl", False),
    ("alcohol_mild", "Lager-olut 0,33 l tölkki", 1.45, "kpl", False),
    ("alcohol_mild", "Olut 0,5 l tölkki", 1.79, "kpl", False),
    ("alcohol_mild", "Olut 12 x 0,33 l", 15.90, "kpl", False),
    ("alcohol_mild", "Siideri 0,33 l", 1.69, "kpl", False),
    ("alcohol_mild", "IPA-olut 0,33 l", 2.29, "kpl", False),
    ("alcohol_mild", "Vehnäolut 0,5 l", 2.19, "kpl", False),
    ("household", "Talouspaperi 4 rl", 3.49, "kpl", True),
    ("household", "WC-paperi 8 rl", 4.99, "kpl", True),
    ("household", "Astianpesuaine 500 ml", 1.99, "kpl", True),
    ("household", "Pyykinpesuaine 1,5 l", 6.99, "kpl", True),
    ("household", "Roskapussit 20 kpl", 1.99, "kpl", True),
    ("household", "Leivinpaperi", 1.99, "kpl", True),
    ("household", "Paristot AA 4 kpl", 5.99, "kpl", False),
    ("household", "Pesuainetabletit 25 kpl", 5.49, "kpl", True),
    ("household", "Kynttilät 12 kpl", 2.99, "kpl", False),
    ("household", "Muovikassi", 0.40, "kpl", False),
    ("hygiene", "Hammastahna 75 ml", 2.49, "kpl", True),
    ("hygiene", "Shampoo 250 ml", 3.99, "kpl", True),
    ("hygiene", "Suihkusaippua 250 ml", 2.99, "kpl", True),
    ("hygiene", "Deodorantti 150 ml", 3.49, "kpl", True),
    ("hygiene", "Käsisaippua 250 ml", 1.99, "kpl", True),
    ("hygiene", "Hammasharja", 2.49, "kpl", True),
    ("baby", "Vaippapaketti 30 kpl", 11.99, "kpl", True),
    ("baby", "Lastenruoka 190 g", 1.29, "kpl", True),
    ("baby", "Kosteuspyyhkeet vauva 60 kpl", 3.29, "kpl", True),
    ("pet", "Kissanruoka 85 g", 0.89, "kpl", True),
    ("pet", "Koiranruoka 400 g", 1.99, "kpl", True),
    ("pet", "Kissanhiekka 10 l", 6.99, "kpl", True),
    ("frozen", "Pakastepizza 350 g", 3.29, "kpl", False),
    ("frozen", "Mustikka pakaste 500 g", 3.99, "kpl", False),
    ("frozen", "Vaniljajäätelö 0,9 l", 3.99, "kpl", False),
    ("frozen", "Kalapuikot 450 g", 3.79, "kpl", True),
    ("frozen", "Pakasteherne 450 g", 1.89, "kpl", True),
    ("frozen", "Ranskalaiset perunat 750 g", 2.79, "kpl", False),
]

CATALOGUE = [
    {"name": n, "group": g, "price": p, "unit": u, "essential": e}
    for (g, n, p, u, e) in _CATALOGUE_ROWS
]
_PRICE_C = [int(round(p["price"] * 100)) for p in CATALOGUE]
_GROUP_BASE = {
    "dairy": 10, "bread": 7, "meat_fish": 8, "fruit_veg": 10, "pantry": 10, "ready_meals": 3,
    "snacks_sweets": 5, "soft_drinks": 4, "energy_drinks": 2, "coffee_tea": 2, "alcohol_mild": 3,
    "household": 4, "hygiene": 2.5, "baby": 0.5, "pet": 0.5, "frozen": 4,
}

CHAINS = [("Prisma", 22), ("S-market", 33), ("Alepa", 17), ("Sale", 14), ("ABC-market", 14)]


# --------------------------------------------------------------------------- helpers

def _h(*parts):
    return int.from_bytes(hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).digest()[:8],
                          "big")


def _eur(x):
    return ins._eur(x)


def _eur0(x):
    return ins._eur0(x)


def store_for(merchant):
    """One stable S Group grocery chain per merchant id (weighted: S-market and Prisma most common)."""
    total = sum(w for _, w in CHAINS)
    x = _h("store", merchant) % total
    for name, w in CHAINS:
        if x < w:
            return name
        x -= w
    return CHAINS[0][0]


@lru_cache(maxsize=64)
def _habit_profile(habit_key):
    """Per-customer product mix: weights for every catalogue product (stable for a habit key)."""
    mult = {g: 1.0 for g in _GROUP_BASE}
    if habit_key is not None:
        r = random.Random(_h("habit", habit_key))
        mult["energy_drinks"] = r.choices([0.1, 0.5, 1.5, 5.0], [40, 25, 20, 15])[0]
        mult["snacks_sweets"] = r.choices([0.3, 0.7, 1.0, 2.0, 3.5], [20, 25, 25, 20, 10])[0]
        mult["alcohol_mild"] = r.choices([0.0, 0.3, 1.0, 2.5, 4.0], [20, 25, 25, 20, 10])[0]
        mult["soft_drinks"] = r.choices([0.4, 1.0, 2.0, 3.0], [30, 35, 25, 10])[0]
        mult["coffee_tea"] = r.choices([0.5, 1.0, 2.0, 3.0], [20, 40, 30, 10])[0]
        mult["ready_meals"] = r.choices([0.4, 1.0, 2.0], [35, 40, 25])[0]
        mult["baby"] = 6.0 if r.random() < 0.08 else 0.0
        mult["pet"] = 6.0 if r.random() < 0.2 else 0.0
    weights = []
    for i, p in enumerate(CATALOGUE):
        w = _GROUP_BASE[p["group"]] * mult[p["group"]]
        if habit_key is not None:
            w *= 0.5 + 1.5 * ((_h("pop", habit_key, p["name"]) % 1000) / 1000.0)
        if p["name"] == "Muovikassi":
            w = 0.0
        weights.append(w)
    cum = []
    s = 0.0
    for w in weights:
        s += w
        cum.append(s)
    return {"weights": tuple(weights), "cum": tuple(cum), "mult": mult}


def _habit_key(habit_seed):
    return None if habit_seed is None else str(habit_seed)


def _draw_qty(rng, p, mult):
    if p["unit"] == "kg":
        return round(rng.uniform(0.25, 1.5), 2)
    g = p["group"]
    if g in ("energy_drinks", "alcohol_mild", "soft_drinks") and p["price"] < 3:
        heavy = mult.get(g, 1.0)
        opts = [1, 2, 3, 4, 6]
        w = [60, 20, 10, 6, 4] if heavy < 2 else [30, 25, 20, 15, 10]
        return rng.choices(opts, w)[0]
    return rng.choices([1, 2, 3, 4], [72, 19, 6, 3])[0]


def _line(p_idx, qty, total_c, unit_price_c=None):
    p = CATALOGUE[p_idx]
    up = _PRICE_C[p_idx] if unit_price_c is None else unit_price_c
    return {"name": p["name"], "group": p["group"], "qty": qty, "unit": p["unit"],
            "unit_price": round(up / 100.0, 2), "line_total": round(total_c / 100.0, 2),
            "essential": p["essential"]}


def _build_lines(rng, total_c, prof):
    """Lines (in cents) that sum to total_c exactly."""
    mult, cum = prof["mult"], prof["cum"]
    n = int(round(total_c / 450.0 * rng.uniform(0.75, 1.3)))
    n = max(1, min(30, n))
    lines = []          # dicts with idx, qty, tc (total cents), upc (unit price cents)
    used = set()
    rem = total_c

    def pick(budget):
        for _ in range(25):
            i = rng.choices(range(len(CATALOGUE)), cum_weights=cum)[0]
            if i in used or _PRICE_C[i] > budget:
                continue
            return i
        ok = [i for i in range(len(CATALOGUE))
              if i not in used and _PRICE_C[i] <= budget and cum[i] > (cum[i - 1] if i else 0)]
        return rng.choice(ok) if ok else None

    def add_normal(budget):
        nonlocal rem
        i = pick(budget)
        if i is None:
            return False
        p = CATALOGUE[i]
        qty = _draw_qty(rng, p, mult)
        tc = int(round(_PRICE_C[i] * qty))
        while tc > budget and (qty > 1 if p["unit"] == "kpl" else qty > 0.1):
            qty = qty - 1 if p["unit"] == "kpl" else round(qty * 0.7, 2)
            tc = int(round(_PRICE_C[i] * qty))
        if tc < 1 or tc > budget:
            return False
        used.add(i)
        lines.append({"i": i, "qty": qty, "tc": tc, "upc": _PRICE_C[i]})
        rem -= tc
        return True

    for k in range(n - 1):
        budget = rem - 60 * (n - 1 - k + 1)
        if budget < 39 or not add_normal(budget):
            break
    while rem > 3000 and len(lines) < 29:
        if not add_normal(rem - 60):
            break

    # Last line absorbs the remainder.
    if rem > 0:
        if rem < 20 and lines:
            for ln in lines:
                if CATALOGUE[ln["i"]]["unit"] == "kpl" and ln["qty"] == 1:
                    ln["tc"] += rem
                    ln["upc"] = ln["tc"]
                    rem = 0
                    break
        if rem > 0:
            _finish(rng, lines, used, rem, cum)
    return lines


def _finish(rng, lines, used, rem, cum):
    best = []
    for i, p in enumerate(CATALOGUE):
        if p["unit"] != "kpl" or p["name"] == "Muovikassi" or i in used:
            continue
        w = cum[i] - (cum[i - 1] if i else 0)
        if w <= 0:
            continue
        for k in range(1, 7):
            if rem % k:
                continue
            ratio = rem / k / _PRICE_C[i]
            if 0.5 <= ratio <= 2.2:
                best.append((w * math.exp(-2.0 * abs(math.log(ratio))) / k, i, k))
    if best:
        _, i, k = rng.choices(best, weights=[b[0] for b in best])[0]
        used.add(i)
        lines.append({"i": i, "qty": k, "tc": rem, "upc": rem // k})
        return
    if rem >= 20 or not lines:
        mi = next(j for j, p in enumerate(CATALOGUE) if p["name"] == "Muovikassi")
        # Large leftover without a plausible single product: a few ordinary-priced lines then a
        # price-adjusted one. Try again with smaller chunks.
        if rem > 1500 and len(lines) < 29:
            cand = [i for i, p in enumerate(CATALOGUE)
                    if p["unit"] == "kpl" and i not in used and p["name"] != "Muovikassi"
                    and _PRICE_C[i] <= rem // 2 and cum[i] > (cum[i - 1] if i else 0)]
            if cand:
                i = rng.choice(cand)
                used.add(i)
                lines.append({"i": i, "qty": 1, "tc": _PRICE_C[i], "upc": _PRICE_C[i]})
                return _finish(rng, lines, used, rem - _PRICE_C[i], cum)
        used.add(mi)
        lines.append({"i": mi, "qty": 1, "tc": rem, "upc": rem})
        return
    # Tiny remainder, nothing to adjust: a bottle deposit line.
    lines.append({"i": None, "qty": 1, "tc": rem, "upc": rem})


def _to_line(ln):
    if ln["i"] is None:
        return {"name": "Pantti", "group": "household", "qty": 1, "unit": "kpl",
                "unit_price": round(ln["tc"] / 100.0, 2), "line_total": round(ln["tc"] / 100.0, 2),
                "essential": False}
    return _line(ln["i"], ln["qty"], ln["tc"], ln["upc"])


def bonus_rate(monthly_grocery):
    m = float(monthly_grocery or 0.0)
    if m < 150:
        return 1
    if m < 250:
        return 2
    if m < 400:
        return 3
    if m < 600:
        return 4
    return 5


def _row_get(row, key):
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


_HOME_CHAINS = [("S-market", 40), ("Alepa", 25), ("Sale", 15), ("Prisma", 20)]


def _home_store(habit_seed):
    x = _h("home", habit_seed) % sum(w for _, w in _HOME_CHAINS)
    for name, w in _HOME_CHAINS:
        if x < w:
            return name
        x -= w
    return _HOME_CHAINS[0][0]


def _grocery_store(merchant, tx_id, ts, total_c, habit_seed):
    """Home store for most small baskets, Prisma for most big ones (deterministic per payment)."""
    if total_c >= 6000 and _h("big", tx_id, ts, total_c) % 100 < 70:
        return "Prisma"
    if habit_seed is not None and _h("small", tx_id, ts, total_c) % 100 < 75:
        return _home_store(habit_seed)
    return store_for(merchant)


# Fictional station names (a real ABC would carry its own place name).
STATIONS = ["ABC Mäntylä", "ABC Kehätie", "ABC Koivisto", "ABC Harjula", "ABC Rantatie",
            "ABC Pitkäkangas", "ABC Nihtisilta", "ABC Laaksola"]
_FUEL_NAMES = {"95 E10": "Bensiini 95 E10", "Diesel": "Diesel"}
# (name, group, price EUR, weight)
_ABC_SHOP = [
    ("Kahvi 0,4 l", "coffee_tea", 2.90, 4.0), ("Iso kahvi 0,6 l", "coffee_tea", 3.50, 3.0),
    ("Korvapuusti", "snacks_sweets", 2.80, 3.0), ("Hot dog", "ready_meals", 3.90, 2.0),
    ("Tuulilasinpesuneste 4 l", "car", 4.90, 1.5), ("Autopesu perus", "car", 9.90, 1.0),
    ("Energiajuoma 0,5 l", "energy_drinks", 2.69, 1.5), ("Suklaapatukka 45 g", "snacks_sweets", 1.99, 2.0),
    ("Kivennäisvesi 0,5 l", "soft_drinks", 2.79, 1.5),
]


def station_for(merchant):
    return STATIONS[_h("station", merchant) % len(STATIONS)]


def fuel_type_for(habit_seed):
    """One fuel type per customer: 95 E10 for most, diesel for about three in ten."""
    if habit_seed is None:
        return "95 E10"
    return "Diesel" if _h("fueltype", habit_seed) % 100 < 30 else "95 E10"


def _fuel_price(ftype, d, rng):
    """Pump price per litre (EUR, 3 decimals): 95 E10 about 1.76-1.95, diesel about 1.71-1.90."""
    try:
        doy = date.fromisoformat(str(d)[:10]).timetuple().tm_yday
    except (ValueError, TypeError):
        doy = 1
    base, lo, hi = (185, 176, 195) if ftype == "95 E10" else (180, 171, 190)
    x = base + 7.0 * math.sin(2 * math.pi * doy / 365.0) + rng.uniform(-3.0, 3.0)
    cents = max(lo, min(hi, int(round(x))))
    return cents / 100.0 - 0.001


def _shop_pick(rng, mult, exclude, max_c):
    cand = [(i, s) for i, s in enumerate(_ABC_SHOP)
            if i not in exclude and int(round(s[2] * 100)) <= max_c]
    if not cand:
        return None
    w = [s[3] * (mult.get(s[1], 1.0) if s[1] == "energy_drinks" else 1.0) for _, s in cand]
    if sum(w) <= 0:
        w = [1.0] * len(cand)
    return rng.choices(cand, weights=w)[0][0]


def _shop_line(i, price_c, qty=1):
    n, g, _, _ = _ABC_SHOP[i]
    return {"name": n, "group": g, "qty": qty, "unit": "kpl", "unit_price": round(price_c / 100.0, 2),
            "line_total": round(price_c * qty / 100.0, 2), "essential": False}


def _fuel_lines(rng, total_c, d, ftype, prof):
    """(lines, fuel info or None). Lines sum to total_c exactly."""
    mult = prof["mult"]
    if total_c < 1200:                         # a coffee or a snack, no fuel
        used, lines, rem = set(), [], total_c
        k = 1 if total_c < 500 else 2
        for _ in range(k - 1):
            i = _shop_pick(rng, mult, used, rem - 150)
            if i is None:
                break
            used.add(i)
            pc = int(round(_ABC_SHOP[i][2] * 100))
            lines.append(_shop_line(i, pc))
            rem -= pc
        i = _shop_pick(rng, mult, used, 10 ** 9)
        lines.append(_shop_line(i, rem))
        return lines, None
    shop, used, shop_c = [], set(), 0
    if total_c >= 2500 and rng.random() < 0.4:
        for _ in range(1 if rng.random() < 0.7 else 2):
            i = _shop_pick(rng, mult, used, total_c - shop_c - 1500)
            if i is None:
                break
            used.add(i)
            pc = int(round(_ABC_SHOP[i][2] * 100))
            shop.append(_shop_line(i, pc))
            shop_c += pc
    f_c = total_c - shop_c
    price = _fuel_price(ftype, d, rng)
    litres = max(round(f_c / 100.0 / price, 2), 0.01)
    unit_price = round(f_c / 100.0 / litres, 3)
    fuel_line = {"name": _FUEL_NAMES[ftype], "group": "fuel", "qty": litres, "unit": "l",
                 "unit_price": unit_price, "line_total": round(f_c / 100.0, 2), "essential": True}
    return [fuel_line] + shop, {"type": ftype, "litres": litres, "price_per_litre": unit_price}


def _bonus(kind, total, monthly_grocery):
    rate = 1 if kind == "fuel" else bonus_rate(1 if monthly_grocery is None else monthly_grocery)
    return {"rate_pct": rate, "amount": round(total * rate / 100.0, 2), "label": "Bonus estimate"}


def receipt_for(tx_row, habit_seed=None, monthly_grocery=None):
    """Deterministic simulated receipt for one Groceries or Fuel purchase, else None."""
    label = _row_get(tx_row, "label")
    if label not in ("Groceries", "Fuel"):
        return None
    amount = _row_get(tx_row, "amount")
    typ = _row_get(tx_row, "type")
    if amount is None or float(amount) >= 0 or (typ not in (None, "purchase")):
        return None
    total_c = int(round(abs(float(amount)) * 100))
    if total_c <= 0:
        return None
    tx_id, ts = _row_get(tx_row, "id"), _row_get(tx_row, "ts")
    merchant = _row_get(tx_row, "merchant")
    d = _row_get(tx_row, "d") or (str(ts)[:10] if ts else None)
    total = round(total_c / 100.0, 2)
    prof = _habit_profile(_habit_key(habit_seed))
    if label == "Fuel":
        rng = random.Random(_h("fuel", tx_id, ts, "%.2f" % float(amount), merchant))
        lines, fuel = _fuel_lines(rng, total_c, d, fuel_type_for(habit_seed), prof)
        return {
            "tx_id": tx_id, "store": station_for(merchant), "chain": "ABC", "kind": "fuel", "d": d,
            "ts": ts, "total": total, "lines": lines, "fuel": fuel,
            "bonus": _bonus("fuel", total, monthly_grocery), "simulated": True,
        }
    rng = random.Random(_h("receipt", tx_id, ts, "%.2f" % float(amount), merchant))
    lines = [_to_line(ln) for ln in _build_lines(rng, total_c, prof)]
    return {
        "tx_id": tx_id, "store": _grocery_store(merchant, tx_id, ts, total_c, habit_seed),
        "kind": "grocery", "d": d, "ts": ts, "total": total, "lines": lines,
        "bonus": _bonus("grocery", total, monthly_grocery), "simulated": True,
    }


# --------------------------------------------------------------------------- period helpers

_PERIOD_MONTHS = {"last_month": 1, "this_month": None, "last_3_months": 3, "last_6_months": 6,
                  "last_12_months": 12, "last_24_months": 24}
def _key(p):
    return str(p or "").strip().lower().replace(" ", "_").replace("-", "_")


def _months_in(period, frm, to):
    m = _PERIOD_MONTHS.get(_key(period))
    if m:
        return float(m)
    days = (ins._d(to) - ins._d(frm)).days + 1
    return max(days / 30.4375, 0.25)


def _phrase(period, frm, to, today=None):
    """The period as a phrase with its preposition: "in August", "over the last 3 months"."""
    return ins.human_period(frm, to, today or to)


_REMAINDER = ("Muovikassi", "Pantti")     # lines that only balance a receipt to the payment to the cent


def _without_receipt(conn, frm, to):
    """Payments labelled Groceries or Fuel that are not card purchases (for example a bill the customer
    re-labelled), so they have no receipt. {label: (count, total)}."""
    cur = conn.execute(
        "SELECT label, COUNT(*), COALESCE(-SUM(amount), 0) FROM tx WHERE label IN ('Groceries', 'Fuel') "
        "AND COALESCE(type, '') <> 'purchase' AND amount < 0 AND d >= ? AND d <= ? GROUP BY label", (frm, to))
    return {r[0]: (int(r[1]), round(float(r[2]), 2)) for r in cur.fetchall()}


def _without_receipt_text(missing):
    parts = []
    for lab in ("Fuel", "Groceries"):
        if lab in missing:
            n, t = missing[lab]
            parts.append("%d payment%s labelled %s (%s)" % (n, "" if n == 1 else "s", ins.label_words(lab),
                                                            ins._eur(t)))
    if not parts:
        return ""
    return " Also %s %s not a card purchase, so there is no receipt for %s." % (
        " and ".join(parts), "is" if sum(v[0] for v in missing.values()) == 1 else "are",
        "it" if sum(v[0] for v in missing.values()) == 1 else "them")


_COLS = "id, d, ts, amount, merchant, label, type"


def _rows(conn, frm, to):
    cur = conn.execute(
        "SELECT %s FROM tx WHERE label IN ('Groceries', 'Fuel') AND type = 'purchase' AND amount < 0 "
        "AND d >= ? AND d <= ? ORDER BY ts DESC, id DESC" % _COLS, (frm, to))
    return [dict(zip(("id", "d", "ts", "amount", "merchant", "label", "type"), r)) for r in cur.fetchall()]


def _monthly_grocery(conn, today):
    frm, to = ins.period(today, "last_3_months")
    s = conn.execute("SELECT COALESCE(SUM(-amount),0) FROM tx WHERE label='Groceries' AND "
                     "type='purchase' AND amount<0 AND d>=? AND d<=?", (frm, to)).fetchone()[0]
    return float(s or 0.0) / 3.0


_DS = {"key": None, "idx": {}}


def dataset_path():
    p = os.environ.get("SVINKKI_RECEIPTS_FILE")
    if p:
        return Path(p)
    from . import db as _db
    return Path(_db.data_db_path()).parent / "receipts" / "receipts.json"


def _dataset_for(habit_seed):
    """{tx_id: stored receipt} for this customer if the dataset file holds them, else None.
    Cached with the file's mtime and size."""
    if habit_seed is None:
        return None
    try:
        path = dataset_path()
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
        if _DS["key"] != key:
            data = json.loads(path.read_text(encoding="utf-8"))
            _DS["idx"] = {cid: {r["tx_id"]: r for r in (c.get("receipts") or [])}
                          for cid, c in (data.get("customers") or {}).items()}
            _DS["key"] = key
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        _DS["key"], _DS["idx"] = None, {}
        return None
    return _DS["idx"].get(str(habit_seed))


def _receipts_in(conn, today, frm, to, habit_seed):
    """All receipts (grocery and fuel) for the payments visible in `conn` inside the period,
    newest first. Stored dataset receipts are used when available, else generated."""
    mg = _monthly_grocery(conn, today)
    ds = _dataset_for(habit_seed)
    out = []
    for r in _rows(conn, frm, to):
        rc = None
        if ds:
            st = ds.get(r["id"])
            if st and st.get("ts") == r["ts"] and abs(st.get("total", 0) + float(r["amount"])) < 0.005:
                rc = dict(st)
                rc["bonus"] = _bonus(rc.get("kind", "grocery"), rc["total"], mg)
        if rc is None:
            rc = receipt_for(r, habit_seed=habit_seed, monthly_grocery=mg)
        if rc:
            out.append(rc)
    return out


def _evidence(frm, to, grocery=True, fuel=False):
    ev = []
    if grocery:
        ev.append(ins._disp_evidence("Groceries", frm, to, "Grocery purchases"))
    if fuel:
        ev.append(ins._disp_evidence("Fuel", frm, to, "Fuel purchases"))
    return ev


def _is_fuel(rc):
    return rc.get("kind") == "fuel"


# --------------------------------------------------------------------------- receipts

def receipts(conn, today, period="last_month", habit_seed=None, limit=20):
    frm, to = ins.period(today, period)
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20
    allr = _receipts_in(conn, today, frm, to, habit_seed)
    gc = sum(int(round(r["total"] * 100)) for r in allr if not _is_fuel(r))
    fc = sum(int(round(r["total"] * 100)) for r in allr if _is_fuel(r))
    n_f = sum(1 for r in allr if _is_fuel(r))
    missing = _without_receipt(conn, frm, to)
    res = {
        "period": {"from": frm, "to": to, "label": ins.human_period(frm, to, today)},
        "label": DEMO_LABEL,
        "count": len(allr), "shown": min(limit, len(allr)), "total": round((gc + fc) / 100.0, 2),
        "grocery_count": len(allr) - n_f, "grocery_total": round(gc / 100.0, 2),
        "fuel_count": n_f, "fuel_total": round(fc / 100.0, 2),
        "receipts": allr[:limit],
        "note": SIM_NOTE,
        "explain": ("Each grocery and fuel payment became a demo receipt whose lines add up to the payment. "
                    "Fuel is counted separately from groceries.%s" % _without_receipt_text(missing)),
        "evidence": _evidence(frm, to, True, True),
    }
    if missing:
        res["without_receipt"] = {k: {"count": v[0], "total": v[1]} for k, v in missing.items()}
    return res


# --------------------------------------------------------------------------- insights

def _aggregate(rcs, skip=()):
    """Cent-exact aggregates: by group and by product. Lines named in `skip` are left out."""
    groups, prods = {}, {}
    for rc in rcs:
        seen_g, seen_p = set(), set()
        for ln in rc["lines"]:
            if ln["name"] in skip:
                continue
            c = int(round(ln["line_total"] * 100))
            g = groups.setdefault(ln["group"], {"c": 0, "items": 0, "tx": set()})
            g["c"] += c
            g["items"] += 1
            g["tx"].add(rc["tx_id"])
            p = prods.setdefault(ln["name"], {"c": 0, "qty": 0.0, "tx": set(), "group": ln["group"],
                                              "unit": ln["unit"]})
            p["c"] += c
            p["qty"] += ln["qty"]
            p["tx"].add(rc["tx_id"])
    return groups, prods


EXTRA_FLOOR = 5.0      # euros a month a product group must reach to be mentioned as an extra
# (group, receipts needed, sentence)
_EXTRA_LINES = [
    ("energy_drinks", 3, "You bought energy drinks %(n)d times: about %(m)s a month, %(y)s a year."),
    ("alcohol_mild", 4, "Beer and cider showed up on %(n)d receipts: about %(m)s a month, %(y)s a year."),
    ("snacks_sweets", 5, "Snacks and sweets were on %(n)d receipts: about %(m)s a month, %(y)s a year."),
    ("soft_drinks", 4, "Soft drinks were on %(n)d receipts: about %(m)s a month, %(y)s a year."),
]


def receipt_insights(conn, today, period="last_3_months", habit_seed=None):
    frm, to = ins.period(today, period)
    months = _months_in(period, frm, to)
    every = _receipts_in(conn, today, frm, to, habit_seed)
    rcs = [r for r in every if not _is_fuel(r)]
    frs = [r for r in every if _is_fuel(r)]
    total_c = sum(int(round(r["total"] * 100)) for r in rcs)
    total = round(total_c / 100.0, 2)
    groups, _all_prods = _aggregate(rcs)
    # the balancing lines (a plastic bag or a deposit that takes up the last cents) are real money in the
    # group totals, but they are never a product the customer chose, so they stay out of the top lists
    groups_top, prods = _aggregate(rcs, skip=_REMAINDER)
    fuel_block = _fuel_block(frs, months)
    missing = _without_receipt(conn, frm, to)
    if missing.get("Fuel"):
        fuel_block["other_payments"] = {"count": missing["Fuel"][0], "total": missing["Fuel"][1]}

    by_group = []
    for g, v in sorted(groups.items(), key=lambda kv: -kv[1]["c"]):
        by_group.append({"group": g, "name": GROUP_NAMES.get(g, g), "total": round(v["c"] / 100.0, 2),
                         "share": round(v["c"] / total_c, 3) if total_c else 0.0, "items": v["items"]})
    top = []
    for name, v in sorted(prods.items(), key=lambda kv: (-len(kv[1]["tx"]), -kv[1]["c"], kv[0]))[:10]:
        t = round(v["c"] / 100.0, 2)
        top.append({"name": name, "times": len(v["tx"]),
                    "qty": int(v["qty"]) if v["unit"] == "kpl" else round(v["qty"], 2),
                    "total": t, "yearly": round(t * 12.0 / months, 2)})
    tc = sum(groups[g]["c"] for g in TREAT_GROUPS if g in groups)
    treats = {"total": round(tc / 100.0, 2), "share": round(tc / total_c, 3) if total_c else 0.0,
              "monthly": round(tc / 100.0 / months, 2), "yearly": round(tc / 100.0 * 12.0 / months, 2),
              "groups": [GROUP_NAMES[g] for g in TREAT_GROUPS]}

    when = _phrase(period, frm, to, today)
    pct = "{:.0f}%".format
    hl = []
    if rcs:
        # 1. the product bought most often, 2. the biggest group, then the extras the customer may care about
        if top:
            t0 = top[0]
            hl.append("You buy %s most often: %d time%s %s, %s in total."
                      % (t0["name"], t0["times"], "" if t0["times"] == 1 else "s", when, _eur(t0["total"])))
        top_groups = sorted(groups_top.items(), key=lambda kv: (-kv[1]["c"], kv[0]))
        if top_groups:
            g, gv = top_groups[0]
            hl.append("Your biggest grocery group is %s: %s, %s of the total."
                      % (GROUP_NAMES.get(g, g).lower(), _eur(gv["c"] / 100.0),
                         pct(100 * gv["c"] / total_c) if total_c else "0%"))
        # the extras are ranked by euros a month (biggest first) and only mentioned from EXTRA_FLOOR a month
        cand = []
        for g, min_receipts, text in _EXTRA_LINES:
            v = groups.get(g)
            if not v or len(v["tx"]) < min_receipts:
                continue
            gt = v["c"] / 100.0
            if gt / months < EXTRA_FLOOR:
                continue
            cand.append((gt / months, g, text % {"n": len(v["tx"]), "m": _eur0(gt / months),
                                                  "y": _eur0(gt * 12.0 / months)}))
        cand.sort(key=lambda c: (-c[0], c[1]))
        extras = [c[2] for c in cand]
        if treats["monthly"] >= EXTRA_FLOOR and len(cand) < 2:
            extras.append("Snacks, soft drinks, energy drinks and beer or cider together came to about "
                          "%s a month (%s of grocery spending)." % (_eur0(treats["monthly"]), pct(100 * treats["share"])))
        hl += extras
        hl = hl[:4]
        if len(hl) < 2 and top:
            hl.append("There were %d grocery receipts %s, %s in total." % (len(rcs), when, _eur(total)))
    else:
        hl = ["There are no grocery purchases %s to look at." % when]
    if fuel_block["fills"]:
        fb = fuel_block
        line = ("You filled up %s: about %.0f litres for %s, roughly %s a month at an average of %s a litre."
                % ("once" if fb["fills"] == 1 else "%d times" % fb["fills"], fb["litres"],
                   _eur(fb["total"]), _eur0(fb["monthly"]), _eur(fb["avg_price_per_litre"])))
        if fuel_block.get("other_payments"):
            op = fuel_block["other_payments"]
            line += (" That counts card purchases at the station only; %d other payment%s labelled fuel (%s) "
                     "%s not on a receipt." % (op["count"], "" if op["count"] == 1 else "s", _eur(op["total"]),
                                               "is" if op["count"] == 1 else "are"))
        hl = hl[:3] + [line]

    bonus_total = round(sum(r["bonus"]["amount"] for r in rcs), 2)
    return {
        "period": {"from": frm, "to": to, "label": ins.human_period(frm, to, today), "months": round(months, 2)},
        "label": DEMO_LABEL,
        "receipt_count": len(rcs), "total": total, "by_group": by_group, "top_products": top,
        "treats": treats, "fuel": fuel_block, "highlights": hl,
        "bonus": {"estimated_total": bonus_total,
                  "note": "A purchase rebate that grows with monthly grocery spend, not your real Bonus balance."},
        "note": SIM_NOTE,
        "explain": ("Grocery receipts %s were summed by product group. Balancing lines such as a plastic bag or a "
                    "deposit count in the group totals but never as a top product or the biggest group. Fuel is "
                    "counted separately from groceries. Yearly figures scale the period to 12 months.%s"
                    % (when, _without_receipt_text(missing) if missing.get("Groceries") else "")),
        "evidence": _evidence(frm, to, True, bool(frs)),
    }


def _fuel_block(frs, months):
    """Fuel-station receipts: the fuel lines only (shop lines are reported as `shop_total`)."""
    fuel_c = litres = shop_c = 0
    litres = 0.0
    fills = 0
    types = {}
    for r in frs:
        for ln in r["lines"]:
            c = int(round(ln["line_total"] * 100))
            if ln["group"] == "fuel":
                fuel_c += c
                litres += ln["qty"]
            else:
                shop_c += c
        if r.get("fuel"):
            fills += 1
            types[r["fuel"]["type"]] = types.get(r["fuel"]["type"], 0) + 1
    t = fuel_c / 100.0
    return {
        "total": round(t, 2), "litres": round(litres, 2), "fills": fills,
        "avg_price_per_litre": round(t / litres, 3) if litres else 0.0,
        "monthly": round(t / months, 2), "yearly": round(t * 12.0 / months, 2),
        "fuel_type": max(types, key=types.get) if types else None,
        "shop_total": round(shop_c / 100.0, 2), "receipts": len(frs),
    }


# --------------------------------------------------------------------------- longer views

BIG_SHOP = 60.0          # euros: a shop this size or more is a "big shop"
SMALL_SHOP = 25.0        # euros: under this is a "small top-up"
HOME_COOK_SHARE = 0.4    # a home-cooked portion costs this share of a ready meal (illustrative)
_DAYS_PER_MONTH = 30.4375
_HABIT_GROUPS = ("alcohol_mild", "ready_meals", "soft_drinks", "energy_drinks", "snacks_sweets", "coffee_tea")
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                "October", "November", "December"]
_DAYPARTS = [("in the morning", 5, 10), ("around midday", 11, 13), ("in the afternoon", 14, 17),
             ("in the evening", 18, 21), ("late at night", 22, 28)]       # hours; 22-28 wraps past midnight


def _first_day(conn):
    try:
        r = conn.execute("SELECT MIN(d) FROM tx").fetchone()
    except sqlite3.Error:
        return None
    return r[0] if r and r[0] else None


def _months_between(frm, to, first, nominal=None):
    """Months in [frm, to]. The nominal count is used unless the customer's data starts well after `frm`;
    then only the months with data count. 0.0 when the data starts after `to`."""
    a, b = ins._d(frm), ins._d(to)
    if first:
        f = ins._d(first)
        if f > b:
            return 0.0
        if nominal is None or f > a + timedelta(days=10):
            a = max(a, f)
            nominal = None
    if nominal:
        return float(nominal)
    return max(((b - a).days + 1) / _DAYS_PER_MONTH, 0.25)


def _span(conn, today, period, whole_months=False):
    """The period, how many months of data it holds, and the equal period just before it (or None).
    With `whole_months`, "last N months" means the N last FULL calendar months, as trends.category_story counts."""
    t = ins._d(today)
    first = _first_day(conn)
    key = _key(period)
    whole_when = None
    m = re.fullmatch(r"last_(\d{1,2})_months", key)
    if m and int(m.group(1)) >= 1 and whole_months:
        n = int(m.group(1))
        end = ins._month_end(t)
        to = t if t == end else ins._month_start(t) - timedelta(days=1)
        frm = ins._add_months(ins._month_start(to), -(n - 1))
        p_to = frm - timedelta(days=1)
        p_frm = ins._add_months(frm, -n)
        nominal = n
        whole_when = "over the last %d full months (%s to %s)" % (n, frm.strftime("%b %Y"), to.strftime("%b %Y"))
    elif m and int(m.group(1)) >= 1:
        n = int(m.group(1))
        frm = ins._add_months(t, -n) + timedelta(days=1)
        to = t
        p_to = ins._add_months(t, -n)
        p_frm = ins._add_months(t, -2 * n) + timedelta(days=1)
        nominal = n
    else:
        f, e = ins.period(today, period)
        frm, to = ins._d(f), ins._d(e)
        nominal = int(_PERIOD_MONTHS[key]) if _PERIOD_MONTHS.get(key) else None
        days = (to - frm).days + 1
        p_to = frm - timedelta(days=1)
        p_frm = p_to - timedelta(days=days - 1)
    months = _months_between(frm, to, first, nominal) or 1.0     # no data at all: never divide by zero
    p_months = _months_between(p_frm, p_to, first, nominal)
    return {"frm": frm.isoformat(), "to": to.isoformat(), "months": months,
            "prev": ({"frm": p_frm.isoformat(), "to": p_to.isoformat(), "months": p_months}
                     if p_months > 0 else None),
            "when": (whole_when if whole_months and m and int(m.group(1)) >= 1
                     else _phrase(period, frm.isoformat(), to.isoformat(), today))}


def _rate(x):
    """A count per month for a sentence: one decimal, no trailing zero."""
    x = round(float(x), 1)
    return "%d" % x if x == int(x) else "%.1f" % x


def _month_label(ym, today):
    y, m = int(ym[:4]), int(ym[5:7])
    name = _MONTH_NAMES[m - 1]
    return name if y == ins._d(today).year else "%s %d" % (name, y)


def _grocery_payments(conn, frm, to):
    cur = conn.execute(
        "SELECT d, ts, -amount FROM tx WHERE label = 'Groceries' AND type = 'purchase' AND amount < 0 "
        "AND d >= ? AND d <= ? ORDER BY ts, id", (frm, to))
    return [(r[0], str(r[1] or ""), float(r[2])) for r in cur.fetchall()]


def _group_stats(rcs):
    """Cent-exact per group over grocery receipts: cents, lines, units (counted items), receipts."""
    out = {}
    for rc in rcs:
        for ln in rc["lines"]:
            g = out.setdefault(ln["group"], {"c": 0, "lines": 0, "units": 0.0, "tx": set()})
            g["c"] += int(round(ln["line_total"] * 100))
            g["lines"] += 1
            if ln["unit"] == "kpl":
                g["units"] += ln["qty"]
            g["tx"].add(rc["tx_id"])
    return out


def _empty_text(when):
    return "There are no grocery purchases %s to look at." % when


def receipt_trends(conn, today, period="last_12_months", habit_seed=None):
    """Product groups over 12 or 24 months on the simulated receipts: euros, euros a month, receipts that
    hold the group, half-year euros a month, fuel litres. Never says a share is rising: the simulated mix is
    fixed per customer, only the grocery total moves."""
    key = _key(period)
    if key not in ("last_12_months", "last_24_months"):
        raise ValueError("unknown period: %s" % period)
    sp = _span(conn, today, key)
    frm, to, months, when = sp["frm"], sp["to"], sp["months"], sp["when"]
    every = _receipts_in(conn, today, frm, to, habit_seed)
    rcs = [r for r in every if not _is_fuel(r)]
    frs = [r for r in every if _is_fuel(r)]
    total_c = sum(int(round(r["total"] * 100)) for r in rcs)
    stats = _group_stats(rcs)
    fuel_block = _fuel_block(frs, months)
    missing = _without_receipt(conn, frm, to)

    groups, small_c, small_n = [], 0, 0
    for g, v in sorted(stats.items(), key=lambda kv: (-kv[1]["c"], kv[0])):
        t = v["c"] / 100.0
        if months and t / months >= EXTRA_FLOOR:
            groups.append({"group": g, "name": GROUP_NAMES.get(g, g), "total": round(t, 2),
                           "monthly": round(t / months, 2), "receipts": len(v["tx"]), "items": v["lines"],
                           "units": int(round(v["units"])), "share": round(v["c"] / total_c, 3)})
        else:
            small_c += v["c"]
            small_n += 1
    listed = {g["group"] for g in groups}

    # half years, oldest first: euros a month per listed group and fuel litres
    first = _first_day(conn)
    halves = []
    t0 = ins._d(to)
    n_h = 2 if key == "last_12_months" else 4
    for i in range(n_h):
        h_to = ins._add_months(t0, -6 * (n_h - 1 - i))
        h_frm = ins._add_months(t0, -6 * (n_h - i)) + timedelta(days=1)
        hm = _months_between(h_frm, h_to, first, 6)
        if hm <= 0:
            continue
        a, b = h_frm.isoformat(), h_to.isoformat()
        h_g = [r for r in rcs if a <= str(r["d"]) <= b]
        h_f = [r for r in frs if a <= str(r["d"]) <= b]
        hs = _group_stats(h_g)
        gc = sum(int(round(r["total"] * 100)) for r in h_g)
        fb = _fuel_block(h_f, hm)
        halves.append({"from": a, "to": b, "months": round(hm, 2),
                       "grocery_monthly": round(gc / 100.0 / hm, 2),
                       "groups": {GROUP_NAMES.get(g, g): round(hs[g]["c"] / 100.0 / hm, 2)
                                  for g in sorted(listed) if g in hs},
                       "fuel_litres": fb["litres"], "fuel_monthly": fb["monthly"]})

    fuel = {"litres": fuel_block["litres"], "fills": fuel_block["fills"], "total": fuel_block["total"],
            "avg_price_per_litre": fuel_block["avg_price_per_litre"], "monthly": fuel_block["monthly"],
            "fuel_type": fuel_block["fuel_type"]}

    hl = []
    if rcs:
        total = total_c / 100.0
        hl.append("On the demo receipts your grocery payments came to %s %s, about %s a month, on %d receipts."
                  % (_eur(total), when, _eur0(total / months), len(rcs)))
        habit = [g for g in groups if g["group"] in _HABIT_GROUPS]
        habit.sort(key=lambda g: (-g["monthly"], g["group"]))
        for g in habit[:3]:
            hl.append("%s came to about %s a month (%s %s), on %d receipts, %s of your grocery spending."
                      % (g["name"], _eur0(g["monthly"]), _eur(g["total"]), when, g["receipts"],
                         "{:.0f}%".format(100 * g["share"])))
        if len(halves) >= 2 and halves[0]["grocery_monthly"] > 0 and halves[-1]["grocery_monthly"] > 0:
            hl.append("Your grocery spending ran about %s a month in the first 6 months of that time and about %s "
                      "a month in the latest 6."
                      % (_eur0(halves[0]["grocery_monthly"]), _eur0(halves[-1]["grocery_monthly"])))
    else:
        hl = []
    if fuel_block["fills"]:
        fb = fuel_block
        hl.append("You filled up %s %s: about %.0f litres for %s, an average of %s a litre, roughly %s a month."
                  % ("once" if fb["fills"] == 1 else "%d times" % fb["fills"], when, fb["litres"],
                     _eur(fb["total"]), _eur(fb["avg_price_per_litre"]), _eur0(fb["monthly"])))
    text = " ".join(hl) + (" These come from simulated demo receipts." if hl else _empty_text(when))
    return {
        "period": {"from": frm, "to": to, "label": when, "months": round(months, 2)},
        "label": DEMO_LABEL,
        "receipt_count": len(rcs), "total": round(total_c / 100.0, 2),
        "groups": groups,
        "other_groups": {"count": small_n, "total": round(small_c / 100.0, 2),
                         "monthly": round(small_c / 100.0 / months, 2) if months else 0.0},
        "half_years": halves, "fuel": fuel,
        "highlights": hl, "text": text, "note": SIM_NOTE,
        "explain": ("Grocery receipts %s were summed by product group; groups under %s a month are lumped together "
                    "as other groups. Half years show euros a month, which follow your grocery payments. The lines "
                    "are simulated, so this shows how much goes to each group, not whether a share is changing.%s"
                    % (when, _eur0(EXTRA_FLOOR), _without_receipt_text(missing) if missing.get("Groceries") else "")),
        "evidence": _evidence(frm, to, True, bool(frs)),
    }


def _daypart(ts):
    try:
        h = int(str(ts)[11:13])
    except ValueError:
        return None
    if h < 5:
        h += 24
    for name, lo, hi in _DAYPARTS:
        if lo <= h <= hi:
            return name
    return None


def _full_months(frm, to, first):
    """YYYY-MM keys of the calendar months that lie wholly inside [frm, to] and after the data starts."""
    a, b = ins._d(frm), ins._d(to)
    if first:
        a = max(a, ins._d(first))
    cur = a if a.day == 1 else ins._add_months(ins._month_start(a), 1)
    out = []
    while ins._month_end(cur) <= b:
        out.append(cur.strftime("%Y-%m"))
        cur = ins._add_months(cur, 1)
    return out


def basket_profile(conn, today, period="last_12_months", habit_seed=None):
    """How and when the customer shops, from the grocery PAYMENTS themselves (no simulated lines)."""
    sp = _span(conn, today, period, whole_months=True)
    frm, to, months, when = sp["frm"], sp["to"], sp["months"], sp["when"]
    pay = _grocery_payments(conn, frm, to)
    base = {"period": {"from": frm, "to": to, "label": when, "months": round(months, 2)},
            "basis": "Real payments labelled groceries, not the simulated receipt lines.",
            "evidence": _evidence(frm, to)}
    n = len(pay)
    if n == 0:
        base.update({"trips": 0, "highlights": [], "text": _empty_text(when),
                     "explain": "No grocery payments in the period."})
        return base
    total = round(sum(a for _, _, a in pay), 2)
    avg = total / n
    per_month = n / months
    big = [a for _, _, a in pay if a >= BIG_SHOP]
    small = [a for _, _, a in pay if a < SMALL_SHOP]
    mid = n - len(big) - len(small)
    wd = {}
    dp = {}
    for d, ts, _a in pay:
        w = ins._d(d).weekday()
        wd[w] = wd.get(w, 0) + 1
        p = _daypart(ts)
        if p:
            dp[p] = dp.get(p, 0) + 1
    top_w = min(wd.items(), key=lambda kv: (-kv[1], kv[0]))
    order = [x[0] for x in _DAYPARTS]
    top_p = min(dp.items(), key=lambda kv: (-kv[1], order.index(kv[0]))) if dp else None
    biggest = max(pay, key=lambda x: (x[2], x[0]))
    # months with the most and fewest trips, over whole calendar months only
    counts = {}
    for d, _ts, _a in pay:
        counts[d[:7]] = counts.get(d[:7], 0) + 1
    full = _full_months(frm, to, _first_day(conn))
    months_info = None
    if len(full) >= 3:
        series = [(counts.get(m, 0), m) for m in full]
        most = max(series, key=lambda x: (x[0], x[1]))
        fewest = min(series, key=lambda x: (x[0], x[1]))
        if most[0] != fewest[0]:
            months_info = {"most": {"month": most[1], "label": _month_label(most[1], today), "trips": most[0]},
                           "fewest": {"month": fewest[1], "label": _month_label(fewest[1], today),
                                      "trips": fewest[0]}}

    # change against the equal period before
    change = None
    pv = sp["prev"]
    if pv:
        prev = _grocery_payments(conn, pv["frm"], pv["to"])
        if len(prev) >= 3:
            p_total = sum(a for _, _, a in prev)
            p_avg = p_total / len(prev)
            p_rate = len(prev) / pv["months"]
            t_pct = (per_month - p_rate) / p_rate
            b_pct = (avg - p_avg) / p_avg
            if abs(t_pct) >= 0.10 and abs(b_pct) < 0.10:
                driver = "trips"
            elif abs(b_pct) >= 0.10 and abs(t_pct) < 0.10:
                driver = "basket"
            elif abs(t_pct) < 0.10 and abs(b_pct) < 0.10:
                driver = "none"
            else:
                driver = "both"
            change = {"trips_per_month_before": round(p_rate, 2), "average_basket_before": round(p_avg, 2),
                      "monthly_before": round(p_total / pv["months"], 2),
                      "trips_change_pct": round(100 * t_pct), "basket_change_pct": round(100 * b_pct),
                      "months_before": round(pv["months"], 2), "driver": driver}

    hl = []
    hl.append("You made about %s grocery trips a month %s, with an average basket of %s."
              % (_rate(per_month), when, _eur(avg)))
    if change:
        c = change
        mb = max(1, int(round(c["months_before"])))
        if c["driver"] == "trips":
            hl.append("That is %s than the %s trips a month in the %d months before, while the average basket stayed "
                      "near %s (%s before), so your grocery spending moved with how often you shop, not with bigger "
                      "baskets: about %s a month now, %s before."
                      % ("more" if per_month > c["trips_per_month_before"] else "fewer",
                         _rate(c["trips_per_month_before"]), mb, _eur(avg), _eur(c["average_basket_before"]),
                         _eur0(total / months), _eur0(c["monthly_before"])))
        elif c["driver"] == "basket":
            hl.append("Your trips stayed near %s a month (%s before), but the average basket went from %s to %s."
                      % (_rate(per_month), _rate(c["trips_per_month_before"]), _eur(c["average_basket_before"]),
                         _eur(avg)))
        elif c["driver"] == "both":
            hl.append("Before, you made %s trips a month with a basket of %s; now it is %s trips and %s."
                      % (_rate(c["trips_per_month_before"]), _eur(c["average_basket_before"]), _rate(per_month),
                         _eur(avg)))
        else:
            hl.append("That is about the same as the %d months before: %s trips a month and a %s basket."
                      % (mb, _rate(c["trips_per_month_before"]), _eur(c["average_basket_before"])))
    pct = "{:.0f}%".format
    hl.append("%s of your trips were big shops of %s or more, and %s were small top-ups under %s."
              % (pct(100.0 * len(big) / n), _eur(BIG_SHOP), pct(100.0 * len(small) / n), _eur(SMALL_SHOP)))
    when_txt = "Most of your trips are on %ss (%s of them)" % (_WEEKDAYS[top_w[0]], pct(100.0 * top_w[1] / n))
    if top_p:
        when_txt += ", usually %s (%s)" % (top_p[0], pct(100.0 * top_p[1] / sum(dp.values())))
    hl.append(when_txt + ".")
    hl.append("Your most expensive shop was %s on %s." % (_eur(biggest[2]), ins.human_range(biggest[0], biggest[0],
                                                                                           today)))
    if months_info:
        hl.append("%s was your busiest month with %d trips and %s your quietest with %d."
                  % (months_info["most"]["label"], months_info["most"]["trips"], months_info["fewest"]["label"],
                     months_info["fewest"]["trips"]))
    base.update({
        "trips": n, "trips_per_month": round(per_month, 2), "total": total, "monthly": round(total / months, 2),
        "average_basket": round(avg, 2),
        "big_shops": {"count": len(big), "share": round(len(big) / n, 3), "from": BIG_SHOP},
        "small_topups": {"count": len(small), "share": round(len(small) / n, 3), "under": SMALL_SHOP},
        "middle_shops": mid,
        "busiest_weekday": {"name": _WEEKDAYS[top_w[0]], "trips": top_w[1], "share": round(top_w[1] / n, 3)},
        "weekday_trips": {_WEEKDAYS[k]: v for k, v in sorted(wd.items())},
        "busiest_time": ({"name": top_p[0], "trips": top_p[1], "share": round(top_p[1] / sum(dp.values()), 3)}
                         if top_p else None),
        "most_expensive": {"amount": round(biggest[2], 2), "d": biggest[0]},
        "months": months_info, "change": change, "highlights": hl, "text": " ".join(hl),
        "explain": ("Counted the grocery payments %s: a big shop is %s or more, a small top-up is under %s. Trips a "
                    "month divide by the months with data. The change compares with the same length of time just "
                    "before." % (when, _eur(BIG_SHOP), _eur(SMALL_SHOP))),
    })
    return base


def cut_ideas(conn, today, period="last_3_months", habit_seed=None):
    """Two to four concrete ideas for spending less on groceries, from the customer's own receipts, ranked by
    what they would free up each month. Group-level only; the simulated lines carry no real prices or brands."""
    sp = _span(conn, today, period)
    frm, to, months, when = sp["frm"], sp["to"], sp["months"], sp["when"]
    rcs = [r for r in _receipts_in(conn, today, frm, to, habit_seed) if not _is_fuel(r)]
    base = {"period": {"from": frm, "to": to, "label": when, "months": round(months, 2)}, "label": DEMO_LABEL,
            "receipt_count": len(rcs), "note": SIM_NOTE, "evidence": _evidence(frm, to)}
    if len(rcs) < 3 or not months:
        base.update({"ideas": [], "highlights": [], "text": _empty_text(when),
                     "explain": "Too few grocery receipts in the period for an idea."})
        return base
    st = _group_stats(rcs)

    def monthly(*groups):
        return sum(st[g]["c"] for g in groups if g in st) / 100.0 / months

    ideas = []
    # ready meals: cook half of them at home
    if "ready_meals" in st:
        now = monthly("ready_meals")
        cnt = st["ready_meals"]["units"] / months
        saved = now * 0.5 * (1.0 - HOME_COOK_SHARE)
        ideas.append({
            "id": "ready_meals", "title": "Cook some ready meals at home",
            "detail": ("You buy about %s ready meals a month for about %s. Cooking half of them at home would save "
                       "about %s a month." % (_rate(cnt), _eur0(now), _eur0(saved))),
            "monthly_now": now, "saved_monthly": saved,
            "basis": ("Assumes half of your ready meals are cooked instead and a home-cooked portion costs %d%% of a "
                      "ready meal. Based on simulated receipt lines." % round(100 * HOME_COOK_SHARE))})
    # soft and energy drinks: half as many
    drinks = monthly("soft_drinks", "energy_drinks")
    if drinks:
        ideas.append({
            "id": "soft_energy_drinks", "title": "Half as many soft and energy drinks",
            "detail": ("Soft and energy drinks come to about %s a month. Having half as many would free up about %s a "
                       "month." % (_eur0(drinks), _eur0(drinks / 2.0))),
            "monthly_now": drinks, "saved_monthly": drinks / 2.0,
            "basis": "Assumes half as many drinks at the same prices. Based on simulated receipt lines."})
    # snacks and sweets: half as many
    snacks = monthly("snacks_sweets")
    if snacks:
        ideas.append({
            "id": "snacks_sweets", "title": "Half as many snacks and sweets",
            "detail": ("Snacks and sweets come to about %s a month. Having half as many would free up about %s a "
                       "month." % (_eur0(snacks), _eur0(snacks / 2.0))),
            "monthly_now": snacks, "saved_monthly": snacks / 2.0,
            "basis": "Assumes half as many at the same prices. Based on simulated receipt lines."})
    # beer and cider: one purchase fewer a week (at most half of what is bought)
    if "alcohol_mild" in st and st["alcohol_mild"]["lines"] >= 2:
        s = st["alcohol_mild"]
        now = monthly("alcohol_mild")
        lines_pm = s["lines"] / months
        avg_line = s["c"] / 100.0 / s["lines"]
        fewer = min(52.0 / 12.0, lines_pm / 2.0)
        saved = avg_line * fewer
        if fewer >= 52.0 / 12.0 - 1e-9:
            title, what = "One beer or cider purchase fewer a week", "One pack fewer a week"
        else:
            title, what = "Half as many beer and cider purchases", "Half as many purchases"
        ideas.append({
            "id": "beer_cider", "title": title,
            "detail": ("Beer and cider come to about %s a month, with an average purchase of %s. %s would free up "
                       "about %s a month." % (_eur0(now), _eur(avg_line), what, _eur0(saved))),
            "monthly_now": now, "saved_monthly": saved,
            "basis": ("Your own average beer or cider line on a receipt (%s) times %s fewer purchases a month. "
                      "Based on simulated receipt lines." % (_eur(avg_line), _rate(fewer)))})
    # small top-up trips: one fewer a week
    pay = _grocery_payments(conn, frm, to)
    small = [a for _, _, a in pay if a < SMALL_SHOP]
    if small and len(small) / months >= 6.0:
        avg_small = sum(small) / len(small)
        saved = avg_small * 52.0 / 12.0
        now = sum(small) / months
        ideas.append({
            "id": "top_up_trips", "title": "One top-up trip fewer a week",
            "detail": ("You make about %s small top-up trips (under %s) a month, about %s in all. One trip fewer a week, "
                       "at your average top-up of %s, is about %s a month."
                       % (_rate(len(small) / months), _eur(SMALL_SHOP), _eur0(now), _eur(avg_small), _eur0(saved))),
            "monthly_now": now, "saved_monthly": saved,
            "basis": "Your average small top-up times about 4.3 weeks a month; assumes the shop is skipped, not moved "
                     "to another trip. From your real payments."})
    ideas = [i for i in ideas if i["saved_monthly"] >= EXTRA_FLOOR]
    ideas.sort(key=lambda i: (-i["saved_monthly"], i["id"]))
    ideas = ideas[:4]
    for i in ideas:
        i["monthly_now"] = round(i["monthly_now"], 2)
        i["saved_monthly"] = round(i["saved_monthly"], 2)
    hl = [i["detail"] for i in ideas]
    base.update({
        "ideas": ideas, "highlights": hl,
        "text": (" ".join(hl) + " These come from simulated demo receipts.") if hl else
                "I found nothing on your receipts %s that would free up %s a month or more." % (when, _eur0(EXTRA_FLOOR)),
        "explain": ("Each idea is a simple what-if on the simulated receipt lines %s, ranked by what it would free up "
                    "each month. Ideas under %s a month are left out." % (when, _eur0(EXTRA_FLOOR)))})
    return base


# --------------------------------------------------------------------------- product habit

# (keywords, display name, kind, groups or None, name substrings or None, unit noun)
_ALIASES = [
    (("fuel", "petrol", "gasoline", "diesel", "bensa", "bensiini", "polttoaine", "tankkaus", "tankkaa"),
     "fuel", "group", {"fuel"}, None, "litres"),
    (("energy drink", "energiajuoma", "energy", "red bull", "monster"), "energy drinks", "group",
     {"energy_drinks"}, None, "cans"),
    (("coffee", "kahvi", "espresso"), "coffee", "product", {"coffee_tea"}, ("kahvi",), "packs"),
    (("tea", "tee"), "tea", "product", {"coffee_tea"}, ("tee",), "packs"),
    (("beer", "olut", "cider", "siideri", "alcohol", "alkoholi", "booze"), "beer and cider", "group",
     {"alcohol_mild"}, None, "cans and bottles"),
    (("sweets", "candy", "karkit", "karkki", "chocolate", "suklaa", "snack", "chips", "naposteltav",
      "herkut"), "sweets and snacks", "group", {"snacks_sweets"}, None, "items"),
    (("soft drink", "soda", "limsa", "limu", "cola", "virvoitusjuoma", "juice", "mehu"),
     "soft drinks", "group", {"soft_drinks"}, None, "bottles and cans"),
    (("milk", "maito"), "milk", "product", {"dairy"}, ("maito",), "items"),
    (("egg", "muna"), "eggs", "product", {"dairy"}, ("muna",), "packs"),
    (("banana", "banaani"), "bananas", "product", {"fruit_veg"}, ("banaani",), "items"),
    (("bread", "leipä", "leipa"), "bread", "group", {"bread"}, None, "items"),
    (("meat", "liha", "fish", "kala"), "meat and fish", "group", {"meat_fish"}, None, "items"),
    (("fruit", "vegetable", "hedelmä", "hedelma", "vihannes", "kasvikset"), "fruit and vegetables",
     "group", {"fruit_veg"}, None, "items"),
    (("frozen", "pakaste", "pizza"), "frozen food", "group", {"frozen"}, None, "items"),
    (("ready meal", "valmisruoka", "valmisateria"), "ready meals", "group", {"ready_meals"}, None,
     "items"),
    (("cleaning", "household", "kotitalous"), "household items", "group", {"household"}, None,
     "items"),
    (("dairy", "maitotuote", "cheese", "juusto", "yogurt", "jogurtti"), "dairy", "group", {"dairy"},
     None, "items"),
]


def _match_query(query):
    q = str(query or "").lower().strip()
    best = None
    for al in _ALIASES:
        for kw in al[0]:
            hit = re.search(r"\b" + re.escape(kw), q) if len(kw) <= 4 else (kw in q)
            if hit and (best is None or len(kw) > best[0]):
                best = (len(kw), al)
    if best:
        _, al = best
        return {"name": al[1], "kind": al[2], "groups": al[3], "subs": al[4], "noun": al[5]}
    for g, nm in GROUP_NAMES.items():
        if q and (q == g or q == nm.lower()):
            return {"name": nm.lower(), "kind": "group", "groups": {g}, "subs": None, "noun": "items"}
    toks = [t for t in re.split(r"[^\wäöå]+", q) if len(t) >= 4]
    for t in toks:
        hits = [p for p in CATALOGUE if t in p["name"].lower()]
        if hits:
            return {"name": t, "kind": "product", "groups": None, "subs": (t,), "noun": "items"}
    return None


def _line_matches(ln, m):
    if m["groups"] is not None and ln["group"] not in m["groups"]:
        return False
    if m["subs"] is not None:
        nm = ln["name"].lower()
        return any(s in nm for s in m["subs"])
    return True


def _qty_text(q, noun):
    q = round(q, 2)
    s = "%d" % q if abs(q - round(q)) < 1e-9 else "%.2f" % q
    if q == 1:
        noun = {"packs": "pack", "cans": "can", "litres": "litre", "items": "item",
                "cans and bottles": "can or bottle", "bottles and cans": "bottle or can"}.get(noun, noun)
    return "%s %s" % (s, noun)


def product_habit(conn, today, query, period="last_3_months", habit_seed=None):
    frm, to = ins.period(today, period)
    months = _months_in(period, frm, to)
    base = {"query": str(query), "note": SIM_NOTE, "evidence": _evidence(frm, to)}
    m = _match_query(query)
    fuel_q = bool(m and m["groups"] == {"fuel"})
    if m is None:
        base.update({
            "matched": None, "times": 0, "qty": 0, "total": 0.0, "monthly": 0.0, "yearly": 0.0,
            "per_purchase": 0.0, "receipts_with_it": [],
            "text": ("I could not match that to a product or group. You can ask about things like "
                     "energy drinks, coffee, beer, sweets, soft drinks, milk, bread or fuel."),
            "explain": "No product or product group matched the question, so nothing was counted.",
        })
        return base
    rcs = _receipts_in(conn, today, frm, to, habit_seed)
    times, qty, tc, ids = 0, 0.0, 0, []
    kinds = set()
    for rc in rcs:
        c, hit = 0, False
        for ln in rc["lines"]:
            if _line_matches(ln, m):
                hit = True
                c += int(round(ln["line_total"] * 100))
                qty += ln["qty"]
        if hit:
            kinds.add("fuel" if _is_fuel(rc) else "grocery")
            times += 1
            tc += c
            if len(ids) < 10:
                ids.append(rc["tx_id"])
    total = round(tc / 100.0, 2)
    monthly = round(total / months, 2)
    yearly = round(total * 12.0 / months, 2)
    per = round(total / times, 2) if times else 0.0
    ph = _phrase(period, frm, to, today)
    if times and fuel_q:
        n_txt = "once" if times == 1 else "%d times" % times
        text = ("You filled up %s %s: %s for %s. At this pace that is about %s a year."
                % (n_txt, ph, _qty_text(qty, "litres"), _eur(total), _eur0(yearly)))
    elif times:
        n_txt = "once" if times == 1 else "%d times" % times
        text = ("You bought %s %s %s, %s for %s. At this pace that is about %s a year."
                % (m["name"], n_txt, ph, _qty_text(qty, m["noun"]), _eur(total), _eur0(yearly)))
    else:
        text = "No %s showed up on your receipts %s." % (m["name"], ph)
    base["evidence"] = _evidence(frm, to, grocery=(not fuel_q) or "grocery" in kinds,
                                 fuel=fuel_q or "fuel" in kinds)
    base.update({
        "matched": {"kind": m["kind"], "name": m["name"]},
        "times": times, "qty": int(qty) if abs(qty - round(qty)) < 1e-9 else round(qty, 2),
        "total": total, "monthly": monthly, "yearly": yearly, "per_purchase": per, "text": text,
        "receipts_with_it": ids,
        "explain": ("Counted the receipt lines for %s %s. Yearly scales the period to "
                    "12 months, so it is a pace, not a forecast." % (m["name"], ph)),
        "label": DEMO_LABEL,
    })
    return base


# --------------------------------------------------------------------------- pasted receipts

_GROUP_KEYWORDS = [
    ("energy_drinks", ("energia", "energy", "red bull", "monster", "battery")),
    ("alcohol_mild", ("olut", "siideri", "lonkero", "karhu", "koff", "olvi", "lapin kulta", "sandels",
                      "beer", "cider")),
    ("coffee_tea", ("kahvi", "coffee", " tee", "tee ")),
    ("soft_drinks", ("cola", "limu", "limonadi", "pepsi", "fanta", "sprite", "mehu", "vesi", "jäätee",
                     "juoma")),
    ("snacks_sweets", ("suklaa", "karkki", "karkit", "lastu", "chips", "pähkin", "keksi", "salmiakki",
                       "popcorn", "patukka", "makeinen")),
    ("frozen", ("pakaste", "pizza", "jäätelö", "kalapuikko")),
    ("ready_meals", ("valmis", "lasagne", "keitto", "sushi", "grillikana", "pullat")),
    ("dairy", ("maito", "jogurtti", "rahka", "juusto", "voi ", "kerma", "kananmuna", "muna", "raejuusto",
               "levite")),
    ("bread", ("leipä", "sämpylä", "pulla", "patonki", "näkki", "ruispala")),
    ("meat_fish", ("liha", "kana", "broiler", "kinkku", "makkara", "nakki", "lohi", "kala", "silli",
                   "possu", "filee")),
    ("fruit_veg", ("banaani", "omena", "kurkku", "tomaatti", "peruna", "sipuli", "porkkana", "salaatti",
                   "appelsiini", "avokado", "paprika", "sitruuna", "rypäle")),
    ("pantry", ("pasta", "spagetti", "riisi", "jauho", "sokeri", "öljy", "mysli", "kaura", "hilloke",
                "hillo", "ketsuppi", "majoneesi", "murska", "kikherne", "pähkinävoi")),
    ("household", ("wc-", "talouspaperi", "pesuaine", "pyykin", "astianpesu", "roskapussi", "muovikassi",
                   "kassi", "paristo", "kynttilä", "leivinpaperi", "pantti")),
    ("hygiene", ("shampoo", "hammastahna", "saippua", "deodor", "hammasharja", "suihku")),
    ("baby", ("vaippa", "lastenruoka", "vauva")),
    ("pet", ("kissan", "koiran", "kissanhiekka")),
]

_TOTAL_RE = re.compile(r"^\s*(yhteensä|yhteensa|summa|loppusumma|maksettava|total|yht\.?)\b", re.I)
_SKIP_RE = re.compile(
    r"\b(alv|vero|veroton|netto|brutto|arvonlisävero|kortti|visa|mastercard|maestro|debit|credit|"
    r"maksettu|käteinen|kateinen|siirto|pankki|auth|tapahtuma|saatu|takaisin|tili|kuitti|kassa|"
    r"myyjä|asiakas|y-tunnus|puh|tel|bonusostot|bonus|bonuskortti|etu|korttinro|pin|vaihtoraha)\b",
    re.I)
_DATE_RE = re.compile(r"\b\d{1,2}[.:]\d{1,2}[.:]\d{2,4}\b|\b\d{1,2}:\d{2}\b")
_ITEM_RE = re.compile(r"^\s*(?P<name>.*?[^\W\d_].*?)\s+(?P<amt>-?\d+[.,]\d{2})\s*(?:€|eur|e)?\s*[A-Za-z]?\s*$",
                      re.I)
_CONT_RE = re.compile(
    r"^\s*(?P<q>\d+(?:[.,]\d+)?)\s*(?P<u>kpl|kg|pcs|st|ps|pss)?\s*(?:x|\*|à|a)?\s*"
    r"(?P<p>\d+[.,]\d{2})\s*(?:€|eur)?\s*(?:/\s*(?P<u2>kpl|kg|pcs|st))?\s*(?:-?\d+[.,]\d{2}\s*(?:€|eur)?)?\s*$",
    re.I)
_CHAIN_RE = re.compile(r"\b(prisma|s-market|alepa|sale|abc|sokos|emotion|s-kaupat)\b", re.I)
_CHAIN_NAMES = {"prisma": "Prisma", "s-market": "S-market", "alepa": "Alepa", "sale": "Sale",
                "abc": "ABC", "sokos": "Sokos", "emotion": "Emotion", "s-kaupat": "S-kaupat"}


def _num(s):
    return float(s.replace(",", "."))


def _guess_group(name):
    n = " " + name.lower() + " "
    for g, kws in _GROUP_KEYWORDS:
        for kw in kws:
            if kw in n:
                return g
    return "other"


def parse_receipt_text(text):
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text) > 8000:
        raise ValueError("receipt text is too long (limit 8,000 characters)")
    if len(text.strip()) < 10:
        raise ValueError("receipt text is too short")
    store, total = None, None
    lines, unparsed = [], []
    raw = text.replace("\r", "\n").split("\n")
    nonempty = 0
    for ln in raw:
        s = ln.strip()
        if not s:
            continue
        nonempty += 1
        if store is None and nonempty <= 4:
            m = _CHAIN_RE.search(s)
            if m and not _ITEM_RE.match(s):
                store = _CHAIN_NAMES[m.group(1).lower()]
                continue
        if _TOTAL_RE.match(s):
            amts = re.findall(r"-?\d+[.,]\d{2}", s)
            if amts and total is None:
                total = _num(amts[-1])
            continue
        if _SKIP_RE.search(s) or _DATE_RE.search(s):
            continue
        c = _CONT_RE.match(s)
        if c and lines:
            q = _num(c.group("q"))
            unit = (c.group("u") or c.group("u2") or "").lower()
            prev = lines[-1]
            if q > 0:
                prev["qty"] = int(q) if abs(q - round(q)) < 1e-9 else round(q, 3)
                prev["unit_price"] = round(_num(c.group("p")), 2)
            continue
        m = _ITEM_RE.match(s)
        if m:
            name = re.sub(r"\s+", " ", m.group("name")).strip(" .:-")
            amt = round(_num(m.group("amt")), 2)
            if len(name) >= 2:
                lines.append({"name": name, "qty": 1, "unit_price": amt, "line_total": amt,
                              "group": _guess_group(name)})
                continue
        if re.search(r"\d", s) and len(unparsed) < 10:
            unparsed.append(s[:80])
    for ln in lines:
        q = ln["qty"]
        if q and q != 1:
            ln["unit_price"] = round(ln["line_total"] / q, 2) if abs(q * ln["unit_price"] - ln["line_total"]) > 0.05 \
                else ln["unit_price"]
    sum_c = sum(int(round(ln["line_total"] * 100)) for ln in lines)
    groups = {}
    for ln in lines:
        g = groups.setdefault(ln["group"], {"c": 0, "items": 0})
        g["c"] += int(round(ln["line_total"] * 100))
        g["items"] += 1
    base_c = sum_c if sum_c > 0 else 0
    by_group = [{"group": g, "name": GROUP_NAMES.get(g, g), "total": round(v["c"] / 100.0, 2),
                 "share": round(v["c"] / base_c, 3) if base_c else 0.0, "items": v["items"]}
                for g, v in sorted(groups.items(), key=lambda kv: (kv[0] == "other", -kv[1]["c"]))]
    tc = sum(groups[g]["c"] for g in TREAT_GROUPS if g in groups)
    return {
        "store": store, "total": None if total is None else round(total, 2),
        "lines": lines, "lines_total": round(sum_c / 100.0, 2),
        "matches_total": total is not None and abs(round(total * 100) - sum_c) == 0,
        "by_group": by_group,
        "treats": {"total": round(tc / 100.0, 2), "share": round(tc / base_c, 3) if base_c else 0.0},
        "unparsed": unparsed, "note": PASTE_NOTE,
    }


# --------------------------------------------------------------------------- stored dataset

DATASET_NOTE = ("Fictional receipts. The challenge data has payment amounts only, so every line here "
                "was generated deterministically from the synthetic payments (Groceries and Fuel). "
                "Not real purchases; prices are illustrative.")
_CSV_HEAD = ["receipt_id", "date", "time", "store", "kind", "product", "group", "qty", "unit",
             "unit_price", "line_total", "receipt_total", "bonus_pct"]
_README = (
    "Svinkki demo receipts: fictional S Group receipts (Prisma, S-market, Alepa, Sale, ABC) for the "
    "demo customers.\n"
    "They are fictional: generated deterministically from the synthetic challenge payments "
    "(label Groceries and Fuel), not real purchases.\n"
    "receipts.json holds every receipt per customer; the CSV files hold one row per receipt line "
    "(UTF-8 with BOM, decimal point).\n"
    "Each receipt's lines add up to the payment to the cent; prices are illustrative.\n"
    "To regenerate: python -m app.receipts (also runs at the end of python -m app.ingest).\n")


def _safe_name(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "", s) or "customer"


def _csv_rows(rc):
    ts = str(rc.get("ts") or "")
    out = []
    for ln in rc["lines"]:
        dec = 3 if ln["unit"] == "l" else 2
        out.append([rc["tx_id"], rc.get("d") or ts[:10], ts[11:19], rc["store"], rc.get("kind", "grocery"),
                    ln["name"], ln["group"], ln["qty"], ln["unit"], "%.*f" % (dec, ln["unit_price"]),
                    "%.2f" % ln["line_total"], "%.2f" % rc["total"], rc["bonus"]["rate_pct"]])
    return out


def build_dataset(db_path=None, out_dir=None, today=None):
    """Write receipts.json, one CSV per demo persona and README.txt. Returns summary dicts."""
    from . import db as _db
    path = Path(db_path) if db_path else Path(_db.data_db_path())
    out = Path(out_dir) if out_dir else path.parent / "receipts"
    out.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if today is None:
            try:
                row = src.execute("SELECT value FROM meta WHERE key = 'today'").fetchone()
            except sqlite3.Error:
                row = None
            if row:
                today = row[0]
            else:
                from . import config
                today = config.today()
        today = str(today)
        personas = src.execute("SELECT cid, name FROM personas ORDER BY rowid").fetchall()
        f3, t3 = ins.period(today, "last_3_months")
        customers, summary = {}, []
        for cid, name in personas:
            mg = (src.execute("SELECT COALESCE(SUM(-amount), 0) FROM tx WHERE cid = ? AND label = "
                              "'Groceries' AND type = 'purchase' AND amount < 0 AND d >= ? AND d <= ?",
                              (cid, f3, t3)).fetchone()[0] or 0.0) / 3.0
            rows = src.execute(
                "SELECT rowid, d, ts, amount, merchant, label, type FROM tx WHERE cid = ? AND d <= ? "
                "AND label IN ('Groceries', 'Fuel') AND type = 'purchase' AND amount < 0 "
                "ORDER BY ts, rowid", (cid, today)).fetchall()
            rcs = []
            for r in rows:
                rc = receipt_for(dict(zip(("id", "d", "ts", "amount", "merchant", "label", "type"), r)),
                                 habit_seed=cid, monthly_grocery=mg)
                if rc:
                    rcs.append(rc)
            customers[cid] = {"name": name, "receipts": rcs}
            first = _safe_name(str(name).split(",")[0].strip())
            n_lines = sum(len(r["lines"]) for r in rcs)
            total_c = sum(int(round(r["total"] * 100)) for r in rcs)
            with open(out / ("%s_%s_receipts.csv" % (cid, first)), "w", encoding="utf-8-sig",
                      newline="") as fh:
                w = csv.writer(fh)
                w.writerow(_CSV_HEAD)
                for rc in rcs:
                    w.writerows(_csv_rows(rc))
            summary.append({"cid": cid, "name": name, "receipts": len(rcs), "lines": n_lines,
                            "total": round(total_c / 100.0, 2)})
    finally:
        src.close()
    doc = {"generated_for_today": today, "note": DATASET_NOTE, "customers": customers}
    tmp = out / "receipts.json.tmp"
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out / "receipts.json")
    (out / "README.txt").write_text(_README, encoding="utf-8")
    for s in summary:
        print("[receipts] %s %s: %d receipts, %d lines, EUR %.2f"
              % (s["cid"], s["name"], s["receipts"], s["lines"], s["total"]), flush=True)
    return summary


if __name__ == "__main__":
    build_dataset()
