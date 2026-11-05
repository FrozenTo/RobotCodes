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


---

## Archival source review — 2026-11-05

**Purpose and outcome:** A student-friendly **shared drawing creation site**, not a robot controller. The author previously reported the website working on the local network; a later access problem was traced to using the **wrong host/IP instructions** and resolved after selecting the correct address. This report of use does **not** mean the archived package was freshly executed after reorganization. The earlier [`PROJECT_NOTES.md`](PROJECT_NOTES.md) explicitly records that relocation runtime was not retested.

### What is in this project

| File or folder | Function |
| --- | --- |
| [`server.py`](server.py) | **Python standard-library** `ThreadingHTTPServer`, serves local HTML/CSS/JS, validates JSON, manages gallery, revision checks and disk files |
| [`index.html`](index.html) + [`styles.css`](styles.css) + [`app.js`](app.js) | The full browser UI: pen, line, rectangle, ellipse, erase-stroke, 12-color palette, undo/redo, new/import/download and shared gallery |
| [`START_WEBSITE.bat`](START_WEBSITE.bat) | Windows launcher for the ordinary server on port **8765** |
| [`START_WITH_ACCESS_CODE.bat`](START_WITH_ACCESS_CODE.bat) | Windows launcher that asks for a shared **HTTP Basic** access code |
| [`drawings/`](drawings/) | Saved `xarm850-freehand-v1` vector drawing JSONs, persistent on the host PC |
| [`alternate-upload-copies/desktop-2026-11-03/`](alternate-upload-copies/desktop-2026-11-03/) | Byte-identical copies of the frontend README, HTML and JavaScript, retained for upload history |
| [`reference-assets/`](reference-assets/) | Historical QR-code image; no verified relationship to running the server |

The site contains **no robot TCP commands**, no xArm SDK import and no hardware connection. The operator must explicitly **download/open a drawing in a separate xArm desktop program**, check actual calibrated wall contact and run it there. This distinction is important for student safety and the application architecture.

### Original saved drawings

Two drawings were recovered as part of the desktop package:

| Preserved JSON | Strokes | Total raw points | Color metadata |
| --- | ---: | ---: | --- |
| [`1fa6257c6bb14905b551629d03d779c2.json`](drawings/1fa6257c6bb14905b551629d03d779c2.json) | **77** | **3,481** | Original black-only drawing, no palette metadata |
| [`f35cc988a9254003920c73d7f710f66b.json`](drawings/f35cc988a9254003920c73d7f710f66b.json) | **3** | **85** | Original black-only drawing, no palette metadata |

Both use `xarm850-freehand-v1` at **360 × 235 mm**, revision **1**. These are stored data samples, **not** evidence that either was physically drawn by the robot. Their stroke counts also match drawings recovered independently in [Freehand Drawing](../freehand-drawing/); do not conclude they are identical without a full geometry/content comparison.

### Technical implementation details

- **Canvas:** defaults to a logical **360 × 235 mm**, with a **12 mm margin**. These dimensions are a reachable drawing preset, **not the whole physical A3 sheet**. The current website margin check is rectangular; it does **not** know the later full app's **five-point clipped unreachable top-right polygon**. Robot-side reachability validation remains necessary.
- **Fiorello palette:** 12 named marker colors; per-stroke color IDs persist in JSON. Old black-only strokes are interpreted as black. The website itself **does not** automatically change physical markers.
- **Storage:** `POST /api/drawings` creates an ID-based JSON in `drawings/`; `PUT /api/drawings/<id>` requires a matching integer revision and rejects stale updates with **HTTP 409**. The server uses a thread lock and temporary-file replacement for reliable concurrent saves.
- **Download:** strips site-specific name, author, revision and timestamps, preserving geometry and optional palette to import into a compatible desktop application.
- **Validation:** maximum request **2,000,000 bytes**, **1,500 strokes**, **2,000 points per stroke**, **100,000 points total**; finite numeric coordinates, recognized shapes/color IDs and matching page dimensions/margins are required.
- **Collaboration:** gallery, name and optional author are metadata only; **there is no ownership enforcement or per-user permissions**. Anyone who can access the site can edit another person's drawing. The gallery auto-refreshes about **every 25 seconds**.
- **Port/network:** `--host` defaults to **0.0.0.0**, opening the server to reachable network peers, with port **8765** by default; actual access depends on firewall, Wi-Fi isolation and correct host IPv4 address. **The host PC IP is not the xArm's IP.**

**Security note:** the optional access code is HTTP Basic over **unencrypted HTTP**, not secure encryption. The server is suitable only for a trusted/private LAN; **do not expose it to the public Internet**. There are no user accounts, account-level permissions, deletion controls, HTTPS or robust public-service protections.

### Working status / future integration

The author reported successful local-website use after fixing the IP mismatch. Browser editing and file storage are implemented; direct robot control is intentionally **not implemented**. The newer [full marker applications](../combined-controller-and-drawer/full-marker-app/) can load compatible saved drawing JSON and offer color-related workflows, but they still require separate calibration and supervised operation.

**No Python, JavaScript, HTML, CSS, launch scripts, QR image or JSON drawing data changed during this documentation review.**
