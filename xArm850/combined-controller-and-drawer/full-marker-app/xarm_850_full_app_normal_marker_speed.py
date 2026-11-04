"""
xArm 850 full controller + wall drawing + marker-change app.

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
    pip install xarm-python-sdk pygame

Includes:
    - Xbox controller XYZ + direct simultaneous joint control
    - L1 precision Y/Z wall-plane controller mode
    - G2 gripper control
    - text, SVG and website JSON drawing
    - optional SVG color mapping to the Fiorello 12-marker palette
    - automatic color-by-color pickup / cap / draw / return workflow
    - tested marker pickup / handoff / return routes
    - controller hot-reconnect support

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
ColoredPath2D = Tuple[str, Polyline]
ColoredPath3D = Tuple[str, Path3D]


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
# Current marker/tool offset. More negative = farther toward the wall.
# The calibrated PAPER_* X values below are stored WITHOUT this marker offset.
CONTACT_X_OFFSET_MM = -19.17


# ============================================================
# MEASURED WALL / PAPER CALIBRATION
# ============================================================
#
# New 5-point reachable surface calibration, revised for current marker reach limits.
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
# PAPER_* X coordinates are marker-offset-neutral wall coordinates.
# CONTACT_X_OFFSET_MM is applied exactly once after interpolation.
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

# Safe TR-bottom was physically taught with CONTACT_X_OFFSET_MM = -19.17:
#   raw TCP = (-533.550537, 291.430176, 689.678589)
#
# Store the calibration surface WITHOUT the marker offset so the normal
# paper mapping can add CONTACT_X_OFFSET_MM exactly once:
#   base X = -533.550537 - (-19.17) = -514.380537
PAPER_TR_BOTTOM: Point3D = (
    -514.380537,
    291.430176,
    689.678589,
)

# Reference only — this pose produced the upper-limit/error condition.
# It is NOT used as a calibration point.
TR_BOTTOM_ERROR_TCP: Tuple[float, float, float, float, float, float] = (
    -533.648499,
    291.493408,
    701.684753,
    -179.699905,
    -3.600008,
    179.099674,
)

# Safe TR-top measured with CONTACT_X_OFFSET_MM = -19.17:
#   raw TCP = (-535.104065, 185.926178, 738.720276)
#
# Store marker-offset-neutral wall X:
#   base X = -535.104065 - (-19.17) = -515.934065
PAPER_TR_TOP: Point3D = (
    -515.934065,
    185.926178,
    738.720276,
)

# Reference only — this pose produced the upper-right/top reach error.
# It is NOT used as a calibration point.
TR_TOP_ERROR_TCP: Tuple[float, float, float, float, float, float] = (
    -535.100525,
    194.571854,
    738.719116,
    -179.700019,
    -3.600008,
    179.100018,
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
MAX_JOINT_SPEED = 10.0         # deg/s for first simultaneous J1-J4 testing
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

# L1 precision wall-plane control.  Hold L1 in XYZ mode:
#   right stick left/right -> Y-/Y+
#   right stick up/down    -> Z+/Z-
# X is locked to 0 velocity and the speed is reduced.
PRECISION_YZ_SPEED_FACTOR = 0.50


# ============================================================
# FIORELLO SKETCH MARKER PALETTE
# ============================================================

MARKER_PALETTE = [
    {"id": "brown",        "name": "Brown",        "hex": "#8B5A2B"},
    {"id": "magenta",      "name": "Magenta",      "hex": "#D81B60"},
    {"id": "red",          "name": "Red",          "hex": "#E53935"},
    {"id": "pink",         "name": "Pink",         "hex": "#F06292"},
    {"id": "orange",       "name": "Orange",       "hex": "#FB8C00"},
    {"id": "yellow",       "name": "Yellow",       "hex": "#FDD835"},
    {"id": "bright_green", "name": "Bright green", "hex": "#7CB342"},
    {"id": "dark_green",   "name": "Dark green",   "hex": "#1B5E20"},
    {"id": "light_blue",   "name": "Light blue",   "hex": "#29B6F6"},
    {"id": "dark_blue",    "name": "Dark blue",    "hex": "#1565C0"},
    {"id": "purple",       "name": "Purple",       "hex": "#7E57C2"},
    {"id": "black",        "name": "Black",        "hex": "#1E293B"},
]
MARKER_BY_ID = {item["id"]: item for item in MARKER_PALETTE}
MARKER_COLOR_ORDER = [item["id"] for item in MARKER_PALETTE]
DEFAULT_MARKER_COLOR = "black"


# ============================================================
# TESTED MARKER PICK / HANDOFF ROUTE
# ============================================================

MARKER_PICK_JOINTS = [
    -161.125014, -29.157536, -26.325291,
    177.925282, -3.691223, -159.999324,
]
MARKER_PICK_ABOVE_JOINTS = [
    -161.024918, -16.920360, -24.378609,
    178.725647, 5.883131, -160.717526,
]
MARKER_PICK_TRANSFER_JOINTS = [
    -160.821518, 19.858717, -57.315088,
    179.907086, 75.597484, -161.733323,
]
MARKER_DRAW_READY_JOINTS = [
    -196.531113, 7.519040, -77.101613,
    181.201913, 80.921408, -195.830958,
]
MARKER_HANDOFF_JOINTS = [
    -281.333966, 7.519040, -77.101613,
    181.201913, 80.921408, -195.830958,
]

MARKER_PICK_ABOVE_TCP = [
    -307.723938, -105.031891, 71.431976,
    -179.569958, -1.128727, -179.067187,
]
MARKER_PICK_TRANSFER_TCP = [
    -307.723938, -105.031891, 519.999939,
    -179.569958, -1.128784, -179.067187,
]
MARKER_DRAW_READY_TCP = [
    -391.468628, 110.893745, 597.494202,
    -179.705921, -3.507648, 179.133536,
]
MARKER_HANDOFF_TCP = [
    71.987541, 398.225983, 598.816772,
    -179.960944, -3.633641, 94.347012,
]

MARKER_GRIP_OPEN_MM = 50.0
MARKER_GRIP_HOLD_MM = 10.0
MARKER_POSE_TOLERANCE_DEG = 3.0

# Marker workflow uses the same normal motion profile as the rest of the app.
# Joint moves: 20 deg/s, 100 deg/s^2
# Cartesian marker transfers: 100 mm/s, 400 mm/s^2
MARKER_HANDOFF_JOINT_SPEED = READY_JOINT_SPEED
MARKER_HANDOFF_JOINT_ACC = JOINT_MAX_ACC
MARKER_PICK_JOINT_SPEED = READY_JOINT_SPEED
MARKER_PICK_JOINT_ACC = JOINT_MAX_ACC
MARKER_CART_SPEED = TRAVEL_SPEED
MARKER_CART_ACC = TCP_MAX_ACC

# Routing from an arbitrary normal pose also uses normal joint speed.
MARKER_ANYWHERE_JOINT_SPEED = READY_JOINT_SPEED
MARKER_ANYWHERE_JOINT_ACC = JOINT_MAX_ACC

# L3 return-to-rack routing heuristic (NOT a start-position restriction):
# if the TCP is already near the pickup X/Y column and above PICK_ABOVE, the
# app first routes through the high Z~520 transfer point before descending.
# Outside this radius it simply routes to PICK_ABOVE. The action never refuses
# merely because the robot is outside this region.
PICKUP_COLUMN_XY_RADIUS_MM = 80.0

# Colored JSON drawings, and SVG drawings when the color checkbox is enabled,
# use the physical marker station workflow automatically.
AUTO_MARKER_COLOR_CYCLE_ENABLED = True


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



# Common CSS names are enough for typical Inkscape / browser SVG files.
_CSS_NAMED_COLORS = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000",
    "green": "#008000", "lime": "#00ff00", "blue": "#0000ff",
    "navy": "#000080", "cyan": "#00ffff", "aqua": "#00ffff",
    "magenta": "#ff00ff", "fuchsia": "#ff00ff", "yellow": "#ffff00",
    "orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb",
    "brown": "#a52a2a", "gray": "#808080", "grey": "#808080",
    "darkgreen": "#006400", "lightblue": "#add8e6",
}


def _style_dict(style: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in style.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key.strip().lower()] = value.strip()
    return out


def _normalize_css_color(value: Optional[str]) -> Optional[str]:
    """Normalize an SVG/CSS color to #RRGGBB. None means no stroke."""
    if value is None:
        return "#000000"
    text = value.strip().lower()
    if not text or text == "none":
        return None
    if text in ("currentcolor", "inherit"):
        return "#000000"
    if text in _CSS_NAMED_COLORS:
        return _CSS_NAMED_COLORS[text]
    if text.startswith("#"):
        body = text[1:]
        if len(body) == 3 and all(c in "0123456789abcdef" for c in body):
            return "#" + "".join(c * 2 for c in body)
        if len(body) >= 6 and all(c in "0123456789abcdef" for c in body[:6]):
            return "#" + body[:6]
    m = re.fullmatch(r"rgb\(\s*([^,]+),\s*([^,]+),\s*([^\)]+)\s*\)", text)
    if m:
        vals = []
        for raw in m.groups():
            raw = raw.strip()
            if raw.endswith("%"):
                v = round(float(raw[:-1]) * 2.55)
            else:
                v = round(float(raw))
            vals.append(max(0, min(255, v)))
        return "#" + "".join(f"{v:02x}" for v in vals)
    return "#000000"


