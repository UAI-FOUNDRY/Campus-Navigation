import heapq
import json
from collections import defaultdict
from pathlib import Path

from .geo import haversine


class CampusGraph:
    """The campus (outdoor + indoor) as an in-memory graph. Built once at startup, then only read."""

    def __init__(self, data):
        self.raw = data
        self.version = data["version"]
        self.floors = {f["floor"]: f for f in data.get("floors", [])}

        self.nodes = {}
        for n in data["nodes"]:
            n = dict(n)
            n.setdefault("space", "outdoor")
            n.setdefault("lat", None)
            n.setdefault("lng", None)
            n.setdefault("name", "")
            n.setdefault("floor", 0)
            self.nodes[n["id"]] = n

        self.edges = {}
        # adjacency list: node id -> [(neighbour id, weight in metres, edge id), ...]
        self.adj = defaultdict(list)
        for e in data["edges"]:
            e = dict(e)
            e.setdefault("space", "outdoor")
            e.setdefault("accessible", True)
            self.edges[e["id"]] = e
            self.adj[e["from"]].append((e["to"], e["weight"], e["id"]))
            self.adj[e["to"]].append((e["from"], e["weight"], e["id"]))

        self.rooms = {}
        self.node_place = {}  # node id -> place name (so "Arrive at Cafeteria / Mess" works for either door)
        for r in data["rooms"]:
            r = dict(r)
            r.setdefault("node_ids", [r["node_id"]])
            self.rooms[r["id"]] = r
            if r.get("type") == "place":
                for nid in r["node_ids"]:
                    self.node_place[nid] = r["name"]

        self.scale = self._heuristic_scale()

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def resolve(self, key):
        """A place id or node id -> list of node ids (a place can have several entrances). None if unknown."""
        if key in self.rooms:
            return list(self.rooms[key]["node_ids"])
        if key in self.nodes:
            return [key]
        return None

    def nearest_node(self, lat, lng, max_m):
        """Closest outdoor node to a GPS position, or None if farther than max_m. O(V), fine for a campus."""
        best = None
        for nid, n in self.nodes.items():
            if n["lat"] is None:
                continue
            d = haversine(lat, lng, n["lat"], n["lng"])
            if best is None or d < best[1]:
                best = (nid, d)
        return best if best and best[1] <= max_m else None

    def _heuristic_scale(self):
        """Largest factor s (<= 1) such that s * straight-line never exceeds the real walking distance
        between any two outdoor points, counting shortcuts through the building. Makes the A* heuristic
        provably safe even if the indoor measurements and the outdoor map disagree slightly."""
        geo = [nid for nid, n in self.nodes.items() if n["lat"] is not None]
        scale = 1.0
        for src in geo:
            dist = {src: 0.0}
            heap = [(0.0, src)]
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist[u]:
                    continue
                for v, w, _ in self.adj[u]:
                    if d + w < dist.get(v, float("inf")):
                        dist[v] = d + w
                        heapq.heappush(heap, (d + w, v))
            a = self.nodes[src]
            for nid in geo:
                if nid in dist:
                    straight = haversine(a["lat"], a["lng"], self.nodes[nid]["lat"], self.nodes[nid]["lng"])
                    if straight >= 5:
                        scale = min(scale, dist[nid] / straight)
        return max(0.0, scale * 0.999)
