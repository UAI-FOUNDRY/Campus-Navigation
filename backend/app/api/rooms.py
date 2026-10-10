from flask import current_app, jsonify, request

from . import bp, error


def _public(graph, room):
    nodes = [graph.nodes[n] for n in room["node_ids"]]
    geo = next((n for n in nodes if n["lat"] is not None), None)
    first = nodes[0]
    return {"id": room["id"], "name": room["name"], "aliases": room["aliases"], "type": room["type"],
            "building": room["building"], "floor": room["floor"], "node_ids": room["node_ids"],
            "indoor": all(n["space"] == "indoor" for n in nodes),
            "lat": geo["lat"] if geo else None, "lng": geo["lng"] if geo else None,
            "x": first.get("x"), "y": first.get("y")}


@bp.get("/rooms")
def search_rooms():
    ctx = current_app.extensions["campus"]
    try:
        limit = max(1, min(int(request.args.get("limit", 8)), 50))
    except ValueError:
        return error("bad_request", "'limit' must be a number", 400)
    hits = ctx["places"].search(request.args.get("q", ""), limit)
    return jsonify(results=[_public(ctx["graph"], r) for r in hits])


@bp.get("/rooms/<room_id>")
def get_room(room_id):
    g = current_app.extensions["campus"]["graph"]
    room = g.rooms.get(room_id)
    if room is None:
        return error("not_found", f"unknown place '{room_id}'", 404)
    return jsonify(_public(g, room))
