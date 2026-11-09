# Нячанг Дом v2: план первой версии

> **Для агента-исполнителя:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (рекомендуется) или superpowers:executing-plans. Шаги с чекбоксами `- [ ]`.

**Цель:** запустить Telegram mini-app «правда о жилье до заезда»: карта мест с отзывами жильцов, платный доступ за Stars, раздел «Свободно сейчас», справочник риелторов, модерация через бота.

**Архитектура:** один процесс FastAPI + SQLite (WAL) на дешёвом VPS. Он отдаёт и API, и статику фронта (один origin, без CORS), принимает webhook бота (платежи Stars, команды Некита). Фронт остаётся на ванильном JS поверх `../shared/tgx.js` и `../shared/ds.css`. Платный контент и контакты отдаёт только сервер после проверки `initData` и срока доступа.

**Стек:** Python 3.12 (через `uv`, системный 3.9 не годится), FastAPI, httpx, Pillow, python-multipart, pytest; фронт: ванильный JS, Leaflet 1.9.4 (cdnjs); тесты UI: существующий Playwright в `../tests/`.

**Спека:** `../../../DESIGN.md` (все разделы). Контекст: `PLAN.md`, `COMPETITORS.md`, `HANDOFF.md` в `nhatrang/`.

**Вне этого плана (отдельный план B, писать после чтения кода `~/Claude Code/tg-harvester`):** автоматические сигналы из Telegram-чатов (фильтр + `claude -p` ночью, лимиты по `~/Claude Code/CLAUDE.md`). Я не читал интерфейсы `tg-harvester`, поэтому планировать их вслепую нельзя. Без плана B 300+ мест получаются из OpenStreetMap (карточки с индексом удобства), а сигналы и отзывы на старте идут вручную и от жильцов. Также вне плана: ИИ-предмодерация, веб-версия, тест цены на 20 покупках.

## Global Constraints

Значения из спеки дословно. Все задачи ими связаны.
- Порог текста отзыва: 150 символов (конфиг, диапазон спеки 150-200). Радиус геометки: 150 м (конфиг, диапазон 100-150). Фото: минимум 2, максимум 5 (моё решение).
- Лимиты: 1 отзыв в день на человека; 1 отзыв на пару «человек + место» за 14 дней; считается по Telegram ID, не по устройству.
- Награда: 1 подтверждённый отзыв = 3 дня платного доступа.
- Тарифы только 3 дня и 7 дней, подписки нет: 3 дня = 300 Stars (₽590), 7 дней = 600 Stars (₽1 190). Цены в конфиге, это гипотезы.
- Оплата только Stars (валюта `XTR`). Карта и Bybit в первую версию не входят. Обязательны `/paysupport` и возврат.
- Бесплатно: фото, цена, базовые условия, общая оценка, число жалоб по типам, индекс удобства, разделы «Проверить жильё» и «Свободно сейчас» без контактов. Платно: тексты и фото отзывов, даты, сигналы со ссылками, список бытовухи с заметками, контакты риелторов (и в справочнике, и в объявлениях).
- Нет платного поднятия в выдаче: порядок только по подтверждённым отзывам. Коммерческие места помечаются явно.
- Сигналы с Booking, Agoda, Trip.com, TopHotels, Tripadvisor и Google вносятся вручную или полуавтоматически с подтверждением Некита, парсер не пишем. Чужие тексты отзывов не храним, только сигналы со ссылкой.
- Метка «без комиссии» у риелтора ставится только после ручного подтверждения Некитом (по умолчанию выключена).
- Рассылку сообщений риелторам и хозяевам не автоматизируем.
- Интерфейс на русском. В текстах для людей нет длинного тире (в тестах проверяется).
- Бюджет сервера до $10-15 в месяц, без платных API на старте.
- На ноуте (8 ГБ RAM): тесты Playwright и стресс запускать по одному, не параллельно; `node e2e.mjs` около 12 минут.
- Районы и их русские названия утверждает Некит, список не выдумывать.

## Review Focus

Что спека подразумевает, но задачи иначе не проверят. Тест на каждый пункт добавлен в указанную задачу.
1. **Утечка платного контента.** Без доступа ни в одном ответе (`/places`, `/places/{id}`, `/listings`, `/realtors`, фото) нет текстов отзывов, контактов, ссылок на фото жильцов; фото без подписи или с чужой/просроченной подписью не отдаются (Task 7, 11).
2. **Подделка и повтор.** Просроченный или подправленный `initData` даёт 401; `user_id` берётся только из подписанных данных, не из тела запроса; режим `dev_auth` в боевом конфиге выключен (Task 3).
3. **Повторная доставка webhook Stars.** Telegram может прислать `successful_payment` дважды: доступ выдаётся один раз (Task 10).
4. **Граница геометки и гонка лимита.** 150 м ровно проходит, 150.1 нет; координаты 0,0 отвергаются; два одновременных отзыва одного человека дают один (Task 8).
5. **Грязный ввод.** Название места с `<script>`, отзыв на 3000 символов с эмодзи, вьетнамские диакритики в поиске («vinh hai» находит «Vĩnh Hải»), не-картинка вместо фото (SVG, PDF) (Task 5, 8, 16).

---

## Структура файлов

