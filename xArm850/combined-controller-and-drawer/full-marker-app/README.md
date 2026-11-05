# xArm 850 — Full Marker Controller + Wall Drawing Apps

**Recovered from:** Original `Even more robot apps` folder (complete 74-file re-upload, 2026-11-04). The four saved Python files and their matching JSON are preserved here **without changes**.  
**Goal:** Integrate smooth Xbox XYZ and simultaneous J1–J4 control, SVG/text/freehand drawing on A3 wall paper, calibrated pen-contact X, and a repeatable marker rack and user cap-removal handoff.  
**Review:** 2026-11-05, source review with author history. **Individual marker pickup/handoff/return stages had physical tests; complete multicolor drawing and every integrated automatic operation are not independently confirmed end-to-end.**

## Why there were so many versions

The author repeatedly found the added **exact-start-pose restrictions** obstructive and unnecessary for normal operation. This matters because the earliest full app had a genuinely restrictive workflow: it knew how to route among a small set of predefined marker positions but refused an action from any other position, even when the intended destination was reachable through planned intermediate moves.

Later variants **improved usability by routing the robot to the required waypoints automatically**, rather than requiring the operator to manually reach an exact initial position first.

**Differentiate two things:** a *route-selection hint or calibration/reachability limit* can be meaningful, but an *arbitrary start-pose refusal* is not evidence of collision danger. These applications still require a clear physical path, accessible hardware E-stop and correct wrist configuration; moving to a waypoint from an arbitrary posture is not, by itself, collision-free.

## Which complete file does what?

| File | What changed | Source-based limitations |
| --- | --- | --- |
| [`xarm_850_full_app.py`](xarm_850_full_app.py) | First combined marker-station version with `PICK`, `PICK_ABOVE`, `PICK_TRANSFER`, `DRAW_READY`, `HANDOFF`, G2 grip/release, manual/assisted color handling | **Exact-pose gates** reject pickup/return/handoff unless the current joints match one of a few predefined configurations. Automatic multi-color station cycle **disabled** (`AUTO_MARKER_COLOR_CYCLE_ENABLED=False`) |
| [`xarm_850_full_app_demo.py`](xarm_850_full_app_demo.py) | Adds **pickup from other normal poses** via a direct joint move to `PICK_ABOVE`, an associated pickup continuation, and a **Mister Bean demo** sequence/controls | Pickup gate largely removed, but **return-to-holder and other helper routes still have exact-pose requirements**. Auto marker-station color cycling remains **disabled** while a wrist-branch transfer needed verification |
| [`xarm_850_full_app_final.py`](xarm_850_full_app_final.py) | Introduces broader **automatic route-to-pick and route-to-draw-ready** handling, R3 pickup with cap-removal handoff, L3 return to rack, single-press controller actions, and enabled color-cycle code | `MAX_JOINT_SPEED=100°/s` for simultaneous-joint experimentation; `MARKER_ANYWHERE_JOINT_SPEED=80°/s`. **“final” is a filename, not proof of the final/most used build** |
| [`xarm_850_full_app_normal_marker_speed.py`](xarm_850_full_app_normal_marker_speed.py) | Keeps the automatic routing and five-point calibration while returning to **normal/less aggressive speed choices** | Saved `MAX_JOINT_SPEED=10°/s`; marker-route joint speeds use `READY_JOINT_SPEED=20°/s` and Cartesian marker travel uses `TRAVEL_SPEED=100 mm/s`. It does **not** mean *all* marker movements are limited to 10°/s |

The full-app variant differs from the earlier standalone [marker-handling scripts](../../marker-handling-tests/), which were purpose-built isolated tests and can have stricter starting assumptions.

### Overrestrictive gate in the first full app — actual source evidence

`xarm_850_full_app.py` has a `marker_pose_name()` function that checks the current six joint angles against taught `HANDOFF`, `DRAW_READY`, `PICK_TRANSFER`, `PICK_ABOVE` and `PICK` within **3°**.

For example, `marker_go_to_holder()` routes from the known predefined states, but if the current joints return `OTHER` it raises an error saying movement **only starts from tested marker-route poses**. `marker_handoff()` also insists on `DRAW_READY`. That is an **application gating policy**, not the robot's physical maximum travel capability.

