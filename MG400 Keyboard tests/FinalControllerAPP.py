import sys
import time
import threading

import pygame

from PySide6.QtCore import QTimer, Signal, QObject, QSettings
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QGroupBox,
    QMessageBox,
)

from dobot_api import DobotApiDashboard, DobotApiMove


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_IP = "192.168.2.6"

INITIAL_POSE = (
    350.0,  # X
    0.0,    # Y
    0.0,    # Z
    0.0,    # R
)

DEFAULT_DEADZONE = 0.10

TRIGGER_THRESHOLD = 0.5

DEFAULT_MAX_SPEED = 70
DEFAULT_INITIAL_SPEED = 30


# =========================================================
# CONTROLLER MAPPING
# Xbox-style controller
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
# QT SIGNALS
# =========================================================

class Signals(QObject):

    status_changed = Signal(str)

    mode_changed = Signal(str)

    joint_changed = Signal(int)

    movement_changed = Signal(str)

    speed_changed = Signal(int)

    tool1_changed = Signal(bool)

    tool2_changed = Signal(bool)

    initial_move_finished = Signal()


# =========================================================
# MG400 ROBOT CONTROLLER
# =========================================================

class MG400Controller:

    def __init__(self, signals):

        self.signals = signals

        self.dashboard = None
        self.move = None

        self.connected = False
        self.enabled = False

        self.current_direction = None
        self.current_speed = None

        self.mode = "XYZ"
        self.selected_joint = 1

        self.tool1_on = False
        self.tool2_on = False

        # After STOP / reconnect / mode switch,
        # sticks must return to center before movement resumes.
        self.stop_latched = False

        # True while MovJ to initial position is running.
        self.initial_move_active = False

        self.deadzone = DEFAULT_DEADZONE
        self.max_speed = DEFAULT_MAX_SPEED
        self.initial_speed = DEFAULT_INITIAL_SPEED


    # =====================================================
    # CONNECTION
    # =====================================================

    def connect_robot(self, ip):

        if self.connected:
            self.signals.status_changed.emit(
                "Robot already connected"
            )
            return

        self.signals.status_changed.emit(
            "Connecting..."
        )

        self.dashboard = DobotApiDashboard(
            ip,
            29999
        )

        self.move = DobotApiMove(
            ip,
            30003
        )

        self.connected = True

        print(
            "ClearError:",
            self.dashboard.ClearError()
        )

        # MG400 needs a moment after ClearError,
        # especially after emergency stop.
        time.sleep(1)

        print(
            "EnableRobot:",
            self.dashboard.EnableRobot()
        )

        time.sleep(0.5)

        self.enabled = True

        self.current_speed = None
        self.current_direction = None

        self.stop_latched = True

        self.signals.status_changed.emit(
            f"Robot enabled — {ip}"
        )


    def enable_robot(self):

        if not self.connected:
            self.signals.status_changed.emit(
                "Connect to robot first"
            )
            return

        if self.enabled:
            return

        try:

            print(
                "ClearError:",
                self.dashboard.ClearError()
            )

            time.sleep(1)

            print(
                "EnableRobot:",
                self.dashboard.EnableRobot()
            )

            time.sleep(0.5)

            self.enabled = True

            self.current_speed = None
            self.current_direction = None

            self.stop_latched = True

            self.signals.status_changed.emit(
                "Robot enabled"
            )

        except Exception as e:

            print(
                "Enable error:",
                e
            )

            self.signals.status_changed.emit(
                "Enable failed"
            )


    # =====================================================
    # SPEED
    # =====================================================

    def speed_from_magnitude(
        self,
        magnitude
    ):

        if magnitude < self.deadzone:
            return 0

        # Stick deflection -> speed.
        #
        # Deadzone - 0.30 : 10%
        # 0.30 - 0.50     : 20%
        # 0.50 - 0.70     : 35%
        # 0.70 - 0.90     : 50%
        # 0.90 - 1.00     : Max configured speed

        bands = [
            (0.30, 10),
            (0.50, 20),
            (0.70, 35),
            (0.90, 50),
            (1.01, self.max_speed),
        ]

        for upper, speed in bands:

            if magnitude < upper:

                return min(
                    speed,
                    self.max_speed
                )

        return self.max_speed


    def set_speed(
        self,
        speed
    ):

        if (
            not self.connected
            or not self.enabled
        ):
            return

        speed = int(
            max(
                1,
                min(
                    100,
                    speed
                )
            )
        )

        # Don't constantly resend same speed.
        if speed == self.current_speed:
            return

        try:

            print(
                "SpeedFactor:",
                self.dashboard.SpeedFactor(
                    speed
                )
            )

            self.current_speed = speed

            self.signals.speed_changed.emit(
                speed
            )

            print(
                f"Speed: {speed}%"
            )

        except Exception as e:

            print(
                "Speed error:",
                e
            )


    # =====================================================
    # JOG
    # =====================================================

    def stop_jog(self):

        # IMPORTANT:
        # Do not keep sending MoveJog() every 10 ms
        # when the robot is already stopped.
        if self.current_direction is None:
            return

        if self.move is None:
            return

        try:

            self.move.MoveJog()

        except Exception as e:

            print(
                "Jog stop error:",
                e
            )

        self.current_direction = None

        self.signals.movement_changed.emit(
            "STOP"
        )

        print("STOP")


    def start_jog(
        self,
        direction,
        magnitude
    ):

        if (
            not self.connected
            or not self.enabled
            or self.initial_move_active
        ):
            return

        speed = self.speed_from_magnitude(
            magnitude
        )

        if speed == 0:

            self.stop_jog()
            return

        # Speed may change even if jog direction doesn't.
        self.set_speed(
            speed
        )

        if direction == self.current_direction:
            return

        # Stop old jog before changing axis.
        if self.current_direction is not None:

            try:
                self.move.MoveJog()
            except Exception:
                pass

        try:

            self.move.MoveJog(
                direction
            )

            self.current_direction = direction

            self.signals.movement_changed.emit(
                direction
            )

            print(
                f"Jog: {direction}"
            )

        except Exception as e:

            print(
                "Jog error:",
                e
            )


    # =====================================================
    # STOP
    # =====================================================

    def stop_command(self):

        # -------------------------------------------------
        # Normal MoveJog movement
        # -------------------------------------------------

        if not self.initial_move_active:

            self.stop_jog()

            self.stop_latched = True

            return

        # -------------------------------------------------
        # Initial-position MovJ movement
        # -------------------------------------------------
        #
        # For this older MG400 API we don't have a clean
        # queue-cancelling motion stop command.
        #
        # Therefore STOP during Initial Position disables
        # the robot.
        # -------------------------------------------------

        print(
            "STOP during Initial Position "
            "-> DisableRobot"
        )

        try:

            self.dashboard.DisableRobot()

        except Exception as e:

            print(
                "Disable error:",
                e
            )

        self.enabled = False
        self.initial_move_active = False

        self.current_direction = None

        self.stop_latched = True

        self.signals.movement_changed.emit(
            "STOP"
        )

        self.signals.status_changed.emit(
            "STOPPED — robot disabled"
        )


    # =====================================================
    # TOOL OUTPUTS
    # =====================================================

    def set_tool1(
        self,
        state
    ):

        if not self.connected:
            return

        try:

            self.dashboard.DO(
                1,
                1 if state else 0
            )

            self.tool1_on = state

            self.signals.tool1_changed.emit(
                state
            )

            print(
                "Tool 1:",
                "ON"
                if state
                else "OFF"
            )

        except Exception as e:

            print(
                "Tool 1 error:",
                e
            )


    def set_tool2(
        self,
        state
    ):

        if not self.connected:
            return

        try:

            self.dashboard.DO(
                2,
                1 if state else 0
            )

            self.tool2_on = state

            self.signals.tool2_changed.emit(
                state
            )

            print(
                "Tool 2:",
                "ON"
                if state
                else "OFF"
            )

        except Exception as e:

            print(
                "Tool 2 error:",
                e
            )


    # =====================================================
    # MODE
    # =====================================================

    def toggle_mode(self):

        if self.initial_move_active:
            return

        self.stop_jog()

        self.stop_latched = True

        if self.mode == "XYZ":
            self.mode = "JOINT"

        else:
            self.mode = "XYZ"

        self.signals.mode_changed.emit(
            self.mode
        )

        print(
            "Mode:",
            self.mode
        )


    def next_joint(self):

        if (
            self.mode != "JOINT"
            or self.initial_move_active
        ):
            return

        self.stop_jog()

        self.stop_latched = True

        self.selected_joint += 1

        if self.selected_joint > 4:
            self.selected_joint = 1

        self.signals.joint_changed.emit(
            self.selected_joint
        )

        print(
            f"Selected joint: "
            f"J{self.selected_joint}"
        )


    # =====================================================
    # XYZ MOVEMENT
    # =====================================================

    def get_xyz_movement(
        self,
        controller
    ):

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

        # -------------------------------------------------
        # X
        # Right stick vertical
        #
        # Up   = X-
        # Down = X+
        # -------------------------------------------------

        if abs(right_y) >= self.deadzone:

            direction = (
                "X-"
                if right_y < 0
                else "X+"
            )

            candidates.append(
                (
                    abs(right_y),
                    direction
                )
            )

        # -------------------------------------------------
        # Y
        # Right stick horizontal
        #
        # Left  = Y-
        # Right = Y+
        # -------------------------------------------------

        if abs(right_x) >= self.deadzone:

            direction = (
                "Y-"
                if right_x < 0
                else "Y+"
            )

            candidates.append(
                (
                    abs(right_x),
                    direction
                )
            )

        # -------------------------------------------------
        # Z
        # Left stick vertical
        #
        # Up   = Z+
        # Down = Z-
        # -------------------------------------------------

        if abs(left_y) >= self.deadzone:

            direction = (
                "Z+"
                if left_y < 0
                else "Z-"
            )

            candidates.append(
                (
                    abs(left_y),
                    direction
                )
            )

        if not candidates:

            return None, 0

        # MG400 only supports one MoveJog axis at once.
        # Whichever stick axis is pushed furthest wins.

        magnitude, direction = max(
            candidates,
            key=lambda item: item[0]
        )

        return direction, magnitude


    # =====================================================
    # JOINT MOVEMENT
    # =====================================================

    def get_joint_movement(
        self,
        controller
    ):

        right_x = controller.get_axis(
            RIGHT_X
        )

        right_y = controller.get_axis(
            RIGHT_Y
        )

        # -------------------------------------------------
        # J1
        #
        # Right stick LEFT / RIGHT
        #
        # Left  = J1-
        # Right = J1+
        # -------------------------------------------------

        if self.selected_joint == 1:

            if abs(right_x) < self.deadzone:
                return None, 0

            direction = (
                "J1-"
                if right_x < 0
                else "J1+"
            )

            return (
                direction,
                abs(right_x)
            )

        # -------------------------------------------------
        # J2
        #
        # Right stick UP / DOWN
        # Inverted as tested.
        #
        # Up   = J2-
        # Down = J2+
        # -------------------------------------------------

        if self.selected_joint == 2:

            if abs(right_y) < self.deadzone:
                return None, 0

            direction = (
                "J2-"
                if right_y < 0
                else "J2+"
            )

            return (
                direction,
                abs(right_y)
            )

        # -------------------------------------------------
        # J3
        #
        # Right stick UP / DOWN
        # Inverted as tested.
        #
        # Up   = J3-
        # Down = J3+
        # -------------------------------------------------

        if self.selected_joint == 3:

            if abs(right_y) < self.deadzone:
                return None, 0

            direction = (
                "J3-"
                if right_y < 0
                else "J3+"
            )

            return (
                direction,
                abs(right_y)
            )

        # -------------------------------------------------
        # J4
        #
        # Right stick LEFT / RIGHT
        #
        # Left  = J4-
        # Right = J4+
        # -------------------------------------------------

        if self.selected_joint == 4:

            if abs(right_x) < self.deadzone:
                return None, 0

            direction = (
                "J4-"
                if right_x < 0
                else "J4+"
            )

            return (
                direction,
                abs(right_x)
            )

        return None, 0


    # =====================================================
    # INITIAL POSITION
    # =====================================================

    def go_to_initial_position(self):

        if not self.connected:

            self.signals.status_changed.emit(
                "Robot not connected"
            )

            return

        if not self.enabled:

            self.signals.status_changed.emit(
                "Robot is disabled"
            )

            return

        if self.initial_move_active:
            return

        # Stop controller jogging first.
        self.stop_jog()

        # Require stick recenter afterwards.
        self.stop_latched = True

        self.initial_move_active = True

        self.set_speed(
            self.initial_speed
        )

        self.signals.status_changed.emit(
            "Moving to Initial Position..."
        )

        self.signals.movement_changed.emit(
            "Initial Position"
        )

        worker = threading.Thread(
            target=self._initial_move_worker,
            daemon=True
        )

        worker.start()


    def _initial_move_worker(self):

        try:

            x, y, z, r = INITIAL_POSE

            print(
                "MovJ Initial Position:",
                INITIAL_POSE
            )

            self.move.MovJ(
                x,
                y,
                z,
                r
            )

            # Wait for robot movement to finish.
            self.move.Sync()

        except Exception as e:

            print(
                "Initial position error:",
                e
            )

        finally:

            self.initial_move_active = False

            self.signals.initial_move_finished.emit()


    # =====================================================
    # DISABLE ROBOT
    # =====================================================

    def disable_robot(self):

        self.stop_jog()

        if not self.connected:
            return

        try:

            # Safe tool shutdown.
            self.set_tool1(False)
            self.set_tool2(False)

            print(
                "DisableRobot:",
                self.dashboard.DisableRobot()
            )

        except Exception as e:

            print(
                "Disable error:",
                e
            )

        self.enabled = False

        self.initial_move_active = False

        self.current_direction = None

        self.stop_latched = True

        self.signals.status_changed.emit(
            "Robot disabled"
        )


