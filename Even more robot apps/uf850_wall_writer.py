"""
UFACTORY 850 wall-writer core logic.

Coordinate convention for this project:
    -X : toward the wall
    +X : away from the wall
    +Y : writing direction (left -> right)
    +Z : up

The wall is initially treated as a flat YZ plane at constant X.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Hashable, List, Optional, Tuple

from xarm.wrapper import XArmAPI


PointName = Hashable
Stroke = List[PointName]
LetterMap = Dict[str, List[Stroke]]
LogCallback = Callable[[str], None]


@dataclass
class WriterSettings:
    # Robot
    ip: str = "192.168.1.208"

    # Current provisional wall/writing pose from UFactory Studio.
    wall_x: float = -405.2
    start_y: float = 4.6
    start_z: float = 993.4
    roll: float = -0.2
    pitch: float = -1.7
    yaw: float = 0.5

    # X distance kept between TCP and the wall when the marker is lifted.
    # Because the wall is on -X, away_x = wall_x + clearance.
    clearance: float = 10.0

    # Speeds
    move_speed: float = 20.0       # mm/s
    contact_speed: float = 10.0    # mm/s
    joint_speed: float = 10.0      # deg/s

    # Manual jog defaults
    xyz_step: float = 5.0          # mm
    joint_step: float = 5.0        # deg

    # Writing geometry: 20 mm high x 10 mm wide by default.
    half_height: float = 10.0
    half_width: float = 5.0
    letter_step: float = 12.0
    space_step: float = 25.0

    # Safety/testing:
    # When True, pen_contact() does NOT move toward wall.
    # This allows testing the full letter path in the air.
    air_draw: bool = True


def default_logger(message: str) -> None:
    print(message)


class UF850WallWriter:
    def __init__(
        self,
        settings: Optional[WriterSettings] = None,
        logger: Optional[LogCallback] = None,
    ) -> None:
        self.settings = settings or WriterSettings()
        self.log = logger or default_logger

        self.arm: Optional[XArmAPI] = None

        self.points = self.build_points()
        self.letters = self.build_letters()

    # ============================================================
    # BASIC STATE
    # ============================================================

    @property
    def is_connected(self) -> bool:
        return bool(self.arm is not None and self.arm.connected)

    @property
    def away_x(self) -> float:
        return self.settings.wall_x + self.settings.clearance

    def rebuild_geometry(self) -> None:
        self.points = self.build_points()

    # ============================================================
    # CONNECTION / ROBOT STATE
    # ============================================================

    def connect_robot(self) -> None:
        if self.is_connected:
            self.log("Robot is already connected.")
            return

        self.log(f"Connecting to UFACTORY 850 at {self.settings.ip}...")
        self.arm = XArmAPI(self.settings.ip, is_radian=False)

        if not self.arm.connected:
            self.arm = None
            raise RuntimeError("Could not connect to the robot.")

        self.log("Connected.")
        self.log(f"Version: {self.arm.get_version()}")
        self.log(f"State: {self.arm.get_state()}")
        self.log(f"Errors / warnings: {self.arm.get_err_warn_code()}")

    def disconnect_robot(self) -> None:
        if self.arm is not None:
            try:
                self.arm.disconnect()
            finally:
                self.arm = None

        self.log("Disconnected.")

    def _require_arm(self) -> XArmAPI:
        if not self.is_connected or self.arm is None:
            raise RuntimeError("Robot is not connected.")
        return self.arm

    def enable_robot(self) -> None:
        arm = self._require_arm()

        # Do not automatically clear errors.
        error_code = arm.error_code
        if error_code != 0:
            raise RuntimeError(
                f"Robot has error code {error_code}. "
                "Check UFactory Studio before enabling."
            )

        self.log("Enabling movement...")
        self._check_ret("motion_enable", arm.motion_enable(enable=True))
        self._check_ret("set_mode(0)", arm.set_mode(0))
        self._check_ret("set_state(0)", arm.set_state(0))
        self.log("Robot ready for position control.")

    def emergency_stop(self) -> None:
        arm = self._require_arm()
        self.log("EMERGENCY STOP requested.")
        ret = arm.emergency_stop()
        self.log(f"Emergency stop result: {ret}")

    # ============================================================
    # READBACK
    # ============================================================

    def get_pose(self) -> Tuple[float, float, float, float, float, float]:
        arm = self._require_arm()
        code, pose = arm.get_position(is_radian=False)

        if code != 0:
            raise RuntimeError(f"Could not read TCP pose. Return code: {code}")

        return tuple(float(v) for v in pose[:6])  # type: ignore[return-value]

    def get_joints(self) -> Tuple[float, float, float, float, float, float]:
        arm = self._require_arm()
        code, joints = arm.get_servo_angle(is_radian=False)

        if code != 0:
            raise RuntimeError(f"Could not read joint angles. Return code: {code}")

        # UFACTORY 850 uses J1-J6. Some SDK responses may contain an
        # additional trailing value; only the first six are used here.
        return tuple(float(v) for v in joints[:6])  # type: ignore[return-value]

    # ============================================================
    # LOW-LEVEL MOVEMENT
    # ============================================================

    def _check_ret(self, action: str, ret: int) -> None:
        if ret != 0:
            raise RuntimeError(f"{action} failed with return code {ret}")

    def move_absolute(
        self,
        x: float,
        y: float,
        z: float,
        *,
        speed: Optional[float] = None,
    ) -> None:
        arm = self._require_arm()
        s = self.settings

        if speed is None:
            speed = s.move_speed

        ret = arm.set_position(
            x,
            y,
            z,
            s.roll,
            s.pitch,
            s.yaw,
            speed=speed,
            relative=False,
            wait=True,
            is_radian=False,
        )
        self._check_ret("Absolute Cartesian move", ret)

    def move_relative(
        self,
        *,
        dx: float = 0.0,
        dy: float = 0.0,
        dz: float = 0.0,
        speed: Optional[float] = None,
    ) -> None:
        arm = self._require_arm()
        s = self.settings

        if speed is None:
            speed = s.move_speed

        ret = arm.set_position(
            dx,
            dy,
            dz,
            0,
            0,
            0,
            speed=speed,
            relative=True,
            wait=True,
            is_radian=False,
        )
        self._check_ret("Relative Cartesian move", ret)

    def jog_cartesian(self, axis: str, amount: float) -> None:
        axis = axis.lower()

        if axis == "x":
            self.move_relative(dx=amount)
        elif axis == "y":
            self.move_relative(dy=amount)
        elif axis == "z":
            self.move_relative(dz=amount)
        else:
            raise ValueError(f"Unknown Cartesian axis: {axis}")

    def jog_joint(self, joint_id: int, angle_change: float) -> None:
        if joint_id not in range(1, 7):
            raise ValueError("UFACTORY 850 joint_id must be 1..6.")

        arm = self._require_arm()

        ret = arm.set_servo_angle(
            servo_id=joint_id,
            angle=angle_change,
            speed=self.settings.joint_speed,
            relative=True,
            wait=True,
            is_radian=False,
        )
        self._check_ret(f"J{joint_id} move", ret)

    # ============================================================
    # WALL / MARKER POSITIONING
    # ============================================================

    def go_to_writing_start(self) -> None:
        s = self.settings

        self.log(
            "Moving to writing start (marker away): "
            f"X={self.away_x:.2f}, Y={s.start_y:.2f}, Z={s.start_z:.2f}, "
            f"R={s.roll:.2f}, P={s.pitch:.2f}, Yaw={s.yaw:.2f}"
        )

        self.move_absolute(
            self.away_x,
            s.start_y,
            s.start_z,
            speed=s.move_speed,
        )

    def marker_contact(self) -> None:
        s = self.settings

        if s.air_draw:
            self.log(
                "[AIR DRAW] Marker contact skipped; staying at clearance X."
            )
            return

        x, y, z, _, _, _ = self.get_pose()

        self.log(
            f"Marker contact: X {x:.2f} -> {s.wall_x:.2f}"
        )

        self.move_absolute(
            s.wall_x,
            y,
            z,
            speed=s.contact_speed,
        )

    def marker_away(self) -> None:
        s = self.settings
        x, y, z, _, _, _ = self.get_pose()

        # In air-draw mode the TCP is normally already at away_x, but
        # explicitly commanding it keeps this button predictable.
        self.log(
            f"Marker away: X {x:.2f} -> {self.away_x:.2f}"
        )

        self.move_absolute(
            self.away_x,
            y,
            z,
            speed=s.contact_speed,
        )

    # ============================================================
    # LETTER GEOMETRY
    # ============================================================

    def build_points(self) -> Dict[PointName, Tuple[float, float]]:
        """
        Return point offsets as (dY, dZ).

                    +Z
                     ^
             1 ----- 2 ----- 3
             |               |
             4 ----- 5 ----- 6    +Y ->
             |               |
             7 ----- 8 ----- 9

        The current letter center is point 5.
        """
        h = self.settings.half_height
        w = self.settings.half_width

        return {
            1: (-w, +h),
            2: (0, +h),
            3: (+w, +h),

            4: (-w, 0),
            5: (0, 0),
            6: (+w, 0),

            7: (-w, -h),
            8: (0, -h),
            9: (+w, -h),

            # A crossbar.
            "A_LEFT": (-w / 2, 0),
            "A_RIGHT": (+w / 2, 0),

            # Dots above Ä / Ö / Ü.
            "DOT_TOP_LEFT": (-w / 2, h + 4),
            "DOT_TOP_RIGHT": (+w / 2, h + 4),

            # Small angular tilde above Õ.
            "TILDE_LEFT": (-w / 2, h + 4),
            "TILDE_MID_LEFT": (-w / 6, h + 6),
            "TILDE_MID_RIGHT": (+w / 6, h + 2),
            "TILDE_RIGHT": (+w / 2, h + 4),
        }

    @staticmethod
    def build_letters() -> LetterMap:
        # Reused from the MG400 writer. The stroke topology stays the
        # same; only point coordinates are now mapped to the YZ plane.
        return {
            "A": [[7, 2, 9], ["A_LEFT", "A_RIGHT"]],
            "B": [[7, 1, 3, 6, 4, 6, 9, 7]],
            "C": [[3, 1, 7, 9]],
            "D": [[7, 1, 2, 6, 8, 7]],
            "E": [[3, 1, 7, 9], [4, 6]],
            "F": [[3, 1, 7], [4, 6]],
            "G": [[3, 1, 7, 9, 6, 5]],
            "H": [[1, 7], [3, 9], [4, 6]],
            "I": [[1, 3], [2, 8], [7, 9]],
            "J": [[1, 3], [2, 8, 7]],
            "K": [[1, 7], [3, 4, 9]],
            "L": [[1, 7, 9]],
            "M": [[7, 1, 8, 3, 9]],
            "N": [[7, 1, 9, 3]],
            "O": [[1, 3, 9, 7, 1]],
            "P": [[7, 1, 3, 6, 4]],
            "Q": [[1, 3, 9, 7, 1], [5, 9]],
            "R": [[7, 1, 3, 6, 4, 9]],
            "S": [[3, 1, 4, 6, 9, 7]],
            "T": [[1, 3], [2, 8]],
            "U": [[1, 7, 9, 3]],
            "V": [[1, 8, 3]],
            "W": [[1, 7, 2, 9, 3]],
            "X": [[1, 9], [3, 7]],
            "Y": [[1, 5, 3], [5, 8]],
            "Z": [[1, 3, 7, 9]],

            "!": [[2, 5], [8]],
            "?": [[1, 3, 6, 5], [8]],
            ".": [[8]],

            "Ä": [
                [7, 2, 9],
                ["A_LEFT", "A_RIGHT"],
                ["DOT_TOP_LEFT"],
                ["DOT_TOP_RIGHT"],
            ],
            "Ö": [
                [1, 3, 9, 7, 1],
                ["DOT_TOP_LEFT"],
                ["DOT_TOP_RIGHT"],
            ],
            "Ü": [
                [1, 7, 9, 3],
                ["DOT_TOP_LEFT"],
                ["DOT_TOP_RIGHT"],
            ],
            "Õ": [
                [1, 3, 9, 7, 1],
                [
                    "TILDE_LEFT",
                    "TILDE_MID_LEFT",
                    "TILDE_MID_RIGHT",
                    "TILDE_RIGHT",
                ],
            ],
        }

    # ============================================================
    # WRITING MOVEMENT
    # ============================================================

    def _move_from_center_to_point(self, point: PointName) -> None:
        dy, dz = self.points[point]
        self.move_relative(dy=dy, dz=dz)

    def _move_between_points(
        self,
        start_point: PointName,
        end_point: PointName,
    ) -> None:
        y1, z1 = self.points[start_point]
        y2, z2 = self.points[end_point]
        self.move_relative(dy=y2 - y1, dz=z2 - z1)

    def _return_from_point_to_center(self, point: PointName) -> None:
        dy, dz = self.points[point]
        self.move_relative(dy=-dy, dz=-dz)

    def draw_stroke(self, stroke: Stroke) -> None:
        if not stroke:
            return

        first_point = stroke[0]
        last_point = stroke[-1]

        # Travel to the beginning with marker away from wall.
        self._move_from_center_to_point(first_point)

        # Touch wall (or stay away in Air Draw mode).
        self.marker_contact()

        # Draw the stroke in the YZ plane.
        for current_point, next_point in zip(stroke, stroke[1:]):
            self._move_between_points(current_point, next_point)

        # Lift before travelling back to letter center.
        self.marker_away()
        self._return_from_point_to_center(last_point)

    def draw_letter(self, letter: str) -> None:
        letter = letter.upper()

        if letter not in self.letters:
            raise ValueError(f"Letter '{letter}' is not defined.")

        self.log(f"--- Drawing {letter} ---")

        for stroke in self.letters[letter]:
            self.draw_stroke(stroke)

    def move_to_next_letter(self) -> None:
        self.log("--- Next letter (+Y) ---")
        self.move_relative(dy=self.settings.letter_step)

    def move_for_space(self) -> None:
        self.log("--- Space (+Y) ---")
        self.move_relative(dy=self.settings.space_step)

    def write_text(self, text: str, *, move_to_start: bool = True) -> None:
        if not text:
            self.log("No text entered.")
            return

        text = text.upper()

        unsupported = sorted(
            {
                ch
                for ch in text
                if ch != " " and ch not in self.letters
            }
        )

        if unsupported:
            raise ValueError(
                "Unsupported character(s): " + ", ".join(unsupported)
            )

        if move_to_start:
            self.go_to_writing_start()

        for index, character in enumerate(text):
            if character == " ":
                self.move_for_space()
                continue

            self.draw_letter(character)

            if index < len(text) - 1:
                next_character = text[index + 1]
                if next_character != " ":
                    self.move_to_next_letter()

        self.log(f"Finished writing: {text}")

    # ============================================================
    # SIMPLE TEST SHAPES
    # ============================================================

    def test_horizontal_line(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: horizontal line")
        self.draw_stroke([4, 6])

    def test_vertical_line(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: vertical line")
        self.draw_stroke([8, 2])

    def test_square(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: square")
        self.draw_stroke([1, 3, 9, 7, 1])

    def test_letter_a(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: letter A")
        self.draw_letter("A")
