# RobotCodes — Final Repository Integrity and Navigation Audit

**Audit date:** 2026-11-05  
**Scope:** Tracked files currently in [RobotCodes](README.md), plus the two historical GitHub snapshot commits. This verifies **repository contents and links**, not unuploaded local PC folders, runtime imports from Windows installations, GitHub-side issue attachments or physical robot behavior.

## Repository inventory after this documentation update

| Item | Count / conclusion |
| --- | --- |
| Tracked Git files / blobs by path | **269** (266 before this audit, plus this report and two preserved historical README originals) |
| Python `.py` paths | **155**, representing **85 different Git blob contents** |
| Additional Python paths with duplicate contents | **70** — intentional archived uploads and local project copies, not evidence of 70 distinct new programs |
| MG400 tracked paths | **67** (including preserved original lesson README below) |
| xArm850 tracked paths | **117** (including preserved original Mister Bean README below) |
| Raw `Even more robot apps/` tracked paths | **74**, preserved in original upload layout |
| Root-level tracked paths | **11** (including the new audit report) |
| Primary project folders with README | **15/15** — 6 MG400 and 9 xArm850 |

The raw upload includes code of **both robots**; the 33 *initially omitted* entries happened to be xArm-related. File counts are **paths**, not distinct applications or unique releases. The archived `__pycache__` entries are history, not required source.

## README link audit

All **32 Markdown documents present before this audit** were read and their ordinary relative Markdown links checked against Git-tracked paths:

- **254 relative links** to files/folders were checked.
- **0 broken relative target paths** were found.
- 9 external URLs were excluded from the target existence check.
- Markdown fragment-only anchors, HTML-only links, runtime import references and external website health were not tested by this checker.

The updated root README, this audit report and map notes were also checked for valid relative targets before merging.

## Historical upload and SHA comparisons

| Map | Entries | Same Git SHA at original map destination | Exceptions |
| --- | ---: | ---: | --- |
| [Initial 100-file map](FILE_MAP.md) | **100** | **98** | Two **actively updated README** files; Python/data entries preserved |
| [26-file desktop map](DESKTOP_UPLOAD_MAP.md) | **26** | **25** | One **actively updated README** file |
| [Recovered 33-file map](RECOVERED_UPLOAD_MAP_2026-11-04.md) | **33** | **33** | None |
| [Latest five-file xArm map](XARM_LATEST_UPLOAD_MAP_2026-11-05.md) | **5** | **5** | None |

**The three exceptions are deliberate documentation edits, not missing robot code:**

1. Initial-map `Even more robot apps/xarm850_shared_drawing_website_colors/xarm850_shared_drawings_site/README.md` → active `xArm850/shared-drawing-website/README.md`. The original SHA is preserved at [`alternate-upload-copies/desktop-2026-11-03/README.md`](xArm850/shared-drawing-website/alternate-upload-copies/desktop-2026-11-03/README.md) and in the raw 74-file folder; the active README gained a full source review.
2. Initial-map `xArm app/Xarm demo/README_Mister_Bean_Demo.md` → active `xArm850/mister-bean-demo/README_Mister_Bean_Demo.md`. The original SHA is now also preserved at [`alternate-upload-copies/original-2026-11-03/README_Mister_Bean_Demo.md`](xArm850/mister-bean-demo/alternate-upload-copies/original-2026-11-03/README_Mister_Bean_Demo.md); the active file now documents the author-confirmed physical demo success and correct **−8.55 mm** original source offset.
3. Desktop-map `mg400_grid_website_v18/README.md` → active `MG400/grid-pick-and-place-website/v1.8/README.md`. Its original SHA is now preserved at [`alternate-upload-copies/desktop-2026-11-03/README.md`](MG400/grid-pick-and-place-website/v1.8/alternate-upload-copies/desktop-2026-11-03/README.md); the active README was expanded with actual lesson context.

The first 100-file snapshot retained only **41** of the intended **74** `Even more robot apps` paths, alongside **59** files from other folders. Re-upload recovered **33** absent paths; **6** blobs were already elsewhere and **27** were newly archived content. The complete re-uploaded 74-file folder matched all the original 41 hashes, and all 33 recovered paths have unchanged organized copies. The subsequent five later xArm files matched their root copies exactly **before the root duplicates were removed**. The original root versions remain verifiable by comparing the pre-cleanup Git commit against the current organized destinations.

## Backup and duplicate preservation

- [First snapshot (100 files)](https://github.com/FrozenTo/RobotCodes/tree/228505cc98f67b9763884a343112d4a156ddf6a3): branch `backup/original-layout-2026-11-03`.
- [Before desktop organization (145 files)](https://github.com/FrozenTo/RobotCodes/tree/a5fc63477cf3fca7d861f8b1d802694f9dbc8956): branch `backup/before-desktop-organization-2026-11-03`.
- The [complete raw source folder](Even%20more%20robot%20apps/) remains on `main`. The **five latest xArm full-app root copies were removed from `main` on 2026-11-06** after verifying exact organized duplicates. The initial root uploads can still be viewed at [the pre-cleanup Git commit](https://github.com/FrozenTo/RobotCodes/tree/0134014726d9448b5afc9d1f69d85f94779cd855); the current copies are all in [READY-routing revisions](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/).
- Original variants under `alternate-upload-copies/` may have **different data** despite identical filenames; comparing only filenames is insufficient.
- No duplicate robot code is deleted by this audit; preserving development stages is intentional.

## Outcomes and limitations

**Confirmed from file audit:** project indexes exist, ordinary Markdown relative links resolve, source-to-copy hash checks pass except documented revised README destinations, and the tracked Git backups still exist.

**Not established by this audit:** completeness of **unuploaded local files**, which historical version was last run where multiple similar copies exist, whether runtime environment packages or user-specific absolute file paths are currently valid, or safety of physical robot motion.

**Documentation-only update:** this audit adds two historical README copies and updates Markdown. It does **not** change Python code, calibration JSONs, SVG drawings, motion waypoints, tool offsets or speed constants.


## Subsequent root cleanup (2026-11-06)

At the author's request, the **four newest full-app Python files and one settings JSON** were kept in [their properly organized folder](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/) and the five redundant copies removed **only from the repository root**. The previous root-copy audit values above are a historical snapshot of **2026-11-05**, not current file totals.

| Measure | 2026-11-05 audit | After 2026-11-06 cleanup |
| --- | ---: | ---: |
| Tracked file paths | **269** | **264** |
| Root-level files | **11** | **6** (README, audit and four upload maps) |
| Python file paths | **155** | **151** |
| Distinct Python blob contents | **85** | **85** |
| Python paths repeating existing content | **70** | **66** |
| xArm850 project files | **117** | **117** (unchanged) |
| MG400 project files | **67** | **67** (unchanged) |
| Raw `Even more robot apps/` files | **74** | **74** (unchanged) |

The [five-file upload map](XARM_LATEST_UPLOAD_MAP_2026-11-05.md) now links to **historical root paths pinned to the earlier Git commit** and the **current organized paths**, rather than producing broken root links. All five organized files have the same exact Git blob SHA as their deleted root counterparts; the latest settings JSON remains next to the scripts, preserving **−12.3 mm** calibration. **No source or calibration content was changed.**
