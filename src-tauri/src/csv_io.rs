//! Read a CSV exported from the user's Google Sheet (date, start, stop, hours, note).

use serde_json::{Value, json};

use crate::repo::iso;
use crate::thaidate as td;
use crate::timecalc as tc;

const HINTS: [(&str, &[&str]); 4] = [
    ("date", &["วันที่", "คอลัมน์ 1", "column 1", "date"]),
    ("start", &["เวลาเริ่ม", "เริ่ม", "start"]),
    ("end", &["เวลาหยุด", "หยุด", "เลิก", "end", "stop"]),
    ("note", &["หมายเหตุ", "note", "รายละเอียด"]),
];

fn decode(raw: &[u8]) -> String {
    if raw.starts_with(&[0xFF, 0xFE]) || raw.starts_with(&[0xFE, 0xFF]) {
        let enc = if raw[0] == 0xFF { encoding_rs::UTF_16LE } else { encoding_rs::UTF_16BE };
        return enc.decode(&raw[2..]).0.into_owned();
    }
    let body = raw.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(raw);
    match std::str::from_utf8(body) {
        Ok(s) => s.to_string(),
        Err(_) => encoding_rs::WINDOWS_874.decode(body).0.into_owned(),
    }
}

fn find_columns(header: &[String]) -> Vec<(&'static str, usize)> {
    let mut cols: Vec<(&'static str, usize)> = vec![];
    for (key, hints) in HINTS {
        for (i, h) in header.iter().enumerate() {
            let h = h.trim().to_lowercase();
            if !cols.iter().any(|(_, c)| *c == i) && hints.iter().any(|x| h.contains(&x.to_lowercase())) {
                cols.push((key, i));
                break;
            }
        }
    }
    cols
}

/// {rows: [{date, start, end, note}], skipped: [[line, reason]]}
pub fn parse(raw: &[u8]) -> Value {
    let text = decode(raw);
    let first = text.lines().find(|l| !l.trim().is_empty()).unwrap_or("");
    let delim = [b',', b';', b'\t'].into_iter().max_by_key(|d| first.bytes().filter(|b| b == d).count()).unwrap_or(b',');
    let lines: Vec<Vec<String>> = csv::ReaderBuilder::new()
        .delimiter(delim)
        .has_headers(false)
        .flexible(true)
        .from_reader(text.as_bytes())
        .records()
        .filter_map(Result::ok)
        .map(|r| r.iter().map(str::to_string).collect())
        .collect();
    let mut cols: Vec<(&str, usize)> = vec![];
    let mut start_at = 0;
    for (i, line) in lines.iter().take(10).enumerate() {
        let c = find_columns(line);
        if c.iter().any(|(k, _)| *k == "start") && c.iter().any(|(k, _)| *k == "end") {
            cols = c;
            start_at = i + 1;
            if !cols.iter().any(|(k, _)| *k == "date") {
                cols.push(("date", 0));
            }
            break;
        }
    }
    if cols.is_empty() {
        cols = vec![("date", 0), ("start", 1), ("end", 2), ("note", 4)];
    }
    let col = |k: &str| cols.iter().find(|(n, _)| *n == k).map(|(_, i)| *i);
    let (mut rows, mut skipped) = (vec![], vec![]);
    for (n, line) in lines.iter().enumerate().skip(start_at) {
        let first = line.first().map(|s| s.trim()).unwrap_or("");
        if line.iter().all(|c| c.trim().is_empty()) || first == "รวม" || first == "Total" || first.starts_with('*') {
            continue;
        }
        let cell = |k: &str| col(k).and_then(|i| line.get(i)).map(|s| s.as_str()).unwrap_or("");
        let parsed = (|| -> Result<Value, String> {
            let d = td::parse_slash(cell("date")).ok_or_else(|| format!("อ่านวันที่ \u{201c}{}\u{201d} ไม่ออก", cell("date")))?;
            let s = tc::parse_hhmm(cell("start")).map_err(|e| e.message)?;
            let e = tc::parse_hhmm(cell("end")).map_err(|e| e.message)?;
            tc::span_minutes(s, e).map_err(|e| e.message)?;
            Ok(json!({"date": iso(d), "start": tc::fmt_hhmm(s), "end": tc::fmt_hhmm(e), "note": cell("note").trim()}))
        })();
        match parsed {
            Ok(v) => rows.push(v),
            Err(reason) => skipped.push(json!([n + 1, reason])),
        }
    }
    json!({"rows": rows, "skipped": skipped})
}
