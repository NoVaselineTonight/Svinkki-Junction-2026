"""The start page: a few example questions show that real questions work, last month is shown in the three
baskets, the check-in and the quiz are closed rows, and nothing empty is shown. Static checks on web/app.js
plus routing of every question a chip sends.
"""
import os
import re
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx


def _js():
    with open(os.path.join(fx.REPO, "web", "app.js"), encoding="utf-8") as f:
        return f.read()


def _css():
    with open(os.path.join(fx.REPO, "web", "styles.css"), encoding="utf-8") as f:
        return f.read()


class StartPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        cls.coach = coach
        cls.js = _js()
        block = cls.js[cls.js.index("var SUGGEST = ["):]
        cls.block = block[:block.index("];") + 1]
        follow = cls.js[cls.js.index("var FOLLOW = {"):]
        cls.follow = follow[:follow.index("function suggestChips(")]
        home = cls.js[cls.js.index("function showHome()"):]
        cls.home = home[:home.index("function convRow(")]

    def test_a_few_short_example_questions_each_doing_one_thing(self):
        """Not a wall of tiles: three to five chips, each short enough for one line on a phone."""
        rows = [l for l in self.block.splitlines() if "label:" in l]
        self.assertTrue(3 <= len(rows) <= 5, len(rows))
        for l in rows:
            with self.subTest(l=l.strip()[:40]):
                label = re.search(r"label: '([^']+)'", l).group(1)
                self.assertLessEqual(len(label), 30)
                self.assertEqual(len(re.findall(r"\b(?:q|act|fill): '", l)), 1)
                self.assertNotIn("hint:", l)

    def test_examples_cover_the_briefs_core_questions(self):
        low = self.block.lower()
        for bit in ("spend this week", "spender", "save more", "afford"):
            self.assertIn(bit, low)

    def test_every_question_a_chip_sends_is_understood_without_a_model(self):
        qs = re.findall(r"\bq: '([^']+)'", self.block) + re.findall(r"'([^']+\?|Give me a challenge|Show my receipts)'", self.follow)
        self.assertGreaterEqual(len(qs), 10)
        for q in qs:
            with self.subTest(q=q):
                self.assertIsNotNone(self.coach.route(q, fx.make_ctx(fx.A_CID)))

    def test_every_tool_a_chip_opens_exists_in_the_conversation(self):
        for act in re.findall(r"\bact: '([^']+)'", self.block):
            with self.subTest(act=act):
                self.assertRegex(self.js, r"act: '%s'" % act)
        self.assertIn("a === 'explain'", self.js)

    def test_the_rest_is_one_link_that_names_what_is_behind_it(self):
        self.assertIn("'Goals, receipts, contracts and more'", self.home)
        self.assertIn("onclick: function () { openAsk(); }", self.home)

    def test_last_month_in_three_baskets_is_on_the_start_page(self):
        self.assertIn("api('/api/baskets')", self.home)
        self.assertIn("monthBaskets(d)", self.home)
        mb = self.js[self.js.index("function monthBaskets(d)"):]
        mb = mb[:mb.index("\n  }\n")]
        self.assertIn("BASKET_BLURB[k]", mb, "each basket says what goes in it")
        self.assertIn("openEvidence(b.evidence, name)", mb, "a basket opens its own transactions")
        self.assertIn("total <= 0) return null", mb, "no empty card")

    def test_follow_ups_only_under_the_latest_answer_and_never_in_another_language(self):
        chat = self.js[self.js.index("function buildChat(opts)"):]
        self.assertIn("dropFollow();\n      // A pasted receipt", chat, "sending removes the old follow-ups")
        self.assertIn("addFollow(m, followUps(res, text));", chat)
        fu = self.js[self.js.index("function followUps(res, asked)"):]
        fu = fu[:fu.index("function suggestChips(")]
        self.assertIn("return [];", fu)
        self.assertRegex(fu, r"paljonko\|mitä")
        self.assertIn(".slice(0, 2)", fu)

    def test_account_card_shows_balance_and_safe_to_spend_only(self):
        card = self.js[self.js.index("function accountCard(a)"):]
        card = card[:card.index("function openAccount(")]
        self.assertNotIn("cur.number", card)
        self.assertNotIn("Demo account", card)
        self.assertIn("num(sav.balance) > 0 ?", card)
        self.assertIn("acct-safe", card)

    def test_new_only_inside_a_conversation(self):
        self.assertIn("document.getElementById('new-btn').hidden = screen !== 'conv';", self.js)

    def test_checkin_quiz_and_worth_a_look_are_closed_rows(self):
        for key in ("checkin", "quiz", "alerts"):
            with self.subTest(key=key):
                self.assertRegex(self.home, r"place\('%s', fold\(" % key)
        fold = self.js[self.js.index("function fold("):]
        fold = fold[:fold.index("\n  }\n") + 5]
        self.assertIn("h('details', { class: 'fold' }", fold)
        self.assertNotIn(".open = true", fold, "closed until the customer opens it")

    def test_no_empty_box_and_no_leftover_starter_chips(self):
        self.assertNotIn("show up here", self.home)
        self.assertIn("thingsBox.hidden = !things.length", self.home)
        self.assertNotIn("STARTERS", self.js)

    def test_order_account_question_box_examples_month_then_for_you(self):
        order = re.search(r"h\('div', \{ class: 'greet' \}.*?\),\s*acctBox,\s*comp\.el, suggest, monthBox, forYou, convBox, thingsBox\)\)",
                          self.home, re.S)
        self.assertIsNotNone(order)

    def test_styles_exist_for_the_new_parts_and_no_default_marker_shows(self):
        css = _css()
        for sel in (".fold > summary", ".fold-body", ".chips.suggest .chip", ".month-card", ".month-row", ".acct-safe", ".follow"):
            self.assertIn(sel, css)
        for gone in (".tool-hint", ".home-tools", ".acct-demo", ".tx-fix"):
            self.assertNotIn(gone, css)
        self.assertIn(".fold > summary::-webkit-details-marker { display: none; }", css)
        self.assertRegex(css, r"\.fold > summary \{[^}]*list-style: none")

    def test_greeting_line_uses_the_customers_own_month(self):
        self.assertIn("greetLine.textContent = sur >= 0", self.home)
        self.assertIn("'You kept ' + money(sur) + ' in ' + when", self.home)
        self.assertIn("more went out than came in", self.home)

    def test_a_checkin_without_income_shows_what_was_spent_not_a_shortfall(self):
        card = self.js[self.js.index("function checkinCard(c)"):]
        card = card[:card.index("function suggestionBlock")]
        self.assertIn("if (num(c.income) > 0) {", card)
        self.assertIn("keyFig(sec, money(c.spent), 'spent');", card)
        self.assertIn("num(c.income) <= 0 ? money(c.spent) + ' spent'", self.home)
        self.assertIn("if (alive(t) && when && num(c.income) > 0) {", self.home)

    def test_welcome_does_not_claim_money_never_moves(self):
        """Money can move inside S-mobiili after approval, so the welcome must not say it never does."""
        self.assertNotIn("I never move money", self.js)
        self.assertIn("Money only moves when you approve it", self.js)

    def test_the_sheet_starts_short_one_closed_topic_each(self):
        ask = self.js[self.js.index("function openAsk()"):]
        ask = ask[:ask.index("// ---------- transactions browser")]
        self.assertIn("openSheet('Everything I can do'", ask)
        self.assertIn("topics.appendChild(fold(", ask)
        self.assertNotIn("ASK_TOOLS", self.js, "tools live inside their topic, not in a second grid")

    def test_no_empty_card_when_nothing_was_spent(self):
        self.assertIn("if (c.type === 'spend' && !num(d.total) && !num(d.count)) return null;", self.js)

    def test_house_rules_no_inner_html(self):
        self.assertNotRegex(self.js, r"\.(?:inner|outer)HTML\s*[+]?=|insertAdjacentHTML|document\.write")


if __name__ == "__main__":
    unittest.main()
