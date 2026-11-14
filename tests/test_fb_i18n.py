"""Lane I18N: the interface in Finnish (web/i18n.js, web/i18n-fi.js). The translator is exercised in node with a
tiny fake window; the tests skip when node is not installed."""
import json
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm'), path = require('path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
function load(lang, nav, withFi) {
  const store = lang ? { 'svinkki.lang': lang } : {};
  const win = { localStorage: { getItem: k => store[k] || null, setItem: (k, v) => { store[k] = v; } }, navigator: { language: nav || 'en-US' } };
  win.window = win;
  const ctx = vm.createContext(win);
  const files = ['i18n.js'].concat(withFi === false ? [] : ['i18n-fi.js']);
  for (const f of files) vm.runInContext(fs.readFileSync(path.join(input.web, f), 'utf8'), ctx);
  return win.SvI18n;
}
const out = {};
const fi = load('fi');
out.fi = input.strings.map(s => fi.t(s));
const en = load('en');
out.en = input.strings.map(s => en.t(s));
out.defaultFi = load(null, 'fi-FI').lang;
out.defaultEn = load(null, 'en-GB').lang;
out.storedWins = load('en', 'fi-FI').lang;
const bare = load('fi', 'fi', false);
bare.add({ 'Hello there': 'Moikka' }, [[/^Total (\d+) items$/, 'Yhteensä $1 kohdetta'], [/^Only (\d+)$/, function (m, n) { return 'Vain ' + n; }]]);
out.add = [bare.t('Hello there'), bare.t('  Hello there \n'), bare.t('Total 4 items'), bare.t('Only 9'), bare.t('Nothing known')];
out.weird = [bare.t(null), bare.t(undefined), bare.t(42), bare.t('x'.repeat(500)), bare.t('12 345'), bare.t('constructor'), bare.t('__proto__')];
console.log(JSON.stringify(out));
"""


def run_node(strings):
    p = subprocess.run([NODE, "-e", HARNESS], input=json.dumps({"web": WEB, "strings": strings}),
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    if p.returncode != 0:
        raise AssertionError(p.stderr)
    return json.loads(p.stdout)


NB = " "
CASES = [
    ("Settings", "Asetukset"),
    ("  Settings  ", "  Asetukset  "),
    ("Your things", "Omat asiasi"),
    ("Daily quiz", "Päivän visa"),
    ("Worth a look", "Kannattaa katsoa"),
    ("Taxi", "Taksit"), ("Groceries", "Ruokakauppa"), ("Restaurant", "Ravintolat"), ("Fast food", "Pikaruoka"),
    ("Fuel", "Polttoaine"), ("Housing", "Asuminen"), ("Regular essentials", "Perusmenot"),
    ("Unexpected necessities", "Odottamattomat menot"), ("Everyday spending", "Arkikulutus"),
    ("Hi Anna!", "Hei Anna!"),
    ("From 5 transactions", "5 tapahtumasta"),
    ("Approve and move 307 €", "Hyväksy ja siirrä 307 €"),
    ("Where your money went in elokuu", "Mihin rahasi menivät elokuussa"),
    ("Safe to spend until 15.10.", "Käyttövara 15.10. asti"),
    ("a month for 12 months", "kuukaudessa 12 kuukauden ajan"),
    ("307 € left over · elokuu", "307 € jäi yli · elokuu"),
    ("Move €307 to savings", "Siirrä 307 € säästöön"),
    ("€1,583.50 saved in S-mobiili", "1" + NB + "583,50 € säästetty S-mobiilissa"),
    ("Done: €307 moved to your S-Bank savings account.", "Valmis: 307 € siirretty S-Pankin säästötilillesi."),
    ("Today 14:05", "Tänään 14:05"),
    ("12 Nov", "12.11."),
    ("Taxi · Savings goal", "Taksit · Säästötavoite"),
]
UNKNOWN = ["Pizzeria Mario", "Anna, 23", "Totally unknown sentence here."]


@unittest.skipUnless(NODE, "node is not installed")
class TestTranslator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.strings = [c[0] for c in CASES] + UNKNOWN + ["Settings"]
        cls.res = run_node(cls.strings)

    def test_finnish_exact_whitespace_and_patterns(self):
        for (src, want), got in zip(CASES, self.res["fi"]):
            self.assertEqual(got, want, src)

    def test_unknown_text_comes_back_unchanged(self):
        base = len(CASES)
        for i, s in enumerate(UNKNOWN):
            self.assertEqual(self.res["fi"][base + i], s)

    def test_english_is_a_passthrough(self):
        self.assertEqual(self.res["en"], self.strings)

    def test_language_choice(self):
        self.assertEqual(self.res["defaultFi"], "fi")      # a Finnish browser starts in Finnish
        self.assertEqual(self.res["defaultEn"], "en")
        self.assertEqual(self.res["storedWins"], "en")     # a stored choice beats the browser

    def test_add_registers_strings_and_patterns(self):
        self.assertEqual(self.res["add"], ["Moikka", "  Moikka \n", "Yhteensä 4 kohdetta", "Vain 9", "Nothing known"])

    def test_never_throws_and_skips_long_text(self):
        n, u, num, long_, digits, ctor, proto = self.res["weird"]
        self.assertIsNone(n)
        self.assertIsNone(u)
        self.assertEqual(num, 42)
        self.assertEqual(long_, "x" * 500)
        self.assertEqual(digits, "12 345")
        self.assertEqual((ctor, proto), ("constructor", "__proto__"))


def _read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def _literals(src):
    return re.findall(r"""'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)\"""", src)


