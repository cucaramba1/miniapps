# Full announcement text + bot profile for selected bots (read-only).
import json, subprocess, sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
BOTS = {"lotusprop108_bot": "Lotus Property", "mota_mota_app_bot": "MOTA MOTA", "motikbot": "Мотик",
        "vietgo_bot": "VietGo", "rent_open_aggregator_bot": "rent_open_aggregator", "nha_trang_bot": "nha_trang_bot",
        "vietchangebot": "vietchangebot", "visarunvnbot": "visarunvnbot", "your_connectly_bot": "Connectly"}

def call(tool, args):
    out = subprocess.run([sys.executable, "-I", os.path.join(HERE, "tgcall.py"), tool, json.dumps(args)],
                         capture_output=True, text=True, timeout=90).stdout
    return out

for b, name in BOTS.items():
    print("=" * 8, name, "@" + b)
    prof = call("get_full_user", {"username": b})
    try:
        d = json.loads(prof)
        keep = {k: d.get(k) for k in ("first_name", "username", "about", "bot_info_description", "bot_description", "bot_active_users", "description") if d.get(k)}
        print("PROFILE:", json.dumps(keep, ensure_ascii=False)[:700])
    except Exception:
        print("PROFILE RAW:", prof[:500])
    raw = call("search_global", {"query": b, "page_size": 10})
    try: rs = json.loads(raw).get("results", [])
    except Exception: print("SEARCH RAW:", raw[:300]); rs = []
    seen = set()
    for r in rs:
        t = (r.get("text") or "").strip()
        if len(t) < 120 or t[:80] in seen:
            continue
        seen.add(t[:80])
        print("POST", r.get("date", "")[:10], "|", r.get("chat_name", "")[:40])
        print(t[:1500])
        if len(seen) >= 2:
            break
    time.sleep(1.5)
