# xArm 850 — Early Xbox Controller and Joint Tests

**Robot:** UFACTORY xArm 850 / UF850  
**Project goal:** Responsive **multi-axis controller-driven** movement unavailable in the author's MG400 `MoveJog` workflow  
**Review:** Source reviewed 2026-11-04; physical test outcome of each exact file is not independently verified.  
**Most developed file in this folder:** `XARM_ContJoint.py`. The later [combined controller and drawing application](../combined-controller-and-drawer/) is a separate, more substantial project to review next.

## Why this followed MG400

The final MG400 Xbox controller **worked**, but its chosen `MoveJog` approach allowed effectively **one axis at a time** during manual joystick control. The author switched to xArm 850 to achieve a more fluid response when moving **two or more Cartesian axes simultaneously**.

The xArm source shows a concrete technical change: it uses the UFACTORY SDK's **Cartesian velocity mode (mode 5)** with a continuously refreshed **velocity vector**, rather than selecting one discrete jog direction. The later prototype adds **joint velocity mode (mode 4)**. This is an improvement in *how the controller can command motion*; its complete physical performance still depends on the robot, speed/acceleration, tool and workspace.

These source files were once stored inside an MG400 keyboard-control upload despite being xArm-specific. They were moved here during GitHub organization without changing the Python content.

## Which script is which?

| File | Role | Key distinction |
| --- | --- | --- |
| `xarm_pos_read.py` | Minimal TCP/joint diagnostic | Connects to `192.168.1.208`, reads `get_servo_angle()` and `get_position()`, prints both arrays and disconnects. **Read only**; it does not intentionally issue motion. |
| `XARM_Controller1.py` | First full live Xbox velocity-control experiment | **Combined X/Y/Z joystick movement** with speed proportional to deflection; D-pad can jog J5/J6 after switching to joint velocity mode; L2/R2 control a G2 gripper; A stops velocity, B exits/disables, X invokes recovery. |
| `XARM_ContJoint.py` | Expanded gamepad control | Retains continuous combined XYZ, adds **R1 XYZ/JOINT mode**, **L1 selected J1–J4**, right-stick joint jogging and D-pad J5/J6. Also adds joint-velocity smoothing, stop/recenter/fault latching and mode-switch handling. |

The second controller is a **functional expansion**, not simply a filename variation. It does **not** replace or include the separate wall-lettering, SVG or freehand editors.

## How simultaneous XYZ movement works

Both controllers read the gamepad sticks and compute three Cartesian velocity components:

| Gamepad input | Cartesian request |
| --- | --- |
| Right stick up / down | **X− / X+** |
| Right stick left / right | **Y− / Y+** |
| Left stick up / down | **Z+ / Z−** |

Instead of choosing one active axis as the MG400 controller did, the code constructs **all three components together** and calls:

```python
arm.vc_set_cartesian_velocity(
    [vx, vy, vz, 0, 0, 0],
    is_tool_coord=False,
    duration=0.5,
)
```

`is_tool_coord=False` means the command is expressed relative to the **robot base axes**, not a camera or writing-surface frame. The three rotational velocity entries are zero: the ordinary XYZ stick mapping **translates without commanding roll/pitch/yaw velocity**.

At full deflection, the source caps the combined XYZ velocity magnitude to `MAX_TCP_SPEED=80` mm/s, rather than permitting faster diagonal motion by simply summing axes. It uses a **15% deadzone**, **50 Hz / 0.02 s input polling**, smoothing factor `0.25`, and **0.5-second velocity command duration**. The 0.5-second duration is a command timeout if updates stop, **not a guarantee of an instantaneous hardware emergency stop**.

This explicitly addresses the simultaneous Cartesian motion goal in **implementation**. Individual physical smoothness and reach tests were not verified in this documentation pass.

## Joint control in XARM_ContJoint.py

- **R1** toggles between XYZ velocity (SDK mode **5**) and JOINT velocity (SDK mode **4**).
- **L1** cycles one **selected joint**, J1 → J2 → J3 → J4 → J1.
- In JOINT mode, the **right stick horizontal axis** operates selected **J1 or J4**, and its **vertical axis** operates selected **J2 or J3**.
- The **D-pad up/down** controls **J5**, and **left/right** controls **J6**. In JOINT mode, these two may be commanded together with the selected J1–J4 velocity in the six-component vector.
- In XYZ mode, D-pad J5/J6 temporarily takes priority and changes the SDK to joint velocity mode for that action, then returns to Cartesian mode.
- Default joint velocities are **20°/s** with joint max acceleration **100°/s²**, smoothing factor `0.25` for J1–J4.

