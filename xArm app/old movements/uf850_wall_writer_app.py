"""
Tkinter GUI for the UFACTORY 850 wall writer.

Run:
    python uf850_wall_writer_app.py
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Dict

from uf850_wall_writer import UF850WallWriter


class UF850WallWriterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("UFACTORY 850 Wall Writer")
        self.geometry("1180x860")
        self.minsize(1080, 760)

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
            "Air Draw is ON by default: writing tests will NOT touch the wall."
        )

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

            "wall_x": tk.StringVar(value=str(s.wall_x)),
            "start_y": tk.StringVar(value=str(s.start_y)),
            "start_z": tk.StringVar(value=str(s.start_z)),
            "roll": tk.StringVar(value=str(s.roll)),
            "pitch": tk.StringVar(value=str(s.pitch)),
            "yaw": tk.StringVar(value=str(s.yaw)),
            "clearance": tk.StringVar(value=str(s.clearance)),

            "half_height": tk.StringVar(value=str(s.half_height)),
            "half_width": tk.StringVar(value=str(s.half_width)),
            "letter_step": tk.StringVar(value=str(s.letter_step)),
            "space_step": tk.StringVar(value=str(s.space_step)),

            "air_draw": tk.BooleanVar(value=s.air_draw),
            "text": tk.StringVar(value="HELLO"),
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
            text="Disconnect",
            command=self.on_disconnect,
        ).grid(row=0, column=4, padx=4)

        ttk.Label(
            parent,
            textvariable=self.vars["status"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=5, padx=12)

        ttk.Button(
            parent,
            text="Refresh",
            command=self.on_refresh,
        ).grid(row=0, column=6, padx=4)

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
            ttk.Label(pose_frame, text=f"{name}:").grid(
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
            text="Wall is on -X.  +Y is writing direction.  +Z is up.",
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
            text="X−  Toward wall",
            command=lambda: self.on_jog_xyz("x", -1),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=5)

        ttk.Button(
            frame,
            text="X+  Away from wall",
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

        setup_frame = ttk.LabelFrame(
            parent,
            text="Wall / Writing Setup",
            padding=12,
        )
        setup_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 6),
            pady=(0, 10),
        )

        geometry_frame = ttk.LabelFrame(
            parent,
            text="Letter Geometry",
            padding=12,
        )
        geometry_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(6, 0),
            pady=(0, 10),
        )

        tests_frame = ttk.LabelFrame(
            parent,
            text="Writing Tests",
            padding=12,
        )
        tests_frame.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 10),
        )

        text_frame = ttk.LabelFrame(
            parent,
            text="Text",
            padding=12,
        )
        text_frame.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
        )

        self._build_setup_controls(setup_frame)
        self._build_geometry_controls(geometry_frame)
        self._build_test_controls(tests_frame)
        self._build_text_controls(text_frame)

    def _build_setup_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(2):
            frame.columnconfigure(col, weight=1)

        self._field(frame, "Wall X / contact X (mm)", "wall_x", 0, 0)
        self._field(frame, "Clearance from wall (mm)", "clearance", 0, 1)

        self._field(frame, "Writing start Y (mm)", "start_y", 2, 0)
        self._field(frame, "Writing start Z (mm)", "start_z", 2, 1)

        self._field(frame, "Roll (°)", "roll", 4, 0)
        self._field(frame, "Pitch (°)", "pitch", 4, 1)
        self._field(frame, "Yaw (°)", "yaw", 6, 0)
        self._field(frame, "Marker contact speed", "contact_speed", 6, 1)

        ttk.Checkbutton(
            frame,
            text="AIR DRAW — never move marker into wall",
            variable=self.vars["air_draw"],
            command=self.on_apply_settings,
        ).grid(
            row=8,
            column=0,
            columnspan=2,
            sticky="w",
            padx=4,
            pady=(10, 6),
        )

        ttk.Button(
            frame,
            text="Use Current Y/Z + Orientation as Writing Start",
            command=self.on_use_current_start,
        ).grid(
            row=9,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            frame,
            text="Use Current X as Wall X",
            command=self.on_use_current_wall_x,
        ).grid(
            row=10,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            frame,
            text="Move to Writing Start (marker away)",
            command=self.on_move_to_start,
        ).grid(
            row=11,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=(10, 4),
        )

        ttk.Button(
            frame,
            text="Marker Contact",
            command=self.on_marker_contact,
        ).grid(
            row=12,
            column=0,
            sticky="ew",
            padx=4,
            pady=4,
        )

        ttk.Button(
            frame,
            text="Marker Away",
            command=self.on_marker_away,
        ).grid(
            row=12,
            column=1,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _build_geometry_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(2):
            frame.columnconfigure(col, weight=1)

        self._field(frame, "Half height (mm)", "half_height", 0, 0)
        self._field(frame, "Half width (mm)", "half_width", 0, 1)

        self._field(frame, "Letter step +Y (mm)", "letter_step", 2, 0)
        self._field(frame, "Space step +Y (mm)", "space_step", 2, 1)

        ttk.Label(
            frame,
            text=(
                "Default letter size: 20 mm high × 10 mm wide.\n"
                "Point 5 is the center of each letter."
            ),
        ).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="w",
            padx=4,
            pady=(12, 8),
        )

        ttk.Button(
            frame,
            text="Apply Settings",
            command=self.on_apply_settings,
        ).grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _build_test_controls(self, frame: ttk.LabelFrame) -> None:
        for col in range(4):
            frame.columnconfigure(col, weight=1)

        ttk.Button(
            frame,
            text="Horizontal Line",
            command=lambda: self.on_test("Horizontal line", self.writer.test_horizontal_line),
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Vertical Line",
            command=lambda: self.on_test("Vertical line", self.writer.test_vertical_line),
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Square",
            command=lambda: self.on_test("Square", self.writer.test_square),
        ).grid(row=0, column=2, sticky="ew", padx=4, pady=4)

        ttk.Button(
            frame,
            text="Letter A",
            command=lambda: self.on_test("Letter A", self.writer.test_letter_a),
        ).grid(row=0, column=3, sticky="ew", padx=4, pady=4)

    def _build_text_controls(self, frame: ttk.LabelFrame) -> None:
        frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(
            frame,
            textvariable=self.vars["text"],
            font=("Segoe UI", 14),
        )
        entry.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 8),
        )
        entry.bind("<Return>", lambda _event: self.on_write_text())

        ttk.Button(
            frame,
            text="Write Text",
            command=self.on_write_text,
        ).grid(
            row=0,
            column=1,
            sticky="ew",
        )

        ttk.Label(
            frame,
            text="Supported: A-Z, space, ! ? . and Ä Ö Ü Õ",
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
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
            height=9,
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
    # LOGGING / UI THREAD HELPERS
    # ============================================================

    def log_message(self, message: str) -> None:
        # The writer logs from worker threads, so marshal UI work
        # back onto Tkinter's main thread.
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

        s.wall_x = float(self.vars["wall_x"].get())
        s.start_y = float(self.vars["start_y"].get())
        s.start_z = float(self.vars["start_z"].get())
        s.roll = float(self.vars["roll"].get())
        s.pitch = float(self.vars["pitch"].get())
        s.yaw = float(self.vars["yaw"].get())
        s.clearance = float(self.vars["clearance"].get())

        s.half_height = float(self.vars["half_height"].get())
        s.half_width = float(self.vars["half_width"].get())
        s.letter_step = float(self.vars["letter_step"].get())
        s.space_step = float(self.vars["space_step"].get())

        s.air_draw = bool(self.vars["air_draw"].get())

        if s.clearance < 0:
            raise ValueError("Clearance must be 0 or greater.")

        if s.xyz_step <= 0 or s.joint_step <= 0:
            raise ValueError("Jog step values must be greater than 0.")

        if s.move_speed <= 0 or s.contact_speed <= 0 or s.joint_speed <= 0:
            raise ValueError("Speed values must be greater than 0.")

        self.writer.rebuild_geometry()

        if log:
            self.log_message("Settings applied.")

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
    # WRITING SETUP
    # ============================================================

    def on_apply_settings(self) -> None:
        try:
            self.apply_settings()
        except Exception as exc:
            self._show_error("Settings", exc)

    def on_use_current_start(self) -> None:
        if not self.writer.is_connected:
            messagebox.showwarning("Robot", "Robot is not connected.")
            return

        def action() -> None:
            x, y, z, roll, pitch, yaw = self.writer.get_pose()

            def update_ui() -> None:
                self.vars["start_y"].set(f"{y:.3f}")
                self.vars["start_z"].set(f"{z:.3f}")
                self.vars["roll"].set(f"{roll:.3f}")
                self.vars["pitch"].set(f"{pitch:.3f}")
                self.vars["yaw"].set(f"{yaw:.3f}")

                self.apply_settings(log=False)
                self.log_message(
                    "Writing start updated from current pose "
                    f"(Y={y:.2f}, Z={z:.2f}, "
                    f"R={roll:.2f}, P={pitch:.2f}, Yaw={yaw:.2f})."
                )

            self.after(0, update_ui)

        self._run_action("Use Current Writing Start", action)

    def on_use_current_wall_x(self) -> None:
        if not self.writer.is_connected:
            messagebox.showwarning("Robot", "Robot is not connected.")
            return

        def action() -> None:
            x, _, _, _, _, _ = self.writer.get_pose()

            def update_ui() -> None:
                self.vars["wall_x"].set(f"{x:.3f}")
                self.apply_settings(log=False)
                self.log_message(
                    f"Wall/contact X updated from current TCP: {x:.2f} mm."
                )

            self.after(0, update_ui)

        self._run_action("Use Current Wall X", action)

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

    # ============================================================
    # WRITING / TESTS
    # ============================================================

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
            lambda: self.writer.write_text(text, move_to_start=True),
        )

    # ============================================================
    # EMERGENCY STOP / CLOSE
    # ============================================================

    def on_emergency_stop(self) -> None:
        if not self.writer.is_connected:
            self.log_message("Emergency stop ignored: robot is not connected.")
            return

        # Do NOT block this behind motion_busy. It must be callable
        # while another command is waiting for movement to finish.
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
