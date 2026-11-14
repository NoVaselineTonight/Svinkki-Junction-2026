"""Putting the demo online (deploy/): the hosted entry point with its daily cap on model turns, the data
build from the organisers' public dataset, and the key check. No network and no real key: downloads are
not exercised here, only what happens to the files once they are on disk.
"""
import csv
import datetime
import io
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc

A = fx.A_CID


class BudgetTests(unittest.TestCase):
    def setUp(self):
        fx.get()
        from deploy import serve
        self.serve = serve

    def test_turns_are_capped_per_day_and_start_again_the_next_day(self):
        day = [datetime.date(2026, 11, 15)]
        b = self.serve.DailyBudget(2, clock=lambda: day[0])
        self.assertEqual([b.take_turn(), b.take_turn(), b.take_turn()], [True, True, False])
        self.assertEqual(b.left(), 0)
        day[0] = datetime.date(2026, 11, 16)
        self.assertTrue(b.take_turn())
        self.assertEqual(b.left(), 1)

    def test_requests_have_a_backstop_of_eight_per_turn(self):
        b = self.serve.DailyBudget(1, clock=lambda: datetime.date(2026, 11, 15))
        self.assertEqual(sum(1 for _ in range(20) if b.take_request()), self.serve.REQUESTS_PER_TURN)

    def test_no_cap_and_zero(self):
        free = self.serve.DailyBudget(None)
        self.assertTrue(all(free.take_turn() and free.take_request() for _ in range(50)))
        self.assertIsNone(free.left())
        self.assertFalse(self.serve.DailyBudget(0).take_turn())

    def test_the_setting_is_read_forgivingly(self):
        d = self.serve.daily_limit
        self.assertEqual((d("400"), d(" 25 "), d(0), d("-3")), (400, 25, 0, 0))
        self.assertIsNone(d("off"))
        self.assertIsNone(d("unlimited"))
        self.assertEqual(d("lots"), self.serve.DEFAULT_DAILY_TURNS)
        self.assertEqual(d(""), self.serve.DEFAULT_DAILY_TURNS)

    def test_address_listens_on_all_addresses_only_when_a_host_gives_the_port(self):
        a = self.serve.address
        self.assertEqual(a({"PORT": "10000"}), ("0.0.0.0", 10000))
        self.assertEqual(a({}), ("127.0.0.1", 8000))
        self.assertEqual(a({"SVINKKI_PORT": "8010"}), ("127.0.0.1", 8010))
        self.assertEqual(a({"PORT": "8055", "SVINKKI_HOST": "127.0.0.1"}), ("127.0.0.1", 8055))
        self.assertEqual(a({"PORT": "abc"}), ("0.0.0.0", 8000))


class CappedCoachTests(unittest.TestCase):
    """The cap wraps the app from outside; these tests pin the two names it relies on."""

    def setUp(self):
        fx.get()
        import app.coach as coach
        import app.llm_claude as llm_claude
        import app.server as server
        from deploy import serve
        self.coach, self.llm, self.server, self.serve = coach, llm_claude, server, serve
        self._turn, self._create, self._routes = coach._claude_turn, llm_claude.create, dict(server.ROUTES)

    def tearDown(self):
        self.coach._claude_turn, self.llm.create = self._turn, self._create
        self.server.ROUTES.clear()
        self.server.ROUTES.update(self._routes)

    def ctx(self):
        c = fx.make_ctx(A)
        c.memory = {}
        c.cid = A
        return c

    def test_after_the_cap_the_built_in_rules_answer_and_no_request_is_made(self):
        self.serve.install_budget(self.serve.DailyBudget(1, clock=lambda: datetime.date(2026, 11, 15)))
        fake = fc.FakeClaude([fc.cl_text("Hello from the model.")])
        with fc.patched_claude(fake):
            first = self.coach.chat("hi there, how are things?", [], self.ctx())
            second = self.coach.chat("How much did I spend on taxis last month?", [], self.ctx())
        self.assertEqual(first["mode"], "claude")
        self.assertEqual(fake.calls, 1)                       # the second question never reached the model
        self.assertEqual(second["mode"], "offline")
        self.assertEqual(second.get("notice"), self.coach.NOTICES["cap"][0])
        self.assertTrue(fx.text_has_amount(second["reply"], 62.10), second["reply"])

    def test_the_request_backstop_stops_other_model_calls_too(self):
        self.serve.install_budget(self.serve.DailyBudget(0))
        with fc.patched_claude(fc.FakeClaude([fc.cl_text("ok")])) as fake:
            with self.assertRaises(self.llm.ClaudeError):
                self.llm.ping(fc.FAKE_KEY, "claude-haiku-5-5")
        self.assertEqual(fake.calls, 0)

    def test_without_a_cap_the_model_answers_as_usual(self):
        self.serve.install_budget(self.serve.DailyBudget(None))
        with fc.patched_claude(fc.FakeClaude([fc.cl_text("Hello from the model.")])) as fake:
            r = self.coach.chat("hi there, how are things?", [], self.ctx())
        self.assertEqual((r["mode"], fake.calls), ("claude", 1))

    def test_public_mode_removes_the_reset_endpoint_and_nothing_else(self):
        self.assertIn("/api/demo/reset", self.server.ROUTES)
        before = set(self.server.ROUTES)
        # public mode also changes three module settings: put them back, or later tests run in public mode
        srv = self.server
        old = (srv.RATE_CHAT, srv.TRUST_FORWARDED_FOR, srv.PER_VISITOR_STATE)
        self.addCleanup(lambda: setattr(srv, "RATE_CHAT", old[0]))
        self.addCleanup(lambda: setattr(srv, "TRUST_FORWARDED_FOR", old[1]))
        self.addCleanup(lambda: setattr(srv, "PER_VISITOR_STATE", old[2]))
        self.assertEqual(self.serve.make_public(), ["/api/demo/reset"])
        self.assertEqual(before - set(self.server.ROUTES), {"/api/demo/reset"})
        self.assertEqual(self.serve.make_public(), [])


