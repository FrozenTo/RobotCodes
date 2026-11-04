# xArm 850 / UF850 — Wall Text Writing

**Robot:** UFACTORY xArm 850 (also called UF850)  
**Project:** Write text with a marker on a **vertical YZ paper/wall plane**, adapting the earlier [MG400 nine-point letter writer](../../MG400/pen-writing/)  
**Outcome:** **Wall writing is author-confirmed working well on the physical xArm**. The author reported that writing was "really well" during development. Which precise archived version was the *last* physically tested build is **not established**; v3 is the most developed **standalone text-writing** pair in this folder.  
**Reviewed:** 2026-11-04

## What changed from MG400?

The letter shapes are again defined by strokes connecting positions on a **3×3 numbered grid**, with additional punctuation and Estonian characters. But the physical drawing plane is different:

- **−X = toward paper**, **+X = away from paper**; X controls marker contact/lift.
- **+Y = writing left-to-right** along the surface.
- **+Z = up** and −Z is down, including advancing to the next text row.

The core script issues position and joint commands using the official **UFACTORY Python SDK** (`xarm.wrapper.XArmAPI`) instead of the MG400's raw TCP command strings.

A key problem was how to bring the much larger arm to the writing area **without forcing an unsafe long straight Cartesian transition**. The author added a **joint-space approach posture**, later a distinct READY position, a safe writing plane, and separate wall contact calibration. This was the major evolution beyond simply copying MG400 letter coordinates.

**Relationship to xArm controller:** This wall-writing pipeline uses planned position/joint movements, **not** the Xbox `vc_set_cartesian_velocity()` loop from the [controller prototypes](../controller-tests/). They become integrated in the [combined controller and drawing project](../combined-controller-and-drawer/).

## Source versions and actual differences

The GUI and core are **paired by import**. Run the corresponding GUI with the matching writer module in the same folder.

| Version / file pair | Functionality | Review interpretation |
| --- | --- | --- |
| **Early legacy**: [`legacy-versions/uf850_wall_writer.py`](legacy-versions/uf850_wall_writer.py) + [legacy GUI](legacy-versions/uf850_wall_writer_app.py) | Fixed wall `wall_x`; single-line text and marker lift; manual XYZ/joint jog; simple fixed writing start and mini-letter grid | Earliest archived pair, useful as a historical baseline |
| **Updated unversioned**: [`uf850_wall_writer.py`](uf850_wall_writer.py) + [GUI](uf850_wall_writer_app.py) | Adds saved **writing joint posture** and two-stage writing-start approach, plus retract-then-`move_gohome()` routine and GUI controls to capture/edit posture | Not identical to the early legacy pair, despite sharing filenames |
| **v2**: [`uf850_wall_writer_v2.py`](uf850_wall_writer_v2.py) + [GUI v2](uf850_wall_writer_app_v2.py) | Four-corner paper calibration, interpolated contact X, separate READY position / safe writing X, paper-corner capture in GUI, calculated starting Z | More realistic compensation for paper that is not at one perfectly constant X |
| **v3**: [`uf850_wall_writer_v3.py`](uf850_wall_writer_v3.py) + [GUI v3](uf850_wall_writer_app_v3.py) | Keeps v2 geometry/approach; adds **multiline text**, row spacing, maximum-row and paper-height checks, editable multiline text box; updated top-left contact coordinate and shorter spaces in main file | Most complete standalone wall-text-writing pair in repository; precise final physical test version not confirmed |

This sequence is inferred from code structure and filenames. **Working wall writing is confirmed**, but no individual hardware verification record is attached to every revision.

### How v2 changed the geometry and approach

The **original** code assumed one effective `wall_x=-405.2` with `clearance=10` mm; its sample start/orientation (`Y=4.6, Z=993.4`, approximately `roll=-0.2, pitch=-1.7, yaw=0.5`) belonged to that early fixture/posture.

In **v2/v3**, the code instead distinguishes:

