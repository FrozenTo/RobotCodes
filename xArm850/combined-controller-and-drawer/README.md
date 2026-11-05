# xArm 850 / UF850 — Combined Controller and Wall Drawing

**Robot:** UFACTORY xArm 850 (historically also called UF850) with a G2 gripper, Xbox controller and **A3 paper on a vertical wall**.  
**Project:** Combine smooth multi-axis manual robot control, SVG/text/freehand drawing and (in later revisions) repeatable marker pickup, handoff and return using a 3D-printed physical rack.  
**Historical results:** The standalone joystick smoothing fix was **author-confirmed working**; xArm wall writing and hand-traced SVG drawing **worked very well**; the freehand v2.2 behavior integrated into combined v3 was **author-confirmed satisfactory**. Later marker/rack work is recorded in source and separate tests, but not every complete automatic sequence has a confirmed end-to-end physical run.  
**Source review:** 2026-11-05, after recovery of the 33 files missed by the original 100-file GitHub browser upload.

## Development map — three distinct phases

| Version / package | What it adds | Important historical distinction |
| --- | --- | --- |
| [Original combined app](xarm_850_combined_controller_drawer.py) | Integrates Xbox XYZ and selected-joint jogging with GUI text/SVG wall drawing, eight-point paper geometry, G2 control and shared marker-contact X offset | Early combined desktop app; no freehand canvas or full marker-rack workflow |
| [Original alternate copy](alternate-upload-copies/recovered-2026-11-04/xarm_850_combined_controller_drawer.py) | Nearly identical earlier upload | Its Git blob differs from main (the main source has an extra `#-500.6` comment); preserved as historical source, not overwritten |
| [Combined v2](xarm_850_combined_controller_drawer_v2.py) | Adds **Initial Position** commands and their UI/control routing | Builds on the original combined app; still not the full marker-changing controller |
| [Combined v3 package](v3-package/) | Integrates the successful standalone **freehand v2.2** editor into a third tab, sharing robot connection, automation lock and X contact setting with SVG/Text | Includes `xarm850-freehand-v1` JSON support; eight-point calibration; **author-confirmed successful freehand behavior** came from v2.2 |
| [Five-point v4](five-point-development/xarm_850_combined_controller_drawer_v4_5point_calibration.py) | Five taught points define a **clipped reachable A3 polygon** instead of treating the full rectangle as drawable | This is a **physical reachability correction**, not an arbitrary movement gate |
| [Five-point v6](five-point-development/xarm_850_combined_controller_drawer_v6_offset_corrected.py) | Separates **offset-neutral paper X** and marker `CONTACT_X_OFFSET_MM`; updates measured lower-right edge | Fixes **double application / mixing of offset and calibrated depth**, not general input restrictions |
| [Five-point v7](five-point-development/xarm_850_combined_controller_drawer_v7_safer_upper_right.py) | Teaches a more reachable **upper-right point** and records unreachable robot-error poses as reference only | Responds to **actual robot travel limits** |
| [Full marker app family](full-marker-app/) | Four saved integrated variants add marker rack/handoff, direct simultaneous J1–J4, color-group handling and later automatic routing | **Contains the overrestrictive waypoint gates** discussed by the author; see separate [full-app README](full-marker-app/README.md) |

The names `v5` or `v8` are **not present among the saved versions**. This is not, by itself, evidence of a further missing upload: not every development step produced a distinct retained source file. The [original raw 74-file folder](../../Even%20more%20robot%20apps/) and the [SHA-verified recovery map](../../RECOVERED_UPLOAD_MAP_2026-11-04.md) remain available.

## Combined controller behavior before marker automation

The original programs adapt the [xArm joystick prototypes](../controller-tests/): velocity-based Cartesian movement rather than MG400's single selected jogging axis. Their basic controller convention was:

- **XYZ mode:** right stick controls X/Y; left stick vertical controls Z (and joint 5/6 commands use the D-pad).
- **JOINT mode:** R1 switches modes, **L1 selects one of J1–J4**, and the right stick operates the selected joint; D-pad operates J5/J6.
- **G2 gripper:** analog trigger controls, robot STOP/recover, connect/disable and later Initial Position actions.
- **Wall drawing:** SVG or the nine-point character font on the Y/Z plane, lifting via safe X and approaching contact depth set from the eight measured paper points plus marker offset.

