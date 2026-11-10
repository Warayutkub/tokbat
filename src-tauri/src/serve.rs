//! Development only: run the UI in a normal browser. Serves web/ and answers POST /api/<method> with the real Api.
//!
//! ```text
//! npm run serve          (= cargo run -- --serve 5177)
//! ```
//!
//! Data goes to .dev-data/ (or TOKBAT_DATA_DIR), never the real Documents folder.

use serde_json::Value;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tiny_http::{Header, Method, Request, Response, Server};

use crate::api::{Api, Dialogs};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

/// No native pickers in a browser: saves go to .dev-data/exports, opens use TOKBAT_DEV_OPEN or a sample.
struct DevDialogs {
    dev: PathBuf,
}
impl Dialogs for DevDialogs {
    fn save(&self, filename: &str, _kind: &str) -> Option<PathBuf> {
        let dir = self.dev.join("exports");
        std::fs::create_dir_all(&dir).ok()?;
        Some(dir.join(filename))
    }
    fn open(&self, kind: &str) -> Option<PathBuf> {
        if let Ok(p) = std::env::var("TOKBAT_DEV_OPEN") {
            return Some(PathBuf::from(p));
        }
        if kind == "csv" {
            return Some(root().join("fixtures").join("sample-sheet.csv"));
        }
        let mut dbs: Vec<PathBuf> = std::fs::read_dir(self.dev.join("exports")).ok()?.filter_map(|e| e.ok().map(|e| e.path())).filter(|p| p.extension().is_some_and(|x| x == "db")).collect();
        dbs.sort();
        dbs.pop()
    }
}

fn content_type(p: &Path) -> &'static str {
    match p.extension().and_then(|x| x.to_str()).unwrap_or("") {
        "html" => "text/html; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "js" | "mjs" => "text/javascript; charset=utf-8",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "ico" => "image/x-icon",
        "ttf" => "font/ttf",
        "woff2" => "font/woff2",
        "json" => "application/json",
        "txt" => "text/plain; charset=utf-8",
        _ => "application/octet-stream",
    }
}

fn header(k: &str, v: &str) -> Header {
    Header::from_bytes(k.as_bytes(), v.as_bytes()).unwrap()
}

fn handle(api: &Api, web: &Path, mut rq: Request) {
    let url = rq.url().split(['?', '#']).next().unwrap_or("/").to_string();
    let no_store = header("Cache-Control", "no-store");
    if *rq.method() == Method::Post {
        let Some(name) = url.strip_prefix("/api/") else {
            let _ = rq.respond(Response::from_string("not found").with_status_code(404));
            return;
        };
        let mut body = String::new();
        let _ = rq.as_reader().read_to_string(&mut body);
        let args: Vec<Value> = serde_json::from_str(if body.trim().is_empty() { "[]" } else { &body }).unwrap_or_default();
        let res = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| api.call(name, &args))).unwrap_or_else(|_| Err(format!("panic in {name}")));
        let resp = match res {
            Ok(v) => Response::from_string(v.to_string()).with_header(header("content-type", "application/json; charset=utf-8")),
            Err(e) => {
                eprintln!("api {name}: {e}");
                Response::from_string(e).with_status_code(500)
            }
        };
        let _ = rq.respond(resp.with_header(no_store));
        return;
    }
    let rel = url.trim_start_matches('/');
    let rel = if rel.is_empty() { "index.html" } else { rel };
    let decoded = percent_decode(rel);
    if decoded.split('/').any(|p| p == "..") {
        let _ = rq.respond(Response::from_string("no").with_status_code(403));
        return;
    }
    let path = web.join(&decoded);
    match std::fs::read(&path) {
        Ok(mut bytes) => {
            if decoded == "index.html" {
                let html = String::from_utf8_lossy(&bytes).replacen("<head>", "<head><script>window.TOKBAT_HTTP=1</script>", 1);
                bytes = html.into_bytes();
            }
            let _ = rq.respond(Response::from_data(bytes).with_header(header("content-type", content_type(&path))).with_header(no_store));
        }
        Err(_) => {
            let _ = rq.respond(Response::from_string("not found").with_status_code(404));
        }
    }
}

fn percent_decode(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            if let Ok(v) = u8::from_str_radix(std::str::from_utf8(&b[i + 1..i + 3]).unwrap_or("zz"), 16) {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// `data`: folder for this server's database (default TOKBAT_DATA_DIR, then .dev-data/).
pub fn run(port: u16, data: Option<PathBuf>) {
    let dev = data.or_else(|| std::env::var("TOKBAT_DATA_DIR").ok().map(PathBuf::from)).unwrap_or_else(|| root().join(".dev-data"));
    let api = Arc::new(Api::new(dev.join("worktime.db"), Some(Box::new(DevDialogs { dev: dev.clone() }))).expect("open dev database"));
    let web = Arc::new(root().join("web"));
    let server = Server::http(("127.0.0.1", port)).expect("port in use?");
    println!("ตอกบัตร dev server: http://127.0.0.1:{port}  (data: {})", dev.display());
    for rq in server.incoming_requests() {
        let (api, web) = (api.clone(), web.clone());
        std::thread::spawn(move || handle(&api, &web, rq));
    }
}
