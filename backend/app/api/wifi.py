import json
import re
from datetime import datetime, timezone

from flask import current_app, jsonify, request

from .. import config
from . import bp, error

_BSSID = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
PER_SPOT = 8          # newest fingerprints kept per spot
MAX_FRESH = 3         # ... of which at most this many not yet merged (reviewed) by tools/merge_wifi.py
MAX_APS = 40          # strongest access points kept per fingerprint


def _day(value):
    """An ISO time (any offset) as its UTC date "YYYY-MM-DD", or "" if it is not one."""
    try:
        t = datetime.fromisoformat(str(value)[:40].replace("Z", "+00:00"))
    except ValueError:
        return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).date().isoformat()


def clean(sample, graph, received=None):
    """Validate a fingerprint and return its normalized representation, or None.

    The sample includes a spot, floor and access-point BSSIDs with signal
    strengths. It contains no user account or phone/device ID. Only the DAY is
    kept, never the time: a spot with an exact time says where someone was.
    [received]: a new fingerprint from the app; its day is the server's (a
    phone's clock can be wrong, and a future date would stay "newest")."""
    if not isinstance(sample, dict):
        return None
    spot = str(sample.get("spot", ""))[:80]
    resolved = graph.resolve(spot) if spot else None
    if resolved is None:
        return None
    try:
        floor = int(sample.get("floor", 0))
    except (TypeError, ValueError):
        return None
    if not -2 <= floor <= 20:
        return None

    # Do not accept a fingerprint that teaches a valid spot the wrong floor.
    room = graph.rooms.get(spot)
    if room is not None and room.get("floor") is not None:
        expected_floors = {int(room["floor"])}
    else:
        expected_floors = {
            int(graph.nodes[node_id].get("floor", 0))
            for node_id in resolved
            if node_id in graph.nodes
        }
    if expected_floors and floor not in expected_floors:
        return None
    aps = sample.get("aps")
    if not isinstance(aps, dict):
        return None
    heard = []
    for bssid, dbm in list(aps.items())[:200]:
        bssid = str(bssid).lower()
        if not _BSSID.match(bssid) or isinstance(dbm, bool) or not isinstance(dbm, (int, float)):
            continue
        if -100 <= dbm <= -20:
            heard.append((bssid, int(round(dbm))))
    if len(heard) < 3:
        return None
    heard.sort(key=lambda kv: -kv[1])
    at = received.date().isoformat() if received is not None else _day(sample.get("at", ""))
    return {"spot": spot, "floor": floor, "at": at, "aps": dict(heard[:MAX_APS])}


def load_committed():
    """The reviewed fingerprints (data/wifi/fingerprints.json, written by tools/merge_wifi.py)."""
    try:
        data = json.loads(config.WIFI_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    samples = data.get("samples", []) if isinstance(data, dict) else data
    return samples if isinstance(samples, list) else []


def load_contributions():
    """What the apps sent since (data/wifi/contributions.jsonl), oldest first."""
    samples = []
    try:
        with config.WIFI_CONTRIB_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    samples.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return samples


def load_samples():
    """Committed fingerprints, then everything the apps sent since (for tools/merge_wifi.py)."""
    return load_committed() + load_contributions()


def newest_per_spot(samples, graph, fresh=(), max_fresh=MAX_FRESH):
    """The newest PER_SPOT fingerprints of every spot. [samples] are trusted (reviewed); of the unreviewed
    [fresh] ones at most [max_fresh] a spot are kept, so a flood of wrong ones cannot push out the reviewed ones.
    Newest = latest day; within a day, the one received last (the sort is stable)."""
    by_spot = {}
    for s in samples:
        c = clean(s, graph)
        if c:
            by_spot.setdefault(c["spot"], []).append(c)
    fresh_by_spot = {}
    for s in fresh:
        c = clean(s, graph)
        if c:
            fresh_by_spot.setdefault(c["spot"], []).append(c)
    for spot, new in fresh_by_spot.items():
        by_spot.setdefault(spot, []).extend(sorted(new, key=lambda s: s["at"])[-max_fresh:])
    out = []
    for spot in sorted(by_spot):
        out += sorted(by_spot[spot], key=lambda s: s["at"])[-PER_SPOT:]
    return out


# GET /api/wifi is answered from this until a file changes (each worker keeps its own copy).
_cache = {"key": None, "body": None}


def _stamp(path):
    try:
        st = path.stat()
        return (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return (str(path), None, None)


@bp.get("/wifi")
def wifi_fingerprints():
    """GET /api/wifi -> {"samples": [{spot, floor, at, aps}], "spots": N}

    Wi-Fi fingerprints of campus spots: the app compares the networks it hears with these to tell the room and
    floor indoors (Android; iPhones cannot scan Wi-Fi). Reviewed fingerprints first; at most MAX_FRESH a spot of
    the ones sent since the last merge."""
    graph = current_app.extensions["campus"]["graph"]
    key = (id(graph), _stamp(config.WIFI_PATH), _stamp(config.WIFI_CONTRIB_PATH))
    if _cache["key"] != key:
        samples = newest_per_spot(load_committed(), graph, fresh=load_contributions())
        _cache["body"] = {"samples": samples, "spots": len({s["spot"] for s in samples})}
        _cache["key"] = key
    return jsonify(_cache["body"])


@bp.post("/wifi")
def wifi_add():
    """POST /api/wifi  {"spot": "<place or node id>", "floor": 0, "at": "<ISO time>", "aps": {"<bssid>": -60, ...}}

    The app sends one when the user confirms where they are (picks their spot in "Where exactly are you?" or scans
    a sign). Appended to data/wifi/contributions.jsonl."""
    graph = current_app.extensions["campus"]["graph"]
    body = request.get_json(silent=True)
    sample = clean(body, graph, received=datetime.now(timezone.utc))
    if sample is None:
        spot = str(body.get("spot", "")) if isinstance(body, dict) else ""
        if spot and graph.resolve(spot) is None:
            return error("not_found", f"unknown spot '{spot[:80]}'", 404)
        return error("bad_request", "send {spot, floor, aps: {bssid: dBm}} with at least 3 access points", 400)
    try:
        path = config.WIFI_CONTRIB_PATH
        if path.exists() and path.stat().st_size > config.WIFI_MAX_BYTES:
            return error("inbox_full", "the Wi-Fi fingerprint inbox is full; run tools/merge_wifi.py", 503)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sample) + "\n")
    except OSError:
        return error("server_error", "could not save the fingerprint", 500)
    return jsonify(status="saved"), 201
