# xArm 850 — Shared LAN drawing editor

This is a **local website hosted by a PC**. Students draw using an ordinary
browser on other computers. Clicking **Save as new drawing** stores JSON files
**on your server PC**, under `drawings/`. Students can add their names. Everyone visiting the site can browse,
open, and download saved drawings.

No browser computer needs Python, VS Code, or robot drivers.

## Quick start on the HOST PC

1. Install regular Python 3.9+ (with "Add Python to PATH" on Windows).
2. Extract this entire folder on the host PC.
3. Open Command Prompt or VS Code Terminal in this folder.
4. On Windows, **double-click `START_WEBSITE.bat`**, or run `py server.py`
   in your terminal. On macOS/Linux, run `python server.py`.
5. The terminal prints URLs, for example:
   - Host PC: `http://localhost:8765`
   - Other computers on the same reachable network: `http://192.168.1.42:8765`
6. Leave the terminal running while others use the website.
7. Stop with **Ctrl+C**. All saved drawings remain in `drawings/`.

**No `pip install` required for the website server.** Only Python standard
library is used. HTML, CSS, and JavaScript are provided locally.

## Windows firewall and school Wi-Fi

If Windows Defender Firewall prompts you on first run, grant the Python
application access on **Private networks only** (if permitted by IT).
The two devices must be able to communicate across the network. School/university
networks sometimes prevent connections between student computers or isolate
Wi-Fi clients. You may need to ask IT for permission or use a dedicated trusted
LAN. To discover the correct address, run `ipconfig` on the host and find its
IPv4 Address. Do not confuse the **host PC IP** with the **robot IP**.

The server listens on port **8765** by default. Example with another port:
`py server.py --port 8888`

## Optional access code

`py server.py --password` (or double-click `START_WITH_ACCESS_CODE.bat` on Windows)

The terminal prompts for a shared password (not visible while typing). The
browser asks visitors for the code. **Important:** This uses HTTP Basic
authentication on unencrypted HTTP and must not be considered secure against
traffic interception. Use it only on a **trusted local network**, never expose
this server to the Internet or forward your router ports to it. The gallery is
collaborative: visitors can edit existing saved drawings; no per-user accounts
or permissions exist yet.

## Robot workflow

The website DOES NOT control the xArm robot. It stores editable vector strokes.

On the robot-control PC:
1. Open the website in a browser.
2. Find a saved drawing in the gallery and click **Download JSON**.
3. Open the standalone **xarm850_freehand_drawer.py** desktop app.
4. Click **Load drawing** and select the downloaded JSON.
5. Check pen calibration, **Show planned XYZ path**, do an **AIR TEST**, and only
   then consider pen contact. Physical E-stop must remain accessible.

The downloaded JSON remains the backward-compatible `xarm850-freehand-v1` format.
New drawings add a Fiorello marker palette ID and a color ID on each stroke:

```json
{
  "format": "xarm850-freehand-v1",
  "palette": "fiorello-sketch-12-v1",
  "width_mm": 360,
  "height_mm": 235,
  "strokes": [
    {
      "shape": "line",
      "color": "red",
      "points": [[20, 20], [120, 100]]
    }
  ]
}
```

The website offers 12 fixed Fiorello Sketch marker choices: Brown, Magenta, Red,
Pink, Orange, Yellow, Bright green, Dark green, Light blue, Dark blue, Purple,
and Black. Older JSON files without a `color` field still import normally and
are treated as Black.

The website defaults to **360 × 235 mm** and a **12 mm** safe margin, matching
the working xArm wall-drawing project. Paper configuration can be changed at
server launch (`--width-mm`, `--height-mm`, `--margin-mm`) but the standalone
robot app must have corresponding settings and calibration. Changing presets
later can make older drawings incompatible unless imported and rescaled.

## Practical notes

- The pen tool captures centerline strokes. No PNG tracing or edge detection.
- Color is stored per stroke using a stable marker color ID, so the future robot app can group paths by physical marker.
- Eraser removes the whole nearest stroke, not individual pixels.
- Everyone can see everyone's drawings in the gallery.
- An editor refreshes the gallery automatically every 25 seconds.
- Revision checking prevents overwriting someone else's newer changes. You can
  still select **Save as new drawing** to preserve your copy.
- Server data is saved as separate `.json` files in the `drawings` directory.
  Back up that directory occasionally.
- If the host computer sleeps, shuts down, loses network access, or the server
  terminal closes, the site is unavailable until restarted. Drawings remain on disk.
- Do not use this as a public cloud service: it has no HTTPS, user accounts,
  quotas, anti-abuse protection or public-Internet security hardening.
