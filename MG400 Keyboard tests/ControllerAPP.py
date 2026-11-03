import sys
import time
import threading

import pygame

from PySide6.QtCore import QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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

DEFAULT_IP = "192.168.1.6"

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
    controller_changed = Signal(str)
    initial_move_finished = Signal()
    request_close = Signal()


# =========================================================
# MG400 CONTROLLER
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

        self.stop_latched = False

        self.initial_move_active = False

        self.deadzone = DEFAULT_DEADZONE
        self.max_speed = DEFAULT_MAX_SPEED
        self.initial_speed = DEFAULT_INITIAL_SPEED

        self.lock = threading.Lock()

    # =====================================================
    # CONNECTION
    # =====================================================

    def connect_robot(self, ip):

        self.signals.status_changed.emit("Connecting...")

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

        time.sleep(1)

        print(
            "EnableRobot:",
            self.dashboard.EnableRobot()
        )

        time.sleep(0.5)

        self.enabled = True

        self.current_speed = None

        self.signals.status_changed.emit(
            f"Connected + Enabled ({ip})"
        )

    def enable_robot(self):

        if not self.connected:
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

            self.signals.status_changed.emit(
                "Robot enabled"
            )

        except Exception as e:

            print("Enable error:", e)

    # =====================================================
    # SPEED
    # =====================================================

    def speed_from_magnitude(
        self,
        magnitude
    ):

        if magnitude < self.deadzone:
            return 0

        # Five speed bands.
        #
        # Last one = configured max speed.

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

        if speed == self.current_speed:
            return

        try:

            self.dashboard.SpeedFactor(
                speed
            )

            self.current_speed = speed

            self.signals.speed_changed.emit(
                speed
            )

            print(
                f"Speed: {speed}%"
            )

        except Exception as e:

            print("Speed error:", e)

    # =====================================================
    # JOG
    # =====================================================

    def stop_jog(self):

        # Already stopped - don't send another command
        if self.current_direction is None:
            return

        if self.move is None:
            return

        try:
            self.move.MoveJog()

        except Exception as e:
            print("Jog stop error:", e)

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

        self.set_speed(
            speed
        )

        if direction == self.current_direction:
            return

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

            print("Jog error:", e)

    # =====================================================
    # STOP
    # =====================================================

    def stop_command(self):

        # Normal jog
        if not self.initial_move_active:

            self.stop_jog()

            self.stop_latched = True

            return

        # Automatic MovJ is running.
        #
        # Old MG400 API has no clean queue-cancelling
        # Stop() method, so disable the robot here.
        print(
            "STOP during initial-position move "
            "-> disabling robot"
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
            "STOPPED - robot disabled"
        )

    # =====================================================
    # TOOLS
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
            f"Selected: J{self.selected_joint}"
        )

    # =====================================================
    # MOVEMENT CALCULATION
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

        # X
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

        # Y
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

        # Z
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

        magnitude, direction = max(
            candidates,
            key=lambda item: item[0]
        )

        return direction, magnitude

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

        # J1 = left/right
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

        # J2 = vertical, inverted
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

        # J3 = vertical, inverted
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

        # J4 = left/right
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

        if (
            not self.connected
            or not self.enabled
            or self.initial_move_active
        ):
            return

        self.stop_jog()

        self.stop_latched = True

        self.initial_move_active = True

        self.set_speed(
            self.initial_speed
        )

        self.signals.status_changed.emit(
            "Moving to InitialPose..."
        )

        self.signals.movement_changed.emit(
            "InitialPose"
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
                "MovJ InitialPose:",
                INITIAL_POSE
            )

            self.move.MovJ(
                x,
                y,
                z,
                r
            )

            # Wait until queued movement is done.
            self.move.Sync()

        except Exception as e:

            print(
                "Initial move error:",
                e
            )

        finally:

            self.initial_move_active = False

            self.signals.initial_move_finished.emit()

    # =====================================================
    # DISABLE
    # =====================================================

    def disable_robot(self):

        self.stop_jog()

        try:

            if self.connected:

                self.set_tool1(False)
                self.set_tool2(False)

                self.dashboard.DisableRobot()

        except Exception as e:

            print(
                "Disable error:",
                e
            )

        self.enabled = False
        self.initial_move_active = False

        self.signals.status_changed.emit(
            "Robot disabled"
        )


