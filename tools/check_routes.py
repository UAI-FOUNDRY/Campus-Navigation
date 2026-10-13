#!/usr/bin/env python3
"""Print route lengths for the v1 places, so you can sanity-check the map without running the API.

    python tools/check_routes.py [data/build/campus.merged.json]
Run  python tools/merge_data.py  first.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.astar import astar  # noqa: E402
from app.core.graph import CampusGraph  # noqa: E402

path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "build" / "campus.merged.json"
g = CampusGraph.load(path)
PLACES = ["admin_lobby", "mess", "mount_everest_130", "mount_lhotse"]
SPEED = 1.3  # metres per second


def run(a, b):
    r = astar(g, g.resolve(a), g.resolve(b))
    if r is None:
        return None, "NO ROUTE"
    via = [g.nodes[n]["name"] for n in r.nodes if g.nodes[n]["name"]]
    via = [v for i, v in enumerate(via) if i == 0 or v != via[i - 1]]
    short = via if len(via) <= 5 else via[:2] + ["..."] + via[-2:]
    south = " [uses the south entrance]" if "a0_quad_south_exit" in r.nodes and a == "gate_main" else ""
    return r.distance, " > ".join(short) + south


print(f"graph version {g.version}: {sum(n['space'] == 'outdoor' for n in g.nodes.values())} outdoor + "
      f"{sum(n['space'] == 'indoor' for n in g.nodes.values())} indoor nodes\n")
if "quad_south_entrance" not in g.nodes:
    print("NOTE: the outdoor dot 'quad_south_entrance' is not on the map yet, so the south entrance is NOT joined.\n")

print("FROM THE MAIN GATE")
for p in PLACES:
    d, via = run("gate_main", p)
    print(f"  to {g.rooms[p]['name']:20s} " + (f"{d:6.1f} m  {d / SPEED / 60:4.1f} min  via {via}" if d is not None else via))
print("\nBETWEEN THE PLACES")
for i, a in enumerate(PLACES):
    for b in PLACES[i + 1:]:
        d, via = run(a, b)
        print(f"  {g.rooms[a]['name']:16s} to {g.rooms[b]['name']:18s} " + (f"{d:6.1f} m  via {via}" if d is not None else via))
