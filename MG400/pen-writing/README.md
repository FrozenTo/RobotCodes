# MG400 pen writing — project review

**Robot:** Dobot MG400  \
**Project:** Text writer / nine-point stroke alphabet  \
**Status:** Most feature-complete source identified; historical physical test status not independently verified.  \
**Reviewed:** 2026-11-03

## Purpose

Write text with the MG400 using a pen attached to the robot. Characters are drawn as sequences of strokes over a 3×3 numbered point grid, with optional additional points for crossbars, diacritics and dots. The first row uses a configurable writing start, with later rows offset along robot X; letters and spaces advance along robot Y.

The program supports **A–Z**, **Ä Ö Ü Õ**, and punctuation **! ? .**, plus spaces. An independent fixed-coordinate underline routine is also provided.

## Which files belong together?

| File or folder | Role |
| --- | --- |
| `mg400_writer.py` | Core robot TCP/IP connection, alphabet, geometry and motion commands |
| `mg400_writer_app.py` | Tkinter desktop GUI; imports the above core |
| `mg400_writer_state.json` | Saved settings, text and up to five named robot XYZ/R poses |
| `legacy-versions/mg400_writer.py` | Older core without live pose query / saved-pose movement helpers |
| `legacy-versions/mg400_writer_app.py` | Older GUI without JSON persistence or saved position controls |
| `alternate-upload-copies/desktop-2026-11-03/` | Later desktop upload; core and GUI are byte-identical copies of the current versions |
| `archive-compiled/` | Original cached bytecode, retained for history; not required to run |

**Run the modern pair together:** `python mg400_writer_app.py` from this directory on a Windows PC with Python and Tkinter. The core uses Python standard-library sockets, so no third-party Python robotics SDK is required. The older pair should likewise be kept together when comparing behavior.

## Development history: legacy vs current

| Feature | Older pair | Current pair |
| --- | --- | --- |
| Nine-point glyphs, Estonian characters, punctuation, spaces | Yes | Yes |
| Adjustable glyph size, pen drop, character/space spacing, row controls | Yes | Yes |
| MG400 dashboard/motion commands over Ethernet | Yes | Yes |
| Fixed underline routine | Yes | Yes |
| Tkinter writing interface and robot connection controls | Yes | Yes |
| Saved settings, text and JSON persistence | No | Yes |
| Five editable named positions | No | Yes |
| Read real XYZ/R position with `GetPose()` | No | Yes |
| Direct move to saved XYZ/R with `MovJ(...)` | No | Yes |
| Copy a saved position into the writing-start fields | No | Yes |

The newer GUI also has a larger window and a section for managing named poses. The core lettering algorithm, point mapping and ordinary TCP/IP movement workflow are essentially the same; the major evolution is **saving/retrieving positions and restoring the application state**.

## How it works

1. Configure the robot IP, port numbers, speed, pen drop and writing geometry. The source default IP is `192.168.2.6` with dashboard port `29999` and motion port `30003`.
2. Connect, then use **Setup Robot** if the robot needs `ClearError()`, `EnableRobot()`, and `SpeedFactor(...)`.
3. **Move to Writing Start** explicitly before writing. The `Write Text` button **does not automatically move to the start**; letters are drawn with relative `RelMovL` movements from the robot's current pose.
4. The program lifts/lowers the pen along Z and draws each glyph stroke in the horizontal plane. A new row changes the calculated base X position, but does not itself move the robot.
5. The current GUI can read a live `GetPose()` into one of five presets; **Use as Start** fills the base pose fields, whereas **Go** sends a direct absolute `MovJ` to that pose.

## JSON settings and calibration

`mg400_writer_app.py` loads and saves `mg400_writer_state.json` beside the script using `Path(__file__).resolve().with_name(...)`. It stores `settings`, `presets`, `last_used_preset`, and `text`.

The checked-in file is historical and **overrides the Python defaults** at startup. For example, the JSON contains robot IP `192.168.1.6`, base Z `-182.1`, base R `-140.0`, and speed factor `100`. Do not assume those values match today's MG400, paper height, pen fixture or correct network port.

The five saved names in the checked-in data are **Point 1**, **Narva**, **Tasub**, **Tulla**, and **calibration**. These are pose presets, not alternate versions of the program. A desktop copy of the GUI without the accompanying JSON will load source defaults instead.

## Source-review warnings (not physical tests)

- **No automatic start before writing:** `Write Text` uses relative commands immediately. The actual robot must first be at the intended lifted writing start, or the writing can appear in the wrong place. If improving this app, use an explicit safe route to the calibrated start instead of assuming the robot is already there.
- **No enforced paper-boundary checks:** `paper_min_x`, `paper_max_x`, `paper_min_y`, and `paper_max_y` are stored but the core comments explicitly say they are not enforced. Long text and multiple rows may leave the paper or work area.
- **Movement replies are not validated:** the code logs robot responses but does not reliably check for controller error codes, wait for motion completion, or enforce a pen-up recovery on failure. The `move_delay` setting is only a fixed delay after commands.
- **The GUI can freeze during writing:** motion calls run in Tkinter button handlers on the UI thread; there is no dedicated worker, queued-job cancellation, or GUI Stop button.
- **Direct saved-pose moves:** `Go` sends one absolute `MovJ` without intermediate clearance waypoints. A saved pose should not be assumed reachable without an obstacle-free route.
- **No input preflight:** an unsupported character raises an exception during text writing, potentially after some characters have already been drawn.
- **Old dry-run switch:** these historical files contain a `Live robot` checkbox / `live_robot` setting. The saved state has live mode enabled. Do not treat the dry-run option as a requirement for new control applications.

These observations are based on **source inspection**, not robot testing. Preserve the history; changes to motion safety and workflow should be designed and tested separately.

## Relationship to later projects

Several MG400 image/SVG drawing and pen-calibration scripts import the same `MG400Writer` class. Their own project directories contain unchanged copies of the current `mg400_writer.py` to preserve local imports. That makes this project a useful starting point for reviewing the rest of the MG400 archive.

## Recommended catalog status

**Primary candidate:** the main-directory `mg400_writer.py` + `mg400_writer_app.py` + `mg400_writer_state.json`.  \
**Historical variant:** the self-contained pair under `legacy-versions/`.  \
**Verified functionality:** by code inspection only. **Working status on physical hardware:** to confirm against the user’s testing history.

No robot scripts or stored poses were edited in this review.
