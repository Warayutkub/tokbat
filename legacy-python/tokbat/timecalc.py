"""Pure time arithmetic. Times are minutes after midnight (0–1439); dates are datetime.date.

Rules agreed with the user:
- A session that ends at or before its start time finished on the next day (overnight);
  its hours belong to the date it started.
- Hours are shown as decimals (6.75) but always summed from minutes, never from rounded rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

DAY = 1440


class TimeError(ValueError):
    """A time value the user typed can't be used; `code` says why."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def parse_hhmm(text: str) -> int:
    """'21:00', '3:00', '03:00:00' → minutes. Raises TimeError for anything else."""
    parts = str(text).strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise TimeError("bad_time", f"อ่านเวลา “{text}” ไม่ออก ใช้รูปแบบ 21:00")
    h, m = int(parts[0]), int(parts[1])
    if h == 24 and m == 0:
        return 0
    if not (0 <= h < 24 and 0 <= m < 60):
        raise TimeError("bad_time", f"เวลา “{text}” ไม่มีจริง")
    return h * 60 + m


def fmt_hhmm(minutes: int) -> str:
    minutes %= DAY
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def is_overnight(start: int, end: int) -> bool:
    return end <= start


def span_minutes(start: int, end: int) -> int:
    """Length from start to end; an end at/before start means the next day."""
    if end == start:
        raise TimeError("zero_length", "เวลาเริ่มกับเวลาหยุดต้องไม่ใช่เวลาเดียวกัน")
    return end - start if end > start else end + DAY - start


def net_minutes(start: int, end: int, break_min: int = 0) -> int:
    span = span_minutes(start, end)
    if break_min < 0:
        raise TimeError("bad_break", "เวลาพักติดลบไม่ได้")
    if break_min >= span:
        raise TimeError("break_too_long", "เวลาพักต้องน้อยกว่าเวลาทำงานของช่วงนี้")
    return span - break_min


def to_decimal_hours(minutes: int | Decimal) -> str:
    """10410 → '173.50' (half-up, 2 places). Accepts fractional minutes (averages)."""
    return str((Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def average_hours(total_minutes: int, count: int, unit: str = "decimal") -> str:
    """Average per day without rounding the minutes first: 10410 / 20 days → '8.68'."""
    if not count:
        return fmt_hours(0, unit)
    avg = Decimal(total_minutes) / Decimal(count)
    if unit == "hm":
        return to_hm(int(avg.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    return to_decimal_hours(avg)


def to_hm(minutes: int) -> str:
    """10410 → '173:30'."""
    return f"{minutes // 60}:{minutes % 60:02d}"


def to_hm_thai(minutes: int) -> str:
    return f"{minutes // 60} ชม. {minutes % 60} นาที"


def fmt_hours(minutes: int, unit: str = "decimal") -> str:
    return to_hm(minutes) if unit == "hm" else to_decimal_hours(minutes)


@dataclass(frozen=True)
class Interval:
    """A session placed on an absolute minute line, so overnight sessions compare correctly."""

    id: int | None
    start_abs: int
    end_abs: int

    def overlap(self, other: "Interval") -> int:
        return max(0, min(self.end_abs, other.end_abs) - max(self.start_abs, other.start_abs))


def interval_for(session_date: date, start: int, end: int | None, base: date, now_abs: int | None = None, sid: int | None = None) -> Interval:
    """Absolute interval relative to `base`. An open session (end None) runs until `now_abs`."""
    offset = (session_date - base).days * DAY
    s = offset + start
    if end is None:
        e = max(now_abs if now_abs is not None else s + 1, s + 1)
    else:
        e = s + span_minutes(start, end)
    return Interval(sid, s, e)


def find_overlaps(candidate: Interval, others: list[Interval]) -> list[tuple[Interval, int]]:
    return [(o, m) for o in others if o.id != candidate.id and (m := candidate.overlap(o)) > 0]


def week_of(d: date) -> list[date]:
    """Monday → Sunday of the week that holds d."""
    monday = d - timedelta(days=d.weekday())
    return [monday + timedelta(days=i) for i in range(7)]
