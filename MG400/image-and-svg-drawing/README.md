# MG400 Image and SVG Drawing — project review

**Robot:** Dobot MG400  
**Project:** Off-axis pen drawing across the largest practical paper area  
**Status:** Author reports that drawing worked *reasonably well* with some residual line offsets and slight unwanted curvature; the main later scripts are configured for live robot execution. Exact test results for each file are not individually confirmed.  
**Reviewed:** 2026-11-03

## Why this project exists

This project followed the [MG400 text writer](../pen-writing/) and a series of [pen calibration experiments](../pen-calibration/), but the **R-axis radius manipulation was exclusively for drawing**, not for improving the already successful lettering app.

A lesson project introduced a 3D-printed pen holder consisting of a connection to the MG400 flange, a thin **flexible arm/board**, and a circular grip that holds the pen **off the flange axis**. When the flange rotates in R, the pen tip travels along an arc. This was interesting to explore for its own sake, and it also offered a way to reach otherwise inaccessible parts of an A4 sheet.

The practical R range varied across the workspace. When the robot head shifted left or right, the body/head linkage and pen-holder clearance changed, so an angle that worked in one region might be blocked in another. Interference was a concern **on both sides**, not just the left. The software therefore attempted to select a feasible R orientation for the *pen tip's requested position*, rather than expecting one R to work across the entire sheet.

**Why the drawing could never be perfectly straight:** Under paper contact, the flexible holder bent upwards, pushing the pen tip **slightly farther outward** than the fixed-radius model predicted. That produced a small lateral shift when R changed, and occasionally a slightly curved line through certain multi-direction/zigzag patterns. The author chose to accept these small **drawing-only** imperfections. The earlier **text-writing application worked well** and was not affected in the same way.

## Development progression

| Main script | Purpose and main difference |
| --- | --- |
| `mg400_image_drawer.py` | First hard-coded, normalized architectural/building path experiment. Anchors to the existing pen writer's WritingStart and uses fixed R. **Not a raster image importer.** Its `__main__` explicitly sets `writer.settings.live_robot = False`. |
| `mg400_image_drawer_safe_test.py` | First measured-paper / off-axis pen compensation test: ~260 × 123 mm main rectangle, 220 × 100 mm drawing inset, five measured R orientations, four broad R zones, J4 monitoring and pen-up preflight option. |
| `mg400_image_drawer_ik_safe.py` | Replaces fixed-quadrant R selection with **controller inverse-kinematics preplanning**. Checks each short segment at contact and lifted Z; chooses from measured R candidates subject to J2/J4 margins. Adds `Sync()` barriers and an optional raised-pen preflight. |
| `mg400_image_drawer_continuous.py` | Keeps the short-segment IK checks but **merges adjacent same-R sections of the same path into continuous pen-down strokes**, avoiding unnecessary lift/drop cycles roughly every 10 mm. |
| `mg400_image_drawer_narva.py` | Builds on the continuous motion planner with a considerably more detailed, manually defined **Narva College architectural sketch** (roof, facade, windows, arches and foreground). |
| `mg400_svg_drawer.py` | Most general-purpose candidate: **loads external SVG**, parses shapes and transforms, flattens curves/arcs, scales/centers paths on the measured paper area, simplifies short paths, and uses the same IK/R-aware continuous-stroke motion approach. |

This is a likely *functional development sequence*, based on source contents and filenames rather than proven per-file creation timestamps.

## Drawing data and file dependencies

- All six main scripts are standalone Python command-line programs. There is **no Tkinter drawing GUI** in this project.
- `mg400_writer.py` is an unchanged local copy of the text-writing core that the drawing scripts import for Ethernet socket commands and robot setup.
- The first five scripts contain **hand-coded point lists** (a simplified building and, later, Narva College). Despite the filenames, they do **not** import PNG/JPG or automatically trace image edges.
- The SVG script reads a user-specified `.svg` from `SVG_FILE`. The checked-in main file refers to `C:\\Users\\user.NK-009\\Desktop\\drawing.svg`, a historical Windows path that is **not included in this project**; it must be updated to an existing file on the machine running the script.
- The SVG parser handles paths, lines, polylines, polygons, rectangles, circles and ellipses; nested groups, `translate(...)` / `matrix(...)` transforms; curve and arc flattening. It is **not a full SVG rendering engine**: test unsupported SVG constructs such as text, `<use>`, clipping and inherited style features before robot motion.
- There are **no project-specific JSON settings files** for these Python drawing scripts. Constants at the top of each file store the measured setup and chosen input SVG.

## Original drawings vs alternate-upload copies

The earlier loose `Even more robot apps` folder included corresponding versions, now preserved under `alternate-upload-copies/`. **They are not all identical**, and their control flags explain why both copies existed:

| Script | Main file | Alternate-upload copy |
| --- | --- | --- |
| `mg400_image_drawer.py` | Exactly identical | Exactly identical |
| `mg400_image_drawer_safe_test.py` | `LIVE_ROBOT=True`, `PREFLIGHT_ONLY=False`; explicit IP assignment | `LIVE_ROBOT=False`, `PREFLIGHT_ONLY=True`; no explicit IP assignment |
| `mg400_image_drawer_ik_safe.py` | Live drawing enabled | `LIVE_ROBOT=False`, preflight flag enabled |
| `mg400_image_drawer_continuous.py` | Live drawing enabled | `LIVE_ROBOT=False`, preflight flag enabled |
| `mg400_image_drawer_narva.py` | Live drawing enabled | `LIVE_ROBOT=False`, preflight flag enabled |
| `mg400_svg_drawer.py` | Live drawing enabled; radius 56 mm; Windows SVG path | `LIVE_ROBOT=False`, `PREFLIGHT_ONLY=True`; radius 55.5 mm; historical uploaded `/mnt/data/...` SVG path |

For the IK, continuous and Narva pairs, the **only line changes** between their main and alternate versions are the two live/preflight flags. For SVG, there are four line changes: those flags, radius, and SVG input path. The simplified original `mg400_image_drawer.py` itself sets live mode **False** in the main block even though the shared writer core defaults to True.

**Historical usage interpretation:** the author says that versions configured with `LIVE_ROBOT = True` were the ones actually used with the robot. The archive copies with False are best labeled **non-live / preflight configurations**, not deleted as meaningless duplicates. `PREFLIGHT_ONLY=True` alone does not imply an actual pen-up robot test when live mode is False, because the IK-based programs skip live planning/movement in that case.

## Mechanical model and safe workspace

The IK building versions use an initial effective model `PEN_RADIUS_MM = 55.5` mm and `PEN_ANGLE_OFFSET_DEG = 26.0`. The current SVG script uses radius **56 mm** and angle offset **26.0°**. These constants approximate the unloaded / effective tool geometry, but the author observed the actual radius **increase under paper pressure** due to flex in the printed pen mount.

The measured main paper rectangle in the scripts is approximately **260 mm horizontally (robot Y) × 123 mm vertically (robot X)**, plus a noted narrower bottom extension. The first bounded drawing experiment uses a **220 × 100 mm** inset. These are historical drawing/robot coordinates, not full physical A4 dimensions or general-purpose bounds.

Early fixed R zones used measured values at four paper corners; the IK versions then evaluate multiple candidate R values dynamically for each short segment. The IK safety margin checks use J2 and J4, and planned lines are divided into pieces around **10 mm** long for checks. Later execution merges consecutive pieces when they have the same R.

In this project, pen reach depends jointly on **flange reach**, R position, actual robot/holder clearance, and the pen-tip offset. A passing inverse-kinematics/joint-limit check **cannot prove that the off-axis pen holder will not contact the robot body** or that the flexible pen tip remains at the modeled XY.

## Code-review limitations / things to remember

1. **Unintended pen contact / clearance:** R rotations and lateral moves can bring the off-axis pen or holder into the robot's occupied space on either side. No complete 3D tool/robot collision model is present.
2. **Mechanical accuracy:** the user observed small stepped line offsets after R changes, plus some curved-looking sections during directional changes. These were accepted for drawing; they **did not impair the text writer**.
3. **Live code can start drawing:** the main later scripts set `LIVE_ROBOT=True`, `PREFLIGHT_ONLY=False`. They connect and begin planning/execution when run; the flags and current fixture must be checked before use.
4. **Partial trajectory checking:** the IK planner samples short-segment endpoints at writing and lifted Z; it does not continuously collision-check every robot link, the pen holder, transitions, or all intermediate joint configurations.
5. **SVG input assumptions:** the main SVG path is a historical absolute Windows path. Incompatible SVG syntax, unconverted text or unexpected geometry may fail parsing or produce unexpected strokes. There is no bundled input `drawing.svg` in this folder.
6. **Manual drawing extent:** a few Narva drawing points extend beyond normalized 0..1 (for example `x=1.05`), so the true target XY envelope can exceed the nominal configured width.
7. **Robot-specific settings:** the test uses historical IP `192.168.1.6` and contact Z `-197.30` for the later files. The IP reflects Ethernet port/network setup; writing Z, pen flex and reach must be rechecked for any new fixture.
8. **Motion failure handling:** the underlying MG400 writer logs controller responses; these prototypes are not a production-grade safety controller or GUI with cancellation.

The observations above are from source inspection and author recollection; no new physical robot tests were performed here. Do not turn tentative history into verified individual test outcomes.

## Catalog recommendation

**Project classification:** **MG400 Drawing — Manual Paths, R-Reach/IK Experiments and SVG Import**.

Keep the main scripts in apparent development order, and retain archived copies as historical dry-run/physical-test configurations. The **SVG drawer** is the most broadly reusable **code candidate**, while the **Narva drawer** remains a worthwhile named drawing/demo. This does **not** mean either is physically verified as the final working deployment.

**Reported outcome:** drawing was usable / reasonable, with slight geometric imperfections from the flexible off-axis pen and the MG400's constrained A4 reach; **text writing remained successful**. The calibration and radius tricks belong to drawing rather than to the text writer.

The next related area to review is [MG400 controller applications](../controller/), since the shared drawing geometry has already been examined in the [calibration project](../pen-calibration/).
