"""Turn a found route into what the app needs: legs to draw (map line / floor-plan line per floor) and readable steps.

Every step has a machine `kind`:  start_walk, walk, turn_left, turn_right, enter, exit, stairs, lift, arrive.
"""
import math

from .geo import bearing, turn_angle

FLOOR_WORDS = {0: "Ground floor", 1: "First floor", 2: "Second floor", 3: "Third floor", 4: "Fourth floor"}


def floor_label(floor):
    return FLOOR_WORDS.get(floor, f"Floor {floor}")


def _round(m):
    return int(5 * math.floor(m / 5 + 0.5)) if m >= 20 else int(round(m))


def _label(node):
    if node["name"]:
        return node["name"]
    if node.get("area"):
        return f"the {node['area']}"
    return "the junction" if node["space"] == "outdoor" else "the corridor"


def _the(area):
    """'the Library', 'the North corridor', but 'Passage 01' (a numbered name needs no article)."""
    if area.lower().startswith("the ") or any(w.isdigit() for w in area.replace("(", " ").split()):
        return area
    return f"the {area}"


def _maneuver(angle):
    a = abs(angle)
    if a < 30:
        return None  # keep going straight
    side = "right" if angle > 0 else "left"
    if a < 60:
        return f"Bear {side}", side
    if a < 135:
        return f"Turn {side}", side
    return f"Make a sharp {side}", side


def _oriented(edge, from_node):
    geo = edge["geometry"]
    return geo if edge["from"] == from_node else geo[::-1]


def _plan_bearing(a, b):
    """Bearing on the floor plan (x right, y down), 0 = 'up' on the plan."""
    return (math.degrees(math.atan2(b[0] - a[0], -(b[1] - a[1]))) + 360) % 360


def _step(node, text, dist, kind):
    s = {"instruction": text, "distance_m": round(dist, 1), "node_id": node["id"], "space": node["space"],
         "floor": node.get("floor", 0), "kind": kind}
    if node.get("lat") is not None:
        s.update(lat=node["lat"], lng=node["lng"])
    if node["space"] == "indoor":
        s.update(x=node["x"], y=node["y"])
    return s


def _edge_len(e):
    return e.get("length", e["weight"])


def _oriented_via(edge, from_node):
    """The edge's bend points (plan metres, px, lat/lng) in walking order."""
    via = edge.get("via") or []
    px = edge["geometry"][1:-1] if len(edge.get("geometry", [])) == len(via) + 2 else []
    geo = edge.get("via_geo") or []
    pts = [{"pos": v, "px": px[k] if px else None, "geo": geo[k] if k < len(geo) else None} for k, v in enumerate(via)]
    return pts if edge["from"] == from_node else pts[::-1]


def _clean(points, keep_deg=8.0):
    """Drop corridor dots that sit on a straight line (no name, no turn): the app draws a dot at every point."""
    if len(points) < 3:
        return points
    out = [points[0]]
    for k in range(1, len(points) - 1):
        p, q, r = out[-1], points[k], points[k + 1]
        if q["name"]:
            out.append(q)
            continue
        a1 = math.atan2(q["y"] - p["y"], q["x"] - p["x"])
        a2 = math.atan2(r["y"] - q["y"], r["x"] - q["x"])
        turn = abs((math.degrees(a2 - a1) + 180) % 360 - 180)
        if turn >= keep_deg and math.dist((p["x"], p["y"]), (q["x"], q["y"])) > 0.5:
            out.append(q)
    out.append(points[-1])
    return out


def _legs(graph, node_ids, edge_ids):
    """Split the route into drawable legs: outdoor (lat/lng line) and indoor (pixel points, one leg per floor)."""
    legs, cur = [], None
    for i, eid in enumerate(edge_ids):
        e = graph.edges[eid]
        if e["space"] == "vertical":
            cur = None          # a lift/stairs ride ends the leg; the next floor starts a new one
            continue
        if e["space"] == "outdoor":
            key = ("outdoor", None)
        else:  # indoor, or a door link (counts as walking indoors on the floor of its indoor end)
            a, b = graph.nodes[node_ids[i]], graph.nodes[node_ids[i + 1]]
            key = ("indoor", (b if b["space"] == "indoor" else a).get("floor", 0))
        if cur is None or cur["key"] != key:
            cur = {"key": key, "distance_m": 0.0, "nodes": [node_ids[i]], "polyline": [], "bends": {}}
            legs.append(cur)
        cur["distance_m"] += _edge_len(e)
        if e.get("via"):
            cur["bends"][len(cur["nodes"]) - 1] = _oriented_via(e, node_ids[i])
        cur["nodes"].append(node_ids[i + 1])
        if key[0] == "outdoor":
            coords = _oriented(e, node_ids[i])
            cur["polyline"].extend(coords if not cur["polyline"] else coords[1:])
    out = []
    for leg in legs:
        if leg["key"][0] == "outdoor":
            out.append({"type": "outdoor", "distance_m": round(leg["distance_m"], 1), "polyline": leg["polyline"]})
            continue
        floor = leg["key"][1]
        info = graph.floors.get(floor, {})
        points = []
        for k, nid in enumerate(leg["nodes"]):
            p = graph.nodes[nid]
            if p["space"] == "indoor":
                q = {"id": p["id"], "name": p["name"], "x": p["x"], "y": p["y"]}
                if p.get("lat") is not None:
                    q.update(lat=p["lat"], lng=p["lng"])
                points.append(q)
            for b in leg["bends"].get(k, []):
                if b["px"]:
                    q = {"id": "", "name": "", "x": b["px"][0], "y": b["px"][1]}
                    if b["geo"]:
                        q.update(lat=b["geo"][0], lng=b["geo"][1])
                    points.append(q)
        points = _clean(points)
        out.append({"type": "indoor", "floor": floor, "floor_label": info.get("label", floor_label(floor)),
                    "image": info.get("image"), "image_size": info.get("image_size"),
                    "distance_m": round(leg["distance_m"], 1), "points": points})
    return out