```
nhatrang/server/
  pyproject.toml                  # зависимости, requires-python >=3.12
  app/
    config.py                     # Settings, load_settings()
    db.py, schema.sql             # connect(), migrate()
    main.py                       # create_app(settings, bot)
    auth.py                       # verify_init_data, current_user
    access.py                     # entitlements: grant, compute_access_until, has_access
    textgeo.py                    # fold(), haversine_m()
    tags.py                       # типы жалоб и позитивные метки (RU подписи)
    places.py                     # чтение, поиск, ранжирование, place_view
    amenities.py                  # индекс удобства
    reviews.py                    # validate_review, author_weight, save_review
    photos.py                     # store_photo, подписанные ссылки
    bot.py                        # BotApi (Protocol), HttpBotApi, handle_update
    payments.py                   # PLANS, invoice, обработка successful_payment, refund
    routes_*.py                   # places, reviews, pay, realtors_listings, me_flags
  tools/                          # osm_import.py, import_listings.py, import_csv.py
  tests/                          # pytest: conftest.py (client, make_init_data, FakeBotApi)
nhatrang/js/                      # api.js, geo.js, map.js, screens_*.js
nhatrang/index.html               # оболочка (переписывается)
```

---

## Фаза 0: проверка рисков

### Task 1: Спайк «камера без галереи и геолокация в Telegram» (одноразовый, не продакшн)

Результат определяет, на чём держится проверка отзывов (раздел 9 спеки). Код выбрасывается.

**Files:** Create `nhatrang/spike/capture.html` (метка `THROWAWAY`); Modify `DESIGN.md` раздел 9 (записать итог).

- [ ] **Step 1:** Страница с тремя блоками: `<input type=file accept="image/*" capture="environment">`; кнопка геолокации через `Telegram.WebApp.LocationManager` (`init`, `getLocation`) и запасная через `navigator.geolocation`; вывод в текст: открылась ли камера, предложил ли телефон галерею, lat/lon/accuracy, время ответа, что вернулось при отказе в доступе.
- [ ] **Step 2:** Отдать страницу по HTTPS (`python3 -m http.server` + туннель; инструмент туннеля выбрать самому) и открыть из тестового бота Некита на его iPhone/Android. Это шаг Некита, ему нужны ссылка и инструкция в три строки.
- [ ] **Step 3:** Записать в `DESIGN.md` раздел 9 таблицу: платформа, камера-онли (да/нет/частично), геолокация (точность, отказ). Ожидаемый результат: три строки «проверено на ...» вместо «не проверено».
- [ ] **Step 4:** Решение по результату: если камера-онли не работает, в Task 8 проверка свежести EXIF и ручная модерация становятся основной защитой (код для них уже в плане); пишется строка в `DESIGN.md`.

---

## Фаза 1: сервер

### Task 2: Каркас сервера, конфиг, схема БД

**Files:** Create `server/pyproject.toml`, `app/config.py`, `app/db.py`, `app/schema.sql`, `app/main.py`, `tests/conftest.py`, `tests/test_scaffold.py`.

**Produces:**
- `Settings` (pydantic или dataclass) с полями: `bot_token, bot_username, webhook_secret, admin_ids: set[int], db_path, photos_dir, web_dir, dev_auth: bool=False, photo_sign_secret, review_min_chars=150, review_min_photos=2, review_max_photos=5, geo_radius_m=150, geo_max_accuracy_m=150, review_reward_days=3, review_place_cooldown_days=14, review_daily_limit=1, initdata_max_age_s=86400`; `load_settings() -> Settings` из окружения.
- `connect(path) -> sqlite3.Connection` (WAL, `foreign_keys=ON`, `row_factory=sqlite3.Row`), `migrate(conn) -> None` (идемпотентно, версия в `PRAGMA user_version`).
- `create_app(settings: Settings, bot: BotApi | None = None) -> FastAPI`, `GET /api/health -> {"ok": true}`; `web_dir` монтируется как статика на `/` последним.
- Таблицы `schema.sql`: `users, entitlements(user_id, days, source in ('stars','review','grant'), ref UNIQUE NULL, created_at, revoked_at), districts, places(status in 'active','pending','rejected'; kind; lat; lon; commercial; aliases JSON), reviews(status in 'published','held','rejected','revoked'; rating 1-5; hold_reason; text_hash; weight), review_reports, signals(source, tag, count, url, confirmed), amenities(category, cheap_local NULL), listings(source_url UNIQUE, place_id NULL, expires_at), realtors(commission_free_confirmed DEFAULT 0, contacts JSON), flags, favorites, payments(charge_id UNIQUE, refunded_at)`.

- [ ] **Step 1:** Тесты: `test_health_ok`; `test_migrate_idempotent` (два вызова подряд, `user_version` не растёт); `test_schema_has_expected_tables`.
- [ ] **Step 2:** Запуск `cd server && uv run pytest -q`, ожидается FAIL (модулей нет).
- [ ] **Step 3:** Реализовать файлы выше. Схема: CHECK-ограничения на статусы, индексы на `reviews(place_id,status)`, `reviews(user_id,created_at)`, `places(lat,lon)`.
- [ ] **Step 4:** `uv run pytest -q` зелёный.
- [ ] **Step 5:** Нет git в `miniapps/`: вместо коммита контрольная точка (весь `pytest` зелёный), см. «Вопросы к Некиту» внизу.

