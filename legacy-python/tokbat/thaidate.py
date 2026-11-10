"""Thai calendar formatting (Buddhist year) and pay-period cycles."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

WEEKDAY_SHORT = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]  # Monday first
MONTH_SHORT = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
MONTH_LONG = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
BE = 543


def be_year(d: date) -> int:
    return d.year + BE


def slash(d: date) -> str:
    """1/9/2569 — the format the user's sheet uses."""
    return f"{d.day}/{d.month}/{be_year(d)}"


def short(d: date) -> str:
    """อ. 10 พ.ย. 2569"""
    return f"{WEEKDAY_SHORT[d.weekday()]} {d.day} {MONTH_SHORT[d.month]} {be_year(d)}"


def long(d: date) -> str:
    return f"{d.day} {MONTH_LONG[d.month]} {be_year(d)}"


def parse_slash(text: str) -> date:
    """'1/9/2569' or '1/9/2026' → date (day/month/year; years > 2400 are Buddhist)."""
    d, m, y = (int(x) for x in str(text).strip().split("/"))
    if y > 2400:
        y -= BE
    return date(y, m, d)


def _month_end(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


def _shift_month(y: int, m: int, k: int) -> tuple[int, int]:
    i = y * 12 + (m - 1) + k
    return i // 12, i % 12 + 1


def cycle_for(d: date, mode: str = "month", cutoff_day: int = 20) -> tuple[date, date]:
    """The period that holds d.
    month  → 1st … last day of the month.
    cutoff → (cutoff+1) of the previous month … cutoff of this month (or the next one after the cutoff)."""
    if mode != "cutoff":
        return date(d.year, d.month, 1), date(d.year, d.month, _month_end(d.year, d.month))
    c = max(1, min(28, int(cutoff_day)))
    if d.day <= c:
        py, pm = _shift_month(d.year, d.month, -1)
        return date(py, pm, c) + timedelta(days=1), date(d.year, d.month, c)
    ny, nm = _shift_month(d.year, d.month, 1)
    return date(d.year, d.month, c) + timedelta(days=1), date(ny, nm, c)


def shift_cycle(start: date, end: date, k: int, mode: str = "month", cutoff_day: int = 20) -> tuple[date, date]:
    """The period k steps before/after the one that ends on `end`."""
    y, m = _shift_month(end.year, end.month, k)
    anchor = date(y, m, min(end.day, _month_end(y, m)))
    return cycle_for(anchor, mode, cutoff_day)


def title_from_pattern(pattern: str, start: date, end: date) -> str:
    """'{เดือน}/{ปี}' → '10/2569', using the month the period ends in."""
    return (pattern or "{เดือน}/{ปี}").replace("{เดือน}", str(end.month)).replace("{ปี}", str(be_year(end)))
