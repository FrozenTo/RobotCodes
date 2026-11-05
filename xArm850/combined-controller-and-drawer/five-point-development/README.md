# xArm 850 — Five-point A3 Paper Calibration (v4, v6, v7)

**Purpose:** Replace the older **eight-edge-point rectangular wall model** with a **five-point reachability-aware paper model** for the author's vertically mounted **A3 paper**. **The entire upper-right physical area was not reachable by the xArm in its configured posture.** This is a real robot/workspace limit, not an arbitrary software safety gate.  
**Status:** Source reviewed 2026-11-05. The author reports the later five-point setup was used for subsequent marker work. Exact physical test results for each code hash are not independently reverified here.

## Why five points instead of eight?

The prior eight-point mapping used a rectangular logical drawing region based on top/middle/bottom measurements on both sides. That could imply points existed near the full top-right edge even when the xArm could not reach them.

The five-point model uses a **clipped pentagon** and explicitly rejects unreachable drawing coordinates. Its taught points are:

```
TL --------------------- TR_TOP
|                          \
|                           TR_BOTTOM
|                           |
BL ------------------------ BR
```

The missing top-right triangle is not drawable; neither an SVG stroke nor a text character can simply be extended into it. The script derives logical paper coordinates from measured Y/Z edge distances, then **triangulates the pentagon into three triangles** and uses **barycentric interpolation** to calculate contact XYZ. The vertices are reproduced exactly by the interpolation (up to numerical tolerance). Drawing outside the calibrated region raises an error rather than extrapolating into the unreachable space.

The source performs a **pure-math calibration consistency check** at startup; that is **not** a collision check or proof that commanded motion is physically safe.

## Source versions

| File | Technical change | Historical interpretation |
| --- | --- | --- |
| [`xarm_850_combined_controller_drawer_v4_5point_calibration.py`](xarm_850_combined_controller_drawer_v4_5point_calibration.py) | First five-point polygon. Stored `CONTACT_X_OFFSET_MM=-7.0` and first taught `TR_BOTTOM`/`TR_TOP` points | **First geometry experiment**; later corrected for actual marker length and reach |
| [`xarm_850_combined_controller_drawer_v6_offset_corrected.py`](xarm_850_combined_controller_drawer_v6_offset_corrected.py) | Updated marker offset to **−19.17 mm**, stored **marker-offset-neutral wall X** values, corrected right-side lower point and preserved one out-of-limit TCP pose as reference only | Fix for a **real calibration offset problem**, not a reason to require an exact start waypoint |
| [`xarm_850_combined_controller_drawer_v7_safer_upper_right.py`](xarm_850_combined_controller_drawer_v7_safer_upper_right.py) | Shifted `TR_TOP` to a more reachable measured position, while keeping previously failing poses in **`TR_TOP_ERROR_TCP` / `TR_BOTTOM_ERROR_TCP`** only for diagnosis | Responds to **real upper-right motion limit feedback**; these error poses are **not used for drawing** |
| [`xarm_combined_settings.json`](xarm_combined_settings.json) | Saved settings for this five-point project, including `contact_offset=-19.17` and the latest limit-test SVG | Version-specific; do **not** merge with earlier eight-point JSON |
| [`test-drawings/`](test-drawings/) | Three small SVG experiments focused on the upper-right limit boundary | Keep all as distinct geometric test attempts |

The filenames jump v4 → v6 → v7, and **no v5 source is present** in this saved set. That alone does not establish a file was lost; the original 74-file upload has since been checked for completeness.

## Contact X versus marker length

This was the central calibration subtlety: a recorded paper-contact pose can already include the marker-tip offset. If the `PAPER_*` X positions include that offset and the interpolation code adds it **again**, the robot travels too far toward the wall.

The v6/v7 sources explicitly distinguish:

- **Calibrated paper X:** a marker-offset-neutral wall coordinate.
- **`CONTACT_X_OFFSET_MM`:** the current marker tool/tip adjustment (−19.17 mm in these versions).
- **Final commanded X:** interpolated paper X **plus the marker offset once**.

For example, v6 documents one physically taught lower-right safe-point raw X **−533.550537 mm** taken with the −19.17 mm marker offset, and records the offset-neutral calibrated X as **−514.380537 mm**. An out-of-limit measurement is retained in a separate `*_ERROR_TCP` field and must not be silently substituted as a usable point.

The author reports that marker contact could vary noticeably with **0.1 mm** changes, and a wrongly set X can make no mark or **crush the marker against the wall**. The later 3D-printed pickup rack improved repeatability of insertion; it does **not** provide force/contact feedback.

## Why the upper-right was revised again

In v6, the initial reachable upper-right-top measurement was at approximately **Y=208.36, Z=748.25**. In v7, the revised taught upper-right-top is approximately **Y=185.93, Z=738.72**, moved inward/down into the robot's more usable region.

The v7 source records the upper-right error pose separately from the new `PAPER_TR_TOP` and explicitly excludes it from interpolation. The earlier lower-right-border limit condition remains documented.

This is a **justified reachability boundary**. It is very different from an operator-facing condition such as *“you must manually place the robot at this exact starting joint pose before pickup.”* That kind of requirement appeared later in the marker-changing apps and was progressively replaced by automatic routing.

## Usage and follow-on projects

The scripts are historical **live-capable xArm controller + drawing applications**, not simulations. They retain the existing controller, SVG and text features while experimenting with calibration.

The logical page and the physical A3 paper are not interchangeable: the GUI's SVG sizing can change, but path points are still rejected outside the **calibrated polygon**. The test SVGs are preserved to show what was tried when investigating the upper-right boundary.

The five-point polygon and marker-contact logic carry forward to the [full marker-rack app](../full-marker-app/) and are separate from the older [eight-point SVG program](../../svg-and-text-drawing/).

**No Python source, measured poses, error-reference coordinates, marker offsets, SVG test patterns or settings JSON were edited in this review.**
