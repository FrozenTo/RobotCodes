"""
Tkinter GUI for the UFACTORY 850 wall writer.

Run:
    python uf850_wall_writer_app_v2.py
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Dict

from uf850_wall_writer_v2 import UF850WallWriter


class UF850WallWriterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("UFACTORY 850 Wall Writer")
        self.geometry("1280x920")
        self.minsize(1120, 800)

        self.motion_busy = False
        self.writer = UF850WallWriter(logger=self.log_message)

        self.vars: Dict[str, tk.Variable] = {}
        self.pose_vars: Dict[str, tk.StringVar] = {}
        self.joint_vars: Dict[int, tk.StringVar] = {}

        self._build_variables()
        self._build_layout()

        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        self.log_message("UFACTORY 850 Wall Writer ready.")
        self.log_message(
            "AIR DRAW is ON by default: writing tests stay at safe X and do not touch paper."
        )
        self._update_derived_display()

    # ============================================================
    # VARIABLES
    # ============================================================

    def _build_variables(self) -> None:
        s = self.writer.settings

        self.vars = {
            "ip": tk.StringVar(value=s.ip),
            "status": tk.StringVar(value="Disconnected"),

            "xyz_step": tk.StringVar(value=str(s.xyz_step)),
            "joint_step": tk.StringVar(value=str(s.joint_step)),
            "move_speed": tk.StringVar(value=str(s.move_speed)),
            "contact_speed": tk.StringVar(value=str(s.contact_speed)),
            "joint_speed": tk.StringVar(value=str(s.joint_speed)),

            "roll": tk.StringVar(value=str(s.roll)),
            "pitch": tk.StringVar(value=str(s.pitch)),
            "yaw": tk.StringVar(value=str(s.yaw)),

            "ready_x": tk.StringVar(value=str(s.ready_x)),
            "ready_y": tk.StringVar(value=str(s.ready_y)),
            "ready_z": tk.StringVar(value=str(s.ready_z)),

            "ready_j1": tk.StringVar(value=str(s.ready_joints[0])),
            "ready_j2": tk.StringVar(value=str(s.ready_joints[1])),
            "ready_j3": tk.StringVar(value=str(s.ready_joints[2])),
            "ready_j4": tk.StringVar(value=str(s.ready_joints[3])),
            "ready_j5": tk.StringVar(value=str(s.ready_joints[4])),
            "ready_j6": tk.StringVar(value=str(s.ready_joints[5])),

            "safe_x": tk.StringVar(value=str(s.safe_x)),
            "start_y": tk.StringVar(value=str(s.start_y)),

            "half_height": tk.StringVar(value=str(s.half_height)),
            "half_width": tk.StringVar(value=str(s.half_width)),
            "letter_step": tk.StringVar(value=str(s.letter_step)),
            "space_step": tk.StringVar(value=str(s.space_step)),

            "tl_x": tk.StringVar(value=str(s.paper_top_left[0])),
            "tl_y": tk.StringVar(value=str(s.paper_top_left[1])),
            "tl_z": tk.StringVar(value=str(s.paper_top_left[2])),

            "tr_x": tk.StringVar(value=str(s.paper_top_right[0])),
            "tr_y": tk.StringVar(value=str(s.paper_top_right[1])),
            "tr_z": tk.StringVar(value=str(s.paper_top_right[2])),

            "br_x": tk.StringVar(value=str(s.paper_bottom_right[0])),
            "br_y": tk.StringVar(value=str(s.paper_bottom_right[1])),
            "br_z": tk.StringVar(value=str(s.paper_bottom_right[2])),

            "bl_x": tk.StringVar(value=str(s.paper_bottom_left[0])),
            "bl_y": tk.StringVar(value=str(s.paper_bottom_left[1])),
            "bl_z": tk.StringVar(value=str(s.paper_bottom_left[2])),

            "air_draw": tk.BooleanVar(value=s.air_draw),
            "text": tk.StringVar(value="HELLO"),

            "derived_start_z": tk.StringVar(value="---"),
            "derived_contact_x": tk.StringVar(value="---"),
            "derived_letter_size": tk.StringVar(value="---"),
        }

        for name in ("X", "Y", "Z", "Roll", "Pitch", "Yaw"):
            self.pose_vars[name] = tk.StringVar(value="---")

        for joint_id in range(1, 7):
            self.joint_vars[joint_id] = tk.StringVar(value="---")

    # ============================================================
    # LAYOUT
    # ============================================================

    def _build_layout(self) -> None:
        top = ttk.Frame(self, padding=(12, 12, 12, 6))
        top.pack(fill="x")

        self._build_connection_bar(top)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=6)

        manual_tab = ttk.Frame(notebook, padding=12)
        writing_tab = ttk.Frame(notebook, padding=12)

        notebook.add(manual_tab, text="Manual / Setup")
        notebook.add(writing_tab, text="Writing")

        self._build_manual_tab(manual_tab)
        self._build_writing_tab(writing_tab)

        self._build_log_panel()

    def _build_connection_bar(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(8, weight=1)

        ttk.Label(parent, text="Robot IP:").grid(row=0, column=0, padx=(0, 6))

        ttk.Entry(
            parent,
            textvariable=self.vars["ip"],
            width=17,
        ).grid(row=0, column=1, padx=(0, 8))

        ttk.Button(
            parent,
            text="Connect",
            command=self.on_connect,
        ).grid(row=0, column=2, padx=4)

        ttk.Button(
            parent,
            text="Enable Movement",
            command=self.on_enable,
        ).grid(row=0, column=3, padx=4)

        ttk.Button(
            parent,
            text="Initial Position",
            command=self.on_return_initial,
        ).grid(row=0, column=4, padx=4)

        ttk.Button(
            parent,
            text="Disconnect",
            command=self.on_disconnect,
        ).grid(row=0, column=5, padx=4)

        ttk.Label(
            parent,
            textvariable=self.vars["status"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=6, padx=12)

        ttk.Button(
            parent,
            text="Refresh",
            command=self.on_refresh,
        ).grid(row=0, column=7, padx=4)

        stop_button = tk.Button(
            parent,
            text="EMERGENCY STOP",
            command=self.on_emergency_stop,
            bg="#d9534f",
            fg="white",
            activebackground="#c9302c",
            activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            padx=18,
            pady=7,
        )
        stop_button.grid(row=0, column=9, sticky="e")

    def _build_manual_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        pose_frame = ttk.LabelFrame(parent, text="Current TCP Pose", padding=10)
        pose_frame.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 10),
        )

        labels = ("X", "Y", "Z", "Roll", "Pitch", "Yaw")

        for idx, name in enumerate(labels):
            ttk.Label(
                pose_frame,
                text=f"{name}:",
            ).grid(
                row=0,
                column=idx * 2,
                padx=(5, 2),
                pady=4,
            )

            ttk.Label(
                pose_frame,
                textvariable=self.pose_vars[name],
                width=11,
            ).grid(
                row=0,
                column=idx * 2 + 1,
                padx=(0, 8),
                pady=4,
            )

        cart_frame = ttk.LabelFrame(parent, text="Cartesian Jog", padding=12)
        cart_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(0, 6),
        )

        joint_frame = ttk.LabelFrame(parent, text="Joint Jog", padding=12)
        joint_frame.grid(
            row=1,
            column=1,
            sticky="nsew",
            padx=(6, 0),
        )

        self._build_cartesian_controls(cart_frame)
        self._build_joint_controls(joint_frame)

    def _build_cartesian_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        ttk.Label(
            frame,
            text="Wall is on -X.  +Y writes right.  +Z is up.",
            font=("Segoe UI", 10, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 10),
        )

        self._field(frame, "XYZ step (mm)", "xyz_step", 1, 0)
        self._field(frame, "XYZ speed (mm/s)", "move_speed", 1, 1)

        ttk.Button(
            frame,
            text="X−  Toward paper",
            command=lambda: self.on_jog_xyz("x", -1),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=5)

        ttk.Button(
            frame,
            text="X+  Away from paper",
            command=lambda: self.on_jog_xyz("x", +1),
        ).grid(row=3, column=2, columnspan=2, sticky="ew", padx=4, pady=5)

        ttk.Button(
            frame,
            text="Y−  ←",
            command=lambda: self.on_jog_xyz("y", -1),
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=5)

        ttk.Button(
            frame,
            text="Y+  Writing →",
            command=lambda: self.on_jog_xyz("y", +1),
        ).grid(row=4, column=2, columnspan=2, sticky="ew", padx=4, pady=5)

        ttk.Button(
            frame,
            text="Z−  Down",
            command=lambda: self.on_jog_xyz("z", -1),
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=5)

        ttk.Button(
            frame,
            text="Z+  Up",
            command=lambda: self.on_jog_xyz("z", +1),
        ).grid(row=5, column=2, columnspan=2, sticky="ew", padx=4, pady=5)

    def _build_joint_controls(self, frame: ttk.LabelFrame) -> None:
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        self._field(frame, "Joint step (°)", "joint_step", 0, 0)
        self._field(frame, "Joint speed (°/s)", "joint_speed", 0, 2)

        for joint_id in range(1, 7):
            row = joint_id + 1

            ttk.Label(
                frame,
                text=f"J{joint_id}",
                width=4,
            ).grid(row=row, column=0, padx=4, pady=4)

            ttk.Button(
                frame,
                text="−",
                command=lambda j=joint_id: self.on_jog_joint(j, -1),
            ).grid(row=row, column=1, sticky="ew", padx=4, pady=4)

            ttk.Label(
                frame,
                textvariable=self.joint_vars[joint_id],
                width=12,
                anchor="center",
            ).grid(row=row, column=2, padx=8, pady=4)

            ttk.Button(
                frame,
                text="+",
                command=lambda j=joint_id: self.on_jog_joint(j, +1),
            ).grid(row=row, column=3, sticky="ew", padx=4, pady=4)

    def _build_writing_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        approach_frame = ttk.LabelFrame(
            parent,
            text="Ready / Writing Approach",
            padding=12,
        )
        approach_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 6),
            pady=(0, 10),
        )

        paper_frame = ttk.LabelFrame(
            parent,
            text="Paper Calibration",
            padding=12,
        )
        paper_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(6, 0),
            pady=(0, 10),
        )

        geometry_frame = ttk.LabelFrame(
            parent,
            text="Letter Geometry / Start",
            padding=12,
        )
        geometry_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(0, 6),
            pady=(0, 10),
        )

        controls_frame = ttk.LabelFrame(
            parent,
            text="Writing Controls",
            padding=12,
        )
        controls_frame.grid(
            row=1,
            column=1,
            sticky="nsew",
            padx=(6, 0),
            pady=(0, 10),
        )

        self._build_approach_controls(approach_frame)
        self._build_paper_controls(paper_frame)
        self._build_geometry_controls(geometry_frame)
        self._build_writing_controls(controls_frame)

    def _build_approach_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(2):
            frame.columnconfigure(col, weight=1)

        ttk.Label(
            frame,
            text="Far-away READY position",
            font=("Segoe UI", 10, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=4,
            pady=(0, 6),
        )

        self._field(frame, "Ready X", "ready_x", 1, 0)
        self._field(frame, "Ready Y", "ready_y", 1, 1)
        self._field(frame, "Ready Z", "ready_z", 3, 0)

        self._field(frame, "Roll", "roll", 3, 1)
        self._field(frame, "Pitch", "pitch", 5, 0)
        self._field(frame, "Yaw", "yaw", 5, 1)

        ttk.Separator(frame, orient="horizontal").grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=8,
        )

        for idx in range(6):
            row = 8 + (idx // 2) * 2
            col = idx % 2
            self._field(
                frame,
                f"Ready J{idx + 1} (°)",
                f"ready_j{idx + 1}",
                row,
                col,
            )

        ttk.Button(
            frame,
            text="Use Current Pose + Joints as READY",
            command=self.on_use_current_ready,
        ).grid(
            row=14,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=(8, 4),
        )

        ttk.Button(
            frame,
            text="Move to READY",
            command=self.on_move_ready,
        ).grid(
            row=15,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _build_paper_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        ttk.Label(
            frame,
            text="Four measured marker-contact corners (X, Y, Z)",
            font=("Segoe UI", 10, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            padx=4,
            pady=(0, 8),
        )

        self._corner_block(
            frame,
            "Top Left",
            "tl",
            row=1,
            col=0,
            capture=self.on_capture_tl,
        )

        self._corner_block(
            frame,
            "Top Right",
            "tr",
            row=1,
            col=2,
            capture=self.on_capture_tr,
        )

        self._corner_block(
            frame,
            "Bottom Left",
            "bl",
            row=7,
            col=0,
            capture=self.on_capture_bl,
        )

        self._corner_block(
            frame,
            "Bottom Right",
            "br",
            row=7,
            col=2,
            capture=self.on_capture_br,
        )

    def _corner_block(
        self,
        parent: ttk.LabelFrame,
        title: str,
        prefix: str,
        *,
        row: int,
        col: int,
        capture: Callable[[], None],
    ) -> None:
        box = ttk.LabelFrame(parent, text=title, padding=6)
        box.grid(
            row=row,
            column=col,
            columnspan=2,
            rowspan=5,
            sticky="nsew",
            padx=4,
            pady=4,
        )
        box.columnconfigure(1, weight=1)

        for r, axis in enumerate(("x", "y", "z")):
            ttk.Label(
                box,
                text=axis.upper(),
            ).grid(row=r, column=0, padx=(0, 4), pady=2)

            ttk.Entry(
                box,
                textvariable=self.vars[f"{prefix}_{axis}"],
                width=12,
            ).grid(row=r, column=1, sticky="ew", pady=2)

        ttk.Button(
            box,
            text="Capture Current",
            command=capture,
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(6, 0),
        )

    def _build_geometry_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(2):
            frame.columnconfigure(col, weight=1)

        self._field(frame, "Safe writing X (mm)", "safe_x", 0, 0)
        self._field(frame, "Start Y (mm)", "start_y", 0, 1)

        self._field(frame, "Half height (mm)", "half_height", 2, 0)
        self._field(frame, "Half width (mm)", "half_width", 2, 1)

        self._field(frame, "Letter step +Y (mm)", "letter_step", 4, 0)
        self._field(frame, "Space step +Y (mm)", "space_step", 4, 1)

        ttk.Separator(frame, orient="horizontal").grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=8,
        )

        ttk.Label(frame, text="Letter size:").grid(
            row=7,
            column=0,
            sticky="w",
            padx=4,
            pady=2,
        )
        ttk.Label(
            frame,
            textvariable=self.vars["derived_letter_size"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=7, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frame, text="Auto Start Z:").grid(
            row=8,
            column=0,
            sticky="w",
            padx=4,
            pady=2,
        )
        ttk.Label(
            frame,
            textvariable=self.vars["derived_start_z"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=8, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(frame, text="Contact X at start:").grid(
            row=9,
            column=0,
            sticky="w",
            padx=4,
            pady=2,
        )
        ttk.Label(
            frame,
            textvariable=self.vars["derived_contact_x"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=9, column=1, sticky="w", padx=4, pady=2)

        ttk.Button(
            frame,
            text="Set Start Y from Paper + Letter Width",
            command=self.on_recalculate_start_y,
        ).grid(
            row=10,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=(8, 4),
        )

        ttk.Button(
            frame,
            text="Apply Settings",
            command=self.on_apply_settings,
        ).grid(
            row=11,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _build_writing_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(2):
            frame.columnconfigure(col, weight=1)

        ttk.Checkbutton(
            frame,
            text="AIR DRAW — never touch paper",
            variable=self.vars["air_draw"],
            command=self.on_apply_settings,
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=4,
            pady=(0, 8),
        )

        ttk.Button(
            frame,
            text="Move to Writing Start",
            command=self.on_move_to_start,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            frame,
            text="Marker Contact",
            command=self.on_marker_contact,
        ).grid(row=2, column=0, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Marker Away",
            command=self.on_marker_away,
        ).grid(row=2, column=1, sticky="ew", padx=4, pady=4)

        ttk.Separator(frame, orient="horizontal").grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=8,
        )

        ttk.Button(
            frame,
            text="Horizontal Line",
            command=lambda: self.on_test(
                "Horizontal line",
                self.writer.test_horizontal_line,
            ),
        ).grid(row=4, column=0, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Vertical Line",
            command=lambda: self.on_test(
                "Vertical line",
                self.writer.test_vertical_line,
            ),
        ).grid(row=4, column=1, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Square",
            command=lambda: self.on_test(
                "Square",
                self.writer.test_square,
            ),
        ).grid(row=5, column=0, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Letter A",
            command=lambda: self.on_test(
                "Letter A",
                self.writer.test_letter_a,
            ),
        ).grid(row=5, column=1, sticky="ew", padx=4, pady=4)

        ttk.Separator(frame, orient="horizontal").grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=8,
        )

        ttk.Entry(
            frame,
            textvariable=self.vars["text"],
            font=("Segoe UI", 13),
        ).grid(
            row=7,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            frame,
            text="Write Text",
            command=self.on_write_text,
        ).grid(
            row=7,
            column=1,
            sticky="ew",
            padx=4,
            pady=4,
        )

        ttk.Label(
            frame,
            text="Supported: A-Z, space, ! ? . and Ä Ö Ü Õ",
        ).grid(
            row=8,
            column=0,
            columnspan=2,
            sticky="w",
            padx=4,
            pady=(4, 0),
        )

    def _build_log_panel(self) -> None:
        frame = ttk.LabelFrame(
            self,
            text="Command / Status Log",
            padding=8,
        )
        frame.pack(
            fill="both",
            expand=False,
            padx=12,
            pady=(0, 12),
        )

        self.log_box = ScrolledText(
            frame,
            height=8,
            wrap="word",
            font=("Consolas", 9),
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

    def _field(
        self,
        parent: ttk.Frame,
        label_text: str,
        var_key: str,
        row: int,
        col: int,
    ) -> None:
        cell = ttk.Frame(parent)
        cell.grid(
            row=row,
            column=col,
            sticky="ew",
            padx=4,
            pady=4,
        )
        cell.columnconfigure(0, weight=1)

        ttk.Label(cell, text=label_text).grid(
            row=0,
            column=0,
            sticky="w",
        )

        ttk.Entry(
            cell,
            textvariable=self.vars[var_key],
        ).grid(
            row=1,
            column=0,
            sticky="ew",
        )

    # ============================================================
    # LOGGING / WORKER THREADS
    # ============================================================

    def log_message(self, message: str) -> None:
        try:
            self.after(0, self._append_log, str(message))
        except tk.TclError:
            pass

    def _append_log(self, message: str) -> None:
        if not hasattr(self, "log_box"):
            print(message)
            return

        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _show_error(self, title: str, exc: Exception) -> None:
        self.log_message(f"ERROR: {exc}")
        self.after(
            0,
            lambda: messagebox.showerror(title, str(exc)),
        )

    def _set_status(self, text: str) -> None:
        self.after(
            0,
            lambda: self.vars["status"].set(text),
        )

    def _run_action(
        self,
        label: str,
        action: Callable[[], None],
        *,
        allow_when_busy: bool = False,
    ) -> None:
        if self.motion_busy and not allow_when_busy:
            self.log_message(
                f"Cannot start '{label}': another robot command is still running."
            )
            return

        if not allow_when_busy:
            self.motion_busy = True

        def worker() -> None:
            try:
                action()
                self._refresh_readouts_worker()
            except Exception as exc:
                self._show_error(label, exc)
            finally:
                if not allow_when_busy:
                    self.motion_busy = False

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    # ============================================================
    # SETTINGS
    # ============================================================

    def apply_settings(self, *, log: bool = True) -> None:
        s = self.writer.settings

        s.ip = str(self.vars["ip"].get()).strip()

        s.xyz_step = float(self.vars["xyz_step"].get())
        s.joint_step = float(self.vars["joint_step"].get())
        s.move_speed = float(self.vars["move_speed"].get())
        s.contact_speed = float(self.vars["contact_speed"].get())
        s.joint_speed = float(self.vars["joint_speed"].get())

        s.roll = float(self.vars["roll"].get())
        s.pitch = float(self.vars["pitch"].get())
        s.yaw = float(self.vars["yaw"].get())

        s.ready_x = float(self.vars["ready_x"].get())
        s.ready_y = float(self.vars["ready_y"].get())
        s.ready_z = float(self.vars["ready_z"].get())

        s.ready_joints = tuple(
            float(self.vars[f"ready_j{i}"].get())
            for i in range(1, 7)
        )  # type: ignore[assignment]

        s.safe_x = float(self.vars["safe_x"].get())
        s.start_y = float(self.vars["start_y"].get())

        s.half_height = float(self.vars["half_height"].get())
        s.half_width = float(self.vars["half_width"].get())
        s.letter_step = float(self.vars["letter_step"].get())
        s.space_step = float(self.vars["space_step"].get())

        s.paper_top_left = (
            float(self.vars["tl_x"].get()),
            float(self.vars["tl_y"].get()),
            float(self.vars["tl_z"].get()),
        )
        s.paper_top_right = (
            float(self.vars["tr_x"].get()),
            float(self.vars["tr_y"].get()),
            float(self.vars["tr_z"].get()),
        )
        s.paper_bottom_right = (
            float(self.vars["br_x"].get()),
            float(self.vars["br_y"].get()),
            float(self.vars["br_z"].get()),
        )
        s.paper_bottom_left = (
            float(self.vars["bl_x"].get()),
            float(self.vars["bl_y"].get()),
            float(self.vars["bl_z"].get()),
        )

        s.air_draw = bool(self.vars["air_draw"].get())

        if s.xyz_step <= 0 or s.joint_step <= 0:
            raise ValueError("Jog step values must be greater than 0.")

        if s.move_speed <= 0 or s.contact_speed <= 0 or s.joint_speed <= 0:
            raise ValueError("Speed values must be greater than 0.")

        if s.half_height <= 0 or s.half_width <= 0:
            raise ValueError("Letter half-height/half-width must be greater than 0.")

        self.writer.rebuild_geometry()
        self._update_derived_display()

        if log:
            self.log_message("Settings applied.")

    def _update_derived_display(self) -> None:
        try:
            start_z = self.writer.start_z
            letter_w = self.writer.letter_width
            letter_h = self.writer.letter_height
            start_y = self.writer.settings.start_y
            contact_x = self.writer.paper_contact_x(start_y, start_z)

            self.vars["derived_start_z"].set(f"{start_z:.1f} mm")
            self.vars["derived_letter_size"].set(
                f"{letter_w:.1f} × {letter_h:.1f} mm"
            )
            self.vars["derived_contact_x"].set(f"{contact_x:.2f} mm")
        except Exception:
            self.vars["derived_start_z"].set("---")
            self.vars["derived_letter_size"].set("---")
            self.vars["derived_contact_x"].set("---")

    # ============================================================
    # CONNECTION / READBACK
    # ============================================================

    def on_connect(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        def action() -> None:
            self.writer.connect_robot()
            self._set_status("Connected")

        self._run_action("Connect", action)

    def on_enable(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        def action() -> None:
            self.writer.enable_robot()
            self._set_status("Connected / Enabled")

        self._run_action("Enable Movement", action)

    def on_disconnect(self) -> None:
        def action() -> None:
            self.writer.disconnect_robot()
            self._set_status("Disconnected")
            self._clear_readouts()

        self._run_action("Disconnect", action)

    def on_refresh(self) -> None:
        self._run_action("Refresh", lambda: None)

    def _refresh_readouts_worker(self) -> None:
        if not self.writer.is_connected:
            return

        pose = self.writer.get_pose()
        joints = self.writer.get_joints()

        def update_ui() -> None:
            for name, value in zip(
                ("X", "Y", "Z", "Roll", "Pitch", "Yaw"),
                pose,
            ):
                self.pose_vars[name].set(f"{value:.2f}")

            for joint_id, value in enumerate(joints, start=1):
                self.joint_vars[joint_id].set(f"{value:.2f}°")

        self.after(0, update_ui)

    def _clear_readouts(self) -> None:
        def update_ui() -> None:
            for var in self.pose_vars.values():
                var.set("---")
            for var in self.joint_vars.values():
                var.set("---")

        self.after(0, update_ui)

    # ============================================================
    # MANUAL JOG
    # ============================================================

    def on_jog_xyz(self, axis: str, direction: int) -> None:
        try:
            self.apply_settings(log=False)
            amount = self.writer.settings.xyz_step * direction
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            f"Jog {axis.upper()}",
            lambda: self.writer.jog_cartesian(axis, amount),
        )

    def on_jog_joint(self, joint_id: int, direction: int) -> None:
        try:
            self.apply_settings(log=False)
            amount = self.writer.settings.joint_step * direction
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            f"Jog J{joint_id}",
            lambda: self.writer.jog_joint(joint_id, amount),
        )

    # ============================================================
    # READY / PAPER CAPTURE
    # ============================================================

    def on_use_current_ready(self) -> None:
        if not self.writer.is_connected:
            messagebox.showwarning("Robot", "Robot is not connected.")
            return

        def action() -> None:
            x, y, z, roll, pitch, yaw = self.writer.get_pose()
            joints = self.writer.get_joints()

            def update_ui() -> None:
                self.vars["ready_x"].set(f"{x:.3f}")
                self.vars["ready_y"].set(f"{y:.3f}")
                self.vars["ready_z"].set(f"{z:.3f}")

                self.vars["roll"].set(f"{roll:.3f}")
                self.vars["pitch"].set(f"{pitch:.3f}")
                self.vars["yaw"].set(f"{yaw:.3f}")

                for i, angle in enumerate(joints, start=1):
                    self.vars[f"ready_j{i}"].set(f"{angle:.3f}")

                self.apply_settings(log=False)
                self.log_message("Current pose + joints saved as READY.")

            self.after(0, update_ui)

        self._run_action("Save READY", action)

    def _capture_corner(self, prefix: str, name: str) -> None:
        if not self.writer.is_connected:
            messagebox.showwarning("Robot", "Robot is not connected.")
            return

        def action() -> None:
            x, y, z, _, _, _ = self.writer.get_pose()

            def update_ui() -> None:
                self.vars[f"{prefix}_x"].set(f"{x:.3f}")
                self.vars[f"{prefix}_y"].set(f"{y:.3f}")
                self.vars[f"{prefix}_z"].set(f"{z:.3f}")
                self.apply_settings(log=False)
                self.log_message(
                    f"{name} captured: X={x:.2f}, Y={y:.2f}, Z={z:.2f}"
                )

            self.after(0, update_ui)

        self._run_action(f"Capture {name}", action)

    def on_capture_tl(self) -> None:
        self._capture_corner("tl", "Top Left")

    def on_capture_tr(self) -> None:
        self._capture_corner("tr", "Top Right")

    def on_capture_br(self) -> None:
        self._capture_corner("br", "Bottom Right")

    def on_capture_bl(self) -> None:
        self._capture_corner("bl", "Bottom Left")

    # ============================================================
    # WRITING SETTINGS / MOVEMENT
    # ============================================================

    def on_apply_settings(self) -> None:
        try:
            self.apply_settings()
        except Exception as exc:
            self._show_error("Settings", exc)

    def on_recalculate_start_y(self) -> None:
        try:
            self.apply_settings(log=False)
            suggested = self.writer.suggested_start_y()
            self.vars["start_y"].set(f"{suggested:.3f}")
            self.apply_settings(log=False)
            self.log_message(
                f"Start Y set to {suggested:.2f} mm "
                "(top-left Y + full letter width)."
            )
        except Exception as exc:
            self._show_error("Start Position", exc)

    def on_move_ready(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            "Move to READY",
            self.writer.go_to_ready_position,
        )

    def on_move_to_start(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            "Move to Writing Start",
            self.writer.go_to_writing_start,
        )

    def on_marker_contact(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            "Marker Contact",
            self.writer.marker_contact,
        )

    def on_marker_away(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            "Marker Away",
            self.writer.marker_away,
        )

    def on_test(
        self,
        label: str,
        function: Callable[[], None],
    ) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(label, function)

    def on_write_text(self) -> None:
        try:
            self.apply_settings(log=False)
            text = str(self.vars["text"].get())
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        self._run_action(
            "Write Text",
            lambda: self.writer.write_text(
                text,
                move_to_start=True,
            ),
        )

    # ============================================================
    # HOME / EMERGENCY / CLOSE
    # ============================================================

    def on_return_initial(self) -> None:
        try:
            self.apply_settings(log=False)
        except Exception as exc:
            self._show_error("Settings", exc)
            return

        def action() -> None:
            self.writer.return_to_initial_position()
            self._set_status("Connected / Initial Position")

        self._run_action("Initial Position", action)

    def on_emergency_stop(self) -> None:
        if not self.writer.is_connected:
            self.log_message("Emergency stop ignored: robot is not connected.")
            return

        def worker() -> None:
            try:
                self.writer.emergency_stop()
                self._set_status("STOPPED — re-enable required")
            except Exception as exc:
                self._show_error("Emergency Stop", exc)

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def on_window_close(self) -> None:
        try:
            if self.writer.is_connected:
                self.writer.disconnect_robot()
        except Exception:
            pass

        self.destroy()


if __name__ == "__main__":
    app = UF850WallWriterApp()
    app.mainloop()
