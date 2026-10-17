from flask import current_app, jsonify

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
    return jsonify(floors=[g.floors[k] for k in sorted(g.floors)])


@bp.get("/graph")
def graph_full():
    """Whole graph WITHOUT internal mapping data (plan metres, notes, 'verify' remarks), for offline use.
    ETag = graph version; caching and 304 are handled in app/web.py."""
    g = current_app.extensions["campus"]["graph"]
    return current_app.response_class(g.public_json(), mimetype="application/json")
