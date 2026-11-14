"""Web UX defects a judge can hit, pinned as static checks on web/app.js (there is no JS engine in the
standard library). Each behaviour was also checked by hand in headless Edge at phone width.

a. A quiz answer or an approved money move on Home stays visible: Home is not redrawn under the customer.
b. Edits made in a sheet (goal, notes, settings, categories) show on Home when the sheet closes.
c. The phone's Back button closes a sheet, leaves a conversation to Home, and leaves the app only from Home.
d. Home shows a short error with a retry when its data cannot be loaded.
e. The welcome only says an AI helps with the wording when a model is connected.
f. Every answer says where it came from: "On-device rules" or the model's name, plus any notice.
g. Cards show looked-up amounts with the same cents as the answer (the taxi answer and its card).
"""
import os
import re
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx


def _read(name):
    with open(os.path.join(fx.REPO, "web", name), encoding="utf-8") as f:
        return f.read()


def _fn(js, head, end="\n  }\n"):
    """The text of one top-level function in app.js, from its head to its closing brace."""
    i = js.index(head)
    return js[i:js.index(end, i) + len(end)]


class HomeKeepsResultsTests(unittest.TestCase):
    """a and b."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read("app.js")

    def test_a_change_never_redraws_home_under_the_customer(self):
        body = _fn(self.js, "function thingsChanged()")
        self.assertNotIn("showHome(", body, "a full redraw wipes the quiz result or the money move just shown")
        self.assertIn("homeStale", body)

    def test_home_refreshes_its_lists_in_place(self):
        home = _fn(self.js, "function showHome()")
        self.assertIn("homeRefresh = refresh", home, "Home can refresh its lists without clearing the page")
        refresh = home[home.index("function refresh("):home.index("homeRefresh = refresh")]
        for bit in ("api('/api/account')", "api('/api/baskets')", "api('/api/home')"):
            self.assertIn(bit, refresh)
        self.assertNotIn("clearView()", refresh)
        self.assertNotIn("api('/api/quiz')", refresh, "the quiz row keeps the answer the customer just got")

    def test_closing_a_sheet_brings_home_up_to_date(self):
        body = _fn(self.js, "function closeSheet(")
        self.assertIn("homeStale", body)
        self.assertRegex(body, r"homeRefresh\(\)|showHome\(\)")

    def test_settings_mark_home_stale(self):
        body = _fn(self.js, "function openSettings()")
        self.assertGreaterEqual(body.count("markHomeStale(true)"), 2, "check-in, quiz and consent changes reach Home")

    def test_every_sheet_edit_reports_a_change(self):
        # goal, target, note, pin: through `done`; categories and the learned list: thingsChanged directly
        self.assertIn("var done = function () { closeSheet(); thingsChanged(); };", self.js)
        picker = _fn(self.js, "function categoryPicker(")
        self.assertIn("thingsChanged();", picker)


class BackButtonTests(unittest.TestCase):
    """c."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read("app.js")

    def test_one_popstate_handler(self):
        self.assertEqual(self.js.count("addEventListener('popstate'"), 1)

    def test_a_sheet_and_a_conversation_each_add_a_history_entry(self):
        self.assertIn("pushNav(", _fn(self.js, "function openSheet("))
        self.assertIn("pushNav(", _fn(self.js, "function openConversation("))

    def test_closing_a_sheet_by_hand_takes_its_entry_back_off(self):
        body = _fn(self.js, "function closeSheet(")
        self.assertIn("popNav()", body)
        self.assertIn("fromPop", body, "a sheet closed by Back does not go back twice")

    def test_back_from_a_conversation_goes_home_and_home_is_the_bottom(self):
        pop = _fn(self.js, "function onPop(")
        self.assertIn("closeSheet({ fromPop: true })", pop)
        self.assertIn("showHome()", pop)
        self.assertIn("history.replaceState(", self.js, "the first screen is the bottom entry")
        nav = _fn(self.js, "function popNav(")
        self.assertIn("history.back()", nav)

    def test_leaving_a_conversation_any_way_removes_its_entry(self):
        for head in ("function showHome()", "function showLogin()", "function showConsent()", "function boot()"):
            with self.subTest(head=head):
                self.assertIn("leaveConv()", _fn(self.js, head))


