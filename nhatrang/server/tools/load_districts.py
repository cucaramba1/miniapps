"""Загрузка районов из data/districts_ru.json (заполняет и утверждает Некит, названия не выдумываем).
  python -m tools.load_districts data/districts_ru.json
Формат: [{"name_ru": "...", "geometry": {"type": "Polygon"|"MultiPolygon"|"Point", "coordinates": [...]}}]
Point = центр района без границ: на карте подпись в точке, район места = ближайший центр (app/districts.py).
Заменяет все районы целиком (идемпотентно)."""
from __future__ import annotations

import json
import sqlite3
import sys


def load_districts(conn: sqlite3.Connection, path: str) -> int:
    items = json.load(open(path, encoding="utf-8"))
    for it in items:
        if not it.get("name_ru", "").strip() or it.get("geometry", {}).get("type") not in ("Polygon", "MultiPolygon", "Point"):
            raise ValueError(f"плохая запись района: {str(it)[:80]}")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("UPDATE places SET district_id=NULL")
        conn.execute("DELETE FROM districts")
        for it in items:
            conn.execute("INSERT INTO districts(name_ru, geojson) VALUES(?,?)",
                         (it["name_ru"].strip(), json.dumps(it["geometry"])))
        from app.districts import assign_districts
        assign_districts(conn)
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return len(items)


if __name__ == "__main__":
    from app.config import load_settings
    from app.db import connect, migrate
    c = connect(load_settings().db_path)
    migrate(c)
    print("districts:", load_districts(c, sys.argv[1]))
