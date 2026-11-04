# xArm 850 — Marker pickup, return and handoff tests

**Recovered 2026-11-04** from the incomplete original `Even more robot apps` upload. These scripts are **isolated physical motion experiments**, not the complete full-marker-rack application.

## Progression found in source

| Script | Experiment |
| --- | --- |
| `xarm_marker_pickup_test.py` | Pick a marker using manually taught `PICK_JOINTS` / `PICK_TCP` and a raised approach point, with slow descent and G2 gripper control |
| `xarm_marker_pickup_test_from_initial.py` | Variant of pickup which routes from **initial/home** (a restrictive start-pose condition was used for this isolated safety test) |
| `xarm_marker_pickup_to_z520_test.py` | Continue the pickup workflow up to a transfer height near Z=520 mm |
| `xarm_pick_transfer_to_cartesian_ready_test.py` | Experiment moving from a pickup transfer waypoint to the paper-writing READY pose |
| `xarm_new_ready_to_handoff_test.py` | Joint-space movement between the new pickup-compatible drawing READY pose and marker handoff pose |
| `xarm_move_ready_then_handoff_test.py` | Tests approaching the handoff pose from the revised READY/transfer posture |
| `xarm_handoff_to_next_marker_test.py` | Routes handoff toward the next marker pickup; includes optional short final pickup descent |
| `xarm_return_marker_to_holder_test.py` | Return the marker to its physical rack/holder |

All scripts contain **setup-specific taught robot coordinates** (for `192.168.1.208`) and several include special start-pose checks because they were **isolated tests**. Those restrictions should not be silently propagated into the later general-purpose full app; production motion should route safely to required waypoints instead.

The author designed a **3D-printed physical marker rack with a backstop/alignment wall** to obtain consistent marker insertion. The author reports that separate pickup/return experiments worked, and later rack-based usage avoided repeated recalibration. Individual full-file physical outcomes and the final integrated marker swap sequence are not independently retested in this archive review.

**Safety:** These scripts send **live xArm/G2 gripper movement** and were written for one physical rack and workspace. Their approach, return, startup and handoff poses may be dangerous if hardware or markers change. Use a physical E-stop and revalidate before live execution.

See [Full Marker App](../combined-controller-and-drawer/full-marker-app/) and [Five-point Development](../combined-controller-and-drawer/five-point-development/).
