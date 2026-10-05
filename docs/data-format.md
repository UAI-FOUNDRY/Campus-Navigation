# Data format (outdoor, as agreed so far)

## Points
| type       | use                                              | example id            |
|------------|--------------------------------------------------|-----------------------|
| gate       | gate into campus                                 | gate_main             |
| junction   | where paths split, meet or turn sharply          | junction_01           |
| entrance   | a door into a building or shop                   | makalu_entrance       |
| room_door  | a classroom that opens directly outside          | door_cr12             |

## Lines
| type       | use                                              |
|------------|--------------------------------------------------|
| path       | normal walkable road or footpath                 |
| steps      | path with stairs (add note)                      |
| ramp       | ramp                                             |
| restricted | path not open to everyone                        |

Lines may pass through several dots; the converter splits them at each dot.

## Properties
- id: unique, lowercase with underscores. NEVER rename once indoor data, photos or QR codes use it.
- name: what students call it (shown in the app). Required on entrances and room doors.
- building: block the door belongs to (optional)
- access: unknown | open | restricted (set after walking the campus)
- note: free text
