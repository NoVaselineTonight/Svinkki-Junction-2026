"""Front page API: conversations stored per customer, "things" the customer has created, kept answers."""
import json
import os
import unittest
from unittest import mock

import fixture as fx


def _fake_chat(seen):
    def chat(message, history, ctx):
        seen.append({"message": message, "history": [dict(h) for h in history], "memory": ctx.memory})
        return {"reply": "answer to: " + message[:40], "cards": [{"type": "note", "data": {"n": len(seen)}}],
                "mode": "offline", "notice": None, "evidence": [], "ai_payload": None}
    return chat


class HomeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()
        import app.state as state
        cls.state = state

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.state.reset_all()
        self.seen = []
        p = mock.patch("app.coach.chat", side_effect=_fake_chat(self.seen))
        p.start()
        self.addCleanup(p.stop)
        self.a = fx.session(self.server, "A")
        self.b = fx.session(self.server, "B")

    def chat(self, c, msg, conv=None):
        body = {"message": msg}
        if conv:
            body["conversation_id"] = conv
        r = c.post("/api/chat", body)
        self.assertEqual(r.status, 200, r.text[:200])
        return r.json


class ConversationTests(HomeBase):
    def test_first_chat_creates_conversation_and_second_appends(self):
        r1 = self.chat(self.a, "How much did I spend on taxis?")
        cid = r1["conversation_id"]
        self.assertTrue(cid and len(cid) >= 16)
        r2 = self.chat(self.a, "and last month?", cid)
        self.assertEqual(r2["conversation_id"], cid)
        conv = self.a.get("/api/conversation?id=" + cid).json
        self.assertEqual(conv["title"], "How much did I spend on taxis?")
        self.assertEqual([t["user"] for t in conv["turns"]], ["How much did I spend on taxis?", "and last month?"])
        t = conv["turns"][0]
        for k in ("reply", "cards", "used", "mode", "notice", "ts"):
            self.assertIn(k, t)
        self.assertEqual(t["cards"][0]["type"], "note")
        # the coach got the stored history on the second turn
        self.assertEqual(self.seen[1]["history"], [
            {"role": "user", "content": "How much did I spend on taxis?"},
            {"role": "assistant", "content": "answer to: How much did I spend on taxis?"}])

    def test_conversations_do_not_leak_into_each_other(self):
        c1 = self.chat(self.a, "first topic")["conversation_id"]
        c2 = self.chat(self.a, "second topic")["conversation_id"]
        self.assertNotEqual(c1, c2)
        self.assertEqual(self.seen[1]["history"], [])
        self.chat(self.a, "more on the second", c2)
        self.assertNotIn("first topic", json.dumps(self.seen[2]["history"]))
        self.chat(self.a, "back to the first", c1)
        self.assertIn("first topic", json.dumps(self.seen[3]["history"]))
        self.assertNotIn("second topic", json.dumps(self.seen[3]["history"]))
        self.assertIsNot(self.seen[2]["memory"], self.seen[3]["memory"])

    def test_unknown_or_foreign_id_starts_a_new_conversation(self):
        cid = self.chat(self.a, "private question")["conversation_id"]
        r = self.chat(self.b, "hello", cid)
        self.assertNotEqual(r["conversation_id"], cid)
        self.assertEqual(self.seen[-1]["history"], [])
        r = self.chat(self.a, "hello", "no-such-id")
        self.assertNotEqual(r["conversation_id"], "no-such-id")

    def test_other_customer_cannot_read_or_delete(self):
        cid = self.chat(self.a, "private question")["conversation_id"]
        self.assertEqual(self.b.get("/api/conversation?id=" + cid).status, 404)
        self.assertEqual(self.b.post("/api/conversation/delete", {"id": cid}).status, 404)
        self.assertEqual(self.a.get("/api/conversation?id=" + cid).status, 200)
        self.assertEqual(self.a.get("/api/conversation?id=nope").status, 404)
        self.assertEqual(self.b.get("/api/home").json["conversations"], [])

    def test_delete(self):
        cid = self.chat(self.a, "something")["conversation_id"]
        self.assertEqual(self.a.post("/api/conversation/delete", {"id": cid}).json, {"ok": True})
        self.assertEqual(self.a.get("/api/conversation?id=" + cid).status, 404)
        self.assertEqual(self.a.get("/api/home").json["conversations"], [])

    def test_home_lists_newest_first_with_turn_counts(self):
        c1 = self.chat(self.a, "one")["conversation_id"]
        c2 = self.chat(self.a, "two")["conversation_id"]
        self.chat(self.a, "three")
        home = self.a.get("/api/home").json
        self.assertEqual([c["title"] for c in home["conversations"]], ["three", "two", "one"])
        self.chat(self.a, "again", c1)
        home = self.a.get("/api/home").json
        self.assertEqual(home["conversations"][0]["id"], c1)
        self.assertEqual(home["conversations"][0]["turns"], 2)
        self.assertEqual(set(home["conversations"][0]), {"id", "title", "updated", "turns"})
        self.assertIn("T", home["conversations"][0]["updated"])
        self.assertTrue(home["name"])
        self.assertEqual(c2, home["conversations"][2]["id"])

    def test_limits_30_conversations_and_80_turns(self):
        first = self.chat(self.a, "q0")["conversation_id"]
        for i in range(1, 31):
            self.chat(self.a, "q%d" % i)
        convs = self.a.get("/api/home").json["conversations"]
        self.assertEqual(len(convs), 30)
        self.assertEqual(self.a.get("/api/conversation?id=" + first).status, 404)
        cid = convs[0]["id"]
        for i in range(85):   # straight into the store: the chat endpoint is rate limited
            self.state.add_turn(fx.A_CID, cid, {"user": "m%d" % i, "reply": "r", "cards": [], "used": []}, "")
        conv = self.a.get("/api/conversation?id=" + cid).json
        self.assertEqual(len(conv["turns"]), 80)
        self.assertEqual(conv["turns"][-1]["user"], "m84")

    def test_oversized_turn_is_stored_without_cards(self):
        big = {"reply": "ok", "cards": [{"type": "x", "data": {"blob": "z" * 400_000}}], "mode": "offline",
               "notice": None, "evidence": []}
        with mock.patch("app.coach.chat", return_value=big):
            r = self.chat(self.a, "big one")
        self.assertTrue(r["cards"])   # the live response is untouched
        conv = self.a.get("/api/conversation?id=" + r["conversation_id"]).json
        self.assertEqual(conv["turns"][0]["cards"], [])
        self.assertEqual(conv["turns"][0]["reply"], "ok")

    def test_titles(self):
        mk = self.state.make_title
        self.assertEqual(mk("short one"), "short one")
        long = "How much did I spend on restaurants and taxis during the last three months overall"
        t = mk(long)
        self.assertLessEqual(len(t), 60)
        self.assertTrue(long.startswith(t))
        self.assertTrue(long[len(t)] == " ", "cut at a word boundary: %r" % t)
        self.assertEqual(mk("a" * 100), "a" * 60)
        self.assertEqual(mk("[pasted receipt, 300 characters]"), "A receipt")
        exact = ("word " * 12)[:60]   # 60 chars ending in a space-trimmed word
        self.assertEqual(mk(exact + "next"), exact.strip())

    def test_pasted_receipt_conversation_title_and_history(self):
        shown = {"reply": "Here is your receipt.", "cards": [], "mode": "offline", "notice": None,
                 "evidence": [], "history_user": "[pasted receipt, 40 characters]"}
        with mock.patch("app.coach.chat", return_value=shown):
            r = self.chat(self.a, "Receipt:\nmaito 1,20\nleipa 2,50\nkahvi 4,00")
        home = self.a.get("/api/home").json
        self.assertEqual(home["conversations"][0]["title"], "A receipt")
        self.assertEqual(self.state.conversation_history(
            self.a_cid(), r["conversation_id"])[0]["content"], "[pasted receipt, 40 characters]")
        conv = self.a.get("/api/conversation?id=" + r["conversation_id"]).json
        self.assertTrue(conv["turns"][0]["user"].startswith("Receipt:"))

    def a_cid(self):
        return fx.A_CID


