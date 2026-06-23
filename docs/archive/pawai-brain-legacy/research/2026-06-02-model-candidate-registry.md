# PawAI Model Candidate Registry

> 🔬 **RESEARCH-ONLY — research-not-truth**。本檔是模型候選註冊，**不是**能力 pass/fail 真相、**不是**實作 backlog、**不是** 6/18 promise list。能力是否 pass 以 [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) 為準；能不能講連 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)。索引見 [`README.md`](README.md)。
> 🏷️ **Tier**：混合 `BASELINE_NOW` / `STUDIO_ONLY_NOW` / `SPIKE_AFTER_FAIL` / `FUTURE_RESEARCH`（逐項見下方 Registry Tiers）。現役 pass 模型一律 `KEEP_CURRENT`，不換。

> Drafted: 2026-06-01 Asia/Taipei  
> File name follows the requested registry path: `2026-06-02-model-candidate-registry.md`  
> Status: research registry, not a 6/18 implementation plan  
> Scope anchor: `docs/mission/2026-06-18-demo-north-star.md` and `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`

This document is a future model candidate registry. It is not a 6/18 promise list, not a Brain mainline contract, and not an instruction to add every listed model to the demo.

The 6/18 rule is:

> Only `BASELINE_NOW` capabilities can affect the main demo path, and only after scoreboard baseline data says pass. Everything else is either Studio evidence, baseline-failure fallback, or future research.

## Source Snapshot

- PINTO clone inspected locally at `C:\tmp\PINTO_model_zoo`, commit `870b2b8`.
- PINTO is a model conversion zoo covering TensorFlow, PyTorch, ONNX, OpenVINO, TF-TRT, TensorFlow Lite, EdgeTPU, CoreML, and related formats. Each subfolder has its own upstream model license.
- Official/current references checked:
  - OpenCV YuNet/SFace: https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html and https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
  - SenseVoice: https://github.com/FunAudioLLM/SenseVoice
  - Ultralytics YOLO26 Jetson/TensorRT: https://docs.ultralytics.com/guides/nvidia-jetson and https://docs.ultralytics.com/modes/export/
  - MediaPipe Gesture/Pose tasks: https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer and https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
  - OpenRouter TTS endpoint: https://openrouter.ai/docs/features/multimodal/tts
  - edge-tts: https://github.com/rany2/edge-tts

## Registry Tiers

| Tier | Meaning | 6/18 effect |
|---|---|---|
| `BASELINE_NOW` | Must be measured because it affects the 6/18 mainline story if it passes. | May enter Brain mainline only when scoreboard grade is `pass`. |
| `STUDIO_ONLY_NOW` | Worth showing as evidence now, but not allowed to drive Brain decisions, motion, or nav. | Studio overlay/event only. |
| `SPIKE_AFTER_FAIL` | Only test if the primary baseline path fails or is blocked. | Time-boxed fallback spike, not a parallel commitment. |
| `FUTURE_RESEARCH` | Interesting, but outside 6/18 scope. | Do not spend 6/18 baseline time on it. |

## Hard Boundaries

- Pose passing baseline does not make pose a Brain mainline trigger. `pose.basic` remains Studio evidence only.
- Gesture scope is `gesture.wave` only. Do not add open palm, thumbs up, OK, pointing, or static gestures to the 6/18 claim unless a later baseline explicitly promotes them.
- YOLO26n is only claimed as `object.cup`. General object recognition, bottle/key/wallet/denture, VLM scene understanding, and object search remain future.
- HSV color is a bbox ROI heuristic for evidence, not a reliable color recognition model and not a Brain gate.
- Nav model candidates may produce evidence, but `nav.safe_stop` remains RPLIDAR/D435/reactive_stop-led. No monocular model may independently stop or resume motion.
- Gemini TTS preview is experience quality, not reliability. Reliability bottom line is edge/local fallback.

## Executive Shortlist

