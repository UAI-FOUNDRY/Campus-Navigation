"""Turn a found route into what the app needs: legs to draw (map line / floor-plan line) and readable steps."""
import math

from .geo import bearing, turn_angle


def _round(m):
    return int(5 * math.floor(m / 5 + 0.5)) if m >= 20 else int(round(m))


def _label(node):
    if node["name"]:
        return node["name"]
    return "the junction" if node["space"] == "outdoor" else "the next point"


def _maneuver(angle):
    a = abs(angle)
    if a < 30:
        return None  # keep going straight
    side = "right" if angle > 0 else "left"
    if a < 60:
        return f"Bear {side}"
    if a < 135:
        return f"Turn {side}"
    return f"Make a sharp {side}"


def _oriented(edge, from_node):
    geo = edge["geometry"]
    return geo if edge["from"] == from_node else geo[::-1]


def _step(node, text, dist):
    s = {"instruction": text, "distance_m": round(dist, 1), "node_id": node["id"], "space": node["space"]}
    if node["space"] == "outdoor":
        s.update(lat=node["lat"], lng=node["lng"])
    else:
        s.update(x=node["x"], y=node["y"], floor=node["floor"])
    return s


def _legs(graph, node_ids, edge_ids):
    legs, cur = [], None
    for i, eid in enumerate(edge_ids):
        e = graph.edges[eid]
        kind = "outdoor" if e["space"] == "outdoor" else "indoor"  # a door link counts as walking indoors
        if cur is None or cur["type"] != kind:
            cur = {"type": kind, "distance_m": 0.0, "nodes": [node_ids[i]], "polyline": []}
            legs.append(cur)
        cur["distance_m"] += e["weight"]
        cur["nodes"].append(node_ids[i + 1])
        if kind == "outdoor":
            coords = _oriented(e, node_ids[i])
            cur["polyline"].extend(coords if not cur["polyline"] else coords[1:])
    out = []
    for leg in legs:
        if leg["type"] == "outdoor":
            out.append({"type": "outdoor", "distance_m": round(leg["distance_m"], 1), "polyline": leg["polyline"]})
        else:
            pts = [graph.nodes[n] for n in leg["nodes"] if graph.nodes[n]["space"] == "indoor"]
            floor = pts[0]["floor"] if pts else 0
            info = graph.floors.get(floor, {})
            out.append({"type": "indoor", "floor": floor, "image": info.get("image"),
                        "image_size": info.get("image_size"), "distance_m": round(leg["distance_m"], 1),
                        "points": [{"id": p["id"], "name": p["name"], "x": p["x"], "y": p["y"]} for p in pts]})
    return out


def _outdoor_steps(graph, node_ids, edge_ids, first):
    """Turn-by-turn for a run of outdoor edges (bearing changes decide left/right)."""
    nodes = graph.nodes
    segs = [(_oriented(graph.edges[e], node_ids[i]), graph.edges[e]["weight"]) for i, e in enumerate(edge_ids)]
    steps = []
    lead = "Start at" if first else "Continue from"
    text, begin, run = f"{lead} {_label(nodes[node_ids[0]])}", node_ids[0], 0.0
    for i, (coords, weight) in enumerate(segs):
        run += weight
        if i == len(segs) - 1:
            break
        nxt = segs[i + 1][0]
        turn = _maneuver(turn_angle(bearing(*coords[-2], *coords[-1]), bearing(*nxt[0], *nxt[1])))
        if turn:
            steps.append(_step(nodes[begin], f"{text} and walk {_round(run)} m", run))
            text, begin, run = f"{turn} at {_label(nodes[node_ids[i + 1]])}", node_ids[i + 1], 0.0
    steps.append(_step(nodes[begin], f"{text} and walk {_round(run)} m", run))
    return steps


def build_route(graph, result, walk_speed, goal_name=None):
    nodes, node_ids, edge_ids = graph.nodes, result.nodes, result.edges
    legs = _legs(graph, node_ids, edge_ids)
    polyline = [pt for leg in legs if leg["type"] == "outdoor" for pt in leg["polyline"]]
    if not edge_ids and nodes[node_ids[0]]["lat"] is not None:
        polyline = [[nodes[node_ids[0]]["lat"], nodes[node_ids[0]]["lng"]]]

    steps, i = [], 0
    while i < len(edge_ids):
        e = graph.edges[edge_ids[i]]
        if e["space"] == "outdoor":
            j = i
            while j < len(edge_ids) and graph.edges[edge_ids[j]]["space"] == "outdoor":
                j += 1
            steps.extend(_outdoor_steps(graph, node_ids[i:j + 1], edge_ids[i:j], first=(i == 0)))
            i = j
            continue
        a, b = nodes[node_ids[i]], nodes[node_ids[i + 1]]
        w = int(round(e["weight"]))  # indoor distances are short: whole metres
        if e["space"] == "link" and e["weight"] < 1:  # a doorway only: no distance to announce
            text = (f"Go inside through {_label(a)}" if a["space"] == "outdoor"
                    else f"Go outside through {_label(b)}")
        elif e["space"] == "link":
            text = (f"Go inside and walk {w} m to {_label(b)}" if a["space"] == "outdoor"
                    else f"Go outside and walk {w} m to {_label(b)}")
        else:
            text = f"Walk {w} m to {_label(b)}"
        steps.append(_step(a, text, e["weight"]))
        i += 1
    dest = nodes[node_ids[-1]]
    steps.append(_step(dest, f"Arrive at {goal_name or _label(dest)}", 0.0))

    return {
        "from": node_ids[0],
        "to": node_ids[-1],
        "to_name": goal_name or dest["name"],
        "distance_m": round(result.distance, 1),
        "duration_s": int(round(result.distance / walk_speed)),
        "nodes": node_ids,
        "legs": legs,
        "polyline": polyline,
        "steps": steps,
        "graph_version": graph.version,
    }
