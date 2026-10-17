#!/usr/bin/env python3
"""Print route lengths, so you can sanity-check the map without running the API.

    python tools/check_routes.py            # main gate -> the version-1 places, and between them
    python tools/check_routes.py --all      # main gate -> every searchable place (finds unreachable ones)
    python tools/check_routes.py --step-free --all
Run  python tools/merge_data.py  first.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.astar import astar  # noqa: E402
from app.core.graph import CampusGraph  # noqa: E402
from app.core.instructions import build_route  # noqa: E402

V1 = ["admin_lobby", "mess", "mount_everest_130", "mount_lhotse"]
SPEED = 1.3  # metres per second


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("graph", nargs="?", default=str(ROOT / "data" / "build" / "campus.merged.json"))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--step-free", action="store_true")
    a = ap.parse_args()
    g = CampusGraph.load(a.graph)

    def run(x, y):
        r = astar(g, g.resolve(x), g.resolve(y), a.step_free)
        if r is None:
            return "NO ROUTE"
        out = build_route(g, r, SPEED, g.node_place.get(r.goal))
        via = [k for k in ("stairs", "lift") if any(s["kind"] == k for s in out["steps"])]
        floors = "/".join(str(f) for f in out["floors"]) or "-"
        return (f"{out['distance_m']:6.1f} m  {out['duration_s'] / 60:4.1f} min  floors {floors:5s}"
                + (f"  by {' + '.join(via)}" if via else ""))

    print(f"graph version {g.version}: {sum(n['space'] == 'outdoor' for n in g.nodes.values())} outdoor + "
          f"{sum(n['space'] == 'indoor' for n in g.nodes.values())} indoor nodes"
          + ("   (step-free)" if a.step_free else "") + "\n")
    targets = sorted(g.rooms, key=lambda r: (g.rooms[r]["floor"], g.rooms[r]["name"])) if a.all else V1
    print("FROM THE MAIN GATE")
    bad = 0
    for p in targets:
        res = run("gate_main", p)
        bad += res == "NO ROUTE"
        print(f"  {g.rooms[p]['name'][:34]:34s} {res}")
    if not a.all:
        print("\nBETWEEN THE VERSION-1 PLACES")
        for i, x in enumerate(V1):
            for y in V1[i + 1:]:
                print(f"  {g.rooms[x]['name']:18s} to {g.rooms[y]['name']:18s} {run(x, y)}")
    if bad:
        print(f"\n{bad} place(s) have NO ROUTE from the main gate")
        sys.exit(1)


if __name__ == "__main__":
    main()
