"""A warmer, concrete coach: the prompt asks for money-psychology habits (meet them first, make it tangible,
start small, one step with a moment, no shame, their choice), and the picture of the customer carries a small
step and what it becomes, worked out by code, so the model can say "€10 a month is €120 in a year" without
doing sums. Basis: docs/MONEY_PSYCHOLOGY.md.
"""
import unittest

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import fixture as fx
import fixture_claude as fc

A = fx.A_CID


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        import app.coach as coach
        import app.voice as voice
        cls.coach, cls.voice = coach, voice

    def ctx(self, cid=A, **over):
        c = fx.make_ctx(cid)
        c.memory = {}
        c.cid = cid
        for k, v in over.items():
            setattr(c, k, v)
        return c


def _hooked():
    """True once app/coach.py uses app/voice.py (the hookup lands in its own pull request)."""
    import app.coach as coach
    return "Your voice: a warm, human coach" in coach.SYSTEM_PROMPT


class VoiceTests(_Base):
    def test_the_voice_asks_for_a_warm_concrete_coach(self):
        p = self.voice.VOICE
        for bit in ("Your voice: a warm, human coach", "Meet them first", "Make every suggestion tangible",
                    "€10 a month is €120 in a year and €240 in two", "Start small", "One step with a moment",
                    "Leave the choice with them", "Takuusäätiö", "never work them out in your head",
                    "docs/MONEY_PSYCHOLOGY.md"):
            self.assertIn(bit, p)
        for shaming in ("you should", "you must"):
            self.assertNotIn(shaming, p.lower().replace('never say "should"', ""))

    def test_the_research_note_exists_with_its_references(self):
        with open(_os.path.join(str(fx.REPO), "docs", "MONEY_PSYCHOLOGY.md"), encoding="utf-8") as f:
            doc = f.read()
        for bit in ("Thaler & Benartzi", "Madrian & Shea", "Hershfield", "Karlan", "Gollwitzer", "Goode & Moorhouse",
                    "What is not claimed"):
            self.assertIn(bit, doc)


class SmallStepTests(_Base):
    def test_the_small_step_is_worked_out_by_code(self):
        s = self.voice.small_step(300, [{"saved_monthly": 23.4}])
        self.assertEqual(s["monthly"], 20.0)                       # the best idea, rounded down to fives
        self.assertIsNone(s["from_idea"])
        self.assertEqual((s["yearly_total"], s["two_years"], s["ten_years_paid"]), (240.0, 480.0, 2400.0))
        self.assertGreater(s["ten_years"], s["ten_years_paid"])
        self.assertLess(s["ten_years"], s["ten_years_paid"] * 1.4)
        self.assertEqual(self.voice.small_step(0, [])["monthly"], 10.0)        # nothing to spare: €10 to start
        self.assertEqual(self.voice.small_step(400, [])["monthly"], 80.0)      # a fifth of what is left
        self.assertEqual(self.voice.small_step(5000, [{"saved_monthly": 900}])["monthly"], 200.0)   # capped

    @unittest.skipUnless(_hooked(), "app/coach.py does not use app/voice.py yet")
    def test_the_picture_carries_it_and_its_figures_pass_the_number_check(self):
        lines, data = self.coach.customer_snapshot(self.ctx())
        line = next(x for x in lines if x.startswith("Small step that fits their month"))
        step = data["small_step"]
        m = step["monthly"]
        self.assertIn("€{:,.0f} a month".format(m), line)
        say = ("Starting with €{:,.0f} a month is €{:,.0f} in a year and €{:,.0f} in two years; in an index fund "
               "it could be about €{:,.0f} after 10 years.").format(m, step["yearly_total"], step["two_years"], step["ten_years"])
        self.assertTrue(self.coach.numbers_grounded(say, [data], "How can I save more?"), say)

    @unittest.skipUnless(_hooked(), "app/coach.py does not use app/voice.py yet")
    def test_the_model_is_given_the_small_step(self):
        fake = fc.FakeClaude([fc.cl_text("Hello")])
        with fc.patched_claude(fake):
            self.coach.chat("How can I save more?", [], self.ctx())
        self.assertIn("Small step that fits their month", fake.requests[0]["system"][1]["text"]
                      if isinstance(fake.requests[0]["system"], list) and len(fake.requests[0]["system"]) > 1
                      else str(fake.requests[0]["system"]))


if __name__ == "__main__":
    unittest.main()
