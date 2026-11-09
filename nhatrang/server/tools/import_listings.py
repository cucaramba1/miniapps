"""Импорт объявлений из ~/Claude Code/nhatrang-search/listings.json.

  uv run python -m tools.import_listings ~/"Claude Code"/nhatrang-search/listings.json

Правила:
- формат: {"listings": [...]}; в записях бывают пустые/относительные даты («1 месяц назад»)
  и служебные записи record_type=contact: они пропускаются;
- status=rejected это личный фильтр Некита и игнорируется; status=closed (объявление закрыто)
  пропускается, это уже не «свободно сейчас»;
- берутся записи, опубликованные не раньше 14 дней назад; дата: posted_at, иначе found_at;
- контакты (agent, url, handles) кладутся в contacts (платная часть).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from app.textgeo import fold

FRESH_DAYS = 14
LOCAL_TZ = timezone(timedelta(hours=7))


def parse_dt(s) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip().replace(" ", "T", 1) if re.match(r"^\d{4}-\d{2}-\d{2} \d", s.strip()) else s.strip()
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=LOCAL_TZ)


def match_place(title: str, district: str, places: list[dict]) -> int | None:
    """Совпадение по имени/алиасу как целому слову. Неоднозначность -> None."""
    hay = fold(f"{title} {district}")
    found: set[int] = set()
    for p in places:
        names = [p["name"], *p.get("aliases", [])]
        for n in names:
            fn = fold(n)
            if len(fn) >= 4 and re.search(r"(?<!\w)" + re.escape(fn) + r"(?!\w)", hay):
                found.add(p["id"])
    return found.pop() if len(found) == 1 else None


def import_listings(conn: sqlite3.Connection, path: str, now: datetime) -> int:
    data = json.load(open(path, encoding="utf-8"))
    recs = data["listings"] if isinstance(data, dict) else data
    places = [{"id": r["id"], "name": r["name"], "aliases": json.loads(r["aliases"])}
              for r in conn.execute("SELECT id, name, aliases FROM places WHERE status='active'")]
    added = 0
    for r in recs:
        url = r.get("url")
        if r.get("record_type") == "contact" or not url or r.get("status") == "closed":
            continue
        posted = parse_dt(r.get("posted_at")) or parse_dt(r.get("found_at"))
        if posted is None or now - posted > timedelta(days=FRESH_DAYS):
            continue
        title = r.get("title") or ""
        district = r.get("district") or ""
        contacts = {k: v for k, v in {"agent": r.get("agent"), "url": url,
                                      "handles": r.get("contact_handles"),
                                      "name": r.get("contact_name")}.items() if v}
        cur = conn.execute(
            "INSERT OR IGNORE INTO listings(source_url, title, price_vnd, bedrooms, district_text, "
            "posted_at, place_id, contacts, expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (url, title, r.get("price_vnd"), r.get("bedrooms"), district, posted.isoformat(),
             match_place(title, district, places), json.dumps(contacts, ensure_ascii=False),
             (posted + timedelta(days=FRESH_DAYS)).isoformat()))
        added += cur.rowcount
    return added


if __name__ == "__main__":
    from app.config import load_settings
    from app.db import connect, migrate
    c = connect(load_settings().db_path)
    migrate(c)
    print("added:", import_listings(c, sys.argv[1], datetime.now(timezone.utc)))
