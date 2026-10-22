import json
import re
from datetime import datetime, timezone

from flask import current_app, jsonify, request

from .. import config
from . import bp, error

_BSSID = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
PER_SPOT = 8          # newest fingerprints kept per spot
MAX_APS = 40          # strongest access points kept per fingerprint


def clean(sample, graph):
    """A valid fingerprint {spot, floor, at, aps: {bssid: dBm}} or None.

    Only access point ids (BSSIDs) and signal strengths are kept: nothing about the phone or the person."""
    if not isinstance(sample, dict):
        return None
    spot = str(sample.get("spot", ""))[:80]
    if not spot or graph.resolve(spot) is None:
        return None
    try:
        floor = int(sample.get("floor", 0))
    except (TypeError, ValueError):
        return None
    if not -2 <= floor <= 20:
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
    at = str(sample.get("at", ""))[:40]
    try:
        datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {"spot": spot, "floor": floor, "at": at, "aps": dict(heard[:MAX_APS])}


def load_samples():
    """The committed fingerprints (data/wifi/fingerprints.json) plus everything the apps sent since
    (data/wifi/contributions.jsonl, merged into the first by tools/merge_wifi.py)."""
    samples = []
    try:
        data = json.loads(config.WIFI_PATH.read_text(encoding="utf-8"))
        samples += data.get("samples", []) if isinstance(data, dict) else data
    except (OSError, ValueError):
        pass
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


def newest_per_spot(samples, graph):
    by_spot = {}
    for s in samples:
        c = clean(s, graph)
        if c:
            by_spot.setdefault(c["spot"], []).append(c)
    out = []
    for spot in sorted(by_spot):
        out += sorted(by_spot[spot], key=lambda s: s["at"])[-PER_SPOT:]
    return out


@bp.get("/wifi")
def wifi_fingerprints():
    """GET /api/wifi -> {"samples": [{spot, floor, at, aps}], "spots": N}

    Wi-Fi fingerprints of campus spots: the app compares the networks it hears with these to tell the room and
    floor indoors (Android; iPhones cannot scan Wi-Fi)."""
    graph = current_app.extensions["campus"]["graph"]
    samples = newest_per_spot(load_samples(), graph)
    return jsonify(samples=samples, spots=len({s["spot"] for s in samples}))


@bp.post("/wifi")
def wifi_add():
    """POST /api/wifi  {"spot": "<place or node id>", "floor": 0, "at": "<ISO time>", "aps": {"<bssid>": -60, ...}}

    The app sends one when the user confirms where they are (picks their spot in "Where exactly are you?" or scans
    a sign). Appended to data/wifi/contributions.jsonl."""
    graph = current_app.extensions["campus"]["graph"]
    body = request.get_json(silent=True)
    sample = clean(body, graph)
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
