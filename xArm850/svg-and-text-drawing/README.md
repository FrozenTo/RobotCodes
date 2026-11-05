# xArm 850 / UF850 — SVG and Wall Text Drawing

**Robot:** UFACTORY xArm 850, drawing on an **A3 sheet mounted vertically on a wall**  
**Purpose:** Reuse the successful manually traced Narva College SVG from the [MG400 drawing project](../../MG400/image-and-svg-drawing/) and optionally write text before the SVG, with control of the marker contact depth.  
**Author-reported result:** SVG wall drawing worked very well after calibrating the marker and paper. The exact last-tested archived script is **not confirmed**.  
**Review:** Source and original/recovered upload variants compared 2026-11-05. This is a documentation-only review, not a new live-robot test.

## How the SVG project began

The MG400 drawing experiments originally tried to reconstruct the detailed Narva College building from an image using hard-coded stroke paths; those attempts were not usable. The author **manually traced the lines in Inkscape** and successfully drew the resulting `drawing.svg` with MG400. The same byte-identical artwork is kept in this xArm folder.

The xArm programs reuse the **SVG parsing concept and artwork**, not MG400 movement coordinates. They convert an SVG into flattened lines and curves, then place the paths on a vertical wall:

- **SVG horizontal → robot Y** across the paper.
- **SVG vertical → robot Z**, with positive Z upward.
- **Robot X → marker distance from the wall**, negative X toward the paper and positive X away.
- A **joint-space READY posture**, followed by Cartesian movements, is used to approach the writing region. Pen-up travel occurs on a separate **SAFE_X** plane.

The sheet itself was **A3**. Constants such as `PAPER_WIDTH_MM` and `PAPER_HEIGHT_MM` express the **calibrated reachable drawing region**, not necessarily the full A3 edges.

## Five main script versions

| File | What was added / how it works | Calibration |
| --- | --- | --- |
| [`xarm_svg_drawer.py`](xarm_svg_drawer.py) | Original standalone SVG import, flatten/scale paths, joint READY motion, optional dry-run preflight, lift between strokes and contact drawing | **4 corners**; `SAFE_X=-480` mm |
| [`xarm_svg_drawer_8point.py`](xarm_svg_drawer_8point.py) | Uses additional upper, middle and lower edge samples to model nonuniform wall depth rather than relying on four corners alone | **8 measured points** |
| [`xarm_hello_narva_then_svg.py`](xarm_hello_narva_then_svg.py) | Adds a pen-written heading before drawing the SVG, with heading size, margin, speed and placement controls | **8 measured points** |
| [`xarm_wall_drawer_app.py`](xarm_wall_drawer_app.py) | Creates a **Tkinter GUI** for browsing SVGs, entering optional heading text, changing drawing/text speeds, scaling and **contact X offset**, and running READY/preflight/draw sequences | **8 measured points** |
| [`xarm_wall_drawer_app_v2.py`](xarm_wall_drawer_app_v2.py) | Extends the GUI with editable **READY joint angles** and **Read current joints**, retaining the earlier drawing and heading options | **8 measured points** |

The main SVG importer handles paths and other line/shape elements, transforms, curves/arcs and geometry simplification; it is not an image-to-vector AI converter. The successful College building SVG was already manually traced before importing.

### Paper calibration and why X offset mattered

The **4-point** version stores `PAPER_TL`, `PAPER_TR`, `PAPER_BR`, `PAPER_BL` and interpolates between measured corner poses. The **8-point** version stores `TL`, `TM`, `TR`, `ML`, `MR`, `BL`, `BM`, `BR` and uses quadratic-through-middle interpolation along the edges.

The author reports that **changes as small as about 0.1 mm in the X contact depth were significant**. When the marker was removed or reinserted, its tip extended a slightly different distance from the gripper. The paper-surface points and the marker-contact offset are therefore **different calibration concerns**.

For the eight-point standalone code, `CONTACT_X_OFFSET_MM` is applied to the interpolated contact X; in the main `xarm_svg_drawer_8point.py` the saved value is **−7.0 mm**, with a comment referring to example new/used marker adjustments. These numbers are **historical examples, not generally safe defaults**. In this physical installation, a more-negative X drives the marker farther toward the wall. Too little depth means no mark; too much can press or **crush the marker against the wall**. These scripts **do not measure or regulate marker contact force**.

A pen-up preflight checks geometry and reach along a retracted path, **not the pressure of the marker against paper**. A successful preflight cannot validate the contact X or guarantee wall and robot-link clearance.

## Recovered copies — line-by-line comparison

