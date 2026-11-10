//! All reads and writes to the database. Returns serde_json values the UI uses directly.

use chrono::{Days, NaiveDate, NaiveDateTime, Timelike};
use rusqlite::{Connection, OptionalExtension, Row, params};
use serde_json::{Map, Value, json};
use std::collections::{HashMap, HashSet};

use crate::thaidate as td;
use crate::timecalc as tc;

pub fn default_settings() -> Map<String, Value> {
    let v = json!({
        "display_name": "",
        "cycle_mode": "cutoff",
        "cutoff_day": 20,
        "title_pattern": "{เดือน}/{ปี}",
        "unit": "decimal",
        "default_break": 0,
        "remind_missing": true,
        "show_characters": true,
        "report_columns": ["date", "start", "end", "hours", "note"],
        "report_footnote": true,
        "report_timestamp": true,
        "report_mascot": true,
        "first_run_done": false,
        "last_backup": "",
        "game_enabled": true,
        "start_page": "garden",
        "coin_cap_hours": 8,
        "rain": true,
        "game_started": ""
    });
    v.as_object().unwrap().clone()
}

pub fn iso(d: NaiveDate) -> String {
    d.format("%Y-%m-%d").to_string()
}

pub fn parse_iso(s: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(s, "%Y-%m-%d").ok()
}

fn session_json(row: &Row) -> rusqlite::Result<Value> {
    let id: i64 = row.get("id")?;
    let date: String = row.get("work_date")?;
    let start: i64 = row.get("start_min")?;
    let end: Option<i64> = row.get("end_min")?;
    let brk: i64 = row.get("break_min")?;
    let note: String = row.get("note")?;
    let source: String = row.get("source")?;
    let minutes = end.map(|e| tc::net_minutes(start, e, brk).unwrap_or(0)).unwrap_or(0);
    Ok(json!({
        "id": id, "date": date, "start": tc::fmt_hhmm(start), "end": end.map(tc::fmt_hhmm),
        "break_min": brk, "note": note, "open": end.is_none(), "source": source,
        "overnight": end.is_some_and(|e| tc::is_overnight(start, e)),
        "minutes": minutes, "hours": tc::to_decimal_hours(minutes),
    }))
}

fn s_str<'a>(v: &'a Value, k: &str) -> &'a str {
    v.get(k).and_then(Value::as_str).unwrap_or("")
}
pub fn s_i64(v: &Value, k: &str) -> i64 {
    v.get(k).and_then(|x| x.as_i64().or_else(|| x.as_f64().map(|f| f as i64)).or_else(|| x.as_str().and_then(|s| s.parse().ok()))).unwrap_or(0)
}

fn err(code: &str, message: impl Into<String>) -> Value {
    json!({"ok": false, "error": {"code": code, "message": message.into()}})
}

pub struct Repo<'c> {
    pub con: &'c Connection,
}

impl<'c> Repo<'c> {
    pub fn get(&self, id: i64) -> Option<Value> {
        self.con.query_row("SELECT * FROM sessions WHERE id = ?", [id], session_json).optional().ok().flatten()
    }

    pub fn between(&self, start: NaiveDate, end: NaiveDate, query: &str) -> Vec<Value> {
        let q = query.trim();
        let mut sql = String::from("SELECT * FROM sessions WHERE work_date BETWEEN ?1 AND ?2");
        if !q.is_empty() {
            sql.push_str(" AND note LIKE ?3");
        }
        sql.push_str(" ORDER BY work_date, start_min");
        let mut st = self.con.prepare(&sql).unwrap();
        let like = format!("%{q}%");
        let rows = if q.is_empty() { st.query_map(params![iso(start), iso(end)], session_json) } else { st.query_map(params![iso(start), iso(end), like], session_json) };
        rows.map(|r| r.filter_map(Result::ok).collect()).unwrap_or_default()
    }

    pub fn on(&self, d: NaiveDate) -> Vec<Value> {
        self.between(d, d, "")
    }

    pub fn open_session(&self) -> Option<Value> {
        self.con.query_row("SELECT * FROM sessions WHERE end_min IS NULL ORDER BY work_date DESC LIMIT 1", [], session_json).optional().ok().flatten()
    }

    pub fn count(&self) -> i64 {
        self.con.query_row("SELECT COUNT(*) FROM sessions", [], |r| r.get(0)).unwrap_or(0)
    }

    fn date_edge(&self, f: &str) -> Option<NaiveDate> {
        let v: Option<String> = self.con.query_row(&format!("SELECT {f}(work_date) FROM sessions"), [], |r| r.get(0)).ok().flatten();
        v.and_then(|s| parse_iso(&s))
    }
    pub fn first_date(&self) -> Option<NaiveDate> {
        self.date_edge("MIN")
    }
    pub fn last_date(&self) -> Option<NaiveDate> {
        self.date_edge("MAX")
    }

