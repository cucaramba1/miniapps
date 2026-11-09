from __future__ import annotations

import json
import sqlite3

from .textgeo import haversine_m

MAX_M = 6000  # дальше 6 км от любого центра район не назначается


def assign_districts(conn: sqlite3.Connection, max_m: float = MAX_M) -> int:
    """Район места = ближайший центр-точка (районы без границ). Полигональные районы не трогаем."""
    centers = []
    for r in conn.execute("SELECT id, geojson FROM districts"):
        g = json.loads(r["geojson"])
        if g.get("type") == "Point":
            centers.append((r["id"], g["coordinates"][1], g["coordinates"][0]))
    if not centers:
        return 0
    n = 0
    for p in conn.execute("SELECT id, lat, lon, district_id FROM places").fetchall():
        best = min(((haversine_m(p["lat"], p["lon"], la, lo), i) for i, la, lo in centers))
        new = best[1] if best[0] <= max_m else None
        if new != p["district_id"]:
            conn.execute("UPDATE places SET district_id=? WHERE id=?", (new, p["id"]))
            n += 1
    return n
