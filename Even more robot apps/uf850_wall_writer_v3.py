"""
UFACTORY 850 wall-writer core logic.

Project coordinate convention
-----------------------------
-X : toward the paper/wall
+X : away from the paper/wall
+Y : writing direction (left -> right)
+Z : up

There are three different X concepts:

1. READY position:
   A far-away pose used before/after writing.

2. SAFE WRITING X:
   A fixed X used while the marker is lifted and moving around the paper.

3. PAPER CONTACT X:
   Calculated from the four measured paper corners so the marker follows
   the actual paper surface while drawing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Hashable, List, Optional, Tuple

from xarm.wrapper import XArmAPI


PointName = Hashable
Stroke = List[PointName]
LetterMap = Dict[str, List[Stroke]]
LogCallback = Callable[[str], None]

XYZ = Tuple[float, float, float]
Joints6 = Tuple[float, float, float, float, float, float]


@dataclass
class WriterSettings:
    ip: str = "192.168.1.208"

    # Fixed marker orientation for the current marker mount.
    roll: float = -179.7
    pitch: float = -3.6
    yaw: float = 179.1

    # Far-away READY pose from the latest screenshot.
    ready_x: float = -391.8
    ready_y: float = 111.0
    ready_z: float = 597.7

    ready_joints: Joints6 = (
        -196.5,
        7.5,
        -77.1,
        1.2,
        -80.9,
        -15.8,
    )

    # Marker-up / travel X while near the paper.
    safe_x: float = -480.0

    # Four measured marker-contact corners: (X, Y, Z)
    paper_top_left: XYZ = (-497.2, -74.6, 706.0)
    paper_top_right: XYZ = (-493.6, 280.5, 706.0)
    paper_bottom_right: XYZ = (-492.5, 279.1, 487.0)
    paper_bottom_left: XYZ = (-498.2, -78.8, 487.0)

    # First letter center Y. Start Z is calculated automatically as:
    # paper_top_z - full_letter_height
    start_y: float = -64.6

    # Speeds
    move_speed: float = 20.0
    contact_speed: float = 10.0
    joint_speed: float = 10.0

    # Manual jog
    xyz_step: float = 5.0
    joint_step: float = 5.0

    # MG400 mini-letter geometry
    half_height: float = 10.0
    half_width: float = 5.0
    letter_step: float = 12.0
    space_step: float = 25.0

    # Multi-row writing.
    # Row spacing is center-to-center in -Z.
    row_spacing: float = 30.0
    max_rows: int = 7

    # True = never touch paper; draw at safe_x only.
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
    # DERIVED VALUES
    # ============================================================

    @property
    def is_connected(self) -> bool:
        return bool(self.arm is not None and self.arm.connected)

    @property
    def letter_height(self) -> float:
        return self.settings.half_height * 2.0

    @property
    def letter_width(self) -> float:
        return self.settings.half_width * 2.0

    @property
    def paper_top_z(self) -> float:
        s = self.settings
        return (s.paper_top_left[2] + s.paper_top_right[2]) / 2.0

    @property
    def paper_bottom_z(self) -> float:
        s = self.settings
        return (s.paper_bottom_left[2] + s.paper_bottom_right[2]) / 2.0

    @property
    def start_z(self) -> float:
        # User-requested rule:
        # first letter center Z = paper top Z - full letter height
        return self.paper_top_z - self.letter_height

    @property
    def rows_that_fit(self) -> int:
        """Return how many complete rows fit vertically on the paper."""
        spacing = self.settings.row_spacing
        if spacing <= 0:
            return 0

        available = (
            self.start_z
            - self.settings.half_height
            - self.paper_bottom_z
        )
        if available < 0:
            return 0

        return int(available // spacing) + 1

    def suggested_start_y(self) -> float:
        # One full letter width inward from the top-left Y edge.
        return self.settings.paper_top_left[1] + self.letter_width

    def rebuild_geometry(self) -> None:
        self.points = self.build_points()

    # ============================================================
    # CONNECTION / STATE
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

        if arm.error_code != 0:
            raise RuntimeError(
                f"Robot has error code {arm.error_code}. "
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

    def get_joints(self) -> Joints6:
        arm = self._require_arm()
        code, joints = arm.get_servo_angle(is_radian=False)

        if code != 0:
            raise RuntimeError(f"Could not read joint angles. Return code: {code}")

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
        orientation: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        arm = self._require_arm()
        s = self.settings

        if speed is None:
            speed = s.move_speed

        if orientation is None:
            roll, pitch, yaw = s.roll, s.pitch, s.yaw
        else:
            roll, pitch, yaw = orientation

        ret = arm.set_position(
            x,
            y,
            z,
            roll,
            pitch,
            yaw,
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

    def move_joints_absolute(self, angles: Joints6) -> None:
        arm = self._require_arm()

        ret = arm.set_servo_angle(
            angle=list(angles),
            speed=self.settings.joint_speed,
            relative=False,
            wait=True,
            is_radian=False,
        )
        self._check_ret("Absolute joint move", ret)

    # ============================================================
    # PAPER SURFACE CALIBRATION
    # ============================================================

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def paper_contact_x(self, y: float, z: float) -> float:
        """
        Interpolate contact X from the four measured paper corners.

        The top and bottom paper edges are almost horizontal in Z.
        We interpolate left/right boundaries at the current Z and then
        interpolate X across Y.

        Coordinates outside the measured paper are clamped to the nearest
        paper edge.
        """
        s = self.settings

        tl = s.paper_top_left
        tr = s.paper_top_right
        br = s.paper_bottom_right
        bl = s.paper_bottom_left

        top_z = (tl[2] + tr[2]) / 2.0
        bottom_z = (bl[2] + br[2]) / 2.0

        if abs(top_z - bottom_z) < 1e-9:
            raise RuntimeError("Paper calibration has zero Z height.")

        v = (z - bottom_z) / (top_z - bottom_z)
        v = self._clamp(v, 0.0, 1.0)

        left_y = bl[1] + v * (tl[1] - bl[1])
        right_y = br[1] + v * (tr[1] - br[1])

        if abs(right_y - left_y) < 1e-9:
            raise RuntimeError("Paper calibration has zero Y width.")

        u = (y - left_y) / (right_y - left_y)
        u = self._clamp(u, 0.0, 1.0)

        left_x = bl[0] + v * (tl[0] - bl[0])
        right_x = br[0] + v * (tr[0] - br[0])

        return left_x + u * (right_x - left_x)

    # ============================================================
    # READY / HOME / WRITING START
    # ============================================================

    def go_to_ready_position(self) -> None:
        s = self.settings

        self.log(
            "Moving by joints to READY posture: "
            + ", ".join(
                f"J{i}={angle:.1f}°"
                for i, angle in enumerate(s.ready_joints, start=1)
            )
        )

        self.move_joints_absolute(s.ready_joints)

        self.log(
            "Correcting to READY TCP: "
            f"X={s.ready_x:.1f}, Y={s.ready_y:.1f}, Z={s.ready_z:.1f}"
        )

        self.move_absolute(
            s.ready_x,
            s.ready_y,
            s.ready_z,
            speed=s.move_speed,
        )

    def go_to_writing_start(self) -> None:
        """
        Staged approach:
          1) joint-space to READY
          2) straight X move from READY to safe writing X
          3) Y/Z move on safe writing plane to first letter center
        """
        s = self.settings

        self.go_to_ready_position()

        self.log(
            f"Approaching safe writing plane: X {s.ready_x:.1f} -> {s.safe_x:.1f}"
        )
        self.move_absolute(
            s.safe_x,
            s.ready_y,
            s.ready_z,
            speed=s.move_speed,
        )

        self.log(
            "Moving to first letter center on safe plane: "
            f"X={s.safe_x:.1f}, Y={s.start_y:.1f}, Z={self.start_z:.1f}"
        )
        self.move_absolute(
            s.safe_x,
            s.start_y,
            self.start_z,
            speed=s.move_speed,
        )

    def return_to_initial_position(self) -> None:
        """
        Finish sequence:
          1) lift to safe_x if touching paper
          2) retreat farther to ready_x
          3) joint-space to READY posture
          4) UFACTORY Initial Position / home
        """
        arm = self._require_arm()
        s = self.settings

        x, y, z, roll, pitch, yaw = self.get_pose()
        current_orientation = (roll, pitch, yaw)

        if x < s.safe_x:
            self.log(
                f"Retracting marker from paper: X {x:.1f} -> {s.safe_x:.1f}"
            )
            self.move_absolute(
                s.safe_x,
                y,
                z,
                speed=s.contact_speed,
                orientation=current_orientation,
            )
            x = s.safe_x

        if x < s.ready_x:
            self.log(
                f"Retreating farther from paper: X {x:.1f} -> {s.ready_x:.1f}"
            )
            self.move_absolute(
                s.ready_x,
                y,
                z,
                speed=s.move_speed,
                orientation=current_orientation,
            )

        self.log("Moving to READY joint posture before homing...")
        self.move_joints_absolute(s.ready_joints)

        self.log("Returning to UFACTORY Initial Position...")
        ret = arm.move_gohome(
            speed=s.joint_speed,
            wait=True,
        )
        self._check_ret("move_gohome", ret)

        self.log("Initial Position reached.")

    # ============================================================
    # MARKER MOVEMENT
    # ============================================================

    def marker_contact(self) -> None:
        s = self.settings
        _, y, z, _, _, _ = self.get_pose()

        if s.air_draw:
            self.log("[AIR DRAW] Contact skipped; marker stays at safe X.")
            self.move_absolute(
                s.safe_x,
                y,
                z,
                speed=s.contact_speed,
            )
            return

        contact_x = self.paper_contact_x(y, z)

        self.log(
            f"Marker contact at Y={y:.1f}, Z={z:.1f}: X -> {contact_x:.2f}"
        )
        self.move_absolute(
            contact_x,
            y,
            z,
            speed=s.contact_speed,
        )

    def marker_away(self) -> None:
        s = self.settings
        x, y, z, _, _, _ = self.get_pose()

        self.log(f"Marker away: X {x:.2f} -> {s.safe_x:.2f}")
        self.move_absolute(
            s.safe_x,
            y,
            z,
            speed=s.contact_speed,
        )

    def safe_move_to(self, y: float, z: float) -> None:
        self.move_absolute(
            self.settings.safe_x,
            y,
            z,
            speed=self.settings.move_speed,
        )

    def contact_move_to(self, y: float, z: float) -> None:
        if self.settings.air_draw:
            self.safe_move_to(y, z)
            return

        contact_x = self.paper_contact_x(y, z)
        self.move_absolute(
            contact_x,
            y,
            z,
            speed=self.settings.move_speed,
        )

    # ============================================================
    # LETTER GEOMETRY
    # ============================================================

    def build_points(self) -> Dict[PointName, Tuple[float, float]]:
        """
        Point offsets are (dY, dZ).

                    +Z
                     ^
             1 ----- 2 ----- 3
             |               |
             4 ----- 5 ----- 6    +Y ->
             |               |
             7 ----- 8 ----- 9

        Point 5 is the current letter center.
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

            "A_LEFT": (-w / 2, 0),
            "A_RIGHT": (+w / 2, 0),

            "DOT_TOP_LEFT": (-w / 2, h + 4),
            "DOT_TOP_RIGHT": (+w / 2, h + 4),

            "TILDE_LEFT": (-w / 2, h + 4),
            "TILDE_MID_LEFT": (-w / 6, h + 6),
            "TILDE_MID_RIGHT": (+w / 6, h + 2),
            "TILDE_RIGHT": (+w / 2, h + 4),
        }

    @staticmethod
    def build_letters() -> LetterMap:
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
    # ABSOLUTE WRITING
    # ============================================================

    def point_position(
        self,
        center_y: float,
        center_z: float,
        point: PointName,
    ) -> Tuple[float, float]:
        dy, dz = self.points[point]
        return center_y + dy, center_z + dz

    def draw_stroke_at(
        self,
        center_y: float,
        center_z: float,
        stroke: Stroke,
    ) -> None:
        if not stroke:
            return

        first_y, first_z = self.point_position(
            center_y,
            center_z,
            stroke[0],
        )

        # Travel to stroke start at safe_x.
        self.safe_move_to(first_y, first_z)

        # Contact or stay in air-draw mode.
        self.marker_contact()

        # Follow calibrated paper surface while drawing.
        for point in stroke[1:]:
            y, z = self.point_position(
                center_y,
                center_z,
                point,
            )
            self.contact_move_to(y, z)

        # Lift after stroke.
        self.marker_away()

    def draw_letter_at(
        self,
        center_y: float,
        center_z: float,
        letter: str,
    ) -> None:
        letter = letter.upper()

        if letter not in self.letters:
            raise ValueError(f"Letter '{letter}' is not defined.")

        self.log(
            f"--- Drawing {letter} at Y={center_y:.1f}, Z={center_z:.1f} ---"
        )

        for stroke in self.letters[letter]:
            self.draw_stroke_at(
                center_y,
                center_z,
                stroke,
            )

        self.safe_move_to(center_y, center_z)

    def write_text(
        self,
        text: str,
        *,
        move_to_start: bool = True,
    ) -> None:
        if not text:
            self.log("No text entered.")
            return

        # Normalise newline styles while preserving intentional blank rows.
        text = text.replace("\r\n", "\n").replace("\r", "\n").upper()
        lines = text.split("\n")

        unsupported = sorted(
            {
                ch
                for ch in text
                if ch not in (" ", "\n") and ch not in self.letters
            }
        )

        if unsupported:
            raise ValueError(
                "Unsupported character(s): " + ", ".join(unsupported)
            )

        requested_rows = len(lines)
        paper_rows = self.rows_that_fit

        if requested_rows > self.settings.max_rows:
            raise ValueError(
                f"Text uses {requested_rows} rows, but Max rows is "
                f"{self.settings.max_rows}."
            )

        if requested_rows > paper_rows:
            raise ValueError(
                f"Text uses {requested_rows} rows, but only {paper_rows} "
                "complete rows fit on the calibrated paper with the current "
                "letter height and row spacing."
            )

        if paper_rows <= 0:
            raise ValueError(
                "No complete rows fit on the calibrated paper with the "
                "current settings."
            )

        if move_to_start:
            self.go_to_writing_start()

        center_y = self.settings.start_y

        for row_index, line in enumerate(lines):
            center_y = self.settings.start_y
            center_z = self.start_z - (
                row_index * self.settings.row_spacing
            )

            self.log(
                f"=== Row {row_index + 1}/{requested_rows}: "
                f"Y={center_y:.1f}, Z={center_z:.1f} ==="
            )

            # New row: marker remains lifted at safe_x while returning left
            # and moving down in -Z.
            if row_index > 0:
                self.safe_move_to(center_y, center_z)

            for character in line:
                if character == " ":
                    center_y += self.settings.space_step
                    self.safe_move_to(center_y, center_z)
                    continue

                self.draw_letter_at(
                    center_y,
                    center_z,
                    character,
                )
                center_y += self.settings.letter_step

        # Finish lifted at the end of the final row.
        if lines:
            final_row_z = self.start_z - (
                (requested_rows - 1) * self.settings.row_spacing
            )
            self.safe_move_to(center_y, final_row_z)

        self.log(f"Finished writing {requested_rows} row(s).")

    # ============================================================
    # TEST SHAPES
    # ============================================================

    def test_horizontal_line(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: horizontal line")
        self.draw_stroke_at(
            self.settings.start_y,
            self.start_z,
            [4, 6],
        )

    def test_vertical_line(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: vertical line")
        self.draw_stroke_at(
            self.settings.start_y,
            self.start_z,
            [8, 2],
        )

    def test_square(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: square")
        self.draw_stroke_at(
            self.settings.start_y,
            self.start_z,
            [1, 3, 9, 7, 1],
        )

    def test_letter_a(self) -> None:
        self.go_to_writing_start()
        self.log("TEST: letter A")
        self.draw_letter_at(
            self.settings.start_y,
            self.start_z,
            "A",
        )
