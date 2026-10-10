"""Checks on the real campus data. These fail when the map has a mistake."""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from validate_graph import validate  # noqa: E402

from app.core.graph import CampusGraph  # noqa: E402

REAL_PATH = ROOT / "data" / "build" / "campus.merged.json"


def test_no_validation_errors():
    if not REAL_PATH.exists():
        return
    g = CampusGraph.load(REAL_PATH)
    errors, _ = validate(g.raw)
    assert errors == []


def test_unique_ids_and_everything_reachable_from_gate():
    if not REAL_PATH.exists():
        return
    g = CampusGraph.load(REAL_PATH)
    assert all(v == 1 for v in Counter(n["id"] for n in g.raw["nodes"]).values())
    _, warnings = validate(g.raw)
    assert not [w for w in warnings if "cannot be reached" in w or "not connected" in w]


def test_every_searchable_place_has_a_name():
    if not REAL_PATH.exists():
        return
    g = CampusGraph.load(REAL_PATH)
    assert all(r["name"] for r in g.rooms.values())