### Task 3: Проверка `initData` и текущий пользователь

**Files:** Create `app/auth.py`, `tests/test_auth.py`; Modify `tests/conftest.py` (фикстура `make_init_data`).

**Produces:** `class AuthError(Exception)`; `verify_init_data(init_data: str, bot_token: str, now: int, max_age_s: int) -> TgUser(id:int, first_name:str, username:str|None)`; зависимость FastAPI `current_user(request) -> TgUser` (заголовок `Authorization: tma <initData>`, upsert в `users`); `make_init_data(user_id, bot_token, auth_date) -> str` в conftest, считает HMAC по алгоритму из документации Telegram (секрет = `HMAC_SHA256(key="WebAppData", bot_token)`, строка проверки из отсортированных пар `k=v` через `\n` без `hash`).

- [ ] **Step 1:** Тесты: валидный → пользователь; неверный hash → `AuthError`; подмена `user.id` в строке → `AuthError`; `auth_date` старше `max_age_s` → `AuthError`; нет `auth_date` → `AuthError`; запрос `GET /api/me` без заголовка → 401; заголовок `X-Dev-User` при `dev_auth=False` → 401, при `True` → 200; `load_settings()` с `APP_ENV=prod` и `dev_auth=true` падает при старте (**Review Focus 2**); `user_id` из тела запроса игнорируется (POST с чужим `user_id` в JSON, в БД автор из initData).
- [ ] **Step 2-4:** FAIL, реализовать (сравнение через `hmac.compare_digest`), PASS.

### Task 4: Права доступа (entitlements) и `/api/me`

**Files:** Create `app/access.py`, `app/routes_me_flags.py` (только `/api/me` здесь), `tests/test_access.py`.

**Produces:**
- `grant(conn, user_id:int, days:int, source:str, ref:str|None, now:datetime) -> bool` (False, если `ref` уже есть, то есть идемпотентно); `revoke(conn, ent_id:int, now) -> None`.
- `compute_access_until(rows:list[EntRow], now:datetime) -> datetime|None`: активные записи (не отозваны) в порядке `created_at` складываются встык: `start = max(cursor, created_at)`, `cursor = start + days`; результат `cursor`, если он позже `now`, иначе `None`.
- `has_access(conn, user_id, now) -> bool`; `GET /api/me -> {id, access_until: iso|null, has_access, reviews_published:int}`.

- [ ] **Step 1:** Тесты по значениям: 3 дня в t0 → `t0+3d`; вторая покупка в t0+1d (7 дней) → `t0+10d`; вторая после истечения (t0+5d) → `t0+12d`; отзыв отозван в середине цепочки, итог пересчитан; истёкший → `None`; `grant` с тем же `ref` второй раз возвращает False и не меняет срок.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 5: Утилиты текста и геометрии

**Files:** Create `app/textgeo.py`, `tests/test_textgeo.py`.

**Produces:** `fold(s:str) -> str` (нижний регистр, снять диакритику через NFD, `đ→d`, `ё→е`, схлопнуть пробелы); `haversine_m(lat1,lon1,lat2,lon2) -> float`.

- [ ] **Step 1:** Тесты: `fold("Vĩnh Hải") == "vinh hai"`, `fold("Đường  Trần Phú") == "duong tran phu"`, `fold("Ёлка") == "елка"`; `haversine_m` на паре точек в 0.001° широты (~111 м) даёт 111±1 м; `haversine_m(a,a)==0`.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 6: Места: чтение, поиск, ранжирование, жалобы по типам

**Files:** Create `app/tags.py`, `app/places.py`, `app/routes_places.py`, `tests/test_places.py`; Modify `tests/conftest.py` (фабрики `make_place`, `make_review`).

**Produces:**
- `tags.COMPLAINTS`: `mold_smell, insects, noise, dirty, utilities, language_gap, mismatch, safety`; `tags.POSITIVE`: `ru_reception, en_reception, market_near, quiet, clean`; словарь RU-подписей. Набор стартовый, правится одной константой.
- `search_places(conn, q:str|None, bbox:tuple|None, district_id:int|None, kind:str|None, limit:int=50) -> list[PlaceListItem]`: поиск по `fold(name)` и `aliases`; в выдачу попадают только `status='active'`.
- `rank_score(avg:float, weight_sum:float, prior_mean:float=3.5, prior_weight:float=3.0) -> float` (байесовское сглаживание); сортировка списка по нему, затем по расстоянию до центра запроса. Поле `commercial` в расчёте не участвует.
- `place_view(conn, place_id:int, has_access:bool, now) -> dict`. Всегда: `id, name, kind, lat, lon, district, price_from_vnd, price_to_vnd, basics, official_photos, rating|None, reviews_count, tag_counts:dict[str,int]` (опубликованные отзывы + подтверждённые сигналы), `amenity_index`, `commercial`, `empty:bool` (нет ни отзывов, ни сигналов). Только при доступе: `paid:{reviews:[{id,text,tags,photo_urls,created_at,author_badge}], signals:[{source,tag,count,url}], amenities:[...]}`. Без доступа ключа `paid` нет, есть `locked:true`.
- Маршруты: `GET /api/places`, `GET /api/places/{id}`. Ответ списка никогда не содержит текстов отзывов.

