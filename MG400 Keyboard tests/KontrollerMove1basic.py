import pygame
import time

from dobot_api import DobotApiDashboard, DobotApiMove


# =========================================================
# SETTINGS
# =========================================================

ROBOT_IP = "192.168.2.6"

SPEED_FACTOR = 20

STICK_DEADZONE = 0.25

TRIGGER_THRESHOLD = 0.5


# Controller mapping
LEFT_X = 0
LEFT_Y = 1

RIGHT_X = 2
RIGHT_Y = 3

L2_AXIS = 4
R2_AXIS = 5

BUTTON_A = 0
BUTTON_B = 1
BUTTON_X = 2
BUTTON_Y = 3

BUTTON_L1 = 4
BUTTON_R1 = 5


# =========================================================
# ROBOT CONNECTION
# =========================================================

print("Connecting to MG400...")

dashboard = DobotApiDashboard(
    ROBOT_IP,
    29999
)

move = DobotApiMove(
    ROBOT_IP,
    30003
)

print(
    "ClearError:",
    dashboard.ClearError()
)

time.sleep(1)

print(
    "EnableRobot:",
    dashboard.EnableRobot()
)

time.sleep(0.5)

print(
    "SpeedFactor:",
    dashboard.SpeedFactor(
        SPEED_FACTOR
    )
)


# =========================================================
# CONTROLLER
# =========================================================

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No controller detected.")

    try:
        dashboard.DisableRobot()
    except Exception:
        pass

    pygame.quit()

    raise SystemExit


controller = pygame.joystick.Joystick(0)
controller.init()

print()
print(
    "Controller:",
    controller.get_name()
)

print()
print("MG400 CONTROLLER ACTIVE")
print("------------------------")

print("Right stick:")
print("  Up       = X-")
print("  Down     = X+")
print("  Left     = Y-")
print("  Right    = Y+")

print()
print("Left stick:")
print("  Up       = Z+")
print("  Down     = Z-")

print()
print("A          = STOP")
print("B          = Disable robot")
print("L2         = Toggle Tool 1")
print("R2         = Toggle Tool 2")

print()
print("Ctrl+C     = Exit")

print()


# =========================================================
# STATE
# =========================================================

current_direction = None

tool1_on = False
tool2_on = False

l2_was_pressed = False
r2_was_pressed = False

stop_latched = False

running = True


# =========================================================
# FUNCTIONS
# =========================================================

def stop_robot():
    global current_direction

    if current_direction is None:
        return

    try:
        move.MoveJog()
    except Exception as e:
        print("STOP error:", e)

    current_direction = None

    print("STOP")


def start_jog(direction):
    global current_direction

    if direction == current_direction:
        return

    # Stop previous direction first.
    if current_direction is not None:
        try:
            move.MoveJog()
        except Exception:
            pass

    try:
        move.MoveJog(direction)

        current_direction = direction

        print("Jog:", direction)

    except Exception as e:
        print("Jog error:", e)


def set_tool1(state):
    global tool1_on

    try:
        dashboard.DO(
            1,
            1 if state else 0
        )

        tool1_on = state

        print(
            "Tool 1:",
            "ON" if state else "OFF"
        )

    except Exception as e:
        print("Tool 1 error:", e)


def set_tool2(state):
    global tool2_on

    try:
        dashboard.DO(
            2,
            1 if state else 0
        )

        tool2_on = state

        print(
            "Tool 2:",
            "ON" if state else "OFF"
        )

    except Exception as e:
        print("Tool 2 error:", e)


def get_movement():

    right_x = controller.get_axis(
        RIGHT_X
    )

    right_y = controller.get_axis(
        RIGHT_Y
    )

    left_y = controller.get_axis(
        LEFT_Y
    )

    candidates = []

    # ------------------------------
    # X
    # ------------------------------

    if abs(right_y) >= STICK_DEADZONE:

        if right_y < 0:
            candidates.append(
                (
                    abs(right_y),
                    "X-"
                )
            )

        else:
            candidates.append(
                (
                    abs(right_y),
                    "X+"
                )
            )

    # ------------------------------
    # Y
    # ------------------------------

    if abs(right_x) >= STICK_DEADZONE:

        if right_x < 0:
            candidates.append(
                (
                    abs(right_x),
                    "Y-"
                )
            )

        else:
            candidates.append(
                (
                    abs(right_x),
                    "Y+"
                )
            )

    # ------------------------------
    # Z
    # ------------------------------

    if abs(left_y) >= STICK_DEADZONE:

        if left_y < 0:
            candidates.append(
                (
                    abs(left_y),
                    "Z+"
                )
            )

        else:
            candidates.append(
                (
                    abs(left_y),
                    "Z-"
                )
            )

    if not candidates:
        return None

    # Strongest stick direction wins
    candidates.sort(
        reverse=True,
        key=lambda item: item[0]
    )

    return candidates[0][1]


def sticks_centered():

    return (
        abs(
            controller.get_axis(
                RIGHT_X
            )
        ) < STICK_DEADZONE

        and

        abs(
            controller.get_axis(
                RIGHT_Y
            )
        ) < STICK_DEADZONE

        and

        abs(
            controller.get_axis(
                LEFT_Y
            )
        ) < STICK_DEADZONE
    )


# =========================================================
# MAIN LOOP
# =========================================================

try:

    while running:

        pygame.event.pump()

        # =============================================
        # A = STOP
        # =============================================

        if controller.get_button(
            BUTTON_A
        ):

            stop_robot()

            # Don't immediately start again because
            # a stick is still being held.
            stop_latched = True

        # After STOP, sticks must return to center
        # before movement becomes active again.

        if stop_latched:

            if sticks_centered():
                stop_latched = False

        else:

            direction = get_movement()

            if direction is None:

                stop_robot()

            else:

                start_jog(
                    direction
                )

        # =============================================
        # B = DISABLE
        # =============================================

        if controller.get_button(
            BUTTON_B
        ):

            print(
                "B -> Disable robot"
            )

            stop_robot()

            set_tool1(False)
            set_tool2(False)

            dashboard.DisableRobot()

            running = False

            continue

        # =============================================
        # L2 = TOOL 1 TOGGLE
        # =============================================

        l2_value = controller.get_axis(
            L2_AXIS
        )

        l2_pressed = (
            l2_value
            > TRIGGER_THRESHOLD
        )

        if (
            l2_pressed
            and not l2_was_pressed
        ):

            set_tool1(
                not tool1_on
            )

        l2_was_pressed = l2_pressed

        # =============================================
        # R2 = TOOL 2 TOGGLE
        # =============================================

        r2_value = controller.get_axis(
            R2_AXIS
        )

        r2_pressed = (
            r2_value
            > TRIGGER_THRESHOLD
        )

        if (
            r2_pressed
            and not r2_was_pressed
        ):

            set_tool2(
                not tool2_on
            )

        r2_was_pressed = r2_pressed

        # Around 100 Hz controller polling
        time.sleep(0.01)


except KeyboardInterrupt:

    print("\nKeyboard interrupt.")


finally:

    print("Stopping...")

    try:
        move.MoveJog()
    except Exception:
        pass

    try:
        dashboard.DO(1, 0)
        dashboard.DO(2, 0)
    except Exception:
        pass

    try:
        dashboard.DisableRobot()
    except Exception:
        pass

    pygame.quit()

    print(
        "Robot stopped and disabled."
    )