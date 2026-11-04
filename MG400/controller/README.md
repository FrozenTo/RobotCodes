# MG400 Keyboard and Xbox Controller — project review

**Robot:** Dobot MG400  
**Project:** Live keyboard and Xbox-style gamepad jogging over TCP/IP  
**Status:** Development history and source implementation reviewed; `FinalControllerAPP.py` is the most developed desktop application in this directory, but its exact last physical test state is not independently verified in this repository.  
**Reviewed:** 2026-11-04

## Goal and history

The goal was to move the MG400 manually from a PC using **held keyboard keys** and, later, an **Xbox-style controller**, without repeatedly operating DobotStudio. The project evolved through short experiments, controller button/axis discovery, motion improvements, joint selection, tool-output toggles, and finally a Windows-oriented **PySide6 + pygame** desktop GUI.

This code belongs to the later MG400 work discussed in the project chat **“MG400 Keyboard Control App”**. It does **not** implement the text-writing or SVG drawing pipelines themselves, though it controls the same hardware family. The original directory included many exploratory test scripts; they are retained here for history.

**Networking:** The `192.168.2.6` and `192.168.1.6` addresses seen across files reflect the MG400 Ethernet port and LAN setup, **not different robot protocols**. The author also encountered a second port changed to `192.168.3.6`. Verify the port and live IP of the robot in use. The final GUI's IP is editable and locally saved.

## File-by-file progression

| File | Main role | Historical notes |
| --- | --- | --- |
| `TestMG400KeyboardMov.py` | Smallest Ethernet/API motion test | Despite the filename, it contains **no keyboard listener**: connects and immediately sends `MoveJog("X+")`. **Do not run casually:** there is no matching stop/disable/close in the file. |
| `Next1.py` | First keyboard-controlled `MoveJog` | Uses `pynput` arrow keys for X/Y, Shift/Ctrl for Z, Space to stop, Esc to disable/exit. |
| `multipleinputs.py` | Held-key and multi-axis movement experiment | Tracks pressed keys in a thread and sends repeated small **`RelMovL`** steps every 0.08 seconds (including diagonal combinations), rather than continuous `MoveJog`. Queued relative moves may continue briefly after keys are released. |
| `KeyboardApp` | Keyboard-only desktop GUI, **without .py extension** | PySide6 interface with IP, speed, connect/disable, stop, two tool outputs, current movement status; `pynput` handles keys. The most recently pressed direction has priority. Run it with `python KeyboardApp` from this folder. |
| `kontroller input test.py` | Controller hardware discovery | Prints pygame joystick axis and button changes to determine the actual Xbox controller mapping. Does not control the robot. |
| `KontrollerMove1basic.py` | First direct Xbox jogging prototype | Right stick X/Y, left-stick vertical Z; A stop, B disable/exit; L2/R2 tool toggles. Fixed `SpeedFactor(20)`, deadzone 0.25. |
| `Kontroller2advanced.py` | Controller speed based on stick deflection | Adds discrete speed bands (10/20/35/50/70%) selected by magnitude. Still mainly XYZ movement. |
| `Kontroller3FinalJoints.py` | Introduces **XYZ / JOINT** modes | R1 switches modes; L1 cycles J1→J2→J3→J4; maps the right stick differently for each selected joint. Console prototype, not the final GUI. |
| `ControllerAPP.py` | First integrated **PySide6 + pygame** controller GUI | Adds IP and speed controls, movement/mode status, tool outputs, stop/disable, and asynchronous **Go to Initial Position**. Source default IP `192.168.1.6`. |
| `FinalControllerAPP.py` | Most developed combined controller GUI | Adds persistent `QSettings`, Xbox connect/disconnect detection and rediscovery, improved stop/recenter latching, polished GUI/status, separate initial-move speed. Source default IP `192.168.2.6`. |
| `dobot_api.py` | Shared Dobot Python Ethernet API wrapper | Required alongside the controller and GUI programs. Imported classes include `DobotApiDashboard` (29999) and `DobotApiMove` (30003). |

The above is a **functional progression reconstructed from source and filenames**, not a precise verified creation timeline. The two main GUI files are **separate gamepad applications**. The keyboard-only GUI is `KeyboardApp`, not a hidden keyboard-control mode in `FinalControllerAPP.py`.

## Final controller GUI: key mapping

The actual movement logic in `FinalControllerAPP.py` is:

| Input | XYZ mode | Joint mode / other |
| --- | --- | --- |
| Right stick up / down | X− / X+ | Selected J2/J3: J2−/J2+ or J3−/J3+ |
| Right stick left / right | Y− / Y+ | Selected J1/J4: J1−/J1+ or J4−/J4+ |
| Left stick up / down | Z+ / Z− | Not used for joint selection movement |
| **R1** | Switch between XYZ and JOINT | Same |
| **L1** | No joint selection effect in XYZ | Cycle selected joint J1→J2→J3→J4→J1 |
| **L2** trigger | Toggle Tool 1, digital output `DO(1)` | Same |
| **R2** trigger | Toggle Tool 2, digital output `DO(2)` | Same |
| **A** | Software STOP | Same |
| **B** | Disable robot and close application | Same |

