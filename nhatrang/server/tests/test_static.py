from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_static_allowlist(tmp_path):
    web = tmp_path / "nh"
    (web / "js").mkdir(parents=True)
    (web / "server" / "data").mkdir(parents=True)
    (web / "index.html").write_text("<html>ok</html>")
    (web / "js" / "a.js").write_text("1")
    (web / "server" / "data" / "app.db").write_text("SECRET")
    (web / "DESIGN.md").write_text("SECRET")
    sh = tmp_path / "shared"
    sh.mkdir()
    (sh / "tgx.js").write_text("tgx")
    s = Settings(db_path=str(tmp_path / "d.db"), photos_dir=str(tmp_path / "p"),
                 web_dir=str(web), shared_dir=str(sh))
    c = TestClient(create_app(s))
    assert c.get("/").text == "<html>ok</html>"
    assert c.get("/js/a.js").text == "1"
    assert c.get("/shared/tgx.js").text == "tgx"
    for bad in ("/server/data/app.db", "/DESIGN.md", "/js/../server/data/app.db",
                "/shared/../nh/DESIGN.md", "/%2e%2e/secret"):
        r = c.get(bad)
        assert "SECRET" not in r.text, bad


def test_tiles_served_with_range(tmp_path):
    web = tmp_path / "nh"
    (web / "tiles").mkdir(parents=True)
    (web / "tiles" / "a.pmtiles").write_bytes(bytes(range(256)) * 4)
    (web / "index.html").write_text("ok")
    s = Settings(db_path=str(tmp_path / "d.db"), photos_dir=str(tmp_path / "p"), web_dir=str(web))
    c = TestClient(create_app(s))
    r = c.get("/tiles/a.pmtiles", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and r.content == bytes(range(10))