class DataBuildTests(unittest.TestCase):
    def setUp(self):
        fx.get()
        from deploy import build_data
        self.b = build_data
        self.tmp = tempfile.mkdtemp(prefix="svinkki_test_deploy_")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_the_list_of_left_out_customers(self):
        ids = self.b.removed_ids()
        self.assertEqual(len(ids), 286)
        self.assertTrue(all(re.fullmatch(r"CUST\d{5}", i) for i in ids))

    def test_a_git_lfs_pointer_is_recognised(self):
        ptr = "version https://git-lfs.github.com/spec/v1\noid sha256:%s\nsize 362796501\n" % ("ab" * 32)
        self.assertEqual(self.b.parse_pointer(ptr), ("ab" * 32, 362796501))
        self.assertIsNone(self.b.parse_pointer("customer_id,bank_account_id\nCUST00001,X\n"))
        self.assertIsNone(self.b.parse_pointer("oid sha256:abc\nsize big\n"))

    def test_left_out_customers_and_their_mortgage_applications_are_filtered(self):
        src, dst = os.path.join(self.tmp, "src"), os.path.join(self.tmp, "dst")
        os.makedirs(src)
        with open(os.path.join(src, self.b.CUSTOMERS), "w", encoding="utf-8-sig", newline="") as f:
            f.write("customer_id,customer_postal_code,customer_age\nCUST00001,00100,30\nCUST00002,00200,40\nCUST00003,00300,50\n")
        with open(os.path.join(src, self.b.TX), "w", encoding="utf-8-sig", newline="") as f:
            f.write("customer_id,bank_account_id,tx_date\nCUST00001,A,2026-01-01\nCUST00002,B,2026-01-02\n"
                    "CUST00002,B,2026-01-03\nCUST00003,C,2026-01-04\n")
        with open(os.path.join(src, self.b.MTG_LINK), "w", encoding="utf-8-sig", newline="") as f:
            f.write("mortgage_customer_id,customer_id,final_decision\nC0001,CUST00001,approved\nC0002,CUST00002,rejected\n")
        with open(os.path.join(src, self.b.MTG_HISTORY), "w", encoding="utf-8-sig", newline="") as f:
            f.write("mortgage_customer_id,timestamp,note\nC0001,x,\"kept, with a comma\"\nC0002,y,gone\nC0002,z,gone\n")
        counts = self.b.filter_dataset(src, dst, {"CUST00002"})
        self.assertEqual(counts[self.b.TX], (2, 2))
        self.assertEqual(counts[self.b.CUSTOMERS], (2, 1))
        self.assertEqual(counts[self.b.MTG_LINK], (1, 1))
        self.assertEqual(counts[self.b.MTG_HISTORY], (1, 2))
        for name in (self.b.TX, self.b.CUSTOMERS, self.b.MTG_LINK, self.b.MTG_HISTORY):
            with open(os.path.join(dst, name), encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertNotIn("CUST00002", " ".join(",".join(r.values()) for r in rows), name)
            self.assertTrue(rows, name)
        with open(os.path.join(dst, self.b.MTG_HISTORY), encoding="utf-8-sig", newline="") as f:
            self.assertEqual(list(csv.DictReader(f))[0]["note"], "kept, with a comma")

    def test_slimming_keeps_the_demo_customers_a_pool_and_all_statistics(self):
        db = os.path.join(self.tmp, "slim.db")
        shutil.copyfile(str(fx.get().db_path), db)
        conn = sqlite3.connect(db)
        personas = [r[0] for r in conn.execute("SELECT cid FROM personas")]
        bench = conn.execute("SELECT * FROM bench ORDER BY 1, 2").fetchall()
        a_rows = conn.execute("SELECT COUNT(*) FROM tx WHERE cid=?", (A,)).fetchone()[0]
        everyone = conn.execute("SELECT COUNT(DISTINCT cid) FROM tx").fetchone()[0]
        conn.close()
        kept = self.b.slim(db, 3)
        conn = sqlite3.connect(db)
        self.addCleanup(conn.close)
        cids = {r[0] for r in conn.execute("SELECT DISTINCT cid FROM tx")}
        self.assertTrue(set(personas) <= cids)
        self.assertEqual(len(cids), kept)
        self.assertLessEqual(kept, len(personas) + 3)
        self.assertLess(kept, everyone)                    # the 52 test customers are cut down
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM tx WHERE cid=?", (A,)).fetchone()[0], a_rows)
        self.assertEqual(conn.execute("SELECT * FROM bench ORDER BY 1, 2").fetchall(), bench)
        self.assertEqual({r[0] for r in conn.execute("SELECT cid FROM customers")}, cids)
        self.assertTrue({r[0] for r in conn.execute("SELECT cid FROM demo_pool")} <= cids)
        self.assertIn("statistics from all", conn.execute("SELECT value FROM meta WHERE key='slim'").fetchone()[0])
        # the same pool every time, so every build of the demo has the same random-login customers
        db2 = os.path.join(self.tmp, "slim2.db")
        shutil.copyfile(str(fx.get().db_path), db2)
        self.b.slim(db2, 3)
        c2 = sqlite3.connect(db2)
        self.addCleanup(c2.close)
        self.assertEqual({r[0] for r in c2.execute("SELECT DISTINCT cid FROM tx")}, cids)


class KeyCheckTests(unittest.TestCase):
    def setUp(self):
        fx.get()
        from deploy import check_key
        self.ck = check_key

    def run_main(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = self.ck.main(argv)
        return code, out.getvalue()

    def test_no_key_is_reported_without_a_request(self):
        code, text = self.run_main([])
        self.assertEqual(code, 1)
        self.assertIn("No Claude key is configured", text)

    def test_a_working_key_is_confirmed_and_never_printed(self):
        with fc.patched_claude(fc.FakeClaude([fc.cl_text("ok")])) as fake:
            code, text = self.run_main([])
        self.assertEqual((code, fake.calls), (0, 1))
        self.assertIn("The key works", text)
        self.assertIn("..." + fc.FAKE_KEY[-4:], text)
        self.assertIn("ANTHROPIC_API_KEY", text)
        self.assertNotIn(fc.FAKE_KEY, text)
        self.assertNotIn(fc.FAKE_KEY[:20], text)

    def test_a_refused_key_gives_exit_code_two_and_only_the_error_type(self):
        with fc.patched_claude(fc.FakeClaude([fc.http_error(401, "authentication_error")])):
            code, text = self.run_main([])
        self.assertEqual(code, 2)
        self.assertIn("did NOT work", text)
        self.assertIn("authentication_error", text)
        self.assertNotIn("details that must not be shown", text)
        self.assertNotIn(fc.FAKE_KEY, text)

    def test_no_call_only_says_where_the_key_comes_from(self):
        with fc.patched_claude(fc.FakeClaude([fc.cl_text("ok")])) as fake:
            code, text = self.run_main(["--no-call"])
        self.assertEqual((code, fake.calls), (0, 0))
        self.assertIn("Key from ANTHROPIC_API_KEY", text)


class DeployFilesTests(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(str(fx.REPO), name), encoding="utf-8") as f:
            return f.read()

    def test_the_image_holds_no_key_and_runs_as_an_ordinary_user(self):
        d = self.read("Dockerfile")
        self.assertIn("python -m deploy.build_data", d)
        self.assertIn('CMD ["python", "-m", "deploy.serve"]', d)
        self.assertIn("USER svinkki", d)
        self.assertIn("SVINKKI_PUBLIC=1", d)
        self.assertNotRegex(d, r"ANTHROPIC_API_KEY\s*=|sk-ant-|claude_api_key\.txt")
        self.assertNotRegex(d, r"(?m)^COPY \. ")              # never the whole folder
        ig = self.read(".dockerignore")
        self.assertEqual(ig.strip().splitlines()[1].strip(), "*")       # everything is left out unless listed
        for pat in ("**/.env", "**/*_api_key.txt", "**/*.db", "**/*.csv"):
            self.assertIn(pat, ig)

    def test_the_blueprint_asks_for_the_key_and_stores_none(self):
        y = self.read("render.yaml")
        self.assertRegex(y, r"- key: ANTHROPIC_API_KEY[^\n]*\n\s+sync: false")
        self.assertNotIn("sk-ant-", y)
        self.assertIn("runtime: docker", y)
        self.assertIn("SVINKKI_AI_DAILY_TURNS", y)
        self.assertIn("autoDeployTrigger: checksPass", y)

    def test_the_guide_covers_the_key_switch(self):
        g = self.read(os.path.join("docs", "DEPLOY.md"))
        for bit in ("Switching the API key", "python -m deploy.check_key", "SVINKKI_AI_DAILY_TURNS", "render.yaml",
                    "revoke"):
            self.assertIn(bit, g)


if __name__ == "__main__":
    unittest.main()
