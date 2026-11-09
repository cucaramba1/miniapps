from __future__ import annotations

import sqlite3

from .textgeo import bbox_around, haversine_m

CATEGORIES = ["massage", "shop", "laundry", "fruit", "cafe", "cheap_local",
              "pharmacy", "hospital", "bank_exchange"]


def _near(conn: sqlite3.Connection, lat: float, lon: float, radius_m: float):
    s, n, w, e = bbox_around(lat, lon, radius_m)
    rows = conn.execute(
        "SELECT name, category, lat, lon, cheap_local FROM amenities "
        "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?", (s, n, w, e)).fetchall()
    for r in rows:
        d = haversine_m(lat, lon, r["lat"], r["lon"])
        if d <= radius_m:
            yield r, d


def amenity_index(conn, lat: float, lon: float, radius_m: int = 400) -> dict[str, int]:
    out = {c: 0 for c in CATEGORIES}
    for r, _ in _near(conn, lat, lon, radius_m):
        if r["category"] in out:
            out[r["category"]] += 1
        if r["cheap_local"] and r["category"] != "cheap_local":
            out["cheap_local"] += 1
    return out


def amenity_list(conn, lat: float, lon: float, radius_m: int = 400) -> list[dict]:
    items = [{"name": r["name"], "category": r["category"], "distance_m": round(d),
              "cheap_local": bool(r["cheap_local"])} for r, d in _near(conn, lat, lon, radius_m)]
    return sorted(items, key=lambda x: x["distance_m"])
