"""The methods the web UI calls (pywebview js_api, or the dev HTTP server). Everything returns plain JSON data."""
from __future__ import annotations

import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from . import csv_io, db, exporter, report
from . import thaidate as td
from . import timecalc as tc
from .paths import resource
from .repo import Repo


def _locked(fn):
    @wraps(fn)
    def run(self, *a, **kw):
        with self._lock:
            return fn(self, *a, **kw)
    return run


class Dialogs:
    """File pickers. The app uses pywebview's native ones; tests and the dev server use a stand-in."""

    def save(self, filename: str, kind: str) -> str | None:  # pragma: no cover - interface
        raise NotImplementedError

    def open(self, kind: str) -> str | None:  # pragma: no cover - interface
        raise NotImplementedError


class Api:
    def __init__(self, db_file: Path, dialogs: Dialogs | None = None, today=None, now=None):
        self._db_file = Path(db_file)
        self._con = db.connect(self._db_file)
        self._repo = Repo(self._con)
        self._dialogs = dialogs
        self._lock = threading.RLock()
        self._pending_imports: dict[str, list[dict]] = {}
        self._today = today or date.today        # injectable clock for tests
        self._now = now or datetime.now

    def _attach(self, dialogs: Dialogs) -> None:
        self._dialogs = dialogs

    # ---------- start ----------
    @_locked
    def bootstrap(self):
        return {"today": self._today().isoformat(), "settings": self._repo.settings(), "count": self._repo.count(),
                "open_session": self._repo.open_session()}

    # ---------- บันทึกเวลา ----------
    @_locked
    def day(self, iso: str):
        d, today, now = date.fromisoformat(iso), self._today(), self._now()
        s = self._repo.settings()
        sessions = self._repo.on(d)
        week = tc.week_of(d)
        mins = self._repo.day_minutes(week[0], week[-1])
        missing = self._repo.missing_days(today) if s["remind_missing"] else []
        days = []
        for w in week:
            iso_w = w.isoformat()
            m = mins.get(iso_w, 0)
            state = "future" if w > today else "done" if m else "miss" if iso_w in missing else "empty"
            sub = {"done": "✓ " + tc.fmt_hours(m, s["unit"]), "miss": "ลืมกรอก"}.get(state, "–")
            days.append({"date": iso_w, "wd": td.WEEKDAY_SHORT[w.weekday()], "n": w.day, "minutes": m, "state": state, "sub": sub})
        miss = next((m for m in missing if m != iso), None)
        return {
            "date": iso, "label": td.short(d), "label_short": _short(d), "next_label": _short(d + timedelta(days=1)),
            "is_today": d == today, "is_past": d < today,
            "sessions": sessions, "total_min": sum(x["minutes"] for x in sessions),
            "now_abs": (now.date() - d).days * tc.DAY + now.hour * 60 + now.minute, "now_hhmm": f"{now:%H:%M}",
            "week": {"days": days, "label": _range_label(week[0], week[-1]), "is_current": today in week,
                     "prev": (d - timedelta(days=7)).isoformat(), "next": (d + timedelta(days=7)).isoformat()},
            "missing": {"date": miss, "label": _short(date.fromisoformat(miss))} if miss else None,
        }

    @_locked
    def save_session(self, data: dict):
        return self._repo.save(data, now=self._now())

    @_locked
    def delete_session(self, sid: int):
        return {"ok": True, "deleted": self._repo.delete(int(sid))}

    @_locked
    def restore_session(self, row: dict):
        return {"ok": True, "session": self._repo.restore(row)}

    @_locked
    def start_now(self):
        now = self._now()
        return self._repo.save({"date": now.date().isoformat(), "start": f"{now:%H:%M}", "end": None, "break_min": 0, "note": ""}, now=now)

    @_locked
    def stop_now(self, sid: int):
        s = self._repo.get(int(sid))
        if not s or not s["open"]:
            return {"ok": False, "error": {"code": "not_open", "message": "ช่วงนี้ไม่ได้กำลังทำงานอยู่"}}
        now = self._now()
        start_dt = datetime.combine(date.fromisoformat(s["date"]), datetime.min.time()) + timedelta(minutes=tc.parse_hhmm(s["start"]))
        if now - start_dt >= timedelta(hours=24):
            return {"ok": False, "error": {"code": "too_long", "message": "ช่วงนี้เกิน 24 ชั่วโมงแล้ว กรอกเวลาออกงานเองแทนนะ"}}
        return self._repo.save({**s, "end": f"{now:%H:%M}"}, now=now)

    @_locked
    def mark_day_off(self, iso: str):
        self._repo.mark_day_off(date.fromisoformat(iso))
        return {"ok": True}

    # ---------- periods / ประวัติ ----------
    @_locked
    def period(self, kind: str, anchor: str, offset: int = 0):
        a, s = date.fromisoformat(anchor), self._repo.settings()
        if kind == "week":
            wk = tc.week_of(a + timedelta(days=7 * int(offset)))
            start, end = wk[0], wk[-1]
        else:
            start, end = td.cycle_for(a, s["cycle_mode"], s["cutoff_day"])
            if offset:
                start, end = td.shift_cycle(start, end, int(offset), s["cycle_mode"], s["cutoff_day"])
        return {"start": start.isoformat(), "end": end.isoformat(), "label": f"{td.slash(start)} – {td.slash(end)}",
                "label_short": _range_slash(start, end), "title": td.title_from_pattern(s["title_pattern"], start, end)}

    @_locked
    def all_range(self):
        f, l = self._repo.first_date(), self._repo.last_date()
        f, l = f or self._today(), l or self._today()
        return {"start": f.isoformat(), "end": l.isoformat()}

    @_locked
    def history(self, start: str, end: str, query: str = ""):
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        groups: dict[str, dict] = {}
        rows = self._repo.between(a, b, query or "")
        for r in rows:
            d = date.fromisoformat(r["date"])
            g = groups.setdefault(r["date"], {"date": r["date"], "label": f"{td.WEEKDAY_SHORT[d.weekday()]} {td.slash(d)}", "slash": td.slash(d),
                                              "total_min": 0, "sessions": []})
            g["sessions"].append(r)
            g["total_min"] += r["minutes"]
        return {"groups": list(groups.values()), "count": len(rows), "total_min": sum(r["minutes"] for r in rows),
                "label": f"{td.slash(a)} – {td.slash(b)}"}

    # ---------- รายงาน ----------
    @_locked
    def report(self, start: str, end: str, unit: str = "decimal"):
        a, b = date.fromisoformat(start), date.fromisoformat(end)
        s = self._repo.settings()
        rep = report.build(self._repo, a, b, unit)
        rep["label_short"] = _range_slash(a, b)
        rep["default_title"] = td.title_from_pattern(s["title_pattern"], a, b)
        rep["recent"] = self._recent()
        if not rep["sessions"] and (last := self._repo.last_date()):
            ls, le = td.cycle_for(last, s["cycle_mode"], s["cutoff_day"])
            rep["latest"] = {"start": ls.isoformat(), "end": le.isoformat()}
        return rep

    def _html(self, opts: dict, font_base: str) -> str:
        a, b = date.fromisoformat(opts["start"]), date.fromisoformat(opts["end"])
        rep = report.build(self._repo, a, b, opts.get("unit") or "decimal")
        mascot = None
        if opts.get("mascot") and self._repo.settings()["show_characters"]:
            svg = resource("web/img/chars/character-idle.svg").read_text(encoding="utf-8")
            mascot = re.sub(r"^<\?xml[^>]*>\s*", "", svg)
        name = self._repo.settings()["display_name"]
        title = opts.get("title") or td.title_from_pattern(self._repo.settings()["title_pattern"], a, b)
        if name:
            rep["label"] = f"{name} · {rep['label']}"
        return report.render_html(rep, title=title, columns=opts.get("columns") or [], footnote=bool(opts.get("footnote", True)),
                                  timestamp=bool(opts.get("timestamp", True)), mascot_svg=mascot, font_base=font_base, printed_at=self._now())

    @_locked
    def report_preview(self, opts: dict):
        return self._html(opts, "fonts/")

    @_locked
    def export_report(self, opts: dict):
        fmt = "png" if opts.get("format") == "png" else "pdf"
        title = opts.get("title") or "รายงาน"
        filename = re.sub(r'[\\/:*?"<>|]+', "-", title).strip(" .-") + f".{fmt}"
        path = self._dialogs.save(filename, fmt) if self._dialogs else None
        if not path:
            return {"ok": False, "cancelled": True}
        try:
            html = self._html(opts, resource("web/fonts").as_uri() + "/")
            out = exporter.export(html, Path(path), fmt)
        except exporter.ExportError as e:
            return {"ok": False, "error": str(e)}
        except OSError as e:
            return {"ok": False, "error": f"บันทึกไฟล์ไม่สำเร็จ ({e.strerror or e}) ลองเลือกโฟลเดอร์อื่น"}
        self._repo.add_export(str(out), fmt, title)
        return {"ok": True, "path": str(out), "name": out.name, "recent": self._recent()}

    def _recent(self):
        out = []
        for r in self._repo.recent_exports():
            when = datetime.strptime(r["created_at"], "%Y-%m-%d %H:%M:%S")
            out.append({"path": r["path"], "name": Path(r["path"]).name, "format": r["format"], "when": f"{when.day} {td.MONTH_SHORT[when.month]}"})
        return out

    def reveal(self, path: str):
        p = Path(path)
        if sys.platform == "win32":
            if p.is_file():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(p if p.is_dir() else p.parent))  # noqa: S606 - opening a local folder for the user
        return {"ok": True}

    # ---------- ตั้งค่า ----------
    @_locked
    def save_settings(self, patch: dict):
        return self._repo.save_settings(patch)

    @_locked
    def data_info(self):
        s = self._repo.settings()
        start, end = td.cycle_for(self._today(), s["cycle_mode"], s["cutoff_day"])
        return {"db_path": str(self._db_file), "db_path_short": _short_path(self._db_file), "count": self._repo.count(),
                "last_backup": s.get("last_backup") or "",
                "cycle": {"label": f"{td.slash(start)} – {td.slash(end)}", "title": td.title_from_pattern(s["title_pattern"], start, end)}}

    @_locked
    def backup(self):
        today = self._today()
        path = self._dialogs.save(f"ตอกบัตร-สำรอง-{today.isoformat()}.db", "db") if self._dialogs else None
        if not path:
            return {"ok": False, "cancelled": True}
        try:
            dst = sqlite3.connect(path)
            with dst:
                self._con.backup(dst)
            dst.close()
        except sqlite3.Error as e:
            return {"ok": False, "error": f"สำรองข้อมูลไม่สำเร็จ ({e})"}
        now = self._now()
        self._repo.save_settings({"last_backup": f"{td.slash(now.date())} {now:%H:%M}"})
        return {"ok": True, "path": path, "name": Path(path).name}

    @_locked
    def restore(self):
        path = self._dialogs.open("db") if self._dialogs else None
        if not path:
            return {"ok": False, "cancelled": True}
        if Path(path).resolve() == self._db_file.resolve():
            return {"ok": False, "error": "ไฟล์นี้คือข้อมูลที่ใช้อยู่ตอนนี้ เลือกไฟล์สำรองอีกไฟล์นะ"}
        if not db.is_tokbat_db(path):
            return {"ok": False, "error": "ไฟล์นี้ไม่ใช่ไฟล์สำรองของตอกบัตร"}
        keep = self._db_file.with_name(f"ก่อนกู้คืน-{self._now():%Y%m%d-%H%M%S}.db")
        dst = sqlite3.connect(keep)
        with dst:
            self._con.backup(dst)
        dst.close()
        src = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
        with self._con:
            src.backup(self._con)
        src.close()
        db.migrate(self._con)
        return {"ok": True, "count": self._repo.count(), "kept": str(keep)}

    @_locked
    def import_pick(self):
        path = self._dialogs.open("csv") if self._dialogs else None
        if not path:
            return {"ok": False, "cancelled": True}
        try:
            parsed = csv_io.parse(Path(path).read_bytes())
        except (OSError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        rows, dup = [], 0
        for r in parsed["rows"]:
            if self._repo.exists(date.fromisoformat(r["date"]), tc.parse_hhmm(r["start"]), tc.parse_hhmm(r["end"])):
                dup += 1
            else:
                rows.append(r)
        token = secrets.token_hex(8)
        self._pending_imports = {token: rows}
        dates = sorted(r["date"] for r in rows)
        label = f"{td.slash(date.fromisoformat(dates[0]))} – {td.slash(date.fromisoformat(dates[-1]))}" if dates else ""
        return {"ok": True, "token": token, "count": len(rows), "duplicates": dup, "skipped": len(parsed["skipped"]), "label": label, "name": Path(path).name}

    @_locked
    def import_commit(self, token: str):
        rows = self._pending_imports.pop(token, None)
        if rows is None:
            return {"ok": False, "error": "หมดเวลานำเข้าแล้ว เลือกไฟล์ใหม่อีกครั้งนะ"}
        added = conflicts = 0
        for r in rows:
            if self._repo.save(r, now=self._now())["ok"]:
                added += 1
            else:
                conflicts += 1
        if added:
            self._repo.save_settings({"first_run_done": True})
        return {"ok": True, "added": added, "conflicts": conflicts}

    @_locked
    def delete_all(self):
        return {"ok": True, "deleted": self._repo.delete_all()}


def _short(d: date) -> str:
    return f"{td.WEEKDAY_SHORT[d.weekday()]} {d.day} {td.MONTH_SHORT[d.month]}"


def _range_label(a: date, b: date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {td.MONTH_SHORT[b.month]} {td.be_year(b)}"
    return f"{a.day} {td.MONTH_SHORT[a.month]} – {b.day} {td.MONTH_SHORT[b.month]} {td.be_year(b)}"


def _range_slash(a: date, b: date) -> str:
    return f"{a.day}/{a.month} – {b.day}/{b.month}/{td.be_year(b)}"


def _short_path(p: Path) -> str:
    parts = Path(p).parts
    return "\\".join(parts[-3:]) if len(parts) > 3 else str(p)
