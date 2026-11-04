# UFACTORY xArm 850 (UF850)

| Project | Purpose |
| --- | --- |
| [text-writing](text-writing/) | Wall lettering/writing core and Tkinter app iterations |
| [svg-and-text-drawing](svg-and-text-drawing/) | Wall SVG / drawing GUI with example SVG and reference images |
| [freehand-drawing](freehand-drawing/) | Mouse-drawn strokes, settings, standalone variations and example JSON drawings |
| [combined-controller-and-drawer](combined-controller-and-drawer/) | Integrated gamepad control, lettering, SVG and freehand drawing |
| [controller-tests](controller-tests/) | Early controller/joint and pose-reading scripts |
| [motion-tests](motion-tests/) | Connection and jog experiments |
| [mister-bean-demo](mister-bean-demo/) | Standalone preprogrammed Mister Bean presentation demo |
| [shared-drawing-website](shared-drawing-website/) | LAN drawing website: server, launch scripts, HTML/CSS/JS and saved JSON drawings (recovered from desktop) |

These names refer to the same physical robot family. The script filenames use both `xarm` and `uf850`.

## Physical wall-writing setup and calibration history

**Physical paper:** **A3** sheet mounted vertically on the wall; the drawings use Y across the sheet, Z vertically, and X to approach/lift the marker. Each saved program's numeric width/height describes a **reachable drawing region**, not necessarily all of A3.

**Contact X is safety-critical.** The author reports that even **0.1 mm** in wall/marker calibration mattered. When a marker was removed and reinserted, its projection from the gripper could change, so an **X contact offset** had to be manually re-adjusted: an overly shallow X would leave no mark, while too much negative X could **crush the marker against the wall**. The software does not automatically regulate marker pressure; manual checks remain necessary.

The historical calibration progression is **fixed wall X → four measured corners (text writer and first SVG) → eight measured edge points (later SVG, freehand and combined v3) → five reachable points with a clipped upper-right inaccessible region (later combined project)**. The last five-point setup was designed because the robot could **not reach the physical A3 top-right corner** safely. The apparent reduction from eight points to five is a **different reachable-region model**, not a regression in the number of measurements.

A later **3D-printed marker rack with a physical alignment/stop wall** made marker position consistent during pickup and return. The author reports the rack-based arrangement was repeatable enough that **no further X-offset recalibration was necessary after the latest updates**. Earlier marker pickup/return sequences were individually tested, but this is not proof of a complete final integrated program run.

**Archival gap:** The five-point calibration was also carried into the later full app named **`xarm_850_full_app_normal_marker_speed.py`**, according to the author's correction and prior development history; an earlier version was named `xarm_850_combined_controller_drawer_v4_5point_calibration.py`. Neither of those precise source files appears in the current `RobotCodes` main branch or its original-layout backups, so their final implementation still needs to be archived and checked. The [SVG and Text Drawing README](svg-and-text-drawing/) documents the checked-in four- and eight-point implementations and explains this later work. Preserve the original calibrated constants in each historical file.

