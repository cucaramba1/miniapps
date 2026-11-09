from app.textgeo import fold, haversine_m


def test_fold():
    assert fold("Vĩnh Hải") == "vinh hai"
    assert fold("Đường  Trần Phú") == "duong tran phu"
    assert fold("Ёлка") == "елка"


def test_haversine():
    d = haversine_m(12.0, 109.0, 12.001, 109.0)
    assert abs(d - 111) < 1.5
    assert haversine_m(12.0, 109.0, 12.0, 109.0) == 0
