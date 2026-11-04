# Dobot MG400 — Projects and Development History

This folder collects the MG400 Python projects created and tested while learning to control a **Dobot MG400** over Ethernet. It includes successful applications, the experiments that led to them, and one separate course/lesson website project.

**Review status as of 2026-11-04:** Four projects have detailed code/history reviews; **Slider Control is not yet reviewed**. The **Grid Pick-and-Place Website** is a separate lesson project intentionally excluded from the current personal-project review.

## Project index

| Project | What it does | Historical status |
| --- | --- | --- |
| [Pen Writing](pen-writing/) | Nine-point letter-grid writer with Tkinter GUI, configurable text/rows, Estonian characters and saved position presets | **Reviewed — author-confirmed working** |
| [Pen Calibration](pen-calibration/) | Experiments with a flexible 3D-printed off-axis pen holder, R-axis arc, reachable drawing area, and pen-tip compensation | **Reviewed — used experiments; imperfect drawing alignment accepted** |
| [Image and SVG Drawing](image-and-svg-drawing/) | Progression from manually coded Narva College drawing paths to an Inkscape SVG importer with IK-aware R-angle planning | **Reviewed — manually traced SVG confirmed working very well** |
| [Keyboard and Xbox Controller](controller/) | Keyboard jogging, gamepad input tests, speed control, selectable joint jogging, tool outputs and a PySide6 controller app | **Reviewed — working; `FinalControllerAPP.py` probably last used version** |
| [Slider Control](slider-control/) | Tkinter XYZ slider control with a local Dobot Ethernet API module | **Pending detailed project review** |
| [Grid Pick-and-Place Website](grid-pick-and-place-website/) | Web interface, cameras and grid-based component handling for an AtomS3R assembly exercise | **Separate lesson project — excluded from this review for now** |

Each project has its own README. For exact locations of files moved from the original uploads, see the repository root [file map](../FILE_MAP.md) and [desktop upload map](../DESKTOP_UPLOAD_MAP.md).

## How the main projects developed

### 1. Pen Writing — successful starting point

The first major MG400 project used a **3×3 numbered point grid** to write letters with a pen. It grew into a desktop interface supporting more characters, multiple lines, position presets and saved settings. The author confirms the writer **worked on the physical robot**. The GUI could become unresponsive while robot commands were running, and other source-review limitations remain documented in the [Pen Writing README](pen-writing/).

### 2. Pen Calibration — experiment with an off-axis tool

For a lesson project, the author designed and 3D-printed a pen holder with a thin flexible arm and a circular grip. Because the pen sat roughly **55.5–56 mm away** from the flange rotation axis, turning the MG400's **R axis** swept its tip around a circle.

This was explored **for fun** and to make better use of a paper sheet that the MG400 could not otherwise cover well. Usable R-angle ranges shifted as the head moved left or right, and pen/robot interference could occur **on both sides**. Under contact pressure the flexible arm bent, pushing the tip slightly **outside the nominal radius**, so compensation was never completely accurate.

**Important:** The R-radius manipulations and these calibration tests were specifically for **drawing**, not for improving the successful text-writing app. Minor offsets and curvature in drawings were accepted. Details and v1/v2 differences are in [Pen Calibration](pen-calibration/).

### 3. Image → SVG Drawing — abandoning inaccurate hard-coded vectors

The first attempts to reconstruct a detailed **Narva College PNG** as hand-coded vectors using GPT did **not** produce acceptable drawings. The source includes several iterations on paper limits, R-zone selection, inverse-kinematics checks and continuous strokes, but the early generated building paths were not usable.

The author then **traced the actual building lines manually in Inkscape**, making [`drawing.svg`](image-and-svg-drawing/drawing.svg). The SVG was successfully drawn by the MG400; the author recalls that it **worked very well**.

The identical artwork was later used for the **[xArm 850 / UF850 SVG drawing project](../xArm850/svg-and-text-drawing/)**, with the robot-specific coordinate mapping adapted for drawing on a vertical surface. See [Image and SVG Drawing](image-and-svg-drawing/) for the six-script progression.

### 4. Keyboard and Xbox Controller — working, but the next robot was needed

The control project progressed from basic keyboard movement to Xbox stick, button and trigger tests; stepped speed based on stick deflection; selectable J1–J4 jogging; tool outputs; and a larger **PySide6 gamepad GUI**. The author recalls **`FinalControllerAPP.py` was probably the last working MG400 version**.

The reason for moving on to xArm 850 was **not that this MG400 application failed**. The real-time `MoveJog` approach allowed effectively **one active jogging axis at a time**, so it could not provide the smooth simultaneous multi-axis movement the author wanted from a controller. That is a limitation of the tested manual-jog workflow, **not** a claim that MG400 cannot execute coordinated programmed multi-axis trajectories.

The next goal was therefore **more fluid simultaneous joystick control on xArm 850**. See [Keyboard and Xbox Controller](controller/) and the [xArm controller prototypes](../xArm850/controller-tests/).

## Separate or pending work

**[Slider Control](slider-control/)** has its own source and short README but has **not yet received the same detailed comparison and usage-history review**. We should review it before declaring the full MG400 folder complete.

**[Grid Pick-and-Place Website](grid-pick-and-place-website/)** is an independent **lesson/course project**, using a web UI, grid locations, cameras and heights for component assembly. It is preserved in GitHub but excluded from the main MG400 personal-project history for now.

## Network, files and usage notes

- MG400 Ethernet projects commonly connect to the **dashboard port 29999** and **motion port 30003**.
- Historical IP differences are largely **Ethernet port/network configuration**: `192.168.2.6` was used on one port, later `192.168.1.6` was more convenient when working with other robots, and the second Ethernet port was later found changed to `192.168.3.6`. An IP change is **not** automatically a software version change.
- Projects may share `MG400Writer` or `dobot_api.py`, but the local copies are intentionally retained to keep historical scripts together. Project settings and named drawing files should remain beside their related code.
- Older **`LIVE_ROBOT = True`** settings are useful evidence that the author used a program on physical hardware. They do not alone verify the exact test result of every historical file.
- **All source positions, robot limits, pen offsets and speed values reflect historical physical setups.** No current physical movement test was performed during this GitHub review. Review reach, tool clearance, safe heights and available emergency-stop controls before running archived code.

## Documentation policy

Detailed project README files distinguish **author-confirmed working results**, **source-based inferences** and **unverified historical tests**. Older working versions, experimental alternatives, and duplicate uploads have been retained; no control code or calibration JSON has been rewritten just to simplify the archive.
