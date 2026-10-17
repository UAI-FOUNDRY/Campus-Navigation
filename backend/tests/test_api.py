"""API tests using Flask's test client (no server needed)."""
from pathlib import Path

from app import create_app

REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "build" / "campus.merged.json"


def client():
    return create_app(REAL_PATH).test_client()


def test_health():
    assert client().get("/api/health").json == {"status": "ok"}


def test_version_graph_etag_and_floors():
    c = client()
    v = c.get("/api/graph/version").json["version"]
    assert c.get("/api/graph").headers["ETag"] == f'"{v}"'
    assert c.get("/api/graph", headers={"If-None-Match": f'"{v}"'}).status_code == 304
    assert c.get("/api/graph", headers={"If-None-Match": v}).status_code == 304
    floors = c.get("/api/floors").json["floors"]
    assert floors and floors[0]["image"] and len(floors[0]["image_size"]) == 2


def test_search_finds_outdoor_and_indoor_places():
    c = client()
    assert any("Makalu" in r["name"] for r in c.get("/api/rooms?q=makalu").json["results"])
    everest = c.get("/api/rooms?q=everest").json["results"][0]
    assert everest["id"] == "mount_everest_130" and everest["indoor"] is True and everest["floor"] == 0
    assert everest["lat"] is not None  # indoor dots get GPS from the georef (plan tied to the facade doors)
    mess = c.get("/api/rooms/mess").json
    assert len(mess["node_ids"]) == 2 and mess["indoor"] is False and mess["lat"] is not None
    assert c.get("/api/rooms?q=zzzzzz").json["results"] == []


def test_outdoor_route_gate_to_gym():
    r = client().get("/api/route?from=gate_main&to=gym_entrance").json
    assert 300 < r["distance_m"] < 520   # v5 joined the gym line (was ~460 m round the turf before)
    assert r["nodes"][0] == "gate_main" and r["nodes"][-1] == "gym_entrance"
    assert [leg["type"] for leg in r["legs"]] == ["outdoor"]
    assert r["steps"][-1]["instruction"].startswith("Arrive at") and len(r["polyline"]) >= 2


def test_route_from_the_gate_into_the_building():
    r = client().get("/api/route?from=gate_main&to=mount_everest_130").json
    assert [leg["type"] for leg in r["legs"]] == ["outdoor", "indoor"]
    assert r["steps"][-1]["instruction"] == "Arrive at Mount Everest 130"
    assert abs(r["distance_m"] - sum(leg["distance_m"] for leg in r["legs"])) < 0.2
    indoor = r["legs"][1]
    assert indoor["image"] and all("x" in p and "y" in p for p in indoor["points"])


def test_all_pairs_of_the_four_places_have_a_route_and_are_symmetric():
    c = client()
    ids = ["admin_lobby", "mess", "mount_everest_130", "mount_lhotse"]
    for a in ids:
        for b in ids:
            if a == b:
                continue
            ab = c.get(f"/api/route?from={a}&to={b}")
            ba = c.get(f"/api/route?from={b}&to={a}")
            assert ab.status_code == 200 and ba.status_code == 200, (a, b)
            assert abs(ab.json["distance_m"] - ba.json["distance_m"]) < 0.1, (a, b)


def test_route_same_place_is_zero():
    r = client().get("/api/route?from=gate_main&to=gate_main").json
    assert r["distance_m"] == 0 and r["steps"][-1]["instruction"].startswith("Arrive at")


def test_bad_requests():
    c = client()
    assert c.get("/api/route?from=gate_main").status_code == 400
    assert c.get("/api/route?to=gym_entrance").status_code == 400
    assert c.get("/api/route?from=gate_main&to=nope").status_code == 404
    assert c.get("/api/route?from_lat=abc&from_lng=1&to=gym_entrance").status_code == 400
    assert c.get("/api/rooms/nope").status_code == 404


def test_gps_start_and_off_campus():
    c = client()
    gate = c.get("/api/rooms/gate_main").json
    ok = c.get(f"/api/route?from_lat={gate['lat']}&from_lng={gate['lng']}&to=mount_lhotse")
    assert ok.status_code == 200 and ok.json["from"] == "gate_main"
    assert c.get("/api/route?from_lat=0&from_lng=0&to=gym_entrance").status_code == 422


def test_estimates_gives_walking_minutes():
    c = client()
    r = c.post("/api/estimates", json={"start": "gate_main", "destinations": ["mess", "gym_entrance", "nope"]})
    est = r.json["estimates"]
    assert r.status_code == 200 and set(est) == {"mess", "gym_entrance"}
    assert all(isinstance(m, int) and m >= 1 for m in est.values())
    assert c.post("/api/estimates", json={"start": "nope", "destinations": []}).status_code == 404
    assert c.post("/api/estimates", json={}).status_code == 400


def test_report_is_saved(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "REPORTS_PATH", tmp_path / "reports.jsonl")
    c = client()
    r = c.post("/api/report", json={"start": "gate_main", "destination": "mess", "reason": "Path is blocked"})
    assert r.status_code == 201
    assert "Path is blocked" in (tmp_path / "reports.jsonl").read_text()
    assert c.post("/api/report", json={"details": "no reason"}).status_code == 400