| Capability | Candidate | Tier | Runtime role | Gate rule |
|---|---|---|---|---|
| `face.recognition` | YuNet + SFace | `BASELINE_NOW` | Face identity evidence/content | Brain may use known/unknown only if scoreboard pass; never stranger-alert. |
| `voice.command` | SenseVoiceSmall GPU | `BASELINE_NOW` | Fixed intent trigger | Unknown/low confidence must no-op or ask repeat. |
| `gesture.wave` | MediaPipe wave detector path | `BASELINE_NOW` | Low-risk interaction trigger | Only wave, only if false-trigger baseline passes. |
| `object.cup` | YOLO26n + TensorRT | `BASELINE_NOW` | Cup content/evidence | Only cup class; no general object claim. |
| `tts.fallback` | edge-tts + local WAV | `BASELINE_NOW` | Voice output reliability | Gemini preview can fail without failing demo; edge/local must work. |
| `pose.basic` | MediaPipe Pose | `STUDIO_ONLY_NOW` | Studio posture evidence | Never triggers motion/nav/Brain action. |
| `object.cup_color` | OpenCV HSV ROI | `STUDIO_ONLY_NOW` | Cup color evidence | Display only; no reliable color claim. |
| `voice.asr_backup` | PINTO Whisper ONNX | `SPIKE_AFTER_FAIL` | ASR fallback comparison | Only if SenseVoice baseline fails or install is blocked. |
| `gesture.wave_backup` | PINTO WHC / PGC | `SPIKE_AFTER_FAIL` | Wave/pointing fallback spike | Only if MediaPipe wave fails. |
| `object.detector_backup` | PINTO YOLOX / PicoDet / NanoDet | `SPIKE_AFTER_FAIL` | Detector fallback | Only if YOLO26n TensorRT path fails. |
| `nav.visual_evidence` | FastDepth / YOLOX / ByteTrack | `FUTURE_RESEARCH` | Studio-only nav evidence | Not part of 6/18 nav baseline. |

## Face Recognition

### BASELINE_NOW: YuNet + SFace

Recommended source:
- Primary: OpenCV Zoo / OpenCV API.
- PINTO backup: `144_YuNet`, `387_YuNetV2`, `256_SFace`, `194_face_recognizer_fast`.

Why this is baseline-worthy:
- OpenCV exposes `FaceDetectorYN` for YuNet and `FaceRecognizerSF` for SFace.
- The OpenCV tutorial documents ONNX model requirements and SFace benchmark thresholds.
- The existing PawAI docs already describe `YuNet -> SFace -> face_db -> /state/perception/face`.

6/18 claim:
- Say: "PawAI can recognize pre-registered demo participants under measured conditions."
- Do not say: public-space identity, stranger alarm, security, or guardian mode.

Minimum baseline:
- registered recall at 1m and 2m
- unknown false accept rate
- wrong-person count
- time to stable identity

Scoreboard behavior:
- `pass`: Brain may use identity as content for greeting.
- `degraded`: Studio may show face evidence; Brain should greet generically.
- `fail`: no identity claim.

### SPIKE_AFTER_FAIL: PINTO Face Variants

Use only if OpenCV DNN/runtime blocks the baseline path.

Candidates:
- `144_YuNet`: OpenCV Zoo YuNet conversion.
- `387_YuNetV2`: newer YuNetV2 conversion.
- `256_SFace`: SFace conversion and demo wrappers.
- `194_face_recognizer_fast`: older SFace/OpenCV Zoo face recognition package.

Risk:
- PINTO gives converted assets and scripts, not the full PawAI threshold/tracking/enrollment policy.
- Swapping runtime does not solve lighting, distance, privacy, or tracking stability.

## Voice And Speech

### BASELINE_NOW: SenseVoiceSmall GPU

Recommended source:
- SenseVoiceSmall through FunASR CUDA path.

Why this is baseline-worthy:
- SenseVoice targets multilingual speech understanding, including ASR, language identification, speech emotion recognition, and audio event detection.
- For PawAI, only ASR and fixed intent extraction should matter for 6/18.

6/18 claim:
- Say: fixed command recognition under tested microphone/noise/distance conditions.
- Do not say: free-form robust conversation, full offline voice AI, or medical/care reliability.

Minimum baseline:
- exact intent accuracy for demo command set
- unknown rejection rate
- median and p90 ASR latency from mic boundary
- stop-command false negative count
- noisy room and robot-audio echo cases

Scoreboard behavior:
- `pass`: fixed command trigger allowed through Brain gate.
- `degraded`: ask repeat or Studio-only transcript.
- `fail`: no voice-triggered skills; use Studio/manual path.

### SPIKE_AFTER_FAIL: PINTO Whisper ONNX

Candidate:
- PINTO `381_Whisper`.

Use only if:
- SenseVoice GPU install/runtime is blocked, or
- SenseVoice accuracy fails and a time-boxed fallback comparison is needed.

Risk:
- Existing project notes already show Whisper Tiny struggled on Chinese short commands with robot noise.
- Do not let Whisper work distract from SenseVoice baseline unless SenseVoice fails.

### BASELINE_NOW: TTS Fallback Chain

