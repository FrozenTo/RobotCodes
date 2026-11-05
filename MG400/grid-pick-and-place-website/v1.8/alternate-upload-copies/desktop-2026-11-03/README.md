
## v1.8 change
- Full AtomS3R now has separate measured heights:
  - pickup: **Z -122.92 mm**
  - press/place: **Z -125.52 mm**
- The deeper place value is intentional to apply a small seating/press force.
- Global assembly R remains **-50.18°** for now; the newly observed R -26.13° is not forced until orientation is confirmed as intentional.

# MG400 Grid Website v1.8

## New in v1.7
- Added measured AtomS3R assembly height presets:
  - Glass only: **Z -150.21 mm**
  - Atom + glass: **Z -140.59 mm**
  - Full AtomS3R: **Z -122.92 mm**
  - Measured assembly orientation: **R -50.18°** (stored as a preset; not forced on ordinary grid motion yet).
- Added station-role field per grid cell (glass input, Atom station, battery/lower-module station, finished output, reject).
- Added buttons to copy any measured assembly height into the selected cell's Pick Z or Place Z.
- All previous v1.5 features remain, including XIAO tool camera and host-PC USB table camera.

# MG400 Grid Website — v1.2

Local Flask website for moving a Dobot MG400 between the centres of the Gridfinity cells in the current 10 × 5 working area.

## Current grid convention

From the operator's viewpoint, facing the robot:

- columns `A ... J`: left → right
- rows `1 ... 5`: farthest from robot → nearest robot
- exact pitch: `42 mm`
- blocked/unreachable: `A1`, `B1`, `I1`, `J1`
- `C1 ... H1` usable
- rows `2 ... 5` initially usable

The first ideal grid fit is based on the measured points from the current rig:

- `grid_x_row1 = 401.19125`
- `grid_y_colA = -191.1925`
- `X = grid_x_row1 - 42 * (row - 1)`
- `Y = grid_y_colA + 42 * column_index`, with A=0 ... J=9

The model deliberately assumes a perfect square grid. If the physical robot/table angle later produces a meaningful error, add a calibration transform instead of changing the 42 mm grid pitch.

## Robot connection

Current default robot IP: `192.168.1.6`

- dashboard port: `29999`
- motion port: `30003`
- Tool 1 / DO1: blow
- Tool 2 / DO2: suction

This app **always controls the real MG400**. There is no simulation or `LIVE_ROBOT` switch.

The Settings panel contains an editable Robot IP and a **Test connection** button. The test checks both TCP ports. It also tries `GetPose()`, but a one-off empty pose reply is only shown as a warning if both ports are reachable.

## Speed

Default speed factor: **20%**.

The server sends `SpeedFactor(20)` after Enable and re-applies the configured speed factor immediately before every `MovJ`/`MovL`. This prevents a reconnect, reboot, or another controller from silently leaving the MG400 at 100% speed.

## Safe Z

Default safe travel height: `Z = -100 mm`.

Every cross-grid movement follows this pattern:

1. lift vertically to safe Z at the current XY;
2. move to the destination XY at safe Z;
3. only then lower vertically to the configured pick/place Z.

Pick and place heights are not pre-filled because different fixtures can have different heights. Pick/Place/Transfer refuses to run if its required Z is not configured.

## Pose reads

`GetPose()` is retried when the MG400 dashboard briefly returns an empty response. During movement completion checks, transient empty pose reads are ignored until the movement timeout rather than turning an otherwise successful movement into an immediate false failure.

## XIAO ESP32S3 Sense camera

The website contains a camera panel for the tool-mounted XIAO ESP32S3 Sense. Enter its camera control-page address in Settings. For the factory hotspot firmware this is normally `http://192.168.4.1`. The website automatically maps that to the MJPEG stream at `http://192.168.4.1:81/stream` and the still-image endpoint at `http://192.168.4.1/capture`.

The Flask server proxies the stream through `/camera/stream`, so browser clients only need the MG400 website address.

The crosshair is visual only in this version. Later it can be calibrated to the suction-cup centre for vision-assisted XY correction.

## Run

Install regular Python 3.9+.

```bash
py -m pip install -r requirements.txt
py server.py
```

Or on Windows double-click `START_WEBSITE.bat`.

The terminal prints URLs similar to:

- host PC: `http://localhost:8765`
- other PCs on the same LAN: `http://<host-ip>:8765`

Leave the terminal running while using the site. Stop with `Ctrl+C`.

## Files

- `server.py` — Flask server, MG400 connection, movement logic and camera proxy
- `config.json` — robot/grid/camera settings
- `data/cells.json` — per-cell labels, blocked state, pick Z and place Z
- `templates/index.html` — web page
- `static/style.css` — interface styling
- `static/app.js` — browser logic

## Safety / behavior notes

- The server serializes robot jobs so two browser requests cannot intentionally run movement sequences at the same time.
- The server does not auto-enable the MG400 at startup.
- `STOP` is a software stop, not a replacement for the physical emergency stop.
- Keep the physical E-stop accessible during testing.
- Test central cells with **Move above** before configuring lower pick/place heights.
- Verify `Z = -100` clears every installed fixture before full transfers.
- XY is generated mathematically from the ideal grid; heights are independent per cell.
- The current R is preserved during grid movement rather than forcing an unverified tool angle.


## Camera note (v1.4)
The web page loads the XIAO MJPEG stream directly from `http://192.168.4.1:81/stream` when the configured camera address is `http://192.168.4.1`. The Flask server no longer proxies the live stream. The **Test camera** button requests a single `http://192.168.4.1/capture` image instead. If the XIAO control page is already streaming, close that page or press **Stop Stream** before using the MG400 website.


## v1.5 — second camera

The page now contains two camera panes:

- **Tool camera:** XIAO ESP32S3 Sense over its Wi-Fi hotspot (`192.168.4.1`).
- **Table camera:** ordinary USB webcam connected to the same Windows PC that runs `server.py`. The host captures it with OpenCV and serves a local MJPEG stream.

For the USB camera, start with camera index `0`. If that selects the laptop's built-in camera, try `1`, then `2`, using **Test USB camera** after each change. Default preview target is 1280×720 at 15 FPS.


## v1.7 change
Assembly height preset buttons now save directly to the selected cell, immediately enabling Pick/Place. Manually typed heights still require **Save cell**.
