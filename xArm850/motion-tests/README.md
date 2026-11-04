# xArm 850 / UF850 — Connection and Motion Tests

**Robot:** UFACTORY xArm 850 (also called UF850 in filenames)  
**Purpose:** First controlled movements, pose/joint readback and a small Tkinter jog interface before gamepad control or wall drawing  
**Review status:** Source reviewed on 2026-11-04. Physical execution results for these **individual** files are not independently confirmed.  
**Typical network:** `192.168.1.208` as configured in each script.

## Where this sits in the project history

The author moved toward xArm after working with an MG400 controller that was functional but too limited for **smooth simultaneous manual joystick movement**. These small xArm tests establish the connection, coordinate conventions and basic step movements before the [Xbox controller prototypes](../controller-tests/) and the later [combined controller/drawing app](../combined-controller-and-drawer/).

These files use the **official UFACTORY Python SDK** (`from xarm.wrapper import XArmAPI`) rather than the MG400's raw dashboard/motion TCP command style. They are **not the main final xArm controller applications**.

## Files and behavior

| File | Intended experiment | What the source actually does |
| --- | --- | --- |
| `uf850_test.py` | First connection and Cartesian move test | Displays firmware/version, status, errors, TCP pose and joint angles; checks for an existing robot error; requires Enter prompts before enabling and each **10 mm** move. Tests +Y, −Y, +X and −X at **20 mm/s**, using relative `set_position(..., wait=True)`. |
| `uf850_jog_test.py` | Simple manual jog from console | Interactive text commands `x+`, `x-`, `y+`, `y-`, `z+`, `z-`, `p` to read TCP, `q` to quit. Each command sends a **5 mm** relative `set_position` at **20 mm/s** and waits for completion. Requests confirmation before a −X move toward the wall. |
| `uf850_tkjog.py` | Mouse-operated control interface | Tkinter window with IP, connect/disconnect/enable, pose readback, XYZ step/speed settings and six XYZ jog buttons; one **J1 ±** jog pair with joint step/speed and angle readback. Has an `EMERGENCY STOP` button that calls the SDK's `arm.emergency_stop()` method. |

The Tkinter app's jog controls are **button-triggered discrete steps**, not continuous gamepad-like velocity control. Joint movement in that app covers **J1 only**, rather than all six joints.

## Coordinate system and wall setup

The experiments assume a **vertical writing surface on the negative-X side of the robot**. The recorded robot IP is `192.168.1.208`.

- **+X** is treated as moving **away from** the wall.
- **−X** is treated as moving **toward** the wall.
- **Y** is horizontal movement along the intended writing surface.
- **Z** is height.

This is the project's **actual tested/intended installation convention**, not a universal property of every xArm mounting. Check the current robot base frame, TCP, tool geometry and wall position before issuing a move.

`uf850_jog_test.py` asks for extra confirmation on **−X**; `uf850_test.py` issues its return −X as part of the prompted four-step sequence; the GUI logs a warning before −X but does not require an extra confirmation.

## Technical implementation

- The scripts use `XArmAPI(..., is_radian=False)`, keeping Cartesian distances in **millimeters** and angles in **degrees**.
- Both terminal tests use **SDK mode 0** and `set_state(0)` after `motion_enable(True)`.
- Terminal test movements use `relative=True`, so a jog requests an offset from the current pose, **not** a fixed global position.
- `uf850_tkjog.py` uses Python `threading.Thread(..., daemon=True)` for enable and movement requests to avoid long blocking callbacks.
- The Tkinter app displays current pose and joint readings, with speed/step controls for XYZ and J1; it does **not** store calibration profiles.
- All three files are designed to talk directly to the **real robot**. There is no simulation/live toggle in these scripts.

## Source review limitations and cautions

1. **Physical safety:** even 5–10 mm can be excessive near a wall, tool rack, workpiece or joint boundary. Verify tool clearance and provide hardware E-stop access.
2. **No full collision/path preflight:** the step-based movement calls do not check all intermediate robot-link configurations.
3. **GUI thread safety:** `uf850_tkjog.py` starts workers that update Tkinter widgets/logs from worker threads. Tkinter operations are not generally thread-safe, which could cause sporadic UI instability. This is a code-review risk, **not a confirmed crash**.
4. **GUI request concurrency:** clicking motion buttons multiple times may launch several workers; the code does not implement a single serialized movement queue. Avoid overlapping motion requests.
5. **Software stop vs hardware E-stop:** the GUI's button invokes `arm.emergency_stop()` through software. It is not a replacement for a physically accessible emergency-stop mechanism.
6. **No automatic movement on opening:** `uf850_test.py` and `uf850_jog_test.py` prompt before movements, while `uf850_tkjog.py` requires button actions. However, enabling a robot always requires a clear work area and suitable supervision.
7. **Limited error handling:** some SDK return values are printed rather than stopping the entire sequence after a nonzero return; the small `xarm_pos_read.py` diagnostic is documented separately in [controller-tests](../controller-tests/).

## Dependencies and running

These programs import the **`xarm` Python SDK**. The Tkinter UI uses Python's standard Tkinter package. There is no `dobot_api.py` dependency for xArm.

Examples from this folder, **for historical documentation only**:

```bash
python uf850_test.py
python uf850_jog_test.py
python uf850_tkjog.py
```

Do not start archived movement tests on a live robot without checking the current tool, settings, reachable area and the operator's Stop/E-stop procedure.

## Catalog conclusion

Keep the three scripts together under **Motion Tests / First xArm Connection**. They explain the first coordinate, movement and user-interface experiments that preceded the Xbox velocity controller. They should not be mislabeled as a completed multi-axis controller. **No Python code or motion values were changed during this review.**
