# Campus Navigation (Universal AI University, Karjat)

Campus navigation feature for the college app: find the shortest route from the main gate to a
building or classroom, outdoors and indoors.

**Stack:** A* routing, Flask REST API, Flutter UI, GeoJSON campus data.
**Deadline:** 20 Oct 2026.

## Folders
- `data/`    campus data (source of truth). Start with `data/outdoor/outdoor_draft_v2.geojson`.
- `tools/`   scripts that convert, merge and validate data; floor plan node editor.
- `backend/` Flask API and A* routing.
- `app/`     Flutter app (run `flutter create .` inside this folder, see app/README.md).
- `docs/`    data format and mapping guide.

## Status
- [x] Outdoor draft v2 drawn in geojson.io
- [ ] Walk the campus and verify paths
- [ ] Converter script (GeoJSON -> graph)
- [ ] Pilot building floor plans
- [ ] Flask API + A*
- [ ] Flutter map and search screens
