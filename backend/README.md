# Backend (Flask + A*)

Run everything from the repo root unless a `cd` is shown.

## 1. Build the graph (outdoor map + indoor floor + places)
    python tools/merge_data.py          # uses the newest data/outdoor/outdoor_draft_vN.geojson,
                                        # data/indoor/ground_floor.json and data/places_v1.json
    python tools/validate_graph.py

Re-run both whenever any data file changes, then commit `data/build/campus.merged.json`. Warnings tell you what is still
missing (for example the outdoor dot `quad_south_entrance` that the south entrance must join). `python tools/convert_geojson.py`
still builds an outdoor-only graph.

## 2. Install and test
    cd backend
    pip install -r requirements.txt
    pytest

## 3. Run the API
    cd backend
    flask --app wsgi run --debug                  # http://127.0.0.1:5000
    flask --app wsgi run --host 0.0.0.0           # reachable from a phone on the same Wi-Fi
    gunicorn wsgi:app                              # production

The Android emulator reaches your computer at http://10.0.2.2:5000. Endpoints and example responses: `docs/api.md`.
