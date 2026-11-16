from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHOTS = ROOT.parent

# Product-first story: personal answers, useful widgets, and action in everyday life.
SCENES = [
    dict(id="01-hook", duration=7.0, screen=None,
         kicker="MEET SVINKKI", heading="Your money.\nYour way forward.",
         tagline="Your personal economic trainer for S-mobiili",
         voice="A bank statement shows what you did. Svinkki helps you decide what to do next.",
         accent="lime"),
    dict(id="02-personal", duration=8.8, screen="02-home-page.png",
         kicker="PERSONAL FROM THE START", heading="Hi Veeti.\nHere's your month.",
         tagline="Your money, your goals, your next step — all in one place.",
         voice="This is Veeti's coach. It already knows his month, his spending and his savings goal. Personal from the very first screen.",
         accent="mint", yaw=-0.13, pitch=0.035, roll=-0.016, crop=(0.40, 0.72, 0.51, 0.26)),
    dict(id="03-ask", duration=6.8, screen="05-ask-chart-first-answer.png",
         kicker="JUST ASK", heading="Talk with\nyour own money.",
         tagline="A clear picture. An answer that makes sense to you.",
         voice="No menus to learn. Just ask. Svinkki turns taxi spending into a picture and one clear answer.",
         accent="lime", yaw=0.13, pitch=-0.025, roll=0.018, crop=(0.77, 0.42, 0.64, 0.29)),
    dict(id="04-proof", duration=7.0, screen="06-proof-ai-wrote-sentence-not-number.png",
         kicker="ANSWERS YOU CAN CHECK", heading="Not a guess.\nYour two taxi rides.",
         tagline="Tap a figure to trace it back to your transactions.",
         voice="The answer is grounded in Veeti's own transactions, down to the two taxi rides. Personal, and verifiable.",
         accent="mint", yaw=-0.08, pitch=0.02, roll=0.01, crop=(0.51, 0.48, 0.55, 0.56)),
    dict(id="05-afford", duration=8.3, screen="07-can-i-afford-it.png",
         kicker="HELP IN THE MOMENT", heading="Can I afford it?\nA straight answer.",
         tagline="Guidance that fits Veeti's payday and upcoming bills.",
         voice="Before Veeti buys a jacket, Svinkki puts it in context. Yes, it fits, with about thirty-five euros a day left until payday.",
         accent="lime", yaw=0.15, pitch=-0.02, roll=-0.014, crop=(0.57, 0.40, 0.62, 0.48)),
    dict(id="06-plan", duration=8.5, screen="09-plan-slider-where-money-comes-from.png",
         kicker="A PLAN MADE FOR YOU", heading="Japan.\nOne month at a time.",
         tagline="Your goal. A monthly amount. A way to get there.",
         voice="Veeti wants to visit Japan. Svinkki builds a plan from his goal, with concrete changes from his own spending to fund it.",
         accent="mint", yaw=-0.12, pitch=0.035, roll=0.018, crop=(0.57, 0.31, 0.63, 0.31)),
    dict(id="07-widget", duration=9.4, screen="03-home-savings-plan-and-suggestions.png",
         kicker="WIDGETS FROM YOUR CONVERSATION", heading="Your plan stays.\nKeep moving forward.",
         tagline="Progress, a projection, and your next step — at a glance.",
         voice="Save that plan as a home-page widget. Progress, a monthly amount and a projection, always one glance away. A conversation that becomes part of your day.",
         accent="lime", yaw=0.12, pitch=0.02, roll=-0.014, crop=(0.66, 0.30, 0.74, 0.23)),
    dict(id="08-proactive", duration=8.4, screen="18-svinkki-suggests-joonas.png",
         kicker="PERSONAL. PROACTIVE.", heading="No finance degree.\nJust your next step.",
         tagline="Proposals based on the customer's actual habits.",
         voice="For Joonas, the suggestions are different: build a buffer, set aside his leftover, cook at home. Coaching that adapts to the person.",
         accent="mint", yaw=-0.15, pitch=0.025, roll=-0.018, crop=(0.39, 0.62, 0.58, 0.34)),
    dict(id="09-honest", duration=7.0, screen="10-plan-added-to-home-page.png",
         kicker="AN HONEST COACH", heading="A plan that fits.\nNot empty optimism.",
         tagline="Personal guidance, even when the goal needs adjusting.",
         voice="If Japan by June is too ambitious, Svinkki says so, then offers Veeti a more realistic path.",
         accent="lime", yaw=0.13, pitch=-0.015, roll=0.013, crop=(0.47, 0.58, 0.54, 0.43)),
    dict(id="10-act", duration=8.0, screen="11-approve-money-move.png",
         kicker="FROM ADVICE TO ACTION", heading="One tap.\nYou're in control.",
         tagline="Approve the exact move, only when it feels right.",
         voice="A good intention becomes action in one tap. Veeti approves every move himself. The coach advises; the customer decides.",
         accent="lime", yaw=-0.15, pitch=0.018, roll=0.014, crop=(0.56, 0.40, 0.60, 0.38)),
    dict(id="11-finnish", duration=7.4, screen="20-finnish-answer.png",
         kicker="PERSONAL IN YOUR LANGUAGE", heading="My money.\nMinun rahani.",
         tagline="Natural financial coaching in English and Finnish.",
         voice="Mihin mun rahat menee? Personal coaching in English and Finnish, in the way you want to talk.",
         accent="mint", yaw=0.10, pitch=-0.025, roll=-0.014, crop=(0.63, 0.38, 0.63, 0.29)),
    dict(id="12-features", duration=9.0, screen=None,
         kicker="COACHING THAT KEEPS HELPING", heading="Small steps.\nBetter money habits.",
         tagline="Made for everyday financial wellbeing.",
         voice="Save money, test a what-if, or learn with a personal quiz. Svinkki turns your everyday decisions into better money habits.",
         accent="lime"),
    dict(id="13-close", duration=11.5, screen=None,
         kicker="S-PANKKI × JUNCTION 2026", heading="Advice that\nbecomes action.",
         tagline="Svinkki. Your money. Your plan. Your next step.",
         voice="A coach that knows your money, speaks your language, and turns personal insight into action. Svinkki. Your money. Your plan. Your next step.",
         accent="lime"),
]

total = 0.0
for _scene in SCENES:
    _scene["start"] = total
    total += _scene["duration"]
TOTAL = total


def print_story():
    for scene in SCENES:
        print(f"{scene['start']:5.1f}–{scene['start']+scene['duration']:5.1f}  {scene['id']}: {scene['voice']}")
    assert TOTAL <= 120
    print(f"Total: {TOTAL:.1f}s")


if __name__ == "__main__":
    print_story()
