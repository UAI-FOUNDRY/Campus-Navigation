#!/usr/bin/env python3
"""Draw a floor's dots and lines on a picture, to check them by eye.

    # on the architect's plan (PRIVATE: needs the PDF in private/plans/, output stays in private/)
    python tools/render_graph.py gf --plan private/plans/UAi_LEARNING_CENTER_-_GF_2026.pdf
    # on the public signage picture the app shows (uses the computed x, y)
    python tools/render_graph.py gf --signage

Needs:  python -m pip install pymupdf pillow   (only for this tool; the backend does not need them)
Output: private/check_<floor>_plan.png or private/check_<floor>_signage.png (private/ is git-ignored).
Red = 'verify' dots, blue = doors, grey = corridor points, purple = lifts/stairs, pink = exits; dashed = steps.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PT_PER_M = 6.30
COL = {"door": (36, 87, 230), "gate": (14, 159, 142), "exit": (224, 69, 123), "lift": (122, 63, 209),
       "stairs": (122, 63, 209), "junction": (91, 100, 120), "corner": (150, 160, 175)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("floor", help="floor code, e.g. gf, ff, sf")
    ap.add_argument("--plan", help="architect's PDF for this floor (kept in private/plans/)")
    ap.add_argument("--signage", action="store_true", help="draw on the app's signage picture instead")
    ap.add_argument("--graph", default=str(ROOT / "data/build/campus.merged.json"))
    ap.add_argument("--zoom", type=float, default=4.0)
    a = ap.parse_args()
    from PIL import Image, ImageDraw

    floor_file = json.loads((ROOT / "data/indoor" / f"{a.floor}.json").read_text(encoding="utf-8"))
    fl = floor_file["floor"]
    g = json.loads(Path(a.graph).read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"] if n.get("space") == "indoor" and n.get("floor") == fl}
    edges = [e for e in g["edges"] if e["from"] in nodes and e["to"] in nodes]

    if a.signage:
        im = Image.open(ROOT / "app/assets/floorplans" / floor_file["image"]).convert("RGB")
        to_px = lambda n: (n["x"], n["y"])  # noqa: E731
        r, out = 6, ROOT / "private" / f"check_{a.floor}_signage.png"
    else:
        if not a.plan:
            ap.error("give --plan <pdf> or --signage")
        import pymupdf
        page = pymupdf.open(a.plan)[0]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(a.zoom, a.zoom))
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        im = Image.blend(im, Image.new("RGB", im.size, "white"), 0.35)
        k = PT_PER_M * a.zoom
        to_px = lambda n: (n["pos"][0] * k, n["pos"][1] * k)  # noqa: E731
        r, out = 2.2 * a.zoom, ROOT / "private" / f"check_{a.floor}_plan.png"

    d = ImageDraw.Draw(im)
    for e in edges:
        if a.signage:
            pts = [tuple(v) for v in e["geometry"]]
        else:
            pts = [to_px(nodes[e["from"]]), *[to_px({"pos": v}) for v in e.get("via", [])], to_px(nodes[e["to"]])]
        col = (255, 120, 0) if e.get("type") == "steps" else (0, 150, 255)
        d.line(pts, fill=col, width=max(2, int(r * 0.6)), joint="curve")
        if e["length"] >= 4:
            mx, my = (pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2
            d.text((mx + 3, my + 3), f"{e['length']:.0f}m", fill=(0, 0, 0))
    for n in nodes.values():
        x, y = to_px(n)
        if n.get("internal"):
            d.ellipse([x - r / 3, y - r / 3, x + r / 3, y + r / 3], fill=(120, 130, 145))
            continue
        c = (220, 0, 0) if n.get("verify") else COL.get(n["type"], (0, 0, 0))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline="white")
        d.text((x + r + 2, y - r), n["id"].split("_", 1)[1] + (f" · {n['name']}" if n["name"] else ""), fill=(0, 0, 0))
    out.parent.mkdir(exist_ok=True)
    im.save(out)
    print(f"wrote {out} ({im.width}x{im.height})")


if __name__ == "__main__":
    main()