# =========================================================
# GUI
# =========================================================

class MainWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "MG400 Controller"
        )

        self.resize(
            560,
            680
        )

        self.signals = Signals()

        self.robot = MG400Controller(
            self.signals
        )

        self.controller = None

        self.previous_buttons = {}

        self.l2_pressed = False
        self.r2_pressed = False

        self.build_ui()
        self.connect_signals()

        self.init_controller()

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.poll_controller
        )

        self.timer.start(
            10
        )

    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):

        main = QVBoxLayout(self)

        # -------------------------------------------------
        # Connection
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Controller status
        # -------------------------------------------------

        controller_group = QGroupBox(
            "Controller"
        )

        controller_layout = QGridLayout()

        self.controller_status = QLabel(
            "Not detected"
        )

        controller_layout.addWidget(
            self.controller_status,
            0,
            0,
            1,
            2
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

        # -------------------------------------------------
        # Settings
        # -------------------------------------------------

        settings_group = QGroupBox(
            "Movement settings"
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
            "%"
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
            "%"
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

        # -------------------------------------------------
        # Initial position
        # -------------------------------------------------

        position_group = QGroupBox(
            "Initial position"
        )

        position_layout = QVBoxLayout()

        position_layout.addWidget(
            QLabel(
                "InitialPose: "
                "X 350, Y 0, Z 0, R 0"
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

        # -------------------------------------------------
        # Tools
        # -------------------------------------------------

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

        # -------------------------------------------------
        # Safety
        # -------------------------------------------------

        self.stop_button = QPushButton(
            "STOP"
        )

        self.stop_button.setMinimumHeight(
            70
        )

        main.addWidget(
            self.stop_button
        )

        self.exit_button = QPushButton(
            "Disable Robot + Exit"
        )

        main.addWidget(
            self.exit_button
        )

        # -------------------------------------------------
        # Mapping
        # -------------------------------------------------

        controls = QLabel(
            "XYZ mode:\n"
            "Right stick = X/Y   |   Left stick vertical = Z\n\n"
            "Joint mode:\n"
            "R1 = switch mode   |   L1 = next joint\n"
            "J1/J4 = right stick left/right\n"
            "J2/J3 = right stick up/down\n\n"
            "A = STOP   |   B = Disable + Exit\n"
            "L2 = Tool 1   |   R2 = Tool 2"
        )

        main.addWidget(
            controls
        )

    # =====================================================
    # SIGNALS
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

        self.signals.status_changed.connect(
            self.robot_status.setText
        )

        self.signals.mode_changed.connect(
            self.mode_label.setText
        )

        self.signals.joint_changed.connect(
            lambda j:
            self.joint_label.setText(
                f"J{j}"
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
    # CONTROLLER INIT
    # =====================================================

    def init_controller(self):

        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:

            self.controller_status.setText(
                "No controller detected"
            )

            return

        self.controller = pygame.joystick.Joystick(
            0
        )

        self.controller.init()

        self.controller_status.setText(
            self.controller.get_name()
        )

    # =====================================================
    # CONNECT
    # =====================================================

    def connect_robot(self):

        try:

            self.robot.connect_robot(
                self.ip_input.text().strip()
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Connection error",
                str(e)
            )

    # =====================================================
    # SETTINGS
    # =====================================================

    def update_settings(self):

        self.robot.deadzone = (
            self.deadzone_input.value()
        )

        self.robot.max_speed = (
            self.max_speed_input.value()
        )

        self.robot.initial_speed = (
            self.initial_speed_input.value()
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

        if self.robot.enabled:

            self.robot_status.setText(
                "InitialPose reached"
            )

            self.movement_label.setText(
                "STOP"
            )

    # =====================================================
    # CONTROLLER LOOP
    # =====================================================

    def poll_controller(self):

        if self.controller is None:
            return

        pygame.event.pump()

        # -------------------------------------------------
        # A = STOP
        # -------------------------------------------------

        a_pressed = bool(
            self.controller.get_button(
                BUTTON_A
            )
        )

        if (
            a_pressed
            and not self.previous_buttons.get(
                BUTTON_A,
                False
            )
        ):

            self.robot.stop_command()

        # -------------------------------------------------
        # B = Disable + exit
        # -------------------------------------------------

        b_pressed = bool(
            self.controller.get_button(
                BUTTON_B
            )
        )

        if (
            b_pressed
            and not self.previous_buttons.get(
                BUTTON_B,
                False
            )
        ):

            self.safe_exit()
            return

        # -------------------------------------------------
        # R1 = mode
        # -------------------------------------------------

        r1_pressed = bool(
            self.controller.get_button(
                BUTTON_R1
            )
        )

        if (
            r1_pressed
            and not self.previous_buttons.get(
                BUTTON_R1,
                False
            )
        ):

            self.robot.toggle_mode()

        # -------------------------------------------------
        # L1 = next joint
        # -------------------------------------------------

        l1_pressed = bool(
            self.controller.get_button(
                BUTTON_L1
            )
        )

        if (
            l1_pressed
            and not self.previous_buttons.get(
                BUTTON_L1,
                False
            )
        ):

            self.robot.next_joint()

        # -------------------------------------------------
        # Triggers
        # -------------------------------------------------

        l2_value = self.controller.get_axis(
            L2_AXIS
        )

        new_l2 = (
            l2_value
            > TRIGGER_THRESHOLD
        )

        if (
            new_l2
            and not self.l2_pressed
        ):

            self.robot.set_tool1(
                not self.robot.tool1_on
            )

        self.l2_pressed = new_l2

        r2_value = self.controller.get_axis(
            R2_AXIS
        )

        new_r2 = (
            r2_value
            > TRIGGER_THRESHOLD
        )

        if (
            new_r2
            and not self.r2_pressed
        ):

            self.robot.set_tool2(
                not self.robot.tool2_on
            )

        self.r2_pressed = new_r2

        # -------------------------------------------------
        # Store button states
        # -------------------------------------------------

        self.previous_buttons[
            BUTTON_A
        ] = a_pressed

        self.previous_buttons[
            BUTTON_B
        ] = b_pressed

        self.previous_buttons[
            BUTTON_R1
        ] = r1_pressed

        self.previous_buttons[
            BUTTON_L1
        ] = l1_pressed

        # -------------------------------------------------
        # Controller movement locked during automatic move
        # -------------------------------------------------

        if self.robot.initial_move_active:
            return

        # -------------------------------------------------
        # Stop latch
        # -------------------------------------------------

        if self.robot.stop_latched:

            if self.sticks_centered():

                self.robot.stop_latched = False

            else:

                return

        # -------------------------------------------------
        # Movement
        # -------------------------------------------------

        if (
            not self.robot.connected
            or not self.robot.enabled
        ):

            return

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

    # =====================================================
    # CENTER CHECK
    # =====================================================

    def sticks_centered(self):

        if self.controller is None:
            return True

        dz = self.robot.deadzone

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

    # =====================================================
    # EXIT
    # =====================================================

    def safe_exit(self):
        self.close()

    def closeEvent(self, event):

        # Stop controller polling FIRST
        if hasattr(self, "timer"):
            self.timer.stop()

        try:
            self.robot.disable_robot()
        except Exception as e:
            print("Shutdown error:", e)

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