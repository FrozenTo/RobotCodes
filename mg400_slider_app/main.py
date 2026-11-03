import tkinter as tk
from tkinter import messagebox

from dobot_api import DobotApiDashboard, DobotApiMove
import re

class MG400SliderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MG400 Slider Control")

        self.dashboard = None
        self.move = None
        self.connected = False

        # -------------------------
        # Connection settings
        # -------------------------
        tk.Label(root, text="Robot IP:").grid(row=0, column=0, sticky="w")

        self.ip_entry = tk.Entry(root, width=18)
        self.ip_entry.insert(0, "192.168.2.6")
        self.ip_entry.grid(row=0, column=1, sticky="w")

        tk.Button(root, text="Connect", command=self.connect_robot).grid(row=0, column=2, padx=5)

        # -------------------------
        # Control buttons
        # -------------------------
        tk.Button(root, text="Enable Robot", command=self.enable_robot).grid(row=1, column=0, pady=5)
        tk.Button(root, text="Disable Robot", command=self.disable_robot).grid(row=1, column=1, pady=5)
        tk.Button(root, text="Clear Error", command=self.clear_error).grid(row=1, column=2, pady=5)

        tk.Button(root, text="STOP", command=self.stop_robot, bg="red", fg="white").grid(
            row=1, column=3, padx=5, pady=5
        )

        # -------------------------
        # Sliders
        # IMPORTANT:
        # These are example limits.
        # Adjust them after checking your real MG400 workspace.
        # -------------------------
        self.x_slider = self.create_slider("X mm", row=2, min_val=100, max_val=350, default=280)
        self.y_slider = self.create_slider("Y mm", row=3, min_val=-250, max_val=250, default=0)
        self.z_slider = self.create_slider("Z mm", row=4, min_val=-80, max_val=250, default=100)
        self.r_slider = self.create_slider("R deg", row=5, min_val=-360, max_val=360, default=0)

        # -------------------------
        # Joint / limb sliders
        # -------------------------
        tk.Label(root, text="Joint / Limb Control").grid(row=10, column=0, sticky="w", pady=10)

        self.j1_slider = self.create_slider("J1 deg", row=11, min_val=-180, max_val=180, default=0)
        self.j2_slider = self.create_slider("J2 deg", row=12, min_val=-180, max_val=180, default=0)
        self.j3_slider = self.create_slider("J3 deg", row=13, min_val=-180, max_val=180, default=0)
        self.j4_slider = self.create_slider("J4 deg", row=14, min_val=-360, max_val=360, default=0)

        tk.Button(root, text="Read Current Joints", command=self.read_angles).grid(
            row=15, column=0, columnspan=2, pady=5
        )

        tk.Button(root, text="Move Joint Angles", command=self.move_joint_angles).grid(
            row=15, column=2, columnspan=2, pady=5
        )

        self.speed_slider = self.create_slider("Speed %", row=6, min_val=1, max_val=50, default=10)

        # -------------------------
        # Movement buttons
        # -------------------------
        tk.Button(root, text="Move Linear MovL", command=self.move_linear).grid(
            row=7, column=0, columnspan=2, pady=10
        )

        tk.Button(root, text="Move Joint MovJ", command=self.move_joint).grid(
            row=7, column=2, columnspan=2, pady=10
        )

        tk.Button(root, text="Read Current Pose", command=self.read_pose).grid(
            row=8, column=0, columnspan=2, pady=5
        )

        self.status_label = tk.Label(root, text="Not connected", fg="gray")
        self.status_label.grid(row=9, column=0, columnspan=4, sticky="w", pady=10)

    def create_slider(self, label, row, min_val, max_val, default):
        tk.Label(self.root, text=label).grid(row=row, column=0, sticky="w")

        slider = tk.Scale(
            self.root,
            from_=min_val,
            to=max_val,
            orient=tk.HORIZONTAL,
            length=350,
            resolution=1
        )
        slider.set(default)
        slider.grid(row=row, column=1, columnspan=3, sticky="w")

        return slider
    
    def connect_robot(self):
        ip = self.ip_entry.get().strip()

        try:
            self.dashboard = DobotApiDashboard(ip, 29999)
            self.move = DobotApiMove(ip, 30003)

            self.connected = True
            self.status_label.config(text=f"Connected to MG400 at {ip}", fg="green")

        except Exception as e:
            self.connected = False
            self.status_label.config(text="Connection failed", fg="red")
            messagebox.showerror("Connection Error", str(e))

    def read_angles(self):
        if not self.require_connection():
            return

        try:
            response = self.dashboard.GetAngle()
            j1, j2, j3, j4 = self.parse_angle(response)

            self.j1_slider.set(round(j1))
            self.j2_slider.set(round(j2))
            self.j3_slider.set(round(j3))
            self.j4_slider.set(round(j4))

            self.status_label.config(
                text=f"Current joints: J1={j1:.2f}, J2={j2:.2f}, J3={j3:.2f}, J4={j4:.2f}",
                fg="purple"
            )

        except Exception as e:
            messagebox.showerror("Read Joint Error", str(e))


    def parse_pose(self, response):
        text = str(response)

        match = re.search(r"\{([^}]*)\}", text)
        if not match:
            raise ValueError(f"Could not parse pose from response: {text}")

        values = match.group(1).split(",")

        if len(values) < 4:
            raise ValueError(f"Pose does not contain 4 values: {text}")

        x = float(values[0])
        y = float(values[1])
        z = float(values[2])
        r = float(values[3])

        return x, y, z, r
    def parse_angle(self, response):
        text = str(response)

        match = re.search(r"\{([^}]*)\}", text)
        if not match:
            raise ValueError(f"Could not parse angles from response: {text}")

        values = match.group(1).split(",")

        if len(values) < 4:
            raise ValueError(f"Angle response does not contain 4 values: {text}")

        j1 = float(values[0])
        j2 = float(values[1])
        j3 = float(values[2])
        j4 = float(values[3])

        return j1, j2, j3, j4

    def require_connection(self):
        if not self.connected or self.dashboard is None or self.move is None:
            messagebox.showwarning("Not connected", "Connect to the robot first.")
            return False
        return True

    def enable_robot(self):
        if not self.require_connection():
            return

        response = self.dashboard.EnableRobot()
        self.status_label.config(text=f"EnableRobot: {response}", fg="blue")

    def disable_robot(self):
        if not self.require_connection():
            return

        response = self.dashboard.DisableRobot()
        self.status_label.config(text=f"DisableRobot: {response}", fg="blue")

    def clear_error(self):
        if not self.require_connection():
            return

        response = self.dashboard.ClearError()
        self.status_label.config(text=f"ClearError: {response}", fg="blue")

    def stop_robot(self):
        if not self.require_connection():
            return

        # ResetRobot stops current robot execution.
        response = self.dashboard.ResetRobot()
        self.status_label.config(text=f"STOP / ResetRobot: {response}", fg="red")

    def get_slider_values(self):
        x = float(self.x_slider.get())
        y = float(self.y_slider.get())
        z = float(self.z_slider.get())
        r = float(self.r_slider.get())
        speed = int(self.speed_slider.get())

        return x, y, z, r, speed

    def move_linear(self):
        if not self.require_connection():
            return

        x, y, z, r, speed = self.get_slider_values()

        try:
            self.dashboard.SpeedL(speed)
            response = self.move.MovL(x, y, z, r)
            self.status_label.config(
                text=f"MovL to X={x}, Y={y}, Z={z}, R={r}: {response}",
                fg="green"
            )

        except Exception as e:
            messagebox.showerror("Move Error", str(e))

    def move_joint(self):
        if not self.require_connection():
            return

        x, y, z, r, speed = self.get_slider_values()

        try:
            self.dashboard.SpeedJ(speed)
            response = self.move.MovJ(x, y, z, r)
            self.status_label.config(
                text=f"MovJ to X={x}, Y={y}, Z={z}, R={r}: {response}",
                fg="green"
            )

        except Exception as e:
            messagebox.showerror("Move Error", str(e))

    def move_joint_angles(self):
        if not self.require_connection():
            return

        j1 = float(self.j1_slider.get())
        j2 = float(self.j2_slider.get())
        j3 = float(self.j3_slider.get())
        j4 = float(self.j4_slider.get())
        speed = int(self.speed_slider.get())

        try:
            self.dashboard.SpeedJ(speed)
            response = self.move.JointMovJ(j1, j2, j3, j4)

            self.status_label.config(
                text=f"JointMovJ to J1={j1}, J2={j2}, J3={j3}, J4={j4}: {response}",
                fg="green"
            )

        except Exception as e:
            messagebox.showerror("Joint Move Error", str(e))


    def read_pose(self):
        if not self.require_connection():
            return

        try:
            response = self.dashboard.GetPose()
            x, y, z, r = self.parse_pose(response)

            self.x_slider.set(round(x))
            self.y_slider.set(round(y))
            self.z_slider.set(round(z))
            self.r_slider.set(round(r))

            self.status_label.config(
                text=f"Current pose: X={x:.2f}, Y={y:.2f}, Z={z:.2f}, R={r:.2f}",
                fg="purple"
            )

        except Exception as e:
            messagebox.showerror("Read Pose Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = MG400SliderApp(root)
    root.mainloop()