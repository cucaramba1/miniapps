from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 1


def connect(path: str) -> sqlite3.Connection:
    # isolation_level=None: транзакциями управляем руками (BEGIN IMMEDIATE где нужно)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    if ver >= SCHEMA_VERSION:
        return
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
