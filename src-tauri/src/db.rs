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
