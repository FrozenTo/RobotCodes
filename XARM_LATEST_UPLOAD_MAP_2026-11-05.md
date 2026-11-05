# Latest xArm ready-routing upload — SHA-preserved organization (2026-11-05)

Five files were uploaded to the root of `FrozenTo/RobotCodes`. All are xArm **full marker-drawing application** revisions. This map records their project-organized locations; **originals remain intact at the root**.

| Original root path | Organized project path | Verification |
| --- | --- | --- |
| [`xarm_850_full_app_l3_routing_v2.py`](xarm_850_full_app_l3_routing_v2.py) | [`xarm_850_full_app_l3_routing_v2.py`](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/xarm_850_full_app_l3_routing_v2.py) | **Identical Git blob SHA** |
| [`xarm_850_full_app_l1_ready_r3_handoff.py`](xarm_850_full_app_l1_ready_r3_handoff.py) | [`xarm_850_full_app_l1_ready_r3_handoff.py`](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/xarm_850_full_app_l1_ready_r3_handoff.py) | **Identical Git blob SHA** |
| [`xarm_850_full_app_unified_safe_ready.py`](xarm_850_full_app_unified_safe_ready.py) | [`xarm_850_full_app_unified_safe_ready.py`](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/xarm_850_full_app_unified_safe_ready.py) | **Identical Git blob SHA** |
| [`xarm_850_full_app_safe_ready_heading_fix.py`](xarm_850_full_app_safe_ready_heading_fix.py) | [`xarm_850_full_app_safe_ready_heading_fix.py`](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/xarm_850_full_app_safe_ready_heading_fix.py) | **Identical Git blob SHA** |
| [`xarm_850_full_app_settings.json`](xarm_850_full_app_settings.json) | [`xarm_850_full_app_settings.json`](xArm850/combined-controller-and-drawer/full-marker-app/ready-routing-revisions/xarm_850_full_app_settings.json) | **Identical Git blob SHA** |

The four original Python files and the original JSON have **not been edited or recalibrated**. The earlier full-app JSON uses `contact_offset=-19.17`, while this later upload uses **`contact_offset=-12.3`**. The author confirms **−12.3 mm** was calibrated to touch the A3 wall paper correctly on this marker/rack setup; confusing the two versions could cause excessive pressure. Preserve both distinct JSON files.

The folder README explains L3 routing, L1 Go to READY, the unified READY wrist configuration and the heading-positioning correction. No physical test was conducted during this organization.
