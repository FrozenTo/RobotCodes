# UFACTORY xArm 850 (UF850)

| Project | Purpose |
| --- | --- |
| [text-writing](text-writing/) | Wall lettering/writing core and Tkinter app iterations |
| [svg-and-text-drawing](svg-and-text-drawing/) | Wall SVG / drawing GUI with example SVG and reference images |
| [freehand-drawing](freehand-drawing/) | Mouse-drawn strokes, settings, standalone variations and example JSON drawings |
| [combined-controller-and-drawer](combined-controller-and-drawer/) | Integrated gamepad control, lettering, SVG and freehand drawing |
| [controller-tests](controller-tests/) | Early controller/joint and pose-reading scripts |
| [marker-handling-tests](marker-handling-tests/) | Recovered isolated marker pickup, return and handoff motion tests |
| [motion-tests](motion-tests/) | Connection and jog experiments |
| [mister-bean-demo](mister-bean-demo/) | Standalone preprogrammed Mister Bean presentation demo |
| [shared-drawing-website](shared-drawing-website/) | LAN drawing website: server, launch scripts, HTML/CSS/JS and saved JSON drawings (recovered from desktop) |

These names refer to the same physical robot family. The script filenames use both `xarm` and `uf850`.

## Recovered later applications (2026-11-04)

The full original **74-file `Even more robot apps`** folder has now been verified and restored: the first GitHub upload included only 41 of those files. The other 33 omitted paths have been accounted for and 27 new source/data blobs copied into the project structure without modifying bytes; details are in [the recovery map](../RECOVERED_UPLOAD_MAP_2026-11-04.md).

The xArm folder now includes [five-point wall calibration development](combined-controller-and-drawer/five-point-development/) (v4, v6, v7 plus SVG reach tests), the [full marker-rack controller applications](combined-controller-and-drawer/full-marker-app/) including `xarm_850_full_app_normal_marker_speed.py`, and [marker pickup/return test scripts](marker-handling-tests/). These are **historical files with setup-specific motion settings**, not blanket approvals for live execution. The five-point calibration clips unreachable A3 paper space at upper-right and keeps a separate X contact offset; incorrect marker X remains a potential crushing/failed-contact hazard.