@unittest.skipUnless(NODE, "node is not installed")
class TestDemoPathCoverage(unittest.TestCase):
    """Strings the demo path shows, taken from app.js at test time: each one has a Finnish entry."""

    def test_home_chips_and_help_questions(self):
        app = _read("app.js")
        blocks = []
        for name in ("SUGGEST", "ASK_GROUPS", "FOLLOW"):
            m = re.search(r"var %s = [\[{].*?\n  [\]}];" % name, app, re.S)
            self.assertIsNotNone(m, name)
            blocks.append(m.group(0))
        keys = set()
        for blk in blocks:
            for a, b in _literals(blk):
                s = (a or b).replace("\\'", "'")
                if re.search(r"[A-Za-z]", s) and " " in s and not re.fullmatch(r"[a-z]+", s):
                    keys.add(s)
        keys = sorted(keys)
        self.assertGreater(len(keys), 40)
        out = run_node(keys)["fi"]
        missing = [k for k, v in zip(keys, out) if k == v]
        self.assertEqual(missing, [])

    def test_must_have_demo_strings(self):
        must = [
            "Who are you today?", "Try as a random customer", "Start", "Your choices", "Ask about your money",
            "Your things", "Conversations", "For you", "Your check-in", "Safe to spend", "Where your money went",
            "What can I ask?", "Everything I can do", "Settings", "Log out", "Try again", "Move money",
            "Approve this move?", "Cancel", "Not now", "Show the move", "Savings goal", "Daily quiz", "Lock in my guess",
            "On track", "Tight", "Over budget", "Regular essentials", "Unexpected necessities", "Everyday spending",
            "Goes out and eats out regularly: taxis, bars and nights out to ask about.",
            "Retired or close to it, with steady, careful spending.", "More", "See the transactions",
            "Nothing moves until you approve. The money stays in S-mobiili.",
            "Your balance covers about 0.5 months of regular costs.",
            "Okay, I won't suggest this again. No money was moved.",
        ]
        out = run_node(must)["fi"]
        self.assertEqual([k for k, v in zip(must, out) if k == v], [])

    def test_every_help_group_title_in_app_js(self):
        app = _read("app.js")
        titles = re.findall(r"\{ title: '([^']+)', icon:", app)
        self.assertGreaterEqual(len(titles), 7)
        out = run_node(titles)["fi"]
        self.assertEqual([k for k, v in zip(titles, out) if k == v], [])


class TestWiring(unittest.TestCase):
    def test_scripts_exist_and_load_before_app(self):
        html = _read("index.html")
        order = [html.index(s) for s in ('src="i18n.js"', 'src="i18n-fi.js"', 'src="extras.js"', 'src="app.js"')]
        self.assertEqual(order, sorted(order))
        for name in ("i18n.js", "i18n-fi.js"):
            self.assertTrue(os.path.getsize(os.path.join(WEB, name)) > 500, name)

    def test_switch_has_no_inline_style(self):
        src = _read("i18n.js")
        self.assertNotIn("createElement('style')", src)
        self.assertNotIn("innerHTML", src)
        self.assertIn("lang-switch", src)


if __name__ == "__main__":
    unittest.main()
