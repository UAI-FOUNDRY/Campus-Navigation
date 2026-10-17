# Live "blue dot" tracking: what is possible for free, and how

Goal: like Google Maps, a dot that shows where the student is and moves along the route, outdoors and inside the
main building. Status: **not part of version 1** (guidance is the "Next step" / "Simulate walk" button). This is the
plan for after the demo.

## What the backend already gives the app

- Every outdoor point has `lat`/`lng`. Since the floor plans were tied to GPS (georef, about 1.7 m), **every indoor
  point has `lat`/`lng` too**, plus `floor` and `x`/`y` on the signage picture. So the app can draw the whole route,
  indoors included, on the same OpenStreetMap map, and move a dot along it.
- `GET /api/route?from_lat=..&from_lng=..&to=..` starts a route from a GPS fix (snaps to the nearest outdoor dot, max
  150 m). Add `&from_floor=N` when the app knows the floor (after a QR scan): then it may snap to indoor dots too.

## Outdoors: GPS (free, works now)

- Flutter packages (all free): `geolocator` (position + accuracy), `flutter_map_location_marker` (the blue dot with
  heading on `flutter_map`), `flutter_compass` or the heading from `geolocator`.
- Phone GPS on open ground: about 3 to 10 m. Snap the dot to the route line when it is within ~15 m, so it doesn't
  wander into buildings ("map matching").
- Off route for more than ~10 s and 25 m: ask for a new route from the GPS fix ("Rerouting...").
- Android needs the location permission; ask only when the student taps "Start navigation".

## Inside the building: GPS is not enough

Concrete roofs make GPS jump 10 to 30 m and it cannot tell the ground floor from the second floor. Options, cheapest
first:

1. **QR checkpoints (free, already in the app).** A QR code at every lift and stair landing and main corridor junction,
   with that floor's node id (`campusnav:a1_lobbya_e`). Scanning puts the dot exactly there, on the right floor.
   `python tools/generate_qr.py` should print them from the merged graph (only junctions, lifts, stairs and exits).
2. **Step counting along the route (free, phone sensors).** After a known position (door, QR scan), count steps with the
   phone's step sensor (`pedometer` package) and move the dot ALONG THE ROUTE by steps x step length (about 0.7 m;
   let the student calibrate once over 10 m). Use the compass (`flutter_compass` / `sensors_plus`) only to confirm
   turns. Error grows about 5 to 10 % of the distance walked, so re-anchor at every QR code and at every turn the student
   confirms ("I've turned").
3. **Floor detection with the barometer (free where the phone has one).** Air pressure drops about 0.4 hPa per floor
   (~4 m). When the route says "take the stairs to the First floor" and pressure drops by roughly that much, move the
   dot to the first floor automatically; otherwise the student confirms the floor.
4. **Wi-Fi positioning** (Android only, needs a site survey and access points that support Wi-Fi RTT). Only if the IT
   team confirms the access points; no extra cost but a lot of setup.
5. **Bluetooth beacons**: 1 to 3 m accuracy, but each beacon costs money (roughly Rs 500 to 1,500) and batteries need
   changing. Out of scope while everything must be free.

**Recommendation:** GPS dot outdoors + QR checkpoints + step counting along the route indoors (1, 2, and 3 when the
phone has a barometer). It is free, works on most phones and is honest about accuracy.

## How it fits together in the app (sketch)

```
state: route (legs with lat/lng), anchor (last known node + time), steps since anchor, floor
outdoor leg  -> position from GPS -> snap to the leg's polyline -> dot
indoor leg   -> position = anchor + (steps x step length) along the leg's points -> dot (on the map, or x/y on the floor picture)
QR scan      -> anchor = scanned node, floor = its floor, steps = 0
stairs/lift step reached + barometer change (or student taps "I'm on the First floor") -> next indoor leg
off route    -> GET /api/route?from=<anchor node> (indoors) or ?from_lat&from_lng (outdoors)
```

Nothing here sends the student's location to the server except the start point of a route request.
