# MG400 Slider Control — early movement experiment

**Robot:** Dobot MG400  
**Interface:** Tkinter desktop application, Python  
**Project status:** **Early prototype; the intended real-time slider-following behavior was not achieved.** The author remembers this as one of the first movement-control projects and a partially unsuccessful attempt to reproduce the immediate slider-based movement they saw in a teacher's web app. The exact physical results of individual manual moves were not recorded.  
**Reviewed:** 2026-11-04

## Original intention versus implemented behavior

The author wanted to drag a slider and see the robot **immediately follow the updated value**, without pressing a separate button. This was an experiment in direct manual control, preceding or overlapping other early MG400 movement work. The exact chronological order relative to other prototypes is not independently established.

**The source does not implement live slider following.** The sliders created with `tk.Scale(...)` have **no `command` callback**, and the program does not poll them and issue movement automatically. The sliders only select a target; movement starts after clicking a button.

| Interface | Behavior in `main.py` |
| --- | --- |
| X, Y, Z and R sliders | Enter a target Cartesian pose, with 1 mm / 1° steps |
| `Move Linear MovL` | Calls `SpeedL(speed)`, then `MovL(x, y, z, r)` once |
| `Move Joint MovJ` | Calls `SpeedJ(speed)`, then `MovJ(x, y, z, r)` once (Cartesian target, joint-style path) |
| J1–J4 angle sliders | Enter target joint angles |
| `Move Joint Angles` | Calls `SpeedJ(speed)`, then `JointMovJ(j1, j2, j3, j4)` once |
| `Read Current Pose` | Reads `GetPose()` and sets the Cartesian slider positions |
| `Read Current Joints` | Reads `GetAngle()` and sets the joint slider positions |
| Connect, Enable, Disable, Clear Error | Use the Dobot dashboard / motion TCP ports |
| `STOP` | Calls the dashboard `ResetRobot()`; **not a guaranteed hardware emergency-stop mechanism** |

There is **no separate live mode**, joystick input, motion queue or saved-pose/preset system. The GUI launches with example slider values, **not a guarantee that the sliders match the robot's actual current pose**.

## Files and dependencies

| File | Role |
| --- | --- |
| `main.py` | The complete Tkinter GUI and button-triggered robot commands |
| `dobot_api.py` | Local copy of the Dobot Ethernet SDK wrapper; also used in [MG400 Controller](../controller/) |
| `archive-compiled/` | Preserved Python bytecode cache, not needed to run |

For a local Windows Python setup, the code imports **Tkinter** (normally included in standard Python builds) and the local `dobot_api.py` module, which imports **NumPy**. No Flask server is required: this is a **desktop program**, despite its inspiration from a web app.

Typical historical launch from this folder: `python main.py`. This is documentation of the archived script, **not a recommendation to connect it to a live robot without reviewing the motion limits first**.

## Saved historical control assumptions

- Default IP: `192.168.2.6`, with dashboard port `29999` and motion port `30003`. The IP reflects one MG400 Ethernet port/network configuration; later projects sometimes used `192.168.1.6`.
- Cartesian slider ranges: X **100..350 mm**, Y **−250..250 mm**, Z **−80..250 mm**, R **−360..360°**.
- Joint ranges: J1/J2/J3 **−180..180°**, J4 **−360..360°**.
- Speed slider: **1..50%**, default **10%**.
- Initial slider entries include X=280, Y=0, Z=100, R=0. The app does **not** obtain the actual pose automatically at startup.

These are **GUI slider bounds, not verified safe reachable limits**. The wide joint ranges especially must not be interpreted as the MG400's actual allowed joint angles.

## Review findings and limitations

1. **Missing core feature:** continuous slide-to-move behavior was never wired. A rewrite would need throttling, latest-target coalescing, motion-completion handling and careful stop/limit behavior to avoid filling a robot's command queue.
2. **Direct moves from displayed target values:** pressing a move button sends the chosen absolute pose or joint angles without intermediate travel/obstacle waypoints and without prechecking reach.
3. **UI may block:** dashboard and motion calls run directly from Tkinter button callbacks, so slow TCP calls can freeze the window. This is a source-based risk, **not** an author-confirmed incident for this particular app.
4. **Loose feedback checking:** a normal Python call return is reported as a success-colored status even if a robot controller may have returned an error code; there is no separate completion verification using `GetPose()` after a move.
5. **Stop design:** `ResetRobot()` is sent from the red STOP button. Treat it as a historical software command, **not a substitute for an accessible physical emergency stop**.
6. **No save/restore:** the program has no settings persistence or calibration profiles.

## Historical conclusion

This is a **useful early prototype**, but it **did not deliver the author's original live-drag control goal**. It showed one way to connect a Tkinter GUI to MG400 position and joint motion APIs; later keyboard/Xbox controller projects pursued more responsive input mechanisms.

**Recommended catalog label:** *Early/experimental — slider-based target entry, not real-time tracking; desired feature unimplemented*. Preserve the code as a learning-stage snapshot. **No code, motion bounds, or calibration values were modified in this review.**
