from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
import cv2
from flask import Flask, Response, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
CELLS_PATH = BASE_DIR / "data" / "cells.json"

app = Flask(__name__)
robot_lock = threading.RLock()
state_lock = threading.RLock()
usb_camera_lock = threading.RLock()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default.copy()


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


config = load_json(CONFIG_PATH, {})
cells = load_json(CELLS_PATH, {})

runtime = {
    "enabled": False,
    "busy": False,
    "last_error": "",
    "last_command": "",
}

LETTERS = "ABCDEFGHIJ"
ROWS = range(1, 6)


def default_cell(name: str) -> dict[str, Any]:
    return {"blocked": False, "label": "", "role": "", "pick_z": None, "place_z": None}


def get_cell(name: str) -> dict[str, Any]:
    data = default_cell(name)
    data.update(cells.get(name, {}))
    return data


def cell_xy(name: str) -> tuple[float, float]:
    if len(name) < 2 or name[0] not in LETTERS:
        raise ValueError("Invalid cell")
    row = int(name[1:])
    if row not in ROWS:
        raise ValueError("Invalid row")
    col_index = LETTERS.index(name[0])
    pitch = float(config["grid_pitch"])
    x = float(config["grid_x_row1"]) - pitch * (row - 1)
    y = float(config["grid_y_colA"]) + pitch * col_index
    return round(x, 3), round(y, 3)


def send_socket_command(port: int, command: str, timeout: float = 2.0) -> str:
    """Send one MG400 TCP command and collect the reply.

    The controller can occasionally take a short moment before returning data, so
    a single recv() is too brittle. Read until the normal ';' terminator or until
    the timeout expires. An empty reply is returned only after the whole receive
    window has elapsed.
    """
    ip = str(config["robot_ip"])
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    with socket.create_connection((ip, port), timeout=timeout) as sock:
        sock.settimeout(0.25)
        sock.sendall(command.strip().encode("utf-8"))
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            if b";" in chunk:
                break
    return b"".join(chunks).decode("utf-8", errors="replace").strip()


def dashboard(command: str) -> str:
    return send_socket_command(int(config["dashboard_port"]), command)


def motion(command: str) -> str:
    return send_socket_command(int(config["motion_port"]), command)


POSE_RE = re.compile(r"\{\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")


def get_pose(attempts: int = 5) -> list[float]:
    last_reply = ""
    for attempt in range(max(1, attempts)):
        reply = dashboard("GetPose()")
        last_reply = reply
        match = POSE_RE.search(reply)
        if match:
            return [float(match.group(i)) for i in range(1, 5)]
        if attempt + 1 < attempts:
            time.sleep(0.12)
    raise RuntimeError(f"Could not parse GetPose response after {attempts} attempts: {last_reply!r}")


def set_last(command: str = "", error: str = "") -> None:
    with state_lock:
        if command:
            runtime["last_command"] = command
        runtime["last_error"] = error


def wait_until_pose(target: list[float], check_r: bool = False) -> None:
    tolerance = float(config.get("pose_tolerance_mm", 1.0))
    timeout = float(config.get("move_timeout_seconds", 20.0))
    deadline = time.time() + timeout
    last_pose_error = ""
    while time.time() < deadline:
        try:
            p = get_pose()
            last_pose_error = ""
        except RuntimeError as exc:
            # A transient empty dashboard read must not turn a completed move
            # into a false failure. Keep polling until the movement timeout.
            last_pose_error = str(exc)
            time.sleep(0.12)
            continue
        xyz_ok = all(abs(p[i] - target[i]) <= tolerance for i in range(3))
        r_ok = (not check_r) or abs(p[3] - target[3]) <= 2.0
        if xyz_ok and r_ok:
            return
        time.sleep(0.12)
    extra = f" Last pose read: {last_pose_error}" if last_pose_error else ""
    raise TimeoutError(f"Robot did not reach target {target} within {timeout:.1f}s.{extra}")


def apply_speed_factor() -> None:
    speed = max(1, min(100, int(round(float(config.get("speed_factor", 20))))))
    reply = dashboard(f"SpeedFactor({speed})")
    if reply and not reply.lstrip().startswith("0"):
        raise RuntimeError(f"SpeedFactor({speed}) -> {reply}")


