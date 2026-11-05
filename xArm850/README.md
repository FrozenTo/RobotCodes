# UFACTORY xArm 850 / UF850 — Robotics Code Archive

**Robot:** UFACTORY xArm 850 (UF850), used for vertical-wall drawing, manual Xbox control, and automated marker pickup/return. **Physical media:** A3 paper mounted on a wall; a 3D-printed marker-holder rack with locating stop was added in later projects. **Robot IP in saved scripts:** generally `192.168.1.208`.

This is an **archive of developmental versions**, not a single fully validated deployment. The author confirmed successful text writing, hand-traced SVG drawing, smooth controller movement after tuning, standalone freehand v2.2, and marker-handling trials. Some later full-app operations remain source-implemented rather than verified end-to-end. Preserve each version's original marker/calibration coordinates instead of merging them.

## Project index

| Folder | What it contains | Documentation status |
| --- | --- | --- |
| [motion-tests](motion-tests/) | Initial xArm/UF850 connection, Cartesian jog and Tkinter movement tests | **Reviewed** |
| [controller-tests](controller-tests/) | Xbox XYZ velocity control, early joint selection, controller response and jitter fix | **Reviewed** |
| [text-writing](text-writing/) | Wall alphabet (including Estonian characters), four-corner paper calibration, multiline GUI versions | **Reviewed** |
| [svg-and-text-drawing](svg-and-text-drawing/) | Manual Inkscape Narva College SVG transplanted from MG400, 4/8-point calibrations, optional heading and GUI | **Reviewed including recovered variants** |
| [freehand-drawing](freehand-drawing/) | Tkinter paint-like editor, saved JSON drawings, unsafe early READY path and author-approved v2.2 | **Reviewed including recovered JSONs** |
| [combined-controller-and-drawer](combined-controller-and-drawer/) | Integrated controller, SVG/text/freehand, eight-point then clipped five-point A3 calibration, marker/color automation | **Reviewed through later READY/headline revisions** |
| [marker-handling-tests](marker-handling-tests/) | Eight isolated tests: rack pickup, transfer at Z≈520, wrist-compatible READY, handoff, return | **Reviewed** |
| [mister-bean-demo](mister-bean-demo/) | Standalone embedded 40-stroke demo with G2 marker pickup, two manual cap handoffs, drawing and return | **Reviewed; demo X-offset documentation corrected** |
| [shared-drawing-website](shared-drawing-website/) | Local PC-hosted collaborative color drawing website, gallery and `xarm850-freehand-v1` JSON export | **Reviewed; no direct robot connection** |

## Actual development progression

1. **Basic movement:** xArm TCP commands and safe positioning experiments in `motion-tests/`.
2. **Xbox controller:** smooth continuous velocity-driven X/Y/Z, later joint control; author-reported severe single-axis jitter improved after adjusting timeout, smoothing, acceleration and deadzone together. The specific individual cause cannot be isolated from that four-setting change.
3. **Wall writing:** MG400 nine-point font adapted to vertical **Y/Z** drawing with **X** for marker contact. Joint-space READY approach, 4 measured wall/paper corners and multiline writing.
4. **SVG/text drawing:** manually traced Narva College SVG from Inkscape, first 4 and then 8 paper X/Y/Z calibration points; GUI selectable SVG and heading text with editable marker contact offset.
5. **Freehand drawing:** Tkinter vector canvas, drawing JSON import/export and optional air drawing; the early Cartesian READY approach caused a concerning arm movement, while **v2.2** was author-reported satisfactory and became the combined app's freehand implementation.
6. **Combined controller:** prior controller + lettering/SVG + freehand GUI; refined movement routing and drawing state management.
7. **Five-point wall reachability:** the robot could not reach the physical A3 page's upper-right region. Versions v4/v6/v7 use a **clipped five-point reachable polygon**, correct X-offset-neutral paper coordinates and retain actual out-of-limit teaching attempts as reference only.
8. **Marker handling:** isolated pickup, marker transfer, new wrist-compatible READY, J1-based handoff and holder-return test scripts; a physical 3D-printed rack improved insertion repeatability.
9. **Full marker apps:** older versions had **unnecessary exact-start-pose refusal gates**; later applications implemented automatic waypoint routing for R3 pickup/L3 return, simultaneous J1–J4 control, color-by-color drawing and operator cap handoffs.
10. **Later full-app updates (2026-11-05):** [READY-routing revisions](combined-controller-and-drawer/full-marker-app/ready-routing-revisions/) implement **L1 = Go to READY**, unify normal drawing READY with the marker-compatible wrist configuration, then add heading repositioning inside the five-point reachable region. **Code implemented ≠ every route physically validated**.
11. **Related standalone outputs:** [Mister Bean self-contained demo](mister-bean-demo/) and [student shared drawing website](shared-drawing-website/), which creates JSON but does **not** operate the robot.

The [recovery map](../RECOVERED_UPLOAD_MAP_2026-11-04.md) documents the 33 files omitted by the original 100-file browser upload. The [latest five-file upload map](../XARM_LATEST_UPLOAD_MAP_2026-11-05.md) verifies the four later full-app Python versions and distinct saved settings JSON. Original uploads and history were preserved.

## Most important physical calibration details

**Paper surface vs marker length:** writing on a vertical wall required measuring X depth to a fraction of a millimetre. Paper points define the surface; a separate **marker contact X offset** compensates for marker length/projection from the gripper. Reinserting a marker previously changed its projection. The **3D-printed rack/locating backstop** improved repeatability so the author reports no further routine X recalibration after the later setup.

**No automatic contact-force control:** incorrect X can leave the marker floating or **crush it into the wall**. This remains an unsolved safety/quality limitation, even if the rack helps keep insertion consistent.

**Offsets are historical, not interchangeable.** The author specifically confirmed **−12.3 mm** touches correctly with the later full-app marker/rack setup, while those Python files still define an older **−19.17 mm** default. A separately embedded [Mister Bean demo](mister-bean-demo/) instead defines **−8.55 mm**; its original README inaccurately claimed −19.17 and has been corrected. These are values for **different source/configuration states**, not a single universal standard.

**A3 reachable area:** eight-point drawing versions use an estimated rectangular working envelope; later five-point versions clip the upper-right reach-limited region. Do not force a drawing into the unreachable area just because its JSON or SVG fits the site's default rectangular dimensions.

**READY wrist branches:** compatible XYZ may correspond to significantly different J4/J5/J6 configurations. Later development unified the READY joint posture across drawing and marker handling after staged pickup→transfer→READY/handoff experiments. Automatic routing reduces needless manual exact-pose gates but cannot guarantee collision-free travel from every possible starting configuration.

## Archive rules and verification status

- **Python, JSON, SVG, route coordinates and robot settings remain unchanged** during README reviews and reorganization. File maps preserve SHA-verified copies.
- **Source-implemented** means a function and planned path exist in the repository; **author-tested** records a reported hardware observation. Neither is a substitute for retesting a changed fixture.
- For any live run, check actual robot/joint state, mounted marker, correct settings file, physical E-stop, full arm/rack/wall clearance, clipped reach polygon and calibrated contact X.
- The **shared drawing website** is a separate LAN-only editor; students can't issue live xArm movement commands through it.
- The **Mister Bean demo** is a standalone operator-assisted presentation; it is not the latest integrated full marker app.

**xArm project-folder review complete as of 2026-11-05.** Individual future changes should be tracked in their own versions/README updates rather than overwriting this historical baseline.
