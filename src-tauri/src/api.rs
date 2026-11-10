//! The methods the web UI calls — one entry point, `Api::call(method, args)`, used by the Tauri command
//! and by the dev HTTP server. Everything returns JSON. Same method names and shapes as the Python version.

use chrono::{Datelike, Duration, Local, NaiveDate, NaiveDateTime, Timelike};
use rusqlite::{Connection, MAIN_DB};
use serde_json::{Map, Value, json};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, MutexGuard, RwLock};

use crate::repo::{Repo, iso, parse_iso};
use crate::thaidate as td;
use crate::timecalc as tc;
use crate::{csv_io, db, exporter, report};

const MASCOT_SVG: &str = include_str!("../../web/img/chars/character-idle.svg");

/// File pickers: native ones in the app, stand-ins in tests and the dev server.
pub trait Dialogs: Send + Sync {
    fn save(&self, filename: &str, kind: &str) -> Option<PathBuf>;
    fn open(&self, kind: &str) -> Option<PathBuf>;
}

pub type Clock<T> = Box<dyn Fn() -> T + Send + Sync>;

pub struct Api {
    db_file: PathBuf,
    con: Mutex<Connection>,
    dialogs: RwLock<Option<Box<dyn Dialogs>>>,
    pending: Mutex<HashMap<String, Vec<Value>>>,
    today: RwLock<Clock<NaiveDate>>,
    now: RwLock<Clock<NaiveDateTime>>,
}

fn arg(args: &[Value], i: usize) -> &Value {
    args.get(i).unwrap_or(&Value::Null)
}
fn arg_str(args: &[Value], i: usize) -> String {
    arg(args, i).as_str().unwrap_or("").to_string()
}
fn arg_date(args: &[Value], i: usize) -> Result<NaiveDate, String> {
    parse_iso(&arg_str(args, i)).ok_or_else(|| format!("bad date in argument {i}"))
}
fn cancelled() -> Value {
    json!({"ok": false, "cancelled": true})
}
fn name_of(p: &Path) -> String {
    p.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default()
}
fn st<'a>(s: &'a Map<String, Value>, k: &str, default: &'a str) -> &'a str {
    s.get(k).and_then(Value::as_str).unwrap_or(default)
}

impl Api {
    pub fn new(db_file: PathBuf, dialogs: Option<Box<dyn Dialogs>>) -> Result<Self, String> {
        if let Some(dir) = db_file.parent() {
            std::fs::create_dir_all(dir).map_err(|e| format!("สร้างโฟลเดอร์ข้อมูลไม่ได้: {e}"))?;
        }
        let con = db::connect(&db_file).map_err(|e| format!("เปิดไฟล์ข้อมูลไม่ได้: {e}"))?;
        Ok(Self {
            db_file,
            con: Mutex::new(con),
            dialogs: RwLock::new(dialogs),
            pending: Mutex::new(HashMap::new()),
            today: RwLock::new(Box::new(|| Local::now().date_naive())),
            now: RwLock::new(Box::new(|| Local::now().naive_local())),
        })
    }

