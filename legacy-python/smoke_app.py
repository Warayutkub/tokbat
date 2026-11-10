"""Open the real app window (pywebview + WebView2) on a throwaway data folder, click through, save screenshots.

    python tools/smoke_app.py <out-dir>
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["TOKBAT_DATA_DIR"] = tempfile.mkdtemp(prefix="tokbat-smoke-")
os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--lang=th")

import webview  # noqa: E402
from PIL import ImageGrab  # noqa: E402

from app import WindowDialogs  # noqa: E402
from tokbat.api import Api, Dialogs  # noqa: E402
from tokbat.paths import db_path, resource  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT.mkdir(parents=True, exist_ok=True)
FIXTURE = ROOT.parent / "fixtures" / "sample-sheet.csv"
results: dict = {}


class CsvOnly(Dialogs):
    def open(self, kind):
        return str(FIXTURE)

    def save(self, filename, kind):
        return str(OUT / filename)


def shot(window, name):
    time.sleep(1.2)
    x, y, w, h = window.x, window.y, window.width, window.height
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(OUT / f"{name}.png")


def run(window):
    time.sleep(2.5)
    results["bridge_count"] = window.evaluate_js("window.pywebview.api.bootstrap().then(b => b.count)")
    results["welcome"] = window.evaluate_js("!!document.querySelector('.welcome')")
    results["mascots_inlined"] = window.evaluate_js("document.querySelectorAll('svg.chalk').length")
    results["font"] = window.evaluate_js("document.fonts.check('600 26px Looped')")
    shot(window, "1-welcome")
    api._attach(CsvOnly())
    pre = api.import_pick()
    results["import"] = api.import_commit(pre["token"])
    api._attach(WindowDialogs(window))
    window.evaluate_js("location.hash = '#/log?date=2026-03-03'")
    time.sleep(2.5)
    results["log_hash"] = window.evaluate_js("location.hash")
    results["log_title"] = window.evaluate_js("document.querySelector('.timeline__head')?.textContent")
    results["log_bars"] = window.evaluate_js("document.querySelectorAll('.tl-bar').length")
    shot(window, "2-log")
    window.evaluate_js("location.hash = '#/report?kind=custom&start=2026-03-01&end=2026-03-20'")
    time.sleep(2)
    results["report_total"] = window.evaluate_js("document.querySelector('.big')?.textContent")
    shot(window, "3-report")
    window.evaluate_js("location.hash = '#/history?kind=custom&start=2026-03-01&end=2026-03-20'")
    shot(window, "4-history")
    window.evaluate_js("location.hash = '#/settings'")
    shot(window, "5-settings")
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    window.destroy()


api = Api(db_path())
win = webview.create_window("ตอกบัตร (smoke)", url=str(resource("web/index.html")), js_api=api, width=1280, height=820,
                            x=40, y=20, min_size=(1120, 740), background_color="#EDF3FB", on_top=True)
webview.start(run, win, gui="edgechromium", http_server=True, private_mode=True)
print(json.dumps(results, ensure_ascii=False))