1. **READY posture / position:** example `ready_x=-391.8`, `ready_y=111.0`, `ready_z=597.7`, with a stored six-joint posture.
2. **Safe writing X:** `safe_x=-480.0`, for traveling with the marker lifted near paper.
3. **Contact X:** `paper_contact_x(y,z)`, interpolated from **all four measured paper-contact corners** (top-left/right and bottom-left/right) to follow the physical surface.

The movement sequence to the first letter is **joint-space to READY → Cartesian X approach to the safe plane → Y/Z move on the safe plane**. This is deliberate automatic routing from an arbitrary current position, not a requirement that the robot must be manually placed at an exact starting pose before every command.

When finishing, the v2/v3 return-to-initial routine retracts the marker away from the paper when needed, moves farther out to READY X, changes to the saved joint posture, then uses the SDK's `move_gohome()`. These are **programmed waypoints**, not a full environmental collision check.

Contact X is interpolated bilinearly in Y/Z between measured edges. Points beyond the measured paper rectangle are **clamped to the nearest edge for contact-X calculation**; that behavior does not make an out-of-bounds Y/Z stroke safe.

### Letter spacing and multiple rows

The core letter geometry remained the familiar **20 mm high × 10 mm wide** mini-letter size (`half_height=10`, `half_width=5`), with default `letter_step=12` mm.

- Older unversioned and v2 versions use `space_step=25` mm.
- The **main v3** uses **`space_step=12` mm**, reflecting the author's request to shorten large gaps.
- v3 adds `row_spacing=30` mm and `max_rows=7`.
- The initial letter center Z is derived as **paper top Z − full letter height**; the first Y can be estimated from the calibrated top-left paper edge plus one letter width.
- Newline characters explicitly start another row: X stays at safe/lifted depth while Y returns to the line start and Z moves down by one row spacing.
- V3 checks the requested number of rows against the configured maximum and the **calculated vertical paper height**.

**Limitation:** the row-fitting logic checks vertical space, not whether a very long line exceeds the **right/left paper boundary**. The GUI doesn't provide general automatic text wrapping. Long text still needs length/clearance checks before live writing.

The Tkinter v3 interface supplies a **multiline text box** (Enter inserts new row; Ctrl+Enter requests writing), row count display, row spacing and maximum-row controls. The older GUIs provide **single-line** text fields.

### Saved duplicates and one meaningful v3 calibration difference

The uploaded folders contain some **byte-identical duplicates**:

- Main `uf850_wall_writer.py` and main `uf850_wall_writer_app.py` equal the matching numbered `(1)` copies in `alternate-upload-copies/`, but **are not** equal to files under `legacy-versions/`.
- Main v2 core/GUI and main v3 GUI equal their counterparts under `alternate-upload-copies/`.
- **Important exception: v3 core**: the archived `alternate-upload-copies/uf850_wall_writer_v3.py` is **not** identical to main `uf850_wall_writer_v3.py`. Exactly **two lines** differ:

| Default setting | Alternate v3 copy | Main v3 |
| --- | --- | --- |
| Paper top-left X | **−497.2 mm** | **−498 mm** |
| Space step | **25 mm** | **12 mm** |

Those are historical **calibration/spacing settings**, not a rewritten motion algorithm. Preserve both files; don't overwrite the main calibrated v3 with the archived copy just because the filenames look interchangeable.

`archive-compiled/` contains historic Python `.pyc` files, not required for normal source execution.

## Current setup in the archived code

**Main v3 settings** (defaults, *not validated for the current robot mounting*):

| Parameter | Recorded default |
| --- | --- |
| Robot IP | `192.168.1.208` |
| Marker orientation (roll, pitch, yaw) | `−179.7°, −3.6°, 179.1°` |
| READY XYZ | `(−391.8, 111.0, 597.7)` mm |
| Safe writing X | **−480 mm** |
| Paper top-left XYZ | `(−498, −74.6, 706)` mm |
| Paper top-right XYZ | `(−493.6, 280.5, 706)` mm |
| Paper bottom-right XYZ | `(−492.5, 279.1, 487)` mm |
| Paper bottom-left XYZ | `(−498.2, −78.8, 487)` mm |
| Travel / contact / joint speed | 20 mm/s / 10 mm/s / 10°/s |
| Letter height × width | 20 × 10 mm |
| Letter step / space step | **12 / 12 mm** |
| Row spacing / maximum rows | **30 mm / 7** |
| `air_draw` | `True` by default — writing does not touch the wall until disabled |

