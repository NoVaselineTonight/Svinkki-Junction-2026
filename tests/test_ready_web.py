"""Lane WEBJS: web/app.js behaviour and copy fixes, checked on the source text (no browser here)."""
import os as _os
import shutil
import subprocess
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fixture as fx  # noqa: E402

WEB = fx.REPO / "web"
JS = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")


class ReadyWeb(unittest.TestCase):
    def test_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        r = subprocess.run([node, "--check", str(WEB / "app.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_hooks_kept(self):
        self.assertIn("window.SvinkkiExtras.afterReply", JS)
        self.assertIn('<script src="app.js"></script>', HTML)
        self.assertIn("extras.js", HTML)
        self.assertIn("extras.css", HTML)

    def test_public_copy_hides_operator_controls(self):
        self.assertIn("me.demo.reset === false", JS)
        self.assertIn("me.demo.ai_setup === false", JS)
        self.assertIn("unknown_persona", JS)

    def test_stored_proposals_have_no_buttons(self):
        self.assertIn("drawingStored", JS)
        self.assertIn("'Moved'", JS)

    def test_overdraft_suggestion_opens_the_question(self):
        self.assertIn("When was my balance below zero?", JS)

    def test_finnish_answers_get_finnish_money_and_chips(self):
        self.assertIn("fi-FI", JS)
        self.assertIn("FOLLOW_FI", JS)
        self.assertIn("res.lang === 'fi'", JS)

    def test_one_quiz_name_and_no_jargon_tag(self):
        self.assertNotIn("Weekly quiz", JS)
        self.assertNotIn("On-device rules", JS)


if __name__ == "__main__":
    unittest.main()
