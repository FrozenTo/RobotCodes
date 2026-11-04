# MG400 Grid Pick-and-Place Website — Lab 2 project

**Robot:** Dobot MG400 with vacuum box and single-cup gripper  
**Project type:** **Separate course/lesson project**, not part of the personal pen-writing, drawing or Xbox-controller project sequence.  
**Application:** Local Flask website for managing a Gridfinity work area, moving between cells, and testing pick/place/assembly operations with two camera views.  
**Archive status:** v1.8 application source and configuration preserved. The author reports the website was running and robot control worked during development, but **a complete finished AtomS3R assembly cycle and all Lab 2 acceptance tests are not verified**.  
**Reviewed:** 2026-11-04 (source and linked lesson requirements)

## What the lesson was building

This website supports a larger **robotics / 3D printing and CAD Lab 2** exercise built around a portable MG400 workstation. The physical rig has a Gridfinity base plate in front of the robot, holding 3D-printed input bins, an assembly/workpiece fixture and finished/reject output holders. It is intended to make fixture locations repeatable after the holders are removed and reinserted.

The overall intended assembly uses **three components**:

1. **AtomS3** (ESP32-based unit).
2. **Polycarbonate glass**, approximately 24 × 24 × 2 mm, to be placed on the Atom display.
3. **Battery/lower module**, mounted beneath the Atom.

The exercise starts with a simpler glass transfer: take glass from an input holder, place it on an Atom dummy at a workstation, pick it up again and deliver it to an output holder. The teacher's Lab 2 materials also specify repeatability testing with **four glasses across five cycles**, including removing and replacing the physical holders without retouching individual robot positions. Those are **lesson goals**, not results demonstrated by the presence of this software.

The physical design also calls for two cameras (tool-level and overhead) to help observe the process.

### Related course documentation (separate GitHub repository)