- [ ] **Step 1:** Тесты: поиск `q="vinh hai"` находит «Vĩnh Hải Hotel»; поиск не находит `status='pending'`; **без доступа JSON ответа не содержит строку из текста отзыва и ключа `paid`** (искать подстроку в `response.text`), с доступом содержит (**Review Focus 1**); `tag_counts` складывает 2 отзыва и 1 подтверждённый сигнал, неподтверждённый сигнал не считается; место с 0 отзывов даёт `empty=True`, `rating=None`; два места с одинаковыми отзывами, одно `commercial=1`, идут в одном порядке независимо от флага; место с названием `<script>alert(1)</script>` возвращается как строка без изменений (экранирует фронт); `rank_score` растёт с `avg` и `weight_sum`, не выходит за [1,5].
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 7: Индекс удобства

**Files:** Create `app/amenities.py`, `tests/test_amenities.py`.

**Produces:** `CATEGORIES = ['massage','shop','laundry','fruit','cafe','cheap_local','pharmacy','hospital','bank_exchange']`; `amenity_index(conn, lat, lon, radius_m:int=400) -> dict[str,int]` (400 м это примерно 5 минут пешком, моё допущение; предфильтр по рамке, точный отбор по `haversine_m`); `amenity_list(conn, lat, lon, radius_m) -> list[dict]` (имя, категория, расстояние, `cheap_local`) только для платного блока.

- [ ] **Step 1:** Тесты: точка на 399 м попадает, на 401 м нет; пустая категория возвращает 0, а не отсутствует ключ; `cheap_local=1` считается в `cheap_local`.
- [ ] **Step 2-4:** FAIL, реализовать, PASS; подключить в `place_view` (поле `amenity_index` : бесплатно, `amenity_list` : в `paid`).

### Task 8: Отзывы жильцов: проверка, фото, награда

**Files:** Create `app/reviews.py`, `app/photos.py`, `app/routes_reviews.py`, `tests/test_reviews.py`, `tests/test_photos.py`.

**Consumes:** `grant`, `haversine_m`, `Settings`. **Produces:**
- `ReviewDraft(text:str, rating:int, tags:list[str], lat:float, lon:float, accuracy_m:float, photo_count:int, exif_oldest_age_s:int|None)`.
- `Verdict(ok:bool, reject_reason:str|None, hold_reason:str|None)`.
- `validate_review(draft, place, history, cfg:Settings, now) -> Verdict`. Жёсткий отказ: `text_short` (после `strip()` меньше `review_min_chars`), `photos_few`, `photos_many`, `bad_coords` (0,0 или вне диапазона), `too_far` (`distance > geo_radius_m`), `daily_limit`, `place_cooldown`, `bad_tag`. Мягкое удержание (`held`): `low_accuracy` (accuracy > `geo_max_accuracy_m`), `exif_stale` (самое раннее фото старше 10 минут, моё допущение), `duplicate_text` (тот же `text_hash` у другого отзыва), `place_pending`.
- `author_weight(approved:int, days_since_first:int) -> float`: `1 + min(approved,10)*0.1 + min(days_since_first/30,3)*0.1`, максимум 2.3 (формула моя).
- `save_review(conn, user_id, place_id, draft, photo_names, cfg, now) -> ReviewResult(id, status, reward_days)`: внутри `BEGIN IMMEDIATE`, чтобы проверки лимитов и вставка не разъезжались при параллельных запросах; при `published` сразу `grant(..., days=cfg.review_reward_days, source='review', ref=f"review:{id}")`; при `held` награды нет до одобрения.
- `store_photo(data:bytes, photos_dir:Path) -> str` (проверка Pillow, форматы JPEG/PNG/WEBP, не больше 6 МБ, пережатие в JPEG до 1280 px по длинной стороне, имя `sha256[:16].jpg`, EXIF снимается после чтения возраста); `sign_photo_url(name, user_id, exp:int, secret) -> str`; `GET /api/photos/{name}?u=&e=&s=` (проверка подписи и срока, не требует заголовка, потому что `<img>` его не шлёт).
- `POST /api/places/{id}/reviews` (multipart: `text, rating, tags[], lat, lon, accuracy_m, photos[]`) → 201 `{id,status,reward_days}` или 422 `{reason}`; `POST /api/reviews/{id}/report` → отзыв `held`, `hold_reason='reported'`.

- [ ] **Step 1:** Тесты `validate_review`: текст 149 символов `text_short`, 150 проходит, 150 пробелов не проходит; расстояние ровно 150.0 м проходит, 150.1 нет (**Review Focus 4**); `lat=0, lon=0` `bad_coords`; второй отзыв того же человека в тот же день `daily_limit`; тот же человек на то же место через 13 дней `place_cooldown`, через 14 проходит; другое место на следующий день проходит (человек сменил жильё); `exif_stale` и `low_accuracy` дают `held`, а не отказ. `author_weight`: монотонно, не выше 2.3. Фото: SVG/PDF/текст под видом картинки → `ValueError`, 7 МБ → `ValueError`, валидный JPEG пережимается и теряет EXIF; подпись: подделанная `s`, чужой `u`, просроченный `e` → 403, верная → 200 (**Review Focus 1**). Интеграция: отзыв 3000 символов с эмодзи проходит и возвращается без искажений; два параллельных `save_review` одного человека из двух потоков дают ровно один `published` (**Review Focus 4**); `published` создаёт запись `entitlements` на 3 дня, `held` не создаёт; одобрение удержанного отзыва (вызов из Task 9) создаёт её один раз.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 9: Добавление места пользователем и модерация через бота

