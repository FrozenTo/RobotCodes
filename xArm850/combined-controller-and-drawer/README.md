# xArm integrated controller + wall drawer

**Upload recovery 2026-11-04:** The original upload had accidentally omitted later versions. This folder now also contains [five-point calibration versions v4/v6/v7](five-point-development/), three SVG reach tests, the [four full marker-changing app variants and their original settings JSON](full-marker-app/), and a slightly different early combined source under `alternate-upload-copies/recovered-2026-11-04/`. The original raw 74-file folder is retained separately. [Full SHA-verified recovery map](../../RECOVERED_UPLOAD_MAP_2026-11-04.md). **The v3 package below is no longer the newest recovered code**, and these later applications should be reviewed individually before claiming the final hardware status.


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

## Settings verification (2026-11-03)
The v3 source explicitly defines `SETTINGS_FILE = "xarm_combined_settings.json"`, locates it using `Path(__file__).resolve().with_name(...)`, and ignores a missing file (using built-in defaults). Saving settings writes the combined JSON beside the v3 Python file.

It includes freehand-editor settings in this **combined** JSON with keys such as `freehand_width`, `freehand_safe_x`, `freehand_draw_speed`, and `freehand_path_step`. In contrast, the standalone freehand v2.2 uses **`xarm850_freehand_settings.json`** with keys like `width_mm`, `safe_x_mm`, and `path_step_mm`. The two files should not be interchanged, though v3 incorporates v2.2-style freehand drawing behavior.