class ThingsTests(HomeBase):
    def kinds(self, c):
        return [t["kind"] for t in c.get("/api/home").json["things"]]

    def test_things_appear_only_when_created(self):
        self.assertEqual(self.kinds(self.a), [])
        self.assertEqual(self.a.post("/api/goal", {"name": "Trip", "target": 3000, "saved": 300}).status, 200)
        things = self.a.get("/api/home").json["things"]
        self.assertEqual(things[0]["id"], "goal")
        self.assertEqual(things[0]["title"], "Trip")
        self.assertEqual(things[0]["summary"], "€300 of €3,000 saved")
        self.assertIn("T", things[0]["updated"])
        self.assertEqual(self.kinds(self.b), [])
        self.a.post("/api/goal", {"clear": True})
        self.assertEqual(self.kinds(self.a), [])

    def test_target_learned_quiz_and_order(self):
        self.a.post("/api/goal", {"name": "Bike", "target": 1200.5, "saved": 0})
        self.assertEqual(self.a.post("/api/settings", {"monthly_saving_target": 100}).status, 200)
        self.state.add_override(fx.A_CID, {"scope": "merchant", "merchant": "MX99999", "label": "Groceries"})
        self.state.add_quiz_result(fx.A_CID, {"at": "2026-09-01T10:00:00", "label": "Taxi", "guess": 30, "actual": 31})
        self.state.add_quiz_result(fx.A_CID, {"at": "2026-09-02T10:00:00", "label": "Taxi", "guess": 5, "actual": 60})
        things = self.a.get("/api/home").json["things"]
        self.assertEqual([t["kind"] for t in things], ["goal", "target", "learned", "quiz"])
        by = {t["kind"]: t for t in things}
        self.assertEqual(by["goal"]["summary"], "€0 of €1,200.50 saved")
        self.assertEqual(by["target"], {"id": "target", "kind": "target", "title": "Monthly saving target",
                                        "summary": "€100 a month"})
        self.assertEqual(by["learned"]["summary"], "1 correction")
        self.assertEqual(by["quiz"]["summary"], "1 of 2 guesses were close")
        self.a.post("/api/settings", {"monthly_saving_target": 0})
        self.assertNotIn("target", self.kinds(self.a))

    def test_active_challenge_is_listed(self):
        self.a.post("/api/settings", {"challenges": "on"})
        opts = self.a.get("/api/challenge").json["options"]
        if not opts:
            self.skipTest("no challenge options for this fixture customer")
        self.assertEqual(self.a.post("/api/challenge", {"id": opts[0]["id"]}).status, 200)
        ch = [t for t in self.a.get("/api/home").json["things"] if t["kind"] == "challenge"]
        self.assertEqual(len(ch), 1)
        self.assertEqual(ch[0]["id"], "challenge")
        self.assertTrue(ch[0]["title"])
        self.a.post("/api/challenge", {"stop": True})
        self.assertNotIn("challenge", self.kinds(self.a))

    def test_home_needs_session_and_consent(self):
        anon = self.server.client()
        self.assertEqual(anon.get("/api/home").status, 401)
        c = fx.session(self.server, "D", consent=False)
        self.assertEqual(c.get("/api/home").status, 403)


