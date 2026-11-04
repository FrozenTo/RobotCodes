"""xArm 850 freehand wall-drawing app (Tkinter + UFACTORY SDK), v2 — relaxed workflow + working-app robot lifecycle.

Draw vector strokes using the mouse. Optional robot control is OFF until the
user explicitly connects and authorizes motion. Geometry is based on the
previously measured eight wall-paper contact/reference points.

Dependencies for ROBOT MODE only: pip install xarm-python-sdk
Run: python xarm850_freehand_drawer.py

IMPORTANT: Use the same robot TCP, pen holder, wall frame, and tool orientation
as the successful xArm wall-drawing project. Air testing is available but optional.
Software STOP is not a replacement for the physical emergency stop.
Robot paths still need physical verification on the actual machine. Keep the workspace clear and the physical E-stop accessible.
"""
from __future__ import annotations

import json
import math
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "xarm850_freehand_settings.json"

# These are the *latest* 8 measured paper points from the working xArm SVG project.
# If the paper, tool or mounting changes, remeasure rather than trusting them.
PAPER_POINTS = {
    "TL": [-487.7, -67.8, 741.4],
    "TM": [-484.6, 107.5, 732.7],
    "TR": [-482.0, 291.6, 721.9],
    "ML": [-487.7, -67.4, 619.8],
    "MR": [-482.9, 292.9, 613.6],
    "BL": [-487.7, -67.8, 499.2],
    "BM": [-485.3, 113.0, 494.1],
    "BR": [-482.7, 291.2, 494.1],
}
# Copied from the user's last successfully operated combined xArm application.
READY_JOINTS = [-196.5, 7.5, -77.1, 1.2, -80.9, -15.8]
INITIAL_JOINTS = [0.0] * 6
READY_JOINT_TOLERANCE_DEG = 5.0
INITIAL_JOINT_TOLERANCE_DEG = 4.0
READY_CART_TOLERANCE_MM = 30.0
READY_RPY_TOLERANCE_DEG = 20.0
READY_JOINT_SPEED = 20.0   # matches the previous combined xArm app
INITIAL_JOINT_SPEED = 20.0

# Older freehand defaults contained paper contact X positions 2 mm farther toward
# the wall than the user's latest combined script. Migrate only those exact
# default values; retain genuine user-customized calibrations.
OLD_PAPER_POINTS = {
    key: [coords[0] - 2.0, coords[1], coords[2]] for key, coords in PAPER_POINTS.items()
}

DEFAULT_SETTINGS = {
    "ip": "192.168.1.208",   # xArm; NOT the Dobot/MG400 IP
    "width_mm": 359.6,     # logical drawing-paper width; mapping uses measured XYZ points
    "height_mm": 235.0,    # logical drawing-paper height
    "margin_mm": 12.0,     # keep away from reach/edge limits
    "offset_x_mm": -7.0,   # last marker adjustment; RECHECK for actual installed marker
    "safe_x_mm": -480.0,   # validated pen-up travel X plane from combined app
    "draw_speed": 25.0,    # mm/s
    "travel_speed": 35.0,  # mm/s
    "acceleration": 150.0,# mm/s^2
    "simplify_mm": 0.35,   # retain corners but eliminate mouse jitter
    "rpy": [-179.7, -3.6, 179.1],
    "ready_xyz": [-391.8, 111.0, 597.7],  # pose associated with READY_JOINTS
    "g2_collision_model": True,  # only if G2 gripper is actually installed
    "move_ready_first": True,   # same convenience used by the previous combined app
    "paper_points": PAPER_POINTS,
}


def lerp(a, b, t):
    return tuple(x + (y-x)*t for x, y in zip(a, b))


def add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def scale(a, k):
    return tuple(x*k for x in a)


def edge(a, middle, b, t):
    """Interpolate an edge through the midpoint, or linearly if absent."""
    if middle is None:
        return lerp(a, b, t)
    # Lagrange interpolation at t={0, 0.5, 1}.
    wa = 2*(t-0.5)*(t-1)
    wm = 4*t*(1-t)
    wb = 2*t*(t-0.5)
    return add(add(scale(a, wa), scale(middle, wm)), scale(b, wb))


def paper_point(u, v, controls):
    """8-point Coons interpolation over the wall paper, u/v in [0,1].

    u increases left->right (+Y); v increases top->bottom (-Z).
    All 8 known control points are reproduced exactly. No invented center.
    """
    tl, tr, bl, br = (controls[k] for k in ("TL", "TR", "BL", "BR"))
    top = edge(tl, controls.get("TM"), tr, u)
    bottom = edge(bl, controls.get("BM"), br, u)
    left = edge(tl, controls.get("ML"), bl, v)
    right = edge(tr, controls.get("MR"), br, v)
    patch = add(add(scale(top, 1-v), scale(bottom, v)),
                add(scale(left, 1-u), scale(right, u)))
    bilinear_corners = add(
        add(scale(tl, (1-u)*(1-v)), scale(tr, u*(1-v))),
        add(scale(bl, (1-u)*v), scale(br, u*v)))
    return sub(patch, bilinear_corners)


def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def point_line_distance(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    den = dx*dx + dy*dy
    if den < 1e-12:
        return distance(point, a)
    t = max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/den))
    return distance(point, (a[0]+t*dx, a[1]+t*dy))


def simplify(points, tolerance):
    """Ramer-Douglas-Peucker simplification (iterative, preserves endpoints)."""
    if len(points) < 3 or tolerance <= 0:
        return points[:]
    keep = {0, len(points)-1}
    stack = [(0, len(points)-1)]
    while stack:
        start, end = stack.pop()
        if end-start <= 1:
            continue
        k = max(range(start+1, end), key=lambda i: point_line_distance(points[i], points[start], points[end]))
        if point_line_distance(points[k], points[start], points[end]) > tolerance:
            keep.add(k)
            stack.extend([(start, k), (k, end)])
    return [points[i] for i in sorted(keep)]


