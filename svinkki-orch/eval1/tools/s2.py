import sys, time; from cdp import Page
p = Page()
print(p.click_text("Veeti, 32")); time.sleep(2)
print(p.text()); print(p.shot("02-welcome.png"))
print(p.js("document.body.innerHTML.length"))
