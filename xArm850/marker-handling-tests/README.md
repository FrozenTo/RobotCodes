# xArm 850 — Marker Pickup, Transfer, Handoff and Return Tests

**Robot:** UFACTORY xArm 850 / UF850, G2 gripper, one physical **3D-printed marker rack with an alignment backstop**, historical robot IP `192.168.1.208`.  
**Purpose:** Test the **individual physical motion segments** that later became the automatic marker-change workflow in the [full xArm controller/drawer app](../combined-controller-and-drawer/full-marker-app/).  
**Outcome:** The author reports that pickup/return tests were used successfully in development and that the rack gave repeatable marker insertion. **Not every individual saved script or an entire multi-marker workflow has an independently confirmed live test record**. Reviewing a saved script is not the same as running it safely.
**Reviewed:** 2026-11-05, including the later READY-branch revisions archived on the same date.

## Why these tests exist

The xArm was already able to write and draw on **A3 wall paper**. Adding a marker rack meant that the robot needed to acquire and replace a physical marker **without disturbing its tip projection** (the wall-contact X offset was extremely sensitive), then return to a **compatible writing wrist configuration**.

A core issue was **inverse-kinematics / wrist-branch compatibility**. Two apparently identical tool-center-point locations can have different **J4/J5/J6** configurations. Sending the robot directly to older stored wall-writing joint angles from a marker pickup posture could make the wrist reconfigure unexpectedly. One source file expressly calls this a **wrist flip** risk. The developer therefore tested the route in short stages, reading the resulting joint solution at each stage before extending the route.

**Design lesson:** the **3° near-a-waypoint tests**, the **120 mm proximity checks**, and the prompts to press Enter were used to isolate an *untested motion segment* with a known starting condition. They were deliberate test gates, not proof that the robot must always be manually moved to those points. The later full app was revised to **route automatically to a waypoint when a suitable known path is available**, without unnecessary exact-start-position restrictions.

## The full marker route developed through the tests

```text
Marker pickup rack                 Wall-compatible workspace
─────────────────────────────────────────────────────────────
PICK_ABOVE
    ↓ slow joint descent
PICK  ──────────────── G2 closes on marker (10 mm)
    ↑ controlled joint lift
PICK_ABOVE
    ↑ linear Cartesian lift
PICK_TRANSFER (Z ≈ 520 mm)
    ↗ linear Cartesian move, preserve wrist branch
MARKER_DRAW_READY
    ↔ J1-only handoff swing
MARKER_HANDOFF  ────── operator removes/replaces marker cap

Return to rack:
MARKER_HANDOFF → MARKER_DRAW_READY → PICK_TRANSFER
              → PICK_ABOVE → PICK → release G2 (50 mm)
              → PICK_ABOVE
```

The source uses **multiple movement types** deliberately: controlled joint-space approach at the holder, Cartesian transfer between known spatial waypoints, and a mostly **J1-only** change from the compatible Draw READY to the handoff posture. The route is **specific to this xArm, marker holder and wall**; it is **not** an environment-aware or certified collision-free general planner.

## All eight archived experiment scripts

| Script | What it actually tests and how it handles the starting position |
| --- | --- |
| [`xarm_marker_pickup_test.py`](xarm_marker_pickup_test.py) | Standalone pickup/gripper test. Requires the TCP to be **within 120 mm of PICK_ABOVE**, pauses before joint entry, descent, G2 close and lift, and **intentionally does not go to DRAW_READY**. Uses cautious speeds **10°/s approach, 6°/s pickup**. |
| [`xarm_marker_pickup_test_from_initial.py`](xarm_marker_pickup_test_from_initial.py) | Adds an *experimental* route from UFACTORY **Initial Position (all joints ≈0°, tolerance 2°)** to PICK_ABOVE, while retaining the near-holder alternative. This script explicitly warns that this new Initial→PICK_ABOVE joint path was not previously validated. Uses **50°/s** initial route and faster **40°/s** PICK step in the saved defaults; not a universal safe route. |
| [`xarm_marker_pickup_to_z520_test.py`](xarm_marker_pickup_to_z520_test.py) | Pickup/lift, then **first linear Cartesian test from PICK_ABOVE to PICK_TRANSFER, Z=520 mm**. Stops there **without commanding DRAW_READY** so the result can be inspected. G2 and rack interaction are step-confirmed. |
| [`xarm_pick_transfer_to_cartesian_ready_test.py`](xarm_pick_transfer_to_cartesian_ready_test.py) | Starts within **3° of PICK_TRANSFER joint configuration**, then moves **linearly in Cartesian space to DRAW_READY_TCP** at **30 mm/s**. Reads resulting six-joint angles and compares them to the **old DRAW_READY** joint solution; prints the new compatible angles rather than calling the old wrist-branch handoff blindly. **Does not command HANDOFF.** |
| [`xarm_new_ready_to_handoff_test.py`](xarm_new_ready_to_handoff_test.py) | From the **new marker-compatible Draw READY** joints (3° tolerance), tests HANDOFF with **J1 rotation only**, preserving J2–J6 and using **8°/s**. Reads the resulting handoff joint angles and TCP. |
| [`xarm_move_ready_then_handoff_test.py`](xarm_move_ready_then_handoff_test.py) | Combines the previously separated segments: starts from **PICK_TRANSFER** or already at compatible Draw READY; if from transfer, makes the tested Cartesian approach; **verifies the resulting wrist branch**, then runs the J1-dominant handoff. Stops if the TCP reaches READY but the six joints are not compatible. |
| [`xarm_handoff_to_next_marker_test.py`](xarm_handoff_to_next_marker_test.py) | Tests the **reverse** route from HANDOFF: **HANDOFF → DRAW_READY (J1) → PICK_TRANSFER (Cartesian) → PICK_ABOVE (Cartesian)**. Ends at PICK_ABOVE by default; an explicitly requested final descent can also close G2 around the next marker. |
| [`xarm_return_marker_to_holder_test.py`](xarm_return_marker_to_holder_test.py) | Tests physically replacing a held marker in the rack: starts from HANDOFF or DRAW_READY (3° tolerance), routes through transfer and PICK_ABOVE, descends into PICK, opens G2 to **50 mm**, then lifts clear. It **rejects arbitrary start poses** because this isolated test only validates the selected route entry states. |

