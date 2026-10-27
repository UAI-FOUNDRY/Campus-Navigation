"""Routes on the real campus data that must keep working. If one fails after a map edit, the edit broke a path."""
import sys
from pathlib import Path

from app import create_app

ROOT = Path(__file__).resolve().parents[2]
REAL_PATH = ROOT / "data" / "build" / "campus.merged.json"
sys.path.insert(0, str(ROOT / "tools"))


def client():
    return create_app(REAL_PATH).test_client()


def route(c, a, b, extra=""):
    r = c.get(f"/api/route?from={a}&to={b}{extra}")
    assert r.status_code == 200, (a, b, r.json)
    return r.json


def test_every_place_is_reachable_from_the_main_gate():
    c = client()
    places = c.get("/api/search?q=").json
    assert len(places) >= 60
    for p in places:
        route(c, "gate_main", p["id"])


def test_version_one_places_have_sensible_lengths():
    c = client()
    for place, lo, hi in [("admin_lobby", 140, 220), ("mess", 150, 240), ("mount_everest_130", 150, 230),
                          ("mount_lhotse", 130, 210)]:
        d = route(c, "gate_main", place)["distance_m"]
        assert lo < d < hi, (place, d)


def test_everest_to_logan_uses_the_block_a_side_door():
    r = route(client(), "mount_everest_130", "mountlogan_entrance")
    assert r["distance_m"] < 100                                  # was 199 m round the quadrangle before v5
    assert "a0_lobbya_w_exit" in r["nodes"]


def test_upper_floors_use_stairs_and_step_free_uses_a_lift():
    c = client()
    r = route(c, "gate_main", "mount_nanda_devi")
    kinds = [s["kind"] for s in r["steps"]]
    assert "stairs" in kinds and r["floors"] == [0, 2]
    assert [leg["floor"] for leg in r["legs"] if leg["type"] == "indoor"] == [0, 2]
    a = route(c, "gate_main", "mount_nanda_devi", "&accessible=1")
    assert "lift" in [s["kind"] for s in a["steps"]] and "stairs" not in [s["kind"] for s in a["steps"]]


def test_indoor_legs_carry_the_floor_picture_and_gps():
    r = route(client(), "gate_main", "mount_kangchenjunga")
    first = [leg for leg in r["legs"] if leg["type"] == "indoor" and leg["floor"] == 1][0]
    assert first["image"] == "first.png" and len(first["image_size"]) == 2
    assert all("x" in p and "lat" in p for p in first["points"])


def test_floors_endpoint_lists_three_floors():
    floors = client().get("/api/floors").json["floors"]
    assert [f["code"] for f in floors] == ["gf", "ff", "sf"]
    assert [f["image"] for f in floors] == ["ground.png", "first.png", "second.png"]


def test_outdoor_map_has_no_breaking_mistakes():
    import json

    from check_map import check, newest

    path = newest(ROOT / "data" / "outdoor")
    problems = [r for r in check(json.loads(path.read_text(encoding="utf-8")))
                if r.split()[0] in ("BROKEN", "CROSSING", "SKIPPED", "ALONE")]
    assert problems == [], problems


def test_gps_start_inside_the_building_needs_the_floor():
    c = client()
    everest = c.get("/api/rooms/mount_everest_130").json
    lat, lng = everest["gps"]["lat"], everest["gps"]["lng"]
    r = c.get(f"/api/route?from_lat={lat}&from_lng={lng}&to=mount_lhotse").json
    assert not r["from"].startswith("a0_")                       # without a floor: snapped to an outdoor dot
    r = c.get(f"/api/route?from_lat={lat}&from_lng={lng}&from_floor=0&to=mount_lhotse").json
    assert r["from"].startswith("a0_")                           # with the floor: snapped inside, on the ground floor
    assert c.get(f"/api/route?from_lat={lat}&from_lng={lng}&from_floor=x&to=mount_lhotse").status_code == 400


def test_shops_and_places_inside_other_places():
    c = client()
    psych = route(c, "gate_main", "psychology_lab")
    assert psych["steps"][-1]["instruction"] == "Arrive at Psychology Lab, inside the Library"
    assert psych["to_within"] == "Library"
    assert route(c, "gate_main", "atm")["steps"][-1]["instruction"].startswith("Arrive at ATM, inside")
    coffee = route(c, "gate_main", "aspretto")
    assert coffee["to_name"].startswith("Aspretto") and coffee["floors"] == [0] and coffee["distance_m"] < 260
    hit = c.get("/api/rooms?q=asperetto").json["results"][0]
    assert hit["id"] == "aspretto"


def test_turns_name_the_corridor_and_lines_stay_clean():
    c = client()
    r = route(c, "gate_main", "registrar_office")
    texts = " | ".join(s["instruction"] for s in r["steps"])
    assert "into the Lobby" in texts and "the corridor" not in texts
    indoor = [leg for leg in r["legs"] if leg["type"] == "indoor"][0]
    pts = indoor["points"]
    # no dot on a straight line: every unnamed middle point is a real bend
    import math
    for p, q, s in zip(pts, pts[1:], pts[2:]):
        if q["name"]:
            continue
        a1 = math.atan2(q["y"] - p["y"], q["x"] - p["x"])
        a2 = math.atan2(s["y"] - q["y"], s["x"] - q["x"])
        assert abs((math.degrees(a2 - a1) + 180) % 360 - 180) >= 8


def test_estimates_agree_with_routes():
    c = client()
    ids = [p["id"] for p in c.get("/api/search?q=").json]
    est = c.post("/api/estimates", json={"start": "gate_main", "destinations": ids}).json["estimates"]
    assert set(est) == set(ids)
    for pid in ("library", "mount_nanda_devi", "aspretto", "mess_first_floor"):
        assert est[pid] == max(1, int(route(c, "gate_main", pid)["duration_s"] / 60 + 0.5))


def test_attic_lab_is_up_the_spiral_staircase():
    r = route(client(), "gate_main", "faculty_room_15")
    assert r["floors"] == [0, 2]
    assert any(s["kind"] == "stairs" and "up to Innovation Lab" in s["instruction"] for s in r["steps"])
    assert r["steps"][-1]["instruction"].endswith("inside the Innovation Lab (Incubation Launchpad)")


def test_map_pins_only_outdoor_places():
    rooms = client().get("/api/rooms?q=&limit=500").json["results"]
    pinned = [r for r in rooms if r["lat"] is not None]
    assert all(not r["indoor"] for r in pinned)
    assert {"gym_entrance", "turf_entrance"} <= {r["id"] for r in pinned}


def test_stairs_only_place_explains_step_free():
    r = client().get("/api/route?from=quad_south_entrance&to=innovation_lab&accessible=1")
    assert r.status_code == 422 and r.json["error"]["code"] == "no_step_free_route"
    assert "only be reached by stairs" in r.json["error"]["message"]


def test_office_wings_are_one_stop_each():
    c = client()
    for old, wing in [("vice chancellor", "admin_wing"), ("director cabin 6", "faculty_directors_wing"),
                      ("faculty room 08", "faculty_offices_sf")]:
        assert c.get(f"/api/rooms?q={old}").json["results"][0]["id"] == wing
        assert route(c, "gate_main", wing)["steps"][-1]["kind"] == "arrive"
