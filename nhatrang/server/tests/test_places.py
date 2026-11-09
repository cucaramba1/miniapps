import json
from tests.conftest import give_access, make_place, make_review, make_user
from app.places import rank_score

SECRET_TEXT = "УНИКАЛЬНЫЙ_ТЕКСТ_ОТЗЫВА_xyz"


def test_search_diacritics(client, db, as_user):
    make_place(db, "Vĩnh Hải Hotel")
    r = client.get("/api/places", params={"q": "vinh hai"}, headers=as_user(1))
    assert [p["name"] for p in r.json()] == ["Vĩnh Hải Hotel"]


def test_search_by_alias(client, db, as_user):
    make_place(db, "Ocean Tower", aliases=["Oceanus"])
    r = client.get("/api/places", params={"q": "oceanus"}, headers=as_user(1))
    assert len(r.json()) == 1


def test_pending_not_listed_or_viewable(client, db, as_user):
    pid = make_place(db, "Hidden", status="pending")
    assert client.get("/api/places", headers=as_user(1)).json() == []
    assert client.get(f"/api/places/{pid}", headers=as_user(1)).status_code == 404


def test_paid_text_not_leaked_without_access(client, db, as_user):
    pid = make_place(db)
    make_review(db, pid, text=SECRET_TEXT, photos=["aaaaaaaaaaaaaaaa.jpg"])
    for url in ("/api/places", f"/api/places/{pid}"):
        r = client.get(url, headers=as_user(2))
        assert SECRET_TEXT not in r.text and "aaaaaaaaaaaaaaaa" not in r.text
    assert '"paid"' not in client.get(f"/api/places/{pid}", headers=as_user(2)).text
    assert client.get(f"/api/places/{pid}", headers=as_user(2)).json()["locked"] is True


def test_paid_text_visible_with_access(client, db, as_user):
    pid = make_place(db)
    make_review(db, pid, text=SECRET_TEXT, photos=["aaaaaaaaaaaaaaaa.jpg"])
    give_access(db, 2)
    r = client.get(f"/api/places/{pid}", headers=as_user(2))
    assert SECRET_TEXT in r.text
    assert "/api/photos/aaaaaaaaaaaaaaaa.jpg?u=2" in r.text


def test_tag_counts_reviews_and_confirmed_signals(client, db, as_user):
    pid = make_place(db)
    make_review(db, pid, user_id=1, tags=["noise"])
    make_review(db, pid, user_id=2, tags=["noise", "clean"])
    make_review(db, pid, user_id=3, tags=["noise"], status="held")
    db.execute("INSERT INTO signals(place_id, source, tag, count, confirmed) VALUES(?,?,?,?,1)",
               (pid, "booking", "noise", 1))
    db.execute("INSERT INTO signals(place_id, source, tag, count, confirmed) VALUES(?,?,?,?,0)",
               (pid, "agoda", "noise", 5))
    v = client.get(f"/api/places/{pid}", headers=as_user(9)).json()
    assert v["tag_counts"] == {"noise": 3, "clean": 1}
    assert v["reviews_count"] == 2


def test_empty_place(client, db, as_user):
    pid = make_place(db)
    v = client.get(f"/api/places/{pid}", headers=as_user(1)).json()
    assert v["empty"] is True and v["rating"] is None


def test_commercial_does_not_affect_order(client, db, as_user):
    a = make_place(db, "A", commercial=0)
    b = make_place(db, "B", commercial=1)
    for pid, u in ((a, 1), (b, 2)):
        make_review(db, pid, user_id=u, rating=4)
    order1 = [p["id"] for p in client.get("/api/places", headers=as_user(9)).json()]
    db.execute("UPDATE places SET commercial=1-commercial")
    order2 = [p["id"] for p in client.get("/api/places", headers=as_user(9)).json()]
    assert order1 == order2


def test_ranking_prefers_better_reviewed(client, db, as_user):
    a = make_place(db, "Low")
    b = make_place(db, "High")
    make_review(db, a, user_id=1, rating=2)
    make_review(db, b, user_id=2, rating=5)
    ids = [p["id"] for p in client.get("/api/places", headers=as_user(9)).json()]
    assert ids == [b, a]


def test_script_name_returned_raw(client, db, as_user):
    pid = make_place(db, "<script>alert(1)</script>")
    assert client.get(f"/api/places/{pid}", headers=as_user(1)).json()["name"] == "<script>alert(1)</script>"


def test_rank_score_monotonic_and_bounded():
    assert rank_score(5, 10) > rank_score(4, 10)
    assert rank_score(4.5, 10) > rank_score(4.5, 2) > 3.5
    for avg in (1, 5):
        for w in (0, 1, 100):
            assert 1 <= rank_score(avg, w) <= 5
