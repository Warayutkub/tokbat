"""Make Figma-exported, brushed SVGs small and safe for the app.

- coordinates rounded to 0.1 px (brush outlines are long paths; this roughly halves the size)
- Figma layer names that are animated parts (leg-*, tail, eye-l …) become classes; every other id goes,
  except ids the drawing itself points at with url(#…) (sky gradients, clip paths)
- the result is checked: nothing that can run code or load anything from outside
"""
import re

PARTS = {"leg-back-far", "leg-back-near", "leg-front-far", "leg-front-near", "tail", "body", "head", "ear-l", "ear-r", "face", "eye-l", "eye-r",
         "pupil", "cheeks", "mouth", "tongue", "dust", "stem", "leaf", "trunk", "canopy", "fronds", "fronds-back", "lamp"}

# anything here means the file is refused (the app checks the same list before installing a pack)
UNSAFE = [r"<script", r"<foreignObject", r"<iframe", r"<!ENTITY", r"<!DOCTYPE", r"\son[a-z]+\s*=", r"javascript:", r"data:text/html",
          r"(?:href|src)\s*=\s*[\"'](?!#)", r"url\(\s*['\"]?(?!#)", r"@import"]


def _num(m):
    s = f"{float(m.group(0)):.1f}"
    if s in ("0.0", "-0.0"):
        return "0"
    return s.rstrip("0").rstrip(".") if "." in s else s


def slim(svg_text):
    s = re.sub(r"<\?xml[^>]*\?>", "", svg_text)
    s = re.sub(r"-?\d+\.\d{2,}", _num, s)
    keep = set(re.findall(r"url\(#([^)]+)\)", s))

    def gid(m):
        raw = m.group(1)
        if raw in keep:
            return f' id="{raw}"'
        return f' class="{raw}"' if raw in PARTS else ""
    s = re.sub(r'\s+id="([^"]*)"', gid, s)
    s = re.sub(r">\s+<", "><", s).strip()
    problems = unsafe(s)
    if problems:
        raise ValueError(f"unsafe SVG: {problems}")
    return s


def unsafe(svg_text):
    return [p for p in UNSAFE if re.search(p, svg_text, re.IGNORECASE)]


def size(svg_text):
    w, h = svg_text.split('viewBox="')[1].split('"')[0].split()[2:]
    return float(w), float(h)