The other repository, [**FrozenTo/RoboticsLesson**](https://github.com/FrozenTo/RoboticsLesson), is the source for the *lesson context* and physical rig—not a replacement for this app's source:

- [3D Printing & CAD — Lab 2 assignment](https://github.com/FrozenTo/RoboticsLesson/blob/main/3d-printing/lab2/Readme.md): workstations, component holders, glass transfer and cameras.
- [MG400 rig system description](https://github.com/FrozenTo/RoboticsLesson/blob/main/3d-printing/lab2/MG%20400%20rakis.md): Gridfinity geometry, physical origin, clearance and calibration procedure.
- [Team's Lab 2 layout](https://github.com/FrozenTo/RoboticsLesson/blob/main/3d-printing/lab2/docs/layout.md): proposed input/workstation/output cells and assembly sequence.
- [Lab 2 progress overview](https://github.com/FrozenTo/RoboticsLesson/blob/main/LAB2_PROGRESS.md): team milestones and outstanding work; many items remain unchecked in the recorded snapshot.
- [Original v1.8 website package](https://github.com/FrozenTo/RoboticsLesson/tree/main/MG400%20python%20apps/mg400_grid_website_v18): another copy of this local Flask website.

The [Smart Solutions Lab 2 assignment](https://github.com/FrozenTo/RoboticsLesson/blob/main/Nutilahendused/lab2/README.md) also describes a more ambitious internet-facing message queue and remote-access system. **That is a separate course objective**; this checked-in grid website is a **local station-control app** and does not implement the assignment's DigitalOcean/HTTPS/Atom-polling architecture.

## Physical grid vs website cell numbering — do not mix

The course rig is physically **7 cells deep × 10 cells wide**, with **42 mm pitch**: 70 possible positions, covering 294 × 420 mm. The physical rig documentation uses names like **B-2** or **E+3**: letters A–G represent *depth from the robot*, while a signed number −5..−1 / +1..+5 represents the side of the robot's centerline. Its coordinates are described in a **design/model frame**.

This website instead represents a **10-column × 5-row working subset**, using labels **A1 ... J5**, with:

- Letters **A–J** across the operator's view, from left to right.
- Rows **1–5** across the working area, with row 1 farthest from the robot (the GUI is drawn with a different visual orientation than the rig's physical-model conventions).
- `X = grid_x_row1 - pitch * (row - 1)`.
- `Y = grid_y_colA + pitch * column_index` (A=0).
- Saved base settings `grid_x_row1=401.19125`, `grid_y_colA=-191.1925`, `pitch=42` mm.
- Originally blocked cells **A1, B1, I1, J1**; other cells should still be checked physically for reach and holder clearance.

**These labels are NOT interchangeable.** Do not take a teacher layout such as `B-2` and issue a website movement to `B2`: those mean different things. The website's Cartesian coordinates are based on an **ideal evenly spaced robot-space grid fit**, not a verified automatic conversion of the teacher's model frame. A real fixture requires coordinate-frame calibration before assuming the two plans refer to the same location.

## Available website functions (v1.8 code)

- **Grid selection and labels:** click a cell, see calculated XY, store a role/label, mark blocked, and save an independent `pick_z` and `place_z`.
- **Manual robot functions:** connect/test, clear error + enable, disable, software STOP; **Move above**, **Pick**, **Place**, **Transfer FROM→TO**.
- **Movement order:** for cell travel, move vertically to a configured safe Z, travel to the destination XY at that height, then descend to the selected cell height. `MovJ` is used for travel and `MovL` for vertical moves.
- **Vacuum tools:** DO2 enables suction; DO1 supplies a short **blow pulse** on release/drop. These assignments reflect the uploaded setup.
- **Station roles:** the interface can tag glass inputs, Atom stations, battery/lower-module stations, finished outputs or rejects. Roles are descriptive; selecting a role by itself does **not** run a complete assembly workflow.
- **Three assembly-level height presets:** glass only, Atom + glass, and full AtomS3R. The version adds separate full-assembly **pickup** and **press/place** Z values.
- **Pick/Place enablement:** these buttons are **intentionally greyed out** when the selected cell is blocked or the matching pick/place Z is missing. Selecting an assembly height preset saves it directly to that cell, so the corresponding button can become enabled; manually edited heights need **Save cell**.
- **Two camera panes:** a XIAO ESP32S3 Sense tool camera on a Wi-Fi address (often factory hotspot `192.168.4.1`) and an ordinary USB table/overhead camera connected to the host PC. The host serves the USB camera through OpenCV. Camera panels and test endpoints are implemented, but reliable simultaneous streaming in the user's actual network arrangement is **not independently confirmed**.
- **Status and configuration:** robot state, editable IP, grid origin/pitch, speed, heights, USB camera index, image resolution and FPS. Robot commands are serialized with a lock; pose reads are retried and checked against a tolerance.

**It is live by design:** this package does **not** have `LIVE_ROBOT=False` or a simulation mode. Opening the website does not automatically enable the MG400, but its movement buttons send commands to the real robot when used.

## Folder layout and versions

| Path | Purpose |
| --- | --- |
| [`v1.8/`](v1.8/) | The full Flask application package and its own historical [README](v1.8/README.md) |
| [`v1.8/server.py`](v1.8/server.py) | Robot TCP command handling, motion sequences, state API and camera endpoints |
| [`v1.8/config.json`](v1.8/config.json) | Saved network, speed, grid geometry, Z heights, tools and camera settings |
| [`v1.8/data/cells.json`](v1.8/data/cells.json) | Per-cell blocked/role/label/pick/place settings |
| [`v1.8/templates/index.html`](v1.8/templates/index.html) | Website layout |
| [`v1.8/static/app.js`](v1.8/static/app.js), [`style.css`](v1.8/static/style.css) | Browser behavior and appearance |
| [`v1.8/requirements.txt`](v1.8/requirements.txt) | Flask, requests and OpenCV |
| [`v1.8/START_WEBSITE.bat`](v1.8/START_WEBSITE.bat) | Windows launch helper |
| [`legacy-v1.6-config/`](legacy-v1.6-config/) | **Only an older v1.6 configuration file**—not a complete runnable v1.6 website |

The source's historical v1.7→v1.8 changes include assembly-height presets, a distinct full AtomS3R press/place Z, and saving a selected preset directly to a cell.

## Critical configuration accuracy (the archived values)

**Read the checked-in JSON before use.** Some descriptive defaults in `v1.8/README.md` were written for an earlier configuration and are **not** the current archived values.

| Setting | v1.8 `config.json` | Notes |
| --- | --- | --- |
| Robot IP | `192.168.1.6` | Ethernet network/port dependent |
| Speed factor | **2%** | The older README says 20%; the code reads **2** from this JSON, reapplies `SpeedFactor(2)` before each move |
| Safe travel Z | **−50 mm** | The older README says −100 mm; the actual code reads **−50** from JSON |
| Grid pitch | 42 mm | Ideal square grid |
| Tool DO | Blow 1, suction 2 | Check physical wiring |
| Tool camera URL | `http://192.168.4.1` | Needs a reachable Wi-Fi route from the viewer/host |
| USB camera | Index 1; 1280×720, 15 FPS requested | May select different hardware on a different PC |
| Glass-only Z | −150.21 mm | Recorded experiment |
| Atom + glass Z | −140.59 mm | Recorded experiment |
| Full AtomS3R pickup | −122.92 mm | Separate from placement |
| Full AtomS3R press/place | **−125.52 mm** | Deeper move intentionally seats/presses part |
| Stored assembly R | −50.18° | Reference setting; ordinary grid movement retains current R |

The v1.6-only configuration had speed factor **3%** and USB camera index **0**, while its safe Z was also **−50 mm**; it did not yet have separate full-pick and full-place Z keys. **Do not copy old v1.6 JSON over v1.8.**

These values are **historical measurements, not a universally safe setup**. The press-fit placement, in particular, must not be applied to a new part without contact/force assessment.

## Local setup (archived package)

Run from within `MG400/grid-pick-and-place-website/v1.8/`:

```bash
python -m pip install -r requirements.txt
python server.py
```

Or use `START_WEBSITE.bat` on Windows. The Flask station page is at **`http://localhost:8765`** on the host and `http://<host-PC-LAN-IP>:8765` from reachable trusted LAN clients. Leave the terminal running; `Ctrl+C` stops the site.

Camera access depends on the actual network: connecting the PC to the XIAO camera's access point can break access to an MG400 on a different wired subnet, or the browser may not reach the direct MJPEG camera URL. **The existence of two image panes does not guarantee both streams work together** on every college Wi-Fi configuration. Route/network planning and live camera testing are still needed.

**This is a local lab-control interface, not a public internet-safe service.** The Flask app binds to `0.0.0.0:8765`, and these archived endpoints have no user authentication. Keep it on a trusted isolated network. The course's DigitalOcean remote-job architecture is a separate task, not present here.

## Safety and open work

- Verify the physical Gridfinity origin and blocked cells before **Move above**. The lesson's model coordinates and this website's live robot coordinates have different names and frames.
- Confirm the current robot IP, both camera routes, **speed factor**, safe-Z clearance, Z pickup/press heights, DO assignments, tool orientation and emergency-stop reach before physical movement.
- The code sends a software `Stop()` on the dashboard; this is **not** the physical emergency stop. Repeated pick/place may require active supervision and mechanical clearance testing.
- `GetPose()` retry/polling reduces some false errors but does not guarantee collision-free motion or validated vacuum grip.
- An independent full assembly recipe, machine vision/crosshair-to-gripper calibration, and completion of the teacher's required 20-glass repeatability test are **not demonstrated** by these saved source files.
- The author's earlier work chat **“Create MG400 Grid App”** documents live website testing and feedback on camera slots, height tiers, disabled Pick buttons and press-in placement. Treat individual live-test results as historical observations, not blanket validation of all assembly stages.

**Catalog classification:** *Course/Lab 2 — MG400 Gridfinity Workstation and Pick/Place Website*, **documented separately** from personal MG400 writer, calibration, drawing and controller work. Preserve original Python/frontend/config values; no motion tests performed as part of this source review.