MIN_RUN_M = 3.0  # shorter wiggles (door to corridor, column to column) are folded into the next instruction


def _run_area(edges, k0, k1):
    """Name of the corridor/room where most of edges[k0:k1] lies (None outdoors or on short door stubs)."""
    tally = {}
    for e in edges[k0:k1]:
        if e.get("area"):
            tally[e["area"]] = tally.get(e["area"], 0.0) + _edge_len(e)
    return max(tally, key=tally.get) if tally else None


def _turn_steps(nodes, ids, edges, seg_bearings, first, finish_named):
    """Shared turn-by-turn for a run of walking edges. seg_bearings[k] = (bearing at start, bearing at end) of edge k.

    Runs shorter than MIN_RUN_M are not announced as separate steps, and a short last bit becomes
    "... Mount Everest 130 is on your left" instead of "Turn left and walk 1 m"."""
    runs, cur = [], {"begin": ids[0], "k": 0, "length": 0.0, "turn": None}
    for k, e in enumerate(edges):
        cur["length"] += _edge_len(e)
        if k == len(edges) - 1:
            break
        m = _maneuver(turn_angle(seg_bearings[k][1], seg_bearings[k + 1][0]))
        if not m:
            continue
        if cur["length"] < MIN_RUN_M:
            cur["turn"] = cur["turn"] or m          # fold the wiggle into this run
            continue
        runs.append(cur)
        cur = {"begin": ids[k + 1], "k": k + 1, "length": 0.0, "turn": m}
    runs.append(cur)
    for i, r in enumerate(runs):
        r["area"] = _run_area(edges, r["k"], runs[i + 1]["k"] if i + 1 < len(runs) else len(edges))

    end = nodes[ids[-1]]
    side_note = None
    if (finish_named and end["name"] and len(runs) > 1 and runs[-1]["turn"]
            and runs[-1]["length"] < MIN_RUN_M):
        last = runs.pop()
        runs[-1]["length"] += last["length"]
        side_note = f". {end['name']} is on your {last['turn'][1]}"

    steps = []
    for i, r in enumerate(runs):
        here = nodes[r["begin"]]
        into = ""
        if (r["area"] and (i == 0 or r["area"] != runs[i - 1]["area"])
                and r["area"].lower() != here["name"].lower()):
            into = f" into {_the(r['area'])}"
        if r["turn"]:
            text, side = r["turn"]
            kind = f"turn_{side}"
            if i == 0 and first:
                lead = f"Start at {_label(here)}, {text.lower()}{into} and walk"
            elif i == 0:
                lead = f"{text}{into} and walk"
            elif here["name"]:
                lead = f"{text} at {here['name']}{into} and walk"
            else:
                lead = f"{text}{into} and walk"     # a bend inside the same corridor: no landmark to name
        else:
            kind = "start_walk" if first and i == 0 else "walk"
            through = f" through {_the(r['area'])}" if into else ""
            lead = f"Start at {_label(here)} and walk" if first and i == 0 else "Walk"
        tail = ""
        if i == len(runs) - 1:
            if side_note:
                tail = side_note
            elif finish_named and end["name"]:
                tail = f" to {end['name']}"
        if not r["turn"] and not (first and i == 0):
            tail = through + tail
        steps.append(_step(here, f"{lead} {_round(r['length'])} m{tail}", r["length"], kind))
    return steps


def _outdoor_steps(graph, ids, edge_ids, first):
    edges = [graph.edges[e] for e in edge_ids]
    bearings = []
    for k, e in enumerate(edges):
        c = _oriented(e, ids[k])
        bearings.append((bearing(*c[0], *c[1]), bearing(*c[-2], *c[-1])))
    return _turn_steps(graph.nodes, ids, edges, bearings, first, finish_named=False)


