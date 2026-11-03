# RobotCodes

A collection of **Dobot MG400** and **UFACTORY xArm 850 / UF850** projects.

The original upload was organized on 2026-11-03 by robot and by project. **All 100 original tracked files are preserved without changing their contents**, including historical snapshots, binaries, and JSON data. This reorganization is not a hardware/runtime test.

- [MG400](MG400/) — text writing, vector/image drawing, pen calibration, controller testing, and slider control.
- [xArm850](xArm850/) — wall text writing, SVG drawing, freehand drawing, controllers, motion tests, Mister Bean demo, and LAN drawing website.
- [FILE_MAP.md](FILE_MAP.md) — exact old and new path of every original file.

## Important usage notes

1. Keep a program's local helper scripts and JSON settings together. The MG400 drawing and calibration projects each include an **unchanged copy** of `mg400_writer.py` because their scripts import it from the same directory.
2. `alternate-upload-copies/` contains preserved uploads from the former `Even more robot apps/` folder. **Do not assume all are byte-identical or that the largest-numbered version is safe.**
3. Existing `__pycache__` files were kept in `archive-compiled/` for archival completeness, not because they are required to run Python source.
4. The xArm freehand packages contain different calibration settings. They are intentionally not merged. The safe-ready package has no settings JSON in the original upload.
5. The xArm combined v3 package has no `xarm_combined_settings.json` in its original package; an older settings file is retained beside the v1/v2 scripts only.
6. The shared drawing website upload has `README.md`, `app.js`, and `index.html`, but lacks the `server.py` and BAT launchers mentioned by its README. It may be incomplete.
7. Robot IP addresses, coordinate calibration, tool offsets, and safe heights reflect historical experiments; verify all before running a physical robot.

An untouched snapshot of the original file layout is preserved on branch `backup/original-layout-2026-11-03`, in addition to Git commit history.
