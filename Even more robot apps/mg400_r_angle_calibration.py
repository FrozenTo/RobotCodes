
"""
MG400 R-angle calibration line test.

Draws two nominally straight lines:
1) R increases from bottom-left toward bottom.
2) R decreases over the same values in reverse.

If the pen TCP model is correct, all segments should meet on the same
straight line despite R changes. The reverse line helps distinguish
geometry/calibration error from mechanical flex/backlash.

Requires mg400_writer.py in the same folder.
"""

from __future__ import annotations

import math
import re
from typing import List, Tuple

from mg400_writer import MG400Writer


ROBOT_IP = "192.168.1.6"
LIVE_ROBOT = True
SPEED_FACTOR = 35

WRITING_Z = -197.30
TRAVEL_LIFT_MM = 10.0

# Keep current model unchanged for the first calibration run.
PEN_RADIUS_MM = 55.5
PEN_ANGLE_OFFSET_DEG = 26.0

R_VALUES = [
    -72.24,
    -64.74,
    -57.24,
    -49.74,
    -42.24,
    -34.74,
    -27.24,
]

SEGMENT_LENGTH_MM = 18.0

# +Y = right, +X = down on the paper.
FORWARD_LINE_X = 315.0
REVERSE_LINE_X = 330.0
START_Y = -63.0

J2_SAFE_MIN = -23.0
J2_SAFE_MAX = 83.0

J4_SAFE_MIN = -172.0
J4_SAFE_MAX = 115.0


def pen_offset_for_r(r_deg: float) -> Tuple[float, float]:
    angle = math.radians(r_deg + PEN_ANGLE_OFFSET_DEG)
    return (
        PEN_RADIUS_MM * math.cos(angle),
        PEN_RADIUS_MM * math.sin(angle),
    )


def flange_for_pen_tip(
    pen_x: float,
    pen_y: float,
    r_deg: float,
) -> Tuple[float, float]:
    offset_x, offset_y = pen_offset_for_r(r_deg)
    return (
        pen_x - offset_x,
        pen_y - offset_y,
    )


def parse_robot_values(response: str) -> Tuple[int, List[float]]:
    response = response.strip()

    error_match = re.match(r"\s*(-?\d+)\s*,", response)
    if not error_match:
        raise ValueError(f"Could not parse robot response: {response}")

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
    writer: MG400Writer,
    flange_x: float,
    flange_y: float,
    z: float,
    r_deg: float,
):
    command = (
        f"InverseSolution("
        f"{flange_x:.3f},{flange_y:.3f},{z:.3f},{r_deg:.3f},0,0)"
    )

    response = writer.send_dashboard(command)
    error_id, values = parse_robot_values(response)

    if error_id != 0 or len(values) < 4:
        return None

    return values[0], values[1], values[2], values[3]


def pose_is_safe(joints) -> bool:
    _, j2, _, j4 = joints

    return (
        J2_SAFE_MIN <= j2 <= J2_SAFE_MAX
        and J4_SAFE_MIN <= j4 <= J4_SAFE_MAX
    )


def sync(writer: MG400Writer) -> None:
    writer.send_motion("Sync()")


def check_line(
    writer: MG400Writer,
    line_x: float,
    r_values: List[float],
    label: str,
) -> None:
    print()
    print(f"Checking {label}...")

    for index, r_deg in enumerate(r_values):
        y1 = START_Y + index * SEGMENT_LENGTH_MM
        y2 = y1 + SEGMENT_LENGTH_MM

        for name, pen_y in (("start", y1), ("end", y2)):
            flange_x, flange_y = flange_for_pen_tip(
                line_x,
                pen_y,
                r_deg,
            )

            joints = inverse_solution(
                writer,
                flange_x,
                flange_y,
                WRITING_Z,
                r_deg,
            )

            if joints is None:
                raise RuntimeError(
                    f"{label}, segment {index + 1}, {name}: "
                    f"no IK solution for R={r_deg:.2f}"
                )

            j1, j2, j3, j4 = joints

            print(
                f"{label} {index + 1}/{len(r_values)} "
                f"R={r_deg:7.2f}  "
                f"{name:5s}  "
                f"J2={j2:6.2f}  J4={j4:7.2f}"
            )

            if not pose_is_safe(joints):
                raise RuntimeError(
                    f"Unsafe planned pose: {label}, segment {index + 1}, "
                    f"{name}, R={r_deg:.2f}, J2={j2:.2f}, J4={j4:.2f}"
                )


