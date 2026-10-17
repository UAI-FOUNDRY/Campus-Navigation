# How to add or change something on the map

After ANY change: `python tools/merge_data.py`, then `python tools/check_routes.py --all`, then
`cd backend ; python -m pytest`, then commit `data/` (including `data/build/campus.merged.json`). Restart Flask
(or redeploy) because the server reads the graph once at start.

## Common changes (no plan needed)

- **A room is renamed / repurposed** (the signage changed): in `data/places.json` change `name`, put the old name in
  `aliases`. Keep the `id`. If the door dot has a `name`, change that too (the steps say it).
- **A new room on an existing corridor**: add a `door` dot on the door mark and pick its corridor in "sits on
  corridor" (node editor, below). No line needed. Then add a place in `data/places.json` with that dot in
  `entry_nodes` (add `"within": "<place id>"` if it is inside another place, like a lab inside the library).
- **A door is closed / a corridor is blocked**: give the line `"type": "restricted"` (A* never uses it). Delete the
  type again when it reopens. For a door that is closed only sometimes, see docs/edge-cases.md.
- **A tape measurement disagrees with the plan**: put `"meters": <tape>` on that line. The merge prints a warning when
  tape and plan differ a lot, so you notice typos.
- **A new floor** (e.g. third floor): copy `sf.json` to `tf.json`, set `code`, `floor`, `label`, `image`,
  `image_size`, `display_anchors`, start ids with `a3_`, and add the floor's lift/stair dots to the lists in
  `building.json > vertical`.

## Indoor: corridors and doors (node editor, plan mode)

1. Put the architect's PDFs in `private/plans/` (never commit them).
2. `python -m pip install pymupdf` once, then `python tools/render_plan.py gf` (or ff, sf). This writes
   `private/plans/gf.png` at 25.2 pixels per metre.
3. Double-click `tools/node_editor/index.html`. **Open JSON** -> `data/indoor/gf.json`; **Open image** ->
   `private/plans/gf.png`. The panel shows "plan mode". Green lines are corridors, dashed green = door stubs.
4. **Corridors first** ("Add corridor", key 4): click along the MIDDLE of the corridor, at each bend, and on every
   dot where another corridor joins (so both share it). Enter = finish, then give it the name students should hear
   ("Block B corridor", "Library", "Lobby"). Keep it straight and square: the app draws exactly this line. In open
   areas (library, lobby, quadrangle) draw the aisle people actually walk, not a diagonal.
5. **Doors**: "Add dot" on the door mark of the plan (the middle of the opening, where the door swing starts), give
   it a name, then choose its corridor in "sits on corridor". Lifts and stairs: put the dot at the landing door.
   Exits: `exit` type + a link (below).
6. Only use "Add line" for what a corridor can't describe (e.g. steps between two levels).
7. **Download JSON**, save over `data/indoor/gf.json`, run the commands at the top.
8. To check by eye: `python tools/render_graph.py gf --plan "private/plans/UAi_LEARNING_CENTER_-_GF_2026.pdf"` and
   `python tools/render_graph.py gf --signage` (pictures go to `private/`; the signage one is what the app shows).

The plan may show a future layout. When the building on the ground differs from the plan, the building wins: move
the dot to where the door really is, and use the signage name.

## Indoor <-> outdoor links

An `exit` dot needs a link (editor "Links" box): indoor dot + outdoor dot id. Leave metres empty: it is computed from
GPS. The outdoor dot must exist in the newest outdoor GeoJSON as `entrance` (with a name) or `junction`, within 6 m of
a path line. If the merge says the dot is far from the door, move the dot in geojson.io.

## Outdoor (geojson.io)

1. Open the newest `data/outdoor/outdoor_draft_vN.geojson` in geojson.io (Open > File).
2. Edit dots and lines. Keep ids unique, never rename an id. Where two paths meet, put a junction dot ON both lines.
3. Save as the next version (`outdoor_draft_v(N+1).geojson`) in `data/outdoor/`.
4. `python tools/check_map.py` must say `0 problem(s) that can break routes`.

## The GPS tie-in (georef)

`building.json > georef > control_points` pairs plan positions with outdoor dots on the facade. If facade doors are
moved in geojson.io, the merge prints the new fit error; above 4 m it warns. Add a control point when you add an
outdoor dot that sits exactly on the building wall (use its `pos` from the plan).
