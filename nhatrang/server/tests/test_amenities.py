from app.amenities import CATEGORIES, amenity_index, amenity_list
from app.textgeo import haversine_m

LAT, LON = 12.2388, 109.1967


def _at(db, meters_north, cat="cafe", cheap=None):
    lat = LAT + meters_north / 111_000 * (1)  # приблизительно, ниже считаем точную дистанцию
    db.execute("INSERT INTO amenities(name, category, lat, lon, cheap_local) VALUES(?,?,?,?,?)",
               ("x", cat, lat, LON, cheap))
    return haversine_m(LAT, LON, lat, LON)


def test_radius_boundary(db):
    inside = _at(db, 395)
    outside = _at(db, 406)
    assert inside < 400 < outside
    assert amenity_index(db, LAT, LON)["cafe"] == 1


def test_empty_categories_zero(db):
    idx = amenity_index(db, LAT, LON)
    assert set(idx) == set(CATEGORIES) and all(v == 0 for v in idx.values())


def test_cheap_local_flag(db):
    _at(db, 100, "cafe", cheap=1)
    idx = amenity_index(db, LAT, LON)
    assert idx["cafe"] == 1 and idx["cheap_local"] == 1


def test_list_sorted(db):
    _at(db, 300)
    _at(db, 100)
    assert [a["distance_m"] for a in amenity_list(db, LAT, LON)] == sorted(
        a["distance_m"] for a in amenity_list(db, LAT, LON))