**Important limitation:** This is **NOT simultaneous independent J1–J4 joystick control**. The four joints are selected by L1, **one at a time**. A later desired mapping—right stick J1/J2 and left stick J3/J4 simultaneously—was a **future design request**, not implemented in these two prototypes. Do not mark it complete simply because `vc_set_joint_velocity` can transmit a multi-joint vector.

## Gripper and other controls

Both main controller scripts assume a **UFACTORY G2 gripper**:

| Input | Action |
| --- | --- |
| **L2 trigger** | Open G2 proportionally by updating target position |
| **R2 trigger** | Close G2 proportionally |
| **A** | Software velocity STOP (zero-velocity command + movement latch) |
| **B** | End controller loop, stop, disable motion and disconnect |
| **X** | Attempt recovery from robot error |
| **D-pad** | J5 / J6 joint velocity |
| **R1** | XYZ / JOINT toggle in `XARM_ContJoint.py` |
| **L1** | Next J1–J4 in JOINT mode in `XARM_ContJoint.py` |

The G2 controller reads the current position where available, limits the target between **0 and 84 mm**, and sends position changes at a reduced rate instead of every 20 ms iteration. This is not the same as the MG400 DO1/DO2 suction/blow tool arrangement. Check which gripper is physically attached before running these scripts; gripper functionality has not been retested here.

Controller axis indices in these files reflect the specific PC/gamepad driver mapping they were written against: left X=0, left Y=1, right X=2, right Y=3, triggers L2=4/R2=5; A=0, B=1, X=2, L1=4, R1=5. Other controllers/OS configurations can differ.

## Safety and recovery behavior seen in source

1. On startup, the two controller apps **connect, clear warnings/errors, configure G2 collision tool model and self-collision detection, enable robot motion, and enter Cartesian velocity mode** without a separate startup confirmation prompt. They are **live motion applications**. Their collision-model setup calls are attempted but caught/logged if unsupported.
2. The gamepad loop handles **controller detach** by issuing stop logic and breaking out; normal cleanup attempts to disable robot motion and disconnect.
3. Software **STOP** uses zero Cartesian/joint velocity, **not a physical emergency stop**. The source uses a stop latch so the stick must return to center before moving again.
4. Faults can trigger a **fault latch** and the X button initiates a clear/re-enable recovery sequence. The physical cause of a fault must be investigated before recovery; pressing X cannot make a collision or unsafe posture acceptable.
5. Mode and selected-joint changes stop existing velocities before switching and require neutral controls, reducing unexpected cross-mode jumps.
6. **No full robot + tool collision proof:** the G2 collision tool setting and self-collision detection are not equivalent to verifying the actual environment, wall, paper or tool attachments.
7. The original `XARM_Controller1.py` includes a repeated, effectively unreachable second X-button recovery check after updating its button-edge state. This appears to be leftover duplicated logic, not a demonstrated physical defect.
8. These scripts use `ROBOT_IP = "192.168.1.208"`, an historical local robot address; they do not automatically detect the current device.

## Running and dependencies

The source imports **`pygame`** and the official **UFACTORY Python SDK (`xarm`)**. A joystick must be attached and reachable by pygame. The scripts have **no graphical desktop interface** or JSON settings file: user feedback is printed to the terminal.

Historical commands, **not live-run recommendations**:

```bash
python xarm_pos_read.py
python XARM_Controller1.py
python XARM_ContJoint.py
```

`xarm_pos_read.py` is the only intentionally read-only utility. The two controller programs directly enable and command physical robot motion; check tool setup, frame orientation, speed and safe workspace first.

## Relationship to later programs

- [Motion Tests](../motion-tests/) contain the initial small-step and Tkinter movement experiments.
- [Combined Controller + Drawer](../combined-controller-and-drawer/) later integrates gamepad control with wall writing, imported SVG and freehand drawing. It is **not yet established here** which combined GUI version was the latest physically confirmed working build.
- [MG400 Controller](../../MG400/controller/) is the predecessor whose single-axis jogging limitation motivated this xArm work.

**Catalog status:** `XARM_ContJoint.py` is the **most feature-complete early controller prototype in this folder**, with **source-confirmed simultaneous Cartesian XYZ**, **selected joint** manual control and **G2** commands. Physical success of every feature and the exact chronological order of individual revisions remain uncertain; do not equate source completeness with full hardware validation.

**No source code, motion constants, calibration settings, or gripper parameters were changed in this review.**
