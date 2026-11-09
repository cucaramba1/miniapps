from datetime import timedelta

from app.access import EntRow, access_until, compute_access_until, grant, revoke
from tests.conftest import T0

D = lambda n: timedelta(days=n)


def test_single():
    assert compute_access_until([EntRow(T0, 3)], T0) == T0 + D(3)


def test_stack_while_active():
    rows = [EntRow(T0, 3), EntRow(T0 + D(1), 7)]
    assert compute_access_until(rows, T0 + D(1)) == T0 + D(10)


def test_after_expiry_starts_fresh():
    rows = [EntRow(T0, 3), EntRow(T0 + D(5), 7)]
    assert compute_access_until(rows, T0 + D(5)) == T0 + D(12)


def test_expired_none():
    assert compute_access_until([EntRow(T0, 3)], T0 + D(4)) is None


def test_empty_none():
    assert compute_access_until([], T0) is None


def _user(db, uid=1):
    db.execute("INSERT INTO users(id, created_at) VALUES(?, ?)", (uid, T0.isoformat()))


def test_grant_idempotent(db):
    _user(db)
    assert grant(db, 1, 3, "stars", "ch1", T0) is True
    assert grant(db, 1, 3, "stars", "ch1", T0 + D(1)) is False
    assert access_until(db, 1, T0) == T0 + D(3)


def test_revoke_middle_recomputes(db):
    _user(db)
    grant(db, 1, 3, "review", "r1", T0)
    grant(db, 1, 3, "review", "r2", T0 + D(1))
    grant(db, 1, 3, "review", "r3", T0 + D(2))
    assert access_until(db, 1, T0 + D(2)) == T0 + D(9)
    eid = db.execute("SELECT id FROM entitlements WHERE ref='r2'").fetchone()[0]
    revoke(db, eid, T0 + D(2))
    assert access_until(db, 1, T0 + D(2)) == T0 + D(6)
