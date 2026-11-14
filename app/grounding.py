"""Grounding: every figure in a model answer is a figure the app computed.

The model never has to type a number about the customer. Every figure it may quote is put in a table for the
turn, each with an id and a label that says what it is:

    f3  = EUR 92.85, money, exact: total spending, category Taxi, last month (2026-08), from get_spend total

The figures come from the turn's tool results (numbers and the figures inside their ready-made sentences),
the customer picture (snapshot lines), calculate / general_estimate / project_savings / loan_payment results,
the coach's earlier answers and the customer's own message. The model sees each figure followed by its slot
("income EUR 3,000 {{f1}}", and a "figures" listing in every tool result) and writes the slot, {{f1}}, in its
answer instead of digits. `render` fills every slot with the value formatted by code (English or Finnish,
house cents rule), and keeps per filled slot a reference to its source (tool, field path, evidence filters),
so the app can show what is behind each figure.

What `render` does with a sentence:
- a slot is filled when its figure fits the sentence (see `fits`), otherwise the sentence fails (misfit);
- a slot id that is not in the table fails the sentence;
- a figure the model wrote in digits next to its own slot ("EUR 92.85 {{f3}}") is dropped (the slot stays);
- any other figure written in digits is "adopted" when it equals a table figure that fits the sentence (it is
  then replaced by that figure, formatted by code, with its source); otherwise the sentence fails. With
  adopt=False every digit figure outside a slot fails the sentence.

Free numbers (written by the model itself, never checked):
- whole numbers 0 to 12 that are not money or a percentage ("2 payments", "3 steps", "12 months", "1 in 5");
- years 1900 to 2100 standing alone ("in 2025"), times of day ("15:00");
- a month without a day ("in August", "elokuussa", "August 2025");
- ordinals 1st to 5th ("2nd").
Dates with a day ("15 October", "October 15th", "15.10.", "15. lokakuuta", "2026-10-15") must be a date that
appears in the turn's data, the customer's message or today; they are not slots. Money and percentages are
never free, whatever their size.

Does a figure fit its sentence (cheap, conservative; an unknown never fails):
- what it measures (money only): income, spending, or kept money (balance, savings, left over). A figure of
  one kind in a sentence that speaks only of another kind fails ("You spent {{income}} on taxis").
- category: a figure of a category (Taxi) in a sentence that names categories but not that one fails.
- rate (money and counts): a sentence part that says "every week" / "a month" / "viikossa" / "kuukaudessa"
  must match the figure's rate or the length of its period (a one-month total said "every week" fails).
- month (money and counts): a sentence part that names one month ("last month", "in July", "viime kuussa")
  must match the month of a one-month figure.
- the customer's own figure (from their message) may be quoted, but not as a fact about their account
  ("You spent 450 on taxis" when only the customer said 450).

The same checks run on raw text with `ungrounded_spans` / `numbers_grounded` for paths that still produce raw
text (a draft before repair, a legacy path): there every figure is a digit figure and adoption decides.

Sentence removal (`render(...).ok`): the result still answers the question only when the first sentence and
the first sentence that holds a figure (the answer and its key figure, as the prompt asks) survive and at most
half of the sentences were removed. Otherwise the caller repairs or falls back; it never keeps only a tail.

Standard library only; this module imports nothing from the app, so coach.py and tools.py can both use it.
"""
import datetime
import re

UNITS = ("money", "percent", "count", "number")
MAX_PER_SOURCE = 60          # figures registered from one tool result
MAX_LIST_ITEMS = 12          # items of a list (rows, by_label ...) whose figures are registered
SOURCE_ORDER = {"tool": 0, "snapshot": 1, "earlier_answer": 2, "customer_message": 3}

# ------------------------------------------------------------------ words
_MONTH_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
             "november", "december"]
_MONTH_ABBR = {m[:3]: i + 1 for i, m in enumerate(_MONTH_EN)}
_MONTH_FI = ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]
_MON_EN_P = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
             r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)")
_MON_FI_P = r"(?:tammi|helmi|maalis|huhti|touko|kesä|heinä|elo|syys|loka|marras|joulu)kuu\w*"

# what a money figure measures, grouped: money coming in, money going out, money kept
_METRIC_WORDS = [
    ("in", r"\bincome\w*|\bearn\w*|\bsalar\w*|\bwages?\b|\bcame in\b|\bcomes in\b|\bcome in\b|\byour pay\b|"
           r"\bpaycheck|\btulo(?:t|si|jen|ja|ihin|istasi|nne)?\b|\bpalk(?!kapäiv)\w*|\bansai\w*|\btienaa\w*|\btienas\w*|"
           r"\btilille tul\w*|\btuli tilille\b|\btulee tilille\b"),
    ("out", r"\bspen[dt]\w*|\bpaid\b|\bpay for\b|\bcost\w*|\bbought\b|\bpurchas\w*|\bwent on\b|\bgoes on\b|"
            r"\bgoes out\b|\bwent out\b|\bgo out\b|\bexpens\w*|\bbills?\b|\boutgoing\w*|\bkäyt(?:it|ät|i|än|ti|tänyt|"
            r"etty|imme)\b|\w*kulu\w*|\bmen(?:i|ee|nyt|neet)\b|\w*meno(?:t|ja|ihin|jen|si|issa|sta)\b|\bmaksoit\b|"
            r"\bmaksat\b|\bmaksaa\b|"
            r"\bostit\b|\bostat\b"),
    ("keep", r"\bbalance\w*|\bin your account\b|\bon your account\b|\bsav(?:e|es|ed|ing|ings)\b|\bset aside\b|"
             r"\bput aside\b|\bleft over\b|\bleftover\b|\bleaves?\b|\bleft\b|\bkept\b|\bkeep\w*|\bsurplus\b|"
             r"\bsaldo\w*|\btilillä\w*|\bsäästö\w*|\bsäästä\w*|\bsäästi\w*|\bjää\w*|\bjäi\w*|\bylijää\w*"),
]
_METRIC_RE = [(g, re.compile(p, re.I)) for g, p in _METRIC_WORDS]

