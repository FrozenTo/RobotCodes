"""
Tkinter desktop app for the MG400 text writer.

SP32

Run:
    python mg400_writer_app.py
"""
#157.3 - 142.3
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict

from mg400_writer import MG400Writer


class MG400WriterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("MG400 Text Writer")
        self.geometry("1080x760")
        self.minsize(980, 680)

        self.writer = MG400Writer(logger=self.log_message)

        self.vars: Dict[str, tk.Variable] = {}
        self._build_variables()
        self._build_layout()
        self.refresh_calculated_start()
        self.log_message("MG400 Text Writer ready.")

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def _build_variables(self) -> None:
        s = self.writer.settings

        self.vars = {
            "text": tk.StringVar(value="Text Here"),

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
        outer.rowconfigure(2, weight=1)

        self._build_text_panel(outer)
        self._build_action_panel(outer)
        self._build_settings_panel(outer)
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

    def _build_log_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Command / status log", padding=12)
        frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
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

    def apply_settings_to_writer(self, show_log: bool = True) -> None:
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

    # ============================================================
    # BUTTON HANDLERS
    # ============================================================

    def on_apply_settings(self) -> None:
        try:
            self.apply_settings_to_writer()
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
        except Exception as exc:
            self.show_error("Row error", exc)

    def on_previous_row(self) -> None:
        try:
            self.apply_settings_to_writer(show_log=False)
            self.writer.previous_row()
            self.vars["current_row"].set(str(self.writer.settings.current_row))
            self.refresh_calculated_start()
        except Exception as exc:
            self.show_error("Row error", exc)

    def destroy(self) -> None:
        try:
            self.writer.close_robot()
        except Exception:
            pass
        super().destroy()


if __name__ == "__main__":
    app = MG400WriterApp()
    app.mainloop()
