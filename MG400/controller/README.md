# MG400 keyboard and gamepad controller

The folder contains keyboard tests, gamepad/joint prototypes, `ControllerAPP.py`, `FinalControllerAPP.py`, the extensionless `KeyboardApp` script, and `dobot_api.py`.

The controller apps import `dobot_api` from this same directory. `FinalControllerAPP.py` is the named final GUI, but the most recent working version has **not** been verified on hardware.

Likely dependencies include `pygame`, `PySide6` and for keyboard input `pynput`. Historical compiled bytecode is under `archive-compiled/`.
