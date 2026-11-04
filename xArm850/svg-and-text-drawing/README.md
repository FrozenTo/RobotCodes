# xArm 850 / UF850 — Wall SVG and Text Drawing

**Robot:** UFACTORY xArm 850 / UF850, writing/drawing on **A3 paper mounted vertically on a wall**  
**Project:** Reuse the successful Inkscape SVG artwork from the [MG400 Image/SVG project](../../MG400/image-and-svg-drawing/), with paper-surface calibration, wall contact and optional text heading  
**Author-confirmed outcome:** The SVG drawing approach was successfully used on the xArm. Marker contact and calibration were sensitive, however, and the most recent five-point/rack-based configuration is **not included in this archived folder**. The precise tested state of each earlier file remains unverified.  
**Reviewed:** 2026-11-04

## The actual problem: drawing on vertical paper

The MG400's successful **`drawing.svg`** came from manually tracing the Narva College building in **Inkscape** after attempts to generate detailed building vectors from PNG proved unusable. The file stored here is **identical** to [MG400's original `drawing.svg`](../../MG400/image-and-svg-drawing/drawing.svg).

The xArm drawing code adapts SVG paths to the vertical wall's **Y (horizontal) and Z (vertical)** axes. The X axis moves the marker **into or away from the paper**: for this installation **negative X is toward the wall** and **positive X is away**. Lettering, SVG, and later freehand drawing therefore shared a difficult real-world task: matching the marker tip to the precise wall/paper X depth.

The author emphasized that **changes of about 0.1 mm mattered**. A wrongly chosen contact X could (1) leave the marker tip too far from the paper to draw or (2) drive the pen/marker hard into the wall, potentially **crushing the marker between robot and wall**. The code does not use contact-force feedback to automatically discover a safe writing depth. This **remains an unresolved manual-calibration hazard**, even though the later 3D-printed marker rack made the grip position reproducible.

The physical sheet was **A3**; the earlier code's `PAPER_WIDTH_MM`/`PAPER_HEIGHT_MM` values describe a **measured usable / reachable drawing region**, not a claim that the robot could reach every edge of the full A3 sheet.

## Development sequence — the five principal scripts

| File | Main change | Paper calibration |
| --- | --- | --- |
| [`xarm_svg_drawer.py`](xarm_svg_drawer.py) | Initial standalone SVG importer: adapts SVG geometry and a joint-space READY approach to the wall; safe X for travel, marker contact for drawing | **4 corner positions**; bilinear mapping; `CONTACT_X_OFFSET_MM=0.0` |
| [`xarm_svg_drawer_8point.py`](xarm_svg_drawer_8point.py) | More carefully measured contact surface, including intermediate edge samples and smoother interpolation; drawing-point execution improvements | **8 measured edge positions**, top/middle/bottom and left/right; `CONTACT_X_OFFSET_MM=-7.0` in saved source |
| [`xarm_hello_narva_then_svg.py`](xarm_hello_narva_then_svg.py) | Adds a **“HELLO NARVA!”-style heading** before drawing the SVG; separate margin, speed and heading-geometry controls | **8 measured points**, with some subsequently adjusted X coordinates |
| [`xarm_wall_drawer_app.py`](xarm_wall_drawer_app.py) | First desktop **Tkinter GUI**: choose SVG, enable optional heading text, change draw/text speeds, scale and contact X offset, run ready/preflight/draw operations | Same historical **8-point** family |
| [`xarm_wall_drawer_app_v2.py`](xarm_wall_drawer_app_v2.py) | GUI revision that adds **read current joint angles / editable READY joint posture** among its refinements; retains SVG and text workflow | Same historical **8-point** family |

This sequence reflects code features and filenames, not a proven physical-test timestamp for each script. The heading program and GUI both contain working code for the optional text-before-SVG behavior, but the specific results of every revision were not independently tested during this GitHub review.

The GUI's adjustable **X contact offset** was requested specifically because different marker lengths and re-gripping caused small contact changes. It is **not** a general robot-base or paper-size calibration control.

## Four-point and eight-point paper models

The original standalone SVG drawer stored measured X/Y/Z values for the **four corners** and interpolated between them. Later code expanded to **eight measured paper-contact positions**:

- top-left, top-middle and top-right;
- middle-left and middle-right;
- bottom-left, bottom-middle and bottom-right.

The eight-point implementation builds a curved/interpolated surface from these edge measurements. Its source notes that the **top-right physical region was hard to reach**, so its working height was reduced relative to the full paper edge.

For example, `xarm_svg_drawer_8point.py` has `PAPER_WIDTH_MM=359.6` and `PAPER_HEIGHT_MM=235.0` for the intended usable region, and **`SAFE_X=-480.0`** for marker-up travel. These are **historical setup-specific values**; an A3 sheet itself is larger.

