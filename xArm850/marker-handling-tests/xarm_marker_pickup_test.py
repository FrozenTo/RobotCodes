import math
import time
from xarm.wrapper import XArmAPI

ROBOT_IP = "192.168.1.208"

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

GRIPPER_OPEN = 50
GRIPPER_PICK = 10
GRIPPER_SPEED = 100
GRIPPER_FORCE = 50

APPROACH_SPEED = 10.0
APPROACH_ACC = 50.0

PICK_SPEED = 6.0
PICK_ACC = 30.0

START_MAX_TCP_DISTANCE_MM = 120.0


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

    print()
    print(f"--- {label} ---")
    print("JOINTS:")
    print([round(v, 6) for v in joints[:6]])
    print("TCP:")
    print([round(v, 6) for v in pose])

    return joints[:6], pose


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


def set_gripper(arm, position):
    print(f"G2 -> {position} mm")
    code = arm.set_gripper_g2_position(
        position,
        speed=GRIPPER_SPEED,
        force=GRIPPER_FORCE,
        wait=True,
    )
    check(code, f"G2 {position} mm")


def main():
    arm = XArmAPI(ROBOT_IP, is_radian=False)

    try:
        print(f"Connecting to {ROBOT_IP}...")
        arm.connect()

        arm.clean_warn()
        arm.clean_error()

        try:
            print("G2 collision model:", arm.set_collision_tool_model(9))
        except Exception as exc:
            print("Could not set G2 collision model:", exc)

        try:
            print("Self-collision detection:", arm.set_self_collision_detection(True))
        except Exception as exc:
            print("Could not enable self-collision detection:", exc)

        check(arm.motion_enable(enable=True), "motion_enable")
        check(arm.set_mode(0), "set_mode(0)")
        check(arm.set_state(0), "set_state(0)")
        time.sleep(0.3)

        _, current_tcp = read_pose(arm, "CURRENT POSITION")

        distance = xyz_distance(current_tcp, PICK_ABOVE_TCP)

        print()
        print(f"Distance from current TCP to PICK_ABOVE: {distance:.1f} mm")

        if distance > START_MAX_TCP_DISTANCE_MM:
            print()
            print("REFUSING AUTOMATIC MOVE.")
            print(
                "Use the controller to move reasonably near the pickup station "
                f"(within {START_MAX_TCP_DISTANCE_MM:.0f} mm of PICK_ABOVE), "
                "then run this test again."
            )
            return

        input("\nPress ENTER to open G2 and move to the exact PICK_ABOVE pose...")

        set_gripper(arm, GRIPPER_OPEN)

        move_joints(
            arm,
            PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            APPROACH_SPEED,
            APPROACH_ACC,
        )

        read_pose(arm, "AT PICK_ABOVE")

        input("\nInspect the approach. If clear, press ENTER to descend to PICK...")

        move_joints(
            arm,
            PICK_JOINTS,
            "PICK",
            PICK_SPEED,
            PICK_ACC,
        )

        read_pose(arm, "AT PICK")

        input(
            "\nIf the gripper is correctly around the marker, "
            "press ENTER to close to 10 mm..."
        )

        set_gripper(arm, GRIPPER_PICK)
        time.sleep(1.0)

        input("\nMarker should now be held. Press ENTER to lift back to PICK_ABOVE...")

        move_joints(
            arm,
            PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            PICK_SPEED,
            PICK_ACC,
        )

        read_pose(arm, "FINAL PICK_ABOVE")

        print()
        print("Pickup test finished successfully.")
        print()
        print("IMPORTANT:")
        print("The robot will stay at PICK_ABOVE.")
        print("Do NOT command DRAW_READY from this script.")
        print(
            "Next, open the controller app from this exact physical pose and "
            "carefully move to a high-clearance transfer checkpoint."
        )
        print("Then record that checkpoint's JOINTS + TCP.")

    except KeyboardInterrupt:
        print("\nStopped by user.")

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

        print("Disconnected.")


if __name__ == "__main__":
    main()
