"""
xArm 850 — Standalone Mister Bean Demo
=======================================

Self-contained presentation/demo program.

The Mister Bean drawing is embedded directly in this Python file.
No SVG/JSON file, controller, pygame, or full drawing app is required.

Demo sequence:
    Initial
      -> PICK_ABOVE
      -> PICK marker
      -> PICK_ABOVE
      -> PICK_TRANSFER
      -> MARKER_DRAW_READY
      -> HANDOFF
      -> wait for cap removal
      -> MARKER_DRAW_READY
      -> draw Mister Bean
      -> MARKER_DRAW_READY
      -> HANDOFF
      -> wait for cap replacement
      -> MARKER_DRAW_READY
      -> PICK_TRANSFER
      -> PICK_ABOVE
      -> PICK / place marker
      -> open G2
      -> PICK_ABOVE
      -> PICK_TRANSFER
      -> Initial

Requires:
    pip install xarm-python-sdk
"""

from __future__ import annotations

import json
import math
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Sequence, Tuple, Optional

from xarm.wrapper import XArmAPI


Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]
Path3D = List[Point3D]


# ============================================================
# ROBOT
# ============================================================

ROBOT_IP = "192.168.1.208"

INITIAL_JOINTS = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
INITIAL_JOINT_SPEED = 20.0
INITIAL_JOINT_ACC = 60.0

ROLL = -179.7
PITCH = -3.6
YAW = 179.1

SAFE_X = -480.0

# Current drawing marker offset.
CONTACT_X_OFFSET_MM = -8.55

TRAVEL_SPEED = 100.0
APPROACH_SPEED = 25.0
DRAW_SPEED = 120.0

# Drawing cleanup.
MIN_PATH_LENGTH_MM = 2.5
SIMPLIFY_TOLERANCE_MM = 0.7

# Mister Bean source canvas / placement.
DEMO_JSON_TOP_MM = 15.0
DEMO_JSON_WIDTH_MM = 359.6
DEMO_JSON_HEIGHT_MM = 235.0


# ============================================================
# 5-POINT WALL CALIBRATION — CURRENT SAFE VERSION
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

# Safe TR-bottom, normalized back to zero drawing offset.
PAPER_TR_BOTTOM: Point3D = (
    -514.380537,
    291.430176,
    689.678589,
)

# Safe TR-top, normalized back to zero drawing offset.
PAPER_TR_TOP: Point3D = (
    -515.934065,
    185.926178,
    738.720276,
)


# ============================================================
# TESTED MARKER ROUTE
# ============================================================

MARKER_PICK_JOINTS = [
    -161.125014,
    -29.157536,
    -26.325291,
    177.925282,
    -3.691223,
    -159.999324,
]

MARKER_PICK_ABOVE_JOINTS = [
    -161.024918,
    -16.920360,
    -24.378609,
    178.725647,
    5.883131,
    -160.717526,
]

MARKER_PICK_ABOVE_TCP = [
    -307.723938,
    -105.031891,
    71.431976,
    -179.569958,
    -1.128727,
    -179.067187,
]

MARKER_PICK_TRANSFER_TCP = [
    -307.723938,
    -105.031891,
    519.999939,
    -179.569958,
    -1.128784,
    -179.067187,
]

MARKER_DRAW_READY_JOINTS = [
    -196.531113,
    7.519040,
    -77.101613,
    181.201913,
    80.921408,
    -195.830958,
]

MARKER_DRAW_READY_TCP = [
    -391.468628,
    110.893745,
    597.494202,
    -179.705921,
    -3.507648,
    179.133536,
]

MARKER_HANDOFF_JOINTS = [
    -281.333966,
    7.519040,
    -77.101613,
    181.201913,
    80.921408,
    -195.830958,
]

MARKER_GRIP_OPEN_MM = 50.0
MARKER_GRIP_HOLD_MM = 10.0

MARKER_ANYWHERE_JOINT_SPEED = 8.0
MARKER_ANYWHERE_JOINT_ACC = 40.0

MARKER_PICK_JOINT_SPEED = 6.0
MARKER_PICK_JOINT_ACC = 30.0

MARKER_HANDOFF_JOINT_SPEED = 8.0
MARKER_HANDOFF_JOINT_ACC = 40.0

MARKER_CART_SPEED = 30.0
MARKER_CART_ACC = 80.0

GRIPPER_SPEED = 100
GRIPPER_FORCE = 50

POSE_TOLERANCE_DEG = 3.0


# ============================================================
# EMBEDDED MISTER BEAN DRAWING
# ============================================================

