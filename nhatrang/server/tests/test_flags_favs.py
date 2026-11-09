from tests.conftest import make_place

FLAG = {"label": "Хороший кофе", "category": "кафе", "color": "#30a46c", "lat": 12.24, "lon": 109.19}


def test_flags_isolated(client, as_user):
    fid = client.post("/api/flags", json=FLAG, headers=as_user(1)).json()["id"]
    assert client.get("/api/flags", headers=as_user(2)).json() == []
    assert client.delete(f"/api/flags/{fid}", headers=as_user(2)).status_code == 404
    assert len(client.get("/api/flags", headers=as_user(1)).json()) == 1
    assert client.delete(f"/api/flags/{fid}", headers=as_user(1)).status_code == 200


def test_flag_bad_color(client, as_user):
    assert client.post("/api/flags", json={**FLAG, "color": "#000000"}, headers=as_user(1)).status_code == 422


def test_flag_limits(client, as_user):
    assert client.post("/api/flags", json={**FLAG, "label": "x" * 41}, headers=as_user(1)).status_code == 422
    assert client.post("/api/flags", json={**FLAG, "category": "x" * 21}, headers=as_user(1)).status_code == 422
    for _ in range(200):
        assert client.post("/api/flags", json=FLAG, headers=as_user(1)).status_code == 201
    assert client.post("/api/flags", json=FLAG, headers=as_user(1)).status_code == 422


def test_flag_html_label_raw(client, as_user):
    r = client.post("/api/flags", json={**FLAG, "label": "<b>x</b>"}, headers=as_user(1))
    assert client.get("/api/flags", headers=as_user(1)).json()[0]["label"] == "<b>x</b>"


def test_favorites_idempotent(client, db, as_user):
    pid = make_place(db)
    for _ in range(2):
        assert client.put(f"/api/favorites/{pid}", headers=as_user(1)).status_code == 200
    assert len(client.get("/api/favorites", headers=as_user(1)).json()) == 1
    assert client.get("/api/favorites", headers=as_user(2)).json() == []
    client.delete(f"/api/favorites/{pid}", headers=as_user(1))
    client.delete(f"/api/favorites/{pid}", headers=as_user(1))
    assert client.get("/api/favorites", headers=as_user(1)).json() == []


def test_favorite_unknown_place(client, as_user):
    assert client.put("/api/favorites/999", headers=as_user(1)).status_code == 404


def test_districts_empty_then_geojson(client, db, as_user):
    d = client.get("/api/districts", headers=as_user(1)).json()
    assert d == {"type": "FeatureCollection", "features": []}
    db.execute("INSERT INTO districts(name_ru, geojson) VALUES(?,?)",
               ("Тест", '{"type":"Polygon","coordinates":[[[109,12],[109.1,12],[109.1,12.1],[109,12]]]}'))
    f = client.get("/api/districts", headers=as_user(1)).json()["features"][0]
    assert f["properties"]["name_ru"] == "Тест" and f["geometry"]["type"] == "Polygon"


def test_config_public_values(client, as_user):
    c = client.get("/api/config", headers=as_user(1)).json()
    assert c["review_min_chars"] == 150 and c["review_min_photos"] == 2 and c["geo_radius_m"] == 150
