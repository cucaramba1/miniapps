from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Callable

from .amenities import amenity_index, amenity_list
from .tags import LABELS_RU
from .textgeo import fold, haversine_m


def rank_score(avg: float, weight_sum: float, prior_mean: float = 3.5,
               prior_weight: float = 3.0) -> float:
    return (prior_weight * prior_mean + avg * weight_sum) / (prior_weight + weight_sum)


def _stats(conn: sqlite3.Connection, place_ids: list[int]) -> dict[int, dict]:
    out = {i: {"n": 0, "wsum": 0.0, "wrate": 0.0, "tags": {}} for i in place_ids}
    if not place_ids:
        return out
    q = ",".join("?" * len(place_ids))
    for r in conn.execute(
            f"SELECT place_id, rating, weight, tags FROM reviews "
            f"WHERE status='published' AND place_id IN ({q})", place_ids):
        s = out[r["place_id"]]
        s["n"] += 1
        s["wsum"] += r["weight"]
        s["wrate"] += r["weight"] * r["rating"]
        for t in json.loads(r["tags"]):
            s["tags"][t] = s["tags"].get(t, 0) + 1
    for r in conn.execute(
            f"SELECT place_id, tag, count FROM signals "
            f"WHERE confirmed=1 AND place_id IN ({q})", place_ids):
        t = out[r["place_id"]]["tags"]
        t[r["tag"]] = t.get(r["tag"], 0) + r["count"]
    return out


def _district_names(conn) -> dict[int, str]:
    return {r["id"]: r["name_ru"] for r in conn.execute("SELECT id, name_ru FROM districts")}


def _summary(p: sqlite3.Row, st: dict, dn: dict[int, str]) -> dict:
    avg = st["wrate"] / st["wsum"] if st["wsum"] else None
    return {
        "id": p["id"], "name": p["name"], "kind": p["kind"], "lat": p["lat"], "lon": p["lon"],
        "district": dn.get(p["district_id"]),
        "price_from_vnd": p["price_from_vnd"], "price_to_vnd": p["price_to_vnd"],
        "rating": round(avg, 2) if avg is not None else None,
        "reviews_count": st["n"], "tag_counts": st["tags"],
        "commercial": bool(p["commercial"]),
        "empty": st["n"] == 0 and not st["tags"],
    }


def search_places(conn, q: str | None = None, bbox: tuple | None = None,
                  district_id: int | None = None, kind: str | None = None,
                  center: tuple[float, float] | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM places WHERE status='active'"
    args: list = []
    if bbox:
        sql += " AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?"
        args += [bbox[0], bbox[2], bbox[1], bbox[3]]  # s, w, n, e -> lat s..n, lon w..e
    if district_id:
        sql += " AND district_id=?"
        args.append(district_id)
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    rows = conn.execute(sql, args).fetchall()
    if q and fold(q):
        fq = fold(q)
        rows = [r for r in rows if fq in r["name_fold"]
                or any(fq in fold(a) for a in json.loads(r["aliases"]))]
    stats = _stats(conn, [r["id"] for r in rows])
    dn = _district_names(conn)
    items = []
    for r in rows:
        st = stats[r["id"]]
        avg = st["wrate"] / st["wsum"] if st["wsum"] else 0.0
        score = rank_score(avg, st["wsum"])
        dist = haversine_m(center[0], center[1], r["lat"], r["lon"]) if center else 0.0
        items.append((-score, dist, r["id"], _summary(r, st, dn)))
    items.sort(key=lambda x: x[:3])
    return [i[3] for i in items[:limit]]


def place_view(conn, place_id: int, has_access: bool, now: datetime,
               photo_url: Callable[[str], str] | None = None) -> dict | None:
    p = conn.execute("SELECT * FROM places WHERE id=? AND status='active'", (place_id,)).fetchone()
    if not p:
        return None
    st = _stats(conn, [place_id])[place_id]
    v = _summary(p, st, _district_names(conn))
    v["basics"] = json.loads(p["basics"])
    v["official_photos"] = json.loads(p["official_photos"])
    v["amenity_index"] = amenity_index(conn, p["lat"], p["lon"])
    v["tag_labels"] = {t: LABELS_RU.get(t, t) for t in v["tag_counts"]}
    if not has_access:
        v["locked"] = True
        return v
    pf = photo_url or (lambda n: n)
    revs = conn.execute(
        "SELECT id, text, tags, photos, created_at, weight FROM reviews "
        "WHERE place_id=? AND status='published' ORDER BY created_at DESC", (place_id,)).fetchall()
    v["paid"] = {
        "reviews": [{"id": r["id"], "text": r["text"], "tags": json.loads(r["tags"]),
                     "photo_urls": [pf(n) for n in json.loads(r["photos"])],
                     "created_at": r["created_at"],
                     "author_badge": "проверенный жилец" if r["weight"] >= 1.5 else None}
                    for r in revs],
        "signals": [{"source": s["source"], "tag": s["tag"], "count": s["count"], "url": s["url"]}
                    for s in conn.execute(
                        "SELECT source, tag, count, url FROM signals "
                        "WHERE place_id=? AND confirmed=1", (place_id,))],
        "amenities": amenity_list(conn, p["lat"], p["lon"]),
    }
    return v
