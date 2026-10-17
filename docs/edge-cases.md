# Edge cases: what a student can run into, and what we do about it

"Done" = handled in the backend now. "App" = the Flutter app must handle it. "Later" = after version 1.

## Where am I? (the start)

- **Start = destination** (scanned the QR on the classroom door). Done: 0 m route, one "Arrive at ..." step.
- **Old or foreign QR code / unknown id.** Done: 404 `not_found`. App: say "This code is not from this campus map,
  pick your location from the list".
- **GPS start far from campus** (or GPS off). Done: 422 `off_campus` beyond 150 m (`MAX_SNAP_M`). App: fall back to the
  start picker / QR.
- **GPS start inside the building.** GPS cannot tell floors apart and is poor indoors. Done: a GPS start snaps to an
  outdoor dot, unless the app sends `from_floor=N` (then it may snap to an indoor dot on floor N). App: inside the
  building, ask the student to scan the nearest QR code (every lift/stair landing and corridor junction should have
  one, with the floor's own id, e.g. `campusnav:a1_lobbya_e`).
- **Start is a place with several doors** (the mess). Done: A* starts from all its doors and picks the best.

## Where am I going? (search)

- **Typos, short names, numbers** ("evrest", "lhotse", "classroom 7", "130"). Done: fuzzy search on names and aliases.
- **Same name on several floors** (washrooms). Done: names say the block and floor ("Washroom (Block A, first floor)").
- **Room renamed** (the plan shows a future layout; the signage is the truth today). Data: change `name` in
  `data/places.json`, keep the `id`, keep the old name as an alias.
- **Place with several doors** (Lhotse front/back, the mess inside/back). Done: the nearest door wins.

## The route itself

- **No route** (a part of the map is cut off, or everything to it is restricted). Done: 422 `no_route`; before every
  deploy `python tools/check_routes.py --all` lists unreachable places and the tests fail.
- **Step-free / wheelchair / heavy luggage.** Done: `accessible=1` (or `step_free: true`) skips stairs and the
  quadrangle steps and uses lifts and ramps. If none exists: `no_route`. App: then say "No step-free route found" and
  offer the normal route.
- **Lift out of service.** Data: add `"closed": true` to that lift in `data/indoor/building.json > vertical`, merge,
  redeploy (routes switch to stairs; step-free routes switch to the other lift). Later: a `/api/closures` list the
  admin can change without redeploying.
- **Door locked at some times** (fire exits, library after hours, the Block A side door). Data now: mark the line
  `"type": "restricted"` while it is locked. Later: `"open_hours": "08:00-18:00"` on lines and a time-aware A*.
- **Which floor?** Done: every step has `floor`; floor changes are separate steps ("Take the Staircase (Block A) up to
  the First floor"); each floor is its own indoor leg with its own picture (`ground.png`, `first.png`, `second.png`).
- **Stairs vs lift choice.** Done: A* minimises TIME. Stairs = 12 m + 20 s per floor, lift = 4 m + 40 s wait + 6 s
  per floor (`building.json > costs`). So one floor up: stairs; two floors in Block A: often the lift. Tune the costs if
  students disagree.
- **Walking through classrooms.** Not allowed: no line goes through a classroom. Open areas (library floor, cafeteria,
  quadrangle) are crossed with `open` lines.
- **Quadrangle crossing.** The plan shows paved stone with planters at the edges, so one `open` line crosses it. If the
  middle is a lawn students must not cross, delete that line: routes then use the walkways (about 15 m longer).
- **Tiny zig-zag instructions** ("turn left, walk 1 m"). Done: runs under 3 m are folded into the next instruction,
  and the last metre becomes "Mount Everest 130 is on your left".
- **Plan and tape disagree.** Done: lengths come from the plan; a tape value (`"meters"`) overrides it and the merge
  warns when the two differ by more than 30 % (typo check). See docs/indoor-survey-checklist.md for the current list.

## The app and the server

- **Server asleep (Render free tier wakes in about a minute).** The app's timeout is 8 s, so the first request after
  15 min idle fails. App: call `/api/health` when the app opens, show "Waking up the campus map..." and retry with a
  longer timeout (60 s) once. Before a demo: open `/api/health` yourself 2 minutes earlier.
- **No internet on campus.** Later: the app downloads `/api/graph` (ETag = graph version) and runs A* on the phone
  (the graph is small). For the demo: mobile data or the phone hotspot.
- **Map data changed while the app is open.** Done: every route carries `graph_version`; `/api/graph` answers 304 when
  the app already has the current version.
- **Very fast repeated requests.** Done: routes are cached in memory (LRU, 512 entries) and A* on this graph takes
  well under a millisecond.

## Safety and privacy

- **Fire exits.** A fire exit is only part of the map when the team confirmed it is open in normal use (it has a
  `verify` note until then). Emergency routing is not a goal of this app.
- **Architect's plans.** Never committed or shipped; only derived positions/lengths are. See docs/data-format.md.
