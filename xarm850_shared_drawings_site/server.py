"""Shared, LAN-only-by-deployment xArm 850 drawing editor.

Run on the HOST PC:
    python server.py
Optionally require a simple HTTP Basic access code:
    python server.py --password

Students use http://HOST_PC_IP:8765/ in their browsers. Drawings are stored
in ./drawings/ in xarm850-freehand-v1 format, accepted by the Tkinter robot app.

Do not expose to the public Internet. HTTP is unencrypted; the optional shared
password is only a deterrent to casual use on a trusted LAN, not strong security.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hmac
import json
import math
import os
import re
import socket
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "drawings"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_BODY = 2_000_000
MAX_STROKES = 1500
MAX_POINTS_PER_STROKE = 2000
MAX_TOTAL_POINTS = 100_000
MAX_NAME = 90

MARKER_PALETTE_ID = "fiorello-sketch-12-v1"
DEFAULT_MARKER_COLOR = "black"
MARKER_COLORS = [
    {"id": "brown",        "name": "Brown",        "hex": "#8B5A2B"},
    {"id": "magenta",      "name": "Magenta",      "hex": "#D81B60"},
    {"id": "red",          "name": "Red",          "hex": "#E53935"},
    {"id": "pink",         "name": "Pink",         "hex": "#F06292"},
    {"id": "orange",       "name": "Orange",       "hex": "#FB8C00"},
    {"id": "yellow",       "name": "Yellow",       "hex": "#FDD835"},
    {"id": "bright_green", "name": "Bright green", "hex": "#7CB342"},
    {"id": "dark_green",   "name": "Dark green",   "hex": "#1B5E20"},
    {"id": "light_blue",   "name": "Light blue",   "hex": "#29B6F6"},
    {"id": "dark_blue",    "name": "Dark blue",    "hex": "#1565C0"},
    {"id": "purple",       "name": "Purple",       "hex": "#7E57C2"},
    {"id": "black",        "name": "Black",        "hex": "#1E293B"},
]
MARKER_COLOR_IDS = {item["id"] for item in MARKER_COLORS}


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_payload(data, width, height, margin):
    """Validate all user-supplied geometry, before writing into the shared folder."""
    if not isinstance(data, dict) or data.get("format") != "xarm850-freehand-v1":
        raise ValueError("Expected an xarm850-freehand-v1 drawing")
    name = data.get("name", "Untitled drawing")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
        raise ValueError("Name is required (up to 90 characters)")
    name = name.strip()
    author = data.get("author", "")
    if not isinstance(author, str) or len(author.strip()) > 60:
        raise ValueError("Creator name must be 60 characters or fewer")
    author = author.strip()
    if not isinstance(data.get("strokes"), list) or len(data["strokes"]) > MAX_STROKES:
        raise ValueError(f"Drawing exceeds {MAX_STROKES} strokes")
    sw, sh = data.get("width_mm"), data.get("height_mm")
    if type(sw) not in (int, float) or type(sh) not in (int, float):
        raise ValueError("Missing numeric paper size")
    if not (math.isfinite(sw) and math.isfinite(sh)):
        raise ValueError("Non-finite paper size")
    if abs(sw - width) > 0.001 or abs(sh - height) > 0.001:
        raise ValueError(f"Drawing must use the {width:g} × {height:g} mm paper preset")
    clean_strokes = []
    total = 0
    for i, stroke in enumerate(data["strokes"]):
        if not isinstance(stroke, dict) or stroke.get("shape") not in ("pen", "line", "rectangle", "ellipse"):
            raise ValueError(f"Stroke {i+1} has unknown tool")
        points = stroke.get("points")
        if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS_PER_STROKE:
            raise ValueError(f"Stroke {i+1} has invalid number of points")
        total += len(points)
        if total > MAX_TOTAL_POINTS:
            raise ValueError("Too many drawing points")
        clean_points = []
        for point in points:
            if (not isinstance(point, (list, tuple)) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
                raise ValueError(f"Stroke {i+1} has invalid coordinates")
            x, y = point
            if not (margin - .001 <= x <= width - margin + .001 and
                    margin - .001 <= y <= height - margin + .001):
                raise ValueError(f"Stroke {i+1} crosses the {margin:g} mm paper margin")
            clean_points.append([round(x, 3), round(y, 3)])
        color = stroke.get("color", DEFAULT_MARKER_COLOR)
        if not isinstance(color, str) or color not in MARKER_COLOR_IDS:
            raise ValueError(f"Stroke {i+1} has unknown marker color")
        clean_strokes.append({"shape": stroke["shape"], "color": color, "points": clean_points})
    return {"format": "xarm850-freehand-v1", "palette": MARKER_PALETTE_ID,
            "name": name, "author": author, "width_mm": width,
            "height_mm": height, "strokes": clean_strokes}


def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".drawing-", suffix=".tmp", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_drawing(drawing_id):
    if not ID_RE.fullmatch(drawing_id):
        return None
    path = DATA_DIR / (drawing_id + ".json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_drawings():
    rows = []
    with LOCK:
        for path in DATA_DIR.glob("*.json"):
            if not ID_RE.fullmatch(path.stem):
                continue
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
                strokes = d.get("strokes", [])
                used_colors = sorted({
                    s.get("color", DEFAULT_MARKER_COLOR)
                    for s in strokes if isinstance(s, dict)
                })
                rows.append({"id": path.stem, "name": d.get("name", "Untitled"),
                             "strokes": len(strokes), "colors": used_colors,
                             "author": d.get("author", ""),
                             "updated_at": d.get("updated_at", ""),
                             "revision": d.get("revision", 1)})
            except (OSError, json.JSONDecodeError, AttributeError, TypeError):
                continue
    return sorted(rows, key=lambda r: r["updated_at"], reverse=True)


def network_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 1))
            return sock.getsockname()[0]
    except OSError:
        return "YOUR_PC_IP"


def make_handler(settings, password):
    width, height, margin = settings

    class Handler(BaseHTTPRequestHandler):
        server_version = "xArmDrawingLAN/1.0"

        def log_message(self, fmt, *args):
            print(f"[{self.log_date_time_string()}] {self.client_address[0]} — {fmt % args}")

        def send_bytes(self, payload, status=200, content_type="application/json; charset=utf-8", filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, obj, status=200):
            self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"), status)

        def fail(self, message, status=400):
            self.send_json({"error": message}, status)

        def authenticated(self):
            if password is None:
                return True
            header = self.headers.get("Authorization", "")
            if header.startswith("Basic "):
                try:
                    decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
                    if ":" in decoded and hmac.compare_digest(decoded.split(":", 1)[1], password):
                        return True
                except (ValueError, UnicodeDecodeError):
                    pass
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Shared xArm drawings", charset="UTF-8"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False

        def request_data(self):
            raw_length = self.headers.get("Content-Length", "")
            if not raw_length.isdecimal():
                raise ValueError("Missing request size")
            length = int(raw_length)
            if not 0 < length <= MAX_BODY:
                raise ValueError("Drawing request too large")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self):
            if not self.authenticated():
                return
            path = urlsplit(self.path).path
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/styles.css": ("styles.css", "text/css; charset=utf-8")}
            if path in files:
                filename, content_type = files[path]
                try:
                    self.send_bytes((HERE / filename).read_bytes(), content_type=content_type)
                except OSError:
                    self.fail("Site files missing", 500)
            elif path == "/api/config":
                self.send_json({
                    "width_mm": width,
                    "height_mm": height,
                    "margin_mm": margin,
                    "palette": MARKER_PALETTE_ID,
                    "default_color": DEFAULT_MARKER_COLOR,
                    "marker_colors": MARKER_COLORS,
                })
            elif path == "/api/drawings":
                self.send_json({"drawings": list_drawings()})
            else:
                match = re.fullmatch(r"/api/drawings/([0-9a-f]{32})(/download)?", path)
                if not match:
                    self.fail("Not found", 404)
                    return
                with LOCK:
                    drawing = read_drawing(match.group(1))
                if drawing is None:
                    self.fail("Drawing not found", 404)
                elif match.group(2):
                    # Same file schema used by the standalone xArm app.
                    exported = {k: drawing[k] for k in ("format", "width_mm", "height_mm", "strokes")}
                    exported["palette"] = drawing.get("palette", MARKER_PALETTE_ID)
                    self.send_bytes(json.dumps(exported, ensure_ascii=False, indent=2).encode("utf-8"),
                                    content_type="application/json; charset=utf-8", filename="xarm_drawing.json")
                else:
                    self.send_json(drawing)

        def do_POST(self):
            if not self.authenticated():
                return
            if urlsplit(self.path).path != "/api/drawings":
                self.fail("Not found", 404)
                return
            try:
                data = validate_payload(self.request_data(), width, height, margin)
                drawing_id = uuid.uuid4().hex
                now = now_utc()
                data.update({"id": drawing_id, "revision": 1, "created_at": now, "updated_at": now})
                with LOCK:
                    atomic_write(DATA_DIR / (drawing_id + ".json"), data)
                self.send_json({"id": drawing_id, "revision": 1, "updated_at": now}, 201)
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as ex:
                self.fail(str(ex), 400)
            except OSError:
                self.fail("Could not save; check folder permissions or disk space", 500)

        def do_PUT(self):
            if not self.authenticated():
                return
            match = re.fullmatch(r"/api/drawings/([0-9a-f]{32})", urlsplit(self.path).path)
            if not match:
                self.fail("Not found", 404)
                return
            try:
                incoming = self.request_data()
                if not isinstance(incoming, dict) or type(incoming.get("revision")) is not int:
                    raise ValueError("Missing drawing revision")
                data = validate_payload(incoming, width, height, margin)
                with LOCK:
                    old = read_drawing(match.group(1))
                    if old is None:
                        self.fail("Drawing not found", 404)
                        return
                    if incoming["revision"] != old["revision"]:
                        self.fail("Another person saved this drawing; reload it or save as a new copy", 409)
                        return
                    revision = old["revision"] + 1
                    now = now_utc()
                    data.update({"id": match.group(1), "revision": revision,
                                 "created_at": old["created_at"], "updated_at": now})
                    atomic_write(DATA_DIR / (match.group(1) + ".json"), data)
                self.send_json({"id": match.group(1), "revision": revision, "updated_at": now})
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as ex:
                self.fail(str(ex), 400)
            except OSError:
                self.fail("Could not save; check folder permissions or disk space", 500)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Host a shared drawing editor for xArm 850 on your LAN")
    parser.add_argument("--host", default="0.0.0.0", help="Listen address; default allows LAN clients")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--width-mm", type=float, default=360.0)
    parser.add_argument("--height-mm", type=float, default=235.0)
    parser.add_argument("--margin-mm", type=float, default=12.0)
    parser.add_argument("--password", action="store_true", help="Prompt for a shared access code")
    args = parser.parse_args()
    if not (100 <= args.width_mm <= 700 and 100 <= args.height_mm <= 600 and
            8 <= args.margin_mm < min(args.width_mm, args.height_mm) / 2 and
            all(math.isfinite(v) for v in (args.width_mm, args.height_mm, args.margin_mm))):
        parser.error("Invalid paper size or margin")
    password = getpass.getpass("Shared access code (characters hidden): ") if args.password else None
    if password == "":
        parser.error("Access code cannot be empty")
    with ThreadingHTTPServer((args.host, args.port), make_handler(
        (args.width_mm, args.height_mm, args.margin_mm), password)) as httpd:
        httpd.daemon_threads = True
        print("\nShared xArm drawing editor running")
        print(f"Local computer: http://localhost:{args.port}")
        print(f"Other PCs (same accessible network): http://{network_ip()}:{args.port}")
        print(f"Drawing files: {DATA_DIR}")
        print("Press Ctrl+C to stop. No robot is controlled by this web server.\n")
        try:
            httpd.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
