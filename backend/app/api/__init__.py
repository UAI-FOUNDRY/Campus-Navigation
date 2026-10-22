from flask import Blueprint, jsonify

bp = Blueprint("api", __name__)


def error(code, message, status):
    return jsonify(error={"code": code, "message": message}), status


def no_route(ctx, starts, goals, accessible, goal_key):
    """422 answer. When only the step-free search failed, say so: the place is up/down stairs only."""
    if accessible and ctx["route"](tuple(starts), tuple(goals), False, goal_key) is not None:
        g = ctx["graph"]
        room = g.rooms.get(goal_key)
        name = room["name"] if room else goal_key
        return error("no_step_free_route",
                     f"{name} can only be reached by stairs (no lift or ramp goes there). "
                     "Turn off step-free to see the route.", 422)
    return error("no_route", "no walkable route between those places", 422)


from . import compat, estimates, meta, report, rooms, routes, wifi  # noqa: E402,F401  (registers the endpoints)
