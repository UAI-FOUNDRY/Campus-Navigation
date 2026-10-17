"""Expand a floor file's corridors into plain dots and lines.

A floor file can describe walking space the way a mapper thinks about it:

  "corridors": [{"id": "a0_c_north", "name": "North corridor", "type": "corridor",
                 "path": ["a0_ww_n", [41.3, 54.4], "a0_nc_e"]}]
      a centre line through the corridor. Path points are [x, y] plan metres or ids of dots in "nodes"
      (use an id where two corridors meet, so they share that junction).
  "nodes": [{"id": "a0_library", "type": "door", "name": "Library", "pos": [36.9, 53.0], "on": "a0_c_library"}]
      "on" = this dot is joined to that corridor by a short straight stub, square to the corridor
      (the junction is created automatically where the stub meets the centre line).
  "edges": [{"from": "a", "to": "b", "via": [[x, y], ...]}]   extra lines; "via" bends a line without new dots.

Generated dots get ids  <corridor>__v<k>  (corridor bends) and  <corridor>__<dot id>  (stub junctions).
They are internal: never print QR codes for them, never reference them from places.
Adding a classroom is therefore one line: a door dot with "on": "<corridor id>".
"""
import math

SNAP_M = 0.3   # a stub that lands this close to an existing corridor point reuses it


def _proj(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    q = (a[0] + t * dx, a[1] + t * dy)
    return math.dist(p, q), t, q


def expand(floor):
    """Return (nodes, edges, errors). Nodes/edges are in the simple format merge_data already understands."""
    errors = []
    nodes = [dict(n) for n in floor.get("nodes", [])]
    by_id = {n["id"]: n for n in nodes if n.get("id")}
    edges = [dict(e) for e in floor.get("edges", [])]
    corridors = floor.get("corridors", [])
    if not corridors:
        return nodes, edges, errors

    cinfo = {}
    for c in corridors:
        cid = c.get("id")
        if not cid or cid in cinfo or cid in by_id:
            errors.append(f"corridor id {cid!r} is missing or used twice")
            continue
        pts = []   # (node id, (x, y))
        for k, p in enumerate(c.get("path", [])):
            if isinstance(p, str):
                if p not in by_id or "pos" not in by_id[p]:
                    errors.append(f"corridor '{cid}': path point '{p}' is not a dot with a pos")
                    continue
                pts.append((p, tuple(by_id[p]["pos"])))
            elif isinstance(p, list) and len(p) == 2:
                vid = f"{cid}__v{k}"
                vn = {"id": vid, "type": "corner", "name": "", "pos": [float(p[0]), float(p[1])],
                      "internal": True, "area": c.get("name", "")}
                nodes.append(vn)
                by_id[vid] = vn
                pts.append((vid, (float(p[0]), float(p[1]))))
            else:
                errors.append(f"corridor '{cid}': bad path point {p!r}")
        if len(pts) < 2:
            errors.append(f"corridor '{cid}' needs at least 2 path points")
            continue
        for nid, _ in pts:   # named path dots inherit the corridor name for "turn at ..." text
            by_id[nid].setdefault("area", c.get("name", ""))
        # stops along each segment: (t, node id)
        cinfo[cid] = {"c": c, "pts": pts, "stops": [[(0.0, pts[i][0]), (1.0, pts[i + 1][0])] for i in range(len(pts) - 1)]}

    for n in list(nodes):
        cid = n.get("on")
        if not cid:
            continue
        if cid not in cinfo:
            errors.append(f"dot '{n['id']}': on unknown corridor '{cid}'")
            continue
        if "pos" not in n:
            errors.append(f"dot '{n['id']}' needs a pos to sit on corridor '{cid}'")
            continue
        info = cinfo[cid]
        best = None
        for i in range(len(info["pts"]) - 1):
            d, t, q = _proj(n["pos"], info["pts"][i][1], info["pts"][i + 1][1])
            if best is None or d < best[0]:
                best = (d, i, t, q)
        d, i, t, q = best
        seg = info["stops"][i]
        near = next((s for s in seg if math.dist(by_id[s[1]]["pos"], q) <= SNAP_M), None)
        if near:
            jid = near[1]
        else:
            jid = f"{cid}__{n['id']}"
            jn = {"id": jid, "type": "junction", "name": "", "pos": [round(q[0], 2), round(q[1], 2)],
                  "internal": True, "area": info["c"].get("name", "")}
            nodes.append(jn)
            by_id[jid] = jn
            seg.append((t, jid))
        if jid != n["id"] and d > 1e-6:
            edges.append({"from": n["id"], "to": jid, "type": n.get("stub_type", "corridor"), "stub": True})

    for cid, info in cinfo.items():
        ctype = info["c"].get("type", "corridor")
        for seg in info["stops"]:
            seg.sort()
            for (_, a), (_, b) in zip(seg, seg[1:]):
                if a != b:
                    edges.append({"from": a, "to": b, "type": ctype, "corridor": cid, "area": info["c"].get("name", "")})
    for n in nodes:
        n.pop("on", None)
        n.pop("stub_type", None)
    return nodes, edges, errors
