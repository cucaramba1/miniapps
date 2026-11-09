from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .access import access_until
from .auth import TgUser, current_user
from .config import Settings
from .deps import get_conn, get_now, get_settings
from .tags import COMPLAINTS, LABELS_RU, POSITIVE
from .places import _district_names, _stats, _summary

router = APIRouter(prefix="/api")

PALETTE = ["#e5484d", "#f76b15", "#ffb224", "#30a46c", "#12a594", "#0091ff", "#6e56cf", "#d6409f"]
MAX_FLAGS = 200


@router.get("/config")
def config(s: Settings = Depends(get_settings)):
    return {"tiles_url": s.tiles_url, "bot_username": s.bot_username,
            "review_min_chars": s.review_min_chars, "review_min_photos": s.review_min_photos,
            "review_max_photos": s.review_max_photos, "geo_radius_m": s.geo_radius_m,
            "review_reward_days": s.review_reward_days, "center": [12.2388, 109.1967],
            "tags": {"complaints": COMPLAINTS, "positive": POSITIVE, "labels": LABELS_RU}}


@router.get("/me")
def me(user: TgUser = Depends(current_user), conn=Depends(get_conn),
       now: datetime = Depends(get_now)):
    until = access_until(conn, user.id, now)
    n = conn.execute("SELECT COUNT(*) FROM reviews WHERE user_id=? AND status='published'",
                     (user.id,)).fetchone()[0]
    return {"id": user.id, "access_until": until.isoformat() if until else None,
            "has_access": until is not None, "reviews_published": n}


class FlagIn(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    category: str = Field(default="", max_length=20)
    color: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    place_id: int | None = None


def _flag(r) -> dict:
    return {k: r[k] for k in ("id", "label", "category", "color", "lat", "lon", "place_id")}


@router.get("/flags")
def list_flags(user: TgUser = Depends(current_user), conn=Depends(get_conn)):
    return [_flag(r) for r in conn.execute("SELECT * FROM flags WHERE user_id=? ORDER BY id", (user.id,))]


@router.post("/flags", status_code=201)
def add_flag(body: FlagIn, user: TgUser = Depends(current_user), conn=Depends(get_conn),
             now: datetime = Depends(get_now)):
    if body.color not in PALETTE:
        raise HTTPException(422, "color not in palette")
    n = conn.execute("SELECT COUNT(*) FROM flags WHERE user_id=?", (user.id,)).fetchone()[0]
    if n >= MAX_FLAGS:
        raise HTTPException(422, "too many flags")
    cur = conn.execute(
        "INSERT INTO flags(user_id, label, category, color, lat, lon, place_id, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (user.id, body.label, body.category, body.color, body.lat, body.lon, body.place_id,
         now.isoformat()))
    return {"id": cur.lastrowid, **body.model_dump()}


@router.delete("/flags/{flag_id}")
def del_flag(flag_id: int, user: TgUser = Depends(current_user), conn=Depends(get_conn)):
    cur = conn.execute("DELETE FROM flags WHERE id=? AND user_id=?", (flag_id, user.id))
    if cur.rowcount == 0:
        raise HTTPException(404)
    return {"ok": True}


@router.get("/favorites")
def list_favorites(user: TgUser = Depends(current_user), conn=Depends(get_conn)):
    rows = conn.execute(
        "SELECT p.* FROM favorites f JOIN places p ON p.id=f.place_id "
        "WHERE f.user_id=? AND p.status='active' ORDER BY f.created_at DESC", (user.id,)).fetchall()
    stats = _stats(conn, [r["id"] for r in rows])
    dn = _district_names(conn)
    return [_summary(r, stats[r["id"]], dn) for r in rows]


@router.put("/favorites/{place_id}")
def add_favorite(place_id: int, user: TgUser = Depends(current_user), conn=Depends(get_conn),
                 now: datetime = Depends(get_now)):
    if not conn.execute("SELECT 1 FROM places WHERE id=? AND status='active'", (place_id,)).fetchone():
        raise HTTPException(404)
    conn.execute("INSERT OR IGNORE INTO favorites(user_id, place_id, created_at) VALUES(?,?,?)",
                 (user.id, place_id, now.isoformat()))
    return {"ok": True}


@router.delete("/favorites/{place_id}")
def del_favorite(place_id: int, user: TgUser = Depends(current_user), conn=Depends(get_conn)):
    conn.execute("DELETE FROM favorites WHERE user_id=? AND place_id=?", (user.id, place_id))
    return {"ok": True}


@router.get("/districts")
def districts(user: TgUser = Depends(current_user), conn=Depends(get_conn)):
    feats = [{"type": "Feature", "geometry": json.loads(r["geojson"]),
              "properties": {"id": r["id"], "name_ru": r["name_ru"]}}
             for r in conn.execute("SELECT * FROM districts ORDER BY id")]
    return {"type": "FeatureCollection", "features": feats}