The **Air Draw** checkbox is a deliberate historical testing control. It allows path tests without marker contact. The user's physical success reports necessarily relate to live writing with contact enabled, even though the checked-in default is `True`. As with the MG400 archive, retaining these switches does **not** mean that new production control applications should default to simulation.

**No adjacent JSON settings file** is part of this standalone text-writing folder. The GUI allows editing settings **in memory during a run**; the code does not implement disk-based save/load of the calibrated corners or ready position. Avoid assuming that the source defaults exactly match values from the user's last physical session.

## App capabilities and dependencies

All GUIs use **Tkinter** and import their corresponding `uf850_wall_writer` core. Features across versions include connection and enable controls, reading current TCP/joint angles, six-axis manual joint jogging, XYZ step jogging, marker contact/lift, short test shapes, editable letter size/speed and typed text. The updated unversioned GUI adds capture/edit controls for the special wall-writing joint pose. The later GUIs add physical paper-corner capture and READY controls; v3 adds multiline writing.

The GUIs run long robot actions in **background worker threads** and keep a `motion_busy` flag to prevent overlapping ordinary movements. Software stop is exposed separately and calls the SDK; it is **not** a substitute for the physical E-stop.

To run the standalone v3 GUI on a properly configured, supervised xArm system (historical command):

```bash
python uf850_wall_writer_app_v3.py
```

The official UFACTORY `xarm` Python SDK and a Python installation with Tkinter are required. Keep both `uf850_wall_writer_app_v3.py` and `uf850_wall_writer_v3.py` in the same directory so the imported module resolves correctly.

## Code-review cautions — not reports of physical incidents

1. **Fixture-dependent calibration:** changing the marker, mount, paper/wall or base frame can invalidate the stored orientation, READY posture, contact corners and safe X values. Some coordinates differ **substantially** from the early unversioned configuration.
2. **No full-space collision guarantee:** saved joint and Cartesian waypoints intentionally manage the approach but do not prove the robot links, pen holder, wall and intervening fixtures are clear. Rerun a careful supervised check after any layout change.
3. **Clamped paper model:** contact X is clamped outside the four-corner bounds, but the corresponding Y/Z point is not necessarily rejected. The v3 row count protects the vertical extent only, **not the horizontal width** or writing speed near joint limits.
4. **Thread/process safety:** ordinary GUI motions are serialized with a `motion_busy` flag, but a software stop or window close can occur while a motion worker is active. The Tkinter window is not a certified safety controller.
5. **Air Draw:** shipped defaults are `True`; unticking it causes real contact motions. The source includes no automatic robot-to-paper contact-force feedback.
6. **No persisted GUI calibration:** values entered during one run are not saved by these standalone GUI scripts. Source constants represent an historical starting configuration only.
7. **Software emergency stop:** the GUI invokes an SDK stop command, not a physical emergency-stop circuit; keep the real E-stop accessible.
8. **Status of individual variants:** physical writing is confirmed successful by the author, but no new test was done for these precise GitHub file hashes during the documentation review.

## Catalog conclusion and relationship to other projects

**Recommended classification:** **Wall Text Writing — successful, standalone v3 most complete; original/legacy/v2 retained as developmental history.** The key improvements were **safe joint-space entry**, **four-corner paper contact calibration**, **shorter spacing**, and **multiline layout**, not a new alphabet.

Next: [xArm SVG and Text Drawing](../svg-and-text-drawing/) reuses the manual Narva College SVG from the MG400 project and adds the wall-oriented drawing workflow. Later, the [Combined Controller + Drawer](../combined-controller-and-drawer/) integrates the controller, text and drawing features.

**This review changed only this README.** No Python source, orientation, robot IP, calibrated coordinates or on-robot settings were modified.
