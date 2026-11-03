from xarm.wrapper import XArmAPI
import time

ROBOT_IP = "192.168.1.208"

STEP = 5       # mm
SPEED = 20     # mm/s


def print_pose(arm):
    code, pose = arm.get_position(is_radian=False)

    if code != 0:
        print(f"Could not read TCP pose. Code: {code}")
        return

    x, y, z, roll, pitch, yaw = pose

    print("\nCurrent TCP:")
    print(f"X     = {x:.3f} mm")
    print(f"Y     = {y:.3f} mm")
    print(f"Z     = {z:.3f} mm")
    print(f"Roll  = {roll:.3f}°")
    print(f"Pitch = {pitch:.3f}°")
    print(f"Yaw   = {yaw:.3f}°")


def move_relative(arm, dx=0, dy=0, dz=0):
    ret = arm.set_position(
        dx,
        dy,
        dz,
        0,
        0,
        0,
        speed=SPEED,
        relative=True,
        wait=True,
        is_radian=False,
    )

    if ret == 0:
        print("Move successful.")
        print_pose(arm)
    else:
        print(f"Movement failed. Return code: {ret}")


arm = XArmAPI(ROBOT_IP, is_radian=False)

try:
    print("\n=== UFACTORY 850 MANUAL JOG TEST ===")

    if not arm.connected:
        print("Could not connect to robot.")
        raise SystemExit

    print("Connected.")
    print("Errors / warnings:", arm.get_err_warn_code())

    if arm.error_code != 0:
        print(f"Robot has error code {arm.error_code}.")
        raise SystemExit

    print_pose(arm)

    input("\nPress ENTER to enable movement...")

    print("motion_enable:", arm.motion_enable(enable=True))
    print("set_mode:", arm.set_mode(0))
    print("set_state:", arm.set_state(0))

    time.sleep(1)

    print(
        "\nCommands:\n"
        "\n"
        "  y+   = +Y   writing direction\n"
        "  y-   = -Y\n"
        "\n"
        "  z+   = +Z\n"
        "  z-   = -Z\n"
        "\n"
        "  x+   = +X   AWAY from wall\n"
        "  x-   = -X   TOWARD wall\n"
        "\n"
        "  p    = print current TCP pose\n"
        "  q    = quit\n"
        "\n"
        f"Current movement step: {STEP} mm\n"
    )

    while True:
        command = input("Command: ").strip().lower()

        if command == "q":
            break

        elif command == "p":
            print_pose(arm)

        elif command == "y+":
            move_relative(arm, dy=STEP)

        elif command == "y-":
            move_relative(arm, dy=-STEP)

        elif command == "z+":
            move_relative(arm, dz=STEP)

        elif command == "z-":
            move_relative(arm, dz=-STEP)

        elif command == "x+":
            move_relative(arm, dx=STEP)

        elif command == "x-":
            print("\nWARNING: -X moves TOWARD the wall.")
            confirm = input(
                f"Move {STEP} mm toward wall? (y/n): "
            ).strip().lower()

            if confirm == "y":
                move_relative(arm, dx=-STEP)
            else:
                print("Cancelled.")

        else:
            print("Unknown command.")

finally:
    print("\nDisconnecting...")
    arm.disconnect()