The program defines numeric constants for X/Y and L3/R3 controller buttons but **does not assign actions to them** in the final poll loop. Do not confuse this MG400 mapping with later xArm marker-pickup button plans.

Controller axis indices are specific to the tested controller/driver mapping: right X=2, right Y=3, left Y=1, L2=4, R2=5. Hardware differences can require rerunning `kontroller input test.py`.

**Single-axis jog:** the program chooses the **strongest active stick axis** for `MoveJog`, so simultaneous diagonals are not continuously jogged on two axes at once. Joint mode likewise operates the **one selected joint** at a time.

## Motion and speed improvements

- The early console controller used a **25% stick deadzone**. Both combined GUIs use **10%** by default.
- The advanced prototypes introduced stick-strength speed bands. The final app computes one of **10%, 20%, 35%, 50%, or the configured maximum** (default max 70%) according to stick deflection, and calls `SpeedFactor`. This is **stepped speed control**, not a continuous analog robot velocity command.
- `stop_jog()` sends `MoveJog()` only when the app believes a direction is active, instead of constantly spamming stop commands during idle polling.
- Switching direction first stops the previous jog; switching modes or joints also stops and **requires sticks to recenter** before movement can resume.
- The final GUI polls pygame at about **100 Hz** (10 ms Qt timer), monitors controller disconnection, stops its current jog on disconnect, and can discover a reconnected controller. It also applies a recenter latch after reconnection.
- `Go to Initial Position` performs `MovJ(350, 0, 0, 0)` in a background thread and waits using `Sync()` so the main GUI does not block throughout the movement. The GUI has a separate initial-position speed setting (default 30%).
- Initial connect/re-enable uses `ClearError()`, a **1-second delay**, then `EnableRobot()`; this reflects prior trouble enabling the robot too quickly after an error/stop.

The hard-coded initial position is a **robot-specific historical target**, not an automatically safe universal pose. The app does not require the robot to *already* be at that exact pose, but it also does not create intermediate obstacle-clearance waypoints on its way there.

## What settings and data files are involved?

`FinalControllerAPP.py` uses Qt `QSettings("UT RoboLab", "MG400 Controller")`, not a nearby JSON file. It persists **robot IP, stick deadzone, maximum jogging speed, and initial-position speed** in operating-system-managed Qt settings on the host PC. This is why no matching `controller_settings.json` appears in the repository.

`dobot_api.py` imports `numpy` and also references `files/alarm_controller.json` and `files/alarm_servo.json` inside an alarm-decoding helper. **Those two alarm lookup files are absent from this folder**. Ordinary dashboard/motion APIs do not necessarily need the alarm decoding helper, so absence does not prove the controller GUI is broken. The API wrapper also imports Tkinter.

For typical Windows use:

- **Gamepad GUI:** install `PySide6`, `pygame`, and `numpy`; run `python FinalControllerAPP.py`.
- **Keyboard GUI:** install `PySide6`, `pynput`, and `numpy`; run `python KeyboardApp`.
- Keep `dobot_api.py` beside these scripts. Use a reachable MG400 on the correct Ethernet port with an accessible emergency-stop device.

These are dependency observations from the imports, not a tested installation procedure on this machine.

## Source-review warnings, not claims of observed accidents

1. **Software STOP is not a hardware emergency stop.** A normally active jog is stopped with `MoveJog()`; during the automatic Initial Position `MovJ`, A/STOP instead calls `DisableRobot()`. Real physical emergency stopping still requires appropriate hardware safety provisions and supervision.
2. `TestMG400KeyboardMov.py` starts jogging immediately and has no release/cleanup logic; keep it strictly as an historical minimal experiment.
3. The queued-`RelMovL` approach in `multipleinputs.py` may leave delayed movements after release, unlike one-axis held `MoveJog`.
4. The initial-position `MovJ` is direct. A target within robot limits can still be unsafe with fixtures, pen holder or obstacles in the workspace.
5. The automatic initial-position worker logs exceptions and always emits `initial_move_finished`; if the worker fails while the software's `enabled` flag remains True, the GUI can still display **“Initial Position reached”**. That status is not an independent verified position readback.
6. The user-selectable IP, speed and joystick controls are important; the stored Qt settings may differ from source defaults. A wrong IP could simply reflect plugging into a different robot Ethernet port.
7. Tool outputs `DO(1)` / `DO(2)` were used for external gripper/tool functions in these prototypes. Check what is actually wired before toggling.
8. These scripts issue **live robot commands**. No simulated/live toggle is required for new applications simply because old experiments offered dry-run modes.

## Recommended status and future review

**Primary application candidate:** `FinalControllerAPP.py` plus `dobot_api.py`. It is the most complete controller GUI in this repository by inspected functionality. The console prototypes, the earlier `ControllerAPP.py`, and the keyboard-only `KeyboardApp` serve distinct development-history roles.

**Actual latest tested version:** to be confirmed against the author's memory. We know the development included actual MG400/gamepad testing, but the checked-in scripts alone do not prove that this exact file was the last build used.

**Next possible improvements (not applied):** more robust controller-command result validation, verified initial-pose feedback, a clearance-aware move-to-initial route, and a clear separation of software Stop from physical E-Stop instructions.

**No Python scripts, robot IPs, speed constants, safety behaviors or external-tool settings were changed in this documentation review.**
