from datetime import timedelta

from app.access import access_until
from tests.conftest import T0, give_access, make_place, make_review, make_user

SECRET = {"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"}
ADMIN = 999


def upd(client, update, headers=SECRET):
    return client.post("/api/bot/webhook", json=update, headers=headers)


def cmd(uid, text):
    return {"message": {"from": {"id": uid}, "chat": {"id": uid}, "text": text}}


def cb(uid, data):
    return {"callback_query": {"id": "cb1", "from": {"id": uid}, "data": data}}


def test_webhook_needs_secret(client):
    assert upd(client, cmd(ADMIN, "/stats"), headers={}).status_code == 403
    assert upd(client, cmd(ADMIN, "/stats"), headers={"X-Telegram-Bot-Api-Secret-Token": "x"}).status_code == 403


def test_non_admin_silent(client, bot, db):
    place = make_place(db, status="pending")
    for c in ("/queue", "/stats", "/revoke 1", "/grant 1 3", "/refund abc"):
        upd(client, cmd(5, c))
    assert bot.calls == []


def test_queue_shows_pending_place(client, bot, db):
    pid = make_place(db, "Новый отель", status="pending")
    upd(client, cmd(ADMIN, "/queue"))
    sent = bot.named("send_message")[0]
    assert "Новый отель" in sent["text"]
    assert sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"ok:place:{pid}"


def test_approve_place_publishes_held_review_once(client, bot, db):
    pid = make_place(db, status="pending")
    make_user(db, 7)
    rid = make_review(db, pid, user_id=7, status="held", hold_reason="place_pending")
    upd(client, cb(ADMIN, f"ok:place:{pid}"))
    upd(client, cb(ADMIN, f"ok:place:{pid}"))  # повторное нажатие
    assert db.execute("SELECT status FROM places WHERE id=?", (pid,)).fetchone()[0] == "active"
    assert db.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0] == "published"
    assert db.execute("SELECT COUNT(*) FROM entitlements WHERE user_id=7").fetchone()[0] == 1


def test_approve_place_leaves_multi_reason_review_held(client, db):
    pid = make_place(db, status="pending")
    rid = make_review(db, pid, user_id=7, status="held", hold_reason="exif_stale,place_pending")
    upd(client, cb(ADMIN, f"ok:place:{pid}"))
    assert db.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0] == "held"


def test_reject_place_no_reward(client, db):
    pid = make_place(db, status="pending")
    rid = make_review(db, pid, user_id=7, status="held", hold_reason="place_pending")
    upd(client, cb(ADMIN, f"no:place:{pid}"))
    assert db.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0] == "rejected"
    assert db.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 0


def test_callback_from_non_admin_ignored(client, db):
    pid = make_place(db, status="pending")
    upd(client, cb(5, f"ok:place:{pid}"))
    assert db.execute("SELECT status FROM places WHERE id=?", (pid,)).fetchone()[0] == "pending"


def test_revoke_recomputes_access(client, db, clock):
    pid = make_place(db)
    from app.reviews import ReviewDraft, save_review
    from app.config import Settings
    rid = make_review(db, pid, user_id=7)
    from app.access import grant
    grant(db, 7, 3, "review", f"review:{rid}", T0)
    assert access_until(db, 7, T0) == T0 + timedelta(days=3)
    upd(client, cmd(ADMIN, f"/revoke {rid}"))
    assert access_until(db, 7, T0) is None
    assert db.execute("SELECT status FROM reviews WHERE id=?", (rid,)).fetchone()[0] == "revoked"


def test_grant_command(client, db):
    make_user(db, 8)
    upd(client, cmd(ADMIN, "/grant 8 5"))
    assert access_until(db, 8, T0) == T0 + timedelta(days=5)


def test_add_place_pending_hidden(client, db, as_user):
    r = client.post("/api/places", headers=as_user(3),
                    json={"name": "Новый Хостел", "kind": "hostel", "lat": 12.24, "lon": 109.19})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert client.get("/api/places", headers=as_user(3)).json() == []


def test_add_place_duplicate_409(client, db, as_user):
    existing = make_place(db, "Vĩnh Hải Hotel", lat=12.24, lon=109.19)
    r = client.post("/api/places", headers=as_user(3),
                    json={"name": "vinh hai hotel", "kind": "hotel", "lat": 12.24001, "lon": 109.19001})
    assert r.status_code == 409 and r.json()["existing_id"] == existing


def test_add_place_bad_input(client, as_user):
    h = as_user(3)
    assert client.post("/api/places", headers=h, json={"name": "x", "kind": "hotel", "lat": 1, "lon": 1}).status_code == 422
    assert client.post("/api/places", headers=h, json={"name": "Ok name", "kind": "castle", "lat": 12, "lon": 109}).status_code == 422
    assert client.post("/api/places", headers=h, json={"name": "Ok name", "kind": "hotel", "lat": 0, "lon": 0}).status_code == 422


def test_pending_places_cap(client, as_user):
    h = as_user(3)
    codes = [client.post("/api/places", headers=h,
                         json={"name": f"Place {i}", "kind": "hotel", "lat": 12 + i * 0.01, "lon": 109}).status_code
             for i in range(6)]
    assert codes == [201] * 5 + [429]
