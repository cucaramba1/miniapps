# Collect Telegram bot / mini-app mentions around Nha Trang from the user's own chats via local telegram-mcp.
import json, re, subprocess, sys, time, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
QUERIES = ["startapp", "мини-приложение", "mini app", "приложение Нячанг", "бот аренда Нячанг",
           "бот Нячанг", "бот обмен Нячанг", "бот байк Нячанг", "бот экскурсии Нячанг", "бот доставка Нячанг",
           "nha trang bot", "бот визаран", "гид по Нячангу бот", "карта Нячанга бот", "бот жильё"]
BOT = re.compile(r"(?:@|t\.me/)([A-Za-z0-9_]{4,40}?bot)\b", re.I)
APP = re.compile(r"t\.me/([A-Za-z0-9_]{4,40})/?([A-Za-z0-9_]*)\?startapp", re.I)
hits = collections.defaultdict(lambda: {"n": 0, "chats": set(), "sample": ""})

def call(q, page):
    out = subprocess.run([sys.executable, "-I", os.path.join(HERE, "tgcall.py"), "search_global",
                          json.dumps({"query": q, "page": page, "page_size": 50})], capture_output=True, text=True, timeout=90).stdout
    try:
        return json.loads(out).get("results", [])
    except Exception:
        return []

for q in QUERIES:
    for page in (1, 2):
        rs = call(q, page)
        for r in rs:
            txt = r.get("text") or ""
            names = {m.lower() for m in BOT.findall(txt)} | {m[0].lower() for m in APP.findall(txt)}
            snd = re.search(r"@([A-Za-z0-9_]+bot)\b", r.get("sender") or "", re.I)
            if snd: names.add(snd.group(1).lower())
            for n in names:
                h = hits[n]; h["n"] += 1; h["chats"].add(r.get("chat_name", "")[:40])
                if not h["sample"]: h["sample"] = txt[:220].replace("\n", " ")
        if len(rs) < 50: break
        time.sleep(1.5)
    time.sleep(1.5)

rows = sorted(hits.items(), key=lambda kv: -kv[1]["n"])
for name, h in rows[:60]:
    print(f"{h['n']:3} @{name} | {'; '.join(sorted(h['chats']))[:90]} | {h['sample'][:200]}")
