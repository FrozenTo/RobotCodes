"""
MG400 text writer core logic.

This module contains:
- MG400 TCP/IP socket communication
- configurable writing settings
- 9-point stroke alphabet
- Estonian special letters and punctuation
- manual row/start-position handling

The GUI lives in mg400_writer_app.py.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import socket
import time
from typing import Callable, Dict, Hashable, List, Optional, Tuple


PointName = Hashable
Stroke = List[PointName]
LetterMap = Dict[str, List[Stroke]]
LogCallback = Callable[[str], None]


@dataclass
class WriterSettings:
    # Robot connection
    live_robot: bool = True
    ip: str = "192.168.2.6"
    dashboard_port: int = 29999
    motion_port: int = 30003
    speed_factor: int = 100
    move_delay: float = 0.1

    # Writing geometry
    half_height: float = 10.0
    half_width: float = 5.0
    letter_step: float = 12.0
    space_step: float = 25.0
    pen_drop: float = -15.0
    #161
    #146
    # Writing start / rows
    # This keeps the current script's effective first-row Y:
    # BASE Y -160.10 + 75 = -85.10
    base_x: float = 260.00
    base_y: float = -85.10
    base_z: float = -147.6
    base_r: float = -21.40
    row_step: float = 27.0
    current_row: int = 0

    # Paper limits noted in the current script.
    # These are stored for future warning/check logic, but not enforced yet.
    paper_min_x: float = 225.87
    paper_max_x: float = 376.30
    paper_min_y: float = -155.97
    paper_max_y: float = 90.00


def default_logger(message: str) -> None:
    print(message)


class MG400Writer:
    def __init__(self, settings: Optional[WriterSettings] = None, logger: Optional[LogCallback] = None):
        self.settings = settings or WriterSettings()
        self.log = logger or default_logger

        self.dashboard_sock: Optional[socket.socket] = None
        self.motion_sock: Optional[socket.socket] = None

        self.points = self.build_points()
        self.letters = self.build_letters()

    # ============================================================
    # CONFIGURATION
    # ============================================================

    def rebuild_geometry(self) -> None:
        """Rebuild relative grid/helper points after dimension changes."""
        self.points = self.build_points()

    def writing_start(self) -> Tuple[float, float, float, float]:
        """
        Current Above5 position for the chosen row.
        +X moves down the page in the current physical layout.
        """
        s = self.settings
        return (
            s.base_x + s.current_row * s.row_step,
            s.base_y,
            s.base_z,
            s.base_r,
        )

    def draw_underline(self) -> None:
        """
        Draw a fixed underline using absolute X/Y coordinates.

        Start: X 276.0, Y -94.5
        End:   X 273.5, Y -2.0
        """

        start_x = 276.0
        start_y = -94.5

        end_x = 273.5
        end_y = -2.0

        # Use the current writing-start lifted Z and R.
        _, _, lifted_z, r = self.writing_start()

        # PEN_DROP is negative in the current settings.
        writing_z = lifted_z + self.settings.pen_drop

        self.log(
            "Drawing underline: "
            f"({start_x}, {start_y}) -> ({end_x}, {end_y})"
        )

        # Move above the beginning of the underline.
        self.send_motion(
            f"MovJ({start_x},{start_y},{lifted_z},{r})"
        )

        # Lower the pen.
        self.send_motion(
            f"MovL({start_x},{start_y},{writing_z},{r})"
        )

        # Draw the underline.
        self.send_motion(
            f"MovL({end_x},{end_y},{writing_z},{r})"
        )

        # Lift the pen at the endpoint.
        self.send_motion(
            f"MovL({end_x},{end_y},{lifted_z},{r})"
        )

        self.log("Finished drawing underline.")


    def next_row(self) -> None:
        self.settings.current_row += 1
        self.log(f"Current row changed to {self.settings.current_row}.")

    def previous_row(self) -> None:
        if self.settings.current_row > 0:
            self.settings.current_row -= 1
        self.log(f"Current row changed to {self.settings.current_row}.")

    # ============================================================
    # GEOMETRY / ALPHABET
    # ============================================================

    def build_points(self) -> Dict[PointName, Tuple[float, float]]:
        h = self.settings.half_height
        w = self.settings.half_width

        return {
            1: (-h, -w),
            2: (-h, 0),
            3: (-h, w),

            4: (0, -w),
            5: (0, 0),
            6: (0, w),

            7: (h, -w),
            8: (h, 0),
            9: (h, w),

            # Special crossbar for A
            "A_LEFT": (0, -w / 2),
            "A_RIGHT": (0, w / 2),

            # Dots above letters: Ä, Ö, Ü
            "DOT_TOP_LEFT": (-h - 4, -w / 2),
            "DOT_TOP_RIGHT": (-h - 4, w / 2),

            # Small angular tilde for Õ
            "TILDE_LEFT": (-h - 4, -w / 2),
            "TILDE_MID_LEFT": (-h - 6, -w / 6),
            "TILDE_MID_RIGHT": (-h - 2, w / 6),
            "TILDE_RIGHT": (-h - 4, w / 2),
        }

    @staticmethod
    def build_letters() -> LetterMap:
        return {
            "A": [
                [7, 2, 9],
                ["A_LEFT", "A_RIGHT"],
            ],
            "B": [
                [7, 1, 3, 6, 4, 6, 9, 7],
            ],
            "C": [
                [3, 1, 7, 9],
            ],
            "D": [
                [7, 1, 2, 6, 8, 7],
            ],
            "E": [
                [3, 1, 7, 9],
                [4, 6],
            ],
            "F": [
                [3, 1, 7],
                [4, 6],
            ],
            "G": [
                [3, 1, 7, 9, 6, 5],
            ],
            "H": [
                [1, 7],
                [3, 9],
                [4, 6],
            ],
            "I": [
                [1, 3],
                [2, 8],
                [7, 9],
            ],
            "J": [
                [1, 3],
                [2, 8, 7],
            ],
            "K": [
                [1, 7],
                [3, 4, 9],
            ],
            "L": [
                [1, 7, 9],
            ],
            "M": [
                [7, 1, 8, 3, 9],
            ],
            "N": [
                [7, 1, 9, 3],
            ],
            "O": [
                [1, 3, 9, 7, 1],
            ],
            "P": [
                [7, 1, 3, 6, 4],
            ],
            "Q": [
                [1, 3, 9, 7, 1],
                [5, 9],
            ],
            "R": [
                [7, 1, 3, 6, 4, 9],
            ],
            "S": [
                [3, 1, 4, 6, 9, 7],
            ],
            "T": [
                [1, 3],
                [2, 8],
            ],
            "U": [
                [1, 7, 9, 3],
            ],
            "V": [
                [1, 8, 3],
            ],
            "W": [
                [1, 7, 2, 9, 3],
            ],
            "X": [
                [1, 9],
                [3, 7],
            ],
            "Y": [
                [1, 5, 3],
                [5, 8],
            ],
            "Z": [
                [1, 3, 7, 9],
            ],

            "!": [
                [2, 5],
                [8],
            ],
            "?": [
                [1, 3, 6, 5],
                [8],
            ],
            ".": [
                [8],
            ],

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
                ["TILDE_LEFT", "TILDE_MID_LEFT", "TILDE_MID_RIGHT", "TILDE_RIGHT"],
            ],
        }

    # ============================================================
    # SOCKET / ROBOT CONTROL
    # ============================================================

    @property
    def is_connected(self) -> bool:
        if not self.settings.live_robot:
            return False
        return self.dashboard_sock is not None and self.motion_sock is not None

    def connect_robot(self) -> None:
        if not self.settings.live_robot:
            self.log("[DRY RUN] Robot sockets not opened.")
            return

        if self.is_connected:
            self.log("Robot is already connected.")
            return

        s = self.settings
        try:
            self.dashboard_sock = socket.socket()
            self.dashboard_sock.connect((s.ip, s.dashboard_port))

            self.motion_sock = socket.socket()
            self.motion_sock.connect((s.ip, s.motion_port))

            self.log(f"Connected to MG400 at {s.ip}.")
        except Exception:
            self.close_robot()
            raise

    def close_robot(self) -> None:
        for sock in (self.dashboard_sock, self.motion_sock):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

        self.dashboard_sock = None
        self.motion_sock = None
        self.log("Sockets closed.")

    def _send_socket_command(self, sock: Optional[socket.socket], cmd: str, channel_name: str) -> str:
        if not self.settings.live_robot:
            self.log(f"[{channel_name}] {cmd}")
            return "[DRY RUN]"

        if sock is None:
            raise RuntimeError(f"{channel_name} socket is not connected.")

        self.log(f">> {cmd}")
        sock.send((cmd + "\r\n").encode())
        response = sock.recv(1024).decode().strip()
        self.log(f"<< {response}")
        return response

    def send_dashboard(self, cmd: str) -> str:
        return self._send_socket_command(self.dashboard_sock, cmd, "DASHBOARD")

    def send_motion(self, cmd: str) -> str:
        response = self._send_socket_command(self.motion_sock, cmd, "MOTION")
        if self.settings.move_delay > 0:
            time.sleep(self.settings.move_delay)
        return response

    def setup_robot(self) -> None:
        self.send_dashboard("ClearError()")
        self.send_dashboard("EnableRobot()")
        self.send_dashboard(f"SpeedFactor({self.settings.speed_factor})")
        time.sleep(1)

    def go_to_writing_start(self) -> None:
        x, y, z, r = self.writing_start()
        self.log(
            "Moving to WritingStart: "
            f"X={x:.2f}, Y={y:.2f}, Z={z:.2f}, R={r:.2f}"
        )
        self.send_motion(f"MovJ({x},{y},{z},{r})")

    def get_current_pose(self) -> Tuple[float, float, float, float]:
        """Read the robot's current X, Y, Z, R pose using GetPose()."""
        if not self.settings.live_robot:
            raise RuntimeError("Current robot pose is unavailable in Dry Run mode.")

        if self.dashboard_sock is None:
            raise RuntimeError("Robot is not connected.")

        response = self.send_dashboard("GetPose()")

        # Typical response:
        # 0,{356.978235,-175.182068,-165.186523,-300.645996},GetPose();
        match = re.search(r"\{([^}]*)\}", response)
        if not match:
            raise ValueError(f"Could not parse GetPose response: {response}")

        values = [part.strip() for part in match.group(1).split(",")]
        if len(values) < 4:
            raise ValueError(f"GetPose did not return X, Y, Z, R: {response}")

        try:
            x, y, z, r = (float(values[i]) for i in range(4))
        except ValueError as exc:
            raise ValueError(f"Invalid GetPose values: {response}") from exc

        self.log(
            f"Current pose: X={x:.3f}, Y={y:.3f}, Z={z:.3f}, R={r:.3f}"
        )
        return x, y, z, r

    def move_to_pose(self, x: float, y: float, z: float, r: float) -> None:
        """Move directly to an absolute saved pose."""
        self.log(
            f"Moving to saved pose: X={x:.3f}, Y={y:.3f}, "
            f"Z={z:.3f}, R={r:.3f}"
        )
        self.send_motion(f"MovJ({x},{y},{z},{r})")

    # ============================================================
    # WRITING MOTION HELPERS
    # ============================================================

    def rel_move(self, dx: float, dy: float, dz: float = 0, dr: float = 0) -> None:
        self.send_motion(f"RelMovL({dx},{dy},{dz},{dr})")

    def pen_down(self) -> None:
        self.rel_move(0, 0, self.settings.pen_drop, 0)

    def pen_up(self) -> None:
        self.rel_move(0, 0, -self.settings.pen_drop, 0)

    # ============================================================
    # LETTER DRAWING
    # ============================================================

    def move_from_center_to_point(self, point: PointName) -> None:
        dx, dy = self.points[point]
        self.rel_move(dx, dy, 0, 0)

    def move_between_points(self, start_point: PointName, end_point: PointName) -> None:
        x1, y1 = self.points[start_point]
        x2, y2 = self.points[end_point]
        self.rel_move(x2 - x1, y2 - y1, 0, 0)

    def return_from_point_to_center(self, point: PointName) -> None:
        dx, dy = self.points[point]
        self.rel_move(-dx, -dy, 0, 0)

    def draw_stroke(self, stroke: Stroke) -> None:
        if not stroke:
            return

        first_point = stroke[0]
        last_point = stroke[-1]

        self.move_from_center_to_point(first_point)
        self.pen_down()

        for current_point, next_point in zip(stroke, stroke[1:]):
            self.move_between_points(current_point, next_point)

        self.pen_up()
        self.return_from_point_to_center(last_point)

    def draw_letter(self, letter: str) -> None:
        letter = letter.upper()
        if letter not in self.letters:
            raise ValueError(f"Letter '{letter}' is not defined.")

        self.log(f"--- Drawing {letter} ---")
        for stroke in self.letters[letter]:
            self.draw_stroke(stroke)

    def move_to_next_letter(self) -> None:
        self.log("--- Moving to next letter ---")
        self.rel_move(0, self.settings.letter_step, 0, 0)

    def move_for_space(self) -> None:
        self.log("--- Space ---")
        self.rel_move(0, self.settings.space_step, 0, 0)

    def write_text(self, text: str) -> None:
        if not text:
            self.log("No text entered.")
            return

        text = text.upper()

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
