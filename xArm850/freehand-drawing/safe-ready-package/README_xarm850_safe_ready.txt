XARM 850 FREEHAND DRAWER — SAFE READY REVISION (21 OCT 2026)
=========================================================

IMPORTANT: This app has NOT been tested on the physical robot. The tested items
are the Python syntax, GUI startup, calibration interpolation, robot path
planning, and simulated robot command sequence. Always assess clearance with
the operator physically present at the robot, and keep E-stop accessible.

1. INSTALL (Windows university PC)
   py -m pip install xarm-python-sdk

2. RUN
   py xarm850_freehand_drawer_safe_ready.py
   Or double-click START_DRAWER.bat if py is available in PATH.

3. WHAT CAUSED THE SUSPECTED PROBLEM?
   The previous freehand program sent a CARTESIAN command directly to the
   supposed READY XYZ position. The older combined controller used a known
   JOINT configuration, which can produce a different robot posture.

4. WHAT CHANGED?
   - Removed automatic Cartesian "move to ready XYZ" at test start/end.
   - Restored READY JOINTS from uploaded combined app:
       [-196.5, 7.5, -77.1, 1.2, -80.9, -15.8] degrees
   - Added explicit "0. Move to READY (joint motion)" button, only available
     from near all-zero Initial joints or near Ready; requires confirmation.
     NEVER USE THIS BUTTON IF THE JOINT MOVE ITSELF WAS COLLIDING BEFORE.
     A joint-space move is not automatically collision-free!
   - Air/drawing start is REFUSED unless the robot is near that READY joint
     configuration or the previously verified pen-up gateway from the same
     session; also checks measured XYZ and tool orientation.
   - Restored the known pen-up SAFE X plane (-480 mm), and first moves to
     X=-480 at the central ready Y/Z before traveling across the paper.
   - Ends the air test and the drawing on that SAME pen-up gateway rather than
     folding back to READY. The real drawing can begin from the gateway after
     the air test without resetting the robot.
   - Enables the xArm self-collision option; optionally sets the G2 gripper
     collision model to 9, only if that model corresponds to the actual tool.
   - Uses the eight most recent contact calibration values from the combined
     program (each X is 2 mm LESS NEGATIVE than the initial freehand version).
     Custom calibrations are preserved; only old default values are migrated.
   - Uses the same xarm850-freehand-v1 JSON file format as the drawing website.

5. SAFE FIRST USE
   a) Stop using the previous freehand app for robot testing.
   b) Inspect robot, gripper, pen holder, and nearby obstructions. Identify
      where the prior self-collision occurred. Do not simply reset and retry.
   c) Use the combined controller to establish the proven READY joint pose if
      any doubt about initial-to-READY joint-path clearance. The separate
      'Move READY' button is not a guarantee of a safe joint trajectory.
   d) Connect new freehand app. Draw a short line near page center. Preview
      planned XYZ path.
   e) Start the AIR TEST at low speed with a person ready to stop. It will
      refuse if the arm isn't in the expected configuration. Note: a pen-up
      air test still moves the robot and CAN collide with the arm/environment.
   f) After observing a successful full air test, consider real contact
      only when marker TCP, paper placement, pen pressure (-7 mm historic),
      fixtures, and clearance have been checked physically.

6. G2 COLLISION CHECKBOX
   The combined controller used tool model 9 for an attached G2 gripper.
   This revision carries that option. Uncheck if the G2 gripper is NOT fitted
   and consult UFACTORY settings for the proper collision model of the
   current tool. Self-collision detection is not a guaranteed safeguard for
   pen holders and accessories, and does not replace physical E-stop.

7. IF IT STILL FOLDS TOWARD ITSELF
   Stop motion. Record current joint angles, the reported error code, and
   which move was executing (READY joints, first X travel, first Y/Z stroke,
   or pen contact). Do not repeat motion until the failing path is understood.

Files from students/the website: use "Load drawing" for downloaded JSON.
The website/server files DO NOT require modification.
