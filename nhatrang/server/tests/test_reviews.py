import io
import threading
from datetime import timedelta

import pytest
from PIL import Image

from app.access import access_until
from app.db import connect
from app.reviews import (History, ReviewDraft, author_weight, publish_review, save_review,
                         validate_review)
from tests.conftest import T0, give_access, make_place, make_review, make_user

PLACE = {"lat": 12.2388, "lon": 109.1967, "status": "active"}
TEXT = "а" * 150


def draft(**kw):
    d = dict(text=TEXT, rating=4, tags=[], lat=PLACE["lat"], lon=PLACE["lon"], accuracy_m=10,
             photo_count=2, exif_oldest_age_s=None)
    d.update(kw)
    return ReviewDraft(**d)


def check(cfg, d=None, hist=None, place=PLACE, now=T0):
    return validate_review(d or draft(), place, hist or History(), cfg, now)


def test_text_length(settings):
    assert check(settings, draft(text="а" * 149)).reject_reason == "text_short"
    assert check(settings, draft(text="а" * 150)).ok
    assert check(settings, draft(text=" " * 150)).reject_reason == "text_short"
    assert check(settings, draft(text="  " + "а" * 149)).reject_reason == "text_short"


def test_photos(settings):
    assert check(settings, draft(photo_count=1)).reject_reason == "photos_few"
    assert check(settings, draft(photo_count=6)).reject_reason == "photos_many"


def test_geo_boundary(settings):
    from app.textgeo import haversine_m
    lat2 = PLACE["lat"] + 0.00135
    d = haversine_m(PLACE["lat"], PLACE["lon"], lat2, PLACE["lon"])
    settings.geo_radius_m = d
    assert check(settings, draft(lat=lat2)).ok  # ровно по границе проходит
    settings.geo_radius_m = d - 0.1
    assert check(settings, draft(lat=lat2)).reject_reason == "too_far"


def test_bad_coords(settings):
    assert check(settings, draft(lat=0, lon=0)).reject_reason == "bad_coords"
    assert check(settings, draft(lat=95, lon=10)).reject_reason == "bad_coords"


def test_daily_limit(settings):
    h = History(user_times=[T0 - timedelta(hours=3)])
    assert check(settings, hist=h).reject_reason == "daily_limit"
    h = History(user_times=[T0 - timedelta(hours=25)])
    assert check(settings, hist=h).ok


def test_place_cooldown(settings):
    assert check(settings, hist=History(user_times=[T0 - timedelta(days=13)],
                                        user_place_times=[T0 - timedelta(days=13)])
                 ).reject_reason == "place_cooldown"
    assert check(settings, hist=History(user_times=[T0 - timedelta(days=14)],
                                        user_place_times=[T0 - timedelta(days=14)])).ok


def test_other_place_next_day_ok(settings):
    h = History(user_times=[T0 - timedelta(days=1, hours=1)], user_place_times=[])
    assert check(settings, hist=h).ok


def test_soft_holds(settings):
    v = check(settings, draft(accuracy_m=500))
    assert v.ok and v.hold_reason == "low_accuracy"
    v = check(settings, draft(exif_oldest_age_s=3600))
    assert v.ok and v.hold_reason == "exif_stale"
    v = check(settings, hist=History(duplicate_text=True))
    assert v.hold_reason == "duplicate_text"
    v = check(settings, place={**PLACE, "status": "pending"})
    assert v.hold_reason == "place_pending"


def test_bad_tag(settings):
    assert check(settings, draft(tags=["nonsense"])).reject_reason == "bad_tag"


def test_author_weight():
    assert author_weight(0, 0) == 1
    assert author_weight(1, 0) < author_weight(5, 0) < author_weight(5, 60)
    assert author_weight(999, 9999) == pytest.approx(2.3)


# ---- интеграция save_review ----

def test_save_published_gives_reward(db, settings):
    pid = make_place(db)
    make_user(db, 1)
    res = save_review(db, 1, pid, draft(), ["a.jpg", "b.jpg"], settings, T0)
    assert res.status == "published" and res.reward_days == 3
    assert access_until(db, 1, T0) == T0 + timedelta(days=3)


def test_held_no_reward_until_approved_once(db, settings):
    pid = make_place(db)
    make_user(db, 1)
    res = save_review(db, 1, pid, draft(accuracy_m=999), ["a.jpg", "b.jpg"], settings, T0)
    assert res.status == "held" and access_until(db, 1, T0) is None
    assert publish_review(db, res.id, settings, T0) is True
    assert publish_review(db, res.id, settings, T0) is False
    assert access_until(db, 1, T0) == T0 + timedelta(days=3)
    assert db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 1


def test_long_emoji_text_roundtrip(db, settings):
    pid = make_place(db)
    make_user(db, 1)
    txt = ("Отлично 😀🏖️ " * 300)[:3000]
    res = save_review(db, 1, pid, draft(text=txt), ["a.jpg", "b.jpg"], settings, T0)
    assert res.status == "published"
    assert db.execute("SELECT text FROM reviews WHERE id=?", (res.id,)).fetchone()[0] == txt.strip()


def test_parallel_reviews_one_wins(settings, app):
    setup = connect(settings.db_path)
    pid = make_place(setup)
    make_user(setup, 1)
    setup.close()
    results = []

    def run():
        c = connect(settings.db_path)
        results.append(save_review(c, 1, pid, draft(), ["a.jpg", "b.jpg"], settings, T0))
        c.close()

    ts = [threading.Thread(target=run) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(r.status for r in results) == ["published", "rejected"]


def test_duplicate_text_from_other_user_held(db, settings):
    pid = make_place(db)
    make_review(db, pid, user_id=5, text=TEXT)
    make_user(db, 1)
    res = save_review(db, 1, pid, draft(), ["a.jpg", "b.jpg"], settings, T0)
    assert res.status == "held" and "duplicate_text" in res.hold_reason
