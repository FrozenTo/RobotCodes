"""
Tkinter desktop app for the MG400 text writer.

SP32

Run:
    python mg400_writer_app.py
"""
#157.3 - 142.3
from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict

from mg400_writer import MG400Writer, WriterSettings


class MG400WriterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("MG400 Text Writer")
        self.geometry("1180x900")
        self.minsize(1050, 780)

        self.state_file = Path(__file__).resolve().with_name("mg400_writer_state.json")

        self.writer = MG400Writer(logger=self.log_message)
        self.presets = self._default_presets()
        self.last_used_preset = 0
        self.saved_text = "Text Here"
        self._load_saved_state()

        self.vars: Dict[str, tk.Variable] = {}
        self.preset_vars = []
        self._build_variables()
        self._build_preset_variables()
        self._build_layout()
        self.refresh_calculated_start()
        self.log_message("MG400 Text Writer ready.")

    # ============================================================
    # PERSISTENCE / SAVED POSITIONS
    # ============================================================

    def _default_presets(self):
        s = self.writer.settings
        return [
            {
                "name": "Point 1",
                "x": s.base_x,
                "y": s.base_y,
                "z": s.base_z,
                "r": s.base_r,
            },
            {"name": "Point 2", "x": None, "y": None, "z": None, "r": None},
            {"name": "Point 3", "x": None, "y": None, "z": None, "r": None},
            {"name": "Point 4", "x": None, "y": None, "z": None, "r": None},
            {"name": "Point 5", "x": None, "y": None, "z": None, "r": None},
        ]

    def _load_saved_state(self) -> None:
        if not self.state_file.exists():
            return

        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))

            saved_settings = data.get("settings", {})
            valid_setting_names = {field.name for field in fields(WriterSettings)}
            for key, value in saved_settings.items():
                if key in valid_setting_names:
                    setattr(self.writer.settings, key, value)

            saved_presets = data.get("presets")
            if isinstance(saved_presets, list):
                for index in range(min(5, len(saved_presets))):
                    item = saved_presets[index]
                    if isinstance(item, dict):
                        self.presets[index] = {
                            "name": str(item.get("name", f"Point {index + 1}")),
                            "x": item.get("x"),
                            "y": item.get("y"),
                            "z": item.get("z"),
                            "r": item.get("r"),
                        }

            self.last_used_preset = int(data.get("last_used_preset", 0))
            if not 0 <= self.last_used_preset <= 4:
                self.last_used_preset = 0

            self.saved_text = str(data.get("text", "Text Here"))
            self.writer.rebuild_geometry()

        except Exception as exc:
            print(f"Could not load saved app state: {exc}")

    def save_state(self) -> None:
        if not hasattr(self, "vars") or not self.vars:
            return

        try:
            self.apply_settings_to_writer(show_log=False, save_after=False)
            self._sync_presets_from_ui()

            data = {
                "settings": asdict(self.writer.settings),
                "presets": self.presets,
                "last_used_preset": self.last_used_preset,
                "text": str(self.vars["text"].get()),
            }

            self.state_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            # A temporary invalid entry should not prevent the app from closing.
            self.log_message(f"Could not save app state: {exc}")

    def _build_preset_variables(self) -> None:
        self.preset_vars = []

        for index, preset in enumerate(self.presets):
            self.preset_vars.append({
                "name": tk.StringVar(value=preset["name"]),
                "x": tk.StringVar(value="" if preset["x"] is None else str(preset["x"])),
                "y": tk.StringVar(value="" if preset["y"] is None else str(preset["y"])),
                "z": tk.StringVar(value="" if preset["z"] is None else str(preset["z"])),
                "r": tk.StringVar(value="" if preset["r"] is None else str(preset["r"])),
            })

    def _sync_presets_from_ui(self) -> None:
        if not self.preset_vars:
            return

        for index, row_vars in enumerate(self.preset_vars):
            def optional_float(key):
                value = str(row_vars[key].get()).strip()
                return None if value == "" else float(value)

            self.presets[index] = {
                "name": str(row_vars["name"].get()).strip() or f"Point {index + 1}",
                "x": optional_float("x"),
                "y": optional_float("y"),
                "z": optional_float("z"),
                "r": optional_float("r"),
            }

    def _preset_pose(self, index: int):
        self._sync_presets_from_ui()
        preset = self.presets[index]

        values = (preset["x"], preset["y"], preset["z"], preset["r"])
        if any(value is None for value in values):
            raise ValueError(f"{preset['name']} does not have a complete X/Y/Z/R pose.")

        return tuple(float(value) for value in values)

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def _build_variables(self) -> None:
        s = self.writer.settings

        self.vars = {
            "text": tk.StringVar(value=self.saved_text),

            "live_robot": tk.BooleanVar(value=s.live_robot),
            "ip": tk.StringVar(value=s.ip),
            "dashboard_port": tk.StringVar(value=str(s.dashboard_port)),
            "motion_port": tk.StringVar(value=str(s.motion_port)),
            "speed_factor": tk.StringVar(value=str(s.speed_factor)),
            "move_delay": tk.StringVar(value=str(s.move_delay)),

            "half_height": tk.StringVar(value=str(s.half_height)),
            "half_width": tk.StringVar(value=str(s.half_width)),
            "letter_step": tk.StringVar(value=str(s.letter_step)),
            "space_step": tk.StringVar(value=str(s.space_step)),
            "pen_drop": tk.StringVar(value=str(s.pen_drop)),

            "base_x": tk.StringVar(value=str(s.base_x)),
            "base_y": tk.StringVar(value=str(s.base_y)),
            "base_z": tk.StringVar(value=str(s.base_z)),
            "base_r": tk.StringVar(value=str(s.base_r)),
            "row_step": tk.StringVar(value=str(s.row_step)),
            "current_row": tk.StringVar(value=str(s.current_row)),

            "calculated_start": tk.StringVar(value=""),
            "connection_status": tk.StringVar(value="Not connected"),
        }

    def _build_layout(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(3, weight=1)

        self._build_text_panel(outer)
        self._build_action_panel(outer)
        self._build_settings_panel(outer)
        self._build_saved_positions_panel(outer)
        self._build_log_panel(outer)

    def _build_text_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Text to write", padding=12)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 10))
        frame.columnconfigure(0, weight=1)

        entry = ttk.Entry(frame, textvariable=self.vars["text"], font=("Segoe UI", 14))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda _event: self.on_write_text())

        ttk.Button(frame, text="Write Text", command=self.on_write_text).grid(
            row=0, column=1, sticky="ew"
        )

        ttk.Label(
            frame,
            text="Supported: A-Z, space, ! ? . and Ä Ö Ü Õ",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _build_action_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Robot actions", padding=12)
        frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            frame,
            text="Live robot",
            variable=self.vars["live_robot"],
            command=self.on_apply_settings,
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(frame, textvariable=self.vars["connection_status"]).grid(
            row=0, column=1, sticky="e"
        )

        ttk.Button(frame, text="Apply Settings", command=self.on_apply_settings).grid(
            row=1, column=0, sticky="ew", pady=(10, 6), padx=(0, 6)
        )
        ttk.Button(frame, text="Connect Robot", command=self.on_connect).grid(
            row=1, column=1, sticky="ew", pady=(10, 6), padx=(6, 0)
        )
        ttk.Button(frame, text="Setup Robot", command=self.on_setup_robot).grid(
            row=2, column=0, sticky="ew", pady=6, padx=(0, 6)
        )
        ttk.Button(frame, text="Move to Writing Start", command=self.on_move_to_start).grid(
            row=2, column=1, sticky="ew", pady=6, padx=(6, 0)
        )
        ttk.Button(
            frame,
            text="Underline",
            command=self.on_underline
        ).grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(6, 0),
            padx=(0, 6)
        )

        ttk.Button(
            frame,
            text="Close Connection",
            command=self.on_close
        ).grid(
            row=3,
            column=1,
            sticky="ew",
            pady=(6, 0),
            padx=(6, 0)
        )

    def _build_settings_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Settings", padding=12)
        frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        for col in range(4):
            frame.columnconfigure(col, weight=1)

        self._section_header(frame, "Robot connection", 0, 0, 4)
        robot_fields = [
            ("IP", "ip"),
            ("Dashboard port", "dashboard_port"),
            ("Motion port", "motion_port"),
            ("Speed factor", "speed_factor"),
            ("Move delay (s)", "move_delay"),
        ]
        self._place_fields(frame, robot_fields, start_row=1, columns=3)

        self._section_header(frame, "Writing geometry", 4, 0, 4)
        geometry_fields = [
            ("Half height", "half_height"),
            ("Half width", "half_width"),
            ("Letter step", "letter_step"),
            ("Space step", "space_step"),
            ("Pen drop", "pen_drop"),
        ]
        self._place_fields(frame, geometry_fields, start_row=5, columns=3)

        self._section_header(frame, "Starting point and rows", 8, 0, 4)
        start_fields = [
            ("Base X", "base_x"),
            ("Base Y", "base_y"),
            ("Base Z", "base_z"),
            ("Base R", "base_r"),
            ("Row step", "row_step"),
            ("Current row", "current_row"),
        ]
        self._place_fields(frame, start_fields, start_row=9, columns=3)

        row_btn_frame = ttk.Frame(frame)
        row_btn_frame.grid(row=11, column=2, columnspan=2, sticky="ew", padx=(10, 0), pady=(4, 0))
        row_btn_frame.columnconfigure(0, weight=1)
        row_btn_frame.columnconfigure(1, weight=1)

        ttk.Button(row_btn_frame, text="Previous Row", command=self.on_previous_row).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(row_btn_frame, text="Next Row", command=self.on_next_row).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

        ttk.Label(frame, text="Calculated WritingStart:").grid(
            row=12, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Label(frame, textvariable=self.vars["calculated_start"]).grid(
            row=12, column=1, columnspan=3, sticky="w", pady=(12, 0)
        )

    def _build_saved_positions_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Saved writing positions", padding=12)
        frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        headers = ["Name", "X", "Y", "Z", "R", "", "", ""]
        for column, text in enumerate(headers):
            if text:
                ttk.Label(frame, text=text, font=("Segoe UI", 9, "bold")).grid(
                    row=0, column=column, sticky="w", padx=4, pady=(0, 5)
                )

        frame.columnconfigure(0, weight=2)
        for column in range(1, 5):
            frame.columnconfigure(column, weight=1)

        for index, row_vars in enumerate(self.preset_vars):
            row = index + 1

            entries = [("name", 18), ("x", 10), ("y", 10), ("z", 10), ("r", 10)]
            for column, (key, width) in enumerate(entries):
                entry = ttk.Entry(frame, textvariable=row_vars[key], width=width)
                entry.grid(row=row, column=column, sticky="ew", padx=4, pady=3)
                entry.bind("<FocusOut>", lambda _event: self.save_state())

            ttk.Button(
                frame,
                text="Save Current",
                command=lambda i=index: self.on_save_current_pose(i),
            ).grid(row=row, column=5, padx=4, pady=3)

            ttk.Button(
                frame,
                text="Use as Start",
                command=lambda i=index: self.on_use_preset(i),
            ).grid(row=row, column=6, padx=4, pady=3)

            ttk.Button(
                frame,
                text="Go",
                command=lambda i=index: self.on_go_to_preset(i),
            ).grid(row=row, column=7, padx=4, pady=3)

        ttk.Label(
            frame,
            text=(
                "Save Current reads the robot's live GetPose(). "
                "Use as Start copies the preset into Base X/Y/Z/R. "
                "Go moves directly to the saved pose."
            ),
        ).grid(row=6, column=0, columnspan=8, sticky="w", padx=4, pady=(7, 0))

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Command / status log", padding=12)
        frame.grid(row=3, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.log_box = ScrolledText(frame, height=14, wrap="word", font=("Consolas", 10))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _section_header(self, parent: ttk.Frame, text: str, row: int, col: int, colspan: int) -> None:
        ttk.Label(parent, text=text, font=("Segoe UI", 10, "bold")).grid(
            row=row, column=col, columnspan=colspan, sticky="w", pady=(0, 4)
        )

    def _place_fields(self, parent: ttk.Frame, fields: list[tuple[str, str]], start_row: int, columns: int) -> None:
        for idx, (label_text, var_key) in enumerate(fields):
            row = start_row + idx // columns
            col = idx % columns

            cell = ttk.Frame(parent)
            cell.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0), pady=4)
            cell.columnconfigure(0, weight=1)

            ttk.Label(cell, text=label_text).grid(row=0, column=0, sticky="w")
            entry = ttk.Entry(cell, textvariable=self.vars[var_key])
            entry.grid(row=1, column=0, sticky="ew")
            entry.bind("<FocusOut>", lambda _event: self.refresh_calculated_start())

    # ============================================================
    # LOGGING / UI HELPERS
    # ============================================================

    def log_message(self, message: str) -> None:
        if hasattr(self, "log_box"):
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        else:
            print(message)

    def show_error(self, title: str, exc: Exception) -> None:
        self.log_message(f"ERROR: {exc}")
        messagebox.showerror(title, str(exc))

    def refresh_connection_status(self) -> None:
        if not self.writer.settings.live_robot:
            self.vars["connection_status"].set("Dry run")
        elif self.writer.is_connected:
            self.vars["connection_status"].set("Connected")
        else:
            self.vars["connection_status"].set("Not connected")

    def refresh_calculated_start(self) -> None:
        try:
            self.apply_settings_to_writer(show_log=False)
            x, y, z, r = self.writer.writing_start()
            self.vars["calculated_start"].set(
                f"X={x:.2f}, Y={y:.2f}, Z={z:.2f}, R={r:.2f}"
            )
            self.refresh_connection_status()
        except Exception:
            self.vars["calculated_start"].set("Enter valid numeric settings to calculate start.")
    
    # ============================================================
    # SETTINGS SYNC
    # ============================================================

    def apply_settings_to_writer(self, show_log: bool = True, save_after: bool = False) -> None:
        s = self.writer.settings

        s.live_robot = bool(self.vars["live_robot"].get())
        s.ip = str(self.vars["ip"].get()).strip()
        s.dashboard_port = int(self.vars["dashboard_port"].get())
        s.motion_port = int(self.vars["motion_port"].get())
        s.speed_factor = int(self.vars["speed_factor"].get())
        s.move_delay = float(self.vars["move_delay"].get())

        s.half_height = float(self.vars["half_height"].get())
        s.half_width = float(self.vars["half_width"].get())
        s.letter_step = float(self.vars["letter_step"].get())
        s.space_step = float(self.vars["space_step"].get())
        s.pen_drop = float(self.vars["pen_drop"].get())

        s.base_x = float(self.vars["base_x"].get())
        s.base_y = float(self.vars["base_y"].get())
        s.base_z = float(self.vars["base_z"].get())
        s.base_r = float(self.vars["base_r"].get())
        s.row_step = float(self.vars["row_step"].get())
        s.current_row = int(self.vars["current_row"].get())

        self.writer.rebuild_geometry()

        if show_log:
            self.log_message("Settings applied.")
        self.refresh_connection_status()

        if save_after:
            self.save_state()

    # ============================================================
    # BUTTON HANDLERS
    # ============================================================

    def on_apply_settings(self) -> None:
        try:
            self.apply_settings_to_writer(save_after=True)
            self.refresh_calculated_start()
        except Exception as exc:
            self.show_error("Settings error", exc)

    def on_connect(self) -> None:
        try:
            self.apply_settings_to_writer()
            self.writer.connect_robot()
            self.refresh_connection_status()
        except Exception as exc:
            self.show_error("Connection error", exc)

    def on_setup_robot(self) -> None:
        try:
            self.apply_settings_to_writer()
            self.writer.setup_robot()
        except Exception as exc:
            self.show_error("Setup error", exc)

    def on_move_to_start(self) -> None:
        try:
            self.apply_settings_to_writer()
            self.writer.go_to_writing_start()
        except Exception as exc:
            self.show_error("Movement error", exc)

    def on_write_text(self) -> None:
        try:
            self.apply_settings_to_writer()
            text = str(self.vars["text"].get())
            self.writer.write_text(text)
        except Exception as exc:
            self.show_error("Writing error", exc)
    def on_underline(self) -> None:
        try:
            self.apply_settings_to_writer()
            self.writer.draw_underline()

        except Exception as exc:
            self.show_error("Underline error", exc)


    def on_save_current_pose(self, index: int) -> None:
        try:
            self.apply_settings_to_writer(show_log=False)
            x, y, z, r = self.writer.get_current_pose()

            row_vars = self.preset_vars[index]
            row_vars["x"].set(f"{x:.3f}")
            row_vars["y"].set(f"{y:.3f}")
            row_vars["z"].set(f"{z:.3f}")
            row_vars["r"].set(f"{r:.3f}")

            if not str(row_vars["name"].get()).strip():
                row_vars["name"].set(f"Point {index + 1}")

            self.last_used_preset = index
            self.save_state()
            self.log_message(f"Saved current robot pose to {row_vars['name'].get()}.")
        except Exception as exc:
            self.show_error("Save position error", exc)

    def on_use_preset(self, index: int) -> None:
        try:
            x, y, z, r = self._preset_pose(index)
            row_vars = self.preset_vars[index]

            self.vars["base_x"].set(str(x))
            self.vars["base_y"].set(str(y))
            self.vars["base_z"].set(str(z))
            self.vars["base_r"].set(str(r))

            self.last_used_preset = index
            self.apply_settings_to_writer(show_log=False)
            self.refresh_calculated_start()
            self.save_state()
            self.log_message(f"Using {row_vars['name'].get()} as the writing base start.")
        except Exception as exc:
            self.show_error("Use saved position error", exc)

    def on_go_to_preset(self, index: int) -> None:
        try:
            self.apply_settings_to_writer(show_log=False)
            x, y, z, r = self._preset_pose(index)
            self.writer.move_to_pose(x, y, z, r)
            self.last_used_preset = index
            self.save_state()
        except Exception as exc:
            self.show_error("Move to saved position error", exc)

    def on_close(self) -> None:
        try:
            self.writer.close_robot()
            self.refresh_connection_status()
        except Exception as exc:
            self.show_error("Close error", exc)

    def on_next_row(self) -> None:
        try:
            self.apply_settings_to_writer(show_log=False)
            self.writer.next_row()
            self.vars["current_row"].set(str(self.writer.settings.current_row))
            self.refresh_calculated_start()
            self.save_state()
        except Exception as exc:
            self.show_error("Row error", exc)

    def on_previous_row(self) -> None:
        try:
            self.apply_settings_to_writer(show_log=False)
            self.writer.previous_row()
            self.vars["current_row"].set(str(self.writer.settings.current_row))
            self.refresh_calculated_start()
            self.save_state()
        except Exception as exc:
            self.show_error("Row error", exc)

    def destroy(self) -> None:
        try:
            self.save_state()
        except Exception:
            pass

        try:
            self.writer.close_robot()
        except Exception:
            pass

        super().destroy()


if __name__ == "__main__":
    app = MG400WriterApp()
    app.mainloop()
