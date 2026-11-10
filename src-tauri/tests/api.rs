//! Same checks as legacy-python/tests/test_api.py, through `Api::call` exactly as the window calls it.

use chrono::NaiveDate;
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use tokbat_lib::api::{Api, Dialogs};

fn fixture() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../fixtures/sample-sheet.csv")
}

struct FakeDialogs {
    tmp: PathBuf,
    open_path: Arc<Mutex<PathBuf>>,
}
impl Dialogs for FakeDialogs {
    fn save(&self, filename: &str, _kind: &str) -> Option<PathBuf> {
        Some(self.tmp.join(filename))
    }
    fn open(&self, _kind: &str) -> Option<PathBuf> {
        Some(self.open_path.lock().unwrap().clone())
    }
}

struct T {
    api_: Option<Api>,
    tmp: PathBuf,
    open_path: Arc<Mutex<PathBuf>>,
}
impl T {
    fn api(&self) -> &Api {
        self.api_.as_ref().unwrap()
    }
    fn call(&self, m: &str, args: Value) -> Value {
        self.api().call(m, args.as_array().unwrap()).unwrap_or_else(|e| panic!("{m}: {e}"))
    }
    fn at(&self, h: u32, mi: u32) {
        let now = NaiveDate::from_ymd_opt(2026, 11, 10).unwrap().and_hms_opt(h, mi, 0).unwrap();
        self.api().set_clock(Box::new(|| NaiveDate::from_ymd_opt(2026, 11, 10).unwrap()), Box::new(move || now));
    }
}
impl Drop for T {
    fn drop(&mut self) {
        self.api_ = None; // close the database first, Windows won't delete an open file
        let _ = std::fs::remove_dir_all(&self.tmp);
    }
}

fn api() -> T {
    let tmp = std::env::temp_dir().join(format!("tokbat-test-{}-{:x}", std::process::id(), rand::random::<u64>()));
    std::fs::create_dir_all(&tmp).unwrap();
    let open_path = Arc::new(Mutex::new(fixture()));
    let api = Api::new(tmp.join("worktime.db"), Some(Box::new(FakeDialogs { tmp: tmp.clone(), open_path: open_path.clone() }))).unwrap();
    let t = T { api_: Some(api), tmp, open_path };
    t.at(13, 28);
    t
}

fn import_sample(t: &T) {
    let pre = t.call("import_pick", json!([]));
    assert_eq!((pre["ok"].as_bool(), pre["count"].as_i64()), (Some(true), Some(22)));
    assert_eq!(pre["label"], "1/3/2569 – 20/3/2569");
    let res = t.call("import_commit", json!([pre["token"]]));
    assert_eq!(res, json!({"ok": true, "added": 22, "conflicts": 0}));
}

#[test]
fn first_run_and_import() {
    let t = api();
    assert_eq!(t.call("bootstrap", json!([]))["count"], 0);
    import_sample(&t);
    let again = t.call("import_pick", json!([]));
    assert_eq!((again["count"].as_i64(), again["duplicates"].as_i64()), (Some(0), Some(22)));
    assert_eq!(t.call("bootstrap", json!([]))["settings"]["first_run_done"], true);
}

#[test]
fn day_view_and_week() {
    let t = api();
    import_sample(&t);
    let d = t.call("day", json!(["2026-03-03"]));
    assert_eq!(d["label"], "อ. 3 มี.ค. 2569");
    assert_eq!(d["sessions"].as_array().unwrap().len(), 2);
    assert_eq!(d["total_min"], 630);
    let states: Vec<&str> = d["week"]["days"].as_array().unwrap().iter().map(|x| x["state"].as_str().unwrap()).collect();
    assert_eq!(states[..3], ["empty", "done", "done"]); // Mon 2 Mar had no work
    assert_eq!(d["week"]["label"], "2–8 มี.ค. 2569");
}

#[test]
fn missing_day_after_last_entry() {
    let t = api();
    t.call("save_session", json!([{"date": "2026-11-05", "start": "09:00", "end": "17:00"}]));
    let d = t.call("day", json!(["2026-11-10"]));
    assert_eq!(d["missing"], json!({"date": "2026-11-09", "label": "จ. 9 พ.ย."}));
}

#[test]
fn periods() {
    let t = api();
    let p = t.call("period", json!(["cycle", "2026-11-10", 0]));
    assert_eq!((&p["start"], &p["end"], &p["title"]), (&json!("2026-10-21"), &json!("2026-11-20"), &json!("11/2569")));
    let w = t.call("period", json!(["week", "2026-11-10", -1]));
    assert_eq!((&w["start"], &w["end"]), (&json!("2026-11-02"), &json!("2026-11-08")));
    let prev = t.call("period", json!(["cycle", "2026-11-10", -1]));
    assert_eq!((&prev["start"], &prev["end"]), (&json!("2026-09-21"), &json!("2026-10-20")));
}

#[test]
fn history_search() {
    let t = api();
    import_sample(&t);
    let h = t.call("history", json!(["2026-03-01", "2026-03-20", "ลูกค้า"]));
    assert_eq!(h["count"], 1);
    assert_eq!(h["groups"][0]["slash"], "17/3/2569");
}

