from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .auth import TgUser, current_user
from .bot import Ctx, handle_update
from .config import Settings
from .db import connect
from .deps import get_conn, get_now, get_settings
from .textgeo import bbox_around, fold, haversine_m

router = APIRouter(prefix="/api")
log = logging.getLogger("webhook")
KINDS = {"hotel", "guest_house", "apartment", "hostel", "other"}
MAX_PENDING_PER_USER = 5


class NewPlace(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: str
    lat: float
    lon: float


@router.post("/places", status_code=201)
def add_place(body: NewPlace, user: TgUser = Depends(current_user), conn=Depends(get_conn),
              now: datetime = Depends(get_now)):
    if body.kind not in KINDS:
        raise HTTPException(422, "bad kind")
    if not (-90 <= body.lat <= 90 and -180 <= body.lon <= 180) or (body.lat == 0 and body.lon == 0):
        raise HTTPException(422, "bad coords")
    name = body.name.strip()
    s, n, w, e = bbox_around(body.lat, body.lon, 50)
    for r in conn.execute("SELECT id, lat, lon FROM places WHERE name_fold=? AND status<>'rejected' "
                          "AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?", (fold(name), s, n, w, e)):
        if haversine_m(body.lat, body.lon, r["lat"], r["lon"]) <= 50:
            return JSONResponse({"detail": "duplicate", "existing_id": r["id"]}, status_code=409)
    pending = conn.execute("SELECT COUNT(*) FROM places WHERE created_by=? AND status='pending'",
                           (user.id,)).fetchone()[0]
    if pending >= MAX_PENDING_PER_USER:
        raise HTTPException(429, "too many pending places")
    cur = conn.execute(
        "INSERT INTO places(name, name_fold, kind, lat, lon, status, created_by, created_at) "
        "VALUES(?,?,?,?,?,'pending',?,?)",
        (name, fold(name), body.kind, body.lat, body.lon, user.id, now.isoformat()))
    return {"id": cur.lastrowid, "status": "pending"}


@router.post("/bot/webhook")
async def webhook(request: Request):
    s: Settings = request.app.state.settings
    if request.headers.get("x-telegram-bot-api-secret-token") != s.webhook_secret:
        raise HTTPException(403)
    update = await request.json()
    _process(request, update)
    return {"ok": True}


def _process(request: Request, update: dict) -> None:
    app = request.app
    conn = connect(app.state.settings.db_path)
    try:
        ctx = Ctx(conn, app.state.settings, app.state.bot, app.state.clock())
        handle_update(update, ctx)
    except Exception:
        # Telegram будет ретраить на не-200; ошибку пишем в лог, ответ всегда 200
        log.exception("update failed")
    finally:
        conn.close()
