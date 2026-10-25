# Campus Navigation: backend, map data and tools

> Turn-by-turn walking directions across Universal AI University, Karjat: from the Main Gate to any classroom, lab,
> office or facility, outdoors and on all three floors of the main building.

This repository holds the **map data**, the **routing server** (Python + Flask + A\*) and the **mapping tools**.
The mobile app lives in [`UAI-FOUNDRY/CampusNav-Flutter`](https://github.com/UAI-FOUNDRY/CampusNav-Flutter) and talks
to this server over a small JSON API.

```
Search "Psychology Lab"  ->  Start at Main Gate and walk 115 m
                             Bear right at the junction and walk 30 m
                             Go inside through Quadrangle South Entrance
                             Walk 45 m through the Quadrangle
                             Turn left into the North corridor and walk 5 m
                             Turn right into the Library and walk 12 m
                             Arrive at Psychology Lab, inside the Library
```

**At a glance**

- 356 map points (38 outdoor, 318 indoor on 3 floors), 387 walkable connections, 137 searchable places
- Shortest routes by A\* in a few milliseconds, with step-free (lift and ramp) routes
- Indoor map built from the architect's CAD plans, tied to GPS (about 1.7 m fit)
- Free to run: Flask on Render's free plan, OpenStreetMap in the app, no paid APIs or hardware
- 85 automated tests, run on every push by GitHub Actions

---

## Contents

1. [How it works](#how-it-works)
2. [Repository layout](#repository-layout)
3. [Quick start](#quick-start)
4. [The map data](#the-map-data)
5. [Routing: A\* and search](#routing-a-and-search)
6. [API](#api)
7. [Changing the map](#changing-the-map)
8. [Indoor positioning: QR, sensors and Wi-Fi](#indoor-positioning-qr-sensors-and-wi-fi)
9. [Privacy and security](#privacy-and-security)
10. [Performance](#performance)
11. [Deployment](#deployment)
12. [Testing](#testing)
13. [Configuration](#configuration)
14. [Roadmap and known limits](#roadmap-and-known-limits)
15. [Team](#team)

---

## How it works

```
 private/ (never in git)            data/ (in git)                       tools/merge_data.py
 architect CAD plans  --derived-->  outdoor_draft_v6.geojson      --->   corridors -> dots and lines
 master plan                        indoor/gf.json ff.json sf.json       lengths, GPS, picture x/y
                                    indoor/building.json                 checks
                                    places.json                          |
                                                                         v
                                                         data/build/campus.merged.json (one file, committed)
                                                                         |
                                                                         v
                                              backend/  Flask API: loads the graph once, A* routes,
                                                        search, step text, caching, limits
                                                                         |  JSON over HTTPS
                                                                         v
                                              CampusNav-Flutter app: map, floor pictures, GPS, QR,
                                                        live guidance
```

1. **Mappers edit plain files.** Outdoor paths are drawn in geojson.io. Indoor corridors and doors are placed with the
   browser-based node editor on top of the architect's plans. Places and their names come from the signage.
2. **One build step** (`tools/merge_data.py`) turns them into a single graph with a length for every line, a GPS
   position for every point (indoors too), and the pixel position on the public floor pictures. It refuses broken
   data.
3. **The server** loads that file once, answers searches and routes, and writes readable steps.
4. **The app** draws the outdoor part on a map and each floor on its signage picture, and guides the user live.

The architect's plans never leave the mappers' machines. The repo, the server and the app only see derived numbers
and the public signage pictures.

---

## Repository layout

- `backend/`: Flask API and the routing engine
    - `app/core/astar.py`: A\* (one route) and Dijkstra (walk times to every place)
    - `app/core/heuristics.py`: the A\* heuristic (scaled straight-line distance)
    - `app/core/graph.py`: the in-memory graph, place lookup, public copy of the graph
    - `app/core/instructions.py`: turns a path into steps and drawable legs
    - `app/core/search.py`: typo-tolerant place search (rapidfuzz)
    - `app/api/`: endpoints: `routes`, `rooms`, `meta`, `estimates`, `compat`, `report`, `wifi`
    - `app/web.py`: security headers, rate limits, ETag/304, gzip, request limits
    - `tests/`: 85 pytest tests (tiny fixture graph + the real campus)
- `data/`
    - `outdoor/outdoor_draft_vN.geojson`: outdoor paths and entrances (the newest N is used; v6 today)
    - `indoor/gf.json`, `ff.json`, `sf.json`: one file per floor (corridors, doors, lifts, stairs, exits)
    - `indoor/building.json`: GPS tie-in, lifts and staircases between floors, floor-change costs
    - `places.json`: everything students can search for, with aliases and categories
    - `wifi/fingerprints.json`: reviewed Wi-Fi fingerprints of campus spots
    - `build/campus.merged.json`: **generated**, committed; the only file the server reads
- `tools/`: build, check and mapping tools (see [Changing the map](#changing-the-map))
    - `node_editor/index.html`: indoor editor, opens in any browser, no install
- `app/assets/floorplans/`: the public signage pictures (`ground.png`, `first.png`, `second.png`)
- `docs/`: detailed guides (data format, mapping guide, API reference, edge cases, live tracking, street view,
  indoor survey checklist)
- `private/`: the architect's plans and anything made from them. **Git-ignored. Never commit or share.**
- `render.yaml`: one-click deployment on Render
- `.github/workflows/backend-tests.yml`: runs the tests on every push and pull request to `main`

---

## Quick start

Requires Python 3.12 (3.10+ works) and Git.

**Windows (PowerShell)**

```powershell
git clone https://github.com/UAI-FOUNDRY/Campus-Navigation.git
cd Campus-Navigation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt

python tools\merge_data.py              # build data\build\campus.merged.json
cd backend
python -m pytest -q                     # 85 passed
python -m flask --app wsgi run --host 0.0.0.0 --port 5000
```

**macOS / Linux**

```bash
git clone https://github.com/UAI-FOUNDRY/Campus-Navigation.git && cd Campus-Navigation
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python tools/merge_data.py
cd backend && python -m pytest -q && python -m flask --app wsgi run --host 0.0.0.0 --port 5000
```

Try it in a browser:

- `http://127.0.0.1:5000/api/health`
- `http://127.0.0.1:5000/api/rooms?q=library`
- `http://127.0.0.1:5000/api/route?from=gate_main&to=psychology_lab`

**Run the app against it.** Put the phone on the same Wi-Fi, find the laptop's address (`ipconfig` / `ip addr`), then
in the Flutter repo:

```
flutter run --dart-define=USE_MOCK=false --dart-define=API_BASE_URL=http://<laptop-ip>:5000
```

The Android emulator reaches the laptop at `http://10.0.2.2:5000`.

Tips:

- "Fatal error in launcher" from `pytest` or `flask` means the virtual environment was moved. Recreate `.venv`, and use
  `python -m pytest` / `python -m flask`.
- The server reads the graph once at start: restart it after `merge_data.py`.

---

## The map data

All files are plain JSON or GeoJSON, edited by people and checked by tools. Every point has an **ID that never
changes**; places, QR codes and the app refer to points only by ID.

### Outdoor: `data/outdoor/outdoor_draft_v6.geojson`

Drawn in [geojson.io](https://geojson.io) on satellite imagery.

- **Points:** `gate`, `entrance` (a door, with a `name`), `junction` (where paths meet)
- **Lines:** `path` (default), `steps`, `ramp`, `restricted` (never used)
- Lines join only through a dot. `tools/check_map.py` finds lines that end next to another line without a dot,
  crossings, duplicates and lonely dots.

### Indoor: `data/indoor/gf.json`, `ff.json`, `sf.json`

Read from the architect's CAD plans (vector PDFs).

- **Plan metres.** Positions are `pos: [x, y]` in metres on the plan sheet: x to the right, y down, 6.30 PDF points =
  1 m (checked against the printed room widths). The three floors share one frame, so a lift is at the same spot on
  every floor.
- **Corridors and doors.**
    - A corridor is a straight centre line through the walkway (`path`).
    - A door is a dot placed on the door mark of the plan with `"on": "<corridor id>"`; the build joins it to the
      corridor with a short, square stub.
    - Adding a room is one line of data.
    - Open areas (Library, Lobby, Quadrangle) get drawn aisles instead of diagonal lines, so routes look clean.

```json
{"id": "a0_c_west", "name": "Block A walkway", "type": "corridor",
 "path": ["a0_ww_n", "a0_ww_everest", "a0_ww_lobbya", "a0_ww_lhotse", "a0_ww_s"]}

{"id": "a0_everest_door", "type": "door", "name": "Mount Everest 130", "pos": [29.29, 63.89], "on": "a0_c_west"}
```

- **Corridor names** are what turns say: "Turn left **into the North corridor**".
- **Staircases inside one floor** (the spiral stair up to the attic Innovation Lab) are an edge with
  `"climb": "up"` and get their own step.
- **`verify`** marks a dot placed from the plan where the building may differ; `docs/indoor-survey-checklist.md`
  lists them.
- **Exits** link to an outdoor dot (`links`), so a route can go in and out of the building.

### Floors, lifts and GPS: `data/indoor/building.json`

- **Vertical connectors:** two lifts and four staircases (Block A, the Block B spiral, the cafeteria and the library stairs) join the floors. Every pair of floors is connected, so one
  ride can skip a floor.
- **Floor-change costs:** stairs = 12 m + 20 s per floor; lift = 4 m + 60 s wait + 6 s per floor.
- **GPS tie-in (georef):** seven doors on the building's facade exist both on the plan and on the outdoor map. A best-fit
  similarity transform from those pairs gives every indoor point a latitude and longitude (about 1.7 m error).

### Places: `data/places.json`

What students search for. Names and aliases come from the **signage** (the building as it is today, which wins over
the plan).

```json
{"id": "psychology_lab", "name": "Psychology Lab", "aliases": ["psychology"],
 "entry_nodes": ["a0_psychology_lab"], "building": "Main building", "category": "lab", "within": "library"}
```

- **`entry_nodes`:** every door into the place, indoor or outdoor. The router picks the nearest.
- **`within`:** "inside the Library" in search results and in the arrival step.
- **Shared doors:** several places may share one door. Yummy Waffle, Vending and the ATM are in one snack room, and
  each still arrives with its own name.
- **`category`:** classroom, lab, library, food, office, facility, washroom, auditorium, shop.

### Floor pictures: `app/assets/floorplans/`

The public signage pictures the app shows. They are not to scale, so each floor's `display_anchors` fit plan metres
to picture pixels, and the build squares straight corridors up on the picture so routes draw as clean right angles.

Full field-by-field reference: [`docs/data-format.md`](docs/data-format.md).

---

## Routing: A\* and search

### From a search to a route

1. **Search.** The typed text is matched against every place name and alias with
   [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz): exact, prefix and substring matches first, then fuzzy matches,
   so "kilimanjro" and "asperetto" still work.
2. **Resolve.** The chosen place becomes its door nodes; the start is a place, a node (from a QR code) or a GPS fix
   snapped to the nearest outdoor point (or indoor point on a known floor).
3. **Search the graph with A\*** for the cheapest path to the nearest door.
4. **Write the steps and legs** the app shows and draws.

### Why A\*

A\* expands points in order of **f(n) = g(n) + h(n)**:

- **g(n):** the real cost from the start to the point
- **h(n):** an estimate of the cost still to go

It returns the same optimal path as Dijkstra while exploring far fewer points, because the estimate pulls it toward
the goal. BFS was ruled out because it counts hops, not metres. Greedy best-first was ruled out because it can return
longer routes.

### How A\* is used here

- **Cost = walking time, expressed in metres.**
    - Every edge has a length.
    - Lifts and stairs also have extra seconds, converted at 1.3 m/s.
    - So A\* can fairly weigh a far lift against nearby stairs. With these costs it takes the stairs for one or two
      floors and the lift only for step-free routes.
- **Heuristic:** straight-line (haversine) distance to the nearest goal, multiplied by a safety factor (about 0.99).
    - At start-up the server measures the smallest ratio of real path to straight line over the whole graph and
      scales by it.
    - So the estimate **never overestimates**: the heuristic is admissible, and every route is provably the shortest.
    - A point without GPS uses 0, which is always safe.
- **Several starts and goals in one search.** All entrances of the destination are goals; the first one reached is
  the nearest. All candidate starts go in the queue together.
- **Step-free.** `accessible=1` skips `steps` edges and staircases and uses lifts and ramps. A place reachable only by
  stairs answers `no_step_free_route` with a clear message.
- **Restricted edges** (a locked door) are never used.
- **Implementation details:**
    - A min-heap with a counter for ties, so results are deterministic.
    - Nodes are reopened when a cheaper path appears, so the result stays optimal even if the heuristic is not
      perfectly consistent.
    - The path is rebuilt from `came_from` links.
- **Cache.** The map does not change while the server runs, so the last 512 routes are cached.
- **Walk-time labels** ("3 min walk" for every place) use **one Dijkstra** from the start instead of one A\* per
  place: with no single goal, a heuristic cannot help. About 2 ms for 137 places.

### From a path to directions

- **Short wiggles fold away.** Moves under 3 m (door to corridor) are folded into the next instruction.
- **Turns** are worked out from the bearings on the plan and named by the corridor or area the route enters: "Turn
  right into the Library".
- **The last few metres** become "Mount Everest 130 is on your left".
- **Floor changes** are their own step: "Take the Staircase (Block A) up to the Second floor".
- **Arrival** says where a room sits: "Arrive at Psychology Lab, inside the Library".
- **Legs for drawing:** one outdoor leg (a GPS line) and one indoor leg per floor (picture pixels and GPS per point).
  Points on a straight line are dropped, so the app only draws real bends.

---

## API

Base URL: your server, e.g. `http://127.0.0.1:5000`. Every error is `{"error": {"code": "...", "message": "..."}}`.

**Places and map**

- `GET /api/health`: `{"status": "ok"}`
- `GET /api/graph`: every place, point and floor in one call. A public copy without plan metres, notes or `verify`
  remarks. `ETag` = the map version.
- `GET /api/graph/version`: the current map version and counts
- `GET /api/floors`: floor pictures and their pixel sizes
- `GET /api/rooms?q=<text>&limit=8`: search (empty `q` lists places, up to 500). Results carry `floor`, `x`/`y` on the
  floor picture, `lat`/`lng` only for places with an outdoor door, `gps` for indoor places, `within_name`.
- `GET /api/rooms/<id>`: one place

**Routes**

- `GET /api/route?from=<id>&to=<id>[&accessible=1]`
    - Also `from_lat`, `from_lng`, optional `from_floor` instead of `from`.
    - Returns `distance_m`, `duration_s`, `floors`, `steps` (each with `kind`: `start_walk`, `walk`, `turn_left`,
      `turn_right`, `enter`, `exit`, `stairs`, `lift`, `arrive`), `legs`, `polyline` and `to_within`.
- `POST /api/estimates` with `{"start", "destinations": [...]}` returns walking minutes for many places.
- App contract: `GET /api/search?q=` (plain list) and `POST /api/route` with `{"start", "destination", "step_free"}`.

**Feedback and positioning**

- `POST /api/report` with `{"start", "destination", "reason", "details"?, "step"?, "step_free"?}`.
    - Appends to `data/reports.jsonl`.
    - With `GITHUB_TOKEN` set, it also opens a GitHub issue (labelled `report`, at most 30 a day).
- `GET /api/wifi`: reviewed Wi-Fi fingerprints of campus spots, used to recognise the room and floor indoors.
- `POST /api/wifi` with `{"spot", "floor", "aps": {"<bssid>": dBm}}` adds a fingerprint when a user confirms where
  they are.

**Error codes**

- `400 bad_request`, `404 not_found`, `405 method_not_allowed`, `413 too_large`
- `422 no_route`, `no_step_free_route`, `off_campus`
- `429 rate_limited` (with `Retry-After`)
- `503 inbox_full`

Full reference with example responses: [`docs/api.md`](docs/api.md).

---

## Changing the map

After **any** change run the three commands, then commit `data/` (including `data/build/campus.merged.json`) and
restart or redeploy the server:

```
python tools/merge_data.py          # build; refuses broken data, warns about suspicious data
python tools/check_routes.py --all  # Main Gate -> every place (add --step-free too)
cd backend ; python -m pytest       # 85 tests
```

**Common changes**

- **A room is renamed:** in `places.json` change `name` and put the old name in `aliases`. Never change an `id`.
- **A new room on a corridor:**
    1. In the node editor, add a door dot on the door mark.
    2. Pick its corridor under "sits on corridor".
    3. Add a place with that dot in `entry_nodes`.
- **A wall or corridor moved:** drag the corridor points or the door dot in the node editor.
- **A door is locked:** set that line's `type` to `restricted`. Delete it again when it reopens.
- **A tape measurement disagrees with the plan:** put `"meters": <tape>` on that line. The build warns when the two
  differ a lot.
- **New outdoor path:** edit the newest GeoJSON in geojson.io, save it as the next `outdoor_draft_vN.geojson`. Then
  `python tools/check_map.py` must report 0 problems.
- **A new floor:**
    1. Copy `sf.json` to `tf.json` and set `code`, `floor`, `label`, `image`, `image_size` and `display_anchors`.
    2. Start the IDs with `a3_`.
    3. Add the floor's lift and stair dots to `building.json`.

**Tools** (`python -m pip install -r tools/requirements-tools.txt` for the plan tools)

- `tools/merge_data.py`: builds `campus.merged.json` (corridors to dots, lengths, GPS, picture positions, checks)
- `tools/check_map.py`: outdoor drawing mistakes
- `tools/validate_graph.py`: structure checks on the merged graph
- `tools/check_routes.py --all [--step-free]`: routes from the Main Gate to every place
- `tools/node_editor/index.html`: indoor editor (corridors, doors, lines, links, `verify` notes), works offline
- `tools/render_plan.py <floor>`: makes the plan picture for the editor (into `private/`)
- `tools/render_graph.py <floor> --plan <pdf> | --signage`: draws the dots and lines to check by eye (into `private/`)
- `tools/generate_qr.py`: prints the QR sheet for lifts, stairs, exits and named junctions (`out/qr_codes.pdf`)
- `tools/merge_wifi.py [--clear]`: reviews the Wi-Fi fingerprints sent by the app into `data/wifi/fingerprints.json`

Step by step: [`docs/mapping-guide.md`](docs/mapping-guide.md).

---

## Indoor positioning: QR, sensors and Wi-Fi

GPS works outdoors (3 to 10 m) but jumps 15 to 40 m under concrete and cannot tell floors apart. Indoors the app
combines free signals instead of paid beacons:

- **QR signs** at entrances, lifts, stair landings and junctions give an exact start on the right floor. Codes hold
  `campusnav:<node id>` or a `campusnav://campus/...` deep link.
- **Steps and turns** from the phone's motion sensors move the arrow along the route; the compass confirms turns.
- **Barometer:** about 0.4 hPa per floor tells the floor after stairs or a lift.
- **Wi-Fi fingerprints** (Android): the networks a phone hears at a spot are compared with `GET /api/wifi`.
    - When a user confirms "I am here", the phone sends a fingerprint.
    - The server keeps at most 3 unreviewed fingerprints per spot until `tools/merge_wifi.py` merges them, so wrong
      ones cannot crowd out the reviewed ones.

Design notes: [`docs/live-tracking.md`](docs/live-tracking.md).

---

## Privacy and security

**The architect's plans stay private.**

- The CAD plans live only in `private/` on the mappers' machines (git-ignored, with `*.dwg` and `out/`).
- Tools that read them write their output into `private/` as well.
- Only derived numbers (positions in metres, lengths, GPS) are committed.

**No personal data is stored.**

- Routes are computed and forgotten. A GPS position is only the start of a route request.
- Wi-Fi fingerprints contain the spot, floor, the day (never the time) and access-point signal strengths. No account,
  phone ID or user is attached.
- Reports keep only what the user typed, with control characters stripped and length capped. GitHub issues neutralise
  @mentions and #links.

**The public graph** (`/api/graph`) strips plan metres, mapper notes and `verify` remarks.

**Request limits** (per client):

- 120 reads a minute
- 40 route or estimate calls a minute
- 2 reports a minute
- 10 Wi-Fi fingerprints a minute

Over the limit the server answers `429` with `Retry-After`.

**Input limits:**

- Bodies are capped at 16 KB and query values at 120 characters.
- The report and Wi-Fi inboxes stop growing at 5 MB and 20 MB.

**Security headers** on every answer:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Content-Security-Policy: default-src 'none'`

**CORS** is open (`*`) on purpose: the data is public and read-only, with no logins or cookies.

**The GitHub token** for reports should be a fine-grained token with Issues read and write on this repository only,
set in the host's environment, never in the repo.

---

## Performance

- **The graph is loaded once** at start into memory: about 350 points, a route in a few milliseconds.
- **ETags:** every GET answer depends only on the map version and the URL, so it carries an `ETag`; repeats get `304`
  with no body. `Cache-Control`: floors 1 h, search and routes 5 min, graph always revalidated.
- **gzip** for large answers: the full graph goes from 170 KB to 23 KB.
- **Route cache:** the last 512 routes. Walk-time labels for every place take one Dijkstra (about 2 ms).
- **Small pictures:** floor pictures are 128-colour PNGs (225 KB for all three, no visible change).
- **gunicorn** with `--preload`, 2 workers × 4 threads: the graph is built once and shared.

---

## Deployment

**Render (free plan)**

1. In the Render dashboard: New, Blueprint, then pick this repository. `render.yaml` sets everything.
2. It deploys `main` on every push. The health check is `/api/health`.
3. Environment set by the blueprint:
    - `PYTHON_VERSION=3.12.7`
    - `TRUSTED_PROXIES=1`, so rate limits see the real client address behind Render's proxy
4. Optional: add `GITHUB_TOKEN` for report issues.

Start command:

```
gunicorn --chdir backend wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --preload --timeout 30 \
         --max-requests 2000 --max-requests-jitter 200
```

**Two things to know:**

- **Render's free plan sleeps** after about 15 minutes idle; the first request then takes several seconds. Open the URL
  a minute before a demo.
- **The free plan's disk is reset on every deploy and restart.** So `data/reports.jsonl` and
  `data/wifi/contributions.jsonl` on the server are temporary. Reports are kept as GitHub issues when `GITHUB_TOKEN` is
  set. Run `tools/merge_wifi.py` and commit `fingerprints.json` to keep Wi-Fi fingerprints.

**Any other host:** `pip install -r backend/requirements.txt`, then the gunicorn command above.
`data/build/campus.merged.json` must be present (it is committed).

---

## Testing

```
cd backend
python -m pytest -q        # 85 tests, about 2 minutes
```

What they cover:

- **A\*:** optimal paths on a tiny fixture graph, compared with Dijkstra, multi-start and goal, restricted edges.
- **The real campus:**
    - Every place is reachable from the Main Gate.
    - Known routes have sane lengths.
    - Stairs versus lifts, step-free, the attic lab.
    - "Inside the Library" and shared doors.
    - Estimates equal route times.
- **Merge and data:** indoor and outdoor joined through door links, the GPS tie-in, lifts and stairs between floors, structure checks on the merged graph.
- **API contract:** the exact JSON the Flutter app reads (`/api/search`, `POST /api/route`, `kind` on steps).
- **Web layer:** security headers, ETag/304, gzip, the stripped public graph, input limits, 429, the inbox size caps.
- **Reports and Wi-Fi:** validation, privacy (day only, no time), per-spot limits, GitHub issue text.

GitHub Actions runs the suite on every push and pull request to `main` that touches `backend/` or the merged graph.

Map checks run separately: `tools/check_map.py`, `tools/validate_graph.py`, `tools/check_routes.py --all --step-free`.

---

## Configuration

All settings are environment variables with safe defaults (`backend/app/config.py`).

**Data and speed**

- `CAMPUS_DATA`: the merged graph file (default `data/build/campus.merged.json`)
- `WALK_SPEED_MPS`: walking speed for times (default 1.3)
- `MAX_SNAP_M`: a GPS start farther than this from every path is "off campus" (default 150)

**Reports**

- `CAMPUS_REPORTS`: the report inbox file (default `data/reports.jsonl`)
- `REPORTS_MAX_BYTES`: inbox size cap (default 5 MB)
- `GITHUB_TOKEN`: if set, reports also become GitHub issues
- `REPORTS_REPO`: where those issues go (default `UAI-FOUNDRY/Campus-Navigation`)
- `REPORTS_LABEL`: their label (default `report`)
- `REPORTS_ISSUES_PER_DAY`: issue cap (default 30)

**Wi-Fi**

- `CAMPUS_WIFI`: reviewed fingerprints (default `data/wifi/fingerprints.json`)
- `CAMPUS_WIFI_INBOX`: fingerprints sent by apps (default `data/wifi/contributions.jsonl`)
- `WIFI_MAX_BYTES`: inbox size cap (default 20 MB)

**Rate limits and proxies**

- `RATE_LIMITS=0` turns the limits off
- `RATE_READ_PER_MIN` (120), `RATE_HEAVY_PER_MIN` (40), `RATE_REPORT_PER_MIN` (2), `RATE_WIFI_PER_MIN` (10)
- `TRUSTED_PROXIES`: 1 behind one proxy (Render), 0 locally

---

## Roadmap and known limits

**Before full trust**

- [ ] Walk the dots marked `verify` and the items in [`docs/indoor-survey-checklist.md`](docs/indoor-survey-checklist.md):
  the lobby and library aisles, the snack room, signage-only offices, the second-floor passages.
- [ ] Quadrangle South Entrance: the outdoor dot is about 12 m from the plan's door. Move the dot or re-check the GPS
  tie-in.
- [ ] Print and fix the QR signs.

**Next features**

- **Faculty directory.** A separate `people.csv` (name, title, department, cabin ID, active) that points at cabin
  places.
    - Search "Dr Sharma" and get a route to their cabin.
    - When someone leaves or moves, edit one row; the map never changes.
    - Public fields only.
- **Street-view photos.** Named points can carry `media: {pano, heading, taken}` for a 360° photo
  ([`docs/street-view.md`](docs/street-view.md)).
- More buildings (hostels, sports complex) as new floor files.

**Known limits**

- Indoor positions come from the plan fit (about 2 m). The plan can differ from the building until it is checked on
  site.
- Lift waiting time is an estimate (60 s).
- The attic Innovation Lab has no step-free route.
- Render's free plan sleeps when idle, and its disk is temporary.

---

## Team

Built by students of Universal AI University, Karjat (UAI-FOUNDRY):

- **Backend, map data, routing and hosting:** Divyansh Routray
- **Flutter app and Report a problem:** Aryaman Singh and the Flutter team
- **Wi-Fi fingerprints and QR tools:** Pushpak Sarode

Questions about the map or a wrong route? Use **Report a problem** in the app, or open an issue in this repository.
