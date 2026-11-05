# RobotCodes — Robotics Code Archive

This repository preserves Python robot-control experiments, working applications, historical revisions, calibration settings, artwork and supporting websites developed for **Dobot MG400** and **UFACTORY xArm 850 (UF850)**. Each robot has a separate project index and detailed per-project READMEs. Some projects were **successfully demonstrated on the real robot**; others remain experiments, prototypes or source-only implementations.

> **Start here:** [MG400 development history](MG400/README.md) · [xArm 850 / UF850 development history](xArm850/README.md) · [Final file-integrity audit](ARCHIVE_AUDIT_2026-11-05.md)

## Robot and project navigation

### Dobot MG400 — tabletop projects

| Project | Contents / historical result |
| --- | --- |
| [Pen Writing](MG400/pen-writing/) | Nine-point letter grid, Python/Tkinter GUI, saved positions, multiple lines and Estonian characters; **author-confirmed working** |
| [Pen Calibration](MG400/pen-calibration/) | 3D-printed flexible off-axis pen holder, R-axis tip arcs and reachable-area experiments; calibration remained approximate |
| [Image and SVG Drawing](MG400/image-and-svg-drawing/) | Hard-coded vector experiments followed by **successful manually traced Inkscape Narva College SVG** |
| [Keyboard and Xbox Controller](MG400/controller/) | Keyboard/gamepad jogging, tool outputs, joint selection and GUI; working MG400 control, with single-axis manual-jog limitations |
| [Slider Control](MG400/slider-control/) | Tkinter XYZ/R and joint sliders for target moves; proposed live slider-follow behavior was **not implemented** |
| [Grid Pick-and-Place Website](MG400/grid-pick-and-place-website/) | **Separate course/lesson project** with Flask, grid positions, cameras and AtomS3R glass/assembly height tiers; documented, but complete physical assembly not verified |

