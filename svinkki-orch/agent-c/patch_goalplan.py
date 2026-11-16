import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:70])
    s = s.replace(old, new)


rep('''     "a home deposit", "asunnon käsiraha", 10000, 20000, 35000,
     "10% of a 200,000 euro home plus transfer tax", "10 % 200 000 euron asunnosta ja varainsiirtovero"),''',
    '''     "a home deposit", "asunnon käsiraha", 13000, 23000, 38000,
     "10% of a 200,000 euro home (20,000) plus the 1.5% transfer tax (3,000)",
     "10 % 200 000 euron asunnosta (20 000) ja 1,5 %:n varainsiirtovero (3 000)"),''')
rep('''LONG_PLAN_MONTHS = 36
''', '''LONG_PLAN_MONTHS = 36
FASTER_FACTOR = 1.75          # "faster": every cut this much deeper (at most 80% of the category)
LOAN_RATE = 0.07              # a typical Finnish consumer / car loan, yearly, for the "borrow the rest" comparison
LOAN_MONTHS = 60
''')
rep('''            "estimate": {"type": "number", "description": "Only for a goal the built-in list cannot price (it says "
                                                          "so): your realistic Finnish price in euros."}},''',
    '''            "estimate": {"type": "number", "description": "Only for a goal the built-in list cannot price (it says "
                                                          "so): your realistic Finnish price in euros."},
            "faster": {"type": "boolean", "description": "true when they find the plan too slow or want it sooner: "
                                                         "deeper cuts and all of the usual leftover."}},''')
rep('''def _cut_options(categories):
    out = []
    for label, avg in categories:
        rule = CUTS.get(label)
        if not rule:
            continue
        freed = math.floor(avg * rule[0])''', '''def _cut_options(categories, faster=False):
    out = []
    for label, avg in categories:
        rule = CUTS.get(label)
        if not rule:
            continue
        share = min(0.8, rule[0] * FASTER_FACTOR) if faster else rule[0]
        freed = math.floor(avg * share)''')
rep('''            freed = math.floor(avg * GROCERY_CUT[0])''',
    '''            freed = math.floor(avg * (GROCERY_CUT[0] * (2 if faster else 1)))''')
rep('''def build(conn, today, goal, target=None, deadline=None, saved=0.0, estimate=None):''',
    '''def loan_monthly(amount, rate=LOAN_RATE, months=LOAN_MONTHS):
    r = rate / 12.0
    return amount * r / (1 - (1 + r) ** -months)


def build(conn, today, goal, target=None, deadline=None, saved=0.0, estimate=None, faster=False):''')
rep('''        if re.search(BUFFER_RE, goal.lower()):
            target = float(max(500, math.ceil(pic["spent"] * 3 / 100.0) * 100))
            est = {"what": "a buffer of three months' spending", "what_fi": "kolmen kuukauden menojen puskuri",
                   "low": target, "high": target, "basis": "three times your usual monthly spending",
                   "basis_fi": "kolme kertaa tavalliset kuukausimenosi", "own_data": True}''',
    '''        if re.search(BUFFER_RE, goal.lower()):
            tight = pic["leftover"] < 0.1 * pic["spent"]
            n = 1 if tight else 3     # money is tight: a first buffer of one month, reachable in a year or two
            target = float(max(500, math.ceil(pic["spent"] * n / 100.0) * 100))
            est = {"what": "a buffer", "what_fi": "puskuri", "low": target, "high": target,
                   "basis": "one month of your usual spending, a first buffer you can reach" if tight else
                            "three months of your usual spending",
                   "basis_fi": "kuukauden tavalliset menosi, ensimmäinen puskuri jonka saavutat" if tight else
                               "kolmen kuukauden tavalliset menosi", "own_data": True}''')
rep('''    from_leftover = float(math.floor(max(0.0, left) * LEFTOVER_SHARE / 10.0) * 10)
    options = _cut_options(pic["categories"])''',
    '''    from_leftover = float(math.floor(max(0.0, left) * (1.0 if faster else LEFTOVER_SHARE) / 10.0) * 10)
    options = _cut_options(pic["categories"], faster)''')
rep('''        if dl is None and len(chosen) >= MAX_CUTS:
            break''', '''        if dl is None and len(chosen) >= MAX_CUTS + (2 if faster else 0):
            break''')
rep('''        if dl is None and from_leftover - deficit >= remaining / 12.0:''',
    '''        if dl is None and not faster and from_leftover - deficit >= remaining / 12.0:''')
rep('''        if dl is None and c["label"] == "Groceries" and''',
    '''        if dl is None and not faster and c["label"] == "Groceries" and''')
rep('''        if cheaper:
            decision += " A %s option''', '''        if dl is not None and not fits:
            by_date = saved + monthly * months_to_dl
            gap = max(0.0, target - by_date)
            loan = loan_monthly(gap) if gap > 0 else 0.0
            alt = {"by_date": round(by_date), "loan_for_rest": round(gap), "loan_monthly": round(loan),
                   "loan_rate_pct": round(LOAN_RATE * 100), "loan_years": LOAN_MONTHS // 12}
            decision += (" If you need it by %s: you would have about %s saved by then, and a loan for the other %s "
                         "would cost roughly %s a month for %d years (at about %d%% interest)." % (
                             _when_en(t, months_to_dl), _eur(by_date), _eur(gap), _eur(loan), LOAN_MONTHS // 12,
                             round(LOAN_RATE * 100)))
            decision_fi += (" Jos tarvitset sen %s: sinulla olisi silloin noin %s säästössä, ja laina loppuihin (%s) "
                            "maksaisi noin %s kuussa %d vuoden ajan (noin %d %%:n korolla)." % (
                                _when_fi(t, months_to_dl), _eur_fi(by_date), _eur_fi(gap), _eur_fi(loan),
                                LOAN_MONTHS // 12, round(LOAN_RATE * 100)))
        if cheaper:
            decision += " A %s option''')
rep('''    out = {"goal": goal,''', '''    alt = locals().get("alt")
    out = {"goal": goal,''')
rep('''           "needed_for_date": needed, "cheaper": cheaper,''',
    '''           "needed_for_date": needed, "cheaper": cheaper, "if_needed_by_date": alt, "faster": bool(faster),''')
rep('''                    estimate=args.get("estimate"))''',
    '''                    estimate=args.get("estimate"), faster=bool(args.get("faster")))''')
open(p, "w", encoding="utf-8").write(s)
print("patched")
