from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from .access import has_access
from .auth import TgUser, current_user
from .config import Settings
from .deps import get_conn, get_now, get_settings
from .photos import sign_photo_url
from .places import place_view, search_places

router = APIRouter(prefix="/api")


@router.get("/places")
def list_places(q: str | None = None, bbox: str | None = None, district_id: int | None = None,
                kind: str | None = None, lat: float | None = None, lon: float | None = None,
                limit: int = 50, user: TgUser = Depends(current_user), conn=Depends(get_conn)):
    bb = None
    if bbox:
        try:
            bb = tuple(float(x) for x in bbox.split(","))
            assert len(bb) == 4
        except (ValueError, AssertionError):
            raise HTTPException(422, "bbox = south,west,north,east")
    center = (lat, lon) if lat is not None and lon is not None else None
    return search_places(conn, q, bb, district_id, kind, center, max(1, min(limit, 200)))


@router.get("/places/{place_id}")
def get_place(place_id: int, user: TgUser = Depends(current_user), conn=Depends(get_conn),
              now: datetime = Depends(get_now), s: Settings = Depends(get_settings)):
    ok = has_access(conn, user.id, now)
    exp = int(now.timestamp()) + s.photo_url_ttl_s
    v = place_view(conn, place_id, ok, now,
                   photo_url=lambda n: sign_photo_url(n, user.id, exp, s.photo_sign_secret))
    if v is None:
        raise HTTPException(404, "place not found")
    return v
