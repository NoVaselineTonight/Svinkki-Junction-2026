"""What the model sees: only anonymised data (agent-s6, priority 2).

A. explore_my_data: the model's SQL runs on a copy of the customer's transactions that has no merchant
   column, so an expression such as '#'||merchant cannot carry a merchant id past coach.anonymise.
B. tools.model_payload: list_transactions, get_receipts and find_leaks send the model aggregates and a few
   trimmed rows (no timestamps, no receipt transaction ids, no merchant hashes); the card keeps everything.
C. tools.mask_names: first names from a built-in list are replaced with [name] in what the customer types.
D. The coach wiring for B and C and the Gemini path (coach.py, held by another agent): expectedFailure until
   the coach.py change lands; that change removes the decorators.
"""
import json
import os
import sqlite3
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc


def _merchants(cid=fx.A_CID):
    conn = fx.open_db()
    try:
        return sorted({r[0] for r in conn.execute("SELECT DISTINCT merchant FROM tx WHERE cid = ?", (cid,))
                       if r[0]})
    finally:
        conn.close()


def _leaks(text, merchants):
    """Merchant ids (or their distinctive tail, e.g. 30111 of MX30111) that appear in text."""
    out = []
    for m in merchants:
        tail = m[2:] if m.upper().startswith("MX") else m
        if m.lower() in text.lower() or (len(tail) >= 4 and tail in text):
            out.append(m)
    return out


LEAKY_SQL = (
    "SELECT d, '#' || merchant AS m FROM tx WHERE merchant <> '' LIMIT 20",
    "SELECT d, merchant || '' AS m FROM tx WHERE merchant <> '' LIMIT 20",
    "SELECT lower(merchant) AS m FROM tx LIMIT 20",
    "SELECT substr(merchant, 3) AS m FROM tx LIMIT 20",
    "SELECT CASE WHEN merchant <> '' THEN 'x' || merchant END AS m FROM tx LIMIT 20",
    "SELECT (SELECT 'id:' || merchant FROM tx t2 WHERE t2.merchant <> '' LIMIT 1) AS m FROM tx LIMIT 1",
    "SELECT replace(merchant, 'MX', 'Q') AS m, count(*) FROM tx GROUP BY merchant",
    "WITH x AS (SELECT merchant AS q FROM tx) SELECT '#' || q FROM x LIMIT 20",
    "SELECT * FROM tx LIMIT 20",
)


class ExploreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach, db, tools
        cls.coach, cls.db, cls.tools = coach, db, tools
        cls.merchants = _merchants()
        assert cls.merchants, "the fixture customer needs merchants"

    def test_no_sql_expression_gets_a_merchant_id_to_the_model(self):
        ctx = fx.make_ctx()
        for sql in LEAKY_SQL:
            with self.subTest(sql=sql):
                res = self.tools.call("explore_my_data", {"sql": sql}, ctx)
                view = json.dumps(self.coach._model_view(res))
                self.assertEqual(_leaks(view, self.merchants), [])
                self.assertEqual(_leaks(json.dumps(res), self.merchants), [])   # nor on the card

    def test_merchant_cannot_be_used_as_an_oracle(self):
        ctx = fx.make_ctx()
        res = self.tools.call("explore_my_data",
                              {"sql": "SELECT count(*) FROM tx WHERE merchant LIKE 'MX3%'"}, ctx)
        self.assertIn("error", res)

    def test_ordinary_queries_still_work(self):
        ctx = fx.make_ctx()
        res = self.tools.call("explore_my_data", {"sql": "SELECT label, round(sum(amount), 2) AS s, count(*) AS n "
                                                         "FROM tx GROUP BY label ORDER BY s LIMIT 5"}, ctx)
        self.assertNotIn("error", res)
        self.assertEqual(res["columns"], ["label", "s", "n"])
        self.assertTrue(res["rows"])
        res = self.tools.call("explore_my_data", {"sql": "SELECT min(balance), max(d), count(*) FROM tx"}, ctx)
        n = ctx.conn.execute("SELECT count(*) FROM tx").fetchone()[0]
        self.assertEqual(res["rows"][0][2], n)
        self.assertEqual(res["rows"][0][1], ctx.conn.execute("SELECT max(d) FROM tx").fetchone()[0])

    def test_the_explore_copy_has_no_identifying_column_and_is_read_only(self):
        ctx = fx.make_ctx()
        copy = self.db.model_copy(ctx.conn)
        try:
            cols = [r[1] for r in copy.execute("PRAGMA table_info(tx)")]
            self.assertEqual(tuple(cols), self.db.MODEL_COLUMNS)
            for banned in ("merchant", "merchant_id", "cid", "customer", "customer_id", "postal", "account_id"):
                self.assertNotIn(banned, cols)
            self.assertEqual(copy.execute("SELECT count(*) FROM tx").fetchone()[0],
                             ctx.conn.execute("SELECT count(*) FROM tx").fetchone()[0])
            with self.assertRaises(sqlite3.OperationalError):
                copy.execute("DELETE FROM tx")
        finally:
            copy.close()
        # the sandbox itself still has the merchant (server-side features use it); it is never queried by the model
        self.assertIn("merchant", [r[1] for r in ctx.conn.execute("PRAGMA table_info(tx)")])

    def test_the_tool_description_does_not_offer_a_merchant_column(self):
        desc = next(t for t in self.tools.TOOLS if t["name"] == "explore_my_data")["description"]
        self.assertNotIn("merchant", desc.lower())


class ModelPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import tools
        cls.tools = tools

    def test_list_transactions_rows_are_trimmed_for_the_model(self):
        ctx = fx.make_ctx()
        res = self.tools.call("list_transactions", {"limit": 50}, ctx)
        self.assertGreater(len(res["rows"]), self.tools.MODEL_TX_ROWS)
        before = json.dumps(res, sort_keys=True)
        out = self.tools.model_payload(res)
        self.assertEqual(json.dumps(res, sort_keys=True), before, "the card result must not change")
        self.assertEqual(len(out["rows"]), self.tools.MODEL_TX_ROWS)
        self.assertEqual(out["rows_left_out"], len(res["rows"]) - self.tools.MODEL_TX_ROWS)
        for k in ("count", "total", "spent", "truncated"):
            self.assertEqual(out[k], res[k])
        for r in out["rows"]:
            self.assertLessEqual(set(r), set(self.tools.MODEL_TX_FIELDS))
            self.assertNotIn("ts", r)
            self.assertNotIn("merchant", r)
        self.assertIn("ts", res["rows"][0])     # the web card keeps the time

    def test_receipts_lose_timestamps_and_transaction_ids(self):
        ctx = fx.make_ctx(cid=fx.D_CID)
        res = self.tools.call("get_receipts", {"period": "last_3_months", "limit": 3}, ctx)
        self.assertTrue(res.get("receipts"))
        out = self.tools.model_payload(res)
        for r in out["receipts"]:
            self.assertNotIn("ts", r)
            self.assertNotIn("tx_id", r)
            self.assertIn("store", r)
            self.assertIn("lines", r)
        self.assertIn("tx_id", res["receipts"][0])

    def test_merchant_hash_never_goes_to_the_model(self):
        res = {"card": "leaks", "subscriptions": [{"merchant_ref": "ab12cd34", "label": "Streaming", "amount": 9.99}],
               "nested": [{"x": {"merchant_ref": "ff00ff00"}}]}
        out = self.tools.model_payload(res)
        self.assertNotIn("merchant_ref", json.dumps(out))
        self.assertEqual(out["subscriptions"][0]["label"], "Streaming")
        self.assertIn("merchant_ref", res["subscriptions"][0])

    def test_other_results_pass_through(self):
        res = {"card": "spend", "total": 12.5, "rows": [{"ts": "2026-01-01 10:00:00", "x": 1}]}
        self.assertEqual(self.tools.model_payload(res), res)
        self.assertEqual(self.tools.model_payload("x"), "x")


class MaskNamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import tools
        cls.tools = tools

    def test_first_names_are_replaced(self):
        for msg, want in (("Did Anna pay me back?", "Did [name] pay me back?"),
                          ("How much did I lend my friend Matti?", "How much did I lend my friend [name]?"),
                          ("Lainasin Annalle 50 euroa", "Lainasin [name] 50 euroa"),
                          ("Was Jessica's dinner on my card?", "Was [name] dinner on my card?"),
                          ("Ostin Veetin kanssa ruokaa", "Ostin [name] kanssa ruokaa")):
            with self.subTest(msg=msg):
                self.assertEqual(self.tools.mask_names(msg)[0], want)

    def test_counts_replacements(self):
        self.assertEqual(self.tools.mask_names("Anna and Matti and Liisa")[1], 3)
        self.assertEqual(self.tools.mask_names("Anna paid me back. Anna minulle vinkki.")[1], 1)
        self.assertEqual(self.tools.mask_names("How much on taxis?")[1], 0)

    def test_words_that_only_look_like_names_are_kept(self):
        for msg in ("Anna minulle vinkki säästämiseen", "Anna lisää vinkkejä", "anna me a tip",
                    "How much at Prisma and Alepa?", "What did I spend at Max and Tim Hortons?",
                    "Time to save more", "Will I make it in May or June?", "Onni on tärkeintä",
                    "My Elisa phone bill", "How much do I spend at Sale?"):
            with self.subTest(msg=msg):
                self.assertEqual(self.tools.mask_names(msg)[0], msg)

    def test_not_a_string(self):
        self.assertEqual(self.tools.mask_names(None), ("", 0))


def _fake_gemini_text(text):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}]}


class CoachWiringTests(unittest.TestCase):
    """Needs the coach.py change (agent-s6 report): until then these fail and are marked expectedFailure."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        from app import coach, tools
        cls.coach, cls.tools = coach, tools

    @unittest.expectedFailure
    def test_model_view_uses_model_payload(self):
        ctx = fx.make_ctx()
        view = self.coach._model_view(self.tools.call("list_transactions", {"limit": 50}, ctx))
        self.assertLessEqual(len(view["rows"]), self.tools.MODEL_TX_ROWS)
        self.assertNotIn('"ts"', json.dumps(view))

    @unittest.expectedFailure
    def test_find_leaks_view_has_no_merchant_hash(self):
        view = self.coach._model_view({"card": "leaks", "subscriptions": [{"merchant_ref": "ab12cd34", "label": "x"}]})
        self.assertNotIn("merchant_ref", json.dumps(view))

    @unittest.expectedFailure
    def test_gemini_path_sends_the_anonymised_message(self):
        ctx = fx.make_ctx()
        seen = []

        def fake_generate(system, contents, declared, key, model, http_post=None):
            seen.append(json.loads(json.dumps(contents)))
            return _fake_gemini_text("Fine.")
        with mock.patch.object(self.coach.llm_gemini, "generate", fake_generate):
            _, _, payload = self.coach._gemini_turn("Did Anna pay MRC-GRO-0035 back?", [], ctx, "k")
        sent = json.dumps(seen[0][-1])
        self.assertNotIn("MRC-GRO-0035", sent)
        self.assertNotIn("Anna", sent)
        self.assertNotIn("Anna", json.dumps(payload["user_message"]))

    @unittest.expectedFailure
    def test_claude_path_masks_names_in_message_and_history(self):
        ctx = fx.make_ctx()
        seen = []

        def fake_create(system, messages, declared, key, model, **kw):
            seen.append(json.loads(json.dumps(messages)))
            return fc.cl_text("Fine.")
        history = [{"role": "user", "text": "I lent Matti 40 euros"}, {"role": "assistant", "text": "Noted."}]
        with mock.patch.object(self.coach.llm_claude, "create", fake_create):
            _, _, payload = self.coach._claude_turn("Did Anna pay me back?", history, ctx, fc.FAKE_KEY)
        sent = json.dumps(seen[0])
        self.assertNotIn("Anna", sent)
        self.assertNotIn("Matti", sent)
        self.assertIn("[name]", payload["user_message"])
        self.assertNotIn("Matti", json.dumps(payload["history"]))


if __name__ == "__main__":
    unittest.main()