The joystick originally jittered badly in single-axis movement. Tuning on **2026-10-13** combined velocity timeout **0.15→0.50 s**, deadzone **10→15%**, TCP acceleration **400 mm/s²**, and smoothing **0.25**. The author then reported movement was **“very smooth and nice.”** These saved combined scripts retain the tuned values; the original jittery pre-fix build has not been identified in GitHub.

The author later noticed a **very small high-speed pause associated with J4 repositioning**, while normal-speed motion was smooth. This is an observed high-speed behavior, **not a confirmed SDK/IK diagnosis**, and it is not evidence that normal controller motion failed.

## v3 — successful freehand integration

The `v3-package` [release notes](v3-package/README.txt) explicitly identify two ingredients: the previous combined controller/SVG/Text app and the **freehand drawer v2.2**. Its tabs are **Controller**, **SVG/Text**, and **Freehand Drawing**. The freehand editor supports Pen/Line/Rectangle/Ellipse/Eraser, Undo/Redo, save/load JSON, waypoint preview, optional AIR test and direct DRAW. It supports the **same** `xarm850-freehand-v1` JSON format as the [shared drawing website](../shared-drawing-website/).

Important behavior retained from the author-approved standalone v2.2:
- **No compulsory AIR test** before a real drawing.
- **No requirement to start at Initial Position** before READY.
- **READY is optional**; when disabled, pen-up travel starts from the current robot pose, without hidden exact-pose gates.
- No arbitrary ±30/±38 mm X-offset limits, drawing speed/point-count caps or unreasonable size restrictions.
- Controller commands are paused when an automation worker owns the arm; STOP remains available.

The same **eight paper points** and **shared X marker-contact offset** are used by SVG/Text and Freehand. A different marker tip/grip length requires a different X contact adjustment unless physical pickup insertion becomes repeatable.

**Settings trap:** v3 source loads `xarm_combined_settings.json` **from beside the v3 script**, but that particular JSON **was not included in the archived v3 package**. The earlier folder's [`xarm_combined_settings.json`](xarm_combined_settings.json) is preserved separately and should **not be silently copied into v3**: it includes an earlier **−38 mm** marker-contact setting and local absolute SVG filepath. If v3 has no settings file, it starts from source defaults; saving creates one locally.

The v3 Python is **byte-identical** to [its extra upload](alternate-upload-copies/xarm850_combined_controller_drawer_v3.py).

## v4–v7 — five-point clipped wall geometry

The earlier eight-point mapping approximated a rectangular reachable surface. On the A3 sheet, the xArm couldn't reach the **true upper-right** region reliably. The v4-v7 code stores **five measured reachable points**: top-left, bottom-left, bottom-right, an upper-right-border lower point and an upper-right-border upper point. It triangulates the resulting **five-sided polygon**, rejects drawing coordinates outside it, and interpolates XYZ inside the triangles.

The actual history:
1. **v4:** first five-point interpolation and clipped top-right region.
2. **v6:** calibrations stored without the per-marker **−19.17 mm** contact offset so it is added **exactly once**; corrected right-side measurement and recorded first upper-limit error pose for reference.
3. **v7:** measured a safer **upper-right-top** location and preserved another error pose as a non-usable reference point.

These bounds have direct physical reasons. **Do not confuse rejecting an unreachable drawing point with refusing to route to an otherwise reachable marker waypoint.** Their details and three SVG boundary-test files are cataloged in [Five-point Development](five-point-development/README.md).

## Later full app — restrictive gates versus useful routing

The author reports that **too many exact-start-pose restrictions were introduced across several development versions**, creating unnecessary friction. The recovered code shows the pattern:

