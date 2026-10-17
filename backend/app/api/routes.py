from flask import current_app, jsonify, request

from .. import config
from . import bp, error


@bp.get("/route")
def route():
    """GET /api/route?from=<id>&to=<id>   or   ?from_lat=..&from_lng=..[&from_floor=0]&to=<id>   [&accessible=1]

    from/to accept a place id (may have several entrances, the nearest is used) or a node id.
    A GPS start snaps to the nearest outdoor dot; with from_floor=N it may also snap to indoor dots of floor N
    (GPS cannot tell floors apart, so the app must say which floor the user is on, e.g. from a QR scan).
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
        spaces = ("outdoor",)
        if a.get("from_floor", "") != "":
            try:
                spaces = ("outdoor", f"indoor{int(a['from_floor'])}")
            except ValueError:
                return error("bad_request", "'from_floor' must be a whole number (0 = ground floor)", 400)
        snap = g.nearest_node(lat, lng, config.MAX_SNAP_M, spaces)
        if snap is None:
            return error("off_campus", "your location is too far from the campus paths", 422)
        starts = [snap[0]]
    else:
        return error("bad_request", "give 'from' or both 'from_lat' and 'from_lng'", 400)

    accessible = a.get("accessible", "").lower() in ("1", "true", "yes")
    result = ctx["route"](tuple(starts), tuple(goals), accessible, a["to"])
    if result is None:
        return error("no_route", "no walkable route between those places", 422)
    return jsonify(result)
