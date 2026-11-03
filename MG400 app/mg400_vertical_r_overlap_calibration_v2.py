
"""
MG400 vertical R-angle overlap calibration.

Why this version:
- The suspected error shows up mainly on UP/DOWN drawing.
- The spring holder makes the beginning of each stroke curve slightly.
- Instead of joining short segments, every R value redraws the SAME long
  vertical line. Ignore the first few mm; compare the middle of the line.

Two columns are drawn:
1) LEFT TEST: every R draws TOP -> BOTTOM.
2) RIGHT TEST: every R draws BOTTOM -> TOP.

If the pen model is correct, all passes should overlap into one thin line.
If some R values are offset, you will see parallel/doubled lines in the
middle section, where the spring has already settled.

Requires mg400_writer.py in the same folder.
"""

from __future__ import annotations

import math
import re
from typing import List, Tuple

from mg400_writer import MG400Writer


# ============================================================
# ROBOT / TEST SETTINGS
# ============================================================

ROBOT_IP = "192.168.1.6"
LIVE_ROBOT = True
SPEED_FACTOR = 30

WRITING_Z = -197.30
TRAVEL_LIFT_MM = 10.0

# Current pen model. Keep unchanged for the first test.
PEN_RADIUS_MM = 55.5
PEN_ANGLE_OFFSET_DEG = 26.0

# Focus on the range where you observed the mismatch.
R_VALUES = [
    -72.24,
    -64.74,
    -57.24,
    -49.74,
    -42.24,
    -34.74,
    -27.24,
]

# Vertical line on paper: +X = down.
#
# The first version used X=285..350. At R=-49.74 that required
# flange X≈234.2 and MG400 returned InverseSolution error -1.
# Moving the whole test lower keeps the same calibration idea while
# giving the flange more reachable room.
LINE_TOP_X = 305.0
LINE_BOTTOM_X = 355.0

# Two separate columns so we can compare travel direction.
DOWN_TEST_Y = -35.0
UP_TEST_Y = 35.0

# The spring may curve the first few mm after touching the paper.
# Visually judge the middle of the 65 mm line, not just the ends.

J2_SAFE_MIN = -23.0
J2_SAFE_MAX = 83.0
J4_SAFE_MIN = -172.0
J4_SAFE_MAX = 115.0


# ============================================================
# HELPERS
# ============================================================

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


# ============================================================
# SAFETY CHECK
# ============================================================

def check_pass(
    writer: MG400Writer,
    pen_y: float,
    start_x: float,
    end_x: float,
    r_deg: float,
    label: str,
) -> None:
    for name, pen_x in (("start", start_x), ("end", end_x)):
        flange_x, flange_y = flange_for_pen_tip(
            pen_x,
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
                f"{label}, {name}: no IK solution for R={r_deg:.2f}"
            )

        j1, j2, j3, j4 = joints

        print(
            f"{label:10s} R={r_deg:7.2f}  {name:5s}  "
            f"J2={j2:6.2f}  J4={j4:7.2f}"
        )

        if not pose_is_safe(joints):
            raise RuntimeError(
                f"Unsafe pose: {label}, {name}, R={r_deg:.2f}, "
                f"J2={j2:.2f}, J4={j4:.2f}"
            )


# ============================================================
# DRAW ONE FULL OVERLAP PASS
# ============================================================

def draw_vertical_pass(
    writer: MG400Writer,
    pen_y: float,
    start_x: float,
    end_x: float,
    r_deg: float,
    label: str,
) -> None:
    lifted_z = WRITING_Z + TRAVEL_LIFT_MM

    start_fx, start_fy = flange_for_pen_tip(
        start_x,
        pen_y,
        r_deg,
    )
    end_fx, end_fy = flange_for_pen_tip(
        end_x,
        pen_y,
        r_deg,
    )

    print(
        f"{label}: R={r_deg:.2f}, "
        f"paper X {start_x:.1f} -> {end_x:.1f}, Y={pen_y:.1f}"
    )

    # Move above start.
    writer.send_motion(
        f"MovJ({start_fx:.3f},{start_fy:.3f},"
        f"{lifted_z:.3f},{r_deg:.3f})"
    )
    sync(writer)

    # Lower pen.
    writer.send_motion(
        f"MovL({start_fx:.3f},{start_fy:.3f},"
        f"{WRITING_Z:.3f},{r_deg:.3f})"
    )
    sync(writer)

    # Draw the SAME nominal vertical line for this R.
    writer.send_motion(
        f"MovL({end_fx:.3f},{end_fy:.3f},"
        f"{WRITING_Z:.3f},{r_deg:.3f})"
    )
    sync(writer)

    # Lift before changing R.
    writer.send_motion(
        f"MovL({end_fx:.3f},{end_fy:.3f},"
        f"{lifted_z:.3f},{r_deg:.3f})"
    )
    sync(writer)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    writer = MG400Writer()

    writer.settings.ip = ROBOT_IP
    writer.settings.live_robot = LIVE_ROBOT
    writer.settings.speed_factor = SPEED_FACTOR

    print()
    print("MG400 VERTICAL R-OVERLAP CALIBRATION")
    print("====================================")
    print(f"Robot IP: {ROBOT_IP}")
    print(f"Writing Z: {WRITING_Z}")
    print(f"Pen radius: {PEN_RADIUS_MM} mm")
    print(f"Pen angle offset: {PEN_ANGLE_OFFSET_DEG} deg")
    print()
    print("LEFT column: every R redraws the same line TOP -> BOTTOM")
    print("RIGHT column: every R redraws the same line BOTTOM -> TOP")
    print("Ignore the first few mm of each pass; inspect the middle.")
    print()

    if not LIVE_ROBOT:
        print("LIVE_ROBOT=False, so no robot movement will occur.")
        raise SystemExit

    writer.connect_robot()
    writer.setup_robot()

    try:
        print("Checking all poses before movement...")

        for r_deg in R_VALUES:
            check_pass(
                writer,
                DOWN_TEST_Y,
                LINE_TOP_X,
                LINE_BOTTOM_X,
                r_deg,
                "DOWN TEST",
            )

            check_pass(
                writer,
                UP_TEST_Y,
                LINE_BOTTOM_X,
                LINE_TOP_X,
                r_deg,
                "UP TEST",
            )

        print()
        print("All poses passed J2/J4 checks.")
        print("Starting overlap test...")
        print()

        # LEFT: same vertical line repeatedly, top -> bottom.
        for r_deg in R_VALUES:
            draw_vertical_pass(
                writer,
                DOWN_TEST_Y,
                LINE_TOP_X,
                LINE_BOTTOM_X,
                r_deg,
                f"DOWN R={r_deg:.2f}",
            )

        # RIGHT: same vertical line repeatedly, bottom -> top.
        for r_deg in R_VALUES:
            draw_vertical_pass(
                writer,
                UP_TEST_Y,
                LINE_BOTTOM_X,
                LINE_TOP_X,
                r_deg,
                f"UP R={r_deg:.2f}",
            )

        print()
        print("Finished.")
        print()
        print("How to read it:")
        print("- One thin line in the middle = R compensation is good.")
        print("- Several parallel lines = TCP radius/angle error.")
        print("- DOWN and UP differ = holder flex/backlash/hysteresis.")
        print("- Only the first few mm curve = spring settling, ignore that part.")

    finally:
        writer.close_robot()
