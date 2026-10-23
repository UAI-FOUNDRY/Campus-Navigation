"""Wi-Fi fingerprints: the app sends one when the user confirms where they are; everyone can download them."""
import json
from datetime import datetime, timezone
from pathlib import Path

from app import config, create_app

REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "build" / "campus.merged.json"

APS = {"aa:bb:cc:00:00:01": -48, "aa:bb:cc:00:00:02": -61, "aa:bb:cc:00:00:03": -70.4, "AA:BB:CC:00:00:04": -88}


def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WIFI_PATH", tmp_path / "fingerprints.json")
    monkeypatch.setattr(config, "WIFI_CONTRIB_PATH", tmp_path / "contributions.jsonl")
    return create_app(REAL_PATH).test_client()


def test_empty_list(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    r = c.get("/api/wifi")
    assert r.status_code == 200
    assert r.json == {"samples": [], "spots": 0}


def test_saved_and_served(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    r = c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 0, "at": "2026-10-18T10:00:00.000Z", "aps": APS})
    assert r.status_code == 201
    saved = json.loads((tmp_path / "contributions.jsonl").read_text().splitlines()[0])
    assert saved["spot"] == "a0_adminlobby" and saved["floor"] == 0
    assert saved["aps"]["aa:bb:cc:00:00:04"] == -88          # ids lower-cased, dBm rounded
    assert saved["aps"]["aa:bb:cc:00:00:03"] == -70
    body = c.get("/api/wifi").json
    assert body["spots"] == 1 and body["samples"][0]["spot"] == "a0_adminlobby"


def aps(i):
    """Access points with a marker in the first one, to tell fingerprints apart."""
    return {"aa:bb:cc:00:00:01": -40 - i, "aa:bb:cc:00:00:02": -61, "aa:bb:cc:00:00:03": -70}


def merge(graph_client):
    """What tools/merge_wifi.py does: everything sent so far becomes reviewed."""
    from app.api.wifi import load_samples, newest_per_spot
    graph = graph_client.application.extensions["campus"]["graph"]
    merged = newest_per_spot(load_samples(), graph)
    config.WIFI_PATH.write_text(json.dumps({"samples": merged}), encoding="utf-8")
    config.WIFI_CONTRIB_PATH.write_text("", encoding="utf-8")


def test_keeps_newest_per_spot(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    for i in range(12):
        assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 0, "aps": aps(i)}).status_code == 201
    # Not reviewed yet: only the newest 3 are served.
    samples = c.get("/api/wifi").json["samples"]
    assert [s["aps"]["aa:bb:cc:00:00:01"] for s in samples] == [-49, -50, -51]
    # Merged (reviewed): the newest 8.
    merge(c)
    samples = c.get("/api/wifi").json["samples"]
    assert len(samples) == 8 and samples[-1]["aps"]["aa:bb:cc:00:00:01"] == -51


def test_only_the_day_and_the_servers_day(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    # A phone with its clock years ahead: its fingerprint must not stay "newest" for ever.
    assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 0, "at": "2099-01-01T08:15:00Z",
                                     "aps": APS}).status_code == 201
    saved = json.loads((tmp_path / "contributions.jsonl").read_text().splitlines()[0])
    today = datetime.now(timezone.utc).date().isoformat()
    assert saved["at"] == today             # the server's day, and no time of day
    assert c.get("/api/wifi").json["samples"][0]["at"] == today


def test_a_flood_does_not_push_out_reviewed_ones(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    for i in range(8):
        c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 0, "aps": aps(i)})
    merge(c)
    wrong = {**APS, "aa:bb:cc:00:00:09": -55}
    for _ in range(50):                      # 50 more, e.g. someone sending wrong ones
        assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 0, "aps": wrong}).status_code == 201
    samples = c.get("/api/wifi").json["samples"]
    reviewed = [s for s in samples if "aa:bb:cc:00:00:09" not in s["aps"]]
    assert len(samples) == 8 and len(reviewed) == 5


def test_rejects_bad_fingerprints(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "aps": {"aa:bb:cc:00:00:01": -50}}).status_code == 400
    assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "aps": {"not-a-mac": -50, "x": -60, "y": -70}}).status_code == 400
    assert c.post("/api/wifi", json={"spot": "nowhere_at_all", "aps": APS}).status_code == 404
    assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 2, "aps": APS}).status_code == 400
    assert c.post("/api/wifi", data="nope", content_type="text/plain").status_code == 400
    assert not (tmp_path / "contributions.jsonl").exists()
