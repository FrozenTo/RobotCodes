import math
import time

import pygame

from xarm.wrapper import XArmAPI


# =========================================================
# SETTINGS
# =========================================================

ROBOT_IP = "192.168.1.208"

# Stick must move this far before robot responds
STICK_DEADZONE = 0.15

# Maximum TCP speed at full stick
# Start conservatively for first test.
MAX_TCP_SPEED = 80.0        # mm/s

# Each velocity command expires after this many seconds
# unless another command arrives.
VELOCITY_TIMEOUT = 0.5

# Main controller loop
LOOP_INTERVAL = 0.02        # 50 Hz

TCP_MAX_ACC = 400.0
# =========================================================
# G2 GRIPPER SETTINGS
# =========================================================

GRIPPER_MIN = 0.0           # fully closed
GRIPPER_MAX = 84.0          # fully open

# How quickly our trigger control changes target position
GRIPPER_RATE = 40.0         # mm/s at full trigger

# Speed sent to G2 itself
GRIPPER_SPEED = 100         # valid: 15-225 mm/s

GRIPPER_FORCE = 50          # valid: 1-100

# Don't send a new gripper command on every 20 ms loop.
GRIPPER_SEND_INTERVAL = 0.08

TRIGGER_DEADZONE = 0.10

DPAD_HAT = 0

J56_SPEED = 20.0          # degrees/sec
JOINT_VELOCITY_TIMEOUT = 0.5
JOINT_MAX_ACC = 100.0     # degrees/sec²

velocity_mode = 5
dpad_joint_active = False
# =========================================================
# XBOX CONTROLLER MAPPING
# =========================================================

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

BUTTON_L3 = 8
BUTTON_R3 = 9


# =========================================================
# HELPERS
# =========================================================
def switch_velocity_mode(new_mode):
    global velocity_mode

    if velocity_mode == new_mode:
        return True

    try:
        # Stop whichever velocity mode is currently active first
        if velocity_mode == 5:
            arm.vc_set_cartesian_velocity(
                [0, 0, 0, 0, 0, 0],
                is_tool_coord=False,
                duration=VELOCITY_TIMEOUT
            )

        elif velocity_mode == 4:
            arm.vc_set_joint_velocity(
                [0, 0, 0, 0, 0, 0],
                is_sync=True,
                duration=JOINT_VELOCITY_TIMEOUT
            )

        code = arm.set_mode(new_mode)

        if code != 0:
            print("Mode change error:", code)
            return False

        arm.set_state(0)

        time.sleep(0.05)

        velocity_mode = new_mode

        return True

    except Exception as e:
        print("Mode switch error:", e)
        return False
    
def update_dpad_joints():

    global dpad_joint_active

    if controller.get_numhats() == 0:
        return False

    dpad_x, dpad_y = controller.get_hat(DPAD_HAT)

    # D-pad released
    if dpad_x == 0 and dpad_y == 0:

        if dpad_joint_active:

            try:
                arm.vc_set_joint_velocity(
                    [0, 0, 0, 0, 0, 0],
                    is_sync=True,
                    duration=JOINT_VELOCITY_TIMEOUT
                )
            except Exception:
                pass

            dpad_joint_active = False

            switch_velocity_mode(5)

            print("Back to Cartesian mode")

        return False


    # D-pad is controlling J5/J6
    if not dpad_joint_active:

        if not switch_velocity_mode(4):
            return True

        try:
            arm.set_joint_maxacc(
                JOINT_MAX_ACC
            )
        except Exception as e:
            print("Joint acceleration error:", e)

        dpad_joint_active = True

        print("D-pad joint control")


    # xArm 850 / 6-axis speed list:
    #
    # [J1, J2, J3, J4, J5, J6]
    joint_speeds = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0
    ]

    # Up / down -> J5
    #
    # Up    = J5+
    # Down  = J5-
    joint_speeds[4] = (
        dpad_y * J56_SPEED
    )

    # Left / right -> J6
    #
    # Right = J6+
    # Left  = J6-
    joint_speeds[5] = (
        dpad_x * J56_SPEED
    )

    code = arm.vc_set_joint_velocity(
        joint_speeds,
        is_sync=True,
        duration=JOINT_VELOCITY_TIMEOUT
    )

    if code == 1:
        latch_motion_fault(code)

    elif code != 0:
        print(
            "Joint velocity command code:",
            code
        )

    return True

def apply_deadzone(value, deadzone):
    """
    Removes deadzone and rescales the remaining range
    back to 0...1.
    """

    magnitude = abs(value)

    if magnitude <= deadzone:
        return 0.0

    scaled = (
        (magnitude - deadzone)
        / (1.0 - deadzone)
    )

    return math.copysign(
        scaled,
        value
    )