    pub fn set_dialogs(&self, d: Box<dyn Dialogs>) {
        *self.dialogs.write().unwrap() = Some(d);
    }
    /// Tests pin the clock.
    pub fn set_clock(&self, today: Clock<NaiveDate>, now: Clock<NaiveDateTime>) {
        *self.today.write().unwrap() = today;
        *self.now.write().unwrap() = now;
    }
    fn today(&self) -> NaiveDate {
        (self.today.read().unwrap())()
    }
    fn now(&self) -> NaiveDateTime {
        (self.now.read().unwrap())()
    }
    fn lock(&self) -> Result<MutexGuard<'_, Connection>, String> {
        // a panic while holding the lock must not take the whole app down with it
        Ok(self.con.lock().unwrap_or_else(|p| p.into_inner()))
    }
    fn save_dialog(&self, name: &str, kind: &str) -> Option<PathBuf> {
        self.dialogs.read().unwrap().as_ref().and_then(|d| d.save(name, kind))
    }
    fn open_dialog(&self, kind: &str) -> Option<PathBuf> {
        self.dialogs.read().unwrap().as_ref().and_then(|d| d.open(kind))
    }

    pub fn call(&self, method: &str, args: &[Value]) -> Result<Value, String> {
        // methods that show a file picker run it before taking the database lock
        match method {
            "export_report" => return self.export_report(arg(args, 0)),
            "backup" => return self.backup(),
            "restore" => return self.restore(),
            "import_pick" => return self.import_pick(),
            "reveal" => {
                reveal(Path::new(&arg_str(args, 0)));
                return Ok(json!({"ok": true}));
            }
            _ => {}
        }
        let con = self.lock()?;
        let repo = Repo { con: &con };
        let s = repo.settings();
        let unit = st(&s, "unit", "decimal").to_string();
        let mode = st(&s, "cycle_mode", "cutoff").to_string();
        let cutoff = s.get("cutoff_day").and_then(Value::as_i64).unwrap_or(20);
        let pattern = st(&s, "title_pattern", "{เดือน}/{ปี}").to_string();
        Ok(match method {
            "bootstrap" => json!({"today": iso(self.today()), "settings": s, "count": repo.count(), "open_session": repo.open_session()}),

            "day" => {
                let d = arg_date(args, 0)?;
                let (today, now) = (self.today(), self.now());
                let sessions = repo.on(d);
                let week = tc::week_of(d);
                let mins = repo.day_minutes(week[0], week[6]);
                let missing = if s.get("remind_missing").and_then(Value::as_bool).unwrap_or(true) { repo.missing_days(today, 14) } else { vec![] };
                let off = repo.days_off(week[0], week[6]);
                let days: Vec<Value> = week
                    .iter()
                    .map(|w| {
                        let k = iso(*w);
                        let m = *mins.get(&k).unwrap_or(&0);
                        let state = if m == 0 && off.contains(&k) {
                            "off"
                        } else if *w > today {
                            "future"
                        } else if m > 0 {
                            "done"
                        } else if missing.contains(&k) {
                            "miss"
                        } else {
                            "empty"
                        };
                        let sub = match state {
                            "done" => format!("✓ {}", tc::fmt_hours(m, &unit)),
                            "miss" => "ลืมกรอก".to_string(),
                            "off" => "หยุด".to_string(),
                            _ => "–".to_string(),
                        };
                        json!({"date": k, "wd": td::wd(*w), "n": w.day(), "minutes": m, "state": state, "sub": sub})
                    })
                    .collect();
                let me = iso(d);
                let miss = missing.iter().find(|m| **m != me).cloned();
                let total: i64 = sessions.iter().map(|x| x["minutes"].as_i64().unwrap_or(0)).sum();
                json!({
                    "date": me, "label": td::short(d), "label_short": td::short_no_year(d), "next_label": td::short_no_year(d + Duration::days(1)),
                    "is_today": d == today, "is_past": d < today, "off": sessions.is_empty() && off.contains(&me),
                    "sessions": sessions, "total_min": total,
                    "now_abs": (now.date() - d).num_days() * tc::DAY + (now.hour() * 60 + now.minute()) as i64,
                    "now_hhmm": now.format("%H:%M").to_string(),
                    "week": {"days": days, "label": range_label(week[0], week[6]), "is_current": week.contains(&today),
                             "prev": iso(d - Duration::days(7)), "next": iso(d + Duration::days(7))},
                    "missing": miss.map(|m| json!({"date": m, "label": td::short_no_year(parse_iso(&m).unwrap())})),
                })
            }

            "save_session" => repo.save(arg(args, 0), self.now()),
            "delete_session" => json!({"ok": true, "deleted": repo.delete(arg(args, 0).as_i64().unwrap_or(-1))}),
            "restore_session" => json!({"ok": true, "session": repo.restore(arg(args, 0))}),
            "start_now" => {
                let now = self.now();
                repo.save(&json!({"date": iso(now.date()), "start": now.format("%H:%M").to_string(), "end": null, "break_min": 0, "note": ""}), now)
            }
            "stop_now" => {
                let Some(mut x) = repo.get(arg(args, 0).as_i64().unwrap_or(-1)).filter(|x| x["open"] == true) else {
                    return Ok(json!({"ok": false, "error": {"code": "not_open", "message": "ช่วงนี้ไม่ได้กำลังทำงานอยู่"}}));
                };
                let now = self.now();
                let date = parse_iso(x["date"].as_str().unwrap_or("")).ok_or("bad session date")?;
                let start = tc::parse_hhmm(x["start"].as_str().unwrap_or("")).map_err(|e| e.message)?;
                let started = date.and_hms_opt(0, 0, 0).unwrap() + Duration::minutes(start);
                if now - started >= Duration::hours(24) {
                    return Ok(json!({"ok": false, "error": {"code": "too_long", "message": "ช่วงนี้เกิน 24 ชั่วโมงแล้ว กรอกเวลาออกงานเองแทนนะ"}}));
                }
                x["end"] = json!(now.format("%H:%M").to_string());
                repo.save(&x, now)
            }
            "mark_day_off" => {
                repo.mark_day_off(arg_date(args, 0)?);
                json!({"ok": true})
            }
            "unmark_day_off" => {
                repo.unmark_day_off(arg_date(args, 0)?);
                json!({"ok": true})
            }

            "period" => {
                let kind = arg_str(args, 0);
                let a = arg_date(args, 1)?;
                let k = arg(args, 2).as_i64().unwrap_or(0);
                let (start, end) = if kind == "week" {
                    let wk = tc::week_of(a + Duration::days(7 * k));
                    (wk[0], wk[6])
                } else {
                    let (s0, e0) = td::cycle_for(a, &mode, cutoff);
                    if k != 0 { td::shift_cycle(e0, k as i32, &mode, cutoff) } else { (s0, e0) }
                };
                json!({"start": iso(start), "end": iso(end), "label": format!("{} – {}", td::slash(start), td::slash(end)),
                       "label_short": range_slash(start, end), "title": td::title_from_pattern(&pattern, end)})
            }
            "all_range" => {
                let t = self.today();
                json!({"start": iso(repo.first_date().unwrap_or(t)), "end": iso(repo.last_date().unwrap_or(t))})
            }
            "history" => {
                let (a, b) = (arg_date(args, 0)?, arg_date(args, 1)?);
                let rows = repo.between(a, b, &arg_str(args, 2));
                let mut groups: Vec<Value> = vec![];
                for r in &rows {
                    let date = r["date"].as_str().unwrap_or("");
                    if groups.last().is_none_or(|g| g["date"] != date) {
                        let d = parse_iso(date).ok_or("bad session date")?;
                        groups.push(json!({"date": date, "label": format!("{} {}", td::wd(d), td::slash(d)), "slash": td::slash(d), "total_min": 0, "sessions": []}));
                    }
                    let g = groups.last_mut().unwrap();
                    g["total_min"] = json!(g["total_min"].as_i64().unwrap_or(0) + r["minutes"].as_i64().unwrap_or(0));
                    g["sessions"].as_array_mut().unwrap().push(r.clone());
                }
                let total: i64 = rows.iter().map(|r| r["minutes"].as_i64().unwrap_or(0)).sum();
                json!({"groups": groups, "count": rows.len(), "total_min": total, "label": format!("{} – {}", td::slash(a), td::slash(b))})
            }

            "report" => {
                let (a, b) = (arg_date(args, 0)?, arg_date(args, 1)?);
                let mut rep = report::build(&repo, a, b, arg(args, 2).as_str().unwrap_or("decimal"));
                rep["label_short"] = json!(range_slash(a, b));
                rep["default_title"] = json!(td::title_from_pattern(&pattern, b));
                rep["recent"] = recent(&repo);
                if rep["sessions"] == 0 {
                    if let Some(last) = repo.last_date() {
                        let (ls, le) = td::cycle_for(last, &mode, cutoff);
                        rep["latest"] = json!({"start": iso(ls), "end": iso(le)});
                    }
                }
                rep
            }
            "report_preview" => json!(self.html(&repo, arg(args, 0))?),

            "save_settings" => json!(repo.save_settings(arg(args, 0))),
            "data_info" => {
                let (a, b) = td::cycle_for(self.today(), &mode, cutoff);
                json!({"db_path": self.db_file.to_string_lossy(), "db_path_short": short_path(&self.db_file), "count": repo.count(),
                       "last_backup": st(&s, "last_backup", ""),
                       "cycle": {"label": format!("{} – {}", td::slash(a), td::slash(b)), "title": td::title_from_pattern(&pattern, b)}})
            }
            "import_commit" => {
                let Some(rows) = self.pending.lock().unwrap().remove(&arg_str(args, 0)) else {
                    return Ok(json!({"ok": false, "error": "หมดเวลานำเข้าแล้ว เลือกไฟล์ใหม่อีกครั้งนะ"}));
                };
                let now = self.now();
                let (mut added, mut conflicts) = (0, 0);
                for r in &rows {
                    if repo.save(r, now)["ok"] == true {
                        added += 1
                    } else {
                        conflicts += 1
                    }
                }
                if added > 0 {
                    repo.save_settings(&json!({"first_run_done": true}));
                }
                json!({"ok": true, "added": added, "conflicts": conflicts})
            }
            "delete_all" => json!({"ok": true, "deleted": repo.delete_all()}),
            other => return Err(format!("no api {other}")),
        })
    }

    fn html(&self, repo: &Repo, o: &Value) -> Result<String, String> {
        let s = repo.settings();
        let a = parse_iso(o["start"].as_str().unwrap_or("")).ok_or("bad start")?;
        let b = parse_iso(o["end"].as_str().unwrap_or("")).ok_or("bad end")?;
        let mut rep = report::build(repo, a, b, o["unit"].as_str().filter(|u| !u.is_empty()).unwrap_or("decimal"));
        let name = st(&s, "display_name", "");
        if !name.is_empty() {
            rep["label"] = json!(format!("{name} · {}", rep["label"].as_str().unwrap_or("")));
        }
        let title = o["title"].as_str().filter(|t| !t.is_empty()).map(str::to_string).unwrap_or_else(|| td::title_from_pattern(st(&s, "title_pattern", "{เดือน}/{ปี}"), b));
        let columns: Vec<String> = o["columns"].as_array().map(|c| c.iter().filter_map(|x| x.as_str().map(str::to_string)).collect()).unwrap_or_default();
        let show = o["mascot"] == true && s.get("show_characters").and_then(Value::as_bool).unwrap_or(true);
        let mascot = show.then(|| strip_xml_decl(MASCOT_SVG));
        Ok(report::render_html(
            &rep,
            &report::PageOptions {
                title: &title,
                columns: &columns,
                footnote: o["footnote"] != false,
                timestamp: o["timestamp"] != false,
                mascot_svg: mascot,
                font_base: "fonts/",
                printed_at: self.now(),
            },
        ))
    }

    fn export_report(&self, o: &Value) -> Result<Value, String> {
        let fmt = if o["format"] == "png" { "png" } else { "pdf" };
        let title = o["title"].as_str().filter(|t| !t.is_empty()).unwrap_or("รายงาน").to_string();
        let filename = format!("{}.{fmt}", safe_file_name(&title));
        let html = {
            let con = self.lock()?;
            self.html(&Repo { con: &con }, o)?
        };
        let Some(path) = self.save_dialog(&filename, fmt) else { return Ok(cancelled()) };
        let out = match exporter::export(&html, &path, fmt) {
            Ok(out) => out,
            Err(e) => return Ok(json!({"ok": false, "error": e})),
        };
        let con = self.lock()?;
        let repo = Repo { con: &con };
        repo.add_export(&out.to_string_lossy(), fmt, &title);
        Ok(json!({"ok": true, "path": out.to_string_lossy(), "name": name_of(&out), "recent": recent(&repo)}))
    }

    fn backup(&self) -> Result<Value, String> {
        let name = format!("ตอกบัตร-สำรอง-{}.db", iso(self.today()));
        let Some(path) = self.save_dialog(&name, "db") else { return Ok(cancelled()) };
        let con = self.lock()?;
        if path.exists() {
            // the picker already asked whether to replace it
            let _ = std::fs::remove_file(&path);
        }
        if let Err(e) = con.backup(MAIN_DB, &path, None) {
            return Ok(json!({"ok": false, "error": format!("สำรองข้อมูลไม่สำเร็จ ({e})")}));
        }
        let now = self.now();
        Repo { con: &con }.save_settings(&json!({"last_backup": format!("{} {}", td::slash(now.date()), now.format("%H:%M"))}));
        Ok(json!({"ok": true, "path": path.to_string_lossy(), "name": name_of(&path)}))
    }

    fn restore(&self) -> Result<Value, String> {
        let Some(path) = self.open_dialog("db") else { return Ok(cancelled()) };
        if path.canonicalize().ok().is_some_and(|p| Some(p) == self.db_file.canonicalize().ok()) {
            return Ok(json!({"ok": false, "error": "ไฟล์นี้คือข้อมูลที่ใช้อยู่ตอนนี้ เลือกไฟล์สำรองอีกไฟล์นะ"}));
        }
        if !db::is_tokbat_db(&path) {
            return Ok(json!({"ok": false, "error": "ไฟล์นี้ไม่ใช่ไฟล์สำรองของตอกบัตร"}));
        }
        let mut con = self.lock()?;
        // keep what was there before, next to the data file
        let keep = self.db_file.with_file_name(format!("ก่อนกู้คืน-{}.db", self.now().format("%Y%m%d-%H%M%S")));
        con.backup(MAIN_DB, &keep, None).map_err(|e| format!("เก็บข้อมูลเดิมไว้ก่อนไม่สำเร็จ ({e})"))?;
        con.restore(MAIN_DB, &path, None::<fn(rusqlite::backup::Progress)>).map_err(|e| format!("กู้คืนไม่สำเร็จ ({e})"))?;
        db::migrate(&con).map_err(|e| e.to_string())?;
        Ok(json!({"ok": true, "count": Repo { con: &con }.count(), "kept": keep.to_string_lossy()}))
    }

    fn import_pick(&self) -> Result<Value, String> {
        let Some(path) = self.open_dialog("csv") else { return Ok(cancelled()) };
        let raw = match std::fs::read(&path) {
            Ok(r) => r,
            Err(e) => return Ok(json!({"ok": false, "error": format!("อ่านไฟล์ไม่ได้ ({e})")})),
        };
        let parsed = csv_io::parse(&raw);
        let con = self.lock()?;
        let repo = Repo { con: &con };
        let (mut rows, mut dup) = (vec![], 0);
        for r in parsed["rows"].as_array().into_iter().flatten() {
            let (Some(d), Ok(s)) = (parse_iso(r["date"].as_str().unwrap_or("")), tc::parse_hhmm(r["start"].as_str().unwrap_or(""))) else { continue };
            let e = r["end"].as_str().and_then(|e| tc::parse_hhmm(e).ok());
            if repo.exists(d, s, e) {
                dup += 1
            } else {
                rows.push(r.clone())
            }
        }
        let mut dates: Vec<&str> = rows.iter().filter_map(|r| r["date"].as_str()).collect();
        dates.sort();
        let label = match (dates.first().and_then(|a| parse_iso(a)), dates.last().and_then(|b| parse_iso(b))) {
            (Some(a), Some(b)) => format!("{} – {}", td::slash(a), td::slash(b)),
            _ => String::new(),
        };
        let token = format!("{:016x}", rand::random::<u64>());
        let count = rows.len();
        *self.pending.lock().unwrap() = HashMap::from([(token.clone(), rows)]);
        Ok(json!({"ok": true, "token": token, "count": count, "duplicates": dup,
                  "skipped": parsed["skipped"].as_array().map_or(0, Vec::len), "label": label, "name": name_of(&path)}))
    }
}

