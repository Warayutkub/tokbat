//! SQLite connection and schema migrations (PRAGMA user_version). Same file format as the first (Python) version.

use rusqlite::{Connection, OpenFlags};
use std::path::Path;

const MIGRATIONS: &[&str] = &[
    // 1 — first schema
    r#"
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
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE days_off (work_date TEXT PRIMARY KEY);
    CREATE TABLE exports (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        path       TEXT NOT NULL,
        format     TEXT NOT NULL,
        title      TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    "#,
    // 2 — garden game. Sessions remember where they came from: only the timer and hand entries earn coins,
    // imports and everything from before the game ("legacy") never do.
    r#"
    ALTER TABLE sessions ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
    UPDATE sessions SET source = 'legacy';
    CREATE TABLE coin_ledger (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        delta INTEGER NOT NULL,
        kind  TEXT    NOT NULL,             -- welcome | quest | buy | adopt | gift
        ref   TEXT    NOT NULL DEFAULT ''
    );
    CREATE UNIQUE INDEX idx_ledger_once ON coin_ledger (kind, ref) WHERE kind IN ('welcome', 'quest');
    CREATE TABLE quest_claims (
        period     TEXT    NOT NULL,        -- 2026-11-10 | W2026-11-09 | once
        quest_id   TEXT    NOT NULL,
        coins      INTEGER NOT NULL,
        claimed_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
        PRIMARY KEY (period, quest_id)
    );
    CREATE TABLE gifts (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id   TEXT NOT NULL,            -- '' when the box held coins
        rarity    TEXT NOT NULL,
        opened_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE TABLE owned_items (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id  TEXT    NOT NULL,
        x        REAL,                      -- NULL = in the tray, otherwise placed in the garden (world units)
        y        REAL,
        flip     INTEGER NOT NULL DEFAULT 0,
        got_from TEXT    NOT NULL,          -- starter | shop | gift
        got_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE TABLE pets (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        species    TEXT NOT NULL,
        color      TEXT NOT NULL,
        name       TEXT NOT NULL,
        adopted_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    "#,
];

pub fn connect(path: &Path) -> rusqlite::Result<Connection> {
    let con = if path.as_os_str() == ":memory:" {
        Connection::open_in_memory()?
    } else {
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        Connection::open(path)?
    };
    con.pragma_update(None, "foreign_keys", "ON")?;
    migrate(&con)?;
    Ok(con)
}

pub fn migrate(con: &Connection) -> rusqlite::Result<i64> {
    let version: i64 = con.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    for (i, sql) in MIGRATIONS.iter().enumerate().skip(version as usize) {
        con.execute_batch(&format!("BEGIN; {sql} PRAGMA user_version = {}; COMMIT;", i + 1))?;
    }
    con.query_row("PRAGMA user_version", [], |r| r.get(0))
}

/// True when the file is a SQLite database with our sessions table (checked before restoring a backup).
pub fn is_tokbat_db(path: &Path) -> bool {
    let Ok(con) = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY) else { return false };
    con.query_row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sessions'", [], |_| Ok(())).is_ok()
}