def _hex_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def nearest_marker_color(css_color: Optional[str]) -> str:
    normalized = _normalize_css_color(css_color)
    if normalized is None:
        return DEFAULT_MARKER_COLOR
    r, g, b = _hex_rgb(normalized)
    best_id = DEFAULT_MARKER_COLOR
    best_d = float("inf")
    for item in MARKER_PALETTE:
        pr, pg, pb = _hex_rgb(item["hex"])
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best_id = item["id"]
    return best_id


def marker_color_name(color_id: str) -> str:
    return MARKER_BY_ID.get(color_id, MARKER_BY_ID[DEFAULT_MARKER_COLOR])["name"]


class SVGColoredExtractor:
    """SVG geometry extractor that also keeps each element's stroke color."""

    def __init__(self, svg_file: str):
        self.svg_file = svg_file

    def load(self) -> Tuple[List[Tuple[str, Polyline]], float, float]:
        root = ET.parse(self.svg_file).getroot()
        view_box = root.attrib.get("viewBox", "").strip()
        if view_box:
            vb = [float(v) for v in view_box.replace(",", " ").split()]
            if len(vb) == 4:
                _, _, view_w, view_h = vb
            else:
                view_w = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", root.attrib.get("width", "100"))[0])
                view_h = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", root.attrib.get("height", "100"))[0])
        else:
            view_w = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", root.attrib.get("width", "100"))[0])
            view_h = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)", root.attrib.get("height", "100"))[0])

        paths: List[Tuple[str, Polyline]] = []
        self._collect(root, IDENTITY, None, paths)
        return paths, view_w, view_h

    def _stroke_for(self, elem: ET.Element, inherited: Optional[str]) -> Optional[str]:
        styles = _style_dict(elem.attrib.get("style", ""))
        if "stroke" in styles:
            return styles["stroke"]
        if "stroke" in elem.attrib:
            return elem.attrib.get("stroke")
        return inherited

    def _collect(
        self,
        elem: ET.Element,
        inherited_transform: Affine,
        inherited_stroke: Optional[str],
        out_paths: List[Tuple[str, Polyline]],
    ) -> None:
        this_transform = mat_mul(inherited_transform, parse_transform(elem.attrib.get("transform")))
        tag = local_name(elem.tag)
        stroke = self._stroke_for(elem, inherited_stroke)

        style = elem.attrib.get("style", "")
        if "display:none" in style or elem.attrib.get("display", "") == "none":
            return

        if tag in ("g", "svg"):
            for child in list(elem):
                self._collect(child, this_transform, stroke, out_paths)
            return

        normalized = _normalize_css_color(stroke)
        if stroke is not None and normalized is None:
            return
        marker_id = nearest_marker_color(stroke)

        def add(poly: Polyline) -> None:
            transformed = [apply_mat(this_transform, p) for p in poly]
            transformed = remove_duplicate_neighbors(transformed)
            if len(transformed) >= 2:
                out_paths.append((marker_id, transformed))

        if tag == "path":
            for poly in parse_svg_path(elem.attrib.get("d", "")):
                add(poly)
        elif tag == "ellipse":
            add(ellipse_polyline(
                float(elem.attrib.get("cx", "0")), float(elem.attrib.get("cy", "0")),
                float(elem.attrib.get("rx", "0")), float(elem.attrib.get("ry", "0")),
            ))
        elif tag == "circle":
            cx = float(elem.attrib.get("cx", "0")); cy = float(elem.attrib.get("cy", "0"))
            r = float(elem.attrib.get("r", "0"))
            add(ellipse_polyline(cx, cy, r, r))
        elif tag == "line":
            add([
                (float(elem.attrib.get("x1", "0")), float(elem.attrib.get("y1", "0"))),
                (float(elem.attrib.get("x2", "0")), float(elem.attrib.get("y2", "0"))),
            ])
        elif tag in ("polyline", "polygon"):
            pts = parse_points_attribute(elem.attrib.get("points", ""))
            if tag == "polygon" and pts:
                pts.append(pts[0])
            add(pts)
        elif tag == "rect":
            x = float(elem.attrib.get("x", "0")); y = float(elem.attrib.get("y", "0"))
            w = float(elem.attrib.get("width", "0")); h = float(elem.attrib.get("height", "0"))
            add([(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)])


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
    use_svg_colors: bool = False


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
        self.paths_by_color: Dict[str, List[Path3D]] = {}

        if self.settings.svg_file:
            self.load_svg()

    # ------------------------------------------------------------
    # SVG -> PAPER
    # ------------------------------------------------------------

    def load_svg(self) -> None:
        svg_path = Path(self.settings.svg_file)
        if not svg_path.is_absolute():
            svg_path = Path(__file__).resolve().parent / svg_path

        if self.settings.use_svg_colors:
            colored_raw, _, _ = SVGColoredExtractor(str(svg_path)).load()
        else:
            raw_paths, _, _ = SVGExtractor(str(svg_path)).load()
            colored_raw = [(DEFAULT_MARKER_COLOR, p) for p in raw_paths]

        if not colored_raw:
            raise RuntimeError(f"No drawable paths found in SVG: {svg_path}")

        all_points = [p for _color, poly in colored_raw for p in poly]
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)

        src_w = max_x - min_x
        src_h = max_y - min_y
        if src_w <= 0 or src_h <= 0:
            raise RuntimeError("SVG bounding box is degenerate.")

        scale_mm = min(
            self.settings.max_width_mm / src_w,
            self.settings.max_height_mm / src_h,
        )
        final_w = src_w * scale_mm
        final_h = src_h * scale_mm
        left_margin_mm = (PAPER_WIDTH_MM - final_w) / 2.0
        top_margin_mm = SVG_TOP_MARGIN_MM

        if top_margin_mm + final_h > PAPER_HEIGHT_MM:
            raise RuntimeError(
                f"Drawing does not fit vertically: top margin {top_margin_mm:.1f} "
                f"+ drawing {final_h:.1f} > paper {PAPER_HEIGHT_MM:.1f} mm"
            )

        mapped_paths: List[Path3D] = []
        mapped_by_color: Dict[str, List[Path3D]] = {}

        for color_id, raw in colored_raw:
            local_mm: Polyline = []
            for x, y in raw:
                local_mm.append(((x - min_x) * scale_mm, (y - min_y) * scale_mm))

            local_mm = remove_duplicate_neighbors(local_mm)
            if len(local_mm) < 2:
                continue
            if self.settings.simplify_tolerance_mm > 0:
                local_mm = rdp(local_mm, self.settings.simplify_tolerance_mm)
                local_mm = remove_duplicate_neighbors(local_mm)
            if len(local_mm) < 2 or polyline_length(local_mm) < self.settings.min_path_length_mm:
                continue

            path3d: Path3D = []
            for right_mm, down_mm in local_mm:
                path3d.append(paper_mm_to_contact(
                    left_margin_mm + right_mm,
                    top_margin_mm + down_mm,
                ))

            cleaned: Path3D = []
            for p in path3d:
                if not cleaned or point3_distance(cleaned[-1], p) > 0.02:
                    cleaned.append(p)
            if len(cleaned) >= 2:
                mapped_paths.append(cleaned)
                mapped_by_color.setdefault(color_id, []).append(cleaned)

        self.paths = mapped_paths
        self.paths_by_color = mapped_by_color

        print(f"Loaded SVG: {svg_path}")
        print(f"  raw paths: {len(colored_raw)}")
        print(f"  kept paths: {len(self.paths)}")
        print(f"  SVG content bbox: {src_w:.2f} x {src_h:.2f}")
        print(f"  final drawing size: {final_w:.1f} x {final_h:.1f} mm")
        print(f"  drawing top margin: {top_margin_mm:.1f} mm")
        if self.settings.use_svg_colors:
            used = [marker_color_name(cid) for cid in MARKER_COLOR_ORDER if cid in mapped_by_color]
            print(f"  mapped marker colors: {', '.join(used) if used else 'none'}")
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
    # PREFLIGHT / DRAW
    # ------------------------------------------------------------

    def preflight_paths(self, paths: Sequence[Path3D], label: str = "drawing") -> None:
        print()
        print(f"Starting pen-up preflight for {len(paths)} {label} paths...")
        print(f"Safe plane X = {SAFE_X:.1f}")
        for i, path in enumerate(paths, start=1):
            if not path:
                continue
            if i == 1 or i % 20 == 0 or i == len(paths):
                print(f"Preflight path {i}/{len(paths)}")
            self.move_xyz(safe_point(path[0]), TRAVEL_SPEED, wait=True)
            if len(path) > 1:
                for p in path[1:-1]:
                    self.move_xyz(safe_point(p), TRAVEL_SPEED, wait=WAIT_FOR_EACH_POINT)
                self.move_xyz(safe_point(path[-1]), TRAVEL_SPEED, wait=True)
        print(f"{label.capitalize()} preflight finished.")

    def preflight(self) -> None:
        self.preflight_paths(self.paths, "SVG")

    def draw_paths(self, paths: Sequence[Path3D], label: str = "drawing") -> None:
        print()
        print(f"Starting {label}: {len(paths)} paths")
        print(f"Travel plane X = {SAFE_X:.1f}")
        print("Contact surface uses the 5-point clipped calibration.")
        for i, path in enumerate(paths, start=1):
            if len(path) < 2:
                continue
            if i == 1 or i % 20 == 0 or i == len(paths):
                print(f"Drawing path {i}/{len(paths)}")
            start_contact = path[0]
            self.move_xyz(safe_point(start_contact), TRAVEL_SPEED, wait=True)
            self.move_xyz(start_contact, APPROACH_SPEED, wait=True)
            for p in path[1:-1]:
                self.move_xyz(p, DRAW_SPEED, wait=False)
            self.move_xyz(path[-1], DRAW_SPEED, wait=True)
            self.move_xyz(safe_point(path[-1]), APPROACH_SPEED, wait=True)
        print(f"{label.capitalize()} finished.")

    def draw(self) -> None:
        self.draw_paths(self.paths, "SVG drawing")


