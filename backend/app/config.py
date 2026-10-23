import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (backend/app/config.py -> repo)
DATA_PATH = Path(os.environ.get("CAMPUS_DATA", ROOT / "data" / "build" / "campus.merged.json"))
WALK_SPEED_MPS = float(os.environ.get("WALK_SPEED_MPS", "1.3"))  # about 78 m per minute
MAX_SNAP_M = float(os.environ.get("MAX_SNAP_M", "150"))  # GPS fix farther than this from any node is "off campus"
ROUTE_CACHE_SIZE = 512
REPORTS_PATH = Path(os.environ.get("CAMPUS_REPORTS", ROOT / "data" / "reports.jsonl"))  # "Report a problem" inbox
# "Report a problem" -> GitHub issues: set GITHUB_TOKEN (a fine-grained token with Issues: read and write on
# REPORTS_REPO only) in the host's environment. Without a token, reports only go to REPORTS_PATH.
REPORTS_REPO = os.environ.get("REPORTS_REPO", "UAI-FOUNDRY/Campus-Navigation")
REPORTS_LABEL = os.environ.get("REPORTS_LABEL", "report")
REPORTS_ISSUES_PER_DAY = int(os.environ.get("REPORTS_ISSUES_PER_DAY", "30"))   # past this, only the file
WIFI_PATH = Path(os.environ.get("CAMPUS_WIFI", ROOT / "data" / "wifi" / "fingerprints.json"))  # committed fingerprints
WIFI_CONTRIB_PATH = Path(os.environ.get("CAMPUS_WIFI_INBOX", ROOT / "data" / "wifi" / "contributions.jsonl"))  # sent by apps

# ---- limits (see app/web.py) ----
MAX_BODY_BYTES = 16 * 1024                       # POST bodies (report, estimates) are tiny
REPORTS_MAX_BYTES = int(os.environ.get("REPORTS_MAX_BYTES", 5 * 1024 * 1024))   # stop appending past this size
WIFI_MAX_BYTES = int(os.environ.get("WIFI_MAX_BYTES", 20 * 1024 * 1024))         # Wi-Fi fingerprint inbox
RATE_LIMITS_ON = os.environ.get("RATE_LIMITS", "1") != "0"
RATE_READ_PER_MIN = int(os.environ.get("RATE_READ_PER_MIN", "120"))     # search, route, floors... per client
RATE_HEAVY_PER_MIN = int(os.environ.get("RATE_HEAVY_PER_MIN", "40"))    # POST /api/route, /api/estimates
RATE_REPORT_PER_MIN = int(os.environ.get("RATE_REPORT_PER_MIN", "2"))   # "Report a problem"
RATE_WIFI_PER_MIN = int(os.environ.get("RATE_WIFI_PER_MIN", "10"))      # Wi-Fi fingerprints sent by the app
TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", "0"))           # 1 on Render (its proxy sets X-Forwarded-For)
