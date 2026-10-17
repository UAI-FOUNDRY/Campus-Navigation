from flask import current_app, jsonify, request

from .. import config
from ..core.astar import walk_times
from . import bp, error


@bp.post("/estimates")
def estimates():
    """POST /api/estimates  {"start": "<id>", "destinations": ["<id>", ...]}

    Answers {"estimates": {"<id>": <walking minutes>}} for the "2 min walk" labels. Places with no route
    from `start` (or unknown ids) are left out. One shortest-path search from `start` answers all of them.
    """
    ctx = current_app.extensions["campus"]
    g = ctx["graph"]
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("start") or not isinstance(body.get("destinations"), list):
        return error("bad_request", "send {'start': <id>, 'destinations': [<id>, ...]}", 400)

    starts = g.resolve(str(body["start"]).removeprefix("campusnav:"))
    if starts is None:
        return error("not_found", f"unknown start '{body['start']}'", 404)

    reach = walk_times(g, tuple(starts), config.WALK_SPEED_MPS)
    out = {}
    for dest in body["destinations"][:200]:     # the app asks for every place at once (about 130 today)
        goals = g.resolve(str(dest))
        if goals is None:
            continue
        best = min((reach[n] for n in goals if n in reach), default=None)   # nearest entrance, as /api/route picks
        if best is not None:
            out[str(dest)] = max(1, int(round(best[1]) / 60 + 0.5))     # same rounding as /api/route
    return jsonify(estimates=out)