# ============================================================
# WEBSITE JSON DRAWING LOADER
# ============================================================

def load_web_json_paths(
    json_file: str,
    max_width_mm: float,
    max_height_mm: float,
    top_margin_mm: float,
) -> Dict[str, List[Path3D]]:
    """Load xarm850-freehand-v1 JSON and preserve its marker color IDs."""
    path = Path(json_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "xarm850-freehand-v1":
        raise RuntimeError("Expected an xarm850-freehand-v1 JSON drawing.")

    width = float(data.get("width_mm", 0.0))
    height = float(data.get("height_mm", 0.0))
    if width <= 0 or height <= 0:
        raise RuntimeError("JSON drawing has invalid width_mm / height_mm.")

    scale = min(max_width_mm / width, max_height_mm / height)
    final_w = width * scale
    final_h = height * scale
    left_margin = (PAPER_WIDTH_MM - final_w) / 2.0
    if top_margin_mm + final_h > PAPER_HEIGHT_MM:
        raise RuntimeError(
            f"JSON drawing does not fit vertically: {top_margin_mm:.1f} + "
            f"{final_h:.1f} > {PAPER_HEIGHT_MM:.1f} mm"
        )

    result: Dict[str, List[Path3D]] = {}
    strokes = data.get("strokes", [])
    if not isinstance(strokes, list):
        raise RuntimeError("JSON drawing has no valid strokes list.")

    for index, stroke in enumerate(strokes, start=1):
        if not isinstance(stroke, dict):
            continue
        points = stroke.get("points")
        if not isinstance(points, list) or len(points) < 2:
            continue
        color_id = stroke.get("color", DEFAULT_MARKER_COLOR)
        if color_id not in MARKER_BY_ID:
            color_id = DEFAULT_MARKER_COLOR

        local: Polyline = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise RuntimeError(f"JSON stroke {index} has an invalid point.")
            local.append((float(point[0]) * scale, float(point[1]) * scale))

        local = remove_duplicate_neighbors(local)
        if len(local) < 2:
            continue
        if SIMPLIFY_TOLERANCE_MM > 0:
            local = rdp(local, SIMPLIFY_TOLERANCE_MM)
            local = remove_duplicate_neighbors(local)
        if len(local) < 2 or polyline_length(local) < MIN_PATH_LENGTH_MM:
            continue

        path3d: Path3D = []
        for right_mm, down_mm in local:
            try:
                path3d.append(paper_mm_to_contact(
                    left_margin + right_mm,
                    top_margin_mm + down_mm,
                ))
            except RuntimeError as exc:
                raise RuntimeError(
                    f"JSON stroke {index} ({marker_color_name(color_id)}) enters the "
                    f"unreachable clipped corner. {exc}"
                ) from exc

        cleaned: Path3D = []
        for p in path3d:
            if not cleaned or point3_distance(cleaned[-1], p) > 0.02:
                cleaned.append(p)
        if len(cleaned) >= 2:
            result.setdefault(color_id, []).append(cleaned)

    if not any(result.values()):
        raise RuntimeError("JSON drawing contains no drawable strokes.")

    print(f"Loaded JSON drawing: {path}")
    print(f"  source canvas: {width:.1f} x {height:.1f} mm")
    print(f"  mapped canvas: {final_w:.1f} x {final_h:.1f} mm")
    print(f"  top margin: {top_margin_mm:.1f} mm")
    print("  colors: " + ", ".join(
        marker_color_name(cid) for cid in MARKER_COLOR_ORDER if cid in result
    ))
    return result


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
        self.precision_yz_factor = PRECISION_YZ_SPEED_FACTOR
        self.precision_yz_active = False

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
        self.precision_yz_active = False
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
            self.log("MODE: JOINT — direct J1-J6 control")
        else:
            if not self.switch_velocity_mode(5):
                return
            self.control_mode = "XYZ"
            self.log("MODE: XYZ")

        self.stop_latched = True


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
            self.precision_yz_active = False
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

    def _xyz_targets(self, controller, precision_yz: bool = False) -> Tuple[float, float, float]:
        right_x = apply_deadzone(controller.get_axis(RIGHT_X), self.deadzone)
        right_y = apply_deadzone(controller.get_axis(RIGHT_Y), self.deadzone)
        left_x = apply_deadzone(controller.get_axis(LEFT_X), self.deadzone)
        left_y = apply_deadzone(controller.get_axis(LEFT_Y), self.deadzone)

        if precision_yz:
            # L1 "scope" mode: lock X and use the right stick on the wall plane.
            # Right = Y+, left = Y-, up = Z+, down = Z-.
            x_component = 0.0
            y_component = right_x
            z_component = -right_y
            speed = self.max_tcp_speed * self.precision_yz_factor
        else:
            # Normal XYZ mapping.
            x_component = right_y       # right stick up = X-
            y_component = left_x if abs(left_x) > abs(right_x) else right_x
            z_component = -left_y       # left stick up = Z+
            speed = self.max_tcp_speed

        magnitude = math.sqrt(
            x_component * x_component
            + y_component * y_component
            + z_component * z_component
        )
        if magnitude > 1.0:
            x_component /= magnitude
            y_component /= magnitude
            z_component /= magnitude

        return (x_component * speed, y_component * speed, z_component * speed)

    def update_cartesian(self, controller) -> None:
        if self.arm is None:
            return

        precision_yz = bool(controller.get_button(BUTTON_L1))
        if precision_yz != self.precision_yz_active:
            # Kill any lingering X component when entering/leaving precision mode.
            self.stop_velocity(force=True)
            self.reset_smoothing()
            self.precision_yz_active = precision_yz
            self.log(
                "L1 precision Y/Z mode ON"
                if precision_yz else
                "L1 precision Y/Z mode OFF"
            )

        vx, vy, vz = self._xyz_targets(controller, precision_yz=precision_yz)
        if abs(vx) < 0.01 and abs(vy) < 0.01 and abs(vz) < 0.01:
            self.stop_velocity()
            if precision_yz:
                self.last_motion_text = "YZ PRECISION — STOP"
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
        prefix = "YZ PRECISION" if precision_yz else "XYZ"
        self.last_motion_text = (
            f"{prefix}  X {self.smoothed_vx:+.1f}  Y {self.smoothed_vy:+.1f}  "
            f"Z {self.smoothed_vz:+.1f} mm/s"
        )
        self.last_speed_text = (
            f"{math.sqrt(self.smoothed_vx**2 + self.smoothed_vy**2 + self.smoothed_vz**2):.1f} mm/s"
        )

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
        left_x = apply_deadzone(controller.get_axis(LEFT_X), self.deadzone)
        left_y = apply_deadzone(controller.get_axis(LEFT_Y), self.deadzone)

        # Direct simultaneous mapping:
        #   right L/R = J1-/+
        #   right U/D = J2+/-
        #   left  U/D = J3-/+
        #   left  L/R = J4-/+
        targets = [0.0] * 6
        targets[0] = right_x * self.max_joint_speed
        targets[1] = -right_y * self.max_joint_speed
        targets[2] = left_y * self.max_joint_speed
        targets[3] = left_x * self.max_joint_speed

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
    # Tested marker pickup / handoff / return routes
    # --------------------------------------------------------

    def _current_joints(self) -> List[float]:
        if self.arm is None:
            raise RuntimeError("Robot is not connected.")
        code, joints = self.arm.get_servo_angle(is_radian=False)
        self._check_code(code, "read joints")
        return [float(v) for v in joints[:6]]

    def _current_tcp(self) -> List[float]:
        if self.arm is None:
            raise RuntimeError("Robot is not connected.")
        code, pose = self.arm.get_position(is_radian=False)
        self._check_code(code, "read TCP")
        return [float(v) for v in pose[:6]]

    @staticmethod
    def _joints_near(
        actual: Sequence[float],
        target: Sequence[float],
        tolerance: float = MARKER_POSE_TOLERANCE_DEG,
    ) -> bool:
        return all(abs(a - b) <= tolerance for a, b in zip(actual[:6], target[:6]))

    def marker_pose_name(self) -> str:
        joints = self._current_joints()
        checks = [
            ("HANDOFF", MARKER_HANDOFF_JOINTS),
            ("DRAW_READY", MARKER_DRAW_READY_JOINTS),
            ("PICK_TRANSFER", MARKER_PICK_TRANSFER_JOINTS),
            ("PICK_ABOVE", MARKER_PICK_ABOVE_JOINTS),
            ("PICK", MARKER_PICK_JOINTS),
        ]
        for name, target in checks:
            if self._joints_near(joints, target):
                return name
        return "OTHER"

    def _marker_joint_move(
        self,
        joints: Sequence[float],
        name: str,
        speed: float,
        acc: float,
    ) -> None:
        if self.arm is None:
            raise RuntimeError("Robot is not connected.")
        self.arm.set_joint_maxacc(acc)
        code = self.arm.set_servo_angle(
            angle=list(joints),
            speed=speed,
            mvacc=acc,
            wait=True,
            is_radian=False,
        )
        self._check_code(code, name)
        if self.automation_stop_requested:
            raise RuntimeError("Operation stopped.")

    def _marker_cart_move(self, pose: Sequence[float], name: str) -> None:
        if self.arm is None:
            raise RuntimeError("Robot is not connected.")
        x, y, z, roll, pitch, yaw = pose
        code = self.arm.set_position(
            x=x,
            y=y,
            z=z,
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            speed=MARKER_CART_SPEED,
            mvacc=MARKER_CART_ACC,
            wait=True,
            relative=False,
            is_radian=False,
            motion_type=0,
        )
        self._check_code(code, name)
        if self.automation_stop_requested:
            raise RuntimeError("Operation stopped.")

    def _marker_set_gripper(self, position: float) -> None:
        if self.arm is None:
            raise RuntimeError("Robot is not connected.")
        code = self.arm.set_gripper_g2_position(
            position,
            speed=self.gripper_speed,
            force=self.gripper_force,
            wait=True,
        )
        self._check_code(code, f"G2 -> {position:.0f} mm")
        self.gripper_target = position
        self.last_gripper_sent = position
        if self.automation_stop_requested:
            raise RuntimeError("Operation stopped.")

    def _near_pickup_column(self) -> bool:
        """Routing hint only; never used as a refusal/safety gate."""
        tcp = self._current_tcp()
        dx = tcp[0] - MARKER_PICK_ABOVE_TCP[0]
        dy = tcp[1] - MARKER_PICK_ABOVE_TCP[1]
        horizontal = math.hypot(dx, dy)
        return (
            horizontal <= PICKUP_COLUMN_XY_RADIUS_MM
            and tcp[2] > MARKER_PICK_ABOVE_TCP[2] + 10.0
        )

    def marker_route_to_pick_above(self, prefer_transfer_if_above: bool = False) -> None:
        """Route to PICK_ABOVE without requiring a special starting pose.

        Known marker-route poses use the already-tested route. From any other
        normal pose the robot performs a slow joint move to PICK_ABOVE. For the
        L3 return workflow, if the TCP is already over the pickup column and
        above PICK_ABOVE, we first use the high PICK_TRANSFER point and descend.
        """
        pose = self.marker_pose_name()

        if pose == "PICK_ABOVE":
            return
        if pose == "PICK":
            self.log("Marker route: PICK -> PICK_ABOVE")
            self._marker_joint_move(
                MARKER_PICK_ABOVE_JOINTS,
                "PICK_ABOVE",
                MARKER_PICK_JOINT_SPEED,
                MARKER_PICK_JOINT_ACC,
            )
            return
        if pose == "PICK_TRANSFER":
            self.log("Marker route: PICK_TRANSFER -> PICK_ABOVE")
            self._marker_cart_move(MARKER_PICK_ABOVE_TCP, "PICK_ABOVE")
            return
        if pose == "DRAW_READY":
            self.log("Marker route: DRAW_READY -> PICK_TRANSFER -> PICK_ABOVE")
            self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
            self._marker_cart_move(MARKER_PICK_ABOVE_TCP, "PICK_ABOVE")
            return
        if pose == "HANDOFF":
            self.log("Marker route: HANDOFF -> DRAW_READY -> PICK_TRANSFER -> PICK_ABOVE")
            self._marker_joint_move(
                MARKER_DRAW_READY_JOINTS,
                "MARKER_DRAW_READY",
                MARKER_HANDOFF_JOINT_SPEED,
                MARKER_HANDOFF_JOINT_ACC,
            )
            self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
            self._marker_cart_move(MARKER_PICK_ABOVE_TCP, "PICK_ABOVE")
            return

        if prefer_transfer_if_above and self._near_pickup_column():
            self.log(
                "Marker return routing: TCP is near the pickup column; "
                "using PICK_TRANSFER (Z~520) before descending."
            )
            self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
            self._marker_cart_move(MARKER_PICK_ABOVE_TCP, "PICK_ABOVE")
            return

        self.log(
            "Marker routing from current pose -> PICK_ABOVE "
            f"({MARKER_ANYWHERE_JOINT_SPEED:.0f} deg/s)."
        )
        self._marker_joint_move(
            MARKER_PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            MARKER_ANYWHERE_JOINT_SPEED,
            MARKER_ANYWHERE_JOINT_ACC,
        )

    def marker_route_to_draw_ready(self) -> None:
        """Route from any normal pose into the marker-compatible Draw Ready branch."""
        pose = self.marker_pose_name()
        if pose == "DRAW_READY":
            return
        if pose == "HANDOFF":
            self.log("Marker route: HANDOFF -> DRAW_READY (J1-only)")
            self._marker_joint_move(
                MARKER_DRAW_READY_JOINTS,
                "MARKER_DRAW_READY",
                MARKER_HANDOFF_JOINT_SPEED,
                MARKER_HANDOFF_JOINT_ACC,
            )
            return
        if pose == "PICK_TRANSFER":
            self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY")
        elif pose == "PICK_ABOVE":
            self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
            self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY")
        elif pose == "PICK":
            self._marker_joint_move(
                MARKER_PICK_ABOVE_JOINTS,
                "PICK_ABOVE",
                MARKER_PICK_JOINT_SPEED,
                MARKER_PICK_JOINT_ACC,
            )
            self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
            self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY")
        else:
            # Avoid asking the operator to manually find an exact waypoint.
            self.marker_route_to_pick_above(prefer_transfer_if_above=True)
            self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
            self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY")

        if self.marker_pose_name() != "DRAW_READY":
            raise RuntimeError(
                "Reached the Draw Ready TCP but not the expected marker-compatible wrist branch."
            )

    def marker_return_from_wall_to_draw_ready(self) -> None:
        """Return from a completed wall drawing to marker-compatible Draw Ready.

        This is the same Cartesian bridge used by the standalone Mister Bean
        demo. The joint branch is verified afterwards before handoff continues.
        """
        self.log("Wall drawing -> marker Draw Ready (Cartesian)")
        self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY after drawing")
        if self.marker_pose_name() != "DRAW_READY":
            raise RuntimeError(
                "Returned to Draw Ready TCP but not the expected marker-compatible wrist branch."
            )

    def marker_go_to_holder(self, prefer_transfer_if_above: bool = False) -> None:
        """Route from any normal pose to the exact PICK / place pose."""
        self.marker_route_to_pick_above(prefer_transfer_if_above=prefer_transfer_if_above)
        self.log("Marker route: PICK_ABOVE -> PICK / PLACE")
        self._marker_joint_move(
            MARKER_PICK_JOINTS,
            "PICK / PLACE",
            MARKER_PICK_JOINT_SPEED,
            MARKER_PICK_JOINT_ACC,
        )

    def marker_pick_to_handoff(self) -> None:
        """Full R3 workflow up to the cap-removal handoff."""
        self.marker_route_to_pick_above(prefer_transfer_if_above=False)
        self.log(f"Opening G2 for pickup -> {MARKER_GRIP_OPEN_MM:.0f} mm")
        self._marker_set_gripper(MARKER_GRIP_OPEN_MM)
        self._marker_joint_move(
            MARKER_PICK_JOINTS,
            "PICK",
            MARKER_PICK_JOINT_SPEED,
            MARKER_PICK_JOINT_ACC,
        )
        self.log(f"Closing G2 on marker -> {MARKER_GRIP_HOLD_MM:.0f} mm")
        self._marker_set_gripper(MARKER_GRIP_HOLD_MM)
        time.sleep(0.5)
        self._marker_joint_move(
            MARKER_PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            MARKER_PICK_JOINT_SPEED,
            MARKER_PICK_JOINT_ACC,
        )
        self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
        self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY")
        if self.marker_pose_name() != "DRAW_READY":
            raise RuntimeError(
                "Reached the Draw Ready TCP but not the expected marker-compatible wrist branch."
            )
        self.marker_handoff()
        self.log("Marker is at HANDOFF, waiting for cap removal.")

    def marker_pick_to_draw_ready(self) -> None:
        """Compatibility helper: pick marker and finish at marker Draw Ready."""
        self.marker_route_to_pick_above(prefer_transfer_if_above=False)
        self._marker_set_gripper(MARKER_GRIP_OPEN_MM)
        self._marker_joint_move(
            MARKER_PICK_JOINTS,
            "PICK",
            MARKER_PICK_JOINT_SPEED,
            MARKER_PICK_JOINT_ACC,
        )
        self._marker_set_gripper(MARKER_GRIP_HOLD_MM)
        time.sleep(0.5)
        self._marker_joint_move(
            MARKER_PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            MARKER_PICK_JOINT_SPEED,
            MARKER_PICK_JOINT_ACC,
        )
        self._marker_cart_move(MARKER_PICK_TRANSFER_TCP, "PICK_TRANSFER")
        self._marker_cart_move(MARKER_DRAW_READY_TCP, "MARKER_DRAW_READY")
        if self.marker_pose_name() != "DRAW_READY":
            raise RuntimeError(
                "Reached the Draw Ready TCP but not the expected marker-compatible wrist branch."
            )

    def marker_handoff(self) -> None:
        """Move to handoff, routing to marker Draw Ready first when needed."""
        self.marker_route_to_draw_ready()
        self.log("Marker route: DRAW_READY -> HANDOFF (J1-only)")
        self._marker_joint_move(
            MARKER_HANDOFF_JOINTS,
            "MARKER_HANDOFF",
            MARKER_HANDOFF_JOINT_SPEED,
            MARKER_HANDOFF_JOINT_ACC,
        )

    def marker_to_draw_ready_from_handoff(self) -> None:
        """Return from handoff; routes itself if called from another pose."""
        self.marker_route_to_draw_ready()

    def marker_release_at_handoff(self) -> None:
        # If this button is used from elsewhere, route there rather than refuse.
        self.marker_handoff()
        self._marker_set_gripper(MARKER_GRIP_OPEN_MM)
        time.sleep(1.0)
        self.log("Marker released at handoff.")

    def marker_return_to_holder(self) -> None:
        """L3 workflow: return held marker to rack from any normal pose."""
        self.marker_go_to_holder(prefer_transfer_if_above=True)
        self.log("Releasing marker into holder...")
        self._marker_set_gripper(MARKER_GRIP_OPEN_MM)
        time.sleep(1.0)
        self._marker_joint_move(
            MARKER_PICK_ABOVE_JOINTS,
            "PICK_ABOVE",
            MARKER_PICK_JOINT_SPEED,
            MARKER_PICK_JOINT_ACC,
        )
        self.log("Marker returned to holder; robot is at PICK_ABOVE.")

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
    SETTINGS_FILE = "xarm_850_full_app_settings.json"

    def __init__(self):
        super().__init__()

        self.title("xArm 850 Full Controller + Wall Drawing")
        self.geometry("1120x950")
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
        self.joint_var = tk.StringVar(value="Direct J1-J6")
        self.motion_var = tk.StringVar(value="STOP")
        self.live_speed_var = tk.StringVar(value="0")
        self.error_var = tk.StringVar(value="None")
        self.gripper_pos_var = tk.StringVar(value="84 mm")

        # Controller settings
        self.deadzone_var = tk.DoubleVar(value=STICK_DEADZONE)
        self.max_tcp_speed_var = tk.DoubleVar(value=MAX_TCP_SPEED)
        self.tcp_acc_var = tk.DoubleVar(value=TCP_MAX_ACC)
        self.smoothing_var = tk.DoubleVar(value=VELOCITY_SMOOTHING)
        self.precision_factor_var = tk.DoubleVar(value=PRECISION_YZ_SPEED_FACTOR * 100.0)
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
        self.svg_colors_var = tk.BooleanVar(value=False)
        default_svg = str((Path(__file__).resolve().parent / SVG_FILE).resolve())
        self.svg_var = tk.StringVar(value=default_svg)
        self.svg_top_var = tk.DoubleVar(value=SVG_TOP_MARGIN_MM)
        self.svg_width_var = tk.DoubleVar(value=MAX_DRAWING_WIDTH_MM)
        self.svg_height_var = tk.DoubleVar(value=MAX_DRAWING_HEIGHT_MM)
        self.draw_speed_var = tk.DoubleVar(value=DRAW_SPEED)

        self.draw_json_var = tk.BooleanVar(value=False)
        self.json_var = tk.StringVar(value="")
        self.json_top_var = tk.DoubleVar(value=15.0)
        self.json_width_var = tk.DoubleVar(value=min(359.6, PAPER_WIDTH_MM))
        self.json_height_var = tk.DoubleVar(value=min(235.0, PAPER_HEIGHT_MM - 15.0))

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
        self.marker_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.controller_tab, text="Controller")
        self.notebook.add(self.drawer_tab, text="Draw / Write")
        self.notebook.add(self.marker_tab, text="Markers")

        self._build_controller_tab()
        self._build_drawer_tab()
        self._build_marker_tab()

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
            ("Joint control", self.joint_var),
            ("Movement", self.motion_var),
            ("Speed", self.live_speed_var),
            ("G2 target", self.gripper_pos_var),
            ("Error", self.error_var),
        ]
        for row, (label, variable) in enumerate(rows):
            ttk.Label(live, text=f"{label}:").grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=2)
            ttk.Label(live, textvariable=variable, wraplength=360).grid(row=row, column=1, sticky="w", pady=2)
        ttk.Button(live, text="Connect / Reconnect Controller", command=self._reconnect_controller).grid(
            row=len(rows), column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

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
            text="Initial Position  (Y)",
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
            ("L1 precision speed (%)", self.precision_factor_var, 10, 100, 5, "J1-J4 speed (deg/s)", self.joint_speed_var, 1, 100, 1),
            ("J5/J6 speed (deg/s)", self.j56_speed_var, 1, 100, 1, "Joint acceleration", self.joint_acc_var, 10, 1000, 10),
            ("G2 trigger rate (mm/s)", self.gripper_rate_var, 5, 150, 5, "G2 speed", self.gripper_speed_var, 15, 225, 5),
            ("G2 force", self.gripper_force_var, 1, 100, 1, "", None, 0, 0, 1),
        ]

        for row, data in enumerate(setting_rows):
            l1, v1, f1, t1, i1, l2, v2, f2, t2, i2 = data
            ttk.Label(settings, text=l1).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            ttk.Spinbox(settings, from_=f1, to=t1, increment=i1, textvariable=v1, width=10).grid(
                row=row, column=1, sticky="w", padx=(0, 16), pady=3
            )
            if l2:
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
                "XYZ mode: right stick = X/Y; left stick = Y/Z.  Hold L1 for precision wall mode: "
                "right stick becomes Y/Z only (right=Y+, left=Y-, up=Z+, down=Z-) at the configured reduced speed.\n"
                "JOINT mode (R1): right stick L/R=J1, U/D=J2; left stick U/D=J3, L/R=J4. "
                "All four can move simultaneously. D-pad = J5/J6.\n"
                "L2 opens G2, R2 closes G2.  A = STOP, X = Recover, Y = Initial Position, "
                "R3 = Pick marker + cap-removal handoff, L3 = Return marker to rack, B = Disable + Exit."
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
            offset_frame, from_=-40.0, to=5.0, increment=0.1,
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
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )
        ttk.Checkbutton(
            svg_box,
            text="Use SVG colors / marker changes",
            variable=self.svg_colors_var,
        ).grid(row=0, column=2, columnspan=2, sticky="w", pady=(0, 5))
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

        # Website JSON
        json_box = ttk.LabelFrame(root, text="Website JSON drawing (colors automatic)", padding=10)
        json_box.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        json_box.columnconfigure(1, weight=1)
        ttk.Checkbutton(json_box, text="Draw JSON", variable=self.draw_json_var).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 5)
        )
        ttk.Label(json_box, text="JSON file").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(json_box, textvariable=self.json_var).grid(row=1, column=1, columnspan=2, sticky="ew", pady=4)
        ttk.Button(json_box, text="Browse…", command=self._browse_json).grid(row=1, column=3, padx=(8, 0), pady=4)
        ttk.Label(json_box, text="Top margin (mm)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(json_box, from_=0, to=PAPER_HEIGHT_MM, increment=1, textvariable=self.json_top_var, width=9).grid(
            row=2, column=1, sticky="w", padx=(0, 12)
        )
        ttk.Label(json_box, text="Max width (mm)").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(json_box, from_=20, to=PAPER_WIDTH_MM, increment=5, textvariable=self.json_width_var, width=9).grid(
            row=2, column=3, sticky="w"
        )
        ttk.Label(json_box, text="Max height (mm)").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(json_box, from_=20, to=PAPER_HEIGHT_MM, increment=5, textvariable=self.json_height_var, width=9).grid(
            row=3, column=1, sticky="w", padx=(0, 12)
        )
        ttk.Label(
            json_box,
            text=(
                "Old JSON files without a color field are treated as Black. "
                "JSON colors automatically use the marker pickup / cap / return workflow."
            ),
        ).grid(row=3, column=2, columnspan=2, sticky="w")

        # Run controls
        controls = ttk.LabelFrame(root, text="Run", padding=10)
        controls.grid(row=4, column=0, sticky="ew")
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
        ).grid(row=5, column=0, sticky="w", pady=(8, 0))

    def _build_marker_tab(self) -> None:
        root = self.marker_tab
        root.columnconfigure(0, weight=1)

        info = ttk.LabelFrame(root, text="Tested marker station workflow", padding=12)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            info,
            text=(
                "Marker actions route themselves to the required waypoint instead of requiring you to manually "
                "place the robot at an exact start pose. From an arbitrary pose, pickup uses a slow move to PICK_ABOVE.\n\n"
                "R3 / Pick marker runs the full pickup -> transfer -> handoff flow, waits for cap removal, then returns "
                "to marker Draw Ready. L3 / Return marker routes back to the holder and releases it. Colored JSON drawings "
                "use the same physical marker/cap cycle automatically; SVG colors do so only when its checkbox is enabled."
            ),
            wraplength=980, justify="left",
        ).pack(anchor="w")

        actions = ttk.LabelFrame(root, text="Marker actions", padding=12)
        actions.grid(row=1, column=0, sticky="ew")
        for col in range(2):
            actions.columnconfigure(col, weight=1)

        self.marker_pick_btn = ttk.Button(
            actions, text="Pick marker + cap handoff  (R3)", command=self._marker_pick
        )
        self.marker_pick_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=5, ipady=8)

        self.marker_handoff_btn = ttk.Button(
            actions, text="Hand marker to user", command=self._marker_handoff
        )
        self.marker_handoff_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=5, ipady=8)

        self.marker_return_btn = ttk.Button(
            actions, text="Return marker to rack  (L3)", command=self._marker_return
        )
        self.marker_return_btn.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=5, ipady=8)

        self.marker_pose_btn = ttk.Button(
            actions, text="Check marker-route pose", command=self._check_marker_pose
        )
        self.marker_pose_btn.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=5, ipady=8)

        ttk.Label(
            root,
            text=(
                "Pickup grip: 10 mm  •  Release/open: 50 mm  •  "
                "HANDOFF ↔ DRAW_READY is J1-only.\n"
                "A / GUI STOP remains active during marker motions."
            ),
            justify="left", wraplength=980,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

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
            "precision_factor": self.precision_factor_var,
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
            "svg_colors": self.svg_colors_var,
            "svg_file": self.svg_var,
            "svg_top": self.svg_top_var,
            "svg_width": self.svg_width_var,
            "svg_height": self.svg_height_var,
            "draw_speed": self.draw_speed_var,
            "draw_json": self.draw_json_var,
            "json_file": self.json_var,
            "json_top": self.json_top_var,
            "json_width": self.json_width_var,
            "json_height": self.json_height_var,
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
            "precision_factor": self.precision_factor_var.get(),
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
            "svg_colors": self.svg_colors_var.get(),
            "svg_file": self.svg_var.get(),
            "svg_top": self.svg_top_var.get(),
            "svg_width": self.svg_width_var.get(),
            "svg_height": self.svg_height_var.get(),
            "draw_speed": self.draw_speed_var.get(),
            "draw_json": self.draw_json_var.get(),
            "json_file": self.json_var.get(),
            "json_top": self.json_top_var.get(),
            "json_width": self.json_width_var.get(),
            "json_height": self.json_height_var.get(),
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
            self.core.precision_yz_factor = max(0.1, min(1.0, float(self.precision_factor_var.get()) / 100.0))
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

    def _find_controller(self, force_reinit: bool = False) -> None:
        try:
            self._init_pygame()
            if force_reinit:
                try:
                    pygame.joystick.quit()
                    pygame.joystick.init()
                    pygame.event.clear()
                except pygame.error:
                    pass
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

    def _reconnect_controller(self) -> None:
        if not self.core.automation_active:
            try:
                self.core.stop_velocity(force=True)
            except Exception:
                pass
        self.controller = None
        self.controller_connected = False
        self.controller_name = ""
        self.previous_buttons.clear()
        self.controller_state_var.set("Scanning...")
        self._find_controller(force_reinit=True)
        if not self.controller_connected:
            self._log("No controller found. Turn it on, then press Connect / Reconnect Controller again.")

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

        try:
            for event in pygame.event.get([pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED]):
                if event.type == pygame.JOYDEVICEREMOVED:
                    self._handle_controller_disconnect()
                elif event.type == pygame.JOYDEVICEADDED and not self.controller_connected:
                    self._find_controller()
        except (pygame.error, AttributeError):
            pass

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
            y = bool(controller.get_button(BUTTON_Y))
            l1 = bool(controller.get_button(BUTTON_L1))
            r1 = bool(controller.get_button(BUTTON_R1))
            l3 = bool(controller.get_button(BUTTON_L3))
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

            # Automatic actions are single-press. A/STOP remains active while
            # any of them are running.
            if not self.core.automation_active:
                if y and not self.previous_buttons.get(BUTTON_Y, False):
                    self._move_initial_position()
                if r3 and not self.previous_buttons.get(BUTTON_R3, False):
                    self._marker_pick()
                if l3 and not self.previous_buttons.get(BUTTON_L3, False):
                    self._marker_return()

            self.previous_buttons[BUTTON_A] = a
            self.previous_buttons[BUTTON_B] = b
            self.previous_buttons[BUTTON_X] = x
            self.previous_buttons[BUTTON_Y] = y
            self.previous_buttons[BUTTON_L1] = l1
            self.previous_buttons[BUTTON_R1] = r1
            self.previous_buttons[BUTTON_L3] = l3
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
        self.joint_var.set("Direct J1-J6" if self.core.control_mode == "JOINT" else "—")
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

    def _browse_json(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose website JSON drawing",
            filetypes=[("JSON drawings", "*.json"), ("All files", "*.*")],
        )
        if filename:
            self.json_var.set(filename)

    def _nudge_offset(self, amount: float) -> None:
        self.offset_var.set(round(float(self.offset_var.get()) + amount, 2))

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        buttons = [self.ready_btn, self.preflight_btn, self.draw_btn, self.initial_btn]
        for name in ("marker_pick_btn", "marker_handoff_btn", "marker_return_btn", "marker_pose_btn"):
            if hasattr(self, name):
                buttons.append(getattr(self, name))
        for button in buttons:
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
        json_enabled = bool(self.draw_json_var.get())

        if require_content and not text_enabled and not svg_enabled and not json_enabled:
            raise ValueError("Enable text, SVG, JSON, or a combination.")

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

        json_path = self.json_var.get().strip()
        if require_content and json_enabled:
            if not json_path:
                raise ValueError("JSON drawing is enabled, but no JSON file is selected.")
            if not Path(json_path).is_file():
                raise ValueError(f"JSON file does not exist:\n{json_path}")

        self._save_settings()
        return {
            "text_enabled": text_enabled,
            "svg_enabled": svg_enabled,
            "svg_colors": bool(self.svg_colors_var.get()) if svg_enabled else False,
            "svg_path": svg_path if svg_enabled else "",
            "json_enabled": json_enabled,
            "json_path": json_path if json_enabled else "",
            "json_top": float(self.json_top_var.get()),
            "json_width": float(self.json_width_var.get()),
            "json_height": float(self.json_height_var.get()),
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
            use_svg_colors=bool(config.get("svg_colors", False)),
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
                f"Text: {config['text_enabled']} | SVG: {config['svg_enabled']} "
                f"(colors={config.get('svg_colors', False)}) | JSON: {config.get('json_enabled', False)}"
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

    def _ask_ok_cancel_threadsafe(self, title: str, message: str) -> bool:
        result = {"value": False}
        event = threading.Event()
        def ask() -> None:
            if not self.closing:
                result["value"] = bool(messagebox.askokcancel(title, message))
            event.set()
        self.after(0, ask)
        while not event.wait(0.1):
            if self.closing:
                return False
        return bool(result["value"])

    def _require_prompt(self, title: str, message: str) -> None:
        if not self._ask_ok_cancel_threadsafe(title, message):
            raise RuntimeError("Operation cancelled by user.")
        if self.core.automation_stop_requested:
            raise RuntimeError("Operation stopped.")

    def _marker_pick(self) -> None:
        self._start_worker("Picking marker", self._task_marker_pick, require_content=False, log_drawer_context=False)

    def _marker_handoff(self) -> None:
        self._start_worker("Marker handoff", self._task_marker_handoff, require_content=False, log_drawer_context=False)

    def _marker_return(self) -> None:
        self._start_worker("Returning marker to holder", self._task_marker_return, require_content=False, log_drawer_context=False)

    def _check_marker_pose(self) -> None:
        try:
            if not self.core.connected:
                self._connect_robot()
            pose = self.core.marker_pose_name()
            self.status_var.set(f"Marker-route pose: {pose}")
            self._log(f"Marker-route pose: {pose}")
        except Exception as exc:
            messagebox.showerror("Marker pose", str(exc))

    def _task_marker_pick(self, config: dict) -> None:
        # R3 / GUI Pick Marker intentionally has no "is the marker present?"
        # confirmation. Pressing the action means: go pick it now.
        self.core.marker_pick_to_handoff()
        self._require_prompt(
            "Remove marker cap",
            "Remove the cap from the marker while the robot holds it.\n\n"
            "Press OK when the cap is off.",
        )
        self.core.marker_to_draw_ready_from_handoff()
        self._log("Marker picked, cap removed, and marker Draw Ready reached.")

    def _task_marker_handoff(self, config: dict) -> None:
        self.core.marker_handoff()
        self._require_prompt(
            "Marker handoff",
            "The marker is at the user handoff position.\n\n"
            "Press OK when you are finished with the marker/cap interaction.",
        )
        self.core.marker_to_draw_ready_from_handoff()

    def _task_marker_return(self, config: dict) -> None:
        self.core.marker_return_to_holder()

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
        if config["json_enabled"]:
            groups = load_web_json_paths(
                config["json_path"],
                config["json_width"],
                config["json_height"],
                config["json_top"],
            )
            paths = [p for cid in MARKER_COLOR_ORDER for p in groups.get(cid, [])]
            self._log(f'Preflighting JSON: {Path(config["json_path"]).name}')
            drawer.preflight_paths(paths, "JSON")

    def _collect_color_groups(self, config: dict, drawer: XArmSVGDrawer) -> Dict[str, List[Path3D]]:
        groups: Dict[str, List[Path3D]] = {}

        def add(color_id: str, paths: Sequence[Path3D]) -> None:
            if paths:
                groups.setdefault(color_id, []).extend(paths)

        # JSON color handling is always automatic.
        if config["json_enabled"]:
            json_groups = load_web_json_paths(
                config["json_path"],
                config["json_width"],
                config["json_height"],
                config["json_top"],
            )
            for cid, paths in json_groups.items():
                add(cid, paths)

        # SVG color handling is opt-in. If an automatic color workflow is already
        # active because JSON is enabled, a non-color SVG is treated as Black.
        if config["svg_enabled"]:
            if config["svg_colors"]:
                for cid, paths in drawer.paths_by_color.items():
                    add(cid, paths)
            elif config["json_enabled"]:
                add(DEFAULT_MARKER_COLOR, drawer.paths)

        # Text has no separate color selector; in an automatic color workflow it
        # becomes Black so the marker cycle remains deterministic.
        if config["text_enabled"] and (config["json_enabled"] or config["svg_colors"]):
            add(DEFAULT_MARKER_COLOR, build_heading_paths(config["text"]))

        return groups

    def _draw_color_groups(
        self,
        drawer: XArmSVGDrawer,
        groups: Dict[str, List[Path3D]],
    ) -> None:
        used = [cid for cid in MARKER_COLOR_ORDER if groups.get(cid)]
        if not used:
            return

        self._log(
            "Drawing colors: "
            + ", ".join(marker_color_name(cid) for cid in used)
        )

        for index, cid in enumerate(used, start=1):
            name = marker_color_name(cid)

            # This prompt is not a generic "is a marker there?" confirmation;
            # it tells the operator which physical color the robot needs next.
            self._require_prompt(
                f"Marker {index}/{len(used)} — {name}",
                f"Put the capped {name} Fiorello marker in the pickup holder.\n\n"
                "Press OK and the robot will immediately pick it up.",
            )

            self.core.marker_pick_to_handoff()
            self._require_prompt(
                f"Remove {name} cap",
                f"Remove the cap from the {name} marker while the robot holds it.\n\n"
                "Press OK when the cap is off.",
            )
            self.core.marker_to_draw_ready_from_handoff()

            self._log(
                f"Drawing color: {name} ({len(groups[cid])} paths)"
            )
            drawer.draw_paths(groups[cid], f"{name} drawing")

            # The drawing finishes on the safe wall plane. Return Cartesian to
            # the marker-compatible Draw Ready and verify the wrist branch.
            self.core.marker_return_from_wall_to_draw_ready()
            self.core.marker_handoff()

            self._require_prompt(
                f"Replace {name} cap",
                f"Put the cap back onto the {name} marker while the robot holds it.\n\n"
                "Press OK when the cap is secure.",
            )
            self.core.marker_to_draw_ready_from_handoff()
            self.core.marker_return_to_holder()

        self._log(
            "Colored drawing finished. Final marker returned to the holder; "
            "robot is at PICK_ABOVE."
        )

    def _task_draw(self, config: dict) -> None:
        drawer = self._make_drawer(config)
        drawer.connect()
        self._log(f"Contact X offset = {CONTACT_X_OFFSET_MM:.2f} mm")

        auto_colors = bool(config["json_enabled"] or config["svg_colors"])
        if auto_colors:
            groups = self._collect_color_groups(config, drawer)
            self._draw_color_groups(drawer, groups)
            return

        # Plain current-marker mode: preserve the existing behavior.
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