def draw_angle_line(
    writer: MG400Writer,
    line_x: float,
    r_values: List[float],
    label: str,
) -> None:
    lifted_z = WRITING_Z + TRAVEL_LIFT_MM

    print()
    print(f"Drawing {label}...")

    for index, r_deg in enumerate(r_values):
        pen_y_start = START_Y + index * SEGMENT_LENGTH_MM
        pen_y_end = pen_y_start + SEGMENT_LENGTH_MM

        start_fx, start_fy = flange_for_pen_tip(
            line_x,
            pen_y_start,
            r_deg,
        )
        end_fx, end_fy = flange_for_pen_tip(
            line_x,
            pen_y_end,
            r_deg,
        )

        print(
            f"{label} segment {index + 1}: "
            f"R={r_deg:.2f}, "
            f"pen Y {pen_y_start:.1f} -> {pen_y_end:.1f}"
        )

        writer.send_motion(
            f"MovJ({start_fx:.3f},{start_fy:.3f},"
            f"{lifted_z:.3f},{r_deg:.3f})"
        )
        sync(writer)

        writer.send_motion(
            f"MovL({start_fx:.3f},{start_fy:.3f},"
            f"{WRITING_Z:.3f},{r_deg:.3f})"
        )
        sync(writer)

        writer.send_motion(
            f"MovL({end_fx:.3f},{end_fy:.3f},"
            f"{WRITING_Z:.3f},{r_deg:.3f})"
        )
        sync(writer)

        writer.send_motion(
            f"MovL({end_fx:.3f},{end_fy:.3f},"
            f"{lifted_z:.3f},{r_deg:.3f})"
        )
        sync(writer)


if __name__ == "__main__":
    writer = MG400Writer()

    writer.settings.ip = ROBOT_IP
    writer.settings.live_robot = LIVE_ROBOT
    writer.settings.speed_factor = SPEED_FACTOR

    print()
    print("MG400 R-ANGLE CALIBRATION TEST")
    print("==============================")
    print(f"Robot IP: {ROBOT_IP}")
    print(f"Writing Z: {WRITING_Z}")
    print(f"Pen radius: {PEN_RADIUS_MM} mm")
    print(f"Pen angle offset: {PEN_ANGLE_OFFSET_DEG} deg")
    print()
    print("Top line:    R increases bottom-left -> bottom")
    print("Bottom line: R decreases bottom -> bottom-left")
    print()

    if not LIVE_ROBOT:
        print("LIVE_ROBOT=False, so no robot movement will occur.")
        raise SystemExit

    writer.connect_robot()
    writer.setup_robot()

    try:
        check_line(
            writer,
            FORWARD_LINE_X,
            R_VALUES,
            "FORWARD",
        )

        check_line(
            writer,
            REVERSE_LINE_X,
            list(reversed(R_VALUES)),
            "REVERSE",
        )

        print()
        print("All planned poses passed J2/J4 safety checks.")
        print("Starting physical test...")

        draw_angle_line(
            writer,
            FORWARD_LINE_X,
            R_VALUES,
            "FORWARD",
        )

        draw_angle_line(
            writer,
            REVERSE_LINE_X,
            list(reversed(R_VALUES)),
            "REVERSE",
        )

        print()
        print("Calibration test finished.")
        print()
        print("Interpretation:")
        print("- Same offset at same R values in both lines:")
        print("  likely pen radius/angle calibration.")
        print("- Different forward vs reverse behavior:")
        print("  likely mechanical flex/backlash in the holder.")

    finally:
        writer.close_robot()
