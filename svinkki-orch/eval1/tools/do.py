# usage: do.py cmd arg ... ; cmds: click:TEXT  clickx:TEXT  js:EXPR  shot:NAME  full:NAME  text  wait:S  ask:Q  url  back  go:URL
import sys, time, json; from cdp import Page
p = Page()
for a in sys.argv[1:]:
    k, _, v = a.partition(":")
    if k == "click": print(p.click_text(v)); time.sleep(1.5)
    elif k == "clickx": print(p.click_text(v, exact=True)); time.sleep(1.5)
    elif k == "clickb": print(p.click_text(v, sel="button,a,summary,[role=button]")); time.sleep(1.5)
    elif k == "js": print(p.js(v))
    elif k == "shot": print(p.shot(v))
    elif k == "full": print(p.shot(v, full=True))
    elif k == "text": print(p.text())
    elif k == "wait": time.sleep(float(v))
    elif k == "url": print(p.js("location.href"))
    elif k == "back": p.js("history.back()"); time.sleep(1.5)
    elif k == "go": p.go(v, 3)
    elif k == "ask":
        r = p.js("""(()=>{const i=[...document.querySelectorAll('textarea,input[type=text],input:not([type])')].filter(e=>e.offsetParent!==null)[0]; if(!i) return 'NOINPUT';
        const set=Object.getOwnPropertyDescriptor(i.__proto__,'value').set; set.call(i,%s); i.dispatchEvent(new Event('input',{bubbles:true}));
        const f=i.closest('form'); if(f){f.requestSubmit(); return 'submitted';} i.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); return 'enter'})()""" % json.dumps(v))
        print(r); time.sleep(4)
