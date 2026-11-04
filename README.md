# RobotCodes

A collection of **Dobot MG400** and **UFACTORY xArm 850 / UF850** projects.

The repository was organized on 2026-11-03 by robot and project, expanded with 26 desktop-uploaded files, and **recovered a further 33 previously omitted paths** on 2026-11-04 after the complete 74-file `Even more robot apps` folder was re-uploaded. The 41 original paths from that folder matched the first snapshot exactly. Of the 33 previously omitted paths, six were already identical to other organized files and 27 contained newly recovered file data. All robot code/settings/SVG/JSON files were copied by unchanged Git blob SHA; no source code was edited during recovery.

- [MG400](MG400/) — text writing, vector/image drawing, pen calibration, controller testing, slider control, and grid pick-and-place assembly.
- [xArm850](xArm850/) — wall text writing, SVG drawing, freehand drawing, controllers, motion tests, Mister Bean demo, and LAN drawing website.
- [DESKTOP_UPLOAD_MAP.md](DESKTOP_UPLOAD_MAP.md) — relocation map for the 26 desktop files.
- [RECOVERED_UPLOAD_MAP_2026-11-04.md](RECOVERED_UPLOAD_MAP_2026-11-04.md) — SHA-verified mapping for 33 files missed by the original 100-file upload.
- [FILE_MAP.md](FILE_MAP.md) — relocation map for the initial 100-file upload.

## Important usage notes

1. Keep a program's local helper scripts and JSON settings together. The MG400 drawing and calibration projects each include an **unchanged copy** of `mg400_writer.py` because their scripts import it from the same directory.
2. `alternate-upload-copies/` contains preserved uploads from the former `Even more robot apps/` folder. **Do not assume all are byte-identical or that the largest-numbered version is safe.**
3. Existing `__pycache__` files were kept in `archive-compiled/` for archival completeness, not because they are required to run Python source.
4. The xArm freehand packages contain different calibration settings. They are intentionally not merged. The safe-ready package has no settings JSON in the original upload.
5. The xArm combined v3 app loads **`xarm_combined_settings.json`**, not `xarm850_freehand_settings.json`. It falls back to built-in defaults if the file is absent and writes combined settings when saved; do not rename or merge freehand calibration JSON blindly. The earlier combined settings file is preserved beside v1/v2.
6. The shared xArm drawing website now includes the server, launch scripts, CSS, and two saved drawing JSON files recovered from the desktop. It remains a LAN-only web editor, not robot control software.
7. Robot IP addresses, coordinate calibration, tool offsets, and safe heights reflect historical experiments; verify all before running a physical robot.

An untouched snapshot of the original file layout is preserved on branch `backup/original-layout-2026-11-03`, in addition to Git commit history.

The desktop upload snapshot before this second reorganization is preserved on branch `backup/before-desktop-organization-2026-11-03`.

## Review scope

The current project-by-project review starts with [MG400 pen writing](MG400/pen-writing/). The [MG400 grid pick-and-place website](MG400/grid-pick-and-place-website/) is a **separate lesson/course project** and is intentionally excluded from the personal robot-code review for now; its uploaded files remain preserved and organized.

## Upload completeness audit (2026-11-04)

The original 100-file upload captured 59 files from other source folders and only 41 of 74 from `Even more robot apps`. The latter 74-file folder has now been re-uploaded intact and preserved at the repository root for independent verification. Its 33 previously omitted paths are documented in the recovery map. The four later full-marker-app versions, five-point calibration tests, marker rack/pickup experiments and preserved settings are now indexed under `xArm850/`. The original 41 match their re-uploaded SHA values, and no tracked originals were deleted by reorganization. File counts include duplicates and historical binary caches; they do not signify distinct working applications.
