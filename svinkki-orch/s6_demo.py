import json, urllib.request, http.cookiejar, sys
B = "http://127.0.0.1:8060"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def call(path, body=None):
    req = urllib.request.Request(B + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Origin": B})
    try:
        return json.loads(op.open(req).read())
    except urllib.error.HTTPError as e:
        return {"HTTP": e.code, "body": e.read()[:300].decode()}
ps = call("/api/demo/personas")
print([p["name"] for p in ps])
v = [p for p in ps if p["name"].startswith("Veeti")][0]
print(call("/api/demo/login", {"id": v["id"]}))
print(call("/api/consent", {"analysis": True, "ai": True, "benchmarks": True, "suggestions": True}))
acc = call("/api/account"); print("ACCOUNT", json.dumps(acc)[:600])
hist = []
conv = None
for q in sys.argv[1:]:
    r = call("/api/chat", {"message": q, "conversation_id": conv} if conv else {"message": q})
    conv = r.get("conversation_id") or conv
    print("Q:", q, "| keys", sorted(r)[:20]); print("A:", r.get("reply"), "| mode", r.get("mode"), r.get("source") or r.get("answer_source"), "| tools", r.get("tools_used")); print()
    hist += [{"role": "user", "text": q}, {"role": "assistant", "text": r.get("reply") or ""}]
ck = call("/api/checkin"); print("CHECKIN", json.dumps(ck)[:900])