def resample_max_step(points, max_step=3.0):
    if not points:
        return []
    out = [points[0]]
    for p in points[1:]:
        prev = out[-1]
        length = distance(prev, p)
        n = max(1, math.ceil(length/max_step))
        for i in range(1, n+1):
            out.append((prev[0]+(p[0]-prev[0])*i/n,
                        prev[1]+(p[1]-prev[1])*i/n))
    return out


def make_path(stroke, tol):
    pts = [tuple(map(float, p)) for p in stroke["points"]]
    if len(pts) == 1:
        # Tiny mark for a click; still a stroke with controllable geometry.
        x, y = pts[0]
        pts = [(x, y), (x+0.6, y)]
    if stroke.get("shape") == "pen":
        pts = simplify(pts, tol)
    return resample_max_step(pts, max_step=3.0)


def validate_settings(settings):
    for field in ("width_mm", "height_mm", "margin_mm", "safe_x_mm", "draw_speed", "travel_speed", "acceleration", "simplify_mm", "offset_x_mm"):
        x = float(settings[field])
        if not math.isfinite(x):
            raise ValueError(f"Invalid {field}")
    w, h = float(settings["width_mm"]), float(settings["height_mm"])
    margin = float(settings["margin_mm"])
    if not (100 <= w <= 700 and 100 <= h <= 600):
        raise ValueError("Paper logical dimensions are outside expected range.")
    if margin < 0 or margin * 2 >= min(w, h):
        raise ValueError("Margin must be 0 mm or more and fit the paper.")
    # No arbitrary narrow safe-X window: geometry clearance below is the real check.
    if abs(float(settings["offset_x_mm"])) > 30:
        raise ValueError("Pen X adjustment exceeds ±30 mm; check tool calibration.")
    if not (1 <= float(settings["draw_speed"]) <= 500):
        raise ValueError("Draw speed must be 1–500 mm/s.")
    if not (1 <= float(settings["travel_speed"]) <= 500):
        raise ValueError("Travel speed must be 1–500 mm/s.")
    if not (10 <= float(settings["acceleration"]) <= 3000):
        raise ValueError("Acceleration must be 10–3000 mm/s².")
    if not (0 <= float(settings["simplify_mm"]) <= 3):
        raise ValueError("Simplification must be 0–3 mm.")
    controls = settings["paper_points"]
    for name in ("TL", "TR", "BL", "BR"):
        if name not in controls:
            raise ValueError("Missing calibrated paper corner: " + name)
    for name, p in controls.items():
        if len(p) != 3 or not all(math.isfinite(float(x)) for x in p):
            raise ValueError(f"Invalid 3D point {name}")
    if len(settings["rpy"]) != 3 or not all(math.isfinite(float(x)) for x in settings["rpy"]):
        raise ValueError("Invalid tool orientation")
    if len(settings["ready_xyz"]) != 3:
        raise ValueError("Invalid ready pose")
    if not isinstance(settings.get("g2_collision_model"), bool):
        raise ValueError("G2 collision model must be true or false")
    if not isinstance(settings.get("move_ready_first", True), bool):
        raise ValueError("Move-ready-first setting must be true or false")
    # The safe travel plane must be on the robot side (+X) of every reachable
    # pen-contact point. Checking an interior grid catches Coons patch curvature.
    clearance = min(
        float(settings["safe_x_mm"]) - (
            paper_point(i / 8, j / 8, settings["paper_points"])[0]
            + float(settings["offset_x_mm"])
        )
        for i in range(9) for j in range(9)
    )
    if clearance < 7.0:
        raise ValueError(
            f"Safe X plane has only {clearance:.1f} mm minimum clearance "
            "from the pen-contact surface (require ≥7 mm)."
        )
    return True


def map_to_robot(p, settings, airborne=False):
    """Convert logical canvas millimeters to calibrated robot Cartesian XYZ."""
    x, y = p
    u = x/float(settings["width_mm"])
    v = y/float(settings["height_mm"])
    if not (0 <= u <= 1 and 0 <= v <= 1):
        raise ValueError("Stroke exceeds calibrated paper.")
    cx, cy, cz = paper_point(u, v, settings["paper_points"])
    correction = float(settings["offset_x_mm"])
    # Reuse the proven constant pen-up plane (-480), rather than a variable
    # plane from "contact X + 25" that differed from the combined app.
    return (float(settings["safe_x_mm"]) if airborne else cx + correction, cy, cz)


def validate_strokes(strokes, settings):
    w, h, m = (float(settings[k]) for k in ("width_mm", "height_mm", "margin_mm"))
    for stroke in strokes:
        if not stroke.get("points"):
            raise ValueError("Empty stroke")
        for x, y in stroke["points"]:
            if not all(math.isfinite(float(v)) for v in (x,y)):
                raise ValueError("Invalid drawing coordinate")
            if not (m-0.15 <= x <= w-m+0.15 and m-0.15 <= y <= h-m+0.15):
                raise ValueError("A stroke is inside the edge safety margin or outside the page")


def robot_plan(strokes, settings, air=False):
    """Yield (xyz, speed, blend, wait) starting at READY_JOINTS.

    IMPORTANT: No Cartesian motion to READY XYZ is performed. The robot
    operator must deliberately position at READY_JOINTS first. Initial travel
    moves directly forward along -X at the ready Y/Z to the proven safe plane,
    then traverses that constant X plane between strokes. The robot finally
    returns to the gateway on the SAME safe X plane, never to READY XYZ.
    """
    validate_settings(settings)
    validate_strokes(strokes, settings)
    tol = float(settings["simplify_mm"])
    draw_speed = float(settings["draw_speed"])
    travel_speed = float(settings["travel_speed"])
    ready = tuple(settings["ready_xyz"])
    safe_x = float(settings["safe_x_mm"])
    # First move: from the joint-defined ready pose toward the wall along X
    # only, at stable Y/Z; never seek READY via Cartesian IK.
    yield (safe_x, ready[1], ready[2]), travel_speed, -1.0, True
    for st in strokes:
        path = make_path(st, tol)
        if len(path) < 2:
            continue
        # Do not execute an uncontrolled number of queued robot commands.
        if len(path) > 2000:
            raise ValueError("Single stroke is too detailed (>2000 points). Simplify it.")
        start_hover = map_to_robot(path[0], settings, airborne=True)
        yield start_hover, travel_speed, -1.0, True
        if not air:
            yield map_to_robot(path[0], settings, airborne=False), 8.0, -1.0, True
        # Buffered path: radius>=0 & wait=False allows smooth continuous drawing.
        # Flush with wait=True at the final point BEFORE retracting.
        for i, point in enumerate(path[1:], start=1):
            last = i == len(path)-1
            xyz = map_to_robot(point, settings, airborne=air)
            yield xyz, draw_speed, -1.0 if last else 0.35, last
        if not air:
            yield map_to_robot(path[-1], settings, airborne=True), 8.0, -1.0, True
    # Finish at the same known pen-up gateway, not at Cartesian READY XYZ.
    # The AIR TEST exercises this return traversal before physical contact.
    yield (safe_x, ready[1], ready[2]), travel_speed, -1.0, True


