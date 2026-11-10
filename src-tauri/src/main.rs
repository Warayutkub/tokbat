// No console window in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! ```text
//! tokbat.exe                       open the app
//! tokbat.exe --selftest <folder>   hidden window on throwaway data, export a PDF + PNG, write results.json
//! tokbat.exe --serve [port]        development: the UI in a normal browser (data in .dev-data/)
//! ```

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("--serve") => tokbat_lib::serve::run(args.get(2).and_then(|p| p.parse().ok()).unwrap_or(5177)),
        Some("--selftest") => tokbat_lib::run(Some(args.get(2).map(Into::into).unwrap_or_else(|| std::env::temp_dir().join("tokbat-selftest-out")))),
        _ => tokbat_lib::run(None),
    }
}
