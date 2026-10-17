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
            e.setdefault("length", e["weight"])     # metres walked (weight = A* cost; a lift adds waiting time)
            e.setdefault("extra_s", 0.0)
            self.edges[e["id"]] = e
            self.adj[e["from"]].append((e["to"], e["weight"], e["id"]))
            self.adj[e["to"]].append((e["from"], e["weight"], e["id"]))

        self.rooms = {}
        self.node_room = {}   # node id -> the first place listed with that door (so either mess door says "Cafeteria")
        for r in data["rooms"]:
            r = dict(r)
            r.setdefault("node_ids", [r["node_id"]])
            self.rooms[r["id"]] = r
            if r.get("type") == "place":
                for nid in r["node_ids"]:
                    self.node_room.setdefault(nid, r)
        self.node_place = {nid: r["name"] for nid, r in self.node_room.items()}

        self.scale = self._heuristic_scale()

    # What the public may see. Plan metres ("pos"), mapper notes and on-site checks stay on the server.
    PUBLIC_NODE = ("id", "type", "name", "space", "floor", "building", "lat", "lng", "x", "y", "area", "media")
    PUBLIC_EDGE = ("id", "from", "to", "weight", "length", "extra_s", "type", "space", "floor", "accessible",
                   "connector", "connector_name", "geometry", "via_geo", "area", "climb")
    PUBLIC_ROOM = ("id", "name", "aliases", "type", "building", "floor", "node_id", "node_ids", "category",
                   "within", "within_name")

    def public_json(self):
        if getattr(self, "_public_json", None) is None:
            pick = lambda d, keys: {k: d[k] for k in keys if k in d}  # noqa: E731
            pub = {"version": self.version, "meta": self.raw.get("meta", {}),
                   "floors": [self.floors[k] for k in sorted(self.floors)],
                   "nodes": [pick(n, self.PUBLIC_NODE) for n in self.raw["nodes"]],
                   "edges": [pick(e, self.PUBLIC_EDGE) for e in self.raw["edges"]],
                   "rooms": [pick(r, self.PUBLIC_ROOM) for r in self.raw["rooms"]]}
            self._public_json = json.dumps(pub, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return self._public_json

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def goal_info(self, goal_node, key=None):
        """(name, within name) to announce on arrival. The asked-for place wins: the waffle shop and the vending
        machines share one door, so "to=atm" must still say "Arrive at ATM"."""
        room = self.rooms.get(key) if key else None
        if room is None or goal_node not in room["node_ids"]:
            room = self.node_room.get(goal_node)
        if room is None:
            return None, None
        return room["name"], room.get("within_name")

    def resolve(self, key):
        """A place id or node id -> list of node ids (a place can have several entrances). None if unknown."""
        if key in self.rooms:
            return list(self.rooms[key]["node_ids"])
        if key in self.nodes:
            return [key]
        return None

    def nearest_node(self, lat, lng, max_m, spaces=("outdoor",)):
        """Closest node (outdoor by default) to a GPS position, or None if farther than max_m. O(V), fine for a campus.

        Indoor nodes have GPS positions too (from the georef) but GPS cannot tell floors apart, so they are only
        used when asked for, e.g. spaces=("outdoor", "indoor0") to include ground-floor indoor dots."""
        best = None
        for nid, n in self.nodes.items():
            if n["lat"] is None:
                continue
            tag = n.get("space", "outdoor") if n.get("space") != "indoor" else f"indoor{n.get('floor', 0)}"
            if tag not in spaces:
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
