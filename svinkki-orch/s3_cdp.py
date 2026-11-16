"""Minimal CDP screenshot driver (stdlib). usage: s3_cdp.py <url> <out.png> <wait_s> [extra chrome flags...]"""
import base64, json, os, socket, struct, subprocess, sys, time, urllib.request

CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"
url, out, wait = sys.argv[1], sys.argv[2], float(sys.argv[3])
extra = sys.argv[4:]
port = 9333
prof = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s3-chrome-cdp")
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--remote-debugging-port=%d" % port,
                         "--user-data-dir=" + prof, "--window-size=480,920", "--no-first-run"] + extra + ["about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/json" % port).read())
            break
        except Exception:
            time.sleep(0.2)
    page = [t for t in tabs if t["type"] == "page"][0]
    ws_url = page["webSocketDebuggerUrl"]
    host_port, path = ws_url[len("ws://"):].split("/", 1)
    h, p = host_port.split(":")
    s = socket.create_connection((h, int(p)))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall(("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, host_port, key)).encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(4096)
    rest = buf.split(b"\r\n\r\n", 1)[1]

    def send(obj):
        data = json.dumps(obj).encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        hdr += mask
        s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv_exact(n):
        global rest
        while len(rest) < n:
            rest += s.recv(1 << 16)
        d, rest = rest[:n], rest[n:]
        return d

    def recv():
        msg = b""
        while True:
            b0, b1 = recv_exact(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", recv_exact(8))[0]
            msg += recv_exact(n)
            if b0 & 0x80:
                return json.loads(msg)

    ids = [0]

    def call(method, **params):
        ids[0] += 1
        send({"id": ids[0], "method": method, "params": params})
        while True:
            m = recv()
            if m.get("id") == ids[0]:
                return m

    call("Page.enable")
    call("Page.navigate", url=url)
    time.sleep(wait)
    shot = call("Page.captureScreenshot", format="png")
    with open(out, "wb") as f:
        f.write(base64.b64decode(shot["result"]["data"]))
    print("wrote", out)
finally:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
