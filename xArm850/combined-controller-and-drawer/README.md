# xArm integrated controller + wall drawer

- `xarm_850_combined_controller_drawer.py` and `_v2.py`: earlier integrated apps.
- `xarm_combined_settings.json`: preserved from the same folder as those earlier versions.
- `v3-package/`: v3 GUI plus its launcher, requirements and README; copied as a unit.
- `alternate-upload-copies/`: identical extra upload of the v3 Python source.

**Important:** The v3 source uses a `xarm_combined_settings.json` filename at runtime, but this settings file was *not* present inside the original v3 distribution folder. The older JSON has not been silently substituted because calibration settings may differ.