def move_abs(x: float, y: float, z: float, r: float, linear: bool = False) -> None:
    cmd_name = "MovL" if linear else "MovJ"
    command = f"{cmd_name}({x:.3f},{y:.3f},{z:.3f},{r:.3f})"
    set_last(command)
    # Re-apply the global speed immediately before every move. This prevents a
    # reconnect, reboot, or another controller from silently leaving the MG400
    # at 100% speed.
    apply_speed_factor()
    reply = motion(command)
    if reply and not reply.lstrip().startswith("0"):
        raise RuntimeError(f"{command} -> {reply}")
    wait_until_pose([x, y, z, r], check_r=False)


def ensure_cell_reachable(name: str) -> dict[str, Any]:
    c = get_cell(name)
    if c.get("blocked"):
        raise ValueError(f"{name} is marked unreachable/blocked")
    cell_xy(name)  # validates name
    return c


def move_safe_to_cell(name: str) -> None:
    ensure_cell_reachable(name)
    x, y = cell_xy(name)
    safe_z = float(config["safe_z"])
    current = get_pose()
    # First lift vertically at current XY, then move across at safe Z.
    if abs(current[2] - safe_z) > 0.5:
        move_abs(current[0], current[1], safe_z, current[3], linear=True)
    move_abs(x, y, safe_z, current[3], linear=False)


def move_cell_height(name: str, field: str) -> None:
    c = ensure_cell_reachable(name)
    z = c.get(field)
    if z is None:
        raise ValueError(f"{name} has no {field.replace('_', ' ')} configured")
    move_safe_to_cell(name)
    p = get_pose()
    move_abs(p[0], p[1], float(z), p[3], linear=True)


def set_do(channel: int, value: int) -> None:
    command = f"DO({int(channel)},{int(value)})"
    set_last(command)
    reply = dashboard(command)
    if reply and not reply.lstrip().startswith("0"):
        raise RuntimeError(f"{command} -> {reply}")


def suction(on: bool) -> None:
    set_do(int(config.get("suction_do", 2)), 1 if on else 0)


def blow_pulse() -> None:
    channel = int(config.get("blow_do", 1))
    set_do(channel, 1)
    time.sleep(float(config.get("blow_seconds", 0.5)))
    set_do(channel, 0)


def execute_locked(fn):
    with robot_lock:
        with state_lock:
            runtime["busy"] = True
        try:
            return fn()
        finally:
            with state_lock:
                runtime["busy"] = False


def open_usb_camera(index: int | None = None):
    """Open the station/host PC USB camera.

    On Windows CAP_DSHOW generally avoids the long Media Foundation startup delay.
    Fall back to the default backend if DirectShow is unavailable.
    """
    idx = int(config.get("usb_camera_index", 0) if index is None else index)
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open USB camera index {idx}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(config.get("usb_camera_width", 1280)))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(config.get("usb_camera_height", 720)))
    cap.set(cv2.CAP_PROP_FPS, int(config.get("usb_camera_fps", 15)))
    return cap


def read_usb_frame(index: int | None = None) -> tuple[bytes, dict[str, Any]]:
    """Capture one JPEG frame and return bytes + actual camera properties."""
    with usb_camera_lock:
        cap = open_usb_camera(index)
        try:
            # Give auto-exposure a few frames to settle a little.
            frame = None
            for _ in range(4):
                ok, candidate = cap.read()
                if ok:
                    frame = candidate
                time.sleep(0.025)
            if frame is None:
                raise RuntimeError("USB camera opened but returned no frame")
            ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if not ok:
                raise RuntimeError("Could not encode USB camera frame")
            info = {
                "index": int(config.get("usb_camera_index", 0) if index is None else index),
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
                "fps_requested": int(config.get("usb_camera_fps", 15)),
            }
            return encoded.tobytes(), info
        finally:
            cap.release()