class HomeErrorTests(unittest.TestCase):
    """d."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read("app.js")
        cls.home = _fn(cls.js, "function showHome()")

    def test_no_home_fetch_swallows_its_error(self):
        self.assertNotIn("function () {});", self.home)
        self.assertGreaterEqual(self.home.count("homeFailed"), 6)

    def test_the_error_is_short_plain_and_has_a_retry(self):
        body = _fn(self.js, "function homeErrorNode(")
        self.assertIn("role: 'alert'", body)
        self.assertIn("'Try again'", body)
        self.assertRegex(body, r"could not (load|be loaded)")

    def test_the_old_home_list_is_used_only_when_the_server_has_none(self):
        self.assertIn("e.status === 404", self.home[self.home.index("api('/api/home')"):])


class WelcomeTests(unittest.TestCase):
    """e."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read("app.js")

    def test_the_ai_sentence_depends_on_a_connected_model(self):
        body = _fn(self.js, "function showConsent()")
        self.assertIn("me.ai_available", body)
        i = body.index("An AI helps with the wording")
        self.assertIn("?", body[body.rindex("ai_available", 0, i):i], "the AI sentence is one side of a choice")
        self.assertIn("built-in rules", body)

    def test_the_server_says_whether_a_model_is_connected(self):
        with open(os.path.join(fx.REPO, "app", "server.py"), encoding="utf-8") as f:
            self.assertIn('"ai_available": bool(config.ai_provider())', f.read())


class SourceLabelTests(unittest.TestCase):
    """f."""

    @classmethod
    def setUpClass(cls):
        cls.js = _read("app.js")
        cls.reply = _fn(cls.js, "function botReply(", "\n    }\n")

    def test_every_answer_names_its_source(self):
        src = _fn(self.js, "function sourceLabel(")
        self.assertIn("'On-device rules'", src)
        self.assertIn("mode === 'offline'", src)
        self.assertIn("res.model", src, "a model name sent with the answer wins")
        self.assertIn("aiModelName", src)
        self.assertIn("sourceLabel(res)", self.reply)
        self.assertNotIn("if (isAiMode(res.mode)) acts.appendChild", self.reply, "not only AI answers are labelled")

    def test_the_model_name_comes_from_the_setup_without_the_note(self):
        body = _fn(self.js, "function loadModelName(")
        self.assertIn("api('/api/demo/ai')", body)
        self.assertIn("replace(/\\s*\\(.*\\)\\s*$/, '')", body, "'Claude Opus 5.5', not '(best answers)'")

    def test_the_notice_is_shown_small(self):
        self.assertIn("if (res.notice) m.appendChild(h('p', { class: 'tiny reply-note' }", self.reply)

    def test_the_label_is_small_and_plain(self):
        css = _read("styles.css")
        rule = re.search(r"\.source-tag \{([^}]*)\}", css)
        self.assertIsNotNone(rule)
        self.assertIn("font-size", rule.group(1))


class ExactAmountTests(unittest.TestCase):
    """g."""

    @classmethod
    def setUpClass(cls):
        fx.get()
        cls.js = _read("app.js")

    def card(self, name):
        i = self.js.index("    %s: function (d) {" % name)
        return self.js[i:self.js.index("\n    },\n", i)]

    def test_the_taxi_answer_has_cents(self):
        import app.coach as coach
        res = coach.chat("How much did I spend on taxis last month?", [], fx.make_ctx(fx.A_CID))
        self.assertRegex(res["reply"], r"€\d+\.\d\d", "the answer keeps the cents of a looked-up total")

    def test_spend_card_keeps_the_cents(self):
        c = self.card("spend")
        self.assertIn("keyFig(c, money(d.total, EXACT)", c)
        self.assertIn("labelBars(labels.slice(0, 8), maxOf(labels), null, true)", c)
        self.assertIn("money(np.total, EXACT)", c)

    def test_other_looked_up_amounts_keep_the_cents(self):
        self.assertIn("money(d.total != null ? d.total : d.lines_total, EXACT)", self.card("receipt_parsed"))
        self.assertIn("['In total', money(d.total, EXACT)]", self.card("receipts"))
        self.assertIn("money(x.amount, EXACT)", self.card("money_holdings"))
        self.assertIn("['Money in your account', money(d.balance, EXACT)]", self.card("safe_to_spend"))

    def test_bars_can_show_cents(self):
        body = _fn(self.js, "function labelBars(")
        self.assertIn("exact ? money(v, EXACT) : null", body)


if __name__ == "__main__":
    unittest.main()