# categories (labels of the data) and the words that name them, English and Finnish
_CATEGORY_WORDS = {
    "Housing": r"\bhousing\b|\brent\b|\basum\w*|\bvuokr\w*",
    "Utilities": r"\butilit\w*|\belectricity\b|\bsähkö\w*",
    "Groceries": r"\bgrocer\w*|\bsupermarket\w*|\bruokaostok\w*|\bruokakaup\w*|\bruokaan\b|\bruokiin\b|\belintarvik\w*",
    "Restaurant": r"\brestaurant\w*|\bravintol\w*",
    "Fast food": r"\bfast food\b|\btakeaway\w*|\bpikaruo\w*",
    "Dining out": r"\bdining out\b|\beating out\b|\bulkona syö\w*",
    "Bar": r"\bbars?\b|\bpubs?\b|\bbaar\w*",
    "Night out": r"\bnights? out\b|\billanvie\w*|\bbaari-ill\w*",
    "Taxi": r"\btax(?:i|is|ies)\b|\btaksi\w*|\btakse\w*",
    "Public transport": r"\bpublic transport\b|\bbus(?:es)?\b|\btrams?\b|\bjoukkoliiken\w*|\bbussi\w*|\bhsl\b",
    "Fuel": r"\bfuel\b|\bpetrol\b|\bpolttoain\w*|\bbensa\w*|\bbensii\w*",
    "Parking": r"\bparking\b|\bpysäköin\w*|\bparkki\w*",
    "Pharmacy": r"\bpharmac\w*|\bapteek\w*",
    "Doctor": r"\bdoctors?\b|\blääkäri\w*|\blääkärei\w*",
    "Dentist": r"\bdentists?\b|\bhammaslääk\w*",
    "Electronics": r"\belectronic\w*|\belektroniik\w*",
    "Clothing": r"\bcloth\w*|\bvaatte\w*|\bvaate\w*",
    "Furniture": r"\bfurniture\b|\bhuonekal\w*",
    "Hobbies": r"\bhobb\w*|\bharrast\w*",
    "Books": r"\bbooks?\b|\bkirjoihin\b|\bkirjoja\b",
    "Events": r"\bevents?\b|\btapahtum\w*",
    "Cinema": r"\bcinema\w*|\bmovies?\b|\belokuv\w*|\bleffa\w*",
    "Gym & sports": r"\bgym\w*|\bsports?\b|\bkuntosal\w*|\burheil\w*",
    "Entertainment": r"\bentertainment\b|\bviihte\w*",
    "Flights": r"\bflights?\b|\blento\w*",
    "Hotels": r"\bhotels?\b|\bhotell\w*",
    "Car rental": r"\bcar rental\b|\bautonvuokr\w*",
}
_CATEGORY_RE = {k: re.compile(v, re.I) for k, v in _CATEGORY_WORDS.items()}
_FAMILIES = [{"Dining out", "Restaurant", "Fast food"}]

_RATE_WORDS = [
    ("week", r"\b(?:a|per|each|every|one) week\b|\bweekly\b|\bviikossa\b|\bjoka viikko\b|\bviikoittain\b|"
             r"/\s?(?:week|wk|vko|viikko)\b"),
    ("month", r"\b(?:a|per|each|every) month\b|\bmonthly\b|\bmonth after month\b|\bkuukaudessa\b|\bkuukausittain\b|"
              r"\bjoka kuukausi\b|/\s?(?:month|mo|kk|kuukausi)\b|(?<!viime )(?<!tässä )(?<!ensi )(?<!samassa )\bkuussa\b"),
    ("year", r"\b(?:a|per|each|every) year\b|\byearly\b|\bannual(?:ly)?\b|\bvuodessa\b|\bvuosittain\b|"
             r"\bjoka vuosi\b|/\s?(?:year|yr|vuosi)\b"),
    ("day", r"\b(?:a|per|each|every) day\b|\bdaily\b|\bpäivässä\b|\bpäivittäin\b|/\s?(?:day|pv|päivä)\b"),
]
_RATE_RE = [(r, re.compile(p, re.I)) for r, p in _RATE_WORDS]

# a sentence part that states something as a fact of the customer's account
_ASSERT_RE = re.compile(
    r"\byou(?:'ve| have)? (?:spent|paid|earned|received|saved|had|got)\b|\byour (?:income|salary|pay|spending|"
    r"balance) (?:is|was|were|came|comes)\b|\bcame in\b|\bkäytit\b|\bmaksoit\b|\bkulutit\b|\bansaitsit\b|"
    r"\btienasit\b|\bsäästit\b|\btulosi (?:ovat|olivat|on|oli)\b|\bsaldosi (?:on|oli)\b", re.I)

# ------------------------------------------------------------------ tokens
_NUM_P = r"\d{1,3}(?:[ \u00a0\u202f,.]\d{3})+(?:[.,]\d{1,2})?(?!\d)|\d+(?:[.,]\d+)?"
_MONEY_AFTER = r"(?:€|eur\b|euro[a-zäö]*\b)"
_PCT_AFTER = r"(?:%|percent\b|per cent\b|prosent\w*)"
SLOT_RE = re.compile(r"(?:€\s?|eur\s?)?\{\{\s*f(\d+)\s*\}\}(?:\s?(?:" + _MONEY_AFTER + "|" + _PCT_AFTER + "))?", re.I)
_TOKEN_RE = re.compile(
    r"(?P<iso>\b\d{4}-\d{2}-\d{2}\b|\b\d{4}-\d{2}\b)"
    r"|(?P<time>\b\d{1,2}:\d{2}\b)"
    r"|(?P<dmy>\b(?P<dmy_d>\d{1,2})\.(?P<dmy_m>\d{1,2})\.(?:(?P<dmy_y>\d{4})\b)?)"
    r"|(?P<fidm>\b(?P<fidm_d>\d{1,2})\.\s?(?P<fidm_m>" + _MON_FI_P + r"))"
    r"|(?P<md>\b(?P<md_m>" + _MON_EN_P + r")\.?\s+(?P<md_d>\d{1,2})(?:st|nd|rd|th)?\b(?!\s*(?:%|€|,\d)))"
    r"|(?P<dm>\b(?P<dm_d>\d{1,2})(?:st|nd|rd|th)?\.?\s+(?:of\s+)?(?P<dm_m>" + _MON_EN_P + r")\b)"
    r"|(?P<m1>(?:€|\beur)\s*(?P<m1n>" + _NUM_P + r")(?P<m1k>\s?k\b)?)"
    r"|(?P<m2>(?P<m2n>" + _NUM_P + r")(?P<m2k>\s?k)?\s?" + _MONEY_AFTER + r")"
    r"|(?P<p>(?P<pn>" + _NUM_P + r")\s?" + _PCT_AFTER + r")"
    r"|(?P<o>\b(?P<on>\d{1,2})(?:st|nd|rd|th)\b)"
    r"|(?P<b>(?<![\w.,])(?:" + _NUM_P + r"))", re.I)


def parse_amount(s):
    """'1,107.64', '1 107,64', '92.85', '92,85', '3,000' -> float."""
    s = re.sub(r"[ \u00a0\u202f]", "", s)
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in s:
        s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", s) else s.replace(",", ".")
    elif "." in s and re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return float(s)


def _mon(s):
    s = s.lower()
    for i, stem in enumerate(_MONTH_FI):
        if s.startswith(stem + "kuu"):
            return i + 1
    return _MONTH_ABBR.get(s[:3])


