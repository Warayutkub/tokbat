"""Render pets (and later props/scene) to a PNG with Edge headless for a quick look."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import draw  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "out"  # gitignored
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def shoot(html: str, name: str, w: int, h: int, scale=1.5):
    OUT.mkdir(exist_ok=True)
    page = OUT / f"{name}.html"
    page.write_text(html, encoding="utf-8")
    out = OUT / f"{name}.png"
    out.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as prof:
        env = {k: v for k, v in os.environ.items() if not k.startswith("WEBVIEW2_")}
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                        f"--window-size={w},{h}", f"--force-device-scale-factor={scale}", f"--screenshot={out}",
                        page.as_uri()], env=env, capture_output=True, timeout=90)
        for _ in range(60):
            if out.exists() and out.stat().st_size > 2000:
                break
            time.sleep(0.25)
    return out


def pets_sheet():
    rows = []
    for title, fn, sets in (("แมว", draw.cat, draw.CATS), ("หมา", draw.dog, draw.DOGS), ("กระต่าย", draw.rabbit, draw.RABBITS)):
        cells = "".join(f'<div class="c"><div>{fn(c, seed=11 + i)}</div><p>{name}</p></div>' for i, (name, c) in enumerate(sets.items()))
        rows.append(f'<h2>{title}</h2><div class="row">{cells}</div>')
    html = ("<html><head><meta charset='utf-8'><style>body{margin:16px;background:#BFE3A1;font:600 14px 'Leelawadee UI';color:#22304A}"
            ".row{display:flex;gap:18px}.c{background:#CDEBB2;border-radius:12px;padding:6px}.c p{margin:0;text-align:center}"
            "h2{margin:6px 0}</style></head><body>" + "".join(rows) + "</body></html>")
    return shoot(html, "pets", 940, 720)


if __name__ == "__main__":
    print(pets_sheet())
