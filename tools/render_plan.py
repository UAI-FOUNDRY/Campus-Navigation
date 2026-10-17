#!/usr/bin/env python3
"""Turn an architect's floor-plan PDF into the picture the node editor needs (PRIVATE: never commit it).

    python tools/render_plan.py gf          # reads source_plan from data/indoor/gf.json
    python tools/render_plan.py ff --pdf "private/plans/UAi_LEARNING_CENTER_-_FF_AREA_2026.pdf"

Writes private/plans/<floor>.png at 25.2 pixels per metre (4x the PDF, whose scale is 6.30 points per metre),
which is the editor's default "plan scale". Needs:  python -m pip install pymupdf
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZOOM = 4  # 6.30 pt/m * 4 = 25.2 px/m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("floor")
    ap.add_argument("--pdf")
    a = ap.parse_args()
    import pymupdf

    pdf = Path(a.pdf) if a.pdf else ROOT / "private/plans" / json.loads(
        (ROOT / "data/indoor" / f"{a.floor}.json").read_text(encoding="utf-8"))["source_plan"]
    if not pdf.exists():
        raise SystemExit(f"{pdf} not found: put the architect's PDFs in private/plans/ (that folder is git-ignored)")
    page = pymupdf.open(pdf)[0]
    out = ROOT / "private/plans" / f"{a.floor}.png"
    page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM)).save(out)
    print(f"wrote {out}  (plan scale {6.30 * ZOOM:.1f} pixels per metre)")


if __name__ == "__main__":
    main()