fn recent(repo: &Repo) -> Value {
    let list: Vec<Value> = repo
        .recent_exports(3)
        .into_iter()
        .map(|(path, format, created)| {
            let when = NaiveDateTime::parse_from_str(&created, "%Y-%m-%d %H:%M:%S").map(|w| format!("{} {}", w.day(), td::MONTH_SHORT[w.month() as usize])).unwrap_or_default();
            json!({"path": path, "name": name_of(Path::new(&path)), "format": format, "when": when})
        })
        .collect();
    json!(list)
}

fn strip_xml_decl(svg: &str) -> &str {
    let t = svg.trim_start();
    match t.strip_prefix("<?xml").and_then(|r| r.find("?>").map(|i| &r[i + 2..])) {
        Some(rest) => rest.trim_start(),
        None => t,
    }
}

/// Title → a name Windows accepts: runs of \ / : * ? " < > | become one "-", then trim " .-".
fn safe_file_name(title: &str) -> String {
    let mut out = String::new();
    let mut in_bad = false;
    for c in title.chars() {
        if r#"\/:*?"<>|"#.contains(c) {
            if !in_bad {
                out.push('-');
            }
            in_bad = true;
        } else {
            out.push(c);
            in_bad = false;
        }
    }
    let t = out.trim_matches(|c: char| c == ' ' || c == '.' || c == '-').to_string();
    if t.is_empty() { "รายงาน".into() } else { t }
}

