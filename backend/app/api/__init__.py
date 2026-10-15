from flask import Blueprint, jsonify

bp = Blueprint("api", __name__)


def error(code, message, status):
    return jsonify(error={"code": code, "message": message}), status


from . import estimates, meta, report, rooms, routes  # noqa: E402,F401  (registers the endpoints)
