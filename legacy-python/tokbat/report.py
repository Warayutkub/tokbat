"""Report numbers for a date range, and the printable A4 page (HTML) that becomes the PDF / PNG."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import thaidate as td
from . import timecalc as tc
from .repo import Repo

TEMPLATES = Path(__file__).parent / "templates"
COLUMN_LABELS = {"date": "วันที่", "start": "เวลาเริ่ม", "end": "เวลาหยุด", "break": "พัก", "hours": "ชั่วโมง", "note": "หมายเหตุ"}
COLUMN_ORDER = ["date", "start", "end", "break", "hours", "note"]


def build(repo: Repo, start: date, end: date, unit: str = "decimal") -> dict:
    sessions = [s for s in repo.between(start, end) if not s["open"]]
    rows, prev_date = [], None
    for s in sessions:
        d = date.fromisoformat(s["date"])
        rows.append({
            **s,
            "date_slash": td.slash(d),
            "weekday": td.WEEKDAY_SHORT[d.weekday()],
            "same_day": s["date"] == prev_date,
            "hours_text": tc.fmt_hours(s["minutes"], unit),
            "break_text": "—" if not s["break_min"] else tc.fmt_hours(s["break_min"], "hm"),
        })
        prev_date = s["date"]
    total = sum(s["minutes"] for s in sessions)
    per_day, d = [], start
    days_with_work = set()
    while d <= end:
        iso = d.isoformat()
        day_min = sum(s["minutes"] for s in sessions if s["date"] == iso and not s["overnight"])
        night_min = sum(s["minutes"] for s in sessions if s["date"] == iso and s["overnight"])
        if day_min or night_min:
            days_with_work.add(iso)
        per_day.append({"date": iso, "day": d.day, "weekday": td.WEEKDAY_SHORT[d.weekday()], "day_min": day_min, "night_min": night_min,
                        "total": tc.fmt_hours(day_min + night_min, unit)})
        d += timedelta(days=1)
    n_days = len(days_with_work)
    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "label": f"{td.slash(start)} – {td.slash(end)}",
        "unit": unit,
        "rows": rows,
        "per_day": per_day,
        "total_min": total,
        "total": tc.fmt_hours(total, unit),
        "total_decimal": tc.to_decimal_hours(total),
        "total_hm": tc.to_hm_thai(total),
        "days": n_days,
        "sessions": len(sessions),
        "overnight": sum(1 for s in sessions if s["overnight"]),
        "break_min": sum(s["break_min"] for s in sessions),
        "avg": tc.average_hours(total, n_days, unit),
    }


_env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))


def render_html(rep: dict, *, title: str, columns: list[str], footnote: bool = True, timestamp: bool = True,
                mascot_svg: str | None = None, font_base: str = "fonts/", printed_at: datetime | None = None) -> str:
    cols = [c for c in COLUMN_ORDER if c in columns] or ["date", "start", "end", "hours"]
    printed_at = printed_at or datetime.now()
    return _env.get_template("report.html").render(
        rep=rep, title=title or rep["label"], cols=cols, labels=COLUMN_LABELS, footnote=footnote,
        timestamp=f"{td.slash(printed_at.date())} {printed_at:%H:%M}" if timestamp else None,
        mascot_svg=mascot_svg, font_base=font_base, unit_note=rep["unit"] == "decimal",
    )
