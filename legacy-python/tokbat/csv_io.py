"""Read a CSV exported from the user's Google Sheet (date, start, stop, hours, note)."""
from __future__ import annotations

import csv
import io
from datetime import date

from . import thaidate as td
from . import timecalc as tc

HEADER_HINTS = {
    "date": ("วันที่", "คอลัมน์ 1", "column 1", "date"),
    "start": ("เวลาเริ่ม", "เริ่ม", "start"),
    "end": ("เวลาหยุด", "หยุด", "เลิก", "end", "stop"),
    "note": ("หมายเหตุ", "note", "รายละเอียด"),
}


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp874", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("อ่านไฟล์ไม่ได้ ลองบันทึกเป็น CSV (UTF-8) จาก Google Sheets อีกครั้ง")


def _find_columns(header: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    low = [h.strip().lower() for h in header]
    for key, hints in HEADER_HINTS.items():
        for i, h in enumerate(low):
            if i not in cols.values() and any(x.lower() in h for x in hints):
                cols[key] = i
                break
    return cols


def parse(raw: bytes) -> dict:
    """{rows: [{date, start, end, note}], skipped: [(line, reason)]}"""
    text = _decode(raw)
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    lines = list(csv.reader(io.StringIO(text), dialect))
    cols, start_at = {}, 0
    for i, line in enumerate(lines[:10]):
        c = _find_columns(line)
        if "start" in c and "end" in c:
            cols, start_at = c, i + 1
            cols.setdefault("date", 0)
            break
    if not cols:
        cols, start_at = {"date": 0, "start": 1, "end": 2, "note": 4}, 0
    rows, skipped = [], []
    for n, line in enumerate(lines[start_at:], start=start_at + 1):
        first = line[0].strip() if line else ""
        if not any(cell.strip() for cell in line) or first in ("รวม", "Total") or first.startswith("*"):
            continue
        try:
            d: date = td.parse_slash(line[cols["date"]])
            s = tc.parse_hhmm(line[cols["start"]])
            e = tc.parse_hhmm(line[cols["end"]])
            tc.span_minutes(s, e)
        except (ValueError, IndexError) as err:
            skipped.append((n, str(err) or "ข้อมูลไม่ครบ"))
            continue
        note = line[cols["note"]].strip() if "note" in cols and cols["note"] < len(line) else ""
        rows.append({"date": d.isoformat(), "start": tc.fmt_hhmm(s), "end": tc.fmt_hhmm(e), "note": note})
    return {"rows": rows, "skipped": skipped}
