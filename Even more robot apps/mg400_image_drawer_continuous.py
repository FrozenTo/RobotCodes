"""
MG400 simplified building drawer - IK-planned safe-area test.

This file is intentionally separate from:
    mg400_writer.py
    mg400_writer_app.py

It reuses MG400Writer for the Ethernet connection and motion commands.

What this version adds:
- measured paper geometry from the pen-tip tests
- ~55.5 mm pen offset from the flange
- R compensation so the desired PEN TIP position stays approximately fixed
- inverse-kinematics planning at the REAL writing Z before any movement
- automatic R selection from measured safe orientations
- J2 + custom J4 safety margins
- continuous same-R strokes: no unnecessary lift every ~10 mm
- Sync() barriers so the pen is fully lifted before travel/rotation
- a pen-up physical preflight mode after the analytical plan is safe

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


# ============================================================
# FIRST-TEST SWITCHES
# ============================================================

# False = print commands only, no physical robot movement.
ROBOT_IP = "192.168.1.6"

LIVE_ROBOT = False

# When True and LIVE_ROBOT=True:
# the robot visits the planned points with the pen lifted,
# checks J4, and DOES NOT DRAW.
#
# First real robot run should use:
# LIVE_ROBOT = True
# PREFLIGHT_ONLY = True
PREFLIGHT_ONLY = True


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

# The planner is free to choose whichever of these measured orientations
# gives the safest joint solution for each short pen stroke.
R_CANDIDATES = [
    R_TOP_LEFT,
    R_TOP_RIGHT,
    R_BOTTOM_LEFT,
    R_BOTTOM_RIGHT,
    R_BOTTOM_EXTENSION,
]


# ============================================================
# JOINT SAFETY
# ============================================================

# MG400 nominal J2 range is -25..85 degrees.
# We deliberately stop before the upper limit because that is the
# limit that interrupted the first real drawing test.
J2_HARD_MIN = -25.0
J2_HARD_MAX = 85.0
J2_MARGIN_DEG = 2.0

J2_SAFE_MIN = J2_HARD_MIN + J2_MARGIN_DEG   # -23
J2_SAFE_MAX = J2_HARD_MAX - J2_MARGIN_DEG   # 83

# Custom J4 limits for THIS side-mounted pen holder.
J4_HARD_MIN = -177.0
J4_HARD_MAX = 120.0
J4_MARGIN_DEG = 5.0

J4_SAFE_MIN = J4_HARD_MIN + J4_MARGIN_DEG   # -172
J4_SAFE_MAX = J4_HARD_MAX - J4_MARGIN_DEG   # +115

# Actual paper-contact flange Z measured during the test.
WRITING_Z = -197.30

# Long drawing lines are subdivided. Smaller pieces make both
# inverse-kinematics checking and actual drawing more conservative.
MAX_SEGMENT_MM = 10.0

# Print an extra high-level progress line during the long IK plan.
PLAN_PROGRESS_EVERY = 20


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
    # INVERSE KINEMATICS / SAFE R PLANNING
    # ============================================================

    @staticmethod
    def _parse_robot_values(response: str) -> Tuple[int, List[float]]:
        """
        Parse responses such as:
            0,{1.0,2.0,3.0,4.0},InverseSolution(...);
        """
        response = response.strip()

        error_match = re.match(r"\s*(-?\d+)\s*,", response)
        if not error_match:
            raise ValueError(f"Could not parse robot error ID: {response}")

        error_id = int(error_match.group(1))

        values_match = re.search(r"\{([^}]*)\}", response)
        if not values_match:
            return error_id, []

        values = [
            float(value.strip())
            for value in values_match.group(1).split(",")
            if value.strip()
        ]
        return error_id, values

    def inverse_solution(
        self,
        flange_x: float,
        flange_y: float,
        z: float,
        r_deg: float,
    ) -> Tuple[float, float, float, float] | None:
        """
        Ask the MG400 controller for the joint angles WITHOUT moving.

        MG400 4-axis TCP command:
            InverseSolution(X,Y,Z,R,User,Tool)

        Returns None when the controller reports that the pose cannot
        be solved.
        """
        if not self.writer.settings.live_robot:
            raise RuntimeError(
                "InverseSolution planning needs a live dashboard connection."
            )

        command = (
            f"InverseSolution("
            f"{flange_x:.3f},{flange_y:.3f},{z:.3f},{r_deg:.3f},0,0)"
        )

        response = self.writer.send_dashboard(command)
        error_id, values = self._parse_robot_values(response)

        if error_id != 0 or len(values) < 4:
            return None

        return values[0], values[1], values[2], values[3]

    @staticmethod
    def joint_pose_is_safe(
        joints: Tuple[float, float, float, float],
    ) -> bool:
        _, j2, _, j4 = joints

        return (
            J2_SAFE_MIN <= j2 <= J2_SAFE_MAX
            and J4_SAFE_MIN <= j4 <= J4_SAFE_MAX
        )

    @staticmethod
    def joint_safety_score(
        joints: Tuple[float, float, float, float],
    ) -> float:
        """
        Larger = farther from the nearest J2/J4 software limit.
        """
        _, j2, _, j4 = joints

        j2_margin = min(
            j2 - J2_SAFE_MIN,
            J2_SAFE_MAX - j2,
        )
        j4_margin = min(
            j4 - J4_SAFE_MIN,
            J4_SAFE_MAX - j4,
        )

        # J2 is the tight constraint in this drawing setup.
        # Use the smaller margin, so a very safe J4 cannot hide a J2
        # that is almost at its limit.
        return min(j2_margin, j4_margin)

    def evaluate_r_for_segment(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        r_deg: float,
        lifted_z: float,
    ):
        """
        Check both ends of a short segment at:
        - real writing Z
        - lifted travel Z

        No robot movement occurs here.
        """
        samples = []

        for pen_x, pen_y in (start, end):
            flange_x, flange_y = self.flange_for_pen_tip(
                pen_x,
                pen_y,
                r_deg,
            )

            for z in (WRITING_Z, lifted_z):
                joints = self.inverse_solution(
                    flange_x,
                    flange_y,
                    z,
                    r_deg,
                )

                if joints is None:
                    return None

                samples.append(joints)

                if not self.joint_pose_is_safe(joints):
                    return None

        score = min(self.joint_safety_score(j) for j in samples)

        return {
            "r": r_deg,
            "score": score,
            "joints": samples,
        }

    def choose_safe_r(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        lifted_z: float,
        previous_r: float | None,
    ):
        """
        Try all measured R orientations and choose a safe one.

        Primary goal:
            maximize distance from J2/J4 limits

        Tie-breaker:
            avoid unnecessary large R changes between neighbouring
            strokes.
        """
        valid = []

        for r_deg in R_CANDIDATES:
            result = self.evaluate_r_for_segment(
                start,
                end,
                r_deg,
                lifted_z,
            )

            if result is not None:
                valid.append(result)

        if not valid:
            return None

        def rank(item):
            continuity_penalty = 0.0
            if previous_r is not None:
                continuity_penalty = abs(item["r"] - previous_r) * 0.01

            return item["score"] - continuity_penalty

        return max(valid, key=rank)

    def plan_all_segments(self):
        """
        Analytical preflight.

        This runs BEFORE physical movement and asks the controller for
        inverse kinematics at the actual drawing Z.

        If even one stroke has no safe R, the program stops and tells
        us exactly which stroke failed.
        """
        lifted_z = WRITING_Z + self.settings.travel_lift_mm
        raw_segments = list(self.iter_pen_segments())

        planned = []
        previous_r = None
        worst_score = float("inf")
        worst_info = None

        self.writer.log(
            f"IK planning {len(raw_segments)} short segments at "
            f"writing Z={WRITING_Z:.2f}..."
        )

        total_segments = len(raw_segments)

        for index, (
            path_index,
            point_index,
            short_index,
            start,
            end,
        ) in enumerate(raw_segments, start=1):

            if (
                index == 1
                or index % PLAN_PROGRESS_EVERY == 0
                or index == total_segments
            ):
                percent = 100.0 * index / total_segments
                self.writer.log(
                    f"PLANNING: {index}/{total_segments} "
                    f"segments ({percent:.0f}%)"
                )

            choice = self.choose_safe_r(
                start,
                end,
                lifted_z,
                previous_r,
            )

            if choice is None:
                raise RuntimeError(
                    "\nNO SAFE R FOUND before robot movement.\n"
                    f"Segment {index}/{len(raw_segments)}\n"
                    f"Path={path_index}, edge={point_index}, "
                    f"subsegment={short_index}\n"
                    f"Pen start=({start[0]:.2f}, {start[1]:.2f})\n"
                    f"Pen end=({end[0]:.2f}, {end[1]:.2f})\n"
                    f"Checked J2 safe range "
                    f"{J2_SAFE_MIN:.1f}..{J2_SAFE_MAX:.1f} deg and "
                    f"J4 safe range "
                    f"{J4_SAFE_MIN:.1f}..{J4_SAFE_MAX:.1f} deg."
                )

            r_deg = choice["r"]
            score = choice["score"]

            planned.append({
                "index": index,
                "path_index": path_index,
                "point_index": point_index,
                "short_index": short_index,
                "start": start,
                "end": end,
                "r": r_deg,
                "score": score,
            })

            if score < worst_score:
                worst_score = score
                worst_info = planned[-1]

            previous_r = r_deg

        self.writer.log(
            f"IK PLAN OK: all {len(planned)} segments have a safe "
            f"J2/J4 solution."
        )

        if worst_info is not None:
            self.writer.log(
                f"Smallest planned joint margin: {worst_score:.2f} deg "
                f"at segment {worst_info['index']} "
                f"(R={worst_info['r']:.2f} deg)."
            )

        return planned

    def get_joint_angles(self) -> Tuple[float, float, float, float]:
        response = self.writer.send_dashboard("GetAngle()")
        error_id, values = self._parse_robot_values(response)

        if error_id != 0 or len(values) < 4:
            raise ValueError(f"Could not read GetAngle(): {response}")

        return values[0], values[1], values[2], values[3]

    def check_actual_joints(self, context: str = ""):
        """
        Runtime sanity check AFTER Sync(), so GetAngle refers to the
        pose that was actually reached rather than an older queued pose.
        """
        if not self.writer.settings.live_robot:
            return

        j1, j2, j3, j4 = self.get_joint_angles()

        self.writer.log(
            f"Actual joints {context}: "
            f"J1={j1:.2f}, J2={j2:.2f}, J3={j3:.2f}, J4={j4:.2f}"
        )

        if not (J2_SAFE_MIN <= j2 <= J2_SAFE_MAX):
            raise RuntimeError(
                f"J2 runtime safety stop: {j2:.2f} deg"
            )

        if not (J4_SAFE_MIN <= j4 <= J4_SAFE_MAX):
            raise RuntimeError(
                f"J4 runtime safety stop: {j4:.2f} deg"
            )

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
    # CONTINUOUS STROKES
    # ============================================================

    @staticmethod
    def _same_point(
        a: Tuple[float, float],
        b: Tuple[float, float],
        tolerance_mm: float = 0.01,
    ) -> bool:
        return (
            abs(a[0] - b[0]) <= tolerance_mm
            and abs(a[1] - b[1]) <= tolerance_mm
        )

    def combine_into_strokes(self, planned):
        """
        Combine consecutive planned 10 mm safety segments into one
        continuous pen-down stroke when:

        - they belong to the same original path,
        - the next segment starts where the previous one ended,
        - and the chosen R does not change.

        The short segments are still kept during IK planning, so we do
        NOT lose the safety checks. We only stop unnecessarily lifting
        the pen between pieces that can be drawn continuously.
        """
        if not planned:
            return []

        strokes = []
        current = None

        for segment in planned:
            if current is None:
                current = {
                    "path_index": segment["path_index"],
                    "r": segment["r"],
                    "points": [segment["start"], segment["end"]],
                    "score": segment["score"],
                    "first_segment": segment["index"],
                    "last_segment": segment["index"],
                }
                continue

            continuous = (
                segment["path_index"] == current["path_index"]
                and abs(segment["r"] - current["r"]) < 1e-6
                and self._same_point(
                    current["points"][-1],
                    segment["start"],
                )
            )

            if continuous:
                current["points"].append(segment["end"])
                current["score"] = min(
                    current["score"],
                    segment["score"],
                )
                current["last_segment"] = segment["index"]
            else:
                strokes.append(current)
                current = {
                    "path_index": segment["path_index"],
                    "r": segment["r"],
                    "points": [segment["start"], segment["end"]],
                    "score": segment["score"],
                    "first_segment": segment["index"],
                    "last_segment": segment["index"],
                }

        if current is not None:
            strokes.append(current)

        return strokes

    # ============================================================
    # MOTION
    # ============================================================

    def sync_motion(self) -> None:
        """
        Wait until queued motion has actually completed.

        This is especially important after lifting the spring-loaded pen:
        the next XY/R travel must not begin while the pen is still
        touching the paper.
        """
        if self.writer.settings.live_robot:
            self.writer.send_motion("Sync()")

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
            f"MovJ({flange_x:.3f},{flange_y:.3f},"
            f"{lifted_z:.3f},{r_deg:.3f})"
        )

    def preflight(self, planned=None) -> None:
        """
        Physical PEN-UP preflight.

        The full IK plan is still done using short safety segments.
        For physical preflight, neighbouring pieces with the same R
        are followed continuously instead of repeatedly revisiting
        every 10 mm segment start/end.
        """
        lifted_z = WRITING_Z + self.settings.travel_lift_mm

        if planned is None:
            planned = self.plan_all_segments()

        strokes = self.combine_into_strokes(planned)

        self.writer.log(
            f"Starting PHYSICAL PEN-UP PRE-FLIGHT: "
            f"{len(planned)} checked segments -> "
            f"{len(strokes)} continuous strokes."
        )
        self.writer.log(
            f"Pen remains lifted at Z={lifted_z:.2f}."
        )

        for i, stroke in enumerate(strokes, start=1):
            points = stroke["points"]
            r_deg = stroke["r"]

            self.writer.log(
                f"[Preflight stroke {i}/{len(strokes)}] "
                f"path={stroke['path_index']}, "
                f"R={r_deg:.2f} deg, "
                f"{len(points) - 1} checked pieces"
            )

            # Travel to start safely while lifted.
            start_pen = points[0]
            self.move_flange_above_pen_tip(
                start_pen[0],
                start_pen[1],
                r_deg,
                lifted_z,
            )
            self.sync_motion()
            self.check_actual_joints("preflight stroke start")

            # Follow the same planned shape while remaining lifted.
            # R stays constant for the entire stroke.
            for pen_x, pen_y in points[1:]:
                flange_x, flange_y = self.flange_for_pen_tip(
                    pen_x,
                    pen_y,
                    r_deg,
                )
                self.writer.send_motion(
                    f"MovL({flange_x:.3f},{flange_y:.3f},"
                    f"{lifted_z:.3f},{r_deg:.3f})"
                )

            self.sync_motion()
            self.check_actual_joints("preflight stroke end")

        self.writer.log("PHYSICAL PRE-FLIGHT completed successfully.")

    def draw(self, planned=None) -> None:
        """
        Draw using the already-validated IK plan.

        The planner still checks the picture in short ~10 mm pieces.

        During execution those pieces are MERGED when they are:
        - part of the same original path,
        - directly connected,
        - and use the same R.

        Therefore a long roof/wall/window line no longer becomes:
            draw 10 mm -> lift -> move -> lower -> draw 10 mm ...

        It becomes:
            move above start
            -> lower once
            -> keep drawing through all checked points
            -> lift once

        If R must change, or a path ends, the pen is lifted first.
        """
        lifted_z = WRITING_Z + self.settings.travel_lift_mm

        if planned is None:
            planned = self.plan_all_segments()

        strokes = self.combine_into_strokes(planned)

        self.writer.log(
            f"Starting simplified building drawing: "
            f"{len(planned)} IK-checked segments -> "
            f"{len(strokes)} continuous pen strokes."
        )
        self.writer.log(
            f"Test area: {self.settings.drawing_width_mm:.1f} x "
            f"{self.settings.drawing_height_mm:.1f} mm"
        )

        for i, stroke in enumerate(strokes, start=1):
            points = stroke["points"]
            r_deg = stroke["r"]

            start_pen_x, start_pen_y = points[0]
            start_fx, start_fy = self.flange_for_pen_tip(
                start_pen_x,
                start_pen_y,
                r_deg,
            )

            self.writer.log(
                f"[Stroke {i}/{len(strokes)}] "
                f"path={stroke['path_index']}, "
                f"R={r_deg:.2f} deg, "
                f"segments={stroke['first_segment']}.."
                f"{stroke['last_segment']}, "
                f"planned margin={stroke['score']:.2f} deg"
            )

            # 1) Travel above the first point.
            self.writer.send_motion(
                f"MovJ({start_fx:.3f},{start_fy:.3f},"
                f"{lifted_z:.3f},{r_deg:.3f})"
            )
            self.sync_motion()
            self.check_actual_joints("before pen down")

            # 2) Lower once.
            self.writer.send_motion(
                f"MovL({start_fx:.3f},{start_fy:.3f},"
                f"{WRITING_Z:.3f},{r_deg:.3f})"
            )
            self.sync_motion()
            self.check_actual_joints("pen down")

            # 3) Keep the pen DOWN while following all contiguous
            #    IK-checked points with the same R.
            #
            # We deliberately do not Sync() after every 10 mm piece;
            # the controller can execute the connected MovL commands
            # as one continuous stroke. Every piece was validated in
            # the analytical IK plan beforehand.
            last_fx = start_fx
            last_fy = start_fy

            for pen_x, pen_y in points[1:]:
                last_fx, last_fy = self.flange_for_pen_tip(
                    pen_x,
                    pen_y,
                    r_deg,
                )

                self.writer.send_motion(
                    f"MovL({last_fx:.3f},{last_fy:.3f},"
                    f"{WRITING_Z:.3f},{r_deg:.3f})"
                )

            self.sync_motion()
            self.check_actual_joints("stroke end")

            # 4) Lift completely before changing XY path or R.
            self.writer.send_motion(
                f"MovL({last_fx:.3f},{last_fy:.3f},"
                f"{lifted_z:.3f},{r_deg:.3f})"
            )
            self.sync_motion()
            self.check_actual_joints("pen lifted")

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
        if LIVE_ROBOT:
            # Analytical IK plan happens first and does not move the robot.
            # If any segment would violate our J2/J4 margins, execution
            # stops here and prints the exact failing segment.
            planned = drawer.plan_all_segments()

            if PREFLIGHT_ONLY:
                drawer.preflight(planned)
            else:
                drawer.draw(planned)
        else:
            print(
                "LIVE_ROBOT=False: inverse-kinematics planning needs "
                "a live dashboard connection, so no motion/IK test was run."
            )
    finally:
        if LIVE_ROBOT:
            writer.close_robot()
