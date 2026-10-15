from flask import current_app, jsonify, request

from . import bp, error


@bp.post("/estimates")
def estimates():
    """POST /api/estimates  {"start": "<id>", "destinations": ["<id>", ...]}

    Answers {"estimates": {"<id>": <walking minutes>}} for the "2 min walk" labels. Places with no route
    from `start` (or unknown ids) are left out. Routes come from the same cache as /api/route.
    """
    ctx = current_app.extensions["campus"]
    g = ctx["graph"]
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get("start") or not isinstance(body.get("destinations"), list):
        return error("bad_request", "send {'start': <id>, 'destinations': [<id>, ...]}", 400)

    starts = g.resolve(str(body["start"]))
    if starts is None:
        return error("not_found", f"unknown start '{body['start']}'", 404)

    out = {}
    for dest in body["destinations"][:200]:
        goals = g.resolve(str(dest))
        if goals is None:
            continue
        found = ctx["route"](tuple(starts), tuple(goals), False)
        if found is not None:
            out[str(dest)] = max(1, int(found["duration_s"] / 60 + 0.5))
    return jsonify(estimates=out)