Recommended order:
1. Gemini 3.1 Flash TTS Preview through OpenRouter for natural demo voice.
2. edge-tts as fast online fallback.
3. Local WAV bank for deterministic failure/safety phrases.

Reliability rule:
- Gemini preview quality is optional.
- edge/local must cover: "please repeat", "I cannot do that", "stopping", "done", "not ready".

Scoreboard behavior:
- `pass`: voice response may be part of demo.
- `degraded`: use local WAV or text-only Studio evidence.
- `fail`: no audio claim; do not block safety behavior.

## LLM / Brain

### BASELINE_NOW: RuleBrain + Fixed Command Gate

Model/service:
- Deterministic local intent allowlist and skill policy gate.
- Cloud LLM can phrase non-control responses only.

Allowed cloud role:
- OpenRouter Gemini Flash/Lite-class model for reply polish or Studio evidence summary.
- It must not create new skills, bypass capability health, or authorize motion.

6/18 claim:
- Say: Brain parses fixed commands and fail-closes through capability gates.
- Do not say: fully autonomous LLM agent or general robot planner.

Scoreboard behavior:
- `grade == pass && claim_level == mainline` is required for any Brain-triggered capability.
- `degraded`, `fail`, `insufficient_data`, `studio_only`, and `future` must not trigger motion/nav.

## Gesture Recognition

### BASELINE_NOW: MediaPipe `gesture.wave`

Recommended source:
- Existing MediaPipe/vision pipeline for wave detection.
- Keep the claim to `gesture.wave` only.

Why this is baseline-worthy:
- It supports the canonical demo story: user approaches, waves, PawAI responds.
- It is non-contact and low-risk if restricted to greeting/emote.

Minimum baseline:
- positive wave recall at 1m and 2m
- person-present idle false trigger rate
- repeated trigger count under cooldown
- latency to event

Scoreboard behavior:
- `pass`: may trigger `wave_hello` or a low-risk greeting.
- `degraded`: Studio shows wave evidence; no automatic greeting.
- `fail`: gesture trigger disabled.

Explicit non-claims:
- no open palm claim
- no OK/thumbs-up claim
- no static gesture command language
- no motion/nav triggered by gesture

### SPIKE_AFTER_FAIL: PINTO WHC / PGC

Candidates:
- `481_WHC`: waving hand classifier.
- `477_PGC`: pointing gesture classifier.

Use only if:
- MediaPipe wave baseline fails because of latency, install, false triggers, or poor recall.

Risk:
- These models depend on upstream crop/detection quality.
- Dataset/domain fit is unknown.
- PGC pointing is not a 6/18 claim; do not promote it unless a later North Star amendment allows it.

## Pose Recognition

### STUDIO_ONLY_NOW: MediaPipe `pose.basic`

Recommended source:
- MediaPipe Pose Landmarker / BlazePose.
- PINTO `053_BlazePose` only as conversion/runtime fallback.

Why this is useful:
- It can enrich Studio with posture evidence such as standing/sitting/bending.
- It helps explain that PawAI sees body state, without claiming care reliability.

6/18 claim:
- Say: Studio can display coarse posture evidence if baseline passes.
- Do not say: Brain uses pose to control robot, fall detection is reliable, or PawAI detects emergencies.

Scoreboard behavior:
- `pass`: Studio overlay/status chip only.
- `degraded`: show lower-confidence/unknown state.
- `fail`: hide or mark unavailable.

Critical boundary:
- Pose must not trigger motion.
- Pose must not trigger TTS alert.
- Pose must not be used as safety gate.

### FUTURE_RESEARCH: Wholebody / RTMPose / ViTPose

Candidates:
- PINTO `393_RTMPose_WholeBody`
- PINTO `427_RTMPose_Hand`
- PINTO `440_ViTPose`
- PINTO wholebody detector families

Reason to defer:
- Better keypoints do not solve 6/18 reliability claims.
- Detector/crop/postprocess complexity will compete with face/voice/object/nav baseline time.

## Object Recognition

### BASELINE_NOW: YOLO26n + TensorRT for `object.cup`

Recommended source:
- Ultralytics YOLO26n exported to TensorRT engine on target Jetson.

Why this is baseline-worthy:
- It directly supports canonical story step: "PawAI sees a cup."
- Ultralytics documents YOLO26n export to TensorRT and Jetson deployment.

6/18 claim:
- Say: `object.cup` can be detected under measured demo conditions.
- Do not say: general object recognition, full COCO reliability, object search, VLM scene understanding, or lost-item finding.

