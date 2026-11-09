#!/bin/bash
# Выкатка «Нячанг Дом» на Ubuntu 24.04 с ноута. Идемпотентно: можно гонять повторно (обновит код, не тронет БД и фото).
#
# Запуск:  deploy/deploy.sh <домен> [--go]
#   без --go только печатает, что собирается сделать (ничего не меняет на сервере)
# Домен: свой, либо временный вида <IP-через-дефисы>.sslip.io (резолвится в IP, сертификат Let's Encrypt выпустит Caddy).
# Переменные: SSH_KEY (путь к ключу) и SSH_HOST (user@адрес сервера). Личные значения лежат в deploy.env рядом со скриптом
# (он в .gitignore, образец в deploy.env.example).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
[ -f "$HERE/deploy.env" ] && . "$HERE/deploy.env"
DOMAIN="${1:?укажи домен: deploy.sh <домен> [--go]}"
GO="${2:-}"
SSH_KEY="${SSH_KEY:?задай SSH_KEY (путь к ключу) в deploy.env или в окружении}"
SSH_HOST="${SSH_HOST:?задай SSH_HOST (user@адрес) в deploy.env или в окружении}"
SRV="$(cd "$HERE/.." && pwd)"            # nhatrang/server
APP="$(cd "$SRV/.." && pwd)"             # nhatrang
SHARED="$(cd "$APP/../shared" && pwd)"   # miniapps/shared
SSH=(ssh -i "$SSH_KEY" -o BatchMode=yes "$SSH_HOST")
RSYNC=(rsync -az -e "ssh -i $SSH_KEY -o BatchMode=yes")

echo "Сервер: $SSH_HOST  Домен: $DOMAIN"
echo "Что будет сделано:"
echo "  1. apt: caddy sqlite3 rsync python3-venv; пользователь nhatrang; каталоги /opt/nhatrang/{server,web,shared,data}"
echo "  2. rsync: server/ (без .venv, data, tests, .env), index.html + js/ + tiles/, shared/{ds.css,tgx.js}"
echo "  3. .env из локального server/.env с APP_ENV=prod, WEBAPP_URL=https://$DOMAIN/ (права 600)"
echo "  4. venv + pip install, systemd-юнит nhatrang (один воркер, MemoryMax 400M), Caddy на $DOMAIN"
echo "  5. ufw: открыть 80 и 443 (сейчас открыт только SSH)"
echo "  6. webhook бота на https://$DOMAIN/api/bot/webhook"
[ "$GO" = "--go" ] || { echo; echo "Сухой прогон. Для запуска добавь --go"; exit 0; }

[ -f "$SRV/.env" ] || { echo "нет $SRV/.env"; exit 1; }
umask 077
ENVTMP="$(mktemp)"; trap 'rm -f "$ENVTMP"' EXIT
grep -Ev '^(APP_ENV|DEV_AUTH|DB_PATH|PHOTOS_DIR|WEB_DIR|SHARED_DIR|WEBAPP_URL)=' "$SRV/.env" > "$ENVTMP"
cat >> "$ENVTMP" <<EOF
APP_ENV=prod
DB_PATH=/opt/nhatrang/data/app.db
PHOTOS_DIR=/opt/nhatrang/data/photos
WEB_DIR=/opt/nhatrang/web
SHARED_DIR=/opt/nhatrang/shared
WEBAPP_URL=https://$DOMAIN/
EOF

"${SSH[@]}" 'sudo apt-get install -y -qq caddy sqlite3 rsync python3-venv >/dev/null \
  && (id nhatrang >/dev/null 2>&1 || sudo useradd --system --home /opt/nhatrang --shell /usr/sbin/nologin nhatrang) \
  && sudo mkdir -p /opt/nhatrang/{server,web,shared,data,seed} && sudo chown -R nikit:nikit /opt/nhatrang/{server,web,shared,seed}'

"${RSYNC[@]}" --delete --exclude .venv --exclude data --exclude tests --exclude __pycache__ --exclude .env --exclude .pytest_cache \
  "$SRV/" "$SSH_HOST:/opt/nhatrang/server/"
"${RSYNC[@]}" --delete "$APP/index.html" "$APP/js" "$APP/tiles" "$SSH_HOST:/opt/nhatrang/web/"
"${RSYNC[@]}" "$SHARED/ds.css" "$SHARED/tgx.js" "$SSH_HOST:/opt/nhatrang/shared/"
"${RSYNC[@]}" "$SRV/data/overpass.json" "$SRV/data/districts_ru.json" "$SSH_HOST:/opt/nhatrang/seed/"
scp -i "$SSH_KEY" -q "$ENVTMP" "$SSH_HOST:/tmp/nhatrang.env"

"${SSH[@]}" "DOMAIN='$DOMAIN' bash -s" <<'REMOTE'
set -euo pipefail
sudo install -m 600 -o nhatrang -g nhatrang /tmp/nhatrang.env /opt/nhatrang/.env && rm -f /tmp/nhatrang.env
sudo chown -R nhatrang:nhatrang /opt/nhatrang/data
cd /opt/nhatrang/server
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/python -c "import tomllib;print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/nd-req.txt
.venv/bin/pip install -q -r /tmp/nd-req.txt
sudo install -m 644 deploy/nhatrang.service /etc/systemd/system/nhatrang.service
printf '%s {\n    encode gzip\n    reverse_proxy 127.0.0.1:8000\n    request_body {\n        max_size 40MB\n    }\n}\n' "$DOMAIN" | sudo tee /etc/caddy/Caddyfile >/dev/null
# первичная загрузка данных, только если таблица мест пуста
sudo -u nhatrang env $(sudo grep -E '^(DB_PATH|PHOTOS_DIR)=' /opt/nhatrang/.env | xargs) .venv/bin/python - <<'PY'
import os, sqlite3, subprocess, sys
from app.db import connect, migrate
c = connect(os.environ["DB_PATH"]); migrate(c)
if c.execute("select count(*) from places").fetchone()[0] == 0:
    subprocess.run([sys.executable, "-m", "tools.osm_import", "load", "/opt/nhatrang/seed/overpass.json"], check=True)
    subprocess.run([sys.executable, "-m", "tools.load_districts", "/opt/nhatrang/seed/districts_ru.json"], check=True)
    print("данные загружены")
else:
    print("места уже есть, данные не трогаю")
PY
sudo systemctl daemon-reload
sudo systemctl enable --now nhatrang
sudo systemctl restart nhatrang
sudo systemctl reload-or-restart caddy
sudo ufw allow 80/tcp >/dev/null; sudo ufw allow 443/tcp >/dev/null
sleep 3; systemctl is-active nhatrang
REMOTE

# webhook: токен берём из локального .env, в вывод не печатаем
set -a; . "$SRV/.env"; set +a
curl -fsS "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
  -d "url=https://$DOMAIN/api/bot/webhook" -d "secret_token=$WEBHOOK_SECRET" \
  -d 'allowed_updates=["message","callback_query","pre_checkout_query"]'
echo; echo "Проверка:  curl -s https://$DOMAIN/api/config | head -c 200"