fn range_label(a: NaiveDate, b: NaiveDate) -> String {
    let m = |d: NaiveDate| td::MONTH_SHORT[d.month() as usize];
    if a.month() == b.month() {
        format!("{}–{} {} {}", a.day(), b.day(), m(b), td::be_year(b))
    } else {
        format!("{} {} – {} {} {}", a.day(), m(a), b.day(), m(b), td::be_year(b))
    }
}

fn range_slash(a: NaiveDate, b: NaiveDate) -> String {
    format!("{}/{} – {}/{}/{}", a.day(), a.month(), b.day(), b.month(), td::be_year(b))
}

fn short_path(p: &Path) -> String {
    let parts: Vec<String> = p.components().map(|c| c.as_os_str().to_string_lossy().trim_end_matches('\\').to_string()).collect();
    if parts.len() > 3 { parts[parts.len() - 3..].join("\\") } else { p.to_string_lossy().to_string() }
}

/// Show a file in Explorer (or open its folder).
fn reveal(p: &Path) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let mut cmd = std::process::Command::new("explorer");
        if p.is_file() {
            cmd.raw_arg(format!("/select,\"{}\"", p.display()));
        } else {
            cmd.arg(if p.is_dir() { p } else { p.parent().unwrap_or(p) });
        }
        let _ = cmd.spawn();
    }
    #[cfg(not(windows))]
    let _ = p;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn file_names() {
        assert_eq!(safe_file_name("10/2569"), "10-2569");
        assert_eq!(safe_file_name("a:*?b."), "a-b");
        assert_eq!(safe_file_name("///"), "รายงาน");
        assert_eq!(strip_xml_decl("<?xml version=\"1.0\"?>\n<svg/>"), "<svg/>");
        assert_eq!(strip_xml_decl("<svg/>"), "<svg/>");
    }
}
