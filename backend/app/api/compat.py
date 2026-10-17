"""The two endpoints the Flutter app (UAI-FOUNDRY/CampusNav-Flutter, lib/services/api_service.dart) calls:

    GET  /api/search?q=...                                   -> [{"id","name","building","floor","type"}, ...]
    POST /api/route  {"start","destination","step_free"}     -> {"distance_meters","estimated_minutes","steps","path", ...}

They reuse the same graph, search index and route cache as /api/rooms and GET /api/route; only the JSON shape differs.
The real geometry is in "legs" / "polyline" ("path" stays empty: it is the app's schematic-map space, which real data cannot fill).
"""
import re

from flask import current_app, jsonify, request

from . import bp, error

# The app's filter chips understand these type words (lib/theme/destination_style.dart, categoryOfType):
# lab, library, hall, auditorium, cafeteria, sports, gym, turf, office, hostel. Anything else shows under "Other".
# First match wins; the words are checked against the place id + name + aliases.
_TYPE_RULES = [
    ("cafeteria", ("mess", "cafeteria", "canteen", "cafe", "bistro", "tuck", "vending", "waffle")),
    ("gym", ("gym",)),
    ("turf", ("turf",)),
    ("library", ("library",)),
    ("lab", ("lab",)),
    ("office", ("office", "admin", "lobby", "registrar")),
    ("hostel", ("hostel", "r7", "r8")),
    ("hall", ("classroom", "mount", "hall")),  # classrooms go under the app's "Halls" chip
]


CATEGORY_TO_APP = {"classroom": "hall", "food": "cafeteria", "office": "office", "lab": "lab", "library": "library",
                   "auditorium": "auditorium", "sports": "sports", "hostel": "hostel"}


def app_type(room):
    """Type word for the app: a place's 'category' from data/places.json wins over the name guess."""
    if room.get("category"):
        return CATEGORY_TO_APP.get(room["category"], "place")
    words = set(re.split(r"[^a-z0-9]+", " ".join([room["id"], room["name"], *room.get("aliases", [])]).lower()))
    for kind, keys in _TYPE_RULES:
        if any(k in words for k in keys) or any(k in room["id"].lower() for k in keys if len(k) > 3):
            return kind
    return "place"


def _search_item(room):
    item = {"id": room["id"], "name": room["name"], "building": room.get("building") or "Campus",
            "floor": room.get("floor", 0), "type": app_type(room)}
    if room.get("within_name"):
        item["within_name"] = room["within_name"]
    return item


@bp.get("/search")
def app_search():
    """Plain list (the app also accepts {"results": [...]}, but a list is what its README documents)."""
    ctx = current_app.extensions["campus"]
    q = request.args.get("q", "")
    hits = ctx["places"].search(q, 500 if not q.strip() else 30)
    return jsonify([_search_item(r) for r in hits])


KIND_TO_APP = {"start_walk": "walk", "walk": "walk", "turn_left": "turn_left", "turn_right": "turn_right",
               "enter": "enter", "exit": "walk", "stairs": "stairs", "lift": "lift", "arrive": "arrive"}


def _step_title(kind, text, dist):
    if kind == "arrive":
        return text  # "Arrive at Mount Lhotse"
    if kind == "enter":
        return "Go inside"
    if kind == "exit":
        return "Go outside"
    if kind in ("turn_left", "turn_right"):
        return text.split(" at ")[0]  # "Bear right", "Turn left", "Make a sharp left"
    if kind == "stairs":
        return "Take the stairs"
    if kind == "lift":
        return "Take the lift"
    return f"Walk {int(round(dist))} m" if dist >= 1 else "Continue"


def to_app_route(result, start_name):
    steps = [{"type": "start", "title": "You are here", "instruction": start_name, "distance": 0, "floor": 0}]
    for s in result["steps"]:
        kind = s.get("kind", "walk")
        steps.append({"type": KIND_TO_APP.get(kind, "walk"), "title": _step_title(kind, s["instruction"], s["distance_m"]),
                      "instruction": s["instruction"], "distance": s["distance_m"], "floor": s.get("floor", 0)})
    return {
        "distance_meters": int(round(result["distance_m"])),
        "estimated_minutes": max(1, int(result["duration_s"] / 60 + 0.5)) if result["duration_s"] > 0 else 0,
        "steps": steps,
        "path": [],
        # extras for drawing the real route (outdoor [lat,lng] polyline, indoor pixel points on the floor plan)
        "legs": result["legs"],
        "polyline": result["polyline"],
        "from": result["from"],
        "to": result["to"],
        "to_name": result["to_name"],
        "to_within": result.get("to_within"),
        "floors": result.get("floors", []),
        "graph_version": result["graph_version"],
    }


@bp.post("/route")
def app_route():
    ctx = current_app.extensions["campus"]
    g = ctx["graph"]
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("start") or not body.get("destination"):
        return error("bad_request", "send {'start': <id>, 'destination': <id>, 'step_free': false}", 400)

    start_key, dest_key = str(body["start"]).strip(), str(body["destination"]).strip()
    if start_key.startswith("campusnav:"):  # a raw QR code value is fine too
        start_key = start_key[len("campusnav:"):]
    starts = g.resolve(start_key)
    if starts is None:
        return error("not_found", f"unknown start '{start_key}'", 404)
    goals = g.resolve(dest_key)
    if goals is None:
        return error("not_found", f"unknown destination '{dest_key}'", 404)

    step_free = str(body.get("step_free", "")).lower() in ("1", "true", "yes")
    result = ctx["route"](tuple(starts), tuple(goals), step_free, dest_key)
    if result is None:
        return error("no_route", "no walkable route between those places", 422)

    room = g.rooms.get(start_key)
    start_name = room["name"] if room else (g.nodes[result["from"]]["name"] or start_key)
    return jsonify(to_app_route(result, start_name))
