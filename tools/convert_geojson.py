#!/usr/bin/env python3
"""Convert the outdoor GeoJSON (drawn in geojson.io) into the campus graph JSON.

Usage (from the repo root):
    python tools/convert_geojson.py data/outdoor/outdoor_draft_v2.geojson data/build/campus.merged.json

How it works
- every Point  -> a graph node (gate, junction, entrance, room_door)
- every LineString is split at each dot that lies within SNAP_M metres of it,
  so one long line through five dots becomes four edges
- an edge's weight is the real walking distance in metres along the drawn line
- each edge keeps the drawn bends (geometry) so the app can draw the route along the paths
- entrances / room doors / gates become searchable "rooms"
"""
import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

EARTH_R = 6371000.0
SNAP_M = 6.0  # a dot within this distance of a line counts as being on it
POINT_TYPES = {"gate", "junction", "entrance", "room_door"}
LINE_TYPES = {"path", "steps", "ramp", "restricted"}
SEARCHABLE = {"gate", "entrance", "room_door"}


def haversine(a, b):
    """Distance in metres between two (lat, lng) pairs."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


class Projector:
    """Flat local metres around the campus (accurate to centimetres at this size)."""

    def __init__(self, lat0):
        self.k = math.cos(math.radians(lat0))

    def xy(self, p):
        return (math.radians(p[1]) * EARTH_R * self.k, math.radians(p[0]) * EARTH_R)


def point_to_segment(p, a, b):
    """Return (distance, t) from point p to segment a-b, all in metres; t is 0..1 along the segment."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)), t


def title_from_id(node_id):
    base = re.sub(r"_(entrance|door)\d*$", "", node_id)
    return re.sub(r"[_\s]+", " ", base).strip().title()


