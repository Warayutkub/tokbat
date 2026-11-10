from datetime import date, datetime
from pathlib import Path

import pytest

from tokbat.api import Api, Dialogs

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "sample-sheet.csv"  # shared with the Rust tests


class FakeDialogs(Dialogs):
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.open_path = str(FIXTURE)

    def save(self, filename, kind):
        return str(self.tmp / filename)

    def open(self, kind):
        return self.open_path


@pytest.fixture
def api(tmp_path):
    a = Api(tmp_path / "worktime.db", FakeDialogs(tmp_path), today=lambda: date(2026, 11, 10), now=lambda: datetime(2026, 11, 10, 13, 28))
    return a


def import_sample(api):
    pre = api.import_pick()
    assert pre["ok"] and pre["count"] == 22 and pre["label"] == "1/3/2569 – 20/3/2569"
    res = api.import_commit(pre["token"])
    assert res == {"ok": True, "added": 22, "conflicts": 0}


def test_first_run_and_import(api):
    assert api.bootstrap()["count"] == 0
    import_sample(api)
    again = api.import_pick()
    assert again["count"] == 0 and again["duplicates"] == 22
    assert api.bootstrap()["settings"]["first_run_done"] is True


def test_day_view_and_week(api):
    import_sample(api)
    d = api.day("2026-03-03")
    assert d["label"] == "อ. 3 มี.ค. 2569" and len(d["sessions"]) == 2 and d["total_min"] == 630
    assert [x["state"] for x in d["week"]["days"]][:3] == ["empty", "done", "done"]  # Mon 2 Mar had no work
    assert d["week"]["label"] == "2–8 มี.ค. 2569"


def test_missing_day_after_last_entry(api):
    api.save_session({"date": "2026-11-05", "start": "09:00", "end": "17:00"})
    d = api.day("2026-11-10")
    assert d["missing"] == {"date": "2026-11-09", "label": "จ. 9 พ.ย."}


def test_periods(api):
    p = api.period("cycle", "2026-11-10", 0)
    assert (p["start"], p["end"], p["title"]) == ("2026-10-21", "2026-11-20", "11/2569")
    w = api.period("week", "2026-11-10", -1)
    assert (w["start"], w["end"]) == ("2026-11-02", "2026-11-08")


def test_history_search(api):
    import_sample(api)
    h = api.history("2026-03-01", "2026-03-20", "ลูกค้า")
    assert h["count"] == 1 and h["groups"][0]["slash"] == "17/3/2569"


def test_report_and_export_pdf_png(api, tmp_path):
    import_sample(api)
    r = api.report("2026-03-01", "2026-03-20")
    assert r["total"] == "124.67" and r["default_title"] == "3/2569"
    opts = {"start": "2026-03-01", "end": "2026-03-20", "title": "3/2569", "unit": "decimal",
            "columns": ["date", "start", "end", "hours", "note"], "footnote": True, "timestamp": True, "mascot": True}
    assert "จำนวนทั้งหมด : 124.67" in api.report_preview(opts)
    pdf = api.export_report({**opts, "format": "pdf"})
    assert pdf["ok"] and pdf["name"] == "3-2569.pdf" and Path(pdf["path"]).stat().st_size > 10_000
    png = api.export_report({**opts, "format": "png"})
    assert png["ok"] and png["name"] == "3-2569.png"
    assert [x["format"] for x in png["recent"]][:2] == ["png", "pdf"]


def test_open_session_start_stop(api):
    started = api.start_now()
    assert started["ok"] and started["session"]["open"]
    api._now = lambda: datetime(2026, 11, 10, 18, 0)
    stopped = api.stop_now(started["session"]["id"])
    assert stopped["ok"] and stopped["session"]["end"] == "18:00" and stopped["session"]["hours"] == "4.53"


def test_backup_restore_roundtrip(api, tmp_path):
    import_sample(api)
    b = api.backup()
    assert b["ok"]
    api.delete_all()
    assert api.bootstrap()["count"] == 0
    api._dialogs.open_path = b["path"]
    r = api.restore()
    assert r["ok"] and r["count"] == 22 and Path(r["kept"]).exists()


def test_restore_rejects_other_files(api, tmp_path):
    bad = tmp_path / "x.db"
    bad.write_bytes(b"not sqlite")
    api._dialogs.open_path = str(bad)
    assert api.restore() == {"ok": False, "error": "ไฟล์นี้ไม่ใช่ไฟล์สำรองของตอกบัตร"}
