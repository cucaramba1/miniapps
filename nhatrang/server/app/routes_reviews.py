from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .auth import TgUser, current_user
from .config import Settings
from .deps import get_conn, get_now, get_settings
from .photos import MAX_BYTES, NAME_RE, check_photo_sig, exif_age_s, store_photo
from .reviews import ReviewDraft, save_review

router = APIRouter(prefix="/api")


@router.post("/places/{place_id}/reviews", status_code=201)
async def post_review(
    place_id: int,
    text: Annotated[str, Form()],
    rating: Annotated[int, Form(ge=1, le=5)],
    lat: Annotated[float, Form()],
    lon: Annotated[float, Form()],
    accuracy_m: Annotated[float, Form()],
    tags: Annotated[list[str], Form()] = [],
    photos: Annotated[list[UploadFile], File()] = [],
    user: TgUser = Depends(current_user),
    conn=Depends(get_conn),
    now: datetime = Depends(get_now),
    s: Settings = Depends(get_settings),
):
    if len(photos) > s.review_max_photos:
        return JSONResponse({"reason": "photos_many"}, status_code=422)
    names, ages = [], []
    for f in photos:
        data = await f.read(MAX_BYTES + 1)
        try:
            names.append(store_photo(data, s.photos_dir))
        except ValueError:
            return JSONResponse({"reason": "bad_photo"}, status_code=422)
        a = exif_age_s(data, now)
        if a is not None:
            ages.append(a)
    draft = ReviewDraft(text=text, rating=rating, tags=tags, lat=lat, lon=lon,
                        accuracy_m=accuracy_m, photo_count=len(set(names)),
                        exif_oldest_age_s=max(ages) if ages else None)
    res = save_review(conn, user.id, place_id, draft, sorted(set(names)), s, now)
    if res.status == "rejected":
        code = 404 if res.reject_reason == "no_place" else 422
        return JSONResponse({"reason": res.reject_reason}, status_code=code)
    return {"id": res.id, "status": res.status, "reward_days": res.reward_days,
            "hold_reason": res.hold_reason}


@router.post("/reviews/{review_id}/report")
def report_review(review_id: int, user: TgUser = Depends(current_user), conn=Depends(get_conn),
                  now: datetime = Depends(get_now)):
    r = conn.execute("SELECT status FROM reviews WHERE id=?", (review_id,)).fetchone()
    if r is None:
        raise HTTPException(404)
    conn.execute("INSERT OR IGNORE INTO review_reports(review_id, user_id, created_at) VALUES(?,?,?)",
                 (review_id, user.id, now.isoformat()))
    if r["status"] == "published":
        conn.execute("UPDATE reviews SET status='held', hold_reason='reported' WHERE id=?",
                     (review_id,))
    return {"ok": True}


@router.get("/photos/{name}")
def get_photo(name: str, u: int, e: int, s: str, request: Request):
    cfg: Settings = request.app.state.settings
    now = int(request.app.state.clock().timestamp())
    if not NAME_RE.match(name) or not check_photo_sig(name, u, e, s, cfg.photo_sign_secret, now):
        raise HTTPException(403)
    path = f"{cfg.photos_dir}/{name}"
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=300"})