MISTER_BEAN_JSON = r"""{"format":"xarm850-freehand-v1","width_mm":359.6,"height_mm":235.0,"strokes":[{"shape":"pen","points":[[122.175,85.649],[121.725,86.099],[120.6,87.0],[119.925,87.45],[118.799,88.575],[117.223,89.701],[115.423,91.051],[113.847,92.402],[110.696,95.778],[109.57,97.354],[108.67,99.605],[108.22,101.856],[108.22,103.206],[108.22,105.232],[108.67,106.808],[110.696,108.159],[113.397,109.284],[114.972,109.509],[117.899,109.734],[121.95,109.509],[126.227,108.834],[128.703,108.609],[132.08,107.483],[134.106,106.133],[135.456,105.457],[136.357,105.007],[136.807,104.782]]},{"shape":"pen","points":[[139.508,92.852],[140.183,91.952],[141.084,91.501],[142.659,91.501],[144.46,91.727],[145.135,92.402],[145.585,93.077],[146.036,94.653],[146.261,96.228],[146.036,97.354],[145.135,98.705],[144.235,99.83],[142.884,100.28],[141.984,100.505],[141.309,100.505]]},{"shape":"ellipse","points":[[184.302,84.186],[184.172,86.181],[183.786,88.141],[183.15,90.03],[182.275,91.814],[181.177,93.463],[179.877,94.946],[178.395,96.237],[176.761,97.313],[175.001,98.154],[173.149,98.747],[171.236,99.08],[169.298,99.146],[167.368,98.946],[165.482,98.483],[163.672,97.764],[161.971,96.803],[160.41,95.617],[159.015,94.227],[157.813,92.657],[156.825,90.937],[156.068,89.096],[155.555,87.167],[155.297,85.186],[155.297,83.186],[155.555,81.204],[156.068,79.276],[156.825,77.435],[157.813,75.714],[159.015,74.145],[160.41,72.755],[161.971,71.569],[163.672,70.608],[165.482,69.889],[167.368,69.425],[169.298,69.225],[171.236,69.292],[173.149,69.625],[175.001,70.217],[176.761,71.059],[178.395,72.135],[179.877,73.426],[181.177,74.909],[182.275,76.557],[183.15,78.342],[183.786,80.231],[184.172,82.191],[184.302,84.186]]},{"shape":"ellipse","points":[[176.649,87.112],[176.484,88.365],[176.0,89.532],[175.231,90.534],[174.229,91.303],[173.062,91.787],[171.809,91.952],[170.557,91.787],[169.389,91.303],[168.387,90.534],[167.618,89.532],[167.134,88.365],[166.97,87.112],[167.134,85.859],[167.618,84.692],[168.387,83.69],[169.389,82.921],[170.557,82.437],[171.809,82.273],[173.062,82.437],[174.229,82.921],[175.231,83.69],[176.0,84.692],[176.484,85.859],[176.649,87.112]]},{"shape":"pen","points":[[112.271,55.486],[120.6,56.612],[125.777,59.313],[127.128,63.59],[126.902,70.568],[125.777,75.52],[123.301,83.398],[121.5,86.099],[121.05,86.549]]},{"shape":"pen","points":[[127.578,67.641],[126.002,66.291],[121.95,65.615],[117.448,65.615],[112.046,67.416],[108.895,70.793],[108.22,75.52],[109.795,80.247],[113.847,83.848],[115.423,84.974],[117.448,87.0],[118.349,88.125]]},{"shape":"ellipse","points":[[123.526,77.883],[123.423,78.67],[123.119,79.403],[122.636,80.032],[122.007,80.515],[121.274,80.818],[120.487,80.922],[119.701,80.818],[118.968,80.515],[118.339,80.032],[117.856,79.403],[117.552,78.67],[117.448,77.883],[117.552,77.097],[117.856,76.364],[118.339,75.734],[118.968,75.251],[119.701,74.948],[120.487,74.844],[121.274,74.948],[122.007,75.251],[122.636,75.734],[123.119,76.364],[123.423,77.097],[123.526,77.883]]},{"shape":"pen","points":[[119.024,88.35],[116.548,88.35],[113.622,89.476],[113.172,91.952],[114.072,92.852]]},{"shape":"pen","points":[[145.135,83.173],[152.338,69.217],[164.043,60.438],[172.822,59.313],[178.224,63.364]]},{"shape":"pen","points":[[152.789,118.063],[151.888,123.69],[144.91,129.092],[135.906,131.118],[128.703,131.118],[125.552,131.118],[125.102,130.893]]},{"shape":"pen","points":[[149.862,117.387],[153.914,118.288],[155.49,121.889],[154.364,118.288]]},{"shape":"pen","points":[[132.305,137.871],[135.906,138.096],[140.408,137.196]]},{"shape":"pen","points":[[164.719,57.737],[160.667,60.888],[160.667,63.139],[162.243,64.04],[165.169,64.04],[167.87,62.689],[170.121,61.789],[171.021,59.988],[168.77,58.863],[164.268,59.088]]},{"shape":"pen","points":[[120.15,54.811],[117.448,55.261],[115.873,58.637],[122.175,60.213],[124.652,61.114],[127.128,59.538],[124.877,56.612],[122.175,55.261],[121.05,54.811],[120.15,54.811]]},{"shape":"pen","points":[[120.6,36.353],[114.972,42.431],[108.22,49.409],[101.917,54.361],[100.566,55.261],[102.592,59.088],[103.943,66.066],[103.718,74.169],[103.042,80.247],[101.242,83.623],[96.064,88.125],[93.138,92.627],[91.788,101.181],[95.389,113.336],[106.419,129.768],[124.426,151.152],[129.604,152.953]]},{"shape":"pen","points":[[129.829,152.727],[133.205,153.178],[134.556,157.68],[134.556,161.281],[134.556,162.632]]},{"shape":"pen","points":[[150.538,163.082],[149.187,157.68],[156.615,152.502],[176.198,141.698],[195.332,118.063],[195.557,115.587],[195.782,116.487],[195.782,115.362]]},{"shape":"ellipse","points":[[176.874,114.461],[176.793,115.16],[176.557,115.812],[176.181,116.371],[175.692,116.8],[175.122,117.07],[174.51,117.162],[173.899,117.07],[173.328,116.8],[172.839,116.371],[172.463,115.812],[172.227,115.16],[172.147,114.461],[172.227,113.762],[172.463,113.111],[172.839,112.551],[173.328,112.122],[173.899,111.852],[174.51,111.76],[175.122,111.852],[175.692,112.122],[176.181,112.551],[176.557,113.111],[176.793,113.762],[176.874,114.461]]},{"shape":"pen","points":[[103.042,59.538],[98.54,56.161],[88.636,55.711],[85.26,60.663],[86.385,76.42],[93.588,91.952],[93.813,92.627]]},{"shape":"pen","points":[[96.515,87.225],[92.463,74.619],[92.913,67.191],[98.09,64.265],[102.817,65.39]]},{"shape":"pen","points":[[195.782,116.712],[204.786,120.089],[219.642,115.587],[222.793,89.25],[209.738,82.273],[200.959,83.848],[196.007,86.324],[196.907,86.774],[195.557,86.324]]},{"shape":"pen","points":[[201.859,93.752],[212.889,90.376],[215.365,92.852],[215.815,98.705],[214.915,104.782],[212.214,109.284],[207.037,111.31],[201.634,111.76],[200.734,111.085]]},{"shape":"pen","points":[[119.474,35.903],[139.958,39.054],[159.316,38.829],[178.675,39.955],[193.981,44.006],[199.383,45.357],[196.907,44.907]]},{"shape":"pen","points":[[98.54,56.837],[100.791,42.656],[112.721,32.526],[118.799,32.301],[119.249,32.526],[140.858,22.847],[181.376,23.072],[216.491,35.002],[215.815,43.331],[215.365,44.006],[232.923,56.837],[225.72,78.221],[215.59,84.073]]},{"shape":"pen","points":[[198.708,45.582],[200.509,47.383],[200.959,49.634],[199.834,52.785],[197.583,57.287],[194.881,61.339],[194.206,65.615],[196.457,71.468],[197.132,76.87],[196.907,82.047],[195.782,85.424]]},{"shape":"pen","points":[[135.456,44.231],[142.209,46.482],[150.087,46.932],[152.563,46.707]]},{"shape":"pen","points":[[132.305,51.659],[137.257,54.361],[143.334,55.036],[148.962,53.235],[154.364,52.785],[156.165,53.91]]},{"shape":"pen","points":[[94.714,202.924],[102.142,182.215],[104.618,174.787],[111.371,171.636],[123.751,166.909],[132.08,163.307],[134.331,164.207],[143.109,166.458],[150.538,163.982],[151.438,163.307],[165.394,170.285],[165.844,170.51],[171.021,199.322],[172.372,203.824]]},{"shape":"pen","points":[[133.205,163.307],[130.279,201.798],[129.829,203.374]]},{"shape":"pen","points":[[151.663,163.307],[153.239,196.621],[153.464,202.023]]},{"shape":"pen","points":[[132.755,173.886],[133.655,176.363],[133.88,176.813]]},{"shape":"pen","points":[[134.331,176.813],[139.733,168.934],[141.759,167.584],[142.209,167.359],[146.036,173.661],[147.386,175.462],[148.287,176.813],[148.512,177.263],[151.438,174.112],[152.113,173.661]]},{"shape":"pen","points":[[138.607,171.185],[142.659,175.237],[144.685,173.661],[145.135,173.211]]},{"shape":"pen","points":[[142.434,174.787],[140.183,190.544],[138.833,201.573]]},{"shape":"pen","points":[[143.56,175.237],[146.936,196.621],[147.386,200.673],[147.386,201.123]]},{"shape":"pen","points":[[105.293,174.787],[110.921,181.09],[115.873,203.599],[115.873,204.95]]},{"shape":"pen","points":[[166.294,171.636],[164.268,186.492],[164.043,200.673],[164.043,205.85]]},{"shape":"pen","points":[[130.504,164.658],[124.877,174.562],[122.851,179.514],[127.803,183.115],[129.153,185.591],[123.526,190.318],[123.526,193.47],[123.526,202.023],[123.526,203.374]]},{"shape":"pen","points":[[153.239,164.658],[157.741,172.311],[158.866,174.112],[159.992,177.938],[160.217,178.839],[155.94,180.414],[159.766,186.267],[159.766,190.093],[159.541,201.348],[159.541,202.474]]},{"shape":"pen","points":[[79.857,197.071],[111.146,204.049],[129.153,205.175],[148.737,204.049],[180.475,203.599],[206.811,194.82]]}]}"""


