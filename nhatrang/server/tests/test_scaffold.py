from app.db import connect, migrate


def test_health_ok(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_migrate_idempotent(settings):
    c = connect(settings.db_path)
    migrate(c)
    v1 = c.execute("PRAGMA user_version").fetchone()[0]
    migrate(c)
    assert c.execute("PRAGMA user_version").fetchone()[0] == v1 >= 1


def test_schema_has_expected_tables(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("users entitlements districts places reviews review_reports signals amenities "
              "listings realtors flags favorites payments").split():
        assert t in names


def test_wal_and_fk(db):
    assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
