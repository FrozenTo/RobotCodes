import math
import time
from xarm.wrapper import XArmAPI

ROBOT_IP = "192.168.1.208"

# =========================================================
# KNOWN SAFE / TAUGHT POSES
# =========================================================

PICK_TRANSFER_JOINTS = [
    -160.821518,
    19.858717,
    -57.315088,
    179.907086,
    75.597484,
    -161.733323,
]

PICK_TRANSFER_TCP = [
    -307.723938,
    -105.031891,
    519.999939,
    -179.569958,
    -1.128784,
    -179.067187,
]

# Existing wall-writing ready pose, expressed as TCP.
# We will target THIS POSE CARTESIANLY rather than replaying
# the old DRAW_READY_JOINTS that caused the wrist flip.
DRAW_READY_TCP = [
    -391.468628,
    110.893806,
    597.494202,
    -179.705921,
    -3.507648,
    179.133536,
]

# Old ready joints kept only for reference.
OLD_DRAW_READY_JOINTS = [
    -196.500001,
    7.500018,
    -77.100008,
    1.200003,
    -80.899979,
    -15.799999,
]

# Existing handoff pose (old wrist solution).
OLD_HANDOFF_JOINTS = [
    -281.302854,
    7.500018,
    -77.100008,
    1.200003,
    -80.899979,
    -15.799999,
]

OLD_HANDOFF_TCP = [
    71.988007,
    398.225952,
    598.817017,
    -179.961001,
    -3.633698,
    94.346897,
]

# =========================================================
# TEST SETTINGS
# =========================================================

START_JOINT_TOLERANCE_DEG = 3.0

# Slow Cartesian transition for first physical test.
CART_SPEED = 30.0      # mm/s
CART_ACC = 80.0        # mm/s^2

# How close to the requested Draw Ready TCP we expect to land.
TCP_POSITION_TOLERANCE_MM = 3.0


def check(code, action):
    if code != 0:
        raise RuntimeError(f"{action} failed, code={code}")


def joints_near(actual, target, tolerance_deg):
    return all(
        abs(a - b) <= tolerance_deg
        for a, b in zip(actual[:6], target[:6])
    )


def xyz_distance(a, b):
    return math.sqrt(
        (a[0] - b[0]) ** 2
        + (a[1] - b[1]) ** 2
        + (a[2] - b[2]) ** 2
    )


def read_pose(arm, label):
    code_j, joints = arm.get_servo_angle(is_radian=False)
    check(code_j, f"read joints ({label})")

    code_p, pose = arm.get_position(is_radian=False)
    check(code_p, f"read TCP ({label})")

    joints6 = joints[:6]

    print()
    print(f"--- {label} ---")
    print("JOINTS:")
    print([round(v, 6) for v in joints6])

    print()
    print("TCP:")
    print([round(v, 6) for v in pose])

    return joints6, pose


def move_cartesian_linear(arm, pose, name, speed, acc):
    x, y, z, roll, pitch, yaw = pose

    print()
    print(f"Linear Cartesian move -> {name}")
    print(
        f"Target: X={x:.3f}, Y={y:.3f}, Z={z:.3f}, "
        f"R={roll:.3f}, P={pitch:.3f}, Yaw={yaw:.3f}"
    )

    code = arm.set_position(
        x=x,
        y=y,
        z=z,
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        speed=speed,
        mvacc=acc,
        wait=True,
        relative=False,
        is_radian=False,
        motion_type=0,
    )

    check(code, name)


def print_joint_comparison(new_joints):
    print()
    print("Joint comparison vs OLD Draw Ready:")
    print()

    for i, (new, old) in enumerate(
        zip(new_joints, OLD_DRAW_READY_JOINTS),
        start=1,
    ):
        delta = new - old
        print(
            f"J{i}: new={new:9.3f}°  "
            f"old={old:9.3f}°  "
            f"delta={delta:+9.3f}°"
        )