def tokens(text):
    """[(kind, value, (start, end))] for every figure written in digits. kind: money, percent, number, ordinal,
    date (value (year|None, month, day|None)), time, bad. Slots are not tokens (see SLOT_RE)."""
    out = []
    text = text or ""
    masked = SLOT_RE.sub(lambda m: "\x00" * len(m.group(0)), text)
    for m in _TOKEN_RE.finditer(masked):
        sp = m.span()
        g = m.group
        try:
            if g("iso"):
                p = g("iso").split("-")
                out.append(("date", (int(p[0]), int(p[1]), int(p[2]) if len(p) > 2 else None), sp))
            elif g("time"):
                out.append(("time", g("time"), sp))
            elif g("dmy"):
                y = g("dmy_y")
                out.append(("date", (int(y) if y else None, int(g("dmy_m")), int(g("dmy_d"))), sp))
            elif g("fidm"):
                out.append(("date", (None, _mon(g("fidm_m")), int(g("fidm_d"))), sp))
            elif g("md"):
                if g("md_m") in ("may", "mar"):    # "you may 2 ..." is not a date: only its number counts
                    out.append(("number", float(g("md_d")), m.span("md_d")))
                    continue
                out.append(("date", (None, _mon(g("md_m")), int(g("md_d"))), sp))
            elif g("dm"):
                out.append(("date", (None, _mon(g("dm_m")), int(g("dm_d"))), sp))
            elif g("m1"):
                out.append(("money", parse_amount(g("m1n")) * (1000 if g("m1k") else 1), sp))
            elif g("m2"):
                out.append(("money", parse_amount(g("m2n")) * (1000 if g("m2k") else 1), sp))
            elif g("p"):
                out.append(("percent", parse_amount(g("pn")), sp))
            elif g("o"):
                out.append(("ordinal", int(g("on")), sp))
            elif g("b"):
                out.append(("number", parse_amount(g("b")), sp))
        except (ValueError, TypeError):
            if g("md") or g("dm"):
                continue
            out.append(("bad", None, sp))
    return out


def slots(text):
    """[(figure id, (start, end))] for every slot written in text (with any currency sign or unit around it)."""
    return [("f" + m.group(1), m.span()) for m in SLOT_RE.finditer(text or "")]


def is_free(kind, val, text="", sp=None):
    """A figure the model may write itself (see the module docstring)."""
    if kind in ("time",):
        return True
    if kind == "date":
        return val[2] is None                      # a month (and year) without a day
    if kind == "ordinal":
        return 1 <= val <= 5
    if kind == "number":
        if val == int(val) and 0 <= val <= 12:
            return True
        if val == int(val) and 1900 <= val <= 2100:
            return True
    return False


# ------------------------------------------------------------------ features of a piece of text
def _ym(today):
    try:
        d = datetime.date.fromisoformat(str(today)[:10])
        return d.year, d.month
    except (TypeError, ValueError):
        return None


def _prev(ym, n=1):
    y, m = ym
    m -= n
    while m < 1:
        m += 12
        y -= 1
    return y, m


def metric_groups(text):
    return {g for g, rx in _METRIC_RE if rx.search(text or "")}


def categories(text):
    return {k for k, rx in _CATEGORY_RE.items() if rx.search(text or "")}


def rate_of(text):
    for r, rx in _RATE_RE:
        if rx.search(text or ""):
            return r
    return None


def months_named(text, today=None):
    """{(year|None, month)} for the months a piece of text names: 'last month', 'in July', 'elokuussa'."""
    text = text or ""
    out = set()
    now = _ym(today)
    if now:
        if re.search(r"\blast month\b|\bviime kuu\w*|\bedellisen?ä kuu\w*", text, re.I):
            out.add(_prev(now))
        if re.search(r"\bthis month\b|\btässä kuussa\b|\btämän kuun\b|\bkuluva\w* kuu\w*", text, re.I):
            out.add(now)
    for m in re.finditer(r"\b(" + _MON_EN_P + r")\b(?:\s+(\d{4}))?", text):
        word = m.group(1)
        if word == "May" or word.lower() != "may":
            mo = _mon(word)
            y = int(m.group(2)) if m.group(2) else None
            if y is None and now:
                y = now[0] if mo <= now[1] else now[0] - 1
            out.add((y, mo))
    for m in re.finditer(r"\b(" + _MON_FI_P + r")(?:\s+(\d{4}))?", text, re.I):
        mo = _mon(m.group(1))
        y = int(m.group(2)) if m.group(2) else None
        if y is None and now:
            y = now[0] if mo <= now[1] else now[0] - 1
        out.add((y, mo))
    return out


_CLAUSE_DELIM = re.compile(r"[,;:()\u2013\u2014]|\s-\s")


def window(text, sp, others=()):
    """The part of a sentence that belongs to the figure at sp: from the previous delimiter (or figure) to the
    next one. Returns (before, after) strings."""
    a, b = sp
    left = 0
    for m in _CLAUSE_DELIM.finditer(text, 0, a):
        left = m.end()
    for o in others:
        if o[1] <= a:
            left = max(left, o[1])
    right = len(text)
    m = _CLAUSE_DELIM.search(text, b)
    if m:
        right = m.start()
    for o in others:
        if o[0] >= b:
            right = min(right, o[0])
    return text[left:a], text[b:right]


def _with_family(cats):
    out = set(cats)
    for fam in _FAMILIES:
        if out & fam:
            out |= fam
    return out


# ------------------------------------------------------------------ formatting
def _has_cents(v):
    return abs(v * 100 - round(v) * 100) >= 0.5 and round(v, 2) != round(v)


def fmt_money(v, exact=False, lang="en", rough=False):
    """House style: an exact amount keeps its cents; a derived one is whole euros from EUR 20, cents under EUR 20,
    and the nearest hundred from EUR 10,000. Always the absolute value: the sentence words a minus."""
    v = abs(float(v))
    if exact:
        cents = _has_cents(v)
    elif v >= 10000 and rough:
        v, cents = round(v / 100.0) * 100, False
    elif v >= 20:
        v, cents = float(round(v)), False
    else:
        cents = _has_cents(v)
    s = ("{:,.2f}" if cents else "{:,.0f}").format(v)
    if lang == "fi":
        return s.replace(",", "\u00a0").replace(".", ",") + "\u00a0€"
    return "€" + s


def fmt_number(v, lang="en"):
    v = float(v)
    s = "%d" % round(v) if abs(v - round(v)) < 1e-9 else ("%.1f" % v)
    return s.replace(".", ",") if lang == "fi" else s


def fmt_percent(v, lang="en"):
    v = abs(float(v))
    s = "%d" % round(v) if (v >= 10 or abs(v - round(v)) < 0.05) else ("%.1f" % v)
    if lang == "fi":
        return s.replace(".", ",") + "\u00a0%"
    return s + "%"


def fmt(fig, lang="en"):
    if fig["unit"] == "money":
        return fmt_money(fig["value"], fig.get("exact"), lang, fig.get("rough"))
    if fig["unit"] == "percent":
        return fmt_percent(fig["value"], lang)
    return fmt_number(fig["value"], lang)


def close(known, a, whole_ok=True):
    """a equals known to the cent, or (whole_ok) is its whole-number rounding, its rounding to one decimal, or
    from 10,000 up its rounding to the nearest hundred."""
    n = abs(float(known))
    a = abs(float(a))
    if abs(round(n, 2) - a) < 0.006:
        return True
    if not whole_ok:
        return False
    if abs(a - round(a)) < 1e-9 and round(n) == round(a):
        return True
    if n >= 10000 and abs(a % 100) < 1e-9 and abs(round(n / 100.0) * 100 - a) < 1e-6:
        return True
    if abs(round(n, 1) - a) < 0.0501 and abs(a * 10 - round(a * 10)) < 1e-6:
        return True
    return False


