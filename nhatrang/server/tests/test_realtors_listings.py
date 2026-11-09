import json
from datetime import timedelta

from tests.conftest import T0, give_access, make_place, make_review

NICK = "@secret_realtor_nick"
ZALO = "0909123456"
URL = "https://facebook.com/groups/x/posts/777"


def add_realtor(db, **kw):
    db.execute("INSERT INTO realtors(name, kind, languages, notes, contacts, "
               "commission_free_confirmed) VALUES(?,?,?,?,?,?)",
               (kw.get("name", "Анна"), "ru", '["ru"]', "заметка",
                json.dumps({"tg": NICK, "zalo": ZALO}), kw.get("cf", 0)))


def add_listing(db, title="Квартира", price=9_000_000, bedrooms=1, district="Vĩnh Hải",
                place_id=None, days_left=5, url=URL, posted=None):
    db.execute("INSERT INTO listings(source_url, title, price_vnd, bedrooms, district_text, "
               "posted_at, place_id, contacts, expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
               (url, title, price, bedrooms, district, posted or T0.isoformat(), place_id,
                json.dumps({"agent": NICK, "url": URL}),
                (T0 + timedelta(days=days_left)).isoformat()))


def test_realtors_locked_without_access(client, db, as_user):
    add_realtor(db)
    r = client.get("/api/realtors", headers=as_user(1))
    assert NICK not in r.text and ZALO not in r.text
    assert r.json()[0]["locked"] is True and "contacts" not in r.json()[0]


def test_realtors_with_access(client, db, as_user):
    add_realtor(db)
    give_access(db, 1)
    assert NICK in client.get("/api/realtors", headers=as_user(1)).text


def test_commission_free_default_false(client, db, as_user):
    add_realtor(db)
    assert client.get("/api/realtors", headers=as_user(1)).json()[0]["commission_free_confirmed"] is False
    # публичного API на изменение нет
    assert client.post("/api/realtors", headers=as_user(1), json={}).status_code in (404, 405)
    assert client.put("/api/realtors/1", headers=as_user(1), json={}).status_code in (404, 405)


def test_listings_locked(client, db, as_user):
    add_listing(db)
    r = client.get("/api/listings", headers=as_user(1))
    assert NICK not in r.text and URL not in r.text and "facebook" not in r.text
    assert r.json()[0]["locked"] is True


def test_listings_unlocked(client, db, as_user):
    add_listing(db)
    give_access(db, 1)
    r = client.get("/api/listings", headers=as_user(1))
    assert NICK in r.text and URL in r.text


def test_expired_hidden(client, db, as_user):
    add_listing(db, days_left=-1, url="u1")
    add_listing(db, days_left=3, url="u2")
    assert len(client.get("/api/listings", headers=as_user(1)).json()) == 1


def test_filters(client, db, as_user):
    add_listing(db, bedrooms=1, price=8_000_000, url="a", district="Vĩnh Hải")
    add_listing(db, bedrooms=2, price=15_000_000, url="b", district="Xương Huân")
    g = lambda **p: client.get("/api/listings", params=p, headers=as_user(1)).json()
    assert len(g(bedrooms=2)) == 1 and g(bedrooms=2)[0]["bedrooms"] == 2
    assert len(g(max_price=10_000_000)) == 1
    assert len(g(district="vinh hai")) == 1


def test_only_with_place(client, db, as_user):
    pid = make_place(db, "Oceanus")
    make_review(db, pid, tags=["noise"])
    add_listing(db, place_id=pid, url="a")
    add_listing(db, place_id=None, url="b")
    g = lambda **p: client.get("/api/listings", params=p, headers=as_user(1)).json()
    assert len(g()) == 2 and len(g(only_with_place=1)) == 1
    summ = g(only_with_place=1)[0]["place_summary"]
    assert summ["tag_counts"] == {"noise": 1}
    assert "text" not in json.dumps(summ)
