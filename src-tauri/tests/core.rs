//! Same checks as legacy-python/tests/test_core.py — the Rust version must give the same answers.

use chrono::{NaiveDate, NaiveDateTime};
use rusqlite::Connection;
use serde_json::{Value, json};
use std::path::Path;

use tokbat_lib::repo::Repo;
use tokbat_lib::thaidate as td;
use tokbat_lib::timecalc as tc;
use tokbat_lib::{csv_io, db, report};

const FIXTURE: &[u8] = include_bytes!("../../fixtures/sample-sheet.csv");

fn d(y: i32, m: u32, dd: u32) -> NaiveDate {
    NaiveDate::from_ymd_opt(y, m, dd).unwrap()
}
fn at(y: i32, m: u32, dd: u32, h: u32, mi: u32) -> NaiveDateTime {
    d(y, m, dd).and_hms_opt(h, mi, 0).unwrap()
}
fn now() -> NaiveDateTime {
    at(2026, 11, 10, 13, 28)
}
fn con() -> Connection {
    db::connect(Path::new(":memory:")).unwrap()
}
fn sample(c: &Connection) {
    let repo = Repo { con: c };
    for r in csv_io::parse(FIXTURE)["rows"].as_array().unwrap() {
        assert_eq!(repo.save(r, now())["ok"], true, "{r}");
    }
}

// ---------- time arithmetic ----------
#[test]
fn parse_and_format() {
    assert_eq!(tc::parse_hhmm("3:00:00"), Ok(180));
    assert_eq!(tc::parse_hhmm("21:00"), Ok(1260));
    assert_eq!(tc::parse_hhmm("24:00"), Ok(0));
    assert_eq!(tc::fmt_hhmm(1260), "21:00");
    assert!(tc::parse_hhmm("25:00").is_err());
    assert!(tc::parse_hhmm("abc").is_err());
}

#[test]
fn overnight_span() {
    let p = |s| tc::parse_hhmm(s).unwrap();
    assert_eq!(tc::span_minutes(p("21:00"), p("03:00")), Ok(360));
    assert_eq!(tc::span_minutes(p("21:00"), p("00:00")), Ok(180));
    assert_eq!(tc::span_minutes(p("13:00"), p("19:00")), Ok(360));
    assert!(tc::span_minutes(600, 600).is_err());
}

#[test]
fn break_rules() {
    assert_eq!(tc::net_minutes(540, 1110, 60), Ok(510));
    assert!(tc::net_minutes(540, 600, 60).is_err());
}

#[test]
fn decimal_rounding_half_up() {
    assert_eq!(tc::to_decimal_hours(260), "4.33"); // 4:20
    assert_eq!(tc::to_decimal_hours(415), "6.92"); // 6:55
    assert_eq!(tc::to_decimal_hours(470), "7.83"); // 7:50
    assert_eq!(tc::to_decimal_hours(405), "6.75");
    assert_eq!(tc::to_hm(10410), "173:30");
}

// ---------- calendar ----------
#[test]
fn thai_dates() {
    assert_eq!(td::slash(d(2026, 9, 1)), "1/9/2569");
    assert_eq!(td::parse_slash("20/9/2569"), Some(d(2026, 9, 20)));
    assert_eq!(td::short(d(2026, 11, 10)), "อ. 10 พ.ย. 2569");
}

#[test]
fn cycles() {
    assert_eq!(td::cycle_for(d(2026, 11, 10), "cutoff", 20), (d(2026, 10, 21), d(2026, 11, 20)));
    assert_eq!(td::cycle_for(d(2026, 11, 25), "cutoff", 20), (d(2026, 11, 21), d(2026, 12, 20)));
    assert_eq!(td::cycle_for(d(2026, 1, 5), "cutoff", 20), (d(2025, 12, 21), d(2026, 1, 20)));
    assert_eq!(td::cycle_for(d(2026, 2, 10), "month", 20), (d(2026, 2, 1), d(2026, 2, 28)));
    let (_, e) = td::cycle_for(d(2026, 11, 10), "cutoff", 20);
    assert_eq!(td::shift_cycle(e, -1, "cutoff", 20), (d(2026, 9, 21), d(2026, 10, 20)));
    assert_eq!(td::title_from_pattern("{เดือน}/{ปี}", e), "11/2569");
}

