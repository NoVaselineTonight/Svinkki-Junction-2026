import sys, time, json; from cdp import Page
p = Page()
qs = json.load(open(sys.argv[1], encoding="utf-8")); prefix = sys.argv[2]
for n, q in enumerate(qs):
    p.js("[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='New')?.click()"); time.sleep(1.2)
    p.js("""(()=>{const i=[...document.querySelectorAll('textarea,input[type=text],input:not([type])')].filter(e=>e.offsetParent!==null)[0];
        const set=Object.getOwnPropertyDescriptor(i.__proto__,'value').set; set.call(i,%s); i.dispatchEvent(new Event('input',{bubbles:true})); i.closest('form').requestSubmit();})()""" % json.dumps(q))
    time.sleep(4)
    t = p.text(); idx = t.rfind(q)
    print("=== Q%d: %s" % (n+1, q)); print(t[idx+len(q):].strip()); 
    print(p.shot("%s-%02d.png" % (prefix, n+1)))
