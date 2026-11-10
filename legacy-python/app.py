"""ตอกบัตร — desktop app entry point (pywebview + Edge WebView2).

    tokbat.exe                       open the app
    tokbat.exe --selftest <folder>   open a hidden window on throwaway data, check it, export a PDF, write results.json
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

import webview

from tokbat.api import Api, Dialogs
from tokbat.paths import data_dir, db_path, documents_dir, resource

APP_TITLE = "ตอกบัตร"
FILE_TYPES = {
    "pdf": ("ไฟล์ PDF (*.pdf)",),
    "png": ("รูปภาพ PNG (*.png)",),
    "db": ("ไฟล์สำรองตอกบัตร (*.db)", "ทุกไฟล์ (*.*)"),
    "csv": ("ไฟล์ CSV (*.csv)", "ทุกไฟล์ (*.*)"),
}


def _dialog(name: str):
    kinds = getattr(webview, "FileDialog", None)
    if kinds is not None:
        return getattr(kinds, name)
    return getattr(webview, f"{name}_DIALOG")


class WindowDialogs(Dialogs):
    def __init__(self, window: webview.Window):
        self.window = window
        self.last_dir = str(documents_dir())

    def save(self, filename, kind):
        res = self.window.create_file_dialog(_dialog("SAVE"), directory=self.last_dir, save_filename=filename, file_types=FILE_TYPES.get(kind, ()))
        path = res[0] if isinstance(res, (tuple, list)) and res else res
        if path:
            self.last_dir = str(Path(path).parent)
        return path or None

    def open(self, kind):
        start = str(data_dir()) if kind == "db" else self.last_dir
        res = self.window.create_file_dialog(_dialog("OPEN"), directory=start, allow_multiple=False, file_types=FILE_TYPES.get(kind, ()))
        return res[0] if res else None


def _window(api: Api, hidden: bool = False) -> webview.Window:
    # Thai UI language for WebView2, so date pickers show day/month like the rest of the app
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--lang=th")
    return webview.create_window(
        APP_TITLE, url=str(resource("web/index.html")), js_api=api, hidden=hidden,
        width=1280, height=820, min_size=(1120, 740), background_color="#EDF3FB", text_select=False,
    )


def main() -> None:
    api = Api(db_path())
    window = _window(api)
    api._attach(WindowDialogs(window))
    webview.start(gui="edgechromium", http_server=True, private_mode=True)


def selftest(out_dir: str) -> int:
    """Checks the packaged app end to end without showing a window."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    os.environ["TOKBAT_DATA_DIR"] = tempfile.mkdtemp(prefix="tokbat-selftest-")
    api = Api(db_path())
    res: dict = {"frozen": bool(getattr(sys, "frozen", False)), "web": resource("web/index.html").is_file()}

    def run(window: webview.Window):
        try:
            window.events.loaded.wait(20)
            time.sleep(2)
            res["welcome"] = window.evaluate_js("!!document.querySelector('.welcome')")
            res["font"] = window.evaluate_js("document.fonts.check('600 26px Looped')")
            res["mascots"] = window.evaluate_js("document.querySelectorAll('svg.chalk').length")
            for d, s, e in [("2026-09-01", "21:00", "03:00"), ("2026-09-02", "13:00", "19:00"), ("2026-09-02", "21:00", "03:00")]:
                api.save_session({"date": d, "start": s, "end": e, "note": "selftest"})
            window.evaluate_js("location.hash = '#/report?kind=custom&start=2026-09-01&end=2026-09-02'")
            time.sleep(2.5)
            res["report_total"] = window.evaluate_js("document.querySelector('.big')?.textContent")

            class Save(Dialogs):
                def save(self, filename, kind):
                    return str(out / filename)

            api._attach(Save())
            opts = {"start": "2026-09-01", "end": "2026-09-02", "title": "selftest", "unit": "decimal",
                    "columns": ["date", "start", "end", "hours", "note"], "footnote": True, "timestamp": True, "mascot": True}
            pdf = api.export_report({**opts, "format": "pdf"})
            png = api.export_report({**opts, "format": "png"})
            res["pdf"] = pdf.get("ok") and Path(pdf["path"]).stat().st_size
            res["png"] = png.get("ok") and Path(png["path"]).stat().st_size
        except Exception:  # report every failure in results.json
            res["error"] = traceback.format_exc()
        finally:
            (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            window.destroy()

    window = _window(api, hidden=True)
    webview.start(run, window, gui="edgechromium", http_server=True, private_mode=True)
    ok = res.get("welcome") and res.get("font") and res.get("mascots") and res.get("report_total") == "18.00" and res.get("pdf") and res.get("png")
    return 0 if ok else 1


def _crash(exc: BaseException) -> None:
    """A windowed build has no console: keep the details in a log and tell the user where it is."""
    log = data_dir() / "error.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        f.write("".join(traceback.format_exception(exc)))
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"ตอกบัตรเปิดไม่สำเร็จ\nรายละเอียดอยู่ที่ {log}\n\nถ้าเพิ่งติดตั้ง Windows ใหม่ ลองติดตั้ง Microsoft Edge WebView2 Runtime", APP_TITLE, 0x10)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
            sys.exit(selftest(sys.argv[2]))
        main()
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001 - last resort for a windowed app
        _crash(e)
        sys.exit(1)
