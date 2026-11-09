"""Собирает папку для публикации артефакта-хаба из файлов проекта.
usage: python3 -I tools/build_bundle.py <папка_вывода>
Результат: <out>/hub.html, <out>/plan.html, <out>/nhatrang, <out>/reels-radar, <out>/shots.
Из страниц убирается скрипт telegram-web-app.js (артефакт блокирует чужие скрипты, прототипы работают и без него),
ds.css и tgx.js кладутся рядом с каждым приложением (пути '../shared' в артефакте не работают).
Публикация: Artifact с file_path=<out>/hub.html, root=<out>, url=https://claude.ai/artifact/AGj2i1WjaDdgiycW2HwdEo,
files = список файлов из <out> (см. HANDOFF каждого проекта)."""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.abspath(sys.argv[1])
if os.path.exists(out):
    shutil.rmtree(out)
os.makedirs(os.path.join(out, "shots"))

for app in ("nhatrang", "reels-radar"):
    os.makedirs(os.path.join(out, app))
    s = open(os.path.join(ROOT, app, "index.html"), encoding="utf-8").read()
    s = s.replace('<script src="https://telegram.org/js/telegram-web-app.js"></script>\n', "")
    s = s.replace("../shared/ds.css", "ds.css").replace("../shared/tgx.js", "tgx.js")
    open(os.path.join(out, app, "index.html"), "w", encoding="utf-8").write(s)
    for f in ("ds.css", "tgx.js"):
        shutil.copy(os.path.join(ROOT, "shared", f), os.path.join(out, app, f))

for f in ("hub.html", "plan.html"):
    shutil.copy(os.path.join(ROOT, "docs", f), os.path.join(out, f))

shots = os.path.join(ROOT, "docs", "shots")
pairs = [("nhatrang/light", "nt-", ["home", "detail", "guide", "paywall", "pay"]),
         ("nhatrang/dark", "nt-", ["guide"]),
         ("reels-radar/light", "rr-", ["trends", "trend", "adapt", "inbox", "search"])]
for sub, prefix, names in pairs:
    for n in names:
        suffix = "-dark" if sub.endswith("dark") else ""
        shutil.copy(os.path.join(shots, sub, n + ".png"), os.path.join(out, "shots", prefix + n + suffix + ".png"))

files = []
for dp, _, fn in os.walk(out):
    for f in fn:
        files.append(os.path.relpath(os.path.join(dp, f), out))
print("\n".join(sorted(files)))
print(len(files), "files")
