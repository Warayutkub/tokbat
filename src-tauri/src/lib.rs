//! ตอกบัตร — work-time log that stays on this computer.

pub mod api;
pub mod csv_io;
pub mod db;
pub mod exporter;
pub mod game;
pub mod packs;
pub mod repo;
pub mod report;
pub mod serve;
pub mod thaidate;
pub mod timecalc;

use serde_json::{Value, json};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::webview::PageLoadEvent;
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::{DialogExt, MessageDialogKind};

use api::{Api, Dialogs};

pub const APP_TITLE: &str = "ตอกบัตร";

pub fn documents_dir() -> PathBuf {
    dirs::document_dir().or_else(|| dirs::home_dir().map(|h| h.join("Documents"))).unwrap_or_else(|| PathBuf::from("."))
}

/// Documents\ตอกบัตร (same folder the Python version used), or TOKBAT_DATA_DIR.
pub fn data_dir() -> PathBuf {
    std::env::var("TOKBAT_DATA_DIR").map(PathBuf::from).unwrap_or_else(|_| documents_dir().join(APP_TITLE))
}

/// A windowed app has no console: keep crash details in a log next to the data.
fn install_panic_log() {
    let default = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let log = data_dir().join("error.log");
        let _ = std::fs::create_dir_all(data_dir());
        let text = format!("\n--- {}\n{info}\n{}\n", chrono::Local::now().format("%Y-%m-%d %H:%M:%S"), std::backtrace::Backtrace::force_capture());
        let _ = std::fs::OpenOptions::new().create(true).append(true).open(log).and_then(|mut f| std::io::Write::write_all(&mut f, text.as_bytes()));
        default(info);
    }));
}

/// Native file pickers, parented to the main window. Remembers the last folder used for saving.
struct WindowDialogs {
    app: AppHandle,
    last_dir: Mutex<PathBuf>,
}

fn filter(kind: &str) -> (&'static str, &'static [&'static str]) {
    match kind {
        "pdf" => ("ไฟล์ PDF", &["pdf"]),
        "png" => ("รูปภาพ PNG", &["png"]),
        "db" => ("ไฟล์สำรองตอกบัตร", &["db"]),
        _ => ("ไฟล์ CSV", &["csv"]),
    }
}

impl WindowDialogs {
    fn builder(&self, kind: &str, dir: PathBuf) -> tauri_plugin_dialog::FileDialogBuilder<tauri::Wry> {
        let (name, ext) = filter(kind);
        let mut b = self.app.dialog().file().add_filter(name, ext).set_directory(dir);
        if let Some(w) = self.app.get_webview_window("main") {
            b = b.set_parent(&w);
        }
        b
    }
}

impl Dialogs for WindowDialogs {
    fn save(&self, filename: &str, kind: &str) -> Option<PathBuf> {
        let dir = self.last_dir.lock().unwrap().clone();
        let path = self.builder(kind, dir).set_file_name(filename).blocking_save_file()?.into_path().ok()?;
        if let Some(parent) = path.parent() {
            *self.last_dir.lock().unwrap() = parent.to_path_buf();
        }
        Some(path)
    }
    fn open(&self, kind: &str) -> Option<PathBuf> {
        let dir = if kind == "db" { data_dir() } else { self.last_dir.lock().unwrap().clone() };
        let mut b = self.builder(kind, dir);
        if kind == "db" || kind == "csv" {
            b = b.add_filter("ทุกไฟล์", &["*"]);
        }
        b.blocking_pick_file()?.into_path().ok()
    }
}

/// The one command the web UI uses: `invoke("api", {method, args})`. Runs off the main thread so pickers and
/// the PDF export never freeze the window.
#[tauri::command]
async fn api(state: tauri::State<'_, Arc<Api>>, method: String, args: Vec<Value>) -> Result<Value, String> {
    let api = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| api.call(&method, &args))).unwrap_or_else(|_| Err(format!("เกิดข้อผิดพลาดภายใน ({method})")))
    })
    .await
    .map_err(|e| e.to_string())?
}

// ---------- app updates (Tauri updater; releases/latest/download/latest.json, signed in CI) ----------

/// {available, version, notes} or {available: false}. Errors (offline, no release yet) come back as Err text.
#[tauri::command]
async fn update_check(app: AppHandle) -> Result<Value, String> {
    use tauri_plugin_updater::UpdaterExt;
    let current = app.package_info().version.to_string();
    match app.updater().map_err(|e| e.to_string())?.check().await.map_err(|e| e.to_string())? {
        Some(u) => Ok(json!({"available": true, "current": current, "version": u.version, "notes": u.body})),
        None => Ok(json!({"available": false, "current": current})),
    }
}

/// Downloads the signed installer, runs it (Windows closes the app for that) and opens the new version.
#[tauri::command]
async fn update_install(app: AppHandle) -> Result<(), String> {
    use tauri_plugin_updater::UpdaterExt;
    let Some(u) = app.updater().map_err(|e| e.to_string())?.check().await.map_err(|e| e.to_string())? else {
        return Err("ไม่มีเวอร์ชันใหม่แล้ว".into());
    };
    u.download_and_install(|_, _| {}, || {}).await.map_err(|e| e.to_string())?;
    app.restart();
}

