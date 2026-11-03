# MG400 pen calibration — project review

**Robot:** Dobot MG400  \
**Purpose:** Determine how pen-holder offset, R-axis rotation, and fixture flex affect line placement  \
**Status:** Calibration scripts used as live-robot experiments according to the project author's convention (`LIVE_ROBOT = True` in all four). Specific measured outcomes and whether each run completed successfully are not independently documented.  \
**Reviewed:** 2026-11-03

## Relationship to the pen-writing project

The [MG400 pen writer](../pen-writing/) draws letters from a 3×3 grid. Later drawing work needed to account for a pen whose tip was **not at the flange rotation axis**. Rotating the robot's R axis therefore moves the pen tip unless the program compensates for the tool offset.

These tests investigate the pen's effective horizontal offset and whether a flexible/spring-like holder changes the result as motion direction and R angle change. They import `MG400Writer` from a same-folder copy of the writer core, used for Ethernet commands rather than for lettering.

## File guide and intended experiments

| File | Test and interpretation |
| --- | --- |
| `mg400_radius_calibration_arc.py` | Keep the flange at fixed XY/Z while sweeping R to draw an arc. Measure the approximate endpoint-to-endpoint diameter to estimate effective pen offset radius. Includes an optional model-based diameter line (disabled by default). |
| `mg400_r_angle_calibration.py` | Draw two parallel segmented lines with successive segments at different R angles; one sweeps R forward, the other in reverse. Compare segment alignment and directional differences to diagnose offset-model errors versus holder flex/backlash. |
| `mg400_vertical_r_overlap_calibration.py` | Redraw the **same** vertical line seven times at different R angles, then repeat in the opposite travel direction in a second column. Middle-of-line overlap tests whether the model holds after spring settling. |
| `mg400_vertical_r_overlap_calibration_v2.py` | The same vertical-overlap experiment moved into a more reachable region after a recorded `InverseSolution` failure in the original. Only the test geometry and explanation changed. |
| `mg400_writer.py` | Verbatim local copy of the pen-writer core, required by `from mg400_writer import MG400Writer`. |
| `alternate-upload-copies/` | Identical-SHA copies of the four scripts from the earlier loose `Even more robot apps` upload. These are **not four additional versions**. |

No separate JSON calibration state is present in this folder: parameters are hard-coded near the top of each test script.

## Calibration model

The scripts use:

- `PEN_RADIUS_MM = 55.5` and `PEN_ANGLE_OFFSET_DEG = 26.0` as the effective horizontal pen model.
- `WRITING_Z = -197.30` mm with `TRAVEL_LIFT_MM = 10.0` mm.
- Robot IP `192.168.1.6` and `LIVE_ROBOT = True`; this IP reflects the selected robot Ethernet connection/network arrangement rather than a new protocol.
- Different test speed factors: radius arc **20**, R-angle segmented lines **35**, vertical overlap **30**.

The modeled offset is:

```python
angle = radians(R + PEN_ANGLE_OFFSET_DEG)
offset_x = PEN_RADIUS_MM * cos(angle)
offset_y = PEN_RADIUS_MM * sin(angle)
flange_x = requested_pen_tip_x - offset_x
flange_y = requested_pen_tip_y - offset_y
```

This converts a desired pen-tip location into the corresponding flange XY for a chosen R orientation. The values are physical setup measurements/assumptions, **not guaranteed valid for another pen holder or work surface**.

The arc script sweeps R from **−115° to +62° in 3° steps** (about a half-turn). Its diameter/2 measurement is an approximation of radius because the angular sweep is **177°**, not exactly 180°. The model radius/angle are not used to generate the primary arc, only for the optional comparison diameter line.

## Vertical-overlap v1 → v2: exactly what changed

The v2 code records a concrete issue: at **R = −49.74°**, the original test required flange X of about **234.2 mm**, and `InverseSolution` returned **−1**. The test line was relocated to give the flange a more reachable position.

| Parameter | Original | v2 |
| --- | ---: | ---: |
| Line top, robot X | 285 mm | 305 mm |
| Line bottom, robot X | 350 mm | 355 mm |
| Test line length | 65 mm | 50 mm |
| Downward-test Y | −35 mm | −35 mm |
| Upward-test Y | +35 mm | +35 mm |
| R angles | −72.24° through −27.24° | Unchanged |
| Pen radius and angle offset | 55.5 mm / 26° | Unchanged |

The rest of the actual test implementation remains unchanged. The v2 comment saying “middle of the 65 mm line” is **stale documentation**; v2's line is 50 mm. The code itself uses the correct revised coordinates.

**Interpretation:** v2 was intended to solve *reachability* of the existing calibration experiment, not to change its geometry model. A passing v2 robot run has not been independently verified in this review.

## R-angle and vertical tests

Both tests use seven R orientations:
`[-72.24, -64.74, -57.24, -49.74, -42.24, -34.74, -27.24]` degrees.

The segmented R-angle test uses consecutive **18 mm** segments in each of two parallel rows, with the R sequence reversed for the second row. It checks whether the nominal straight line stays aligned when the wrist angle changes.

The vertical-overlap test draws **two columns** and repeats the entire line for each angle in each column. One column draws top-to-bottom (+X), the other bottom-to-top (−X). Its comments instruct checking the **middle** of the line because the flexible holder can curve the beginning of a stroke while settling.

Both check endpoint inverse-kinematics solutions at the writing height and apply project-specific limits for **J2 (−23° to +83°)** and **J4 (−172° to +115°)**. They then issue motion commands with `Sync()` after key steps.

## Source-review warnings (not test results)

1. **These are live motion scripts**, not passive diagnostic tools. Executing them can connect, clear errors, enable the robot, and start drawing automatically. Confirm work area, tools, limits, emergency stop, and pen contact height first.
2. The segmented R-angle and vertical-overlap scripts check the IK solution and J2/J4 margins at **segment endpoints**, not every intermediate point of the physical robot trajectory; the checks do not prove collision-free travel.
3. The **arc script has no equivalent planned IK/J2/J4 preflight over its R sweep**. Its intended fixed-flange rotation can still encounter robot limits. Review its path independently before use.
4. All calibration scripts assume a fixed **writing Z of −197.30 mm**. With a different fixture, tool or paper, that may press the pen too hard or be unreachable.
5. They depend on the writer core's socket command routine, which logs responses but does not robustly handle all controller error codes or motion timeouts. `Sync()` barriers help with ordering but do not replace safety validation.
6. Values such as pen radius, angle offset, safe joint margins and Z are experiment-specific assumptions, not universal MG400 settings.

These are code-inspection observations, except the original vertical-test `InverseSolution` failure explicitly recorded in the v2 source. Actual drawing quality and whether the calibration converged need user recollection or physical test records.

## Link to later drawing code

The [MG400 image and SVG drawing project](../image-and-svg-drawing/) incorporates the same pen-offset compensation, inverse-kinematics checks and repeated-stroke considerations. Its Narva/continuous drawing iterations retain **55.5 mm / 26°** as initial parameters. A later SVG drawer has **56 mm / 26°** (with a note about a not-yet-applied R-transition correction). Those values are clues about the development sequence, not proof that any one calibration run established the final correct radius.

**Catalog recommendation:** Keep all four scripts under one **Pen Calibration** project, with v2 as the later *vertical overlap* candidate and the other two as separate diagnostics—not superseded copies. Keep usage status as **used for live experimentation**; outcome as **not yet confirmed**. Do not modify original scripts or measured values just to make the historical versions agree.
