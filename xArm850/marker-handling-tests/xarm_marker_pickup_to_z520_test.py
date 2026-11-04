import math
import time
from xarm.wrapper import XArmAPI

ROBOT_IP = "192.168.1.208"

# =========================================================
# TAUGHT PICKUP POSES
# =========================================================

PICK_JOINTS = [
    -161.125014,
    -29.157536,
    -26.325291,
    177.925282,
    -3.691223,
    -159.999324,
]

PICK_TCP = [
    -305.388947,
    -105.130829,
    8.789021,
    -179.532257,
    -0.359646,
    -179.090679,
]

PICK_ABOVE_JOINTS = [
    -161.024918,
    -16.920360,
    -24.378609,
    178.725647,
    5.883131,
    -160.717526,
]

PICK_ABOVE_TCP = [
    -307.723938,
    -105.031891,
    71.431976,
    -179.569958,
    -1.128727,
    -179.067187,
]

# =========================================================
# CANDIDATE TRANSFER CHECKPOINT
# =========================================================
#
# Keep the exact X/Y/orientation of PICK_ABOVE, but lift
# vertically in base coordinates to Z = 520 mm.
#
# We do NOT predefine joints here. The robot reaches this
# with a linear Cartesian move, then we read/print the
# resulting joint configuration and use that as the taught
# PICK_TRANSFER if the path is physically safe.
# =========================================================

TRANSFER_Z = 520.0

PICK_TRANSFER_TCP = [
    PICK_ABOVE_TCP[0],
    PICK_ABOVE_TCP[1],
    TRANSFER_Z,
    PICK_ABOVE_TCP[3],
    PICK_ABOVE_TCP[4],
    PICK_ABOVE_TCP[5],
]

# =========================================================
# GRIPPER
# =========================================================

GRIPPER_OPEN = 50
GRIPPER_PICK = 10

GRIPPER_SPEED = 100
GRIPPER_FORCE = 50

# =========================================================
# MOTION SETTINGS
# =========================================================

JOINT_APPROACH_SPEED = 10.0
JOINT_APPROACH_ACC = 50.0

PICK_SPEED = 6.0
PICK_ACC = 30.0

# Cartesian straight-up transfer.
TRANSFER_SPEED = 40.0       # mm/s
TRANSFER_ACC = 100.0        # mm/s^2

# Only allow the automatic PICK_ABOVE approach when already
# reasonably near the pickup station.
START_MAX_TCP_DISTANCE_MM = 120.0


# =========================================================
# HELPERS
# =========================================================

def check(code, action):
    if code != 0:
        raise RuntimeError(f"{action} failed, code={code}")


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


def move_joints(arm, joints, name, speed, acc):
    print()
    print(f"Moving -> {name}")

    code = arm.set_servo_angle(
        angle=joints,
        speed=speed,
        mvacc=acc,
        wait=True,
        is_radian=False,
    )

    check(code, name)


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
        motion_type=0,  # explicitly request linear Cartesian planning
    )

    check(code, name)


def set_gripper(arm, position):
    print()
    print(f"G2 -> {position} mm")

    code = arm.set_gripper_g2_position(
        position,
        speed=GRIPPER_SPEED,
        force=GRIPPER_FORCE,
        wait=True,
    )

    check(code, f"G2 {position} mm")


# =========================================================
# TEST
# =========================================================

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

        _, current_tcp = read_pose(
            arm,
            "CURRENT POSITION",
        )

        distance = xyz_distance(
            current_tcp,
            PICK_ABOVE_TCP,
        )

        print()
        print(
            "Distance from current TCP to PICK_ABOVE: "
            f"{distance:.1f} mm"
        )

        if distance > START_MAX_TCP_DISTANCE_MM:
            print()
            print("REFUSING AUTOMATIC PICKUP APPROACH.")
            print(
                "Use the controller to move reasonably near the pickup "
                f"station (within {START_MAX_TCP_DISTANCE_MM:.0f} mm of "
                "PICK_ABOVE), then run this test again."
            )
            return

        input(
            "\nPress ENTER to open G2 and move to exact PICK_ABOVE..."
        )

        set_gripper(
            arm,
            GRIPPER_OPEN,
        )

        move_joints(
            arm,
            PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            JOINT_APPROACH_SPEED,
            JOINT_APPROACH_ACC,
        )

        read_pose(
            arm,
            "AT PICK_ABOVE",
        )

        input(
            "\nInspect the approach. If clear, press ENTER to descend to PICK..."
        )

        move_joints(
            arm,
            PICK_JOINTS,
            "PICK",
            PICK_SPEED,
            PICK_ACC,
        )

        read_pose(
            arm,
            "AT PICK",
        )

        input(
            "\nIf the gripper is correctly around the marker, "
            "press ENTER to close to 10 mm..."
        )

        set_gripper(
            arm,
            GRIPPER_PICK,
        )

        time.sleep(1.0)

        input(
            "\nPress ENTER to lift back to exact PICK_ABOVE..."
        )

        move_joints(
            arm,
            PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            PICK_SPEED,
            PICK_ACC,
        )

        read_pose(
            arm,
            "BACK AT PICK_ABOVE",
        )

        print()
        print("==============================================")
        print("NEXT MOVE IS THE NEW TEST")
        print("==============================================")
        print(
            "The robot will now keep the same X/Y and wrist orientation "
            "and move linearly upward to:"
        )
        print()
        print(
            f"X = {PICK_TRANSFER_TCP[0]:.3f}"
            f" | Y = {PICK_TRANSFER_TCP[1]:.3f}"
            f" | Z = {PICK_TRANSFER_TCP[2]:.3f}"
        )
        print()
        print(
            "Watch the ENTIRE arm during this move and keep the physical "
            "E-stop ready."
        )

        input(
            "\nPress ENTER to test PICK_ABOVE -> Z=520, "
            "or Ctrl+C to cancel..."
        )

        move_cartesian_linear(
            arm,
            PICK_TRANSFER_TCP,
            "PICK_TRANSFER candidate",
            TRANSFER_SPEED,
            TRANSFER_ACC,
        )

        transfer_joints, transfer_tcp = read_pose(
            arm,
            "PICK_TRANSFER CANDIDATE",
        )

        print()
        print("==============================================")
        print("TRANSFER TEST COMPLETE")
        print("==============================================")
        print()
        print("If this path was physically clean, save these values:")
        print()
        print("PICK_TRANSFER_JOINTS = [")
        for value in transfer_joints:
            print(f"    {value:.6f},")
        print("]")
        print()
        print("PICK_TRANSFER_TCP = [")
        for value in transfer_tcp:
            print(f"    {value:.6f},")
        print("]")
        print()
        print("The robot will remain at this transfer pose.")
        print("This script will NOT move to DRAW_READY.")

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
        # Do not automatically move anywhere after the transfer test.
        # We want the robot to remain physically at the tested checkpoint.
        try:
            arm.disconnect()
        except Exception:
            pass

        print()
        print("Disconnected.")


if __name__ == "__main__":
    main()
