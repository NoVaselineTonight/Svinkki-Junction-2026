"""Fuel receipts and the stored fictional receipt dataset (app/receipts.py).

Uses a small invented database built inside the test (temp folder); no real data, no network, no key.
"""
import csv
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SVINKKI_AI_KEY_FILE", os.path.join(tempfile.gettempdir(), "no_such_dir", "no_key.txt"))

from app import receipts as R  # noqa: E402

TODAY = "2026-09-26"
CID = "TEST001"
OTHER = "TEST002"


def _build_db(path):
    rng = random.Random(7)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE tx (cid TEXT, d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, "
                 "category TEXT, mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT)")
    conn.execute("CREATE TABLE personas (cid TEXT PRIMARY KEY, name TEXT, blurb TEXT)")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('today', ?)", (TODAY,))
    conn.execute("INSERT INTO personas VALUES (?, ?, '')", (CID, "Testi, 30"))
    conn.execute("INSERT INTO personas VALUES (?, ?, '')", (OTHER, "Äiti-Liisa, 61"))
    start = date.fromisoformat(TODAY) - timedelta(days=200)
    rows = []
    for cid in (CID, OTHER):
        for i in range(200):
            d = start + timedelta(days=i)
            for k in range(2):
                if rng.random() < 0.28:
                    amt = round(rng.uniform(2.5, 140.0), 2)
                    rows.append((cid, d.isoformat(), "%s %02d:%02d:11" % (d.isoformat(), 9 + k * 6, i % 60),
                                 -amt, 0, "purchase", "x", "5411", "M%d" % rng.randint(1, 6), "Groceries"))
            if rng.random() < 0.08:
                amt = round(rng.choice([4.3, 9.8, 38.5, 55.12, 71.4, 82.99]) + rng.random(), 2)
                rows.append((cid, d.isoformat(), "%s 17:%02d:40" % (d.isoformat(), i % 60), -amt, 0,
                             "purchase", "x", "5541", "F%d" % rng.randint(1, 3), "Fuel"))
            if rng.random() < 0.1:
                rows.append((cid, d.isoformat(), "%s 20:05:00" % d.isoformat(), -23.5, 0, "purchase", "x",
                             "5812", "R1", "Restaurant"))
    conn.executemany("INSERT INTO tx (cid,d,ts,amount,balance,type,category,mcc,merchant,label,basket,context)"
                     " VALUES (?,?,?,?,?,?,?,?,?,?,'everyday','')", rows)
    conn.commit()
    conn.close()


