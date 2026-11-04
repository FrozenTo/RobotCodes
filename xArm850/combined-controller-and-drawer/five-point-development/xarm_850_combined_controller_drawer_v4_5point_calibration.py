"""
xArm wall SVG drawer.

Uses the same SVG parsing approach that worked for the MG400 drawing, but the
robot-side geometry is much simpler:

    SVG x -> paper left/right -> xArm Y
    SVG y -> paper top/bottom -> xArm Z
    paper surface depth       -> xArm X

Five taught wall/paper points define the reachable drawing surface. The
upper-right corner is clipped because that area is outside the robot's useful
reach. The five points are triangulated so every taught calibration point is
reproduced exactly and drawing points in the unreachable corner are rejected.

Requires:
    pip install xarm-python-sdk

Put this file in the same folder as your SVG, or change SVG_FILE below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import threading
import traceback
import json
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pygame

from xarm.wrapper import XArmAPI


Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]
Polyline = List[Point2D]
Path3D = List[Point3D]


# ============================================================
# USER SETTINGS
# ============================================================

ROBOT_IP = "192.168.1.208"
SVG_FILE = "drawing.svg"

LIVE_ROBOT = True

# True = follow the whole drawing at the safe X plane without touching paper.
# First real run: LIVE_ROBOT=True, PREFLIGHT_ONLY=True
PREFLIGHT_ONLY = False

# Move first to the known working ready joint pose from the wall-writer app.
MOVE_TO_READY_FIRST = True


# ============================================================
# WORKING xARM POSES / ORIENTATION
# ============================================================

READY_JOINTS = [-196.5, 7.5, -77.1, 1.2, -80.9, -15.8]

# UFactory Studio "Initial Position": all six joints at 0 degrees.
# Kept separate from READY_JOINTS because the wall-writing ready pose is a
# calibrated working pose, while Initial Position is the robot's neutral pose.
INITIAL_JOINTS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
INITIAL_JOINT_SPEED = 20.0       # deg/s

# Known ready Cartesian pose, kept here for reference/logging.
READY_X = -391.8
READY_Y = 111.0
READY_Z = 597.7

# Marker orientation from the working wall-writing app.
ROLL = -179.7
PITCH = -3.6
YAW = 179.1

# -480 is the safe writing/travel plane. Paper contact is farther toward -X.
SAFE_X = -480.0

# Optional extra push into the wall, in mm.
# The recorded corner X values were already paper-touch points, so 0.0 is the
# correct starting value. More negative = push farther into the paper.
CONTACT_X_OFFSET_MM = -7.0  #for brand new marker -6.0, slightly used -7.5


# ============================================================
# MEASURED WALL / PAPER CALIBRATION
# ============================================================
#
# New 5-point reachable surface calibration (29.10.2026).
#
# Logical drawing coordinates:
#   right_mm = 0 at the left side, increasing toward +Y
#   down_mm  = 0 at the top, increasing toward -Z
#
# Reachable shape:
#
#       TL -------------------- TR_TOP
#       |                           \
#       |                            \
#       |                             TR_BOTTOM
#       |                              |
#       |                              |
#       BL --------------------------- BR
#
# The missing upper-right triangle is intentionally NOT drawable.
# Any text/SVG point that falls there is rejected during preflight.
#
# CONTACT_X_OFFSET_MM is still applied after interpolation, exactly as in
# the previous working wall-writer configuration.
# ============================================================

PAPER_TL: Point3D = (
    -520.227600,
    -79.035851,
    757.862732,
)

PAPER_BL: Point3D = (
    -520.319336,
    -80.749542,
    490.642792,
)

PAPER_BR: Point3D = (
    -514.019104,
    302.926208,
    490.637115,
)

PAPER_TR_BOTTOM: Point3D = (
    -514.712585,
    301.527771,
    708.277710,
)

PAPER_TR_TOP: Point3D = (
    -515.721069,
    208.359039,
    748.254517,
)

# Build a logical paper coordinate system from the taught left and bottom
# edges. This keeps "millimetres on the drawing" as real physical mm.
_PAPER_RIGHT_Y = PAPER_BR[1] - PAPER_BL[1]
_PAPER_RIGHT_Z = PAPER_BR[2] - PAPER_BL[2]
_PAPER_DOWN_Y = PAPER_BL[1] - PAPER_TL[1]
_PAPER_DOWN_Z = PAPER_BL[2] - PAPER_TL[2]

PAPER_WIDTH_MM = math.hypot(_PAPER_RIGHT_Y, _PAPER_RIGHT_Z)
PAPER_HEIGHT_MM = math.hypot(_PAPER_DOWN_Y, _PAPER_DOWN_Z)

_PAPER_RIGHT_UNIT = (
    _PAPER_RIGHT_Y / PAPER_WIDTH_MM,
    _PAPER_RIGHT_Z / PAPER_WIDTH_MM,
)
_PAPER_DOWN_UNIT = (
    _PAPER_DOWN_Y / PAPER_HEIGHT_MM,
    _PAPER_DOWN_Z / PAPER_HEIGHT_MM,
)

# Leave familiar conservative defaults for the actual artwork size.
# The full calibrated polygon is larger, and the GUI can still be adjusted
# up to PAPER_WIDTH_MM / PAPER_HEIGHT_MM. Reachability is checked point-by-point.
MAX_DRAWING_WIDTH_MM = 330.0
MAX_DRAWING_HEIGHT_MM = 185.0

# Place the SVG lower so the top-left stays available for the heading.
SVG_TOP_MARGIN_MM = 42.0

# ============================================================
# HEADING SETTINGS
# ============================================================

WRITE_HEADING_FIRST = True
HEADING_TEXT = "HELLO NARVA!"

# Left-aligned heading near the top-left of the paper.
HEADING_LEFT_MM = 10.0
HEADING_TOP_MM = 7.0

HEADING_HEIGHT_MM = 18.0
HEADING_WIDTH_MM = 10.0
HEADING_GAP_MM = 3.5
HEADING_SPACE_MM = 8.0
HEADING_SPEED = 70.0


# ============================================================
# MOTION SETTINGS
# ============================================================

READY_JOINT_SPEED = 20.0       # deg/s
TRAVEL_SPEED = 100.0            # mm/s at SAFE_X
APPROACH_SPEED = 25.0          # mm/s toward / away from paper
DRAW_SPEED = 120.0              # mm/s while pen is touching

# Keep the first version conservative and deterministic.
# Every Cartesian target waits until reached.
WAIT_FOR_EACH_POINT = True


# ============================================================
# CONTROLLER SETTINGS
# ============================================================

# Controller input / polling
STICK_DEADZONE = 0.15
TRIGGER_DEADZONE = 0.10
LOOP_INTERVAL_MS = 20          # 50 Hz controller polling

# Cartesian velocity mode (xArm mode 5)
MAX_TCP_SPEED = 80.0           # mm/s at full stick
TCP_MAX_ACC = 400.0            # mm/s^2
VELOCITY_TIMEOUT = 0.5         # controller auto-stops if updates disappear
VELOCITY_SMOOTHING = 0.25      # 0..1, larger = more responsive

# Joint velocity mode (xArm mode 4)
MAX_JOINT_SPEED = 20.0         # deg/s for selected J1-J4
J56_SPEED = 20.0               # deg/s for D-pad J5/J6
JOINT_MAX_ACC = 100.0          # deg/s^2
JOINT_VELOCITY_TIMEOUT = 0.5
JOINT_SMOOTHING = 0.25

# G2 gripper
GRIPPER_MIN = 0.0              # mm, fully closed
GRIPPER_MAX = 84.0             # mm, fully open
GRIPPER_RATE = 40.0            # target-change mm/s at full trigger
GRIPPER_SPEED = 100             # G2 command speed
GRIPPER_FORCE = 50              # G2 force
GRIPPER_SEND_INTERVAL = 0.08

# Xbox-style pygame mapping measured on this controller.
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
DPAD_HAT = 0


# ============================================================
# SVG CLEANUP / CURVE SETTINGS
# ============================================================

MIN_PATH_LENGTH_MM = 2.5
SIMPLIFY_TOLERANCE_MM = 0.7


# These are in SVG source units before scaling. The same values already worked
# for the MG400 SVG importer.
CURVE_TARGET_STEP_UNITS = 3.0
ARC_TARGET_STEP_UNITS = 3.0


# ============================================================
# BASIC GEOMETRY HELPERS
# ============================================================

def distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def polyline_length(points: Sequence[Point2D]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(distance(a, b) for a, b in zip(points, points[1:]))


def remove_duplicate_neighbors(points: Sequence[Point2D], tolerance: float = 1e-9) -> Polyline:
    if not points:
        return []
    out = [points[0]]
    for p in points[1:]:
        if distance(out[-1], p) > tolerance:
            out.append(p)
    return out


def rdp(points: Sequence[Point2D], epsilon: float) -> Polyline:
    """
    Ramer-Douglas-Peucker simplification.
    """
    if len(points) < 3:
        return list(points)

    start = points[0]
    end = points[-1]

    sx, sy = start
    ex, ey = end

    max_dist = -1.0
    index = -1

    denom = math.hypot(ex - sx, ey - sy)
    for i, p in enumerate(points[1:-1], start=1):
        px, py = p
        if denom == 0:
            d = math.hypot(px - sx, py - sy)
        else:
            d = abs((ey - sy) * px - (ex - sx) * py + ex * sy - ey * sx) / denom

        if d > max_dist:
            max_dist = d
            index = i

    if max_dist <= epsilon:
        return [start, end]

    left = rdp(points[: index + 1], epsilon)
    right = rdp(points[index:], epsilon)
    return left[:-1] + right


# ============================================================
# SVG TRANSFORMS
# ============================================================

Affine = Tuple[float, float, float, float, float, float]
IDENTITY: Affine = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(a: Affine, b: Affine) -> Affine:
    """
    Multiply two SVG affine matrices in (a,b,c,d,e,f) form:
        x' = a*x + c*y + e
        y' = b*x + d*y + f
    """
    a1, b1, c1, d1, e1, f1 = a
    a2, b2, c2, d2, e2, f2 = b

    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def apply_mat(m: Affine, p: Point2D) -> Point2D:
    a, b, c, d, e, f = m
    x, y = p
    return (a * x + c * y + e, b * x + d * y + f)


_transform_item_re = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")
_number_re = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def parse_transform(transform: Optional[str]) -> Affine:
    if not transform:
        return IDENTITY

    current = IDENTITY

    for name, arg_text in _transform_item_re.findall(transform):
        values = [float(v) for v in _number_re.findall(arg_text)]

        name = name.strip()

        if name == "matrix" and len(values) == 6:
            item = tuple(values)  # type: ignore
        elif name == "translate":
            tx = values[0] if len(values) >= 1 else 0.0
            ty = values[1] if len(values) >= 2 else 0.0
            item = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif name == "scale":
            sx = values[0] if len(values) >= 1 else 1.0
            sy = values[1] if len(values) >= 2 else sx
            item = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "rotate":
            angle = math.radians(values[0] if values else 0.0)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            rot = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
            if len(values) >= 3:
                cx, cy = values[1], values[2]
                item = mat_mul(
                    mat_mul((1.0, 0.0, 0.0, 1.0, cx, cy), rot),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                item = rot
        elif name == "skewX":
            angle = math.radians(values[0] if values else 0.0)
            item = (1.0, 0.0, math.tan(angle), 1.0, 0.0, 0.0)
        elif name == "skewY":
            angle = math.radians(values[0] if values else 0.0)
            item = (1.0, math.tan(angle), 0.0, 1.0, 0.0, 0.0)
        else:
            item = IDENTITY

        current = mat_mul(current, item)

    return current


# ============================================================
# SVG PATH PARSING / FLATTENING
# ============================================================

_path_token_re = re.compile(
    r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
)


def lerp(a: Point2D, b: Point2D, t: float) -> Point2D:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def cubic_point(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D, t: float) -> Point2D:
    mt = 1.0 - t
    x = (
        mt**3 * p0[0]
        + 3 * mt**2 * t * p1[0]
        + 3 * mt * t**2 * p2[0]
        + t**3 * p3[0]
    )
    y = (
        mt**3 * p0[1]
        + 3 * mt**2 * t * p1[1]
        + 3 * mt * t**2 * p2[1]
        + t**3 * p3[1]
    )
    return (x, y)


def quadratic_point(p0: Point2D, p1: Point2D, p2: Point2D, t: float) -> Point2D:
    mt = 1.0 - t
    x = mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0]
    y = mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1]
    return (x, y)


def flatten_cubic(p0: Point2D, p1: Point2D, p2: Point2D, p3: Point2D) -> Polyline:
    approx = (
        distance(p0, p1)
        + distance(p1, p2)
        + distance(p2, p3)
    )
    steps = max(4, int(math.ceil(approx / CURVE_TARGET_STEP_UNITS)))
    return [cubic_point(p0, p1, p2, p3, i / steps) for i in range(1, steps + 1)]


def flatten_quadratic(p0: Point2D, p1: Point2D, p2: Point2D) -> Polyline:
    approx = distance(p0, p1) + distance(p1, p2)
    steps = max(4, int(math.ceil(approx / CURVE_TARGET_STEP_UNITS)))
    return [quadratic_point(p0, p1, p2, i / steps) for i in range(1, steps + 1)]


def vector_angle(ux: float, uy: float, vx: float, vy: float) -> float:
    dot = ux * vx + uy * vy
    det = ux * vy - uy * vx
    return math.atan2(det, dot)


def flatten_arc(
    p0: Point2D,
    rx: float,
    ry: float,
    x_axis_rotation_deg: float,
    large_arc_flag: float,
    sweep_flag: float,
    p1: Point2D,
) -> Polyline:
    """
    SVG elliptical arc to polyline.
    Based on the SVG specification's endpoint-to-center conversion.
    """
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]

    rx = abs(rx)
    ry = abs(ry)

    phi = math.radians(x_axis_rotation_deg % 360.0)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    x1, y1 = p0
    x2, y2 = p1

    dx2 = (x1 - x2) / 2.0
    dy2 = (y1 - y2) / 2.0

    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2

    # Correct radii if too small.
    lam = (x1p**2) / (rx**2) + (y1p**2) / (ry**2)
    if lam > 1:
        scale = math.sqrt(lam)
        rx *= scale
        ry *= scale

    sign = -1.0 if large_arc_flag == sweep_flag else 1.0

    numerator = rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2
    denominator = rx**2 * y1p**2 + ry**2 * x1p**2
    if denominator == 0:
        return [p1]

    coef = sign * math.sqrt(max(0.0, numerator / denominator))
    cxp = coef * (rx * y1p / ry)
    cyp = coef * (-ry * x1p / rx)

    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2.0

    ux = (x1p - cxp) / rx
    uy = (y1p - cyp) / ry
    vx = (-x1p - cxp) / rx
    vy = (-y1p - cyp) / ry

    theta1 = vector_angle(1, 0, ux, uy)
    delta_theta = vector_angle(ux, uy, vx, vy)

    if not sweep_flag and delta_theta > 0:
        delta_theta -= 2 * math.pi
    elif sweep_flag and delta_theta < 0:
        delta_theta += 2 * math.pi

    approx_len = max(rx, ry) * abs(delta_theta)
    steps = max(6, int(math.ceil(approx_len / ARC_TARGET_STEP_UNITS)))

    pts = []
    for i in range(1, steps + 1):
        t = theta1 + delta_theta * i / steps
        ct = math.cos(t)
        st = math.sin(t)

        x = cos_phi * rx * ct - sin_phi * ry * st + cx
        y = sin_phi * rx * ct + cos_phi * ry * st + cy
        pts.append((x, y))

    return pts


def parse_svg_path(d: str) -> List[Polyline]:
    tokens = _path_token_re.findall(d)
    if not tokens:
        return []

    i = 0
    cmd = None

    paths: List[Polyline] = []
    current_path: Polyline = []

    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    last_cubic_ctrl: Optional[Point2D] = None
    last_quad_ctrl: Optional[Point2D] = None

    def is_command(tok: str) -> bool:
        return len(tok) == 1 and tok.isalpha()

    def next_number() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    def ensure_path_started():
        nonlocal current_path
        if not current_path:
            current_path = [cur]

    while i < len(tokens):
        if is_command(tokens[i]):
            cmd = tokens[i]
            i += 1
        elif cmd is None:
            raise ValueError("SVG path data started without a command.")

        assert cmd is not None

        if cmd in "Mm":
            x = next_number()
            y = next_number()
            cur = (x, y) if cmd == "M" else (cur[0] + x, cur[1] + y)

            if current_path:
                paths.append(remove_duplicate_neighbors(current_path))
            current_path = [cur]
            start = cur

            last_cubic_ctrl = None
            last_quad_ctrl = None

            # Additional pairs after M/m become L/l
            while i < len(tokens) and not is_command(tokens[i]):
                x = next_number()
                y = next_number()
                nxt = (x, y) if cmd == "M" else (cur[0] + x, cur[1] + y)
                current_path.append(nxt)
                cur = nxt

            cmd = "L" if cmd == "M" else "l"

        elif cmd in "Ll":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                x = next_number()
                y = next_number()
                nxt = (x, y) if cmd == "L" else (cur[0] + x, cur[1] + y)
                current_path.append(nxt)
                cur = nxt
            last_cubic_ctrl = None
            last_quad_ctrl = None

        elif cmd in "Hh":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                x = next_number()
                nxt = (x, cur[1]) if cmd == "H" else (cur[0] + x, cur[1])
                current_path.append(nxt)
                cur = nxt
            last_cubic_ctrl = None
            last_quad_ctrl = None

        elif cmd in "Vv":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                y = next_number()
                nxt = (cur[0], y) if cmd == "V" else (cur[0], cur[1] + y)
                current_path.append(nxt)
                cur = nxt
            last_cubic_ctrl = None
            last_quad_ctrl = None

        elif cmd in "Cc":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                x1 = next_number()
                y1 = next_number()
                x2 = next_number()
                y2 = next_number()
                x = next_number()
                y = next_number()

                p1 = (x1, y1) if cmd == "C" else (cur[0] + x1, cur[1] + y1)
                p2 = (x2, y2) if cmd == "C" else (cur[0] + x2, cur[1] + y2)
                p = (x, y) if cmd == "C" else (cur[0] + x, cur[1] + y)

                current_path.extend(flatten_cubic(cur, p1, p2, p))
                cur = p
                last_cubic_ctrl = p2
                last_quad_ctrl = None

        elif cmd in "Ss":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                x2 = next_number()
                y2 = next_number()
                x = next_number()
                y = next_number()

                if last_cubic_ctrl is None:
                    p1 = cur
                else:
                    p1 = (2 * cur[0] - last_cubic_ctrl[0], 2 * cur[1] - last_cubic_ctrl[1])

                p2 = (x2, y2) if cmd == "S" else (cur[0] + x2, cur[1] + y2)
                p = (x, y) if cmd == "S" else (cur[0] + x, cur[1] + y)

                current_path.extend(flatten_cubic(cur, p1, p2, p))
                cur = p
                last_cubic_ctrl = p2
                last_quad_ctrl = None

        elif cmd in "Qq":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                x1 = next_number()
                y1 = next_number()
                x = next_number()
                y = next_number()

                p1 = (x1, y1) if cmd == "Q" else (cur[0] + x1, cur[1] + y1)
                p = (x, y) if cmd == "Q" else (cur[0] + x, cur[1] + y)

                current_path.extend(flatten_quadratic(cur, p1, p))
                cur = p
                last_quad_ctrl = p1
                last_cubic_ctrl = None

        elif cmd in "Tt":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                x = next_number()
                y = next_number()

                if last_quad_ctrl is None:
                    p1 = cur
                else:
                    p1 = (2 * cur[0] - last_quad_ctrl[0], 2 * cur[1] - last_quad_ctrl[1])

                p = (x, y) if cmd == "T" else (cur[0] + x, cur[1] + y)

                current_path.extend(flatten_quadratic(cur, p1, p))
                cur = p
                last_quad_ctrl = p1
                last_cubic_ctrl = None

        elif cmd in "Aa":
            ensure_path_started()
            while i < len(tokens) and not is_command(tokens[i]):
                rx = next_number()
                ry = next_number()
                angle = next_number()
                large = next_number()
                sweep = next_number()
                x = next_number()
                y = next_number()

                p = (x, y) if cmd == "A" else (cur[0] + x, cur[1] + y)

                current_path.extend(flatten_arc(cur, rx, ry, angle, large, sweep, p))
                cur = p
                last_cubic_ctrl = None
                last_quad_ctrl = None

        elif cmd in "Zz":
            if current_path:
                current_path.append(start)
                paths.append(remove_duplicate_neighbors(current_path))
                current_path = []
                cur = start
            last_cubic_ctrl = None
            last_quad_ctrl = None

        else:
            raise ValueError(f"Unsupported SVG path command: {cmd}")

    if current_path:
        paths.append(remove_duplicate_neighbors(current_path))

    return [p for p in paths if len(p) >= 2]


# ============================================================
# SVG LOADING
# ============================================================

def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def visible_stroked_element(elem: ET.Element) -> bool:
    style = elem.attrib.get("style", "")
    display = elem.attrib.get("display", "")
    if "display:none" in style or display == "none":
        return False

    # If stroke is explicitly none and no style stroke is present, skip.
    stroke_attr = elem.attrib.get("stroke")
    if stroke_attr == "none":
        return False
    if "stroke:none" in style:
        return False

    return True


def parse_points_attribute(text: str) -> Polyline:
    nums = [float(v) for v in _number_re.findall(text)]
    pts = []
    for i in range(0, len(nums) - 1, 2):
        pts.append((nums[i], nums[i + 1]))
    return pts


def ellipse_polyline(cx: float, cy: float, rx: float, ry: float, steps: int = 40) -> Polyline:
    pts = []
    for i in range(steps + 1):
        t = 2 * math.pi * i / steps
        pts.append((cx + rx * math.cos(t), cy + ry * math.sin(t)))
    return pts


class SVGExtractor:
    def __init__(self, svg_file: str):
        self.svg_file = svg_file

    def load(self) -> Tuple[List[Polyline], float, float]:
        root = ET.parse(self.svg_file).getroot()

        view_box = root.attrib.get("viewBox", "").strip()
        if view_box:
            vb = [float(v) for v in view_box.replace(",", " ").split()]
            if len(vb) == 4:
                _, _, view_w, view_h = vb
            else:
                view_w = float(root.attrib.get("width", "100"))
                view_h = float(root.attrib.get("height", "100"))
        else:
            view_w = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", root.attrib.get("width", "100"))[0])
            view_h = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", root.attrib.get("height", "100"))[0])

        paths: List[Polyline] = []
        self._collect(root, IDENTITY, paths)

        return paths, view_w, view_h

    def _collect(self, elem: ET.Element, inherited_transform: Affine, out_paths: List[Polyline]) -> None:
        this_transform = mat_mul(inherited_transform, parse_transform(elem.attrib.get("transform")))
        tag = local_name(elem.tag)

        if tag == "g" or tag == "svg":
            for child in list(elem):
                self._collect(child, this_transform, out_paths)
            return

        if not visible_stroked_element(elem):
            return

        if tag == "path":
            d = elem.attrib.get("d", "")
            for poly in parse_svg_path(d):
                transformed = [apply_mat(this_transform, p) for p in poly]
                transformed = remove_duplicate_neighbors(transformed)
                if len(transformed) >= 2:
                    out_paths.append(transformed)

        elif tag == "ellipse":
            cx = float(elem.attrib.get("cx", "0"))
            cy = float(elem.attrib.get("cy", "0"))
            rx = float(elem.attrib.get("rx", "0"))
            ry = float(elem.attrib.get("ry", "0"))
            poly = ellipse_polyline(cx, cy, rx, ry)
            transformed = [apply_mat(this_transform, p) for p in poly]
            out_paths.append(remove_duplicate_neighbors(transformed))

        elif tag == "circle":
            cx = float(elem.attrib.get("cx", "0"))
            cy = float(elem.attrib.get("cy", "0"))
            r = float(elem.attrib.get("r", "0"))
            poly = ellipse_polyline(cx, cy, r, r)
            transformed = [apply_mat(this_transform, p) for p in poly]
            out_paths.append(remove_duplicate_neighbors(transformed))

        elif tag == "line":
            x1 = float(elem.attrib.get("x1", "0"))
            y1 = float(elem.attrib.get("y1", "0"))
            x2 = float(elem.attrib.get("x2", "0"))
            y2 = float(elem.attrib.get("y2", "0"))
            poly = [apply_mat(this_transform, (x1, y1)), apply_mat(this_transform, (x2, y2))]
            out_paths.append(remove_duplicate_neighbors(poly))

        elif tag == "polyline":
            pts = parse_points_attribute(elem.attrib.get("points", ""))
            transformed = [apply_mat(this_transform, p) for p in pts]
            transformed = remove_duplicate_neighbors(transformed)
            if len(transformed) >= 2:
                out_paths.append(transformed)

        elif tag == "polygon":
            pts = parse_points_attribute(elem.attrib.get("points", ""))
            if pts:
                pts.append(pts[0])
            transformed = [apply_mat(this_transform, p) for p in pts]
            transformed = remove_duplicate_neighbors(transformed)
            if len(transformed) >= 2:
                out_paths.append(transformed)

        elif tag == "rect":
            x = float(elem.attrib.get("x", "0"))
            y = float(elem.attrib.get("y", "0"))
            w = float(elem.attrib.get("width", "0"))
            h = float(elem.attrib.get("height", "0"))
            poly = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
            transformed = [apply_mat(this_transform, p) for p in poly]
            out_paths.append(remove_duplicate_neighbors(transformed))






# ============================================================
# PAPER MAPPING
# ============================================================

def _yz_to_paper_mm(y: float, z: float) -> Point2D:
    """
    Convert an xArm Y/Z point into logical paper coordinates:
        x = mm to the right
        y = mm downward

    The basis comes from the taught TL->BL and BL->BR edges.
    """
    vy = y - PAPER_TL[1]
    vz = z - PAPER_TL[2]

    ry, rz = _PAPER_RIGHT_UNIT
    dy, dz = _PAPER_DOWN_UNIT

    det = ry * dz - rz * dy
    if abs(det) < 1e-9:
        raise RuntimeError("Paper calibration basis is degenerate.")

    right_mm = (vy * dz - vz * dy) / det
    down_mm = (ry * vz - rz * vy) / det
    return (right_mm, down_mm)


# Logical coordinates of the two measured points forming the clipped corner.
PAPER_TR_TOP_MM: Point2D = _yz_to_paper_mm(
    PAPER_TR_TOP[1],
    PAPER_TR_TOP[2],
)
PAPER_TR_BOTTOM_MM: Point2D = _yz_to_paper_mm(
    PAPER_TR_BOTTOM[1],
    PAPER_TR_BOTTOM[2],
)

# Reachable polygon in logical paper mm, clockwise.
PAPER_REACHABLE_POLYGON: List[Point2D] = [
    (0.0, 0.0),
    PAPER_TR_TOP_MM,
    PAPER_TR_BOTTOM_MM,
    (PAPER_WIDTH_MM, PAPER_HEIGHT_MM),
    (0.0, PAPER_HEIGHT_MM),
]


def _barycentric_weights(
    p: Point2D,
    a: Point2D,
    b: Point2D,
    c: Point2D,
) -> Optional[Tuple[float, float, float]]:
    """Return barycentric weights for p in triangle abc, or None if degenerate."""
    px, py = p
    ax, ay = a
    bx, by = b
    cx, cy = c

    denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denom) < 1e-12:
        return None

    w1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denom
    w2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denom
    w3 = 1.0 - w1 - w2
    return (w1, w2, w3)


def _blend3(
    weights: Tuple[float, float, float],
    a: Point3D,
    b: Point3D,
    c: Point3D,
) -> Point3D:
    w1, w2, w3 = weights
    return (
        w1 * a[0] + w2 * b[0] + w3 * c[0],
        w1 * a[1] + w2 * b[1] + w3 * c[1],
        w1 * a[2] + w2 * b[2] + w3 * c[2],
    )


# Fan triangulation of the convex 5-point reachable polygon.
# Using the measured 3D points directly means every calibration point is
# reproduced exactly; there is no single-plane approximation error.
_PAPER_TRIANGLES = [
    (
        (0.0, 0.0), PAPER_TL,
        PAPER_TR_TOP_MM, PAPER_TR_TOP,
        PAPER_TR_BOTTOM_MM, PAPER_TR_BOTTOM,
    ),
    (
        (0.0, 0.0), PAPER_TL,
        PAPER_TR_BOTTOM_MM, PAPER_TR_BOTTOM,
        (PAPER_WIDTH_MM, PAPER_HEIGHT_MM), PAPER_BR,
    ),
    (
        (0.0, 0.0), PAPER_TL,
        (PAPER_WIDTH_MM, PAPER_HEIGHT_MM), PAPER_BR,
        (0.0, PAPER_HEIGHT_MM), PAPER_BL,
    ),
]


def paper_mm_is_reachable(
    right_mm: float,
    down_mm: float,
    tolerance: float = 1e-7,
) -> bool:
    """True if the logical paper point lies inside the calibrated polygon."""
    p = (right_mm, down_mm)

    for a2, _a3, b2, _b3, c2, _c3 in _PAPER_TRIANGLES:
        weights = _barycentric_weights(p, a2, b2, c2)
        if weights is None:
            continue
        if min(weights) >= -tolerance:
            return True

    return False


def paper_mm_to_contact(right_mm: float, down_mm: float) -> Point3D:
    """
    Map logical paper millimetres to the calibrated 3D wall surface.

    The surface is a piecewise-planar interpolation through all five taught
    points. The clipped upper-right area is rejected instead of extrapolated.
    """
    p = (right_mm, down_mm)

    for a2, a3, b2, b3, c2, c3 in _PAPER_TRIANGLES:
        weights = _barycentric_weights(p, a2, b2, c2)
        if weights is None:
            continue

        if min(weights) >= -1e-7:
            x, y, z = _blend3(weights, a3, b3, c3)
            return (x + CONTACT_X_OFFSET_MM, y, z)

    raise RuntimeError(
        "Drawing point is outside the calibrated reachable wall area: "
        f"right={right_mm:.1f} mm, down={down_mm:.1f} mm. "
        "This is usually the clipped upper-right corner."
    )


def safe_point(contact: Point3D) -> Point3D:
    """Same Y/Z as contact point, but pulled away from the wall to SAFE_X."""
    _, y, z = contact
    return (SAFE_X, y, z)




def validate_paper_calibration() -> None:
    """Fail early if the derived polygon or taught-point mapping is inconsistent."""
    expected = [
        ((0.0, 0.0), PAPER_TL),
        (PAPER_TR_TOP_MM, PAPER_TR_TOP),
        (PAPER_TR_BOTTOM_MM, PAPER_TR_BOTTOM),
        ((PAPER_WIDTH_MM, PAPER_HEIGHT_MM), PAPER_BR),
        ((0.0, PAPER_HEIGHT_MM), PAPER_BL),
    ]

    # Compare after removing the editable contact offset from X.
    for logical, taught in expected:
        mapped = paper_mm_to_contact(*logical)
        mapped_no_offset = (
            mapped[0] - CONTACT_X_OFFSET_MM,
            mapped[1],
            mapped[2],
        )
        err = point3_distance(mapped_no_offset, taught)
        if err > 0.01:
            raise RuntimeError(
                "Paper calibration self-check failed at "
                f"{logical}: error={err:.4f} mm"
            )



def point3_distance(a: Point3D, b: Point3D) -> float:
    return math.sqrt(
        (b[0] - a[0]) ** 2
        + (b[1] - a[1]) ** 2
        + (b[2] - a[2]) ** 2
    )


# Pure-math calibration check; does not connect to or move the robot.
validate_paper_calibration()



# ============================================================
# SIMPLE LINE FONT
# ============================================================

# 3x3 normalized character grid:
#
#   1 --- 2 --- 3
#   |     |     |
#   4 --- 5 --- 6
#   |     |     |
#   7 --- 8 --- 9
#
# x = 0..1 from left to right
# y = 0..1 from top to bottom
FONT_POINTS: Dict[object, Point2D] = {
    1: (0.0, 0.0),
    2: (0.5, 0.0),
    3: (1.0, 0.0),
    4: (0.0, 0.5),
    5: (0.5, 0.5),
    6: (1.0, 0.5),
    7: (0.0, 1.0),
    8: (0.5, 1.0),
    9: (1.0, 1.0),

    "A_LEFT": (0.25, 0.5),
    "A_RIGHT": (0.75, 0.5),

    # Slightly above the normal character box.
    "DOT_TOP_LEFT": (0.30, -0.18),
    "DOT_TOP_RIGHT": (0.70, -0.18),

    "TILDE_LEFT": (0.20, -0.18),
    "TILDE_MID_LEFT": (0.40, -0.28),
    "TILDE_MID_RIGHT": (0.60, -0.08),
    "TILDE_RIGHT": (0.80, -0.18),
}

# Same simple straight-line alphabet that worked in the earlier robot writer.
FONT_STROKES: Dict[str, List[List[object]]] = {
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

    "Ä": [[7, 2, 9], ["A_LEFT", "A_RIGHT"],
          ["DOT_TOP_LEFT"], ["DOT_TOP_RIGHT"]],
    "Ö": [[1, 3, 9, 7, 1],
          ["DOT_TOP_LEFT"], ["DOT_TOP_RIGHT"]],
    "Ü": [[1, 7, 9, 3],
          ["DOT_TOP_LEFT"], ["DOT_TOP_RIGHT"]],
    "Õ": [[1, 3, 9, 7, 1],
          ["TILDE_LEFT", "TILDE_MID_LEFT",
           "TILDE_MID_RIGHT", "TILDE_RIGHT"]],
}


def build_heading_paths(text: str) -> List[Path3D]:
    """
    Build 3D pen paths for left-aligned text.

    Lowercase input is automatically converted to uppercase.
    Supported: A-Z, Ä Ö Ü Õ, space, ! ? .
    """
    paths: List[Path3D] = []
    cursor_x = HEADING_LEFT_MM

    for ch in text.upper():
        if ch == " ":
            cursor_x += HEADING_SPACE_MM
            continue

        glyph = FONT_STROKES.get(ch)
        if glyph is None:
            # Unsupported character: leave a normal character-sized gap.
            cursor_x += HEADING_WIDTH_MM + HEADING_GAP_MM
            continue

        for stroke in glyph:
            path: Path3D = []

            # A single-point stroke is a dot. Give it a short visible segment
            # instead of sending a zero-length robot path.
            if len(stroke) == 1:
                gx, gy = FONT_POINTS[stroke[0]]
                dot_half_mm = max(0.5, HEADING_HEIGHT_MM * 0.035)

                p1 = paper_mm_to_contact(
                    cursor_x + gx * HEADING_WIDTH_MM,
                    HEADING_TOP_MM + gy * HEADING_HEIGHT_MM - dot_half_mm,
                )
                p2 = paper_mm_to_contact(
                    cursor_x + gx * HEADING_WIDTH_MM,
                    HEADING_TOP_MM + gy * HEADING_HEIGHT_MM + dot_half_mm,
                )
                paths.append([p1, p2])
                continue

            for point_name in stroke:
                gx, gy = FONT_POINTS[point_name]
                right_mm = cursor_x + gx * HEADING_WIDTH_MM
                down_mm = HEADING_TOP_MM + gy * HEADING_HEIGHT_MM
                path.append(paper_mm_to_contact(right_mm, down_mm))

            if len(path) >= 2:
                paths.append(path)

        cursor_x += HEADING_WIDTH_MM + HEADING_GAP_MM

    if cursor_x > PAPER_WIDTH_MM:
        raise RuntimeError(
            f'Text "{text}" is too wide for the calibrated paper.'
        )

    return paths


@dataclass
class XArmSVGSettings:
    svg_file: str = SVG_FILE
    max_width_mm: float = MAX_DRAWING_WIDTH_MM
    max_height_mm: float = MAX_DRAWING_HEIGHT_MM
    min_path_length_mm: float = MIN_PATH_LENGTH_MM
    simplify_tolerance_mm: float = SIMPLIFY_TOLERANCE_MM


class XArmSVGDrawer:
    def __init__(
        self,
        settings: Optional[XArmSVGSettings] = None,
        arm: Optional[XArmAPI] = None,
    ):
        self.settings = settings or XArmSVGSettings()
        self.arm: Optional[XArmAPI] = arm
        self._owns_arm = arm is None
        self.paths: List[Path3D] = []

        if self.settings.svg_file:
            self.load_svg()

    # ------------------------------------------------------------
    # SVG -> PAPER
    # ------------------------------------------------------------

    def load_svg(self) -> None:
        svg_path = Path(self.settings.svg_file)
        if not svg_path.is_absolute():
            svg_path = Path(__file__).resolve().parent / svg_path

        extractor = SVGExtractor(str(svg_path))
        raw_paths, _, _ = extractor.load()

        if not raw_paths:
            raise RuntimeError(f"No drawable paths found in SVG: {svg_path}")

        all_points = [p for poly in raw_paths for p in poly]
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)

        src_w = max_x - min_x
        src_h = max_y - min_y

        if src_w <= 0 or src_h <= 0:
            raise RuntimeError("SVG bounding box is degenerate.")

        # Uniform scaling: keep the SVG proportions.
        scale_mm = min(
            self.settings.max_width_mm / src_w,
            self.settings.max_height_mm / src_h,
        )

        final_w = src_w * scale_mm
        final_h = src_h * scale_mm

        # Center horizontally, but intentionally place the building lower
        # so the top-left area remains available for "HELLO NARVA!".
        left_margin_mm = (PAPER_WIDTH_MM - final_w) / 2.0
        top_margin_mm = SVG_TOP_MARGIN_MM

        if top_margin_mm + final_h > PAPER_HEIGHT_MM:
            raise RuntimeError(
                f"Drawing does not fit vertically: top margin {top_margin_mm:.1f} "
                f"+ drawing {final_h:.1f} > paper {PAPER_HEIGHT_MM:.1f} mm"
            )

        mapped_paths: List[Path3D] = []

        for raw in raw_paths:
            # First convert to local physical drawing mm.
            local_mm: Polyline = []
            for x, y in raw:
                local_right_mm = (x - min_x) * scale_mm
                local_down_mm = (y - min_y) * scale_mm
                local_mm.append((local_right_mm, local_down_mm))

            local_mm = remove_duplicate_neighbors(local_mm)
            if len(local_mm) < 2:
                continue

            if self.settings.simplify_tolerance_mm > 0:
                local_mm = rdp(local_mm, self.settings.simplify_tolerance_mm)
                local_mm = remove_duplicate_neighbors(local_mm)

            if len(local_mm) < 2:
                continue

            if polyline_length(local_mm) < self.settings.min_path_length_mm:
                continue

            path3d: Path3D = []
            for right_mm, down_mm in local_mm:
                paper_right_mm = left_margin_mm + right_mm
                paper_down_mm = top_margin_mm + down_mm
                path3d.append(
                    paper_mm_to_contact(
                        paper_right_mm,
                        paper_down_mm,
                    )
                )

            # Remove effectively duplicate 3D points.
            cleaned: Path3D = []
            for p in path3d:
                if not cleaned or point3_distance(cleaned[-1], p) > 0.02:
                    cleaned.append(p)

            if len(cleaned) >= 2:
                mapped_paths.append(cleaned)

        self.paths = mapped_paths

        print(f"Loaded SVG: {svg_path}")
        print(f"  raw paths: {len(raw_paths)}")
        print(f"  kept paths: {len(self.paths)}")
        print(f"  SVG content bbox: {src_w:.2f} x {src_h:.2f}")
        print(f"  final drawing size: {final_w:.1f} x {final_h:.1f} mm")
        print(f"  drawing top margin: {top_margin_mm:.1f} mm")
        print(f"  paper: {PAPER_WIDTH_MM:.0f} x {PAPER_HEIGHT_MM:.0f} mm")
        print(
            "  clipped corner: "
            f"TR-top=({PAPER_TR_TOP_MM[0]:.1f}, {PAPER_TR_TOP_MM[1]:.1f}) mm, "
            f"TR-bottom=({PAPER_TR_BOTTOM_MM[0]:.1f}, {PAPER_TR_BOTTOM_MM[1]:.1f}) mm"
        )

    # ------------------------------------------------------------
    # xARM CONNECTION / MOVEMENT
    # ------------------------------------------------------------

    @staticmethod
    def _check_code(code: int, action: str) -> None:
        if code != 0:
            raise RuntimeError(f"xArm error during {action}: code={code}")

    def connect(self) -> None:
        # In the combined app this class normally borrows an already-connected
        # XArmAPI instance. It can still be used standalone if no arm was passed.
        if self.arm is None:
            print(f"Connecting to xArm at {ROBOT_IP}...")
            self.arm = XArmAPI(ROBOT_IP, is_radian=False)
            self.arm.connect()
            self._owns_arm = True

        # Drawing/writing uses normal position-control mode.
        self.arm.clean_warn()
        self.arm.clean_error()
        self._check_code(self.arm.motion_enable(enable=True), "motion_enable")
        self._check_code(self.arm.set_mode(0), "set_mode(0)")
        self._check_code(self.arm.set_state(0), "set_state(0)")

        print("Connected and enabled in position mode.")

    def disconnect(self) -> None:
        # Never close the combined app's shared connection.
        if self.arm is not None and self._owns_arm:
            try:
                self.arm.disconnect()
            finally:
                self.arm = None
        if self._owns_arm:
            print("xArm disconnected.")

    def move_ready(self) -> None:
        assert self.arm is not None
        print("Moving to known ready joint pose...")
        code = self.arm.set_servo_angle(
            angle=READY_JOINTS,
            speed=READY_JOINT_SPEED,
            wait=True,
            is_radian=False,
        )
        self._check_code(code, "move to ready joints")

    def move_xyz(self, point: Point3D, speed: float, wait: bool = True) -> None:
        assert self.arm is not None
        x, y, z = point
        code = self.arm.set_position(
            x=x,
            y=y,
            z=z,
            roll=ROLL,
            pitch=PITCH,
            yaw=YAW,
            speed=speed,
            wait=wait,
            relative=False,
            is_radian=False,
        )
        self._check_code(code, f"move to X={x:.1f}, Y={y:.1f}, Z={z:.1f}")

    # ------------------------------------------------------------
    # HEADING
    # ------------------------------------------------------------

    def preflight_heading(self, text: str = HEADING_TEXT) -> None:
        paths = build_heading_paths(text)

        print()
        print(f'Preflighting text: "{text}"')
        print(f"Heading strokes: {len(paths)}")

        for path in paths:
            self.move_xyz(safe_point(path[0]), TRAVEL_SPEED, wait=True)

            for p in path[1:-1]:
                self.move_xyz(safe_point(p), TRAVEL_SPEED, wait=False)

            self.move_xyz(safe_point(path[-1]), TRAVEL_SPEED, wait=True)

        print("Heading preflight finished.")

    def write_heading(self, text: str = HEADING_TEXT) -> None:
        paths = build_heading_paths(text)

        print()
        print(f'Writing text: "{text}"')
        print(f"Heading strokes: {len(paths)}")

        for path in paths:
            start_contact = path[0]

            self.move_xyz(safe_point(start_contact), TRAVEL_SPEED, wait=True)
            self.move_xyz(start_contact, APPROACH_SPEED, wait=True)

            for p in path[1:-1]:
                self.move_xyz(p, HEADING_SPEED, wait=False)

            self.move_xyz(path[-1], HEADING_SPEED, wait=True)
            self.move_xyz(safe_point(path[-1]), APPROACH_SPEED, wait=True)

        print("Heading finished.")

    # ------------------------------------------------------------
    # PREFLIGHT
    # ------------------------------------------------------------

    def preflight(self) -> None:
        print()
        print(f"Starting pen-up preflight for {len(self.paths)} SVG paths...")
        print(f"Safe plane X = {SAFE_X:.1f}")

        for i, path in enumerate(self.paths, start=1):
            if not path:
                continue

            if i == 1 or i % 20 == 0 or i == len(self.paths):
                print(f"Preflight path {i}/{len(self.paths)}")

            # Move to path start on safe plane.
            self.move_xyz(safe_point(path[0]), TRAVEL_SPEED, wait=True)

            # Follow its Y/Z geometry without touching the paper.
            # Intermediate points may be queued, but always wait for the final
            # point before starting the next path.
            if len(path) > 1:
                for p in path[1:-1]:
                    self.move_xyz(
                        safe_point(p),
                        TRAVEL_SPEED,
                        wait=WAIT_FOR_EACH_POINT,
                    )

                self.move_xyz(
                    safe_point(path[-1]),
                    TRAVEL_SPEED,
                    wait=True,
                )

        print("Pen-up preflight finished.")

    # ------------------------------------------------------------
    # DRAW
    # ------------------------------------------------------------

    def draw(self) -> None:
        print()
        print(f"Starting SVG drawing: {len(self.paths)} paths")
        print(f"Travel plane X = {SAFE_X:.1f}")
        print("Contact surface uses the new 5-point clipped calibration.")

        for i, path in enumerate(self.paths, start=1):
            if len(path) < 2:
                continue

            if i == 1 or i % 20 == 0 or i == len(self.paths):
                print(f"Drawing path {i}/{len(self.paths)}")

            start_contact = path[0]
            start_safe = safe_point(start_contact)

            # 1) Travel in Y/Z while away from the wall.
            self.move_xyz(start_safe, TRAVEL_SPEED, wait=True)

            # 2) Move straight toward wall until marker touches.
            self.move_xyz(start_contact, APPROACH_SPEED, wait=True)

            # 3) Follow the SVG while continuously staying on the calibrated surface.
            # Queue intermediate points for speed.
            for p in path[1:-1]:
                self.move_xyz(p, DRAW_SPEED, wait=False)

            # Explicitly wait for the final drawing point.
            # This guarantees the drawn path has finished before retracting.
            self.move_xyz(path[-1], DRAW_SPEED, wait=True)

            # 4) Only now pull straight away from the wall.
            self.move_xyz(
                safe_point(path[-1]),
                APPROACH_SPEED,
                wait=True,
            )

        print("SVG drawing finished.")



# ============================================================
# CONTROLLER HELPERS
# ============================================================

def apply_deadzone(value: float, deadzone: float) -> float:
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return math.copysign(scaled, value)


def trigger_amount(raw_value: float, deadzone: float = TRIGGER_DEADZONE) -> float:
    # Xbox triggers report roughly -1 released ... +1 fully pressed.
    amount = max(0.0, min(1.0, (raw_value + 1.0) / 2.0))
    if amount <= deadzone:
        return 0.0
    return (amount - deadzone) / (1.0 - deadzone)


# ============================================================
# PERSISTENT ROBOT / CONTROLLER CORE
# ============================================================

class XArmControlCore:
    """Owns the single persistent xArm connection used by controller and drawer."""

    def __init__(
        self,
        log_callback: Callable[[str], None],
        status_callback: Callable[[str], None],
    ) -> None:
        self.log = log_callback
        self.set_status = status_callback

        self.arm: Optional[XArmAPI] = None
        self.connected = False
        self.enabled = False

        # User-facing controller mode.
        self.control_mode = "XYZ"
        self.selected_joint = 1

        # Actual xArm mode: 0=position, 4=joint velocity, 5=Cartesian velocity.
        self.velocity_mode = 5
        self.xyz_dpad_active = False

        self.stop_latched = True
        self.fault_latched = False
        self.fault_error_code = 0
        self.manual_stop_latched = False
        self.currently_moving = False

        # True while a ready/preflight/draw/write worker owns the robot.
        self.automation_active = False
        self.automation_stop_requested = False

        # Tunable controller settings (updated from GUI).
        self.deadzone = STICK_DEADZONE
        self.max_tcp_speed = MAX_TCP_SPEED
        self.tcp_max_acc = TCP_MAX_ACC
        self.velocity_timeout = VELOCITY_TIMEOUT
        self.velocity_smoothing = VELOCITY_SMOOTHING

        self.max_joint_speed = MAX_JOINT_SPEED
        self.j56_speed = J56_SPEED
        self.joint_max_acc = JOINT_MAX_ACC
        self.joint_velocity_timeout = JOINT_VELOCITY_TIMEOUT
        self.joint_smoothing = JOINT_SMOOTHING

        self.gripper_rate = GRIPPER_RATE
        self.gripper_speed = GRIPPER_SPEED
        self.gripper_force = GRIPPER_FORCE
        self.gripper_target = GRIPPER_MAX
        self.last_gripper_sent = GRIPPER_MAX
        self.last_gripper_send_time = 0.0

        self.smoothed_vx = 0.0
        self.smoothed_vy = 0.0
        self.smoothed_vz = 0.0
        self.smoothed_joint = [0.0] * 6

        self.last_motion_text = "STOP"
        self.last_speed_text = "0"
        self.last_api_log_time = 0.0

    # --------------------------------------------------------
    # Connection / setup
    # --------------------------------------------------------

    def connect(self, ip: str) -> None:
        if self.connected and self.arm is not None:
            self.enable_for_controller()
            return

        self.set_status("Connecting to xArm...")
        self.log(f"Connecting to xArm at {ip}...")

        arm = XArmAPI(ip, is_radian=False)
        arm.connect()
        if not arm.connected:
            raise RuntimeError(f"Could not connect to xArm at {ip}")

        self.arm = arm
        self.connected = True

        self.arm.clean_warn()
        self.arm.clean_error()

        # Tell self-collision detection that the G2 tool is fitted.
        try:
            code = self.arm.set_collision_tool_model(9)
            self.log(f"G2 collision model: {code}")
        except Exception as exc:
            self.log(f"G2 collision model setup failed: {exc}")

        try:
            code = self.arm.set_self_collision_detection(True)
            self.log(f"Self-collision detection: {code}")
        except Exception as exc:
            self.log(f"Self-collision detection setup failed: {exc}")

        self.enable_for_controller()
        self._read_initial_gripper_position()
        self.log("xArm connected and controller-ready.")

    def enable_for_controller(self) -> None:
        if self.arm is None:
            raise RuntimeError("Robot is not connected.")

        self.arm.clean_warn()
        self.arm.clean_error()
        self._check_code(self.arm.motion_enable(enable=True), "motion_enable")

        desired_mode = 4 if self.control_mode == "JOINT" else 5
        self._check_code(self.arm.set_mode(desired_mode), f"set_mode({desired_mode})")
        self._check_code(self.arm.set_state(0), "set_state(0)")

        self.arm.set_tcp_maxacc(self.tcp_max_acc)
        self.arm.set_joint_maxacc(self.joint_max_acc)

        self.enabled = True
        self.velocity_mode = desired_mode
        self.xyz_dpad_active = False
        self.fault_latched = False
        self.fault_error_code = 0
        self.manual_stop_latched = False
        self.stop_latched = True
        self.reset_smoothing()
        self.set_status("Robot enabled")

    def disable(self) -> None:
        if self.arm is None:
            return

        try:
            if self.automation_active:
                self.automation_stop_requested = True
                self.arm.set_state(4)
            else:
                self.stop_velocity(force=True)
        except Exception:
            pass

        try:
            self.arm.motion_enable(enable=False)
        except Exception as exc:
            self.log(f"Disable error: {exc}")

        self.enabled = False
        self.currently_moving = False
        self.stop_latched = True
        self.set_status("Robot disabled")

    def disconnect(self) -> None:
        if self.arm is None:
            return
        try:
            self.disable()
        except Exception:
            pass
        try:
            self.arm.disconnect()
        finally:
            self.arm = None
            self.connected = False
            self.enabled = False
            self.set_status("Robot disconnected")

    @staticmethod
    def _check_code(code: int, action: str) -> None:
        if code != 0:
            raise RuntimeError(f"xArm error during {action}: code={code}")

    def _read_initial_gripper_position(self) -> None:
        if self.arm is None:
            return
        try:
            result = self.arm.get_gripper_g2_position()
            self.log(f"G2 position: {result}")
            if isinstance(result, (tuple, list)) and len(result) >= 2 and result[0] == 0:
                value = float(result[1])
                value = max(GRIPPER_MIN, min(GRIPPER_MAX, value))
                self.gripper_target = value
                self.last_gripper_sent = value
        except Exception as exc:
            self.log(f"Could not read G2 position: {exc}")

    # --------------------------------------------------------
    # Shared state / smoothing
    # --------------------------------------------------------

    def reset_smoothing(self) -> None:
        self.smoothed_vx = 0.0
        self.smoothed_vy = 0.0
        self.smoothed_vz = 0.0
        self.smoothed_joint = [0.0] * 6

    def _throttled_api_log(self, message: str) -> None:
        now = time.monotonic()
        if now - self.last_api_log_time >= 0.5:
            self.log(message)
            self.last_api_log_time = now

    # --------------------------------------------------------
    # Stop / mode switching
    # --------------------------------------------------------

    def stop_velocity(self, force: bool = False) -> None:
        if self.arm is None:
            return
        if self.fault_latched:
            self.currently_moving = False
            self.reset_smoothing()
            return
        if not self.currently_moving and not force:
            return

        try:
            if self.velocity_mode == 4:
                self.arm.vc_set_joint_velocity(
                    [0.0] * 6,
                    is_sync=True,
                    duration=self.joint_velocity_timeout,
                )
            elif self.velocity_mode == 5:
                self.arm.vc_set_cartesian_velocity(
                    [0.0] * 6,
                    is_tool_coord=False,
                    duration=self.velocity_timeout,
                )
        except Exception as exc:
            self.log(f"STOP error: {exc}")

        self.currently_moving = False
        self.last_motion_text = "STOP"
        self.reset_smoothing()

    def stop_command(self) -> None:
        """A button / GUI STOP. Keeps working during automatic drawing."""
        if self.arm is None:
            return

        if self.automation_active:
            self.log("STOP during automatic motion -> xArm stop state")
            self.automation_stop_requested = True
            self.manual_stop_latched = True
            try:
                self.arm.set_state(4)
            except Exception as exc:
                self.log(f"Automatic-motion STOP error: {exc}")
            self.set_status("STOPPED — press X / Recover to re-arm")
        else:
            self.stop_velocity(force=True)

        self.stop_latched = True
        self.currently_moving = False
        self.last_motion_text = "STOP"

    def switch_velocity_mode(self, new_mode: int) -> bool:
        if self.arm is None or self.fault_latched or self.automation_active:
            return False
        if self.velocity_mode == new_mode:
            return True

        self.stop_velocity(force=True)
        try:
            code = self.arm.set_mode(new_mode)
            if code != 0:
                self._throttled_api_log(f"Mode change error: {code}")
                return False
            code = self.arm.set_state(0)
            if code != 0:
                self._throttled_api_log(f"State change error: {code}")
                return False
            self.velocity_mode = new_mode
            self.reset_smoothing()
            time.sleep(0.05)
            return True
        except Exception as exc:
            self.log(f"Mode switch error: {exc}")
            return False

    def toggle_control_mode(self) -> None:
        if self.arm is None or self.fault_latched or self.automation_active:
            return

        self.stop_velocity(force=True)
        self.xyz_dpad_active = False

        if self.control_mode == "XYZ":
            if not self.switch_velocity_mode(4):
                return
            self.control_mode = "JOINT"
            self.log(f"MODE: JOINT — selected J{self.selected_joint}")
        else:
            if not self.switch_velocity_mode(5):
                return
            self.control_mode = "XYZ"
            self.log("MODE: XYZ")

        self.stop_latched = True

    def next_joint(self) -> None:
        if self.control_mode != "JOINT" or self.fault_latched or self.automation_active:
            return
        self.stop_velocity(force=True)
        self.selected_joint += 1
        if self.selected_joint > 4:
            self.selected_joint = 1
        self.stop_latched = True
        self.reset_smoothing()
        self.log(f"Selected joint: J{self.selected_joint}")

    # --------------------------------------------------------
    # Fault handling / recovery
    # --------------------------------------------------------

    def latch_motion_fault(self, api_code: int) -> None:
        if self.fault_latched or self.arm is None:
            return

        self.fault_latched = True
        self.currently_moving = False
        self.reset_smoothing()
        time.sleep(0.05)

        try:
            status = self.arm.get_err_warn_code()
            self.fault_error_code = int(self.arm.error_code)
            self.log("ROBOT MOTION FAULT")
            self.log(f"API return code: {api_code}")
            self.log(f"Error/warn: {status}")
            self.log(f"Controller error: {self.arm.error_code}")
            self.log(f"Controller warning: {self.arm.warn_code}")
            if self.fault_error_code == 22:
                self.log("SELF-COLLISION DETECTED")
                self.set_status("FAULT: SELF-COLLISION — center controls, press X / Recover")
            else:
                self.set_status(f"FAULT: xArm error {self.fault_error_code} — press X / Recover")
        except Exception as exc:
            self.log(f"Could not read robot error: {exc}")
            self.set_status("ROBOT FAULT — press X / Recover")

    def note_existing_error(self) -> None:
        if self.arm is None:
            return
        try:
            self.arm.get_err_warn_code()
            if int(self.arm.error_code) != 0:
                self.latch_motion_fault(1)
        except Exception:
            pass

    def recover(self) -> bool:
        if self.arm is None:
            return False
        if self.automation_active:
            self.set_status("Wait for automatic operation to stop first")
            return False

        self.log("Attempting robot recovery...")
        try:
            self.arm.clean_error()
            self.arm.clean_warn()
            time.sleep(0.2)
            self._check_code(self.arm.motion_enable(enable=True), "motion_enable")

            desired_mode = 4 if self.control_mode == "JOINT" else 5
            self._check_code(self.arm.set_mode(desired_mode), f"set_mode({desired_mode})")
            self._check_code(self.arm.set_state(0), "set_state(0)")
            self.arm.set_tcp_maxacc(self.tcp_max_acc)
            self.arm.set_joint_maxacc(self.joint_max_acc)
            time.sleep(0.2)

            self.arm.get_err_warn_code()
            if int(self.arm.error_code) != 0:
                self.log(f"Recovery failed: error {self.arm.error_code} remains")
                self.fault_error_code = int(self.arm.error_code)
                return False

            self.enabled = True
            self.velocity_mode = desired_mode
            self.xyz_dpad_active = False
            self.fault_latched = False
            self.fault_error_code = 0
            self.manual_stop_latched = False
            self.stop_latched = True
            self.currently_moving = False
            self.reset_smoothing()
            self.set_status("Robot recovered — center controls")
            self.log("Robot recovered.")
            return True
        except Exception as exc:
            self.log(f"Recovery error: {exc}")
            self.set_status("Recovery failed")
            return False

    # --------------------------------------------------------
    # Initial position
    # --------------------------------------------------------

    def move_initial_position(self) -> None:
        """Move to UFactory Studio Initial Position: J1..J6 = 0 degrees.

        This is called from an automation worker after begin_automation() has
        switched the robot to normal position-control mode. A / GUI STOP still
        works because automatic motion ownership remains active while waiting.
        """
        if self.arm is None or not self.connected:
            raise RuntimeError("Robot is not connected.")
        if not self.enabled:
            raise RuntimeError("Robot is disabled.")

        self.log("Moving to Initial Position: J1-J6 = 0°...")
        code = self.arm.set_servo_angle(
            angle=INITIAL_JOINTS,
            speed=INITIAL_JOINT_SPEED,
            wait=True,
            is_radian=False,
        )
        self._check_code(code, "move to Initial Position")
        self.log("Initial Position reached.")

    # --------------------------------------------------------
    # Automatic drawing/writing ownership
    # --------------------------------------------------------

    def begin_automation(self) -> None:
        if self.arm is None or not self.connected:
            raise RuntimeError("Robot is not connected.")
        if not self.enabled:
            raise RuntimeError("Robot is disabled.")
        if self.fault_latched:
            raise RuntimeError("Robot has an active fault. Recover it first.")

        self.stop_velocity(force=True)
        self.xyz_dpad_active = False
        self.automation_stop_requested = False
        self.stop_latched = True
        self.reset_smoothing()

        # Only mark automation active after the robot successfully enters
        # normal position-control mode.
        self._check_code(self.arm.set_mode(0), "set_mode(0)")
        self._check_code(self.arm.set_state(0), "set_state(0)")
        self.velocity_mode = 0
        self.automation_active = True

    def finish_automation(self) -> None:
        self.automation_active = False
        self.currently_moving = False
        self.reset_smoothing()

        if self.arm is None:
            return

        # If the user pressed STOP, deliberately leave the robot stopped until
        # X / Recover is pressed. This avoids an unexpected automatic resume.
        if self.automation_stop_requested or self.manual_stop_latched:
            self.set_status("Automatic motion stopped — press X / Recover")
            return

        try:
            self.arm.get_err_warn_code()
            if int(self.arm.error_code) != 0:
                self.latch_motion_fault(1)
                return
        except Exception:
            pass

        desired_mode = 4 if self.control_mode == "JOINT" else 5
        try:
            self._check_code(self.arm.set_mode(desired_mode), f"set_mode({desired_mode})")
            self._check_code(self.arm.set_state(0), "set_state(0)")
            self.arm.set_tcp_maxacc(self.tcp_max_acc)
            self.arm.set_joint_maxacc(self.joint_max_acc)
            self.velocity_mode = desired_mode
            self.stop_latched = True
            self.set_status("Ready")
        except Exception as exc:
            self.log(f"Could not restore controller mode: {exc}")
            self.note_existing_error()

    # --------------------------------------------------------
    # Center check
    # --------------------------------------------------------

    def controls_centered(self, controller) -> bool:
        try:
            sticks_ok = (
                abs(controller.get_axis(RIGHT_X)) < self.deadzone
                and abs(controller.get_axis(RIGHT_Y)) < self.deadzone
                and abs(controller.get_axis(LEFT_X)) < self.deadzone
                and abs(controller.get_axis(LEFT_Y)) < self.deadzone
            )
            if controller.get_numhats() > 0:
                dpad_ok = controller.get_hat(DPAD_HAT) == (0, 0)
            else:
                dpad_ok = True
            return sticks_ok and dpad_ok
        except pygame.error:
            return True

    # --------------------------------------------------------
    # Cartesian controller mode
    # --------------------------------------------------------

    def _xyz_targets(self, controller) -> Tuple[float, float, float]:
        right_x = apply_deadzone(controller.get_axis(RIGHT_X), self.deadzone)
        right_y = apply_deadzone(controller.get_axis(RIGHT_Y), self.deadzone)
        left_x = apply_deadzone(controller.get_axis(LEFT_X), self.deadzone)
        left_y = apply_deadzone(controller.get_axis(LEFT_Y), self.deadzone)

        x_component = right_y       # right stick up = X-

        # Y can be controlled from either stick's horizontal axis.
        # Use whichever stick is pushed farther so using both sticks does not
        # accidentally double the requested Y speed.
        y_component = left_x if abs(left_x) > abs(right_x) else right_x

        z_component = -left_y       # left stick up = Z+

        magnitude = math.sqrt(
            x_component * x_component
            + y_component * y_component
            + z_component * z_component
        )
        if magnitude > 1.0:
            x_component /= magnitude
            y_component /= magnitude
            z_component /= magnitude

        return (
            x_component * self.max_tcp_speed,
            y_component * self.max_tcp_speed,
            z_component * self.max_tcp_speed,
        )

    def update_cartesian(self, controller) -> None:
        if self.arm is None:
            return
        vx, vy, vz = self._xyz_targets(controller)

        if abs(vx) < 0.01 and abs(vy) < 0.01 and abs(vz) < 0.01:
            self.stop_velocity()
            return

        self.smoothed_vx += (vx - self.smoothed_vx) * self.velocity_smoothing
        self.smoothed_vy += (vy - self.smoothed_vy) * self.velocity_smoothing
        self.smoothed_vz += (vz - self.smoothed_vz) * self.velocity_smoothing

        code = self.arm.vc_set_cartesian_velocity(
            [self.smoothed_vx, self.smoothed_vy, self.smoothed_vz, 0.0, 0.0, 0.0],
            is_tool_coord=False,
            duration=self.velocity_timeout,
        )
        if code == 1:
            self.latch_motion_fault(code)
            return
        if code != 0:
            self._throttled_api_log(f"Cartesian velocity code: {code}")
            return

        self.currently_moving = True
        self.last_motion_text = (
            f"XYZ  X {self.smoothed_vx:+.1f}  Y {self.smoothed_vy:+.1f}  "
            f"Z {self.smoothed_vz:+.1f} mm/s"
        )
        self.last_speed_text = f"{math.sqrt(self.smoothed_vx**2 + self.smoothed_vy**2 + self.smoothed_vz**2):.1f} mm/s"

    def update_xyz_dpad(self, controller) -> bool:
        if self.arm is None or controller.get_numhats() == 0:
            return False

        dpad_x, dpad_y = controller.get_hat(DPAD_HAT)

        if dpad_x == 0 and dpad_y == 0:
            if self.xyz_dpad_active:
                self.stop_velocity(force=True)
                self.xyz_dpad_active = False
                self.switch_velocity_mode(5)
                self.stop_latched = True
                self.last_motion_text = "STOP"
                self.log("Back to Cartesian control")
                return True
            return False

        if not self.xyz_dpad_active:
            self.stop_velocity(force=True)
            if not self.switch_velocity_mode(4):
                return True
            self.xyz_dpad_active = True
            self.log("Temporary J5/J6 control")

        joint_speeds = [0.0, 0.0, 0.0, 0.0, dpad_y * self.j56_speed, dpad_x * self.j56_speed]
        code = self.arm.vc_set_joint_velocity(
            joint_speeds,
            is_sync=True,
            duration=self.joint_velocity_timeout,
        )
        if code == 1:
            self.latch_motion_fault(code)
        elif code != 0:
            self._throttled_api_log(f"J5/J6 velocity code: {code}")
        else:
            self.currently_moving = True
            self.last_motion_text = f"J5 {joint_speeds[4]:+.1f}  J6 {joint_speeds[5]:+.1f} deg/s"
            self.last_speed_text = f"{max(abs(joint_speeds[4]), abs(joint_speeds[5])):.1f} deg/s"
        return True

    # --------------------------------------------------------
    # Joint controller mode
    # --------------------------------------------------------

    def _joint_targets(self, controller) -> List[float]:
        right_x = apply_deadzone(controller.get_axis(RIGHT_X), self.deadzone)
        right_y = apply_deadzone(controller.get_axis(RIGHT_Y), self.deadzone)
        targets = [0.0] * 6

        if self.selected_joint == 1:
            targets[0] = right_x * self.max_joint_speed
        elif self.selected_joint == 2:
            # User-tested inversion: J2 is opposite J3.
            # Up -> J2+, Down -> J2-
            targets[1] = -right_y * self.max_joint_speed
        elif self.selected_joint == 3:
            # Up -> J3-, Down -> J3+
            targets[2] = right_y * self.max_joint_speed
        elif self.selected_joint == 4:
            targets[3] = right_x * self.max_joint_speed

        if controller.get_numhats() > 0:
            dpad_x, dpad_y = controller.get_hat(DPAD_HAT)
            targets[4] = dpad_y * self.j56_speed
            targets[5] = dpad_x * self.j56_speed
        return targets

    def update_joint_mode(self, controller) -> None:
        if self.arm is None:
            return

        targets = self._joint_targets(controller)
        for i in range(4):
            self.smoothed_joint[i] += (
                targets[i] - self.smoothed_joint[i]
            ) * self.joint_smoothing
        # D-pad is digital: stop J5/J6 immediately on release.
        self.smoothed_joint[4] = targets[4]
        self.smoothed_joint[5] = targets[5]

        if not any(abs(value) > 0.01 for value in self.smoothed_joint):
            self.stop_velocity()
            return

        code = self.arm.vc_set_joint_velocity(
            self.smoothed_joint,
            is_sync=True,
            duration=self.joint_velocity_timeout,
        )
        if code == 1:
            self.latch_motion_fault(code)
            return
        if code != 0:
            self._throttled_api_log(f"Joint velocity code: {code}")
            return

        self.currently_moving = True
        active = [
            f"J{i+1} {speed:+.1f}"
            for i, speed in enumerate(self.smoothed_joint)
            if abs(speed) > 0.05
        ]
        self.last_motion_text = "  ".join(active) + " deg/s"
        self.last_speed_text = f"{max(abs(v) for v in self.smoothed_joint):.1f} deg/s"

    # --------------------------------------------------------
    # G2 gripper
    # --------------------------------------------------------

    def update_gripper(self, controller, dt: float) -> None:
        if self.arm is None or self.automation_active or self.fault_latched:
            return

        l2 = trigger_amount(controller.get_axis(L2_AXIS))
        r2 = trigger_amount(controller.get_axis(R2_AXIS))
        gripper_velocity = (l2 - r2) * self.gripper_rate
        if abs(gripper_velocity) < 0.01:
            return

        self.gripper_target += gripper_velocity * dt
        self.gripper_target = max(GRIPPER_MIN, min(GRIPPER_MAX, self.gripper_target))

        now = time.monotonic()
        if now - self.last_gripper_send_time < GRIPPER_SEND_INTERVAL:
            return
        if abs(self.gripper_target - self.last_gripper_sent) < 1.0:
            return

        target = int(round(self.gripper_target))
        try:
            code = self.arm.set_gripper_g2_position(
                target,
                speed=int(self.gripper_speed),
                force=int(self.gripper_force),
                wait=False,
            )
            if code == 0:
                self.last_gripper_sent = self.gripper_target
            else:
                self._throttled_api_log(f"G2 command code: {code}")
        except Exception as exc:
            self._throttled_api_log(f"G2 error: {exc}")
        self.last_gripper_send_time = now

    def set_gripper_position(self, position_mm: float) -> None:
        if self.arm is None or not self.enabled or self.automation_active:
            return
        position_mm = max(GRIPPER_MIN, min(GRIPPER_MAX, position_mm))
        code = self.arm.set_gripper_g2_position(
            int(round(position_mm)),
            speed=int(self.gripper_speed),
            force=int(self.gripper_force),
            wait=False,
        )
        if code == 0:
            self.gripper_target = position_mm
            self.last_gripper_sent = position_mm
        else:
            self.log(f"G2 command code: {code}")


# ============================================================
# COMBINED TKINTER APP
# ============================================================

class XArmCombinedApp(tk.Tk):
    SETTINGS_FILE = "xarm_combined_settings.json"

    def __init__(self):
        super().__init__()

        self.title("xArm 850 Controller + SVG / Text Wall Drawer")
        self.geometry("1080x900")
        self.minsize(920, 760)

        self.worker: Optional[threading.Thread] = None
        self.closing = False

        self.controller = None
        self.controller_connected = False
        self.controller_name = ""
        self.previous_buttons: Dict[int, bool] = {}
        self.last_controller_scan = 0.0
        self.last_loop_time = time.monotonic()

        self._build_variables()
        self.core = XArmControlCore(self._log, self._set_status_threadsafe)
        self._build_ui()
        self._load_settings()
        self._apply_controller_settings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._init_pygame()
        self._find_controller()
        self.after(LOOP_INTERVAL_MS, self._controller_tick)
        self.after(100, self._refresh_live_labels)

        self._log("Combined xArm app ready.")
        self._log(f"Current contact X offset: {self.offset_var.get():.1f} mm")

    # --------------------------------------------------------
    # Variables
    # --------------------------------------------------------

    def _build_variables(self) -> None:
        # Shared robot / status
        self.ip_var = tk.StringVar(value=ROBOT_IP)
        self.status_var = tk.StringVar(value="Ready")
        self.robot_state_var = tk.StringVar(value="Disconnected")
        self.controller_state_var = tk.StringVar(value="Disconnected")
        self.mode_var = tk.StringVar(value="XYZ")
        self.joint_var = tk.StringVar(value="J1")
        self.motion_var = tk.StringVar(value="STOP")
        self.live_speed_var = tk.StringVar(value="0")
        self.error_var = tk.StringVar(value="None")
        self.gripper_pos_var = tk.StringVar(value="84 mm")

        # Controller settings
        self.deadzone_var = tk.DoubleVar(value=STICK_DEADZONE)
        self.max_tcp_speed_var = tk.DoubleVar(value=MAX_TCP_SPEED)
        self.tcp_acc_var = tk.DoubleVar(value=TCP_MAX_ACC)
        self.smoothing_var = tk.DoubleVar(value=VELOCITY_SMOOTHING)
        self.joint_speed_var = tk.DoubleVar(value=MAX_JOINT_SPEED)
        self.j56_speed_var = tk.DoubleVar(value=J56_SPEED)
        self.joint_acc_var = tk.DoubleVar(value=JOINT_MAX_ACC)
        self.gripper_rate_var = tk.DoubleVar(value=GRIPPER_RATE)
        self.gripper_speed_var = tk.IntVar(value=GRIPPER_SPEED)
        self.gripper_force_var = tk.IntVar(value=GRIPPER_FORCE)

        # Wall drawer settings from the existing app.
        self.offset_var = tk.DoubleVar(value=CONTACT_X_OFFSET_MM)
        self.write_text_var = tk.BooleanVar(value=True)
        self.text_var = tk.StringVar(value="HELLO NARVA!")
        self.text_left_var = tk.DoubleVar(value=HEADING_LEFT_MM)
        self.text_top_var = tk.DoubleVar(value=HEADING_TOP_MM)
        self.text_height_var = tk.DoubleVar(value=HEADING_HEIGHT_MM)
        self.text_speed_var = tk.DoubleVar(value=HEADING_SPEED)

        self.draw_svg_var = tk.BooleanVar(value=True)
        default_svg = str((Path(__file__).resolve().parent / SVG_FILE).resolve())
        self.svg_var = tk.StringVar(value=default_svg)
        self.svg_top_var = tk.DoubleVar(value=SVG_TOP_MARGIN_MM)
        self.svg_width_var = tk.DoubleVar(value=MAX_DRAWING_WIDTH_MM)
        self.svg_height_var = tk.DoubleVar(value=MAX_DRAWING_HEIGHT_MM)
        self.draw_speed_var = tk.DoubleVar(value=DRAW_SPEED)
        self.move_ready_var = tk.BooleanVar(value=True)

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        outer.rowconfigure(1, weight=0)

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.controller_tab = ttk.Frame(self.notebook, padding=10)
        self.drawer_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.controller_tab, text="Controller")
        self.notebook.add(self.drawer_tab, text="Draw / Write")

        self._build_controller_tab()
        self._build_drawer_tab()

        # Shared log/status area
        log_box = ttk.LabelFrame(outer, text="Status / Log", padding=8)
        log_box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        log_box.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_box, height=9, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)
        ttk.Label(log_box, textvariable=self.status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )

    def _build_controller_tab(self) -> None:
        tab = self.controller_tab
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

        # Robot connection
        robot = ttk.LabelFrame(tab, text="Robot", padding=10)
        robot.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        robot.columnconfigure(1, weight=1)

        ttk.Label(robot, text="Robot IP").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(robot, textvariable=self.ip_var, width=22).grid(row=0, column=1, sticky="ew")
        ttk.Button(robot, text="Connect + Enable", command=self._connect_robot).grid(
            row=0, column=2, padx=(8, 3)
        )
        ttk.Button(robot, text="Enable", command=self._enable_robot).grid(row=0, column=3, padx=3)
        ttk.Button(robot, text="Disable", command=self._disable_robot).grid(row=0, column=4, padx=3)

        ttk.Label(robot, text="Robot:").grid(row=1, column=0, sticky="w", pady=(7, 0))
        ttk.Label(robot, textvariable=self.robot_state_var).grid(
            row=1, column=1, columnspan=4, sticky="w", pady=(7, 0)
        )

        # Live controller status
        live = ttk.LabelFrame(tab, text="Live controller status", padding=10)
        live.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(0, 8))
        live.columnconfigure(1, weight=1)

        rows = [
            ("Controller", self.controller_state_var),
            ("Mode", self.mode_var),
            ("Selected joint", self.joint_var),
            ("Movement", self.motion_var),
            ("Speed", self.live_speed_var),
            ("G2 target", self.gripper_pos_var),
            ("Error", self.error_var),
        ]
        for row, (label, variable) in enumerate(rows):
            ttk.Label(live, text=f"{label}:").grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=2)
            ttk.Label(live, textvariable=variable, wraplength=360).grid(row=row, column=1, sticky="w", pady=2)

        # Safety/action buttons
        safety = ttk.LabelFrame(tab, text="Safety / actions", padding=10)
        safety.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(0, 8))
        safety.columnconfigure(0, weight=1)

        self.stop_btn = ttk.Button(safety, text="STOP  (A)", command=self._stop_robot)
        self.stop_btn.grid(row=0, column=0, sticky="ew", pady=3, ipady=10)
        self.recover_btn = ttk.Button(safety, text="Recover / Re-arm  (X)", command=self._recover_robot)
        self.recover_btn.grid(row=1, column=0, sticky="ew", pady=3, ipady=5)
        self.initial_btn = ttk.Button(
            safety,
            text="Initial Position  (R3)",
            command=self._move_initial_position,
        )
        self.initial_btn.grid(row=2, column=0, sticky="ew", pady=3, ipady=5)
        ttk.Button(safety, text="Open G2 fully", command=lambda: self._set_gripper_gui(GRIPPER_MAX)).grid(
            row=3, column=0, sticky="ew", pady=3
        )
        ttk.Button(safety, text="Close G2 fully", command=lambda: self._set_gripper_gui(GRIPPER_MIN)).grid(
            row=4, column=0, sticky="ew", pady=3
        )
        ttk.Button(safety, text="Disable + Exit  (B)", command=self._on_close).grid(
            row=5, column=0, sticky="ew", pady=(12, 3)
        )

        # Movement settings
        settings = ttk.LabelFrame(tab, text="Controller settings", padding=10)
        settings.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        for col in range(4):
            settings.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        setting_rows = [
            ("Stick deadzone", self.deadzone_var, 0.05, 0.50, 0.01, "Max TCP speed (mm/s)", self.max_tcp_speed_var, 10, 300, 5),
            ("TCP acceleration", self.tcp_acc_var, 50, 3000, 50, "Velocity smoothing", self.smoothing_var, 0.05, 1.0, 0.05),
            ("J1-J4 speed (deg/s)", self.joint_speed_var, 1, 100, 1, "J5/J6 speed (deg/s)", self.j56_speed_var, 1, 100, 1),
            ("Joint acceleration", self.joint_acc_var, 10, 1000, 10, "G2 trigger rate (mm/s)", self.gripper_rate_var, 5, 150, 5),
            ("G2 speed", self.gripper_speed_var, 15, 225, 5, "G2 force", self.gripper_force_var, 1, 100, 1),
        ]

        for row, data in enumerate(setting_rows):
            l1, v1, f1, t1, i1, l2, v2, f2, t2, i2 = data
            ttk.Label(settings, text=l1).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            ttk.Spinbox(settings, from_=f1, to=t1, increment=i1, textvariable=v1, width=10).grid(
                row=row, column=1, sticky="w", padx=(0, 16), pady=3
            )
            ttk.Label(settings, text=l2).grid(row=row, column=2, sticky="w", padx=(0, 6), pady=3)
            ttk.Spinbox(settings, from_=f2, to=t2, increment=i2, textvariable=v2, width=10).grid(
                row=row, column=3, sticky="w", pady=3
            )

        ttk.Button(settings, text="Apply controller settings", command=self._apply_controller_settings).grid(
            row=len(setting_rows), column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )

        # Mapping
        mapping = ttk.LabelFrame(tab, text="Controller mapping", padding=10)
        mapping.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Label(
            mapping,
            justify="left",
            text=(
                "XYZ mode:  Right stick = X/Y; left stick = Y/Z (left/right = Y, up/down = Z).  "
                "True multi-axis movement works.\n"
                "JOINT mode: R1 toggles XYZ/JOINT; L1 cycles J1-J4.  J1/J4 use right stick left/right; "
                "J2/J3 use up/down.\n"
                "J2 is inverted: stick up = J2+, down = J2-.  D-pad always controls J5 (up/down) and J6 (left/right).\n"
                "L2 opens G2, R2 closes G2.  A = STOP, X = Recover, R3 = Initial Position, "
                "B = Disable + Exit."
            ),
            wraplength=960,
        ).pack(anchor="w")

    def _build_drawer_tab(self) -> None:
        root = self.drawer_tab
        root.columnconfigure(0, weight=1)

        robot = ttk.LabelFrame(root, text="Wall / pen contact", padding=10)
        robot.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        robot.columnconfigure(1, weight=1)

        ttk.Label(robot, text="Contact X offset (mm)").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        offset_frame = ttk.Frame(robot)
        offset_frame.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Spinbox(
            offset_frame, from_=-20.0, to=5.0, increment=0.1,
            textvariable=self.offset_var, width=10,
        ).pack(side="left")
        ttk.Button(offset_frame, text="-0.5", width=7, command=lambda: self._nudge_offset(-0.5)).pack(
            side="left", padx=(8, 3)
        )
        ttk.Button(offset_frame, text="+0.5", width=7, command=lambda: self._nudge_offset(0.5)).pack(
            side="left", padx=3
        )
        ttk.Label(
            robot,
            text="More negative = farther toward the paper / more marker pressure.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # Text
        text_box = ttk.LabelFrame(root, text="Text", padding=10)
        text_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        text_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(text_box, text="Write text before SVG", variable=self.write_text_var).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5)
        )
        ttk.Label(text_box, text="Text").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(text_box, textvariable=self.text_var).grid(row=1, column=1, columnspan=3, sticky="ew", pady=4)
        ttk.Label(text_box, text="Left (mm)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(text_box, from_=0, to=PAPER_WIDTH_MM, increment=1, textvariable=self.text_left_var, width=9).grid(
            row=2, column=1, sticky="w", padx=(0, 12)
        )
        ttk.Label(text_box, text="Top (mm)").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(text_box, from_=0, to=PAPER_HEIGHT_MM, increment=1, textvariable=self.text_top_var, width=9).grid(
            row=2, column=3, sticky="w"
        )
        ttk.Label(text_box, text="Height (mm)").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(text_box, from_=5, to=60, increment=1, textvariable=self.text_height_var, width=9).grid(
            row=3, column=1, sticky="w", padx=(0, 12)
        )
        ttk.Label(text_box, text="Speed (mm/s)").grid(row=3, column=2, sticky="w")
        ttk.Spinbox(text_box, from_=5, to=300, increment=5, textvariable=self.text_speed_var, width=9).grid(
            row=3, column=3, sticky="w"
        )
        ttk.Label(
            text_box,
            text="Supported: A-Z, Ä Ö Ü Õ, space, ! ? .  Lowercase becomes uppercase.",
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(5, 0))

        # SVG
        svg_box = ttk.LabelFrame(root, text="SVG drawing", padding=10)
        svg_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        svg_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(svg_box, text="Draw SVG", variable=self.draw_svg_var).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5)
        )
        ttk.Label(svg_box, text="SVG file").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(svg_box, textvariable=self.svg_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Button(svg_box, text="Browse…", command=self._browse_svg).grid(row=1, column=3, padx=(8, 0), pady=4)
        ttk.Label(svg_box, text="Top margin (mm)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(svg_box, from_=0, to=PAPER_HEIGHT_MM, increment=1, textvariable=self.svg_top_var, width=9).grid(
            row=2, column=1, sticky="w", padx=(0, 12)
        )
        ttk.Label(svg_box, text="Draw speed (mm/s)").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(svg_box, from_=5, to=500, increment=5, textvariable=self.draw_speed_var, width=9).grid(
            row=2, column=3, sticky="w"
        )
        ttk.Label(svg_box, text="Max width (mm)").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(svg_box, from_=20, to=PAPER_WIDTH_MM, increment=5, textvariable=self.svg_width_var, width=9).grid(
            row=3, column=1, sticky="w", padx=(0, 12)
        )
        ttk.Label(svg_box, text="Max height (mm)").grid(row=3, column=2, sticky="w")
        ttk.Spinbox(svg_box, from_=20, to=PAPER_HEIGHT_MM, increment=5, textvariable=self.svg_height_var, width=9).grid(
            row=3, column=3, sticky="w"
        )

        # Run controls
        controls = ttk.LabelFrame(root, text="Run", padding=10)
        controls.grid(row=3, column=0, sticky="ew")
        ttk.Checkbutton(controls, text="Move to ready pose first", variable=self.move_ready_var).pack(
            side="left", padx=(0, 12)
        )
        self.ready_btn = ttk.Button(controls, text="Move Ready", command=self._move_ready)
        self.ready_btn.pack(side="left", padx=4)
        self.preflight_btn = ttk.Button(controls, text="Preflight (pen away)", command=self._preflight)
        self.preflight_btn.pack(side="left", padx=4)
        self.draw_btn = ttk.Button(controls, text="Start drawing / writing", command=self._draw)
        self.draw_btn.pack(side="left", padx=4)
        ttk.Label(
            root,
            text=(
                "Controller movement is locked while an automatic wall operation runs. "
                "A / GUI STOP remains active and puts the xArm into stop state; use X / Recover afterwards."
            ),
            wraplength=900,
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

    # --------------------------------------------------------
    # Logging / status
    # --------------------------------------------------------

    def _log(self, message: str) -> None:
        if not hasattr(self, "log_text"):
            return
        def append() -> None:
            if self.closing:
                return
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message.rstrip() + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        try:
            self.after(0, append)
        except tk.TclError:
            pass

    def _set_status_threadsafe(self, message: str) -> None:
        try:
            self.after(0, lambda: self.status_var.set(message) if not self.closing else None)
        except tk.TclError:
            pass

    # --------------------------------------------------------
    # Settings persistence
    # --------------------------------------------------------

    def _settings_path(self) -> Path:
        return Path(__file__).resolve().with_name(self.SETTINGS_FILE)

    def _load_settings(self) -> None:
        path = self._settings_path()
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._log(f"Could not load settings: {exc}")
            return

        mapping = {
            "ip": self.ip_var,
            "deadzone": self.deadzone_var,
            "max_tcp_speed": self.max_tcp_speed_var,
            "tcp_acc": self.tcp_acc_var,
            "smoothing": self.smoothing_var,
            "joint_speed": self.joint_speed_var,
            "j56_speed": self.j56_speed_var,
            "joint_acc": self.joint_acc_var,
            "gripper_rate": self.gripper_rate_var,
            "gripper_speed": self.gripper_speed_var,
            "gripper_force": self.gripper_force_var,
            "contact_offset": self.offset_var,
            "write_text": self.write_text_var,
            "text": self.text_var,
            "text_left": self.text_left_var,
            "text_top": self.text_top_var,
            "text_height": self.text_height_var,
            "text_speed": self.text_speed_var,
            "draw_svg": self.draw_svg_var,
            "svg_file": self.svg_var,
            "svg_top": self.svg_top_var,
            "svg_width": self.svg_width_var,
            "svg_height": self.svg_height_var,
            "draw_speed": self.draw_speed_var,
            "move_ready": self.move_ready_var,
        }
        for key, variable in mapping.items():
            if key in data:
                try:
                    variable.set(data[key])
                except Exception:
                    pass

    def _save_settings(self) -> None:
        data = {
            "ip": self.ip_var.get().strip(),
            "deadzone": self.deadzone_var.get(),
            "max_tcp_speed": self.max_tcp_speed_var.get(),
            "tcp_acc": self.tcp_acc_var.get(),
            "smoothing": self.smoothing_var.get(),
            "joint_speed": self.joint_speed_var.get(),
            "j56_speed": self.j56_speed_var.get(),
            "joint_acc": self.joint_acc_var.get(),
            "gripper_rate": self.gripper_rate_var.get(),
            "gripper_speed": self.gripper_speed_var.get(),
            "gripper_force": self.gripper_force_var.get(),
            "contact_offset": self.offset_var.get(),
            "write_text": self.write_text_var.get(),
            "text": self.text_var.get(),
            "text_left": self.text_left_var.get(),
            "text_top": self.text_top_var.get(),
            "text_height": self.text_height_var.get(),
            "text_speed": self.text_speed_var.get(),
            "draw_svg": self.draw_svg_var.get(),
            "svg_file": self.svg_var.get(),
            "svg_top": self.svg_top_var.get(),
            "svg_width": self.svg_width_var.get(),
            "svg_height": self.svg_height_var.get(),
            "draw_speed": self.draw_speed_var.get(),
            "move_ready": self.move_ready_var.get(),
        }
        try:
            self._settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            self._log(f"Could not save settings: {exc}")

    # --------------------------------------------------------
    # Controller settings / robot buttons
    # --------------------------------------------------------

    def _apply_controller_settings(self) -> None:
        try:
            self.core.deadzone = float(self.deadzone_var.get())
            self.core.max_tcp_speed = float(self.max_tcp_speed_var.get())
            self.core.tcp_max_acc = float(self.tcp_acc_var.get())
            self.core.velocity_smoothing = float(self.smoothing_var.get())
            self.core.max_joint_speed = float(self.joint_speed_var.get())
            self.core.j56_speed = float(self.j56_speed_var.get())
            self.core.joint_max_acc = float(self.joint_acc_var.get())
            self.core.gripper_rate = float(self.gripper_rate_var.get())
            self.core.gripper_speed = int(self.gripper_speed_var.get())
            self.core.gripper_force = int(self.gripper_force_var.get())

            if self.core.arm is not None and self.core.enabled and not self.core.automation_active:
                self.core.arm.set_tcp_maxacc(self.core.tcp_max_acc)
                self.core.arm.set_joint_maxacc(self.core.joint_max_acc)
            self._save_settings()
            if hasattr(self, "log_text"):
                self._log("Controller settings applied.")
        except Exception as exc:
            if hasattr(self, "log_text"):
                messagebox.showerror("Invalid controller settings", str(exc))

    def _connect_robot(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showwarning("Robot busy", "Wait for the current robot operation to finish.")
            return
        try:
            self._apply_controller_settings()
            self.core.connect(self.ip_var.get().strip())
            self.robot_state_var.set("Connected + enabled")
        except Exception as exc:
            self.robot_state_var.set("Connection failed")
            self._log(traceback.format_exc())
            messagebox.showerror("Connection error", str(exc))

    def _enable_robot(self) -> None:
        try:
            if not self.core.connected:
                self._connect_robot()
                return
            self._apply_controller_settings()
            self.core.enable_for_controller()
            self.robot_state_var.set("Enabled")
        except Exception as exc:
            messagebox.showerror("Enable error", str(exc))

    def _disable_robot(self) -> None:
        self.core.disable()
        self.robot_state_var.set("Disabled")

    def _stop_robot(self) -> None:
        self.core.stop_command()

    def _recover_robot(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.status_var.set("Wait for automatic operation to stop before recovery")
            return
        if self.controller_connected and self.controller is not None:
            if not self.core.controls_centered(self.controller):
                self.status_var.set("Center sticks / D-pad before recovery")
                return
        if self.core.recover():
            self.robot_state_var.set("Enabled")

    def _set_gripper_gui(self, value: float) -> None:
        try:
            self._apply_controller_settings()
            self.core.set_gripper_position(value)
        except Exception as exc:
            messagebox.showerror("G2 error", str(exc))

    # --------------------------------------------------------
    # Pygame controller lifecycle
    # --------------------------------------------------------

    def _init_pygame(self) -> None:
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
        except pygame.error as exc:
            self._log(f"pygame init error: {exc}")

    def _find_controller(self) -> None:
        try:
            self._init_pygame()
            pygame.event.pump()
            if pygame.joystick.get_count() == 0:
                self.controller = None
                self.controller_connected = False
                self.controller_state_var.set("Disconnected")
                return

            controller = pygame.joystick.Joystick(0)
            controller.init()
            self.controller = controller
            self.controller_connected = True
            self.controller_name = controller.get_name()
            self.previous_buttons.clear()
            self.core.stop_latched = True
            self.controller_state_var.set(self.controller_name)
            self._log(f"Controller connected: {self.controller_name}")
        except pygame.error as exc:
            self.controller = None
            self.controller_connected = False
            self.controller_state_var.set("Controller error")
            self._log(f"Controller init error: {exc}")

    def _controller_attached(self) -> bool:
        if self.controller is None:
            return False
        try:
            if hasattr(self.controller, "get_attached"):
                return bool(self.controller.get_attached())
            self.controller.get_axis(RIGHT_X)
            return True
        except pygame.error:
            return False

    def _handle_controller_disconnect(self) -> None:
        if self.controller_connected:
            self._log("Controller disconnected.")
        if not self.core.automation_active:
            self.core.stop_velocity(force=True)
        self.core.stop_latched = True
        self.controller = None
        self.controller_connected = False
        self.controller_name = ""
        self.previous_buttons.clear()
        self.controller_state_var.set("Disconnected")

    # --------------------------------------------------------
    # Controller polling
    # --------------------------------------------------------

    def _controller_tick(self) -> None:
        if self.closing:
            return

        now = time.monotonic()

        if not self.controller_connected:
            if now - self.last_controller_scan >= 1.0:
                self.last_controller_scan = now
                self._find_controller()
            self.last_loop_time = now
            self.after(LOOP_INTERVAL_MS, self._controller_tick)
            return

        if not self._controller_attached():
            self._handle_controller_disconnect()
            self.last_loop_time = now
            self.after(LOOP_INTERVAL_MS, self._controller_tick)
            return

        try:
            pygame.event.pump()
            controller = self.controller
            assert controller is not None

            dt = max(0.0, min(0.2, now - self.last_loop_time))
            self.last_loop_time = now

            a = bool(controller.get_button(BUTTON_A))
            b = bool(controller.get_button(BUTTON_B))
            x = bool(controller.get_button(BUTTON_X))
            l1 = bool(controller.get_button(BUTTON_L1))
            r1 = bool(controller.get_button(BUTTON_R1))
            r3 = bool(controller.get_button(BUTTON_R3))

            if a and not self.previous_buttons.get(BUTTON_A, False):
                self.core.stop_command()
            if b and not self.previous_buttons.get(BUTTON_B, False):
                self._on_close()
                return
            if x and not self.previous_buttons.get(BUTTON_X, False):
                self._recover_robot()
            if r1 and not self.previous_buttons.get(BUTTON_R1, False):
                self.core.toggle_control_mode()
            if l1 and not self.previous_buttons.get(BUTTON_L1, False):
                self.core.next_joint()
            if r3 and not self.previous_buttons.get(BUTTON_R3, False):
                if not self.core.automation_active:
                    self._move_initial_position()

            self.previous_buttons[BUTTON_A] = a
            self.previous_buttons[BUTTON_B] = b
            self.previous_buttons[BUTTON_X] = x
            self.previous_buttons[BUTTON_L1] = l1
            self.previous_buttons[BUTTON_R1] = r1
            self.previous_buttons[BUTTON_R3] = r3

            # Controller gripper stays disabled during automatic wall operations.
            if self.core.connected and self.core.enabled:
                self.core.update_gripper(controller, dt)

            # A/B/X are intentionally handled even during automatic motion.
            if self.core.automation_active or self.core.fault_latched:
                self.after(LOOP_INTERVAL_MS, self._controller_tick)
                return

            if not self.core.connected or not self.core.enabled:
                self.after(LOOP_INTERVAL_MS, self._controller_tick)
                return

            if self.core.stop_latched:
                if self.core.controls_centered(controller):
                    self.core.stop_latched = False
                else:
                    self.after(LOOP_INTERVAL_MS, self._controller_tick)
                    return

            if self.core.control_mode == "XYZ":
                if self.core.update_xyz_dpad(controller):
                    self.after(LOOP_INTERVAL_MS, self._controller_tick)
                    return
                if self.core.velocity_mode != 5 and not self.core.switch_velocity_mode(5):
                    self.after(LOOP_INTERVAL_MS, self._controller_tick)
                    return
                self.core.update_cartesian(controller)
            else:
                if self.core.velocity_mode != 4 and not self.core.switch_velocity_mode(4):
                    self.after(LOOP_INTERVAL_MS, self._controller_tick)
                    return
                self.core.update_joint_mode(controller)

        except pygame.error:
            self._handle_controller_disconnect()
        except Exception as exc:
            self._log(f"Controller loop error: {exc}")
            self._log(traceback.format_exc())

        self.after(LOOP_INTERVAL_MS, self._controller_tick)

    def _refresh_live_labels(self) -> None:
        if self.closing:
            return
        self.mode_var.set(self.core.control_mode)
        self.joint_var.set(f"J{self.core.selected_joint}")
        self.motion_var.set(self.core.last_motion_text)
        self.live_speed_var.set(self.core.last_speed_text)
        self.gripper_pos_var.set(f"{self.core.gripper_target:.0f} mm")

        if self.core.fault_latched:
            self.error_var.set(
                "SELF-COLLISION (22)" if self.core.fault_error_code == 22
                else f"xArm error {self.core.fault_error_code}"
            )
        elif self.core.manual_stop_latched:
            self.error_var.set("Stopped — Recover required")
        else:
            self.error_var.set("None")

        if self.core.connected:
            if self.core.manual_stop_latched:
                state = "Stopped — Recover required"
            elif self.core.fault_latched:
                state = "Fault"
            else:
                state = "Enabled" if self.core.enabled else "Disabled"
                if self.core.automation_active:
                    state += " — automatic motion"
            self.robot_state_var.set(state)
        else:
            self.robot_state_var.set("Disconnected")

        self.after(100, self._refresh_live_labels)

    # --------------------------------------------------------
    # Drawer settings / helpers
    # --------------------------------------------------------

    def _browse_svg(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose SVG file",
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")],
        )
        if filename:
            self.svg_var.set(filename)

    def _nudge_offset(self, amount: float) -> None:
        self.offset_var.set(round(float(self.offset_var.get()) + amount, 2))

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (self.ready_btn, self.preflight_btn, self.draw_btn, self.initial_btn):
            button.configure(state=state)

    def _show_error(self, title: str, message: str) -> None:
        try:
            self.after(0, lambda: messagebox.showerror(title, message) if not self.closing else None)
        except tk.TclError:
            pass

    def _apply_drawer_settings(self, require_content: bool = True) -> dict:
        global ROBOT_IP
        global CONTACT_X_OFFSET_MM
        global HEADING_TEXT, HEADING_LEFT_MM, HEADING_TOP_MM
        global HEADING_HEIGHT_MM, HEADING_WIDTH_MM, HEADING_GAP_MM
        global HEADING_SPACE_MM, HEADING_SPEED
        global SVG_TOP_MARGIN_MM
        global MAX_DRAWING_WIDTH_MM, MAX_DRAWING_HEIGHT_MM
        global DRAW_SPEED

        ROBOT_IP = self.ip_var.get().strip()
        if not ROBOT_IP:
            raise ValueError("Robot IP cannot be empty.")

        CONTACT_X_OFFSET_MM = float(self.offset_var.get())
        text_enabled = bool(self.write_text_var.get())
        svg_enabled = bool(self.draw_svg_var.get())

        if require_content and not text_enabled and not svg_enabled:
            raise ValueError("Enable text, SVG, or both.")

        HEADING_TEXT = self.text_var.get()
        HEADING_LEFT_MM = float(self.text_left_var.get())
        HEADING_TOP_MM = float(self.text_top_var.get())
        HEADING_HEIGHT_MM = float(self.text_height_var.get())
        HEADING_WIDTH_MM = HEADING_HEIGHT_MM * (10.0 / 18.0)
        HEADING_GAP_MM = HEADING_HEIGHT_MM * (3.5 / 18.0)
        HEADING_SPACE_MM = HEADING_HEIGHT_MM * (8.0 / 18.0)
        HEADING_SPEED = float(self.text_speed_var.get())

        if require_content and text_enabled and not HEADING_TEXT.strip():
            raise ValueError("Text is enabled, but the text box is empty.")

        SVG_TOP_MARGIN_MM = float(self.svg_top_var.get())
        MAX_DRAWING_WIDTH_MM = float(self.svg_width_var.get())
        MAX_DRAWING_HEIGHT_MM = float(self.svg_height_var.get())
        DRAW_SPEED = float(self.draw_speed_var.get())

        svg_path = self.svg_var.get().strip()
        if require_content and svg_enabled:
            if not svg_path:
                raise ValueError("SVG drawing is enabled, but no SVG file is selected.")
            if not Path(svg_path).is_file():
                raise ValueError(f"SVG file does not exist:\n{svg_path}")

        self._save_settings()
        return {
            "text_enabled": text_enabled,
            "svg_enabled": svg_enabled,
            "svg_path": svg_path if svg_enabled else "",
            "text": HEADING_TEXT,
            "move_ready": bool(self.move_ready_var.get()),
        }

    def _make_drawer(self, config: dict) -> XArmSVGDrawer:
        settings = XArmSVGSettings(
            svg_file=config["svg_path"],
            max_width_mm=MAX_DRAWING_WIDTH_MM,
            max_height_mm=MAX_DRAWING_HEIGHT_MM,
            min_path_length_mm=MIN_PATH_LENGTH_MM,
            simplify_tolerance_mm=SIMPLIFY_TOLERANCE_MM,
        )
        return XArmSVGDrawer(settings, arm=self.core.arm)

    # --------------------------------------------------------
    # Worker handling
    # --------------------------------------------------------

    def _ensure_connected_for_worker(self) -> None:
        if not self.core.connected:
            self._connect_robot()
        if not self.core.connected or self.core.arm is None:
            raise RuntimeError("Robot is not connected.")
        if not self.core.enabled:
            self.core.enable_for_controller()

    def _start_worker(
        self,
        label: str,
        func,
        require_content: bool = True,
        log_drawer_context: bool = True,
    ) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showwarning("Robot busy", "A robot operation is already running.")
            return

        try:
            config = self._apply_drawer_settings(require_content=require_content)
            self._apply_controller_settings()
            self._ensure_connected_for_worker()
            self.core.begin_automation()
        except Exception as exc:
            messagebox.showerror("Cannot start robot operation", str(exc))
            return

        self._set_busy(True)
        self.status_var.set(label)
        self._log("")
        self._log(f"--- {label} ---")
        if log_drawer_context:
            self._log(
                f"X offset: {CONTACT_X_OFFSET_MM:.2f} mm | "
                f"Text: {config['text_enabled']} | SVG: {config['svg_enabled']}"
            )

        def worker() -> None:
            success = False
            try:
                func(config)
                success = True
                self._log(f"{label}: finished.")
            except Exception as exc:
                self._log(f"ERROR: {exc}")
                self._log(traceback.format_exc())
                self.core.note_existing_error()
                if not self.core.automation_stop_requested:
                    self._show_error("Robot operation failed", str(exc))
            finally:
                self.core.finish_automation()
                try:
                    self.after(0, lambda: self.status_var.set("Ready" if success else self.status_var.get()))
                    self.after(0, lambda: self._set_busy(False))
                except tk.TclError:
                    pass

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    # --------------------------------------------------------
    # Initial position / drawing-writing tasks
    # --------------------------------------------------------

    def _move_initial_position(self) -> None:
        self._start_worker(
            "Moving to Initial Position",
            self._task_move_initial_position,
            require_content=False,
            log_drawer_context=False,
        )

    def _move_ready(self) -> None:
        self._start_worker("Moving to ready pose", self._task_move_ready, require_content=False)

    def _preflight(self) -> None:
        self._start_worker("Preflight", self._task_preflight, require_content=True)

    def _draw(self) -> None:
        self._start_worker("Drawing / writing", self._task_draw, require_content=True)

    def _task_move_initial_position(self, config: dict) -> None:
        self.core.move_initial_position()

    def _task_move_ready(self, config: dict) -> None:
        drawer = XArmSVGDrawer(XArmSVGSettings(svg_file=""), arm=self.core.arm)
        drawer.connect()
        drawer.move_ready()
        self._log("Ready pose reached.")

    def _task_preflight(self, config: dict) -> None:
        drawer = self._make_drawer(config)
        drawer.connect()

        if config["move_ready"]:
            drawer.move_ready()
            self._log("Ready pose reached.")
        if config["text_enabled"]:
            self._log(f'Preflighting text: "{config["text"]}"')
            drawer.preflight_heading(config["text"])
        if config["svg_enabled"]:
            self._log(f'Preflighting SVG: {Path(config["svg_path"]).name}')
            drawer.preflight()

    def _task_draw(self, config: dict) -> None:
        drawer = self._make_drawer(config)
        drawer.connect()
        self._log(f"Contact X offset = {CONTACT_X_OFFSET_MM:.2f} mm")

        if config["move_ready"]:
            drawer.move_ready()
            self._log("Ready pose reached.")
        if config["text_enabled"]:
            self._log(f'Writing: "{config["text"]}"')
            drawer.write_heading(config["text"])
        if config["svg_enabled"]:
            self._log(f'Drawing: {Path(config["svg_path"]).name}')
            drawer.draw()

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    def _on_close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self._save_settings()

        try:
            if self.core.arm is not None and self.core.automation_active:
                self.core.automation_stop_requested = True
                self.core.arm.set_state(4)
        except Exception:
            pass

        try:
            self.core.disconnect()
        except Exception as exc:
            print(f"Shutdown error: {exc}")

        try:
            pygame.quit()
        except Exception:
            pass

        try:
            self.destroy()
        except tk.TclError:
            pass


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    app = XArmCombinedApp()
    app.mainloop()
