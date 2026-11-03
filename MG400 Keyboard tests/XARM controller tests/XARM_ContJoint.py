import math
import time

import pygame

from xarm.wrapper import XArmAPI


# =========================================================
# SETTINGS
# =========================================================

ROBOT_IP = "192.168.1.208"

STICK_DEADZONE = 0.15

LOOP_INTERVAL = 0.02

# Cartesian velocity
MAX_TCP_SPEED = 80.0          # mm/s
TCP_MAX_ACC = 400.0           # mm/s^2
VELOCITY_TIMEOUT = 0.5
VELOCITY_SMOOTHING = 0.25

# Joint velocity
MAX_JOINT_SPEED = 20.0        # deg/s for J1-J4
J56_SPEED = 20.0              # deg/s for D-pad J5/J6
JOINT_MAX_ACC = 100.0         # deg/s^2
JOINT_VELOCITY_TIMEOUT = 0.5
JOINT_SMOOTHING = 0.25


# =========================================================
# G2 GRIPPER
# =========================================================

GRIPPER_MIN = 0.0
GRIPPER_MAX = 84.0

GRIPPER_RATE = 40.0

GRIPPER_SPEED = 100
GRIPPER_FORCE = 50

GRIPPER_SEND_INTERVAL = 0.08

TRIGGER_DEADZONE = 0.10


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

DPAD_HAT = 0


# =========================================================
# HELPERS
# =========================================================

def apply_deadzone(value, deadzone):

    magnitude = abs(value)

    if magnitude <= deadzone:
        return 0.0

    scaled = (
        (magnitude - deadzone)
        /
        (1.0 - deadzone)
    )

    return math.copysign(
        scaled,
        value
    )


def trigger_amount(raw_value):

    # Xbox trigger:
    # -1 = released
    # +1 = full press

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

    return (
        amount - TRIGGER_DEADZONE
    ) / (
        1.0 - TRIGGER_DEADZONE
    )


# =========================================================
# CONNECT
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

try:

    print(
        "G2 collision model:",
        arm.set_collision_tool_model(9)
    )

except Exception as e:

    print(
        "Collision model error:",
        e
    )


try:

    print(
        "Self-collision detection:",
        arm.set_self_collision_detection(True)
    )

