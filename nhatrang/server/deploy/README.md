# Развёртывание Нячанг Дом (VPS до $10-15/мес)

Шаги, где нужен Некит, помечены **[Некит]**. Я цены VPS и условия провайдеров не проверял.

1. **[Некит]** VPS (Ubuntu 22.04/24.04, 1 ГБ RAM хватает) + домен, A-запись на VPS. Дать мне SSH.
2. **[Некит]** @BotFather: создать бота, получить токен; `/setdomain` = домен; кнопка Web App (`/setmenubutton` или Main Mini App) на `https://YOUR_DOMAIN/`; `/setcommands`: `start`, `paysupport`.
3. Пакеты: `apt install caddy sqlite3 rsync`; пользователь `nhatrang`; код в `/opt/nhatrang/server`, фронт: `index.html`+`js/` в `/opt/nhatrang/web`, `ds.css`+`tgx.js` в `/opt/nhatrang/shared`.
4. `cd /opt/nhatrang/server && uv sync --python 3.12` (или `python3.12 -m venv .venv && .venv/bin/pip install .`).
5. `.env` из `env.example` (права 600). `APP_ENV=prod` отказывается стартовать с `DEV_AUTH` и с тестовыми секретами.
6. `cp nhatrang.service /etc/systemd/system/ && systemctl enable --now nhatrang`; `Caddyfile` в `/etc/caddy/Caddyfile`, `systemctl reload caddy`.
7. Webhook:
   `curl -s "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" -d url=https://YOUR_DOMAIN/api/bot/webhook -d secret_token=$WEBHOOK_SECRET -d 'allowed_updates=["message","callback_query","pre_checkout_query"]'`
8. Данные: `python -m tools.osm_import load data/overpass.json`; `python -m tools.import_listings <listings.json>`; районы: **[Некит]** `data/districts_ru.json` (формат ниже) и загрузка в таблицу `districts`; CSV риелторов и сигналов заполняет Некит (`python -m tools.import_csv realtors|signals file.csv`).
9. Бэкап: `crontab -e` -> `20 3 * * * /opt/nhatrang/server/deploy/backup.sh`. Раз в неделю **[Некит]** скачивает свежий `app-*.db.gz`.
10. Проверка на боевом боте: свой платёж на минимальный тариф, `/refund <charge_id>`, свой отзыв с телефона с геометкой, `/queue`.

## Чек-лист «не проверено до запуска»
- Реальный платёж Stars и возврат (методы Telegram API написаны по памяти, сверить с `core.telegram.org/bots/payments-stars`).
- Курс и вывод Stars.
- Камера-онли и геолокация на iOS и Android (Task 1, спайк на телефоне Некита).
- Условия провайдера тайлов (OSM напрямую для боевого трафика нельзя).
- Нагрузка на VPS (k6/locust на `/api/places`).
- Подписи Leaflet с cdnjs без SRI-хэшей; при желании вынести Leaflet на свой домен.

## Формат districts_ru.json (предлагаемый)
`[{"name_ru": "Название", "geometry": {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}}]`. Загрузка: `python -m tools.load_districts data/districts_ru.json`. Пока таблица `districts` пуста, `/api/districts` отдаёт пустой список и фронт просто не показывает районы.