def build_graph(geo, source_name="outdoor.geojson"):
    errors, warnings = [], []
    nodes, lines = {}, []

    # ---- 1. read features -------------------------------------------------
    for i, feat in enumerate(geo.get("features", [])):
        geom = feat.get("geometry")
        props = feat.get("properties") or {}
        if not geom:
            warnings.append(f"feature #{i} has no geometry and was skipped (delete it in geojson.io)")
            continue
        if geom["type"] == "Point":
            nid, ntype = props.get("id"), props.get("type")
            if not nid:
                errors.append(f"point #{i} has no 'id'")
                continue
            if ntype not in POINT_TYPES:
                errors.append(f"point '{nid}' has unknown type {ntype!r} (allowed: {sorted(POINT_TYPES)})")
                continue
            if nid in nodes:
                errors.append(f"duplicate id '{nid}' (point #{i})")
                continue
            lng, lat = geom["coordinates"][:2]
            nodes[nid] = {"id": nid, "lat": round(lat, 7), "lng": round(lng, 7), "floor": 0,
                          "type": ntype, "name": (props.get("name") or "").strip(),
                          "building": props.get("building", ""), "aliases": props.get("aliases", "")}
        elif geom["type"] == "LineString":
            coords = [(c[1], c[0]) for c in geom["coordinates"]]  # -> (lat, lng)
            ltype = props.get("type") if props.get("type") in LINE_TYPES else "path"
            lines.append((i, ltype, coords))
        else:
            warnings.append(f"feature #{i} is a {geom['type']} and was ignored")

    if errors or not nodes:
        return None, errors or ["no points found"], warnings

    proj = Projector(sum(n["lat"] for n in nodes.values()) / len(nodes))
    node_xy = {nid: proj.xy((n["lat"], n["lng"])) for nid, n in nodes.items()}

    # ---- 2. split lines at the dots they pass through ---------------------
    edges = []
    for li, ltype, coords in lines:
        pts = [proj.xy(c) for c in coords]
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        hits = []
        for nid, p in node_xy.items():
            best = None
            for k in range(len(pts) - 1):
                d, t = point_to_segment(p, pts[k], pts[k + 1])
                pos = cum[k] + t * (cum[k + 1] - cum[k])
                if best is None or d < best[0]:
                    best = (d, pos)
            if best[0] <= SNAP_M:
                hits.append((best[1], nid))
        hits.sort()
        if len(hits) < 2:
            near = hits[0][1] if hits else "no dot"
            warnings.append(f"line #{li} touches fewer than 2 dots (only {near}) and was skipped: "
                            "extend it to a dot, or delete it")
            continue
        for (pa, a), (pb, b) in zip(hits, hits[1:]):
            if a == b:
                continue
            na, nb = nodes[a], nodes[b]
            straight = haversine((na["lat"], na["lng"]), (nb["lat"], nb["lng"]))
            weight = max(pb - pa, straight, 0.1)  # never shorter than the straight line (keeps A* correct)
            geometry = [[na["lat"], na["lng"]]]
            for k, c in enumerate(coords):
                if pa < cum[k] < pb:
                    geometry.append([round(c[0], 7), round(c[1], 7)])
            geometry.append([nb["lat"], nb["lng"]])
            edges.append({"from": a, "to": b, "weight": round(weight, 1), "type": ltype,
                          "accessible": ltype not in ("steps", "restricted"), "geometry": geometry})

    edges.sort(key=lambda e: (e["from"], e["to"], e["weight"]))
    for n, e in enumerate(edges, 1):
        e["id"] = f"e{n:03d}"

    # ---- 3. rooms (searchable places) --------------------------------------
    rooms = []
    for nid, n in nodes.items():
        if n["type"] not in SEARCHABLE:
            continue
        name = n["name"] or title_from_id(nid)
        if not n["name"]:
            warnings.append(f"'{nid}' has no name; using '{name}'. Add a 'name' in geojson.io")
        aliases = {name.lower(), title_from_id(nid).lower()}
        aliases |= {a.strip().lower() for a in str(n["aliases"]).split(",") if a.strip()}
        aliases = sorted(a for a in aliases if a)
        rooms.append({"id": nid, "name": name, "aliases": aliases, "type": n["type"],
                      "building": n["building"], "floor": 0, "node_id": nid})
    rooms.sort(key=lambda r: r["name"].lower())

    # ---- 4. sanity warnings -------------------------------------------------
    degree = defaultdict(int)
    for e in edges:
        degree[e["from"]] += 1
        degree[e["to"]] += 1
    for nid in nodes:
        if degree[nid] == 0:
            warnings.append(f"'{nid}' is not on any path (add a line to it)")
    root = "gate_main" if "gate_main" in nodes else next((i for i, n in nodes.items() if n["type"] == "gate"), None)
    if root:
        adj = defaultdict(list)
        for e in edges:
            adj[e["from"]].append(e["to"])
            adj[e["to"]].append(e["from"])
        seen, queue = {root}, deque([root])
        while queue:
            for nb in adj[queue.popleft()]:
                if nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        for nid in nodes:
            if nid not in seen:
                warnings.append(f"'{nid}' cannot be reached from '{root}'")
    else:
        warnings.append("no gate point found (type 'gate')")

    # ---- 5. package ----------------------------------------------------------
    node_list = [{k: v for k, v in n.items() if k not in ("aliases",)} for n in nodes.values()]
    node_list.sort(key=lambda n: n["id"])
    body = {"nodes": node_list, "edges": edges, "rooms": rooms}
    version = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:10]
    graph = {"version": version,
             "meta": {"source": source_name, "snap_m": SNAP_M, "node_count": len(node_list),
                      "edge_count": len(edges), "room_count": len(rooms)},
             **body}
    return graph, [], warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("geojson", help="input .geojson from geojson.io")
    ap.add_argument("output", help="output graph .json")
    ap.add_argument("--pretty", action="store_true", help="indent the JSON for reading")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    geo = json.loads(Path(args.geojson).read_text(encoding="utf-8"))
    graph, errors, warnings = build_graph(geo, Path(args.geojson).name)
    for w in warnings:
        print("WARNING:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        sys.exit(1)
    if args.strict and warnings:
        sys.exit(1)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=1 if args.pretty else None,
                              separators=None if args.pretty else (",", ":")), encoding="utf-8")
    m = graph["meta"]
    print(f"OK: {m['node_count']} nodes, {m['edge_count']} edges, {m['room_count']} searchable places, "
          f"version {graph['version']} -> {out}")


if __name__ == "__main__":
    main()
