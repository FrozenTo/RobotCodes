# MG400 grid pick-and-place assembly website

The site drives a **Dobot MG400** to pick and place components at grid positions, with per-cell measured Z heights and two camera panels. It is intended for AtomS3R assembly.

- [v1.8](v1.8/): complete uploaded Flask package; `server.py`, `START_WEBSITE.bat`, `requirements.txt`, `config.json`, `data/cells.json`, HTML template and JS/CSS assets.
- [legacy-v1.6-config](legacy-v1.6-config/): **config JSON only**, not a full runnable v1.6 distribution.

The v1.8 README notes separate measured heights for full AtomS3R **pickup** (`-122.92 mm`) and **press/place** (`-125.52 mm`); these values reflect one physical setup and should not be applied automatically to another robot or fixture. The v1.8 `config.json` sets a different speed factor and camera index from v1.6. Neither configuration has been altered.

The server loads `config.json` and `data/cells.json` relative to its own `server.py`, so those files stay in the v1.8 package. Static web assets remain under `static/` and the Flask page under `templates/`.

**Safety:** The software issues live robot commands. Verify IP, reachable grid cells, rotation, tool outputs, safe-Z, recorded pickup/press heights and accessible emergency stop before operation. No robot motion/runtime test was performed during Git organization. Compiled bytecode from the upload is retained under `v1.8/archive-compiled/` only as an archive.
