from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .access import grant, revoke_by_ref
from .config import Settings
from .tags import ALL_TAGS
from .textgeo import fold, haversine_m

MAX_CHARS = 5000


@dataclass
class ReviewDraft:
    text: str
    rating: int
    tags: list[str]
    lat: float
    lon: float
    accuracy_m: float
    photo_count: int
    exif_oldest_age_s: int | None = None


@dataclass
class History:
    user_times: list[datetime] = field(default_factory=list)        # все живые отзывы человека
    user_place_times: list[datetime] = field(default_factory=list)  # его отзывы на это место
    duplicate_text: bool = False


@dataclass
class Verdict:
    ok: bool
    reject_reason: str | None = None
    hold_reason: str | None = None


@dataclass
class ReviewResult:
    id: int | None
    status: str
    reward_days: int = 0
    reject_reason: str | None = None
    hold_reason: str | None = None


def text_hash(text: str) -> str:
    return hashlib.sha256(fold(text).encode()).hexdigest()


def validate_review(draft: ReviewDraft, place, history: History, cfg: Settings,
                    now: datetime) -> Verdict:
    def no(r: str) -> Verdict:
        return Verdict(False, reject_reason=r)

    if any(t not in ALL_TAGS for t in draft.tags):
        return no("bad_tag")
    n = len(draft.text.strip())
    if n < cfg.review_min_chars:
        return no("text_short")
    if len(draft.text) > MAX_CHARS:
        return no("text_long")
    if draft.photo_count < cfg.review_min_photos:
        return no("photos_few")
    if draft.photo_count > cfg.review_max_photos:
        return no("photos_many")
    if not (-90 <= draft.lat <= 90 and -180 <= draft.lon <= 180) or (draft.lat == 0 and draft.lon == 0):
        return no("bad_coords")
    if haversine_m(draft.lat, draft.lon, place["lat"], place["lon"]) > cfg.geo_radius_m:
        return no("too_far")
    day = timedelta(days=1)
    if sum(1 for t in history.user_times if now - t < day) >= cfg.review_daily_limit:
        return no("daily_limit")
    cd = timedelta(days=cfg.review_place_cooldown_days)
    if any(now - t < cd for t in history.user_place_times):
        return no("place_cooldown")
    holds = []
    if draft.accuracy_m > cfg.geo_max_accuracy_m:
        holds.append("low_accuracy")
    if draft.exif_oldest_age_s is not None and draft.exif_oldest_age_s > 600:
        holds.append("exif_stale")
    if history.duplicate_text:
        holds.append("duplicate_text")
    if place["status"] == "pending":
        holds.append("place_pending")
    return Verdict(True, hold_reason=",".join(holds) or None)


def author_weight(approved: int, days_since_first: int) -> float:
    return 1 + min(approved, 10) * 0.1 + min(days_since_first / 30, 3) * 0.1


def _weight_for(conn, user_id: int, now: datetime) -> float:
    r = conn.execute("SELECT COUNT(*) n, MIN(created_at) first FROM reviews "
                     "WHERE user_id=? AND status='published'", (user_id,)).fetchone()
    days = (now - datetime.fromisoformat(r["first"])).days if r["first"] else 0
    return author_weight(r["n"], days)


def _history(conn, user_id: int, place_id: int, thash: str) -> History:
    live = ("published", "held")
    q = lambda extra, args: [
        datetime.fromisoformat(r[0]) for r in conn.execute(
            f"SELECT created_at FROM reviews WHERE user_id=? AND status IN (?,?) {extra}",
            (user_id, *live, *args))]
    dup = conn.execute("SELECT 1 FROM reviews WHERE text_hash=? AND user_id<>? AND status<>'rejected' LIMIT 1",
                       (thash, user_id)).fetchone() is not None
    return History(q("", ()), q("AND place_id=?", (place_id,)), dup)


def save_review(conn: sqlite3.Connection, user_id: int, place_id: int, draft: ReviewDraft,
                photo_names: list[str], cfg: Settings, now: datetime) -> ReviewResult:
    conn.execute("BEGIN IMMEDIATE")
    try:
        place = conn.execute("SELECT * FROM places WHERE id=? AND status IN ('active','pending')",
                             (place_id,)).fetchone()
        if place is None:
            conn.execute("ROLLBACK")
            return ReviewResult(None, "rejected", reject_reason="no_place")
        th = text_hash(draft.text.strip())
        verdict = validate_review(draft, place, _history(conn, user_id, place_id, th), cfg, now)
        if not verdict.ok:
            conn.execute("ROLLBACK")
            return ReviewResult(None, "rejected", reject_reason=verdict.reject_reason)
        status = "held" if verdict.hold_reason else "published"
        weight = _weight_for(conn, user_id, now)
        cur = conn.execute(
            "INSERT INTO reviews(place_id, user_id, status, rating, text, tags, lat, lon, "
            "accuracy_m, photos, hold_reason, text_hash, weight, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (place_id, user_id, status, draft.rating, draft.text.strip(),
             json.dumps(draft.tags), draft.lat, draft.lon, draft.accuracy_m,
             json.dumps(photo_names), verdict.hold_reason, th, weight, now.isoformat()))
        rid = cur.lastrowid
        reward = 0
        if status == "published":
            grant(conn, user_id, cfg.review_reward_days, "review", f"review:{rid}", now)
            reward = cfg.review_reward_days
        conn.execute("COMMIT")
        return ReviewResult(rid, status, reward, hold_reason=verdict.hold_reason)
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def publish_review(conn: sqlite3.Connection, review_id: int, cfg: Settings, now: datetime) -> bool:
    """Одобрение удержанного отзыва. Награда выдаётся один раз (ref=review:id)."""
    r = conn.execute("SELECT user_id, status FROM reviews WHERE id=?", (review_id,)).fetchone()
    if r is None or r["status"] in ("published", "revoked"):
        return False
    weight = _weight_for(conn, r["user_id"], now)
    conn.execute("UPDATE reviews SET status='published', hold_reason=NULL, weight=? WHERE id=?",
                 (weight, review_id))
    grant(conn, r["user_id"], cfg.review_reward_days, "review", f"review:{review_id}", now)
    return True


def reject_review(conn, review_id: int, now: datetime) -> bool:
    r = conn.execute("SELECT status FROM reviews WHERE id=?", (review_id,)).fetchone()
    if r is None or r["status"] in ("rejected", "revoked"):
        return False
    conn.execute("UPDATE reviews SET status='rejected' WHERE id=?", (review_id,))
    revoke_by_ref(conn, f"review:{review_id}", now)
    return True


def revoke_review(conn, review_id: int, now: datetime) -> bool:
    r = conn.execute("SELECT status FROM reviews WHERE id=?", (review_id,)).fetchone()
    if r is None or r["status"] == "revoked":
        return False
    conn.execute("UPDATE reviews SET status='revoked' WHERE id=?", (review_id,))
    revoke_by_ref(conn, f"review:{review_id}", now)
    return True
