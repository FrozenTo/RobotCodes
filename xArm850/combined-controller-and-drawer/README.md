# xArm integrated controller + wall drawer

- `xarm_850_combined_controller_drawer.py` and `_v2.py`: earlier integrated apps.
- `xarm_combined_settings.json`: preserved from the same folder as those earlier versions.
- `v3-package/`: v3 GUI plus its launcher, requirements and README; copied as a unit.
- `alternate-upload-copies/`: identical extra upload of the v3 Python source.

**Important:** The v3 source uses a `xarm_combined_settings.json` filename at runtime, but this settings file was *not* present inside the original v3 distribution folder. The older JSON has not been silently substituted because calibration settings may differ.

## Settings verification (2026-11-03)
The v3 source explicitly defines `SETTINGS_FILE = "xarm_combined_settings.json"`, locates it using `Path(__file__).resolve().with_name(...)`, and ignores a missing file (using built-in defaults). Saving settings writes the combined JSON beside the v3 Python file.

It includes freehand-editor settings in this **combined** JSON with keys such as `freehand_width`, `freehand_safe_x`, `freehand_draw_speed`, and `freehand_path_step`. In contrast, the standalone freehand v2.2 uses **`xarm850_freehand_settings.json`** with keys like `width_mm`, `safe_x_mm`, and `path_step_mm`. The two files should not be interchanged, though v3 incorporates v2.2-style freehand drawing behavior.
