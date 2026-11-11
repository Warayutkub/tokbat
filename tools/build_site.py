"""Prepare the GitHub Pages site in docs/ from the app's own files, so the two never drift apart.

    python tools/build_site.py

- web/css/tokens.css and web/css/mascots.css      → docs/css/ (same colours and mascot motion as the app)
- web/img/chars/anim/*.svg                         → docs/img/chars/
- web/fonts/*.ttf                                  → docs/fonts/*.woff2 (+ OFL.txt)
- build-assets/site/*.png (app screenshots, made-up data) → docs/img/*.webp
- build-assets/tokbat-1024.png                     → docs/img/favicon.png, apple-touch-icon.png
- the garden demo: web/js/garden/stage.js → docs/js/garden/, the scene part of web/css/garden.css
  → docs/css/garden.css, and only the drawings docs/garden/demo.json uses → docs/garden/base/ (+ a manifest
  with the sizes from the approved Figma scene)
docs/index.html, docs/css/site.css, docs/js/site.js, docs/js/garden-demo.js, docs/js/garden/art.js and
docs/garden/demo.json are written by hand; this script then stamps ?v=<hash> on the page's CSS/JS links so
browsers fetch a file again as soon as it changes (Pages caches for 10 min).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WEB, DOCS, SRC = ROOT / "web", ROOT / "docs", ROOT / "build-assets" / "site"
WEIGHTS = ["Regular", "Medium", "SemiBold"]
SHOTS = {"app-home": 1600, "app-log": 1600, "app-history": 1600, "app-report": 1600, "app-dayoff": 1600,
         "report-a4": 900, "garden-day": 1280}
GARDEN = WEB / "garden" / "base"


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


def between(text: str, start: str, end: str) -> str:
    a = text.index(start)
    return text[a:text.index(end, a)]


def garden() -> None:
    """The live garden demo: the app's own stage code, styles and drawings (only what the demo shows)."""
    demo = json.loads((DOCS / "garden" / "demo.json").read_text(encoding="utf-8"))
    props = sorted({row[0] for row in demo["items"]})
    pets = [f"{species}-{color}" for species, color, *_ in demo["pets"]]
    out = DOCS / "garden" / "base"
    if out.exists():
        shutil.rmtree(out)  # generated: drop drawings the demo no longer uses
    for sub, names in (("props", props), ("pets", pets), ("bg", ["day", "night", "rain"])):
        (out / sub).mkdir(parents=True)
        for name in names:
            shutil.copy2(GARDEN / sub / f"{name}.svg", out / sub / f"{name}.svg")
    full = json.loads((GARDEN / "manifest.json").read_text(encoding="utf-8"))
    items = []
    for item in full["items"]:
        if item["id"] in props:
            w, h = demo["sizes"][item["id"]]  # as drawn in the approved scene, a little smaller than in the game
            items.append({**item, "w": w, "h": h})
    manifest = {"items": items, "pets": [p for p in full["pets"] if f"{p['species']}-{p['color']}" in pets], "species": full.get("species", [])}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    js = DOCS / "js" / "garden"
    js.mkdir(parents=True, exist_ok=True)
    for name in ("stage.js",):
        text = (WEB / "js" / "garden" / name).read_text(encoding="utf-8")
        (js / name).write_text(f"// Copied from web/js/garden/{name} by tools/build_site.py — edit the app's file, then rerun.\n" + text,
                               encoding="utf-8")
    css = (WEB / "css" / "garden.css").read_text(encoding="utf-8")
    parts = [between(css, "/* ---------- garden view", "/* ---------- HUD"), between(css, "/* the tint and the rain", "/* pet name tag")]
    note = "/* The scene and pet parts of web/css/garden.css, copied by tools/build_site.py — edit the app's file, then rerun. */\n"
    (DOCS / "css" / "garden.css").write_text(note + "\n".join(p.strip() + "\n" for p in parts), encoding="utf-8")


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
    garden()
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    stamp()
    for p in sorted(DOCS.rglob("*")):
        if p.is_file():
            print(f"{p.stat().st_size:>9,}  {p.relative_to(DOCS)}")