# ------------------------------------------------------------------ what a field of a tool result is
_PCT_KEY = re.compile(r"pct|percent|share|ratio|rate")
_OTHER_KEY = re.compile(r"count|^n$|days|months|weeks|^years?$|_year$|^year_|_id$|^id$|rank|score|limit|affected|"
                        r"turn|visits|rides|population|^age|index|number|^rows$|^month$|^dated?$|^tx$|streak|level|"
                        r"receipts?$|lines$|times$|hour|qty|quantit|litre|liter|^kg$|weekday|grams|size")
_COUNT_KEY = re.compile(r"count|^n$|visits|rides|receipts?$|lines$|times$|affected|^tx$")
_SKIP_KEY = re.compile(r"_id$|^id$|rank|score|index|level|^age|hour|weekday")
# keys whose value is the total of the result's period: only these take the period's length as their rate
_TOTAL_KEY = re.compile(r"^(?:total|spent|spending|income|saved|surplus|sum|kept|regular|unexpected|everyday|savings)$")
_SPEND_TOOLS = ("get_spend", "get_baskets", "list_transactions", "explore_my_data", "get_receipts")
_ROUGH_TOOLS = ("general_estimate", "project_savings", "loan_payment", "check_mortgage")
_HELPERS = ("general_estimate", "calculate", "project_savings", "loan_payment", "save_goal")


def _key_metric(tool, keys):
    k = keys[-1] if keys else ""
    path = ".".join(keys)
    if re.search(r"income|salary|earn|came_in", k):
        return "in"
    if re.search(r"safe", k):
        return None
    if re.search(r"balance|lowest|surplus|left|kept|leftover|remaining|saved|saving|invest", k):
        return "keep"
    if re.search(r"spent|spend|cost|expense|outgoing|bills", k):
        return "out"
    if re.search(r"baskets", path) and k in ("regular", "unexpected", "everyday"):
        return "out"
    if re.search(r"baskets", path) and k == "savings":
        return "keep"
    if k in ("total", "amount", "sum") and (tool in _SPEND_TOOLS or re.search(r"by_label|top_labels|night_out", path)):
        return "out"
    return None


def _key_rate(keys):
    k = (keys[-1] if keys else "").lower()
    if re.search(r"week", k):
        return "week"
    if re.search(r"per_day|daily|a_day|_day$", k):
        return "day"
    if re.search(r"year|annual", k):
        return "year"
    if re.search(r"month|avg|average|usual|typical", k):
        return "month"
    return None


def _period_info(p, today):
    """(span, (year, month) | None) for a period value of a tool result or its args."""
    if isinstance(p, dict):
        frm, to = str(p.get("from") or "")[:10], str(p.get("to") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", frm) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", to):
            try:
                days = (datetime.date.fromisoformat(to) - datetime.date.fromisoformat(frm)).days + 1
            except ValueError:
                days = None
            same = frm[:7] == to[:7]
            if days is not None:
                if days <= 1:
                    return "day", (int(frm[:4]), int(frm[5:7]))
                if days <= 7:
                    return "week", (int(frm[:4]), int(frm[5:7])) if same else None
                if same and days >= 20:
                    return "month", (int(frm[:4]), int(frm[5:7]))
                if same:
                    return "part_month", (int(frm[:4]), int(frm[5:7]))
                if 360 <= days <= 366:
                    return "year", None
                return "multi", None
        p = p.get("name")
    p = str(p or "")
    if re.fullmatch(r"\d{4}-\d{2}", p):
        return "month", (int(p[:4]), int(p[5:7]))
    now = _ym(today)
    if p == "last_month":
        return "month", _prev(now) if now else None
    if p == "this_month":
        return "part_month", now
    if p in ("this_week", "last_week"):
        return "week", None
    if p in ("today", "yesterday", "last_night"):
        return "day", None
    if p.startswith("last_") and p.endswith("months"):
        return "multi", None
    return None, None


