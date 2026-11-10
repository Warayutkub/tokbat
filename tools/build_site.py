"""Prepare the GitHub Pages site in docs/ from the app's own files, so the two never drift apart.

    python tools/build_site.py

- web/css/tokens.css and web/css/mascots.css      → docs/css/ (same colours and mascot motion as the app)
- web/img/chars/anim/*.svg                         → docs/img/chars/
- web/fonts/*.ttf                                  → docs/fonts/*.woff2 (+ OFL.txt)
- build-assets/site/*.png (app screenshots, made-up data) → docs/img/*.webp
- build-assets/tokbat-1024.png                     → docs/img/favicon.png, apple-touch-icon.png
docs/index.html, docs/css/site.css and docs/js/site.js are written by hand; this script then stamps
?v=<hash> on their CSS/JS links so browsers fetch a file again as soon as it changes (Pages caches for 10 min).
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WEB, DOCS, SRC = ROOT / "web", ROOT / "docs", ROOT / "build-assets" / "site"
WEIGHTS = ["Regular", "Medium", "SemiBold"]
SHOTS = {"app-log": 1600, "app-history": 1600, "app-report": 1600, "app-dayoff": 1600, "report-a4": 900}


def copy_css() -> None:
    (DOCS / "css").mkdir(parents=True, exist_ok=True)
    for name in ("tokens.css", "mascots.css"):
        text = (WEB / "css" / name).read_text(encoding="utf-8")
        note = f"/* Copied from web/css/{name} by tools/build_site.py — edit the app's file, then rerun. */\n"
        (DOCS / "css" / name).write_text(note + text, encoding="utf-8")


def copy_mascots() -> None:
    out = DOCS / "img" / "chars"
    out.mkdir(parents=True, exist_ok=True)
    for svg in (WEB / "img" / "chars" / "anim").glob("*.svg"):
        shutil.copy2(svg, out / svg.name)


def fonts() -> None:
    out = DOCS / "fonts"
    out.mkdir(parents=True, exist_ok=True)
    for w in WEIGHTS:
        src, dst = WEB / "fonts" / f"IBMPlexSansThaiLooped-{w}.ttf", out / f"IBMPlexSansThaiLooped-{w}.woff2"
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue  # WOFF2 output differs byte-wise on every run; don't churn git when the font didn't change
        font = TTFont(src)
        font.flavor = "woff2"
        font.save(dst)
    shutil.copy2(WEB / "fonts" / "OFL.txt", out / "OFL.txt")


def images() -> None:
    out = DOCS / "img"
    out.mkdir(parents=True, exist_ok=True)
    for name, width in SHOTS.items():
        im = Image.open(SRC / f"{name}.png").convert("RGB")
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im.save(out / f"{name}.webp", "WEBP", quality=84, method=6)
    icon = Image.open(ROOT / "build-assets" / "tokbat-1024.png").convert("RGBA")
    icon.resize((64, 64), Image.LANCZOS).save(out / "favicon.png")
    icon.resize((180, 180), Image.LANCZOS).save(out / "apple-touch-icon.png")


def stamp() -> None:
    """css/x.css → css/x.css?v=<first 8 of its sha1>, same for js/."""
    page = DOCS / "index.html"
    html = page.read_text(encoding="utf-8")

    def versioned(m: re.Match) -> str:
        path = m.group(2)
        digest = hashlib.sha1((DOCS / path).read_bytes()).hexdigest()[:8]
        return f'{m.group(1)}{path}?v={digest}"'

    html = re.sub(r'((?:href|src)=")((?:css|js)/[\w.-]+\.(?:css|js))(?:\?v=\w+)?"', versioned, html)
    page.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    copy_css()
    copy_mascots()
    fonts()
    images()
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    stamp()
    for p in sorted(DOCS.rglob("*")):
        if p.is_file():
            print(f"{p.stat().st_size:>9,}  {p.relative_to(DOCS)}")