**Files:** Create `app/bot.py`, `tests/test_moderation.py`; Modify `app/routes_places.py` (`POST /api/places`), `app/main.py` (маршрут webhook).

**Produces:**
- `BotApi` (Protocol): `send_message(chat_id:int, text:str, reply_markup:dict|None=None)`, `answer_callback(callback_id:str, text:str)`, `create_invoice_link(title:str, description:str, payload:str, stars:int) -> str`, `answer_pre_checkout(query_id:str, ok:bool, error:str|None=None)`, `refund_star_payment(user_id:int, charge_id:str)`; `HttpBotApi(token)` через `httpx`; `FakeBotApi` в `tests/conftest.py` (пишет вызовы в список).
- `POST /api/places {name, kind, lat, lon}` → 201 `{id, status:'pending'}`; дубликат (то же `fold(name)` в радиусе 50 м, моё допущение) → 409 с `existing_id`.
- `POST /api/bot/webhook` с проверкой заголовка `X-Telegram-Bot-Api-Secret-Token` (иначе 403); `handle_update(update:dict, ctx) -> None`.
- Команды только для `admin_ids`: `/queue` (следующий элемент очереди: новые места и удержанные отзывы, кнопки «одобрить» и «отклонить», `callback_data` вида `ok:place:12`, `no:review:5`), `/revoke <review_id>` (отзыв `revoked`, запись награды отзывается), `/grant <user_id> <days>`, `/stats`. Чужие получают молчание.
- Одобрение места: `status='active'`, все отзывы с единственной причиной `place_pending` становятся `published` и получают награду. Отклонение места: эти отзывы `rejected`, без награды.

- [ ] **Step 1:** Тесты через `TestClient` и `FakeBotApi`: webhook без секрета 403; `/queue` от не-админа не вызывает `send_message`; одобрение места публикует удержанный отзыв и создаёт ровно одну награду (повторное нажатие кнопки не удваивает); отклонение места не создаёт награду; `/revoke` пересчитывает `access_until` пользователя; `POST /api/places` с названием-дубликатом 409; новое место `pending` не видно в `GET /api/places`.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 10: Оплата Stars

**Files:** Create `app/payments.py`, `app/routes_pay.py`, `tests/test_payments.py`.

Перед реализацией сверить методы с `core.telegram.org/bots/api` и `core.telegram.org/bots/payments-stars` (я писал по памяти): `createInvoiceLink` (валюта `XTR`, без `provider_token`), `answerPreCheckoutQuery`, поле `successful_payment.telegram_payment_charge_id`, `refundStarPayment`, на клиенте `Telegram.WebApp.openInvoice(url, cb)`.

**Produces:** `PLANS = {'d3': Plan(days=3, stars=300, rub=590), 'd7': Plan(days=7, stars=600, rub=1190)}` (читается из `Settings`); `GET /api/plans`; `POST /api/pay/invoice {plan}` → `{invoice_url}` (payload `f"{plan}:{user_id}"`); обработка апдейтов: `pre_checkout_query` → `answer_pre_checkout(ok=True)` только если payload валиден, сумма и `XTR` совпадают; `successful_payment` → запись в `payments` по `charge_id` (UNIQUE) и `grant(days, 'stars', ref=charge_id)`; команда `/paysupport` с текстом поддержки; админ-команда `/refund <charge_id>` вызывает `refund_star_payment`, проставляет `refunded_at`, отзывает награду.

- [ ] **Step 1:** Тесты: invoice создаётся со `stars=300` для `d3`; неизвестный план 422; `pre_checkout` с суммой 299 → `ok=False`; **один и тот же `successful_payment` дважды → одна запись и срок увеличен один раз** (**Review Focus 3**); payload одного пользователя при платеже от другого → не выдаёт доступ; после `/refund` доступ пересчитан; `/paysupport` отвечает любому пользователю.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 11: Риелторы и «Свободно сейчас»

**Files:** Create `app/routes_realtors_listings.py`, `tests/test_realtors_listings.py`.

**Produces:** `GET /api/realtors -> [{id, name, kind:'ru'|'vi', languages, commission_free_confirmed:bool, notes, contacts?}]`; `GET /api/listings?district=&bedrooms=&max_price=&only_with_place=` → `[{id, title, price_vnd, bedrooms, district_text, posted_at, place_id|None, place_summary|None, chats_count, contacts?}]`. Поле `contacts` есть только при доступе; в остальных случаях ключ отсутствует и стоит `locked:true`. Объявления старше `expires_at` не отдаются. `place_summary` содержит только бесплатные поля места (оценка, `tag_counts`).

- [ ] **Step 1:** Тесты: без доступа в тексте ответа нет ни ника риелтора, ни Zalo, ни ссылки на оригинальный пост (**Review Focus 1**); с доступом есть; `commission_free_confirmed` по умолчанию False и не меняется через публичный API; просроченное объявление скрыто; фильтры по `bedrooms` и `max_price` работают; объявление без `place_id` отдаётся в списке, но не в `only_with_place=1`.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 12: Флажки, избранное, районы

