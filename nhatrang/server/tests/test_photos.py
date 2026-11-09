import io
from datetime import datetime, timezone, timedelta

import pytest
from PIL import Image

from app.photos import check_photo_sig, exif_age_s, sign_photo_url, store_photo
from tests.conftest import T0, give_access, make_place, make_user


def jpeg(size=(40, 30), exif_dt=None, color=(200, 10, 10)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    kw = {}
    if exif_dt:
        ex = Image.Exif()
        ex[306] = exif_dt
        kw["exif"] = ex
    img.save(buf, "JPEG", **kw)
    return buf.getvalue()


def test_rejects_non_images(tmp_path):
    for bad in (b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"%PDF-1.4 ...", b"hello"):
        with pytest.raises(ValueError):
            store_photo(bad, tmp_path)


def test_rejects_big(tmp_path):
    with pytest.raises(ValueError):
        store_photo(b"\xff\xd8" + b"0" * (7 * 1024 * 1024), tmp_path)


def test_recompress_strips_exif_and_resizes(tmp_path):
    name = store_photo(jpeg((3000, 2000), exif_dt="2026:11:04 19:00:00"), tmp_path)
    assert name.endswith(".jpg") and len(name) == 20
    img = Image.open(tmp_path / name)
    assert max(img.size) == 1280
    assert not img.getexif()


def test_exif_age(tmp_path):
    now = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)  # 19:00 по Нячангу
    assert exif_age_s(jpeg(exif_dt="2026:11:04 18:58:00"), now) == 120
    assert exif_age_s(jpeg(exif_dt="2026:11:01 18:58:00"), now) > 600
    assert exif_age_s(jpeg(), now) is None


def test_signature_check():
    url = sign_photo_url("0123456789abcdef.jpg", 7, 2000, "sec")
    q = dict(p.split("=") for p in url.split("?")[1].split("&"))
    n = "0123456789abcdef.jpg"
    assert check_photo_sig(n, int(q["u"]), int(q["e"]), q["s"], "sec", 1000)
    assert not check_photo_sig(n, 8, int(q["e"]), q["s"], "sec", 1000)       # чужой u
    assert not check_photo_sig(n, 7, 2001, q["s"], "sec", 1000)              # подправленный e
    assert not check_photo_sig(n, 7, 2000, "0" * 32, "sec", 1000)            # поддельная s
    assert not check_photo_sig(n, 7, 2000, q["s"], "sec", 2001)              # просрочено
    assert not check_photo_sig("../../etc/passwd", 7, 2000, q["s"], "sec", 1000)


def test_photo_endpoint(client, settings, tmp_path):
    name = store_photo(jpeg(), settings.photos_dir)
    url = sign_photo_url(name, 7, int(T0.timestamp()) + 100, settings.photo_sign_secret)
    assert client.get(url).status_code == 200
    assert client.get(url.replace("u=7", "u=8")).status_code == 403
    exp = sign_photo_url(name, 7, int(T0.timestamp()) - 1, settings.photo_sign_secret)
    assert client.get(exp).status_code == 403
    assert client.get(f"/api/photos/{name}").status_code == 422  # нет подписи


def _post(client, headers, pid, text="б" * 150, n_photos=2, lat=12.2388, lon=109.1967, acc=10,
          tags=("noise",)):
    files = [("photos", (f"{i}.jpg", jpeg(color=(i * 40, 5, 5)), "image/jpeg"))
             for i in range(n_photos)]
    return client.post(f"/api/places/{pid}/reviews", headers=headers, files=files,
                       data={"text": text, "rating": 4, "lat": lat, "lon": lon,
                             "accuracy_m": acc, "tags": list(tags)})


def test_post_review_ok_and_reward(client, db, as_user):
    pid = make_place(db)
    r = _post(client, as_user(11), pid)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "published" and r.json()["reward_days"] == 3
    assert client.get("/api/me", headers=as_user(11)).json()["has_access"] is True


def test_post_review_rejections(client, db, as_user):
    pid = make_place(db)
    assert _post(client, as_user(11), pid, text="коротко").json() == {"reason": "text_short"}
    assert _post(client, as_user(11), pid, n_photos=1).json() == {"reason": "photos_few"}
    assert _post(client, as_user(11), pid, lat=12.30).json() == {"reason": "too_far"}


def test_post_review_bad_photo(client, db, as_user):
    pid = make_place(db)
    r = client.post(f"/api/places/{pid}/reviews", headers=as_user(11),
                    files=[("photos", ("a.svg", b"<svg/>", "image/svg+xml")),
                           ("photos", ("b.jpg", jpeg(), "image/jpeg"))],
                    data={"text": "б" * 150, "rating": 4, "lat": 12.2388, "lon": 109.1967,
                          "accuracy_m": 5})
    assert r.status_code == 422 and r.json() == {"reason": "bad_photo"}


def test_author_comes_from_auth_not_body(client, db, as_user):
    pid = make_place(db)
    files = [("photos", (f"{i}.jpg", jpeg(color=(i * 40, 5, 5)), "image/jpeg")) for i in range(2)]
    client.post(f"/api/places/{pid}/reviews", headers=as_user(11), files=files,
                data={"text": "б" * 150, "rating": 4, "lat": 12.2388, "lon": 109.1967,
                      "accuracy_m": 5, "user_id": 999})
    assert db.execute("SELECT user_id FROM reviews").fetchone()[0] == 11


def test_report_holds_review(client, db, as_user):
    from tests.conftest import make_review
    pid = make_place(db)
    rid = make_review(db, pid)
    assert client.post(f"/api/reviews/{rid}/report", headers=as_user(3)).status_code == 200
    row = db.execute("SELECT status, hold_reason FROM reviews WHERE id=?", (rid,)).fetchone()
    assert (row[0], row[1]) == ("held", "reported")


def test_full_flow_photos_visible_with_access_only(client, db, as_user):
    pid = make_place(db)
    _post(client, as_user(11), pid)
    r = client.get(f"/api/places/{pid}", headers=as_user(22))  # без доступа
    assert "/api/photos/" not in r.text
    r = client.get(f"/api/places/{pid}", headers=as_user(11))  # автор получил 3 дня
    url = r.json()["paid"]["reviews"][0]["photo_urls"][0]
    assert client.get(url).status_code == 200
