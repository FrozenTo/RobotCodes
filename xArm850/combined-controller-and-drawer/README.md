# xArm integrated controller + wall drawer

- `xarm_850_combined_controller_drawer.py` and `_v2.py`: earlier integrated apps.
- `xarm_combined_settings.json`: preserved from the same folder as those earlier versions.
- `v3-package/`: v3 GUI plus its launcher, requirements and README; copied as a unit.
- `alternate-upload-copies/`: identical extra upload of the v3 Python source.

**Important:** The v3 source uses a `xarm_combined_settings.json` filename at runtime, but this settings file was *not* present inside the original v3 distribution folder. The older JSON has not been silently substituted because calibration settings may differ.

## Controller movement history — verified tuning and residual high-speed pause

The combined app's joystick controller grew out of the standalone [xArm controller experiments](../controller-tests/). In those early experiments, the author observed **severe straight-axis jitter/jumping while diagonal movement looked smooth**. In the project chat on **2026-10-13**, the team changed **velocity timeout 0.15→0.50 s**, **deadzone 0.10→0.15**, configured **TCP maximum acceleration 400 mm/s²**, and introduced **velocity smoothing 0.25**. The author then reported movement was **“very smooth and nice.”** The original jittery *pre-fix* script is not separately identified in the archive; the changes were made together, so no single setting can be identified as the sole cause.

The checked-in **v3 combined app** retains the tuned **0.15 deadzone**, **80 mm/s maximum TCP speed**, **400 mm/s² TCP acceleration**, **0.5 s velocity timeout**, and **0.25 smoothing** as initial controller constants. The actual values at runtime may be modified by the GUI's settings persistence.

**Author observation about a later/current combined controller version:** Normal-speed XYZ movement is very smooth. At **higher speeds**, there can be a **small momentary pause associated with J4 repositioning** before the requested direction continues. The pause is barely noticeable and is **not the severe jitter from the original controller**. Whether this is caused by wrist reconfiguration, an IK solution transition, the robot's internal motion planner or another mechanism **has not been established from code or diagnostics**. This account does not prove the exact saved v3 package was the particular build used for that observation.

The full history and controller button map are documented in [xArm controller-tests README](../controller-tests/).

## A3 marker contact, rack, and later five-point geometry

The **v3 combined app in this folder** still uses the **eight-point interpolated paper surface** derived from the xArm SVG/freehand experiments, with a user-adjustable **X contact offset**. This reflects an **A3 sheet on a wall**, but its saved `PAPER_WIDTH_MM=359.6` and `PAPER_HEIGHT_MM=235.0` define a **reachable calibrated drawing region**, not the full A3 page. The author reports that contact was extremely sensitive: changing marker grip position could require roughly **0.1 mm adjustments**. An offset set too far from the wall could prevent drawing; too deep into the wall could **crush the marker**. The checked-in v3 package does **not** automatically measure or regulate force.

**Later development, not present in this GitHub folder:** an earlier file named `xarm_850_combined_controller_drawer_v4_5point_calibration.py` developed a **five-point model for the usable A3 area**, with a clipped **unreachable upper-right region**. The author identifies a later full-app script **`xarm_850_full_app_normal_marker_speed.py`** as also containing that five-point calibration. References to the development history support those names, but neither source file is currently available in `RobotCodes` for line-by-line verification. This differs from the v3 eight-point surface in both point layout and reachable region. Do not describe the saved v3 code as five-point.

A later **3D-printed marker pickup rack** included a physical backstop/alignment wall to make marker projection repeatable when the robot picked up or returned a marker. The author reports that separate pickup/return tests worked, and that after settling on the rack-based arrangement **no further manual X recalibration was needed**. That does **not** eliminate the underlying possibility of damage if the offset is entered incorrectly; the latest setup simply became more repeatable. It also does not prove the full unarchived integrated app's automated pickup/return buttons were physically validated end-to-end.

**Archive boundary:** none of the checked-in combined v1/v2/v3 programs contain the complete later five-point calibration and marker-rack workflow. Its real code and calibration settings must be archived as a distinct version when available. See [xArm SVG drawing README](../svg-and-text-drawing/) for the earlier four-/eight-point history.

## Settings verification (2026-11-03)
The v3 source explicitly defines `SETTINGS_FILE = "xarm_combined_settings.json"`, locates it using `Path(__file__).resolve().with_name(...)`, and ignores a missing file (using built-in defaults). Saving settings writes the combined JSON beside the v3 Python file.

It includes freehand-editor settings in this **combined** JSON with keys such as `freehand_width`, `freehand_safe_x`, `freehand_draw_speed`, and `freehand_path_step`. In contrast, the standalone freehand v2.2 uses **`xarm850_freehand_settings.json`** with keys like `width_mm`, `safe_x_mm`, and `path_step_mm`. The two files should not be interchanged, though v3 incorporates v2.2-style freehand drawing behavior.
