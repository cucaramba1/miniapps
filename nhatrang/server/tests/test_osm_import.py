import json
from pathlib import Path

from tools.osm_import import parse_overpass, upsert

FX = json.loads((Path(__file__).parent / "fixtures" / "overpass_sample.json").read_text())


def test_parse_categories():
    b = parse_overpass(FX)
    assert {p["osm_id"] for p in b.places} == {"node/1", "way/2"}
    assert {a["category"] for a in b.amenities} == {"pharmacy", "massage", "fruit"}


def test_skips_no_coords_no_name_irrelevant():
    b = parse_overpass(FX)
    ids = {p["osm_id"] for p in b.places} | {a["osm_id"] for a in b.amenities}
    assert "node/3" not in ids and "node/7" not in ids and "node/8" not in ids


def test_way_center_used():
    p = next(p for p in parse_overpass(FX).places if p["osm_id"] == "way/2")
    assert (p["lat"], p["lon"]) == (12.24, 109.19)


def test_quotes_emoji_preserved_and_alias(db):
    upsert(db, parse_overpass(FX))
    r = db.execute("SELECT name, aliases FROM places WHERE osm_id='node/1'").fetchone()
    assert r["name"] == 'Vĩnh Hải "Sunrise" 🌅'
    assert json.loads(r["aliases"]) == ["Vinh Hai Sunrise"]


def test_idempotent_and_keeps_moderation(db):
    c1 = upsert(db, parse_overpass(FX))
    db.execute("UPDATE places SET commercial=1, price_from_vnd=500000 WHERE osm_id='node/1'")
    c2 = upsert(db, parse_overpass(FX))
    assert c1["places_new"] == 2 and c2["places_new"] == 0 and c2["places_updated"] == 2
    assert db.execute("SELECT COUNT(*) FROM places").fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM amenities").fetchone()[0] == 3
    r = db.execute("SELECT commercial, price_from_vnd FROM places WHERE osm_id='node/1'").fetchone()
    assert (r[0], r[1]) == (1, 500000)