This table is based on actual saved program commands, prompts and constants. A script's printed text such as “test complete” is **a result the program would print if it ran successfully**, not historical proof that this exact Git blob was physically executed.

## The important READY/wrist discovery

[`xarm_pick_transfer_to_cartesian_ready_test.py`](xarm_pick_transfer_to_cartesian_ready_test.py) has unusually explicit developer comments: the **old DRAW_READY joint solution could cause a wrist flip** when approached from the pickup transfer. The experiment requests the **same physical READY TCP** as before, but with a *Cartesian* transfer preserving a compatible branch, then prints the achieved J1–J6 angles.

Those measured compatible READY angles were adopted by [`xarm_new_ready_to_handoff_test.py`](xarm_new_ready_to_handoff_test.py): approximately

```text
MARKER_DRAW_READY_JOINTS:
J1 = -196.531°   J2 =  7.519°   J3 = -77.102°
J4 =  181.202°   J5 = 80.921°   J6 = -195.831°
```

The compatible HANDOFF was built by adjusting primarily **J1 from −196.531° to −281.334°**, while preserving the other five joint values.

This explains why later attempts to use two different READY configurations in the same full app were problematic. The author's [newly uploaded unified SAFE READY version](../combined-controller-and-drawer/full-marker-app/ready-routing-revisions/) adopts the **same marker-compatible six-joint READY as the normal wall drawing READY**. Its actual physical results should still be checked separately; a matching named posture is not a guarantee every connecting path is safe.

## Why some of the restrictions were appropriate *here*, but not in the full app

The user experienced excessive software restrictions across subsequent versions of the complete combined app. These *standalone first-exposure movement experiments* are different:

- A **120 mm starting-distance filter** in the first pickup test limits which unverified approach paths it is willing to try.
- A **2° Initial Position recognition rule** in the from-initial version selects the dedicated experimental start case.
- A **3° joint tolerance** in transfer/handoff tests enforces the specific known starting wrist branch before testing a new motion segment.
- Repeated **Enter / inspect / E-stop-ready** prompts prevent automatically chaining segments that haven't yet been evaluated.

That is understandable in a short deliberate motion trial, but **the full app should not simply reuse the test's start-pose refusal as its normal UX**. Its job is to select or construct a validated waypoint route from the current state, declining only routes that cannot safely be established. Later [full-marker-app revisions](../combined-controller-and-drawer/full-marker-app/) progress toward that design.

## Marker precision and physical safety

The later rack used a **3D-printed alignment stop** so the gripper could grasp a marker at a consistent projection. This mattered because the **contact X offset on the A3 wall could vary by tenths of a millimetre**, and a bad value could leave the marker in air or **crush it against the wall**.

**Recent calibration clarification (2026-11-05):** in the latest READY-routing app, the author confirmed **−12.3 mm** was the correct marker contact offset for that physical marker/paper setup. Earlier full-app Python source defaults used **−19.17 mm**, nearly **6.87 mm farther inward/toward the wall** if applied to the same fixture. Both values have been retained, not merged or edited. The exact runtime source of a reported excessive-pressure incident is still unknown.

The test scripts themselves principally operate **in free space around the rack**. They do not calibrate wall contact or provide force feedback. Enabling an SDK G2 collision tool model or self-collision detection is **not** proof of safe physical motion; collision geometry and external wall/rack clearance still require testing.

**These scripts command live robot motion when run.** Do not replay old coordinates without verifying the actual arm mounting, G2 orientation, rack placement, pen seating, firmware limits, E-stop access and clearance along entire paths.

## Archive relationship and status

- **Earlier:** [xArm controller tests](../controller-tests/) → [text writing](../text-writing/) → [SVG drawing](../svg-and-text-drawing/) → [freehand drawing](../freehand-drawing/).
- **Integration:** [combined controller and drawer v1–v3](../combined-controller-and-drawer/) → [five-point calibration v4/v6/v7](../combined-controller-and-drawer/five-point-development/) → [full marker app variants](../combined-controller-and-drawer/full-marker-app/).
- **Latest uploaded revisions:** [L3 routing, L1 Go READY, unified READY, heading fix, and calibrated settings JSON](../combined-controller-and-drawer/full-marker-app/ready-routing-revisions/).

**No motion scripts, marker poses, gripper configuration, speeds or robot settings were modified in this documentation review.** The eight original test programs remain byte-for-byte preserved.
