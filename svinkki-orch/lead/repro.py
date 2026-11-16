import json, sys, urllib.request, http.cookiejar
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8070"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def call(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Origin": BASE})
    try:
        return json.loads(op.open(req, timeout=200).read() or b"null")
    except urllib.error.HTTPError as e:
        return {"HTTP": e.code, "body": e.read().decode()[:300]}
ps = call("/api/demo/personas")
veeti = next(p for p in (ps if isinstance(ps, list) else ps.get("personas", [])) if "Veeti" in json.dumps(p))
print(call("/api/demo/login", {"id": veeti.get("id") or veeti.get("token")}))
print(call("/api/consent", {"analysis": True, "ai": True, "benchmarks": True, "suggestions": True}))
qs = [l.strip() for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
for q in qs:
    r = call("/api/chat", {"message": q})
    cards = [c.get("type") for c in (r.get("cards") or [])] if isinstance(r, dict) else None
    print("Q:", q); print("A:", (r.get("reply") if isinstance(r, dict) else r)); print("   mode=%s notice=%s cards=%s" % (r.get("mode"), r.get("notice"), cards)); print()
acc = call("/api/account"); print("ACCOUNT:", json.dumps(acc)[:600])
