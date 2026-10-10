from flask import current_app, jsonify, make_response, request

from . import bp


@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.get("/graph/version")
def graph_version():
    g = current_app.extensions["campus"]["graph"]
    return jsonify(version=g.version, **g.raw["meta"])


@bp.get("/floors")
def floors():
    """Floor-plan images the app should bundle, with their pixel sizes."""
    g = current_app.extensions["campus"]["graph"]
    return jsonify(floors=list(g.floors.values()))


@bp.get("/graph")
def graph_full():
    """Whole graph, for the app to cache (or bundle) so it can work offline. ETag = version."""
    g = current_app.extensions["campus"]["graph"]
    if request.headers.get("If-None-Match") == g.version:
        return make_response("", 304)
    resp = jsonify(g.raw)
    resp.headers["ETag"] = g.version
    resp.headers["Cache-Control"] = "no-cache"
    return resp
