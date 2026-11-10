//! Pure time arithmetic. Times are minutes after midnight (0–1439).
//!
//! Rules agreed with the user:
//! - a session that ends at or before its start time finished on the next day (overnight);
//!   its hours belong to the date it started;
//! - hours show as decimals (6.75) but are always summed from minutes, never from rounded rows.

use chrono::{Datelike, Days, NaiveDate};

pub const DAY: i64 = 1440;

#[derive(Debug, Clone, PartialEq)]
pub struct TimeError {
    pub code: &'static str,
    pub message: String,
}

impl TimeError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self { code, message: message.into() }
    }
}

/// "21:00", "3:00", "03:00:00" → minutes.
pub fn parse_hhmm(text: &str) -> Result<i64, TimeError> {
    let t = text.trim();
    let parts: Vec<&str> = t.split(':').collect();
    if !(parts.len() == 2 || parts.len() == 3) || !parts.iter().all(|p| !p.is_empty() && p.chars().all(|c| c.is_ascii_digit())) {
        return Err(TimeError::new("bad_time", format!("อ่านเวลา \u{201c}{t}\u{201d} ไม่ออก ใช้รูปแบบ 21:00")));
    }
    let h: i64 = parts[0].parse().unwrap_or(99);
    let m: i64 = parts[1].parse().unwrap_or(99);
    if h == 24 && m == 0 {
        return Ok(0);
    }
    if !(0..24).contains(&h) || !(0..60).contains(&m) {
        return Err(TimeError::new("bad_time", format!("เวลา \u{201c}{t}\u{201d} ไม่มีจริง")));
    }
    Ok(h * 60 + m)
}

pub fn fmt_hhmm(minutes: i64) -> String {
    let m = minutes.rem_euclid(DAY);
    format!("{:02}:{:02}", m / 60, m % 60)
}

pub fn is_overnight(start: i64, end: i64) -> bool {
    end <= start
}

/// Length from start to end; an end at/before the start means the next day.
pub fn span_minutes(start: i64, end: i64) -> Result<i64, TimeError> {
    if end == start {
        return Err(TimeError::new("zero_length", "เวลาเริ่มกับเวลาหยุดต้องไม่ใช่เวลาเดียวกัน"));
    }
    Ok(if end > start { end - start } else { end + DAY - start })
}

pub fn net_minutes(start: i64, end: i64, break_min: i64) -> Result<i64, TimeError> {
    let span = span_minutes(start, end)?;
    if break_min < 0 {
        return Err(TimeError::new("bad_break", "เวลาพักติดลบไม่ได้"));
    }
    if break_min >= span {
        return Err(TimeError::new("break_too_long", "เวลาพักต้องน้อยกว่าเวลาทำงานของช่วงนี้"));
    }
    Ok(span - break_min)
}

/// round(n / d) with halves going up, for n, d >= 0.
fn div_half_up(n: i128, d: i128) -> i128 {
    (2 * n + d) / (2 * d)
}

fn hundredths(h: i128) -> String {
    format!("{}.{:02}", h / 100, h % 100)
}

/// 7480 → "124.67" (half-up, two places).
pub fn to_decimal_hours(minutes: i64) -> String {
    hundredths(div_half_up(minutes as i128 * 100, 60))
}

/// 10410 → "173:30".
pub fn to_hm(minutes: i64) -> String {
    format!("{}:{:02}", minutes / 60, minutes % 60)
}

pub fn to_hm_thai(minutes: i64) -> String {
    format!("{} ชม. {} นาที", minutes / 60, minutes % 60)
}

pub fn fmt_hours(minutes: i64, unit: &str) -> String {
    if unit == "hm" { to_hm(minutes) } else { to_decimal_hours(minutes) }
}

/// Average per day without rounding the minutes first: 10410 over 20 days → "8.68".
pub fn average_hours(total_minutes: i64, count: i64, unit: &str) -> String {
    if count <= 0 {
        return fmt_hours(0, unit);
    }
    if unit == "hm" {
        return to_hm(div_half_up(total_minutes as i128, count as i128) as i64);
    }
    hundredths(div_half_up(total_minutes as i128 * 100, 60 * count as i128))
}

/// A session placed on an absolute minute line, so overnight sessions compare correctly.
#[derive(Debug, Clone, Copy)]
pub struct Interval {
    pub id: Option<i64>,
    pub start_abs: i64,
    pub end_abs: i64,
}

impl Interval {
    pub fn overlap(&self, other: &Interval) -> i64 {
        (self.end_abs.min(other.end_abs) - self.start_abs.max(other.start_abs)).max(0)
    }
}

/// Absolute interval relative to `base`. An open session (no end) runs until `now_abs`.
pub fn interval_for(session_date: NaiveDate, start: i64, end: Option<i64>, base: NaiveDate, now_abs: i64, id: Option<i64>) -> Interval {
    let offset = (session_date - base).num_days() * DAY;
    let s = offset + start;
    let e = match end {
        None => now_abs.max(s + 1),
        Some(e) => s + span_minutes(start, e).unwrap_or(1),
    };
    Interval { id, start_abs: s, end_abs: e }
}

/// Monday → Sunday of the week that holds d.
pub fn week_of(d: NaiveDate) -> Vec<NaiveDate> {
    let monday = d - Days::new(d.weekday().num_days_from_monday() as u64);
    (0..7).map(|i| monday + Days::new(i)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_and_format() {
        assert_eq!(parse_hhmm("3:00:00"), Ok(180));
        assert_eq!(parse_hhmm("21:00"), Ok(1260));
        assert_eq!(parse_hhmm("24:00"), Ok(0));
        assert_eq!(fmt_hhmm(1260), "21:00");
        assert!(parse_hhmm("25:00").is_err());
        assert!(parse_hhmm("abc").is_err());
    }

    #[test]
    fn overnight_span() {
        assert_eq!(span_minutes(1260, 180), Ok(360));
        assert_eq!(span_minutes(1260, 0), Ok(180));
        assert_eq!(span_minutes(780, 1140), Ok(360));
        assert!(span_minutes(600, 600).is_err());
    }

    #[test]
    fn break_rules() {
        assert_eq!(net_minutes(540, 1110, 60), Ok(510));
        assert!(net_minutes(540, 600, 60).is_err());
    }

    #[test]
    fn decimal_rounding_half_up() {
        assert_eq!(to_decimal_hours(260), "4.33");
        assert_eq!(to_decimal_hours(415), "6.92");
        assert_eq!(to_decimal_hours(470), "7.83");
        assert_eq!(to_decimal_hours(405), "6.75");
        assert_eq!(to_hm(10410), "173:30");
        assert_eq!(average_hours(10410, 20, "decimal"), "8.68");
    }
}
