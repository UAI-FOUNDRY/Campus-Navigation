# API reference (backend)

Base URL while developing: `http://127.0.0.1:5000` (Android emulator: `http://10.0.2.2:5000`; phone on the same Wi-Fi: your laptop's address).
All responses are JSON. Errors always look like `{"error": {"code": "...", "message": "..."}}`.

> The indoor distances come from the team's tile measurements and the pixel positions on the plan are still being confirmed,
> so indoor numbers can change. Always read `graph_version` (below) instead of assuming the map is fixed.

## Concepts
- **Place** = something a student searches for. It has an `id`, a `name`, and one or more entry points (`node_ids`).
  The Cafeteria / Mess has two (the inside door and the back door); the route goes to whichever is nearer.
- **Outdoor** places have `lat`/`lng`. **Indoor** places have `x`/`y` (pixels on the floor-plan image) and `lat`/`lng` = `null`.
- A route is split into **legs**: `outdoor` legs are drawn on the map (`[lat, lng]` list), `indoor` legs are drawn on a floor plan
  image (`points` with pixel `x`,`y`). A route from the gate to a classroom is an outdoor leg followed by an indoor leg.

## GET /api/health
`{"status": "ok"}`

## GET /api/rooms?q=<text>&limit=8
Search places by name or alias; typos are tolerated. Empty `q` lists places. Example `/api/rooms?q=everest&limit=2`:
```json
{
  "results": [
    {
      "id": "mount_everest_130",
      "name": "Mount Everest 130",
      "aliases": [
        "130",
        "everest",
        "mount everest",
        "mount everest 130"
      ],
      "type": "place",
      "building": "Block A",
      "floor": 0,
      "node_ids": [
        "a0_everest_door"
      ],
      "indoor": true,
      "lat": null,
      "lng": null,
      "x": 733,
      "y": 400
    }
  ]
}
```
`GET /api/rooms/<id>` returns one place, e.g. `/api/rooms/mess`:
```json
{
  "id": "mess",
  "name": "Cafeteria / Mess",
  "aliases": [
    "cafeteria",
    "cafeteria / mess",
    "canteen",
    "mess"
  ],
  "type": "place",
  "building": "Main building",
  "floor": 0,
  "node_ids": [
    "a0_mess_inside_door",
    "mess_entrance"
  ],
  "indoor": false,
  "lat": 18.902549,
  "lng": 73.374595,
  "x": 990,
  "y": 336
}
```

## GET /api/route
Query: `to=<place or node id>` (required) and either `from=<place or node id>` **or** `from_lat=..&from_lng=..` (the user's GPS;
snapped to the nearest outdoor path point, `422 off_campus` if farther than 150 m). Optional `accessible=1` avoids stairs.

Example, outdoor then indoor: `/api/route?from=gate_main&to=mount_everest_130`
```json
{
  "from": "gate_main",
  "to": "a0_everest_door",
  "to_name": "Mount Everest 130",
  "distance_m": 331.7,
  "duration_s": 255,
  "nodes": [
    "gate_main",
    "main_junction",
    "faculty_junction",
    "mess_junction",
    "..."
  ],
  "legs": [
    {
      "type": "outdoor",
      "distance_m": 261.7,
      "polyline": [
        [
          18.903652,
          73.373594
        ],
        [
          18.903564,
          73.37372
        ],
        "..."
      ]
    },
    {
      "type": "indoor",
      "floor": 0,
      "image": "ground.png",
      "image_size": [
        1357,
        882
      ],
      "distance_m": 70.0,
      "points": [
        {
          "id": "a0_mess_inside_door",
          "name": "Cafeteria / Mess inside door",
          "x": 990,
          "y": 336
        },
        {
          "id": "a0_library",
          "name": "Library",
          "x": 800,
          "y": 330
        },
        {
          "id": "a0_everest_door",
          "name": "Mount Everest 130",
          "x": 733,
          "y": 400
        }
      ]
    }
  ],
  "polyline": [
    [
      18.903652,
      73.373594
    ],
    [
      18.903564,
      73.37372
    ],
    "..."
  ],
  "steps": [
    {
      "instruction": "Start at Main Gate and walk 125 m",
      "distance_m": 126.1,
      "node_id": "gate_main",
      "space": "outdoor",
      "lat": 18.903652,
      "lng": 73.373594
    },
    {
      "instruction": "Turn right at the junction and walk 60 m",
      "distance_m": 61.5,
      "node_id": "main_junction",
      "space": "outdoor",
      "lat": 18.903091,
      "lng": 73.374406
    },
    {
      "instruction": "Bear right at the junction and walk 50 m",
      "distance_m": 51.2,
      "node_id": "faculty_junction",
      "space": "outdoor",
      "lat": 18.902669,
      "lng": 73.374095
    },
    "..."
  ],
  "graph_version": "f6b176c64d"
}
```
Example, indoor only: `/api/route?from=admin_lobby&to=mount_everest_130`
```json
{
  "from": "a0_adminlobby",
  "to": "a0_everest_door",
  "to_name": "Mount Everest 130",
  "distance_m": 78.0,
  "duration_s": 60,
  "nodes": [
    "a0_adminlobby",
    "a0_mess_inside_door",
    "a0_library",
    "a0_everest_door"
  ],
  "legs": [
    {
      "type": "indoor",
      "floor": 0,
      "image": "ground.png",
      "image_size": [
        1357,
        882
      ],
      "distance_m": 78.0,
      "points": [
        {
          "id": "a0_adminlobby",
          "name": "Admin Lobby gate",
          "x": 981,
          "y": 560
        },
        {
          "id": "a0_mess_inside_door",
          "name": "Cafeteria / Mess inside door",
          "x": 990,
          "y": 336
        },
        {
          "id": "a0_library",
          "name": "Library",
          "x": 800,
          "y": 330
        },
        "..."
      ]
    }
  ],
  "polyline": [],
  "steps": [
    {
      "instruction": "Walk 27 m to Cafeteria / Mess inside door",
      "distance_m": 27.0,
      "node_id": "a0_adminlobby",
      "space": "indoor",
      "x": 981,
      "y": 560,
      "floor": 0
    },
    {
      "instruction": "Walk 32 m to Library",
      "distance_m": 32.0,
      "node_id": "a0_mess_inside_door",
      "space": "indoor",
      "x": 990,
      "y": 336,
      "floor": 0
    },
    {
      "instruction": "Walk 19 m to Mount Everest 130",
      "distance_m": 19.0,
      "node_id": "a0_library",
      "space": "indoor",
      "x": 800,
      "y": 330,
      "floor": 0
    },
    "..."
  ],
  "graph_version": "f6b176c64d"
}
```

Fields: `distance_m`, `duration_s` (walking speed 1.3 m/s), `nodes` (ids along the way), `legs`, `polyline` (all outdoor
coordinates joined, for a quick map line), `steps`, `graph_version`. Each step has `instruction`, `distance_m`, `node_id`,
`space` (`outdoor` or `indoor`) and either `lat`/`lng` or `x`/`y`/`floor`.

Errors: `400 bad_request` (missing/invalid parameter), `404 not_found` (unknown id), `422 no_route` or `off_campus`.
Example: `/api/route?from=gate_main&to=nope` gives 404:
```json
{
  "error": {
    "code": "not_found",
    "message": "unknown destination 'nope'"
  }
}
```

## POST /api/estimates
Walking minutes from one start to many places, for the "2 min walk" labels. Body: `{"start": "gate_main", "destinations": ["mess", "gym_entrance"]}`.
Answers `{"estimates": {"mess": 3, "gym_entrance": 7}}`. Unknown or unreachable places are left out; unknown `start` is `404 not_found`.

## GET /api/wifi  and  POST /api/wifi
Wi-Fi fingerprints of campus spots, for "Use my location" indoors (Android; iPhones cannot scan Wi-Fi).

When a student confirms where they are (picks their spot in the app's "Where exactly are you?" list, or scans a sign),
the app sends the Wi-Fi networks it hears there:
```json
POST /api/wifi
{"spot": "a0_adminlobby", "floor": 0, "at": "2026-10-18T10:00:00Z",
 "aps": {"aa:bb:cc:00:00:01": -48, "aa:bb:cc:00:00:02": -61, "aa:bb:cc:00:00:03": -70}}
```
`spot` is a place or node id, `aps` maps access point ids (BSSIDs) to signal strength in dBm (at least 3). Nothing about
the phone or the person is sent or stored. Answers `201 {"status": "saved"}`; a bad body is `400`, an unknown spot
`404`. Saved to `data/wifi/contributions.jsonl` (env `CAMPUS_WIFI_INBOX`, git-ignored, stops at 20 MB:
`503 inbox_full`).

`GET /api/wifi` returns every fingerprint (the committed `data/wifi/fingerprints.json`, env `CAMPUS_WIFI`, plus the inbox),
the newest 8 per spot: `{"samples": [{"spot", "floor", "at", "aps"}], "spots": 12}`. The app downloads it at most once an
hour and keeps it for offline use.

`python tools/merge_wifi.py --clear` folds the inbox into `data/wifi/fingerprints.json`; commit that file so every
deployment (Render's disk is wiped on redeploy) serves the fingerprints.

## POST /api/report
The app's "Report a problem" sheet. Body: `{"start", "destination", "reason", "details"}` (`reason` required). Each report is appended to
`data/reports.jsonl` (override with `CAMPUS_REPORTS`). Answers `201 {"status": "received"}`.

## GET /api/floors
Floor-plan images the app should bundle (put the file in `app/assets/floorplans/`). `image_size` is the pixel size that
`x`/`y` refer to.
```json
{
  "floors": [
    {
      "floor": 0,
      "image": "ground.png",
      "image_size": [
        1357,
        882
      ]
    }
  ]
}
```

## GET /api/graph/version and GET /api/graph
`/api/graph/version` returns the current `version` and counts; compare it with the one you cached. `/api/graph` returns the whole
graph (small) with an `ETag` equal to the version; send `If-None-Match: <version>` and you get `304` when nothing changed.
```json
{
  "version": "f6b176c64d",
  "source": "outdoor_draft_v2.geojson",
  "snap_m": 6.0,
  "node_count": 41,
  "edge_count": 51,
  "room_count": 22,
  "outdoor_nodes": 34,
  "indoor_nodes": 7
}
```

## Drawing hints for the Flutter team
- **Outdoor leg:** convert each `[lat, lng]` to `LatLng(lat, lng)` and draw a `Polyline` in `flutter_map`.
- **Indoor leg:** show the floor image at its displayed size; a point at pixel `(x, y)` goes at `(x / image_size[0] * displayedWidth,
  y / image_size[1] * displayedHeight)`. Connect the `points` in order with a `CustomPainter`.
- Show `steps` as the text list; tapping a step can centre the map or plan on its `lat`/`lng` or `x`/`y`.
- Wait about 300 ms after the user stops typing before calling `/api/rooms`.

## App contract (what the Flutter app calls)
These two endpoints match `lib/services/api_service.dart` in `UAI-FOUNDRY/CampusNav-Flutter`. They use the same graph and route cache as the endpoints above.

### GET /api/search?q=
A **plain list**. Empty `q` returns every place. `building` is `"Campus"` for outdoor places that have no building. `type` uses the app's
filter words: `cafeteria`, `gym`, `turf`, `library`, `lab`, `office`, `hostel`, `hall` (classrooms), else `place` (shows under "Other").
```json
[{"id": "mount_everest_130", "name": "Mount Everest 130", "building": "Block A", "floor": 0, "type": "hall"}]
```

### POST /api/route
Body: `{"start": "gate_main", "destination": "mount_lhotse", "step_free": false}`. `start`/`destination` take a place id or node id;
`start` may also be a raw QR value `campusnav:<node id>`. Errors: 400 bad body, 404 unknown id, 422 `no_route`.
```json
{"distance_meters": 169, "estimated_minutes": 2,
 "steps": [
  {"type": "start", "title": "You are here", "instruction": "Main Gate", "distance": 0, "floor": 0},
  {"type": "walk", "title": "Walk 115 m", "instruction": "Start at Main Gate and walk 115 m", "distance": 115.0, "floor": 0},
  {"type": "turn_right", "title": "Bear right", "instruction": "Bear right at the junction and walk 25 m", "distance": 25.0, "floor": 0},
  {"type": "enter", "title": "Go inside", "instruction": "Go inside through Quadrangle South Entrance", "distance": 0.0, "floor": 0},
  {"type": "walk", "title": "Walk 15 m", "instruction": "Walk 15 m to Clinic", "distance": 15.0, "floor": 0},
  {"type": "walk", "title": "Walk 14 m", "instruction": "Walk 14 m to Mount Lhotse", "distance": 14.0, "floor": 0},
  {"type": "arrive", "title": "Arrive at Mount Lhotse", "instruction": "Arrive at Mount Lhotse", "distance": 0.0, "floor": 0}],
 "path": [],
 "legs": ["... same as GET /api/route ..."], "polyline": [[18.9, 73.3], "..."],
 "from": "gate_main", "to": "a0_lhotse_door", "to_name": "Mount Lhotse", "graph_version": "f4f1dd1c5d"}
```
`path` is always empty (it belongs to the app's schematic map). To draw the real route use `legs`: `outdoor` legs have a `[lat, lng]`
`polyline`; `indoor` legs have pixel `points` on the floor-plan `image`.

## Multi-floor data (update 6, 17 Oct 2026)

What changed for the app (all additive; old fields are unchanged):

- `GET /api/floors` lists every floor in order: `{"floor": 0, "code": "gf", "label": "Ground floor", "image": "ground.png",
  "image_size": [1357, 882]}`, then `ff` (`first.png`) and `sf` (`second.png`). Bundle all three pictures from
  `app/assets/floorplans/`.
- Route answers have `floors` (e.g. `[0, 2]`) and **one indoor leg per floor**:
  `{"type": "indoor", "floor": 2, "floor_label": "Second floor", "image": "second.png", "image_size": [...],
  "distance_m": 18.4, "points": [{"id", "name", "x", "y", "lat", "lng"}]}`. Draw each indoor leg on its own picture
  (floor selector), or draw `lat`/`lng` on the map: indoor points now have GPS positions too.
- Every step has `kind` (`start_walk`, `walk`, `turn_left`, `turn_right`, `enter`, `exit`, `stairs`, `lift`,
  `arrive`) and `floor`. Use `kind` for the icon instead of reading the sentence. Floor changes are their own step:
  "Take the Staircase (Block A) up to the First floor".
- `duration_s` includes lift waiting time; `distance_m` is metres walked only.
- `accessible=1` (or `"step_free": true` on `POST /api/route`) avoids stairs and steps and uses lifts and ramps.
- GPS start: `?from_lat=..&from_lng=..` snaps to an outdoor dot; add `&from_floor=N` when the app knows the floor
  (e.g. after a QR scan) to allow indoor dots on that floor.
- `POST /api/route` step `type` now also returns `stairs` and `lift` (the app already has icons for them).
- `GET /api/rooms` results have `floor` and (for most places now) `lat`/`lng`.

## Update 7 (17 Oct 2026): clean indoor lines, "inside the Library", speed and safety

All additive for the app; nothing it already reads has changed shape.

**Places inside places.** `GET /api/rooms` results have `within` (place id) and `within_name` ("Library");
`GET /api/search` items have `within_name` when there is one. Show it under the name: "Psychology Lab · inside the
Library". Route answers have `to_within`, and the last step already says "Arrive at Psychology Lab, inside the
Library". Places that share one door (Yummy Waffle, Vending, ATM in the snack room) still arrive with the asked name.

**Turn text names the corridor.** "Turn left into the North corridor and walk 5 m", "Walk 45 m through the
Quadrangle", "Turn right into the Library and walk 12 m". No more "at the corridor".

**Indoor leg points are the drawable line.** Points that sit on a straight line are left out, so every middle point
is a real bend or a named place (the app draws a small dot at each). Lines are square on the signage picture.
Points without a name have `"name": ""`; a bend without a dot has `"id": ""` too.

**Caching.** Every GET answer depends only on the map version and the URL, so it has an `ETag`;
send it back in `If-None-Match` and you get `304` with no body. `Cache-Control`: floors 1 h, search/rooms/route
5 min, graph `no-cache` (always revalidate). Flutter's `http` does not cache by itself: keep the last answer and its
ETag if you want the 304s (e.g. for `/api/search?q=` at app start).

**gzip.** Send `Accept-Encoding: gzip` (Dart's `http`/`dio` do this by default) and large answers come compressed
(the full graph: 170 KB -> 23 KB).

**GET /api/graph** is the public copy: no plan metres, mapper notes or `verify` remarks. `ETag` = `"<version>"`.

**Limits** (per client, per server process):
- 120 GET requests/min (bursts of 60 are fine), 40/min for `POST /api/route` and `/api/estimates`,
  2/min for `POST /api/report`, 10/min for `POST /api/wifi`. Over the limit: `429 {"error": {"code": "rate_limited"}}` with `Retry-After`
  seconds. The app should show "Try again in a moment", not retry in a loop.
- Request bodies over 16 KB: `413 too_large`. Query values over 120 characters: `400`. Wrong method: `405`.
- The report inbox stops at 5 MB (`503 inbox_full`) until the team clears `data/reports.jsonl`.
- Tune with env vars `RATE_READ_PER_MIN`, `RATE_HEAVY_PER_MIN`, `RATE_REPORT_PER_MIN`, `RATE_WIFI_PER_MIN`, `RATE_LIMITS=0` (off),
  `TRUSTED_PROXIES=1` (set on Render so the real client address is used).

**`POST /api/estimates`** now runs one search for all destinations (about 2 ms for 130 places) and gives the same
minutes as `/api/route`.

**Security headers** on every answer: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'`. CORS stays `*` (public read-only
data, no cookies or logins).

**Floor pictures** in `app/assets/floorplans/` were re-saved as 128-colour PNGs: 593 KB -> 225 KB for the three,
same look. Re-copy them into the Flutter assets.

## Update 8 (17 Oct 2026): map pins, all places, attic lab, outdoor v6

- `GET /api/rooms?q=&limit=500`: the limit now goes up to 500 (it was 50, so with 137 places the Gym, Turf, R7...
  never reached the app). Ask for all places in one call.
- `lat`/`lng` in `/api/rooms` are now **only for places with an outdoor door** (gates, entrances, the mess back door).
  Indoor places have `lat`/`lng` = `null` and `x`/`y` + `floor` for the floor picture, as in version 1. Their GPS is still
  there as `gps: {"lat", "lng"}` (for live tracking later). So the campus map shows outdoor pins only and the Indoors tab
  shows rooms per floor.
- A staircase inside one floor (the spiral stair from Work Station 01 up to the Innovation Lab attic) is its own step:
  `{"kind": "stairs", "instruction": "Take the spiral staircase up to Innovation Lab"}`.
