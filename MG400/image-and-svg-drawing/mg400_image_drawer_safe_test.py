"""
MG400 simplified building drawer - first safe-area test.

This file is intentionally separate from:
    mg400_writer.py
    mg400_writer_app.py

It reuses MG400Writer for the Ethernet connection and motion commands.

What this version adds:
- measured paper geometry from the pen-tip tests
- ~55.5 mm pen offset from the flange
- R compensation so the desired PEN TIP position stays approximately fixed
- four conservative R zones based on the measured paper corners
- J4 monitoring with a software safety margin
- a pen-up preflight mode before actual drawing

IMPORTANT:
The pen-offset model is still an approximation. Keep PREFLIGHT_ONLY = True
for the first live test and watch the robot carefully.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import List, Sequence, Tuple

from mg400_writer import MG400Writer


Point2D = Tuple[float, float]
Path2D = Sequence[Point2D]

ROBOT_IP = "192.168.1.6"

# ============================================================
# FIRST-TEST SWITCHES
# ============================================================

# False = print commands only, no physical robot movement.
LIVE_ROBOT = True

# When True and LIVE_ROBOT=True:
# the robot visits the planned points with the pen lifted,
# checks J4, and DOES NOT DRAW.
#
# First real robot run should use:
# LIVE_ROBOT = True
# PREFLIGHT_ONLY = True
PREFLIGHT_ONLY = False


# ============================================================
# MEASURED PEN / ROBOT GEOMETRY
# ============================================================

# Approximate centre-to-centre distance:
# flange rotation axis -> pen axis
PEN_RADIUS_MM = 55.5

# From the user's measured R directions:
# R ≈ -26° points the pen almost exactly toward robot +X
# (down the paper).
#
# Therefore pen offset angle in XY ≈ R + 26°.
PEN_ANGLE_OFFSET_DEG = 26.0


# ============================================================
# MEASURED PAPER / SAFE AREA
# ============================================================
#
# These are conservative PEN-TIP coordinates derived from the
# measured corner poses and the 55.5 mm radial pen offset.
#
# Main rectangle is approximately:
#   260 mm wide  (robot Y direction)
#   123 mm high  (robot X direction)
#
# For the FIRST DRAWING TEST we deliberately inset from the edges.
# ============================================================

PAPER_TOP_X = 260.0
PAPER_BOTTOM_X = 383.0

PAPER_LEFT_Y = -123.0
PAPER_RIGHT_Y = 137.0

PAPER_WIDTH_MM = PAPER_RIGHT_Y - PAPER_LEFT_Y     # ~260 mm
PAPER_HEIGHT_MM = PAPER_BOTTOM_X - PAPER_TOP_X    # ~123 mm

# Additional bottom area discussed:
BOTTOM_EXTENSION_MM = 16.0
BOTTOM_SIDE_INSET_MM = 40.0

# First test is intentionally smaller than the known rectangle.
TEST_DRAWING_WIDTH_MM = 220.0
TEST_DRAWING_HEIGHT_MM = 100.0


# ============================================================
# MEASURED R VALUES
# ============================================================
#
# These are based on the corner / limit tests.
# We keep R fixed while drawing each individual line segment.
#
#              top
#       TL                 TR
#      -162               +107
#
#       BL                 BR
#       -72                +18
#              bottom
#
# Later we can make this smarter / smoother.
# ============================================================

R_TOP_LEFT = -162.15
R_TOP_RIGHT = 107.45
R_BOTTOM_LEFT = -72.24
R_BOTTOM_RIGHT = 17.86

# Useful special orientation for the extra bottom strip.
R_BOTTOM_EXTENSION = -27.24


# ============================================================
# J4 SAFETY
# ============================================================

J4_HARD_MIN = -177.0
J4_HARD_MAX = 120.0

# Do not intentionally automate right up to the physical holder limits.
J4_MARGIN_DEG = 5.0

J4_SAFE_MIN = J4_HARD_MIN + J4_MARGIN_DEG   # -172
J4_SAFE_MAX = J4_HARD_MAX - J4_MARGIN_DEG   # +115

# Long drawing lines are subdivided so the preflight checks
# intermediate positions rather than only the endpoints.
MAX_SEGMENT_MM = 10.0


# ============================================================
# SIMPLE BUILDING
# ============================================================
#
# Normalized coordinates:
# x: 0..1 = left -> right
# y: 0..1 = top -> bottom
#
# This is intentionally a simplified architectural sketch,
# not an automatic trace of the source image.
# ============================================================

SIMPLE_BUILDING_PATHS: List[List[Point2D]] = [
    # Main roof and outer structure
    [(0.18, 0.25), (0.33, 0.08), (0.78, 0.12), (0.88, 0.23)],
    [(0.18, 0.25), (0.76, 0.29), (0.88, 0.23)],
    [(0.18, 0.25), (0.18, 0.76), (0.76, 0.80), (0.76, 0.29)],
    [(0.76, 0.29), (0.88, 0.23), (0.88, 0.69), (0.76, 0.80)],

    # Floor divisions
    [(0.18, 0.43), (0.76, 0.47)],
    [(0.18, 0.60), (0.76, 0.64)],
    [(0.76, 0.47), (0.88, 0.42)],
    [(0.76, 0.64), (0.88, 0.57)],

    # Roof details
    [(0.33, 0.08), (0.45, 0.18), (0.78, 0.12)],
    [(0.26, 0.23), (0.37, 0.11)],
    [(0.36, 0.24), (0.45, 0.10)],
    [(0.47, 0.26), (0.54, 0.10)],
    [(0.58, 0.27), (0.63, 0.11)],
    [(0.68, 0.28), (0.72, 0.12)],

    # Upper windows
    [(0.24, 0.34), (0.24, 0.41), (0.28, 0.41), (0.28, 0.34), (0.24, 0.34)],
    [(0.34, 0.35), (0.34, 0.42), (0.38, 0.42), (0.38, 0.35), (0.34, 0.35)],
    [(0.44, 0.36), (0.44, 0.43), (0.48, 0.43), (0.48, 0.36), (0.44, 0.36)],
    [(0.54, 0.37), (0.54, 0.44), (0.58, 0.44), (0.58, 0.37), (0.54, 0.37)],
    [(0.64, 0.38), (0.64, 0.45), (0.68, 0.45), (0.68, 0.38), (0.64, 0.38)],

    # Middle windows
    [(0.25, 0.49), (0.25, 0.57), (0.29, 0.57), (0.29, 0.49), (0.25, 0.49)],
    [(0.36, 0.50), (0.36, 0.58), (0.40, 0.58), (0.40, 0.50), (0.36, 0.50)],
    [(0.47, 0.51), (0.47, 0.59), (0.51, 0.59), (0.51, 0.51), (0.47, 0.51)],
    [(0.58, 0.52), (0.58, 0.60), (0.62, 0.60), (0.62, 0.52), (0.58, 0.52)],
    [(0.68, 0.53), (0.68, 0.61), (0.72, 0.61), (0.72, 0.53), (0.68, 0.53)],

    # Ground arches
    [(0.23, 0.76), (0.23, 0.68), (0.25, 0.65), (0.27, 0.68), (0.27, 0.76)],
    [(0.32, 0.77), (0.32, 0.69), (0.34, 0.66), (0.36, 0.69), (0.36, 0.77)],
    [(0.41, 0.77), (0.41, 0.69), (0.43, 0.66), (0.45, 0.69), (0.45, 0.77)],
    [(0.50, 0.78), (0.50, 0.70), (0.52, 0.67), (0.54, 0.70), (0.54, 0.78)],
    [(0.59, 0.78), (0.59, 0.70), (0.61, 0.67), (0.63, 0.70), (0.63, 0.78)],
    [(0.68, 0.79), (0.68, 0.71), (0.70, 0.68), (0.72, 0.71), (0.72, 0.79)],

    # Right-side windows
    [(0.79, 0.34), (0.79, 0.41), (0.82, 0.40), (0.82, 0.33), (0.79, 0.34)],
    [(0.84, 0.32), (0.84, 0.39), (0.87, 0.38), (0.87, 0.31), (0.84, 0.32)],
    [(0.79, 0.50), (0.79, 0.57), (0.82, 0.55), (0.82, 0.48), (0.79, 0.50)],
    [(0.84, 0.47), (0.84, 0.54), (0.87, 0.52), (0.87, 0.45), (0.84, 0.47)],

    # Courtyard / foreground
    [(0.18, 0.76), (0.08, 0.77), (0.04, 0.84), (0.14, 0.88)],
    [(0.18, 0.76), (0.12, 0.83), (0.21, 0.88), (0.41, 0.86)],
    [(0.41, 0.86), (0.55, 0.83), (0.76, 0.80)],

    # Foreground rectangles
    [(0.08, 0.79), (0.16, 0.79), (0.16, 0.83), (0.08, 0.83), (0.08, 0.79)],
    [(0.23, 0.83), (0.31, 0.83), (0.31, 0.87), (0.23, 0.87), (0.23, 0.83)],
]


@dataclass
class DrawerSettings:
    drawing_width_mm: float = TEST_DRAWING_WIDTH_MM
    drawing_height_mm: float = TEST_DRAWING_HEIGHT_MM

    # Keep the first test inside the measured main rectangle.
    use_bottom_extension: bool = False

    # Height above writing surface used during path-to-path travel.
    # The actual lifted Z comes from the measured writing surface + this value.
    travel_lift_mm: float = 10.0


class MG400ImageDrawer:
    def __init__(
        self,
        writer: MG400Writer,
        settings: DrawerSettings | None = None,
    ):
        self.writer = writer
        self.settings = settings or DrawerSettings()

    # ============================================================
    # PEN OFFSET
    # ============================================================

    @staticmethod
    def pen_offset_for_r(r_deg: float) -> Tuple[float, float]:
        """
        Approximate XY offset from flange centre to pen tip.
        """
        angle = math.radians(r_deg + PEN_ANGLE_OFFSET_DEG)

        offset_x = PEN_RADIUS_MM * math.cos(angle)
        offset_y = PEN_RADIUS_MM * math.sin(angle)

        return offset_x, offset_y

    @classmethod
    def flange_for_pen_tip(
        cls,
        pen_x: float,
        pen_y: float,
        r_deg: float,
    ) -> Tuple[float, float]:
        """
        Given a desired pen-tip XY and R, calculate the approximate
        flange XY that keeps the pen tip at that point.
        """
        offset_x, offset_y = cls.pen_offset_for_r(r_deg)

        flange_x = pen_x - offset_x
        flange_y = pen_y - offset_y

        return flange_x, flange_y

    # ============================================================
    # DRAWING AREA
    # ============================================================

    def test_area_origin(self) -> Tuple[float, float]:
        """
        Centre the first test drawing inside the known main rectangle.

        Returns PEN-TIP coordinates for the test drawing top-left.
        """
        left_margin = (PAPER_WIDTH_MM - self.settings.drawing_width_mm) / 2
        top_margin = (PAPER_HEIGHT_MM - self.settings.drawing_height_mm) / 2

        top_x = PAPER_TOP_X + top_margin
        left_y = PAPER_LEFT_Y + left_margin

        return top_x, left_y

    def normalized_to_pen_tip(self, point: Point2D) -> Tuple[float, float]:
        """
        normalized x = left -> right
        normalized y = top -> bottom

        Robot paper directions:
        +Y = right
        +X = down
        """
        nx, ny = point
        origin_x, origin_y = self.test_area_origin()

        pen_x = origin_x + ny * self.settings.drawing_height_mm
        pen_y = origin_y + nx * self.settings.drawing_width_mm

        return pen_x, pen_y

    # ============================================================
    # R ZONES
    # ============================================================

    @staticmethod
    def choose_r_for_pen_tip(pen_x: float, pen_y: float) -> float:
        """
        First conservative rule:
        choose the measured R from the nearest paper quadrant.

        We intentionally do NOT change R while the pen is down.
        """
        center_x = (PAPER_TOP_X + PAPER_BOTTOM_X) / 2
        center_y = (PAPER_LEFT_Y + PAPER_RIGHT_Y) / 2

        top_half = pen_x <= center_x
        left_half = pen_y <= center_y

        if top_half and left_half:
            return R_TOP_LEFT

        if top_half and not left_half:
            return R_TOP_RIGHT

        if not top_half and left_half:
            return R_BOTTOM_LEFT

        return R_BOTTOM_RIGHT

    # ============================================================
    # J4 CHECKING
    # ============================================================

    def get_joint_angles(self) -> Tuple[float, float, float, float]:
        response = self.writer.send_dashboard("GetAngle()")

        match = re.search(r"\{([^}]*)\}", response)
        if not match:
            raise ValueError(f"Could not parse GetAngle response: {response}")

        values = [
            float(value.strip())
            for value in match.group(1).split(",")
        ]

        if len(values) < 4:
            raise ValueError(f"GetAngle returned too few values: {response}")

        return values[0], values[1], values[2], values[3]

    def check_j4(self, context: str = "") -> float:
        if not self.writer.settings.live_robot:
            return 0.0

        _, _, _, j4 = self.get_joint_angles()

        self.writer.log(
            f"J4 check {context}: {j4:.2f}° "
            f"(safe {J4_SAFE_MIN:.1f}° .. {J4_SAFE_MAX:.1f}°)"
        )

        if j4 < J4_SAFE_MIN or j4 > J4_SAFE_MAX:
            raise RuntimeError(
                f"J4 safety stop: {j4:.2f}° is outside "
                f"{J4_SAFE_MIN:.1f}° .. {J4_SAFE_MAX:.1f}°"
            )

        return j4

    # ============================================================
    # SEGMENT PREPARATION
    # ============================================================

    @staticmethod
    def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return math.hypot(b[0] - a[0], b[1] - a[1])

    @classmethod
    def subdivide_segment(
        cls,
        start: Tuple[float, float],
        end: Tuple[float, float],
        max_length: float = MAX_SEGMENT_MM,
    ) -> List[Tuple[float, float]]:
        """
        Return points including start and end, with no step longer
        than max_length.
        """
        total = cls.distance(start, end)

        if total <= max_length:
            return [start, end]

        steps = math.ceil(total / max_length)

        result = []
        for i in range(steps + 1):
            t = i / steps
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            result.append((x, y))

        return result

    def iter_pen_segments(self):
        """
        Yield short PEN-TIP line segments.

        For this first version, every original polyline edge is
        treated as an independent drawing stroke. This keeps R fixed
        while the pen is touching the paper.
        """
        for path_index, path in enumerate(SIMPLE_BUILDING_PATHS, start=1):
            for point_index, (a, b) in enumerate(zip(path, path[1:]), start=1):
                pen_a = self.normalized_to_pen_tip(a)
                pen_b = self.normalized_to_pen_tip(b)

                subdivided = self.subdivide_segment(pen_a, pen_b)

                for short_index, (s, e) in enumerate(
                    zip(subdivided, subdivided[1:]),
                    start=1,
                ):
                    yield (
                        path_index,
                        point_index,
                        short_index,
                        s,
                        e,
                    )

    # ============================================================
    # MOTION
    # ============================================================

    def move_flange_above_pen_tip(
        self,
        pen_x: float,
        pen_y: float,
        r_deg: float,
        lifted_z: float,
    ) -> None:
        flange_x, flange_y = self.flange_for_pen_tip(
            pen_x,
            pen_y,
            r_deg,
        )

        self.writer.send_motion(
            f"MovJ({flange_x:.3f},{flange_y:.3f},{lifted_z:.3f},{r_deg:.3f})"
        )

    def preflight(self) -> None:
        """
        Pen-up reach/J4 test.

        It visits the start and end of every short drawing segment,
        checks J4, and never lowers the pen.
        """
        writing_z = -197.30
        lifted_z = writing_z + self.settings.travel_lift_mm

        segments = list(self.iter_pen_segments())

        self.writer.log(
            f"Starting PRE-FLIGHT for {len(segments)} short segments."
        )
        self.writer.log(
            f"Pen stays lifted at Z={lifted_z:.2f}."
        )

        for index, (_, _, _, start, end) in enumerate(segments, start=1):
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            r_deg = self.choose_r_for_pen_tip(mid_x, mid_y)

            self.writer.log(
                f"[Preflight {index}/{len(segments)}] "
                f"R={r_deg:.2f}°"
            )

            self.move_flange_above_pen_tip(
                start[0], start[1], r_deg, lifted_z
            )
            self.check_j4("segment start")

            self.move_flange_above_pen_tip(
                end[0], end[1], r_deg, lifted_z
            )
            self.check_j4("segment end")

        self.writer.log("PRE-FLIGHT completed successfully.")

    def draw(self) -> None:
        """
        Actual drawing.

        Every short segment:
        - choose one R
        - move above start
        - lower pen
        - draw segment
        - lift pen

        R never changes while the pen is down.
        """
        writing_z = -197.30
        lifted_z = writing_z + self.settings.travel_lift_mm

        segments = list(self.iter_pen_segments())

        self.writer.log(
            f"Starting simplified building drawing: {len(segments)} segments."
        )
        self.writer.log(
            f"Test area: {self.settings.drawing_width_mm:.1f} x "
            f"{self.settings.drawing_height_mm:.1f} mm"
        )

        for index, (_, _, _, start, end) in enumerate(segments, start=1):
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2

            r_deg = self.choose_r_for_pen_tip(mid_x, mid_y)

            start_fx, start_fy = self.flange_for_pen_tip(
                start[0], start[1], r_deg
            )
            end_fx, end_fy = self.flange_for_pen_tip(
                end[0], end[1], r_deg
            )

            self.writer.log(
                f"[Draw {index}/{len(segments)}] "
                f"R={r_deg:.2f}°"
            )

            # Travel above start.
            self.writer.send_motion(
                f"MovJ({start_fx:.3f},{start_fy:.3f},{lifted_z:.3f},{r_deg:.3f})"
            )
            self.check_j4("before pen down")

            # Pen down.
            self.writer.send_motion(
                f"MovL({start_fx:.3f},{start_fy:.3f},{writing_z:.3f},{r_deg:.3f})"
            )

            # Draw.
            self.writer.send_motion(
                f"MovL({end_fx:.3f},{end_fy:.3f},{writing_z:.3f},{r_deg:.3f})"
            )

            # Pen up.
            self.writer.send_motion(
                f"MovL({end_fx:.3f},{end_fy:.3f},{lifted_z:.3f},{r_deg:.3f})"
            )

            self.check_j4("after segment")

        self.writer.log("Finished simplified building drawing.")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    writer = MG400Writer()
    writer.settings.ip = ROBOT_IP
    writer.settings.live_robot = LIVE_ROBOT 

    drawer = MG400ImageDrawer(
        writer,
        DrawerSettings(
            drawing_width_mm=TEST_DRAWING_WIDTH_MM,
            drawing_height_mm=TEST_DRAWING_HEIGHT_MM,
            use_bottom_extension=False,
            travel_lift_mm=10.0,
        ),
    )

    print()
    print("MG400 BUILDING DRAW TEST")
    print("========================")
    print(f"Paper main rectangle: ~{PAPER_WIDTH_MM:.0f} x {PAPER_HEIGHT_MM:.0f} mm")
    print(
        f"First test drawing: {drawer.settings.drawing_width_mm:.0f} x "
        f"{drawer.settings.drawing_height_mm:.0f} mm"
    )
    print(f"Live robot: {LIVE_ROBOT}")
    print(f"Preflight only: {PREFLIGHT_ONLY}")
    print()

    if LIVE_ROBOT:
        writer.connect_robot()
        writer.setup_robot()

    try:
        if PREFLIGHT_ONLY:
            drawer.preflight()
        else:
            drawer.draw()
    finally:
        if LIVE_ROBOT:
            writer.close_robot()
