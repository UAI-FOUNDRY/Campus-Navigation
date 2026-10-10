#!/usr/bin/env python3
"""Check the built graph before using it.   python tools/validate_graph.py [data/build/campus.merged.json]

Errors (exit code 1): broken references, duplicate ids, outdoor edges shorter than the straight line.
Warnings: unnamed places, isolated or unreachable nodes, suspicious parallel routes, and a safe-A* check.
"""
import json
import math
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def haversine(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def validate(g):
    errors, warnings = [], []
    nodes = {n["id"]: n for n in g["nodes"]}
    if len(nodes) != len(g["nodes"]):
        errors.append("duplicate node ids: " + ", ".join(k for k, v in Counter(n["id"] for n in g["nodes"]).items() if v > 1))
    adj, pairs = defaultdict(list), defaultdict(list)
    for e in g["edges"]:
        if e["from"] not in nodes or e["to"] not in nodes:
            errors.append(f"edge {e['id']} refers to a missing node")
            continue
        a, b = nodes[e["from"]], nodes[e["to"]]
        if a.get("lat") is not None and b.get("lat") is not None:
            straight = haversine(a, b)
            if e["weight"] + 0.5 < straight:
                errors.append(f"edge {e['id']} ({e['from']} - {e['to']}) is {e['weight']} m but the straight line is "
                              f"{straight:.1f} m (A* needs weight >= straight line)")
        adj[e["from"]].append(e["to"])
        adj[e["to"]].append(e["from"])
        pairs[tuple(sorted((e["from"], e["to"])))].append(e["weight"])
    for r in g["rooms"]:
        for nid in r.get("node_ids", [r["node_id"]]):
            if nid not in nodes:
                errors.append(f"place '{r['id']}' points at missing node '{nid}'")
    for n in g["nodes"]:
        if n["type"] in ("entrance", "room_door") and not n.get("name"):
            warnings.append(f"'{n['id']}' has no name")
        if not adj[n["id"]]:
            warnings.append(f"'{n['id']}' is not connected to anything")
    root = "gate_main" if "gate_main" in nodes else next((i for i, n in nodes.items() if n["type"] == "gate"), None)
    if root:
        seen, q = {root}, deque([root])
        while q:
            for nb in adj[q.popleft()]:
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        for nid in nodes:
            if nid not in seen:
                warnings.append(f"'{nid}' cannot be reached from '{root}'")
    for (a, b), ws in pairs.items():
        if len(ws) > 1 and max(ws) - min(ws) > 5:
            warnings.append(f"two different routes between '{a}' and '{b}' ({', '.join(str(w) for w in sorted(ws))} m): "
                            "real parallel paths, or one path drawn twice?")
    try:  # how much the outdoor map and indoor measurements disagree (1.0 = perfect)
        sys.path.insert(0, str(ROOT / "backend"))
        from app.core.graph import CampusGraph
        scale = CampusGraph(g).scale
        if scale < 0.9:
            warnings.append(f"A* safety factor is {scale:.2f}: some indoor shortcut is much shorter than the straight-line "
                            "distance on the outdoor map. Re-check the link distances and the outdoor dots.")
    except Exception:  # the validator still works without the backend installed
        pass
    return errors, warnings


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data/build/campus.merged.json")
    graph = json.loads(path.read_text(encoding="utf-8"))
    errs, warns = validate(graph)
    for w in warns:
        print("WARNING:", w)
    for e in errs:
        print("ERROR:", e)
    print(f"{len(graph['nodes'])} nodes, {len(graph['edges'])} edges: {len(errs)} errors, {len(warns)} warnings")
    sys.exit(1 if errs else 0)