In `xarm_850_full_app_demo.py`, `marker_go_to_pick_above_anywhere()` allows a **direct joint command** to `PICK_ABOVE` from a different pose (the source explicitly says “not pose-gated”). However, its `marker_go_to_holder()` still contains the earlier restricted route logic. The demo's assisted multi-color mode is not an automatic color-rack solution.

In **`final` and `normal_marker_speed`**, `marker_route_to_pick_above()` and `marker_route_to_draw_ready()` detect known waypoint states and take appropriate routes. For unknown **normal** poses, they select a more general approach via `PICK_ABOVE`, then use the higher `PICK_TRANSFER` (~Z=520 mm) and `DRAW_READY` as needed. **L3 return** uses proximity to the pickup column as a **routing heuristic** to choose a transfer waypoint when appropriate; its radius check is **not a refusal gate**.

The author explicitly preferred this: **press the task button and have the robot route itself**, instead of requiring an exact manually reached initial pose. This preference does **not** waive trajectory verification if a proposed new path would risk hitting the marker rack, paper, wall or arm.

### Important physical route distinctions

- `PICK` / `PICK_ABOVE`: physical marker holder and raised approach.
- `PICK_TRANSFER` (~Z=520 mm): higher transfer point between rack and wall-compatible configuration.
- `DRAW_READY`: marker-compatible approach posture for wall drawing.
- `HANDOFF`: user can remove/replace the marker cap without entering the robot's movement area.

The source deliberately uses the **higher transfer route** for rack→wall travel, rather than blindly moving directly between `PICK_ABOVE` and `DRAW_READY`. The wrist/joint branch also matters: reaching an equivalent TCP coordinate via a different arm configuration may not be safe or compatible with the recorded handoff path.

These physical waypoint choices are **not** unnecessary restrictions. They are distinct from demanding that the operator pre-position the robot to an exact pose before accepting a command.

## Controller mappings in the archived full apps

Compared with the older [selected-joint controller](../../controller-tests/), these full apps include **simultaneous J1–J4 velocity**:

- **XYZ mode:** right stick X/Y, left stick vertical Z.
- **JOINT mode (R1 toggle):** **right stick horizontal J1, vertical J2; left stick vertical J3, horizontal J4**; D-pad J5/J6.
- **L2/R2 triggers:** G2 gripper motion.
- **Y:** Return to Initial Position.
- **R3:** Pick marker; in `final` and `normal_marker_speed`, a **single press** begins the full pickup route, continues to user handoff for cap removal, then goes to Draw Ready after the cap prompt.
- **L3:** Return held marker to the rack, with automatic routing in the later two variants.
- **A:** software STOP; **B:** disable/exit; **X:** recover.

**Archive-versus-future-mapping distinction:** These four uploaded files still implement **L1 held = precision Y/Z wall-plane control**, a scoped stick mode with 50% default speed. The author later requested **L1 = automatic Go to READY**, using safe routing through handoff or PICK_ABOVE/PICK_TRANSFER as needed. **That newer L1 mapping is not present in the saved files**; it should be documented as subsequent requested development, **not attributed to this GitHub source** until its implemented file is archived.

The author reports that XYZ manual movement is smooth following earlier tuning. At higher speeds, a **very brief pause linked with J4 reorientation** can occur, but it is minimal. The underlying mechanical/IK/SDK explanation has not been confirmed.

## Color-aware SVG and JSON support

These full apps recognize paths from SVG and the **`xarm850-freehand-v1`** drawing JSON format also used by the shared website. A color palette maps strokes/colors to marker choices (the source names a **Fiorello 12-marker set**). SVG color mapping is opt-in; loaded color-compatible JSON strokes can be grouped by their saved colors. Plain text is handled as the default black color during automatic color workflows.

The original and demo full apps have **`AUTO_MARKER_COLOR_CYCLE_ENABLED=False`**. Their current assisted workflow asks the operator to swap markers manually at the wall-ready location. Their disabled branch references a **not-yet-validated marker/wall wrist-branch bridge**, so do not call the automatic color cycle completed in those versions.

The `final` and `normal_marker_speed` sources enable color cycling. For each detected color they **ask the operator to put the relevant capped marker in the holder**, pick it, go to handoff, wait for the **cap removal**, draw that color, return to handoff for **cap replacement**, and return the marker to the rack. This is **operator-assisted automatic motion**, not autonomous cap handling or a fully automatic 12-slot tool changer.

