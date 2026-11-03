"""
Simple MG400 image/path drawer.

This is intentionally a manual, simplified vector drawing test.
It reuses MG400Writer from mg400_writer.py for:
- connection
- motion commands
- pen height
- current WritingStart

Coordinate system:
- local x = left -> right across the drawing
- local y = top -> bottom down the drawing

For the current MG400 paper orientation:
- local x maps to robot +Y
- local y maps to robot +X

The current WritingStart is treated as the TOP-LEFT anchor of the drawing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from mg400_writer import MG400Writer


Point2D = Tuple[float, float]
Path2D = Sequence[Point2D]


@dataclass
class DrawingSettings:
    width_mm: float = 100.0
    height_mm: float = 70.0
    return_to_origin_after: bool = True


# Normalized paths:
# x = 0.0 .. 1.0 from left to right
# y = 0.0 .. 1.0 from top to bottom
#
# This is deliberately simplified. The goal is to test:
# - image-to-robot coordinate mapping
# - multiple separate paths
# - pen up/down behavior
# - scale
# - drawing speed
# - recognizability
SIMPLE_BUILDING_PATHS: List[List[Point2D]] = [
    # Main roof and outer building
    [(0.18, 0.25), (0.33, 0.08), (0.78, 0.12), (0.88, 0.23)],
    [(0.18, 0.25), (0.76, 0.29), (0.88, 0.23)],
    [(0.18, 0.25), (0.18, 0.76), (0.76, 0.80), (0.76, 0.29)],
    [(0.76, 0.29), (0.88, 0.23), (0.88, 0.69), (0.76, 0.80)],

    # Horizontal floor lines
    [(0.18, 0.43), (0.76, 0.47)],
    [(0.18, 0.60), (0.76, 0.64)],
    [(0.76, 0.47), (0.88, 0.42)],
    [(0.76, 0.64), (0.88, 0.57)],

    # Roof structure
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

    # Ground-floor arches
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

    # Small courtyard marks
    [(0.67, 0.83), (0.67, 0.86)],
    [(0.71, 0.82), (0.71, 0.85)],
    [(0.74, 0.81), (0.74, 0.84)],
]


class MG400ImageDrawer:
    def __init__(self, writer: MG400Writer, settings: DrawingSettings | None = None):
        self.writer = writer
        self.settings = settings or DrawingSettings()

    def normalized_to_robot(
        self,
        point: Point2D,
        origin_x: float,
        origin_y: float,
    ) -> Tuple[float, float]:
        """
        Convert normalized drawing coordinates to robot X/Y.

        Drawing:
            +x = right
            +y = down

        Robot:
            +Y = right on the paper
            +X = down on the paper
        """
        local_x, local_y = point

        robot_x = origin_x + local_y * self.settings.height_mm
        robot_y = origin_y + local_x * self.settings.width_mm

        return robot_x, robot_y

    def draw_path(
        self,
        path: Path2D,
        origin_x: float,
        origin_y: float,
        lifted_z: float,
        writing_z: float,
        r: float,
    ) -> None:
        if len(path) < 2:
            return

        start_x, start_y = self.normalized_to_robot(path[0], origin_x, origin_y)

        # Move above first point.
        self.writer.send_motion(
            f"MovJ({start_x},{start_y},{lifted_z},{r})"
        )

        # Lower pen.
        self.writer.send_motion(
            f"MovL({start_x},{start_y},{writing_z},{r})"
        )

        # Draw path.
        for point in path[1:]:
            x, y = self.normalized_to_robot(point, origin_x, origin_y)
            self.writer.send_motion(
                f"MovL({x},{y},{writing_z},{r})"
            )

        # Lift pen.
        end_x, end_y = self.normalized_to_robot(path[-1], origin_x, origin_y)
        self.writer.send_motion(
            f"MovL({end_x},{end_y},{lifted_z},{r})"
        )

    def draw_simple_building(self) -> None:
        """
        Draw the simplified building.

        Current WritingStart is used as the TOP-LEFT anchor.
        """
        origin_x, origin_y, lifted_z, r = self.writer.writing_start()
        writing_z = lifted_z + self.writer.settings.pen_drop

        self.writer.log(
            "Starting simplified building drawing "
            f"({self.settings.width_mm:.1f} x {self.settings.height_mm:.1f} mm)"
        )
        self.writer.log(
            f"Drawing origin: X={origin_x:.2f}, Y={origin_y:.2f}, "
            f"lifted Z={lifted_z:.2f}"
        )

        for index, path in enumerate(SIMPLE_BUILDING_PATHS, start=1):
            self.writer.log(
                f"--- Drawing image path {index}/{len(SIMPLE_BUILDING_PATHS)} ---"
            )
            self.draw_path(
                path,
                origin_x,
                origin_y,
                lifted_z,
                writing_z,
                r,
            )

        if self.settings.return_to_origin_after:
            self.writer.log("Returning to drawing origin.")
            self.writer.send_motion(
                f"MovJ({origin_x},{origin_y},{lifted_z},{r})"
            )

        self.writer.log("Finished simplified building drawing.")


if __name__ == "__main__":
    writer = MG400Writer()

    # Keep False for the first dry run.
    writer.settings.live_robot = False

    # Current/default drawing anchor settings.
    writer.settings.base_x = 260.0
    writer.settings.base_y = -85.10
    writer.settings.base_z = -147.6
    writer.settings.base_r = -21.40
    writer.settings.current_row = 0

    drawer = MG400ImageDrawer(
        writer,
        DrawingSettings(
            width_mm=100.0,
            height_mm=70.0,
            return_to_origin_after=True,
        ),
    )

    if writer.settings.live_robot:
        writer.connect_robot()
        writer.setup_robot()

    try:
        drawer.draw_simple_building()
    finally:
        if writer.settings.live_robot:
            writer.close_robot()