def trigger_amount(raw_value):
    """
    Xbox trigger:
        released = -1
        full      = +1

    Convert to:
        released = 0
        full      = 1
    """

    amount = (
        raw_value + 1.0
    ) / 2.0

    amount = max(
        0.0,
        min(
            1.0,
            amount
        )
    )

    if amount <= TRIGGER_DEADZONE:
        return 0.0

    # Rescale after deadzone
    return (
        amount - TRIGGER_DEADZONE
    ) / (
        1.0 - TRIGGER_DEADZONE
    )


# =========================================================
# CONNECT TO XARM
# =========================================================

print("Connecting to xArm 850...")

arm = XArmAPI(
    ROBOT_IP,
    is_radian=False
)

arm.connect()

print(
    "Connected:",
    arm.connected
)

print(
    "Clean warning:",
    arm.clean_warn()
)

print(
    "Clean error:",
    arm.clean_error()
)


# =========================================================
# COLLISION PROTECTION
# =========================================================

# Tool type 9 = xArm Gripper G2
try:

    print(
        "G2 collision model:",
        arm.set_collision_tool_model(9)
    )

except Exception as e:

    print(
        "Could not set G2 collision model:",
        e
    )


try:

    print(
        "Self-collision detection:",
        arm.set_self_collision_detection(True)
    )

except Exception as e:

    print(
        "Could not enable self-collision detection:",
        e
    )


# =========================================================
# ENABLE ROBOT
# =========================================================

print(
    "Motion enable:",
    arm.motion_enable(
        enable=True
    )
)

# Mode 5 = Cartesian velocity mode
print(
    "Set mode 5:",
    arm.set_mode(5)
)

print(
    "Set state 0:",
    arm.set_state(0)
)

print(
    "TCP max acceleration:",
    arm.set_tcp_maxacc(TCP_MAX_ACC)
)

time.sleep(0.5)


# =========================================================
# READ INITIAL G2 POSITION
# =========================================================

gripper_target = GRIPPER_MAX

try:

    result = arm.get_gripper_g2_position()

    print(
        "G2 position result:",
        result
    )

    if (
        isinstance(result, (tuple, list))
        and len(result) >= 2
        and result[0] == 0
    ):

        gripper_target = float(
            result[1]
        )

except Exception as e:

    print(
        "Could not read G2 position:",
        e
    )


gripper_target = max(
    GRIPPER_MIN,
    min(
        GRIPPER_MAX,
        gripper_target
    )
)

last_gripper_sent = gripper_target
last_gripper_send_time = 0.0


print(
    f"Initial G2 target: "
    f"{gripper_target:.1f} mm"
)


# =========================================================
# CONTROLLER
# =========================================================

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:

    print("No controller detected.")

    arm.motion_enable(
        enable=False
    )

    arm.disconnect()

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
print("xArm CONTROLLER ACTIVE")
print("----------------------")

print()
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
print("Diagonal / combined movement is supported.")

print()
print("L2         = Open G2")
print("R2         = Close G2")

print()
print("A          = STOP")
print("B          = Disable + Exit")

print()
print(
    f"Maximum TCP speed: "
    f"{MAX_TCP_SPEED:.0f} mm/s"
)

print()


# =========================================================
# STATE
# =========================================================

running = True

stop_latched = False

a_was_pressed = False
b_was_pressed = False

currently_moving = False

smoothed_vx = 0.0
smoothed_vy = 0.0
smoothed_vz = 0.0

VELOCITY_SMOOTHING = 0.25

fault_latched = False
fault_error_code = 0

x_was_pressed = False

# =========================================================
# VELOCITY CONTROL
# =========================================================

def send_velocity(
    vx,
    vy,
    vz
):

    global currently_moving

    code = arm.vc_set_cartesian_velocity(
        [
            vx,
            vy,
            vz,
            0,
            0,
            0
        ],
        is_tool_coord=False,
        duration=VELOCITY_TIMEOUT
    )

    currently_moving = (
        abs(vx) > 0.01
        or abs(vy) > 0.01
        or abs(vz) > 0.01
    )

    return code


def stop_robot():

    global currently_moving

    if fault_latched:
        currently_moving = False
        return

    try:

        if velocity_mode == 4:

            arm.vc_set_joint_velocity(
                [0, 0, 0, 0, 0, 0],
                is_sync=True,
                duration=JOINT_VELOCITY_TIMEOUT
            )

        else:

            arm.vc_set_cartesian_velocity(
                [0, 0, 0, 0, 0, 0],
                is_tool_coord=False,
                duration=VELOCITY_TIMEOUT
            )

    except Exception as e:
        print("STOP error:", e)

    currently_moving = False


# =========================================================
# XYZ STICK -> VELOCITY
# =========================================================

