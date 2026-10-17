#!/usr/bin/env python3
"""Merge the outdoor GeoJSON + the indoor floor files + the places list into ONE graph JSON for the API.

Usage (from the repo root; every argument is optional):
    python tools/merge_data.py
    python tools/merge_data.py --outdoor data/outdoor/outdoor_draft_v6.geojson --places data/places.json

Defaults: newest data/outdoor/outdoor_draft_v*.geojson, every data/indoor/<code>.json floor file (gf, ff, sf, ...),
data/indoor/building.json (georef + lifts/stairs), data/places.json, output data/build/campus.merged.json.

Indoor floor file (see docs/data-format.md):
  nodes  {id, type, name, pos: [x, y] in plan metres}      (older files: x, y in pixels + edges with meters)
  edges  {from, to, [type], [meters]}   length = straight line between the two dots unless "meters" is given
  links  {indoor, outdoor, [meters]}    joins an indoor exit to an outdoor dot; distance from GPS if not given
building.json: georef control points (plan <-> outdoor dots), vertical connectors (lifts/stairs), costs.
A place can have several entry nodes (the mess has two); the router goes to whichever is nearer.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert_geojson import build_graph as build_outdoor, haversine  # noqa: E402
from corridors import expand  # noqa: E402
from planref import Display, Georef  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WALK_REF_MPS = 1.3          # turns extra seconds (lift wait) into "metres" for A*'s cost
ID_RE = re.compile(r"^[A-Za-z0-9_]+$")
WALK_TYPES = {"corridor", "open", "ramp", "steps", "restricted"}
DEFAULT_COSTS = {"stairs_m_per_floor": 12, "stairs_s_per_floor": 20, "lift_m": 4, "lift_wait_s": 60,
                 "lift_s_per_floor": 6}


def square_up(local, fedges, hand_placed, tol_m=0.3):
    """Make straight corridors look straight on the (not-to-scale) signage picture.

    The picture is a hand-drawn schematic, so a corridor that is perfectly straight on the plan comes out slightly
    slanted after the plan -> picture fit. Here every vertical corridor gets ONE picture x and every horizontal one
    ONE picture y; a stub junction slides along its corridor so the stub to its door is square too. Doors themselves
    never move (they mark the room on the picture). Returns the largest move in pixels (for a sanity warning)."""
    parent = {}

    def find(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        parent[find(a)] = find(b)

    target = {}                                   # (node, axis) -> picture coordinate wanted by a door stub
    for e in fedges:
        a, b = local.get(e.get("from")), local.get(e.get("to"))
        if not a or not b or "pos" not in a or "pos" not in b or e.get("via"):
            continue
        dx, dy = abs(a["pos"][0] - b["pos"][0]), abs(a["pos"][1] - b["pos"][1])
        if e.get("stub"):
            door, junc = (a, b) if not a.get("internal") else (b, a)
            if junc.get("internal"):
                if dy < tol_m:
                    target.setdefault((junc["id"], "y"), door["y"])
                elif dx < tol_m:
                    target.setdefault((junc["id"], "x"), door["x"])
        else:                                     # corridor pieces and straight extra lines (steps)
            if dx < tol_m:
                union((a["id"], "x"), (b["id"], "x"))
            elif dy < tol_m:
                union((a["id"], "y"), (b["id"], "y"))
    groups = defaultdict(list)
    for key in list(parent):
        groups[find(key)].append(key)
    moved = 0.0
    new = {}
    for members in groups.values():
        axis = members[0][1]
        fixed = [local[n][axis] for n, _ in members if n in hand_placed]
        value = fixed[0] if fixed else sum(local[n][axis] for n, _ in members) / len(members)
        for n, _ in members:
            new[(n, axis)] = value
    for (n, axis), v in target.items():
        if (n, axis) not in new and n not in hand_placed:   # free coordinate along the corridor: follow the door
            new[(n, axis)] = v
    for (n, axis), v in new.items():
        if n in hand_placed:
            continue
        moved = max(moved, abs(local[n][axis] - v))
        local[n][axis] = round(v, 1)
    return moved


def latest_outdoor(folder):
    files = [p for p in folder.glob("outdoor_draft_v*.geojson") if re.search(r"_v(\d+)", p.name)]
    return max(files, key=lambda p: int(re.search(r"_v(\d+)", p.name).group(1))) if files else None


def floor_files(folder):
    """data/indoor/*.json except building.json. When the new per-floor files (with a "code") exist, old files
    without one (e.g. ground_floor.json) are ignored, so a leftover copy cannot clash with gf.json."""
    files = [p for p in sorted(folder.glob("*.json")) if p.name != "building.json" and not p.name.startswith("_")]
    coded = [p for p in files if "code" in json.loads(p.read_text(encoding="utf-8"))]
    if coded and len(coded) < len(files):
        print("NOTE: ignoring old floor file(s) without a 'code':", [p.name for p in files if p not in coded],
              "(delete them)")
    return coded or files


def merge(outdoor_geo, indoor_files, places, outdoor_name="outdoor.geojson", building=None):
    errors, warnings = [], []
    graph, errs, warns = build_outdoor(outdoor_geo, outdoor_name)
    warnings += warns
    if errs:
        return None, errs, warnings

    nodes = {n["id"]: dict(n, space="outdoor") for n in graph["nodes"]}
    edges = [dict(e, space="outdoor", length=e["weight"]) for e in graph["edges"]]
    rooms = {r["id"]: dict(r, node_ids=[r["node_id"]]) for r in graph["rooms"]}
    building = building or {}
    costs = dict(DEFAULT_COSTS, **{k: v for k, v in building.get("costs", {}).items() if not k.startswith("_")})
    floors, n_in, n_link, n_vert = [], 0, 0, 0

    # ---- georef: plan metres -> GPS, from outdoor dots on the facade ----------------------------
    geo = None
    cps = building.get("georef", {}).get("control_points", [])
    pairs = [(tuple(c["pos"]), (nodes[c["outdoor"]]["lat"], nodes[c["outdoor"]]["lng"]))
             for c in cps if c.get("outdoor") in nodes]
    for c in cps:
        if c.get("outdoor") not in nodes:
            warnings.append(f"georef control point '{c.get('outdoor')}' is not on the outdoor map; skipped")
    if len(pairs) >= 2:
        geo = Georef(pairs)
        if geo.rms > 4:
            warnings.append(f"georef fits the outdoor map with {geo.rms:.1f} m average error: check the control points")
    elif cps:
        warnings.append("georef needs 2+ control points that exist on the outdoor map; indoor dots get no GPS position")

    # ---- floors ------------------------------------------------------------------------------
    for ind in sorted(indoor_files, key=lambda f: f.get("floor", 0)):
        fl = ind.get("floor", 0)
        code = ind.get("code", f"f{fl}")
        if ind.get("status") == "draft":
            warnings.append(f"indoor floor {code} is marked DRAFT")
        floors.append({"floor": fl, "code": code, "label": ind.get("label", f"Floor {fl}"),
                       "image": ind["image"], "image_size": ind["image_size"]})
        display = None
        if len(ind.get("display_anchors", [])) >= 3:
            try:
                display = Display([(tuple(a), tuple(b)) for a, b in ind["display_anchors"]])
            except ValueError as ex:
                errors.append(f"floor {code}: display_anchors: {ex}")
        local = {}
        fnodes, fedges, cerrs = expand(ind)
        errors += [f"floor {code}: {e}" for e in cerrs]
        for n in fnodes:
            nid = n.get("id")
            if not nid or not ID_RE.match(nid) or nid in nodes:
                errors.append(f"indoor node id {nid!r} is missing, has bad characters, or is already used")
                continue
            pos = n.get("pos")
            node = {"id": nid, "lat": None, "lng": None, "floor": fl, "type": n.get("type", "door"),
                    "name": n.get("name", ""), "building": n.get("building", ""), "space": "indoor", "plan": ind["image"]}
            if pos is not None:
                if not (isinstance(pos, list) and len(pos) == 2 and all(isinstance(v, (int, float)) for v in pos)):
                    errors.append(f"indoor node '{nid}': pos must be [x, y] in plan metres")
                    continue
                node["pos"] = [float(pos[0]), float(pos[1])]
                if geo:
                    node["lat"], node["lng"] = geo.to_latlng(*pos)
                if isinstance(n.get("x"), (int, float)) and isinstance(n.get("y"), (int, float)):
                    node["x"], node["y"] = n["x"], n["y"]               # hand-placed on the picture
                elif display:
                    node["x"], node["y"] = display.to_px(*pos)
                else:
                    errors.append(f"indoor node '{nid}': floor {code} needs display_anchors (or give x, y)")
                    continue
            elif all(isinstance(n.get(k), (int, float)) for k in ("x", "y")):
                node["x"], node["y"] = n["x"], n["y"]                   # older files: pixels only
            else:
                errors.append(f"indoor node '{nid}' needs pos (plan metres) or x and y (pixels)")
                continue
            for k in ("verify", "internal", "area", "note", "media"):
                if n.get(k):
                    node[k] = n[k]
            nodes[nid] = local[nid] = node
        hand = {i for i, n in ((n.get("id"), n) for n in fnodes) if isinstance(n.get("x"), (int, float))}
        moved = square_up(local, fedges, hand)
        if moved > 80:
            warnings.append(f"floor {code}: squaring corridors on the picture moved a dot {moved:.0f} px: check "
                            "display_anchors (or give that dot x, y)")
        if sum(1 for n in local.values() if n.get("verify")):
            warnings.append(f"floor {code}: {sum(1 for n in local.values() if n.get('verify'))} dot(s) marked 'verify' "
                            "(placed from the plan; check on site)")

        for ed in fedges:
            a, b, lab = ed.get("from"), ed.get("to"), ed.get("label", "")
            tag = f"floor {code} edge {lab or str(a) + ' - ' + str(b)}"
            if a not in local or b not in local:
                errors.append(f"{tag}: unknown node")
                continue
            etype = ed.get("type", "corridor")
            if etype not in WALK_TYPES:
                errors.append(f"{tag}: unknown type {etype!r} (allowed: {sorted(WALK_TYPES)})")
                continue
            m = ed.get("meters")
            via = ed.get("via") or []
            if via and not all(isinstance(v, list) and len(v) == 2 for v in via):
                errors.append(f"{tag}: via must be a list of [x, y] plan metres")
                continue
            plan_len = None
            if "pos" in local[a] and "pos" in local[b]:
                chain = [local[a]["pos"], *via, local[b]["pos"]]
                plan_len = sum(math.dist(p, q) for p, q in zip(chain, chain[1:]))
            if m is None and plan_len is None:
                (warnings if ed.get("optional") else errors).append(f"{tag} has no 'meters' yet")
                continue
            if m is not None and (not isinstance(m, (int, float)) or m <= 0):
                errors.append(f"{tag}: 'meters' must be a positive number")
                continue
            length = float(m) if m is not None else plan_len
            if m is not None and plan_len and not ed.get("climb") and abs(m - plan_len) > max(3.0, 0.3 * plan_len):
                warnings.append(f"{tag}: measured {m} m but the plan says {plan_len:.1f} m: re-check one of them")
            if length > 120:
                warnings.append(f"{tag} is {length:.0f} m: please re-check")
            n_in += 1
            px_via = [list(display.to_px(*v)) for v in via] if (via and display) else []
            edge = {"id": f"i{n_in:03d}", "from": a, "to": b, "weight": round(max(length, 0.1), 1),
                    "length": round(length, 1), "type": etype, "space": "indoor", "floor": fl,
                    "accessible": etype not in ("steps", "restricted"), "label": lab,
                    "source": "measured" if m is not None else "plan",
                    "geometry": [[local[a]["x"], local[a]["y"]], *px_via, [local[b]["x"], local[b]["y"]]]}
            if via:
                edge["via"] = [[float(v[0]), float(v[1])] for v in via]
                if geo:
                    edge["via_geo"] = [list(geo.to_latlng(*v)) for v in via]
            if ed.get("climb") in ("up", "down"):   # stairs inside a floor: announced as their own step
                edge["climb"] = ed["climb"]
            for k in ("corridor", "area"):
                if ed.get(k):
                    edge[k] = ed[k]
            edges.append(edge)

        for lk in ind.get("links", []):
            i, o, m, lab = lk.get("indoor"), lk.get("outdoor"), lk.get("meters"), lk.get("label", "")
            tag = f"link {lab or str(i) + ' - ' + str(o)}"
            if i not in local:
                errors.append(f"{tag}: unknown indoor node {i!r}")
                continue
            if o not in nodes or nodes[o]["space"] != "outdoor":
                warnings.append(f"{tag}: outdoor node '{o}' is not on the outdoor map yet, so the indoor map is "
                                f"NOT joined here (add the dot in geojson.io)")
                continue
            if m is None and local[i]["lat"] is not None:
                m = haversine((local[i]["lat"], local[i]["lng"]), (nodes[o]["lat"], nodes[o]["lng"]))
                if m > 25:
                    warnings.append(f"{tag}: the outdoor dot is {m:.0f} m from the door on the plan: move the dot "
                                    "in geojson.io, or give the link 'meters'")
            if m is None:
                (warnings if lk.get("optional") else errors).append(f"{tag} has no 'meters' yet")
                continue
            n_link += 1
            edges.append({"id": f"k{n_link:03d}", "from": o, "to": i, "weight": round(max(float(m), 0.0), 1),
                          "length": round(float(m), 1), "type": "link", "space": "link", "floor": fl,
                          "accessible": True, "label": lab, "geometry": []})

    # ---- lifts and staircases between floors -----------------------------------------------------
    for v in building.get("vertical", []):
        vid, vtype, ids = v.get("id"), v.get("type"), v.get("nodes", [])
        if v.get("closed"):
            warnings.append(f"vertical '{vid}' is marked closed: routes will not use it")
            continue
        if vtype not in ("lift", "stairs"):
            errors.append(f"vertical '{vid}': type must be 'lift' or 'stairs'")
            continue
        missing = [x for x in ids if x not in nodes]
        if missing:
            errors.append(f"vertical '{vid}': unknown node(s) {missing}")
            continue
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = nodes[ids[x]], nodes[ids[y]]
                floors_moved = abs(b["floor"] - a["floor"])
                if floors_moved == 0:
                    errors.append(f"vertical '{vid}': {ids[x]} and {ids[y]} are on the same floor")
                    continue
                if vtype == "stairs":
                    length = costs["stairs_m_per_floor"] * floors_moved
                    extra = costs["stairs_s_per_floor"] * floors_moved
                else:
                    length = costs["lift_m"]
                    extra = costs["lift_wait_s"] + costs["lift_s_per_floor"] * floors_moved
                n_vert += 1
                edges.append({"id": f"v{n_vert:03d}", "from": ids[x], "to": ids[y],
                              "weight": round(length + extra * WALK_REF_MPS, 1), "length": float(length),
                              "extra_s": float(extra), "type": vtype, "space": "vertical", "connector": vid,
                              "connector_name": v.get("name", vid), "accessible": vtype == "lift", "geometry": []})

    # ---- places --------------------------------------------------------------------------------
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
        elif any(nodes[x].get("internal") for x in entry):
            errors.append(f"place '{pid}': entry nodes must be real doors, not generated corridor dots")
        elif p.get("within") and p["within"] not in {q.get("id") for q in places}:
            errors.append(f"place '{pid}': within {p['within']!r} is not a place id")
        else:
            aliases = sorted({p["name"].lower(), *[a.strip().lower() for a in p.get("aliases", []) if a.strip()]})
            first = nodes[entry[0]]
            room = {"id": pid, "name": p["name"], "aliases": aliases, "type": "place",
                    "building": p.get("building", ""), "floor": p.get("floor", first["floor"]),
                    "node_id": entry[0], "node_ids": list(entry)}
            for k in ("category", "within", "note"):
                if p.get(k):
                    room[k] = p[k]
            rooms[pid] = room
            used.update(entry)
    for rid in [r for r, v in rooms.items() if v["type"] != "place" and v["node_id"] in used]:
        del rooms[rid]  # an outdoor door that is now one entrance of a place is not listed twice
    for r in rooms.values():   # "inside the Library": keep the parent's display name next to the id
        if r.get("within") in rooms:
            r["within_name"] = rooms[r["within"]]["name"]

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

    body = {"nodes": sorted(nodes.values(), key=lambda n: (n["space"] != "outdoor", n.get("floor", 0), n["id"])),
            "edges": edges, "rooms": sorted(rooms.values(), key=lambda r: r["name"].lower()),
            "floors": sorted(floors, key=lambda f: f["floor"])}
    version = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:10]
    meta = dict(graph["meta"], outdoor_nodes=sum(n["space"] == "outdoor" for n in nodes.values()),
                indoor_nodes=sum(n["space"] == "indoor" for n in nodes.values()),
                node_count=len(nodes), edge_count=len(edges), room_count=len(rooms),
                floors=[f["code"] for f in sorted(floors, key=lambda f: f["floor"])])
    if geo:
        meta["georef_rms_m"] = round(geo.rms, 2)
    return {"version": version, "meta": meta, **body}, [], warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdoor")
    ap.add_argument("--indoor", action="append", help="floor file (repeat for several); default: all of data/indoor/")
    ap.add_argument("--building", default=str(ROOT / "data" / "indoor" / "building.json"))
    ap.add_argument("--places")
    ap.add_argument("--out", default=str(ROOT / "data" / "build" / "campus.merged.json"))
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    a = ap.parse_args()

    outdoor = Path(a.outdoor) if a.outdoor else latest_outdoor(ROOT / "data" / "outdoor")
    if not outdoor or not outdoor.exists():
        sys.exit("ERROR: no outdoor GeoJSON found (put outdoor_draft_vN.geojson in data/outdoor/)")
    indoor_paths = [Path(p) for p in a.indoor] if a.indoor else floor_files(ROOT / "data" / "indoor")
    building_path = Path(a.building)
    building = json.loads(building_path.read_text(encoding="utf-8")) if building_path.exists() else {}
    places_path = Path(a.places) if a.places else next(
        (p for p in (ROOT / "data/places.json", ROOT / "data/places_v1.json") if p.exists()), ROOT / "data/places.json")
    places = json.loads(places_path.read_text(encoding="utf-8")) if places_path.exists() else []

    print(f"outdoor: {outdoor.name}   indoor: {[p.name for p in indoor_paths]}   places: {len(places)}")
    graph, errors, warnings = merge(json.loads(outdoor.read_text(encoding="utf-8")),
                                    [json.loads(p.read_text(encoding="utf-8")) for p in indoor_paths], places,
                                    outdoor.name, building)
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
    out.write_text(json.dumps(graph, indent=1 if a.pretty else None, separators=None if a.pretty else (",", ":")),
                   encoding="utf-8")
    m = graph["meta"]
    print(f"OK: {m['outdoor_nodes']} outdoor + {m['indoor_nodes']} indoor nodes on floors {m['floors']}, "
          f"{m['edge_count']} edges, {m['room_count']} searchable places"
          + (f", georef error {m['georef_rms_m']} m" if "georef_rms_m" in m else "")
          + f", version {graph['version']} -> {out}")


if __name__ == "__main__":
    main()