**Files:** Modify `app/routes_me_flags.py`; Create `tests/test_flags_favs.py`.

**Produces:** `GET/POST/DELETE /api/flags` (`{label≤40, category≤20, color из палитры ['#e5484d','#f76b15','#ffb224','#30a46c','#12a594','#0091ff','#6e56cf','#d6409f'], lat, lon, place_id?}`; максимум 200 на человека); `GET/PUT/DELETE /api/favorites/{place_id}`; `GET /api/districts -> GeoJSON FeatureCollection` с `properties.name_ru`. Данные только свои: чужие флажки не читаются и не удаляются (404).

- [ ] **Step 1:** Тесты: пользователь A не видит и не удаляет флажок B; цвет вне палитры 422; 201-й флажок 422; `label` с HTML возвращается строкой; избранное идемпотентно.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

---

## Фаза 2: данные

### Task 13: Импорт мест, бытовухи и районов из OpenStreetMap

**Files:** Create `tools/osm_import.py`, `tests/fixtures/overpass_sample.json`, `tests/test_osm_import.py`, `server/data/districts_ru.json` (заполняет Некит).

**Produces:** `parse_overpass(payload:dict) -> OsmBatch(places:list, amenities:list)`: теги жилья `tourism=hotel|guest_house|apartment|hostel`, `building` с названием отдельно не берём (моё допущение); бытовуха: `amenity=pharmacy|hospital|clinic|restaurant|cafe|bank|bureau_de_change`, `shop=convenience|supermarket|laundry|greengrocer`, `shop=massage`/`leisure=spa` (точные теги проверить на реальных данных); `upsert(conn, batch) -> dict(counts)` идемпотентно по `osm_id`; `fetch_overpass(bbox) -> dict` (один запрос, пауза и User-Agent, запускается руками, не по расписанию).

- [ ] **Step 1:** Тесты на фикстуре: места и точки разложены по категориям; повторный импорт не дублирует; узел без координат пропущен; название с кавычками и эмодзи сохраняется как есть.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.
- [ ] **Step 5 (с Некитом):** запустить `fetch_overpass` на рамке Нячанга, посмотреть, сколько реально мест и точек пришло (цель спеки 300+ мест, оценка из OSM может быть ниже, тогда решает Некит: добавить ручной ввод или принять меньше). Границы районов: посмотреть, отдаёт ли OSM административные границы подрайонов; если нет, Некит рисует их в geojson.io. Названия районов по-русски утверждает Некит и кладёт в `districts_ru.json`; без этого файла `GET /api/districts` отдаёт пустой список.

### Task 14: Импорт объявлений, риелторов и сигналов

**Files:** Create `tools/import_listings.py`, `tools/import_csv.py`, `tests/test_importers.py`.

**Produces:**
- `import_listings(conn, path, now) -> int`: формат `~/Claude Code/nhatrang-search/listings.json` проверен 04.11: словарь с одним ключом, внутри список записей с полями `id, title, price_vnd, bedrooms, district, posted_at, url, agent`. Поле `status: rejected` относится к личному фильтру Некита и игнорируется. В базу идут записи не старше 14 дней, `source_url` уникален, `agent` и `url` попадают в `contacts` (платное).
- `match_place(title:str, district:str, places) -> int|None`: совпадение по `fold(name)` и `aliases` как целого слова; при нескольких кандидатах `None` (лучше без привязки, чем неверная).
- `import_realtors_csv(conn, path)` (колонки `name,kind,languages,contacts,notes,commission_free_confirmed`; значение `1` принимается только вместе с непустым `confirmed_at`); `import_signals_csv(conn, path)` (колонки `place,source,tag,count,url,confirmed`; строки с `confirmed!=1` пропускаются и попадают в отчёт).

- [ ] **Step 1:** Тесты: запись старше 14 дней пропущена; повторный запуск не дублирует; «Oceanus, 3 спальни...» привязывается к месту с алиасом `Oceanus`, а при двух таких местах остаётся `None`; `commission_free_confirmed=1` без `confirmed_at` отклоняется; сигнал без подтверждения не считается в `tag_counts`.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

---

## Фаза 3: фронт

Общие правила для задач 15-19: переписать `nhatrang/index.html` и вынести логику в `nhatrang/js/`. Старые экраны `guide`, `contract`, `safety`, `templ`, гейт «3 бесплатных контакта» и мок-данные удалить (замена включает удаление). Весь пользовательский текст приходит из `textContent` или `tgx.esc` (**Review Focus 5**). Тап-зоны не меньше 36 px, светлая и тёмная темы, 360/390/430 px, как в существующих проверках `../tests/e2e.mjs`.

### Task 15: Оболочка, клиент API, вход, онбординг, навигация

**Files:** Modify `index.html`; Create `js/api.js`, `js/geo.js`, `js/screens_core.js`.

