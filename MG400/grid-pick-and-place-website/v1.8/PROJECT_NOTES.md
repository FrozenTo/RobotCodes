# v1.8 package notes

Run information and version changes are documented in this folder's `README.md`.

- Main server: `server.py` (Flask, requests, OpenCV).
- Calibration and robot setup: `config.json` (kept untouched).
- Grid cell configuration: `data/cells.json` (kept untouched).
- Frontend: `templates/index.html`, `static/app.js`, `static/style.css`.
- Launch script: `START_WEBSITE.bat`.

The previous v1.6 desktop upload contained **only** a configuration file. It was preserved separately to avoid accidentally replacing the v1.8 live calibration with older values.
