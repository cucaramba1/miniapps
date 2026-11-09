import json
from datetime import datetime, timedelta, timezone

from tests.conftest import T0, make_place
from tools.import_csv import import_realtors_csv, import_signals_csv
from tools.import_listings import import_listings, match_place, parse_dt


def write(tmp_path, recs):
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"listings": recs}, ensure_ascii=False))
    return str(p)


def rec(**kw):
    base = {"id": "NT-1", "status": "new", "title": "Oceanus, 3 спальни", "price_vnd": 23_000_000,
            "bedrooms": 3, "district": "Север", "posted_at": (T0 - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
            "url": "https://t.me/x/1", "agent": "@agent"}
    base.update(kw)
    return base


def test_old_skipped_recent_kept(db, tmp_path):
    p = write(tmp_path, [rec(), rec(url="https://t.me/x/2", posted_at="2026-09-21 12:10")])
    assert import_listings(db, p, T0) == 1


def test_idempotent(db, tmp_path):
    p = write(tmp_path, [rec()])
    assert import_listings(db, p, T0) == 1
    assert import_listings(db, p, T0) == 0
    assert db.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 1


def test_rejected_imported_closed_and_contact_skipped(db, tmp_path):
    p = write(tmp_path, [rec(status="rejected", url="a"), rec(status="closed", url="b"),
                         rec(record_type="contact", url="c"), rec(url=None)])
    assert import_listings(db, p, T0) == 1


def test_weird_dates_fall_back_to_found_at(db, tmp_path):
    p = write(tmp_path, [rec(posted_at="1 месяц назад", found_at=(T0 - timedelta(days=1)).isoformat(), url="a"),
                         rec(posted_at="около часа назад", found_at=None, url="b"),
                         rec(posted_at=None, found_at=None, url="c")])
    assert import_listings(db, p, T0) == 1


def test_contacts_stored(db, tmp_path):
    import_listings(db, write(tmp_path, [rec()]), T0)
    c = json.loads(db.execute("SELECT contacts FROM listings").fetchone()[0])
    assert c["agent"] == "@agent" and c["url"] == "https://t.me/x/1"


def test_match_place_alias_and_ambiguity():
    one = [{"id": 1, "name": "Ocean Tower", "aliases": ["Oceanus"]}]
    assert match_place("Oceanus, 3 спальни", "", one) == 1
    two = one + [{"id": 2, "name": "Oceanus Villas", "aliases": ["Oceanus"]}]
    assert match_place("Oceanus, 3 спальни", "", two) is None
    assert match_place("Квартира у моря", "", one) is None
    assert match_place("Oceanusx tower", "", [{"id": 1, "name": "Oceanus", "aliases": []}]) is None


def test_listing_gets_place_link(db, tmp_path):
    pid = make_place(db, "Ocean Tower", aliases=["Oceanus"])
    import_listings(db, write(tmp_path, [rec()]), T0)
    assert db.execute("SELECT place_id FROM listings").fetchone()[0] == pid


def test_realtor_commission_needs_confirmation(db, tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("name,kind,languages,contacts,notes,commission_free_confirmed,confirmed_at\n"
                 'Анна,ru,ru;en,"{""tg"": ""@a""}",ок,1,\n'
                 'Борис,ru,ru,"{""tg"": ""@b""}",ок,1,2026-11-01\n'
                 'Вова,vi,vi,"{}",,0,\n')
    rep = import_realtors_csv(db, str(f))
    assert rep["added"] == 2 and len(rep["rejected"]) == 1
    rows = {r["name"]: r["commission_free_confirmed"] for r in db.execute("SELECT * FROM realtors")}
    assert rows == {"Борис": 1, "Вова": 0}


def test_signals_unconfirmed_not_counted(db, tmp_path, client, as_user):
    pid = make_place(db, "Hotel X")
    f = tmp_path / "s.csv"
    f.write_text("place,source,tag,count,url,confirmed\n"
                 "Hotel X,booking,noise,2,https://b/1,1\n"
                 "Hotel X,agoda,noise,9,https://a/1,0\n"
                 "Нет такого,booking,noise,1,u,1\n")
    rep = import_signals_csv(db, str(f))
    assert rep["added"] == 1 and rep["skipped_unconfirmed"] == ["Hotel X"] and len(rep["rejected"]) == 1
    v = client.get(f"/api/places/{pid}", headers=as_user(1)).json()
    assert v["tag_counts"] == {"noise": 2}


def test_load_districts_idempotent_and_validates(db, tmp_path, client, as_user):
    from tools.load_districts import load_districts
    f = tmp_path / "d.json"
    f.write_text(json.dumps([{"name_ru": "Район А", "geometry": {"type": "Polygon", "coordinates": [[[109, 12], [109.1, 12], [109.1, 12.1], [109, 12]]]}}]))
    assert load_districts(db, str(f)) == 1 and load_districts(db, str(f)) == 1
    assert db.execute("SELECT COUNT(*) FROM districts").fetchone()[0] == 1
    assert client.get("/api/districts", headers=as_user(1)).json()["features"][0]["properties"]["name_ru"] == "Район А"
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps([{"name_ru": " ", "geometry": {"type": "Point"}}]))
    import pytest
    with pytest.raises(ValueError):
        load_districts(db, str(bad))
    assert db.execute("SELECT COUNT(*) FROM districts").fetchone()[0] == 1


def test_point_districts_assign_nearest(db, tmp_path):
    from tools.load_districts import load_districts
    a = make_place(db, "A", lat=12.2450, lon=109.1960)
    b = make_place(db, "B", lat=12.2810, lon=109.2010)
    far = make_place(db, "Far", lat=12.40, lon=109.40)
    f = tmp_path / "d.json"
    f.write_text(json.dumps([
        {"name_ru": "Центр", "geometry": {"type": "Point", "coordinates": [109.196, 12.245]}},
        {"name_ru": "Север", "geometry": {"type": "Point", "coordinates": [109.2015, 12.2812]}}]))
    load_districts(db, str(f))
    d = {r["name"]: r["district_id"] for r in db.execute("SELECT name, district_id FROM places")}
    names = {r["id"]: r["name_ru"] for r in db.execute("SELECT * FROM districts")}
    assert names[d["A"]] == "Центр" and names[d["B"]] == "Север" and d["Far"] is None
