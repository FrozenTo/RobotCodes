# xArm 850 freehand drawing

Draw paths in a Tkinter canvas and save/load `xarm850-freehand-v1` JSON stroke files.

- Main directory: un-packaged freehand Python iterations, with their `xarm850_freehand_settings.json` beside the scripts that load it.
- `v2.2-package/`: self-contained historical distribution with its **own different** `xarm850_freehand_settings.json`, README and launcher.
- `safe-ready-package/`: another historical distribution with README and launcher. No settings JSON accompanied it in the original upload; the code uses a same-folder settings filename.
- `example-drawings/`: `my_xarm_drawing.json` and `mister_bean_color_compatible.json`. These are **drawing data**, not robot calibration settings. Load them through the app's drawing-file picker.

The two saved settings JSONs contain different robot movement/calibration choices. They were not merged or overwritten.

## Wall calibration and marker position

These freehand variants descend from the **eight measured edge-point** wall calibration used for A3 paper. The measured drawing rectangle describes the **reachable area**, not the full physical A3 page. The code includes editable X contact offsets because each marker's tip position could change when removed/reinserted into the gripper.

The author reports that an error of **around 0.1 mm could noticeably affect contact**: too far from the paper means no mark; too much inward X can press and **crush a marker against the wall**. The software has no automatic contact-force sensing.

The **later five-point calibration** for an unreachable upper-right paper region, and a **3D-printed marker pickup rack with a physical alignment stop**, belong to newer combined xArm work; **these archived standalone freehand versions still use the eight-point model**. The author says the later rack made insertion repeatable enough that no further X-offset recalibration was necessary. Do not rewrite earlier JSON calibration values to make them match the later setup.

See [SVG and Text Drawing](../svg-and-text-drawing/) and [Combined Controller and Drawer](../combined-controller-and-drawer/) for this progression.
