"""Plan-metre indoor data: georef, display mapping, floors, lifts/stairs, step-free routes and step kinds."""
import math
import sys
from pathlib import Path

from helpers import dijkstra

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from merge_data import merge  # noqa: E402
from planref import Display, Georef  # noqa: E402

from app.core.astar import astar  # noqa: E402
from app.core.graph import CampusGraph  # noqa: E402
from app.core.instructions import build_route  # noqa: E402


def pt(i, t, name, lng, lat):
    return {"type": "Feature", "properties": {"id": i, "type": t, "name": name},
            "geometry": {"type": "Point", "coordinates": [lng, lat]}}


def line(coords):
    return {"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": coords}}


# A building whose plan x axis points east and y axis points south: 1 plan metre = 1 m on the ground.
LAT0, LNG0 = 19.0, 73.0
KX = 111320 * math.cos(math.radians(LAT0))
KY = 111132.0


def ll(x, y):
    return LNG0 + x / KX, LAT0 - y / KY


OUT = {"type": "FeatureCollection", "features": [
    pt("gate_main", "gate", "Main Gate", *ll(-60, 0)),
    pt("door_w", "entrance", "West Door", *ll(0, 0)),
    pt("door_s", "entrance", "South Door", *ll(20, 10)),
    pt("ref_n", "entrance", "North Corner", *ll(0, -30)),
    line([list(ll(-60, 0)), list(ll(0, 0))]),
    line([list(ll(-60, 0)), list(ll(-60, 10)), list(ll(20, 10))]),
    line([list(ll(0, 0)), list(ll(0, -30))]),
]}

GF = {"code": "gf", "floor": 0, "label": "Ground floor", "image": "g.png", "image_size": [400, 300],
      "display_anchors": [[[0, 0], [0, 0]], [[40, 0], [400, 0]], [[0, 30], [0, 300]]],
      "nodes": [{"id": "g_w", "type": "exit", "name": "West exit", "pos": [0, 0]},
                {"id": "g_c", "type": "junction", "name": "", "pos": [20, 0]},
                {"id": "g_s", "type": "exit", "name": "South exit", "pos": [20, 9]},
                {"id": "g_lift", "type": "lift", "name": "Lift", "pos": [30, 0]},
                {"id": "g_stair", "type": "stairs", "name": "Stairs", "pos": [20, -5]},
                {"id": "g_room", "type": "door", "name": "Room G", "pos": [10, 0]}],
      "edges": [{"from": "g_w", "to": "g_room"}, {"from": "g_room", "to": "g_c"}, {"from": "g_c", "to": "g_s"},
                {"from": "g_c", "to": "g_lift"}, {"from": "g_c", "to": "g_stair"}],
      "links": [{"indoor": "g_w", "outdoor": "door_w"}, {"indoor": "g_s", "outdoor": "door_s"}]}
FF = {"code": "ff", "floor": 1, "label": "First floor", "image": "f.png", "image_size": [400, 300],
      "display_anchors": [[[0, 0], [0, 0]], [[40, 0], [400, 0]], [[0, 30], [0, 300]]],
      "nodes": [{"id": "f_lift", "type": "lift", "name": "Lift", "pos": [30, 0]},
                {"id": "f_stair", "type": "stairs", "name": "Stairs", "pos": [20, -5]},
                {"id": "f_c", "type": "junction", "name": "", "pos": [20, 0]},
                {"id": "f_room", "type": "door", "name": "Room F", "pos": [20, 20]}],
      "edges": [{"from": "f_stair", "to": "f_c"}, {"from": "f_lift", "to": "f_c"}, {"from": "f_c", "to": "f_room"}]}
BUILDING = {"georef": {"control_points": [{"outdoor": "door_w", "pos": [0, 0]}, {"outdoor": "door_s", "pos": [20, 10]},
                                          {"outdoor": "ref_n", "pos": [0, -30]}]},
            "vertical": [{"id": "lift", "type": "lift", "name": "Lift", "nodes": ["g_lift", "f_lift"]},
                         {"id": "stairs", "type": "stairs", "name": "Main stairs", "nodes": ["g_stair", "f_stair"]}]}
PLACES = [{"id": "room_f", "name": "Room F", "entry_nodes": ["f_room"], "category": "classroom"},
          {"id": "room_g", "name": "Room G", "entry_nodes": ["g_room"]}]


def build():
    data, errors, warnings = merge(OUT, [GF, FF], PLACES, building=BUILDING)
    assert not errors, errors
    return CampusGraph(data), data, warnings