**Produces:** `api.get(path, params)`, `api.post(path, body|FormData)`, `api.del(path)` добавляют `Authorization: tma ${Telegram.WebApp.initData}`; в браузере без Telegram работает только если сервер в `dev_auth` (`X-Dev-User`). Ошибка 401 показывает экран «Откройте приложение из Telegram». `geo.getPosition() -> Promise<{lat,lon,accuracy}>` (`LocationManager`, запасной `navigator.geolocation`, по итогу Task 1); отказ даёт понятный текст и путь «разрешить в настройках». Нижнее меню: «Проверить», «Свободно», «Риелторы», «Избранное», «Профиль». Онбординг на 3 шага из прототипа с новым текстом.

- [ ] **Step 1:** Тесты Playwright (см. Task 20 про запуск с сервером): первый запуск показывает онбординг, повторный нет; все 5 табов открываются, активен один экран; запрос без `initData` и без `dev_auth` показывает экран «Откройте из Telegram»; в DOM нет вызовов `innerHTML` с данными API (проверка поиском в исходниках `js/`).
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 16: «Проверить жильё»: карта, районы, поиск, карточка места

**Files:** Create `js/map.js`, `js/screens_check.js`.

**Produces:** `createMap(el, {center, zoom}) -> MapApi{addDistricts(fc), setPlaces(items,onTap), setFlags(items,onTap), onPick(cb)}` на Leaflet; подложка берётся из настройки `tiles_url` (провайдер тайлов выбирает Некит, см. вопросы), районы рисуются слоем с подписью `name_ru`; экран поиска (поле, чипы типов, список и карта), карточка места: бесплатный блок (фото, цена, условия, оценка, жалобы по типам, индекс удобства) и закрытый блок «Что пишут жильцы» с кнопкой в paywall; при `empty=true` честная плашка «Отзывов пока нет», кнопка оплаты скрыта.

- [ ] **Step 1:** Тесты: поиск «vinh hai» показывает место с диакритикой; карточка без доступа не содержит в DOM текста отзыва и содержит счётчики; при `empty` нет кнопки оплаты; название `<img src=x onerror=...>` отображается текстом и `window.__xss` не появляется; на карте видны подписи районов из фикстуры.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 17: Отзыв и добавление места

**Files:** Create `js/screens_review.js`.

**Produces:** экран «Оставить отзыв»: поле текста с счётчиком до 150, оценка 1-5, метки (жалобы и плюсы), до 5 фото через `<input type=file accept="image/*" capture="environment">` (если спайк подтвердил камера-онли) с превью, блок геолокации с понятным статусом («вы в 40 м от места» или «вы далеко»), кнопка отправки неактивна, пока не выполнены текст ≥150, фото ≥2 и геопозиция; после ответа показывает `reward_days` или причину удержания. Если места нет в поиске, кнопка «Добавить место» ведёт на форму (название, тип, точка на карте), после отправки «место на проверке, отзыв опубликуется после проверки».

- [ ] **Step 1:** Тесты с подменой `geo.getPosition` и загрузкой тестовых картинок: кнопка неактивна при 149 символах и активна при 150; при 1 фото неактивна; при удалённом месте (геопозиция 500 м) показывает «вы далеко»; успешная отправка показывает «+3 дня»; ответ 422 `daily_limit` показывает человеческий текст; добавление нового места показывает «на проверке».
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 18: «Свободно», «Риелторы», «Избранное», флажки

**Files:** Create `js/screens_free.js`, `js/screens_realtors.js`, `js/screens_favs.js`.

**Produces:** «Свободно сейчас»: список и карта объявлений, фильтры (бюджет, спальни, только с привязкой к месту), карточка с ценой, свежестью, `chats_count`, жалобами места; контакты закрыты (кнопка в paywall). «Риелторы»: список с метками «без комиссии» (только подтверждённые), языки, контакты закрыты. «Избранное»: места и объявления. Режим «поставить флажок» на карте: выбор категории и цвета, подпись, сохранение и удаление.

- [ ] **Step 1:** Тесты: без доступа в DOM нет контактов и ников; с доступом есть; метка «без комиссии» только у подтверждённых; флажок создаётся с цветом и после перезагрузки остаётся; удаление работает; пустое состояние «Свободно» не пустой экран.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

### Task 19: Paywall, оплата Stars, профиль

**Files:** Create `js/screens_pay.js`, `js/screens_profile.js`.

**Produces:** paywall с двумя тарифами (3 дня, 7 дней), тексты о том, что открывается; кнопка оплаты вызывает `POST /api/pay/invoice`, затем `Telegram.WebApp.openInvoice(url, cb)`; статусы `paid` → экран успеха и обновление `/api/me`, `cancelled` → назад на paywall, `failed` → экран ошибки с «повторить». Профиль: срок доступа и сколько осталось, сколько отзывов опубликовано, как получить дни за отзыв, ссылка `/paysupport`. Вне Telegram (мок-ветка) оплата показывает «Откройте из Telegram», карточка и QR Bybit из прототипа удаляются.

- [ ] **Step 1:** Тесты с подменой `Telegram.WebApp.openInvoice`: статус `paid` обновляет срок и открывает платный блок; `cancelled` возвращает на paywall без изменений; `failed` показывает ошибку и «повторить»; профиль показывает остаток дней по `access_until`.
- [ ] **Step 2-4:** FAIL, реализовать, PASS.

---

## Фаза 4: проверка и запуск

### Task 20: Обновить существующие тесты UI под сервер

