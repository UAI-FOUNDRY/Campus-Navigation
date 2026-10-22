#!/usr/bin/env python3
"""Print QR codes for the start points students scan (one A4 PDF, 6 codes per page).

    python -m pip install "qrcode[pil]"
    python tools/generate_qr.py                    # lifts, stairs, exits, named junctions, gates, outdoor entrances
    python tools/generate_qr.py --ids a0_lobbya_e a1_lobbya_e gate_main
    python tools/generate_qr.py --floors           # only the stairs and lift landings (floor checkpoints)

Each code holds  campusnav:<node id>  (the app also accepts the bare id). Output: out/qr_codes.pdf (git-ignored).
Codes use node ids, so they keep working when names change. Re-print only when a node is deleted.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOORS = {0: "Ground floor", 1: "First floor", 2: "Second floor"}


def pick(nodes):
    out = []
    for n in nodes:
        if n.get("internal"):        # generated corridor dots: their ids change when a corridor is redrawn
            continue
        if n.get("space") == "outdoor" and n["type"] in ("gate", "entrance"):
            out.append(n)
        elif n.get("space") == "indoor" and (n["type"] in ("lift", "stairs", "exit", "gate")
                                            or (n["type"] in ("junction", "corner") and n.get("name"))):
            out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", default=str(ROOT / "data/build/campus.merged.json"))
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--floors", action="store_true",
                    help="only stairs and lift landings: one sticker per landing fixes the floor on any phone")
    ap.add_argument("--out", default=str(ROOT / "out/qr_codes.pdf"))
    a = ap.parse_args()
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    g = json.loads(Path(a.graph).read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in g["nodes"]}
    chosen = [nodes[i] for i in a.ids] if a.ids else pick(g["nodes"])
    if a.floors:
        chosen = [n for n in chosen if n.get("space") == "indoor" and n["type"] in ("lift", "stairs")]
    chosen.sort(key=lambda n: (n.get("space") != "outdoor", n.get("floor", 0), n["id"]))

    W, H = 1240, 1754                      # A4 at 150 dpi
    cell_w, cell_h = W // 2, H // 3
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
        small = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        font = small = ImageFont.load_default()
    pages, page = [], None
    for k, n in enumerate(chosen):
        if k % 6 == 0:
            page = Image.new("RGB", (W, H), "white")
            pages.append(page)
        d = ImageDraw.Draw(page)
        cx, cy = (k % 6) % 2 * cell_w, (k % 6) // 2 * cell_h
        img = qrcode.make(f"campusnav:{n['id']}", box_size=10, border=2).convert("RGB").resize((380, 380))
        page.paste(img, (cx + (cell_w - 380) // 2, cy + 40))
        title = n.get("name") or n["id"]
        where = "Outside" if n.get("space") == "outdoor" else FLOORS.get(n.get("floor", 0), f"Floor {n.get('floor')}")
        d.text((cx + 40, cy + 440), title[:38], fill="black", font=font)
        d.text((cx + 40, cy + 485), f"{where} · scan to start here · {n['id']}", fill=(90, 90, 90), font=small)
        d.rectangle([cx + 10, cy + 10, cx + cell_w - 10, cy + cell_h - 10], outline=(200, 200, 200))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
    print(f"wrote {out}: {len(chosen)} codes on {len(pages)} page(s)")


if __name__ == "__main__":
    main()
