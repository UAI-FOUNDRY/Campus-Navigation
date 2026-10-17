#!/usr/bin/env python3
"""Find drawing mistakes in the outdoor GeoJSON that make A* lose a path.

    python tools/check_map.py                      # newest data/outdoor/outdoor_draft_vN.geojson
    python tools/check_map.py data/outdoor/outdoor_draft_v5.geojson

What it reports
  BROKEN   a line END that stops near another line but not at a dot: the two paths are NOT joined.
           Fix: put a junction dot where they meet (both lines must pass within 6 m of it).
  CROSSING two lines cross with no dot at the crossing: walkers can't turn there.
           Fix: add a junction dot at the crossing (or ignore if it is a bridge/underpass).
  LOOSE    a line end that is far from everything (dead end that goes nowhere).
  SKIPPED  a line that touches fewer than 2 dots: the converter ignores it completely.
  ALONE    a dot that no line passes within 6 m of.
  DOUBLE   the same stretch drawn twice (two lines between the same two dots with similar length).
  CHECK    dots of different places closer than 4 m (often fine: two doors side by side).
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from convert_geojson import SNAP_M, Projector, build_graph, point_to_segment  # noqa: E402

NEAR_M = 12.0  # a line end this close to another line probably meant to join it


def newest(folder):
    files = list(folder.glob("outdoor_draft_v*.geojson"))
    return max(files, key=lambda p: int(re.search(r"_v(\d+)", p.name).group(1))) if files else None


def seg_cross(a, b, c, d):
    """Intersection point of segments a-b and c-d (strictly inside both), or None."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / den
    u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / den
    if 0.02 < t < 0.98 and 0.02 < u < 0.98:
        return (a[0] + t * r[0], a[1] + t * r[1])
    return None


def check(geo):
    out = []
    feats = geo.get("features", [])
    dots, lines = {}, []
    for i, f in enumerate(feats):
        g = f.get("geometry") or {}
        p = f.get("properties") or {}
        if g.get("type") == "Point" and p.get("id"):
            dots[p["id"]] = (g["coordinates"][1], g["coordinates"][0], p.get("type"), p.get("name", ""))
        elif g.get("type") == "LineString":
            lines.append((i, [(c[1], c[0]) for c in g["coordinates"]]))
    if not dots:
        return ["ERROR no dots"]
    proj = Projector(sum(d[0] for d in dots.values()) / len(dots))
    dxy = {k: proj.xy((v[0], v[1])) for k, v in dots.items()}
    lxy = [(i, [proj.xy(c) for c in cs]) for i, cs in lines]

    def nearest_dot(p):
        k = min(dxy, key=lambda k: math.dist(p, dxy[k]))
        return k, math.dist(p, dxy[k])

    def dots_on(pts):
        hit = []
        for k, p in dxy.items():
            d = min(point_to_segment(p, a, b)[0] for a, b in zip(pts, pts[1:])) if len(pts) > 1 else math.dist(p, pts[0])
            if d <= SNAP_M:
                hit.append(k)
        return hit

    # line ends
    for i, pts in lxy:
        if len(pts) < 2:
            out.append(f"SKIPPED  line #{i} has fewer than 2 points")
            continue
        if len(dots_on(pts)) < 2:
            out.append(f"SKIPPED  line #{i} touches fewer than 2 dots, so the converter ignores it")
        for end in (pts[0], pts[-1]):
            k, d = nearest_dot(end)
            if d <= SNAP_M:
                continue
            best = None
            for j, other in lxy:
                if j == i:
                    continue
                for a, b in zip(other, other[1:]):
                    dd = point_to_segment(end, a, b)[0]
                    if best is None or dd < best[0]:
                        best = (dd, j)
            lat, lng = lines[[x for x, _ in lines].index(i)][1][0 if end is pts[0] else -1]
            if best and best[0] <= NEAR_M:
                out.append(f"BROKEN   line #{i} ends {best[0]:.1f} m from line #{best[1]} but not at a dot "
                           f"(nearest dot '{k}' is {d:.1f} m away) at [{lng:.6f}, {lat:.6f}]: add a junction dot there")
            else:
                out.append(f"LOOSE    line #{i} ends at [{lng:.6f}, {lat:.6f}], {d:.1f} m from the nearest dot '{k}'")
    # crossings without a dot
    for x in range(len(lxy)):
        for y in range(x + 1, len(lxy)):
            i, p1 = lxy[x]
            j, p2 = lxy[y]
            for a, b in zip(p1, p1[1:]):
                for c, d in zip(p2, p2[1:]):
                    q = seg_cross(a, b, c, d)
                    if q and nearest_dot(q)[1] > SNAP_M:
                        out.append(f"CROSSING lines #{i} and #{j} cross with no dot near "
                                   f"(nearest dot '{nearest_dot(q)[0]}' {nearest_dot(q)[1]:.1f} m away)")
    # lonely dots
    on_any = set()
    for _, pts in lxy:
        if len(pts) > 1:
            on_any.update(dots_on(pts))
    for k in dots:
        if k not in on_any:
            out.append(f"ALONE    dot '{k}' is not within {SNAP_M:.0f} m of any line")
    # doubles via the converter's own split
    graph, errs, _ = build_graph(geo)
    if graph:
        seen = {}
        for e in graph["edges"]:
            key = tuple(sorted((e["from"], e["to"])))
            if key in seen and abs(seen[key] - e["weight"]) < max(3.0, 0.15 * e["weight"]):
                out.append(f"DOUBLE   '{key[0]}' - '{key[1]}' is drawn twice ({seen[key]} m and {e['weight']} m)")
            elif key in seen:
                out.append(f"CHECK    two different routes between '{key[0]}' and '{key[1]}' "
                           f"({seen[key]} m and {e['weight']} m): real, or one drawn twice?")
            seen.setdefault(key, e["weight"])
    # unnamed searchable dots, and very close doors
    for k, (_, _, t, name) in dots.items():
        if t in ("entrance", "room_door", "gate") and not name:
            out.append(f"NAME     '{k}' is a {t} with no name (students would see '{k}')")
    keys = list(dots)
    for x in range(len(keys)):
        for y in range(x + 1, len(keys)):
            d = math.dist(dxy[keys[x]], dxy[keys[y]])
            if d < 4 and dots[keys[x]][2] != "junction" and dots[keys[y]][2] != "junction":
                out.append(f"CHECK    '{keys[x]}' and '{keys[y]}' are only {d:.1f} m apart (two real doors?)")
    return out


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else newest(ROOT / "data" / "outdoor")
    if not path or not path.exists():
        sys.exit("no outdoor GeoJSON found")
    print(f"checking {path.name}")
    res = check(json.loads(path.read_text(encoding="utf-8")))
    order = ["BROKEN", "CROSSING", "SKIPPED", "ALONE", "NAME", "LOOSE", "DOUBLE", "CHECK"]
    res.sort(key=lambda s: order.index(s.split()[0]) if s.split()[0] in order else 99)
    print("\n".join(res) if res else "no problems found")
    bad = sum(r.split()[0] in ("BROKEN", "CROSSING", "SKIPPED", "ALONE") for r in res)
    print(f"\n{bad} problem(s) that can break routes, {len(res) - bad} note(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
