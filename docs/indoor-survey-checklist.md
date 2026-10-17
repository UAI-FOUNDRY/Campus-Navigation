# Indoor survey checklist (walk these before trusting the indoor map)

The indoor map was built from the architect's plans (dates 01.09.2026 and 22.01.2026). The plans can show a newer
layout than the building today, so a few dots need a quick on-site check. For each one: walk there, fix the dot in
the node editor if needed, delete its `verify` note, merge, commit.

## Dots placed from the plan that need a look

(Generated from the merged map: every dot with a `verify` note.)

**Ground floor** (gf.json)

- `a0_accounts` Accounts Office: Signage only: north-east corner of the lobby. Check the door.
- `a0_clinic` Clinic: Plan shows a plant room here; signage shows the Clinic. Check the door.
- `a0_counseling_lab` Counseling Lab: The plan shows one double door (Psychology Lab); check where the Counseling Lab door is.
- `a0_lobbya_w_exit` Block A side door (by Yummy Waffle): Fire exit on the plan; the outdoor Vending entrance is right outside. Check it is open in the day.
- `a0_merch_store` Merchandise Store: Signage only: east side of the lobby.
- `a0_stair_lib` Library staircase: Steel staircase ST-02; check students may use it.
- `a0_study_pods` Study Pods: Signage only: east side of the lobby.
- `a0_wellbeing` Wellbeing Office: Signage only (the plan shows a small enclosure by Executive Dining). Check the door.

**First floor** (ff.json)

- `a1_counseling` Safe Space (Counseling Room): Door side not visible on the plan.
- `a1_dhaulagiri_door` Mount Dhaulagiri: Door read from the drawing, not a door mark.
- `a1_exam_office` Examination Office: Plan: Data room / Faculty Cabin 126.
- `a1_lift_b` Lift (Block B): First-floor plan draws a tutorial room here; signage shows the lift.
- `a1_siesta_lounge` Staff Siesta Lounge: Plan: Office; door side not visible.
- `a1_wellness` Wellness Room: Door read from the drawing, not a door mark.

**Second floor** (sf.json)

- `a2_auditorium_door` Auditorium / Multi Sports Centre: Entrance position estimated along the passage.
- `a2_design_counseling` Design Counseling Room: Plan: Design Display.
- `a2_music_room` Music Recording Room: Door side estimated.
- `a2_school_music` School of Music, Sound & Cinematics: Plan: Conference Room; door side estimated.
- `a2_sound_studio` Sound Studio: Door side estimated.
- `a2_untersberg_door` Untersberg Mountain: Signage puts Untersberg (16) where the plan shows Sound Studio 03; door side estimated.

## New in update 7: check these on the walk

- **Aspretto**: dot `a0_aspretto` is at the plan's "Coffee shop" by the spiral staircase, opening onto the lobby
  aisle. Check the counter's side.
- **Snack room (Yummy Waffle, Vending, ATM)**: the room the plan calls DATA-02, door `a0_shop_a` on the small hall
  south of Everest. Is the ATM in there too? If not, move the ATM place to its own door.
- **Lobby (Block B)**: the aisle is drawn down the middle (x = 57 m) from the Admin Lobby gate. Accounts Office,
  Study Pods and Merchandise Store are from the signage only (the plan shows steps on the east side): find their doors.
- **Library**: the aisle goes from the library door north, then west to Kosciuszko and the library staircase, with a
  branch to the Psychology and Counseling Labs. Walk it: if students walk a different aisle, move the corridor points.
- **First floor, north part of Block A** (Thomson Reuters room, washroom, Wellness Room, Dhaulagiri): the plan has a
  double wall between them and the Aconcagua/McKinley rooms, so the map reaches them through the Student Seating
  Area (mezzanine). Confirm that is the way in.
- **Second floor, Block A**: Passage 02 is only drawn south of Passage 01 (north of it the plan has the IoT lab and the
  lift). The studios are reached by the ramp (west) and Passage 03. The AI lab is entered through the lobby area
  north of Passage 01. Confirm.

## Plan distances vs the team's tile measurements (ground floor)

Most legs agree within a few metres, which also confirms the plan reading. The legs below differ; the plan is
used for now. Re-walk them and, if the tape is right, put `"meters"` on the line or move the dots.

- Quadrangle south entrance to Admin Lobby gate: team 40 m, plan 29 m (plan goes up the east walkway to the lobby's
  middle opening; check which opening is the "gate").
- Cafeteria/Mess inside door to Library: team 32 m, plan 18 m (plan uses the library's corridor door; the team's point
  may have been inside the library).
- Mount Lhotse to Clinic: team 14 m, plan 41 m from the FRONT door, but only 2 m from Lhotse's back door. The team
  probably walked through the hall; Lhotse now has both doors as entrances.
- Mess inside door to mess back entrance (outdoor dot): team 19 m, plan 28 m (12 m of it is from the cafeteria back
  door to the outdoor dot; the dot may sit too far out in the sitting area).
- Agreeing within 3 m: Admin Lobby to Mess (27 / 28), Library to Everest (19 / 18), Everest to Lhotse (21 / 26),
  Clinic to quadrangle entrance (15 / 14).

## Questions only the team can answer

- Is the Block A side door (fire exit by Yummy Waffle / Vending) open in the day? It makes Everest to Logan 76 m
  instead of 199 m. If it is locked, set that line to `restricted`.
- Is the middle of the quadrangle walkable (paved) or a lawn? See docs/edge-cases.md.
- Mount Logan, K2 and Makalu: only outside doors (as now), or also doors from the library?
- First floor Block B: the plan draws a tutorial room where the signage shows the lift. Where is the lift door?
- Second floor Block A: the plan shows one big classroom where the signage has Mauna Kea and Mount Vinson.
- Which door students use for the Auditorium / Multi Sports Centre (second floor).
