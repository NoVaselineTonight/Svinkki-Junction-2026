import base64, json, os, socket, struct, time, urllib.request
OUT = "C:/Users/onnik/Desktop/svinkki-orch/eval1/"
class Page:
    def __init__(self, port=9444, idx=0):
        tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/json" % port).read())
        page = [t for t in tabs if t["type"] == "page"][idx]
        ws = page["webSocketDebuggerUrl"]
        hp, path = ws[5:].split("/", 1); h, p = hp.split(":")
        self.s = socket.create_connection((h, int(p)))
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, hp, key)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf: buf += self.s.recv(4096)
        self.rest = buf.split(b"\r\n\r\n", 1)[1]; self.i = 0
        self.call("Page.enable"); self.call("Runtime.enable")
        self.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
    def _send(self, obj):
        data = json.dumps(obj).encode(); hdr = bytearray([0x81]); n = len(data)
        if n < 126: hdr.append(0x80 | n)
        elif n < 65536: hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
        else: hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
        m = os.urandom(4); hdr += m
        self.s.sendall(bytes(hdr) + bytes(b ^ m[i % 4] for i, b in enumerate(data)))
    def _rx(self, n):
        while len(self.rest) < n: self.rest += self.s.recv(1 << 16)
        d, self.rest = self.rest[:n], self.rest[n:]; return d
    def _recv(self):
        msg = b""
        while True:
            b0, b1 = self._rx(2); n = b1 & 0x7F
            if n == 126: n = struct.unpack(">H", self._rx(2))[0]
            elif n == 127: n = struct.unpack(">Q", self._rx(8))[0]
            msg += self._rx(n)
            if b0 & 0x80: return json.loads(msg)
    def call(self, method, **params):
        self.i += 1; self._send({"id": self.i, "method": method, "params": params})
        while True:
            m = self._recv()
            if m.get("id") == self.i: return m
    def js(self, expr):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        res = r.get("result", {})
        if "exceptionDetails" in res: return "JSERR: " + json.dumps(res["exceptionDetails"])[:400]
        return res.get("result", {}).get("value")
    def go(self, url, wait=2):
        self.call("Page.navigate", url=url); time.sleep(wait)
    def shot(self, name, full=False):
        kw = {"format": "png"}
        if full: kw["captureBeyondViewport"] = True
        d = self.call("Page.captureScreenshot", **kw)["result"]["data"]
        open(OUT + name, "wb").write(base64.b64decode(d)); return OUT + name
    def text(self):
        return self.js("document.body.innerText")
    def click_text(self, t, sel="button,a,[role=button],summary,li,div,span", exact=False):
        expr = """(()=>{const t=%s, ex=%s; const els=[...document.querySelectorAll(%s)].filter(e=>e.offsetParent!==null||e.getClientRects().length);
        let c=els.filter(e=>ex? e.innerText.trim()===t : e.innerText.trim().includes(t));
        c.sort((a,b)=>a.innerText.length-b.innerText.length); if(!c.length) return 'NOTFOUND';
        c[0].scrollIntoView({block:'center'}); c[0].click(); return 'clicked:'+c[0].tagName+':'+c[0].innerText.trim().slice(0,60)})()""" % (json.dumps(t), "true" if exact else "false", json.dumps(sel))
        return self.js(expr)