[MG400 README](MG400/README.md) explains the development sequence, tested behavior, device/network changes and known problems. The grid website is kept with MG400 because it controls that robot, but its lesson context is **not** the same as the personal writing/controller experiments; see the related [RoboticsLesson repository](https://github.com/FrozenTo/RoboticsLesson).

### UFACTORY xArm 850 / UF850 — controller, wall writer and marker rack

| Project | Contents / historical result |
| --- | --- |
| [Motion Tests](xArm850/motion-tests/) | First UF850 connection, pose and jogging experiments |
| [Controller Tests](xArm850/controller-tests/) | Xbox Cartesian velocity movement, joints and smoothing/jitter experiments |
| [Text Writing](xArm850/text-writing/) | Vertical-wall lettering, multilingual text, multiline GUI; **author-confirmed working** |
| [SVG and Text Drawing](xArm850/svg-and-text-drawing/) | Adapted the successful MG400 Inkscape artwork to an A3 wall, using 4- then 8-point paper calibration |
| [Freehand Drawing](xArm850/freehand-drawing/) | Mouse-drawn vector strokes, drawing JSONs and versions through **author-approved v2.2** |
| [Combined Controller and Drawer](xArm850/combined-controller-and-drawer/) | Integrated Xbox control, SVG/text/freehand, clipped five-point wall geometry and later full marker-changing apps |
| [Marker Handling Tests](xArm850/marker-handling-tests/) | Eight staged marker pickup, Z≈520 transfer, compatible READY, handoff and rack-return experiments |
| [Mister Bean Demo](xArm850/mister-bean-demo/) | **Confirmed complete successful physical demonstration:** pickup, cap handoff, drawing, cap replacement and return to holder |
| [Shared Drawing Website](xArm850/shared-drawing-website/) | PC-hosted collaborative LAN editor, 12 marker colors and saved `xarm850-freehand-v1` JSON; **does not directly control the robot** |

[xArm850 README](xArm850/README.md) documents the end-to-end development history, including the code versions, excessive exact-start-pose gates, later automatic READY routing, and five-point calibration of the A3 reachable area. The [latest READY-routing revisions](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/) include L1 Go to READY and a unified wrist-compatible drawing/marker READY configuration.

## How the work developed across both robots

The MG400 projects established Python robot communication, letter writing and drawing. After early attempts to generate an accurate Narva College building outline from images failed, the artwork was **manually traced in Inkscape**; that SVG drew well on MG400 and was adapted to xArm's **vertical Y/Z wall**.

MG400 gamepad jogging worked but the tested MoveJog workflow did not provide the **simultaneous multi-axis response** sought for manual control. That led to smooth Cartesian controller development on xArm and then to combined wall-writing, SVG, freehand and marker-handling apps.

The xArm marker rack evolved through isolated experiments. A **five-point clipped paper polygon** addressed the physically unreachable upper-right A3 region; separate marker-tip X offset accounts for tool projection. An early full app imposed excessive exact-waypoint start requirements, which later builds replaced with more automatic intermediate-waypoint routing. The standalone Mister Bean demonstration ultimately **completed its entire pickup→draw→return sequence on real hardware**. The later multi-color full-app workflows are present in source but **not confirmed end-to-end** on the physical robot.

## Important physical setup and configuration notes

- **MG400 historical Ethernet:** robot/network setup varied; commonly `192.168.2.6`, later `192.168.1.6` and one Ethernet port found at `192.168.3.6`; dashboard **29999**, motion **30003**. Use the actual connected robot address.
- **xArm historical address:** generally `192.168.1.208`, via the UFACTORY xArm Python SDK. Controller/gamepad apps have their own dependencies and launch instructions.
- **Keep settings next to the correct script.** A later xArm full app looks for `xarm_850_full_app_settings.json` in the running `.py` file's directory. The author **confirmed** that moving older JSONs into a different folder while continuing development elsewhere caused the app to miss its saved offset and use the old Python default. Saving then wrote a new JSON beside the active script. The former settings were **misplaced relative to the code, not necessarily deleted**.
- **xArm marker contact offsets are version- and marker-specific:** later correctly loaded full-app JSON **−12.3 mm** was author-confirmed to touch paper properly; the old Python default **−19.17 mm** would move about **6.87 mm deeper toward the wall** on that same setup. The standalone successful Mister Bean demo uses its own fixed **−8.55 mm** offset, recalled to be for a **new marker**. **Do not interchange these calibrations.**
- **No automatic marker force regulation:** incorrect contact X can leave no ink or damage/crush the marker. The 3D-printed rack helps insertion repeatability but cannot replace checking actual tip depth.
- **READY wrist configuration and paper reach:** a matching tool XYZ does not guarantee matching J4/J5/J6 angles. The later full app unified the READY posture. The A3 page's upper-right clipped region is a **real reachability constraint**, not an unnecessary application restriction.
- **Physical robot safety:** these are **live-capable archived scripts**, not universally safe simulations. Inspect calibration, work area, full arm/tool clearance, source/default versus loaded settings, wrist posture and hardware E-stop before use. A source-implemented routine is not automatically physically validated.

## Original uploads and file provenance

No historical Python, JSON calibration, SVG artwork or robot-motion code was rewritten during archival review. Files with the same names may be **different versions**, and historical duplicates exist deliberately so an experiment's local imports/settings remain associated with that experiment. The [audit report](ARCHIVE_AUDIT_2026-11-05.md) separates original-file SHA checks from subsequently edited documentation.

| Map / snapshot | Scope |
| --- | --- |
| [Initial upload map](FILE_MAP.md) | **100** paths from the original first GitHub upload |
| [Desktop upload map](DESKTOP_UPLOAD_MAP.md) | **26** additional desktop-uploaded paths |
| [Recovered upload map](RECOVERED_UPLOAD_MAP_2026-11-04.md) | **33** paths missing from the original 100-file upload, recovered by re-uploading the complete 74-file `Even more robot apps` folder |
| [Latest xArm upload map](XARM_LATEST_UPLOAD_MAP_2026-11-05.md) | Four later full-app Python versions and one settings JSON, uploaded at repository root and copied to their project folder |
| [Final archive integrity audit](ARCHIVE_AUDIT_2026-11-05.md) | Project index and Markdown-link checks, current file/duplicate counts, original READMEs kept versus actively revised READMEs |

The original first-upload snapshot exists at [commit `228505c`](https://github.com/FrozenTo/RobotCodes/tree/228505cc98f67b9763884a343112d4a156ddf6a3) (branch `backup/original-layout-2026-11-03`). The before-desktop-reorganization snapshot is [commit `a5fc634`](https://github.com/FrozenTo/RobotCodes/tree/a5fc63477cf3fca7d861f8b1d802694f9dbc8956) (branch `backup/before-desktop-organization-2026-11-03`). **The first snapshot contained only 41 of the 74 files** eventually re-uploaded under `Even more robot apps/`; the complete raw folder is also preserved on `main`.

## Review status

**MG400's six project folders and xArm850's nine project folders have all received source-grounded README reviews as of 2026-11-05.** This means the **archive/documentation review is complete**, not that every robot application has passed a final hardware acceptance test. Further work should add clearly labeled versions rather than overwrite previous successful or experimental sources.
