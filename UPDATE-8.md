# Update 8: map pins fixed, all places listed, attic Innovation Lab, outdoor back to your v4

## Apply (PowerShell)
```powershell
cd C:\Projects\Campus_navigation
git checkout main ; git pull
cd C:\Projects
Expand-Archive -Force .\campus-nav-update-8.zip -DestinationPath .
cd C:\Projects\Campus_navigation
Remove-Item -ErrorAction SilentlyContinue data\outdoor\outdoor_draft_v5.geojson, UPDATE-7.md
.\.venv\Scripts\Activate.ps1
python tools\merge_data.py
cd backend ; python -m pytest -q ; cd ..
git add -A
git status
git commit -m "Update 8: outdoor v6 (v4 + joins), map pins, attic lab, floor pictures"
git push
```
Expected: `OK: 38 outdoor + 318 indoor nodes ... 137 searchable places, ... version 8d920a2d1a` and `73 passed`.
`git status` must list `app/assets/floorplans/ground.png, first.png, second.png` (they were missing from your last
push) and nothing from `private/`.
