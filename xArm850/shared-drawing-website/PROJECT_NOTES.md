# xArm 850 shared LAN drawing website — recovered desktop package

The initial upload contained only `README.md`, `app.js`, and `index.html`. The later desktop upload supplied **`server.py`, `START_WEBSITE.bat`, `START_WITH_ACCESS_CODE.bat`, `styles.css`, and two `drawings/*.json` files**. These are now alongside the original frontend, forming the server package described in the supplied README.

The three identical frontend files from the desktop copy have been preserved under `alternate-upload-copies/desktop-2026-11-03/` to retain the complete upload provenance. The original `qrcode_docs.google.com.png` is under `reference-assets/`; its relevance is unverified.

The website does not command the robot. Students save `xarm850-freehand-v1` drawing JSON, which is imported separately by a compatible freehand drawing desktop app. The HTTP Basic-password option is unsuitable for exposure to public networks.

**Runtime has not been tested** after relocating the package. Confirm port, firewall and paths when running.
