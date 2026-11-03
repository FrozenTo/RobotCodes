# Dobot MG400

| Project | Purpose |
| --- | --- |
| [pen-writing](pen-writing/) | 9-point stroke-based letter writer; Tkinter GUI, core and saved JSON state |
| [image-and-svg-drawing](image-and-svg-drawing/) | Image/vector drawing prototypes, IK-safe area iterations and SVG drawer |
| [pen-calibration](pen-calibration/) | Pen-tip orientation and R-axis/radius calibration experiments |
| [controller](controller/) | Keyboard + Xbox controller applications, joint tests and Dobot API driver |
| [slider-control](slider-control/) | Tkinter XYZ slider movement app and local Dobot API driver |

The drawing and calibration folders include identical copies of the text writer core as a local import dependency. All hardware movements should be reviewed against current workspace geometry.
