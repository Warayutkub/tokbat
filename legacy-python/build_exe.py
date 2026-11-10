"""Build dist/tokbat/tokbat.exe in a clean venv (only the app's own libraries), then self-test it.

    python tools/build_exe.py

Building from the everyday Python pulls in whatever else is installed (torch, jax, opencv…) — 1.3 GB.
The clean venv keeps it at ~136 MB.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv-build"
PY = VENV / "Scripts" / "python.exe"
DEPS = ["pywebview", "Jinja2", "PyMuPDF", "Pillow", "pyinstaller"]
EXCLUDE = ["pymupdf4llm", "pymupdf_layout", "tkinter", "numpy", "onnxruntime"]


def run(*cmd: str) -> None:
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def app_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq tokbat.exe", "/NH"], capture_output=True, text=True).stdout
    return "tokbat.exe" in out


def main() -> int:
    if app_running():   # PyInstaller would half-delete dist/tokbat and then fail on the locked files
        print("ตอกบัตรเปิดอยู่ ปิดแอปก่อนแล้วค่อย build ใหม่", file=sys.stderr)
        return 2
    if not PY.exists():
        run(sys.executable, "-m", "venv", str(VENV))
        run(str(PY), "-m", "pip", "install", "--progress-bar", "off", "--timeout", "30", *DEPS)
    run(str(PY), "tools/make_icon.py")
    args = [str(PY), "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "tokbat",
            "--icon", "build-assets/tokbat.ico", "--add-data", "web;web", "--add-data", "tokbat/templates;tokbat/templates"]
    for m in EXCLUDE:
        args += ["--exclude-module", m]
    run(*args, "app.py")
    out = Path(tempfile.mkdtemp(prefix="tokbat-exe-test-"))
    code = subprocess.run([str(ROOT / "dist" / "tokbat" / "tokbat.exe"), "--selftest", str(out)], timeout=180).returncode
    print(json.dumps(json.loads((out / "results.json").read_text(encoding="utf-8")), ensure_ascii=False, indent=1))
    print("SELFTEST", "OK" if code == 0 else "FAILED", "→", ROOT / "dist" / "tokbat" / "tokbat.exe")
    return code


if __name__ == "__main__":
    sys.exit(main())
