# How to add or change something on the map
1. Open data/outdoor/outdoor_draft_v2.geojson in geojson.io (Import).
2. Edit dots and lines. Keep ids unique and never rename existing ids.
3. Export, save as the next version, and commit.
4. Run tools/validate_graph.py, then tools/convert_geojson.py.
