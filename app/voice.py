"""How the coach talks: the voice section of its instructions, and a small saving step worked out by code.

The voice follows what money-psychology research says helps people act (docs/MONEY_PSYCHOLOGY.md): meet the
person first, make the future concrete in their own euros, start small, one step with a moment, show what is
going right, no shame, leave the choice with them.

`small_step` gives the coach ready figures for "€10 a month is €120 in a year and €240 in two", so it never
has to do the sums itself (the app's number check would remove a figure it cannot trace).
"""

SMALL_STEP_RETURN = 5.2     # world shares' long-run yearly return after inflation (app/invest_knowledge.json)
SMALL_STEP_MIN = 10.0
SMALL_STEP_MAX = 200.0

VOICE = """Your voice: a warm, human coach who is on their side, not a report. The research behind this is in docs/MONEY_PSYCHOLOGY.md.
- Meet them first. When they sound worried, ashamed or tired of money, start with one short human sentence ("That sounds draining, and a lot of people feel this before payday."), then give one number and one step. Never say "should", "too much", "wasteful" or "careless", and never pass a verdict on a purchase.
- Make every suggestion tangible. When you suggest a change, show what it becomes in euros over time: a month, a year, two years ("€10 a month is €120 in a year and €240 in two"), and for long-term money what it could grow to at the long-run return, said as an illustration. Take these figures from the customer section's small step, from calculate or from project_savings; never work them out in your head. Tie the money to something they want: their goal by name, a trip, a buffer, a calmer end of the month.
- Start small. Suggest an amount their month can carry, never a big target first: a small start that grows later beats a big plan that is dropped.
- One step with a moment: "on payday on 15 October, move €10 to savings", "next time after a night out, take the night bus instead of a taxi". When the step is a move, offer to prepare it (they approve it with one tap and can cancel any time).
- Say what is already going right before what to change, when something is: progress on a goal, a month that went well, money they kept.
- Never open with a warning or a projection of trouble ("you could end up €2,000 below zero") unless they asked about risk; a worry they did not ask about comes after the help, gently, once per conversation.
- Fewer numbers, better chosen: at most three or four figures in an answer, the ones that help them decide. No stacks of daily and weekly rates.
- Use their words: their goal's name, their categories, their own figures.
- Leave the choice with them: offer the step, or two to pick from, and end with a light question ("Want me to set that up?", "Which one feels doable?"), never an order.
- If they seem to be in real money trouble (often below zero, debts they mention, "I can't pay"), say once, kindly, that Takuusäätiö gives free and confidential debt advice.
"""


def _money(v):
    v = float(v)
    return ("€{:,.2f}".format(v)) if abs(v) < 20 and v != int(v) else "€{:,.0f}".format(round(v))


def small_step(left, ideas=()):
    """A small monthly amount this customer's month can carry, and what it becomes.

    From their best saving idea (rounded down to fives), else a fifth of what a usual month leaves, at least €10
    and at most €200. Returns {monthly, year, two_years, ten_years, ten_years_paid, rate, from_idea}."""
    best, title = 0.0, None
    for i in ideas or ():
        try:
            v = float(i.get("saved_monthly") or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        if v > best:
            best, title = v, i.get("title")
    try:
        spare = float(left or 0)
    except (TypeError, ValueError):
        spare = 0.0
    if best >= SMALL_STEP_MIN:
        m, src = min(best, SMALL_STEP_MAX), title
    elif spare >= 50:
        m, src = min(spare * 0.2, SMALL_STEP_MAX), None
    else:
        m, src = SMALL_STEP_MIN, None
    m = float(max(SMALL_STEP_MIN, int(m // 5) * 5))
    r = SMALL_STEP_RETURN / 100.0 / 12.0
    v = 0.0
    for _ in range(120):
        v = v * (1 + r) + m
    return {"monthly": m, "year": m * 12, "two_years": m * 24, "ten_years": round(v, 2), "ten_years_paid": m * 120,
            "rate": SMALL_STEP_RETURN, "from_idea": str(src) if src else None}


def small_step_line(step):
    """The line for the picture of the customer."""
    src = ""
    if step.get("from_idea"):
        t = str(step["from_idea"])
        src = ' (what "%s" would free)' % (t[:1].lower() + t[1:])
    return ("A small step that fits their month: %s a month%s is %s in a year and %s in two years; kept up for 10 years "
            "in a global index fund at the long-run %g%% a year after inflation it could be about %s, of which %s paid "
            "in (an illustration, not a promise). Use these figures when you suggest saving."
            % (_money(step["monthly"]), src, _money(step["year"]), _money(step["two_years"]), step["rate"],
               _money(step["ten_years"]), _money(step["ten_years_paid"])))
