# Minimal MCP streamable-HTTP client for the local telegram-mcp server (read-only use).
# usage: python3 -I tgcall.py <tool> '<json args>'
import json, sys, urllib.request

URL = "http://127.0.0.1:8765/mcp"
HDR = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def post(body, sid=None):
    h = dict(HDR)
    if sid:
        h["mcp-session-id"] = sid
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        sid = r.headers.get("mcp-session-id") or sid
        raw = r.read().decode("utf-8", "replace")
    msgs = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            msgs.append(json.loads(line[5:].strip()))
    if not msgs and raw.strip().startswith("{"):
        msgs.append(json.loads(raw))
    return sid, msgs


sid, _ = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                          "clientInfo": {"name": "tgcall", "version": "0"}}})
post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
tool, args = sys.argv[1], json.loads(sys.argv[2] if len(sys.argv) > 2 else "{}")
_, msgs = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": args}}, sid)
for m in msgs:
    res = m.get("result") or m.get("error")
    if isinstance(res, dict) and "content" in res:
        for c in res["content"]:
            print(c.get("text", ""))
    else:
        print(json.dumps(res, ensure_ascii=False)[:4000])
