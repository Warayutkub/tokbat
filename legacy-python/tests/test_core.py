from datetime import date, datetime
from pathlib import Path

import pytest

from tokbat import csv_io, db, report
from tokbat import thaidate as td
from tokbat import timecalc as tc
from tokbat.repo import Repo

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample-sheet.csv"  # shared with the Rust tests


@pytest.fixture
def repo():
    return Repo(db.connect(":memory:"))


@pytest.fixture
def sample(repo):
    for r in csv_io.parse(FIXTURE.read_bytes())["rows"]:
        assert repo.save(r)["ok"], r
    return repo


# ---------- time arithmetic ----------
def test_parse_and_format():
    assert tc.parse_hhmm("3:00:00") == 180
    assert tc.parse_hhmm("21:00") == 1260
    assert tc.parse_hhmm("24:00") == 0
    assert tc.fmt_hhmm(1260) == "21:00"
    with pytest.raises(tc.TimeError):
        tc.parse_hhmm("25:00")
    with pytest.raises(tc.TimeError):
        tc.parse_hhmm("abc")


def test_overnight_span():
    assert tc.span_minutes(tc.parse_hhmm("21:00"), tc.parse_hhmm("03:00")) == 360
    assert tc.span_minutes(tc.parse_hhmm("21:00"), tc.parse_hhmm("00:00")) == 180
    assert tc.span_minutes(tc.parse_hhmm("13:00"), tc.parse_hhmm("19:00")) == 360
    with pytest.raises(tc.TimeError):
        tc.span_minutes(600, 600)


def test_break_rules():
    assert tc.net_minutes(540, 1110, 60) == 510
    with pytest.raises(tc.TimeError):
        tc.net_minutes(540, 600, 60)


def test_decimal_rounding_half_up():
    assert tc.to_decimal_hours(260) == "4.33"      # 4:20
    assert tc.to_decimal_hours(415) == "6.92"      # 6:55
    assert tc.to_decimal_hours(470) == "7.83"      # 7:50
    assert tc.to_decimal_hours(405) == "6.75"
    assert tc.to_hm(10410) == "173:30"


# ---------- calendar ----------
def test_thai_dates():
    assert td.slash(date(2026, 9, 1)) == "1/9/2569"
    assert td.parse_slash("20/9/2569") == date(2026, 9, 20)
    assert td.short(date(2026, 11, 10)) == "อ. 10 พ.ย. 2569"


def test_cycles():
    assert td.cycle_for(date(2026, 11, 10), "cutoff", 20) == (date(2026, 10, 21), date(2026, 11, 20))
    assert td.cycle_for(date(2026, 11, 25), "cutoff", 20) == (date(2026, 11, 21), date(2026, 12, 20))
    assert td.cycle_for(date(2026, 1, 5), "cutoff", 20) == (date(2025, 12, 21), date(2026, 1, 20))
    assert td.cycle_for(date(2026, 2, 10), "month") == (date(2026, 2, 1), date(2026, 2, 28))
    s, e = td.cycle_for(date(2026, 11, 10), "cutoff", 20)
    assert td.shift_cycle(s, e, -1, "cutoff", 20) == (date(2026, 9, 21), date(2026, 10, 20))
    assert td.title_from_pattern("{เดือน}/{ปี}", s, e) == "11/2569"


# ---------- a made-up sheet in the same layout as the user's Google Sheet ----------
def test_csv_reads_the_sheet_layout():
    out = csv_io.parse(FIXTURE.read_bytes())
    assert len(out["rows"]) == 22
    assert out["skipped"] == []
    assert out["rows"][0] == {"date": "2026-03-01", "start": "21:00", "end": "02:30", "note": "ออกแบบหน้าจอ"}


