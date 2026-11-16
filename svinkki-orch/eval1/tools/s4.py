import sys, time; from cdp import Page
p = Page()
print(p.click_text("S-Bank current account")); time.sleep(2)
print(p.text()); print(p.shot("05-account.png")); print(p.shot("05-account-full.png", full=True))
print(p.js("location.href"))
