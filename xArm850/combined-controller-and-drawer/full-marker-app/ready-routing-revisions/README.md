# xArm 850 — Later Full App READY Routing and Heading Fixes (2026-11-05)

**Source:** Five original files uploaded by the author to the repository root, then copied here **byte-for-byte by their Git blob SHA**. The original five root-level files remain available for comparison. These scripts are later than the four [earlier full marker apps](../) and must **not** be confused with the separate [five-point v4/v6/v7 calibration experiments](../../five-point-development/).

**Working-status warning:** The user reports that READY movement may have regressed in one of these revisions and later been corrected, and that a marker at one point pressed worryingly far into the paper. **Neither the precise hardware test result for each new version nor the source-level cause of the overpressure has been established.** Treat these as archived iterative builds; no version is declared physically verified or inherently safe just because it is named “safe” or “fix.”

## Version sequence and source-confirmed differences

| File | Development changes |
| --- | --- |
| [`xarm_850_full_app_l3_routing_v2.py`](xarm_850_full_app_l3_routing_v2.py) | Expanded L3 marker-return routing based on Y/Z position rather than refusing unrecognized starting positions. **L1 still means held precision Y/Z**. Normal saved maximum J1–J4 speed is 10°/s. |
| [`xarm_850_full_app_l1_ready_r3_handoff.py`](xarm_850_full_app_l1_ready_r3_handoff.py) | Changes **L1** to a single-press automatic **Go to Draw READY** action, preserving **R3 pickup + cap-removal handoff** and L3 return routing. This version still defines a **different `READY_JOINTS`** from its marker-compatible `MARKER_DRAW_READY_JOINTS`. |
| [`xarm_850_full_app_unified_safe_ready.py`](xarm_850_full_app_unified_safe_ready.py) | Makes the ordinary drawing READY and marker-compatible DRAW_READY share **one six-joint configuration**: `MARKER_DRAW_READY_JOINTS = list(READY_JOINTS)`. The unified posture uses a substantially different **J4/J5/J6 wrist configuration** from the older writing READY. This is a plausible code response to inconsistent READY/wrist branches, **not proof of a physical fix**. |
| [`xarm_850_full_app_safe_ready_heading_fix.py`](xarm_850_full_app_safe_ready_heading_fix.py) | Retains the unified READY arrangement; changes heading generation to move the entire text **down in 0.5 mm increments, up to 30 mm**, when its top points lie above the clipped five-point reach boundary, rather than rejecting otherwise usable headings. This is **geometric layout handling**, not contact-pressure regulation. |
| [`xarm_850_full_app_settings.json`](xarm_850_full_app_settings.json) | Saved settings uploaded with this later set, including `contact_offset = -12.3`, `joint_speed = 10`, `move_ready = false`, and example `Mr.Bean` heading text. Every script loads **this filename from the script directory**, so keep this JSON here. |

All four scripts still have a **five-point calibrated reachable A3 wall polygon**, manually adjustable X contact, Xbox XYZ and simultaneous joint control, G2 gripper, marker pickup/return/handoff and color-aware SVG/JSON drawing. No live robot command was sent during this review.

## READY distinction — automatic routing versus wrist configuration

**L1 READY routing:** the newer controller code reads the current TCP and chooses:

1. **Y > 160 and X > −350 mm:** go through **HANDOFF** and then Draw READY.
2. Otherwise, if **Z < 290 mm:** move through **PICK_ABOVE → PICK_TRANSFER (~Z 520) → DRAW_READY**.
3. Otherwise, use a more direct move to Draw READY.

These are **route-selection rules**, not blanket requirements that a user manually position the arm at exactly one pose. They do not certify arbitrary joint-to-joint paths as collision-free.

The earlier L1-ready version contains distinct six-joint values for the normal wall-writing READY and the marker-compatible DRAW_READY (which have substantially different wrist joint branches). The **unified** revision deliberately makes them the same. That is the main source evidence for a **READY consistency revision**. Whether it resolved every physical movement concern must still be established by actual test feedback.

**Important:** an earlier combined-app README said L1 Go to READY was merely a *requested future change*. **These newly uploaded files now contain the actual implementation**, so that statement is outdated and corrected in the parent documentation.

## Marker X contact: verified author correction

The archived scripts define `CONTACT_X_OFFSET_MM = -19.17` in Python as an initial default. The **newly uploaded settings JSON explicitly stores `contact_offset = -12.3`**.

**Author's physical observation:** the marker touched the paper correctly at **−12.3 mm** on this setup. The roughly **6.87 mm extra inward travel** associated with the earlier −19.17 mm default was alarming; with the same physical fixture, a more-negative X moves **toward** the wall. **The corrected −12.3 mm value must be preserved, not described as erroneous.**

The GUI loads the JSON into its contact-offset control, and applying drawing settings updates the module's `CONTACT_X_OFFSET_MM` used to calculate wall contact. The Python default can still matter if the JSON is missing, isn't loaded or a code path uses the module value before applying GUI settings. **No exact root cause of the incident is proven from the files alone.** Do not assume the wall or marker changed, or that any selected file was the exact run that caused pressure.

There is **no force or tactile contact feedback**. Even the confirmed −12.3 mm setting is only known to have worked for the specific marker, rack, gripper and paper arrangement tested, not a generally safe universal offset.

**Do not change or merge** this JSON with the earlier [full-marker-app settings](../xarm_850_full_app_settings.json), which stores the old −19.17 value. Historical settings belong with the corresponding script revisions.

## Integrity and safety

- The four Python files and their settings JSON were **copied unchanged** into this project subfolder. The originals remain at the repository root.
- The latest filename `safe_ready_heading_fix` identifies the last **uploaded revision**, not independent certification that the marker pressing problem or all movement paths have been solved.
- Keep the physical E-stop accessible, confirm actual robot TCP/joints, confirm contact X and holder geometry, and test pen-up waypoints before trying another wall-contact move.
- The recovered marker rack scripts, test results and version history are documented in [Marker Handling Tests](../../../marker-handling-tests/).

See also [Full Marker App version history](../README.md), [Combined Controller history](../../README.md), and [five-point calibration](../../five-point-development/README.md).