def test_report_matches_sheet_rows_and_sums_minutes(sample):
    rep = report.build(sample, date(2026, 3, 1), date(2026, 3, 20))
    assert [r["hours_text"] for r in rep["rows"]][:7] == ["5.50", "5.33", "5.17", "8.17", "6.25", "6.83", "6.83"]
    assert rep["sessions"] == 22 and rep["days"] == 18 and rep["overnight"] == 11
    assert rep["avg"] == "6.93"   # 124.67 / 18 = 6.926, half-up
    # a sheet that rounds each row first gets 124.65; minutes say 124:40
    assert rep["total"] == "124.67"
    assert rep["total_hm"] == "124 ชม. 40 นาที"
    assert sum(float(r["hours_text"]) for r in rep["rows"]) == pytest.approx(124.65)
    day3 = next(d for d in rep["per_day"] if d["day"] == 3)
    assert (day3["day_min"], day3["night_min"]) == (320, 310)


def test_report_hm_unit(sample):
    rep = report.build(sample, date(2026, 3, 4), date(2026, 3, 4), unit="hm")
    assert rep["rows"][0]["hours_text"] == "8:10"


def test_report_html_renders_thai_and_columns(sample):
    rep = report.build(sample, date(2026, 3, 1), date(2026, 3, 20))
    html = report.render_html(rep, title="3/2569", columns=["date", "start", "end", "hours", "note"],
                              printed_at=datetime(2026, 11, 10, 13, 28))
    assert "3/2569" in html and "จำนวนทั้งหมด : 124.67" in html
    assert "พิมพ์เมื่อ 10/11/2569 13:28" in html
    assert "หน่วยเป็นทศนิยม" in html
    assert "<th class=\"c-break\">" not in html


# ---------- saving rules ----------
def test_overlap_same_day(repo):
    assert repo.save({"date": "2026-11-10", "start": "13:00", "end": "19:00"})["ok"]
    res = repo.save({"date": "2026-11-10", "start": "18:00", "end": "03:00"})
    assert not res["ok"] and res["error"]["code"] == "overlap"
    assert res["error"]["suggest_start"] == "19:00"
    assert res["error"]["overlap_min"] == 60


def test_overnight_spills_into_next_day(repo):
    assert repo.save({"date": "2026-11-10", "start": "21:00", "end": "03:00"})["ok"]
    res = repo.save({"date": "2026-11-11", "start": "02:00", "end": "05:00"})
    assert not res["ok"] and res["error"]["overlap_min"] == 60
    assert repo.save({"date": "2026-11-11", "start": "03:00", "end": "05:00"})["ok"]


def test_edit_does_not_clash_with_itself(repo):
    s = repo.save({"date": "2026-11-10", "start": "09:00", "end": "12:00"})["session"]
    res = repo.save({**s, "end": "12:30"})
    assert res["ok"] and res["previous"]["end"] == "12:00" and res["session"]["end"] == "12:30"


def test_delete_and_undo(repo):
    s = repo.save({"date": "2026-11-10", "start": "09:00", "end": "12:00", "note": "x"})["session"]
    gone = repo.delete(s["id"])
    assert repo.count() == 0
    back = repo.restore(gone)
    assert back["id"] == s["id"] and back["note"] == "x"


def test_open_session_and_missing_days(repo):
    repo.save({"date": "2026-11-05", "start": "09:00", "end": "17:00"})
    res = repo.save({"date": "2026-11-10", "start": "13:05", "end": None}, now=datetime(2026, 11, 10, 14, 0))
    assert res["ok"] and res["session"]["open"]
    assert repo.open_session()["id"] == res["session"]["id"]
    missing = repo.missing_days(date(2026, 11, 10))
    assert missing == ["2026-11-09", "2026-11-08", "2026-11-07", "2026-11-06"]
    repo.mark_day_off(date(2026, 11, 8))
    assert "2026-11-08" not in repo.missing_days(date(2026, 11, 10))


def test_settings_roundtrip(repo):
    assert repo.settings()["unit"] == "decimal"
    s = repo.save_settings({"unit": "hm", "cutoff_day": 25, "unknown": 1})
    assert s["unit"] == "hm" and s["cutoff_day"] == 25 and "unknown" not in s