# ============================================================
# GEOMETRY
# ============================================================

def distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def polyline_length(points: Sequence[Point2D]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(distance(a, b) for a, b in zip(points, points[1:]))


def remove_duplicate_neighbors(
    points: Sequence[Point2D],
    tolerance: float = 1e-9,
) -> List[Point2D]:
    if not points:
        return []
    out = [points[0]]
    for p in points[1:]:
        if distance(out[-1], p) > tolerance:
            out.append(p)
    return out


def rdp(points: Sequence[Point2D], epsilon: float) -> List[Point2D]:
    if len(points) < 3:
        return list(points)

    start = points[0]
    end = points[-1]
    sx, sy = start
    ex, ey = end

    denom = math.hypot(ex - sx, ey - sy)
    max_dist = -1.0
    index = -1

    for i, p in enumerate(points[1:-1], start=1):
        px, py = p
        if denom == 0:
            d = math.hypot(px - sx, py - sy)
        else:
            d = abs(
                (ey - sy) * px
                - (ex - sx) * py
                + ex * sy
                - ey * sx
            ) / denom

        if d > max_dist:
            max_dist = d
            index = i

    if max_dist <= epsilon:
        return [start, end]

    left = rdp(points[: index + 1], epsilon)
    right = rdp(points[index:], epsilon)
    return left[:-1] + right


def point3_distance(a: Point3D, b: Point3D) -> float:
    return math.sqrt(
        (b[0] - a[0]) ** 2
        + (b[1] - a[1]) ** 2
        + (b[2] - a[2]) ** 2
    )


# Logical wall basis.
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


def yz_to_paper_mm(y: float, z: float) -> Point2D:
    vy = y - PAPER_TL[1]
    vz = z - PAPER_TL[2]

    ry, rz = _PAPER_RIGHT_UNIT
    dy, dz = _PAPER_DOWN_UNIT

    det = ry * dz - rz * dy
    if abs(det) < 1e-9:
        raise RuntimeError("Paper calibration basis is degenerate.")

    right_mm = (vy * dz - vz * dy) / det
    down_mm = (ry * vz - rz * vy) / det
    return right_mm, down_mm


PAPER_TR_TOP_MM = yz_to_paper_mm(PAPER_TR_TOP[1], PAPER_TR_TOP[2])
PAPER_TR_BOTTOM_MM = yz_to_paper_mm(
    PAPER_TR_BOTTOM[1],
    PAPER_TR_BOTTOM[2],
)


def barycentric_weights(
    p: Point2D,
    a: Point2D,
    b: Point2D,
    c: Point2D,
) -> Optional[Tuple[float, float, float]]:
    px, py = p
    ax, ay = a
    bx, by = b
    cx, cy = c

    denom = (
        (by - cy) * (ax - cx)
        + (cx - bx) * (ay - cy)
    )
    if abs(denom) < 1e-12:
        return None

    w1 = (
        (by - cy) * (px - cx)
        + (cx - bx) * (py - cy)
    ) / denom
    w2 = (
        (cy - ay) * (px - cx)
        + (ax - cx) * (py - cy)
    ) / denom
    w3 = 1.0 - w1 - w2
    return w1, w2, w3


def blend3(
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


def paper_mm_to_contact(
    right_mm: float,
    down_mm: float,
) -> Point3D:
    p = (right_mm, down_mm)

    for a2, a3, b2, b3, c2, c3 in _PAPER_TRIANGLES:
        weights = barycentric_weights(p, a2, b2, c2)
        if weights is None:
            continue

        if min(weights) >= -1e-7:
            x, y, z = blend3(weights, a3, b3, c3)
            return (
                x + CONTACT_X_OFFSET_MM,
                y,
                z,
            )

    raise RuntimeError(
        "Mister Bean enters the unreachable upper-right wall area "
        f"at right={right_mm:.1f} mm, down={down_mm:.1f} mm."
    )


def safe_point(contact: Point3D) -> Point3D:
    return SAFE_X, contact[1], contact[2]


def build_mister_bean_paths() -> List[Path3D]:
    data = json.loads(MISTER_BEAN_JSON)

    width = float(data["width_mm"])
    height = float(data["height_mm"])

    scale = min(
        DEMO_JSON_WIDTH_MM / width,
        DEMO_JSON_HEIGHT_MM / height,
    )

    final_w = width * scale
    final_h = height * scale

    left_margin = (PAPER_WIDTH_MM - final_w) / 2.0
    top_margin = DEMO_JSON_TOP_MM

    if top_margin + final_h > PAPER_HEIGHT_MM:
        raise RuntimeError("Embedded Mister Bean drawing does not fit vertically.")

    paths: List[Path3D] = []

    for index, stroke in enumerate(data.get("strokes", []), start=1):
        points = stroke.get("points", [])
        if len(points) < 2:
            continue

        local = [
            (float(p[0]) * scale, float(p[1]) * scale)
            for p in points
        ]

        local = remove_duplicate_neighbors(local)

        if SIMPLIFY_TOLERANCE_MM > 0:
            local = rdp(local, SIMPLIFY_TOLERANCE_MM)
            local = remove_duplicate_neighbors(local)

        if (
            len(local) < 2
            or polyline_length(local) < MIN_PATH_LENGTH_MM
        ):
            continue

        path3d: Path3D = []

        for right_mm, down_mm in local:
            path3d.append(
                paper_mm_to_contact(
                    left_margin + right_mm,
                    top_margin + down_mm,
                )
            )

        cleaned: Path3D = []
        for p in path3d:
            if (
                not cleaned
                or point3_distance(cleaned[-1], p) > 0.02
            ):
                cleaned.append(p)

        if len(cleaned) >= 2:
            paths.append(cleaned)

    if not paths:
        raise RuntimeError("Embedded Mister Bean drawing has no usable paths.")

    return paths


# Precompute and validate without connecting to the robot.
MISTER_BEAN_PATHS = build_mister_bean_paths()


# ============================================================
# DEMO APP
# ============================================================

class MisterBeanDemo:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("xArm 850 — Mister Bean Demo")
        self.root.geometry("780x720")
        self.root.minsize(700, 650)

        self.arm: Optional[XArmAPI] = None
        self.running = False
        self.stop_requested = False

        self.status_var = tk.StringVar(value="Ready")
        self.step_var = tk.StringVar(value="Ready for demo")

        self._build_ui()
        self._draw_preview()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(
            outer,
            text="xArm 850 — Mister Bean Demo",
            font=("Segoe UI", 22, "bold"),
        )
        title.pack(pady=(0, 4))

        subtitle = ttk.Label(
            outer,
            text=(
                "One-button marker pickup → cap removal → drawing → "
                "cap replacement → marker return"
            ),
            font=("Segoe UI", 10),
        )
        subtitle.pack(pady=(0, 12))

        preview_frame = ttk.LabelFrame(
            outer,
            text="Embedded drawing",
            padding=8,
        )
        preview_frame.pack(fill="x", pady=(0, 12))

        self.canvas = tk.Canvas(
            preview_frame,
            height=270,
            background="white",
            highlightthickness=0,
        )
        self.canvas.pack(fill="x")

        info = ttk.Frame(outer)
        info.pack(fill="x", pady=(0, 10))

        ttk.Label(
            info,
            text="Status:",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            info,
            textvariable=self.status_var,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        ttk.Label(
            info,
            text="Step:",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Label(
            info,
            textvariable=self.step_var,
        ).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        info.columnconfigure(1, weight=1)

        self.run_btn = ttk.Button(
            outer,
            text="RUN MISTER BEAN DEMO",
            command=self.start_demo,
        )
        self.run_btn.pack(fill="x", ipady=14, pady=(2, 8))

        row = ttk.Frame(outer)
        row.pack(fill="x", pady=(0, 10))

        self.recover_btn = ttk.Button(
            row,
            text="Connect / Recover",
            command=self.connect_or_recover,
        )
        self.recover_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.stop_btn = ttk.Button(
            row,
            text="STOP",
            command=self.stop,
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        ttk.Label(
            outer,
            text=(
                "Demo assumptions: capped marker is already in the holder; "
                "the robot starts in a clear workspace. "
                "Only the cap-removal and cap-replacement steps require you."
            ),
            wraplength=720,
            justify="left",
        ).pack(fill="x", pady=(0, 8))

        log_frame = ttk.LabelFrame(
            outer,
            text="Demo log",
            padding=6,
        )
        log_frame.pack(fill="both", expand=True)

        self.log_box = tk.Text(
            log_frame,
            height=8,
            state="disabled",
            wrap="word",
            font=("Consolas", 9),
        )
        self.log_box.pack(fill="both", expand=True)

    def _draw_preview(self) -> None:
        self.canvas.delete("all")
        data = json.loads(MISTER_BEAN_JSON)

        width = float(data["width_mm"])
        height = float(data["height_mm"])

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = 270

        margin = 18
        sx = (canvas_w - margin * 2) / width
        sy = (canvas_h - margin * 2) / height
        scale = min(sx, sy)

        ox = (canvas_w - width * scale) / 2.0
        oy = (canvas_h - height * scale) / 2.0

        for stroke in data.get("strokes", []):
            pts = stroke.get("points", [])
            if len(pts) < 2:
                continue

            coords = []
            for x, y in pts:
                coords.extend([
                    ox + float(x) * scale,
                    oy + float(y) * scale,
                ])

            self.canvas.create_line(
                *coords,
                fill="#111111",
                width=2,
                smooth=False,
            )

        # Re-render after geometry is known.
        if canvas_w <= 1:
            self.root.after(150, self._draw_preview)

    # --------------------------------------------------------
    # Thread-safe UI helpers
    # --------------------------------------------------------

    def set_status(self, text: str) -> None:
        self.root.after(0, self.status_var.set, text)

    def set_step(self, text: str) -> None:
        self.root.after(0, self.step_var.set, text)

    def log(self, text: str) -> None:
        print(text)

        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.root.after(0, append)

    def ask_ok(self, title: str, message: str) -> bool:
        event = threading.Event()
        result = {"value": False}

        def show() -> None:
            result["value"] = messagebox.askokcancel(
                title,
                message,
                parent=self.root,
            )
            event.set()

        self.root.after(0, show)
        event.wait()

        return bool(result["value"])

    def show_error(self, text: str) -> None:
        self.root.after(
            0,
            lambda: messagebox.showerror(
                "Demo error",
                text,
                parent=self.root,
            ),
        )

    # --------------------------------------------------------
    # xArm helpers
    # --------------------------------------------------------

    @staticmethod
    def check(code: int, action: str) -> None:
        if code != 0:
            raise RuntimeError(
                f"xArm error during {action}: code={code}"
            )

    def ensure_connected(self) -> None:
        if self.arm is None:
            self.log(f"Connecting to {ROBOT_IP}...")
            self.arm = XArmAPI(
                ROBOT_IP,
                is_radian=False,
            )
            self.arm.connect()

        self.arm.clean_warn()
        self.arm.clean_error()

        try:
            self.arm.set_collision_tool_model(9)
        except Exception as exc:
            self.log(f"Collision tool model warning: {exc}")

        try:
            self.arm.set_self_collision_detection(True)
        except Exception as exc:
            self.log(f"Self-collision setting warning: {exc}")

        self.check(
            self.arm.motion_enable(enable=True),
            "motion_enable",
        )
        self.check(
            self.arm.set_mode(0),
            "set_mode(0)",
        )
        self.check(
            self.arm.set_state(0),
            "set_state(0)",
        )

        self.set_status("Connected")

    def connect_or_recover(self) -> None:
        if self.running:
            return

        try:
            self.ensure_connected()
            self.set_status("Connected / recovered")
            self.log("Robot connected and recovered.")
        except Exception as exc:
            self.show_error(str(exc))

    def check_stop(self) -> None:
        if self.stop_requested:
            raise RuntimeError("Demo stopped by user.")

    def joint_move(
        self,
        joints: Sequence[float],
        name: str,
        speed: float,
        acc: float,
    ) -> None:
        self.check_stop()
        assert self.arm is not None

        self.log(f"Move -> {name}")
        try:
            self.arm.set_joint_maxacc(acc)
        except Exception:
            pass

        code = self.arm.set_servo_angle(
            angle=list(joints),
            speed=speed,
            mvacc=acc,
            wait=True,
            is_radian=False,
        )
        self.check(code, name)
        self.check_stop()

    def cart_move(
        self,
        pose: Sequence[float],
        name: str,
    ) -> None:
        self.check_stop()
        assert self.arm is not None

        x, y, z, roll, pitch, yaw = pose

        self.log(f"Cartesian -> {name}")
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
        self.check(code, name)
        self.check_stop()

    def draw_move_xyz(
        self,
        point: Point3D,
        speed: float,
        wait: bool = True,
    ) -> None:
        self.check_stop()
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
        self.check(
            code,
            f"draw move X={x:.1f} Y={y:.1f} Z={z:.1f}",
        )

    def set_gripper(self, position: float) -> None:
        self.check_stop()
        assert self.arm is not None

        self.log(f"G2 -> {position:.0f} mm")

        code = self.arm.set_gripper_g2_position(
            position,
            speed=GRIPPER_SPEED,
            force=GRIPPER_FORCE,
            wait=True,
        )
        self.check(code, "G2 gripper")
        self.check_stop()

    def current_joints(self) -> List[float]:
        assert self.arm is not None

        code, joints = self.arm.get_servo_angle(
            is_radian=False,
        )
        self.check(code, "read joints")
        return [float(v) for v in joints[:6]]

    @staticmethod
    def joints_near(
        actual: Sequence[float],
        target: Sequence[float],
        tolerance: float = POSE_TOLERANCE_DEG,
    ) -> bool:
        return all(
            abs(a - b) <= tolerance
            for a, b in zip(actual[:6], target[:6])
        )

    def verify_marker_draw_ready(self) -> None:
        joints = self.current_joints()

        if not self.joints_near(
            joints,
            MARKER_DRAW_READY_JOINTS,
        ):
            raise RuntimeError(
                "Reached the Draw Ready TCP but not the expected "
                "marker-compatible wrist configuration. Demo stopped."
            )

    # --------------------------------------------------------
    # Drawing
    # --------------------------------------------------------

    def draw_mister_bean(self) -> None:
        paths = MISTER_BEAN_PATHS
        total = len(paths)

        self.log(
            f"Drawing Mister Bean: {total} paths"
        )

        for i, path in enumerate(paths, start=1):
            self.check_stop()

            self.set_step(
                f"Drawing Mister Bean — path {i} / {total}"
            )

            if (
                i == 1
                or i % 10 == 0
                or i == total
            ):
                self.log(
                    f"Drawing path {i} / {total}"
                )

            start = path[0]

            # Travel with pen away from wall.
            self.draw_move_xyz(
                safe_point(start),
                TRAVEL_SPEED,
                wait=True,
            )

            # Approach wall.
            self.draw_move_xyz(
                start,
                APPROACH_SPEED,
                wait=True,
            )

            # Draw.
            for point in path[1:-1]:
                self.draw_move_xyz(
                    point,
                    DRAW_SPEED,
                    wait=False,
                )

            self.draw_move_xyz(
                path[-1],
                DRAW_SPEED,
                wait=True,
            )

            # Lift pen.
            self.draw_move_xyz(
                safe_point(path[-1]),
                APPROACH_SPEED,
                wait=True,
            )

        self.log("Mister Bean drawing finished.")

    # --------------------------------------------------------
    # Demo
    # --------------------------------------------------------

    def start_demo(self) -> None:
        if self.running:
            return

        self.running = True
        self.stop_requested = False

        self.run_btn.configure(state="disabled")
        self.recover_btn.configure(state="disabled")

        thread = threading.Thread(
            target=self.demo_worker,
            daemon=True,
        )
        thread.start()

    def demo_worker(self) -> None:
        try:
            self.ensure_connected()

            # 1. Initial.
            self.set_step("1/10 — Initial Position")
            self.log("DEMO 1/10 — Initial Position")
            self.joint_move(
                INITIAL_JOINTS,
                "Initial Position",
                INITIAL_JOINT_SPEED,
                INITIAL_JOINT_ACC,
            )

            # 2. Go above marker.
            self.set_step("2/10 — Moving above marker")
            self.log("DEMO 2/10 — Initial -> PICK_ABOVE")
            self.joint_move(
                MARKER_PICK_ABOVE_JOINTS,
                "PICK_ABOVE",
                MARKER_ANYWHERE_JOINT_SPEED,
                MARKER_ANYWHERE_JOINT_ACC,
            )

            # DEMO ONLY: no "marker present?" prompt.
            self.set_step("3/10 — Picking marker")
            self.log("DEMO 3/10 — Picking marker")

            self.set_gripper(MARKER_GRIP_OPEN_MM)

            self.joint_move(
                MARKER_PICK_JOINTS,
                "PICK",
                MARKER_PICK_JOINT_SPEED,
                MARKER_PICK_JOINT_ACC,
            )

            self.set_gripper(MARKER_GRIP_HOLD_MM)
            time.sleep(0.5)

            self.joint_move(
                MARKER_PICK_ABOVE_JOINTS,
                "PICK_ABOVE",
                MARKER_PICK_JOINT_SPEED,
                MARKER_PICK_JOINT_ACC,
            )

            self.cart_move(
                MARKER_PICK_TRANSFER_TCP,
                "PICK_TRANSFER",
            )

            self.cart_move(
                MARKER_DRAW_READY_TCP,
                "MARKER_DRAW_READY",
            )
            self.verify_marker_draw_ready()

            # 4. Handoff for cap removal.
            self.set_step("4/10 — Remove marker cap")
            self.log("DEMO 4/10 — Handoff for cap removal")

            self.joint_move(
                MARKER_HANDOFF_JOINTS,
                "MARKER_HANDOFF",
                MARKER_HANDOFF_JOINT_SPEED,
                MARKER_HANDOFF_JOINT_ACC,
            )

            if not self.ask_ok(
                "Remove marker cap",
                "Remove the cap from the marker.\n\n"
                "The robot will keep holding the marker.\n\n"
                "Press OK when the cap is off.",
            ):
                raise RuntimeError(
                    "Demo cancelled during cap removal."
                )

            # Back to draw ready.
            self.joint_move(
                MARKER_DRAW_READY_JOINTS,
                "MARKER_DRAW_READY",
                MARKER_HANDOFF_JOINT_SPEED,
                MARKER_HANDOFF_JOINT_ACC,
            )

            # 5. Draw.
            self.set_step("5/10 — Drawing Mister Bean")
            self.log("DEMO 5/10 — Drawing Mister Bean")
            self.draw_mister_bean()

            # Return to marker-compatible ready branch.
            self.set_step("6/10 — Returning to Draw Ready")
            self.log("DEMO 6/10 — Returning to MARKER_DRAW_READY")

            self.cart_move(
                MARKER_DRAW_READY_TCP,
                "MARKER_DRAW_READY after drawing",
            )
            self.verify_marker_draw_ready()

            # 7. Handoff for cap replacement.
            self.set_step("7/10 — Replace marker cap")
            self.log("DEMO 7/10 — Handoff for cap replacement")

            self.joint_move(
                MARKER_HANDOFF_JOINTS,
                "MARKER_HANDOFF",
                MARKER_HANDOFF_JOINT_SPEED,
                MARKER_HANDOFF_JOINT_ACC,
            )

            if not self.ask_ok(
                "Replace marker cap",
                "Put the cap back onto the marker.\n\n"
                "The robot will keep holding the marker.\n\n"
                "Press OK when the cap is secure.",
            ):
                raise RuntimeError(
                    "Demo cancelled during cap replacement."
                )

            # 8. Full reverse route to holder.
            self.set_step("8/10 — Returning marker to holder")
            self.log("DEMO 8/10 — Returning marker to holder")

            self.joint_move(
                MARKER_DRAW_READY_JOINTS,
                "MARKER_DRAW_READY",
                MARKER_HANDOFF_JOINT_SPEED,
                MARKER_HANDOFF_JOINT_ACC,
            )

            self.cart_move(
                MARKER_PICK_TRANSFER_TCP,
                "PICK_TRANSFER",
            )

            self.cart_move(
                MARKER_PICK_ABOVE_TCP,
                "PICK_ABOVE",
            )

            self.joint_move(
                MARKER_PICK_JOINTS,
                "PICK / PLACE",
                MARKER_PICK_JOINT_SPEED,
                MARKER_PICK_JOINT_ACC,
            )

            # 9. Release and clear holder.
            self.set_step("9/10 — Placing marker in rack")
            self.log("DEMO 9/10 — Releasing marker")

            self.set_gripper(MARKER_GRIP_OPEN_MM)
            time.sleep(1.0)

            self.joint_move(
                MARKER_PICK_ABOVE_JOINTS,
                "PICK_ABOVE",
                MARKER_PICK_JOINT_SPEED,
                MARKER_PICK_JOINT_ACC,
            )

            # More clearance before all-zero joint move.
            self.cart_move(
                MARKER_PICK_TRANSFER_TCP,
                "PICK_TRANSFER",
            )

            # 10. Initial.
            self.set_step("10/10 — Returning to Initial")
            self.log("DEMO 10/10 — Returning to Initial Position")

            self.joint_move(
                INITIAL_JOINTS,
                "Initial Position",
                INITIAL_JOINT_SPEED,
                INITIAL_JOINT_ACC,
            )

            self.set_step("Demo complete")
            self.set_status("Demo complete")
            self.log("MISTER BEAN DEMO COMPLETE")

            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Demo complete",
                    "Mister Bean demo finished successfully.",
                    parent=self.root,
                ),
            )

        except Exception as exc:
            self.set_status("Stopped / error")
            self.set_step("Demo stopped")
            self.log(f"ERROR: {exc}")

            if not self.stop_requested:
                self.show_error(str(exc))

        finally:
            self.running = False

            def restore() -> None:
                self.run_btn.configure(state="normal")
                self.recover_btn.configure(state="normal")

            self.root.after(0, restore)

    # --------------------------------------------------------
    # Stop / close
    # --------------------------------------------------------

    def stop(self) -> None:
        self.stop_requested = True
        self.set_status("STOP requested")
        self.set_step("Stopping robot")
        self.log("STOP requested.")

        if self.arm is not None:
            try:
                self.arm.set_state(4)
            except Exception as exc:
                self.log(f"STOP warning: {exc}")

    def close(self) -> None:
        if self.running:
            if not messagebox.askyesno(
                "Exit demo",
                "The demo is running. Stop the robot and exit?",
                parent=self.root,
            ):
                return

            self.stop()

        if self.arm is not None:
            try:
                self.arm.disconnect()
            except Exception:
                pass

        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = MisterBeanDemo(root)
    root.mainloop()


if __name__ == "__main__":
    main()