# ------------------------------------------------------------------ the table
class FigureTable:
    """The figures one turn may quote. Each figure is a dict:
    id, value, unit (money|percent|count|number), exact, label (for the model and the app), group (in|out|keep|
    None), categories, rate (week|month|year|day|None), span (day|week|month|part_month|multi|year|None),
    month ((year, month)|None), said (from the customer's message), source {kind, tool, call, path, args,
    evidence, line}."""

    def __init__(self, today=None):
        self.today = today
        self.figs = []
        self.by_id = {}
        self.dates = set()                 # (month, day) the turn's data or the customer's message names
        self._calls = 0
        now = _ym(today)
        if now:
            try:
                d = datetime.date.fromisoformat(str(today)[:10])
                self.dates.add((d.month, d.day))
            except ValueError:
                pass

    # -- adding
    def _add(self, value, unit, label, source, exact=False, group=None, cats=(), rate=None, span=None, month=None,
             said=False, dedupe=None):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        if value != value or abs(value) > 1e12:
            return None
        if dedupe is not None:
            key = (dedupe, unit, round(abs(value), 2))
            for f in self.figs:
                if f.get("_dedupe") == key:
                    return f["id"]
        fid = "f%d" % (len(self.figs) + 1)
        fig = {"id": fid, "value": round(value, 4), "unit": unit, "exact": bool(exact), "label": label,
               "group": group, "categories": sorted(cats), "rate": rate, "span": span, "month": month,
               "said": bool(said), "source": source,
               "rough": source.get("tool") in _ROUGH_TOOLS or bool(re.search(r"loan|price|mid|low|high|value_at_end",
                                                                            str(source.get("path") or "")))}
        if dedupe is not None:
            fig["_dedupe"] = (dedupe, unit, round(abs(value), 2))
        self.figs.append(fig)
        self.by_id[fid] = fig
        return fid

    def get(self, fid):
        return self.by_id.get(str(fid))

    def tag_text(self, text, source, base=None, said=False, dedupe=None, tag=True):
        """Register every figure written in text (with the meaning its sentence part gives it) and return text
        with each followed by its slot: 'income €3,000 {{f1}}'. base: features inherited from a tool result."""
        base = base or {}
        text = str(text or "")
        toks = tokens(text)
        spans = [t[2] for t in toks if t[0] in ("money", "percent", "number")]
        out, pos = [], 0
        for kind, val, sp in toks:
            if kind == "date" and val[2] is not None:
                self.dates.add((val[1], val[2]))
                continue
            if kind not in ("money", "percent", "number") or is_free(kind, val, text, sp):
                continue
            before, after = window(text, sp, [s for s in spans if s != sp])
            part = before + " " + after
            sent = _sentence_around(text, sp)
            groups = metric_groups(part) or (metric_groups(sent) if len(metric_groups(sent)) == 1 else set())
            cats = categories(part) or (categories(sent) if len(categories(sent)) == 1 else set()) \
                or set(base.get("categories") or ())
            rate = rate_of(after) or rate_of(before) or base.get("rate")
            months = months_named(part, self.today) or months_named(sent, self.today)
            month = next(iter(months)) if len(months) == 1 else base.get("month")
            unit = {"money": "money", "percent": "percent"}.get(kind, "number")
            label = "%s: \u201c%s\u201d" % (base.get("label") or source.get("kind", ""),
                                           " ".join((before[-60:] + text[sp[0]:sp[1]] + after[:40]).split()))
            fid = self._add(val, unit, label, dict(source), exact=(unit == "money" and _has_cents(val)),
                            group=(next(iter(groups)) if len(groups) == 1 else None), cats=cats, rate=rate,
                            span=base.get("span") if not rate else None, month=month, said=said, dedupe=dedupe)
            if fid and tag:
                out.append(text[pos:sp[1]] + " {{%s}}" % fid)
                pos = sp[1]
        out.append(text[pos:])
        return "".join(out)

    def add_snapshot(self, lines, data=None):
        """The customer picture: returns the lines with every figure tagged with its slot. When the data the
        lines were written from is given, each figure's source points at the field it came from."""
        out = []
        for i, line in enumerate(lines or ()):
            src = {"kind": "snapshot", "tool": "customer_snapshot", "line": i}
            start = len(self.figs)
            tagged = self.tag_text(line, src, {"label": "customer picture"})
            for f in self.figs[start:]:
                hit = _find_in(data, f["value"], f["unit"]) if isinstance(data, dict) else None
                if hit:
                    f["source"].update(hit)
            out.append(tagged)
        return out

    def add_earlier(self, answers):
        """The coach's earlier answers in this conversation (checked when they were given)."""
        return [self.tag_text(a, {"kind": "earlier_answer", "tool": "earlier_answer", "index": i},
                              {"label": "your earlier answer"}) for i, a in enumerate(answers or ())]

    def add_message(self, message):
        """The customer's own figures: they may be quoted, never as a fact of their account."""
        self.tag_text(message, {"kind": "customer_message", "tool": "customer_message"},
                      {"label": "the customer's message"}, said=True, tag=False)

    def add_result(self, tool, args, view, raw=None):
        """Register the figures of one tool result. view: what the model will see (anonymised); raw: the full
        result, used for the evidence filters behind each figure. Returns a copy of view whose strings carry
        slots and which has a "figures" listing {id: label} for its numbers."""
        call = self._calls
        self._calls += 1
        args = args if isinstance(args, dict) else {}
        evid = {}
        if isinstance(raw, (dict, list)):
            _evidence_paths(raw, (), evid)
        listing = {}
        span, month = _period_info(args.get("period"), self.today)
        if args.get("from_date") and args.get("to_date"):
            span, month = _period_info({"from": args.get("from_date"), "to": args.get("to_date")}, self.today)
        base = {"categories": categories(str(args.get("label") or "")) | ({args["label"]} if str(args.get("label") or "")
                in _CATEGORY_WORDS else set()), "span": span, "month": month, "rate": None}
        if tool == "general_estimate" and isinstance(view, dict):
            base["rate"] = {"per month": "month", "per year": "year"}.get(str(view.get("per") or ""))
        state = {"n": 0, "calc_labels": {}}
        if tool == "calculate" and isinstance(view, dict) and isinstance(view.get("results"), list):
            state["calc_labels"] = {"results[%d]" % i: str(r.get("label") or "")
                                    for i, r in enumerate(view["results"]) if isinstance(r, dict)}
        tagged = self._walk(tool, args, view, (), base, None, call, evid, listing, state)
        if isinstance(tagged, dict) and listing:
            tagged = dict(tagged)
            tagged["figures"] = listing
        return tagged

    def _walk(self, tool, args, o, keys, ctx, unit, call, evid, listing, state):
        if isinstance(o, bool) or o is None:
            return o
        if isinstance(o, (int, float)):
            fid = self._leaf(tool, args, o, keys, ctx, unit, call, evid, state)
            if fid:
                listing[fid] = self._listing_label(self.by_id[fid])
            return o
        if isinstance(o, str):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", o.strip()):
                self.dates.add((int(o[5:7]), int(o[8:10])))
                return o
            if state["n"] >= MAX_PER_SOURCE or (keys and keys[-1] in ("expression", "label", "what")):
                return o         # a calculation's own expression, a label: not figures to quote
            src = {"kind": "tool", "tool": tool, "call": call, "path": _path(keys), "args": args,
                   "evidence": _evidence_for(evid, keys)}
            before = len(self.figs)
            out = self.tag_text(o, src, dict(ctx, label="%s %s" % (tool, _path(keys))), dedupe=("call", call))
            state["n"] += len(self.figs) - before
            return out
        if isinstance(o, dict):
            ctx = dict(ctx)
            if isinstance(o.get("label"), str):
                cats = categories(o["label"]) | ({o["label"]} if o["label"] in _CATEGORY_WORDS else set())
                if cats:
                    ctx["categories"] = cats
            if "period" in o:
                sp, mo = _period_info(o.get("period"), self.today)
                if sp:
                    ctx["span"], ctx["month"] = sp, mo
            if isinstance(o.get("month"), str) and re.fullmatch(r"\d{4}-\d{2}", o["month"]):
                ctx["span"], ctx["month"] = _period_info(o["month"], self.today)
            if "from" in o and "to" in o:
                sp, mo = _period_info(o, self.today)
                if sp:
                    ctx["span"], ctx["month"] = sp, mo
            u = o.get("unit") if isinstance(o.get("unit"), str) else unit
            if isinstance(o.get("note"), str) and "percent" in o["note"].lower():
                u = "pct"
            out = {}
            cols = o.get("columns")
            for k, v in o.items():
                if k in ("card", "evidence", "figures"):
                    out[k] = v
                    continue
                if k == "rows" and isinstance(cols, list) and isinstance(v, list) and v and isinstance(v[0], list):
                    rows = []
                    for i, r in enumerate(v):
                        if i < MAX_LIST_ITEMS:
                            rows.append([self._walk(tool, args, x, keys + ("rows[%d]" % i, str(c)), ctx, None, call,
                                                    evid, listing, state) for c, x in zip(cols, r)])
                        else:
                            rows.append(r)
                    out[k] = rows
                    continue
                sub_u = "pct" if (_PCT_KEY.search(str(k).lower()) and isinstance(v, dict)) else (None if k == "unit" else u)
                out[k] = self._walk(tool, args, v, keys + (str(k),), ctx, sub_u, call, evid, listing, state)
            return out
        if isinstance(o, (list, tuple)):
            res = []
            for i, v in enumerate(o):
                if i < MAX_LIST_ITEMS:
                    res.append(self._walk(tool, args, v, keys[:-1] + ((keys[-1] if keys else "") + "[%d]" % i,),
                                          ctx, unit, call, evid, listing, state))
                else:
                    res.append(v)
            return res
        return o

    def _leaf(self, tool, args, v, keys, ctx, unit, call, evid, state):
        if state["n"] >= MAX_PER_SOURCE or not keys:
            return None
        k = keys[-1].split("[")[0].lower()
        if _SKIP_KEY.search(k) or (k in ("year", "years") and 1900 <= abs(v) <= 2100):
            return None
        u = str(unit or "").lower()
        exact = False
        if _PCT_KEY.search(k) or u in ("share", "ratio", "pct", "percent"):
            kind, val = "percent", (v * 100 if abs(v) <= 1.0 and not re.search(r"pct|percent", k) else v)
        elif _OTHER_KEY.search(k) or re.search(r"count|people|years|m2|days|months", u):
            kind, val = ("count" if _COUNT_KEY.search(k) else "number"), v
        else:
            kind, val = "money", v
            exact = (tool not in _HELPERS and k in ("total", "amount", "balance", "price", "spent", "income", "sum")
                     and not re.search(r"avg|average|usual|typical|per_|monthly|estimate|mid", ".".join(keys)))
        group, rate, cats = None, None, set(ctx.get("categories") or ())
        if tool == "calculate":
            row_label = _calc_label(keys, state)
            group = None
            rate = rate_of(row_label)
            cats = categories(row_label)
            if re.search(r"\bmonths?\b|\bweeks?\b|\bdays?\b|\byears?\b|\btimes\b|kuukau|viiko|päiv|vuo", row_label, re.I) \
                    and not re.search(r"€|eur|per month|a month|kuukaudessa", row_label, re.I):
                kind = "number"
            elif re.search(r"%|percent|share|prosent|osuus", row_label, re.I):
                kind = "percent"
            if keys[-1] in ("rounded", "rounded_up"):
                return None
        elif kind == "money":
            group = _key_metric(tool, [x.split("[")[0] for x in keys])
            rate = _key_rate(keys) or ctx.get("rate")
        span = ctx.get("span") if (not rate and _TOTAL_KEY.match(k)) else None
        month = ctx.get("month") if (ctx.get("span") in ("month", "part_month", "day") and not rate) else None
        src = {"kind": "tool", "tool": tool, "call": call, "path": _path(keys), "args": args,
               "evidence": _evidence_for(evid, keys)}
        label = _leaf_label(tool, keys, cats, rate, span, month, args, state)
        fid = self._add(val, kind, label, src, exact=exact, group=group, cats=cats, rate=rate, span=span,
                        month=month, dedupe=("call", call))
        state["n"] += 1
        return fid

    def _listing_label(self, f):
        return "%s = %s" % (fmt(f), f["label"])

    # -- for the model
    def listing(self, ids=None):
        """'f1 = €3,000: ...' lines, for a prompt or a repair note."""
        return "\n".join(self._listing_label(f) for f in self.figs if ids is None or f["id"] in ids)

    def value(self, fid):
        f = self.get(fid)
        return None if f is None else f["value"]

    def resolve_expression(self, expr):
        """For calculate: '{{f3}} * 12' or 'f3 * 12' -> '92.85 * 12'. Raises KeyError for an unknown id."""
        def one(m):
            fid = "f" + (m.group(1) or m.group(2))
            f = self.get(fid)
            if f is None:
                raise KeyError(fid)
            return repr(float(f["value"]))
        return re.sub(r"\{\{\s*f(\d+)\s*\}\}|\bf(\d+)\b", one, str(expr))

    # -- matching
    def candidates(self, kind, val):
        out = []
        for f in self.figs:
            if kind == "money" and f["unit"] != "money" and not (f["unit"] == "number"
                                                                and f["source"].get("tool") == "calculate"):
                continue
            if kind == "percent" and f["unit"] != "percent":
                continue
            if close(f["value"], val):
                out.append(f)
        return out


