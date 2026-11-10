//! Thai calendar formatting (Buddhist year) and pay-period cycles.

use chrono::{Datelike, Days, NaiveDate};

pub const WEEKDAY_SHORT: [&str; 7] = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]; // Monday first
pub const MONTH_SHORT: [&str; 13] = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
const BE: i32 = 543;

pub fn be_year(d: NaiveDate) -> i32 {
    d.year() + BE
}

pub fn wd(d: NaiveDate) -> &'static str {
    WEEKDAY_SHORT[d.weekday().num_days_from_monday() as usize]
}

/// 1/9/2569 — the format the user's sheet uses.
pub fn slash(d: NaiveDate) -> String {
    format!("{}/{}/{}", d.day(), d.month(), be_year(d))
}

/// อ. 10 พ.ย. 2569
pub fn short(d: NaiveDate) -> String {
    format!("{} {} {} {}", wd(d), d.day(), MONTH_SHORT[d.month() as usize], be_year(d))
}

/// อ. 10 พ.ย.
pub fn short_no_year(d: NaiveDate) -> String {
    format!("{} {} {}", wd(d), d.day(), MONTH_SHORT[d.month() as usize])
}

/// "1/9/2569" or "1/9/2026" → date (day/month/year; years above 2400 are Buddhist).
pub fn parse_slash(text: &str) -> Option<NaiveDate> {
    let p: Vec<&str> = text.trim().split('/').collect();
    if p.len() != 3 {
        return None;
    }
    let (d, m, mut y): (u32, u32, i32) = (p[0].trim().parse().ok()?, p[1].trim().parse().ok()?, p[2].trim().parse().ok()?);
    if y > 2400 {
        y -= BE;
    }
    NaiveDate::from_ymd_opt(y, m, d)
}

fn month_end(y: i32, m: u32) -> u32 {
    let (ny, nm) = shift_month(y, m, 1);
    (NaiveDate::from_ymd_opt(ny, nm, 1).unwrap() - Days::new(1)).day()
}

fn shift_month(y: i32, m: u32, k: i32) -> (i32, u32) {
    let i = y * 12 + (m as i32 - 1) + k;
    (i.div_euclid(12), (i.rem_euclid(12) + 1) as u32)
}

/// The period that holds d. `month`: the 1st to the last day. `cutoff`: (cutoff+1) of the previous month
/// to the cutoff of this month — or of the next month once the cutoff has passed.
pub fn cycle_for(d: NaiveDate, mode: &str, cutoff_day: i64) -> (NaiveDate, NaiveDate) {
    if mode != "cutoff" {
        return (NaiveDate::from_ymd_opt(d.year(), d.month(), 1).unwrap(), NaiveDate::from_ymd_opt(d.year(), d.month(), month_end(d.year(), d.month())).unwrap());
    }
    let c = cutoff_day.clamp(1, 28) as u32;
    if d.day() <= c {
        let (py, pm) = shift_month(d.year(), d.month(), -1);
        (NaiveDate::from_ymd_opt(py, pm, c).unwrap() + Days::new(1), NaiveDate::from_ymd_opt(d.year(), d.month(), c).unwrap())
    } else {
        let (ny, nm) = shift_month(d.year(), d.month(), 1);
        (NaiveDate::from_ymd_opt(d.year(), d.month(), c).unwrap() + Days::new(1), NaiveDate::from_ymd_opt(ny, nm, c).unwrap())
    }
}

/// The period k steps before/after the one that ends on `end`.
pub fn shift_cycle(end: NaiveDate, k: i32, mode: &str, cutoff_day: i64) -> (NaiveDate, NaiveDate) {
    let (y, m) = shift_month(end.year(), end.month(), k);
    let anchor = NaiveDate::from_ymd_opt(y, m, end.day().min(month_end(y, m))).unwrap();
    cycle_for(anchor, mode, cutoff_day)
}

/// "{เดือน}/{ปี}" → "10/2569", from the month the period ends in.
pub fn title_from_pattern(pattern: &str, end: NaiveDate) -> String {
    let p = if pattern.is_empty() { "{เดือน}/{ปี}" } else { pattern };
    p.replace("{เดือน}", &end.month().to_string()).replace("{ปี}", &be_year(end).to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn d(y: i32, m: u32, dd: u32) -> NaiveDate {
        NaiveDate::from_ymd_opt(y, m, dd).unwrap()
    }

    #[test]
    fn thai_dates() {
        assert_eq!(slash(d(2026, 9, 1)), "1/9/2569");
        assert_eq!(parse_slash("20/9/2569"), Some(d(2026, 9, 20)));
        assert_eq!(short(d(2026, 11, 10)), "อ. 10 พ.ย. 2569");
    }

    #[test]
    fn cycles() {
        assert_eq!(cycle_for(d(2026, 11, 10), "cutoff", 20), (d(2026, 10, 21), d(2026, 11, 20)));
        assert_eq!(cycle_for(d(2026, 11, 25), "cutoff", 20), (d(2026, 11, 21), d(2026, 12, 20)));
        assert_eq!(cycle_for(d(2026, 1, 5), "cutoff", 20), (d(2025, 12, 21), d(2026, 1, 20)));
        assert_eq!(cycle_for(d(2026, 2, 10), "month", 20), (d(2026, 2, 1), d(2026, 2, 28)));
        let (_, e) = cycle_for(d(2026, 11, 10), "cutoff", 20);
        assert_eq!(shift_cycle(e, -1, "cutoff", 20), (d(2026, 9, 21), d(2026, 10, 20)));
        assert_eq!(title_from_pattern("{เดือน}/{ปี}", e), "11/2569");
    }
}