def go(g, a, b, step_free=False):
    r = astar(g, g.resolve(a), g.resolve(b), step_free)
    return r, build_route(g, r, 1.3, g.node_place.get(r.goal))


def test_georef_recovers_a_known_frame():
    pairs = [((0, 0), ll(0, 0)[::-1]), ((20, 10), ll(20, 10)[::-1]), ((0, -30), ll(0, -30)[::-1])]
    geo = Georef(pairs)
    assert geo.rms < 0.05 and abs(geo.scale - 1) < 0.01
    lat, lng = geo.to_latlng(13, 7)
    x, y = geo.to_plan(lat, lng)
    assert abs(x - 13) < 0.02 and abs(y - 7) < 0.02


def test_display_hits_its_anchors_and_interpolates():
    d = Display([((0, 0), (0, 0)), ((40, 0), (400, 0)), ((0, 30), (0, 300)), ((40, 30), (420, 310))])
    assert d.to_px(40, 30) == (420, 310)
    x, y = d.to_px(20, 15)
    assert 195 <= x <= 215 and 145 <= y <= 160


def test_indoor_nodes_get_gps_pixels_and_floors():
    g, data, _ = build()
    room = g.nodes["f_room"]
    assert room["floor"] == 1 and (room["x"], room["y"]) == (200, 200)
    assert abs(room["lat"] - ll(20, 20)[1]) < 1e-5 and abs(room["lng"] - ll(20, 20)[0]) < 1e-5
    assert [f["code"] for f in data["floors"]] == ["gf", "ff"]


def test_lengths_come_from_the_plan_and_links_from_gps():
    g, data, _ = build()
    e = next(e for e in data["edges"] if {e["from"], e["to"]} == {"g_w", "g_room"})
    assert e["length"] == 10.0 and e["source"] == "plan"
    link = next(e for e in data["edges"] if e["from"] == "door_s")
    assert link["length"] < 1.5          # door_s is 1 m from the South exit dot


def test_stairs_by_default_lift_when_step_free():
    g, _, _ = build()
    r, out = go(g, "gate_main", "room_f")
    kinds = [s["kind"] for s in out["steps"]]
    assert "stairs" in kinds and "lift" not in kinds
    assert [(leg["type"], leg.get("floor")) for leg in out["legs"]] == [("outdoor", None), ("indoor", 0), ("indoor", 1)]
    r2, out2 = go(g, "gate_main", "room_f", step_free=True)
    assert "lift" in [s["kind"] for s in out2["steps"]] and "stairs" not in [s["kind"] for s in out2["steps"]]
    assert out2["duration_s"] > out["duration_s"]          # the lift wait is counted in the time
    assert any("First floor" in s["instruction"] for s in out2["steps"])


def test_route_metres_do_not_include_lift_waiting():
    g, _, _ = build()
    _, out = go(g, "g_lift", "f_lift", step_free=True)
    assert out["distance_m"] == 4.0 and out["duration_s"] > 30


def test_turns_are_read_from_plan_geometry():
    g, _, _ = build()
    _, out = go(g, "g_w", "g_s")      # east 20 m, then south 9 m: a right turn
    assert [s["kind"] for s in out["steps"]] == ["start_walk", "turn_right", "arrive"]


def test_a_star_matches_dijkstra_on_every_pair():
    g, _, _ = build()
    for a in g.nodes:
        for b in g.nodes:
            found, expected = astar(g, a, b), dijkstra(g, a, b)
            assert (found is None) == (expected is None)
            if found:
                assert abs(found.distance - expected) < 1e-6, (a, b)


def test_bad_inputs_are_reported():
    bad = {**GF, "nodes": GF["nodes"] + [{"id": "Bad Id", "type": "door", "name": "x", "pos": [1, 1]}]}
    _, errors, _ = merge(OUT, [bad, FF], PLACES, building=BUILDING)
    assert any("Bad Id" in e for e in errors)
    vert = {**BUILDING, "vertical": [{"id": "v", "type": "lift", "nodes": ["g_lift", "g_room"]}]}
    _, errors, _ = merge(OUT, [GF, FF], PLACES, building=vert)
    assert any("same floor" in e for e in errors)


def test_measured_metres_override_and_warn_when_far_off():
    ff = {**FF, "edges": FF["edges"][:2] + [{"from": "f_c", "to": "f_room", "meters": 50}]}
    data, errors, warnings = merge(OUT, [GF, ff], PLACES, building=BUILDING)
    assert not errors and any("plan says 20.0 m" in w for w in warnings)
    e = next(e for e in data["edges"] if e["to"] == "f_room")
    assert e["length"] == 50 and e["source"] == "measured"
