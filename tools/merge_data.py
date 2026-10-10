#!/usr/bin/env python3
"""Merge outdoor GeoJSON + indoor floor file(s) + places list into ONE graph JSON for the API.

Usage (from the repo root; every argument is optional):
    python tools/merge_data.py
    python tools/merge_data.py --outdoor data/outdoor/outdoor_draft_v3.geojson \
        --indoor data/indoor/ground_floor.json --places data/places_v1.json \
        --out data/build/campus.merged.json

Defaults: newest data/outdoor/outdoor_draft_v*.geojson, data/indoor/ground_floor.json,
data/places_v1.json, output data/build/campus.merged.json.

Indoor file: nodes (id, type, name, x, y in pixels on the floor image), edges (from, to, meters),
links (indoor node <-> outdoor node id, meters). A place can have several entry nodes (the mess has two);
the router goes to whichever is nearer.
"""
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert_geojson import build_graph as build_outdoor  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def latest_outdoor(folder):
    files = [p for p in folder.glob("outdoor_draft_v*.geojson") if re.search(r"_v(\d+)", p.name)]
    return max(files, key=lambda p: int(re.search(r"_v(\d+)", p.name).group(1))) if files else None


def merge(outdoor_geo, indoor_files, places, outdoor_name="outdoor.geojson"):
    errors, warnings = [], []
    graph, errs, warns = build_outdoor(outdoor_geo, outdoor_name)
    warnings += warns
    if errs:
        return None, errs, warnings

    nodes = {n["id"]: dict(n, space="outdoor") for n in graph["nodes"]}
    edges = [dict(e, space="outdoor") for e in graph["edges"]]
    rooms = {r["id"]: dict(r, node_ids=[r["node_id"]]) for r in graph["rooms"]}
    floors, n_in, n_link = [], 0, 0

    for ind in indoor_files:
        fl = ind.get("floor", 0)
        if ind.get("status") == "draft":
            warnings.append(f"indoor floor {fl} is marked DRAFT (pixel positions are guesses until confirmed)")
        floors.append({"floor": fl, "image": ind["image"], "image_size": ind["image_size"]})
        local = {}
        for n in ind.get("nodes", []):
            nid = n.get("id")
            if not nid or nid in nodes:
                errors.append(f"indoor node id {nid!r} is missing or already used")
                continue
            if not all(isinstance(n.get(k), (int, float)) for k in ("x", "y")):
                errors.append(f"indoor node '{nid}' needs numeric x and y (pixels on the floor image)")
                continue
            node = {"id": nid, "lat": None, "lng": None, "floor": fl, "type": n.get("type", "door"),
                    "name": n.get("name", ""), "building": n.get("building", ""), "space": "indoor",
                    "x": n["x"], "y": n["y"], "plan": ind["image"]}
            nodes[nid] = local[nid] = node
        for ed in ind.get("edges", []):
            a, b, m, lab = ed.get("from"), ed.get("to"), ed.get("meters"), ed.get("label", "")
            tag = f"indoor edge {lab or a + ' - ' + str(b)}"
            if a not in local or b not in local:
                errors.append(f"{tag}: unknown node")
            elif m is None:
                (warnings if ed.get("optional") else errors).append(f"{tag} has no 'meters' yet")
            elif not isinstance(m, (int, float)) or m <= 0:
                errors.append(f"{tag}: 'meters' must be a positive number")
            else:
                if m > 120:
                    warnings.append(f"{tag} is {m} m: please re-check that measurement")
                n_in += 1
                edges.append({"id": f"i{n_in:03d}", "from": a, "to": b, "weight": round(float(m), 1),
                              "type": "indoor", "space": "indoor", "accessible": True, "label": lab,
                              "geometry": [[local[a]["x"], local[a]["y"]], [local[b]["x"], local[b]["y"]]]})
        for lk in ind.get("links", []):
            i, o, m, lab = lk.get("indoor"), lk.get("outdoor"), lk.get("meters"), lk.get("label", "")
            tag = f"link {lab or str(i) + ' - ' + str(o)}"
            if i not in local:
                errors.append(f"{tag}: unknown indoor node {i!r}")
            elif o not in nodes or nodes[o]["space"] != "outdoor":
                warnings.append(f"{tag}: outdoor node '{o}' is not on the outdoor map yet, so the indoor map is "
                                f"NOT joined here (add the dot in geojson.io)")
            elif m is None:
                (warnings if lk.get("optional") else errors).append(f"{tag} has no 'meters' yet")
            else:
                n_link += 1
                edges.append({"id": f"k{n_link:03d}", "from": o, "to": i, "weight": round(float(m), 1),
                              "type": "link", "space": "link", "accessible": True, "label": lab, "geometry": []})

    used = set()
    for p in places:
        pid, entry = p.get("id"), p.get("entry_nodes", [])
        missing = [x for x in entry if x not in nodes]
        if not pid or not p.get("name") or not entry:
            errors.append(f"place {pid!r} needs id, name and entry_nodes")
        elif missing:
            errors.append(f"place '{pid}': unknown entry node(s) {missing}")
        elif pid in rooms:
            errors.append(f"place id '{pid}' is already used")
        else:
            aliases = sorted({p["name"].lower(), *[a.strip().lower() for a in p.get("aliases", []) if a.strip()]})
            first = nodes[entry[0]]
            rooms[pid] = {"id": pid, "name": p["name"], "aliases": aliases, "type": "place",
                          "building": p.get("building", ""), "floor": p.get("floor", first["floor"]),
                          "node_id": entry[0], "node_ids": list(entry)}
            used.update(entry)
    for rid in [r for r, v in rooms.items() if v["type"] != "place" and v["node_id"] in used]:
        del rooms[rid]  # an outdoor door that is now one entrance of a place is not listed twice

    if errors:
        return None, errors, warnings

    root = "gate_main" if "gate_main" in nodes else next((i for i, n in nodes.items() if n["type"] == "gate"), None)
    adj = defaultdict(list)
    for e in edges:
        adj[e["from"]].append(e["to"])
        adj[e["to"]].append(e["from"])
    if root:
        seen, q = {root}, deque([root])
        while q:
            for nb in adj[q.popleft()]:
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        for nid, n in nodes.items():
            if nid not in seen and n["space"] == "indoor":
                warnings.append(f"indoor node '{nid}' cannot be reached from '{root}' (the indoor map is not joined yet)")

    body = {"nodes": sorted(nodes.values(), key=lambda n: (n["space"] != "outdoor", n["id"])),
            "edges": edges, "rooms": sorted(rooms.values(), key=lambda r: r["name"].lower()), "floors": floors}
    version = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:10]
    meta = dict(graph["meta"], outdoor_nodes=sum(n["space"] == "outdoor" for n in nodes.values()),
                indoor_nodes=sum(n["space"] == "indoor" for n in nodes.values()),
                node_count=len(nodes), edge_count=len(edges), room_count=len(rooms))
    return {"version": version, "meta": meta, **body}, [], warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdoor")
    ap.add_argument("--indoor", action="append")
    ap.add_argument("--places")
    ap.add_argument("--out", default=str(ROOT / "data" / "build" / "campus.merged.json"))
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    a = ap.parse_args()

    outdoor = Path(a.outdoor) if a.outdoor else latest_outdoor(ROOT / "data" / "outdoor")
    if not outdoor or not outdoor.exists():
        sys.exit("ERROR: no outdoor GeoJSON found (put outdoor_draft_vN.geojson in data/outdoor/)")
    indoor_paths = [Path(p) for p in a.indoor] if a.indoor else [p for p in [ROOT / "data/indoor/ground_floor.json"] if p.exists()]
    places_path = Path(a.places) if a.places else (ROOT / "data/places_v1.json")
    places = json.loads(places_path.read_text(encoding="utf-8")) if places_path.exists() else []

    print(f"outdoor: {outdoor.name}   indoor: {[p.name for p in indoor_paths]}   places: {len(places)}")
    graph, errors, warnings = merge(json.loads(outdoor.read_text(encoding="utf-8")),
                                    [json.loads(p.read_text(encoding="utf-8")) for p in indoor_paths], places, outdoor.name)
    for w in warnings:
        print("WARNING:", w)
    if errors:
        for e in errors:
            print("ERROR:", e)
        sys.exit(1)
    if a.strict and warnings:
        sys.exit(1)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=1 if a.pretty else None, separators=None if a.pretty else (",", ":")), encoding="utf-8")
    m = graph["meta"]
    print(f"OK: {m['outdoor_nodes']} outdoor + {m['indoor_nodes']} indoor nodes, {m['edge_count']} edges, "
          f"{m['room_count']} searchable places, version {graph['version']} -> {out}")


if __name__ == "__main__":
    main()
