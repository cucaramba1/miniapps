"""Импорт мест и бытовухи из OpenStreetMap (Overpass).

Запуск руками, не по расписанию:
  uv run python -m tools.osm_import fetch  data/overpass.json     # один запрос к Overpass
  uv run python -m tools.osm_import load   data/overpass.json     # разобрать и залить в БД
Повторный load идемпотентен (по osm_id) и не трогает status/commercial/цены.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.textgeo import fold

# юг, запад, север, восток; рамка с запасом вокруг Нячанга, уточняется после первого запуска
NHA_TRANG_BBOX = (12.15, 109.10, 12.36, 109.30)

PLACE_KINDS = {"hotel": "hotel", "guest_house": "guest_house", "apartment": "apartment",
               "hostel": "hostel"}


def _amenity_category(tags: dict) -> str | None:
    a, s, l = tags.get("amenity"), tags.get("shop"), tags.get("leisure")
    if a == "pharmacy":
        return "pharmacy"
    if a in ("hospital", "clinic"):
        return "hospital"
    if a in ("cafe", "restaurant"):
        return "cafe"
    if a in ("bank", "bureau_de_change"):
        return "bank_exchange"
    if s in ("convenience", "supermarket"):
        return "shop"
    if s == "laundry":
        return "laundry"
    if s == "greengrocer":
        return "fruit"
    if s == "massage" or l == "spa" or a == "spa":
        return "massage"
    return None


@dataclass
class OsmBatch:
    places: list[dict] = field(default_factory=list)
    amenities: list[dict] = field(default_factory=list)


def _coords(el: dict) -> tuple[float, float] | None:
    if "lat" in el and "lon" in el:
        return el["lat"], el["lon"]
    c = el.get("center")
    if c and "lat" in c and "lon" in c:
        return c["lat"], c["lon"]
    return None


def parse_overpass(payload: dict) -> OsmBatch:
    batch = OsmBatch()
    for el in payload.get("elements", []):
        xy = _coords(el)
        tags = el.get("tags") or {}
        if xy is None or not tags:
            continue
        osm_id = f"{el['type']}/{el['id']}"
        kind = PLACE_KINDS.get(tags.get("tourism", ""))
        if kind and tags.get("name"):
            aliases = [tags[k] for k in ("name:en", "name:vi", "name:ru", "alt_name", "old_name")
                       if tags.get(k) and tags[k] != tags["name"]]
            batch.places.append({"osm_id": osm_id, "name": tags["name"], "kind": kind,
                                 "lat": xy[0], "lon": xy[1], "aliases": aliases})
            continue
        cat = _amenity_category(tags)
        if cat:
            batch.amenities.append({"osm_id": osm_id, "name": tags.get("name", ""),
                                    "category": cat, "lat": xy[0], "lon": xy[1]})
    return batch


def upsert(conn: sqlite3.Connection, batch: OsmBatch) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    counts = {"places_new": 0, "places_updated": 0, "amenities_new": 0, "amenities_updated": 0}
    conn.execute("BEGIN IMMEDIATE")
    try:
        for p in batch.places:
            exists = conn.execute("SELECT 1 FROM places WHERE osm_id=?", (p["osm_id"],)).fetchone()
            if exists:
                conn.execute("UPDATE places SET name=?, name_fold=?, kind=?, lat=?, lon=?, aliases=? "
                             "WHERE osm_id=?", (p["name"], fold(p["name"]), p["kind"], p["lat"],
                                                p["lon"], json.dumps(p["aliases"], ensure_ascii=False),
                                                p["osm_id"]))
                counts["places_updated"] += 1
            else:
                conn.execute("INSERT INTO places(osm_id, name, name_fold, kind, lat, lon, aliases, "
                             "status, created_at) VALUES(?,?,?,?,?,?,?,'active',?)",
                             (p["osm_id"], p["name"], fold(p["name"]), p["kind"], p["lat"], p["lon"],
                              json.dumps(p["aliases"], ensure_ascii=False), now))
                counts["places_new"] += 1
        for a in batch.amenities:
            exists = conn.execute("SELECT 1 FROM amenities WHERE osm_id=?", (a["osm_id"],)).fetchone()
            if exists:
                conn.execute("UPDATE amenities SET name=?, category=?, lat=?, lon=? WHERE osm_id=?",
                             (a["name"], a["category"], a["lat"], a["lon"], a["osm_id"]))
                counts["amenities_updated"] += 1
            else:
                conn.execute("INSERT INTO amenities(osm_id, name, category, lat, lon) VALUES(?,?,?,?,?)",
                             (a["osm_id"], a["name"], a["category"], a["lat"], a["lon"]))
                counts["amenities_new"] += 1
        from app.districts import assign_districts
        assign_districts(conn)
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return counts


def build_query(bbox: tuple[float, float, float, float]) -> str:
    b = ",".join(str(x) for x in bbox)
    return f"""[out:json][timeout:90];
(
  nwr["tourism"~"^(hotel|guest_house|apartment|hostel)$"]({b});
  nwr["amenity"~"^(pharmacy|hospital|clinic|restaurant|cafe|bank|bureau_de_change|spa)$"]({b});
  nwr["shop"~"^(convenience|supermarket|laundry|greengrocer|massage)$"]({b});
  nwr["leisure"="spa"]({b});
);
out center tags;"""


MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]


def fetch_overpass(bbox=NHA_TRANG_BBOX) -> dict:
    import httpx
    last = None
    for url in MIRRORS:  # по одному запросу на зеркало, без ретраев в цикле
        try:
            r = httpx.post(url, data={"data": build_query(bbox)}, timeout=120,
                           headers={"User-Agent": "nhatrang-dom-importer/0.2 (manual one-off)"})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            last = e
    raise RuntimeError(f"Overpass недоступен: {last}")


if __name__ == "__main__":
    from app.config import load_settings
    from app.db import connect, migrate
    mode, path = sys.argv[1], sys.argv[2]
    if mode == "fetch":
        json.dump(fetch_overpass(), open(path, "w"), ensure_ascii=False)
        print("saved", path)
    elif mode == "load":
        c = connect(load_settings().db_path)
        migrate(c)
        print(upsert(c, parse_overpass(json.load(open(path)))))
