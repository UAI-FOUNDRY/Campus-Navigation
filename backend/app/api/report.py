import json
from datetime import datetime, timezone

from flask import jsonify, request

from .. import config
from . import bp, error


@bp.post("/report")
def report_problem():
    """POST /api/report  {"start", "destination", "reason", "details"}

    The app's "Report a problem" sheet. Each report is appended as one JSON line to data/reports.jsonl
    so the team can read them while walking the campus to fix the map.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not str(body.get("reason", "")).strip():
        return error("bad_request", "send a JSON body with at least a 'reason'", 400)

    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for key in ("start", "destination", "reason", "details"):
        entry[key] = str(body.get(key, ""))[:500]  # keep one report small

    try:
        config.REPORTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.REPORTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return error("server_error", "could not save the report", 500)
    return jsonify(status="received"), 201
