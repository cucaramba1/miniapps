"""Одноразовый съём рилсов одного профиля через залогиненный data/pw-profile бота (только чтение)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

USER = sys.argv[1]
PROFILE = Path(sys.argv[2])
OUT = Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)

caught = []
def on(r):
    try:
        if "graphql" in r.url or "/api/v1/" in r.url:
            t = r.text()
            if '"play_count"' in t or '"taken_at"' in t:
                caught.append(json.loads(t))
    except Exception:
        pass

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(str(PROFILE), headless=True, viewport={"width": 1280, "height": 1400})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", on)
    for path in ("", "reels/"):
        resp = page.goto(f"https://www.instagram.com/{USER}/{path}", wait_until="domcontentloaded", timeout=30000)
        print("goto", path, resp.status if resp else None, page.url, flush=True)
        if "/accounts/login" in page.url or "/challenge" in page.url:
            print("LOGIN REQUIRED"); break
        page.wait_for_timeout(6000)
        last = -1
        for i in range(15):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(3500)
            if len(caught) == last:
                break
            last = len(caught)
        page.screenshot(path=str(OUT / f"page_{path.strip('/') or 'main'}.png"))
    ctx.close()

(OUT / "raw.json").write_text(json.dumps(caught, ensure_ascii=False))
print("responses", len(caught))
