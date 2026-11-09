from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class EntRow:
    created_at: datetime
    days: int


def grant(conn: sqlite3.Connection, user_id: int, days: int, source: str,
          ref: str | None, now: datetime) -> bool:
    """False, если запись с таким ref уже есть (идемпотентно)."""
    try:
        conn.execute(
            "INSERT INTO entitlements(user_id, days, source, ref, created_at) VALUES(?,?,?,?,?)",
            (user_id, days, source, ref, now.isoformat()),
        )
    except sqlite3.IntegrityError:
        return False
    return True


def revoke(conn: sqlite3.Connection, ent_id: int, now: datetime) -> None:
    conn.execute("UPDATE entitlements SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                 (now.isoformat(), ent_id))


def revoke_by_ref(conn: sqlite3.Connection, ref: str, now: datetime) -> None:
    conn.execute("UPDATE entitlements SET revoked_at=? WHERE ref=? AND revoked_at IS NULL",
                 (now.isoformat(), ref))


def compute_access_until(rows: list[EntRow], now: datetime) -> datetime | None:
    cursor: datetime | None = None
    for r in sorted(rows, key=lambda r: r.created_at):
        start = r.created_at if cursor is None else max(cursor, r.created_at)
        cursor = start + timedelta(days=r.days)
    if cursor is not None and cursor > now:
        return cursor
    return None


def access_until(conn: sqlite3.Connection, user_id: int, now: datetime) -> datetime | None:
    rows = conn.execute(
        "SELECT created_at, days FROM entitlements WHERE user_id=? AND revoked_at IS NULL",
        (user_id,),
    ).fetchall()
    return compute_access_until(
        [EntRow(datetime.fromisoformat(r["created_at"]), r["days"]) for r in rows], now)


def has_access(conn: sqlite3.Connection, user_id: int, now: datetime) -> bool:
    return access_until(conn, user_id, now) is not None