#[test]
fn report_and_export_pdf_png() {
    let t = api();
    import_sample(&t);
    let r = t.call("report", json!(["2026-03-01", "2026-03-20"]));
    assert_eq!((&r["total"], &r["default_title"]), (&json!("124.67"), &json!("3/2569")));
    let opts = json!({"start": "2026-03-01", "end": "2026-03-20", "title": "3/2569", "unit": "decimal",
                      "columns": ["date", "start", "end", "hours", "note"], "footnote": true, "timestamp": true, "mascot": true});
    assert!(t.call("report_preview", json!([opts])).as_str().unwrap().contains("จำนวนทั้งหมด : 124.67"));
    let mut o = opts.clone();
    o["format"] = json!("pdf");
    let pdf = t.call("export_report", json!([o]));
    assert_eq!(pdf["ok"], true, "{pdf}");
    assert_eq!(pdf["name"], "3-2569.pdf");
    assert!(std::fs::metadata(pdf["path"].as_str().unwrap()).unwrap().len() > 10_000);
    o["format"] = json!("png");
    let png = t.call("export_report", json!([o]));
    assert_eq!(png["ok"], true, "{png}");
    assert_eq!(png["name"], "3-2569.png");
    let formats: Vec<&str> = png["recent"].as_array().unwrap().iter().map(|x| x["format"].as_str().unwrap()).collect();
    assert_eq!(formats[..2], ["png", "pdf"]);
    // the PNG is the whole page at 2x: 1588 px wide and taller than it is wide
    let bytes = std::fs::read(png["path"].as_str().unwrap()).unwrap();
    let (w, h) = (u32::from_be_bytes(bytes[16..20].try_into().unwrap()), u32::from_be_bytes(bytes[20..24].try_into().unwrap()));
    assert_eq!(w, 1588);
    assert!(h > w, "png {w}x{h}");
}

#[test]
fn open_session_start_stop() {
    let t = api();
    let started = t.call("start_now", json!([]));
    assert_eq!((started["ok"].as_bool(), started["session"]["open"].as_bool()), (Some(true), Some(true)));
    t.at(18, 0);
    let stopped = t.call("stop_now", json!([started["session"]["id"]]));
    assert_eq!(stopped["ok"], true);
    assert_eq!(stopped["session"]["end"], "18:00");
    assert_eq!(stopped["session"]["hours"], "4.53");
}

#[test]
fn backup_restore_roundtrip() {
    let t = api();
    import_sample(&t);
    let b = t.call("backup", json!([]));
    assert_eq!(b["ok"], true, "{b}");
    t.call("delete_all", json!([]));
    assert_eq!(t.call("bootstrap", json!([]))["count"], 0);
    *t.open_path.lock().unwrap() = PathBuf::from(b["path"].as_str().unwrap());
    let r = t.call("restore", json!([]));
    assert_eq!((r["ok"].as_bool(), r["count"].as_i64()), (Some(true), Some(22)), "{r}");
    assert!(Path::new(r["kept"].as_str().unwrap()).exists());
}

#[test]
fn restore_rejects_other_files() {
    let t = api();
    let bad = t.tmp.join("x.db");
    std::fs::write(&bad, b"not sqlite").unwrap();
    *t.open_path.lock().unwrap() = bad;
    assert_eq!(t.call("restore", json!([])), json!({"ok": false, "error": "ไฟล์นี้ไม่ใช่ไฟล์สำรองของตอกบัตร"}));
}

#[test]
fn day_off_shows_in_day_and_week() {
    let t = api();
    t.call("save_session", json!([{"date": "2026-11-05", "start": "09:00", "end": "17:00"}]));
    assert_eq!(t.call("day", json!(["2026-11-10"]))["missing"]["date"], "2026-11-09");
    t.call("mark_day_off", json!(["2026-11-09"]));
    t.call("mark_day_off", json!(["2026-11-12"])); // a planned day off in the future
    let d = t.call("day", json!(["2026-11-09"]));
    assert_eq!(d["off"], true);
    let days = d["week"]["days"].as_array().unwrap();
    let state = |date: &str| days.iter().find(|x| x["date"] == date).map(|x| (x["state"].clone(), x["sub"].clone())).unwrap();
    assert_eq!(state("2026-11-09"), (json!("off"), json!("หยุด")));
    assert_eq!(state("2026-11-12"), (json!("off"), json!("หยุด")));
    assert_ne!(t.call("day", json!(["2026-11-10"]))["missing"]["date"], "2026-11-09");
    t.call("unmark_day_off", json!(["2026-11-09"]));
    assert_eq!(t.call("day", json!(["2026-11-09"]))["off"], false);
    assert_eq!(t.call("day", json!(["2026-11-10"]))["missing"]["date"], "2026-11-09");
}

#[test]
fn unknown_method_is_an_error() {
    let t = api();
    assert!(t.api().call("drop_tables", &[]).is_err());
}