// ---------- a made-up sheet in the same layout as the user's Google Sheet ----------
#[test]
fn csv_reads_the_sheet_layout() {
    let out = csv_io::parse(FIXTURE);
    assert_eq!(out["rows"].as_array().unwrap().len(), 22);
    assert_eq!(out["skipped"], json!([]));
    assert_eq!(out["rows"][0], json!({"date": "2026-03-01", "start": "21:00", "end": "02:30", "note": "ออกแบบหน้าจอ"}));
}

#[test]
fn report_matches_sheet_rows_and_sums_minutes() {
    let c = con();
    sample(&c);
    let rep = report::build(&Repo { con: &c }, d(2026, 3, 1), d(2026, 3, 20), "decimal");
    let hours: Vec<&str> = rep["rows"].as_array().unwrap().iter().map(|r| r["hours_text"].as_str().unwrap()).collect();
    assert_eq!(hours[..7], ["5.50", "5.33", "5.17", "8.17", "6.25", "6.83", "6.83"]);
    assert_eq!((rep["sessions"].as_i64(), rep["days"].as_i64(), rep["overnight"].as_i64()), (Some(22), Some(18), Some(11)));
    assert_eq!(rep["avg"], "6.93"); // 124.67 / 18 = 6.926, half-up
    // a sheet that rounds each row first gets 124.65; minutes say 124:40
    assert_eq!(rep["total"], "124.67");
    assert_eq!(rep["total_hm"], "124 ชม. 40 นาที");
    let row_sum: f64 = hours.iter().map(|h| h.parse::<f64>().unwrap()).sum();
    assert!((row_sum - 124.65).abs() < 1e-6, "{row_sum}");
    let day3 = rep["per_day"].as_array().unwrap().iter().find(|x| x["day"] == 3).unwrap();
    assert_eq!((day3["day_min"].as_i64(), day3["night_min"].as_i64()), (Some(320), Some(310)));
}

#[test]
fn report_hm_unit() {
    let c = con();
    sample(&c);
    let rep = report::build(&Repo { con: &c }, d(2026, 3, 4), d(2026, 3, 4), "hm");
    assert_eq!(rep["rows"][0]["hours_text"], "8:10");
}

#[test]
fn report_html_renders_thai_and_columns() {
    let c = con();
    sample(&c);
    let rep = report::build(&Repo { con: &c }, d(2026, 3, 1), d(2026, 3, 20), "decimal");
    let cols: Vec<String> = ["date", "start", "end", "hours", "note"].map(String::from).to_vec();
    let html = report::render_html(&rep, &report::PageOptions {
        title: "3/2569", columns: &cols, footnote: true, timestamp: true, mascot_svg: None, font_base: "fonts/", printed_at: now(),
    });
    assert!(html.contains("3/2569") && html.contains("จำนวนทั้งหมด : 124.67"));
    assert!(html.contains("พิมพ์เมื่อ 10/11/2569 13:28"));
    assert!(html.contains("หน่วยเป็นทศนิยม"));
    assert!(!html.contains("<th class=\"c-break\">"));
    assert!(html.contains("url(\"fonts/IBMPlexSansThaiLooped-Regular.ttf\")"));
    assert!(html.contains("<td class=\"c-date\">1/3/2569</td>"));
}

// ---------- saving rules ----------
fn save(repo: &Repo, v: Value) -> Value {
    repo.save(&v, now())
}

#[test]
fn overlap_same_day() {
    let c = con();
    let repo = Repo { con: &c };
    assert_eq!(save(&repo, json!({"date": "2026-11-10", "start": "13:00", "end": "19:00"}))["ok"], true);
    let res = save(&repo, json!({"date": "2026-11-10", "start": "18:00", "end": "03:00"}));
    assert_eq!(res["ok"], false);
    assert_eq!(res["error"]["code"], "overlap");
    assert_eq!(res["error"]["suggest_start"], "19:00");
    assert_eq!(res["error"]["overlap_min"], 60);
}

#[test]
fn overnight_spills_into_next_day() {
    let c = con();
    let repo = Repo { con: &c };
    assert_eq!(save(&repo, json!({"date": "2026-11-10", "start": "21:00", "end": "03:00"}))["ok"], true);
    let res = save(&repo, json!({"date": "2026-11-11", "start": "02:00", "end": "05:00"}));
    assert_eq!((res["ok"].as_bool(), res["error"]["overlap_min"].as_i64()), (Some(false), Some(60)));
    assert_eq!(save(&repo, json!({"date": "2026-11-11", "start": "03:00", "end": "05:00"}))["ok"], true);
}

