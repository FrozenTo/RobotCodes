import time
from xarm.wrapper import XArmAPI

ROBOT_IP = "192.168.1.208"

# =========================================================
# NEW PICKUP-COMPATIBLE DRAW READY POSE
# =========================================================

MARKER_DRAW_READY_JOINTS = [
    -196.531113,
    7.519040,
    -77.101613,
    181.201913,
    80.921408,
    -195.830958,
]

MARKER_DRAW_READY_TCP = [
    -391.468628,
    110.893745,
    597.494202,
    -179.705921,
    -3.507648,
    179.133536,
]

# Old safe Ready -> Handoff movement changed only J1:
# old ready J1    = -196.500001
# old handoff J1  = -281.302854
# delta           = -84.802853 deg
#
# Apply the SAME J1 delta to the new pickup-compatible ready pose.

MARKER_HANDOFF_JOINTS = [
    -281.333966,
    7.519040,
    -77.101613,
    181.201913,
    80.921408,
    -195.830958,
]

START_JOINT_TOLERANCE_DEG = 3.0

HANDOFF_SPEED = 8.0
HANDOFF_ACC = 40.0


def check(code, action):
    if code != 0:
        raise RuntimeError(f"{action} failed, code={code}")


def joints_near(actual, target, tolerance_deg):
    return all(
        abs(a - b) <= tolerance_deg
        for a, b in zip(actual[:6], target[:6])
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


def move_joints(arm, joints, name):
    print()
    print(f"Moving -> {name}")
    print("Only J1 should change significantly.")

    code = arm.set_servo_angle(
        angle=joints,
        speed=HANDOFF_SPEED,
        mvacc=HANDOFF_ACC,
        wait=True,
        is_radian=False,
    )

    check(code, name)


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

        current_joints, _ = read_pose(
            arm,
            "CURRENT POSITION",
        )

        if not joints_near(
            current_joints,
            MARKER_DRAW_READY_JOINTS,
            START_JOINT_TOLERANCE_DEG,
        ):
            print()
            print("REFUSING AUTOMATIC HANDOFF TEST.")
            print(
                "Robot is not currently at MARKER_DRAW_READY "
                f"(within ±{START_JOINT_TOLERANCE_DEG:.1f}° per joint)."
            )
            return

        print()
        print("MARKER_DRAW_READY confirmed.")
        print()
        print("Target handoff joints:")
        print(MARKER_HANDOFF_JOINTS)
        print()
        print(
            "This applies the exact same J1 rotation that was already safe "
            "for the old Draw Ready -> Handoff route, while keeping the new "
            "pickup-compatible J2-J6 wrist configuration unchanged."
        )

        input(
            "\nPress ENTER to test MARKER_DRAW_READY -> MARKER_HANDOFF, "
            "or Ctrl+C to cancel..."
        )

        move_joints(
            arm,
            MARKER_HANDOFF_JOINTS,
            "MARKER_HANDOFF",
        )

        handoff_joints, handoff_tcp = read_pose(
            arm,
            "AT NEW MARKER_HANDOFF",
        )

        print()
        print("==============================================")
        print("HANDOFF TEST COMPLETE")
        print("==============================================")
        print()
        print("If this movement was clean, save:")
        print()
        print("MARKER_HANDOFF_JOINTS = [")
        for value in handoff_joints:
            print(f"    {value:.6f},")
        print("]")
        print()
        print("MARKER_HANDOFF_TCP = [")
        for value in handoff_tcp:
            print(f"    {value:.6f},")
        print("]")
        print()
        print("The robot will remain at the handoff pose.")

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
