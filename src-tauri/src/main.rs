// No console window in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! ```text
//! tokbat.exe                       open the app
//! tokbat.exe --selftest <folder>   hidden window on throwaway data, export a PDF + PNG, write results.json
//! tokbat.exe --serve [port] [--data <folder>]
//!                                  development: the UI in a normal browser (data in .dev-data/ unless --data)
//! ```

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("--serve") => {
            let data = args.iter().position(|a| a == "--data").and_then(|i| args.get(i + 1)).map(Into::into);
            tokbat_lib::serve::run(args.get(2).and_then(|p| p.parse().ok()).unwrap_or(5177), data)
        }
        Some("--selftest") => tokbat_lib::run(Some(args.get(2).map(Into::into).unwrap_or_else(|| std::env::temp_dir().join("tokbat-selftest-out")))),
        _ => tokbat_lib::run(None),
    }
}
