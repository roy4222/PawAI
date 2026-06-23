# Face Recognition

**English** | [中文](./README.zh.md)

> **Scope**: face_perception module design source-of-truth (YuNet + SFace + IOU tracker) | **Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception | **Capability claim source-of-truth**: [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `face.recognition` (any "can we claim it, which layer does it belong to" defers to this page)
> **Capability grade evidence (final fact)**: [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (face = 🟢 pass, narrow version; caveats override the narrative on this page)
> **Maintained sub-files**: `CLAUDE.md` (work rules) | `AGENT.md` (topic interface contract) | `research/` (research-only, not source-of-truth)
> **What this page is NOT**: not the adjudication of capability pass/fail (see baseline-evidence); not the measurement protocol (see [`specs/2026-06-18-capability-baseline-spec.md`](../../specs/2026-06-18-capability-baseline-spec.md)); does not cover stranger rejection / guardian / "never misidentifies a person".

> YuNet detection + SFace recognition + IOU tracking, identifying **registered familiar people** and triggering interaction (narrow version: registered people only).

## Capability Card (canonical 8 fields → link to claim matrix, don't duplicate the full prose on this page)

> See the full 8-field prose in [claim matrix `face.recognition`](../../../mission/2026-06-18-capability-claim-matrix.md#facerecognition). This table is a quick reference.

| Field | Value |
|---|---|
| **Current Claim** | The 6/04 trusted measurement got a pass for "registered Roy" at ~1.5–2.4m, demonstrating recognizing a registered person and greeting them (narrow version) |
| **Claim Level** | CLAIM_WITH_CAVEAT |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (n=9, registered_recall=1.0, unknown_false_accept=0.0, p50≈74ms) |
| **Pass/Degraded/Fail/Insufficient** | 🟢 pass (narrow version) — single registered person only, single lighting, lowest positive conf 0.2378, idle=empty scene |
| **Fallback** | track jitter / name flicker → fall back to a generic "saw someone approaching and said hello" or only show `debug_image` to prove the pipeline |
| **Non-Claims** | stranger rejection / guardian / stranger alert / "never misidentifies a person" / identity verification / access-control-grade confirmation / reliable at 2m+ / general face recognition |
| **Model Candidates** | BASELINE_NOW (YuNet + SFace, in-service pass, no swap) |
| **Next Retest** | #81 clean rerun: ≥2 registered people + multiple lighting conditions, real stranger samples, conf moving off the 0.24 boundary, retest after long full-stack runtime |

## Status Card

> **Status card caveat (converged 6/04)**: the "completion 95%" in the table below is module development progress, **not capability pass evidence**. Capability evidence defers to the [capability card](#capability-card-canonical-8-fields--link-to-claim-matrix-dont-duplicate-the-full-prose-on-this-page) + baseline-evidence (face = 🟢 pass, narrow version: registered familiar people only / empty-scene idle, **stranger rejection not verified**).

| Item | Value |
|------|---|
| Status | **Registered familiar-person greeting (narrow-version pass)** |
| Version/Decision | YuNet 2023mar (CPU 71.3 FPS) + SFace 2021dec |
| Completion | 95% (module development progress, not capability pass — see caveat above) |
| Last verified | 2026-05-08 (sim_threshold_upper 0.30→0.40 raised the stranger threshold to avoid 60%+ false positives during demo); last full smoke 2026-04-06 (identity_stable 21 times/2min) |
| Entry file | `face_perception/face_perception/face_identity_node.py` |
| Tests | `python3 -m pytest face_perception/test/ -v` |

## How to Launch

```bash
# 一鍵啟動（推薦）
bash scripts/start_face_identity_tmux.sh

# 或手動
ros2 launch face_perception face_perception.launch.py
```

## Core Flow

```
RealSense D435 RGB + Depth
    |
face_identity_node（YuNet 偵測 -> SFace embedding -> IOU 追蹤）
    |
/state/perception/face（10Hz JSON：face_count, tracks[{track_id, stable_name, sim, distance_m, bbox}]）
/event/face_identity（觸發式：track_started / identity_stable / identity_changed / track_lost）
    |
interaction_executive_node 訂閱 -> WELCOME 觸發 -> TTS 問候
```

**Hysteresis stabilization** (two-stage tuning on 4/6 + 5/8):
- 4/6: `sim_threshold_upper`: 0.35 → 0.30, `sim_threshold_lower`: 0.25 → **0.22** (to let known faces be recognized quickly)
- **5/8**: `sim_threshold_upper`: 0.30 → **0.40** (to keep unknowns from firing randomly; demo white-box observation showed 60%+ stranger false triggers came from hands / glass reflections / skin-colored objects. Paired with `unknown_face_accumulate_s`: 3.0 → 5.0 for 2 more seconds of confirmation)
- `track_iou_threshold`: **0.15**, `track_max_misses`: **20**, `stable_hits`: **2**, `unknown_grace_s`: **2.5**
- 2-minute smoke test after 4/6 tuning: `identity_stable: roy` 21 times (1-3 times before tuning), zero misidentifications
- **Known limitation**: track jitter still present (45 tracks/2min, target ≤5), root cause is unstable YuNet detection

**face_db**: `/home/jetson/face_db/`, currently has two people, roy and grama.

## Skill Trigger Mapping (5/12 Sprint Scene 4 + 8)

> **Claim boundary (6/04)**: the `stranger_alert` in the table below is an **internal event routing mechanism**, **not** a verified stranger detection/alert capability. The 6/04 idle only tested an empty scene, **real stranger rejection is not measured** (baseline-evidence honesty caveat). The demo/presentation **must not** claim guardian / stranger alert / "never misidentifies a person" (claim matrix `face.recognition` Non-Claims).

| Event | Brain-triggered Skill | Demo Scene | Notes |
|---|---|---|---|
| `identity_stable` (known face stable ≥2 hits) | `greet_known_person` | Scene 4 familiar-person interaction | LLM dynamic greeting, with `{name}` customization |
| `identity_unknown` (stranger after unknown_grace) | `stranger_alert` | Scene 8 stranger + safety stop | **5/7 night demo silence**: `SkillContract.steps[0].args["text"] = ""`, IE-node SAY returns `empty_tts_text`, `/tts` does not fire. The `/brain/proposal` trace still emits, the Studio chip is still visible. Same pattern as fall_alert b224217 |
| `track_started` / `track_lost` | (no direct skill trigger) | — | Pure state update, interpreted by brain rules |

**`{name}` customization**: the face name is taken from the most recent `identity_stable`'s `stable_name` in `/state/perception/face`, rendered by the LLM bridge with say_template. The same variable is also used in `fallen_alert` in `pose/README.md` ("{name}, a fall was detected, please be careful").

## Registering a New Face (advanced, post-demo)

> The 5/12 demo does not allow on-site registration, only the existing face_db is used. The registration mechanism is marked **advanced**, to be re-evaluated post-demo.

**Manual flow** (dev only):
1. Put 1-3 frontal photos of the target person (256×256+) into `/home/jetson/face_db/<name>/`
2. Restart `face_identity_node`; on startup it automatically reads face_db and recomputes the SFace embedding
3. Walk a few steps in front of the camera to verify the `identity_stable: <name>` trigger

**Not doing right now**:
- ROS service `/face/register` (would expand demo scope)
- Studio upload UI
- Automatic similarity merging (consolidating multiple IDs for one person)

## Input/Output

| Topic | Direction | Description |
|-------|:----:|------|
| `/state/perception/face` | output | Face state 10Hz JSON |
| `/event/face_identity` | output | Identity events (triggered) |
| `/face_identity/debug_image` | output | Debug image ~6.6Hz |

## Model Paths (Jetson)

- YuNet: `/home/jetson/face_models/face_detection_yunet_2023mar.onnx`
- SFace: `/home/jetson/face_models/face_recognition_sface_2021dec.onnx`

## Known Issues

- **Repeated greeting triggers** (confirmed in 4/8 meeting): the same person repeatedly triggers greeting in a short time, no cooldown set yet
- **Low-light misidentification**: occasional wrong names in low-light environments
- **No-person hallucination**: occasionally falsely detects a face when no one is present
- **Multi-person skeleton jumping**: tracking gets confused when multiple people appear at once, cannot distinguish them correctly
- track jitter still present (45 tracks/2min, target ≤5), root cause is unstable YuNet detection
- Model path hardcoded to `/home/jetson/face_models/`
- face_db only has 2 people (roy, grama), the demo may need expansion
- OpenCV version constraint (Jetson 4.5.4)

## Next Steps

- [ ] **5/12 Sprint Scene 4 + 8 on-device verification**: `greet_known_person` stably triggers 3 times each for roy / grama; `stranger_alert` stably triggers 3 times for unknown faces
- [ ] Greeting cooldown (prevent the same person from repeatedly triggering in a short time, a current known issue)
- [ ] Multi-person recognition stabilization (tracks don't jump when multiple people appear at once)
- [ ] Clean Architecture refactor (after the 5/13 demo, see `docs/archive/2026-05-docs-reorg/research-misc/2026-03-25-go2-sdk-capability-and-architecture.md` S5.4)
- [ ] Register-new-face ROS service (advanced, post-demo)

## Subfolders

| Folder | Contents |
|--------|------|
| research/ | Model selection research (YuNet vs ArcFace vs SCRFD) |
| archive/ | Junior-developer task-split guide (3/8, no longer used by anyone) |