def main():
    arm = XArmAPI(
        ROBOT_IP,
        is_radian=False,
    )

    try:
        print(f"Connecting to xArm at {ROBOT_IP}...")
        arm.connect()

        arm.clean_warn()
        arm.clean_error()

        try:
            print(
                "G2 collision model:",
                arm.set_collision_tool_model(9),
            )
        except Exception as exc:
            print("Could not set G2 collision model:", exc)

        try:
            print(
                "Self-collision detection:",
                arm.set_self_collision_detection(True),
            )
        except Exception as exc:
            print("Could not enable self-collision detection:", exc)

        check(
            arm.motion_enable(enable=True),
            "motion_enable",
        )

        check(
            arm.set_mode(0),
            "set_mode(0)",
        )

        check(
            arm.set_state(0),
            "set_state(0)",
        )

        time.sleep(0.3)

        current_joints, current_tcp = read_pose(
            arm,
            "CURRENT POSITION",
        )

        if not joints_near(
            current_joints,
            PICK_TRANSFER_JOINTS,
            START_JOINT_TOLERANCE_DEG,
        ):
            print()
            print("REFUSING AUTOMATIC TEST.")
            print(
                "The robot is not at the recorded PICK_TRANSFER pose "
                f"(within ±{START_JOINT_TOLERANCE_DEG:.1f}° on every joint)."
            )
            print()
            print("Expected PICK_TRANSFER joints:")
            print(PICK_TRANSFER_JOINTS)
            return

        print()
        print("PICK_TRANSFER pose confirmed.")
        print()
        print("TEST:")
        print("PICK_TRANSFER -> DRAW_READY_TCP")
        print()
        print(
            "This time the target is the SAME physical Draw Ready TCP pose, "
            "but reached with a linear Cartesian move instead of the old "
            "joint-space Draw Ready command."
        )
        print()
        print(
            "Watch the entire arm and keep the physical E-stop ready."
        )

        input(
            "\nPress ENTER to test Cartesian PICK_TRANSFER -> DRAW_READY, "
            "or Ctrl+C to cancel..."
        )

        move_cartesian_linear(
            arm,
            DRAW_READY_TCP,
            "DRAW_READY_TCP",
            CART_SPEED,
            CART_ACC,
        )

        new_ready_joints, new_ready_tcp = read_pose(
            arm,
            "NEW CARTESIAN DRAW READY",
        )

        distance = xyz_distance(
            new_ready_tcp,
            DRAW_READY_TCP,
        )

        print()
        print(
            f"XYZ distance from requested Draw Ready TCP: "
            f"{distance:.3f} mm"
        )

        print_joint_comparison(
            new_ready_joints
        )

        print()
        print("==============================================")
        print("CARTESIAN READY TEST COMPLETE")
        print("==============================================")
        print()

        if distance <= TCP_POSITION_TOLERANCE_MM:
            print("The TCP reached the requested Draw Ready position closely.")
        else:
            print(
                "WARNING: TCP position differs more than the expected "
                f"{TCP_POSITION_TOLERANCE_MM:.1f} mm."
            )

        print()
        print("If the whole-arm path was physically clean, save:")
        print()
        print("MARKER_DRAW_READY_JOINTS = [")
        for value in new_ready_joints:
            print(f"    {value:.6f},")
        print("]")

        print()
        print("MARKER_DRAW_READY_TCP = [")
        for value in new_ready_tcp:
            print(f"    {value:.6f},")
        print("]")

        print()
        print("IMPORTANT:")
        print(
            "This test intentionally DOES NOT move to the old HANDOFF pose."
        )
        print(
            "The old handoff joints belong to the old Draw Ready wrist "
            "configuration. If this new Cartesian Ready uses a different "
            "J4/J5/J6 solution, commanding OLD_HANDOFF_JOINTS could recreate "
            "the same unwanted wrist flip."
        )
        print()
        print(
            "If this path looked good, send me the printed "
            "MARKER_DRAW_READY_JOINTS/TCP. Then we will build a matching "
            "handoff pose from THIS wrist configuration, preferably by "
            "changing only J1."
        )
        print()
        print("The robot will remain at the new Draw Ready pose.")

    except KeyboardInterrupt:
        print()
        print("Cancelled by user.")

    except Exception as exc:
        print()
        print("ERROR:", exc)

        try:
            code, status = arm.get_err_warn_code()
            print("Robot error/warn:", code, status)
        except Exception:
            pass

    finally:
        try:
            arm.disconnect()
        except Exception:
            pass

        print()
        print("Disconnected.")


if __name__ == "__main__":
    main()
