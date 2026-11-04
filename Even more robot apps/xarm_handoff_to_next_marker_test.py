import time
from xarm.wrapper import XArmAPI

ROBOT_IP = "192.168.1.208"

# =========================================================
# FINAL TAUGHT MARKER ROUTE POSES
# =========================================================

MARKER_HANDOFF_JOINTS = [
    -281.333966,
    7.519040,
    -77.101613,
    181.201913,
    80.921408,
    -195.830958,
]

MARKER_HANDOFF_TCP = [
    71.987541,
    398.225983,
    598.816772,
    -179.960944,
    -3.633641,
    94.347012,
]

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

PICK_JOINTS = [
    -161.125014,
    -29.157536,
    -26.325291,
    177.925282,
    -3.691223,
    -159.999324,
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

START_JOINT_TOLERANCE_DEG = 3.0

# Handoff <-> Draw Ready is intentionally J1-only.
HANDOFF_SPEED = 8.0
HANDOFF_ACC = 40.0

# Cartesian reverse of the already-tested forward route.
CART_SPEED = 30.0
CART_ACC = 80.0

# Final short pickup descent, only if explicitly chosen.
PICK_SPEED = 6.0
PICK_ACC = 30.0


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


def move_joints(arm, joints, name, speed, acc):
    print()
    print(f"Joint move -> {name}")

    code = arm.set_servo_angle(
        angle=joints,
        speed=speed,
        mvacc=acc,
        wait=True,
        is_radian=False,
    )

    check(code, name)


def move_cartesian_linear(arm, pose, name):
    x, y, z, roll, pitch, yaw = pose

    print()
    print(f"Linear Cartesian move -> {name}")

    code = arm.set_position(
        x=x,
        y=y,
        z=z,
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        speed=CART_SPEED,
        mvacc=CART_ACC,
        wait=True,
        relative=False,
        is_radian=False,
        motion_type=0,
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


def main():
    arm = XArmAPI(ROBOT_IP, is_radian=False)

    try:
        print(f"Connecting to xArm at {ROBOT_IP}...")
        arm.connect()

        arm.clean_warn()
        arm.clean_error()

        try:
            print("G2 collision model:", arm.set_collision_tool_model(9))
        except Exception as exc:
            print("Could not set G2 collision model:", exc)

        try:
            print(
                "Self-collision detection:",
                arm.set_self_collision_detection(True),
            )
        except Exception as exc:
            print("Could not enable self-collision detection:", exc)

        check(arm.motion_enable(enable=True), "motion_enable")
        check(arm.set_mode(0), "set_mode(0)")
        check(arm.set_state(0), "set_state(0)")
        time.sleep(0.3)

        current_joints, _ = read_pose(arm, "CURRENT POSITION")

        if not joints_near(
            current_joints,
            MARKER_HANDOFF_JOINTS,
            START_JOINT_TOLERANCE_DEG,
        ):
            print()
            print("REFUSING AUTOMATIC TEST.")
            print(
                "Start from the recorded MARKER_HANDOFF pose "
                f"(within ±{START_JOINT_TOLERANCE_DEG:.1f}° per joint)."
            )
            return

        print()
        print("MARKER_HANDOFF confirmed.")
        print()
        print("This test checks the route used to fetch the NEXT marker:")
        print()
        print("HANDOFF")
        print("  -> MARKER_DRAW_READY   (J1 only)")
        print("  -> PICK_TRANSFER       (Cartesian reverse route)")
        print("  -> PICK_ABOVE          (straight Cartesian descent)")
        print()
        print("It will stop at PICK_ABOVE unless you explicitly choose")
        print("to test the final short descent to PICK.")

        input(
            "\nMake sure the previous marker has been removed. "
            "Press ENTER to open the gripper to 50 mm..."
        )

        set_gripper(arm, GRIPPER_OPEN)

        input(
            "\nPress ENTER to move HANDOFF -> MARKER_DRAW_READY..."
        )

        move_joints(
            arm,
            MARKER_DRAW_READY_JOINTS,
            "MARKER_DRAW_READY",
            HANDOFF_SPEED,
            HANDOFF_ACC,
        )

        read_pose(arm, "AT MARKER_DRAW_READY")

        input(
            "\nIf the J1-only return looked clean, press ENTER for "
            "MARKER_DRAW_READY -> PICK_TRANSFER..."
        )

        move_cartesian_linear(
            arm,
            PICK_TRANSFER_TCP,
            "PICK_TRANSFER",
        )

        read_pose(arm, "AT PICK_TRANSFER")

        input(
            "\nIf that reverse Cartesian route looked clean, press ENTER for "
            "PICK_TRANSFER -> PICK_ABOVE..."
        )

        move_cartesian_linear(
            arm,
            PICK_ABOVE_TCP,
            "PICK_ABOVE",
        )

        read_pose(arm, "AT PICK_ABOVE")

        print()
        print("==============================================")
        print("REVERSE ROUTE TEST COMPLETE")
        print("==============================================")
        print()
        print("Robot is now at PICK_ABOVE.")

        answer = input(
            "\nType P and press ENTER to also test the final PICK descent "
            "and close G2 to 10 mm, or just press ENTER to stop here: "
        ).strip().lower()

        if answer == "p":
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

            print()
            print("Pickup closed.")
            print("Robot will remain at PICK.")

        else:
            print()
            print("Stopping at PICK_ABOVE.")

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