def usb_mjpeg_generator():
    """MJPEG generator for the overhead/table camera connected to the host PC."""
    idx = int(config.get("usb_camera_index", 0))
    with usb_camera_lock:
        cap = open_usb_camera(idx)
        try:
            target_fps = max(1, min(30, int(config.get("usb_camera_fps", 15))))
            delay = 1.0 / target_fps
            while True:
                started = time.perf_counter()
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.1)
                    continue
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
                if not ok:
                    continue
                jpg = encoded.tobytes()
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(jpg)).encode("ascii") + b"\r\n\r\n" + jpg + b"\r\n")
                elapsed = time.perf_counter() - started
                if elapsed < delay:
                    time.sleep(delay - elapsed)
        finally:
            cap.release()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    try:
        pose = get_pose()
        online = True
        error = ""
    except Exception as exc:
        pose = None
        online = False
        error = str(exc)
    with state_lock:
        rt = dict(runtime)
    return jsonify({
        "online": online,
        "pose": pose,
        "runtime": rt,
        "config": {
            "robot_ip": config.get("robot_ip"),
            "dashboard_port": config.get("dashboard_port"),
            "motion_port": config.get("motion_port"),
            "safe_z": config.get("safe_z"),
            "speed_factor": config.get("speed_factor"),
            "camera_stream_url": config.get("camera_stream_url", ""),
            "grid_pitch": config.get("grid_pitch"),
            "grid_x_row1": config.get("grid_x_row1"),
            "grid_y_colA": config.get("grid_y_colA"),
            "usb_camera_index": config.get("usb_camera_index", 0),
            "usb_camera_width": config.get("usb_camera_width", 1280),
            "usb_camera_height": config.get("usb_camera_height", 720),
            "usb_camera_fps": config.get("usb_camera_fps", 15),
            "assembly_z_glass": config.get("assembly_z_glass", -150.21),
            "assembly_z_atom_glass": config.get("assembly_z_atom_glass", -140.59),
            "assembly_z_full": config.get("assembly_z_full", -122.92),
            "assembly_z_full_pick": config.get("assembly_z_full_pick", config.get("assembly_z_full", -122.92)),
            "assembly_z_full_place": config.get("assembly_z_full_place", -125.52),
            "assembly_r": config.get("assembly_r", -50.18),
        },
        "error": error,
    })


@app.get("/api/grid")
def api_grid():
    output = []
    for row in ROWS:
        for letter in LETTERS:
            name = f"{letter}{row}"
            x, y = cell_xy(name)
            output.append({"name": name, "x": x, "y": y, **get_cell(name)})
    return jsonify(output)


@app.post("/api/cell/<name>")
def api_save_cell(name: str):
    name = name.upper()
    cell_xy(name)
    body = request.get_json(force=True) or {}
    c = get_cell(name)
    c["label"] = str(body.get("label", c.get("label", ""))).strip()[:80]
    c["blocked"] = bool(body.get("blocked", c.get("blocked", False)))
    c["role"] = str(body.get("role", c.get("role", ""))).strip()[:40]
    for field in ("pick_z", "place_z"):
        raw = body.get(field, c.get(field))
        c[field] = None if raw in (None, "") else float(raw)
    cells[name] = c
    save_json(CELLS_PATH, cells)
    return jsonify({"ok": True, "cell": {"name": name, "x": cell_xy(name)[0], "y": cell_xy(name)[1], **c}})


@app.post("/api/settings")
def api_settings():
    body = request.get_json(force=True) or {}
    numeric = ["safe_z", "grid_pitch", "grid_x_row1", "grid_y_colA", "speed_factor", "usb_camera_index", "usb_camera_width", "usb_camera_height", "usb_camera_fps", "assembly_z_glass", "assembly_z_atom_glass", "assembly_z_full", "assembly_z_full_pick", "assembly_z_full_place", "assembly_r"]
    strings = ["camera_stream_url", "robot_ip"]
    for key in numeric:
        if key in body:
            config[key] = float(body[key])
    for key in strings:
        if key in body:
            config[key] = str(body[key]).strip()
    save_json(CONFIG_PATH, config)
    return jsonify({"ok": True})


def checked_dashboard(command: str) -> str:
    reply = dashboard(command)
    if not reply:
        raise RuntimeError(f"{command} returned no response")
    if not reply.lstrip().startswith("0"):
        raise RuntimeError(f"{command} -> {reply}")
    return reply


