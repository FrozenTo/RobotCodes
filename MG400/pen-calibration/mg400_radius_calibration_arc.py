
"""
MG400 pen-radius calibration by rotating R in place.

Idea:
If the flange center stays fixed and only R changes, the pen tip draws an arc.
That arc radius is the effective pen offset radius at the current pen pressure.

This is useful because your spring-board holder changes the effective radius
when the pen is pressed into the paper.

What to do:
1) Draw the arc.
2) Measure the diameter between the arc endpoints on paper.
3) Set:
       PEN_RADIUS_MM = measured_diameter_mm / 2

Important:
- The measured diameter gives you the EFFECTIVE average radius at this
  pen pressure and holder flex.
- If the holder flex changes with direction, one single radius still cannot
  perfectly fix every orientation. But this test gives a much better value.
"""

from __future__ import annotations

import math
from typing import List

from mg400_writer import MG400Writer


# ============================================================
# ROBOT SETTINGS
# ============================================================

ROBOT_IP = "192.168.1.6"
LIVE_ROBOT = True
SPEED_FACTOR = 20

WRITING_Z = -197.30
TRAVEL_LIFT_MM = 10.0


# ============================================================
# CALIBRATION SETTINGS
# ============================================================

# Flange center position.
# This should be somewhere safe, roughly near the middle of the usable area.
CENTER_X = 320.0
CENTER_Y = 0.0

# Angle sweep for the arc.
# Adjust if needed, but this should be close to a half-circle in your setup.
ARC_START_R = -115.0
ARC_END_R = 62.0
ARC_STEP_DEG = 3.0

# Your current compensation values.
# These are NOT used to draw the arc itself (only R motion is used),
# but they are used if you enable the optional diameter line.
PEN_RADIUS_MM = 55.5
PEN_ANGLE_OFFSET_DEG = 26.0

# Optional:
# If True, draw an approximate straight line between the two arc endpoints.
# This line uses the current PEN_RADIUS_MM and PEN_ANGLE_OFFSET_DEG, so if
# those are wrong, it may not hit the arc endpoints perfectly.
DRAW_DIAMETER_LINE = False

# R used while drawing the optional diameter line.
# A bottom-ish angle is often convenient.
DIAMETER_LINE_R = -27.24


# ============================================================
# HELPERS
# ============================================================

def frange(start: float, end: float, step: float) -> List[float]:
    values = []
    if step == 0:
        raise ValueError("step cannot be zero")

    if start <= end and step > 0:
        x = start
        while x <= end + 1e-9:
            values.append(round(x, 6))
            x += step
    elif start >= end and step < 0:
        x = start
        while x >= end - 1e-9:
            values.append(round(x, 6))
            x += step
    else:
        raise ValueError("step sign does not move from start toward end")

    return values


def pen_offset_for_r(r_deg: float):
    angle = math.radians(r_deg + PEN_ANGLE_OFFSET_DEG)
    return (
        PEN_RADIUS_MM * math.cos(angle),
        PEN_RADIUS_MM * math.sin(angle),
    )


def pen_tip_from_flange(flange_x: float, flange_y: float, r_deg: float):
    ox, oy = pen_offset_for_r(r_deg)
    return (flange_x + ox, flange_y + oy)


def flange_for_pen_tip(pen_x: float, pen_y: float, r_deg: float):
    ox, oy = pen_offset_for_r(r_deg)
    return (pen_x - ox, pen_y - oy)


def sync(writer: MG400Writer):
    writer.send_motion("Sync()")


# ============================================================
# DRAWING
# ============================================================

