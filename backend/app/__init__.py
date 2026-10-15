from functools import lru_cache

from flask import Flask, jsonify

from . import config
from .api import bp as api_bp
from .core.astar import astar
from .core.graph import CampusGraph
from .core.instructions import build_route
from .core.search import PlaceIndex


def create_app(data_path=None):
    """Build the Flask app. The graph is loaded ONCE here, not per request."""
    app = Flask(__name__)
    app.json.sort_keys = False

    graph = CampusGraph.load(data_path or config.DATA_PATH)

    @lru_cache(maxsize=config.ROUTE_CACHE_SIZE)
    def cached_route(starts, goals, accessible_only):
        found = astar(graph, starts, goals, accessible_only)
        if found is None:
            return None
        return build_route(graph, found, config.WALK_SPEED_MPS, graph.node_place.get(found.goal))

    app.extensions["campus"] = {"graph": graph, "places": PlaceIndex(graph.rooms.values()), "route": cached_route}
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.after_request
    def add_cors(resp):  # lets the Flutter web build and local tools call the API
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, If-None-Match"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error={"code": "not_found", "message": "unknown endpoint"}), 404

    @app.errorhandler(500)
    def server_error(_):
        return jsonify(error={"code": "server_error", "message": "something went wrong"}), 500

    return app
