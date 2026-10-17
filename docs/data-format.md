# Data format

Everything the router knows comes from five kinds of files. `python tools/merge_data.py` turns them into
`data/build/campus.merged.json` (commit that file; the server only reads it).

```
data/outdoor/outdoor_draft_vN.geojson   outdoor paths and doors (geojson.io); the newest N is used
data/indoor/building.json               shared by all floors: GPS tie-in, lifts and stairs, floor-change costs
data/indoor/gf.json  ff.json  sf.json    one file per floor (gf = ground, ff = first, sf = second, tf = third ...)
data/places.json                        what students can search for, and which doors lead into it
app/assets/floorplans/*.png             the PUBLIC signage pictures the app shows (ground.png, first.png, second.png)
private/plans/*.pdf                     the architect's plans: NEVER committed, never shipped (see below)
```

## Outdoor GeoJSON (unchanged)

Points (`type`): `gate`, `junction` (3+ paths meet), `entrance` (a door; needs a `name`), `room_door`.
Lines (`type`): `path` (default), `steps`, `ramp`, `restricted`. A line is split at every dot within 6 m of it, so two
lines only join through a dot. Properties: `id` (unique, lowercase_with_underscores, **never renamed**), `name`,
optional `building`, `access`, `note`, `aliases`. Run `python tools/check_map.py` after every edit: it finds line
ends that stop next to another line without a dot (BROKEN), crossings without a dot, lines the converter skips,
lonely dots, and the same path drawn twice.

## Plan metres (how indoor positions work)

Indoor dots are placed on the architect's floor plans, in **metres**: `pos: [x, y]`, x to the right, y down, origin =
top-left corner of the A4 sheet. On these sheets 1 m = 6.30 PDF points (checked against the printed dimensions,
e.g. the 17.99 m and 14.52 m room widths). Ground, first and second floor sheets share the same frame, so a lift
sits at the same `pos` on every floor.

From `pos` the merge tool computes three things, so nobody types them by hand:
- **length of every line** = distance along the line (corridor centre line, stub, `via` bends).
  Put `"meters": 23.5` on a line only to override with a tape measurement; the merge warns if the two disagree a lot.
- **GPS** (`lat`, `lng`) through `building.json > georef`: a best fit between plan positions and outdoor dots that sit
  on the building's facade (Logan, K2, Makalu, washrooms, Vending...). The fit is about 1.7 m.
- **pixels on the signage picture** (`x`, `y`) through the floor's `display_anchors`. The signage picture is not to
  scale, so this only decides where the line is DRAWN in the app. After the fit, every straight corridor is squared up
  on the picture (one x for a vertical corridor, one y for a horizontal one, stubs square to it) so the app draws
  clean right-angled lines. Give a dot its own `"x"`, `"y"` to place it by hand; squaring then follows that dot.

## Floor file (`data/indoor/gf.json`): corridors + doors

A floor is described the way a mapper thinks about it: **corridors** are centre lines, **doors** sit on a corridor.

```json
{"code": "gf", "floor": 0, "label": "Ground floor", "status": "plan",
 "source_plan": "UAi_LEARNING_CENTER_-_GF_2026.pdf",
 "image": "ground.png", "image_size": [1357, 882],
 "display_anchors": [[[29.37, 52.38], [733, 367]], ...],
 "corridors": [
   {"id": "a0_c_west", "name": "Block A walkway", "type": "corridor",
    "path": ["a0_ww_n", "a0_ww_everest", "a0_ww_lobbya", "a0_ww_lhotse", "a0_ww_s"]},
   {"id": "a0_c_library", "name": "Library", "type": "open",
    "path": ["a0_library", [36.9, 42.86], "a0_lib_x", [24.13, 42.86], [24.13, 24.6]]}],
 "nodes": [
   {"id": "a0_ww_everest", "type": "junction", "name": "", "pos": [30.63, 63.81]},
   {"id": "a0_everest_door", "type": "door", "name": "Mount Everest 130", "pos": [29.29, 63.89], "on": "a0_c_west"},
   {"id": "a0_aspretto", "type": "door", "name": "Aspretto (coffee shop)", "pos": [54.29, 88.89], "on": "a0_c_lobby_b_e"}],
 "edges": [{"from": "a0_quad_n", "to": "a0_nc_steps", "type": "steps"}],
 "links": [{"indoor": "a0_quad_south_exit", "outdoor": "quad_south_entrance"}]}
```

- **Corridor** `path`: points along the middle of the walkway. A point is either `[x, y]` (a plain bend) or the id of
  a dot (use a dot where two corridors meet, so they share that junction, or where a named landmark is). Keep
  corridors straight between points and square at the bends: that is what the app draws.
  `name` is what turns say: "Turn left **into the Library**", "Turn right into Passage 01".
  `type` as for lines (`corridor`, `open` for halls/libraries/the quadrangle, `ramp`, `steps`, `restricted`).
