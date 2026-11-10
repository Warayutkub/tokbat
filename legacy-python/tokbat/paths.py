"""Where things live: bundled files (web/, templates) and the user's data folder."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


def resource(rel: str) -> Path:
    """A file shipped with the app (works from source and from a PyInstaller build)."""
    base = Path(getattr(sys, "_MEIPASS", APP_DIR))
    if not (base / rel).exists() and (APP_DIR.parent / rel).exists():
        return APP_DIR.parent / rel  # web/ is shared with the Rust app one folder up
    return base / rel


def documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            from uuid import UUID

            class GUID(ctypes.Structure):
                _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_byte * 8)]

            u = UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")  # FOLDERID_Documents
            g = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_byte * 8).from_buffer_copy(u.bytes[8:]))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) == 0:
                p = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                return p
        except (OSError, AttributeError, ValueError):
            pass
    return Path.home() / "Documents"


def data_dir() -> Path:
    override = os.environ.get("TOKBAT_DATA_DIR")
    d = Path(override) if override else documents_dir() / "ตอกบัตร"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / "worktime.db"
