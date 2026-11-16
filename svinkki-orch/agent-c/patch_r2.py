import sys

root = sys.argv[1]


def patch(path, pairs):
    p = root + "/" + path
    s = open(p, encoding="utf-8").read()
    for old, new in pairs:
        assert s.count(old) == 1, (path, s.count(old), old[:80])
        s = s.replace(old, new)
    open(p, "w", encoding="utf-8").write(s)


patch("app/voice.py", [
    ("Otherwise treat the receipts as their receipts: answer price, product, shop and weekday questions from them "
     "like any other data, without mentioning that they are simulated, and never use that as a reason not to answer.",
     "Otherwise treat the receipts as their receipts: answer price, product, shop and weekday questions from them "
     "like any other data. The card under your text already says the receipt lines are simulated, so never say it "
     "in your text (not \"simulated\", \"demo\" or \"made up\"), even when a tool result mentions it, and never use "
     "it as a reason not to answer. When the receipts show no price change, say the prices on their receipts held "
     "steady, give the cost of the product per month or year, and one step."),
    ("A question outside money altogether (a capital city, a fact) gets the plain answer in a few words, then one "
     "light line back to their money.",
     "A question outside money altogether (a capital city, a fact, a recipe, a tip) gets the plain, useful answer "
     "in a few short sentences (a recipe: the dish, the main ingredients and the steps in one or two sentences), then "
     "one light line back to their money. Never say it is outside your lane."),
    ("when they gave none (\\\"how can I save?\\\"), start a buffer:",
     "\\\"I have no savings\\\", \\\"where do I start\\\" and \\\"I want a buffer\\\" are a make_savings_plan call with "
     "goal \\\"buffer\\\" (it sizes a first buffer they can reach and names the cuts that close any monthly gap). when "
     "they gave none and only ask how to save more (\\\"how can I save?\\\"), start a buffer:"),
    ("38. Money is tight (they spend more than they earn in a usual month, or the balance hits zero before payday): "
     "any plan or tip must first close that gap.",
     "38. Money is tight (they spend more than they earn in a usual month, or the balance hits zero before payday): "
     "any plan or tip must first close that gap. Say which period a leftover or a gap is for (\"over the last 6 "
     "months\", \"in a usual month this year\") and keep using the same figure through the conversation; if two tools "
     "give different figures for different periods, name both periods instead of letting them look contradictory."),
])
patch("app/coach.py", [
    ("For someone buying a first home, lead with the `first_home` part of the result",
     "Assume a first home unless they say they own or have owned one. For someone buying a first home, lead with "
     "the `first_home` part of the result"),
])
patch("app/goalplan.py", [
    ('''    parts_en = (["%s of your usual leftover" % _eur(used_leftover)] if used_leftover > 0 else []) + [''',
     '''    parts_en = (["%s of what you usually have left (last %d months)" % (_eur(used_leftover), pic["months"])]
                if used_leftover > 0 else []) + ['''),
    ('''    parts_fi = (["%s tavallisesta ylijäämästäsi" % _eur_fi(used_leftover)] if used_leftover > 0 else []) + [''',
     '''    parts_fi = (["%s tavallisesta ylijäämästäsi (viim. %d kk)" % (_eur_fi(used_leftover), pic["months"])]
                if used_leftover > 0 else []) + ['''),
    ('''        src_en += " Today about %s more goes out than comes in a month, so the cuts cover that first." % _eur(deficit)
        src_fi += " Nyt kuussa menee noin %s enemmän kuin tulee, joten säästöt kattavat ensin sen." % _eur_fi(deficit)''',
     '''        src_en += (" Over the last %d months about %s a month more went out than came in, so the cuts cover that "
                   "first." % (pic["months"], _eur(deficit)))
        src_fi += (" Viimeisten %d kuukauden aikana kuussa meni noin %s enemmän kuin tuli, joten säästöt kattavat "
                   "ensin sen." % (pic["months"], _eur_fi(deficit)))'''),
])
print("ok")