class PinTests(HomeBase):
    CARD = {"type": "spend_summary", "data": {"total": 12.5, "rows": [1, 2]}}

    def test_create_get_remove_and_home_listing(self):
        r = self.a.post("/api/pins", {"title": "Taxi spend", "card": self.CARD})
        self.assertEqual(r.status, 200, r.text[:200])
        pin = r.json
        self.assertRegex(pin["id"], r"^pin:\d+$")
        self.assertEqual(pin["title"], "Taxi spend")
        got = self.a.get("/api/pin?id=" + pin["id"]).json
        self.assertEqual(got["card"], self.CARD)
        self.assertEqual(set(got), {"id", "title", "card", "created"})
        pins = [t for t in self.a.get("/api/home").json["things"] if t["kind"] == "pin"]
        self.assertEqual(pins[0]["id"], pin["id"])
        self.assertEqual(pins[0]["card_type"], "spend_summary")
        self.assertRegex(pins[0]["summary"], r"^Saved \d{1,2} [A-Z][a-z]{2} \d{4}$")
        # another customer sees nothing and cannot touch it
        self.assertEqual(self.b.get("/api/pin?id=" + pin["id"]).status, 404)
        self.assertEqual(self.b.post("/api/pins/remove", {"id": pin["id"]}).status, 404)
        self.assertEqual(self.a.get("/api/pin?id=" + pin["id"]).status, 200)
        self.assertEqual(self.a.post("/api/pins/remove", {"id": pin["id"]}).json, {"ok": True})
        self.assertEqual(self.a.get("/api/pin?id=" + pin["id"]).status, 404)
        self.assertEqual([t for t in self.a.get("/api/home").json["things"] if t["kind"] == "pin"], [])

    def test_validation(self):
        post = lambda body: self.a.post("/api/pins", body).status   # noqa: E731
        self.assertEqual(post({"title": "", "card": self.CARD}), 400)
        self.assertEqual(post({"title": "x" * 81, "card": self.CARD}), 400)
        self.assertEqual(post({"title": "ok"}), 400)
        self.assertEqual(post({"title": "ok", "card": {"type": "bad type!", "data": {}}}), 400)
        self.assertEqual(post({"title": "ok", "card": {"type": "a" * 41, "data": {}}}), 400)
        self.assertEqual(post({"title": "ok", "card": {"type": "t", "data": [1]}}), 400)
        self.assertEqual(post({"title": "ok", "card": {"type": "t", "data": {"blob": "z" * 210_000}}}), 400)
        self.assertEqual(post({"title": "ok", "card": {"type": "t", "data": {"blob": "z" * 150_000}}}), 200)
        self.assertEqual(self.a.get("/api/pin?id=garbage").status, 404)
        self.assertEqual(self.a.post("/api/pins/remove", {"id": 5}).status, 400)

    def test_limit_of_20_drops_the_oldest(self):
        ids = [self.a.post("/api/pins", {"title": "p%d" % i, "card": self.CARD}).json["id"] for i in range(22)]
        pins = [t for t in self.a.get("/api/home").json["things"] if t["kind"] == "pin"]
        self.assertEqual(len(pins), 20)
        self.assertEqual(pins[0]["id"], ids[-1])        # newest first
        self.assertEqual(self.a.get("/api/pin?id=" + ids[0]).status, 404)
        self.assertEqual(self.a.get("/api/pin?id=" + ids[2]).status, 200)
        self.b.post("/api/pins", {"title": "b", "card": self.CARD})
        self.assertEqual(len([t for t in self.b.get("/api/home").json["things"] if t["kind"] == "pin"]), 1)


