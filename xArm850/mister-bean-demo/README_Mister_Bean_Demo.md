# xArm 850 — Mister Bean Standalone Demo

This demo runs a complete automatic marker-writing sequence on the **UFactory xArm 850**.

The Mister Bean drawing is embedded directly inside:

`xarm_850_mister_bean_standalone_demo.py`

No separate JSON or SVG drawing file is required.

---

## What the demo does

The robot performs the following sequence automatically:

1. Moves to **Initial Position**.
2. Moves above the marker holder.
3. Opens the G2 gripper.
4. Moves down to the marker.
5. Grips the marker.
6. Lifts back above the marker holder.
7. Moves up to the safe transfer height.
8. Moves to the marker-compatible **Draw Ready** position.
9. Moves to the user handoff position.
10. Waits for the operator to remove the marker cap.
11. Returns to Draw Ready.
12. Draws the embedded Mister Bean drawing.
13. Returns to Draw Ready after drawing.
14. Moves to the user handoff position again.
15. Waits for the operator to put the marker cap back on.
16. Returns to Draw Ready.
17. Moves back through the safe marker-transfer route.
18. Moves above the marker holder.
19. Places the marker back into the holder.
20. Opens the gripper and releases the marker.
21. Lifts clear of the marker holder.
22. Moves back to the safe transfer height.
23. Returns to **Initial Position**.

The only manual interaction during a normal demo is:

- remove the marker cap when asked;
- put the marker cap back on when asked.

---

## Before running the demo

Make sure all of the following are true:

- The xArm 850 is powered on.
- The robot is reachable at:

  `192.168.1.208`

- The G2 gripper is installed.
- The marker is already sitting correctly in the marker holder.
- The marker has its cap on at the beginning of the demo.
- The calibrated drawing surface is in its normal position.
- The area around the robot is clear.
- Nothing blocks the path between:
  - Initial Position,
  - marker holder,
  - Draw Ready,
  - user handoff position,
  - drawing surface.

Pay particular attention to monitors or other equipment near the robot.

Keep the physical emergency stop accessible during testing and demonstrations.

---

## Required software

### Python

Install regular Python 3.

The current demo has been used with Python 3.12.

When installing Python on Windows, enable:

`Add Python to PATH`

---

## Python dependency

Install the UFactory xArm Python SDK:

```bash
pip install xarm-python-sdk
```

The demo uses Python's built-in `tkinter` library for the interface.

On normal Windows Python installations, Tkinter is already included.

No Pygame, SVG library, or additional drawing-file dependency is required for this standalone demo.

---

## Running the demo

Open Command Prompt, PowerShell, or the VS Code terminal in the folder containing:

`xarm_850_mister_bean_standalone_demo.py`

Run:

```bash
python xarm_850_mister_bean_standalone_demo.py
```

On some Windows systems you may instead use:

```bash
py xarm_850_mister_bean_standalone_demo.py
```

---

## Demo interface

The standalone application contains:

### RUN MISTER BEAN DEMO

Starts the complete automatic demo sequence.

### Connect / Recover

Connects to the robot and attempts to clear robot warnings/errors.

This can be useful if the robot was stopped or entered an error state.

### STOP

Requests the robot to stop.

Use this if the movement does not look correct.

The physical emergency stop should still be used whenever immediate hardware stopping is necessary.

### Status / Step

Shows the current state of the demo and the current automatic step.

### Demo log

Displays the movements and major actions being performed.

---

## What the operator must do

### At the start

The marker should already be:

- in the marker holder;
- positioned normally;
- capped.

Press:

**RUN MISTER BEAN DEMO**

The robot will pick up the marker automatically.

There is no confirmation prompt before the marker pickup in demo mode.

---

## First handoff — remove the cap

After pickup, the robot moves to the user handoff position.

A dialog appears asking you to remove the marker cap.

Do not pull the marker out of the gripper.

Only remove the cap.

When the cap is fully removed, press:

**OK**

The robot then returns to Draw Ready and starts drawing Mister Bean.

---

## Drawing

The drawing stage is automatic.

Do not move:

