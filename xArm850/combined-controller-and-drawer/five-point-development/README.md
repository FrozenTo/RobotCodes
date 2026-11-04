# xArm 850 — Five-point wall calibration development

**Recovered 2026-11-04** from the original `Even more robot apps` folder, whose final 33 files were omitted by the first 100-file browser upload. All Python, settings and SVG files in this folder are **verbatim copies** from the re-upload.

## Files

- `xarm_850_combined_controller_drawer_v4_5point_calibration.py`: introduces a **five-point calibrated reachable surface**. The top-right corner is clipped because parts of the A3 sheet were beyond the xArm's useful reach. The source triangulates the taught points to reproduce each calibration point.
- `xarm_850_combined_controller_drawer_v6_offset_corrected.py`: corrects the distinction between **marker-offset-neutral paper X positions** and the separate `CONTACT_X_OFFSET_MM`, avoiding applying the marker offset twice. Its historical default offset is **−19.17 mm**.
- `xarm_850_combined_controller_drawer_v7_safer_upper_right.py`: changes the upper-right reachable-area calibration after tests encountered robot limits. The source retains **error poses for reference only** and does not treat them as usable calibration points.
- `xarm_combined_settings.json`: matching historical application settings. The programs locate this filename beside the script.
- `test-drawings/`: three small SVG test paths probing the five-point upper-right reach boundary.

These intermediate apps evolved from the [eight-point combined v3](../v3-package/) and precede the [full marker-handling app](../full-marker-app/).

**Important:** the author reports that marker contact was very sensitive (approximately 0.1 mm mattered). Incorrect X offsets could leave the pen in the air or crush it against the wall. The five-point mapping does **not** provide automatic contact-force sensing. No source file or calibration value was changed or physically tested during this GitHub recovery.