Minimum baseline:
- cup recall at 1m and 2m
- idle false positive rate in no-cup scenes
- latency with TensorRT cache warmed
- wrong-class count
- model startup/cache behavior

Scoreboard behavior:
- `pass`: Brain may mention cup as content, not as safety signal.
- `degraded`: Studio-only bbox evidence.
- `fail`: no object claim in demo narration.

### STUDIO_ONLY_NOW: OpenCV HSV Cup Color Evidence

Definition:
- A new bbox ROI color heuristic over YOLO26n cup detection.
- It is not a trained model and not a reliable color recognition capability.

Allowed output:
- Studio evidence label such as `cup_color_hint=red-ish`.
- Screenshot/debug overlay.

Disallowed output:
- Brain gate.
- Reliable color claim.
- "PawAI recognizes colors" phrasing.

Minimum measurement:
- run only on frames where cup bbox confidence passes threshold
- record dominant hue bucket, ROI crop, lighting condition, and confidence
- mark as `insufficient_data` by default until separately tested

### SPIKE_AFTER_FAIL: PINTO Detector Backups

Candidates:
- `132_YOLOX`: nano/tiny/s variants.
- `174_PP-PicoDet`: S/M/L detector family.
- `072_NanoDet`: lightweight detector.

Use only if:
- YOLO26n export/runtime fails, or
- YOLO26n cup recall is unacceptable after threshold/config checks.

Risk:
- Switching detector families may consume more time than fixing data, thresholds, or lighting.
- If YOLO26n passes, these do not add 6/18 value.

## Navigation / Avoidance Evidence

### FUTURE_RESEARCH: Visual Evidence Models

Candidates:
- `146_FastDepth`
- `439_Depth-Anything`
- `132_YOLOX`
- `262_ByteTrack`
- `116_DroNet`
- `258_TinyHITNet`

Registry role:
- Future visual evidence radar only.
- Do not run these before nav baseline unless the baseline owner explicitly opens a spike window.

Why not now:
- North Star v2 requires nav.short_move + safe_stop to be measured conservatively.
- Visual ML depth/tracking can easily distract from RPLIDAR/D435/reactive_stop baseline.
- Monocular depth and collision probability are not metric safety guarantees.

Allowed future use:
- Studio overlay: bbox, track id, relative depth heatmap, near-zone visualization.
- Offline rosbag analysis.
- Evidence correlation against D435/LiDAR.

Disallowed 6/18 use:
- independent stop
- resume
- dynamic avoidance claim
- follow-person claim
- guide-dog framing

## Brain / Studio / CLI Infrastructure

These are not model candidates, but they define how candidates are allowed to matter.

### Brain

- Brain consumes capability health, not raw model enthusiasm.
- The policy should remain fail-closed:
  - `BASELINE_NOW + pass + mainline`: may be used according to dependency role.
  - `STUDIO_ONLY_NOW`: display only.
  - `SPIKE_AFTER_FAIL`: disabled unless primary failed and spike was approved.
  - `FUTURE_RESEARCH`: not visible to Brain as capability.

### Studio

Studio should show:
- model name/version
- source (`live`, `mock`, `frozen`, `missing`)
- capability id
- grade
- confidence
- latency
- last tested time
- reason for degraded/fail/insufficient_data

Studio should not be treated as authority. It displays evidence; scoreboard and runtime gates decide behavior.

### pawai CLI

CLI should remain the readiness/deploy surface:
- `pawai dev info <module>` maps work to `face`, `speech`, `gesture`, `pose`, `object`, `nav`, `brain`, `studio`.
- `pawai jetson deploy --module <module>` moves code to Jetson.
- future `pawai readiness` / scoreboard commands should report whether a candidate is active, studio-only, fallback, or future.

The registry does not require new CLI behavior by itself.

## Candidate Table

