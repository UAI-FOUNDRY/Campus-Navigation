# Street-view style photos (future): how the data is ready for it

Goal: at a junction or door, the app can show a 360° photo ("what it looks like here"), like Google Street View.

## Where photos attach

Photos belong to **named, stable dots**: doors, junctions with a name, lifts, stairs, exits, outdoor entrances.
Never to generated corridor dots (`...__v1`, `...__a0_x`): their ids change when a corridor is redrawn.

Each such dot may get a `media` field in its floor file (or as a property in the outdoor GeoJSON):

```json
{"id": "a0_lobby_c", "type": "junction", "name": "Lobby", "pos": [57.14, 78.89], "on": "a0_c_lobby_b_e",
 "media": {"pano": "gf_lobby_c_2026_11.jpg", "heading": 180, "taken": "2026-11"}}
```

- `pano`: file name of an equirectangular 360° photo (2:1, e.g. 5760 x 2880, JPEG ~1.5 MB).
- `heading`: compass direction (degrees) of the photo's centre, so the app can turn the view to face the route.
  The route's direction at a dot is the bearing from that dot to the next point of the leg (all points have lat/lng).
- `taken`: month, so stale photos are easy to find after a renovation.

`media` passes through the public graph untouched; the merge does not need to change.

## Free way to take and serve them

1. Use the phone camera's photo-sphere / 360 panorama mode or a free 360 camera app, or borrow a 360 camera from
   the media team (better stitching).
2. Stand on the dot (the corridor centre at that door/junction), hold the phone at eye height, face the corridor's
   main direction, note that compass heading.
3. Put the photos in a public bucket or the Flutter assets (only common spots: ~30 photos x 1.5 MB). Do NOT
   photograph the architect's drawings or private offices.
4. In Flutter, a free panorama viewer package from pub.dev (e.g. `panorama_viewer`) shows an equirectangular photo
   with touch/gyro control; check its licence before adding it.

## Order of work

Start with the places people get lost: the three entrances, both lobbies, every lift and staircase landing, the library
aisle, the second-floor passages. That is about 25 photos and covers most routes.
