from xarm.wrapper import XArmAPI
import time

ROBOT_IP = "192.168.1.208"

# Very slow/small movement for first tests
MOVE_DISTANCE = 10   # mm
SPEED = 20           # mm/s


arm = XArmAPI(ROBOT_IP, is_radian=False)

try:
    # --------------------------------------------------
    # 1. CONNECTION TEST
    # --------------------------------------------------

    print("\n=== CONNECTION ===")

    if not arm.connected:
        print("Could not connect to robot.")
        raise SystemExit

    print("Connected!")

    print("Version:", arm.get_version())
    print("State:", arm.get_state())
    print("Errors / warnings:", arm.get_err_warn_code())

    print("\n=== CURRENT TCP POSITION ===")

    position = arm.get_position(is_radian=False)
    print(position)

    print("\nFormat:")
    print("[X, Y, Z, Roll, Pitch, Yaw]")

    print("\n=== CURRENT JOINT ANGLES ===")
    print(arm.get_servo_angle(is_radian=False))

    # Do NOT automatically clear errors during our first tests.
    if arm.error_code != 0:
        print(f"\nRobot has error code {arm.error_code}.")
        print("Not attempting movement.")
        raise SystemExit

    # --------------------------------------------------
    # 2. PREPARE ROBOT FOR CARTESIAN MOVEMENT
    # --------------------------------------------------

    input(
        "\nPress ENTER to enable the robot for movement.\n"
        "Make sure the robot has space around it first..."
    )

    ret = arm.motion_enable(enable=True)
    print("motion_enable:", ret)

    ret = arm.set_mode(0)
    print("set_mode(0):", ret)

    ret = arm.set_state(state=0)
    print("set_state(0):", ret)

    time.sleep(1)

    print("\nReady.")
    print("TCP:", arm.get_position(is_radian=False))

    # --------------------------------------------------
    # 3. TEST +Y
    # --------------------------------------------------

    input(
        f"\nPress ENTER to move +Y by {MOVE_DISTANCE} mm..."
    )

    ret = arm.set_position(
        0,
        MOVE_DISTANCE,
        0,
        0,
        0,
        0,
        speed=SPEED,
        relative=True,
        wait=True,
        is_radian=False,
    )

    print("Move result:", ret)
    print("TCP:", arm.get_position(is_radian=False))

    # --------------------------------------------------
    # 4. RETURN -Y
    # --------------------------------------------------

    input(
        f"\nPress ENTER to return -Y by {MOVE_DISTANCE} mm..."
    )

    ret = arm.set_position(
        0,
        -MOVE_DISTANCE,
        0,
        0,
        0,
        0,
        speed=SPEED,
        relative=True,
        wait=True,
        is_radian=False,
    )

    print("Move result:", ret)
    print("TCP:", arm.get_position(is_radian=False))

    # --------------------------------------------------
    # 5. TEST +X
    #
    # Your wall is on -X, so +X should move AWAY from it.
    # --------------------------------------------------

    input(
        f"\nPress ENTER to move +X by {MOVE_DISTANCE} mm "
        "(AWAY from the wall)..."
    )

    ret = arm.set_position(
        MOVE_DISTANCE,
        0,
        0,
        0,
        0,
        0,
        speed=SPEED,
        relative=True,
        wait=True,
        is_radian=False,
    )

    print("Move result:", ret)
    print("TCP:", arm.get_position(is_radian=False))

    # --------------------------------------------------
    # 6. RETURN TO ORIGINAL X
    # --------------------------------------------------

    input(
        f"\nPress ENTER to return -X by {MOVE_DISTANCE} mm..."
    )

    ret = arm.set_position(
        -MOVE_DISTANCE,
        0,
        0,
        0,
        0,
        0,
        speed=SPEED,
        relative=True,
        wait=True,
        is_radian=False,
    )

    print("Move result:", ret)
    print("TCP:", arm.get_position(is_radian=False))

    print("\nTest complete.")

finally:
    print("\nDisconnecting...")
    arm.disconnect()