    /// None when the session can be saved, otherwise the reason (with a suggested start for overlaps).
    pub fn check(&self, d: NaiveDate, start: i64, end: Option<i64>, brk: i64, sid: Option<i64>, now: NaiveDateTime) -> Option<Value> {
        if let Some(e) = end {
            if let Err(e) = tc::net_minutes(start, e, brk) {
                return Some(json!({"code": e.code, "message": e.message}));
            }
        }
        let now_abs = (now.date() - d).num_days() * tc::DAY + (now.hour() * 60 + now.minute()) as i64;
        let cand = tc::interval_for(d, start, end, d, now_abs, sid);
        let mut best: Option<(Value, tc::Interval, i64)> = None;
        for s in self.between(d - Days::new(1), d + Days::new(1), "") {
            let id = s["id"].as_i64();
            if id == sid {
                continue;
            }
            let sd = parse_iso(s_str(&s, "date")).unwrap();
            let ss = tc::parse_hhmm(s_str(&s, "start")).unwrap();
            let se = s["end"].as_str().map(|x| tc::parse_hhmm(x).unwrap());
            let iv = tc::interval_for(sd, ss, se, d, now_abs, id);
            let m = cand.overlap(&iv);
            if m > 0 && best.as_ref().is_none_or(|b| m > b.2) {
                best = Some((s, iv, m));
            }
        }
        let (s, iv, m) = best?;
        let suggest = (iv.start_abs <= cand.start_abs && cand.start_abs < iv.end_abs).then(|| tc::fmt_hhmm(iv.end_abs));
        let other_date = parse_iso(s_str(&s, "date")).unwrap();
        Some(json!({
            "code": "overlap",
            "message": format!("ทับกับช่วง {}–{} ของ {} อยู่ {}", s_str(&s, "start"), s["end"].as_str().unwrap_or("ตอนนี้"), td::slash(other_date), tc::to_hm_thai(m)),
            "with": s, "overlap_min": m, "suggest_start": suggest,
        }))
    }

    /// Insert or update. {ok, session, previous} or {ok: false, error}.
    pub fn save(&self, data: &Value, now: NaiveDateTime) -> Value {
        let Some(d) = parse_iso(s_str(data, "date")) else { return err("bad_date", "วันที่ไม่ถูกต้อง") };
        let start = match tc::parse_hhmm(s_str(data, "start")) {
            Ok(v) => v,
            Err(e) => return err(e.code, e.message),
        };
        let end = match data.get("end").and_then(Value::as_str).filter(|s| !s.is_empty()) {
            None => None,
            Some(t) => match tc::parse_hhmm(t) {
                Ok(v) => Some(v),
                Err(e) => return err(e.code, e.message),
            },
        };
        let brk = s_i64(data, "break_min");
        let note = s_str(data, "note").trim().to_string();
        let sid = data.get("id").and_then(Value::as_i64);
        if let Some(e) = self.check(d, start, end, brk, sid, now) {
            return json!({"ok": false, "error": e});
        }
        let previous = sid.and_then(|id| self.get(id));
        // timer | manual | import. Changing the times of a timer entry by hand makes it a hand entry.
        let asked = data.get("source").and_then(Value::as_str).filter(|s| ["timer", "manual", "import"].contains(s));
        let source = match (&previous, asked) {
            (_, Some(s)) => s.to_string(),
            (None, None) => "manual".to_string(),
            (Some(p), None) => {
                let same = s_str(p, "date") == iso(d) && s_str(p, "start") == tc::fmt_hhmm(start) && p["end"].as_str() == end.map(tc::fmt_hhmm).as_deref();
                if same { s_str(p, "source").to_string() } else { "manual".to_string() }
            }
        };
        let id = match sid {
            Some(id) => {
                self.con
                    .execute(
                        "UPDATE sessions SET work_date=?1, start_min=?2, end_min=?3, break_min=?4, note=?5, source=?6, updated_at=datetime('now','localtime') WHERE id=?7",
                        params![iso(d), start, end, brk, note, source, id],
                    )
                    .ok();
                id
            }
            None => {
                self.con
                    .execute(
                        "INSERT INTO sessions (work_date, start_min, end_min, break_min, note, source, created_at) VALUES (?1,?2,?3,?4,?5,?6,?7)",
                        params![iso(d), start, end, brk, note, source, now.format("%Y-%m-%d %H:%M:%S").to_string()],
                    )
                    .ok();
                self.con.last_insert_rowid()
            }
        };
        // working on a day means it isn't a day off any more
        self.con.execute("DELETE FROM days_off WHERE work_date = ?", [iso(d)]).ok();
        json!({"ok": true, "session": self.get(id), "previous": previous})
    }

