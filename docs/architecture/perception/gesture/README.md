# Gesture Recognition

**English** | [中文](./README.zh.md)

> **Scope**: Source of truth for the vision_perception gesture subsystem design (MediaPipe Gesture Recognizer + in-house geometric/temporal detector) ｜ **Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception ｜ **Capability claim source of truth**: [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `gesture.wave`
> **Capability grade evidence (final fact)**: [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (gesture.wave = 🔴 **fail**; caveats override this page's narrative)
> **Maintained sub-files**: `CLAUDE.md` (working rules) ｜ `AGENT.md` (topic interface contract) ｜ `research/` (research-only, not source of truth)
> **What this page is not**: It is not the adjudication of capability pass/fail (see baseline-evidence). ⚠️ **gesture.wave is currently fail**; the "5/5 PASS" below is a 4/04 development-period unit test / local observation, **not the 6/04 trusted baseline**. Static gestures (thumbs_up/ok/palm) are fallback/demo-only, **not** the wave capability.

> MediaPipe Gesture Recognizer recognizes gestures. **Camera dynamic wave was measured as fail on 6/04**; static gestures can serve as a fallback.

## Capability Card (canonical 8 fields → link to claim matrix, do not repeat the full prose on this page)

> See the full 8-field prose in [claim matrix `gesture.wave`](../../../mission/2026-06-18-capability-claim-matrix.md#gesturewave). This table is a quick reference.

| Field | Value |
|---|---|
| **Current Claim** | Waving (camera dynamic wave) measured **fail** on 6/04; switch to static palm / raised hand, or only display the event in the Studio gesture panel |
| **Claim Level** | DO_NOT_CLAIM (fail, requires fallback) |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/) (n=9, recall=0.0, 6/6 positives all none, wave_pub=False throughout) |
| **Pass/Degraded/Fail/Insufficient** | 🔴 fail — root cause = intermittent 1.5m hand detection + overly strict WaveDetector threshold |
| **Fallback** | Do not demo camera dynamic wave (known fail, not an on-site failure); fall back to static palm / raised hand, or the voice path `wave_hello(1016)` (**a separate path**), or only display in Studio and mark as fail |
| **Non-Claims** | "Waving can trigger a greeting" / demoing wave as a reliable interaction / gestures triggering Go2 motion / conflating the `wave_hello` voice path with camera wave having passed |
| **Model Candidates** | SPIKE_AFTER_FAIL (not switching models; tune gesture_min_score / min_amplitude_px / vote_frames) |
| **Next Retest** | HITL tune gesture_min_score 0.1→0.05, min_amplitude_px 50→35, vote_frames/stable_s revert then retest; otherwise change the script to palm fallback |

> **Static gestures (palm / fist / index / thumbs_up / peace / ok)** are a usable fallback / demo-only on 6/04, **not the gesture.wave capability**, and have not been measured against a trusted baseline — unless the baseline is rerun, static gestures must not be claimed as "passed".

## Status Card

> **Status card caveat (converged 6/04)**: The "4/04 5/5 PASS" in the table below is a **local observation from the static-gesture development period**, **not the trusted baseline for the gesture.wave capability**. The 6/04 trusted measurement is **gesture.wave = 🔴 fail** (see capability card above). Completion is module development progress, not capability pass.

| Item | Value |
|------|---|
| Status | **gesture.wave = 🔴 fail (6/04 trusted)**; static gestures are fallback/demo-only |
| Version/Decision | MediaPipe Gesture Recognizer (CPU 7.2 FPS) |
| Completion | 90% (module development progress, not capability pass — see caveat above) |
| Last verified | gesture.wave latest trusted = 2026-06-04 HITL (**fail**); 4/04 5/5 PASS is only a local observation from the static-gesture development period |
| Entry file | `vision_perception/vision_perception/gesture_classifier.py` |
| Tests | `python3 -m pytest vision_perception/test/test_gesture_classifier.py -v` |

## How to Launch

```bash
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  gesture_backend:=recognizer max_hands:=2
```

## Core Flow

```
D435 RGB → vision_perception_node
    ↓
MediaPipe Gesture Recognizer（CPU, 21 手部關鍵點）
    ↓
gesture_classifier.py（靜態：stop/point/fist, 時序：wave）
    ↓
/event/gesture_detected（JSON: gesture, confidence, hand_label）
    ↓
interaction_executive_node → Go2 動作
```

## Supported Gestures (MOC 9 types, in 3 groups)

### 1. System Control (4 types)

| Gesture | Label | Mode | Triggered Skill | Description |
|:---:|:---|:---|:---|:---|
| 🖐️ | Palm | Pause | `system_pause` | Full pause — stops all current actions and movement |
| 👊 | Fist | Mute | `enter_mute_mode` (Hidden) | Robot dog sits down, turns off voice output |
| ☝️ | Index | Listen | `enter_listen_mode` (Hidden) | Robot dog stands up, turns on speech recognition |
| 👌 | OK | Confirm | (gate, does not trigger skill directly) | **Secondary confirmation action**: two-stage execution confirmation after any command |

### 2. Interaction & Emotion (2 types)

| Gesture | Label | Mode | Triggered Skill | Go2 ID | Action |
|:---:|:---|:---|:---|:---:|:---|
| 👍 | Thumb | Happy | `wiggle` | 1033 | Wiggle butt (Wiggle) |
| ✌️ | Peace | Relax | `stretch` | 1017 | Stretch (Stretch) |

### 3. Dynamic (3 types, require detecting motion trajectory)

| Gesture | Label | Mode | Triggered Skill | Go2 ID | Detection Method |
|:---:|:---|:---|:---|:---:|:---|
| 👋 | Wave | Greeting | `wave_hello` | 1016 | Wave back and forth left-right, velocity reversal count ≥ 2 |
| 🫴 | ComeHere | Follow | `follow_me` (Future) | 1018 | Palm swiping inward (advanced mode) |
| 🔄 | Circle | Dance | `dance` (Future) | — | Circular trajectory |

> **Active** (marked in 5/12 sprint, **enum/skill wiring existing ≠ capability pass**): Palm, OK, Thumb, Peace, Wave
> ⚠️ **Wave (camera dynamic) 6/04 trusted = 🔴 fail** (see capability card); the 6/18 demo does not perform camera dynamic wave, falling back to static palm/raised hand or the voice `wave_hello`. The remaining static gestures are demo-only fallback, not measured against a trusted baseline.
> **Hidden** (in the registry, grayed-out in Studio, enum implemented but not bound to a skill): Fist, Index
> **Future** (trajectory detector not implemented): ComeHere, Circle
> Corresponds to sprint design §4 Skill Registry 26+1 entries.

## Trigger Rules

Per the MOC spec + sprint design §4.2:

1. **0.5-second stable hold**: A gesture must be held stably for **0.5 seconds** or more before it can trigger (temporal dedup, avoiding false triggers from passing waves)
2. **OK secondary confirmation**: After a high-risk action (motion / state-change) is recognized, a 👌 OK gesture must be made again for "final confirmation" before execution; low-risk social skills (e.g. wave_hello) can trigger directly without OK
   - High-risk (must pass OK): `wiggle`, `stretch`, `follow_me`, `dance`
   - Low-risk (direct trigger): `wave_hello` (wave response), `system_pause` (palm, safety immediate), `enter_mute_mode` (fist, changed to direct fire on 5/12 — mode switch treated as low-risk), `enter_listen_mode` (index, changed to direct fire on 5/12 likewise)

   > **5/12 change**: `enter_mute_mode` / `enter_listen_mode` changed from "must pass OK" to "direct fire". Reason: a mode switch is explicit user intent and does not involve motion safety; passing OK instead slows the demo pace. See implementation in `interaction_executive/interaction_executive/brain_node.py:_GESTURE_DIRECT`.
3. **Operation flow example**:
   - Step A: Make ✌️ (Peace) toward the camera, held for 0.5 seconds
   - Step B: After the system locks on, make 👌 (OK), held for 0.5 seconds
   - Execution: Go2 performs action 1017 (Stretch)

## 5/5 Implementation Landing (Active enum)

The actual enums emitted (aligned with MOC naming):

| Rule Source | Landed Gesture | Code |
|---|---|---|
| MediaPipe Recognizer label remap | palm / fist / index / **thumbs_up** / peace | `gesture_recognizer_backend.py:_GESTURE_MAP` (5/8 commit `efda3c0`: `thumb` → `thumbs_up` to align with the contract enum, otherwise `brain_node._GESTURE_CONFIRM` won't receive thumbs_up→wiggle) |
| In-house geometric rule override | **ok** (thumb tip ↔ index tip distance < hand_width × 0.3 + middle/ring/pinky not fully curled) | `gesture_classifier.py:detect_ok_circle` |
| Temporal trajectory override | **wave** (wrist X velocity reversals ≥ 2 within a 1.5s window + amplitude > 50px) | `dynamic_gesture_detector.py:WaveDetector` |

**Not landed (still Future)**: ComeHere, Circle — the trajectory loop needs a longer buffer + shape matching, to be evaluated post-demo.

**Removed 5/5**: the actual conversion of `GESTURE_COMPAT_MAP={"fist":"ok"}` (semantic conflict, MOC's Fist=Mute ≠ OK=Confirm); the constant is retained as an empty dict to avoid breaking downstream imports.

## 0.5s Stability Gate (implemented, parameterizable)

`vision_perception_node` adds the ROS param `gesture_stable_s` (default 0.5):
- The same gesture must be held stably for 0.5 seconds before `/event/gesture_detected` is emitted
- Set `0.0` for instant bypass (for debug):
  ```bash
  ros2 param set /vision_perception_node gesture_stable_s 0.0
  ```

## Operational Limits and Known Issues

- **Effective range**: within approximately **2m** in front of the D435 (confirmed in the 4/8 meeting, imprecise at too great a distance)
- **Single-person operation only**: may be confused when multiple people appear simultaneously
- The point gesture is unstable (MediaPipe backend) → removed from the enum on 5/5 (no longer maps to MOC)
- There may be latency when switching gestures quickly (voting buffer 5 frames + 0.5s gate)
- After a Wave detector reset, ~6 frames are needed before it triggers again (min_samples)

## Event Schema (v2.0 frozen)

```json
{
  "stamp":       1710000000.123,
  "event_type":  "gesture_detected",
  "gesture":     "wave",
  "confidence":  0.87,
  "hand":        "right"
}
```

## Gesture → Skill Mapping (5/12 Sprint)

| Gesture | Brain Trigger | OK Secondary Confirmation | Go2 ID | TTS / Feedback | Cooldown |
|---|---|:---:|:---:|---|:---:|
| Palm | `system_pause` | ❌ Direct trigger (safety immediate) | StopMove (1003) | — | **None** |
| Fist | `enter_mute_mode` | ❌ Direct trigger (changed 5/12) | Sit down + mute | — | 3s |
| Index | `enter_listen_mode` | ❌ Direct trigger (changed 5/12) | Stand up + ASR on | — | 3s |
| OK | gate only — does not trigger skill directly | — | — | — | — |
| Thumb | `wiggle` | ✅ | 1033 (wiggle butt) | 「收到！」 | 3s |
| Peace | `stretch` | ✅ | 1017 (stretch) | — | 3s |
| Wave | `wave_hello` | ❌ Direct trigger (low-risk social) | 1016 | 「Hi！」 | 3s |
| ComeHere | `follow_me` (Future) | ✅ | 1018 | — | — |
| Circle | `dance` (Future) | ✅ | — | — | — |

> 5/12 demo Active 7 (Palm/Fist/Index/OK/Thumb/Peace/Wave) — i.e. the 7 gesture interactions of "stop / mute / listen / confirm / happy / relax / greet" (5/12 added Fist+Index direct fire). The 2 Future entries (ComeHere/Circle) keep the registry but the Studio button is grayed-out.

## Next Steps

- [x] **B4-2 Wave dynamic trajectory detection** — landed 5/5 (commit `95982d6`, `dynamic_gesture_detector.WaveDetector` + bypass 5/12 fix); **real-machine effect pending verification**, and note that wave takes an independent publish path (does not enter the static stable gate, to avoid being overridden by adjacent palm/peace voting)
- [ ] **B4-3 Palm Pause / Fist Mute rule linkage** (system_pause / enter_mute_mode going live) — enum implemented, skill trigger chain not yet connected
- [x] **0.5s stable dedup gate** — landed 5/5 in `vision_perception/vision_perception/vision_perception_node.py` (commit `4f638ae`), ros param `gesture_stable_s` (default 0.5, can be set to 0.0 to bypass); **applies only to static gestures**, wave does not go through this gate
- [ ] **OK secondary confirmation gate**: add a confirmation state machine in `interaction_executive` — lock the pending skill → OK triggers → execute (Stretch P1)
- [ ] ComeHere / Circle gesture detector (post-demo, Future bucket)
- [ ] point gesture stabilization (currently unstable on the MediaPipe backend, retired in the sprint design)

## Subfolders

| Folder | Contents |
|--------|------|
| research/ | Model selection process (MediaPipe vs RTMPose vs custom), benchmark comparisons, community feedback |
