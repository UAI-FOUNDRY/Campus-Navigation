from flask import current_app, jsonify, request

from .. import config
from . import bp, error


@bp.get("/route")
def route():
    """GET /api/route?from=<id>&to=<id>   or   ?from_lat=..&from_lng=..&to=<id>   [&accessible=1]

    from/to accept a place id (may have several entrances, the nearest is used) or a node id.
    """
    ctx = current_app.extensions["campus"]
    g = ctx["graph"]
    a = request.args

    if not a.get("to"):
        return error("bad_request", "missing 'to' (a place or node id)", 400)
    goals = g.resolve(a["to"])
    if goals is None:
        return error("not_found", f"unknown destination '{a['to']}'", 404)

    if a.get("from"):
        starts = g.resolve(a["from"])
        if starts is None:
            return error("not_found", f"unknown start '{a['from']}'", 404)
    elif a.get("from_lat") and a.get("from_lng"):
        try:
            lat, lng = float(a["from_lat"]), float(a["from_lng"])
        except ValueError:
            return error("bad_request", "'from_lat' and 'from_lng' must be numbers", 400)
        snap = g.nearest_node(lat, lng, config.MAX_SNAP_M)
        if snap is None:
            return error("off_campus", "your location is too far from the campus paths", 422)
        starts = [snap[0]]
    else:
        return error("bad_request", "give 'from' or both 'from_lat' and 'from_lng'", 400)

    accessible = a.get("accessible", "").lower() in ("1", "true", "yes")
    result = ctx["route"](tuple(starts), tuple(goals), accessible)
    if result is None:
        return error("no_route", "no walkable route between those places", 422)
    return jsonify(result)