def draw_arc(writer: MG400Writer):
    lifted_z = WRITING_Z + TRAVEL_LIFT_MM

    step = ARC_STEP_DEG if ARC_END_R >= ARC_START_R else -abs(ARC_STEP_DEG)
    r_values = frange(ARC_START_R, ARC_END_R, step)

    print()
    print("Drawing R-sweep arc...")
    print(f"Center flange pose: X={CENTER_X}, Y={CENTER_Y}")
    print(f"R sweep: {ARC_START_R} -> {ARC_END_R} in {abs(ARC_STEP_DEG)}° steps")
    print(f"Number of points: {len(r_values)}")
    print()

    start_r = r_values[0]

    writer.send_motion(f"MovJ({CENTER_X:.3f},{CENTER_Y:.3f},{lifted_z:.3f},{start_r:.3f})")
    sync(writer)

    writer.send_motion(f"MovL({CENTER_X:.3f},{CENTER_Y:.3f},{WRITING_Z:.3f},{start_r:.3f})")
    sync(writer)

    for r_deg in r_values[1:]:
        writer.send_motion(f"MovL({CENTER_X:.3f},{CENTER_Y:.3f},{WRITING_Z:.3f},{r_deg:.3f})")

    sync(writer)

    end_r = r_values[-1]
    writer.send_motion(f"MovL({CENTER_X:.3f},{CENTER_Y:.3f},{lifted_z:.3f},{end_r:.3f})")
    sync(writer)

    return r_values


def draw_nominal_diameter_line(writer: MG400Writer):
    lifted_z = WRITING_Z + TRAVEL_LIFT_MM

    # Nominal arc endpoints according to current radius model.
    start_tip = pen_tip_from_flange(CENTER_X, CENTER_Y, ARC_START_R)
    end_tip = pen_tip_from_flange(CENTER_X, CENTER_Y, ARC_END_R)

    # Draw a straight line between those pen-tip points using one fixed R.
    start_fx, start_fy = flange_for_pen_tip(start_tip[0], start_tip[1], DIAMETER_LINE_R)
    end_fx, end_fy = flange_for_pen_tip(end_tip[0], end_tip[1], DIAMETER_LINE_R)

    print()
    print("Drawing optional nominal diameter line...")
    print("Note: this uses the current PEN_RADIUS_MM / PEN_ANGLE_OFFSET_DEG,")
    print("so if those are wrong, the line may not hit the arc endpoints exactly.")
    print()

    writer.send_motion(
        f"MovJ({start_fx:.3f},{start_fy:.3f},{lifted_z:.3f},{DIAMETER_LINE_R:.3f})"
    )
    sync(writer)

    writer.send_motion(
        f"MovL({start_fx:.3f},{start_fy:.3f},{WRITING_Z:.3f},{DIAMETER_LINE_R:.3f})"
    )
    sync(writer)

    writer.send_motion(
        f"MovL({end_fx:.3f},{end_fy:.3f},{WRITING_Z:.3f},{DIAMETER_LINE_R:.3f})"
    )
    sync(writer)

    writer.send_motion(
        f"MovL({end_fx:.3f},{end_fy:.3f},{lifted_z:.3f},{DIAMETER_LINE_R:.3f})"
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
    print("MG400 PEN RADIUS CALIBRATION ARC")
    print("================================")
    print(f"Robot IP: {ROBOT_IP}")
    print(f"Live robot: {LIVE_ROBOT}")
    print(f"Flange center: X={CENTER_X}, Y={CENTER_Y}")
    print(f"Writing Z: {WRITING_Z}")
    print(f"Arc R range: {ARC_START_R} -> {ARC_END_R}")
    print()
    print("After drawing:")
    print("1) Measure endpoint-to-endpoint diameter on the paper.")
    print("2) Set PEN_RADIUS_MM = measured_diameter_mm / 2")
    print()
    print("Example:")
    print("  diameter = 111 mm  ->  PEN_RADIUS_MM = 55.5")
    print()

    if not LIVE_ROBOT:
        print("LIVE_ROBOT=False, so no robot movement will occur.")
        raise SystemExit

    writer.connect_robot()
    writer.setup_robot()

    try:
        draw_arc(writer)

        if DRAW_DIAMETER_LINE:
            draw_nominal_diameter_line(writer)

        print()
        print("Finished.")
        print("If your measured diameter is ~111 mm, that confirms a radius of ~55.5 mm.")

    finally:
        writer.close_robot()
