"""Lane EXTRAS: web/extras.js (tappable figures) is wired in, served, safe, and its pure functions behave."""
import json
import os as _os
import re
import shutil
import subprocess
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fixture as fx  # noqa: E402

WEB = fx.REPO / "web"
JS = (WEB / "extras.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


class ExtrasStatic(unittest.TestCase):
    def test_defines_the_hook(self):
        self.assertRegex(JS, r"window\.SvinkkiExtras\s*=\s*\{")
        self.assertIn("afterReply", JS)

    def test_no_inner_html(self):
        self.assertNotRegex(JS, r"innerHTML|outerHTML|insertAdjacentHTML|document\.write")

    def test_load_order_in_the_page(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("styles.css"), html.index("extras.css"))
        self.assertLess(html.index("extras.js"), html.index('src="app.js"'))

    def test_no_raw_keys_shown(self):
        self.assertNotIn("{{", JS)


class ExtrasServed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_both_files_are_served(self):
        for path, kind in (("/extras.js", "javascript"), ("/extras.css", "text/css")):
            r = self.server.client().get(path)
            self.assertEqual(r.status, 200, path)
            self.assertRegex(r.header("Content-Type"), kind)


@unittest.skipUnless(NODE, "node is not installed")
class ExtrasPure(unittest.TestCase):
    def run_js(self, body):
        code = ("global.window={};global.document={addEventListener(){}};"
                "require(%s);const T=window.SvinkkiExtras._test;%s" % (json.dumps(str(WEB / "extras.js")), body))
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_phrase_and_matching(self):
        fig = {"text": "\u20ac92.85", "label": "total, category Taxi, one month, 2026-08", "start": 10,
               "source": {"kind": "tool", "tool": "get_spend", "path": "total",
                          "evidence": [{"title": "Taxi purchases", "from": "2026-08-01", "to": "2026-08-31"}]}}
        est = {"text": "\u20ac700", "label": "low", "source": {"kind": "tool", "tool": "general_estimate",
               "args": {"what": "a bike"}, "evidence": []}}
        weird = {"text": "39%", "label": "top_labels[0].share", "source": {"kind": "tool", "tool": "get_overview",
                 "path": "top_labels[0].share"}}
        out = self.run_js("console.log(JSON.stringify({a:T.phrase(%s),b:T.phrase(%s),c:T.phrase(%s),"
                          "m:T.matchFigures(['You spent ','\u20ac92.85',' on taxis, \u20ac92.85 again'],"
                          "[{text:'\u20ac92.85'},{text:'\u20ac92.85'},{text:'nope'},{text:'\u20ac92.85'}]),"
                          "e:T.matchFigures([],[{text:'x'}]),n:T.matchFigures(['a'],[{}, null])}))"
                          % (json.dumps(fig), json.dumps(est), json.dumps(weird)))
        self.assertIn("August 2026", out["a"]["lead"])
        self.assertIn("Added up by the app", out["a"]["how"])
        self.assertTrue(out["b"]["estimate"])
        self.assertIn("estimate", out["b"]["lead"])
        for k in "abc":
            blob = json.dumps(out[k])
            self.assertNotRegex(blob, r"get_spend|get_overview|general_estimate|\[0\]|top_labels")
        self.assertEqual([(h["node"], h["at"]) for h in out["m"]], [(1, 0), (2, 11)])
        self.assertEqual(out["e"], [])
        self.assertEqual(out["n"], [])


if __name__ == "__main__":
    unittest.main()