def _calc_label(keys, state):
    lab = state.get("calc_labels", {}).get(keys[0] if keys else "")
    return lab or ""


def _leaf_label(tool, keys, cats, rate, span, month, args, state):
    what = ".".join(keys)
    if tool == "calculate":
        what = _calc_label(keys, state) or what
    parts = [what]
    if cats:
        parts.append("category " + "/".join(sorted(cats)))
    if rate:
        parts.append("per " + rate)
    elif span:
        parts.append({"month": "one month", "part_month": "part of a month", "week": "one week", "day": "one day",
                      "multi": "several months", "year": "a year"}.get(span, span))
    if month:
        parts.append("%d-%02d" % month if month[0] else "month %d" % month[1])
    return ", ".join(parts)


def _path(keys):
    return ".".join(keys)


def _evidence_paths(o, keys, out):
    if isinstance(o, dict):
        ev = o.get("evidence")
        if isinstance(ev, list):
            out[keys] = [e for e in ev if isinstance(e, dict)][:5]
        elif isinstance(ev, dict):
            out[keys] = [ev]
        for k, v in o.items():
            if k not in ("evidence", "card"):
                _evidence_paths(v, keys + (str(k),), out)
    elif isinstance(o, list):
        for i, v in enumerate(o[:MAX_LIST_ITEMS]):
            _evidence_paths(v, keys[:-1] + ((keys[-1] if keys else "") + "[%d]" % i,), out)


def _evidence_for(evid, keys):
    for n in range(len(keys), -1, -1):
        if tuple(keys[:n]) in evid:
            return evid[tuple(keys[:n])]
    return []


def _find_in(data, value, unit):
    """(tool, path, evidence) of the first number in the snapshot data that the figure equals."""
    hits = []

    def walk(o, keys, ev):
        if hits:
            return
        if isinstance(o, dict):
            e = o.get("evidence")
            ev2 = [e] if isinstance(e, dict) else ([x for x in e if isinstance(x, dict)][:5] if isinstance(e, list) else ev)
            for k, v in o.items():
                if k not in ("evidence", "card") and not str(k).startswith("_"):
                    walk(v, keys + (str(k),), ev2)
        elif isinstance(o, list):
            for i, v in enumerate(o[:MAX_LIST_ITEMS]):
                walk(v, keys[:-1] + ((keys[-1] if keys else "") + "[%d]" % i,), ev)
        elif isinstance(o, (int, float)) and not isinstance(o, bool) and o:
            v = o * 100 if unit == "percent" and abs(o) <= 1 else o
            if close(v, value):
                hits.append({"tool": keys[0] if keys else "customer_snapshot", "path": ".".join(keys[1:]),
                             "evidence": ev or []})
    walk(data, (), [])
    return hits[0] if hits else None


def _sentence_around(text, sp):
    a = 0
    for m in _SENT_END.finditer(text, 0, sp[0]):
        a = m.end()
    m = _SENT_END.search(text, sp[1])
    return text[a:m.start() if m else len(text)]


_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÅ\"\u201c(€\d{])|\n+")


