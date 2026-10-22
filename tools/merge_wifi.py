"""Merge the Wi-Fi fingerprints the app sent (data/wifi/contributions.jsonl) into data/wifi/fingerprints.json.

Run from the repo root:
    python tools/merge_wifi.py            # merge, keep the inbox
    python tools/merge_wifi.py --clear    # merge, then empty the inbox

Keeps the newest 8 fingerprints per spot and drops ones for spots that are no longer on the map. Commit
data/wifi/fingerprints.json afterwards so every deployment of the backend serves them.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.api.wifi import load_samples, newest_per_spot  # noqa: E402
from app.core.graph import CampusGraph  # noqa: E402


def main():
    graph = CampusGraph.load(config.DATA_PATH)
    merged = newest_per_spot(load_samples(), graph)
    data = {
        "about": "Wi-Fi fingerprints of campus spots (access point id -> signal dBm). Filled by tools/merge_wifi.py "
                 "from what the app sends (data/wifi/contributions.jsonl). See docs/live-tracking.md.",
        "samples": merged,
    }
    config.WIFI_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.WIFI_PATH.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    spots = len({s["spot"] for s in merged})
    print(f"{len(merged)} fingerprints for {spots} spots -> {config.WIFI_PATH}")
    if "--clear" in sys.argv and config.WIFI_CONTRIB_PATH.exists():
        config.WIFI_CONTRIB_PATH.write_text("", encoding="utf-8")
        print("inbox cleared")


if __name__ == "__main__":
    main()