class EraseTests(HomeBase):
    def counts(self):
        import sqlite3
        import os
        con = sqlite3.connect(os.environ["SVINKKI_STATE_DB"])
        try:
            return {t: con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
                    for t in ("conversations", "turns", "pins")}
        finally:
            con.close()

    def fill(self, c):
        self.chat(c, "hello there")
        c.post("/api/pins", {"title": "kept", "card": PinTests.CARD})

    def test_erase_removes_only_this_customers_data(self):
        self.fill(self.a)
        self.fill(self.b)
        self.assertEqual(self.a.post("/api/privacy/erase", {}).status, 200)
        self.assertEqual(self.a.get("/api/home").status, 403)   # consent is erased too
        self.assertEqual(self.counts(), {"conversations": 1, "turns": 1, "pins": 1})
        self.assertEqual(self.state.list_conversations(fx.A_CID), [])
        self.assertEqual(self.state.list_pins(fx.A_CID), [])
        self.assertEqual(len(self.state.list_conversations(fx.B_CID)), 1)

    def test_reset_all_removes_everything(self):
        self.fill(self.a)
        self.fill(self.b)
        self.assertEqual(self.counts(), {"conversations": 2, "turns": 2, "pins": 2})
        self.state.reset_all()
        self.assertEqual(self.counts(), {"conversations": 0, "turns": 0, "pins": 0})



