# xArm 850 / UF850 — Freehand Wall Drawing

**Robot:** UFACTORY xArm 850 / UF850, marker on **A3 paper attached vertically to a wall**  
**Project goal:** A Paint-like Tkinter canvas for drawing original vector strokes and shapes, saving and loading them, then translating the strokes into robot movement along the calibrated wall. This is **different from importing an SVG**.  
**Author's outcome:** The author confirmed on **2026-10-21** that the **v2.2 app “works perfectly in my opinion now”**, and approved incorporating that freehand behavior into the later combined xArm v3 application. A preceding physical movement problem involved the robot **“moving into itself”** during a drawing test. The archive does not prove actual physical self-contact or validate every archived version on the robot.  
**Source review:** 2026-11-05; includes the three drawing JSON files recovered during the re-upload.

## Where this project sits in xArm development

The [xArm wall SVG/text drawer](../svg-and-text-drawing/) already converted vector linework into moves on a vertical paper surface. Freehand drawing adds a **mouse-driven drawing editor**:

- Tools: **Pen, Line, Rectangle, Ellipse, Eraser**, plus **Undo / Redo / Clear**.
- Draw on a Tkinter canvas; strokes remain real vector points, **not a rasterized image or PNG outline**.
- **Save** and **load** portable `xarm850-freehand-v1` JSON drawings.
- **Preview** generated XYZ robot waypoints; optionally perform a pen-up **AIR** movement test, then physically **DRAW on paper**.
- Tune marker contact offset and motion speeds; the later versions add READY/Initial controls and safer robot lifecycle handling.
- The robot uses **the official `xarm` Python SDK**, not the MG400 raw socket motion API.

It was a direct precursor to the **[combined controller/drawer v3](../combined-controller-and-drawer/v3-package/)**, which explicitly lists tested **v2.2 freehand behavior** as the source for its Freehand Drawing tab.

## Development versions — what changed

| File | Development stage and noteworthy changes | Status |
| --- | --- | --- |
| [`xarm850_freehand_drawer.py`](xarm850_freehand_drawer.py) | First standalone editor. Eight-point wall interpolation, fixed X retraction **contact X + 25 mm**, drawing JSON, air preview/testing and buffered strokes. Calls a **Cartesian READY XYZ** at the start/end of the planned trajectory; strict limits including offset ±15 mm and mandatory prior AIR run | **Early experiment**, not a confirmed successful physical draw |
| [`xarm850_freehand_drawer (1).py`](xarm850_freehand_drawer%20%281%29.py) | Tightens initial TCP XYZ/orientation checks and tracks app-enabled robot state; still uses the earlier Cartesian READY approach and strict AIR/offset constraints | **Intermediate safety revision**; not a final fix |
| [`safe-ready-package/xarm850_freehand_drawer_safe_ready.py`](safe-ready-package/xarm850_freehand_drawer_safe_ready.py) | Corrective experiment after the unsafe movement report: **joint-space READY pose**, fixed pen-up **X=−480**, READY/gateway checks, G2 collision-model option and same-gateway end of test; requires AIR test and known start configuration | **Not physically tested** according to its bundled 2026-10-21 README |
| [`xarm850_freehand_drawer_v2.py`](xarm850_freehand_drawer_v2.py) | Moves toward the earlier **working combined xArm app workflow**: optional auto joint READY, more permissive AIR/draw, adjustable SAFE_X and offset nudges, enable/disable/recover/initial-position actions. Some upper bounds remain, including **±30 mm** X offset | **Intermediate iteration**; individual physical result not established |
| [`xarm850_freehand_drawer_v2_1.py`](xarm850_freehand_drawer_v2_1.py) | **Only three lines differ from v2**: removes the hard ±30 mm marker X offset rejection so tool lengths such as **−38 mm** can be entered | **Small correction**, not a separate feature rewrite |
| [`v2.2-package/xarm850_freehand_drawer_v2_2.py`](v2.2-package/xarm850_freehand_drawer_v2_2.py) | Restores flexible start-to-stroke workflow, removes unnecessary software caps and forced READY/AIR prerequisites; adds configurable approach speed and path-point spacing, processes long drawings in bounded SDK batches | **Author-confirmed satisfactory version**, integrated next into combined app v3 |

There is **no reason to overwrite** the earlier files: the evolution captures a genuine problem, an intentionally cautious but restrictive response, and a later version that better matched the author's expected workflow.

### The movement problem and its resolution

The author reported during the **October 21, 2026** development discussion that the robot **“moves into itself while trying to go to the drawing test.”** We should record this as a **serious observed movement/near-self-interference concern**, **not** assert that robot links physically collided or that damage occurred.