### Contact X offset — marker length is not paper geometry

The archived eight-point programs use an additional `CONTACT_X_OFFSET_MM` in the mapping from paper contact surface to robot target X. One source comment records:

```python
CONTACT_X_OFFSET_MM = -7.0  # for brand new marker -6.0, slightly used -7.5
```

Those are **examples from actual historical calibration**, not universal safe settings. The author repeatedly had to **manually adjust X after taking the marker out and putting it back into the gripper**. A different grip depth, tip wear or marker length could move the contact point even when the sheet itself was unchanged. This is why the software exposed an editable offset and small adjustment controls.

**Do not blindly copy `-7.0` or another historical X offset to a new marker.** More negative X means moving farther **toward** the wall in this installation; an overlarge adjustment can damage the tip or cause a hazardous collision. The source has no sensor-based contact-pressure regulation.

## Important later development — five-point calibration and marker rack

The author subsequently created a **five-point paper calibration for the latest combined xArm project**, using reachable points around a **clipped / unreachable upper-right region of the A3 sheet** rather than pretending all four paper corners were attainable. Earlier project discussions describe the five points as **top-left, bottom-left, bottom-right and two reachable points bordering the upper-right exclusion**. This latest model is **not** the same algorithm as the eight-point interpolation in the archived SVG scripts.

A **3D-printed marker rack / pickup station with a physical positioning wall/stop** was later used to insert the marker in a more repeatable position. That reduced changes in tip projection when picking up or returning the marker. The author reports that the rack-based setup became consistent enough that **no more X-offset recalibration was needed after the latest updates**. Earlier pickup and return sequences were individually tested successfully; this is **not** an assertion that every automated marker operation in the newest integrated application has been verified.

**Repository distinction:** at the time of this review, `RobotCodes/main` contains **four-point and eight-point** SVG/wall drawing implementations, plus the combined **v3** package, but it **does not contain** the later `xarm_850_combined_controller_drawer_v4_5point_calibration.py` implementation or its complete marker-rack automation. Do **not** relabel existing archived scripts “five-point” or overwrite their calibration points. The later successful setup should be archived **separately** once its actual files are available.

## SVG parsing and motion behavior

The standalone source parses SVG paths/shapes and supported transforms, flattens curves and scales the path into the configured drawing envelope. It lifts the marker to **SAFE_X** before traveling to another stroke, approaches contact X at a lower approach speed, then draws at the selected draw speed. A joint-space READY move helps the robot establish the correct approach posture.

The newer programs can queue short intermediate drawing moves and wait for the final point before moving to the next stroke. Their preflight options can move along paths with the marker **lifted off the paper**; these are **not proof that contacting paths will be safe or correctly pressured**. They do not implement a full 3D collision or wall-contact-force planner.

The Tkinter SVG GUI includes editable contact X offset, text-heading enablement, input file selection, geometric sizing and draw speeds. The **v2 GUI** includes a control to read the current joint angles for setting the READY posture. The archive does **not** include a separate calibration JSON for this SVG app; settings are held in code and GUI values in the saved versions.

## Source inspection cautions

1. **X contact is the dominant physical hazard.** Either missing contact or excessive pressure can result from a small offset error. A rack improves repeatability but does **not** introduce automatic force sensing.
2. **Top-right reach limits:** source bounds reflect a usable region inside the physical A3 page. An unreachable top-right corner should not be crossed merely because the SVG has been scaled to rectangular bounds.
3. **A passing motion preflight is not a force test.** Air/dry-run moves do not confirm paper contact.
4. **Historical constants are fixture-specific:** `READY_JOINTS`, `SAFE_X`, marker orientation, paper points, marker offset, speeds and SVG path all need review after robot, wall or tool changes.
5. **Source vs later history:** current archived files still use eight-point geometry; the five-point/rack approach belongs to later work and must be verified from its own source when archived.
6. **Software STOP and GUI are not a substitute for the physical emergency-stop mechanism.**

## Archive summary

**Confirmed project direction:** successful migration of the Inkscape **Narva College SVG** from MG400 to xArm wall drawing, with optional heading text and a Tkinter GUI. The major challenge was **precise A3 wall contact and marker length**, not simply parsing SVG paths.

**Later improvements:** five-point clipped reach calibration and a repeatable 3D-printed marker rack; these are **not present in the older saved SVG scripts**.

See the [xArm 850 parent README](../README.md) and the [combined controller / drawing README](../combined-controller-and-drawer/) for the subsequent integrated application. The [text-writing README](../text-writing/) documents the earlier four-point wall writer.

**No Python source, paper-contact coordinates, marker offsets or motion parameters were modified during this documentation review.**
