# MG400 drawing experiments

Drawing prototypes: `mg400_image_drawer.py`, `mg400_image_drawer_safe_test.py`, `mg400_image_drawer_ik_safe.py`, `mg400_image_drawer_continuous.py`, `mg400_image_drawer_narva.py`, plus `mg400_svg_drawer.py`.

- These are **different experimental snapshots**, not guaranteed drop-in upgrades. They include work on pen offsets, inverse kinematics, R compensation, and drawing paths.
- `mg400_writer.py` is an unchanged extra copy of the original writer core because drawing scripts use `from mg400_writer import MG400Writer`.
- `alternate-upload-copies/` preserves duplicate/alternate uploads from the former loose-files folder; a few differ slightly in content.
- The SVG drawer has an absolute `SVG_FILE` path from the old PC. Change it to your current SVG path before running.

Source organization only: robot reachability and motion safety have not been tested.