#[test]
fn edit_does_not_clash_with_itself() {
    let c = con();
    let repo = Repo { con: &c };
    let mut s = save(&repo, json!({"date": "2026-11-10", "start": "09:00", "end": "12:00"}))["session"].clone();
    s["end"] = json!("12:30");
    let res = repo.save(&s, now());
    assert_eq!(res["ok"], true);
    assert_eq!(res["previous"]["end"], "12:00");
    assert_eq!(res["session"]["end"], "12:30");
}

#[test]
fn delete_and_undo() {
    let c = con();
    let repo = Repo { con: &c };
    let s = save(&repo, json!({"date": "2026-11-10", "start": "09:00", "end": "12:00", "note": "x"}))["session"].clone();
    let gone = repo.delete(s["id"].as_i64().unwrap()).unwrap();
    assert_eq!(repo.count(), 0);
    let back = repo.restore(&gone).unwrap();
    assert_eq!(back["id"], s["id"]);
    assert_eq!(back["note"], "x");
}

#[test]
fn open_session_and_missing_days() {
    let c = con();
    let repo = Repo { con: &c };
    save(&repo, json!({"date": "2026-11-05", "start": "09:00", "end": "17:00"}));
    let res = repo.save(&json!({"date": "2026-11-10", "start": "13:05", "end": null}), at(2026, 11, 10, 14, 0));
    assert_eq!(res["ok"], true);
    assert_eq!(res["session"]["open"], true);
    assert_eq!(repo.open_session().unwrap()["id"], res["session"]["id"]);
    assert_eq!(repo.missing_days(d(2026, 11, 10), 14), ["2026-11-09", "2026-11-08", "2026-11-07", "2026-11-06"]);
    repo.mark_day_off(d(2026, 11, 8));
    assert!(!repo.missing_days(d(2026, 11, 10), 14).contains(&"2026-11-08".to_string()));
}

#[test]
fn settings_roundtrip() {
    let c = con();
    let repo = Repo { con: &c };
    assert_eq!(repo.settings()["unit"], "decimal");
    let s = repo.save_settings(&json!({"unit": "hm", "cutoff_day": 25, "unknown": 1}));
    assert_eq!(s["unit"], "hm");
    assert_eq!(s["cutoff_day"], 25);
    assert!(!s.contains_key("unknown"));
}

/// The Python app stored settings with json.dumps; make sure a database it wrote reads back the same.
#[test]
fn reads_settings_written_by_python() {
    let c = con();
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('display_name', '\"\\u0e19\\u0e32\\u0e22 \\u0e01\"'), ('cutoff_day', '25'), ('remind_missing', 'false')", []).unwrap();
    let s = Repo { con: &c }.settings();
    assert_eq!(s["display_name"], "นาย ก");
    assert_eq!(s["cutoff_day"], 25);
    assert_eq!(s["remind_missing"], false);
}

#[test]
fn day_off_mark_unmark_and_cleared_by_work() {
    let c = con();
    let repo = Repo { con: &c };
    repo.mark_day_off(d(2026, 11, 8));
    repo.mark_day_off(d(2026, 11, 9));
    assert_eq!(repo.days_off(d(2026, 11, 1), d(2026, 11, 30)).len(), 2);
    repo.unmark_day_off(d(2026, 11, 8));
    assert!(!repo.days_off(d(2026, 11, 1), d(2026, 11, 30)).contains("2026-11-08"));
    // logging work on a day off turns it back into a work day
    assert_eq!(save(&repo, json!({"date": "2026-11-09", "start": "09:00", "end": "12:00"}))["ok"], true);
    assert!(repo.days_off(d(2026, 11, 1), d(2026, 11, 30)).is_empty());
}

#[test]
fn report_counts_days_off() {
    let c = con();
    sample(&c);
    let repo = Repo { con: &c };
    repo.mark_day_off(d(2026, 3, 21));
    repo.mark_day_off(d(2026, 3, 22));
    let rep = report::build(&repo, d(2026, 3, 1), d(2026, 3, 31), "decimal");
    assert_eq!(rep["days_off"], 2);
    assert_eq!(rep["total"], "124.67"); // a day off adds no rows or hours
}