# =========================================================
# MAIN WINDOW
# =========================================================

class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "MG400 Controller"
        )

        self.resize(
            570,
            720
        )

        # -------------------------------------------------
        # Saved settings
        # -------------------------------------------------

        self.settings = QSettings(
            "UT RoboLab",
            "MG400 Controller"
        )

        # -------------------------------------------------
        # Robot
        # -------------------------------------------------

        self.signals = Signals()

        self.robot = MG400Controller(
            self.signals
        )

        # -------------------------------------------------
        # Controller state
        # -------------------------------------------------

        self.controller = None

        self.controller_connected = False

        self.controller_name = None

        self.previous_buttons = {}

        self.l2_pressed = False
        self.r2_pressed = False

        # -------------------------------------------------

        self.build_ui()

        self.load_settings()

        self.connect_signals()

        self.init_pygame()

        self.find_controller()

        # -------------------------------------------------
        # Controller polling
        # -------------------------------------------------

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.poll_controller
        )

        # 100 Hz
        self.timer.start(
            10
        )


    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):

        main = QVBoxLayout(self)


        # =================================================
        # ROBOT CONNECTION
        # =================================================

        robot_group = QGroupBox(
            "Robot"
        )

        robot_layout = QGridLayout()

        robot_layout.addWidget(
            QLabel("IP:"),
            0,
            0
        )

        self.ip_input = QLineEdit(
            DEFAULT_IP
        )

        robot_layout.addWidget(
            self.ip_input,
            0,
            1,
            1,
            2
        )

        self.connect_button = QPushButton(
            "Connect + Enable"
        )

        self.enable_button = QPushButton(
            "Enable"
        )

        self.disable_button = QPushButton(
            "Disable"
        )

        robot_layout.addWidget(
            self.connect_button,
            1,
            0
        )

        robot_layout.addWidget(
            self.enable_button,
            1,
            1
        )

        robot_layout.addWidget(
            self.disable_button,
            1,
            2
        )

        self.robot_status = QLabel(
            "Disconnected"
        )

        robot_layout.addWidget(
            self.robot_status,
            2,
            0,
            1,
            3
        )

        robot_group.setLayout(
            robot_layout
        )

        main.addWidget(
            robot_group
        )


        # =================================================
        # CONTROLLER STATUS
        # =================================================

        controller_group = QGroupBox(
            "Controller"
        )

        controller_layout = QGridLayout()

        controller_layout.addWidget(
            QLabel("Controller:"),
            0,
            0
        )

        self.controller_status = QLabel(
            "Not detected"
        )

        controller_layout.addWidget(
            self.controller_status,
            0,
            1
        )

        controller_layout.addWidget(
            QLabel("Mode:"),
            1,
            0
        )

        self.mode_label = QLabel(
            "XYZ"
        )

        controller_layout.addWidget(
            self.mode_label,
            1,
            1
        )

        controller_layout.addWidget(
            QLabel("Selected joint:"),
            2,
            0
        )

        self.joint_label = QLabel(
            "J1"
        )

        controller_layout.addWidget(
            self.joint_label,
            2,
            1
        )

        controller_layout.addWidget(
            QLabel("Movement:"),
            3,
            0
        )

        self.movement_label = QLabel(
            "STOP"
        )

        controller_layout.addWidget(
            self.movement_label,
            3,
            1
        )

        controller_layout.addWidget(
            QLabel("Speed:"),
            4,
            0
        )

        self.speed_label = QLabel(
            "0%"
        )

        controller_layout.addWidget(
            self.speed_label,
            4,
            1
        )

        controller_group.setLayout(
            controller_layout
        )

        main.addWidget(
            controller_group
        )


        # =================================================
        # MOVEMENT SETTINGS
        # =================================================

        settings_group = QGroupBox(
            "Movement Settings"
        )

        settings_layout = QGridLayout()

        settings_layout.addWidget(
            QLabel("Stick deadzone:"),
            0,
            0
        )

        self.deadzone_input = QDoubleSpinBox()

        self.deadzone_input.setRange(
            0.05,
            0.50
        )

        self.deadzone_input.setSingleStep(
            0.05
        )

        self.deadzone_input.setDecimals(
            2
        )

        self.deadzone_input.setValue(
            DEFAULT_DEADZONE
        )

        settings_layout.addWidget(
            self.deadzone_input,
            0,
            1
        )

        settings_layout.addWidget(
            QLabel("Max jog speed:"),
            1,
            0
        )

        self.max_speed_input = QSpinBox()

        self.max_speed_input.setRange(
            10,
            100
        )

        self.max_speed_input.setSuffix(
            " %"
        )

        self.max_speed_input.setValue(
            DEFAULT_MAX_SPEED
        )

        settings_layout.addWidget(
            self.max_speed_input,
            1,
            1
        )

        settings_layout.addWidget(
            QLabel("Initial-position speed:"),
            2,
            0
        )

        self.initial_speed_input = QSpinBox()

        self.initial_speed_input.setRange(
            1,
            100
        )

        self.initial_speed_input.setSuffix(
            " %"
        )

        self.initial_speed_input.setValue(
            DEFAULT_INITIAL_SPEED
        )

        settings_layout.addWidget(
            self.initial_speed_input,
            2,
            1
        )

        settings_group.setLayout(
            settings_layout
        )

        main.addWidget(
            settings_group
        )


        # =================================================
        # INITIAL POSITION
        # =================================================

        position_group = QGroupBox(
            "Initial Position"
        )

        position_layout = QVBoxLayout()

        position_layout.addWidget(
            QLabel(
                "X = 350   Y = 0   Z = 0   R = 0"
            )
        )

        self.initial_button = QPushButton(
            "Go to Initial Position"
        )

        self.initial_button.setMinimumHeight(
            45
        )

        position_layout.addWidget(
            self.initial_button
        )

        position_group.setLayout(
            position_layout
        )

        main.addWidget(
            position_group
        )


        # =================================================
        # TOOLS
        # =================================================

        tools_group = QGroupBox(
            "Tools"
        )

        tools_layout = QGridLayout()

        self.tool1_label = QLabel(
            "Tool 1: OFF"
        )

        self.tool2_label = QLabel(
            "Tool 2: OFF"
        )

        self.tool1_button = QPushButton(
            "Toggle Tool 1"
        )

        self.tool2_button = QPushButton(
            "Toggle Tool 2"
        )

        tools_layout.addWidget(
            self.tool1_label,
            0,
            0
        )

        tools_layout.addWidget(
            self.tool1_button,
            0,
            1
        )

        tools_layout.addWidget(
            self.tool2_label,
            1,
            0
        )

        tools_layout.addWidget(
            self.tool2_button,
            1,
            1
        )

        tools_group.setLayout(
            tools_layout
        )

        main.addWidget(
            tools_group
        )


        # =================================================
        # STOP
        # =================================================

        self.stop_button = QPushButton(
            "STOP"
        )

        self.stop_button.setMinimumHeight(
            70
        )

        main.addWidget(
            self.stop_button
        )


        # =================================================
        # EXIT
        # =================================================

        self.exit_button = QPushButton(
            "Disable Robot + Exit"
        )

        main.addWidget(
            self.exit_button
        )


        # =================================================
        # CONTROLLER MAPPING
        # =================================================

        controls_group = QGroupBox(
            "Controller Mapping"
        )

        controls_layout = QVBoxLayout()

        controls = QLabel(
            "XYZ MODE\n"
            "Right stick: X / Y\n"
            "Left stick vertical: Z\n\n"

            "JOINT MODE\n"
            "R1: XYZ ↔ Joint mode\n"
            "L1: J1 → J2 → J3 → J4\n"
            "J1 / J4: Right stick left/right\n"
            "J2 / J3: Right stick up/down\n\n"

            "A: STOP\n"
            "B: Disable robot + Exit\n"
            "L2: Toggle Tool 1\n"
            "R2: Toggle Tool 2\n\n"

            "Stick deflection controls movement speed."
        )

        controls_layout.addWidget(
            controls
        )

        controls_group.setLayout(
            controls_layout
        )

        main.addWidget(
            controls_group
        )


    # =====================================================
    # SIGNAL CONNECTIONS
    # =====================================================

    def connect_signals(self):

        self.connect_button.clicked.connect(
            self.connect_robot
        )

        self.enable_button.clicked.connect(
            self.robot.enable_robot
        )

        self.disable_button.clicked.connect(
            self.robot.disable_robot
        )

        self.stop_button.clicked.connect(
            self.robot.stop_command
        )

        self.initial_button.clicked.connect(
            self.go_initial
        )

        self.tool1_button.clicked.connect(
            lambda:
            self.robot.set_tool1(
                not self.robot.tool1_on
            )
        )

        self.tool2_button.clicked.connect(
            lambda:
            self.robot.set_tool2(
                not self.robot.tool2_on
            )
        )

        self.exit_button.clicked.connect(
            self.safe_exit
        )

        self.deadzone_input.valueChanged.connect(
            self.update_settings
        )

        self.max_speed_input.valueChanged.connect(
            self.update_settings
        )

        self.initial_speed_input.valueChanged.connect(
            self.update_settings
        )

        # -------------------------------------------------
        # Robot -> GUI
        # -------------------------------------------------

        self.signals.status_changed.connect(
            self.robot_status.setText
        )

        self.signals.mode_changed.connect(
            self.mode_label.setText
        )

        self.signals.joint_changed.connect(
            lambda joint:
            self.joint_label.setText(
                f"J{joint}"
            )
        )

        self.signals.movement_changed.connect(
            self.movement_label.setText
        )

        self.signals.speed_changed.connect(
            lambda speed:
            self.speed_label.setText(
                f"{speed}%"
            )
        )

        self.signals.tool1_changed.connect(
            lambda state:
            self.tool1_label.setText(
                "Tool 1: ON"
                if state
                else "Tool 1: OFF"
            )
        )

        self.signals.tool2_changed.connect(
            lambda state:
            self.tool2_label.setText(
                "Tool 2: ON"
                if state
                else "Tool 2: OFF"
            )
        )

        self.signals.initial_move_finished.connect(
            self.initial_move_finished
        )


    # =====================================================
    # SETTINGS
    # =====================================================

    def load_settings(self):

        self.ip_input.setText(
            self.settings.value(
                "robot_ip",
                DEFAULT_IP
            )
        )

        self.deadzone_input.setValue(
            float(
                self.settings.value(
                    "deadzone",
                    DEFAULT_DEADZONE
                )
            )
        )

        self.max_speed_input.setValue(
            int(
                self.settings.value(
                    "max_speed",
                    DEFAULT_MAX_SPEED
                )
            )
        )

        self.initial_speed_input.setValue(
            int(
                self.settings.value(
                    "initial_speed",
                    DEFAULT_INITIAL_SPEED
                )
            )
        )

        self.update_settings(
            save=False
        )


    def save_settings(self):

        self.settings.setValue(
            "robot_ip",
            self.ip_input.text().strip()
        )

        self.settings.setValue(
            "deadzone",
            self.deadzone_input.value()
        )

        self.settings.setValue(
            "max_speed",
            self.max_speed_input.value()
        )

        self.settings.setValue(
            "initial_speed",
            self.initial_speed_input.value()
        )


    def update_settings(
        self,
        save=True
    ):

        self.robot.deadzone = (
            self.deadzone_input.value()
        )

        self.robot.max_speed = (
            self.max_speed_input.value()
        )

        self.robot.initial_speed = (
            self.initial_speed_input.value()
        )

        if save:
            self.save_settings()


    # =====================================================
    # PYGAME / CONTROLLER
    # =====================================================

    def init_pygame(self):

        if not pygame.get_init():
            pygame.init()

        if not pygame.joystick.get_init():
            pygame.joystick.init()


    def find_controller(self):

        try:

            self.init_pygame()

            pygame.event.pump()

            count = pygame.joystick.get_count()

        except pygame.error as e:

            print(
                "pygame controller error:",
                e
            )

            return

        if count == 0:

            self.controller = None

            self.controller_connected = False

            self.controller_name = None

            self.controller_status.setText(
                "Disconnected"
            )

            return

        try:

            controller = pygame.joystick.Joystick(
                0
            )

            controller.init()

            self.controller = controller

            self.controller_connected = True

            self.controller_name = (
                controller.get_name()
            )

            self.controller_status.setText(
                f"Connected: "
                f"{self.controller_name}"
            )

            # Reset all button edge states.
            self.previous_buttons.clear()

            self.l2_pressed = False
            self.r2_pressed = False

            # Don't instantly move if reconnect happens
            # while a stick is already held.
            self.robot.stop_latched = True

            print(
                "Controller connected:",
                self.controller_name
            )

        except pygame.error as e:

            print(
                "Controller init error:",
                e
            )

            self.controller = None

            self.controller_connected = False

            self.controller_status.setText(
                "Controller error"
            )


    def controller_is_attached(self):

        if self.controller is None:
            return False

        try:

            # SDL2 / pygame 2.x
            if hasattr(
                self.controller,
                "get_attached"
            ):

                return bool(
                    self.controller.get_attached()
                )

            # Fallback: try reading controller.
            self.controller.get_axis(
                RIGHT_X
            )

            return True

        except pygame.error:

            return False


    def handle_controller_disconnect(self):

        if not self.controller_connected:
            return

        print(
            "Controller disconnected"
        )

        self.robot.stop_jog()

        self.robot.stop_latched = True

        self.controller_connected = False

        self.controller = None

        self.controller_name = None

        self.previous_buttons.clear()

        self.l2_pressed = False
        self.r2_pressed = False

        self.controller_status.setText(
            "Disconnected"
        )


    def check_controller_connection(self):

        # -------------------------------------------------
        # Currently connected
        # -------------------------------------------------

        if self.controller_connected:

            if not self.controller_is_attached():

                self.handle_controller_disconnect()

            return

        # -------------------------------------------------
        # Currently disconnected:
        # see whether something appeared.
        # -------------------------------------------------

        try:

            pygame.event.pump()

            if pygame.joystick.get_count() > 0:

                self.find_controller()

        except pygame.error:

            pass


    # =====================================================
    # CONNECT ROBOT
    # =====================================================

    def connect_robot(self):

        try:

            self.update_settings()

            self.robot.connect_robot(
                self.ip_input.text().strip()
            )

        except Exception as e:

            self.robot.connected = False
            self.robot.enabled = False

            self.robot_status.setText(
                "Connection failed"
            )

            QMessageBox.critical(
                self,
                "Connection error",
                str(e)
            )


    # =====================================================
    # INITIAL POSITION
    # =====================================================

    def go_initial(self):

        self.update_settings()

        self.robot.go_to_initial_position()

        if self.robot.initial_move_active:

            self.initial_button.setEnabled(
                False
            )

            self.initial_button.setText(
                "Moving..."
            )


    def initial_move_finished(self):

        self.initial_button.setEnabled(
            True
        )

        self.initial_button.setText(
            "Go to Initial Position"
        )

        self.movement_label.setText(
            "STOP"
        )

        if self.robot.enabled:

            self.robot_status.setText(
                "Robot enabled — Initial Position reached"
            )

        else:

            self.robot_status.setText(
                "Robot disabled"
            )


    # =====================================================
    # STICK CENTER CHECK
    # =====================================================

    def sticks_centered(self):

        if (
            self.controller is None
            or not self.controller_connected
        ):

            return True

        dz = self.robot.deadzone

        try:

            return (
                abs(
                    self.controller.get_axis(
                        RIGHT_X
                    )
                ) < dz

                and

                abs(
                    self.controller.get_axis(
                        RIGHT_Y
                    )
                ) < dz

                and

                abs(
                    self.controller.get_axis(
                        LEFT_Y
                    )
                ) < dz
            )

        except pygame.error:

            return True


    # =====================================================
    # CONTROLLER LOOP
    # =====================================================

    def poll_controller(self):

        # -------------------------------------------------
        # Controller connection monitoring
        # -------------------------------------------------

        self.check_controller_connection()

        if (
            self.controller is None
            or not self.controller_connected
        ):

            return

        try:

            pygame.event.pump()

        except pygame.error:

            self.handle_controller_disconnect()

            return

        try:

            # =================================================
            # BUTTON STATES
            # =================================================

            a_pressed = bool(
                self.controller.get_button(
                    BUTTON_A
                )
            )

            b_pressed = bool(
                self.controller.get_button(
                    BUTTON_B
                )
            )

            l1_pressed = bool(
                self.controller.get_button(
                    BUTTON_L1
                )
            )

            r1_pressed = bool(
                self.controller.get_button(
                    BUTTON_R1
                )
            )


            # =================================================
            # A = STOP
            # =================================================

            if (
                a_pressed
                and not self.previous_buttons.get(
                    BUTTON_A,
                    False
                )
            ):

                self.robot.stop_command()


            # =================================================
            # B = DISABLE + EXIT
            # =================================================

            if (
                b_pressed
                and not self.previous_buttons.get(
                    BUTTON_B,
                    False
                )
            ):

                self.safe_exit()
                return


            # =================================================
            # R1 = XYZ / JOINT MODE
            # =================================================

            if (
                r1_pressed
                and not self.previous_buttons.get(
                    BUTTON_R1,
                    False
                )
            ):

                self.robot.toggle_mode()


            # =================================================
            # L1 = NEXT JOINT
            # =================================================

            if (
                l1_pressed
                and not self.previous_buttons.get(
                    BUTTON_L1,
                    False
                )
            ):

                self.robot.next_joint()


            # =================================================
            # L2 = TOOL 1
            # =================================================

            l2_value = (
                self.controller.get_axis(
                    L2_AXIS
                )
            )

            new_l2_pressed = (
                l2_value
                > TRIGGER_THRESHOLD
            )

            if (
                new_l2_pressed
                and not self.l2_pressed
            ):

                self.robot.set_tool1(
                    not self.robot.tool1_on
                )

            self.l2_pressed = (
                new_l2_pressed
            )


            # =================================================
            # R2 = TOOL 2
            # =================================================

            r2_value = (
                self.controller.get_axis(
                    R2_AXIS
                )
            )

            new_r2_pressed = (
                r2_value
                > TRIGGER_THRESHOLD
            )

            if (
                new_r2_pressed
                and not self.r2_pressed
            ):

                self.robot.set_tool2(
                    not self.robot.tool2_on
                )

            self.r2_pressed = (
                new_r2_pressed
            )


            # =================================================
            # STORE BUTTON STATES
            # =================================================

            self.previous_buttons[
                BUTTON_A
            ] = a_pressed

            self.previous_buttons[
                BUTTON_B
            ] = b_pressed

            self.previous_buttons[
                BUTTON_L1
            ] = l1_pressed

            self.previous_buttons[
                BUTTON_R1
            ] = r1_pressed


            # =================================================
            # AUTOMATIC INITIAL POSITION
            # =================================================
            #
            # Normal stick movement is disabled,
            # but A/B/tools were still checked above.
            # =================================================

            if self.robot.initial_move_active:
                return


            # =================================================
            # STOP LATCH
            # =================================================

            if self.robot.stop_latched:

                if self.sticks_centered():

                    self.robot.stop_latched = False

                else:

                    return


            # =================================================
            # ROBOT READY?
            # =================================================

            if (
                not self.robot.connected
                or not self.robot.enabled
            ):

                return


            # =================================================
            # MOVEMENT
            # =================================================

            if self.robot.mode == "XYZ":

                direction, magnitude = (
                    self.robot.get_xyz_movement(
                        self.controller
                    )
                )

            else:

                direction, magnitude = (
                    self.robot.get_joint_movement(
                        self.controller
                    )
                )


            if direction is None:

                self.robot.stop_jog()

            else:

                self.robot.start_jog(
                    direction,
                    magnitude
                )


        except pygame.error:

            self.handle_controller_disconnect()


    # =====================================================
    # EXIT
    # =====================================================

    def safe_exit(self):

        # closeEvent performs all cleanup.
        self.close()


    def closeEvent(
        self,
        event
    ):

        # VERY IMPORTANT:
        # stop Qt polling before pygame.quit()
        if hasattr(
            self,
            "timer"
        ):

            self.timer.stop()

        self.save_settings()

        try:

            self.robot.disable_robot()

        except Exception as e:

            print(
                "Shutdown error:",
                e
            )

        try:

            pygame.quit()

        except Exception:

            pass

        event.accept()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    window = MainWindow()

    window.show()

    sys.exit(
        app.exec()
    )