There is no proof here that a complete multi-marker colored drawing was physically run through every step. Source support and physical outcome remain separate.

## A3 wall calibration and physical marker rack

All full-app variants use **five taught reachable paper points** rather than the previous eight-point rectangular model. The upper-right corner is **clipped** because the robot could not reach that part of the A3 sheet. The source interpolates inside the reachable polygon, rejecting points outside.

The separate contact `CONTACT_X_OFFSET_MM` defaults to **−19.17 mm**. The calibrated paper X is recorded **without that offset**, so the code applies the marker adjustment **once** when calculating contact. A wrongly adjusted X can leave no ink or **crush the marker against the wall**: **there is no automatic force/contact sensing**.

The author built a **3D-printed rack with a physical locating wall/end stop** so each marker is held at a reproducible projection. The author reports this eliminated the need for repeated manual X recalibration after the latest setup. That observation is important but does not make old saved offsets safe on a changed tool.

## Settings JSON — keep it with the app

[`xarm_850_full_app_settings.json`](xarm_850_full_app_settings.json) is the original full-app settings file. It includes the historical IP `192.168.1.208`, controller deadzone `0.15`, max TCP speed `80`, acceleration `400`, smoothing `0.25`, contact offset **−19.17**, optional SVG and text settings, and an absolute Windows path to a local `drawing.svg`.

**Do not confuse this with either** `xarm_combined_settings.json` for the original eight-point combined app or the five-point intermediate versions. The full app's settings loader expects its **own filename beside the Python source**. Also note that saved settings may override some source defaults, so the runtime speed or drawing configuration must be read from both code **and JSON**.

The settings file does not certify the marker rack geometry or the current robot TCP calibration.

## Development status and next review

| Topic | Evidence level |
| --- | --- |
| Smooth simultaneous XYZ | **Author-confirmed** in earlier xArm controller tests |
| Smooth simultaneous J1–J4 interface | **Source-implemented** in these full apps; precise physical validation by variant not established |
| Wall text/SVG/freehand drawing | **Author-confirmed successes** in preceding standalones; integrated workflow requires setup-dependent testing |
| Five-point clipped reachable calibration | **Source-implemented;** upper-right restrictions follow recorded real robot-limit problems |
| Individual marker pickup/handoff/return | **User-reported tested in stages**; see [marker-handling tests](../../marker-handling-tests/) |
| Single-press R3 pickup / L3 rack return | **Source-implemented** in later two variants |
| End-to-end multi-color automatic changing | **Implemented in later source, not confirmed end-to-end on physical robot** |
| L1 automatic Go to READY | **Later requested mapping; not implemented in these archived four files** |

**Source-review conclusion:** The many iterations were **not** evidence that an xArm was inherently unable to move between ordinary poses. Some versions imposed restrictive *software gates*; the later full app instead **routed automatically**. Preserve the genuine A3 reachable-area, wrist branch and marker contact constraints.

**No Python source, gripper/marker poses, tool offsets, speeds or settings JSON were modified during this review.**

## Additional later READY-routing versions (uploaded 2026-11-05)

The four full apps compared above **are no longer the last archived versions**. See [READY Routing Revisions](ready-routing-revisions/) for four newer scripts: `xarm_850_full_app_l3_routing_v2.py`, `xarm_850_full_app_l1_ready_r3_handoff.py`, `xarm_850_full_app_unified_safe_ready.py` and `xarm_850_full_app_safe_ready_heading_fix.py`, plus the **separate** matching settings JSON. In those later versions **L1 Go to READY is implemented**, the drawing and marker READY joint branches are unified, and the final uploaded script shifts headings that would be outside the clipped top boundary. This updates (but does not erase) the older-version summary above, where L1 was precision mode.

**Crucial contact-offset distinction:** the latest uploaded JSON uses **−12.3 mm**, physically confirmed by the author to place the marker on paper correctly in the latest setup. The code's default is still **−19.17 mm**, nearly **6.87 mm more negative/toward the wall**, and cannot be used interchangeably. The user reported alarming excessive wall pressure during this development; the exact offending runtime offset remains unproven. The last script's “safe” filename is not a hardware safety guarantee. Original Python/JSON files unchanged. [Latest upload map](../../../XARM_LATEST_UPLOAD_MAP_2026-11-05.md).