def get_xyz_velocity():

    right_x = apply_deadzone(
        controller.get_axis(
            RIGHT_X
        ),
        STICK_DEADZONE
    )

    right_y = apply_deadzone(
        controller.get_axis(
            RIGHT_Y
        ),
        STICK_DEADZONE
    )

    left_y = apply_deadzone(
        controller.get_axis(
            LEFT_Y
        ),
        STICK_DEADZONE
    )

    # -----------------------------------------------------
    # Mapping
    #
    # Right stick up:
    #   raw Y is negative
    #   want X negative
    #
    # Therefore:
    #   vx = right_y
    #
    # Right stick horizontal:
    #   left = negative Y
    #   right = positive Y
    #
    # Left stick up:
    #   raw = negative
    #   want Z positive
    #
    # Therefore:
    #   vz = -left_y
    # -----------------------------------------------------

    x_component = right_y

    y_component = right_x

    z_component = -left_y


    # -----------------------------------------------------
    # Normalise combined XYZ vector
    #
    # Without this:
    # X=100 + Y=100 would give
    # ~141 mm/s diagonally.
    #
    # This caps total TCP velocity at MAX_TCP_SPEED.
    # -----------------------------------------------------

    magnitude = math.sqrt(
        x_component ** 2
        + y_component ** 2
        + z_component ** 2
    )

    if magnitude > 1.0:

        x_component /= magnitude
        y_component /= magnitude
        z_component /= magnitude


    vx = (
        x_component
        * MAX_TCP_SPEED
    )

    vy = (
        y_component
        * MAX_TCP_SPEED
    )

    vz = (
        z_component
        * MAX_TCP_SPEED
    )

    return (
        vx,
        vy,
        vz
    )


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

#========================================================
# Fault handler
#========================================================
def latch_motion_fault(api_code):

    global fault_latched
    global fault_error_code
    global currently_moving

    if fault_latched:
        return

    fault_latched = True
    currently_moving = False

    # Give report data a moment to update
    time.sleep(0.05)

    try:
        status = arm.get_err_warn_code()

        print()
        print("==============================")
        print("ROBOT MOTION FAULT")
        print("API return code:", api_code)
        print("Error/warn result:", status)
        print("Controller error:", arm.error_code)
        print("Controller warning:", arm.warn_code)

        fault_error_code = arm.error_code

        if fault_error_code == 22:
            print("SELF-COLLISION DETECTED")

        print()
        print("Center the sticks.")
        print("Press X to clear/recover.")
        print("==============================")
        print()

    except Exception as e:
        print("Could not read robot error:", e)


def recover_robot():

    global fault_latched
    global fault_error_code
    global stop_latched

    global smoothed_vx
    global smoothed_vy
    global smoothed_vz

    if not fault_latched:
        print("No robot fault to recover.")
        return

    if not sticks_centered():
        print("Center sticks before recovery.")
        return

    print()
    print("Attempting robot recovery...")

    try:

        print(
            "Clean error:",
            arm.clean_error()
        )

        print(
            "Clean warning:",
            arm.clean_warn()
        )

        time.sleep(0.2)

        print(
            "Motion enable:",
            arm.motion_enable(
                enable=True
            )
        )

        # Restore Cartesian velocity mode
        print(
            "Set mode 5:",
            arm.set_mode(5)
        )

        print(
            "Set state 0:",
            arm.set_state(0)
        )

        # Restore our smooth velocity acceleration
        print(
            "TCP max acceleration:",
            arm.set_tcp_maxacc(
                TCP_MAX_ACC
            )
        )

        time.sleep(0.3)

        # Refresh status
        status = arm.get_err_warn_code()

        print(
            "Error/warn after recovery:",
            status
        )

        if arm.error_code != 0:

            print(
                "Recovery failed. "
                f"Error is still {arm.error_code}"
            )

            return

        fault_latched = False
        fault_error_code = 0

        smoothed_vx = 0.0
        smoothed_vy = 0.0
        smoothed_vz = 0.0

        # Stick must leave center again before moving.
        stop_latched = True

        print("Robot recovered.")
        print("Move away from the collision area.")
        print()

    except Exception as e:

        print(
            "Recovery error:",
            e
        )
# =========================================================
# G2 GRIPPER
# =========================================================