def _indoor_steps(graph, ids, edge_ids, first):
    nodes = graph.nodes
    edges = [graph.edges[e] for e in edge_ids]
    if not all("pos" in nodes[n] for n in ids):     # older pixel-only data: one plain step per edge
        steps = []
        for k, e in enumerate(edges):
            w = int(round(_edge_len(e)))
            steps.append(_step(nodes[ids[k]], f"Walk {w} m to {_label(nodes[ids[k + 1]])}", _edge_len(e), "walk"))
        return steps
    bearings = []
    for k, e in enumerate(edges):
        chain = [nodes[ids[k]]["pos"], *[b["pos"] for b in _oriented_via(e, ids[k])], nodes[ids[k + 1]]["pos"]]
        bearings.append((_plan_bearing(chain[0], chain[1]), _plan_bearing(chain[-2], chain[-1])))
    return _turn_steps(nodes, ids, edges, bearings, first, finish_named=True)


def _link_step(a, b, e):
    w = int(round(_edge_len(e)))
    going_in = a["space"] == "outdoor"
    if _edge_len(e) < 3:  # a doorway only (the outdoor dot is at the door): no distance to announce
        text = f"Go inside through {_label(a)}" if going_in else f"Go outside through {_label(b)}"
    else:
        text = (f"Go inside through {_label(a)} and walk {w} m" if going_in
                else f"Go outside and walk {w} m to {_label(b)}")
    return _step(a, text, _edge_len(e), "enter" if going_in else "exit")


def _vertical_step(a, b, e):
    up = b.get("floor", 0) > a.get("floor", 0)
    to = floor_label(b.get("floor", 0))
    if e["type"] == "lift":
        text = f"Take the {e.get('connector_name', 'lift')} to the {to}"
    else:
        text = f"Take the {e.get('connector_name', 'stairs')} {'up' if up else 'down'} to the {to}"
    return _step(a, text, _edge_len(e), e["type"])


def build_route(graph, result, walk_speed, goal_name=None, goal_within=None):
    """goal_within: display name of the place the destination is inside ("Library"), for the arrival text."""
    nodes, node_ids, edge_ids = graph.nodes, result.nodes, result.edges
    legs = _legs(graph, node_ids, edge_ids)
    polyline = [pt for leg in legs if leg["type"] == "outdoor" for pt in leg["polyline"]]
    if not edge_ids and nodes[node_ids[0]]["lat"] is not None and nodes[node_ids[0]]["space"] == "outdoor":
        polyline = [[nodes[node_ids[0]]["lat"], nodes[node_ids[0]]["lng"]]]

    steps, i = [], 0
    while i < len(edge_ids):
        e = graph.edges[edge_ids[i]]
        if e.get("climb"):          # a staircase inside one floor (e.g. the spiral stair up to the attic lab)
            a, b = nodes[node_ids[i]], nodes[node_ids[i + 1]]
            up = (e["climb"] == "up") == (e["from"] == a["id"])
            via = "the " + a["name"][0].lower() + a["name"][1:] if a["type"] == "stairs" and a["name"] else "the stairs"
            text = f"Take {via} {'up' if up else 'down'} to {_label(b)}"
            steps.append(_step(a, text, _edge_len(e), "stairs"))
            i += 1
            continue
        if e["space"] in ("outdoor", "indoor"):
            j = i
            while (j < len(edge_ids) and graph.edges[edge_ids[j]]["space"] == e["space"]
                   and graph.edges[edge_ids[j]].get("floor", 0) == e.get("floor", 0)
                   and not graph.edges[edge_ids[j]].get("climb")):
                j += 1
            make = _outdoor_steps if e["space"] == "outdoor" else _indoor_steps
            steps.extend(make(graph, node_ids[i:j + 1], edge_ids[i:j], first=(i == 0)))
            i = j
            continue
        a, b = nodes[node_ids[i]], nodes[node_ids[i + 1]]
        steps.append(_vertical_step(a, b, e) if e["space"] == "vertical" else _link_step(a, b, e))
        i += 1
    dest = nodes[node_ids[-1]]
    where = f", inside {_the(goal_within)}" if goal_within else ""
    steps.append(_step(dest, f"Arrive at {goal_name or _label(dest)}{where}", 0.0, "arrive"))

    length = sum(_edge_len(graph.edges[e]) for e in edge_ids)
    extra = sum(graph.edges[e].get("extra_s", 0.0) for e in edge_ids)
    floors = sorted({nodes[n].get("floor", 0) for n in node_ids if nodes[n]["space"] == "indoor"})
    return {
        "from": node_ids[0],
        "to": node_ids[-1],
        "to_name": goal_name or dest["name"],
        "to_within": goal_within,
        "distance_m": round(length, 1),
        "duration_s": int(round(length / walk_speed + extra)),
        "floors": floors,
        "nodes": node_ids,
        "legs": legs,
        "polyline": polyline,
        "steps": steps,
        "graph_version": graph.version,
    }
