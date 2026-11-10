"""Export drawings from Figma (brush included) into a folder, slimmed.

  python tools/garden/export.py --within <section or frame id> --prefix "Prop/" --out <folder>
  python tools/garden/export.py --node 18:21411=cat-orange --node 20:31220=gift-box --out <folder>

With --prefix, every FRAME inside --within whose name starts with the prefix is exported as
<name without prefix>.svg (e.g. "Prop/tree-round" → tree-round.svg).
"""
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from slim import slim  # noqa: E402
from wridge import call, open_file  # noqa: E402


def export_node(node_id):
    with tempfile.TemporaryDirectory() as tmp:
        r = call("export_assets", {"nodeIds": [node_id], "outDir": tmp, "format": "svg"})
        return Path(r[0]["file"]).read_text(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--within")
    ap.add_argument("--prefix")
    ap.add_argument("--node", action="append", default=[], help="id=name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--file", default="work-time")
    a = ap.parse_args()
    open_file(a.file)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [tuple(n.split("=", 1)) for n in a.node]
    if a.within and a.prefix:
        for n in call("find_nodes", {"name": a.prefix, "withinId": a.within, "type": "FRAME", "limit": 500})["nodes"]:
            if n["name"].startswith(a.prefix):
                jobs.append((n["id"], n["name"][len(a.prefix):]))
    for node_id, name in jobs:
        s = slim(export_node(node_id))
        (out / f"{name}.svg").write_text(s, encoding="utf-8")
        print(f"{name}.svg  {len(s):,} bytes")
    if not jobs:
        print("nothing to export")


if __name__ == "__main__":
    main()
