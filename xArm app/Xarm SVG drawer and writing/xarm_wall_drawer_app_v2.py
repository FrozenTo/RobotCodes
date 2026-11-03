"""
xArm wall SVG drawer.

Uses the same SVG parsing approach that worked for the MG400 drawing, but the
robot-side geometry is much simpler:

    SVG x -> paper left/right -> xArm Y
    SVG y -> paper top/bottom -> xArm Z
    paper surface depth       -> xArm X

The four measured paper corners are used with bilinear interpolation, so the
contact X follows the real wall/paper plane rather than assuming one fixed X.

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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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
# MEASURED PAPER CORNERS (marker touching paper)
# ============================================================
#
#              TOP
#       TL ------------- TR
#       |                 |
#       |                 |
#       BL ------------- BR
#             BOTTOM
#
# Wall direction is -X.
# +Y moves right across the paper.
# +Z moves up the paper.
# ============================================================

# New 8-point contact calibration (23.09.2026).
# These are marker-contact poses taken around the reachable paper boundary.
PAPER_TL: Point3D = (-487.7, -67.8, 741.4) 
PAPER_TM: Point3D = (-484.6, 107.5, 732.7)
PAPER_TR: Point3D = (-482, 291.6, 721.9)

PAPER_ML: Point3D = (-487.7, -67.4, 619.8)
PAPER_MR: Point3D = (-482.9, 292.9, 613.6)

PAPER_BL: Point3D = (-487.7, -67.8, 499.2)
PAPER_BM: Point3D = (-485.3, 113.0, 494.1)
PAPER_BR: Point3D = (-482.7, 291.2, 494.1)

# Effective calibrated drawing surface dimensions.
# Horizontal edge length is ~359.6 mm.
# Average reachable vertical edge length is ~235.0 mm because the top-right
# reachable point is slightly lower than the physical edge.
PAPER_WIDTH_MM = 359.6
PAPER_HEIGHT_MM = 235.0

# Leave margins instead of using every last mm of paper.
MAX_DRAWING_WIDTH_MM = 330.0
MAX_DRAWING_HEIGHT_MM = 185.0

# Place the building lower instead of vertically centering it.
# This leaves room for the heading at the top-left.
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

def bilinear_paper_point(u: float, v: float) -> Point3D:
    """
    8-point curved-surface interpolation.

    u: 0 = calibrated left edge, 1 = calibrated right edge
    v: 0 = calibrated top edge,  1 = calibrated bottom edge

    The old version used only 4 corners and a bilinear plane.
    This version also uses top/bottom/left/right midpoint contact measurements.

    Each boundary is fitted as a quadratic curve through:
        endpoint -> measured midpoint -> endpoint

    Then a Coons patch blends all four boundaries across the interior.

    This means all 8 measured edge contact poses are reproduced exactly.
    """

    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))

    def add(a: Point3D, b: Point3D) -> Point3D:
        return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

    def sub(a: Point3D, b: Point3D) -> Point3D:
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def mul(a: Point3D, s: float) -> Point3D:
        return (a[0] * s, a[1] * s, a[2] * s)

    def quadratic_through_mid(
        p0: Point3D,
        pm: Point3D,
        p1: Point3D,
        t: float,
    ) -> Point3D:
        """
        Quadratic Lagrange interpolation through:
            t=0.0 -> p0
            t=0.5 -> pm
            t=1.0 -> p1
        """
        w0 = 2.0 * (t - 0.5) * (t - 1.0)
        wm = -4.0 * t * (t - 1.0)
        w1 = 2.0 * t * (t - 0.5)

        return (
            p0[0] * w0 + pm[0] * wm + p1[0] * w1,
            p0[1] * w0 + pm[1] * wm + p1[1] * w1,
            p0[2] * w0 + pm[2] * wm + p1[2] * w1,
        )

    # Four measured curved boundaries.
    top = quadratic_through_mid(PAPER_TL, PAPER_TM, PAPER_TR, u)
    bottom = quadratic_through_mid(PAPER_BL, PAPER_BM, PAPER_BR, u)
    left = quadratic_through_mid(PAPER_TL, PAPER_ML, PAPER_BL, v)
    right = quadratic_through_mid(PAPER_TR, PAPER_MR, PAPER_BR, v)

    # Blend the four boundary curves.
    boundary_blend = add(
        add(mul(top, 1.0 - v), mul(bottom, v)),
        add(mul(left, 1.0 - u), mul(right, u)),
    )

    # Subtract the corner contribution that was counted twice.
    corner_blend = add(
        add(
            mul(PAPER_TL, (1.0 - u) * (1.0 - v)),
            mul(PAPER_TR, u * (1.0 - v)),
        ),
        add(
            mul(PAPER_BL, (1.0 - u) * v),
            mul(PAPER_BR, u * v),
        ),
    )

    x, y, z = sub(boundary_blend, corner_blend)

    return (x + CONTACT_X_OFFSET_MM, y, z)

def safe_point(contact: Point3D) -> Point3D:
    """Same Y/Z as contact point, but pulled away from the wall to SAFE_X."""
    _, y, z = contact
    return (SAFE_X, y, z)


def point3_distance(a: Point3D, b: Point3D) -> float:
    return math.sqrt(
        (b[0] - a[0]) ** 2
        + (b[1] - a[1]) ** 2
        + (b[2] - a[2]) ** 2
    )



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


def paper_mm_to_contact(right_mm: float, down_mm: float) -> Point3D:
    """Map physical paper coordinates to the calibrated 3D surface."""
    u = right_mm / PAPER_WIDTH_MM
    v = down_mm / PAPER_HEIGHT_MM
    return bilinear_paper_point(u, v)


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
    def __init__(self, settings: Optional[XArmSVGSettings] = None):
        self.settings = settings or XArmSVGSettings()
        self.arm: Optional[XArmAPI] = None
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
                u = (left_margin_mm + right_mm) / PAPER_WIDTH_MM
                v = (top_margin_mm + down_mm) / PAPER_HEIGHT_MM
                path3d.append(bilinear_paper_point(u, v))

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

    # ------------------------------------------------------------
    # xARM CONNECTION / MOVEMENT
    # ------------------------------------------------------------

    @staticmethod
    def _check_code(code: int, action: str) -> None:
        if code != 0:
            raise RuntimeError(f"xArm error during {action}: code={code}")

    def connect(self) -> None:
        print(f"Connecting to xArm at {ROBOT_IP}...")
        self.arm = XArmAPI(ROBOT_IP, is_radian=False)

        # Clear stale state, then enable normal position mode.
        self.arm.clean_warn()
        self.arm.clean_error()
        self._check_code(self.arm.motion_enable(enable=True), "motion_enable")
        self._check_code(self.arm.set_mode(0), "set_mode(0)")
        self._check_code(self.arm.set_state(0), "set_state(0)")

        print("Connected and enabled.")

    def disconnect(self) -> None:
        if self.arm is not None:
            try:
                self.arm.disconnect()
            finally:
                self.arm = None
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
        print("Contact surface is interpolated from 8 measured edge contact points.")

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
# TKINTER APP
# ============================================================

class XArmWallDrawerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("xArm SVG + Text Wall Drawer")
        self.geometry("900x760")
        self.minsize(820, 680)

        self.worker: Optional[threading.Thread] = None

        self._build_variables()
        self._build_ui()

    # --------------------------------------------------------
    # Variables
    # --------------------------------------------------------

    def _build_variables(self) -> None:
        self.ip_var = tk.StringVar(value=ROBOT_IP)
        self.offset_var = tk.DoubleVar(value=CONTACT_X_OFFSET_MM)

        # Editable initial / ready joint pose.
        self.ready_joint_vars = [
            tk.DoubleVar(value=value) for value in READY_JOINTS
        ]

        self.write_text_var = tk.BooleanVar(value=True)
        self.text_var = tk.StringVar(value="HELLO NARVA!")
        self.text_left_var = tk.DoubleVar(value=HEADING_LEFT_MM)
        self.text_top_var = tk.DoubleVar(value=HEADING_TOP_MM)
        self.text_height_var = tk.DoubleVar(value=HEADING_HEIGHT_MM)
        self.text_speed_var = tk.DoubleVar(value=HEADING_SPEED)

        self.draw_svg_var = tk.BooleanVar(value=True)
        default_svg = str(
            (Path(__file__).resolve().parent / SVG_FILE).resolve()
        )
        self.svg_var = tk.StringVar(value=default_svg)
        self.svg_top_var = tk.DoubleVar(value=SVG_TOP_MARGIN_MM)
        self.svg_width_var = tk.DoubleVar(value=MAX_DRAWING_WIDTH_MM)
        self.svg_height_var = tk.DoubleVar(value=MAX_DRAWING_HEIGHT_MM)
        self.draw_speed_var = tk.DoubleVar(value=DRAW_SPEED)

        self.move_ready_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="Ready")

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        root.columnconfigure(0, weight=1)
        root.rowconfigure(5, weight=1)

        # ROBOT -------------------------------------------------
        robot = ttk.LabelFrame(root, text="Robot / Pen contact", padding=10)
        robot.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        robot.columnconfigure(1, weight=1)

        ttk.Label(robot, text="Robot IP").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(robot, textvariable=self.ip_var, width=22).grid(
            row=0, column=1, sticky="w", pady=4
        )

        ttk.Label(robot, text="Contact X offset (mm)").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )

        offset_frame = ttk.Frame(robot)
        offset_frame.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Spinbox(
            offset_frame,
            from_=-20.0,
            to=5.0,
            increment=0.1,
            textvariable=self.offset_var,
            width=10,
        ).pack(side="left")

        ttk.Button(
            offset_frame,
            text="-0.5",
            width=7,
            command=lambda: self._nudge_offset(-0.5),
        ).pack(side="left", padx=(8, 3))

        ttk.Button(
            offset_frame,
            text="+0.5",
            width=7,
            command=lambda: self._nudge_offset(0.5),
        ).pack(side="left", padx=3)

        ttk.Label(
            robot,
            text="More negative = farther toward the paper / more marker pressure.",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # INITIAL / READY POSE ---------------------------------
        ready_box = ttk.LabelFrame(root, text="Initial / Ready position", padding=10)
        ready_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(
            ready_box,
            text="Joint pose used before preflight/drawing (degrees)",
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))

        for i, var in enumerate(self.ready_joint_vars):
            joint_frame = ttk.Frame(ready_box)
            joint_frame.grid(row=1, column=i, padx=(0 if i == 0 else 6, 0), sticky="w")

            ttk.Label(joint_frame, text=f"J{i + 1}").pack(anchor="w")
            ttk.Spinbox(
                joint_frame,
                from_=-360.0,
                to=360.0,
                increment=0.1,
                textvariable=var,
                width=9,
            ).pack(anchor="w")

        ready_buttons = ttk.Frame(ready_box)
        ready_buttons.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))

        ttk.Button(
            ready_buttons,
            text="Read current robot joints",
            command=self._read_current_joints,
        ).pack(side="left", padx=(0, 8))

        ttk.Label(
            ready_buttons,
            text="Use this after manually moving the robot to a good start pose.",
        ).pack(side="left")

        # TEXT --------------------------------------------------
        text_box = ttk.LabelFrame(root, text="Text", padding=10)
        text_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        text_box.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            text_box,
            text="Write text before SVG",
            variable=self.write_text_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ttk.Label(text_box, text="Text").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(text_box, textvariable=self.text_var).grid(
            row=1, column=1, columnspan=3, sticky="ew", pady=4
        )

        ttk.Label(text_box, text="Left (mm)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(
            text_box, from_=0, to=PAPER_WIDTH_MM, increment=1,
            textvariable=self.text_left_var, width=9
        ).grid(row=2, column=1, sticky="w", padx=(0, 12))

        ttk.Label(text_box, text="Top (mm)").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(
            text_box, from_=0, to=PAPER_HEIGHT_MM, increment=1,
            textvariable=self.text_top_var, width=9
        ).grid(row=2, column=3, sticky="w")

        ttk.Label(text_box, text="Height (mm)").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(
            text_box, from_=5, to=60, increment=1,
            textvariable=self.text_height_var, width=9
        ).grid(row=3, column=1, sticky="w", padx=(0, 12))

        ttk.Label(text_box, text="Speed (mm/s)").grid(row=3, column=2, sticky="w")
        ttk.Spinbox(
            text_box, from_=5, to=300, increment=5,
            textvariable=self.text_speed_var, width=9
        ).grid(row=3, column=3, sticky="w")

        ttk.Label(
            text_box,
            text="Supported: A-Z, Ä Ö Ü Õ, space, ! ? .  Lowercase becomes uppercase.",
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(5, 0))

        # SVG ---------------------------------------------------
        svg_box = ttk.LabelFrame(root, text="SVG drawing", padding=10)
        svg_box.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        svg_box.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            svg_box,
            text="Draw SVG",
            variable=self.draw_svg_var,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        ttk.Label(svg_box, text="SVG file").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(svg_box, textvariable=self.svg_var).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=4
        )
        ttk.Button(svg_box, text="Browse…", command=self._browse_svg).grid(
            row=1, column=3, padx=(8, 0), pady=4
        )

        ttk.Label(svg_box, text="Top margin (mm)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(
            svg_box, from_=0, to=PAPER_HEIGHT_MM, increment=1,
            textvariable=self.svg_top_var, width=9
        ).grid(row=2, column=1, sticky="w", padx=(0, 12))

        ttk.Label(svg_box, text="Draw speed (mm/s)").grid(row=2, column=2, sticky="w")
        ttk.Spinbox(
            svg_box, from_=5, to=500, increment=5,
            textvariable=self.draw_speed_var, width=9
        ).grid(row=2, column=3, sticky="w")

        ttk.Label(svg_box, text="Max width (mm)").grid(row=3, column=0, sticky="w")
        ttk.Spinbox(
            svg_box, from_=20, to=PAPER_WIDTH_MM, increment=5,
            textvariable=self.svg_width_var, width=9
        ).grid(row=3, column=1, sticky="w", padx=(0, 12))

        ttk.Label(svg_box, text="Max height (mm)").grid(row=3, column=2, sticky="w")
        ttk.Spinbox(
            svg_box, from_=20, to=PAPER_HEIGHT_MM, increment=5,
            textvariable=self.svg_height_var, width=9
        ).grid(row=3, column=3, sticky="w")

        # CONTROLS ----------------------------------------------
        controls = ttk.LabelFrame(root, text="Run", padding=10)
        controls.grid(row=4, column=0, sticky="ew", pady=(0, 8))

        ttk.Checkbutton(
            controls,
            text="Move to ready pose first",
            variable=self.move_ready_var,
        ).pack(side="left", padx=(0, 12))

        self.ready_btn = ttk.Button(
            controls, text="Move Ready", command=self._move_ready
        )
        self.ready_btn.pack(side="left", padx=4)

        self.preflight_btn = ttk.Button(
            controls, text="Preflight (pen away)", command=self._preflight
        )
        self.preflight_btn.pack(side="left", padx=4)

        self.draw_btn = ttk.Button(
            controls, text="Start drawing", command=self._draw
        )
        self.draw_btn.pack(side="left", padx=4)

        # LOG ---------------------------------------------------
        log_box = ttk.LabelFrame(root, text="Status", padding=8)
        log_box.grid(row=5, column=0, sticky="nsew")
        log_box.columnconfigure(0, weight=1)
        log_box.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_box, height=12, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(
            log_box, orient="vertical", command=self.log_text.yview
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        ttk.Label(root, textvariable=self.status_var).grid(
            row=6, column=0, sticky="w", pady=(6, 0)
        )

        self._log("App ready.")
        self._log(f"Current contact X offset: {self.offset_var.get():.1f} mm")

    # --------------------------------------------------------
    # GUI helpers
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

    def _read_current_joints(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showwarning(
                "Robot busy",
                "A robot operation is already running.",
            )
            return

        robot_ip = self.ip_var.get().strip()
        if not robot_ip:
            messagebox.showerror("Invalid settings", "Robot IP cannot be empty.")
            return

        self._set_busy(True)
        self.status_var.set("Reading current joints")
        self._log("")
        self._log("--- Reading current robot joints ---")

        def worker():
            arm = None
            try:
                arm = XArmAPI(robot_ip, is_radian=False)
                code, angles = arm.get_servo_angle(is_radian=False)
                if code != 0:
                    raise RuntimeError(
                        f"Could not read current joints: xArm code={code}"
                    )

                if angles is None or len(angles) < 6:
                    raise RuntimeError(
                        f"Unexpected joint response: {angles}"
                    )

                values = [float(v) for v in angles[:6]]

                def apply_values():
                    for var, value in zip(self.ready_joint_vars, values):
                        var.set(round(value, 2))
                    self.status_var.set("Ready")

                self.after(0, apply_values)
                self._log(
                    "Current joints: "
                    + ", ".join(f"J{i+1}={v:.2f}°" for i, v in enumerate(values))
                )

            except Exception as exc:
                self._log(f"ERROR: {exc}")
                self._show_error("Could not read joints", str(exc))
                self.after(0, lambda: self.status_var.set("Error"))
            finally:
                if arm is not None:
                    try:
                        arm.disconnect()
                    except Exception:
                        pass
                self.after(0, lambda: self._set_busy(False))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _log(self, message: str) -> None:
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message.rstrip() + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, append)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (self.ready_btn, self.preflight_btn, self.draw_btn):
            button.configure(state=state)

    def _show_error(self, title: str, message: str) -> None:
        self.after(0, lambda: messagebox.showerror(title, message))

    # --------------------------------------------------------
    # Read / validate GUI settings
    # --------------------------------------------------------

    def _apply_gui_settings(self) -> dict:
        global ROBOT_IP
        global CONTACT_X_OFFSET_MM
        global READY_JOINTS
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

        READY_JOINTS = [
            float(var.get()) for var in self.ready_joint_vars
        ]

        text_enabled = bool(self.write_text_var.get())
        svg_enabled = bool(self.draw_svg_var.get())

        if not text_enabled and not svg_enabled:
            raise ValueError("Enable text, SVG, or both.")

        HEADING_TEXT = self.text_var.get()
        HEADING_LEFT_MM = float(self.text_left_var.get())
        HEADING_TOP_MM = float(self.text_top_var.get())
        HEADING_HEIGHT_MM = float(self.text_height_var.get())

        # Preserve the proportions of the working 18 x 10 mm lettering.
        HEADING_WIDTH_MM = HEADING_HEIGHT_MM * (10.0 / 18.0)
        HEADING_GAP_MM = HEADING_HEIGHT_MM * (3.5 / 18.0)
        HEADING_SPACE_MM = HEADING_HEIGHT_MM * (8.0 / 18.0)
        HEADING_SPEED = float(self.text_speed_var.get())

        if text_enabled and not HEADING_TEXT.strip():
            raise ValueError("Text is enabled, but the text box is empty.")

        SVG_TOP_MARGIN_MM = float(self.svg_top_var.get())
        MAX_DRAWING_WIDTH_MM = float(self.svg_width_var.get())
        MAX_DRAWING_HEIGHT_MM = float(self.svg_height_var.get())
        DRAW_SPEED = float(self.draw_speed_var.get())

        svg_path = self.svg_var.get().strip()
        if svg_enabled:
            if not svg_path:
                raise ValueError("SVG drawing is enabled, but no SVG file is selected.")
            if not Path(svg_path).is_file():
                raise ValueError(f"SVG file does not exist:\n{svg_path}")

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
        return XArmSVGDrawer(settings)

    # --------------------------------------------------------
    # Worker handling
    # --------------------------------------------------------

    def _start_worker(self, label: str, func) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showwarning(
                "Robot busy",
                "A robot operation is already running.",
            )
            return

        try:
            config = self._apply_gui_settings()
        except Exception as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        self._set_busy(True)
        self.status_var.set(label)
        self._log("")
        self._log(f"--- {label} ---")
        self._log(
            f"X offset: {CONTACT_X_OFFSET_MM:.2f} mm | "
            f"Text: {config['text_enabled']} | SVG: {config['svg_enabled']}"
        )
        self._log(
            "Ready joints: "
            + ", ".join(
                f"J{i+1}={value:.1f}°"
                for i, value in enumerate(READY_JOINTS)
            )
        )

        def worker():
            try:
                func(config)
                self._log(f"{label}: finished.")
                self.after(0, lambda: self.status_var.set("Ready"))
            except Exception as exc:
                self._log(f"ERROR: {exc}")
                self._log(traceback.format_exc())
                self._show_error("Robot operation failed", str(exc))
                self.after(0, lambda: self.status_var.set("Error"))
            finally:
                self.after(0, lambda: self._set_busy(False))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    # --------------------------------------------------------
    # Robot tasks
    # --------------------------------------------------------

    def _move_ready(self) -> None:
        self._start_worker("Moving to ready pose", self._task_move_ready)

    def _preflight(self) -> None:
        self._start_worker("Preflight", self._task_preflight)

    def _draw(self) -> None:
        self._start_worker("Drawing", self._task_draw)

    def _task_move_ready(self, config: dict) -> None:
        # No SVG needs to be parsed just to move ready.
        drawer = XArmSVGDrawer(
            XArmSVGSettings(svg_file="")
        )
        drawer.connect()
        try:
            self._log("Connected.")
            drawer.move_ready()
            self._log("Ready pose reached.")
        finally:
            drawer.disconnect()

    def _task_preflight(self, config: dict) -> None:
        drawer = self._make_drawer(config)
        drawer.connect()

        try:
            self._log("Connected.")

            if config["move_ready"]:
                drawer.move_ready()
                self._log("Ready pose reached.")

            if config["text_enabled"]:
                self._log(f'Preflighting text: "{config["text"]}"')
                drawer.preflight_heading(config["text"])

            if config["svg_enabled"]:
                self._log(
                    f'Preflighting SVG: {Path(config["svg_path"]).name}'
                )
                drawer.preflight()

        finally:
            drawer.disconnect()

    def _task_draw(self, config: dict) -> None:
        drawer = self._make_drawer(config)
        drawer.connect()

        try:
            self._log("Connected.")
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

        finally:
            drawer.disconnect()


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":
    app = XArmWallDrawerApp()
    app.mainloop()
