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
