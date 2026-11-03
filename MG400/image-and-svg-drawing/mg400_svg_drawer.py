
"""
MG400 SVG drawer with:
- direct SVG import
- support for translate(...) and matrix(...) transforms
- support for nested group transforms
- path flattening (lines, curves, arcs)
- scaling/centering into the measured MG400 paper area
- the existing IK / J2 / J4 safety planning
- continuous drawing when connected pieces keep the same R

This file is intentionally separate from:
    mg400_writer.py
    mg400_writer_app.py

Expected workflow:
1) Put your SVG path into SVG_FILE
2) Test with:
       LIVE_ROBOT = True
       PREFLIGHT_ONLY = True
3) If preflight succeeds:
       PREFLIGHT_ONLY = False
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from mg400_writer import MG400Writer


Point2D = Tuple[float, float]
Polyline = List[Point2D]


# ============================================================
# USER SETTINGS
# ============================================================

ROBOT_IP = "192.168.1.6"
LIVE_ROBOT = True
PREFLIGHT_ONLY = False

# Update this later when you make a newer SVG.
SVG_FILE = "C:\\Users\\user.NK-009\\Desktop\\drawing.svg"


# ============================================================
# MEASURED PEN / ROBOT GEOMETRY
# ============================================================

PEN_RADIUS_MM = 56

# NOTE:
# The 1 mm R-transition correction has NOT been applied here yet.
# This file still uses 26.0 like the previous versions.
# Later, if you want to test the correction, try e.g. 25.3.
PEN_ANGLE_OFFSET_DEG = 26.0


# ============================================================
# MEASURED PAPER / SAFE AREA
# ============================================================

PAPER_TOP_X = 260.0
PAPER_BOTTOM_X = 383.0

PAPER_LEFT_Y = -123.0
PAPER_RIGHT_Y = 137.0

PAPER_WIDTH_MM = PAPER_RIGHT_Y - PAPER_LEFT_Y
PAPER_HEIGHT_MM = PAPER_BOTTOM_X - PAPER_TOP_X


# ============================================================
# DRAWING SETTINGS
# ============================================================

TEST_DRAWING_WIDTH_MM = 220.0
TEST_DRAWING_HEIGHT_MM = 100.0

# SVG cleanup / simplification
MIN_PATH_LENGTH_MM = 2.5
SIMPLIFY_TOLERANCE_MM = 0.45

# Curve and arc flattening (in SVG units before final scaling)
CURVE_TARGET_STEP_UNITS = 3.0
ARC_TARGET_STEP_UNITS = 3.0

# Split long final pen segments before IK planning.
MAX_SEGMENT_MM = 10.0

PLAN_PROGRESS_EVERY = 20


# ============================================================
# SAFE R ORIENTATIONS FOUND EXPERIMENTALLY
# ============================================================

R_TOP_LEFT = -162.15
R_TOP_RIGHT = 107.45
R_BOTTOM_LEFT = -72.24
R_BOTTOM_RIGHT = 17.86
R_BOTTOM_EXTENSION = -27.24

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

J2_HARD_MIN = -25.0
J2_HARD_MAX = 85.0
J2_MARGIN_DEG = 2.0

J2_SAFE_MIN = J2_HARD_MIN + J2_MARGIN_DEG
J2_SAFE_MAX = J2_HARD_MAX - J2_MARGIN_DEG

J4_HARD_MIN = -177.0
J4_HARD_MAX = 120.0
J4_MARGIN_DEG = 5.0

J4_SAFE_MIN = J4_HARD_MIN + J4_MARGIN_DEG
J4_SAFE_MAX = J4_HARD_MAX - J4_MARGIN_DEG

WRITING_Z = -197.30


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
# DRAWER SETTINGS
# ============================================================

@dataclass
class DrawerSettings:
    svg_file: str = SVG_FILE
    drawing_width_mm: float = TEST_DRAWING_WIDTH_MM
    drawing_height_mm: float = TEST_DRAWING_HEIGHT_MM
    travel_lift_mm: float = 10.0
    min_path_length_mm: float = MIN_PATH_LENGTH_MM
    simplify_tolerance_mm: float = SIMPLIFY_TOLERANCE_MM


# ============================================================
# MG400 SVG DRAWER
# ============================================================

class MG400SVGDrawer:
    def __init__(
        self,
        writer: MG400Writer,
        settings: Optional[DrawerSettings] = None,
    ):
        self.writer = writer
        self.settings = settings or DrawerSettings()

        self.ik_cache: Dict[Tuple[float, float, float, float], Optional[Tuple[float, float, float, float]]] = {}
        self.scaled_paths: List[Polyline] = self.load_scaled_svg_paths()

    # ------------------------------------------------------------
    # PEN OFFSET
    # ------------------------------------------------------------

    @staticmethod
    def pen_offset_for_r(r_deg: float) -> Tuple[float, float]:
        angle = math.radians(r_deg + PEN_ANGLE_OFFSET_DEG)
        return (
            PEN_RADIUS_MM * math.cos(angle),
            PEN_RADIUS_MM * math.sin(angle),
        )

    @classmethod
    def flange_for_pen_tip(cls, pen_x: float, pen_y: float, r_deg: float) -> Tuple[float, float]:
        ox, oy = cls.pen_offset_for_r(r_deg)
        return (pen_x - ox, pen_y - oy)

    # ------------------------------------------------------------
    # PAPER AREA
    # ------------------------------------------------------------

    def test_area_origin(self) -> Tuple[float, float]:
        left_margin = (PAPER_WIDTH_MM - self.settings.drawing_width_mm) / 2.0
        top_margin = (PAPER_HEIGHT_MM - self.settings.drawing_height_mm) / 2.0

        top_x = PAPER_TOP_X + top_margin
        left_y = PAPER_LEFT_Y + left_margin
        return top_x, left_y

    def load_scaled_svg_paths(self) -> List[Polyline]:
        extractor = SVGExtractor(self.settings.svg_file)
        raw_paths, view_w, view_h = extractor.load()

        if not raw_paths:
            raise RuntimeError(f"No drawable paths found in SVG: {self.settings.svg_file}")

        all_points = [p for poly in raw_paths for p in poly]
        min_x = min(p[0] for p in all_points)
        max_x = max(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_y = max(p[1] for p in all_points)

        src_w = max_x - min_x
        src_h = max_y - min_y

        if src_w <= 0 or src_h <= 0:
            raise RuntimeError("SVG bounding box is degenerate.")

        scale = min(
            self.settings.drawing_width_mm / src_w,
            self.settings.drawing_height_mm / src_h,
        )

        final_w = src_w * scale
        final_h = src_h * scale

        top_x, left_y = self.test_area_origin()
        x_margin = (self.settings.drawing_height_mm - final_h) / 2.0
        y_margin = (self.settings.drawing_width_mm - final_w) / 2.0

        pen_top_x = top_x + x_margin
        pen_left_y = left_y + y_margin

        scaled: List[Polyline] = []

        for poly in raw_paths:
            transformed = []
            for x, y in poly:
                # SVG x -> robot paper +Y
                # SVG y -> robot paper +X
                pen_x = pen_top_x + (y - min_y) * scale
                pen_y = pen_left_y + (x - min_x) * scale
                transformed.append((pen_x, pen_y))

            transformed = remove_duplicate_neighbors(transformed)

            if len(transformed) < 2:
                continue

            if self.settings.simplify_tolerance_mm > 0:
                transformed = rdp(transformed, self.settings.simplify_tolerance_mm)
                transformed = remove_duplicate_neighbors(transformed)

            if len(transformed) < 2:
                continue

            if polyline_length(transformed) < self.settings.min_path_length_mm:
                continue

            scaled.append(transformed)

        self.writer.log(
            f"Loaded SVG: {self.settings.svg_file}\n"
            f"  raw paths: {len(raw_paths)}\n"
            f"  kept paths after simplification/filtering: {len(scaled)}\n"
            f"  source bbox: {src_w:.2f} x {src_h:.2f} svg units\n"
            f"  final drawing size: {final_w:.2f} x {final_h:.2f} mm"
        )

        return scaled

    # ------------------------------------------------------------
    # SEGMENT PREPARATION
    # ------------------------------------------------------------

    @staticmethod
    def subdivide_segment(start: Point2D, end: Point2D, max_length: float = MAX_SEGMENT_MM) -> List[Point2D]:
        total = distance(start, end)

        if total <= max_length:
            return [start, end]

        steps = max(1, int(math.ceil(total / max_length)))
        return [
            (
                start[0] + (end[0] - start[0]) * i / steps,
                start[1] + (end[1] - start[1]) * i / steps,
            )
            for i in range(steps + 1)
        ]

    def iter_pen_segments(self):
        for path_index, path in enumerate(self.scaled_paths, start=1):
            for edge_index, (a, b) in enumerate(zip(path, path[1:]), start=1):
                subdivided = self.subdivide_segment(a, b)
                for short_index, (s, e) in enumerate(zip(subdivided, subdivided[1:]), start=1):
                    yield (
                        path_index,
                        edge_index,
                        short_index,
                        s,
                        e,
                    )

    # ------------------------------------------------------------
    # IK / PLANNING
    # ------------------------------------------------------------

    @staticmethod
    def _parse_robot_values(response: str) -> Tuple[int, List[float]]:
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
        self,
        flange_x: float,
        flange_y: float,
        z: float,
        r_deg: float,
    ) -> Optional[Tuple[float, float, float, float]]:
        if not self.writer.settings.live_robot:
            raise RuntimeError("InverseSolution planning requires LIVE_ROBOT=True")

        key = (
            round(flange_x, 3),
            round(flange_y, 3),
            round(z, 3),
            round(r_deg, 3),
        )

        if key in self.ik_cache:
            return self.ik_cache[key]

        cmd = f"InverseSolution({flange_x:.3f},{flange_y:.3f},{z:.3f},{r_deg:.3f},0,0)"
        response = self.writer.send_dashboard(cmd)
        error_id, values = self._parse_robot_values(response)

        if error_id != 0 or len(values) < 4:
            self.ik_cache[key] = None
            return None

        result = (values[0], values[1], values[2], values[3])
        self.ik_cache[key] = result
        return result

    @staticmethod
    def joint_pose_is_safe(joints: Tuple[float, float, float, float]) -> bool:
        _, j2, _, j4 = joints
        return (
            J2_SAFE_MIN <= j2 <= J2_SAFE_MAX
            and J4_SAFE_MIN <= j4 <= J4_SAFE_MAX
        )

    @staticmethod
    def joint_safety_score(joints: Tuple[float, float, float, float]) -> float:
        _, j2, _, j4 = joints
        j2_margin = min(j2 - J2_SAFE_MIN, J2_SAFE_MAX - j2)
        j4_margin = min(j4 - J4_SAFE_MIN, J4_SAFE_MAX - j4)
        return min(j2_margin, j4_margin)

    def evaluate_r_for_segment(
        self,
        start: Point2D,
        end: Point2D,
        r_deg: float,
    ):
        samples = []

        for pen_x, pen_y in (start, end):
            flange_x, flange_y = self.flange_for_pen_tip(pen_x, pen_y, r_deg)

            joints = self.inverse_solution(flange_x, flange_y, WRITING_Z, r_deg)
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

    def choose_safe_r(self, start: Point2D, end: Point2D, previous_r: Optional[float]):
        valid = []

        for r_deg in R_CANDIDATES:
            result = self.evaluate_r_for_segment(start, end, r_deg)
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
        raw_segments = list(self.iter_pen_segments())

        planned = []
        previous_r = None
        worst_score = float("inf")
        worst_info = None
        total_segments = len(raw_segments)

        self.writer.log(
            f"IK planning {total_segments} short segments at writing Z={WRITING_Z:.2f}..."
        )

        for index, (path_index, edge_index, short_index, start, end) in enumerate(raw_segments, start=1):
            if index == 1 or index % PLAN_PROGRESS_EVERY == 0 or index == total_segments:
                percent = 100.0 * index / total_segments
                self.writer.log(f"PLANNING: {index}/{total_segments} segments ({percent:.0f}%)")

            choice = self.choose_safe_r(start, end, previous_r)

            if choice is None:
                raise RuntimeError(
                    "\nNO SAFE R FOUND before robot movement.\n"
                    f"Segment {index}/{total_segments}\n"
                    f"Path={path_index}, edge={edge_index}, subsegment={short_index}\n"
                    f"Pen start=({start[0]:.2f}, {start[1]:.2f})\n"
                    f"Pen end=({end[0]:.2f}, {end[1]:.2f})\n"
                    f"Checked J2 safe range {J2_SAFE_MIN:.1f}..{J2_SAFE_MAX:.1f} deg and "
                    f"J4 safe range {J4_SAFE_MIN:.1f}..{J4_SAFE_MAX:.1f} deg."
                )

            planned.append({
                "index": index,
                "path_index": path_index,
                "edge_index": edge_index,
                "short_index": short_index,
                "start": start,
                "end": end,
                "r": choice["r"],
                "score": choice["score"],
            })

            if choice["score"] < worst_score:
                worst_score = choice["score"]
                worst_info = planned[-1]

            previous_r = choice["r"]

        self.writer.log(f"IK PLAN OK: all {len(planned)} segments have a safe J2/J4 solution.")
        if worst_info is not None:
            self.writer.log(
                f"Smallest planned joint margin: {worst_score:.2f} deg "
                f"at segment {worst_info['index']} (R={worst_info['r']:.2f} deg)."
            )

        return planned

    def get_joint_angles(self) -> Tuple[float, float, float, float]:
        response = self.writer.send_dashboard("GetAngle()")
        error_id, values = self._parse_robot_values(response)
        if error_id != 0 or len(values) < 4:
            raise ValueError(f"Could not read GetAngle(): {response}")
        return (values[0], values[1], values[2], values[3])

    def check_actual_joints(self, context: str = ""):
        if not self.writer.settings.live_robot:
            return

        j1, j2, j3, j4 = self.get_joint_angles()
        self.writer.log(
            f"Actual joints {context}: "
            f"J1={j1:.2f}, J2={j2:.2f}, J3={j3:.2f}, J4={j4:.2f}"
        )

        if not (J2_SAFE_MIN <= j2 <= J2_SAFE_MAX):
            raise RuntimeError(f"J2 runtime safety stop: {j2:.2f} deg")

        if not (J4_SAFE_MIN <= j4 <= J4_SAFE_MAX):
            raise RuntimeError(f"J4 runtime safety stop: {j4:.2f} deg")

    # ------------------------------------------------------------
    # CONTINUOUS STROKES
    # ------------------------------------------------------------

    @staticmethod
    def _same_point(a: Point2D, b: Point2D, tolerance_mm: float = 0.01) -> bool:
        return abs(a[0] - b[0]) <= tolerance_mm and abs(a[1] - b[1]) <= tolerance_mm

    def combine_into_strokes(self, planned):
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
                and self._same_point(current["points"][-1], segment["start"])
            )

            if continuous:
                current["points"].append(segment["end"])
                current["score"] = min(current["score"], segment["score"])
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

    # ------------------------------------------------------------
    # MOTION
    # ------------------------------------------------------------

    def sync_motion(self) -> None:
        if self.writer.settings.live_robot:
            self.writer.send_motion("Sync()")

    def move_flange_above_pen_tip(self, pen_x: float, pen_y: float, r_deg: float, lifted_z: float) -> None:
        flange_x, flange_y = self.flange_for_pen_tip(pen_x, pen_y, r_deg)
        self.writer.send_motion(
            f"MovJ({flange_x:.3f},{flange_y:.3f},{lifted_z:.3f},{r_deg:.3f})"
        )

    def preflight(self, planned=None) -> None:
        lifted_z = WRITING_Z + self.settings.travel_lift_mm

        if planned is None:
            planned = self.plan_all_segments()

        strokes = self.combine_into_strokes(planned)

        self.writer.log(
            f"Starting PHYSICAL PEN-UP PRE-FLIGHT: "
            f"{len(planned)} checked segments -> {len(strokes)} continuous strokes."
        )
        self.writer.log(f"Pen remains lifted at Z={lifted_z:.2f}.")

        for i, stroke in enumerate(strokes, start=1):
            points = stroke["points"]
            r_deg = stroke["r"]

            self.writer.log(
                f"[Preflight stroke {i}/{len(strokes)}] "
                f"path={stroke['path_index']}, "
                f"R={r_deg:.2f} deg, "
                f"{len(points) - 1} checked pieces"
            )

            start_pen = points[0]
            self.move_flange_above_pen_tip(start_pen[0], start_pen[1], r_deg, lifted_z)
            self.sync_motion()
            self.check_actual_joints("preflight stroke start")

            for pen_x, pen_y in points[1:]:
                flange_x, flange_y = self.flange_for_pen_tip(pen_x, pen_y, r_deg)
                self.writer.send_motion(
                    f"MovL({flange_x:.3f},{flange_y:.3f},{lifted_z:.3f},{r_deg:.3f})"
                )

            self.sync_motion()
            self.check_actual_joints("preflight stroke end")

        self.writer.log("PHYSICAL PRE-FLIGHT completed successfully.")

    def draw(self, planned=None) -> None:
        lifted_z = WRITING_Z + self.settings.travel_lift_mm

        if planned is None:
            planned = self.plan_all_segments()

        strokes = self.combine_into_strokes(planned)

        self.writer.log(
            f"Starting SVG drawing: {len(planned)} IK-checked segments -> "
            f"{len(strokes)} continuous pen strokes."
        )
        self.writer.log(
            f"Target area: {self.settings.drawing_width_mm:.1f} x "
            f"{self.settings.drawing_height_mm:.1f} mm"
        )

        for i, stroke in enumerate(strokes, start=1):
            points = stroke["points"]
            r_deg = stroke["r"]

            start_pen_x, start_pen_y = points[0]
            start_fx, start_fy = self.flange_for_pen_tip(start_pen_x, start_pen_y, r_deg)

            self.writer.log(
                f"[Stroke {i}/{len(strokes)}] "
                f"path={stroke['path_index']}, "
                f"R={r_deg:.2f} deg, "
                f"segments={stroke['first_segment']}..{stroke['last_segment']}, "
                f"planned margin={stroke['score']:.2f} deg"
            )

            self.writer.send_motion(
                f"MovJ({start_fx:.3f},{start_fy:.3f},{lifted_z:.3f},{r_deg:.3f})"
            )
            self.sync_motion()
            self.check_actual_joints("before pen down")

            self.writer.send_motion(
                f"MovL({start_fx:.3f},{start_fy:.3f},{WRITING_Z:.3f},{r_deg:.3f})"
            )
            self.sync_motion()
            self.check_actual_joints("pen down")

            last_fx, last_fy = start_fx, start_fy
            for pen_x, pen_y in points[1:]:
                last_fx, last_fy = self.flange_for_pen_tip(pen_x, pen_y, r_deg)
                self.writer.send_motion(
                    f"MovL({last_fx:.3f},{last_fy:.3f},{WRITING_Z:.3f},{r_deg:.3f})"
                )

            self.sync_motion()
            self.check_actual_joints("stroke end")

            self.writer.send_motion(
                f"MovL({last_fx:.3f},{last_fy:.3f},{lifted_z:.3f},{r_deg:.3f})"
            )
            self.sync_motion()
            self.check_actual_joints("pen lifted")

        self.writer.log("Finished SVG drawing.")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    writer = MG400Writer()
    writer.settings.ip = ROBOT_IP
    writer.settings.live_robot = LIVE_ROBOT

    drawer = MG400SVGDrawer(
        writer,
        DrawerSettings(
            svg_file=SVG_FILE,
            drawing_width_mm=TEST_DRAWING_WIDTH_MM,
            drawing_height_mm=TEST_DRAWING_HEIGHT_MM,
            travel_lift_mm=10.0,
            min_path_length_mm=MIN_PATH_LENGTH_MM,
            simplify_tolerance_mm=SIMPLIFY_TOLERANCE_MM,
        ),
    )

    print()
    print("MG400 SVG DRAW TEST")
    print("===================")
    print(f"SVG file: {SVG_FILE}")
    print(f"Paper main rectangle: ~{PAPER_WIDTH_MM:.0f} x {PAPER_HEIGHT_MM:.0f} mm")
    print(f"First test drawing area: {drawer.settings.drawing_width_mm:.0f} x {drawer.settings.drawing_height_mm:.0f} mm")
    print(f"Live robot: {LIVE_ROBOT}")
    print(f"Preflight only: {PREFLIGHT_ONLY}")
    print()

    if LIVE_ROBOT:
        writer.connect_robot()
        writer.setup_robot()

    try:
        if LIVE_ROBOT:
            planned = drawer.plan_all_segments()

            if PREFLIGHT_ONLY:
                drawer.preflight(planned)
            else:
                drawer.draw(planned)
        else:
            print(
                "LIVE_ROBOT=False: SVG was loaded and simplified, but IK planning\n"
                "and robot movement were not run because they require a live MG400."
            )
    finally:
        if LIVE_ROBOT:
            writer.close_robot()