The early freehand trajectory included a Cartesian move directly to the stored `ready_xyz` pose. The working wall writer/combined controller instead used a **known six-joint READY posture**. Two different joint configurations can correspond to similar TCP Cartesian poses, and commanding a Cartesian transition can produce an unexpected sweep.

The **safe-ready** package addressed this suspected cause by removing the automatic Cartesian READY transition, adding an explicit joint-space READY action and checking whether the robot was near the known joint posture or a previously verified pen-up gateway. Its own [README](safe-ready-package/README_xarm850_safe_ready.txt) explicitly states: **physical movement not tested** (syntax/GUI/interpolation/planning/simulated command sequence were tested).

The later v2/v2.1/v2.2 work moved away from making exact starting poses a normal user prerequisite. **v2.2** instead allows **optional Move to READY (joint move)**; when that is switched off, it starts with pen-up travel from the **current robot pose**. AIR testing is **optional** before drawing. This matches the author's request for a practical application rather than a series of restrictive test gates. It **does not guarantee safe movement from an arbitrary posture**: the operator must confirm the actual arm configuration and obstacle clearance.

After testing and adjustments, the author said v2.2 **“works perfectly in my opinion now.”** The next combined v3 package calls out v2.2 as the freehand implementation to integrate. The exact physical validation of every tool, stroke JSON and possible start position is not separately documented.

### What v2.2 relaxed (and what it retained)

The bundled [v2.2 release notes](v2.2-package/README_xarm850_freehand_v2_2.txt) explicitly record:

- No hard ±30 mm **X contact offset** cap; the operator can enter values such as −38 mm.
- AIR test remains optional, with **no automatic requirement to run it before DRAW**.
- **Move to READY before AIR/DRAW** is optional; OFF means no hidden READY or gateway start-pose gate. Explicit Move READY still sends the joint command.
- No arbitrary software maxima for paper dimensions, draw/travel/approach speeds, acceleration or point simplification; firmware/SDK constraints still apply.
- **Approach speed** and **path point spacing** are configurable; default approach **25 mm/s**, point spacing **3 mm**.
- No previous **2,000 points-per-stroke** or **4,000 strokes-per-file** rejection. It flushes the SDK command queue periodically (typically **every 250 path points**) instead of refusing long strokes.
- The pen-up SAFE_X plane must genuinely be on the **robot side of the contact surface**, not behind it. The extra artificial 7 mm minimum-clearance rule was removed.

Basic validity checks **remain**: positive paper dimensions/speeds/acceleration/path spacing, nonnegative simplification and margin, finite coordinates, strokes within page/margins, a nonempty drawing, and pen-up X that is on the robot side of the intended paper contact.

## Physical wall calibration and marker-contact hazard

All standalone versions here use an **eight-point** wall calibration (`TL, TM, TR, ML, MR, BL, BM, BR`). The original app's saved paper X values differ by around **2 mm** from those in later v2/v2.2 defaults, which are borrowed from the previous combined xArm setup. The v2 code includes a migration rule for **matching old default points**, while attempting to preserve genuinely customized calibration points.

The drawing canvas coordinates (typically **359.6 × 235 mm** in v2.2) describe a **logical calibrated reachable region**, not a claim that every edge of the physical A3 sheet is accessible. Robot Y/Z place the stroke on the paper, while X controls marker depth into/out of the wall.

The author reports that **0.1 mm differences** could matter for marker contact after reinserting a marker into the gripper. Setting X too shallow results in **no mark**; too far inward can **crush the marker against the wall**. The standalone eight-point code has **no automatic force/pressure feedback**. Its `offset_x_mm` is a **marker-contact adjustment**, not a replacement for the measured paper surface.

### Two original settings files — do not mix

There are **two different `xarm850_freehand_settings.json` files** in the repository. Each script resolves `SETTINGS_FILE` **beside itself**; files inside the v2.2 package load that package's JSON, not the top-level JSON.

| Setting | [Main folder JSON](xarm850_freehand_settings.json) | [v2.2 package JSON](v2.2-package/xarm850_freehand_settings.json) |
| --- | --- | --- |
| Logical paper width × height | **360 × 235 mm** | **359.6 × 235 mm** |
| Marker X offset | **−7 mm** | **−36 mm** |
| Pen-up movement | **`lift_x_mm=25`** added to contact X | **`safe_x_mm=−480`** fixed travel plane |
| Draw / travel speed | **25 / 35 mm/s** | **60 / 100 mm/s** |
| Approach speed | Not a separate setting | **40 mm/s** in saved JSON (code default 25) |
| Robot | `192.168.1.208` | `192.168.1.208` |
| Paper points | Older eight measured XYZs | Later eight measured XYZs |
| Auto READY / G2 collision model | Not present | Both **true** in JSON |

