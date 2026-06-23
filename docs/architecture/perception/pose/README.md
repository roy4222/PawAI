# Pose Recognition

**English** | [中文](./README.zh.md)

> **Scope**: vision_perception pose subsystem design source-of-truth (MediaPipe Pose + angle/geometry classification) | **Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception | **Capability claim source-of-truth**: [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `pose.basic` / `pose.fall`
> **Capability grade evidence (final fact)**: [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (pose.basic / pose.fall = ⚪ **insufficient_data**, no pose observer; caveats override the narrative on this page)
> **Maintained sub-files**: `CLAUDE.md` (work rules) | `AGENT.md` (topic interface contract) | `research/` (research-only, not source-of-truth)
> **What this page is NOT**: it is not the adjudication of capability pass/fail (see baseline-evidence). ⚠️ **pose.basic = Studio-only / insufficient_data** (no observer on 6/04, not measured); **fall detection (pose.fall) is future, not an emergency behavior**, demo keeps `enable_fallen:=false`. **Do NOT claim that fall detection is reliable / fall-prevention guardianship / emergency alert has passed.**

> MediaPipe Pose recognizes human body poses. **pose.basic was not measured this round (Studio-only); fall detection is future, not an emergency behavior.**

## Capability card (canonical 8 fields → links to claim matrix, do not repeat the full prose on this page)

> For the full 8-field prose, see [claim matrix `pose.basic / pose.fall`](../../../mission/2026-06-18-capability-claim-matrix.md#posebasic--posefall). This table is a quick reference.

| Field | Value |
|---|---|
| **Current Claim** | Pose / fall has a capability chain but was not measured this round; demo does not perform it, covered with an application-scenario video instead |
| **Claim Level** | DO_NOT_CLAIM |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (n=0, no pose observer, fall claim_level=future, `brain_allowed=false`) |
| **Pass/Degraded/Fail/Insufficient** | ⚪ insufficient_data (pose.basic = Studio-only); fall is **future**, not an emergency behavior |
| **Fallback** | When the camera shows the Studio fallen red marker, the narration **never mentions falling**; demo startup keeps `enable_fallen:=false` |
| **Non-Claims** | Reliable fall detection / fall-prevention guardianship / sit-down detection has passed / emergency alert / treating pose observation as a medical judgment |
| **Model Candidates** | FUTURE_RESEARCH (fall); pose.basic awaiting observer construction |
| **Next Retest** | A pose observer tool must be built + HITL ground-truth samples collected before pass can be discussed; fall is future by nature and does not enter the demo |

## Status card

> **Status card caveat (converged 6/04)**: the "5/7 on-device pass" in the table below is a **subjective on-device observation during development (no observer quantification)**, **not the 6/04 trusted baseline**. On 6/04 pose.basic / pose.fall = ⚪ insufficient_data (no pose observer, n=0). Completion is module development progress, not a capability pass. "fallen stable" **does not constitute a fall-detection pass**—fall is future, not an emergency.

| Item | Value |
|------|---|
| Status | **pose.basic = ⚪ Studio-only / insufficient (6/04 trusted)**; fallen = future, not an emergency |
| Version/Decision | MediaPipe Pose (CPU 18.5 FPS) |
| Completion | 90% (module development progress, not a capability pass — see caveat above) |
| Last verified | 6/04 trusted, no pose observer (insufficient_data); 5/7 "on-device pass" is only a subjective development-period observation |
| Entry file | `vision_perception/vision_perception/pose_classifier.py` |
| Tests | `python3 -m pytest vision_perception/test/test_pose_classifier.py -v` |

## How to launch

```bash
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe
```

## Core flow

```
D435 RGB → vision_perception_node
    ↓
MediaPipe Pose（CPU, COCO 17-point）
    ↓
pose_classifier.py（hip/knee/trunk 角度判定）
    ↓
/event/pose_detected（JSON: pose, confidence）
    ↓
interaction_executive_node → fallen = EMERGENCY（內部 routing 標籤）
```

> ⚠️ **"EMERGENCY" is an internal event-routing label, not a verified emergency-guardianship capability.** Fall detection (pose.fall) = future, not an emergency behavior (claim matrix `pose.fall` Non-Claims). The demo keeps `enable_fallen:=false`, and both fallen TTS paths are muted (5/8); **do not publicly claim that fall guardianship / emergency alert has passed.**

## Supported poses (all 7 in the MOC are Active, landed 5/5)

| Pose | Decision logic | Triggered Skill | Line template (demo bridge) | Status |
|------|---------|---|---|:---:|
| standing | hip_angle > 155° + knee_angle > 155° | (default, does not trigger) | — | Active |
| akimbo | standing variant; shoulder/elbow/hip vis ≥ 0.5; both elbows out > hip_width × 0.4; elbow y between shoulder and hip+0.5×hip_width; elbow angle 60-140° when wrist is visible | `akimbo_react` | "You look quite poised!" (tentative) | **Unstable** (5/6) |
| sitting | y-geometry: trunk < 35° + hip_y ≈ knee_y (< 0.12×torso) OR knee_y < hip_y + ankle_y - hip_y > 0.5×torso + knee_angle < 145° | `sit_along` | "Are you tired?" | Active |
| crouching | hip_angle < 145°, knee_angle < 145°, trunk > 10° | (interaction say) | "I'm right here" | Active |
| bending | trunk > 30°, knee_angle > 130°, hip_angle < 160°, bbox ≤ 1.0 | `careful_remind` | "Please be careful" | Active |
| knee_kneel | y difference between the two knees > 0.07×torso; hip/knee/stand_ankle vis ≥ 0.5; kneel ankle hidden OR ankle_y ≈ knee_y (< 0.20×torso) OR kneel angle < 130°; stand angle > 130° OR sitting-like support | `knee_kneel_react` | "Do you need my help?" (tentative) | **Unstable** (5/6) |
| fallen | trunk > 60° AND 0 ≤ vertical_ratio < 0.4 AND torso vis ≥ 0.5; deep-bending guard: skip when the angle between hip→ankle and the downward vertical is < 30° and bbox ≤ 1.0; bbox > 1.0 adds a +0.05 confidence bonus (no longer a hard condition) | `fallen_alert` (EMERGENCY) | "{name}, a fall has been detected, please stay safe!" | Active (can be disabled) |

> **5/6 algorithm upgrade** (commits TBD, based on community-validated rules):
> - `fallen` removes the "bbox_ratio > 1.0 required condition", switching to vertical_ratio as the primary gatekeeper + torso visibility ≥ 0.5 to reject MediaPipe garbage frames (which sometimes label the shoulder below the hip); adds a deep-bending guard to prevent bending-to-touch-the-ground being misjudged as fallen.
> - `sitting` switches to y-geometry (hip≈knee y + ankle clearly lower than hip) instead of the angle method, avoiding overlap with bending / crouching.
> - `akimbo` changes its primary signal to elbow-bowed-out (the wrist-drift pitfall from the community BleedAI / MediaPipe issue #4462), raising the visibility threshold from 0.2 to 0.5.
> - `knee_kneel` adds kneel-side ankle.y ≈ knee.y to distinguish kneel-vs-lunge (community yoga-pose rule); a hidden ankle is treated as a kneel signal.
> - Order: fallen → standing/akimbo → knee_kneel → sitting → crouching → bending → None.
> 26/26 unit tests all green (synthetic); 5/7 actions PASS on-device, akimbo + knee_kneel still need tuning against real MediaPipe data.
> Full plan: `$HOME/.claude/plans/pose-validated-harp.md`.

## Operational limits and known issues

- **Effective range**: within about **4-5m** in front of the D435
- **Single-person tracking only**: with multiple people, MediaPipe tracks only one
- RTMPose balanced mode GPU 91-99% (fallback option, the mainline uses MediaPipe CPU 0%)
- ~~Frontal standing pose misjudged as fallen~~ — **fixed (4/3)**: added a `vertical_ratio` guard, using shoulder-hip vertical difference / torso length as a relative scale (threshold 0.4), unaffected by distance
- ~~Bending to touch the ground swallowed as fallen~~ — **fixed (5/6)**: added a deep-bending guard inside the fallen main branch (hip→ankle vector and downward vertical angle < 30° + bbox ≤ 1.0 → skip).
- ~~MediaPipe garbage frame triggering fallen~~ — **fixed (5/6)**: frames where trunk_angle computes shoulder.y > hip.y (vertical_ratio negative) are rejected; an average visibility of the 4 torso points < 0.5 is also rejected.
- Fall detection may produce false positives (lying down on a chair)
- **akimbo / knee_kneel unstable on-device** (measured 5/6): MediaPipe Pose frequently hallucinates landmarks for frames with the wrist near the hip or a single knee kneeling (trunk=160°+ is a common signal). The community-validated fixes have been applied (elbow-bowed-out as the primary signal, ankle.y ≈ knee.y to distinguish kneel-vs-lunge), but there are still occasional misses on real hardware. May require: (1) extending the field of view to 1.5-3m (avoiding half the body leaving the frame), (2) switching to RTMPose-wholebody (GPU path), (3) adding hand keypoint signals.
- Ghost fall detection: the voting buffer (majority vote over 20 frames) has greatly reduced false positives, but has not fully eliminated them. **The 4/8 meeting confirmed hallucinations are still frequent** (with no one present, locking onto a coat rack or similar object and judging it fallen)
- **`enable_fallen` is now parameterized** (4/6): the demo can disable fall detection to avoid false positives
- Since the project no longer centers on elderly care, **the fall-detection feature may be de-emphasized**
- Side-view sitting causes deviation in hip_angle and trunk_angle calculations; facing the camera frontally during the demo is recommended

## Event Schema (frozen v2.0)

```json
{
  "stamp":       1710000000.123,
  "event_type":  "pose_detected",
  "pose":        "standing",
  "confidence":  0.92,
  "track_id":    1
}
```

## Pose → Skill Mapping (5/12 Sprint)

| Pose | Brain trigger | Cooldown | Demo Scene |
|---|---|:---:|---|
| sitting | demo bridge → "Are you tired?" TTS (say only) | 5s | Interaction segment |
| crouching | demo bridge → "I'm right here" TTS | 5s | Interaction segment |
| bending | demo bridge → "Please be careful" TTS | 5s | Interaction segment |
| fallen | **demo silence** (5/8) — both TTS paths are muted, the Studio Trace still shows a red alert | **10s** | Scene 8 (future, not an emergency; use the wording "watch over / report", not "guard") |
| akimbo | demo bridge → "You look quite poised!" (tentative) | 5s | Interaction segment (promoted to Active 5/5) |
| knee_kneel | demo bridge → "Do you need my help?" (tentative) | 5s | Interaction segment (promoted to Active 5/5) |

> standing does not trigger any skill (pure baseline state).
> All go through the demo bridge in `vision_perception/vision_perception/event_action_bridge.py` POSE_TTS_MAP — only publishing `/tts`, not issuing Go2 motion. The long-term path switches to a formal Brain skill (`sit_along` / `careful_remind` / `fallen_alert` / `akimbo_react` / `knee_kneel_react`) via `/brain/proposal` → `/skill_result`, listed as a post-demo Stretch.

**5/8 fallen demo silence** (both TTS paths are muted, to avoid mid-frame false falls from carts/chairs interrupting the conversation):
1. `_on_fall_alert` (topic `/event/interaction/fall_alert`) → `FALL_ALERT_TTS = ""` + `if FALL_ALERT_TTS:` guard (commit `9d8acb7`)
2. `_on_pose_event` (topic `/event/pose_detected`) → `POSE_TTS_MAP` removes the `"fallen"` key (commit `b224217`)

Added the sync test `test_pose_tts_map_no_fallen_template_demo_silence` to lock both paths. Studio still shows the red alert chip — the visual record is retained, only the voice is not emitted.

**5/8 ankle-on-floor gate** (`pose_classifier.classify_pose` adds an `image_height` parameter): when `image_height` is provided, fallen is only accepted if `ankle_y / image_height > 0.7` (the person is in the lower 30% of the frame → actually lying on the ground). `image_height=None` keeps the original behavior (the existing unit tests are not broken), blocking mid-frame ankles (cart / chair / bending object). `vision_perception_node.py:289` passes `image.shape[0]` at the call site.

### `fallen_alert` wiring the face name (aligned 5/5)

The say_template of `fallen_alert` references the `{name}` variable: "**{name}**, a fall has been detected, please stay safe". Source of `{name}`:

1. When Brain receives a `pose_detected: fallen` event, it looks up the most recent `stable_name` of `identity_stable` from `/state/perception/face`
2. If there is no face recognition (unknown / no face in view) → fallback "a fall has been detected, please stay safe" (no name)
3. The same `{name}` variable is also used in face/README.md's `greet_known_person`; the template source is unified in the `interaction_executive` skill registry

> Detail: `docs/contracts/interaction_contract.md` v2.5 say_template section.

## Next steps

- [x] fallen → EMERGENCY integrated into the executive (already 4/4 PASS)
- [x] **akimbo / knee_kneel decision algorithm** (5/5 commit `ca32655`, `pose_classifier._is_akimbo` / `_is_knee_kneel` + demo bridge TTS template)
- [x] **B4-5 fallen_alert + {name} full chain** (5/5 commit `4f638ae`, event_action_bridge demo bridge subscribes to `/state/perception/face` caching the most recent stable name + format("{name}"))
- [x] **7-pose algorithm upgrade** (5/6, community-validated rules: elbow-bowed-out / ankle ≈ knee y / vertical_ratio gatekeeping / deep-bending guard, 26 unit tests all green)
- [x] **5/12 Sprint 5/7 on-device verification**: standing / sitting / crouching / bending / fallen passed (5/6)
- [ ] **akimbo / knee_kneel on-device miss fix** (5/6 user reported "basically can't detect at all") — candidates: extend the field-of-view distance, switch to RTMPose-wholebody, add hand keypoints
- [ ] **5/12 Sprint Active 7 on-device verification**: sitting / crouching / bending / fallen-with-name / akimbo / knee_kneel / standing, 3 stable triggers each
- [ ] **demo bridge exit path**: change pose→/tts to a formal Brain skill (`sit_along` / `careful_remind` / `fallen_alert`, etc.) via `/brain/proposal` → `/skill_result` (post-demo, Stretch P1)
- [ ] Fall-detection hallucination (locking onto a coat rack when no one is present) — change the voting buffer to 30 frames OR switch to a movement-based filter

## Subfolders

| Folder | Contents |
|--------|------|
| research/ | Model-selection process (MediaPipe vs RTMPose vs DWPose), benchmark comparisons, fall-detection research |