def build_table(calls=(), snapshot_lines=(), snapshot_data=None, earlier=(), message="", today=None):
    """A table from (tool, args, result) calls, the customer picture, earlier answers and the message."""
    t = FigureTable(today)
    t.add_snapshot(snapshot_lines, snapshot_data)
    t.add_earlier(earlier)
    t.add_message(message)
    for c in calls or ():
        t.add_result(c[0], c[1], c[2], raw=c[2])
    return t


# ------------------------------------------------------------------ does a figure fit its sentence
def fits(fig, sentence, before, after, today=None):
    """None when the figure may stand at this place of the sentence, else the reason it may not."""
    part = before + " " + after
    if fig.get("said") and _ASSERT_RE.search(part):
        return "is the customer's own figure, stated as a fact of their account"
    cats = _with_family(fig.get("categories") or ())
    named = _with_family(categories(sentence))
    if cats and named and not (cats & named):
        return "is about %s, but the sentence is about %s" % ("/".join(sorted(fig["categories"])),
                                                              "/".join(sorted(categories(sentence))))
    if fig["unit"] == "money" and fig.get("group"):
        allg = metric_groups(sentence)
        groups = allg & {"in", "out"}
        if fig["group"] == "keep":
            groups = groups if groups == {"in"} and "keep" not in allg else set()
        elif allg == {"keep"}:
            groups = allg if fig["group"] == "in" else set()
        if groups and fig["group"] not in groups:
            return "is %s, but the sentence speaks of %s" % (_GROUP_WORD[fig["group"]],
                                                             " and ".join(_GROUP_WORD[g] for g in sorted(groups)))
    if fig["unit"] in ("money", "count"):
        said_rate = rate_of(after) or rate_of(before)
        fig_rate = fig.get("rate") or {"month": "month", "week": "week", "day": "day", "year": "year",
                                       "multi": "multi", "part_month": "part_month"}.get(fig.get("span"))
        if said_rate and fig_rate and said_rate != fig_rate:
            return "is %s, but the sentence says %s" % (_RATE_WORD.get(fig_rate, fig_rate), _RATE_SAID[said_rate])
        if fig.get("month") and not fig.get("rate"):
            named_m = months_named(part, today) or (months_named(sentence, today)
                                                     if len(months_named(sentence, today)) == 1 else set())
            fm = tuple(fig["month"])
            if named_m and not any(m[1] == fm[1] and (m[0] is None or fm[0] is None or m[0] == fm[0])
                                   for m in named_m):
                return "is for %s, but the sentence names another month" % _month_word(fm)
    return None


_GROUP_WORD = {"in": "income (money coming in)", "out": "spending", "keep": "money kept (balance, savings, left over)"}
_RATE_WORD = {"month": "a figure for one month", "week": "a figure for one week", "day": "a figure for one day",
              "year": "a figure for a year", "multi": "a total over several months",
              "part_month": "a total for part of a month"}
_RATE_SAID = {"week": "every week", "month": "a month", "year": "a year", "day": "a day"}


def _month_word(ym):
    return "%s%s" % (_MONTH_EN[ym[1] - 1].capitalize(), (" %d" % ym[0]) if ym[0] else "")


# ------------------------------------------------------------------ checking and filling an answer
def split_sentences(text):
    """[(paragraph index, sentence)]."""
    out = []
    for pi, para in enumerate(re.split(r"\n\s*\n", str(text or "").strip())):
        for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÅ\"\u201c(€\d{])", para.strip()):
            if s.strip():
                out.append((pi, " ".join(s.split())))
    return out


def _date_known(val, table):
    return (val[1], val[2]) in table.dates


def process_sentence(sentence, table, lang="en", adopt=True):
    """(rendered sentence, [figure records with offsets in it], [violations])."""
    today = table.today
    found = []          # (start, end, kind, payload)
    for fid, sp in slots(sentence):
        found.append((sp[0], sp[1], "slot", fid))
    for kind, val, sp in tokens(sentence):
        found.append((sp[0], sp[1], kind, val))
    found.sort()
    spans = [(a, b) for a, b, k, _ in found if k in ("slot", "money", "percent", "number", "bad")]
    pieces, figs, bad = [], [], []
    pos = 0
    drop = {}           # index of a token -> the span removed with it
    swallow = {}        # index of a slot -> characters after it removed with it
    # a figure in digits right next to its own slot ("€92.85 {{f3}}", "{{f3}} (€92.85)") is dropped
    for i, (a, b, k, p) in enumerate(found):
        if k != "slot" or table.get(p) is None:
            continue
        for j in (i - 1, i + 1):
            if 0 <= j < len(found) and found[j][2] in ("money", "percent", "number") and j not in drop:
                ja, jb = found[j][0], found[j][1]
                gap = sentence[jb:a] if j < i else sentence[b:ja]
                if re.fullmatch(r"[\s(\[=:~]*", gap) and close(table.get(p)["value"], found[j][3]):
                    if j < i:
                        drop[j] = (ja, a)
                        m = re.match(r"\s*[)\]]", sentence[b:]) if ("(" in gap or "[" in gap) else None
                        if m:
                            swallow[i] = m.end()      # "€92.85 ({{f3}})": the closing bracket goes too
                    else:
                        m = re.match(r"\s*[)\]]", sentence[jb:]) if ("(" in gap or "[" in gap) else None
                        drop[j] = (b, jb + m.end() if m else jb)
    for i, (a, b, k, p) in enumerate(found):
        raw = sentence[a:b]
        others = [s for s in spans if s != (a, b)]
        before, after = window(sentence, (a, b), others)
        rep = None
        fig = None
        if i in drop:
            ra, rb = drop[i]
            pieces.append(sentence[pos:max(pos, ra)])
            pos = max(pos, rb)
            continue
        if k == "slot":
            fig = table.get(p)
            if fig is None:
                bad.append({"raw": raw, "reason": "unknown_slot", "detail": "%s is not in the figure list" % p})
                continue
            why = fits(fig, sentence, before, after, today)
            if why:
                bad.append({"raw": raw, "id": p, "reason": "misfit", "detail": "%s %s" % (p, why)})
                continue
            rep = fmt(fig, lang)
        elif k == "bad":
            bad.append({"raw": raw, "reason": "unreadable", "detail": "%s cannot be read as a figure" % raw})
            continue
        elif k == "date":
            if p[2] is not None and not _date_known(p, table):
                bad.append({"raw": raw, "reason": "unknown_date", "detail": "the date %s is not in the data" % raw})
            continue
        elif is_free(k, p, sentence, (a, b)):
            continue
        elif k == "ordinal":
            if not any(d == p for _m, d in table.dates):
                bad.append({"raw": raw, "reason": "unknown", "detail": "%s is not a figure of this turn" % raw})
            continue
        else:
            cands = table.candidates(k, p)
            if not cands:
                bad.append({"raw": raw, "reason": "unknown",
                            "detail": "%s is not a figure in the data, the customer picture, an estimate or a "
                                      "calculation" % raw})
                continue
            ok = [c for c in cands if not fits(c, sentence, before, after, today)]
            if not ok:
                bad.append({"raw": raw, "reason": "misfit", "id": cands[0]["id"],
                            "detail": "%s matches %s, which %s" % (raw, cands[0]["id"],
                                                                   fits(cands[0], sentence, before, after, today))})
                continue
            if not adopt:
                bad.append({"raw": raw, "reason": "digits", "id": ok[0]["id"],
                            "detail": "%s written in digits; write {{%s}}" % (raw, ok[0]["id"])})
                continue
            ok.sort(key=lambda c: (abs(c["value"] - abs(p)) > 0.006, c["said"],
                                   SOURCE_ORDER.get(c["source"].get("kind"), 9), -int(c["id"][1:])))
            fig = ok[0]
            rep = _restyle(k, p, raw, lang)
        pieces.append(sentence[pos:a])
        start = sum(len(x) for x in pieces)
        pieces.append(rep)
        figs.append({"id": fig["id"], "start": start, "end": start + len(rep), "text": rep, "label": fig["label"],
                     "unit": fig["unit"], "value": fig["value"], "source": _public_source(fig["source"]),
                     "written": "slot" if k == "slot" else "digits"})
        pos = b + swallow.get(i, 0)
    pieces.append(sentence[pos:])
    out = re.sub(r"[ \t]{2,}", " ", "".join(pieces))
    if out != "".join(pieces):        # offsets moved: recompute by searching in order
        cur = 0
        for f in figs:
            i = out.find(f["text"], cur)
            f["start"], f["end"] = i, i + len(f["text"])
            cur = f["end"]
    return out, figs, bad


