# Object Recognition

**English** | [中文](./README.zh.md)

> **Scope**: object_perception module design source-of-truth (YOLO26n ONNX + ORT TensorRT EP FP16 + HSV color) | **Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception | **Capability claim source-of-truth**: [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `object.cup`
> **Capability grade evidence (final fact)**: [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (object.cup = 🟢 pass **only at ~1m close-range, cup-only**; caveats override this page's narrative)
> **Maintained sub-files**: `CLAUDE.md` (working rules) | `AGENT.md` (topic interface contract) | `research/` (research-only, not source-of-truth)
> **What this page is NOT**: it is not the adjudication of capability pass/fail (see baseline-evidence). ⚠️ **On 6/04 the trusted measurement covered only `object.cup` (~1m close-range)** — although the code supports COCO 80 class + 12 colors, **80 classes / generic detection / object-finding / VLM / reliable color / stable at 2m have all NOT been measured by a trusted baseline and must not be claimed**.

> YOLO26n ONNX + ORT TensorRT EP. The code supports COCO 80 class, but the **6/18 capability claim is narrowly locked to `object.cup` ~1m close-range** (config can hard-lock `class_whitelist=[41,999]`).

## Capability Card (canonical 8 fields → link to claim matrix, do not repeat the full prose on this page)

> See the full 8-field prose at [claim matrix `object.cup`](../../../mission/2026-06-18-capability-claim-matrix.md#objectcup). This table is for quick reference.

| Field | Value |
|---|---|
| **Current Claim** | At ~1m close-range, with a single-color cup on a table in a controlled placement, reliably recognizes the "cup" class; config hard-locks cup-only |
| **Claim Level** | CLAIM_WITH_CAVEAT |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (5/5 positive @1m, conf 0.83–0.88, idle 0 false triggers, n=7) |
| **Pass/Degraded/Fail/Insufficient** | 🟢 pass (narrow close-range version) — no samples at 2m, distance=manual_declared, latency p90≈4.9s |
| **Fallback** | If distance increases / latency is awkward → lock to ~1m, do not say "real-time", switch to "I see there's an item on the table" |
| **Non-Claims** | Generic object recognition / 80 classes / "stable at 2m too" / "real-time / very fast" / floor water-cup reminders (trip-hazard guardian language) / treating the LLM's spoken "I see a cup" as perception evidence / using objects to trigger robot-dog movement / reliable color / object-finding / VLM |
| **Model Candidates** | BASELINE_NOW (YOLO26n TRT FP16, currently the active narrow version passes, do not switch) |
| **Next Retest** | Multi-distance 1 / 1.5 / 2m, 5 samples each + D435 depth distance measurement; re-run across lighting / cold-start TRT |

> **Color / 80 classes / Chinese labels**: the following sections describe **code capability**, **not a trusted-baseline-verified capability claim**. On 6/04, color accuracy and multi-class recall were not measured — the demo/slides must not claim "reliable color recognition" or "generic 80-class detection".

## Status Card

> **Status card caveat (converged 6/04)**: the table below's 5/6 "Brain full-chain works" is a **development-period on-device observation**, **not the 6/04 trusted baseline**. The only trusted capability is `object.cup` ~1m close-range (🟢 pass narrow version). Color / 80 classes / 32-class TTS are code capabilities, **not quantitatively verified**.

| Item | Value |
|------|---|
| Status | **object.cup ~1m close-range = 🟢 pass narrow version (6/04 trusted)**; color/80 classes are code capabilities, not a claim |
| Version/Decision | YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16 (do not install ultralytics) |
| Completeness | 85% (module development progress, not a capability pass — see caveat above)|
| Last Verified | 2026-05-06 (chair brown/black, cup gray, person cyan — full chain observed triggering brain `object_remark` → zh TTS)|
| Model File | Jetson: `/home/jetson/models/yolo26n.onnx` (size to be measured) |
| TRT Cache | `/home/jetson/trt_cache/` (first startup 3-10 minutes, then seconds to start) |
| Package | `object_perception/` (ROS2 Python, entry: `object_perception_node`) |

## Core Flow

```
D435 RGB (/camera/camera/color/image_raw)
    ↓
object_perception_node（YOLO26n ONNX, ORT TensorRT EP FP16）
    ├→ /event/object_detected（JSON: objects[] 陣列，per-class cooldown 5s）
    └→ /perception/object/debug_image（bbox overlay, Foxglove 可視化）
    ↓
interaction_executive_node（物體辨識結果 → TTS 回報）[待整合]
```

## Event Schema

```json
{
  "stamp": 1775371004.13,
  "event_type": "object_detected",
  "objects": [
    {"class_name": "chair", "confidence": 0.878, "bbox": [336, 240, 462, 474]}
  ]
}
```

- Multiple objects may be detected each tick, all unified in the `objects` array
- `bbox`: Python int `[x1, y1, x2, y2]` pixel coordinates (after inverse letterbox)
- `class_name`: see the P0 class table below
- Per-class cooldown 5s: continuous detection of the same class does not re-emit events

## Measured Resources

### 4/4 Phase B (all four cores running, stress test)
| Metric | Value |
|------|---|
| FPS | 15.0 stable (zero dropped frames over 70 seconds) |
| RAM increment | +1GB (3667/7620 MB) |
| GPU | 0% (TensorRT EP) |
| Temperature | 56°C |
| Power | 8.9W |

### 4/5 Phase C (ROS2 node running standalone for 5 minutes, stability)
| Metric | Value |
|------|---|
| Debug image Hz | 6.3-6.8 Hz (publish_fps=8.0) |
| Event publishing | Correct (per-class cooldown 5s in effect) |
| RAM | 2312 → 2319 MB (+7MB, no leak) |
| Temperature | 48°C (held steady, slightly down) |
| Node process CPU | 38.5% |
| ONNX providers | TensorRT + CUDA + CPU |

## Model Comparison (yolo26n vs yolov8n vs yolo26s)

> **Status**: to be measured. The table below only lists the **comparison dimensions and current roles**; concrete numbers such as mAP / FPS / model size will be filled in **only after the 5/12 demo** (benchmarks are only meaningful under our own Jetson + class_whitelist conditions; quoting the full 80-class numbers from the upstream README would be misleading).

| Model | Role | Comparison Dimensions |
|---|---|---|
| **yolo26n** | **Mainline** (verified on-device for the 5/12 demo) | To be measured: mAP / size / Jetson FP16 FPS / small-object detection rate |
| yolov8n | MOC §5 comparison candidate; currently not on-device | Same as above; entering the mainline requires an A/B first |
| yolo26s | Upgrade candidate (post-demo) | Same as above; MOC mentions improved small-object handling, needs verification |

> MOC §5 says "comparison of yolo26n and yolov8n object recognition effectiveness" — the 5/12 demo will not do a full A/B (insufficient time), keep it as a post-demo evaluation item. **yolo26n is already the on-device-verified mainline**, do not switch.
> Real numbers will be filled into the benchmark reports in the [`research/`](./research/) sub-folder; cite the source before updating this table.

## HSV Color Detection (5/6 upgrade to 12 colors)

> MOC §5: "must be able to detect color".
> Code: `object_perception/object_perception/object_perception_node.py::analyze_bbox_color` (module-level, unit-testable; the class staticmethod delegates to it)
> History: 5/5 landed 4 colors (commit `4f638ae`) → 5/6 upgraded to 12 colors (commit `d9fef2d`)

### Algorithm (per-pixel classification, take the mode)

```
YOLO bbox → crop ROI → cv2.cvtColor(BGR→HSV)
  → 12 個互斥 mask（V/S 守門優先於 hue band）
  → peak mask pixels / total pixels = ratio
  → ratio < 0.25 視為「太碎」回 "Unknown"
```

### 12-Color Classification

| Priority | Label | Rule (OpenCV: H 0-180, S/V 0-255)|
|:---:|:---:|---|
| 1 | black | V < 50 |
| 2 | white | S < 40 AND V ≥ 200 |
| 3 | gray | S < 40 AND 50 ≤ V < 200 |
| 4 | brown | warm hue 5-25 AND V < 130 (chromatic & dark)|
| 5 | pink | (red side H ≥ 160 OR ≤ 5 + S < 150 + V ≥ 180) OR magenta band 150-165 |
| 6 | red | H ≤ 8 OR ≥ 165 (not brown / pink)|
| 7 | orange | 8 < H ≤ 22 |
| 8 | yellow | 22 < H ≤ 35 |
| 9 | green | 35 < H ≤ 85 |
| 10 | cyan | 85 < H ≤ 100 |
| 11 | blue | 100 < H ≤ 130 |
| 12 | purple | 130 < H ≤ 150 |

**Why brown / pink go through V/S first, not just hue**: brown's hue is in the orange/yellow band but V is low; pink is on the red or magenta side but usually has lower S and higher V. Simply widening the hue band would classify a coffee-brown chair as yellow / red.

### Event-Writing Rules

Saturation too low or ratio < 0.25 → do not write `color` / `color_confidence` (the frontend treats it as colorless).

Example (coffee-brown chair):
```json
{
  "objects": [
    {"class_name": "chair", "confidence": 0.51, "bbox": [..],
     "color": "brown", "color_confidence": 0.367}
  ]
}
```

### Chinese Display + TTS Rendering

- Three zh dicts (perception node `coco_classes.py:COLOR_ZH` / brain `OBJECT_COLOR_ZH` / frontend `object-config.ts:COLOR_ZH`) — mutually independent to avoid ROS2 cross-package imports; the keep-in-sync note is marked at the top of each file
- `紅 / 橘 / 黃 / 綠 / 青 / 藍 / 紫 / 粉紅 / 咖啡 / 黑 / 白 / 灰`
- Studio object panel `live-detection.tsx` renders: "咖啡色 椅子" (COLOR_ZH + getLabel(class_name))
- Brain `build_object_tts(class_name, color)` produces: `看到{COLOR_ZH}的{class_zh}了` + optional personality suffix

### 80-Class Chinese + zh Rendering (debug overlay)

`object_perception_node._publish_debug_image` switched to PIL CJK rendering starting 5/6 (cv2.putText does not support Chinese), reading `coco_classes.COCO_CLASSES_ZH` to display 80-class Chinese labels; the font is loaded from `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`, falling back to ASCII if there is no CJK font.

## Scene 6 `object_remark` Integration (5/12 Sprint)

### Trigger Conditions

```
/event/object_detected: { class_name: "cup", color: "red", confidence: ≥0.35 }  # 6/9 b1f5058: launch 預設 0.5→0.35（原 0.5 靜默蓋 yaml 害近距 cup 不出）
    ↓
brain_node 規則 `object_remark` 命中（class ∈ {cup, bottle, ...} + color 非空）
    ├─ class_name == "person" → return None（5/7 night demo silence，避開 face/stranger 路徑衝突；Studio chip 仍可見）
    └─ (class, color) 60s 內已講過 → return None（5/7 night `OBJECT_REMARK_DEDUP_S = 60.0`，YOLO 持續偵測同一張椅子不重發）
    ↓
SkillPlan(object_remark) → say_template 渲染 `{class}` + `{color}`
    ↓
TTS：「咦，你拿著紅色的杯子！」
```

### 5/7 Night Demo Silence (commits `685c97d` + `e1363c8`)

Two tightening rules complement SkillContract.cooldown_s=5:

| Rule | Why | Implementation Location |
|---|---|---|
| `class_name == "person"` stays silent | YOLO detecting person collides with the face stranger_alert / greet_known_person paths, causing a chain of "I see a black person" / "detected an unknown person" shouts | `brain_node.py:build_object_tts()` returns None directly |
| Per-(class, color) 60s self-deduplication | `SkillContract.cooldown_s=5` only blocks the SAY skill, not brain_node re-emitting on the same chair every 5s; continuous YOLO detection would shout constantly | `brain_node.py._on_object()` adds an `_object_remark_seen[(class, color)]` dict + 60s window |

Verification: the 5/7 night smoke "I see a coffee-brown chair" only repeats after 60s; person detection is completely silent; the Studio object panel still shows the bbox.

### Event Schema Extension (from 5/5)

```json
{
  "event_type": "object_detected",
  "objects": [
    {
      "class_name": "cup",
      "confidence": 0.878,
      "bbox": [336, 240, 462, 474],
      "color": "red",          // 新增（HSV 結果，可為 null）
      "color_confidence": 0.72  // 新增
    }
  ]
}
```

> Schema changes must be synced to `docs/contracts/interaction_contract.md` v2.6 (contract version bump). This README describes it first; cross-link when the contract version is bumped.

### Personalized Reply Examples (passed to brain, rewritten by the LLM)

| class | color | TTS (demo baseline examples)|
|---|:---:|---|
| cup | red | 「咦，你拿著紅色的杯子！」 |
| cup | blue | 「藍杯子，看起來很涼」 |
| bottle | red | 「紅瓶子，喝點水吧」 |
| bottle | green | 「綠色瓶子是茶嗎？」 |
| other | * | LLM dynamically generated |

## Detection Classes — COCO 80 class (all enabled by default)

Since v0.2 (2026-04-05), the node detects the **complete COCO 80 classes** by default. The full class ID → name mapping is in `object_perception/object_perception/coco_classes.py`.

### Class whitelist (optional reduction)

The ROS2 parameter `class_whitelist` controls this:
- `[]` (default) — all 80 classes enabled
- `[0, 16, 39, 41, 56, 60]` — reduced to the original P0 6 classes

Override at launch:
```bash
ros2 launch object_perception object_perception.launch.py \
  class_whitelist:='[0, 16, 39, 41, 56, 60]'
```

Or edit `config/object_perception.yaml`.

### Common P0 subset (Demo target)

| Class | COCO ID | Name | Purpose |
|-------|:-------:|------|------|
| person | 0 | `person` | Person detection |
| dog | 16 | `dog` | Project theme |
| bottle | 39 | `bottle` | Small-object showcase |
| cup | 41 | `cup` | Small-object showcase |
| chair | 56 | `chair` | Environment understanding |
| dining table | 60 | `dining_table` | Environment understanding |

### Naming Convention

COCO original names containing spaces are uniformly changed to underscores (JSON consistency):
- `dining table` → `dining_table`
- `cell phone` → `cell_phone`
- `traffic light` → `traffic_light`
- `teddy bear` → `teddy_bear`
- and so on (15 names originally contained spaces)

## Deployment Path

**Do not install ultralytics on the Jetson** (it would overwrite the Jetson torch wheel — already hit this pitfall on 4/4).

1. Export with ultralytics on WSL: `yolo26n.pt` → `yolo26n.onnx` (`format='onnx', imgsz=640, simplify=True, opset=17`)
2. scp to the Jetson `/home/jetson/models/`
3. On the Jetson, load directly with `onnxruntime-gpu` (already present), TensorRT EP + FP16

YOLO26n is NMS-free, output shape `(1, 300, 6)` = `[x1, y1, x2, y2, conf, class_id]`, post-processing only needs a threshold filter.

## How to Launch

```bash
# Jetson 上（需 D435 先跑）
ros2 launch realsense2_camera rs_launch.py enable_depth:=false pointcloud.enable:=false
# 另一個 window
source install/setup.zsh
ros2 launch object_perception object_perception.launch.py
```

**TRT parameter pitfall**: the values of `trt_engine_cache_enable` and `trt_fp16_enable` must be the strings `"True"`/`"False"`, not `"1"`/`"0"`, otherwise it will fall back to CPU.

## Brain Integration (5/6 rewrite, replacing the 5/5 state_machine path)

The actual production path goes through `interaction_executive/brain_node.py:_on_object` → `build_object_tts` → `object_remark` skill, and does **not** go through `state_machine.py:OBJECT_TTS_MAP` (the latter is no longer on the actual wire).

### TTS whitelist (~32 class)

Only speaks for common household objects; the other 48 classes (frisbee, traffic light, snowboard, etc.) still display in the UI, but brain stays silent:

```
cup, bottle, book, person, dog, cat, chair, couch, bed, dining_table,
tv, laptop, cell_phone, remote, keyboard, mouse, backpack, handbag,
umbrella, clock, vase, potted_plant, teddy_bear, scissors, wine_glass,
fork, knife, spoon, bowl, banana, apple, orange
```

### Template: colour preamble + optional personality suffix

```python
# 標準格式：「看到 {COLOR_ZH 顏色} 的 {class_zh}」
build_object_tts("cup", "red")     == "看到紅色的杯子了，你要喝水嗎？"   # special suffix
build_object_tts("laptop", "blue") == "看到藍色的筆電了"                # no suffix
build_object_tts("chair", "brown") == "看到咖啡色的椅子了"
build_object_tts("cup", "Unknown") == "看到杯子了，你要喝水嗎？"        # 無顏色
build_object_tts("frisbee", "red") is None                            # 不在 whitelist
```

`OBJECT_TTS_SPECIAL_SUFFIX` has personality phrases for only cup / bottle / book (5/6 user feedback: the suffix is appended after the colour preamble, not a replacement).

### Behavioral Constraints

- Cooldown 5s (in brain `_emit_with_cooldown`)
- Accepts both payload formats: production `{"objects": [...]}` and legacy flat `{"label", "color"}`
- Only triggers when not in an active sequence (gated by brain `_has_active_sequence`)

### Deprecated Path

`interaction_executive/state_machine.py:OBJECT_TTS_MAP` (5/5 design, English templates for the three classes cup / bottle / book) — still in the file but not wired; do not modify it when adding new classes.

## Measured Results (4/6 on-device verification)

| Item | Result | Notes |
|------|:----:|------|
| cup | ✅ | threshold 0.5, triggers TTS "do you want some water?" |
| cell phone | ✅ | recognizable under adequate lighting |
| book | ⚠️ | difficult when lying flat, recognizable when opened for display (occasionally detected at threshold 0.3) |
| bottle | ❌ | not detected, not shown in the demo |

## Known Issues

- **Small objects are nearly impossible to recognize under insufficient lighting** — the demo must have the lights on
- Objects must be at a certain height and facing the camera angle to be detected
- YOLO26n is the Nano version (low small-object detection rate, model size to be measured)
- Flat objects lying down are hard to recognize (book, phone lying flat)
- **Jetson power instability**: 8+ cumulative power losses
- Tracking, 3D depth, and target selection are not done

## Next Steps

- [x] **B4-4 HSV color detection** (5/5 commit `4f638ae` landed 4 colors; 5/6 commit `d9fef2d` upgraded to 12 colors + brown / pink / black-gray-white)
- [x] **Scene 6 `object_remark` integration** (5/6 commit `545cd33` brain pipeline, real-machine observation of chair brown / chair black triggering zh TTS)
- [x] **Event schema bumped to v2.5** (5/6 commit `545cd33` added color / color_confidence; commit `d9fef2d` upgraded to the 12-color enum)
- [ ] **Small-object detection distance issue**: `input_size` 640 → 960 A/B (YOLO26n was trained at 640, tuning to 960 does not guarantee improvement; needs dual-axis verification of mAP + Jetson FPS)
- [ ] Indoor dataset advancement (post-demo): MOC §5 mentions "the dataset currently uses coco, consider using more indoor data" — for the 5/12 demo, COCO 80 + 12 colour is enough; evaluate OpenImages / Objects365 finetune post-demo
- [ ] yolo26s upgrade evaluation (mAP / size / Jetson FPS / small-object detection rate all to be measured)
- [ ] Improve recognition rate of flat objects lying down (book, phone) (lighting + angle + threshold tuning)

## Sub-folders

| Folder | Content |
|--------|------|
| research/ | Object recognition feasibility research (YOLO26n evaluation) |
