import sys, io
p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()
def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:80])
    s = s.replace(old, new)

# ---- 1. span_from_text after month_of_period
rep('''_LABEL_PATTERNS = [
    (r"\bdining out\b''', '''_MON_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_YR = r"(?:\s+(20\d\d))?"
_RANGE_RES = [
    re.compile(r"\bbetween\s+(?:the\s+)?(" + _MON_ALT + r")" + _YR + r"\s+and\s+(?:the\s+)?(?:end\s+of\s+)?(" + _MON_ALT + r")\b" + _YR),
    re.compile(r"\b(" + _MON_ALT + r")" + _YR + r"\s*(?:-|–|—|\bto\b|\btill\b|\buntil\b|\bthrough\b|\bthru\b)\s*"
               r"(?:the\s+)?(?:end\s+of\s+)?(" + _MON_ALT + r")\b" + _YR),
]
_SINCE_RE = re.compile(r"\bsince\s+(?:the\s+)?(?:start\s+of\s+|beginning\s+of\s+)?(" + _MON_ALT + r")\b" + _YR)
_LAST_N_RE = re.compile(r"\b(?:last|past|previous)\s+(\d{1,2}|two|four|five|six|seven|eight|nine|ten|eleven|eighteen|"
                        r"twenty-four)\s+months\b")
_RANGE_CUE = re.compile(r"\b(?:between|from|since|until|till|through|thru|before|after)\b[^?.!]{0,25}\b(?:" + _MON_ALT +
                        r")\b|\b(?:" + _MON_ALT + r")\b\s*(?:-|–|—|\bto\b|\btill\b|\buntil\b|\bthrough\b)")
_N_WORDS = {"two": 2, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "eighteen": 18, "twenty-four": 24}


def _fi_elative(m):
    return _FI_MONTHS[m - 1][0] + "sta"


def _fi_illative(m):
    return _FI_MONTHS[m - 1][0] + "hun"


def span_from_text(msg, today):
    """A time span the named periods cannot hold: a range of months ("between June and August", "June-August",
    "from December to February"), "since June", or "the last N months" for N other than 3 and 12.
    Returns ("dates", from, to, words_en, words_fi), ("unclear",) when the message names months around a
    range word that could not be read (so the reply says so instead of quietly answering one month), or None."""
    import datetime as _dt
    s = (msg or "").lower()
    try:
        t = _dt.date.fromisoformat(str(today)[:10])
    except ValueError:
        return None
    m = _LAST_N_RE.search(s)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _N_WORDS[m.group(1)]
        if n in (3, 12):
            return None                      # named periods: last_3_months, last_12_months
        if not 2 <= n <= 24:
            return ("unclear",)
        y, mo = t.year, t.month - n
        while mo < 1:
            mo, y = mo + 12, y - 1
        last = (_dt.date(y + (mo == 12), mo % 12 + 1, 1) - _dt.timedelta(days=1)).day
        start = _dt.date(y, mo, min(t.day, last)) + _dt.timedelta(days=1)
        return ("dates", start.isoformat(), t.isoformat(), "over the last %d months" % n,
                "viimeisen %d kuukauden aikana" % n)
    m = _SINCE_RE.search(s)
    if m:
        sm = _MONTHS[m.group(1)]
        sy = int(m.group(2)) if m.group(2) else (t.year if sm <= t.month else t.year - 1)
        start = _dt.date(sy, sm, 1)
        if start > t:
            return ("unclear",)
        return ("dates", start.isoformat(), t.isoformat(), "since %s %d" % (_MONTH_NAMES[sm], sy),
                "%s %d alkaen" % (_fi_elative(sm), sy))
    for rx in _RANGE_RES:
        m = rx.search(s)
        if not m:
            continue
        sm, y1, em, y2 = _MONTHS[m.group(1)], m.group(2), _MONTHS[m.group(3)], m.group(4)
        if y2:
            ey = int(y2)
        elif y1:
            ey = int(y1) + (1 if em < sm else 0)
        else:
            ey = t.year if em <= t.month else t.year - 1
        sy = int(y1) if y1 else (ey if sm <= em else ey - 1)
        start = _dt.date(sy, sm, 1)
        end = _dt.date(ey + (em == 12), em % 12 + 1, 1) - _dt.timedelta(days=1)
        if start > end or start > t:
            return ("unclear",)
        so_far = end >= t
        end = min(end, t)
        if sy == ey:
            en = "from %s to %s %d" % (_MONTH_NAMES[sm], _MONTH_NAMES[em], ey)
            fi = "%s %s %d" % (_fi_elative(sm), _fi_illative(em), ey)
        else:
            en = "from %s %d to %s %d" % (_MONTH_NAMES[sm], sy, _MONTH_NAMES[em], ey)
            fi = "%s %d %s %d" % (_fi_elative(sm), sy, _fi_illative(em), ey)
        if so_far:
            en, fi = en + " so far", fi + " tähän mennessä"
        return ("dates", start.isoformat(), end.isoformat(), en, fi)
    if _RANGE_CUE.search(s):
        return ("unclear",)
    return None


_LABEL_PATTERNS = [
    (r"\bcaf[eé]s?\b|\bcoffee (?:shops?|places?|bars?)\b", "Dining out"),
    (r"\bdining out\b''')

rep('''(r"\brestaurants?\b|\blunch(es)?\b|\bdinners?\b|\bcafes?\b|\bcafés?\b", "Restaurant"),''',
    '''(r"\brestaurants?\b|\blunch(es)?\b|\bdinners?\b", "Restaurant"),''')

# ---- 2. coffee: "how much on coffee"
rep('''    re.compile(r"\bwhat (?:do|did) i (?:spend|spent) (?:on|for) (?P<x>[^?!.]*)", re.I),''',
    '''    re.compile(r"\bwhat (?:do|did) i (?:spend|spent) (?:on|for) (?P<x>[^?!.]*)", re.I),
    re.compile(r"\bhow much\b(?: money)?(?: (?:did|do|does|has|have) (?:i|it))?(?: (?:go|went|gone|goes))? (?:on|for|in) "
               r"(?P<x>[^?!.]*)", re.I),''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
