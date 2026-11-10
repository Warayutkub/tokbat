"""Run the UI in a normal browser for development: serves web/ and answers /api/<method> with the real Api.

    python devserver.py [port]      (data goes to .dev-data/, never your real Documents folder)
"""
from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEV = ROOT / ".dev-data"
os.environ.setdefault("TOKBAT_DATA_DIR", str(DEV))

from tokbat.api import Api, Dialogs  # noqa: E402  (env must be set first)
from tokbat.paths import db_path  # noqa: E402


class DevDialogs(Dialogs):
    """No native pickers in a browser: saves go to .dev-data/exports, opens use TOKBAT_DEV_OPEN or a sample."""

    def save(self, filename, kind):
        out = DEV / "exports" / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        return str(out)

    def open(self, kind):
        if os.environ.get("TOKBAT_DEV_OPEN"):
            return os.environ["TOKBAT_DEV_OPEN"]
        if kind == "csv":
            return str(ROOT.parent / "fixtures" / "sample-sheet.csv")
        backups = sorted((DEV / "exports").glob("*.db"))
        return str(backups[-1]) if backups else None


API = Api(db_path(), DevDialogs())


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "web"), **kw)

    def log_message(self, fmt, *args):  # quieter console
        if "/api/" in (args[0] if args else ""):
            return
        super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html") or self.path.startswith("/?"):
            html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").replace("<head>", "<head><script>window.TOKBAT_HTTP=1</script>", 1)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/"):
            self.send_error(404)
            return
        name = self.path[5:]
        fn = getattr(API, name, None)
        if name.startswith("_") or not callable(fn):
            self.send_error(404, f"no api {name}")
            return
        args = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"[]")
        try:
            out = json.dumps(fn(*args), ensure_ascii=False).encode("utf-8")
        except Exception as e:  # surface the error to the page during development
            self.send_error(500, f"{type(e).__name__}: {e}")
            raise
        self.send_response(200)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5177
    sys.stdout.reconfigure(errors="replace")
    print(f"tokbat dev server -> http://127.0.0.1:{port}  (data: {DEV})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