except Exception as e:

    print(
        "Self-collision setup error:",
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

# Start in Cartesian velocity mode
print(
    "Mode 5:",
    arm.set_mode(5)
)

print(
    "State 0:",
    arm.set_state(0)
)

print(
    "TCP max acceleration:",
    arm.set_tcp_maxacc(
        TCP_MAX_ACC
    )
)

print(
    "Joint max acceleration:",
    arm.set_joint_maxacc(
        JOINT_MAX_ACC
    )
)

time.sleep(0.5)


# =========================================================
# G2 INITIAL POSITION
# =========================================================

gripper_target = GRIPPER_MAX

try:

    result = arm.get_gripper_g2_position()

    print(
        "G2 position:",
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
        "G2 read error:",
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
print("Controller:", controller.get_name())
print()
print("xArm CONTROLLER ACTIVE")
print("======================")
print()
print("XYZ MODE")
print("Right stick = X / Y")
print("Left stick  = Z")
print("D-pad ↑↓    = J5")
print("D-pad ←→    = J6")
print()
print("JOINT MODE")
print("L1 = select J1-J4")
print("J1/J4 = right stick ←→")
print("J2/J3 = right stick ↑↓")
print("D-pad ↑↓ = J5")
print("D-pad ←→ = J6")
print()
print("R1 = XYZ / JOINT")
print()
print("L2 = Open G2")
print("R2 = Close G2")
print()
print("A = STOP")
print("X = Recover error")
print("B = Disable + Exit")
print()


# =========================================================
# STATE
# =========================================================

running = True

# User-facing control mode
control_mode = "XYZ"

selected_joint = 1

# Actual xArm velocity mode:
# 5 = Cartesian
# 4 = Joint
velocity_mode = 5

# Used when D-pad temporarily enters joint mode
# while control_mode is XYZ.
xyz_dpad_active = False

stop_latched = False

fault_latched = False
fault_error_code = 0

currently_moving = False


# Button edge states
a_was_pressed = False
b_was_pressed = False
x_was_pressed = False

l1_was_pressed = False
r1_was_pressed = False


# Cartesian smoothing
smoothed_vx = 0.0
smoothed_vy = 0.0
smoothed_vz = 0.0

# J1-J4 smoothing
smoothed_joint = [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0
]


# =========================================================
# RESET SMOOTHING
# =========================================================

def reset_smoothing():

    global smoothed_vx
    global smoothed_vy
    global smoothed_vz
    global smoothed_joint

    smoothed_vx = 0.0
    smoothed_vy = 0.0
    smoothed_vz = 0.0

    smoothed_joint = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0
    ]


# =========================================================
# CENTER CHECK
# =========================================================

def controls_centered():

    sticks_ok = (
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

    if controller.get_numhats() > 0:

        dpad_ok = (
            controller.get_hat(
                DPAD_HAT
            )
            ==
            (0, 0)
        )

    else:

        dpad_ok = True

    return (
        sticks_ok
        and dpad_ok
    )


# =========================================================
# STOP
# =========================================================

def stop_robot(force=False):

    global currently_moving

    if fault_latched:

        currently_moving = False
        return

    if (
        not currently_moving
        and not force
    ):
        return

    try:

        if velocity_mode == 4:

            arm.vc_set_joint_velocity(
                [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0
                ],
                is_sync=True,
                duration=JOINT_VELOCITY_TIMEOUT
            )

        else:

            arm.vc_set_cartesian_velocity(
                [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0
                ],
                is_tool_coord=False,
                duration=VELOCITY_TIMEOUT
            )

    except Exception as e:

        print(
            "STOP error:",
            e
        )

    if currently_moving:
        print("STOP")

    currently_moving = False

    reset_smoothing()


# =========================================================
# VELOCITY MODE SWITCH
# =========================================================

def switch_velocity_mode(new_mode):

    global velocity_mode
    global currently_moving

    if fault_latched:
        return False

    if velocity_mode == new_mode:
        return True

    stop_robot(
        force=True
    )

    try:

        code = arm.set_mode(
            new_mode
        )

        if code != 0:

            print(
                "Mode change error:",
                code
            )

            return False

        code = arm.set_state(0)

        if code != 0:

            print(
                "State change error:",
                code
            )

            return False

        velocity_mode = new_mode

        currently_moving = False

        reset_smoothing()

        time.sleep(0.05)

        return True

    except Exception as e:

        print(
            "Mode switch error:",
            e
        )

        return False


# =========================================================
# FAULT HANDLING
# =========================================================

def latch_motion_fault(api_code):

    global fault_latched
    global fault_error_code
    global currently_moving

    if fault_latched:
        return

    fault_latched = True
    currently_moving = False

    time.sleep(0.05)

    try:

        status = arm.get_err_warn_code()

        fault_error_code = arm.error_code

        print()
        print("==============================")
        print("ROBOT MOTION FAULT")
        print("API return code:", api_code)
        print("Error/warn:", status)
        print("Error code:", arm.error_code)
        print("Warning code:", arm.warn_code)

        if arm.error_code == 22:
            print("SELF-COLLISION DETECTED")

        print()
        print("Center all controls.")
        print("Press X to recover.")
        print("==============================")
        print()

    except Exception as e:

        print(
            "Error status read failed:",
            e
        )


def recover_robot():

    global fault_latched
    global fault_error_code
    global stop_latched
    global velocity_mode
    global xyz_dpad_active

    if not fault_latched:

        print(
            "No robot fault to recover."
        )

        return

    if not controls_centered():

        print(
            "Center controls before recovery."
        )

        return

    print()
    print("Attempting recovery...")

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

        # Restore mode based on selected control mode.
        desired_mode = (
            4
            if control_mode == "JOINT"
            else 5
        )

        print(
            "Set mode:",
            arm.set_mode(
                desired_mode
            )
        )

        print(
            "Set state:",
            arm.set_state(0)
        )

        print(
            "TCP max acceleration:",
            arm.set_tcp_maxacc(
                TCP_MAX_ACC
            )
        )

        print(
            "Joint max acceleration:",
            arm.set_joint_maxacc(
                JOINT_MAX_ACC
            )
        )

        time.sleep(0.3)

        status = arm.get_err_warn_code()

        print(
            "Error/warn after recovery:",
            status
        )

        if arm.error_code != 0:

            print(
                "Recovery failed. "
                f"Error remains {arm.error_code}"
            )

            return

        velocity_mode = desired_mode

        xyz_dpad_active = False

        fault_latched = False
        fault_error_code = 0

        stop_latched = True

        reset_smoothing()

        print("Robot recovered.")
        print()

    except Exception as e:

        print(
            "Recovery error:",
            e
        )


# =========================================================
# CONTROL MODE SWITCH
# =========================================================

def toggle_control_mode():

    global control_mode
    global stop_latched
    global xyz_dpad_active

    if fault_latched:
        return

    stop_robot(
        force=True
    )

    xyz_dpad_active = False

    if control_mode == "XYZ":

        if not switch_velocity_mode(4):
            return

        control_mode = "JOINT"

        print()
        print("====================")
        print("MODE: JOINT")
        print(
            f"Selected joint: J{selected_joint}"
        )
        print("====================")
        print()

    else:

        if not switch_velocity_mode(5):
            return

        control_mode = "XYZ"

        print()
        print("====================")
        print("MODE: XYZ")
        print("====================")
        print()

    stop_latched = True


def next_joint():

    global selected_joint
    global stop_latched

    if (
        fault_latched
        or control_mode != "JOINT"
    ):
        return

    stop_robot(
        force=True
    )

    selected_joint += 1

    if selected_joint > 4:
        selected_joint = 1

    stop_latched = True

    reset_smoothing()

    print(
        f"Selected joint: "
        f"J{selected_joint}"
    )


# =========================================================
# CARTESIAN VELOCITY
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


    x_component = right_y

    y_component = right_x

    z_component = -left_y


    # Cap combined XYZ magnitude to 1.
    magnitude = math.sqrt(
        x_component ** 2
        +
        y_component ** 2
        +
        z_component ** 2
    )

    if magnitude > 1.0:

        x_component /= magnitude
        y_component /= magnitude
        z_component /= magnitude


    return (
        x_component * MAX_TCP_SPEED,
        y_component * MAX_TCP_SPEED,
        z_component * MAX_TCP_SPEED
    )


def update_cartesian():

    global smoothed_vx
    global smoothed_vy
    global smoothed_vz
    global currently_moving

    vx, vy, vz = (
        get_xyz_velocity()
    )


    # Stick completely centered
    if (
        abs(vx) < 0.01
        and abs(vy) < 0.01
        and abs(vz) < 0.01
    ):

        stop_robot()
        return


    smoothed_vx += (
        vx - smoothed_vx
    ) * VELOCITY_SMOOTHING

    smoothed_vy += (
        vy - smoothed_vy
    ) * VELOCITY_SMOOTHING

    smoothed_vz += (
        vz - smoothed_vz
    ) * VELOCITY_SMOOTHING


    code = arm.vc_set_cartesian_velocity(
        [
            smoothed_vx,
            smoothed_vy,
            smoothed_vz,
            0,
            0,
            0
        ],
        is_tool_coord=False,
        duration=VELOCITY_TIMEOUT
    )

    if code == 1:

        latch_motion_fault(
            code
        )

        return

    if code != 0:

        print(
            "Cartesian velocity code:",
            code
        )

        return

    currently_moving = True


# =========================================================
# XYZ MODE D-PAD J5/J6
# =========================================================

def update_xyz_dpad():

    global xyz_dpad_active
    global stop_latched
    global currently_moving

    if controller.get_numhats() == 0:
        return False

    dpad_x, dpad_y = (
        controller.get_hat(
            DPAD_HAT
        )
    )


    # -----------------------------------------------------
    # D-pad released after temporary joint mode
    # -----------------------------------------------------

    if (
        dpad_x == 0
        and dpad_y == 0
    ):

        if xyz_dpad_active:

            stop_robot(
                force=True
            )

            xyz_dpad_active = False

            switch_velocity_mode(5)

            # Prevent held XYZ stick from immediately
            # taking off after releasing D-pad.
            stop_latched = True

            print(
                "Back to Cartesian control"
            )

            return True

        return False


    # -----------------------------------------------------
    # D-pad pressed
    # -----------------------------------------------------

    if not xyz_dpad_active:

        stop_robot(
            force=True
        )

        if not switch_velocity_mode(4):
            return True

        xyz_dpad_active = True

        print(
            "Temporary J5/J6 control"
        )


    joint_speeds = [
        0.0,
        0.0,
        0.0,
        0.0,

        # D-pad up/down
        dpad_y * J56_SPEED,

        # D-pad left/right
        dpad_x * J56_SPEED
    ]


    code = arm.vc_set_joint_velocity(
        joint_speeds,
        is_sync=True,
        duration=JOINT_VELOCITY_TIMEOUT
    )

    if code == 1:

        latch_motion_fault(
            code
        )

    elif code != 0:

        print(
            "J5/J6 velocity code:",
            code
        )

    else:

        currently_moving = True


    return True


# =========================================================
# JOINT MODE
# =========================================================

def get_joint_velocity_targets():

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


    targets = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0
    ]


    # -----------------------------------------------------
    # Selected J1-J4
    # -----------------------------------------------------

    if selected_joint == 1:

        # Left = J1-
        # Right = J1+
        targets[0] = (
            right_x
            * MAX_JOINT_SPEED
        )


    elif selected_joint == 2:

        # Up = J2-
        # Down = J2+
        targets[1] = (
            right_y
            * MAX_JOINT_SPEED
        )


    elif selected_joint == 3:

        # Up = J3-
        # Down = J3+
        targets[2] = (
            right_y
            * MAX_JOINT_SPEED
        )


    elif selected_joint == 4:

        # Left = J4-
        # Right = J4+
        targets[3] = (
            right_x
            * MAX_JOINT_SPEED
        )


    # -----------------------------------------------------
    # Dedicated J5/J6 D-pad
    # -----------------------------------------------------

    if controller.get_numhats() > 0:

        dpad_x, dpad_y = (
            controller.get_hat(
                DPAD_HAT
            )
        )

        # Up = J5+
        # Down = J5-
        targets[4] = (
            dpad_y
            * J56_SPEED
        )

        # Right = J6+
        # Left = J6-
        targets[5] = (
            dpad_x
            * J56_SPEED
        )


    return targets


def update_joint_mode():

    global smoothed_joint
    global currently_moving


    targets = (
        get_joint_velocity_targets()
    )


    # Smooth J1-J4 analog stick motion.
    for i in range(4):

        smoothed_joint[i] += (
            targets[i]
            -
            smoothed_joint[i]
        ) * JOINT_SMOOTHING


    # J5/J6 are digital D-pad inputs.
    # Stop immediately when released.
    smoothed_joint[4] = targets[4]
    smoothed_joint[5] = targets[5]


    moving = any(
        abs(value) > 0.01
        for value in smoothed_joint
    )


    if not moving:

        stop_robot()
        return


    code = arm.vc_set_joint_velocity(
        smoothed_joint,
        is_sync=True,
        duration=JOINT_VELOCITY_TIMEOUT
    )


    if code == 1:

        latch_motion_fault(
            code
        )

        return


    if code != 0:

        print(
            "Joint velocity code:",
            code
        )

        return


    currently_moving = True


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


    # L2 = open
    # R2 = close

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
        <
        GRIPPER_SEND_INTERVAL
    ):
        return


    if (
        abs(
            gripper_target
            -
            last_gripper_sent
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

last_loop_time = (
    time.monotonic()
)


try:

    while running:

        pygame.event.pump()


        # =================================================
        # CONTROLLER CONNECTION
        # =================================================

        if (
            hasattr(
                controller,
                "get_attached"
            )
            and
            not controller.get_attached()
        ):

            print(
                "Controller disconnected."
            )

            stop_robot(
                force=True
            )

            break


        now = time.monotonic()

        dt = (
            now
            -
            last_loop_time
        )

        last_loop_time = now


        # =================================================
        # BUTTON STATES
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

        l1_pressed = bool(
            controller.get_button(
                BUTTON_L1
            )
        )

        r1_pressed = bool(
            controller.get_button(
                BUTTON_R1
            )
        )


        # =================================================
        # B = EXIT
        # =================================================

        if (
            b_pressed
            and
            not b_was_pressed
        ):

            print(
                "B -> Disable + Exit"
            )

            stop_robot(
                force=True
            )

            running = False

            continue


        # =================================================
        # X = RECOVER
        # =================================================

        if (
            x_pressed
            and
            not x_was_pressed
        ):

            recover_robot()


        # =================================================
        # A = STOP
        # =================================================

        if (
            a_pressed
            and
            not a_was_pressed
        ):

            stop_robot(
                force=True
            )

            stop_latched = True

            print(
                "A -> STOP"
            )


        # =================================================
        # R1 = XYZ / JOINT
        # =================================================

        if (
            r1_pressed
            and
            not r1_was_pressed
        ):

            toggle_control_mode()


        # =================================================
        # L1 = NEXT J1-J4
        # =================================================

        if (
            l1_pressed
            and
            not l1_was_pressed
        ):

            next_joint()


        # Store button states
        a_was_pressed = a_pressed
        b_was_pressed = b_pressed
        x_was_pressed = x_pressed

        l1_was_pressed = l1_pressed
        r1_was_pressed = r1_pressed


        # =================================================
        # G2
        # =================================================

        update_gripper(
            dt
        )


        # =================================================
        # FAULT
        # =================================================

        if fault_latched:

            time.sleep(
                LOOP_INTERVAL
            )

            continue


        # =================================================
        # STOP LATCH
        # =================================================

        if stop_latched:

            if controls_centered():

                stop_latched = False

                print(
                    "Movement re-armed"
                )

            time.sleep(
                LOOP_INTERVAL
            )

            continue


        # =================================================
        # XYZ MODE
        # =================================================

        if control_mode == "XYZ":

            # D-pad takes priority and temporarily
            # switches to joint velocity mode.
            if update_xyz_dpad():

                time.sleep(
                    LOOP_INTERVAL
                )

                continue


            # Ensure Cartesian mode
            if velocity_mode != 5:

                if not switch_velocity_mode(5):

                    time.sleep(
                        LOOP_INTERVAL
                    )

                    continue


            update_cartesian()


        # =================================================
        # JOINT MODE
        # =================================================

        else:

            if velocity_mode != 4:

                if not switch_velocity_mode(4):

                    time.sleep(
                        LOOP_INTERVAL
                    )

                    continue


            update_joint_mode()


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

        stop_robot(
            force=True
        )

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