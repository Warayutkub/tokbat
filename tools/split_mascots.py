"""Turn the mascot SVGs exported from Figma into animation-ready SVGs.

Figma exports each character as one flat list of paths, in the order they were drawn. SPEC lists that
order as part names, so the paths can be wrapped in nested <g class="p-…"> groups (fig › face › eye-l › pupil)
that web/css/mascots.css moves: blinking, looking around, breathing, waving, zz, confetti.

    python tools/split_mascots.py     (reads web/img/chars/character-*.svg, writes web/img/chars/anim/*.svg)
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "img" / "chars"
OUT = SRC / "anim"


def face(eyes_extra: int = 1, mouth: int = 1) -> list[tuple[str, int]]:
    """eyes (white = 2 paths, then pupil/lid = 1 each), blush (2), mouth."""
    lid = "pupil" if eyes_extra == 1 else "lid"
    return [("fig.face.eye-l", 2), (f"fig.face.eye-l.{lid}", 1), ("fig.face.eye-r", 2), (f"fig.face.eye-r.{lid}", 1),
            ("fig.face.blush", 2), ("fig.face.mouth", mouth)]


def closed_face(mouth: int = 1) -> list[tuple[str, int]]:
    return [("fig.face.eye-l", 2), ("fig.face.eye-l.lid", 1), ("fig.face.eye-r", 2), ("fig.face.eye-r.lid", 1),
            ("fig.face.blush", 2), ("fig.face.mouth", mouth)]


# (part path, how many exported layers) in drawing order — mirrors the generator that drew them in Figma
SPEC: dict[str, list[tuple[str, int]]] = {
    "idle": [("legs", 2), ("fig.arm-l", 1), ("fig.arm-r", 1), ("fig.body", 2), *face(), ("dust", 5)],
    "write": [("trail", 1), ("dust", 4), ("@open", 1),
              ("fig.legs", 2), ("fig.arm-l", 1), ("fig.arm-r", 1), ("fig.body", 2), *face(), ("@close", 1)],
    "break": [("legs", 2), ("fig.body", 2), *closed_face(), ("fig.mug", 3), ("fig.steam", 2), ("fig.hands", 2), ("z1", 1), ("z2", 1)],
    "done": [("fig.legs", 2), ("fig.arm-l", 1), ("fig.arm-r", 1), ("fig.body", 2), ("fig.face.eye-l", 2), ("fig.face.eye-l.lid", 1),
             ("fig.face.eye-r", 2), ("fig.face.eye-r.lid", 1), ("fig.face.blush", 2), ("fig.face.mouth", 2), ("conf", 6), ("dust", 3)],
    "peek": [("fig.body", 2), *face(), ("hands", 4)],
    "eraser": [("legs", 2), ("fig.felt", 10), ("fig.wood", 3), ("fig.face.eyes", 2), ("fig.face.mouth", 1), ("fig.face.blush", 2),
               ("dust", 6), ("z1", 1), ("z2", 1)],
}


def expand(spec):
    for name, n in spec:
        yield from [name] * n


def tag_children(children: list[ET.Element], tags) -> list[tuple[str, ET.Element]]:
    out = []
    for el in children:
        tag = next(tags)
        if tag == "@open":
            inner = tag_children(list(el), tags)
            closing = next(tags)
            assert closing == "@close", f"expected @close, got {closing}"
            out.append(("@group", (el, inner)))
        else:
            out.append((tag, el))
    return out


def nest(items: list[tuple[str, ET.Element]], depth: int = 0) -> list[ET.Element]:
    """Wrap runs that share the same path segment at this depth into <g class="p-segment">."""
    result: list[ET.Element] = []
    i = 0
    while i < len(items):
        tag, el = items[i]
        if tag == "@group":
            g, inner = el
            for c in list(g):
                g.remove(c)
            g.extend(nest(inner, 0))
            g.set("class", "p-wrap")
            result.append(g)
            i += 1
            continue
        parts = tag.split(".")
        if len(parts) <= depth:
            result.append(el)
            i += 1
            continue
        seg = parts[depth]
        j = i
        while j < len(items) and items[j][0] != "@group" and len(items[j][0].split(".")) > depth and items[j][0].split(".")[depth] == seg:
            j += 1
        g = ET.Element(f"{{{SVG_NS}}}g", {"class": f"p-{seg}"})
        g.extend(nest(items[i:j], depth + 1))
        result.append(g)
        i = j
    return result


def strip_ids(el: ET.Element) -> None:
    for e in el.iter():
        e.attrib.pop("id", None)


def split(pose: str) -> Path:
    src = SRC / f"character-{pose}.svg"
    tree = ET.parse(src)
    svg = tree.getroot()
    for d in svg.findall(f"{{{SVG_NS}}}defs"):   # Figma adds a clip for parts that poke out of the frame; let them show
        svg.remove(d)
    for e in svg.iter():
        e.attrib.pop("clip-path", None)
    (frame,) = list(svg)
    children = list(frame)
    tags = iter(list(expand(SPEC[pose])))
    items = tag_children(children, tags)
    left = list(tags)
    assert not left, f"{pose}: {len(left)} part names left over — SPEC does not match the export"
    for c in children:
        frame.remove(c)
    frame.extend(nest(items))
    frame.set("class", "p-root")
    strip_ids(svg)
    svg.set("class", f"chalk chalk--{pose}")
    svg.set("aria-hidden", "true")
    svg.set("focusable", "false")
    for a in ("width", "height"):
        svg.attrib.pop(a, None)
    OUT.mkdir(exist_ok=True)
    out = OUT / f"{pose}.svg"
    tree.write(out, encoding="unicode", xml_declaration=False)
    return out


if __name__ == "__main__":
    for pose in SPEC:
        try:
            print("ok", split(pose).relative_to(ROOT))
        except (AssertionError, StopIteration, ValueError) as e:
            print("FAIL", pose, e, file=sys.stderr)
            sys.exit(1)
