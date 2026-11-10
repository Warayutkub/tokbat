"""SQLite connection and schema migrations (PRAGMA user_version)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1 — first schema
    """
    CREATE TABLE sessions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        work_date  TEXT    NOT NULL,                       -- ISO date the session started on
        start_min  INTEGER NOT NULL CHECK (start_min BETWEEN 0 AND 1439),
        end_min    INTEGER CHECK (end_min BETWEEN 0 AND 1439), -- NULL = still working; <= start = next day
        break_min  INTEGER NOT NULL DEFAULT 0 CHECK (break_min >= 0),
        note       TEXT    NOT NULL DEFAULT '',
        created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE INDEX idx_sessions_date ON sessions (work_date, start_min);
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);   -- JSON values
    CREATE TABLE days_off (work_date TEXT PRIMARY KEY);                   -- days the user said they did not work
    CREATE TABLE exports (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        path       TEXT NOT NULL,
        format     TEXT NOT NULL,
        title      TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    """,
]


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    migrate(con)
    return con


def migrate(con: sqlite3.Connection) -> int:
    version = con.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        with con:
            con.executescript(sql)
            con.execute(f"PRAGMA user_version = {i}")
    return con.execute("PRAGMA user_version").fetchone()[0]


def is_tokbat_db(path: Path | str) -> bool:
    """True when the file is a SQLite database with our sessions table (used before restoring a backup)."""
    try:
        con = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()
            return row is not None
        finally:
            con.close()
    except sqlite3.Error:
        return False