def update_gripper(dt):

    global gripper_target
    global last_gripper_sent
    global last_gripper_send_time

    l2 = trigger_amount(
        controller.get_axis(
            L2_AXIS
        )
    )

    r2 = trigger_amount(
        controller.get_axis(
            R2_AXIS
        )
    )

    # L2 opens -> toward 84
    # R2 closes -> toward 0

    gripper_velocity = (
        l2 - r2
    ) * GRIPPER_RATE

    if abs(gripper_velocity) < 0.01:
        return

    gripper_target += (
        gripper_velocity
        * dt
    )

    gripper_target = max(
        GRIPPER_MIN,
        min(
            GRIPPER_MAX,
            gripper_target
        )
    )


    now = time.monotonic()

    if (
        now - last_gripper_send_time
        < GRIPPER_SEND_INTERVAL
    ):

        return


    # Don't resend effectively identical positions
    if (
        abs(
            gripper_target
            - last_gripper_sent
        )
        < 1.0
    ):

        return


    target = int(
        round(
            gripper_target
        )
    )

    try:

        code = arm.set_gripper_g2_position(
            target,
            speed=GRIPPER_SPEED,
            force=GRIPPER_FORCE,
            wait=False
        )

        if code == 0:

            last_gripper_sent = (
                gripper_target
            )

            print(
                f"G2: {target} mm"
            )

        else:

            print(
                "G2 command code:",
                code
            )

    except Exception as e:

        print(
            "G2 error:",
            e
        )

    last_gripper_send_time = now


# =========================================================
# MAIN LOOP
# =========================================================

last_loop_time = time.monotonic()

try:

    while running:

        pygame.event.pump()

        # -------------------------------------------------
        # Controller disconnect
        # -------------------------------------------------

        if (
            hasattr(
                controller,
                "get_attached"
            )
            and not controller.get_attached()
        ):

            print(
                "Controller disconnected."
            )

            stop_robot()

            break


        now = time.monotonic()

        dt = (
            now
            - last_loop_time
        )

        last_loop_time = now

        # =================================================
        # D-PAD = J5 / J6
        # =================================================

        if not fault_latched:

            if update_dpad_joints():

                # D-pad takes priority over XYZ sticks
                time.sleep(LOOP_INTERVAL)
                continue

        # =================================================
        # BUTTONS
        # =================================================

        a_pressed = bool(
            controller.get_button(
                BUTTON_A
            )
        )

        b_pressed = bool(
            controller.get_button(
                BUTTON_B
            )
        )

        x_pressed = bool(
            controller.get_button(
                BUTTON_X
            )
        )
        # =================================================
        # A = STOP
        # =================================================

        if (
            a_pressed
            and not a_was_pressed
        ):

            stop_robot()

            stop_latched = True

            print(
                "A -> STOP"
            )


        # =================================================
        # B = EXIT
        # =================================================

        if (
            b_pressed
            and not b_was_pressed
        ):

            print(
                "B -> Disable + Exit"
            )

            stop_robot()

            running = False

            continue
        
        # =================================================
        # X = RECOVER FROM ROBOT ERROR
        # =================================================

        if (
            x_pressed
            and not x_was_pressed
        ):

            recover_robot()
            
        a_was_pressed = a_pressed
        b_was_pressed = b_pressed
        x_was_pressed = x_pressed
        # =================================================
        # X = RECOVER FROM ROBOT ERROR
        # =================================================

        if (
            x_pressed
            and not x_was_pressed
        ):

            recover_robot()

        # =================================================
        # G2 GRIPPER
        # =================================================

        update_gripper(
            dt
        )


        # =================================================
        # STOP LATCH
        # =================================================

        if stop_latched:

            stop_robot()

            if sticks_centered():

                stop_latched = False

                print(
                    "Movement re-armed"
                )

            time.sleep(
                LOOP_INTERVAL
            )

            continue


        # =================================================
        # XYZ VELOCITY
        # =================================================
        if fault_latched:

            time.sleep(
                LOOP_INTERVAL
            )

            continue
        vx, vy, vz = (
            get_xyz_velocity()
        )

# Completely centered -> stop immediately.
        if (
            abs(vx) < 0.01
            and abs(vy) < 0.01
            and abs(vz) < 0.01
        ):

            smoothed_vx = 0.0
            smoothed_vy = 0.0
            smoothed_vz = 0.0

            stop_robot()

        else:

            # Smooth changes in requested velocity.
            smoothed_vx += (
                vx - smoothed_vx
            ) * VELOCITY_SMOOTHING

            smoothed_vy += (
                vy - smoothed_vy
            ) * VELOCITY_SMOOTHING

            smoothed_vz += (
                vz - smoothed_vz
            ) * VELOCITY_SMOOTHING

            code = send_velocity(
                smoothed_vx,
                smoothed_vy,
                smoothed_vz
            )

            if code == 1:

                latch_motion_fault(code)

            elif code != 0:

                print(
                    "Velocity command code:",
                    code
                )

        time.sleep(
            LOOP_INTERVAL
        )


except KeyboardInterrupt:

    print(
        "\nKeyboard interrupt."
    )


finally:

    print(
        "Stopping xArm..."
    )

    try:
        stop_robot()
    except Exception:
        pass

    time.sleep(0.1)

    try:

        print(
            "Motion disable:",
            arm.motion_enable(
                enable=False
            )
        )

    except Exception:
        pass

    try:

        arm.disconnect()

    except Exception:
        pass

    pygame.quit()

    print(
        "Robot stopped and disconnected."
    )
    