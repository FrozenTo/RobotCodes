# xArm 850 — Full marker-rack controller + drawing application

**Recovered 2026-11-04.** These are verbatim copies of four related apps and their matching original settings file from `Even more robot apps`. They were not in the initial GitHub upload.

| File | Distinguishing source detail |
| --- | --- |
| `xarm_850_full_app.py` | Adds the integrated controller, SVG/text/freehand and marker-changing operations; includes the **five-point clipped calibration** and marker-rack return code |
| `xarm_850_full_app_demo.py` | Separate demonstration-oriented full app variant; retain independently rather than assuming it replaces the main full app |
| `xarm_850_full_app_final.py` | Later variant with a saved **100°/s** `MAX_JOINT_SPEED` constant for simultaneous J1–J4 experimentation; **“final” is a filename, not proof of physical validation** |
| `xarm_850_full_app_normal_marker_speed.py` | Later variant with **10°/s** `MAX_JOINT_SPEED`; includes five-point paper calibration, direct multiple-joint gamepad mapping, and marker pickup/return GUI buttons including L3/R3 |
| `xarm_850_full_app_settings.json` | The full apps' historical GUI settings; the normal-speed script explicitly loads this filename from its own directory |

The source uses **five measured reachable wall points**, with a **clipped upper-right area**. It keeps the paper surface X model separate from the marker-tip contact offset; this is necessary because the 3D-printed marker rack makes marker insertion repeatable but does not measure force.

**Safety and accuracy:** The author reports that the rack-based setup no longer needed repeated manual X recalibration, but if the stored contact X is wrong, the marker can still fail to touch the paper or become crushed against the wall. Historical XYZ, J1–J6, calibration points and rack waypoints must not be treated as universal safe poses.

**Review state:** Source was located and restored; exact full-app functionality, UI controls, motion sequencing, latest working revision and hardware test results will receive a separate detailed review. No code execution or physical robot commands occurred during restoration.

For early marker-handling steps, see [Marker Handling Tests](../../marker-handling-tests/). For incremental five-point calibration, see [Five-point Development](../five-point-development/).
