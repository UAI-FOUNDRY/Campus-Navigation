"""A* tests. Run from backend/:  pytest"""
from pathlib import Path

from helpers import dijkstra

from app.core.astar import astar
from app.core.graph import CampusGraph

HERE = Path(__file__).parent
TINY = CampusGraph.load(HERE / "fixtures" / "tiny_campus.json")
REAL_PATH = HERE.parents[1] / "data" / "build" / "campus.merged.json"


def test_start_equals_goal():
    r = astar(TINY, "A", "A")
    assert r.nodes == ["A"] and r.edges == [] and r.distance == 0.0


def test_known_shortest_path():
    # the direct A-D edge (67.3 m) beats going round A-B-C-D (131.1 m)
    r = astar(TINY, "A", "D")
    assert r.nodes == ["A", "D"] and abs(r.distance - 67.3) < 0.01


def test_path_through_several_nodes():
    r = astar(TINY, "A", "C")
    assert r.nodes == ["A", "B", "C"] and abs(r.distance - (44.5 + 42.1)) < 0.01


def test_unreachable_node_returns_none():
    assert astar(TINY, "A", "E") is None


def test_unknown_node_raises():
    try:
        astar(TINY, "A", "nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_restricted_edge_is_never_used():
    result = astar(TINY, "A", "F")
    assert result is not None
    assert "restricted" not in [TINY.edges[e]["type"] for e in result.edges]


def test_accessible_only_avoids_stairs():
    normal = astar(TINY, "C", "F")
    access = astar(TINY, "C", "F", accessible_only=True)
    assert normal is not None
    assert access is None or "steps" not in [TINY.edges[e]["type"] for e in access.edges]


def test_several_goals_picks_the_nearest():
    r = astar(TINY, "A", ["C", "B"])  # B is nearer than C
    assert r.goal == "B" and abs(r.distance - 44.5) < 0.01


def test_several_starts_picks_the_nearest():
    r = astar(TINY, ["A", "C"], "D")  # C-D is 44.5, A-D is 67.3
    assert r.start == "C" and abs(r.distance - 44.5) < 0.01


def test_matches_dijkstra_on_every_pair_of_the_real_campus():
    if not REAL_PATH.exists():
        return
    g = CampusGraph.load(REAL_PATH)
    ids = list(g.nodes)
    for a in ids:
        for b in ids:
            found, expected = astar(g, a, b), dijkstra(g, a, b)
            if expected is None:
                assert found is None
            else:
                assert found is not None and abs(found.distance - expected) < 1e-6, (a, b)