- **Door** `"on": "<corridor id>"`: the merge joins the dot to the nearest point of that corridor with a short stub
  square to it. Put the dot ON the door mark of the plan (middle of the opening). Adding a room is one line.
- Generated dots: corridor bends become `<corridor>__v<k>`, stub junctions `<corridor>__<dot id>`. They are marked
  `internal`, carry the corridor name as `area`, and change when a corridor is redrawn: **never** use them in
  places.json, QR codes or the app (the merge refuses places that point at them; generate_qr skips them).
- `edges`: extra lines that a corridor can't describe (steps between two levels, a door straight onto another door).
  `"via": [[x, y], ...]` bends a line without adding dots. Length = along the bends.
- Node `type`: `door` (a room you can route to), `junction`, `corner`, `exit` (door to outside; needs a link),
  `gate`, `lift`, `stairs`. `name` is what the steps say ("... Mount Lhotse is on your left").
- Ids: floor prefix + short name: `a0_` ground, `a1_` first, `a2_` second. **Never rename an id once used.**
- `verify`: a note on a dot whose position needs an on-site look. The merge counts them; delete it once checked.
- `note`: free text for mappers (e.g. "Plan: Conference Room"). Never sent to the app.
- `media` (reserved for street view, see docs/street-view.md): `{"pano": "<photo id>", "heading": 90}`. Passed to the
  app as is.
- `links`: an indoor exit joined to an outdoor dot id. `meters` is optional: it is computed from GPS. The merge warns
  when the outdoor dot is more than 25 m from the door (move the dot in geojson.io).

**When the building changes:** a room renamed = change `name` in places.json (keep ids). A wall moved = drag the
corridor points or the door dot in the editor. A new corridor = draw it, pass through the dots it meets. Nothing else
needs touching: lengths, GPS, picture positions and turn names are all recomputed by `merge_data.py`.

## building.json

```json
{"floors": [{"code": "gf", "floor": 0, "label": "Ground floor"}, ...],
 "georef": {"control_points": [{"outdoor": "makalu_entrance", "pos": [8.73, 49.21]}, ...]},
 "vertical": [{"id": "lift_a", "type": "lift", "name": "Lift (Block A)", "nodes": ["a0_lift_a", "a1_lift_a", "a2_lift_a"]},
              {"id": "stair_a", "type": "stairs", "name": "Staircase (Block A)", "nodes": ["a0_stair_a", "a1_stair_a", "a2_stair_a"]}],
 "costs": {"stairs_m_per_floor": 12, "stairs_s_per_floor": 20, "lift_m": 4, "lift_wait_s": 60, "lift_s_per_floor": 6}}
```
- `vertical`: one dot per floor, bottom first. Every pair gets a connection, so one ride can skip floors.
- `costs`: A* minimises time. Stairs = 12 m walked + 20 s per floor; a lift = 4 m + 60 s wait + 6 s per floor. Stairs
  are skipped when the app asks for step-free routes. The lift wait counts in the time but not in the metres shown.

## places.json

```json
{"id": "mount_lhotse", "name": "Mount Lhotse", "aliases": ["lhotse", "classroom 1"],
 "entry_nodes": ["a0_lhotse_door", "a0_lhotse_door_s"], "building": "Block A", "category": "classroom"}
```
- Names and aliases come from the **signage** (the current state). When a room is renamed, change `name` and add the
  old name to `aliases`; never change `id`.
- `entry_nodes`: every door into the place, indoor or outdoor. A* uses the nearest.
- `category`: classroom, lab, library, food, office, facility, washroom, auditorium, shop (the app maps these to its
  chips).
- Outdoor `entrance` dots are searchable on their own (Makalu, K2, Logan...) unless a place lists them.
- `within`: the id of the place this one is inside (`"within": "library"` on the Psychology Lab). Search results get
  `within_name` ("Library") and the last step says "Arrive at Psychology Lab, inside the Library".
- Several places may share one door (the snack room door is the entry of Yummy Waffle, Vending and ATM): the route
  still announces the place that was asked for.
- `note`: mapper remark, not sent to the app.

## Privacy: the architect's plans

The CAD plans are not public. They live only in `private/plans/` on the machines of the people who map
(`private/` is git-ignored). What is committed is only what we derived: dot positions in metres, lengths, GPS. The
app shows the public signage pictures. Tools that need the plans (`render_plan.py`, `render_graph.py --plan`) write
their output into `private/` too. `GET /api/graph` sends a public copy without plan metres, notes and `verify`
remarks.