class ToolOnlyConversationTests(HomeBase):
    """A conversation that holds only a tool card (quiz, check-in, the afford form) is kept and listed."""

    def tool(self, c, name, conv=None):
        body = {"tool": name}
        if conv:
            body["conversation_id"] = conv
        return c.post("/api/conversation/tool", body)

    def test_opening_a_tool_creates_a_listed_conversation_titled_after_it(self):
        r = self.tool(self.a, "afford")
        self.assertEqual(r.status, 200, r.text[:200])
        cid = r.json["conversation_id"]
        convs = self.a.get("/api/home").json["conversations"]
        self.assertEqual([(c["id"], c["title"]) for c in convs], [(cid, "Can I afford it?")])
        conv = self.a.get("/api/conversation?id=" + cid).json
        self.assertEqual(len(conv["turns"]), 1)
        self.assertEqual(conv["turns"][0]["tool"], "afford")
        self.assertEqual(conv["turns"][0]["user"], "")
        self.assertEqual(conv["turns"][0]["cards"], [], "only the name is stored; the card is drawn fresh")

    def test_a_tool_joins_the_conversation_it_was_opened_in(self):
        cid = self.chat(self.a, "How much did I spend on taxis?")["conversation_id"]
        self.assertEqual(self.tool(self.a, "quiz", cid).json["conversation_id"], cid)
        conv = self.a.get("/api/conversation?id=" + cid).json
        self.assertEqual(conv["title"], "How much did I spend on taxis?")
        self.assertEqual([t.get("tool") for t in conv["turns"]], [None, "quiz"])

    def test_tool_turns_are_not_sent_to_the_coach_as_history(self):
        cid = self.tool(self.a, "checkin").json["conversation_id"]
        self.chat(self.a, "first question", cid)
        self.chat(self.a, "second question", cid)
        self.assertEqual(self.seen[0]["history"], [])
        self.assertEqual(self.seen[1]["history"], [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "answer to: first question"}])

    def test_unknown_tool_names_are_refused(self):
        for bad in ("explain", "", None, 5, "quiz; DROP TABLE turns", "<b>quiz</b>"):
            with self.subTest(bad=bad):
                self.assertEqual(self.tool(self.a, bad).status, 400)
        self.assertEqual(self.a.get("/api/home").json["conversations"], [])

    def test_another_customers_conversation_id_starts_a_new_one(self):
        mine = self.tool(self.a, "quiz").json["conversation_id"]
        theirs = self.tool(self.b, "quiz", mine).json["conversation_id"]
        self.assertNotEqual(mine, theirs)
        self.assertEqual(len(self.a.get("/api/conversation?id=" + mine).json["turns"]), 1)
        self.assertEqual(self.b.get("/api/conversation?id=" + mine).status, 404)

    def test_every_tool_the_web_stores_is_known_to_the_server(self):
        import re
        import app.server as server
        with open(os.path.join(fx.REPO, "web", "app.js"), encoding="utf-8") as f:
            js = f.read()
        block = re.search(r"var STORED_TOOLS = \{([^}]+)\}", js).group(1)
        names = set(re.findall(r"(\w+): 1", block))
        self.assertEqual(names, set(server.CONVERSATION_TOOLS))
        self.assertIn("if (tn.tool) { insert(tn.tool, null, true); return; }", js)

if __name__ == "__main__":
    unittest.main()
