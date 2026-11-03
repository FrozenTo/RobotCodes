# xArm 850 freehand drawing

Draw paths in a Tkinter canvas and save/load `xarm850-freehand-v1` JSON stroke files.

- Main directory: un-packaged freehand Python iterations, with their `xarm850_freehand_settings.json` beside the scripts that load it.
- `v2.2-package/`: self-contained historical distribution with its **own different** `xarm850_freehand_settings.json`, README and launcher.
- `safe-ready-package/`: another historical distribution with README and launcher. No settings JSON accompanied it in the original upload; the code uses a same-folder settings filename.
- `example-drawings/`: `my_xarm_drawing.json` and `mister_bean_color_compatible.json`. These are **drawing data**, not robot calibration settings. Load them through the app's drawing-file picker.

The two saved settings JSONs contain different robot movement/calibration choices. They were not merged or overwritten.
