"""Build and sign a content pack for the garden, ready to publish on GitHub Pages (docs/packs/).

  python tools/make_pack.py <source folder> [--out docs/packs]

The source folder holds pack.src.json and the drawings it names:

  {
    "id": "spring-2027", "version": 1, "title": "ของแต่งหน้าร้อน",
    "items": [{"id": "sun-umbrella", "name": "ร่มชายหาด", "cat": "decor", "price": 45, "rarity": "rare",
               "file": "props/sun-umbrella.svg", "shelter": true}],
    "pets":  [{"species": "cat", "color": "pink", "colorName": "ชมพู", "file": "pets/cat-pink.svg"}]
  }

Drawings must already be slimmed (tools/garden/export.py does that). The builder checks every rule the app checks,
writes <out>/<id>/pack.json + pack.sig + the files, and adds the pack to <out>/index.json.
pack.json is signed byte for byte, so it is written with LF line ends and never re-formatted (see .gitattributes).
"""
import argparse
import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "garden"))
from pack_key import load  # noqa: E402
from slim import size, unsafe  # noqa: E402

BASE = json.loads((HERE.parent / "web/garden/base/manifest.json").read_text(encoding="utf-8"))
CATS = {"trees", "plants", "homes", "farm", "toys", "decor", "ground"}
RARITY = {"common", "rare", "special"}
SPECIES = {"cat": "แมว", "dog": "หมา", "rabbit": "กระต่าย"}
FLAGS = {"shelter", "ground", "bed", "light"}
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
PATH = re.compile(r"^(props|pets)/[a-z0-9][a-z0-9-]{0,59}\.svg$")


def fail(msg):
    raise SystemExit(f"make_pack: {msg}")


def build(src, out):
    spec = json.loads((src / "pack.src.json").read_text(encoding="utf-8"))
    pid, version, title = spec.get("id", ""), spec.get("version"), spec.get("title", "").strip()
    if not ID.match(pid):
        fail(f"bad pack id {pid!r}")
    if not isinstance(version, int) or version < 1:
        fail("version must be a whole number from 1")
    if not title:
        fail("title is empty")
    taken = {i["id"] for i in BASE["items"]}
    files, items, pets = {}, [], []

    def take(path):
        if not PATH.match(path):
            fail(f"bad file path {path!r}")
        text = (src / path).read_text(encoding="utf-8")
        bad = unsafe(text)
        if bad:
            fail(f"{path} is not safe: {bad}")
        files[path] = text
        return size(text)

    for it in spec.get("items", []):
        if not ID.match(it.get("id", "")) or it["id"] in taken:
            fail(f"item id {it.get('id')!r} is bad or already used")
        taken.add(it["id"])
        if it.get("cat") not in CATS or it.get("rarity") not in RARITY:
            fail(f"{it['id']}: cat must be one of {sorted(CATS)}, rarity one of {sorted(RARITY)}")
        if not isinstance(it.get("price"), int) or not 1 <= it["price"] <= 500:
            fail(f"{it['id']}: price 1–500")
        if not it.get("name", "").strip():
            fail(f"{it['id']}: name is empty")
        w, h = take(it["file"])
        extra = {k: it[k] for k in FLAGS if k in it}
        items.append({"id": it["id"], "name": it["name"].strip(), "cat": it["cat"], "price": it["price"], "rarity": it["rarity"],
                      "w": w, "h": h, "file": it["file"], **extra})
    base_pets = {(p["species"], p["color"]) for p in BASE["pets"]}
    for p in spec.get("pets", []):
        key = (p.get("species"), p.get("color"))
        if p.get("species") not in SPECIES or not ID.match(p.get("color", "")) or key in base_pets:
            fail(f"pet {key} is bad or already exists")
        base_pets.add(key)
        w, h = take(p["file"])
        pets.append({"species": p["species"], "color": p["color"], "colorName": p["colorName"], "speciesName": SPECIES[p["species"]],
                     "w": w, "h": h, "file": p["file"]})
    if not items and not pets:
        fail("a pack needs at least one item or pet")

    pack = {"format": 1, "id": pid, "version": version, "title": title, "items": items, "pets": pets,
            "files": {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in sorted(files.items())}}
    body = json.dumps(pack, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sig = base64.b64encode(load().sign(body)).decode("ascii")

    dest = out / pid
    if dest.exists():
        shutil.rmtree(dest)
    for path, text in files.items():
        (dest / path).parent.mkdir(parents=True, exist_ok=True)
        (dest / path).write_bytes(text.encode("utf-8"))
    (dest / "pack.json").write_bytes(body)
    (dest / "pack.sig").write_bytes(sig.encode("ascii"))

    index_file = out / "index.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {"format": 1, "packs": []}
    index["packs"] = [p for p in index["packs"] if p["id"] != pid] + [
        {"id": pid, "version": version, "title": title, "url": f"{pid}/pack.json", "items": len(items), "pets": len(pets)}]
    index_file.write_bytes(json.dumps(index, ensure_ascii=False, indent=1).encode("utf-8") + b"\n")
    print(f"{pid} v{version}: {len(items)} items, {len(pets)} pets -> {dest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default=str(HERE.parent / "docs/packs"))
    a = ap.parse_args()
    build(Path(a.src), Path(a.out))
