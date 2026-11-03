xArm 850 Combined Controller + SVG/Text + Freehand Drawer v3
=============================================================

This build combines:
- the attached xarm_850_combined_controller_drawer_v2(1).py controller/SVG/text app
- the tested xarm850_freehand_drawer_v2.2 behavior

Tabs
----
1. Controller
   Existing Xbox controller, robot connection, STOP/recover, gripper,
   Initial Position and READY controls from the attached combined app.

2. SVG / Text
   Existing calibrated wall SVG drawing and line-font writing.

3. Freehand Drawing
   Paint-like vector drawing canvas with Pen, Line, Rectangle, Ellipse,
   Eraser, Undo/Redo, Save/Load JSON, path preview, optional AIR test,
   and direct DRAW on paper.

The Freehand tab uses the same xArm connection and automation ownership as
Controller and SVG/Text. Controller motion is locked while an automatic draw
operation is active, but the existing STOP remains active.

Freehand JSON compatibility
---------------------------
The tab reads/writes format: xarm850-freehand-v1
This is compatible with the shared browser drawing website created earlier.

Freehand behavior retained from v2.2
------------------------------------
- AIR test is optional.
- No requirement to start from Initial Position before READY.
- READY is the same joint pose:
  [-196.5, 7.5, -77.1, 1.2, -80.9, -15.8]
- Automatic READY can be turned off; then pen-up travel starts from the
  current robot pose.
- Pen X adjustment is not artificially capped; values such as -38 mm are
  accepted.
- No arbitrary software maximums for speed/acceleration/simplification.
- No hard stroke/point count caps.
- Pen-up safe X only has to be actually on the robot side of the commanded
  contact surface.

Shared calibration
------------------
The same 8 measured xArm wall-paper points from the attached combined app are
used by SVG/Text and Freehand drawing.

Important: Pen X adjustment is shared between the SVG/Text and Freehand tabs,
because it represents the physical marker/tool X offset. Changing it in either
tab changes the value used by both modes.

Dependencies
------------
Python packages:
  py -m pip install xarm-python-sdk pygame

Or:
  py -m pip install -r requirements.txt

Run
---
Double-click START_XARM_APP.bat
or:
  py xarm850_combined_controller_drawer_v3.py

Notes
-----
- The existing settings file name remains xarm_combined_settings.json.
  Old settings files remain usable; new freehand settings are added when saved.
- The shared website itself is NOT embedded in this desktop app. Downloaded
  website JSON drawings can be opened with Freehand Drawing -> Load drawing.