def _restyle(kind, val, raw, lang):
    """A figure the model wrote in digits and that matched the table: its own value and rounding, in the
    reply's way of writing money and percentages."""
    if kind == "money":
        cents = abs(val - round(val)) > 0.004 or bool(re.search(r"[.,]\d{2}(?!\d)", raw))
        s = ("{:,.2f}" if cents else "{:,.0f}").format(abs(val))
        return s.replace(",", "\u00a0").replace(".", ",") + "\u00a0€" if lang == "fi" else "€" + s
    if kind == "percent":
        return fmt_percent(val, lang)
    return raw


def _public_source(src):
    keep = ("kind", "tool", "call", "path", "args", "evidence", "line", "index")
    return {k: v for k, v in (src or {}).items() if k in keep}


class Rendered(dict):
    """text, ok, figures (offsets in text), violations, dropped, sentences, answer_dropped."""


def render(text, table, lang="en", adopt=True):
    """Fill the slots of a model answer and remove the sentences that fail. ok is False when what is left would
    not answer the question (see the module docstring); the caller then repairs or falls back."""
    sents = split_sentences(text)
    kept, figures, violations, dropped = [], [], [], []
    answer_idx = None
    for i, (pi, s) in enumerate(sents):
        rendered, figs, bad = process_sentence(s, table, lang, adopt)
        has_figure = bool(slots(s)) or any(k in ("money", "percent") or (k == "number" and not is_free(k, v))
                                           for k, v, _sp in tokens(s))
        if answer_idx is None and has_figure:
            answer_idx = i
        if bad:
            dropped.append(i)
            for b in bad:
                b["sentence"] = i
                b["text"] = s
            violations.extend(bad)
            continue
        kept.append((pi, rendered, figs))
    out, pos, last_p = [], 0, None
    for pi, s, figs in kept:
        sep = "" if last_p is None else ("\n\n" if pi != last_p else " ")
        pos += len(sep)
        for f in figs:
            f = dict(f, start=f["start"] + pos, end=f["end"] + pos)
            figures.append(f)
        out.append(sep + s)
        pos += len(s)
        last_p = pi
    final = "".join(out)
    answer_dropped = bool(dropped) and (0 in dropped or (answer_idx is not None and answer_idx in dropped))
    ok = bool(final.strip()) and not answer_dropped and len(dropped) * 2 <= len(sents)
    return Rendered(text=final, ok=ok, figures=figures, violations=violations, dropped=dropped,
                    sentences=len(sents), answer_dropped=answer_dropped)


def check(text, table, adopt=True):
    """The violations of a draft (empty when every figure is grounded and fits)."""
    return render(text, table, adopt=adopt)["violations"]


REPAIR_NOTE = ("[Automatic check by the app, not a message from the customer] Your draft was not shown. Write every "
               "figure as its slot from the figure lists, for example {{f3}}, never in digits, and only where the "
               "figure's label fits the sentence. These did not pass: %s. Get a figure you lack with a tool "
               "(calculate for sums, general_estimate for outside knowledge, a data tool for their own money) or "
               "leave it out, then write the whole answer again for the customer, without mentioning this check.")


def repair_note(violations, limit=6):
    seen, parts = set(), []
    for v in violations:
        d = v.get("detail") or v.get("raw")
        if d in seen:
            continue
        seen.add(d)
        parts.append(d)
        if len(parts) >= limit:
            break
    return REPAIR_NOTE % "; ".join(parts)


def answering_call(calls, figures, helpers=_HELPERS):
    """Index into calls of the data tool that answered: the one whose figures the answer used most (ties: the
    later one), else the last data tool called, else None. figures: render(...)["figures"] or slot records."""
    counts = {}
    for f in figures or ():
        src = f.get("source") or {}
        i = src.get("call")
        if src.get("kind") == "tool" and isinstance(i, int) and 0 <= i < len(calls) and calls[i][0] not in helpers:
            counts[i] = counts.get(i, 0) + 1
    if counts:
        return max(counts, key=lambda i: (counts[i], i))
    data = [i for i, c in enumerate(calls or ()) if c[0] not in helpers]
    return data[-1] if data else None


def used_figures(text, table):
    """The figure records a draft refers to, valid or not: for answering_call on a draft that failed."""
    out = []
    for _pi, s in split_sentences(text):
        for fid, _sp in slots(s):
            f = table.get(fid)
            if f:
                out.append({"id": fid, "source": f["source"]})
        for kind, val, _sp in tokens(s):
            if kind in ("money", "percent", "number") and not is_free(kind, val):
                for f in table.candidates(kind, val)[:1]:
                    out.append({"id": f["id"], "source": f["source"]})
    return out


# ------------------------------------------------------------------ the raw-text checker (legacy paths)
def ungrounded_spans(text, calls=(), message="", snapshot_lines=(), snapshot_data=None, earlier=(), today=None,
                     table=None):
    """Spans of figures in raw text that are not grounded or do not fit their sentence. Default settings check
    money, percentages and bare numbers (with the free-number rule) and what each figure refers to."""
    table = table or build_table(calls, snapshot_lines, snapshot_data, earlier, message, today)
    text = text or ""
    bad = []
    for _pi, s in split_sentences(text):
        _out, _figs, vs = process_sentence(s, table)
        if not vs:
            continue
        base = text.find(s)
        for v in vs:
            i = s.find(v["raw"])
            if base >= 0 and i >= 0:
                bad.append((base + i, base + i + len(v["raw"])))
            else:
                bad.append((0, 0))
    return bad


def numbers_grounded(text, calls=(), message="", **kw):
    return not ungrounded_spans(text, calls, message, **kw)