**Files:** Modify `../tests/lib.mjs`, `../tests/e2e.mjs`, `../tests/stress.mjs`, `../tests/telegram-real.mjs`, `../tests/README.md`; Create `server/tools/seed_test.py`.

**Что менять:** `urlOf('nhatrang')` сегодня возвращает `file://`, для нового приложения нужен `http://127.0.0.1:<порт>/`. Тесты поднимают сервер `APP_ENV=test` (`dev_auth=true`, тестовая БД во временной папке, `seed_test.py` заливает размеченные тестовые места и отзывы, это фикстуры, а не данные продукта) и гасят его по PID в конце (правило из памяти: `pkill -f` промахивается). Обновить `SAMPLE` и сценарии под новые экраны. Остальные приложения (`reels-radar`, `faceless`) не трогать, `ONLY=nhatrang` продолжает работать. Стресс: инвариант «нет контактов и текстов отзывов без доступа» проверяется после каждого действия бота.

- [ ] **Step 1:** Подготовить сервер для тестов и `seed_test.py`; прогнать один раз вручную.
- [ ] **Step 2:** `ONLY=nhatrang node e2e.mjs` : ожидается 0 FAIL (старое число 506 неактуально, новое записать в README); `node telegram-real.mjs nhatrang` 0 FAIL; `node stress.mjs nhatrang 40 60 8 3` без нарушений. Запускать по одному.
- [ ] **Step 3:** Обновить `HANDOFF.md`: что сделано, как запустить, что осталось.

### Task 21: Развёртывание и чек-лист запуска

**Files:** Create `server/deploy/README.md`, `server/deploy/nhatrang.service` (systemd), `server/deploy/Caddyfile`, `server/deploy/backup.sh`.

Это шаги, где нужен Некит (аккаунты и деньги):
- [ ] **Step 1 (Некит):** выбрать VPS в пределах $10-15/мес вместе с доменом (я цен не проверял) и дать доступ по SSH; завести бота у @BotFather (токен, имя, `/setdomain`, кнопка Web App на URL домена, `/paysupport` текст).
- [ ] **Step 2:** Установить сервер, `Caddy` с автоматическим HTTPS, `systemd` с автоперезапуском; `setWebhook` с `secret_token`; `.env` вне репозитория, права 600.
- [ ] **Step 3:** `backup.sh` по cron на VPS: `sqlite3 .backup` каждую ночь, хранить 14 копий, плюс папка фото; раз в неделю Некит скачивает копию вручную (так не заводим новую ночную задачу на ноуте и не трогаем правила ресурсов).
- [ ] **Step 4:** Импорт: `osm_import` (Task 13), районы, `import_listings` (Task 14); CSV риелторов и сигналов Некит заполняет сам. Проверка на боевом боте: свой платёж на минимальный тариф, возврат `/refund`, свой отзыв с телефона с геометкой.
- [ ] **Step 5:** Чек-лист «не проверено до запуска»: реальный платёж Stars и возврат, курс и вывод Stars, камера-онли и геолокация на iOS и Android (Task 1), условия провайдера тайлов, нагрузка на VPS (простой тест `k6` или `locust` на `/api/places`).

---

## Вопросы к Некиту (блокируют отдельные задачи, не весь план)

1. **Тайлы карты.** Подложка OSM для боевого трафика ограничена правилами проекта OSM (прямое массовое использование не разрешено), нужен провайдер (например с бесплатным лимитом, условия я не проверял). Какой выбираешь, или я подберу и покажу варианты?
2. **Git.** В `miniapps/` нет репозитория, поэтому в плане вместо коммитов стоят прогоны тестов. Сделать `git init` в `~/Claude Code/miniapps/` (без пуша на GitHub)?
3. **Названия районов** (Task 13): дашь список, или я предложу из данных OSM и ты поправишь.
4. **VPS и домен** (Task 21): у тебя есть предпочтение, или предложить варианты с ценами после проверки?

## Самопроверка плана

- **Покрытие спеки:** разд. 2-3 (аудитория, анти-цели) Task 6, 12, 16; разд. 4 (структура) Task 15, 18; разд. 5-6 (место, платно/бесплатно) Task 6, 16; разд. 7 (бытовуха) Task 7, 13; разд. 8 (карта, районы, флажки) Task 12, 16, 18; разд. 9-10 (отзывы, награда) Task 8, 9, 17; разд. 11 (источники) Task 13, 14, плюс план B для чатов; разд. 12 (рейтинг без проплаты) Task 6; разд. 13-14 (Свободно, Риелторы) Task 11, 14, 18; разд. 15 (деньги) Task 10, 19; разд. 16 (ограничения) Global Constraints, Task 3, 21; разд. 17 (решения) учтены: место не в базе Task 9, 17; ручные сигналы Task 14; предпроверка Task 8 (эвристики вместо ИИ).
- **Известный пробел:** сигналы из чатов (план B) и ИИ-предмодерация; без них цель «300+ мест с сигналами» к концу месяца вряд ли достижима, места будут, сигналов мало.
- **Согласованность имён:** `grant`, `has_access`, `place_view`, `validate_review`, `save_review`, `BotApi`, `FakeBotApi`, `Settings` везде одинаковы; награда помечается `ref="review:{id}"`, платёж `ref=charge_id`.