These are **historical fixture-specific settings**. `-36` is the saved v2.2 contact offset; **−38** is an example of an offset that the revised validation permits, not a claim that the saved JSON actually contains −38.

The [safe-ready package](safe-ready-package/) has **no saved settings JSON** in its original upload. The script computes its default settings itself and would create/update a local JSON only during use; do **not** silently copy either other package's settings into it.

In the even later [five-point combined app](../combined-controller-and-drawer/five-point-development/) and [full marker-rack app](../combined-controller-and-drawer/full-marker-app/), the paper geometry changed to accommodate the unreachable **upper-right** A3 region. A **3D-printed marker rack with a locating wall** made insertion more repeatable, reducing further manual X recalibration. Those are **later projects**, not functions implemented in these standalone freehand versions. The underlying excessive-pressure hazard still exists.

## Drawing JSONs and compatibility

The app saves **vector drawing data**, not robot coordinates or settings. A typical drawing contains:

```json
{
  "format": "xarm850-freehand-v1",
  "width_mm": 359.6,
  "height_mm": 235.0,
  "strokes": [
    {"shape": "pen", "points": [[30.0, 40.0], [31.0, 41.0]]}
  ]
}
```

Both the standalone freehand app and the later combined drawing application use the **`xarm850-freehand-v1`** format, also used by the [shared drawing website](../shared-drawing-website/). When loading, the standalone app **rescales stored XY coordinates** to its current logical width/height, then validates the selected page margins. A format match alone does not guarantee that every file can be drawn with the currently selected margins and calibration.

| Saved drawing | Strokes | Notes |
| --- | ---: | --- |
| [`my_xarm_drawing.json`](example-drawings/my_xarm_drawing.json) | **19** | Original freehand example |
| [`mister_bean_color_compatible.json`](example-drawings/mister_bean_color_compatible.json) | **40** | Has an extra palette and per-stroke **color** metadata |
| [`xarm_drawing.json`](example-drawings/recovered-2026-11-04/xarm_drawing.json) | **18** | Recovered from omitted upload |
| [`xarm_drawing (2).json`](example-drawings/recovered-2026-11-04/xarm_drawing%20%282%29.json) | **3** | Small recovered test drawing |
| [`xarm_drawing (3).json`](example-drawings/recovered-2026-11-04/xarm_drawing%20%283%29.json) | **77** | Larger, detailed recovered drawing |

**Important compatibility nuance:** the standalone v2.2 loader reads the `shape` and `points` of each stroke and **does not preserve or interpret `color` or `palette`**. It can treat the color-compatible Mister Bean JSON as ordinary paths (subject to dimension/margin checks), but **it does not automatically switch markers or execute colored drawing**. Color/marker automation belongs to separate later work.

The restored JSON files were **copied byte-for-byte** during [PR #16](https://github.com/FrozenTo/RobotCodes/pull/16). No drawing file or settings was edited here.

## Running and dependencies

**Original standalone versions:** ordinary Python with Tkinter, JSON and math. **Robot connection** requires the UFACTORY Python SDK:

```powershell
py -m pip install xarm-python-sdk
```

To launch the **v2.2 historical package**, run in [`v2.2-package/`](v2.2-package/):

```powershell
py xarm850_freehand_drawer_v2_2.py
```

Or use its `START_DRAWER_V2_2.bat` launcher. Drawing/editing JSON works without a connected robot; **Connect, AIR and DRAW** command the real xArm, with explicit connection and action prompts.

**Do not connect an archived app to a robot without checking its actual tool, marker, paper positions, SAFE_X, READY joint path, firmware limits and physical E-stop.** Even a pen-up test can collide with the arm, rack, wall or surrounding furniture. Software STOP and G2 self-collision/tool-model settings are not a certified collision-free guarantee.

## Review status / next project

- **Working outcome:** v2.2 author-approved on 2026-10-21; its freehand features were carried into the later combined v3 app.
- **Observed historical issue:** robot moved into itself during an early drawing-test trajectory; physical contact not proven.
- **Unverified experiment:** the `safe-ready-package` release explicitly says its physical robot behavior was not tested.
- **Calibration:** these standalone versions remain eight-point; they predate the five-point cropped reachable region and the reliable marker rack.
- **Files preserved:** all six Python variants, both original settings JSONs, packaged release notes/launchers and all five drawing JSON files remain unchanged.

**Only this README was updated during the review. No movement code, paper coordinates, tool offsets, speeds, JSON settings or drawing files were altered.**
