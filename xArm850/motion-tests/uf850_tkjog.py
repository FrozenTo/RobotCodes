import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

from xarm.wrapper import XArmAPI


ROBOT_IP = "192.168.1.208"


class UF850JogApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UFACTORY 850 - Wall Writer Control")
        self.root.geometry("780x650")

        self.arm = None
        self.connected = False

        self.build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def build_ui(self):
        # =========================
        # CONNECTION
        # =========================

        connection_frame = ttk.LabelFrame(
            self.root,
            text="Robot Connection",
            padding=10
        )
        connection_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(
            connection_frame,
            text="Robot IP:"
        ).grid(row=0, column=0, padx=5)

        self.ip_var = tk.StringVar(value=ROBOT_IP)

        ttk.Entry(
            connection_frame,
            textvariable=self.ip_var,
            width=18
        ).grid(row=0, column=1, padx=5)

        ttk.Button(
            connection_frame,
            text="Connect",
            command=self.connect_robot
        ).grid(row=0, column=2, padx=5)

        ttk.Button(
            connection_frame,
            text="Disconnect",
            command=self.disconnect_robot
        ).grid(row=0, column=3, padx=5)

        ttk.Button(
            connection_frame,
            text="Enable Movement",
            command=self.enable_robot
        ).grid(row=0, column=4, padx=5)

        self.connection_label = ttk.Label(
            connection_frame,
            text="Disconnected"
        )
        self.connection_label.grid(
            row=1,
            column=0,
            columnspan=5,
            pady=5
        )

        # =========================
        # CURRENT POSITION
        # =========================

        pose_frame = ttk.LabelFrame(
            self.root,
            text="Current TCP Pose",
            padding=10
        )
        pose_frame.pack(fill="x", padx=10, pady=5)

        self.pose_labels = {}

        names = [
            "X",
            "Y",
            "Z",
            "Roll",
            "Pitch",
            "Yaw"
        ]

        for i, name in enumerate(names):
            ttk.Label(
                pose_frame,
                text=f"{name}:"
            ).grid(row=0, column=i * 2, padx=3)

            label = ttk.Label(
                pose_frame,
                text="---",
                width=10
            )

            label.grid(
                row=0,
                column=i * 2 + 1,
                padx=3
            )

            self.pose_labels[name] = label

        ttk.Button(
            pose_frame,
            text="Refresh Pose",
            command=self.refresh_pose
        ).grid(
            row=1,
            column=0,
            columnspan=12,
            pady=10
        )

        # =========================
        # SETTINGS
        # =========================

        settings_frame = ttk.LabelFrame(
            self.root,
            text="Jog Settings",
            padding=10
        )
        settings_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(
            settings_frame,
            text="XYZ step (mm):"
        ).grid(row=0, column=0, padx=5)

        self.xyz_step_var = tk.DoubleVar(value=5.0)

        ttk.Entry(
            settings_frame,
            textvariable=self.xyz_step_var,
            width=8
        ).grid(row=0, column=1)

        ttk.Label(
            settings_frame,
            text="XYZ speed (mm/s):"
        ).grid(row=0, column=2, padx=5)

        self.xyz_speed_var = tk.DoubleVar(value=20.0)

        ttk.Entry(
            settings_frame,
            textvariable=self.xyz_speed_var,
            width=8
        ).grid(row=0, column=3)

        ttk.Label(
            settings_frame,
            text="Joint step (°):"
        ).grid(row=0, column=4, padx=5)

        self.joint_step_var = tk.DoubleVar(value=5.0)

        ttk.Entry(
            settings_frame,
            textvariable=self.joint_step_var,
            width=8
        ).grid(row=0, column=5)

        ttk.Label(
            settings_frame,
            text="Joint speed (°/s):"
        ).grid(row=0, column=6, padx=5)

        self.joint_speed_var = tk.DoubleVar(value=10.0)

        ttk.Entry(
            settings_frame,
            textvariable=self.joint_speed_var,
            width=8
        ).grid(row=0, column=7)

        # =========================
        # CARTESIAN JOG
        # =========================

        jog_frame = ttk.LabelFrame(
            self.root,
            text="Cartesian Jog",
            padding=10
        )
        jog_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(
            jog_frame,
            text="Wall is on -X side"
        ).grid(
            row=0,
            column=0,
            columnspan=6,
            pady=5
        )

        ttk.Button(
            jog_frame,
            text="X-  Toward Wall",
            command=lambda: self.jog_xyz("x", -1)
        ).grid(row=1, column=0, padx=5, pady=5)

        ttk.Button(
            jog_frame,
            text="X+  Away From Wall",
            command=lambda: self.jog_xyz("x", 1)
        ).grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(
            jog_frame,
            text="Y-",
            command=lambda: self.jog_xyz("y", -1)
        ).grid(row=1, column=2, padx=5, pady=5)

        ttk.Button(
            jog_frame,
            text="Y+  Writing →",
            command=lambda: self.jog_xyz("y", 1)
        ).grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(
            jog_frame,
            text="Z-  Down",
            command=lambda: self.jog_xyz("z", -1)
        ).grid(row=1, column=4, padx=5, pady=5)

        ttk.Button(
            jog_frame,
            text="Z+  Up",
            command=lambda: self.jog_xyz("z", 1)
        ).grid(row=1, column=5, padx=5, pady=5)

        # =========================
        # J1 JOG
        # =========================

        joint_frame = ttk.LabelFrame(
            self.root,
            text="Joint Jog",
            padding=10
        )
        joint_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            joint_frame,
            text="J1 -",
            command=lambda: self.jog_joint1(-1)
        ).pack(
            side="left",
            padx=10,
            pady=5,
            expand=True
        )

        ttk.Button(
            joint_frame,
            text="J1 +",
            command=lambda: self.jog_joint1(1)
        ).pack(
            side="left",
            padx=10,
            pady=5,
            expand=True
        )

        self.joint_label = ttk.Label(
            joint_frame,
            text="J1: ---"
        )

        self.joint_label.pack(
            side="left",
            padx=20
        )

        ttk.Button(
            joint_frame,
            text="Refresh Joints",
            command=self.refresh_joints
        ).pack(
            side="left",
            padx=10
        )

        # =========================
        # SAFETY
        # =========================

        safety_frame = ttk.LabelFrame(
            self.root,
            text="Safety",
            padding=10
        )
        safety_frame.pack(fill="x", padx=10, pady=5)

        stop_button = tk.Button(
            safety_frame,
            text="EMERGENCY STOP",
            command=self.emergency_stop,
            font=("Arial", 14, "bold"),
            height=2
        )

        stop_button.pack(fill="x")

        # =========================
        # LOG
        # =========================

        log_frame = ttk.LabelFrame(
            self.root,
            text="Log",
            padding=10
        )
        log_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )

        self.log_box = tk.Text(
            log_frame,
            height=10,
            state="disabled"
        )

        self.log_box.pack(
            fill="both",
            expand=True
        )

    # --------------------------------------------------
    # LOG
    # --------------------------------------------------

    def log(self, text):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def connect_robot(self):
        if self.connected:
            self.log("Already connected.")
            return

        ip = self.ip_var.get().strip()

        try:
            self.log(f"Connecting to {ip}...")

            self.arm = XArmAPI(
                ip,
                is_radian=False
            )

            if not self.arm.connected:
                self.log("Connection failed.")
                return

            self.connected = True

            self.connection_label.config(
                text="Connected"
            )

            self.log("Connected successfully.")

            self.log(
                f"Version: {self.arm.get_version()}"
            )

            self.log(
                f"State: {self.arm.get_state()}"
            )

            self.log(
                f"Errors: {self.arm.get_err_warn_code()}"
            )

            self.refresh_pose()
            self.refresh_joints()

        except Exception as e:
            self.log(f"Connection error: {e}")

    def disconnect_robot(self):
        if self.arm:
            try:
                self.arm.disconnect()
            except Exception:
                pass

        self.arm = None
        self.connected = False

        self.connection_label.config(
            text="Disconnected"
        )

        self.log("Disconnected.")

    # --------------------------------------------------
    # ENABLE
    # --------------------------------------------------

    def enable_robot(self):
        if not self.check_connection():
            return

        def task():
            try:
                self.log("Enabling robot...")

                ret = self.arm.motion_enable(
                    enable=True
                )
                self.log(
                    f"motion_enable: {ret}"
                )

                ret = self.arm.set_mode(0)
                self.log(
                    f"set_mode(0): {ret}"
                )

                ret = self.arm.set_state(0)
                self.log(
                    f"set_state(0): {ret}"
                )

                time.sleep(0.5)

                self.log("Robot ready.")

                self.refresh_pose()

            except Exception as e:
                self.log(f"Enable error: {e}")

        threading.Thread(
            target=task,
            daemon=True
        ).start()

    # --------------------------------------------------
    # CARTESIAN MOVEMENT
    # --------------------------------------------------

    def jog_xyz(self, axis, direction):
        if not self.check_connection():
            return

        try:
            step = float(
                self.xyz_step_var.get()
            )

            speed = float(
                self.xyz_speed_var.get()
            )

        except ValueError:
            messagebox.showerror(
                "Error",
                "Invalid movement settings."
            )
            return

        dx = 0
        dy = 0
        dz = 0

        value = step * direction

        if axis == "x":
            dx = value

        elif axis == "y":
            dy = value

        elif axis == "z":
            dz = value

        # Extra warning when moving toward wall
        if axis == "x" and direction < 0:
            self.log(
                f"Moving {step} mm toward wall (-X)"
            )

        def task():
            try:
                ret = self.arm.set_position(
                    dx,
                    dy,
                    dz,
                    0,
                    0,
                    0,
                    speed=speed,
                    relative=True,
                    wait=True,
                    is_radian=False
                )

                self.log(
                    f"{axis.upper()} move result: {ret}"
                )

                self.refresh_pose()

            except Exception as e:
                self.log(
                    f"Movement error: {e}"
                )

        threading.Thread(
            target=task,
            daemon=True
        ).start()

    # --------------------------------------------------
    # J1 MOVEMENT
    # --------------------------------------------------

    def jog_joint1(self, direction):
        if not self.check_connection():
            return

        try:
            step = float(
                self.joint_step_var.get()
            )

            speed = float(
                self.joint_speed_var.get()
            )

        except ValueError:
            messagebox.showerror(
                "Error",
                "Invalid joint settings."
            )
            return

        angle_change = step * direction

        def task():
            try:
                self.log(
                    f"Moving J1 {angle_change:+.1f}°"
                )

                ret = self.arm.set_servo_angle(
                    servo_id=1,
                    angle=angle_change,
                    speed=speed,
                    relative=True,
                    wait=True,
                    is_radian=False
                )

                self.log(
                    f"J1 move result: {ret}"
                )

                self.refresh_joints()
                self.refresh_pose()

            except Exception as e:
                self.log(
                    f"J1 error: {e}"
                )

        threading.Thread(
            target=task,
            daemon=True
        ).start()

    # --------------------------------------------------
    # POSE
    # --------------------------------------------------

    def refresh_pose(self):
        if not self.check_connection(
            show_message=False
        ):
            return

        try:
            code, pose = self.arm.get_position(
                is_radian=False
            )

            if code != 0:
                self.log(
                    f"Pose read error: {code}"
                )
                return

            names = [
                "X",
                "Y",
                "Z",
                "Roll",
                "Pitch",
                "Yaw"
            ]

            for name, value in zip(
                names,
                pose
            ):
                self.pose_labels[
                    name
                ].config(
                    text=f"{value:.2f}"
                )

        except Exception as e:
            self.log(
                f"Pose error: {e}"
            )

    # --------------------------------------------------
    # JOINTS
    # --------------------------------------------------

    def refresh_joints(self):
        if not self.check_connection(
            show_message=False
        ):
            return

        try:
            code, joints = (
                self.arm.get_servo_angle(
                    is_radian=False
                )
            )

            if code != 0:
                self.log(
                    f"Joint read error: {code}"
                )
                return

            self.joint_label.config(
                text=f"J1: {joints[0]:.2f}°"
            )

        except Exception as e:
            self.log(
                f"Joint error: {e}"
            )

    # --------------------------------------------------
    # EMERGENCY STOP
    # --------------------------------------------------

    def emergency_stop(self):
        if not self.arm:
            return

        try:
            self.arm.emergency_stop()
            self.log("EMERGENCY STOP activated.")

        except Exception as e:
            self.log(
                f"Emergency stop error: {e}"
            )

    # --------------------------------------------------
    # UTIL
    # --------------------------------------------------

    def check_connection(
        self,
        show_message=True
    ):
        if not self.arm or not self.connected:
            if show_message:
                messagebox.showwarning(
                    "Robot",
                    "Robot is not connected."
                )

            return False

        return True


if __name__ == "__main__":
    root = tk.Tk()

    app = UF850JogApp(root)

    root.mainloop()