from pathlib import Path

from app.core.graph import CampusGraph
from app.core.search import PlaceIndex

REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "build" / "campus.merged.json"


def index():
    return PlaceIndex(CampusGraph.load(REAL_PATH).rooms.values())


def first(q):
    hits = index().search(q)
    return hits[0]["id"] if hits else None


def test_the_four_v1_places_are_found_by_their_aliases():
    assert first("everest") == "mount_everest_130"
    assert first("130") == "mount_everest_130"
    assert first("lhotse") == "mount_lhotse"
    assert first("canteen") == "mess"
    assert first("cafeteria") == "mess"
    assert first("badminton court") == "admin_lobby"


def test_typos_still_find_the_place():
    assert first("evrest") == "mount_everest_130"
    assert first("lobbyy") == "admin_lobby"


def test_nonsense_finds_nothing():
    assert index().search("zzzzzz") == []
