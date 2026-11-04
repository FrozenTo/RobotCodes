xArm 850 Freehand Drawer v2.2

Purpose of this revision:
Remove artificial software restrictions that were not present in the older working combined xArm app, while keeping basic validity/safety checks.

Changes from v2.1:
- Pen X adjustment remains unrestricted (e.g. -38 mm is accepted).
- AIR test remains optional; no AIR-test prerequisite for real drawing.
- Move READY no longer requires Initial Position first.
- When "Move to READY before AIR / DRAW" is OFF, the app no longer requires READY or a previously verified gateway. It starts pen-up Cartesian travel from the current robot pose, matching the previous combined app behavior.
- Removed the extra Cartesian READY/gateway waypoint. Each stroke now follows: travel pen-up to stroke start -> approach -> draw -> retract.
- Manual Move READY always sends the READY joint command instead of refusing/skipping based on a near-READY tolerance.
- Initial Position likewise always sends the requested 0-degree joint target after confirmation.
- Removed arbitrary paper dimension maximum/minimum ranges; dimensions only need to be positive and contain the selected margin.
- Removed arbitrary upper software limits on draw/travel/approach speed and acceleration. The xArm controller/SDK still enforces its own valid ranges.
- Removed the 3 mm maximum simplification restriction; simplification only needs to be >= 0.
- Added configurable Approach speed (default 25 mm/s, matching the older combined app).
- Added configurable Path point spacing (default 3 mm).
- Removed the 2000-points-per-stroke rejection.
- Removed the 4000-strokes-per-file rejection.
- Long paths are periodically flushed to the SDK queue instead of being rejected.
- Removed the hard 200-point cap when constructing ellipse geometry.
- Pen-up safe X no longer needs an arbitrary 7 mm clearance; it only must actually remain on the robot side of the commanded contact surface.

Intentionally retained checks:
- Paper width/height must be > 0.
- Margin must be >= 0 and fit inside the page.
- Speeds, acceleration, and path spacing must be > 0.
- Simplification must be >= 0.
- Drawing coordinates must remain inside the calibrated page/margin.
- Pen-up safe X must be away from the commanded paper-contact surface, not behind it.
- A drawing must contain at least one stroke before AIR/DRAW can run.
- The READY move is still verified after the joint command; TCP XYZ/RPY differences are warnings.
- STOP, self-collision setup, G2 collision model option, and explicit robot enable/recover behavior remain.

Install robot dependency:
    py -m pip install xarm-python-sdk

Run:
    py xarm850_freehand_drawer_v2_2.py

Drawing-only/offline use requires no xArm package until you connect to the robot.
