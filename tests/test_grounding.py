"""app/grounding.py: the figure table, slots filled by code, and the referent-aware raw checker.

Pure functions on hand-made tool results: no database, no network."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app import grounding as g  # noqa: E402

TODAY = "2026-09-26"
SPEND = ("get_spend", {"label": "Taxi", "period": "last_month"},
         {"period": {"from": "2026-08-01", "to": "2026-08-31", "name": "last_month"}, "total": 92.85, "count": 4,
          "by_label": [{"label": "Taxi", "total": 92.85, "count": 4}],
          "explain": "Added up 4 outgoing payments for taxis in August. €28 of this was on a night out.",
          "evidence": [{"title": "Taxi purchases", "from": "2026-08-01", "to": "2026-08-31", "label": "Taxi"}]})
OVERVIEW = ("get_overview", {},
            {"month": "2026-08", "period": {"from": "2026-08-01", "to": "2026-08-31"}, "income": 2336.0,
             "spent": 1571.15, "saved": 200.0, "surplus": 564.85,
             "top_labels": [{"label": "Housing", "total": 900.0, "count": 1, "share": 0.57,
                             "evidence": {"title": "Housing", "from": "2026-08-01", "to": "2026-08-31"}},
                            {"label": "Groceries", "total": 251.15, "count": 5, "share": 0.16}]})
CALLS = [SPEND, OVERVIEW]


def table(calls=CALLS, message="", **kw):
    return g.build_table(calls, message=message, today=TODAY, **kw)


def ok(text, calls=CALLS, message="", **kw):
    return g.numbers_grounded(text, calls, message, today=TODAY, **kw)


class RawChecker(unittest.TestCase):
    """The four sentences the old default check let through, and their honest counterparts."""

    def test_income_stated_as_taxi_spending_fails(self):
        self.assertFalse(ok("You spent €2,336 on taxis last month."))

    def test_invented_finnish_euroa_fails(self):
        self.assertFalse(ok("Käytit takseihin 450 euroa viime kuussa."))

    def test_bare_number_and_percent_fail(self):
        self.assertFalse(ok("You spent 450 on taxis, which is 45% of your income."))

    def test_monthly_total_said_every_week_fails(self):
        self.assertFalse(ok("You spend €92.85 on taxis every week."))

    def test_true_sentence_passes(self):
        self.assertTrue(ok("You spent €92.85 on taxis last month."))

    def test_true_sentences_pass(self):
        for s in ("Käytit takseihin 92,85 € viime kuussa.",
                  "Käytit takseihin 92,85 euroa elokuussa.",
                  "You spent €92.85 on taxis in August, €28 of it on a night out.",
                  "Your income in August was €2,336.",
                  "You spent €92.85 on taxis last month (4 payments), about €93 a month.",
                  "Housing took 57% of your spending in August."):
            self.assertTrue(ok(s), s)

    def test_wrong_month_fails(self):
        self.assertFalse(ok("You spent €92.85 on taxis in July."))

    def test_finnish_week_rate_fails(self):
        self.assertFalse(ok("Käytät takseihin 92,85 € viikossa."))

    def test_wrong_category_fails(self):
        self.assertFalse(ok("You spent €251.15 on taxis last month."))
        self.assertFalse(ok("Taxis took 57% of your spending."))

    def test_customer_figure_is_not_their_data(self):
        msg = "I spend about 450 on taxis, right?"
        self.assertFalse(ok("You spent 450 on taxis last month.", message=msg))
        self.assertTrue(ok("Not quite: you spent €92.85 on taxis last month, well under the 450 you guessed.",
                           message=msg))
        self.assertTrue(ok("A €1,200 sofa would be more than your August spending on groceries.",
                           message="Can I afford a €1,200 sofa?"))

    def test_free_numbers(self):
        for s in ("Over the last 12 months your income held steady.", "In 2025 you went out more.",
                  "Most of it lands between 15:00 and 16:00.", "Try cooking 1 in 5 meals at home."):
            self.assertTrue(ok(s), s)

    def test_dates_must_be_known(self):
        self.assertTrue(ok("Those taxis were paid between 1 August and 31 August."))
        self.assertFalse(ok("Your next payday is 17 October."))
        cal = CALLS + [("get_safe_to_spend", {}, {"next_payday": "2026-10-15", "safe_total": 400.0})]
        self.assertTrue(ok("Your next payday is 15 October.", cal))
        self.assertTrue(ok("Seuraava palkkapäiväsi on 15.10.", cal))

    def test_snapshot_and_earlier_answers_count(self):
        lines = ["Their usual month, on the last 12 full months: about €3,000 comes in and about €1,621 goes out, "
                 "which leaves about €1,379 a month."]
        self.assertTrue(ok("A usual month leaves you about €1,379.", snapshot_lines=lines))
        self.assertFalse(ok("A usual month leaves you about €1,379 every week.", snapshot_lines=lines))
        self.assertTrue(ok("As I said, that was €61 on a night out.",
                           earlier=["Your nights out cost €61 in August."]))

    def test_spans_point_at_the_figure(self):
        text = "You spent €92.85 on taxis last month. You spent €2,336 on taxis last month."
        spans = g.ungrounded_spans(text, CALLS, today=TODAY)
        self.assertEqual([text[a:b] for a, b in spans], ["€2,336"])


class WhatTheRealDataNeeds(unittest.TestCase):
    """Cases found by running the checker over the built-in replies and realistic model answers."""

    def test_mental_arithmetic_is_not_grounded_by_a_count(self):
        self.assertFalse(ok("That is 4 rides, so roughly €23 each."))

    def test_money_kept_is_not_income(self):
        calls = CALLS + [("get_save_more", {}, {"ideas": [{"title": "Move your leftover", "saved_monthly": 564.85}]})]
        self.assertFalse(ok("Your income is €564.85 a month.", calls))
        self.assertTrue(ok("Of your €2,336 income you kept €564.85 in August.", calls))
        self.assertTrue(ok("Trimming everyday spending would save about €565 a month.", calls))

    def test_finnish_compound_words_name_spending(self):
        calls = [("get_baskets", {}, {"period": {"from": "2026-08-01", "to": "2026-08-31"},
                                      "baskets": {"regular": 1365.75, "everyday": 205.4, "savings": 200.0}})]
        self.assertTrue(ok("Elokuussa perusmenot olivat 1 366 €, arkikulutus 205 € ja säästöt 200 €.", calls))
        self.assertTrue(ok("Elokuussa käytit 1 571 €, eli vähemmän kuin tilille tuli (2 336 €).", CALLS))
        short = [("get_safe_to_spend", {}, {"balance": 3800.0, "safe_total": -3800.0})]
        self.assertTrue(ok("Rahasi eivät riitä palkkapäivään asti: puuttuu noin 3 800 €.", short))

    def test_list_items_do_not_take_the_period_as_their_rate(self):
        calls = [("find_leaks", {}, {"period": {"from": "2026-03-01", "to": "2026-08-31"},
                                     "subscriptions": [{"label": "Public transport", "amount": 3.10}]})]
        self.assertTrue(ok("A public transport charge of €3.10 repeats every month.", calls))

    def test_adoption_keeps_the_models_rounding_in_the_replys_language(self):
        t = table([("get_safe_to_spend", {}, {"balance": 31469.3})])
        self.assertEqual(g.render("Your balance is €31,469.", t)["text"], "Your balance is €31,469.")
        self.assertEqual(g.render("Saldosi on 31 469,30 €.", t, lang="fi")["text"], "Saldosi on 31 469,30 €.")


class Tokens(unittest.TestCase):
    def test_kinds(self):
        kinds = [(k, v) for k, v, _ in g.tokens("€1,107.64 and 1 107,64 € and 450 euroa, 45%, 12 % and 15.10. "
                                                 "and 15 October and 2026-10-15 and 3rd and 15:00 and 300")]
        self.assertEqual(kinds, [("money", 1107.64), ("money", 1107.64), ("money", 450.0), ("percent", 45.0),
                                 ("percent", 12.0), ("date", (None, 10, 15)), ("date", (None, 10, 15)),
                                 ("date", (2026, 10, 15)), ("ordinal", 3), ("time", "15:00"), ("number", 300.0)])

    def test_may_is_a_verb(self):
        self.assertEqual([k for k, _v, _ in g.tokens("you may 2 times")], ["number"])


class Formatting(unittest.TestCase):
    def test_money(self):
        self.assertEqual(g.fmt_money(92.85, exact=True), "€92.85")
        self.assertEqual(g.fmt_money(92.85), "€93")
        self.assertEqual(g.fmt_money(7.91), "€7.91")
        self.assertEqual(g.fmt_money(122_480, rough=True), "€122,500")
        self.assertEqual(g.fmt_money(31_469.3), "€31,469")
        self.assertEqual(g.fmt_money(-457.5), "€458")
        self.assertEqual(g.fmt_money(3000.0, exact=True), "€3,000")
        self.assertEqual(g.fmt_money(1107.64, exact=True, lang="fi"), "1\u00a0107,64\u00a0€")
        self.assertEqual(g.fmt_money(1583.2, lang="fi"), "1\u00a0583\u00a0€")

    def test_percent_and_number(self):
        self.assertEqual(g.fmt_percent(57), "57%")
        self.assertEqual(g.fmt_percent(4.14), "4.1%")
        self.assertEqual(g.fmt_percent(4.14, "fi"), "4,1\u00a0%")
        self.assertEqual(g.fmt_number(23), "23")


class Table(unittest.TestCase):
    def test_labels_and_sources(self):
        t = table()
        taxi = [f for f in t.figs if f["source"].get("path") == "total" and f["source"]["tool"] == "get_spend"][0]
        self.assertEqual(taxi["unit"], "money")
        self.assertTrue(taxi["exact"])
        self.assertEqual(taxi["group"], "out")
        self.assertEqual(taxi["categories"], ["Taxi"])
        self.assertEqual(taxi["span"], "month")
        self.assertEqual(tuple(taxi["month"]), (2026, 8))
        self.assertEqual(taxi["source"]["evidence"][0]["label"], "Taxi")
        inc = [f for f in t.figs if f["source"].get("path") == "income"][0]
        self.assertEqual(inc["group"], "in")
        share = [f for f in t.figs if f["source"].get("path") == "top_labels[0].share"][0]
        self.assertEqual((share["unit"], share["value"], share["categories"]), ("percent", 57.0, ["Housing"]))
        self.assertEqual(share["source"]["evidence"][0]["title"], "Housing")

    def test_tagged_view_for_the_model(self):
        t = g.FigureTable(TODAY)
        view = t.add_result(*SPEND)
        self.assertIn("figures", view)
        fid = [k for k, v in view["figures"].items() if v.startswith("€92.85")][0]
        self.assertIn("€28 {{", view["explain"])
        self.assertEqual(view["total"], 92.85)          # numbers stay numbers
        self.assertIn("Taxi", view["figures"][fid])

    def test_snapshot_lines_are_tagged_with_their_source(self):
        t = g.FigureTable(TODAY)
        data = {"get_overview": OVERVIEW[2]}
        lines = t.add_snapshot(["In August: income €2,336, spending €1,571, left over €565."], data)
        self.assertRegex(lines[0], r"income €2,336 \{\{f1\}\}, spending €1,571 \{\{f2\}\}")
        self.assertEqual(t.get("f1")["group"], "in")
        self.assertEqual(t.get("f2")["group"], "out")
        self.assertEqual(t.get("f1")["source"]["tool"], "get_overview")
        self.assertEqual(t.get("f1")["source"]["path"], "income")

    def test_calculate_results_take_their_label(self):
        calc = ("calculate", {}, {"results": [{"label": "monthly saving needed per month", "expression": "1200/6",
                                               "value": 200.0, "rounded": 200.0, "rounded_up": 200.0},
                                              {"label": "months to save", "expression": "1200/100", "value": 12.0,
                                               "rounded": 12.0, "rounded_up": 12.0}], "no_card": True})
        t = table(CALLS + [calc])
        f = [x for x in t.figs if x["source"]["tool"] == "calculate"]
        self.assertEqual([(x["unit"], x["value"], x["rate"]) for x in f], [("money", 200.0, "month"), ("number", 12.0, None)])

    def test_resolve_expression(self):
        t = table()
        fid = [f for f in t.figs if f["source"].get("path") == "total"][0]["id"]
        self.assertEqual(t.resolve_expression("{{%s}} * 12" % fid), "92.85 * 12")
        with self.assertRaises(KeyError):
            t.resolve_expression("f999 * 2")


def _id(t, tool, path):
    return [f for f in t.figs if f["source"].get("tool") == tool and f["source"].get("path") == path][0]["id"]


class Slots(unittest.TestCase):
    def test_slots_filled_english_and_finnish_with_sources(self):
        t = table()
        taxi, inc = _id(t, "get_spend", "total"), _id(t, "get_overview", "income")
        r = g.render("You spent {{%s}} on taxis last month, out of {{%s}} of income." % (taxi, inc), t)
        self.assertTrue(r["ok"])
        self.assertEqual(r["text"], "You spent €92.85 on taxis last month, out of €2,336 of income.")
        self.assertEqual([r["text"][f["start"]:f["end"]] for f in r["figures"]], ["€92.85", "€2,336"])
        self.assertEqual(r["figures"][0]["source"]["tool"], "get_spend")
        self.assertEqual(r["figures"][0]["source"]["evidence"][0]["label"], "Taxi")
        fi = g.render("Käytit takseihin {{%s}} viime kuussa." % taxi, t, lang="fi")
        self.assertEqual(fi["text"], "Käytit takseihin 92,85\u00a0€ viime kuussa.")

    def test_misfit_slot_fails(self):
        t = table()
        inc, taxi = _id(t, "get_overview", "income"), _id(t, "get_spend", "total")
        for s in ("You spent {{%s}} on taxis last month." % inc, "You spend {{%s}} on taxis every week." % taxi,
                  "Käytät takseihin {{%s}} viikossa." % taxi):
            r = g.render(s, t)
            self.assertFalse(r["ok"], s)
            self.assertEqual(r["violations"][0]["reason"], "misfit", s)

    def test_unknown_slot_and_digits_fail(self):
        t = table()
        self.assertEqual(g.check("You spent {{f999}} on taxis.", t)[0]["reason"], "unknown_slot")
        self.assertEqual(g.check("You spent €450 on taxis.", t)[0]["reason"], "unknown")
        self.assertEqual(g.check("You spent €92.85 on taxis.", t, adopt=False)[0]["reason"], "digits")

    def test_digits_next_to_their_slot_and_currency_around_a_slot(self):
        t = table()
        taxi = _id(t, "get_spend", "total")
        self.assertEqual(g.render("You spent €92.85 {{%s}} on taxis." % taxi, t)["text"], "You spent €92.85 on taxis.")
        self.assertEqual(g.render("You spent €{{%s}} on taxis." % taxi, t)["text"], "You spent €92.85 on taxis.")
        self.assertEqual(g.render("You spent {{%s}} (€92.85) on taxis." % taxi, t)["text"], "You spent €92.85 on taxis.")
        self.assertEqual(g.render("You spent €92.85 ({{%s}}) on taxis." % taxi, t)["text"], "You spent €92.85 on taxis.")
        self.assertEqual(g.render("Käytit {{%s}} euroa takseihin." % taxi, t, lang="fi")["text"],
                         "Käytit 92,85\u00a0€ takseihin.")

    def test_adopted_digits_are_reformatted_and_sourced(self):
        t = table()
        r = g.render("You spent €1,571.15 in August.", t, lang="fi")
        self.assertEqual(r["text"], "You spent 1\u00a0571,15\u00a0€ in August.")
        self.assertEqual(r["figures"][0]["written"], "digits")


class SentenceRemoval(unittest.TestCase):
    def test_answer_dropped_means_not_ok(self):
        t = table()
        r = g.render("You spent €450 on taxis last month. That is a lot of rides. Walking would help.", t)
        self.assertFalse(r["ok"])
        self.assertTrue(r["answer_dropped"])

    def test_tail_dropped_keeps_answer(self):
        t = table()
        r = g.render("You spent €92.85 on taxis last month. That is about €40 more than usual. "
                     "A bus pass would cut it.", t)
        self.assertTrue(r["ok"])
        self.assertEqual(r["text"], "You spent €92.85 on taxis last month. A bus pass would cut it.")

    def test_answer_after_a_human_first_sentence(self):
        t = table()
        r = g.render("I hear you. You spent €450 on taxis last month. Let's look at it.", t)
        self.assertFalse(r["ok"])

    def test_more_than_half_dropped_means_not_ok(self):
        t = table()
        r = g.render("You spent €92.85 on taxis last month. It was €450 in July. And €300 in June.", t)
        self.assertFalse(r["ok"])

    def test_paragraphs_kept(self):
        t = table()
        r = g.render("You spent €92.85 on taxis last month.\n\nYour income was €2,336.", t)
        self.assertEqual(r["text"], "You spent €92.85 on taxis last month.\n\nYour income was €2,336.")
        self.assertEqual([r["text"][f["start"]:f["end"]] for f in r["figures"]], ["€92.85", "€2,336"])


class Fallback(unittest.TestCase):
    def test_answering_call_is_the_one_whose_figures_were_used(self):
        calls = [OVERVIEW, SPEND, ("calculate", {}, {"results": []})]
        t = table(calls)
        draft = "You spent {{%s}} on taxis last month, about €40 more than usual." % _id(t, "get_spend", "total")
        self.assertEqual(g.answering_call(calls, g.used_figures(draft, t)), 1)
        self.assertEqual(g.answering_call(calls, []), 1)          # no figures used: the last data tool
        self.assertIsNone(g.answering_call([("calculate", {}, {})], []))

    def test_repair_note_names_the_problems(self):
        t = table()
        note = g.repair_note(g.check("You spent €2,336 on taxis last month.", t))
        self.assertIn("€2,336", note)
        self.assertIn("income", note)
        self.assertIn("{{f3}}", note)


if __name__ == "__main__":
    unittest.main()
