# MG400 Image and SVG Drawing — project review

**Robot:** Dobot MG400  
**Project:** Off-axis pen drawing across the largest practical paper area  
**Status:** **SVG workflow confirmed working very well on the physical MG400 by the author.** Early attempts to hand-code a complex image from PNG reference were inaccurate and unusable; small mechanical drawing offsets were tolerated. The outcome of each intermediate safety/IK script remains unverified individually.  
**Reviewed:** 2026-11-03

## Why this project exists

This project followed the [MG400 text writer](../pen-writing/) and a series of [pen calibration experiments](../pen-calibration/), but the **R-axis radius manipulation was exclusively for drawing**, not for improving the already successful lettering app.

A lesson project introduced a 3D-printed pen holder consisting of a connection to the MG400 flange, a thin **flexible arm/board**, and a circular grip that holds the pen **off the flange axis**. When the flange rotates in R, the pen tip travels along an arc. This was interesting to explore for its own sake, and it also offered a way to reach otherwise inaccessible parts of an A4 sheet.

The practical R range varied across the workspace. When the robot head shifted left or right, the body/head linkage and pen-holder clearance changed, so an angle that worked in one region might be blocked in another. Interference was a concern **on both sides**, not just the left. The software therefore attempted to select a feasible R orientation for the *pen tip's requested position*, rather than expecting one R to work across the entire sheet.

**Why the drawing could never be perfectly straight:** Under paper contact, the flexible holder bent upwards, pushing the pen tip **slightly farther outward** than the fixed-radius model predicted. That produced a small lateral shift when R changed, and occasionally a slightly curved line through certain multi-direction/zigzag patterns. The author chose to accept these small **drawing-only** imperfections. The earlier **text-writing application worked well** and was not affected in the same way.

## Critical turning point: from PNG approximation to manual SVG

The first attempts at recreating the **Narva College building** were based on a supplied PNG reference. GPT tried to work out the many individual vector coordinates directly from that image. The author reports that **the manually coded approximations (described as versions 1 and 2) were terrible and unusable**: there were simply too many lines and architectural details to reconstruct accurately that way. This is important historical context; do **not** label the earlier coded-building files successful demos based on their source alone.

The author instead opened **Inkscape**, traced/redrew the architectural linework themselves, and saved a proper **`drawing.svg`**. The MG400 SVG drawer then **worked very well on the real robot**. This is the confirmed successful drawing approach, as opposed to generated coordinate approximations. It still had the small flex-induced geometric imperfections documented below, but those were acceptable.

**Recovered input file:** [`drawing.svg`](drawing.svg) (50,781 bytes; 215 SVG `<path>` elements and one `<ellipse>`, with grouped paths). The SVG was supplied again by the author and is **byte-for-byte identical** to [`xArm850/svg-and-text-drawing/drawing.svg`](../../xArm850/svg-and-text-drawing/drawing.svg) already in this repository. The xArm code also explicitly documents using the SVG parsing approach that worked on MG400. This provides a direct, verified link between the MG400 and UF850/xArm 850 drawing projects.

The SVG files are stored in both project folders for convenience but **share the exact same Git blob content**. They are not different redraws.

## Development progression

