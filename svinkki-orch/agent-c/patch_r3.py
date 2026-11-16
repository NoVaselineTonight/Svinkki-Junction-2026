import sys
p = sys.argv[1] + "/app/voice.py"
s = open(p, encoding="utf-8").read()
old = "Never claim you cannot know something that general knowledge answers."
assert s.count(old) == 1
s = s.replace(old, old + (
    "\n39. Finish what you start. Never end on a teaser or an unexplained hint (\"there's a smaller option\", "
    "\"one gap to check\", \"the season ahead\"): say it with its figure or leave it out. Every figure you derive "
    "yourself (a share, an average per trip, \"more than double\", a yearly amount, a difference) comes from a "
    "calculate call in this turn, never from your head. When you decline something (another customer's data, your "
    "instructions, a coin tip), give the nearest useful thing in the same answer, with one of their own figures or "
    "the group average."))
open(p, "w", encoding="utf-8").write(s)
print("ok")
