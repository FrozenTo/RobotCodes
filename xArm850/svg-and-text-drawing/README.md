# xArm SVG and text drawing

- `xarm_wall_drawer_app.py` and `xarm_wall_drawer_app_v2.py`: GUI iterations for wall SVG/text drawing.
- `xarm_svg_drawer.py`, `xarm_svg_drawer_8point.py`, and `xarm_hello_narva_then_svg.py`: earlier standalone SVG drawing progression, including 8-point paper calibration and writing a greeting before SVG drawing.
- `drawing.svg`: **Narva College linework manually traced in Inkscape by the project author**. This is **byte-identical** to the source added under [`MG400/image-and-svg-drawing/drawing.svg`](../../MG400/image-and-svg-drawing/drawing.svg). The original hand-coded building geometry attempts were not usable, but the SVG worked very well on MG400 and was reused for the xArm drawing work. Standalone scripts and the GUI typically default to a same-folder `drawing.svg` when no other file is selected.
- `reference-images/`: screenshots of drawing settings.

The files were brought together to preserve same-folder SVG lookup. Verify measured paper corners, contact X and robot-ready pose before running.

## Project provenance

The artwork originated as the **successful MG400 drawing** after earlier attempts to reconstruct a detailed building illustration as hard-coded paths from a PNG proved inaccurate. The xArm/UF850 drawing code explicitly describes adopting the SVG parsing approach from MG400 and mapping the paper differently (horizontal plane on MG400 versus a vertical wall plane on xArm). This establishes a shared **artwork and parser concept**, **not** shared robot motion or calibration coordinates.

The SVG's exact content was verified against the author's newly re-uploaded file. **No xArm or MG400 robot execution was performed as part of this Git review.**

## Additional SVG source variants recovered (2026-11-04)

The full original `Even more robot apps` folder also contained copies of `xarm_svg_drawer.py`, `xarm_svg_drawer_8point.py`, and `xarm_hello_narva_then_svg.py` that **do not have the same Git content hashes as the previously organized desktop versions**. They are now preserved **unchanged** in [`alternate-upload-copies/recovered-2026-11-04/`](alternate-upload-copies/recovered-2026-11-04/), instead of overwriting the main files. The recovered upload also contains separate [five-point calibration development](../combined-controller-and-drawer/five-point-development/) and the later [full marker app](../combined-controller-and-drawer/full-marker-app/); the SVG scripts in this folder retain their four-/eight-point history.
