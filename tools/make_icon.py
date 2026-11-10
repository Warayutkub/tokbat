"""Build the app icon (build-assets/tokbat.ico) from the peeking chalk mascot exported from Figma."""
from __future__ import annotations

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "img" / "chars" / "character-peek.svg"
OUT = ROOT / "build-assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_svg(path: Path, px: int) -> Image.Image:
    doc = pymupdf.open(str(path))
    page = doc[0]
    zoom = px / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
    img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    doc.close()
    return img.crop(img.getbbox())


def main() -> Path:
    OUT.mkdir(exist_ok=True)
    big = 1024
    base = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle((24, 24, big - 24, big - 24), radius=220, fill=(0xE3, 0xEF, 0xFF, 255), outline=(0x22, 0x30, 0x4A, 255), width=34)
    chalk = render_svg(SRC, 2000)
    scale = (big * 0.80) / chalk.height
    chalk = chalk.resize((round(chalk.width * scale), round(chalk.height * scale)), Image.LANCZOS)
    base.alpha_composite(chalk, ((big - chalk.width) // 2, big - 24 - 34 - chalk.height + 30))
    # keep the mascot inside the rounded square
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, big - 24, big - 24), radius=220, fill=255)
    clipped = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    clipped.paste(base, (0, 0), mask)
    ImageDraw.Draw(clipped).rounded_rectangle((24, 24, big - 24, big - 24), radius=220, outline=(0x22, 0x30, 0x4A, 255), width=34)
    clipped.save(OUT / "tokbat-1024.png")
    ico = OUT / "tokbat.ico"
    clipped.save(ico, sizes=[(s, s) for s in SIZES])
    return ico


if __name__ == "__main__":
    print(main())
