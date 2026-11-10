"""All reads and writes to the database. Returns plain dicts the UI can use as JSON."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

from . import thaidate as td
from . import timecalc as tc

DEFAULT_SETTINGS: dict = {
    "display_name": "",
    "cycle_mode": "cutoff",          # "month" | "cutoff"
    "cutoff_day": 20,
    "title_pattern": "{เดือน}/{ปี}",
    "unit": "decimal",               # "decimal" (6.75) | "hm" (6:45)
    "default_break": 0,
    "remind_missing": True,
    "show_characters": True,
    "report_columns": ["date", "start", "end", "hours", "note"],
    "report_footnote": True,
    "report_timestamp": True,
    "report_mascot": True,
    "first_run_done": False,
    "last_backup": "",
}


class Repo:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    # ---------- sessions ----------
    @staticmethod
    def to_dict(row: sqlite3.Row) -> dict:
        start, end, brk = row["start_min"], row["end_min"], row["break_min"]
        d = {
            "id": row["id"],
            "date": row["work_date"],
            "start": tc.fmt_hhmm(start),
            "end": None if end is None else tc.fmt_hhmm(end),
            "break_min": brk,
            "note": row["note"],
            "open": end is None,
            "overnight": end is not None and tc.is_overnight(start, end),
        }
        d["minutes"] = 0 if end is None else tc.net_minutes(start, end, brk)
        d["hours"] = tc.to_decimal_hours(d["minutes"])
        return d

    def get(self, sid: int) -> dict | None:
        row = self.con.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return self.to_dict(row) if row else None

    def between(self, start: date, end: date, query: str = "") -> list[dict]:
        sql = "SELECT * FROM sessions WHERE work_date BETWEEN ? AND ?"
        args: list = [start.isoformat(), end.isoformat()]
        if query.strip():
            sql += " AND note LIKE ?"
            args.append(f"%{query.strip()}%")
        sql += " ORDER BY work_date, start_min"
        return [self.to_dict(r) for r in self.con.execute(sql, args)]

    def on(self, d: date) -> list[dict]:
        return self.between(d, d)

    def open_session(self) -> dict | None:
        row = self.con.execute("SELECT * FROM sessions WHERE end_min IS NULL ORDER BY work_date DESC LIMIT 1").fetchone()
        return self.to_dict(row) if row else None

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

    def first_date(self) -> date | None:
        v = self.con.execute("SELECT MIN(work_date) FROM sessions").fetchone()[0]
        return date.fromisoformat(v) if v else None

    def last_date(self) -> date | None:
        v = self.con.execute("SELECT MAX(work_date) FROM sessions").fetchone()[0]
        return date.fromisoformat(v) if v else None

    def check(self, d: date, start: int, end: int | None, break_min: int, sid: int | None = None, now: datetime | None = None) -> dict | None:
        """None when the session can be saved, otherwise {code, message, ...} for the UI."""
        try:
            if end is not None:
                tc.net_minutes(start, end, break_min)
        except tc.TimeError as e:
            return {"code": e.code, "message": str(e)}
        now = now or datetime.now()
        now_abs = (now.date() - d).days * tc.DAY + now.hour * 60 + now.minute
        cand = tc.interval_for(d, start, end, d, now_abs, sid)
        others = []
        for s in self.between(d - timedelta(days=1), d + timedelta(days=1)):
            sd = date.fromisoformat(s["date"])
            others.append((s, tc.interval_for(sd, tc.parse_hhmm(s["start"]), None if s["end"] is None else tc.parse_hhmm(s["end"]), d, now_abs, s["id"])))
        hits = [(s, iv, m) for s, iv in others if iv.id != sid and (m := cand.overlap(iv)) > 0]
        if not hits:
            return None
        s, iv, m = max(hits, key=lambda h: h[2])
        suggest = None
        if iv.start_abs <= cand.start_abs < iv.end_abs:
            suggest = tc.fmt_hhmm(iv.end_abs)   # start right after the other one
        return {
            "code": "overlap",
            "message": f"ทับกับช่วง {s['start']}–{s['end'] or 'ตอนนี้'} ของ {td.slash(date.fromisoformat(s['date']))} อยู่ {tc.to_hm_thai(m)}",
            "with": s,
            "overlap_min": m,
            "suggest_start": suggest,
        }

    def save(self, data: dict, now: datetime | None = None) -> dict:
        """Insert or update. Returns {ok, session, previous} or {ok: False, error}."""
        d = date.fromisoformat(data["date"])
        try:
            start = tc.parse_hhmm(data["start"])
            end = None if data.get("end") in (None, "") else tc.parse_hhmm(data["end"])
        except tc.TimeError as e:
            return {"ok": False, "error": {"code": e.code, "message": str(e)}}
        brk = int(data.get("break_min") or 0)
        note = str(data.get("note") or "").strip()
        sid = data.get("id")
        err = self.check(d, start, end, brk, sid, now)
        if err:
            return {"ok": False, "error": err}
        previous = self.get(sid) if sid else None
        with self.con:
            if sid:
                self.con.execute(
                    "UPDATE sessions SET work_date=?, start_min=?, end_min=?, break_min=?, note=?, updated_at=datetime('now','localtime') WHERE id=?",
                    (d.isoformat(), start, end, brk, note, sid))
            else:
                cur = self.con.execute("INSERT INTO sessions (work_date, start_min, end_min, break_min, note) VALUES (?,?,?,?,?)",
                                       (d.isoformat(), start, end, brk, note))
                sid = cur.lastrowid
        return {"ok": True, "session": self.get(sid), "previous": previous}

    def delete(self, sid: int) -> dict | None:
        row = self.get(sid)
        if row:
            with self.con:
                self.con.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        return row

    def restore(self, s: dict) -> dict:
        """Put back a deleted session (undo) with its old id."""
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO sessions (id, work_date, start_min, end_min, break_min, note) VALUES (?,?,?,?,?,?)",
                             (s["id"], s["date"], tc.parse_hhmm(s["start"]), None if s["end"] is None else tc.parse_hhmm(s["end"]), int(s["break_min"]), s["note"]))
        return self.get(s["id"])

    def delete_all(self) -> int:
        n = self.count()
        with self.con:
            self.con.execute("DELETE FROM sessions")
            self.con.execute("DELETE FROM days_off")
        return n

    def exists(self, d: date, start: int, end: int | None) -> bool:
        return self.con.execute("SELECT 1 FROM sessions WHERE work_date=? AND start_min=? AND end_min IS ?",
                                (d.isoformat(), start, end)).fetchone() is not None

    # ---------- days ----------
    def day_minutes(self, start: date, end: date) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.between(start, end):
            out[s["date"]] = out.get(s["date"], 0) + s["minutes"]
        return out

    def mark_day_off(self, d: date) -> None:
        with self.con:
            self.con.execute("INSERT OR IGNORE INTO days_off (work_date) VALUES (?)", (d.isoformat(),))

    def missing_days(self, today: date, lookback: int = 14) -> list[str]:
        """Past days (newest first) with no session, after the first entry, not marked as off."""
        first = self.first_date()
        if not first:
            return []
        start = max(first, today - timedelta(days=lookback))
        have = set(self.day_minutes(start, today).keys())
        off = {r[0] for r in self.con.execute("SELECT work_date FROM days_off")}
        out, d = [], today - timedelta(days=1)
        while d >= start:
            iso = d.isoformat()
            if iso not in have and iso not in off:
                out.append(iso)
            d -= timedelta(days=1)
        return out

    # ---------- settings ----------
    def settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        for k, v in self.con.execute("SELECT key, value FROM settings"):
            try:
                s[k] = json.loads(v)
            except ValueError:
                pass
        return s

    def save_settings(self, patch: dict) -> dict:
        with self.con:
            for k, v in patch.items():
                if k in DEFAULT_SETTINGS:
                    self.con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v, ensure_ascii=False)))
        return self.settings()

    # ---------- exports ----------
    def add_export(self, path: str, fmt: str, title: str) -> None:
        with self.con:
            self.con.execute("INSERT INTO exports (path, format, title) VALUES (?,?,?)", (path, fmt, title))

    def recent_exports(self, limit: int = 3) -> list[dict]:
        return [dict(r) for r in self.con.execute("SELECT path, format, title, created_at FROM exports ORDER BY id DESC LIMIT ?", (limit,))]
