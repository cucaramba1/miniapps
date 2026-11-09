import json
import pytest
from fastapi.testclient import TestClient

from app.auth import AuthError, verify_init_data
from app.config import Settings, load_settings
from app.main import create_app
from tests.conftest import make_init_data

TOKEN = "123:abc"
NOW = 1_800_000_000


def test_valid():
    u = verify_init_data(make_init_data(42, TOKEN, NOW), TOKEN, NOW + 10, 86400)
    assert u.id == 42


def test_bad_hash():
    s = make_init_data(42, TOKEN, NOW)
    with pytest.raises(AuthError):
        verify_init_data(s, "other:token", NOW, 86400)


def test_tampered_user_id():
    s = make_init_data(42, TOKEN, NOW).replace("%22id%22%3A+42", "%22id%22%3A+43")
    assert "43" in s
    with pytest.raises(AuthError):
        verify_init_data(s, TOKEN, NOW, 86400)


def test_expired():
    with pytest.raises(AuthError):
        verify_init_data(make_init_data(42, TOKEN, NOW), TOKEN, NOW + 86401, 86400)


def test_no_auth_date():
    import hashlib, hmac
    from urllib.parse import urlencode
    f = {"user": json.dumps({"id": 1})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(f.items()))
    sec = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    f["hash"] = hmac.new(sec, check.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(AuthError):
        verify_init_data(urlencode(f), TOKEN, NOW, 86400)


def test_me_without_header_401(client):
    assert client.get("/api/me").status_code == 401


def test_me_with_init_data(client, as_user):
    r = client.get("/api/me", headers=as_user(7))
    assert r.status_code == 200 and r.json()["id"] == 7 and r.json()["has_access"] is False


def test_forged_header_401(client, settings):
    h = {"Authorization": "tma " + make_init_data(7, "wrong:token")}
    assert client.get("/api/me", headers=h).status_code == 401


def test_dev_header_off(client):
    assert client.get("/api/me", headers={"X-Dev-User": "5"}).status_code == 401


def test_dev_header_on(tmp_path):
    s = Settings(db_path=str(tmp_path / "d.db"), photos_dir=str(tmp_path / "p"),
                 web_dir=str(tmp_path / "w"), dev_auth=True)
    c = TestClient(create_app(s))
    assert c.get("/api/me", headers={"X-Dev-User": "5"}).status_code == 200


def test_prod_with_dev_auth_fails():
    with pytest.raises(RuntimeError):
        load_settings({"APP_ENV": "prod", "DEV_AUTH": "true", "BOT_TOKEN": "x",
                       "WEBHOOK_SECRET": "x", "PHOTO_SIGN_SECRET": "x"})


def test_prod_requires_secrets():
    with pytest.raises(RuntimeError):
        load_settings({"APP_ENV": "prod"})


def test_env_file_parsing(tmp_path):
    from app.config import read_env_file
    f = tmp_path / ".env"
    f.write_text("# c\nBOT_TOKEN=abc:def   # inline\nEMPTY=   # x\nQ=\"v\"\n")
    assert read_env_file(f) == {"BOT_TOKEN": "abc:def", "EMPTY": "", "Q": "v"}