On 2026-11-04, the original complete **74-file `Even more robot apps` folder** was re-uploaded after an earlier GitHub upload had silently omitted its final 33 files. Copies of these three SVG scripts were among the recovered material, and they were preserved **unchanged** at [`alternate-upload-copies/recovered-2026-11-04/`](alternate-upload-copies/recovered-2026-11-04/) because **their contents are different** from the already-organized main files.

The comparison below is between the exact preserved sources. It does not prove the date of every physical run.

| Main file vs re-uploaded alternate | Exact important differences | What that means |
| --- | --- | --- |
| `xarm_svg_drawer.py` — **5 changed lines** | Main: `drawing.svg`, `LIVE_ROBOT=True`, `PREFLIGHT_ONLY=False`, travel/draw speeds **120/120 mm/s**. Alternate: `drawing(1).svg`, `LIVE_ROBOT=False`, `PREFLIGHT_ONLY=True`, speeds **80/40 mm/s** | Alternate is configured as a non-live/preflight trial; **main is configured for live drawing** |
| `xarm_svg_drawer_8point.py` — **9 changed lines** | Main: `CONTACT_X_OFFSET_MM=-7.0` with a particular set of eight X coordinates; alternate: `CONTACT_X_OFFSET_MM=0.0` with **all eight paper X coordinates different and approximately 10–13 mm more negative**. Y/Z coordinates and movement logic are unchanged | **Two distinct marker/paper-contact calibrations.** Do not merge the alternate X coordinates with the main offset |
| `xarm_hello_narva_then_svg.py` — **6 changed lines** | Four paper X coordinates differ slightly. Main heading `"Privet zanna!"`, heading speed **120 mm/s**; alternate `"HELLO NARVA!"`, heading speed **70 mm/s** | Heading content, contact and heading speed reflect different historical settings; code remains otherwise the same |

The `xarm_svg_drawer_8point.py` source comment about its measured X coordinates and additional X offset should not be treated as proof that either set was universally correct: the physical marker, depth and rack setup changed during development. **Preserve both complete sets**.

Other relevant files:

- [`drawing.svg`](drawing.svg) — the original manually traced Narva College artwork, byte-identical to the MG400 drawing folder copy.
- [`reference-images/`](reference-images/) — historical screenshots of the drawing setup.
- The GUI scripts contain their own SVG parsing, calibration and drawing functions; they **do not import** the standalone `xarm_svg_drawer_8point.py` as a required separate module. Each is a historical standalone application.

## Graphical application behavior

The Tkinter drawing apps provide a way to choose a different `.svg`, enter or disable a text heading, adjust its placement/size/speed, set the SVG output size/margins, change travel/approach/draw speeds, and fine-tune the marker **X offset**. The GUI includes buttons to move to READY, perform a **pen-up preflight**, and start the actual drawing.

Version 2 adds a **Read current joints** action to capture/update the six-joint READY pose, so users can adjust the approach posture without editing the top-of-file `READY_JOINTS` list. Both apps use worker threads for long robot operations and gate ordinary competing actions while busy. They do not persist calibration/settings to a separate local JSON by default in this folder.

The main code is configured for a physical xArm at `192.168.1.208`. UI controls, SAFE_X, paper corners, READY joints and tool orientation are **setup-specific**. There is no automated touch sensing and no collision-free guarantee in this implementation.

## Relationship to later five-point and marker-rack work

The eight-point source files are **not** the five-point code. The later [five-point development](../combined-controller-and-drawer/five-point-development/) introduced a **clipped upper-right reachable region** because the xArm could not safely reach the full physical A3 upper-right area. Intermediate versions `v4`, `v6` and `v7` are now archived, including calibration-offset corrections and upper-right safety tests.

The [full marker-handling application](../combined-controller-and-drawer/full-marker-app/) now includes `xarm_850_full_app_normal_marker_speed.py`, which uses the **five-point** calibrated surface and a 3D-printed rack/pickup location. The rack has a physical locating wall/stop, making insertion depth more repeatable; the author reports that after this setup became consistent, further manual X-offset readjustment was no longer needed. However, **a wrongly entered X offset can still cause a missing mark or crushed marker**. The full app has its own version review; these older SVG scripts should not be relabeled as five-point.

See also [standalone wall text writing](../text-writing/), [freehand drawing](../freehand-drawing/), and [marker handling experiments](../marker-handling-tests/).

## Review conclusion

**Confirmed:** successfully transferred a manually traced Inkscape SVG from MG400 to xArm wall drawing, with a usable GUI and optional heading. **Main technical difficulty:** accurate paper surface depth and repeatable marker tip position, not SVG parsing itself.

**Not confirmed:** which exact archived SVG/GUI file was the final physically run revision, and whether every stored coordinate remains appropriate after the later marker rack or five-point calibration updates.

**This review modifies only this README.** Original Python, SVG and calibration constants remain byte-for-byte unchanged.
