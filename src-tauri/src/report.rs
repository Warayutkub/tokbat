//! Report numbers for a date range, and the printable A4 page (HTML) that becomes the PDF / PNG.

use chrono::{Datelike, Days, NaiveDate, NaiveDateTime};
use minijinja::{AutoEscape, Environment, context};
use serde_json::{Value, json};
use std::collections::HashSet;

use crate::repo::{Repo, iso, parse_iso};
use crate::thaidate as td;
use crate::timecalc as tc;

const TEMPLATE: &str = include_str!("../templates/report.html");
pub const COLUMN_ORDER: [&str; 6] = ["date", "start", "end", "break", "hours", "note"];

fn label(c: &str) -> &'static str {
    match c {
        "date" => "วันที่",
        "start" => "เวลาเริ่ม",
        "end" => "เวลาหยุด",
        "break" => "พัก",
        "hours" => "ชั่วโมง",
        _ => "หมายเหตุ",
    }
}

pub fn build(repo: &Repo, start: NaiveDate, end: NaiveDate, unit: &str) -> Value {
    let sessions: Vec<Value> = repo.between(start, end, "").into_iter().filter(|s| !s["open"].as_bool().unwrap_or(false)).collect();
    let mut rows = vec![];
    let mut prev: Option<String> = None;
    for s in &sessions {
        let date = s["date"].as_str().unwrap().to_string();
        let d = parse_iso(&date).unwrap();
        let minutes = s["minutes"].as_i64().unwrap_or(0);
        let brk = s["break_min"].as_i64().unwrap_or(0);
        let mut r = s.clone();
        let o = r.as_object_mut().unwrap();
        o.insert("date_slash".into(), json!(td::slash(d)));
        o.insert("weekday".into(), json!(td::wd(d)));
        o.insert("same_day".into(), json!(prev.as_deref() == Some(date.as_str())));
        o.insert("hours_text".into(), json!(tc::fmt_hours(minutes, unit)));
        o.insert("break_text".into(), json!(if brk == 0 { "—".to_string() } else { tc::fmt_hours(brk, "hm") }));
        rows.push(r);
        prev = Some(date);
    }
    let total: i64 = sessions.iter().map(|s| s["minutes"].as_i64().unwrap_or(0)).sum();
    let mut per_day = vec![];
    let mut worked = HashSet::new();
    let mut d = start;
    while d <= end {
        let k = iso(d);
        let pick = |night: bool| -> i64 { sessions.iter().filter(|s| s["date"] == k.as_str() && s["overnight"].as_bool() == Some(night)).map(|s| s["minutes"].as_i64().unwrap_or(0)).sum() };
        let (day_min, night_min) = (pick(false), pick(true));
        if day_min + night_min > 0 {
            worked.insert(k.clone());
        }
        per_day.push(json!({"date": k, "day": d.day(), "weekday": td::wd(d),
            "day_min": day_min, "night_min": night_min, "total": tc::fmt_hours(day_min + night_min, unit)}));
        d = d + Days::new(1);
    }
    let n_days = worked.len() as i64;
    let days_off = repo.days_off(start, end).iter().filter(|d| !worked.contains(*d)).count();
    json!({
        "start": iso(start), "end": iso(end), "label": format!("{} – {}", td::slash(start), td::slash(end)), "unit": unit,
        "rows": rows, "per_day": per_day,
        "total_min": total, "total": tc::fmt_hours(total, unit), "total_decimal": tc::to_decimal_hours(total), "total_hm": tc::to_hm_thai(total),
        "days": n_days, "days_off": days_off, "sessions": sessions.len(),
        "overnight": sessions.iter().filter(|s| s["overnight"].as_bool() == Some(true)).count(),
        "break_min": sessions.iter().map(|s| s["break_min"].as_i64().unwrap_or(0)).sum::<i64>(),
        "avg": tc::average_hours(total, n_days, unit),
    })
}

fn html_escape(s: &str) -> String {
    let mut o = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '&' => o.push_str("&amp;"),
            '<' => o.push_str("&lt;"),
            '>' => o.push_str("&gt;"),
            '"' => o.push_str("&#34;"),
            '\'' => o.push_str("&#39;"),
            _ => o.push(c),
        }
    }
    o
}

pub struct PageOptions<'a> {
    pub title: &'a str,
    pub columns: &'a [String],
    pub footnote: bool,
    pub timestamp: bool,
    pub mascot_svg: Option<&'a str>,
    pub font_base: &'a str,
    pub printed_at: NaiveDateTime,
}

pub fn render_html(rep: &Value, o: &PageOptions) -> String {
    let mut cols: Vec<&str> = COLUMN_ORDER.iter().copied().filter(|c| o.columns.iter().any(|x| x == c)).collect();
    if cols.is_empty() {
        cols = vec!["date", "start", "end", "hours"];
    }
    let labels: serde_json::Map<String, Value> = COLUMN_ORDER.iter().map(|c| (c.to_string(), json!(label(c)))).collect();
    let mut env = Environment::new();
    env.set_auto_escape_callback(|_| AutoEscape::Html);
    // escape like Jinja2 (& < > " ') — minijinja also escapes "/", which breaks url("fonts/…") inside <style>
    env.set_formatter(|out, _state, value| {
        if value.is_undefined() || value.is_none() {
            return Ok(());
        }
        let text = value.to_string();
        if value.is_safe() {
            out.write_str(&text)?;
        } else {
            out.write_str(&html_escape(&text))?;
        }
        Ok(())
    });
    env.add_template("report.html", TEMPLATE).expect("report template");
    let title = if o.title.is_empty() { rep["label"].as_str().unwrap_or("") } else { o.title };
    let timestamp = o.timestamp.then(|| format!("{} {}", td::slash(o.printed_at.date()), o.printed_at.format("%H:%M")));
    env.get_template("report.html")
        .unwrap()
        .render(context! {
            rep => rep, title => title, cols => cols, labels => labels, footnote => o.footnote, timestamp => timestamp,
            mascot_svg => o.mascot_svg, font_base => o.font_base, unit_note => rep["unit"] == "decimal",
            mid_span => (cols.len() as i64 - 2).max(1),
        })
        .unwrap_or_else(|e| format!("<p>report error: {e}</p>"))
}
