"""The JSON contract the Flutter app expects (GET /api/search, POST /api/route)."""
from pathlib import Path

from app import create_app

REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "build" / "campus.merged.json"
STEP_TYPES = {"start", "walk", "turn_left", "turn_right", "enter", "stairs", "lift", "arrive"}


def client():
    return create_app(REAL_PATH).test_client()


def test_search_is_a_plain_list_with_the_app_fields():
    c = client()
    everything = c.get("/api/search?q=").json
    assert isinstance(everything, list) and len(everything) >= 20
    for item in everything:
        assert set(item) == {"id", "name", "building", "floor", "type"} and item["building"]
    hit = c.get("/api/search?q=everest").json[0]
    assert hit["id"] == "mount_everest_130" and hit["type"] == "hall" and hit["floor"] == 0
    types = {i["id"]: i["type"] for i in everything}
    assert types["mess"] == "cafeteria" and types["admin_lobby"] == "office" and types["gym_entrance"] == "gym"
    assert c.get("/api/search?q=zzzzzz").json == []


def test_post_route_gate_to_lhotse():
    r = client().post("/api/route", json={"start": "gate_main", "destination": "mount_lhotse", "step_free": False})
    assert r.status_code == 200
    d = r.json
    assert isinstance(d["distance_meters"], int) and 150 < d["distance_meters"] < 200
    assert d["estimated_minutes"] >= 1 and d["path"] == []
    steps = d["steps"]
    assert steps[0]["type"] == "start" and steps[0]["title"] == "You are here"
    assert steps[-1]["type"] == "arrive" and steps[-1]["title"] == "Arrive at Mount Lhotse"
    assert all(s["type"] in STEP_TYPES and s["title"] and s["instruction"] for s in steps)
    assert "enter" in {s["type"] for s in steps}
    assert [leg["type"] for leg in d["legs"]] == ["outdoor", "indoor"]


def test_post_route_get_route_agree():
    c = client()
    for dest in ("admin_lobby", "mess", "mount_everest_130", "mount_lhotse"):
        a = c.post("/api/route", json={"start": "gate_main", "destination": dest}).json
        b = c.get(f"/api/route?from=gate_main&to={dest}").json
        assert a["distance_meters"] == int(round(b["distance_m"])), dest


def test_post_route_accepts_qr_value_and_node_ids():
    r = client().post("/api/route", json={"start": "campusnav:a0_everest_door", "destination": "mess"})
    assert r.status_code == 200 and r.json["from"] == "a0_everest_door"


def test_post_route_errors():
    c = client()
    assert c.post("/api/route", json={}).status_code == 400
    assert c.post("/api/route", data="not json").status_code == 400
    assert c.post("/api/route", json={"start": "nope", "destination": "mess"}).status_code == 404
    assert c.post("/api/route", json={"start": "gate_main", "destination": "nope"}).status_code == 404


def test_cors_preflight_for_post():
    r = client().options("/api/route", headers={"Origin": "http://x", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and "POST" in r.headers["Access-Control-Allow-Methods"]
