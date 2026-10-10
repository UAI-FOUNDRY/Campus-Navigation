import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (backend/app/config.py -> repo)
DATA_PATH = Path(os.environ.get("CAMPUS_DATA", ROOT / "data" / "build" / "campus.merged.json"))
WALK_SPEED_MPS = float(os.environ.get("WALK_SPEED_MPS", "1.3"))  # about 78 m per minute
MAX_SNAP_M = float(os.environ.get("MAX_SNAP_M", "150"))  # GPS fix farther than this from any node is "off campus"
ROUTE_CACHE_SIZE = 512