- The first `xarm_850_full_app.py` permits certain marker operations **only** from exact predefined waypoint configurations (`HANDOFF`, `DRAW_READY`, `PICK_TRANSFER`, `PICK_ABOVE`, `PICK`), otherwise raising an error. These restrictive checks are **not proof that other starting poses were physically unsafe**.
- `xarm_850_full_app_demo.py` lets pickup first command a joint move to `PICK_ABOVE` from another normal pose, but its **return-to-rack remains restricted**; the demo also keeps automatic multi-color rack cycling behind an explicitly unverified wrist-branch bridge.
- `xarm_850_full_app_final.py` and `xarm_850_full_app_normal_marker_speed.py` add **automatic route-to-PICK_ABOVE** and **route-to-DRAW_READY** methods for unknown normal poses, using known intermediate waypoints instead of demanding manual placement at an exact start pose. The L3 return path uses the pickup-column proximity test as a **routing hint, not a refusal**.
- The latest archived normal-marker-speed variant uses **10°/s controller max joint speed**, while `final` saved **100°/s**; *“final” in the filename does not mean the last successful build*.

**The right distinction:** An accessible hardware E-stop, wall-contact depth, collision clearance, verified arm wrist branch, staged PICK_ABOVE→PICK_TRANSFER→DRAW_READY path and reachable paper boundary are genuine physical concerns. An arbitrary rule that the operator must manually place the robot at one exact pose before pressing pickup/return is **a design choice, often later removed**. We should not add those gates back without a specific physical reason.

A later design discussion requested **L1 = automatic Go to READY** with route selection, replacing the archived **L1 held = precision Y/Z** control. **The restored full-app Python files still implement L1 precision mode**, not the later Go-to-READY mapping; that change should not be credited to the saved files unless its implemented source is separately archived and reviewed.

## A3 sheet, X offset and marker rack

Marker contact was very sensitive: the author reports **0.1 mm changes could matter** when a marker was taken out and reinserted. Too little negative X makes no mark; too deep into the wall can **crush the marker**. The most recent physical setup added a **3D-printed marker rack with a backstop**, giving a repeatable grip depth. The author reports **no more recalibration after that setup became consistent**, though the underlying missing-contact/overpressure hazard remains without force feedback.

The later full applications use **five-point geometry** and separately editable marker offset rather than mixing them. The original marker routes were developed through a series of isolated [Marker Handling Tests](../marker-handling-tests/), which should be reviewed individually. **A successful standalone move does not automatically verify the entire automated color-change sequence.**

## Dependencies and preserved files

- Robot network: historical `192.168.1.208`; official **`xarm-python-sdk`**, `pygame`, Tkinter, JSON and SVG parser.
- `v3-package/` includes the original requirements, launcher and detailed release notes.
- `five-point-development/` includes its own `xarm_combined_settings.json` (historical **−19.17 mm** contact X); **do not** use the older `−38 mm` JSON from this folder for that calibration.
- `full-marker-app/` contains its different `xarm_850_full_app_settings.json`, with settings for the later full app. The settings and absolute filepaths are local historical data, not transferable calibration.
- The physical A3 page is larger than the reachable paper polygon or arbitrary drawing-size defaults. Never assume the entire sheet is safe to contact.

**Review status:** Original combined apps, v3, five-point v4/v6/v7 and the saved full-app family have now been **source-compared and indexed**; standalone physical validation differs per feature and cannot be inferred from the code alone. Further targeted review of individual marker tests and the full-app operator workflow can expand the linked subfolder READMEs.

**No robot-control source, JSON settings, marker coordinates, SVG drawings or Python constants were changed during this documentation review.**

## Newly archived READY-routing / heading iterations (2026-11-05)

A subsequent five-file upload, [indexed here](full-marker-app/ready-routing-revisions/), includes **four later full-app code revisions** and their original saved JSON. They implement **L3 Y/Z-based return routing**, then **L1 single-press automatic Go to READY**, then a **unified drawing/marker READY joint branch**, then a **heading auto-shift** for the clipped upper paper reach boundary. This **supersedes the prior archive observation that L1 Go to READY was requested but not yet implemented**: it was not present in the earlier four full-app files but **is present in the newly archived revisions**. The author's −12.3 mm settings offset touched paper correctly; the Python -19.17 mm default must not be mixed with it. The author reported a READY regression and scary marker overpressure during development, but the exact affected code path and physical outcome of each latest script remain unverified. All original files were preserved byte-for-byte.
