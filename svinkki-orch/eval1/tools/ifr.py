import sys, time, json, urllib.request; import cdp
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9444/json").read())
# monkeypatch: connect to iframe target
class F(cdp.Page):
    def __init__(self):
        import base64, os, socket
        t = [t for t in tabs if t["type"] == "iframe"][0]; ws = t["webSocketDebuggerUrl"]
        hp, path = ws[5:].split("/", 1); h, p = hp.split(":")
        self.s = socket.create_connection((h, int(p))); key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, hp, key)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf: buf += self.s.recv(4096)
        self.rest = buf.split(b"\r\n\r\n", 1)[1]; self.i = 0; self.call("Runtime.enable")
f = F(); top = cdp.Page()
for a in sys.argv[1:]:
    k, _, v = a.partition(":")
    if k == "clickb": print(f.click_text(v, sel="button,a,summary,[role=button]")); time.sleep(2)
    elif k == "js": print(f.js(v))
    elif k == "shot": print(top.shot(v))
    elif k == "wait": time.sleep(float(v))
    elif k == "ask":
        print(f.js("""(()=>{const i=[...document.querySelectorAll('textarea,input[type=text],input:not([type])')].filter(e=>e.offsetParent!==null)[0]; if(!i) return 'NOINPUT';
        const set=Object.getOwnPropertyDescriptor(i.__proto__,'value').set; set.call(i,%s); i.dispatchEvent(new Event('input',{bubbles:true})); i.closest('form').requestSubmit(); return 'ok'})()""" % json.dumps(v))); time.sleep(4)
