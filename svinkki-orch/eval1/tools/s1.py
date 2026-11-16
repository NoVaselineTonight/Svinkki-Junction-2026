import sys, time; from cdp import Page
p = Page(); p.go("http://127.0.0.1:8090/", 3)
print(p.text()); print(p.shot("01-login.png"))
