"""Wi-Fi fingerprints: the app sends one when the user confirms where they are; everyone can download them."""
import json
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


def test_keeps_newest_per_spot(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    for i in range(12):
        assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "floor": 0,
                                         "at": f"2026-10-18T10:{i:02d}:00Z", "aps": APS}).status_code == 201
    samples = c.get("/api/wifi").json["samples"]
    assert len(samples) == 8 and samples[-1]["at"].startswith("2026-10-18T10:11")


def test_rejects_bad_fingerprints(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "aps": {"aa:bb:cc:00:00:01": -50}}).status_code == 400
    assert c.post("/api/wifi", json={"spot": "a0_adminlobby", "aps": {"not-a-mac": -50, "x": -60, "y": -70}}).status_code == 400
    assert c.post("/api/wifi", json={"spot": "nowhere_at_all", "aps": APS}).status_code == 404
    assert c.post("/api/wifi", data="nope", content_type="text/plain").status_code == 400
    assert not (tmp_path / "contributions.jsonl").exists()