- the drawing surface;
- the marker holder;
- the robot base;
- the marker inside the gripper.

The robot moves away from the wall between separate drawing strokes and approaches the wall again for each path.

---

## Second handoff — replace the cap

After the drawing is finished, the robot returns to the user handoff position.

A dialog asks you to put the cap back onto the marker.

Place the cap securely onto the marker.

Do not remove the marker from the gripper.

When the cap is on, press:

**OK**

The robot then automatically returns the marker to the marker holder.

---

## End of demo

After releasing the marker into the holder, the robot:

1. lifts above the holder;
2. moves to the safe transfer position;
3. returns to Initial Position.

A completion message is shown when the full sequence finishes.

---

## Marker handling notes

The G2 gripper currently uses approximately:

- **50 mm** = open;
- **10 mm** = holding the marker.

The marker may briefly stick to one of the gripper fingers during handoff or release.

The marker holder may move slightly during this interaction.

During testing, the two sides of the gripper naturally guide the holder back into its normal position during the following pickup/place motion, so this small movement has not caused a noticeable position drift.

---

## Drawing calibration

The demo uses the current five-point calibrated drawing area.

The upper-right corner of the drawing surface is intentionally treated as a restricted / clipped area because of the xArm reach limit.

The standalone demo Python source actually defines the marker X offset as:

`-8.55 mm`

**Archive correction (2026-11-05):** An earlier edition of this README incorrectly said `-19.17 mm`. That value belongs to some **earlier combined full-app** defaults, not the checked-in standalone demo script. The later full-app upload separately contains a settings JSON with **`contact_offset = -12.3`**, which the author reports was the working paper-contact setting on that later fixture. These historical offsets are **not interchangeable**; no automatic contact-force sensor is present. Check the actual script and marker/rack setup before any live use.

The embedded Mister Bean drawing has already been mapped to the calibrated area.

No drawing file or manual SVG positioning is required.

---

## Important safety notes

This program controls a real robot.

During the first runs:

- use reduced robot speed if needed;
- watch the complete arm, not only the gripper;
- keep the emergency stop ready;
- keep people outside the robot movement area except when the robot is waiting at the handoff position;
- do not reach toward the robot while it is moving.

The automatic path is based on the physically tested marker pickup, transfer, handoff, return, and drawing positions for this setup.

If the physical setup is changed, the taught positions may no longer be safe.

Examples include moving:

- the robot;
- the wall/drawing surface;
- the marker holder;
- nearby monitors or furniture.

---

## Robot connection

Default robot IP:

`192.168.1.208`

If the robot IP changes, edit this line near the top of the Python file:

```python
ROBOT_IP = "192.168.1.208"
```

---

## File required for the demo

Only this file is required:

`xarm_850_mister_bean_standalone_demo.py`

The Mister Bean drawing is embedded directly in the program.


---

## Archival source verification (2026-11-05)

- This README describes what the demo's **source is programmed to do**, including two operator cap prompts and a 10-stage automatic robot motion sequence. It does **not** independently establish that every move in this exact GitHub source was safely executed end-to-end on the present robot.
- The source stores the **Mister Bean drawing inline** as `MISTER_BEAN_JSON` with **40 strokes and 408 raw points**, using format `xarm850-freehand-v1`, width **359.6 mm** and height **235 mm**. Its shape and points are **identical** to the separate [color-compatible Mister Bean example](../freehand-drawing/example-drawings/mister_bean_color_compatible.json), though that example adds `palette` and per-stroke `color` metadata. No external JSON is loaded at demo runtime.
- The drawing paths are simplified and validated against the **five-point clipped reachable polygon** before robot connection; this is geometric validation, **not** a collision clearance or marker-force test.
- The app uses Tkinter and the xArm Python SDK only. It does not import Pygame or need a game controller, SVG parser or local drawing file.
- The author has reported prior successful marker pickup and return stages. The detailed README includes setup observations from development. The exact final state of this standalone demo and its current contact pressure are **not reverified** during documentation review.

**No Python source, marker route coordinates, gripper pose or X offsets were changed in this review.**
