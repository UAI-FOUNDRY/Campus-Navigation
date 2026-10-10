"""Tests for tools/merge_data.py and for routing over a small outdoor + indoor graph with known numbers."""
import sys
from pathlib import Path

from helpers import dijkstra

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from merge_data import merge  # noqa: E402

from app.core.astar import astar  # noqa: E402
from app.core.graph import CampusGraph  # noqa: E402
from app.core.instructions import build_route  # noqa: E402


def pt(i, t, name, lng, lat):
    return {"type": "Feature", "properties": {"id": i, "type": t, "name": name},
            "geometry": {"type": "Point", "coordinates": [lng, lat]}}


def line(coords):
    return {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": coords}}


OUTDOOR = {"type": "FeatureCollection", "features": [
    pt("gate_main", "gate", "Main Gate", 73.0000, 19.0000),
    pt("j1", "junction", "", 73.0009, 19.0000),
    pt("back_door", "entrance", "Back Door", 73.0009, 19.0009),
    line([[73.0000, 19.0000], [73.0009, 19.0000], [73.0009, 19.0009]]),
]}


def indoor(meters=30, link_to="back_door"):
    return {"floor": 0, "image": "g.png", "image_size": [400, 300], "nodes": [
        {"id": "X", "type": "door", "name": "Hall door", "x": 100, "y": 100},
        {"id": "Y", "type": "door", "name": "Room Y", "x": 200, "y": 100},
        {"id": "Z", "type": "door", "name": "Room Z", "x": 100, "y": 200}],
        "edges": [{"label": "xy", "from": "X", "to": "Y", "meters": meters},
                  {"label": "xz", "from": "X", "to": "Z", "meters": 20}],
        "links": [{"label": "door", "indoor": "X", "outdoor": link_to, "meters": 50}]}


PLACES = [{"id": "hall", "name": "Hall", "aliases": ["main hall"], "entry_nodes": ["X", "back_door"]},
          {"id": "room_y", "name": "Room Y", "entry_nodes": ["Y"]},
          {"id": "room_z", "name": "Room Z", "entry_nodes": ["Z"]}]


def build(ind=None, places=PLACES):
    data, errors, warnings = merge(OUTDOOR, [ind or indoor()], places)
    assert not errors, errors
    return CampusGraph(data), warnings


def route(g, a, b):
    r = astar(g, g.resolve(a), g.resolve(b))
    return r, build_route(g, r, 1.3, g.node_place.get(r.goal))


def test_place_with_two_entrances_uses_the_nearer_one():
    g, _ = build()
    r, out = route(g, "gate_main", "hall")
    assert r.goal == "back_door"                      # the outdoor door is nearer than X (50 m further)
    assert [leg["type"] for leg in out["legs"]] == ["outdoor"]
    assert out["to_name"] == "Hall"


def test_gate_to_indoor_room_has_outdoor_then_indoor_legs():
    g, _ = build()
    r, out = route(g, "gate_main", "room_z")
    outdoor, inside = out["legs"]
    assert outdoor["type"] == "outdoor" and inside["type"] == "indoor"
    assert inside["distance_m"] == 70.0               # 50 m link + 20 m
    assert [p["id"] for p in inside["points"]] == ["X", "Z"]
    assert abs(out["distance_m"] - (outdoor["distance_m"] + 70.0)) < 0.2
    assert any(s["instruction"].startswith("Go inside") for s in out["steps"])
    assert out["steps"][-1]["instruction"] == "Arrive at Room Z"


def test_starting_from_a_place_with_two_doors():
    g, _ = build()
    r, out = route(g, "hall", "room_y")
    assert r.start == "X" and r.distance == 30.0
    assert [leg["type"] for leg in out["legs"]] == ["indoor"] and out["polyline"] == []


def test_indoor_only_route_points_are_pixels_on_the_plan():
    g, _ = build()
    _, out = route(g, "room_y", "room_z")
    leg = out["legs"][0]
    assert leg["image"] == "g.png" and leg["image_size"] == [400, 300]
    assert [(p["x"], p["y"]) for p in leg["points"]] == [(200, 100), (100, 100), (100, 200)]


def test_missing_meters_is_an_error_but_optional_is_a_warning():
    ind = indoor(meters=None)
    _, errors, _ = merge(OUTDOOR, [ind], PLACES)
    assert any("no 'meters'" in e for e in errors)
    ind["edges"][0]["optional"] = True
    data, errors, warnings = merge(OUTDOOR, [ind], PLACES)
    assert not errors and any("no 'meters'" in w for w in warnings)


def test_link_to_a_missing_outdoor_dot_is_a_warning_and_leaves_indoor_unjoined():
    data, errors, warnings = merge(OUTDOOR, [indoor(link_to="not_drawn_yet")], [])
    assert not errors
    assert any("not_drawn_yet" in w for w in warnings) and any("cannot be reached" in w for w in warnings)


def test_a_place_is_not_listed_twice():
    g, _ = build()
    assert "back_door" not in g.rooms and "hall" in g.rooms  # back_door is now an entrance of 'hall'


def test_unknown_entry_node_is_an_error():
    _, errors, _ = merge(OUTDOOR, [indoor()], [{"id": "p", "name": "P", "entry_nodes": ["nope"]}])
    assert any("unknown entry" in e for e in errors)


def test_a_too_good_indoor_shortcut_does_not_break_a_star():
    ind = indoor()
    ind["nodes"].append({"id": "W", "type": "door", "name": "W", "x": 300, "y": 200})
    ind["edges"].append({"label": "zw", "from": "Z", "to": "W", "meters": 5})
    outdoor = {"type": "FeatureCollection", "features": OUTDOOR["features"] + [
        pt("far_door", "entrance", "Far Door", 73.0030, 19.0000),
        line([[73.0009, 19.0000], [73.0030, 19.0000]])]}
    ind["links"].append({"label": "bogus", "indoor": "W", "outdoor": "far_door", "meters": 5})
    data, errors, _ = merge(outdoor, [ind], [])
    assert not errors
    g = CampusGraph(data)
    assert g.scale < 1.0  # the indoor shortcut is shorter than the straight line, so the heuristic is scaled down
    for a in g.nodes:
        for b in g.nodes:
            found, expected = astar(g, a, b), dijkstra(g, a, b)
            assert (found is None) == (expected is None)
            if found:
                assert abs(found.distance - expected) < 1e-6, (a, b)