    pub fn delete(&self, id: i64) -> Option<Value> {
        let row = self.get(id);
        if row.is_some() {
            self.con.execute("DELETE FROM sessions WHERE id = ?", [id]).ok();
        }
        row
    }

    /// Put back a deleted session (undo), keeping its id.
    pub fn restore(&self, s: &Value) -> Option<Value> {
        let id = s["id"].as_i64()?;
        let start = tc::parse_hhmm(s_str(s, "start")).ok()?;
        let end = s["end"].as_str().and_then(|e| tc::parse_hhmm(e).ok());
        self.con
            .execute(
                "INSERT OR REPLACE INTO sessions (id, work_date, start_min, end_min, break_min, note, source) VALUES (?1,?2,?3,?4,?5,?6,?7)",
                params![id, s_str(s, "date"), start, end, s_i64(s, "break_min"), s_str(s, "note"), Some(s_str(s, "source")).filter(|x| !x.is_empty()).unwrap_or("manual")],
            )
            .ok()?;
        self.get(id)
    }

    pub fn delete_all(&self) -> i64 {
        let n = self.count();
        self.con.execute_batch("DELETE FROM sessions; DELETE FROM days_off;").ok();
        n
    }

    pub fn exists(&self, d: NaiveDate, start: i64, end: Option<i64>) -> bool {
        self.con.query_row("SELECT 1 FROM sessions WHERE work_date=?1 AND start_min=?2 AND end_min IS ?3", params![iso(d), start, end], |_| Ok(())).is_ok()
    }

    pub fn day_minutes(&self, start: NaiveDate, end: NaiveDate) -> HashMap<String, i64> {
        let mut out = HashMap::new();
        for s in self.between(start, end, "") {
            *out.entry(s_str(&s, "date").to_string()).or_insert(0) += s["minutes"].as_i64().unwrap_or(0);
        }
        out
    }

    pub fn mark_day_off(&self, d: NaiveDate) {
        self.con.execute("INSERT OR IGNORE INTO days_off (work_date) VALUES (?)", [iso(d)]).ok();
    }

    pub fn unmark_day_off(&self, d: NaiveDate) {
        self.con.execute("DELETE FROM days_off WHERE work_date = ?", [iso(d)]).ok();
    }

    /// Days marked as off between start and end (inclusive), as ISO dates.
    pub fn days_off(&self, start: NaiveDate, end: NaiveDate) -> HashSet<String> {
        self.con
            .prepare("SELECT work_date FROM days_off WHERE work_date BETWEEN ?1 AND ?2")
            .and_then(|mut s| s.query_map(params![iso(start), iso(end)], |r| r.get(0)).map(|r| r.filter_map(Result::ok).collect()))
            .unwrap_or_default()
    }

    /// Past days (newest first) with no session, after the first entry, not marked as off.
    pub fn missing_days(&self, today: NaiveDate, lookback: u64) -> Vec<String> {
        let Some(first) = self.first_date() else { return vec![] };
        let start = first.max(today - Days::new(lookback));
        let have: HashSet<String> = self.day_minutes(start, today).into_keys().collect();
        let off: HashSet<String> = self.con.prepare("SELECT work_date FROM days_off").and_then(|mut s| s.query_map([], |r| r.get(0)).map(|r| r.filter_map(Result::ok).collect())).unwrap_or_default();
        let mut out = vec![];
        let mut d = today - Days::new(1);
        while d >= start {
            let k = iso(d);
            if !have.contains(&k) && !off.contains(&k) {
                out.push(k);
            }
            d = d - Days::new(1);
        }
        out
    }

    pub fn settings(&self) -> Map<String, Value> {
        let mut s = default_settings();
        if let Ok(mut st) = self.con.prepare("SELECT key, value FROM settings") {
            let rows = st.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?)));
            if let Ok(rows) = rows {
                for (k, v) in rows.filter_map(Result::ok) {
                    if let Ok(val) = serde_json::from_str(&v) {
                        s.insert(k, val);
                    }
                }
            }
        }
        s
    }

    pub fn save_settings(&self, patch: &Value) -> Map<String, Value> {
        let known = default_settings();
        if let Some(p) = patch.as_object() {
            for (k, v) in p {
                if known.contains_key(k) {
                    self.con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?1, ?2)", params![k, v.to_string()]).ok();
                }
            }
        }
        self.settings()
    }

    pub fn add_export(&self, path: &str, format: &str, title: &str) {
        self.con.execute("INSERT INTO exports (path, format, title) VALUES (?1,?2,?3)", params![path, format, title]).ok();
    }

    pub fn recent_exports(&self, limit: i64) -> Vec<(String, String, String)> {
        self.con
            .prepare("SELECT path, format, created_at FROM exports ORDER BY id DESC LIMIT ?")
            .and_then(|mut s| s.query_map([limit], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?))).map(|r| r.filter_map(Result::ok).collect()))
            .unwrap_or_default()
    }
}
