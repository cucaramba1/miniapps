"""Тестовые данные для UI-тестов (фикстуры, НЕ данные продукта).
  APP_ENV=test DB_PATH=/tmp/x.db python -m tools.seed_test
Пользователь 1001 без доступа, 1002 с доступом (3 дня)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from app.access import grant
from app.config import load_settings
from app.db import connect, migrate
from app.textgeo import fold


def seed(conn, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    ts = now.isoformat()
    for uid in (1001, 1002, 1003):
        conn.execute("INSERT OR IGNORE INTO users(id, first_name, created_at) VALUES(?,?,?)", (uid, "Тест", ts))
    grant(conn, 1002, 3, "grant", "seed:1002", now)
    places = [
        ("Vĩnh Hải Hotel", "hotel", 12.2388, 109.1967, 0, ["Vinh Hai"]),
        ("<img src=x onerror=window.__xss=1>", "hostel", 12.2400, 109.1980, 0, []),
        ("Sunrise Apartments", "apartment", 12.2450, 109.1950, 1, []),
        ("Пустое Место", "guest_house", 12.2300, 109.1900, 0, []),
    ]
    ids = []
    for name, kind, lat, lon, com, al in places:
        cur = conn.execute(
            "INSERT INTO places(name, name_fold, kind, lat, lon, commercial, aliases, status, created_at, price_from_vnd) "
            "VALUES(?,?,?,?,?,?,?,'active',?,?)", (name, fold(name), kind, lat, lon, com, json.dumps(al, ensure_ascii=False), ts, 500000))
        ids.append(cur.lastrowid)
    texts = ["УНИКАЛЬНЫЙ_ТЕКСТ_ОТЗЫВА_ОДИН " + "а" * 120, "УНИКАЛЬНЫЙ_ТЕКСТ_ОТЗЫВА_ДВА " + "б" * 120]
    for i, t in enumerate(texts):
        conn.execute(
            "INSERT INTO reviews(place_id, user_id, status, rating, text, tags, lat, lon, photos, text_hash, weight, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (ids[0], 1003, "published", 4 - i, t, json.dumps(["noise"] if i == 0 else ["noise", "clean"]), 12.2388, 109.1967, "[]",
             hashlib.sha256(t.encode()).hexdigest(), 1.0, (now - timedelta(days=i + 1)).isoformat()))
        conn.execute("UPDATE reviews SET user_id=1003 WHERE id=last_insert_rowid()")
    conn.execute("INSERT INTO realtors(name, kind, languages, notes, contacts, commission_free_confirmed, confirmed_at) VALUES(?,?,?,?,?,?,?)",
                 ("Тест Риелтор", "ru", '["ru","en"]', "Фикстура", json.dumps({"tg": "@seed_realtor_nick"}), 1, ts))
    conn.execute("INSERT INTO realtors(name, kind, languages, notes, contacts) VALUES(?,?,?,?,?)",
                 ("Местный Агент", "vi", '["vi"]', "", json.dumps({"zalo": "0900000001"})))
    conn.execute("INSERT INTO listings(source_url, title, price_vnd, bedrooms, district_text, posted_at, place_id, chats_count, contacts, expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 ("https://example.test/post/1", "Квартира у моря", 15000000, 2, "Север", ts, ids[0], 3,
                  json.dumps({"agent": "@seed_agent_nick", "url": "https://example.test/post/1"}), (now + timedelta(days=10)).isoformat()))
    conn.execute("INSERT INTO listings(source_url, title, price_vnd, bedrooms, district_text, posted_at, contacts, expires_at) VALUES(?,?,?,?,?,?,?,?)",
                 ("https://example.test/post/2", "Студия <b>без привязки</b>", 9000000, 1, "Центр", ts, json.dumps({"agent": "@seed_agent2"}), (now + timedelta(days=10)).isoformat()))
    conn.execute("INSERT INTO districts(name_ru, geojson) VALUES(?,?)",
                 ("Тестовый район", json.dumps({"type": "Polygon", "coordinates": [[[109.18, 12.22], [109.21, 12.22], [109.21, 12.25], [109.18, 12.25], [109.18, 12.22]]]})))


if __name__ == "__main__":
    s = load_settings()
    c = connect(s.db_path)
    migrate(c)
    seed(c)
    print("seeded", s.db_path)
