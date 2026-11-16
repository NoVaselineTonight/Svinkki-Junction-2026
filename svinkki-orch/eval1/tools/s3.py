import sys, time; from cdp import Page
p = Page()
print(p.click_text("Your choices")); time.sleep(1)
print(p.text()); print(p.shot("03-choices.png", full=True))
print(p.click_text("Start", sel="button", exact=True)); time.sleep(3)
print("-----"); print(p.text()); print(p.shot("04-front.png"))
