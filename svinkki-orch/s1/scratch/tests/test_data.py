"""Data layer: ingest, classification, sandbox, safe_select, bench.

Acceptance: M1, M2 (isolation), M6, M7; plan: SR-2, SR-6, SR-8, SR-13, SR-14, SR-26, SR-31, V3, V4, V9.
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx


def _rows_by_key(conn):
    """sandbox rows keyed by (ts, amount in cents)."""
    out = {}
    for r in conn.execute("SELECT * FROM tx"):
        out.setdefault((r["ts"], round(r["amount"] * 100)), []).append(r)
    return out


class IngestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = fx.get()

    def test_input_csv_format_is_as_contracted(self):
        # The fixture itself must follow STATE.md 5.7, otherwise the ingest tests prove nothing.
        raw = (self.env.csv_dir / "tx_junction_transactions.csv").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "CSV must be UTF-8 with BOM")
        head = raw.decode("utf-8-sig").splitlines()
        self.assertEqual(head[0], "customer_id,bank_account_id,tx_date,tx_timestamp,category,"
                                  "tx_amount_eur,balance_after_eur,transaction_type,merchant_id,mcc_code")
        self.assertRegex(head[1].split(",")[3], r"^\d{2}[A-Z]{3}\d{2}:\d{2}:\d{2}:\d{2}$")

    def test_build_result_counts(self):
        r = self.env.build_result
        self.assertEqual(r["customers"], fx.CUSTOMER_COUNT)
        self.assertEqual(r["rows"], fx.TOTAL_ROWS)
        self.assertIn("seconds", r)

    def test_schema_matches_contract(self):
        con = fx.open_db()
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(tx)")}
            self.assertEqual(cols, {"cid", "d", "ts", "amount", "balance", "type", "category", "mcc",
                                    "merchant", "label", "basket", "context"})
            for table in ("customers", "bench", "personas", "meta"):
                self.assertTrue(con.execute("SELECT name FROM sqlite_master WHERE name=?", (table,)).fetchone(),
                                "missing table " + table)
            n = con.execute("SELECT count(*) FROM tx").fetchone()[0]
            self.assertEqual(n, fx.TOTAL_ROWS)
            meta = dict(con.execute("SELECT key, value FROM meta"))
            self.assertEqual(int(meta["rows"]), fx.TOTAL_ROWS)
            self.assertEqual(int(meta["customers"]), fx.CUSTOMER_COUNT)
        finally:
            con.close()

    def test_timestamp_conversion(self):
        # Salary of customer A on 15 Oct 2024 at 08:00:04 is written as 15OCT24:08:00:04.
        con = fx.open_db()
        try:
            row = con.execute("SELECT d, ts, amount FROM tx WHERE cid=? AND type='salary' ORDER BY ts LIMIT 1",
                              (fx.A_CID,)).fetchone()
            self.assertEqual(row[0], "2024-10-15")
            self.assertEqual(row[1], "2024-10-15 08:00:04")
            self.assertAlmostEqual(row[2], 3000.00, places=2)
            # every row: ts date part equals d, format is fixed width
            bad = [r for r in con.execute("SELECT d, ts FROM tx")
                   if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", r[1]) or r[1][:10] != r[0]]
            self.assertEqual(bad, [])
        finally:
            con.close()

    def test_after_midnight_row_keeps_its_own_date(self):
        con = fx.open_db()
        try:
            row = con.execute("SELECT d, ts FROM tx WHERE cid=? AND ts='2026-08-22 01:10:00'", (fx.A_CID,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "2026-08-22")
        finally:
            con.close()

    def test_amounts_balances_and_ids_round_trip(self):
        con = fx.open_db()
        try:
            for cid in (fx.A_CID, fx.D_CID):
                rows = fx.rows_for(cid)
                got = con.execute("SELECT count(*), round(sum(amount),2) FROM tx WHERE cid=?", (cid,)).fetchone()
                self.assertEqual(got[0], len(rows))
                self.assertAlmostEqual(got[1], sum(r["cents"] for r in rows) / 100.0, places=2)
            last = con.execute("SELECT balance FROM tx WHERE cid=? ORDER BY ts DESC, rowid DESC LIMIT 1",
                               (fx.A_CID,)).fetchone()[0]
            self.assertAlmostEqual(last, fx.rows_for(fx.A_CID)[-1]["balance"], places=2)
        finally:
            con.close()

    def test_postal_leading_zero_and_area(self):
        con = fx.open_db()
        try:
            row = con.execute("SELECT postal, age, age_band, area FROM customers WHERE cid=?", (fx.A_CID,)).fetchone()
            self.assertEqual(row[0], fx.A_POSTAL)          # leading zeros preserved: text, not a number
            self.assertEqual(row[1], fx.A_AGE)
            self.assertEqual(row[2], "25-34")
            self.assertEqual(row[3], "00")
        finally:
            con.close()

    def test_age_bands_cover_every_boundary(self):
        con = fx.open_db()
        try:
            got = {r[0]: r[1] for r in con.execute("SELECT cid, age_band FROM customers")}
            self.assertEqual(len(got), fx.CUSTOMER_COUNT)
            for c in fx.CUSTOMERS:
                self.assertEqual(got[c["cid"]], fx.band_of(c["age"]), "age %d" % c["age"])
            self.assertEqual({fx.band_of(a) for a in (24, 25, 34, 35, 44, 45, 54, 55, 64, 65)},
                             {"18-24", "25-34", "35-44", "45-54", "55-64", "65+"})
            self.assertTrue({"18-24", "25-34", "35-44", "45-54", "55-64", "65+"} <= set(got.values()))
        finally:
            con.close()

    def test_personas_are_six_real_customers_with_invented_names(self):
        ps = self.env.ingest_personas
        self.assertEqual(len(ps), 6, "ingest must choose 6 personas")
        known = {c["cid"] for c in fx.CUSTOMERS}
        for p in ps:
            self.assertIn(p["cid"], known)
            self.assertRegex(p["name"], r"^[^\d,]+, \d{2}$", "persona name is 'FirstName, age'")
            self.assertTrue(p["blurb"])
            self.assertNotIn("CUST", p["name"] + p["blurb"])

    def test_limit_customers_and_atomic_replace(self):
        import app.ingest as ingest
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "small.db")
            r = ingest.build(str(self.env.csv_dir), out, limit_customers=5)
            self.assertEqual(r["customers"], 5)
            con = sqlite3.connect(out)
            try:
                self.assertEqual(con.execute("SELECT count(*) FROM customers").fetchone()[0], 5)
                self.assertEqual(con.execute("SELECT count(DISTINCT cid) FROM tx").fetchone()[0], 5)
            finally:
                con.close()
            r2 = ingest.build(str(self.env.csv_dir), out, limit_customers=3)       # replaces the file
            self.assertEqual(r2["customers"], 3)
            leftovers = [n for n in os.listdir(d) if n != "small.db"]
            self.assertEqual(leftovers, [], "no temporary file may be left behind")

    def test_cli_builds_a_database(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "cli.db")
            p = subprocess.run([sys.executable, "-m", "app.ingest", "--data-dir", str(self.env.csv_dir),
                                "--out", out, "--customers", "4"], cwd=str(fx.REPO),
                               capture_output=True, text=True, timeout=180)
            self.assertEqual(p.returncode, 0, p.stderr[-500:])
            con = sqlite3.connect(out)
            try:
                self.assertEqual(con.execute("SELECT count(*) FROM customers").fetchone()[0], 4)
            finally:
                con.close()


class IngestRowOrderTests(unittest.TestCase):
    """The contract does not say whether the CSV is grouped by customer. A real export may mix customers
    in time order, so the result must not depend on it (robustness; STATE.md 5.7 is silent)."""

    @classmethod
    def setUpClass(cls):
        cls.env = fx.get()

    def test_interleaved_customers_give_the_same_database(self):
        import app.ingest as ingest
        with tempfile.TemporaryDirectory() as d:
            csv_dir = Path(d) / "csv"
            fx.write_csvs(csv_dir, interleaved=True)
            out = os.path.join(d, "mixed.db")
            r = ingest.build(str(csv_dir), out)
            self.assertEqual(r["rows"], fx.TOTAL_ROWS)
            con = sqlite3.connect(out)
            ref = fx.open_db()
            try:
                def q(c, sql, *a):
                    return c.execute(sql, a).fetchall()
                self.assertEqual(q(con, "SELECT count(*) FROM tx WHERE context='night_out'"),
                                 q(ref, "SELECT count(*) FROM tx WHERE context='night_out'"))
                self.assertEqual(q(con, "SELECT label, basket, count(*) FROM tx GROUP BY 1,2 ORDER BY 1,2"),
                                 q(ref, "SELECT label, basket, count(*) FROM tx GROUP BY 1,2 ORDER BY 1,2"))
                self.assertEqual(q(con, "SELECT DISTINCT group_key FROM bench ORDER BY 1"),
                                 q(ref, "SELECT DISTINCT group_key FROM bench ORDER BY 1"))
                self.assertGreaterEqual(q(con, "SELECT count(*) FROM personas")[0][0], 1)
            finally:
                con.close()
                ref.close()


class ClassifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = fx.get()
        cls.conn = fx.sandbox(fx.A_CID)

    def test_every_outflow_has_exactly_one_basket(self):
        con = fx.open_db()
        try:
            bad = con.execute("SELECT count(*) FROM tx WHERE amount < 0 AND "
                              "(basket IS NULL OR basket NOT IN ('regular','unexpected','everyday','savings','transfer'))"
                              ).fetchone()[0]
            self.assertEqual(bad, 0)
            nulls = con.execute("SELECT count(*) FROM tx WHERE basket IS NULL OR basket='' OR label IS NULL OR label=''"
                                ).fetchone()[0]
            self.assertEqual(nulls, 0)
            inflow_bad = con.execute("SELECT count(*) FROM tx WHERE amount > 0 AND basket NOT IN ('income','transfer')"
                                     ).fetchone()[0]
            self.assertEqual(inflow_bad, 0)
        finally:
            con.close()

    def test_labels_baskets_and_context_match_the_known_history(self):
        got = _rows_by_key(self.conn)
        problems = []
        for r in fx.rows_for(fx.A_CID):
            if r["d"] > fx.TODAY:
                continue
            hits = got.get((r["ts"], r["cents"]))
            if not hits:
                problems.append(("missing row", r["ts"], r["label"]))
                continue
            row = hits.pop(0)
            if (row["label"], row["basket"], row["context"] or "") != (r["label"], r["basket"], r["context"]):
                problems.append((r["ts"], r["label"], "got", row["label"], row["basket"], row["context"]))
        self.assertEqual(problems[:8], [], "%d rows classified differently from the known history" % len(problems))

    def test_mcc_labels(self):
        expect = {"4121": "Taxi", "5813": "Bar", "5814": "Fast food", "5812": "Restaurant",
                  "5541": "Fuel", "5912": "Pharmacy", "5411": "Groceries", "4111": "Public transport",
                  "5732": "Electronics", "5651": "Clothing", "8011": "Doctor"}
        con = fx.open_db()
        try:
            for mcc, label in expect.items():
                labels = {r[0] for r in con.execute("SELECT DISTINCT label FROM tx WHERE mcc=?", (mcc,))}
                self.assertEqual(labels, {label}, "MCC %s" % mcc)
        finally:
            con.close()

    def test_purchase_without_mcc_is_labelled_from_category(self):
        row = self.conn.execute("SELECT * FROM tx WHERE ts LIKE '2026-08-08 10:00:00' AND amount < 0").fetchone()
        self.assertIsNotNone(row)
        self.assertFalse(row["mcc"])
        self.assertEqual(row["label"], "Groceries")
        self.assertEqual(row["basket"], "regular")

    def test_night_out_rule_for_the_friday_in_august(self):
        c = self.conn
        night = {r["ts"]: r for r in c.execute("SELECT * FROM tx WHERE context='night_out'")}
        for ts in ("2026-08-21 21:30:00", "2026-08-22 01:10:00", "2026-08-22 01:40:00"):
            self.assertIn(ts, night, "%s must be part of the night out" % ts)
        self.assertEqual(night["2026-08-22 01:10:00"]["label"], "Fast food")     # label keeps the merchant type
        self.assertEqual(night["2026-08-22 01:40:00"]["label"], "Taxi")

    def test_daytime_lunch_and_taxi_are_not_night_out(self):
        # Wednesday 12 Aug 2026: lunch 12:30, taxi 08:10. Also the 19:30 dinner on the 10th and the 17:00 taxi on the 24th.
        for ts in ("2026-08-12 12:30:00", "2026-08-12 08:10:00", "2026-08-10 19:30:00", "2026-08-24 17:00:00"):
            row = self.conn.execute("SELECT context FROM tx WHERE ts=?", (ts,)).fetchone()
            self.assertIsNotNone(row, ts)
            self.assertFalse(row["context"], "%s must not be night_out" % ts)

    def test_small_hours_snack_without_a_bar_is_not_night_out(self):
        # Customer B buys fast food at 01:10 and a taxi at 01:40 but never visits a bar.
        b = fx.sandbox(fx.B_CID)
        rows = b.execute("SELECT context, label FROM tx WHERE ts LIKE '2026-08-20 01:%'").fetchall()
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertFalse(r["context"], "no bar in the window, so %s is not a night out" % r["label"])
        self.assertEqual(b.execute("SELECT count(*) FROM tx WHERE context='night_out'").fetchone()[0], 0)

    def test_baskets_for_unexpected_regular_savings_and_income(self):
        c = self.conn
        e = c.execute("SELECT basket, label FROM tx WHERE ts='2026-06-20 14:00:00'").fetchone()
        self.assertEqual((e["basket"], e["label"]), ("unexpected", "Electronics"))          # 600 EUR appliance
        for label, basket in (("Pharmacy", "regular"), ("Housing", "regular"), ("Utilities", "regular"),
                              ("Savings & investments", "savings"), ("Salary", "income"), ("Taxi", "everyday")):
            baskets = {r[0] for r in c.execute("SELECT DISTINCT basket FROM tx WHERE label=?", (label,))}
            self.assertEqual(baskets, {basket}, label)

    def test_basket_rules_text_is_exposed(self):
        import app.classify as classify
        self.assertIsInstance(classify.BASKET_RULES_TEXT, str)
        self.assertGreater(len(classify.BASKET_RULES_TEXT), 40)


class SandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = fx.get()

    def test_sandbox_holds_one_customer_and_nothing_after_today(self):
        import app.db as db
        conn = db.sandbox(fx.A_CID, fx.TODAY)
        want = [r for r in fx.rows_for(fx.A_CID) if r["d"] <= fx.TODAY]
        self.assertEqual(conn.execute("SELECT count(*) FROM tx").fetchone()[0], len(want))
        self.assertAlmostEqual(conn.execute("SELECT round(sum(amount),2) FROM tx").fetchone()[0],
                               sum(r["cents"] for r in want) / 100.0, places=2)
        self.assertLessEqual(conn.execute("SELECT max(d) FROM tx").fetchone()[0], fx.TODAY)
        self.assertEqual(conn.execute("SELECT count(*) FROM tx WHERE d > ?", (fx.TODAY,)).fetchone()[0], 0)
        # no trace of any other customer's distinctive row (B earns 2600, A earns 3000)
        self.assertEqual(conn.execute("SELECT count(*) FROM tx WHERE amount = 2600").fetchone()[0], 0)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tx)")]
        self.assertNotIn("cid", cols)
        self.assertIsInstance(conn.execute("SELECT * FROM tx LIMIT 1").fetchone(), sqlite3.Row)

    def test_sandbox_has_only_the_tx_table(self):
        import app.db as db
        conn = db.sandbox(fx.A_CID, fx.TODAY)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("tx", names)
        self.assertFalse(names & {"customers", "bench", "personas", "meta"}, names)

    def test_sandbox_for_another_customer_is_a_different_world(self):
        import app.db as db
        b = db.sandbox(fx.B_CID, fx.TODAY)
        self.assertEqual(b.execute("SELECT count(*) FROM tx").fetchone()[0],
                         len([r for r in fx.rows_for(fx.B_CID) if r["d"] <= fx.TODAY]))
        self.assertEqual(b.execute("SELECT count(*) FROM tx WHERE amount = 3000").fetchone()[0], 0)

    def test_sandbox_for_unknown_customer_is_empty(self):
        import app.db as db
        conn = db.sandbox("CUST99999", fx.TODAY)
        self.assertEqual(conn.execute("SELECT count(*) FROM tx").fetchone()[0], 0)

    def test_profile_has_no_exact_age_or_postal_code(self):
        import app.db as db
        p = db.profile(fx.A_CID)
        self.assertEqual(p["age_band"], "25-34")
        self.assertEqual(p["area"], "00")
        self.assertNotIn("age", p)
        self.assertNotIn("postal", p)
        blob = repr(p)
        self.assertNotIn(fx.A_POSTAL, blob)
        self.assertNotIn(str(fx.A_AGE), blob)

    def test_customer_exists_and_personas(self):
        import app.db as db
        self.assertTrue(db.customer_exists(fx.A_CID))
        self.assertFalse(db.customer_exists("CUST99999"))
        names = {p["name"] for p in db.list_personas()}
        self.assertTrue({fx.A_NAME, fx.B_NAME, fx.D_NAME} <= names)


def _first_value(res):
    row = res["rows"][0]
    if isinstance(row, dict):
        return list(row.values())[0]
    return row[0]


class SafeSelectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = fx.get()

    def setUp(self):
        import app.db as db
        self.db = db
        self.conn = db.sandbox(fx.A_CID, fx.TODAY)
        self.count = self.conn.execute("SELECT count(*) FROM tx").fetchone()[0]

    def _unchanged(self):
        self.assertEqual(self.conn.execute("SELECT count(*) FROM tx").fetchone()[0], self.count)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM tx WHERE amount = 0").fetchone()[0], 0)

    def test_select_works_and_has_the_contracted_shape(self):
        res = self.db.safe_select(self.conn, "SELECT count(*) AS n FROM tx")
        self.assertEqual(set(res) >= {"columns", "rows", "truncated"}, True)
        self.assertEqual(res["columns"], ["n"])
        self.assertEqual(_first_value(res), self.count)
        self.assertFalse(res["truncated"])

    def test_V4_writes_and_other_statements_are_rejected(self):
        bad = [
            "UPDATE tx SET amount = 0",
            "DELETE FROM tx",
            "DROP TABLE tx",
            "INSERT INTO tx (d, ts, amount) VALUES ('2026-01-01', '2026-01-01 00:00:00', 1)",
            "PRAGMA table_info(tx)",
            "ATTACH DATABASE ':memory:' AS other",
            "CREATE TABLE x (a)",
            "ALTER TABLE tx ADD COLUMN z",
            "SELECT 1; SELECT 2",
            "SELECT 1; DROP TABLE tx",
            "SELECT 1 /* hi */; DELETE FROM tx",
            "VACUUM",
            "",
        ]
        for sql in bad:
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    self.db.safe_select(self.conn, sql)
        self._unchanged()

    def test_V3_other_tables_and_system_tables_are_out_of_reach(self):
        for sql in ("SELECT * FROM customers", "SELECT * FROM bench", "SELECT * FROM personas",
                    "SELECT * FROM meta"):
            with self.subTest(sql=sql):
                with self.assertRaises((ValueError, sqlite3.Error)):
                    self.db.safe_select(self.conn, sql)
        try:
            res = self.db.safe_select(self.conn, "SELECT name FROM sqlite_master")
        except (ValueError, sqlite3.Error):
            return
        names = {str(v) for row in res["rows"] for v in (row.values() if isinstance(row, dict) else row)}
        self.assertFalse(names & {"customers", "bench", "personas", "meta"})

    def test_V3_select_all_rows_returns_only_this_customers_rows(self):
        res = self.db.safe_select(self.conn, "SELECT * FROM tx", max_rows=10000)
        self.assertLessEqual(len(res["rows"]), 10000)
        # A earns 3000 a month; the only salary amounts in view are A's
        res = self.db.safe_select(self.conn, "SELECT DISTINCT amount FROM tx WHERE type='salary'")
        self.assertEqual([float(_first_value({"rows": [r]})) for r in res["rows"]], [3000.0])

    def test_row_cap(self):
        res = self.db.safe_select(self.conn, "SELECT * FROM tx")
        self.assertEqual(len(res["rows"]), 50)
        self.assertTrue(res["truncated"])
        res = self.db.safe_select(self.conn, "SELECT * FROM tx", max_rows=5)
        self.assertEqual(len(res["rows"]), 5)
        self.assertTrue(res["truncated"])
        res = self.db.safe_select(self.conn, "SELECT * FROM tx LIMIT 3")
        self.assertEqual(len(res["rows"]), 3)
        self.assertFalse(res["truncated"])

    def test_time_limit_stops_a_runaway_query(self):
        sql = ("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c")
        t0 = time.time()
        with self.assertRaises((ValueError, sqlite3.Error)):
            self.db.safe_select(self.conn, sql, timeout_s=0.5)
        self.assertLess(time.time() - t0, 10)
        self._unchanged()

    def test_a_failed_attempt_does_not_break_later_reads(self):
        with self.assertRaises(ValueError):
            self.db.safe_select(self.conn, "DROP TABLE tx")
        self.assertEqual(_first_value(self.db.safe_select(self.conn, "SELECT count(*) FROM tx")), self.count)


class BenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = fx.get()

    def test_no_group_below_twenty_customers_is_stored(self):
        con = fx.open_db()
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM bench WHERE n < 20").fetchone()[0], 0)
            keys = {r[0] for r in con.execute("SELECT DISTINCT group_key FROM bench")}
        finally:
            con.close()
        # 52 customers; 22 aged 25-34 (4 in area 00, 18 in area 20); exactly 20 aged 35-44, all in area 33.
        self.assertEqual(keys, {"all", "age:25-34", "age:35-44", "age:35-44|area:33"})

    def test_group_sizes_and_medians_match_the_population(self):
        import statistics
        import app.db as db
        for key, n in (("all", 52), ("age:25-34", 22), ("age:35-44", 20), ("age:35-44|area:33", 20)):
            res = db.bench([key], "income")
            self.assertIsNotNone(res, key)
            self.assertEqual(res["group_key"], key)
            self.assertEqual(res["n"], n)
            want = statistics.median(fx.salary_of(c) for c in fx.group_cids(key))
            self.assertAlmostEqual(res["median"], want, delta=0.01, msg=key)
            self.assertLessEqual(res["p25"], res["median"])
            self.assertLessEqual(res["median"], res["p75"])
            self.assertAlmostEqual(res["mean"], sum(fx.salary_of(c) for c in fx.group_cids(key)) / n, delta=0.01)

    def test_V9_bench_picks_first_existing_group_and_never_a_small_one(self):
        import app.db as db
        res = db.bench(["age:25-34|area:00", "age:25-34", "all"], "income")      # 4 customers -> skipped
        self.assertEqual(res["group_key"], "age:25-34")
        self.assertGreaterEqual(res["n"], 20)
        res = db.bench(["age:25-34|area:20", "all"], "income")                     # 18 customers -> skipped
        self.assertEqual(res["group_key"], "all")
        res = db.bench(["age:45-54", "all"], "income")                             # 3 customers -> skipped
        self.assertEqual(res["group_key"], "all")
        self.assertIsNone(db.bench(["age:45-54", "age:45-54|area:40"], "income"))
        self.assertIsNone(db.bench(["all"], "no_such_metric"))

    def test_bench_stores_statistics_only(self):
        con = fx.open_db()
        try:
            cols = [r[1] for r in con.execute("PRAGMA table_info(bench)")]
        finally:
            con.close()
        self.assertEqual(set(cols), {"group_key", "metric", "n", "p25", "median", "p75", "mean"})


class RepositoryHygieneTests(unittest.TestCase):
    """SR-25, SR-26, SR-31 (V16 in miniature)."""

    def test_gitignore_covers_secrets_and_data(self):
        text = (fx.REPO / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "*.csv", "*.db", "*.sqlite", "*.parquet", "data/"):
            self.assertIn(pattern, text, "SR-26: .gitignore must cover " + pattern)

    def test_no_data_or_secret_files_are_tracked(self):
        try:
            out = subprocess.run(["git", "ls-files"], cwd=str(fx.REPO), capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git not available")
        if out.returncode != 0:
            self.skipTest("not a git checkout")
        bad = [f for f in out.stdout.splitlines()
               if re.search(r"\.(csv|db|sqlite|parquet)$", f) or f == ".env" or (f.startswith(".env.") and f != ".env.example")]
        self.assertEqual(bad, [])

    def test_no_api_key_shaped_strings_in_the_working_tree(self):
        pat = re.compile(r"AIza[0-9A-Za-z_\-]{35}|sk-[A-Za-z0-9]{32,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
        hits = []
        for folder in ("app", "web", "docs", "tests"):
            for p in (fx.REPO / folder).rglob("*"):
                if p.is_file() and p.suffix in (".py", ".js", ".html", ".css", ".md", ".json", ".txt"):
                    if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                        hits.append(str(p))
        self.assertEqual(hits, [])

    def test_fixture_is_invented_not_copied(self):
        # SR-31: the fixture builds its own temp folder and never touches the real dataset folder.
        env = fx.get()
        self.assertTrue(str(env.csv_dir).startswith(tempfile.gettempdir()) or "svinkki_test_" in str(env.csv_dir))
        self.assertEqual(os.environ["SVINKKI_DATA_DIR"], str(env.csv_dir))
        self.assertNotIn("Junction-2026", os.environ["SVINKKI_DATA_DIR"])


if __name__ == "__main__":
    unittest.main()