| Area | Candidate | Source | Tier | Runtime target | 6/18 allowed behavior | Defer reason / trigger |
|---|---|---|---|---|---|---|
| Face | YuNet + SFace | OpenCV Zoo / PINTO `144`, `256` | `BASELINE_NOW` | OpenCV DNN ONNX | Known-person greeting content | n/a |
| Face | YuNetV2 | PINTO `387_YuNetV2` | `SPIKE_AFTER_FAIL` | ONNX/TFLite variants | Backup only | OpenCV YuNet blocked |
| ASR | SenseVoiceSmall GPU | FunAudioLLM | `BASELINE_NOW` | CUDA/FunASR | Fixed intent trigger | n/a |
| ASR | Whisper ONNX | PINTO `381_Whisper` | `SPIKE_AFTER_FAIL` | ONNX | ASR fallback comparison | SenseVoice fails |
| LLM | RuleBrain/fixed allowlist | Local | `BASELINE_NOW` | Python deterministic | Skill gate input | n/a |
| LLM | Cloud LLM via OpenRouter | OpenRouter | `STUDIO_ONLY_NOW` | API | Text polish/evidence summary | Never controls motion |
| TTS | edge-tts | edge-tts | `BASELINE_NOW` | Python online TTS | fallback speech | Gemini preview slow/down |
| TTS | local WAV bank | local files | `BASELINE_NOW` | local playback | deterministic phrases | n/a |
| TTS | Gemini TTS preview | OpenRouter | `STUDIO_ONLY_NOW` | `/audio/speech` | natural voice when available | preview/cloud risk |
| Gesture | wave | MediaPipe/current pipeline | `BASELINE_NOW` | MediaPipe/OpenCV | low-risk greeting | n/a |
| Gesture | WHC | PINTO `481_WHC` | `SPIKE_AFTER_FAIL` | ONNX | wave fallback | MediaPipe wave fails |
| Gesture | PGC | PINTO `477_PGC` | `SPIKE_AFTER_FAIL` | ONNX | research only | pointing not claimed |
| Pose | pose.basic | MediaPipe Pose | `STUDIO_ONLY_NOW` | MediaPipe task | posture evidence | never Brain mainline |
| Pose | BlazePose converted | PINTO `053_BlazePose` | `SPIKE_AFTER_FAIL` | TFLite/ONNX variants | pose runtime backup | MediaPipe install blocked |
| Pose | RTMPose/ViTPose | PINTO `393`, `427`, `440` | `FUTURE_RESEARCH` | ONNX/TFLite | none | too much pipeline cost |
| Object | cup | YOLO26n | `BASELINE_NOW` | TensorRT engine | cup content/evidence | n/a |
| Object | cup color hint | OpenCV HSV ROI | `STUDIO_ONLY_NOW` | OpenCV heuristic | Studio evidence | not reliable color model |
| Object | YOLOX/PicoDet/NanoDet | PINTO `132`, `174`, `072` | `SPIKE_AFTER_FAIL` | ONNX/TFLite/TRT | detector backup | YOLO26n fails |
| Nav | visual bbox/track | YOLOX + ByteTrack | `FUTURE_RESEARCH` | ONNX + tracker | future Studio overlay | distracts nav baseline |
| Nav | monocular depth | FastDepth/Depth-Anything | PINTO `146`, `439` | `FUTURE_RESEARCH` | future overlay/offline | not metric safety |
| Nav | collision probability | DroNet | PINTO `116` | `FUTURE_RESEARCH` | offline only | domain mismatch |

## Recommended Next Tests

Run only the `BASELINE_NOW` and `STUDIO_ONLY_NOW` rows first:

1. `face.recognition`: YuNet + SFace, known/unknown, 1m/2m, wrong-person count.
2. `voice.command`: SenseVoiceSmall GPU, fixed commands, unknown rejection, mic-boundary latency.
3. `gesture.wave`: wave positive/idle false-trigger baseline.
4. `object.cup`: YOLO26n TensorRT, cup/no-cup scenes, warm cache latency.
5. `tts.fallback`: edge/local fallback phrases before Gemini quality tests.
6. `pose.basic`: Studio-only posture overlay; no Brain trigger.
7. `object.cup_color`: HSV ROI debug evidence; no Brain gate.

Do not open `SPIKE_AFTER_FAIL` until the corresponding baseline row has failed with a recorded reason.

## Promotion Rules

A candidate can move upward only by written amendment:

- `FUTURE_RESEARCH -> SPIKE_AFTER_FAIL`: requires a concrete baseline failure or a post-6/18 research window.
- `SPIKE_AFTER_FAIL -> BASELINE_NOW`: requires owner, deadline, pass/fail metric, and replacement target.
- `STUDIO_ONLY_NOW -> BASELINE_NOW`: requires explicit North Star amendment and safety review.
- `BASELINE_NOW -> Brain mainline`: requires scoreboard `pass`, `claim_level=mainline`, and dependency role compatibility.

No model is promoted by "it runs once."

## One-Line Summary

This registry is a candidate radar. For 6/18, only `BASELINE_NOW` is eligible for the mainline demo, `STUDIO_ONLY_NOW` is evidence-only, `SPIKE_AFTER_FAIL` opens only after a measured failure, and `FUTURE_RESEARCH` stays out of the demo path.
