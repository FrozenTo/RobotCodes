import time
from pynput import keyboard
from dobot_api import DobotApiDashboard, DobotApiMove


ROBOT_IP = "192.168.2.6"

dashboard = DobotApiDashboard(ROBOT_IP, 29999)
move = DobotApiMove(ROBOT_IP, 30003)

current_key = None


def stop_robot():
    global current_key

    try:
        move.MoveJog()
        print("STOP")
    except Exception as e:
        print("Stop error:", e)

    current_key = None


def disable_robot():
    try:
        print("Disabling robot...")
        print("DisableRobot:", dashboard.DisableRobot())
    except Exception as e:
        print("Disable error:", e)


def on_press(key):
    global current_key

    if key == current_key:
        return

    try:
        if key == keyboard.Key.up:
            print("X-")
            move.MoveJog("X-")
            current_key = key

        elif key == keyboard.Key.down:
            print("X+")
            move.MoveJog("X+")
            current_key = key

        elif key == keyboard.Key.left:
            print("Y-")
            move.MoveJog("Y-")
            current_key = key

        elif key == keyboard.Key.right:
            print("Y+")
            move.MoveJog("Y+")
            current_key = key

        elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            print("Z+")
            move.MoveJog("Z+")
            current_key = key

        elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            print("Z-")
            move.MoveJog("Z-")
            current_key = key

        elif key == keyboard.Key.space:
            print("SPACE -> STOP")
            stop_robot()

        elif key == keyboard.Key.esc:
            print("ESC -> STOP + DISABLE + EXIT")
            stop_robot()
            disable_robot()
            return False

    except Exception as e:
        print("Movement error:", e)
        stop_robot()


def on_release(key):
    global current_key

    if key == current_key:
        stop_robot()


print("Connecting to MG400...")

print("ClearError:", dashboard.ClearError())

print("Waiting for error clear...")
time.sleep(1)

print("EnableRobot:", dashboard.EnableRobot())

time.sleep(0.5)

print("SpeedFactor:", dashboard.SpeedFactor(60))

print()
print("MG400 keyboard control active")
print("-----------------------------")
print("↑             X-")
print("↓             X+")
print("←             Y-")
print("→             Y+")
print("Left/Right Shift   Z+")
print("Left/Right Ctrl    Z-")
print("Space         STOP")
print("Esc           STOP + disable + exit")
print()

try:
    with keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    ) as listener:
        listener.join()

finally:
    # Safety cleanup if the script exits/crashes.
    stop_robot()
    disable_robot()

    print("Robot stopped and disabled.")