// ---------- self-test: `tokbat.exe --selftest <folder>` runs a hidden window on throwaway data ----------

struct Selftest {
    out: PathBuf,
    started: AtomicBool,
}

const SELFTEST_JS: &str = r##"
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const call = (step, res) => window.__TAURI__.core.invoke("selftest", { step, res: res || {} });
  const res = {};
  try {
    await sleep(2500);
    res.welcome = !!document.querySelector(".welcome");
    res.font = document.fonts.check("600 26px Looped");
    res.mascots = document.querySelectorAll("svg.chalk").length;
    res.tauri_api = (await window.__TAURI__.core.invoke("api", { method: "bootstrap", args: [] })).count === 0;
    await call("seed");
    location.hash = "#/report?kind=custom&start=2026-09-01&end=2026-09-02";
    await sleep(2500);
    res.report_total = document.querySelector(".big")?.textContent;
    // the updater is set up (key + endpoint); before the first signed release the endpoint has no latest.json yet
    res.update = await window.__TAURI__.core.invoke("update_check").then((r) => `ok available=${r.available}`, (e) => `err ${e}`);
  } catch (e) {
    res.error = String((e && e.stack) || e);
  }
  await call("done", res);
})();
"##;

struct SaveTo(PathBuf);
impl Dialogs for SaveTo {
    fn save(&self, filename: &str, _kind: &str) -> Option<PathBuf> {
        Some(self.0.join(filename))
    }
    fn open(&self, _kind: &str) -> Option<PathBuf> {
        None
    }
}

#[tauri::command]
async fn selftest(app: AppHandle, step: String, res: Value) -> Result<(), String> {
    let Some(t) = app.try_state::<Selftest>() else { return Err("not in self-test".into()) };
    let out = t.out.clone();
    let api = app.state::<Arc<Api>>().inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        if step == "seed" {
            for (d, s, e) in [("2026-09-01", "21:00", "03:00"), ("2026-09-02", "13:00", "19:00"), ("2026-09-02", "21:00", "03:00")] {
                let _ = api.call("save_session", &[json!({"date": d, "start": s, "end": e, "note": "selftest"})]);
            }
            return;
        }
        let mut res = res;
        api.set_dialogs(Box::new(SaveTo(out.clone())));
        let opts = json!({"start": "2026-09-01", "end": "2026-09-02", "title": "selftest", "unit": "decimal",
                          "columns": ["date", "start", "end", "hours", "note"], "footnote": true, "timestamp": true, "mascot": true});
        for fmt in ["pdf", "png"] {
            let mut o = opts.clone();
            o["format"] = json!(fmt);
            let r = api.call("export_report", &[o]).unwrap_or_else(|e| json!({"ok": false, "error": e}));
            res[fmt] = match r["path"].as_str() {
                Some(p) if r["ok"] == true => json!(std::fs::metadata(p).map(|m| m.len()).unwrap_or(0)),
                _ => r,
            };
        }
        let ok = res["welcome"] == true
            && res["font"] == true
            && res["mascots"].as_u64().unwrap_or(0) > 0
            && res["tauri_api"] == true
            && res["report_total"] == "18.00"
            && res["pdf"].as_u64().unwrap_or(0) > 10_000
            && res["png"].as_u64().unwrap_or(0) > 10_000;
        res["ok"] = json!(ok);
        let _ = std::fs::write(out.join("results.json"), serde_json::to_string_pretty(&res).unwrap_or_default());
        app.exit(if ok { 0 } else { 1 });
    })
    .await
    .map_err(|e| e.to_string())
}

pub fn run(selftest_out: Option<PathBuf>) {
    install_panic_log();
    let db_file = match &selftest_out {
        Some(_) => std::env::temp_dir().join(format!("tokbat-selftest-{}", std::process::id())).join("worktime.db"),
        None => data_dir().join("worktime.db"),
    };
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![api, selftest, update_check, update_install])
        .on_page_load(|webview, payload| {
            if payload.event() != PageLoadEvent::Finished {
                return;
            }
            if let Some(t) = webview.try_state::<Selftest>() {
                if !t.started.swap(true, Ordering::SeqCst) {
                    let _ = webview.eval(SELFTEST_JS);
                }
            }
        })
        .setup(move |app| {
            let handle = app.handle().clone();
            if let Some(out) = selftest_out {
                std::fs::create_dir_all(&out)?;
                app.manage(Selftest { out, started: AtomicBool::new(false) });
            }
            match Api::new(db_file, None) {
                Ok(api) => {
                    if app.try_state::<Selftest>().is_none() {
                        api.set_dialogs(Box::new(WindowDialogs { app: handle.clone(), last_dir: Mutex::new(documents_dir()) }));
                        if let Some(w) = app.get_webview_window("main") {
                            w.show()?;
                            w.set_focus().ok();
                        }
                    }
                    app.manage(Arc::new(api));
                }
                Err(e) => {
                    let log = data_dir().join("error.log");
                    let _ = std::fs::write(&log, &e);
                    app.dialog()
                        .message(format!("ตอกบัตรเปิดไม่สำเร็จ\n{e}\n\nรายละเอียดอยู่ที่ {}", log.display()))
                        .title(APP_TITLE)
                        .kind(MessageDialogKind::Error)
                        .show(move |_| handle.exit(1));
                }
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
