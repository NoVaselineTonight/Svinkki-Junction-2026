"""The start page: what the coach can do is visible at once, the check-in and the quiz are closed rows,
and nothing empty is shown. Static checks on web/app.js plus routing of every question a tile sends.
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
        block = cls.js[cls.js.index("var HOME_TOOLS = ["):]
        cls.block = block[:block.index("];") + 1]
        home = cls.js[cls.js.index("function showHome()"):]
        cls.home = home[:home.index("function convRow(")]

    def test_six_tiles_each_with_a_label_a_hint_and_one_thing_it_does(self):
        rows = [l for l in self.block.splitlines() if "label:" in l]
        self.assertEqual(len(rows), 6)
        for l in rows:
            with self.subTest(l=l.strip()[:40]):
                self.assertRegex(l, r"hint: '[^']{8,40}'")
                self.assertEqual(len(re.findall(r"\b(?:q|act|fill): '", l)), 1)
                self.assertRegex(l, r"icon: '\w+'")

    def test_tiles_show_the_advanced_things(self):
        for word in ("afford", "receipts", "goal", "payday", "contract", "save"):
            self.assertIn(word, self.block.lower())

    def test_every_question_a_tile_sends_is_understood_without_a_model(self):
        qs = re.findall(r"\bq: '([^']+)'", self.block)
        self.assertGreaterEqual(len(qs), 3)
        for q in qs:
            with self.subTest(q=q):
                self.assertIsNotNone(self.coach.route(q, fx.make_ctx(fx.A_CID)))

    def test_every_tool_a_tile_opens_exists_in_the_conversation(self):
        for act in re.findall(r"\bact: '([^']+)'", self.block):
            with self.subTest(act=act):
                self.assertRegex(self.js, r"act: '%s'" % act)
        self.assertIn("a === 'explain'", self.js)

    def test_the_sentence_a_tile_starts_becomes_a_goal_once_finished(self):
        fill = re.findall(r"\bfill: '([^']+)'", self.block)
        self.assertEqual(len(fill), 1)
        routed = self.coach.route(fill[0] + "a trip to Japan", fx.make_ctx(fx.A_CID))
        self.assertIsNotNone(routed)
        self.assertEqual(routed[0], "plan_goal_by_date")

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

    def test_order_account_question_box_tools_then_for_you(self):
        order = re.search(r"acctBox,\s*h\('div', \{ class: 'greet' \}.*?\),\s*comp\.el, toolsBox, forYou, convBox, thingsBox\)\)",
                          self.home, re.S)
        self.assertIsNotNone(order)

    def test_styles_exist_for_the_new_parts_and_no_default_marker_shows(self):
        css = _css()
        for sel in (".fold > summary", ".fold-body", ".tool-hint", ".home-tools .tool"):
            self.assertIn(sel, css)
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

    def test_the_sheet_is_named_like_the_link_that_opens_it(self):
        self.assertIn("'Everything I can do');", self.home)
        self.assertIn("openSheet('Everything I can do'", self.js)

    def test_no_empty_card_when_nothing_was_spent(self):
        self.assertIn("if (c.type === 'spend' && !num(d.total) && !num(d.count)) return null;", self.js)

    def test_house_rules_no_inner_html(self):
        self.assertNotRegex(self.js, r"\.(?:inner|outer)HTML\s*[+]?=|insertAdjacentHTML|document\.write")


if __name__ == "__main__":
    unittest.main()
