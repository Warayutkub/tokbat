"""Turn the report HTML into PDF (Microsoft Edge, headless) and PNG (PyMuPDF). Works offline."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

EDGE_CANDIDATES = [
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
]


class ExportError(RuntimeError):
    pass


def find_edge() -> Path | None:
    for p in EDGE_CANDIDATES:
        if p.is_file():
            return p
    found = shutil.which("msedge")
    return Path(found) if found else None


def html_to_pdf(html: str, pdf_path: Path, timeout: int = 60) -> Path:
    edge = find_edge()
    if not edge:
        raise ExportError("ไม่พบ Microsoft Edge ในเครื่อง จึงสร้าง PDF ไม่ได้")
    pdf_path = Path(pdf_path)
    # Edge hands the job to a background process and returns at once, so wait for the file itself.
    with tempfile.TemporaryDirectory(prefix="tokbat-", ignore_cleanup_errors=True) as tmp:
        src = Path(tmp) / "report.html"
        src.write_text(html, encoding="utf-8")
        out = Path(tmp) / "report.pdf"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [str(edge), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
               f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={out}", src.as_uri()]
        deadline = time.monotonic() + timeout
        try:
            subprocess.run(cmd, check=False, timeout=timeout, creationflags=flags, capture_output=True)
        except subprocess.TimeoutExpired as e:
            raise ExportError("Edge ใช้เวลานานเกินไป ลองบันทึกใหม่อีกครั้ง") from e
        last = -1
        while time.monotonic() < deadline:
            size = out.stat().st_size if out.is_file() else -1
            if size > 0 and size == last and _readable_pdf(out):
                break
            last = size
            time.sleep(0.3)
        else:
            raise ExportError("สร้าง PDF ไม่สำเร็จ ลองบันทึกใหม่อีกครั้ง")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, pdf_path)
    return pdf_path


def _readable_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            f.seek(-1024, os.SEEK_END)
            return b"%%EOF" in f.read()
    except OSError:
        return False


def pdf_to_png(pdf_path: Path, png_path: Path, zoom: float = 2.0) -> Path:
    """Every page, stacked top to bottom into one image."""
    import pymupdf
    from PIL import Image

    doc = pymupdf.open(str(pdf_path))
    try:
        pages = []
        for page in doc:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            pages.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    finally:
        doc.close()
    width = max(p.width for p in pages)
    sheet = Image.new("RGB", (width, sum(p.height for p in pages)), "white")
    y = 0
    for p in pages:
        sheet.paste(p, (0, y))
        y += p.height
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(png_path, optimize=True)
    return png_path


def export(html: str, target: Path, fmt: str) -> Path:
    target = Path(target)
    if fmt == "pdf":
        return html_to_pdf(html, target)
    with tempfile.TemporaryDirectory(prefix="tokbat-") as tmp:
        pdf = html_to_pdf(html, Path(tmp) / "r.pdf")
        return pdf_to_png(pdf, target)