| Main script | Purpose and main difference |
| --- | --- |
| `mg400_image_drawer.py` | Early hard-coded, normalized architectural/building path experiment from the pre-SVG approach. Anchors to the writer's WritingStart, uses fixed R, and does **not** import raster images. Its `__main__` sets `writer.settings.live_robot = False`; not a confirmed usable drawing. |
| `mg400_image_drawer_safe_test.py` | First measured-paper / off-axis pen compensation test: ~260 × 123 mm main rectangle, 220 × 100 mm drawing inset, five measured R orientations, four broad R zones, J4 monitoring and pen-up preflight option. |
| `mg400_image_drawer_ik_safe.py` | Replaces fixed-quadrant R selection with **controller inverse-kinematics preplanning**. Checks each short segment at contact and lifted Z; chooses from measured R candidates subject to J2/J4 margins. Adds `Sync()` barriers and an optional raised-pen preflight. |
| `mg400_image_drawer_continuous.py` | Keeps the short-segment IK checks but **merges adjacent same-R sections of the same path into continuous pen-down strokes**, avoiding unnecessary lift/drop cycles roughly every 10 mm. |
| `mg400_image_drawer_narva.py` | Builds on the continuous planner with a much more detailed **hard-coded Narva College sketch** (roof, facade, windows, arches and foreground). The author's attempts to approximate the intricate reference image by GPT-generated vector coordinates were **not usable**; don't confuse coded detail with successful output. |
| `mg400_svg_drawer.py` | **Confirmed successful drawing workflow:** imports the manually traced Inkscape SVG, parses shapes/transforms, flattens curves/arcs, scales/centers paths, simplifies geometry and uses IK/R-aware continuous strokes. |

This is a likely *functional development sequence*, based on source contents and filenames rather than proven per-file creation timestamps.

## Drawing data and file dependencies

- All six main scripts are standalone Python command-line programs. There is **no Tkinter drawing GUI** in this project.
- `mg400_writer.py` is an unchanged local copy of the text-writing core that the drawing scripts import for Ethernet socket commands and robot setup.
- The first five scripts contain **hand-coded point lists** (a simplified building and, later, Narva College). Despite the filenames, they do **not** import PNG/JPG or automatically trace image edges.
- The SVG script reads a user-specified `.svg` from `SVG_FILE`. The original manually traced **[`drawing.svg`](drawing.svg) is now included** beside the MG400 code. The checked-in Python script **still references the historical Windows absolute path** `C:\\Users\\user.NK-009\\Desktop\\drawing.svg`; it must be changed to an accessible input path (for example `drawing.svg` when launching from this directory) before reuse. The original Python source has not been modified.
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
5. **SVG input assumptions:** `drawing.svg` is now bundled, but the main Python script still points to a historical absolute Windows path. Set `SVG_FILE` appropriately before reuse. Incompatible SVG syntax, unconverted text or unexpected geometry may fail parsing or produce unexpected strokes.
6. **Manual drawing extent:** a few Narva drawing points extend beyond normalized 0..1 (for example `x=1.05`), so the true target XY envelope can exceed the nominal configured width.
7. **Robot-specific settings:** the test uses historical IP `192.168.1.6` and contact Z `-197.30` for the later files. The IP reflects Ethernet port/network setup; writing Z, pen flex and reach must be rechecked for any new fixture.
8. **Motion failure handling:** the underlying MG400 writer logs controller responses; these prototypes are not a production-grade safety controller or GUI with cancellation.

The observations above are from source inspection and author recollection; no new physical robot tests were performed here. Do not turn tentative history into verified individual test outcomes.

## Catalog recommendation

**Project classification:** **MG400 Drawing — Manual Paths, R-Reach/IK Experiments and SVG Import**.

Keep the main scripts in apparent development order and retain archived copies as historical dry-run/physical-test configurations. The **SVG drawer using the manually traced Narva College `drawing.svg` is the author-confirmed working result**. The hard-coded Narva and earlier coordinate-approximation variants are valuable development history, **not successful final drawings**. Intermediate IK/control iterations should not be individually labeled tested solely from `LIVE_ROBOT=True`.

**Reported outcome:** the hand-coded PNG-to-vector approximations failed to produce an acceptable picture. The manually traced Inkscape SVG **drew very well with MG400** and the *same exact artwork* was subsequently reused with UF850/xArm 850. Minor flex-related geometric imperfections were accepted; **text writing remained successful**. The calibration and radius tricks belong to drawing rather than to the text writer.

The next related area to review is [MG400 controller applications](../controller/), since the shared drawing geometry has already been examined in the [calibration project](../pen-calibration/).
