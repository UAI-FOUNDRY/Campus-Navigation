import json
import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import current_app, jsonify, request

from .. import config
from . import bp, error

log = logging.getLogger(__name__)

FIELDS = ("start", "destination", "reason", "details", "step")


def _clean(value, limit=500):
    text = str(value if value is not None else "")[:limit]
    return "".join(ch for ch in text if ch.isprintable() or ch == " ").strip()   # no control characters


def _quiet(text):
    """Text from the app, made safe for an issue title or list: no @mentions, no #issue links."""
    return text.replace("@", "@\u200b").replace("#", "#\u200b")


@bp.post("/report")
def report_problem():
    """POST /api/report  {"start", "destination", "reason", "details"?, "step"?, "step_free"?}

    The app's "Report a problem" sheet. Every report is appended as one JSON line to data/reports.jsonl and,
    when GITHUB_TOKEN is set, opened as an issue in REPORTS_REPO (labelled REPORTS_LABEL) so the team can
    assign and close it. The issue is created in the background: the app gets its answer at once.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not _clean(body.get("reason")):
        return error("bad_request", "send a JSON body with at least a 'reason'", 400)

    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for key in FIELDS:
        entry[key] = _clean(body.get(key), 300 if key == "step" else 500)
    entry["step_free"] = str(body.get("step_free", "")).lower() in ("1", "true", "yes")

    try:
        if config.REPORTS_PATH.exists() and config.REPORTS_PATH.stat().st_size > config.REPORTS_MAX_BYTES:
            return error("inbox_full", "the report inbox is full; the team has been asked to clear it", 503)
        config.REPORTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with config.REPORTS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        if not os.environ.get("GITHUB_TOKEN"):
            return error("server_error", "could not save the report", 500)
        # The issue below still keeps it.

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and _take_daily_slot():
        graph = current_app.extensions["campus"]["graph"]
        issue = build_issue(entry, graph, request.host_url)
        _dispatch(lambda: open_issue(issue, token))
    return jsonify(status="received"), 201


# ---- GitHub issues

_day = {"date": None, "count": 0}
_day_lock = threading.Lock()


def _take_daily_slot():
    """At most REPORTS_ISSUES_PER_DAY issues a day (per server process): a flood stays in the file."""
    today = datetime.now(timezone.utc).date()
    with _day_lock:
        if _day["date"] != today:
            _day["date"], _day["count"] = today, 0
        if _day["count"] >= config.REPORTS_ISSUES_PER_DAY:
            return False
        _day["count"] += 1
        return True


def _name(graph, key):
    """A place or node id as people know it."""
    if not key:
        return "?"
    room = graph.rooms.get(key)
    if room:
        return room["name"]
    node = graph.nodes.get(key)
    if node and node.get("name"):
        return node["name"]
    return _quiet(key)


def build_issue(entry, graph, host_url):
    start, dest = _name(graph, entry["start"]), _name(graph, entry["destination"])
    reason = _quiet(entry["reason"])[:80]
    lines = [f"**{reason}**", "", f"- Route: {start} \u2192 {dest}"]
    if entry.get("step"):
        lines.append(f"- At the step: {_quiet(entry['step'])}")
    if entry.get("step_free"):
        lines.append("- Step-free route (lifts, no stairs)")
    if entry["start"] and entry["destination"]:
        query = {"from": entry["start"], "to": entry["destination"]}
        if entry.get("step_free"):
            query["accessible"] = 1
        lines.append(f"- See the route: {host_url}api/route?{urlencode(query)}")
    lines.append(f"- Sent: {entry['at']} (UTC)")
    if entry.get("details"):
        # In a fenced block GitHub shows the text as written: no links, mentions or formatting.
        details = entry["details"].replace("~~~", "~ ~ ~")
        lines += ["", "What they wrote:", "", "~~~text", details, "~~~"]
    lines += ["", "_From the app's Report a problem sheet. No name, account or position of the person is sent._"]
    return {
        "title": f"Report: {reason} ({start} \u2192 {dest})"[:120],
        "body": "\n".join(lines),
        "labels": [config.REPORTS_LABEL],
    }


def open_issue(issue, token):
    """POST the issue to GitHub. Returns its URL, or None (logged) when GitHub said no."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{config.REPORTS_REPO}/issues",
        data=json.dumps(issue).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "campus-nav-api",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            url = json.loads(r.read().decode("utf-8")).get("html_url")
            log.info("report opened as %s", url)
            return url
    except urllib.error.HTTPError as e:
        log.warning("report not opened as an issue: GitHub answered %s %s", e.code, e.read()[:300])
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.warning("report not opened as an issue: %s", e)
    return None


def _dispatch(job):
    """Run [job] after the answer has gone (tests replace this to run it at once)."""
    threading.Thread(target=job, daemon=True).start()