def test_tcp_port(ip: str, port: int, timeout: float = 1.5) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            ms = (time.perf_counter() - started) * 1000.0
            return {"ok": True, "ms": round(ms, 1)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/api/robot/test")
def api_robot_test():
    ip = str(config.get("robot_ip", "")).strip()
    dash_port = int(config.get("dashboard_port", 29999))
    move_port = int(config.get("motion_port", 30003))
    result: dict[str, Any] = {
        "ok": False,
        "ip": ip,
        "dashboard_port": dash_port,
        "motion_port": move_port,
    }
    result["dashboard_tcp"] = test_tcp_port(ip, dash_port)
    result["motion_tcp"] = test_tcp_port(ip, move_port)
    if result["dashboard_tcp"]["ok"]:
        try:
            reply = dashboard("GetPose()")
            result["get_pose_reply"] = reply
            match = POSE_RE.search(reply)
            if match:
                result["pose"] = [float(match.group(i)) for i in range(1, 5)]
            else:
                result["get_pose_warning"] = "Dashboard and motion ports connected; GetPose returned no usable data on this test."
            result["ok"] = bool(result["motion_tcp"]["ok"])
        except Exception as exc:
            result["get_pose_error"] = str(exc)
    if not result["ok"]:
        problems = []
        if not result["dashboard_tcp"]["ok"]:
            problems.append(f"dashboard {dash_port}: {result['dashboard_tcp'].get('error', 'failed')}")
        if not result["motion_tcp"]["ok"]:
            problems.append(f"motion {move_port}: {result['motion_tcp'].get('error', 'failed')}")
        result["error"] = "; ".join(problems) or "Robot connection test failed"
    return jsonify(result), (200 if result["ok"] else 503)


@app.post("/api/robot/enable")
def api_enable():
    def work():
        checked_dashboard("ClearError()")
        # MG400 can need a moment after clearing an E-stop/error before EnableRobot is accepted.
        time.sleep(1.5)
        checked_dashboard("EnableRobot()")
        apply_speed_factor()
        with state_lock:
            runtime["enabled"] = True
        return {"ok": True}
    try:
        return jsonify(execute_locked(work))
    except Exception as exc:
        with state_lock:
            runtime["enabled"] = False
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/robot/disable")
def api_disable():
    try:
        with robot_lock:
            try:
                suction(False)
                set_do(int(config.get("blow_do", 1)), 0)
            except Exception:
                pass
            dashboard("DisableRobot()")
            with state_lock:
                runtime["enabled"] = False
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/robot/stop")
def api_stop():
    try:
        dashboard("Stop()")
        set_last("Stop()")
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/move/above/<name>")
def api_move_above(name: str):
    name = name.upper()
    try:
        execute_locked(lambda: move_safe_to_cell(name))
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/move/pick/<name>")
def api_pick(name: str):
    name = name.upper()
    def work():
        move_cell_height(name, "pick_z")
        suction(True)
        time.sleep(float(config.get("pick_settle_seconds", 0.35)))
        p = get_pose()
        move_abs(p[0], p[1], float(config["safe_z"]), p[3], linear=True)
    try:
        execute_locked(work)
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/move/place/<name>")
def api_place(name: str):
    name = name.upper()
    def work():
        move_cell_height(name, "place_z")
        suction(False)
        time.sleep(float(config.get("place_settle_seconds", 0.2)))
        blow_pulse()
        p = get_pose()
        move_abs(p[0], p[1], float(config["safe_z"]), p[3], linear=True)
    try:
        execute_locked(work)
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/move/transfer")
def api_transfer():
    body = request.get_json(force=True) or {}
    source = str(body.get("source", "")).upper()
    destination = str(body.get("destination", "")).upper()

    def work():
        if source == destination:
            raise ValueError("Source and destination are the same cell")
        move_cell_height(source, "pick_z")
        suction(True)
        time.sleep(float(config.get("pick_settle_seconds", 0.35)))
        p = get_pose()
        move_abs(p[0], p[1], float(config["safe_z"]), p[3], linear=True)
        move_cell_height(destination, "place_z")
        suction(False)
        time.sleep(float(config.get("place_settle_seconds", 0.2)))
        blow_pulse()
        p = get_pose()
        move_abs(p[0], p[1], float(config["safe_z"]), p[3], linear=True)

    try:
        execute_locked(work)
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/tool/suction")
def api_suction():
    body = request.get_json(force=True) or {}
    try:
        with robot_lock:
            suction(bool(body.get("on")))
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/tool/blow")
def api_blow():
    try:
        with robot_lock:
            blow_pulse()
        return jsonify({"ok": True})
    except Exception as exc:
        set_last(error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500



@app.get("/camera/usb/stream")
def usb_camera_stream():
    try:
        return Response(usb_mjpeg_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception as exc:
        return Response(str(exc), status=503, mimetype="text/plain")


@app.get("/camera/usb/snapshot")
def usb_camera_snapshot():
    try:
        frame, _ = read_usb_frame()
        return Response(frame, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})
    except Exception as exc:
        return Response(str(exc), status=503, mimetype="text/plain")


@app.post("/api/camera/usb/test")
def api_usb_camera_test():
    body = request.get_json(silent=True) or {}
    try:
        idx = int(body.get("index", config.get("usb_camera_index", 0)))
        frame, info = read_usb_frame(idx)
        info["jpeg_bytes"] = len(frame)
        return jsonify({"ok": True, **info})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.post("/api/camera/test")
def api_camera_test():
    raw = str(config.get("camera_stream_url", "")).strip()
    if not raw:
        return jsonify({"ok": False, "error": "Camera address is not configured"}), 400
    try:
        control, stream, snapshot = normalize_camera_urls(raw)
        # Test with a single still image instead of opening a second endless MJPEG stream.
        # This is friendlier to the ESP32 and avoids colliding with a stream already open in a browser.
        if not snapshot:
            raise RuntimeError("Could not derive the XIAO /capture endpoint from this camera address")
        r = requests.get(snapshot, timeout=(3, 8))
        content_type = r.headers.get("Content-Type", "")
        status = r.status_code
        size = len(r.content)
        if status >= 400:
            raise RuntimeError(f"Camera snapshot returned HTTP {status}")
        if "image" not in content_type.lower():
            raise RuntimeError(f"Camera snapshot returned unexpected Content-Type: {content_type or 'unknown'}")
        if size < 100:
            raise RuntimeError("Camera snapshot response was unexpectedly small")
        return jsonify({"ok": True, "control_url": control, "stream_url": stream, "snapshot_url": snapshot, "content_type": content_type, "snapshot_bytes": size})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

@app.get("/camera/stream")
def camera_stream():
    raw = str(config.get("camera_stream_url", "")).strip()
    if not raw:
        return Response("Camera address is not configured", status=404, mimetype="text/plain")
    try:
        _, url, _ = normalize_camera_urls(raw)
        upstream = requests.get(url, stream=True, timeout=(3, 30))
        upstream.raise_for_status()
        content_type = upstream.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame")

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        return Response(generate(), content_type=content_type)
    except Exception as exc:
        return Response(f"Camera unavailable: {exc}", status=502, mimetype="text/plain")




def normalize_camera_urls(value: str) -> tuple[str, str, str]:
    """Return (control_page, stream_url, snapshot_url) for XIAO/ESP32 CameraWebServer.

    The factory-style camera server uses port 80 for the control page and /capture,
    and port 81 for the MJPEG /stream endpoint. A fully custom stream URL is left
    alone when it has a non-default path/port.
    """
    raw = (value or "").strip()
    if not raw:
        return "", "", ""
    if '://' not in raw:
        raw = 'http://' + raw
    u = urlparse(raw)
    if not u.hostname:
        raise ValueError('Invalid camera address')
    scheme = u.scheme or 'http'
    host = u.hostname
    host_fmt = f'[{host}]' if ':' in host and not host.startswith('[') else host
    # Preserve explicit credentials only if they were supplied (normally none).
    auth = ''
    if u.username:
        auth = u.username
        if u.password:
            auth += ':' + u.password
        auth += '@'

    path = u.path or '/'
    explicit_port = u.port
    factory_like = path in ('', '/', '/stream', '/capture') and explicit_port in (None, 80, 81)
    if factory_like:
        control = f'{scheme}://{auth}{host_fmt}'
        stream = f'{scheme}://{auth}{host_fmt}:81/stream'
        snapshot = f'{scheme}://{auth}{host_fmt}/capture'
        return control, stream, snapshot

    # Custom URL: use it as the stream and derive only a best-effort control host.
    stream = urlunparse(u)
    control_netloc = f'{auth}{host_fmt}' + (f':{explicit_port}' if explicit_port else '')
    control = urlunparse((scheme, control_netloc, '/', '', '', ''))
    snapshot = ''
    return control, stream, snapshot


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    print("\nMG400 Grid Website")
    print("------------------")
    print("Host PC:   http://localhost:8765")
    print(f"LAN:       http://{local_ip()}:8765")
    print(f"Robot:     {config.get('robot_ip')}")
    print(f"Safe Z:    {config.get('safe_z')} mm")
    print("Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=8765, debug=False, threaded=True)