@dataclass
class Stroke:
    shape: str
    points: list[tuple[float, float]]

    def json(self):
        return {"shape": self.shape, "points": [[round(x,3), round(y,3)] for x,y in self.points]}


class DrawingApp:
    def __init__(self, root):
        self.root = root
        root.title("xArm 850 | Freehand Paper Drawer")
        root.geometry("1110x775")
        root.minsize(930, 650)
        self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        if SETTINGS_FILE.exists():
            try:
                saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                self.settings.update(saved)
                if self.settings.get("paper_points") == OLD_PAPER_POINTS:
                    self.settings["paper_points"] = json.loads(json.dumps(PAPER_POINTS))
                # Obsolete lift_x_mm from old settings is intentionally ignored.
                self.settings.pop("lift_x_mm", None)
                validate_settings(self.settings)
            except Exception as ex:
                self.settings = json.loads(json.dumps(DEFAULT_SETTINGS))
                messagebox.showwarning("Settings", f"Saved settings could not be loaded: {ex}\nUsing project defaults.")
        self.strokes: list[Stroke] = []
        self.redo_stack: list[Stroke] = []
        self.active = None
        self.start = None
        self.pen_tool = tk.StringVar(value="pen")
        self.show_transfers = tk.BooleanVar(value=False)
        self.arm = None
        self.arm_lock = threading.Lock()
        self.connected = False
        self.arm_enabled_by_app = False
        self.busy = False
        self.stop_event = threading.Event()
        self.events = queue.Queue()
        self.drawing_dirty = True
        self.verified_gateway = None  # only from a successfully completed run
        self._build()
        self.root.after(80, self.poll_events)
        self.redraw()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        shell = ttk.Frame(self.root, padding=10)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="xArm 850  /  Freehand Wall Drawing", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(shell, text="Draw real strokes (not PNG outlines). Based on the 8-point calibrated wall paper.", foreground="#555").pack(anchor="w", pady=(1, 7))

        bar = ttk.Frame(shell)
        bar.pack(fill="x", pady=(0, 7))
        for name in ("pen", "line", "rectangle", "ellipse", "erase"):
            ttk.Radiobutton(bar, text=name.capitalize(), value=name, variable=self.pen_tool).pack(side="left", padx=(0, 9))
        for label, action in [("Undo", self.undo), ("Redo", self.redo), ("Clear", self.clear),
                              ("Save drawing", self.save_drawing), ("Load drawing", self.load_drawing)]:
            ttk.Button(bar, text=label, command=action).pack(side="left", padx=2)
        ttk.Checkbutton(bar, text="Show pen-up travel", variable=self.show_transfers, command=self.redraw).pack(side="right")

        middle = ttk.Frame(shell)
        middle.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(middle, bg="#FFFFFF", highlightbackground="#9BA6B2", highlightthickness=1,
                                cursor="crosshair")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.mouse_down)
        self.canvas.bind("<B1-Motion>", self.mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.mouse_up)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.root.bind("<Control-z>", lambda _e: self.undo())
        self.root.bind("<Control-y>", lambda _e: self.redo())

        side = ttk.Frame(middle, padding=(12, 0, 0, 0), width=285)
        side.pack(side="right", fill="y")
        self.vars = {}
        def field(label, key, width=13):
            line = ttk.Frame(side)
            line.pack(fill="x", pady=2)
            ttk.Label(line, text=label).pack(side="left")
            value = tk.StringVar(value=str(self.settings[key]))
            ent = ttk.Entry(line, textvariable=value, width=width)
            ent.pack(side="right")
            ent.bind("<FocusOut>", lambda _e: self.read_fields(silent=True))
            self.vars[key] = value
        ttk.Label(side, text="Paper & motion", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        field("Width (mm)", "width_mm")
        field("Height (mm)", "height_mm")
        field("Edge margin (mm)", "margin_mm")
        ttk.Separator(side).pack(fill="x", pady=8)
        field("Pen X adjustment (mm)", "offset_x_mm")
        nudge = ttk.Frame(side)
        nudge.pack(fill="x", pady=(0, 3))
        ttk.Button(nudge, text="Pen -0.5 mm", command=lambda: self.nudge_offset(-0.5)).pack(side="left", expand=True, fill="x", padx=(0,2))
        ttk.Button(nudge, text="Pen +0.5 mm", command=lambda: self.nudge_offset(0.5)).pack(side="left", expand=True, fill="x", padx=(2,0))
        field("Pen-up safe X (mm)", "safe_x_mm")
        field("Draw speed (mm/s)", "draw_speed")
        field("Travel speed (mm/s)", "travel_speed")
        field("Acceleration", "acceleration")
        field("Simplification (mm)", "simplify_mm")
        ttk.Separator(side).pack(fill="x", pady=8)
        self.g2_model_var = tk.BooleanVar(value=bool(self.settings["g2_collision_model"]))
        ttk.Checkbutton(side, text="G2 gripper fitted (collision model 9)",
                        variable=self.g2_model_var).pack(fill="x", pady=2)
        self.move_ready_first_var = tk.BooleanVar(value=bool(self.settings.get("move_ready_first", True)))
        field("Robot IP", "ip", 17)
        ttk.Button(side, text="Save settings", command=self.save_settings).pack(fill="x", pady=(3, 2))
        ttk.Button(side, text="Connect robot (no motion)", command=self.connect).pack(fill="x", pady=2)
        ttk.Button(side, text="Recover / Re-arm", command=self.recover_robot).pack(fill="x", pady=2)
        ttk.Button(side, text="Disable robot", command=self.disable_robot).pack(fill="x", pady=2)
        ttk.Button(side, text="Initial Position (J1-J6 = 0°)", command=self.move_initial_position).pack(fill="x", pady=2)
        ttk.Button(side, text="Move to READY", command=self.move_ready).pack(fill="x", pady=2)
        ttk.Checkbutton(side, text="Move to READY before AIR / DRAW",
                        variable=self.move_ready_first_var).pack(fill="x", pady=(4,2))
        ttk.Button(side, text="Show planned XYZ path", command=self.inspect_path).pack(fill="x", pady=2)
        ttk.Button(side, text="Test entire drawing in AIR (optional)", command=lambda: self.run_robot(True)).pack(fill="x", pady=(12,2))
        ttk.Button(side, text="DRAW on paper", command=lambda: self.run_robot(False)).pack(fill="x", pady=2)
        stop = tk.Button(side, text="STOP ROBOT", bg="#AF2F31", fg="white", activebackground="#7F2222",
                         font=("Segoe UI", 11, "bold"), command=self.stop_robot)
        stop.pack(fill="x", pady=(12, 4), ipady=5)
        ttk.Label(side, text="Use the physical E-stop for emergencies.", foreground="#9B3333", wraplength=265).pack(anchor="w")
        ttk.Separator(side).pack(fill="x", pady=10)
        ttk.Label(side, text="AIR test is optional. READY uses the same joint target as the previous combined app.\nKnown pen-up X = -480 mm.\nThe -7 mm offset is historical: verify with the installed pen.",
                  foreground="#555", wraplength=280, justify="left").pack(anchor="w")
        self.status = tk.StringVar(value="OFFLINE drawing mode. Nothing moves until you connect and confirm.")
        status_line = ttk.Frame(shell)
        status_line.pack(fill="x", pady=(8,0))
        ttk.Label(status_line, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)
        self.count_label = ttk.Label(status_line, text="0 strokes")
        self.count_label.pack(side="right")

    def page_rect(self):
        cw, ch = max(100, self.canvas.winfo_width()), max(100, self.canvas.winfo_height())
        w = float(self.settings["width_mm"])
        h = float(self.settings["height_mm"])
        s = min((cw-35)/w, (ch-35)/h)
        x0, y0 = (cw-w*s)/2, (ch-h*s)/2
        return x0, y0, s

    def mm_to_px(self, p):
        x0,y0,s = self.page_rect()
        return x0+p[0]*s, y0+p[1]*s

    def px_to_mm(self, x, y):
        x0,y0,s = self.page_rect()
        w,h,m = (float(self.settings[k]) for k in ("width_mm","height_mm","margin_mm"))
        return (max(m, min(w-m, (x-x0)/s)), max(m, min(h-m, (y-y0)/s)))

    def draw_stroke(self, stroke, color="#1F2937", dash=None, width=2):
        if not stroke.points:
            return
        pts = [self.mm_to_px(p) for p in stroke.points]
        if len(pts) == 1:
            x,y = pts[0]
            self.canvas.create_oval(x-1.5,y-1.5,x+1.5,y+1.5, fill=color,outline="")
            return
        xy = [v for p in pts for v in p]
        self.canvas.create_line(*xy, fill=color, width=width, dash=dash,
                                capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def redraw(self):
        c = self.canvas
        c.delete("all")
        x0,y0,s = self.page_rect()
        w,h,m = (float(self.settings[k]) for k in ("width_mm","height_mm","margin_mm"))
        c.create_rectangle(x0, y0, x0+w*s, y0+h*s, outline="#788493", width=1)
        c.create_rectangle(x0+m*s, y0+m*s, x0+(w-m)*s, y0+(h-m)*s,
                           outline="#CBD5E1", dash=(4,5))
        if self.show_transfers.get() and len(self.strokes) > 1:
            for a,b in zip(self.strokes[:-1], self.strokes[1:]):
                if a.points and b.points:
                    x1,y1 = self.mm_to_px(a.points[-1]); x2,y2 = self.mm_to_px(b.points[0])
                    c.create_line(x1,y1,x2,y2, fill="#B8A98D", dash=(3,5), width=1)
        for stroke in self.strokes:
            self.draw_stroke(stroke)
        if self.active is not None:
            self.draw_stroke(self.active, color="#2563EB")
        c.create_text(x0+4, y0+5, text="TOP LEFT", fill="#7A8290", anchor="nw", font=("Segoe UI",8))
        self.count_label.configure(text=f"{len(self.strokes)} strokes")

    def mark_dirty(self):
        # Editing the drawing does not physically move the robot, so it must not
        # invalidate a verified pen-up gateway.
        self.drawing_dirty = True

    def mouse_down(self, e):
        if self.busy:
            return
        tool = self.pen_tool.get()
        p = self.px_to_mm(e.x,e.y)
        if tool == "erase":
            self.erase_near(p)
            return
        self.start = p
        self.active = Stroke(tool, [p])
        self.redraw()

    def mouse_drag(self,e):
        if not self.active:
            return
        p = self.px_to_mm(e.x,e.y)
        if self.active.shape == "pen":
            if distance(self.active.points[-1], p) >= 0.45:
                self.active.points.append(p)
        else:
            self.active.points = self.shape_points(self.active.shape, self.start, p)
        self.redraw()

    def mouse_up(self,e):
        if not self.active:
            return
        p = self.px_to_mm(e.x,e.y)
        if self.active.shape == "pen":
            if distance(self.active.points[-1],p)>0.3:
                self.active.points.append(p)
        else:
            self.active.points = self.shape_points(self.active.shape,self.start,p)
        if self.active.points:
            self.strokes.append(self.active)
            self.redo_stack.clear()
            self.mark_dirty()
        self.active = None
        self.redraw()

    def shape_points(self, shape, a, b):
        if shape == "line":
            return [a,b]
        l,r = min(a[0], b[0]), max(a[0],b[0])
        t,btm = min(a[1],b[1]), max(a[1],b[1])
        if shape == "rectangle":
            return [(l,t),(r,t),(r,btm),(l,btm),(l,t)]
        if shape == "ellipse":
            cx,cy=(l+r)/2,(t+btm)/2
            rx,ry=(r-l)/2,(btm-t)/2
            count=max(24,min(200,math.ceil(math.pi*(rx+ry)/2)))
            return [(cx+rx*math.cos(2*math.pi*i/count),cy+ry*math.sin(2*math.pi*i/count)) for i in range(count+1)]
        return [a,b]

    def erase_near(self,p):
        closest, index = float("inf"), None
        for i,stroke in enumerate(self.strokes):
            for a,b in zip(stroke.points[:-1],stroke.points[1:]):
                d = point_line_distance(p,a,b)
                if d<closest:
                    closest,index=d,i
            if len(stroke.points)==1:
                d=distance(p,stroke.points[0])
                if d<closest: closest,index=d,i
        if index is not None and closest < 6:
            self.strokes.pop(index)
            self.redo_stack.clear()
            self.mark_dirty()
            self.redraw()

    def undo(self):
        if not self.busy and self.strokes:
            self.redo_stack.append(self.strokes.pop())
            self.mark_dirty(); self.redraw()

    def redo(self):
        if not self.busy and self.redo_stack:
            self.strokes.append(self.redo_stack.pop())
            self.mark_dirty(); self.redraw()

    def clear(self):
        if self.busy:
            return
        if self.strokes and messagebox.askyesno("Clear", "Clear all strokes?"):
            self.strokes.clear(); self.redo_stack.clear(); self.mark_dirty(); self.redraw()

    def read_fields(self,silent=False):
        if self.busy:
            return False
        try:
            changed = self.settings.copy()
            for key, var in self.vars.items():
                changed[key] = var.get().strip() if key=="ip" else float(var.get())
            changed["g2_collision_model"] = bool(self.g2_model_var.get())
            changed["move_ready_first"] = bool(self.move_ready_first_var.get())
            validate_settings(changed)
            if changed != self.settings:
                self.settings=changed
                self.mark_dirty()
                self.redraw()
            return True
        except (ValueError,KeyError) as ex:
            if not silent:
                messagebox.showerror("Invalid settings",str(ex))
            return False

    def nudge_offset(self, amount):
        if self.busy:
            return
        try:
            current = float(self.vars["offset_x_mm"].get())
            self.vars["offset_x_mm"].set(f"{current + amount:.2f}")
            self.read_fields(silent=True)
        except Exception:
            pass

    def save_settings(self):
        if not self.read_fields():
            return
        SETTINGS_FILE.write_text(json.dumps(self.settings,indent=2), encoding="utf-8")
        self.status.set(f"Saved settings to {SETTINGS_FILE.name}")

    def save_drawing(self):
        if self.busy or not self.read_fields():
            return
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Freehand drawing", "*.json")],
                                                initialfile="my_xarm_drawing.json")
        if filename:
            Path(filename).write_text(json.dumps({"format":"xarm850-freehand-v1",
                   "width_mm":self.settings["width_mm"], "height_mm":self.settings["height_mm"],
                   "strokes":[s.json() for s in self.strokes]},indent=2),encoding="utf-8")
            self.status.set(f"Saved {len(self.strokes)} strokes")

    def load_drawing(self):
        if self.busy:
            return
        name = filedialog.askopenfilename(filetypes=[("Freehand drawing","*.json")])
        if not name:
            return
        try:
            data=json.loads(Path(name).read_text(encoding="utf-8"))
            if data.get("format")!="xarm850-freehand-v1":
                raise ValueError("Not an xArm freehand drawing JSON")
            # Rescale to current paper logical dimensions if necessary.
            sx=float(self.settings["width_mm"])/float(data["width_mm"])
            sy=float(self.settings["height_mm"])/float(data["height_mm"])
            strokes=[Stroke(item.get("shape","pen"),[(float(x)*sx,float(y)*sy) for x,y in item["points"]])
                     for item in data["strokes"]]
            validate_strokes([s.json() for s in strokes],self.settings)
            if len(strokes)>4000:
                raise ValueError("Too many strokes")
            self.strokes=strokes
            self.redo_stack=[]
            self.mark_dirty(); self.redraw()
            self.status.set(f"Loaded {len(strokes)} strokes")
        except Exception as ex:
            messagebox.showerror("Load drawing",str(ex))

    def prepared(self):
        if not self.read_fields():
            return None
        if not self.strokes:
            messagebox.showinfo("Empty drawing", "Draw some strokes first.")
            return None
        data=[s.json() for s in self.strokes]
        try:
            validate_strokes(data,self.settings)
            for s in data:
                if len(make_path(s,float(self.settings["simplify_mm"])))>2000:
                    raise ValueError("One stroke has more than 2000 points")
            return data
        except Exception as ex:
            messagebox.showerror("Path problem",str(ex))
            return None

    def inspect_path(self):
        data=self.prepared()
        if data is None:
            return
        plan=list(robot_plan(data,self.settings,air=False))
        detail=tk.Toplevel(self.root)
        detail.title("Robot path preview (XYZ in mm)")
        detail.geometry("740x490")
        txt=tk.Text(detail,wrap="none",font=("Consolas",10))
        txt.pack(fill="both",expand=True)
        txt.insert("end",f"Paper {self.settings['width_mm']} × {self.settings['height_mm']} mm\n")
        txt.insert("end",f"8-point interpolation | X offset {self.settings['offset_x_mm']} mm | safe X {self.settings['safe_x_mm']} mm\n")
        txt.insert("end","START: READY joints, or a pen-up gateway if automatic READY is disabled.\n")
        txt.insert("end",f"{len(self.strokes)} strokes | {len(plan)} robot waypoints\n\n")
        for i,(xyz,speed,radius,wait) in enumerate(plan):
            txt.insert("end",f"{i:04d}: X={xyz[0]:9.2f} Y={xyz[1]:9.2f} Z={xyz[2]:9.2f} "
                      f"speed={speed:5.1f} blend={radius:5.2f} wait={wait}\n")
        txt.configure(state="disabled")

    def connect(self):
        if self.busy or not self.read_fields():
            return
        if self.arm is not None and self.connected:
            self.status.set("Robot is already connected. No motion authorized.")
            return
        self.busy=True
        self.verified_gateway = None
        self.status.set("Connecting to xArm (no motion)...")
        def work():
            try:
                from xarm.wrapper import XArmAPI
                arm=XArmAPI(self.settings["ip"],is_radian=False)
                if not arm.connected:
                    raise RuntimeError("SDK reports robot not connected")
                code, pose=arm.get_position(is_radian=False)
                if code!=0:
                    raise RuntimeError(f"get_position returned error {code}")
                self.arm=arm
                self.connected=True
                self.events.put(("connected",pose))
            except Exception as ex:
                self.events.put(("error",str(ex)))
            finally:
                self.events.put(("idle",None))
        threading.Thread(target=work,daemon=True).start()

    @staticmethod
    def read_joint_angles(arm):
        code, angles = arm.get_servo_angle(is_radian=False)
        DrawingApp.check(code, "Read current joint angles")
        if len(angles) < 6:
            raise RuntimeError("Robot did not return six joint angles")
        return [float(v) for v in angles[:6]]

    @staticmethod
    def is_near_joints(actual, target, tolerance):
        # Compare actual joint angles, NOT equivalent TCP poses or wrapped RPY:
        # robot can reach the same XYZ with dangerously different IK solutions.
        return all(abs(a - b) <= tolerance for a, b in zip(actual, target))

    @staticmethod
    def check_ready_pose(arm, settings):
        """Require the known READY joint configuration.

        Unlike the previous safe-ready revision, Cartesian XYZ/RPY differences
        are reported as warnings instead of blocking motion. This matches the
        older combined app, where READY was fundamentally a joint pose.
        """
        current = DrawingApp.read_joint_angles(arm)
        if not DrawingApp.is_near_joints(current, READY_JOINTS, READY_JOINT_TOLERANCE_DEG):
            raise RuntimeError(
                "Robot is not at READY joints. "
                f"Current: {[round(v, 1) for v in current]} | Target: {READY_JOINTS}"
            )
        warnings = []
        try:
            code, pose = arm.get_position(is_radian=False)
            DrawingApp.check(code, "Read READY Cartesian pose")
            reference = settings["ready_xyz"]
            if any(abs(float(pose[i]) - float(reference[i])) > READY_CART_TOLERANCE_MM for i in range(3)):
                warnings.append(
                    f"READY TCP XYZ differs from the old reference: current "
                    f"{[round(float(v),1) for v in pose[:3]]}, old {reference}"
                )
            if len(pose) >= 6:
                diffs=[]
                for i in range(3):
                    actual, expected = float(pose[i+3]), float(settings["rpy"][i])
                    diffs.append(abs((actual-expected+180.0)%360.0-180.0))
                if max(diffs) > READY_RPY_TOLERANCE_DEG:
                    warnings.append(
                        f"READY RPY differs from old pen reference: current "
                        f"{[round(float(v),1) for v in pose[3:6]]}, old {settings['rpy']}"
                    )
        except Exception as ex:
            warnings.append(f"Could not compare READY TCP reference: {ex}")
        return current, warnings

    @staticmethod
    def check_verified_gateway(arm, settings, record):
        """Allow a repeat run after reaching pen-up waypoint in this session.

        Validation is both Cartesian AND joint-based. If an operator manually
        moves the arm after the air run, the saved gateway record is invalid.
        """
        if record is None:
            raise RuntimeError("No verified pen-up gateway from a completed test")
        target = (float(settings["safe_x_mm"]), float(settings["ready_xyz"][1]),
                  float(settings["ready_xyz"][2]))
        if any(abs(record["xyz"][i] - target[i]) > 2.0 for i in range(3)):
            raise RuntimeError("Gateway record does not match current settings")
        code, pose = arm.get_position(is_radian=False)
        DrawingApp.check(code, "Verify pen-up gateway XYZ")
        if any(abs(float(pose[i]) - target[i]) > 2.0 for i in range(3)):
            raise RuntimeError(
                "Robot has left its verified pen-up gateway. "
                "Do not resume automatically; return via verified joint/controller motion."
            )
        if len(pose) >= 6:
            for i in range(3):
                delta = abs((float(pose[i + 3]) - float(settings["rpy"][i])
                             + 180.0) % 360.0 - 180.0)
                if delta > 3.0:
                    raise RuntimeError("Pen orientation changed since the air test")
        joints = DrawingApp.read_joint_angles(arm)
        if not DrawingApp.is_near_joints(joints, record["joints"], 1.5):
            raise RuntimeError("Robot joint configuration changed since the air test")
        return joints

    def enable_position_mode_with_protection(self, arm, settings):
        """Prepare position mode using the same best-effort safety setup as the combined app."""
        try:
            arm.clean_warn()
        except Exception:
            pass
        try:
            arm.clean_error()
        except Exception:
            pass
        if settings["g2_collision_model"]:
            try:
                code = arm.set_collision_tool_model(9)
                if code != 0:
                    self.events.put(("notice", f"G2 collision-model setup returned code {code}"))
            except Exception as ex:
                self.events.put(("notice", f"G2 collision-model setup skipped: {ex}"))
        try:
            code = arm.set_self_collision_detection(True)
            if code != 0:
                self.events.put(("notice", f"Self-collision setup returned code {code}"))
        except Exception as ex:
            self.events.put(("notice", f"Self-collision setup unavailable: {ex}"))
        self.check(arm.motion_enable(enable=True), "Enable motion")
        self.arm_enabled_by_app = True
        self.check(arm.set_mode(0), "Set position mode")
        if self.stop_event.is_set():
            raise RuntimeError("Stopped during setup")
        self.check(arm.set_state(0), "Set state ready")

    def disable_robot(self):
        if self.busy:
            messagebox.showwarning("Robot busy", "STOP the current operation before disabling.")
            return
        if not self.connected or self.arm is None:
            return
        try:
            try:
                self.arm.set_state(4)
            except Exception:
                pass
            self.arm.motion_enable(enable=False)
            self.arm_enabled_by_app = False
            self.verified_gateway = None
            self.status.set("Robot disabled. Use Recover / Re-arm before movement.")
        except Exception as ex:
            messagebox.showerror("Disable robot", str(ex))

    def recover_robot(self):
        """Recover/re-arm after STOP or a recoverable controller fault."""
        if self.busy or not self.connected or self.arm is None:
            if not self.connected:
                messagebox.showwarning("Not connected", "Connect robot first.")
            return
        arm = self.arm
        self.status.set("Recovering / re-arming robot...")
        self.stop_event.clear()
        try:
            self.enable_position_mode_with_protection(arm, self.settings)
            self.status.set("Robot recovered / re-armed in position mode.")
        except Exception as ex:
            self.status.set("Recovery failed")
            messagebox.showerror("Recover / Re-arm", str(ex))

    def move_initial_position(self):
        """Move to UFactory Studio Initial Position (all six joints = 0°)."""
        if self.busy or not self.read_fields():
            return
        if not self.connected or self.arm is None:
            messagebox.showwarning("Not connected", "Connect robot first.")
            return
        arm = self.arm
        try:
            joints = self.read_joint_angles(arm)
        except Exception as ex:
            messagebox.showerror("Initial Position", str(ex))
            return
        if self.is_near_joints(joints, INITIAL_JOINTS, INITIAL_JOINT_TOLERANCE_DEG):
            self.status.set("Robot is already near Initial Position.")
            return
        if not messagebox.askyesno(
            "Move to Initial Position",
            "Move J1-J6 to 0° using joint motion?\n\n"
            f"Current: {[round(v,1) for v in joints]}\n"
            f"Speed: {INITIAL_JOINT_SPEED} deg/s\n\n"
            "Keep the workspace clear and watch the entire movement."
        ):
            return
        self.busy = True
        self.verified_gateway = None
        self.stop_event.clear()
        self.status.set("Moving to Initial Position...")
        settings = json.loads(json.dumps(self.settings))
        def work():
            try:
                self.enable_position_mode_with_protection(arm, settings)
                self.check(arm.set_servo_angle(
                    angle=INITIAL_JOINTS, speed=INITIAL_JOINT_SPEED, wait=True, is_radian=False
                ), "Move to Initial Position")
                self.events.put(("initial_completed", None))
            except Exception as ex:
                self.events.put(("error", str(ex)))
                try: arm.set_state(4)
                except Exception: pass
            finally:
                self.events.put(("idle", None))
        threading.Thread(target=work, daemon=True).start()

    def move_ready(self):
        """Move directly to the same READY joint pose used by the previous combined app.

        No artificial requirement to start from Initial Position. The SDK joint
        command is issued from the robot's current configuration, matching the
        older working code.
        """
        if self.busy or not self.read_fields():
            return
        if not self.connected or self.arm is None:
            messagebox.showwarning("Not connected", "Connect robot first.")
            return
        arm = self.arm
        try:
            joints = self.read_joint_angles(arm)
        except Exception as ex:
            messagebox.showerror("Move READY", str(ex))
            return
        if self.is_near_joints(joints, READY_JOINTS, READY_JOINT_TOLERANCE_DEG):
            _, warnings = self.check_ready_pose(arm, self.settings)
            self.status.set("Robot is already at READY." + (" " + " | ".join(warnings) if warnings else ""))
            return
        prompt = (
            "Move to the previously used READY joint angles from the CURRENT pose?\n\n"
            f"FROM: {[round(v,1) for v in joints]}\n"
            f"TO:   {READY_JOINTS}\n"
            f"Speed: {READY_JOINT_SPEED} deg/s\n\n"
            "This now matches the previous combined xArm app: it does not require J1-J6 = 0° first. "
            "Keep the workspace clear and watch the move."
        )
        if not messagebox.askyesno("Confirm READY move", prompt):
            return
        self.busy = True
        self.verified_gateway = None
        self.stop_event.clear()
        self.status.set("Moving to READY joint configuration...")
        settings = json.loads(json.dumps(self.settings))
        def work():
            try:
                self.enable_position_mode_with_protection(arm, settings)
                self.check(arm.set_servo_angle(
                    angle=READY_JOINTS, speed=READY_JOINT_SPEED, wait=True, is_radian=False
                ), "Joint-space Move READY")
                _, warnings = self.check_ready_pose(arm, settings)
                self.events.put(("ready_completed", warnings))
            except Exception as ex:
                self.events.put(("error", str(ex)))
                try: arm.set_state(4)
                except Exception: pass
            finally:
                self.events.put(("idle", None))
        threading.Thread(target=work, daemon=True).start()

    def run_robot(self,air):
        if self.busy:
            return
        data=self.prepared()
        if data is None:
            return
        if not self.connected or self.arm is None:
            messagebox.showwarning("Not connected", "Connect robot first. Drawing/preview works offline.")
            return
        plan=list(robot_plan(data,self.settings,air=air))
        auto_ready=bool(self.move_ready_first_var.get())
        name=(f"AIR TEST (pen stays on safe X={self.settings['safe_x_mm']} mm plane)"
              if air else "REAL PEN DRAWING")
        info=(f"{name}\n\n{len(data)} strokes; {len(plan)} robot commands.\n"
              f"Paper: {self.settings['width_mm']} × {self.settings['height_mm']} mm\n"
              f"X pen adjustment: {self.settings['offset_x_mm']} mm\n"
              f"Pen-up travel plane: X={self.settings['safe_x_mm']} mm\n"
              f"Robot: {self.settings['ip']}\n"
              f"Move to READY first: {auto_ready}\n\n"
              "AIR testing is optional. Check the physical pen/TCP, paper, obstacles and E-stop access. Continue?")
        if not messagebox.askyesno("Confirm robot motion",info):
            return
        if not air and not messagebox.askyesno("Begin real drawing",
              "Begin REAL drawing on paper now?"):
            return
        self.busy=True
        self.stop_event.clear()
        self.status.set("AIR TEST running..." if air else "DRAWING on paper...")
        settings=json.loads(json.dumps(self.settings))
        settings["move_ready_first"] = auto_ready
        gateway_before = json.loads(json.dumps(self.verified_gateway)) if self.verified_gateway is not None else None
        arm=self.arm

        def work():
            try:
                self.enable_position_mode_with_protection(arm, settings)

                # Same convenience as the previous combined app: optionally move
                # to READY automatically before starting. No Initial-Position gate.
                if settings.get("move_ready_first", True):
                    joints = self.read_joint_angles(arm)
                    if not self.is_near_joints(joints, READY_JOINTS, READY_JOINT_TOLERANCE_DEG):
                        self.events.put(("notice", "Moving to READY before drawing/test..."))
                        self.check(arm.set_servo_angle(
                            angle=READY_JOINTS, speed=READY_JOINT_SPEED, wait=True, is_radian=False
                        ), "Automatic Move READY")
                    _, warnings = self.check_ready_pose(arm, settings)
                    for warning in warnings:
                        self.events.put(("notice", warning))
                else:
                    # If automatic READY is disabled, accept either READY itself
                    # or a pen-up gateway reached by a successful prior run.
                    try:
                        self.check_ready_pose(arm, settings)
                    except RuntimeError as ready_error:
                        if gateway_before is None:
                            raise ready_error
                        self.check_verified_gateway(arm, settings, gateway_before)

                for i,(xyz,speed,radius,wait) in enumerate(plan):
                    if self.stop_event.is_set():
                        raise RuntimeError("Stopped by user")
                    ret=arm.set_position(x=xyz[0],y=xyz[1],z=xyz[2],
                        roll=settings["rpy"][0],pitch=settings["rpy"][1],yaw=settings["rpy"][2],
                        speed=speed,mvacc=settings["acceleration"],
                        radius=radius,wait=wait,is_radian=False, timeout=120 if wait else None)
                    self.check(ret,f"Move {i+1}/{len(plan)}")
                    if i%15==0:
                        self.events.put(("progress",(i+1,len(plan),air)))
                code, end_pose = arm.get_position(is_radian=False)
                self.check(code, "Read completed pen-up gateway")
                end_joints = self.read_joint_angles(arm)
                expected_gateway = (float(settings["safe_x_mm"]),
                                    float(settings["ready_xyz"][1]),
                                    float(settings["ready_xyz"][2]))
                if any(abs(float(end_pose[k]) - expected_gateway[k]) > 3.0
                       for k in range(3)):
                    self.events.put(("notice",
                        f"Finished, but final pen-up XYZ differs from nominal gateway: "
                        f"{[round(float(v),1) for v in end_pose[:3]]}"))
                record = {"xyz": [float(v) for v in end_pose[:3]],
                          "joints": end_joints}
                self.events.put(("completed",(air,record)))
            except Exception as ex:
                self.events.put(("error",str(ex)))
                try: arm.set_state(4)
                except Exception: pass
            finally:
                self.events.put(("idle",None))
        threading.Thread(target=work,daemon=True).start()

    @staticmethod
    def check(code,what):
        if code != 0:
            raise RuntimeError(f"{what}: xArm SDK error {code}")

    def stop_robot(self):
        # Immediately request stop even if a worker is blocked on wait=True.
        self.stop_event.set()
        self.verified_gateway=None
        self.status.set("STOP requested: commanding controller to STOP (state 4)...")
        if self.arm is not None:
            def halt():
                try:
                    rc=self.arm.set_state(4)
                    self.events.put(("halted",rc))
                except Exception as ex:
                    self.events.put(("error",f"STOP request error: {ex}"))
            threading.Thread(target=halt,daemon=True).start()

    def poll_events(self):
        try:
            while True:
                evt,payload=self.events.get_nowait()
                if evt=="connected":
                    self.status.set(f"Connected; TCP pose = {[round(x,1) for x in payload]}. No movement yet.")
                elif evt=="error":
                    self.status.set("Robot error / operation aborted: "+str(payload))
                    self.verified_gateway=None
                    messagebox.showerror("Robot",str(payload))
                elif evt=="idle":
                    self.busy=False
                elif evt=="progress":
                    i,n,air=payload
                    self.status.set(f"{'AIR TEST' if air else 'DRAWING'}: command {i}/{n} (STOP available)")
                elif evt=="ready_completed":
                    warnings = payload or []
                    self.status.set("READY reached." + (" " + " | ".join(warnings) if warnings else ""))
                elif evt=="initial_completed":
                    self.status.set("Initial Position reached (J1-J6 = 0°).")
                elif evt=="notice":
                    self.status.set(str(payload))
                elif evt=="completed":
                    was_air, gateway_record = payload
                    self.verified_gateway=gateway_record
                    self.status.set("Air test completed; robot is at the pen-up gateway." if was_air
                                    else "Robot finished drawing at the pen-up gateway.")
                elif evt=="halted":
                    self.status.set(f"STOP controller response {payload}. Recover/enable explicitly before new movement.")
        except queue.Empty:
            pass
        self.root.after(80,self.poll_events)

    def close(self):
        if self.busy:
            self.stop_robot()
            messagebox.showwarning("Stopping robot", "STOP has been requested. Wait until the current operation has stopped, then close the app. Keep the physical E-stop accessible.")
            return
        if self.arm is not None:
            try:
                if self.arm_enabled_by_app:
                    self.arm.set_state(4)
                    self.arm.motion_enable(enable=False)
                self.arm.disconnect()
            except Exception as ex:
                if not messagebox.askyesno("Disconnect problem", f"Could not confirm safe disconnect: {ex}\nClose anyway?"):
                    return
        self.root.destroy()


if __name__=="__main__":
    app_root=tk.Tk()
    try:
        style=ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    DrawingApp(app_root)
    app_root.mainloop()
