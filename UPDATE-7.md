# Update 7: indoor map rebuilt on the real door marks (includes update 6)

Your GitHub main is still at update 5, so this zip carries update 6 AND update 7.

## Apply (PowerShell)

```powershell
cd C:\Projects
Expand-Archive -Force .\campus-nav-update-7.zip -DestinationPath .
cd C:\Projects\Campus_navigation
# files that no longer exist
Remove-Item -ErrorAction SilentlyContinue data\indoor\ground_floor.json, data\places_v1.json, tools\node_editor\editor.js, tools\node_editor\style.css
.\.venv\Scripts\Activate.ps1
python tools\merge_data.py
cd backend ; python -m pytest -q ; cd ..
git checkout -b update-7-indoor
git add -A ; git commit -m "Update 7: corridor-based indoor maps, shops, within, caching, rate limits"
git push -u origin update-7-indoor
```
Expected: `OK: 38 outdoor + 314 indoor nodes ...` and `71 passed`. Then open a pull request (or merge to main) so
Render redeploys. Keep `private\plans\` as it is (never committed).

## Tell the Flutter team

- Copy `app/assets/floorplans/ground.png, first.png, second.png` again (same pictures, 60 % smaller).
- Search items may have `within_name` ("Library"): show "inside the Library" under the name.
- Route answers have `to_within`; the arrive step already says it.
- Indoor `points` are now only bends and named places, square on the picture: draw them as they come.
- `429 rate_limited` has a `Retry-After`: show "try again in a moment", don't retry in a loop.
