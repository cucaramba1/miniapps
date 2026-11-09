from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends

from .access import has_access
from .auth import TgUser, current_user
from .deps import get_conn, get_now
from .places import _district_names, _stats, _summary
from .textgeo import fold

router = APIRouter(prefix="/api")


@router.get("/realtors")
def realtors(user: TgUser = Depends(current_user), conn=Depends(get_conn),
             now: datetime = Depends(get_now)):
    ok = has_access(conn, user.id, now)
    out = []
    for r in conn.execute("SELECT * FROM realtors ORDER BY commission_free_confirmed DESC, name"):
        item = {"id": r["id"], "name": r["name"], "kind": r["kind"],
                "languages": json.loads(r["languages"]),
                "commission_free_confirmed": bool(r["commission_free_confirmed"]),
                "notes": r["notes"]}
        if ok:
            item["contacts"] = json.loads(r["contacts"])
        else:
            item["locked"] = True
        out.append(item)
    return out


@router.get("/listings")
def listings(district: str | None = None, bedrooms: int | None = None,
             max_price: int | None = None, only_with_place: int = 0,
             user: TgUser = Depends(current_user), conn=Depends(get_conn),
             now: datetime = Depends(get_now)):
    ok = has_access(conn, user.id, now)
    sql = "SELECT * FROM listings WHERE expires_at > ?"
    args: list = [now.isoformat()]
    if bedrooms is not None:
        sql += " AND bedrooms=?"
        args.append(bedrooms)
    if max_price is not None:
        sql += " AND price_vnd<=?"
        args.append(max_price)
    if only_with_place:
        sql += " AND place_id IS NOT NULL"
    sql += " ORDER BY posted_at DESC, id DESC"
    rows = conn.execute(sql, args).fetchall()
    if district:
        fd = fold(district)
        rows = [r for r in rows if fd in fold(r["district_text"])]
    pids = [r["place_id"] for r in rows if r["place_id"]]
    places = {p["id"]: p for p in conn.execute(
        f"SELECT * FROM places WHERE status='active' AND id IN ({','.join('?' * len(pids))})",
        pids)} if pids else {}
    stats = _stats(conn, list(places))
    dn = _district_names(conn)
    out = []
    for r in rows:
        item = {"id": r["id"], "title": r["title"], "price_vnd": r["price_vnd"],
                "bedrooms": r["bedrooms"], "district_text": r["district_text"],
                "posted_at": r["posted_at"], "place_id": r["place_id"],
                "place_summary": None, "chats_count": r["chats_count"]}
        p = places.get(r["place_id"])
        if p:
            s = _summary(p, stats[p["id"]], dn)
            item["place_summary"] = {"name": s["name"], "rating": s["rating"],
                                     "reviews_count": s["reviews_count"],
                                     "tag_counts": s["tag_counts"]}
        if ok:
            item["contacts"] = json.loads(r["contacts"])
        else:
            item["locked"] = True
        out.append(item)
    return out