def _sandbox(db_path, cid):
    """In-memory sandbox like app.db.sandbox: the customer's rows with id = main-table rowid."""
    src = sqlite3.connect(db_path)
    rows = src.execute("SELECT d, ts, amount, balance, type, category, mcc, merchant, label, basket, "
                       "context, rowid FROM tx WHERE cid = ? AND d <= ? ORDER BY ts, rowid",
                       (cid, TODAY)).fetchall()
    src.close()
    mem = sqlite3.connect(":memory:")
    mem.execute("CREATE TABLE tx (d TEXT, ts TEXT, amount REAL, balance REAL, type TEXT, category TEXT, "
                "mcc TEXT, merchant TEXT, label TEXT, basket TEXT, context TEXT, id INTEGER)")
    mem.executemany("INSERT INTO tx VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    mem.commit()
    return mem


def _row(**kw):
    base = {"id": 1, "d": "2026-08-14", "ts": "2026-08-14 17:30:00", "amount": -62.37,
            "merchant": "F1", "label": "Fuel", "type": "purchase"}
    base.update(kw)
    return base


class FuelReceiptTests(unittest.TestCase):
    def test_fuel_receipt_sums_to_the_cent_and_is_deterministic(self):
        for i, amt in enumerate([-62.37, -9.8, -4.3, -38.5, -81.02, -12.0, -27.77]):
            row = _row(id=100 + i, amount=amt, ts="2026-08-1%d 12:00:00" % (i % 9))
            a = R.receipt_for(row, habit_seed="C1")
            self.assertEqual(a, R.receipt_for(row, habit_seed="C1"))
            self.assertEqual(a["kind"], "fuel")
            self.assertTrue(a["store"].startswith("ABC"))
            cents = sum(round(ln["line_total"] * 100) for ln in a["lines"])
            self.assertEqual(cents, round(-amt * 100))
            self.assertTrue(all(ln["line_total"] > 0 and ln["unit_price"] > 0 and ln["qty"] > 0
                                for ln in a["lines"]))

    def test_fuel_line_has_litres_and_plausible_price(self):
        row = _row(amount=-71.40)
        rc = R.receipt_for(row, habit_seed="C1")
        fl = rc["lines"][0]
        self.assertEqual(fl["unit"], "l")
        self.assertEqual(fl["group"], "fuel")
        self.assertEqual(fl["qty"], round(fl["qty"], 2))
        self.assertTrue(1.70 <= fl["unit_price"] <= 1.96, fl["unit_price"])
        self.assertEqual(rc["fuel"]["litres"], fl["qty"])
        self.assertAlmostEqual(fl["qty"] * fl["unit_price"], fl["line_total"], delta=0.06)

    def test_customer_keeps_one_fuel_type(self):
        types = set()
        for i in range(30):
            rc = R.receipt_for(_row(id=i, amount=-50 - i), habit_seed="C9")
            types.add(rc["fuel"]["type"])
        self.assertEqual(len(types), 1)

    def test_other_labels_have_no_receipt(self):
        self.assertIsNone(R.receipt_for(_row(label="Restaurant")))
        self.assertIsNone(R.receipt_for(_row(amount=20.0)))
        self.assertIn("fuel", R.GROUP_NAMES)
        self.assertNotIn("fuel", R.TREAT_GROUPS)


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="svinkki_receipts_")
        cls.db = os.path.join(cls.tmp, "test.db")
        cls.out = os.path.join(cls.tmp, "out")
        _build_db(cls.db)
        cls.summary = R.build_dataset(db_path=cls.db, out_dir=cls.out)
        cls.old_env = os.environ.get("SVINKKI_RECEIPTS_FILE")

    @classmethod
    def tearDownClass(cls):
        if cls.old_env is None:
            os.environ.pop("SVINKKI_RECEIPTS_FILE", None)
        else:
            os.environ["SVINKKI_RECEIPTS_FILE"] = cls.old_env
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        os.environ["SVINKKI_RECEIPTS_FILE"] = os.path.join(self.out, "receipts.json")

    def test_files_are_written(self):
        names = sorted(os.listdir(self.out))
        self.assertIn("receipts.json", names)
        self.assertIn("README.txt", names)
        self.assertIn("%s_Testi_receipts.csv" % CID, names)
        self.assertIn("%s_AitiLiisa_receipts.csv" % OTHER, names)
        with open(os.path.join(self.out, "receipts.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(doc["generated_for_today"], TODAY)
        self.assertIn("fictional", doc["note"].lower())
        self.assertEqual(set(doc["customers"]), {CID, OTHER})
        kinds = {r["kind"] for r in doc["customers"][CID]["receipts"]}
        self.assertEqual(kinds, {"grocery", "fuel"})
        with open(os.path.join(self.out, "README.txt"), encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().strip().splitlines()), 5)
        for s in self.summary:
            self.assertGreater(s["receipts"], 0)

    def test_csv_line_totals_sum_to_receipt_total(self):
        path = os.path.join(self.out, "%s_Testi_receipts.csv" % CID)
        with open(path, "rb") as fh:
            self.assertTrue(fh.read(3) == b"\xef\xbb\xbf")
        sums, totals = defaultdict(int), {}
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rd = csv.DictReader(fh)
            self.assertEqual(rd.fieldnames[0], "receipt_id")
            for row in rd:
                sums[row["receipt_id"]] += round(float(row["line_total"]) * 100)
                totals[row["receipt_id"]] = round(float(row["receipt_total"]) * 100)
        self.assertGreater(len(sums), 20)
        for k in sums:
            self.assertEqual(sums[k], totals[k], k)

    def test_dataset_and_on_the_fly_paths_are_identical(self):
        conn = _sandbox(self.db, CID)
        self.assertIsNotNone(R._dataset_for(CID))
        calls = [
            lambda: R.receipts(conn, TODAY, "last_3_months", habit_seed=CID, limit=100),
            lambda: R.receipts(conn, TODAY, "last_month", habit_seed=CID),
            lambda: R.receipt_insights(conn, TODAY, "last_3_months", habit_seed=CID),
            lambda: R.receipt_insights(conn, TODAY, "last_12_months", habit_seed=CID),
            lambda: R.product_habit(conn, TODAY, "beer", habit_seed=CID),
            lambda: R.product_habit(conn, TODAY, "coffee", "last_6_months", habit_seed=CID),
            lambda: R.product_habit(conn, TODAY, "fuel", habit_seed=CID),
        ]
        stored = [c() for c in calls]
        os.environ["SVINKKI_RECEIPTS_FILE"] = os.path.join(self.tmp, "does_not_exist.json")
        self.assertIsNone(R._dataset_for(CID))
        fresh = [c() for c in calls]
        self.assertEqual(stored, fresh)

    def test_stored_receipts_are_really_read(self):
        conn = _sandbox(self.db, CID)
        with open(os.path.join(self.out, "receipts.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        marked = os.path.join(self.tmp, "marked.json")
        for r in doc["customers"][CID]["receipts"]:
            r["store"] = "MARKED"
        with open(marked, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        os.environ["SVINKKI_RECEIPTS_FILE"] = marked
        res = R.receipts(conn, TODAY, "last_3_months", habit_seed=CID, limit=5)
        self.assertTrue(res["receipts"])
        self.assertTrue(all(r["store"] == "MARKED" for r in res["receipts"]))

    def test_fuel_stays_out_of_grocery_figures(self):
        conn = _sandbox(self.db, CID)
        ri = R.receipt_insights(conn, TODAY, "last_3_months", habit_seed=CID)
        frm, to = ri["period"]["from"], ri["period"]["to"]
        groc = conn.execute("SELECT SUM(-amount) FROM tx WHERE label='Groceries' AND d>=? AND d<=?",
                            (frm, to)).fetchone()[0]
        self.assertAlmostEqual(ri["total"], round(groc, 2), places=2)
        self.assertAlmostEqual(sum(g["total"] for g in ri["by_group"]), ri["total"], places=2)
        self.assertNotIn("fuel", [g["group"] for g in ri["by_group"]])
        fb = ri["fuel"]
        self.assertGreater(fb["fills"], 0)
        self.assertAlmostEqual(fb["yearly"], fb["total"] * 4, places=1)
        self.assertTrue(1.70 <= fb["avg_price_per_litre"] <= 1.96)
        self.assertLessEqual(len(ri["highlights"]), 4)
        self.assertTrue(any("filled up" in h for h in ri["highlights"]))
        labels = {e.get("label") for e in ri["evidence"]}
        self.assertEqual(labels, {"Groceries", "Fuel"})
        ph = R.product_habit(conn, TODAY, "diesel", habit_seed=CID)
        self.assertEqual(ph["matched"]["name"], "fuel")
        self.assertEqual({e.get("label") for e in ph["evidence"]}, {"Fuel"})
        self.assertIn("litres", ph["text"])

    def test_customer_missing_from_dataset_still_works(self):
        conn = _sandbox(self.db, CID)
        self.assertIsNone(R._dataset_for("NOT_THERE"))
        res = R.receipts(conn, TODAY, "last_3_months", habit_seed="NOT_THERE")
        self.assertGreater(res["count"], 0)
        for rc in res["receipts"]:
            self.assertEqual(sum(round(ln["line_total"] * 100) for ln in rc["lines"]),
                             round(rc["total"] * 100))
        self.assertIsNotNone(R.receipt_insights(conn, TODAY, habit_seed=None)["fuel"])
        self.assertIn("matched", R.product_habit(conn, TODAY, "beer", habit_seed="NOT_THERE"))


if __name__ == "__main__":
    unittest.main()
