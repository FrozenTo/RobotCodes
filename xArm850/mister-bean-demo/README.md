# xArm 850 — Standalone Mister Bean Marker-and-Drawing Demo

**Purpose:** A compact, **self-contained presentation program** for the UFACTORY xArm 850 using a real marker rack, G2 gripper and A3 paper mounted on the wall.

**Entry point:** [`xarm_850_mister_bean_standalone_demo.py`](xarm_850_mister_bean_standalone_demo.py). For the original operator instructions and complete sequence, see [`README_Mister_Bean_Demo.md`](README_Mister_Bean_Demo.md).

## Sequence implemented

The code has a simple Tkinter window with **RUN MISTER BEAN DEMO**, **Connect / Recover**, **STOP**, progress/status and an activity log. The **RUN** action starts a background worker that executes:

1. Initial joints → **PICK_ABOVE** → open G2 → descend to PICK → grip marker (10 mm setting) → rise back up.
2. Cartesian **PICK_TRANSFER (about Z=520 mm)** → marker-compatible **DRAW_READY**; verify the intended six-joint READY branch.
3. Swing to **HANDOFF**, wait while an operator removes the cap, then return to DRAW_READY.
4. Lift and approach the wall for each stroke of the embedded Mister Bean drawing.
5. Return to DRAW_READY → HANDOFF; wait for the operator to replace the cap.
6. Return through DRAW_READY → PICK_TRANSFER → PICK_ABOVE → PICK, release the marker into the rack (50 mm opening), lift clear, transfer and return to Initial Position.

The application automatically runs those steps **in code**; cap removal and replacement remain **manual operator actions**. This is **not** a completely unattended, multi-marker color changer.

## Drawing and relationship to earlier projects

The program embeds an entire **`xarm850-freehand-v1` JSON drawing** directly in a Python string named `MISTER_BEAN_JSON`: **40 strokes and 408 original points**, width **359.6 × 235 mm**. Stroke shapes/coordinates match the separately archived [`mister_bean_color_compatible.json`](../freehand-drawing/example-drawings/mister_bean_color_compatible.json), but the standalone embedded copy omits palette/color metadata. **It does not read that JSON file at runtime** and does not switch markers by stroke color.

The source simplifies strokes, drops very short segments, centers the result horizontally, positions it at a fixed top margin and maps paper coordinates onto the **five-point, upper-right-clipped A3 reachable polygon**. It precomputes drawing paths before connecting to the robot. Pen-up travel uses **SAFE_X = −480 mm**, while paper contact X comes from the surface interpolation **plus a fixed marker offset**.

## Important documentation correction: contact X

| Historic configuration | Saved contact X offset |
| --- | ---: |
| **Actual standalone demo Python** | **−8.55 mm** |
| An older edition of the accompanying detailed README | **−19.17 mm (incorrect for this standalone script)** |
| Later combined full-app settings JSON, separately uploaded | **−12.3 mm (author-confirmed paper contact for that later setup)** |

The detailed README was corrected to **−8.55 mm** to match the actual standalone source. This program uses that constant directly and does **not** load the later full-app settings JSON. In this installation, **more-negative X travels toward the wall**; mixing historical settings can leave the marker floating or **press/crush it against the wall**. There is no contact-force feedback to prevent that.

## Status and dependencies

The program imports the **UFACTORY xArm Python SDK** and **Tkinter**. It does **not** need Pygame, a controller, SVG library or separate JSON artwork. Historical robot address is `192.168.1.208`. The bundled detailed README reports the system was used with Python 3.12.

**Evidence level:** the source implements the complete demonstration; the original author documentation describes the sequence and some real marker-handling observations. **A fresh end-to-end demonstration with this exact GitHub file has not been witnessed or executed in this archival review.** Keep the physical E-stop available and validate the actual robot mounting, rack, marker depth and clearances before live execution.

**Nothing in the Python source or calibration values was edited.** This folder's review only updates documentation.
