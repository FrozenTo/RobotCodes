import time
import threading
from pynput import keyboard
from dobot_api import DobotApiDashboard, DobotApiMove


ROBOT_IP = "192.168.2.6"

SPEED_FACTOR = 20

# How far each RelMovL command moves, in mm
MOVE_STEP = 0.5

# Delay between movement commands
MOVE_INTERVAL = 0.08


dashboard = DobotApiDashboard(ROBOT_IP, 29999)
move = DobotApiMove(ROBOT_IP, 30003)

pressed_keys = set()

running = True
movement_enabled = True

lock = threading.Lock()


def stop_robot():
    """
    Stop jog motion if there is any.
    RelMovL itself isn't MoveJog, but sending this is still useful
    as a general jog-stop safeguard.
    """
    try:
        move.MoveJog()
    except Exception:
        pass

    print("STOP")


def disable_robot():
    try:
        print("Disabling robot...")
        print("DisableRobot:", dashboard.DisableRobot())
    except Exception as e:
        print("Disable error:", e)


def get_direction():
    dx = 0
    dy = 0
    dz = 0

    with lock:
        keys = pressed_keys.copy()

    # X
    if keyboard.Key.up in keys:
        dx -= MOVE_STEP

    if keyboard.Key.down in keys:
        dx += MOVE_STEP

    # Y
    if keyboard.Key.left in keys:
        dy -= MOVE_STEP

    if keyboard.Key.right in keys:
        dy += MOVE_STEP

    # Z+
    if (
        keyboard.Key.shift in keys
        or keyboard.Key.shift_l in keys
        or keyboard.Key.shift_r in keys
    ):
        dz += MOVE_STEP

    # Z-
    if (
        keyboard.Key.ctrl in keys
        or keyboard.Key.ctrl_l in keys
        or keyboard.Key.ctrl_r in keys
    ):
        dz -= MOVE_STEP

    return dx, dy, dz


def movement_loop():
    global running

    while running:

        if not movement_enabled:
            time.sleep(MOVE_INTERVAL)
            continue

        dx, dy, dz = get_direction()

        if dx != 0 or dy != 0 or dz != 0:

            try:
                print(
                    f"Move: "
                    f"X={dx:+.1f} "
                    f"Y={dy:+.1f} "
                    f"Z={dz:+.1f}"
                )

                move.RelMovL(
                    dx,
                    dy,
                    dz,
                    0
                )

            except Exception as e:
                print("Movement error:", e)

        time.sleep(MOVE_INTERVAL)


def on_press(key):
    global running
    global movement_enabled

    # SPACE = stop movement immediately
    if key == keyboard.Key.space:

        with lock:
            pressed_keys.clear()

        movement_enabled = False

        stop_robot()

        print("SPACE -> MOVEMENT DISABLED")
        print("Press any movement key to enable movement again.")
        return

    # ESC = exit
    if key == keyboard.Key.esc:

        print("ESC -> EXIT")

        with lock:
            pressed_keys.clear()

        movement_enabled = False
        running = False

        stop_robot()
        disable_robot()

        return False

    # Movement keys
    movement_keys = (
        keyboard.Key.up,
        keyboard.Key.down,
        keyboard.Key.left,
        keyboard.Key.right,
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r,
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r,
    )

    if key in movement_keys:

        movement_enabled = True

        with lock:
            pressed_keys.add(key)


def on_release(key):

    with lock:
        pressed_keys.discard(key)


print("Connecting to MG400...")

print("ClearError:", dashboard.ClearError())

time.sleep(1)

print("EnableRobot:", dashboard.EnableRobot())

time.sleep(0.5)

print("SpeedFactor:", dashboard.SpeedFactor(SPEED_FACTOR))

print()
print("MG400 multi-key control active")
print("--------------------------------")
print("↑             X-")
print("↓             X+")
print("←             Y-")
print("→             Y+")
print("Shift         Z+")
print("Ctrl          Z-")
print()
print("Combinations are allowed:")
print("↑ + →         X- Y+")
print("↑ + Shift     X- Z+")
print("↑ + → + Shift X- Y+ Z+")
print()
print("SPACE = STOP")
print("ESC   = STOP + Disable + Exit")
print()
print(f"Move step: {MOVE_STEP} mm")
print(f"Interval:  {MOVE_INTERVAL} s")
print(f"Speed:     {SPEED_FACTOR}%")
print()

movement_thread = threading.Thread(
    target=movement_loop,
    daemon=True
)

movement_thread.start()

try:

    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    ) as listener:

        listener.join()

finally:

    running = False

    with lock:
        pressed_keys.clear()

    stop_robot()
    disable_robot()

    print("Robot stopped and disabled.")