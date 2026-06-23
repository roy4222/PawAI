# PawAI Mission Entry Page

**English** | [中文](./README.zh.md)

> **Governance header**
> - **Scope**: Entry page and summary of product direction / demo script / the eight major features (no technical details — those belong in each module's README).
> - **Status**: active / source-of-truth (mission lane). **Note**: The §2 positioning text on this page (v2.3, 2026-04-08) still uses the old "home interaction + guardian" framing; **for the 6/18 project review, the positioning, prohibited-terms list, and capability tiering are governed by [`2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md) v2 and [`2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md) (the latter wins)** — for 6/18, always say "watching over (守望)", never "guardian / stranger alert (守護 / 陌生人警報)".
> - **Owner lane**: mission (strategic boundary).
> - **Source-of-truth priority**: empirical evidence ([`runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)) ＞ convergence audit (`archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`) ＞ capability spec ([`architecture/specs/2026-06-18-capability-baseline-spec.md`](../architecture/specs/2026-06-18-capability-baseline-spec.md)) ＞ strategic boundary (north-star v2) ＞ this page's narrative.
> - **Maintained child files**: [`2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md), [`2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md), [`2026-06-18-demo-flow-plan.md`](2026-06-18-demo-flow-plan.md), [`2026-06-18-final-presentation-outline.md`](2026-06-18-final-presentation-outline.md), [`sprint-b-prime.md`](sprint-b-prime.md), [`demo-scope.md`](demo-scope.md), [`handoff_316.md`](handoff_316.md), [`meetings/`](meetings/).
> - **Archived / legacy boundary**: `meetings/*` are historical meeting snapshots (each file is marked historical at the top); `archive/` is fully frozen.
> - **What this README is NOT**: not the interface contract (see [`../contracts/interaction_contract.md`](../contracts/interaction_contract.md)), not technical details (see each module's README), not the final factual basis for capability pass/fail (see claim matrix + baseline-evidence).

**Project name**: Elder and Dog / PawAI
**Document version**: v2.3
**Finalized date**: 2026-03-07
**Last updated**: 2026-04-08
**Delivery deadlines**: 4/13 document submission, 5/16 Provincial Night Demo, 5/18 formal presentation, June oral report

> **v2.0 update**: Comprehensive update of the feature closed-loop design, local/cloud split strategy, PawAI Studio positioning, and team division-of-labor direction.

---

## 1. Document Positioning and How to Read It

### What this document is

This is the **Entry Point** for the PawAI Mission, responsible for integrating the project's core decisions, system outline, feature closed loops, and key navigation.

**Positioning notes**:
- It does not replace module design documents — it is a **summary + links**
- It does not replace the interface contract document — it is **decision context + acceptance goals**
- It provides a **Single Source of Truth** for the whole team

### Who should read it

| Role | Reading focus | Further reading |
|------|----------|----------|
| New member | Sections 1, 2, 3, 7 | [setup/README.md](../runbook/README.md) |
| Gesture/pose research (Huang Xu, Chen Ruo-en) | Sections 5, 6, 7 | [Gesture recognition/README.md](../architecture/perception/gesture/README.md) |
| Frontend development (Wei Yu-tong) | Sections 5, 6, 7 | [Pawai-studio/README.md](../architecture/studio/README.md) |
| System Architect | Whole document + appendix | [interaction_contract.md](../contracts/interaction_contract.md) |

---

## 2. One-Sentence Project Positioning

> **PawAI is a home robot dog centered on home interaction, while also possessing guardian capabilities.**

It is neither a chatbot nor a fixed surveillance camera, but a home robot dog with a sense of presence, capable of multimodal perception and physical response. Its main job is **to interact with users through gestures, posture, voice, and object recognition**, and to provide guardian reminders when it detects strangers or abnormal situations.

**Interaction / guardian ratio**:
- **Interaction 70%**: gesture / posture / voice / object recognition → trigger action or movement (the demo's main act)
- **Guardian 30%**: stranger alert, patrol (requires LiDAR), following (document-level future work)

**Why it has to be a Go2**: If you only want recognition and notification, a camera is enough. If you only want voice interaction, a speaker is enough. But what PawAI aims to build is an **interactive embodiment that can see, hear, move, and respond to your body language** — embodied presence + active response + physical approach, which requires a physical robot dog.

**Dual-version architecture**:
- **Main version (no LiDAR)**: fixed-location interaction — multimodal triggers, personalized greetings for acquaintances, stranger alerts, Studio remote observation
- **Upgraded version (with LiDAR)**: adds patrol + short-distance approach capabilities (LiDAR purchase confirmed; timeline pending the teacher's NSTC process)

> **System design spec (current)**: `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-11-pawai-home-interaction-design.md`
> The 4/10 guardian dog spec is already superseded: `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-10-guardian-dog-design.md`

**PawAI Studio** is the system's control console and demo observation entry point:

> It combines the chat/voice entry point, real-time video streaming, perception panels, and guardian mode display in one. During the demo, the laptop opens Studio as the sole interface for voice capture + system monitoring.

---

## 3. Project Background and Delivery Goals

### 3.1 Project Origin

This project uses the Unitree Go2 Pro as the platform to build a **prototype interactive robot dog for home scenarios**, with stranger-guarding capabilities as well. The core is not "better at chatting", but an embodied interaction system that "turns multimodal perception into physical interaction".

**Core values**:
- **PawAI Brain**: three-layer decision architecture (Safety → Policy → Expression), harness-oriented design
- **Multimodal perception**: gesture + posture + voice + object + face, forming the interaction main axis (70%)
- **Guardian assistance capabilities**: stranger alert + patrol (requires LiDAR) + following (document-level future work) (30%)
- **PawAI Studio**: control console, real-time video + guardian_mode + event push
- **Degradable, observable**: four-tier voice fallback, skill contract, pre-action validation
- Modular integration (Clean Architecture + standard interfaces), enabling division of labor and remote development

**Target scenario**: home interaction (gesture / posture / voice / object triggers) + guardian assistance (stranger alert).

### 3.2 Delivery Goals (4/13 hard deadline)

| Milestone | Date | Deliverable | Status |
|--------|------|----------|:----:|
| Feature closed-loop freeze | 3/12 | Confirm the local/cloud split for the 8 features (this document) | ✅ |
| Offense/defense handover | 3/16 | Roy hands off the architecture core; other members take over frontend and docs | ✅ |
| Frontend website deadline | 3/26 | Frontend pages complete; Roy reviews and informs of revision items | ✅ |
| Four-feature integration test | 3/26 – 4/2 | Face + voice + gesture + posture integration verification | ✅ |
| Five-feature integration + Studio | 4/7 | Object recognition + Studio Chat closed loop + Live View | ✅ |
| P0 stabilization | 4/6 | Demo main-line success rate >= 90% | ✅ |
| External LiDAR finalized | **4/14** | Confirm whether to purchase + model (school loan or new purchase) | 🔄 |
| **Document submission** | **4/13** | **Project document submission (target 60+ pages, currently 46 pages)** | 🔄 |
| PAI Docs website skeleton | 4/12 | Astro + Starlight framework + basic content | 🔄 |
| **Provincial Night Demo** | **5/16** | **Full system demonstration (provincial-level review)** | |
| **Formal presentation** | **5/18** | **Final presentation** | |
| Oral report | June | Oral report defense | |

---

## 4. System Platform and Compute Configuration

### 4.1 Hardware Configuration Overview

| Tier | Device | Specs | Use | Status |
|------|------|------|------|:----:|
| **Robot platform** | Unitree Go2 Pro | 12-joint quadruped, built-in LiDAR/IMU | Motion execution, environment perception | ✅ |
| **Edge compute** | NVIDIA Jetson Orin Nano SUPER | 8GB unified memory, 67 TOPS | Real-time perception, local inference, ROS2 runtime | ✅ installed |
| **Vision sensing** | Intel RealSense D435 | RGB-D depth camera | Face detection, gesture/posture/object recognition | ✅ installed |
| **Audio output** | USB external speaker (CD002-AUDIO) | USB DAC | TTS voice playback (works well) | ✅ installed |
| **Audio input (Demo)** | Laptop built-in microphone | via PawAI Studio web page | Demo voice capture main line (cleanest) | ✅ main line |
| ~~Audio input (onboard)~~ | ~~USB microphone (UACDemoV1.0)~~ | ~~mono, 48kHz~~ | ~~Go2 onboard capture~~ | ❌ deprecated |
| **Power supply** | XL4015 buck module | Go2 battery → 20V → Jetson | Jetson power | ⚠️ unstable |
| **External LiDAR (under evaluation)** | RPLIDAR A2M12 | 12m / 16000 scans/s / 360° | SLAM mapping + navigation obstacle avoidance | 🔄 finalized 4/14 |
| **Remote compute** | 5× NVIDIA Quadro RTX 8000 | 48GB VRAM each, 240GB total | LLM inference, ASR, cloud augmentation | ✅ |

> **Confirmed 4/8**: Jetson, D435, external speaker, and XL4015 are all formally installed on the Go2 body.
>
> **⚠️ Power risk**: The XL4015 buck board repeatedly cuts power while the Go2 is running (8+ cumulative times); the voltage has been set to 20V (Jetson's safe limit is 9-20V). Running multiple features simultaneously increases power draw, causing the voltage to drop and trigger a forced shutdown. There is a power-cut risk during the demo.
>
> **Microphone decision (4/8 meeting)**: The Go2 fan noise is extremely loud, making the onboard USB microphone nearly unusable (in testing, you may have to speak 5 times to be heard once). The demo switches to the laptop microphone, capturing audio via the PawAI Studio web page over WebSocket → Gateway → ROS2 pipeline, which is the cleanest.

**Remote server detailed specs**:
- CPU: 2× Intel Xeon Gold 6248R (96 threads)
- RAM: 754 GiB
- CUDA runtime: 13.0 / nvcc toolkit: 12.0

### 4.2 Local/Cloud Compute Split Strategy

**Core principles**:
- **Low-latency needs** → keep on local (Jetson)
- **High-quality understanding** → hand off to cloud (RTX 8000)
- **Safety control** → never hand off to the cloud for direct execution

```
┌─────────────────────────────────────────────────────────────┐
│  雲端增強層 (5×RTX 8000, 240GB VRAM)                         │
│  ├── GPU 0: LLM Brain (Qwen2.5-7B-Instruct, vLLM)           │
│  ├── GPU 1: 備用 / 模型實驗                                   │
│  ├── GPU 2-4: 未來擴充（物體辨識、ArcFace 等）                │
│  └── CPU: FastAPI Gateway + Event Bus + PawAI Studio Backend │
└─────────────────────────────────────────────────────────────┘
                          ↑↓ WebSocket / HTTP
┌─────────────────────────────────────────────────────────────┐
│  邊緣端 (Jetson Orin Nano 8GB)                               │
│  ├── 常駐：Sherpa-onnx KWS (~50MB) + YuNet 人臉偵測 (~100MB) │
│  ├── 觸發式：faster-whisper ASR + Piper TTS                   │
│  ├── 降級用：Qwen2.5-0.8B INT4 (~1GB, 僅斷網時載入)          │
│  ├── ROS2 Humble + Interaction Executive                     │
│  └── D435 RGB-D + 深度估計                                    │
└─────────────────────────────────────────────────────────────┘
                          ↑↓ WebRTC DataChannel
┌─────────────────────────────────────────────────────────────┐
│  機器人 (Go2 Pro)                                            │
│  ├── 運動控制 (stand/sit/lie/wave/spin)                      │
│  ├── 音訊播放 (WebRTC api_id 4001-4004)                      │
│  └── 內建感測 (LiDAR/IMU/關節狀態)                            │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Jetson Memory Budget

| Item | Estimated footprint | Mode |
|------|----------|------|
| Ubuntu + ROS2 base system | 1.5-2.0 GB | resident |
| D435 + video streaming | 0.6-1.0 GB | resident |
| YuNet face detection | ~0.1 GB | resident |
| Sherpa-onnx wake word | ~0.05 GB | resident |
| faster-whisper Tiny/Small | 0.4-1.0 GB | triggered (loaded after wake) |
| Piper TTS | 0.3-0.5 GB | triggered (loaded after wake) |
| Qwen2.5-0.8B INT4 | ~1.0 GB | loaded only on offline degradation |
| External LiDAR driver (rplidar_ros2) | ~0.05 GB | resident (if purchased) |
| slam_toolbox (online_async) | ~0.3 GB | resident (if SLAM enabled) |
| Nav2 (AMCL + controller, composed) | ~0.5-0.8 GB | resident (if navigation enabled) |
| Safety margin | >= 0.8 GB | must be reserved |

> **SLAM/Nav2 resource assessment (4/8 investigation result)**:
>
> | Metric | Data | Verdict |
> |------|------|:----:|
> | RAM (SLAM+Nav2 added) | ~0.85-1.15 GB | ✅ safe (total ~3.5-4.7 GB / 8 GB, leaving 3.3-4.5 GB) |
> | CPU (slam_toolbox async) | ~70% (x86 baseline, higher on ARM) | ⚠️ risk point |
> | GPU | 0% (slam_toolbox is pure CPU) | ✅ no conflict |
> | LiDAR frequency requirement | 5-10 Hz (RPLIDAR A2 native 10Hz, sufficient) | ✅ |
>
> **Conclusion**: RAM is safe; CPU is the only risk. It is recommended to temporarily disable the Gesture Recognizer during demo navigation scenarios (to save CPU), since navigation does not need gestures.
> Configuration recommendation: `online_async` mode + `resolution: 0.15` + `minimum_travel_distance: 0.5` + Nav2 node composition + swap 4-8 GB.
> Reference: Waveshare UGV Beast already has a complete Jetson Orin Nano + RPLIDAR + SLAM + Nav2 tutorial, proving it is feasible at the hardware level.

---

## 5. Eight-Feature Closed-Loop Design (v2.4 — home interaction robot dog version)

### 5.1 Feature Overview and Interaction/Guardian Roles

> **Design principle**: interaction 70% + guardian 30%. All features serve the multimodal interaction main axis + the stranger-alert guardian scenario.

| # | Feature | Role in PawAI | Local/Cloud | Status |
|---|------|-----------|:---------:|:----:|
| 1 | Voice | **Interaction main axis A**: ASR + LLM + TTS closed-loop conversation | Cloud main line + local fallback | ✅ Chat closed loop passed 12 sentences (4/8), E2E ~2s |
| 2 | Gesture recognition | **Interaction main axis B**: mode switching + command triggers (Huang Xu to design details next week) | Local | ✅ on-device 5/5 PASS, mapping needs expansion |
| 3 | Posture recognition | State-perception layer: prolonged-sitting reminders, secondary alerts | Local | ✅ on-device 4/4 PASS, fall-hallucination risk |
| 4 | Object recognition | Context-enhancement layer: contextual responses to everyday items | Local (YOLO26n) | ✅ Executive integration done, cup ✅ bottle ❌ |
| 5 | Face recognition | Identity layer: personalized greetings for acquaintances + stranger-alert trigger | Local only | ✅ greeting made reliable, missing stranger logic |
| 6 | AI Brain (**PawAI Brain**) | **System core**: three-layer decision engine (Safety/Policy/Expression) | Mostly cloud | 🔄 being upgraded from rule engine |
| 7 | Navigation obstacle avoidance | Guardian upgrade capability: patrol + short-distance approach | External LiDAR + local | 🔄 LiDAR purchase confirmed, timeline pending NSTC process |
| 8 | PawAI Studio | Control console: remote observation + interaction entry point | N/A | ✅ Chat + Live View closed loop passed |

### 5.1.1 PawAI Brain Architecture (updated 4/11)

```
PawAI Brain（高階決策）→ Executive（唯一動作出口）→ Go2
Brain 不直接執行，Executive 才執行。
```

**Three-layer architecture**:
- **Layer A Safety** (inside Executive): stop / obstacle / emergency / banned_api / pre-action validation — always deterministic, never through the LLM
- **Layer B Policy** (Brain): interaction context → intent judgment → PawAI Skills selection → policy override — rules + PawAI Memory + function calling
- **Layer C Expression** (Brain): reply_text / tone / wording / Studio trace — LLM language capability

**Naming system**: the overall system name is **PawAI Brain**, the three layers are Safety/Policy/Expression, the skill set is **PawAI Skills**, the memory set is **PawAI Memory**, and the state topic is **`/state/pawai_brain`**. Guardian-related terms are kept in the subdomain: `guardian_mode` / `guardian_alert` / `guardian_behavior` / `guardian_incident`.

**Degradation**: LLM down → fixed lines / Cloud LLM down → RuleBrain / everything down → Safety Layer still runs

### 5.1.2 Demo P0 Script (5/16 Provincial Night Demo, 3 minutes)

> Interaction 70% / guardian 30%. Demo location: Room 1003, Third Hall.

| Time | Scene | Performance focus |
|------|------|---------|
| 0:00-0:10 | Opening: PawAI on standby | Studio shows idle |
| 0:10-0:45 | **★ Wow Moment: Self Introduce** | Host says "PawAI, introduce yourself" → 6-step skill queue (interaction as main subject + guardian mentioned in one line) |
| 0:45-2:30 | **Interaction main act (TBD 4/15)** | Gesture mode switching + voice conversation + object context + acquaintance greeting + posture perception |
| 2:30-3:00 | Stranger alert + wrap-up | Unregistered person enters → alert + Studio push + verbally note patrol/following |

> The interaction main act details will be filled in after the four members report their designs at next week's meeting (4/15). The full script is in `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-11-pawai-home-interaction-design.md` §7.

### 5.2 Feature 1: Voice

#### Demo main-line chain (finalized at 4/8 meeting: all-cloud + Studio voice entry)

```
筆電麥克風（via PawAI Studio 網頁）
  → WebSocket → Gateway (Jetson:8080) → ROS2 /asr_result
  → SenseVoice Cloud ASR（RTX 8000，~430ms）
  → Intent 分類（高信心 ≥ 0.8 → fast path 跳過 LLM）
  → Cloud Qwen2.5-7B-Instruct（vLLM，~1.5s）
  → edge-tts 雲端合成（P50 0.72s）
  → USB 外接喇叭 local playback
  → Studio Chat AI bubble 同步顯示
E2E 延遲：~2s（比機身 5-14s 大幅改善）
```

> **Onboard ASR deprecated**: Go2 fan noise drops the onboard USB microphone recognition rate to ~20%; switched to Studio web-page capture.

#### Local fallback chain (Jetson 8GB, for offline use)

```
Energy VAD 持續監聽（always-on，無喚醒詞）
  → Whisper Small (faster-whisper CUDA float16, ~12s warmup)
  → Intent 分類 → RuleBrain 模板回覆
  → Piper 本地 TTS → USB 外接喇叭
```

#### Four-tier degradation strategy

| Level | Condition | Behavior |
|:-----:|------|------|
| 0 | Cloud normal | Cloud Qwen2.5-7B full conversation + edge-tts + Studio full functionality |
| 1 | Cloud LLM disconnected | Auto-switch to Ollama qwen2.5:1.5b basic conversation + edge-tts |
| 2 | Cloud fully down (LLM+TTS) | RuleBrain template replies + Piper local TTS |
| 3 | Minimal floor | ASR + Intent fast path + RuleBrain + Piper (stop/bye/greeting) |
| **B** | **Demo emergency (Plan B)** | **Fixed-line script mode (~0.x second response)**: preset Q&A such as "hello", "what's your name", "what features do you have", etc. After ASR determines the intent, it directly matches a fixed answer. Studio shows a connection-status indicator light, and the team decides in real time whether to switch. |

> **Plan B design (decided at 4/8 meeting)**: Two versions of the demo conversation script must be prepared — Plan A (cloud AI normal conversation) and Plan B (local fixed lines). The cloud GPU has unexpectedly disconnected twice, so Plan B is mandatory insurance. If necessary, show a recording as evidence of the AI conversation feature.

#### Voice state machine

```
idle_listening (Energy VAD 持續監聽)
  → voice_detected → recording → transcribing (Whisper CUDA)
  → intent_classified → [high confidence] fast_path → speaking
                       → [low confidence]  llm_pending (Cloud→Ollama→RuleBrain)
  → reply_ready → tts_synthesizing (edge-tts / Piper fallback)
  → speaking → echo_cooldown → idle_listening
```

#### Key technology choices

| Module | Choice | Notes |
|------|------|------|
| Wake word | Not implemented (always-on listening) | Sherpa-onnx KWS was deferred after evaluation; currently uses Energy VAD for continuous listening |
| ASR (cloud main line) | SenseVoice Cloud (FunASR, RTX 8000) | ~430ms, three-tier fallback: cloud → SenseVoice local → Whisper |
| ASR (local fallback) | Whisper Small (faster-whisper CUDA float16) | Local offline, RTF 0.13, has hallucination issues (filtering rules established). **Performs very poorly on-device; long-sentence recognition fails; severe noise interference** |
| Local LLM | Ollama qwen2.5:1.5b | Fallback when cloud is disconnected. **Confirmed at 4/8 meeting: extremely low IQ, gibberish, completely unreliable** |
| Cloud LLM | Qwen2.5-7B-Instruct (vLLM) | The system's central brain; latency ~1.5s after Prefix Cache |
| TTS (cloud main line) | edge-tts (Microsoft) | P50 0.72s, extremely fast (synthesis completed within ~1 second) |
| TTS (local fallback) | Piper huayan | Acceptable speed, slightly slower than cloud (~2.0s). **Can serve as an offline backup** |

> **Local-solution summary (confirmed at 4/8 meeting)**: Whisper local ❌, Qwen 0.8B local ❌, Piper local ⚠️ backup only. The entire voice chain depends on the cloud, so the Plan B fixed-line script is mandatory insurance.

#### Core files

- `speech_processor/speech_processor/stt_intent_node.py` — ASR + Intent integration node
- `speech_processor/speech_processor/tts_node.py` — TTS + Go2/USB playback (edge-tts/Piper/MeloTTS/ElevenLabs)
- `speech_processor/speech_processor/llm_bridge_node.py` — LLM three-tier fallback + Go2 action
- `scripts/start_llm_e2e_tmux.sh` — main-line startup script (edge-tts + USB external devices)

### 5.3 Feature 2: Face Recognition

#### Positioning

**Local-only main line, never to the cloud.** YuNet + SFace + IOU tracking, greeting reliability completed (4/6).

#### Core capabilities

- YuNet 2023mar detection (CPU 71.3 FPS) + SFace 2021dec recognition
- IOU tracking (multi-face tracking)
- Hysteresis stabilization (sim_threshold_upper=**0.30** / lower=**0.22**, stable_hits=**2**)
- Depth distance estimation (D435 aligned depth, median filtering)
- 2-minute smoke test: `identity_stable: roy` 21 times (1-3 times before tuning), zero misidentification

#### Known issues (confirmed at 4/8 meeting)

- **Repeated greeting triggers**: the same person triggers repeatedly in a short time; no cooldown set yet (Roy to fix)
- **Low-light misjudgment**: occasional misjudgment in low-light environments (e.g., showing the wrong name)
- **No-person hallucination**: occasionally misjudges that a face is present when no one is there
- **Multi-person skeleton jumping**: tracking is chaotic when multiple people appear at once, unable to distinguish them correctly
- Track jitter persists (45 tracks/2min, target ≤5); the root cause is unstable YuNet detection

#### Changes before 4/13

Add two classes of standard ROS2 output to the existing script:

**`/state/perception/face`** (high-frequency continuous publishing):
- `track_id` — tracking ID
- `stable_name` — stabilized identity name
- `sim` — similarity score
- `distance_m` | null — depth distance (may be unavailable)
- `bbox` — bounding box
- `mode` — stable / hold
- `face_count` — number of people currently tracked

**`/event/face_identity`** (low-frequency conditional trigger):
- `event_type` — track_started / identity_stable / identity_changed / track_lost
- `track_id`
- `stable_name`
- `sim`
- `distance_m` | null

#### After 4/13

Refactor into a Clean Architecture ROS2 package.

### 5.4 Feature 3: Gesture Recognition 🔄

**Main line: MediaPipe Gesture Recognizer** (CPU 7.2 FPS, 0.10.18 aarch64 wheel).

> Selected after the 3/21 benchmark. CPU-only but FPS is sufficient. On-device acceptance 5/5 PASS (4/4).

- **Main line**: MediaPipe Gesture Recognizer (stop / thumbs_up / ok / fist / wave / point)
- **Backup**: RTMPose wholebody (rtmlib + onnxruntime-gpu)
- **Effective distance**: about **2m** (inaccurate when too far)
- **Limitation**: supports single-person detection only; gets confused with multiple people
- **To be expanded (4/8 meeting)**: members each develop new gesture types and corresponding interaction behaviors
- On-device acceptance passed: stop/thumbs_up/non-whitelist/distance/dedup all PASS

> See [`docs/architecture/perception/gesture/README.md`](../architecture/perception/gesture/README.md) for details

### 5.5 Feature 4: Posture Recognition 🔄

**Main line: MediaPipe Pose** (CPU 18.5 FPS, 17 keypoints COCO format).

> Selected at the 3/21 benchmark. On-device acceptance 4/4 PASS (4/4).

- **Main line**: MediaPipe Pose (standing / sitting / crouching / fallen / bending)
- **Backup**: RTMPose lightweight (GPU; mind the VRAM when coexisting with Whisper)
- **Fall detection**: `enable_fallen` is now parameterized (4/6); the demo can disable it to avoid false alarms
- **Limitation**: supports single-person tracking only; with multiple people it tracks only one
- **Known issue (confirmed at 4/8 meeting)**: fall hallucinations are still frequent (misjudging a fall when no one is there, locking onto objects like a clothes rack). Since the project no longer centers on elder care, **fall detection can be considered for de-emphasis**
- L3 stress test 60s passed (RAM 1.2GB, 52°C, GPU 0%)

> See [`docs/architecture/perception/pose/README.md`](../architecture/perception/pose/README.md) for details

### 5.6 Feature 5: AI Brain (PawAI Studio)

#### Positioning

**The system's central brain**, not just a chat model.

PawAI Studio = a ChatGPT / OpenClaw–style main entry point + an AI version of Foxglove, serving as the robot dog's control center.

#### AI Brain responsibilities

**Responsible for**:
- Event understanding (face / speech / gesture / pose → understandable context)
- High-level intent judgment (combining multimodal perception + robot dog state)
- Skill dispatch suggestions (greet_person / answer_question / follow_person / stop)
- Panel orchestration (deciding which panels Studio expands)
- Memory and summarization (conversation memory, person memory, trace summary)
- Natural-language reply generation

**Not responsible for**:
- Low-level control (does not directly control Go2 motors)
- Real-time safety control (obstacle avoidance, stop, safety gate)
- Millisecond-level reaction (wakeword, VAD, the front part of ASR, face detect)

#### Architecture relationship

```
Qwen2.5-7B-Instruct 提建議
  → Interaction Executive 做決策
  → Runtime 安全執行
```

#### Cloud main-brain status

- **Current**: Qwen2.5-7B-Instruct on RTX 8000 (vLLM, E2E verified)
- **Upgrade candidate**: a larger-parameter model, to be decided based on server stability
- **Local fallback**: Qwen2.5-0.8B (Jetson, backup when the cloud is disconnected, IQ to be tested)

#### PawAI Studio composition

| Element | Notes |
|------|------|
| Chat main entry | Unified entry point for text / voice input |
| Live Feed | D435 real-time video + face boxes |
| Robot Status | executive / perception / battery / posture |
| Skills console | Stand / Sit / Wave / Stop skill buttons |
| Event Timeline | Event-stream timeline (the core difference from ordinary chat) |
| Brain / Trace Panel | current intent / selected skill / why this action |
| Module Health Panel | active/inactive / latency of face / speech / cloud brain |

### 5.7 Feature 6: Object Recognition (P1 — core five features)

**One of the core five features** (finalized at the 3/18 meeting). Executive integration completed (4/6).

**Model**: YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16, stable at 15 FPS on the Jetson.

**Strategy**: preset target recognition (specified everyday items), not free search. All 80 COCO classes enabled, filtered by whitelist.

**Measured results (4/6 on-device verification)**:

| Item | Result | Notes |
|------|:----:|------|
| Cup (cup) | ✅ | threshold 0.5, triggers TTS "Would you like to drink water?" |
| Phone | ✅ | recognizable under appropriate lighting |
| Suitcase | ✅ | larger objects detected well |
| Book (book) | ⚠️ | difficult when lying flat; recognizable when opened for display (occasionally detected at threshold 0.3) |
| Water bottle (bottle) | ❌ | not detected, not shown in the demo |

**Known limitations**:
- **Small objects are nearly unrecognizable in low light**
- Objects must be at a certain height and facing the camera angle to be detected
- YOLO26n has a low small-object detection rate; upgrading to yolo26s is the subsequent improvement direction
- **To be decided**: members to select COCO classes suitable for indoor scenarios

### 5.8 Feature 7: Navigation Obstacle Avoidance (P2 → external LiDAR under evaluation)

#### Current status

**D435 solution discontinued** (4/3) — limited by the camera angle, which software cannot overcome.
**External LiDAR solution under evaluation** (4/8 meeting) — the teacher agreed to try it, to be finalized before 4/14.

#### History of the D435 solution's failure

LiDAR formally abandoned (3/26) → D435 reactive obstacle avoidance implemented + desk test passed (4/1) → all 3 rounds of on-device anti-collision testing on the Go2 failed (4/3) → discontinued. Root cause: the camera is mounted too high; low obstacles only enter the FOV at ~0.4m + a latency chain of ~1-1.5s.

#### External LiDAR solution (added at 4/8 meeting)

**Background**: The Go2 Pro's built-in LiDAR has only 18% coverage (22/120 valid points), and it is confirmed across the web that no one has successfully developed navigation on the Go2 Pro. An external LiDAR connects directly to the Jetson via USB, completely bypassing the Go2 WebRTC + voxel decoding bottleneck.

**Candidate product**: Slamtec RPLIDAR A2M12 ($7,530, 12m, 16000 scans/s, 360°)

**Evaluation timeline**:
1. 4/9: the teacher confirms whether the school (Teacher Huang's lab) has an old LiDAR to lend
2. If not → finalize the purchase model and budget before 4/14 (easier to reimburse under ten thousand)
3. After arrival: install + rplidar_ros2 driver + SLAM mapping + Nav2 tuning

**Technical assessment (investigation completed 4/8)**:
- **RAM: safe** — SLAM + Nav2 adds ~0.85-1.15 GB, totaling ~3.5-4.7 GB / 8 GB
- **CPU: risk point** — slam_toolbox ~70% CPU (x86 baseline); recommend temporarily disabling the Gesture Recognizer during demo navigation
- **GPU: no conflict** — slam_toolbox is pure CPU and does not contend for the GPU
- **LiDAR frequency: sufficient** — RPLIDAR A2 native 10Hz; slam_toolbox needs 5-10Hz
- **Power risk** — the LiDAR motor adds ~2-5W, which may aggravate the XL4015 power-cut issue
- **Reference case** — Waveshare UGV Beast already has a complete Jetson Orin Nano + RPLIDAR + SLAM + Nav2 tutorial
- See §4.3 memory budget for details

**Movement-option discussion (4/8 meeting)**:

| Option | Feasibility | Notes |
|------|:------:|------|
| No movement at all | Safe but awkward | A robot dog that can't walk will be questioned |
| **Straight-line short-distance movement** | **Minimum viable** | After recognizing a person, walk straight 2-3 steps, no left/right turns |
| Walk toward the person after recognition | Has interaction feel | Requires controlling distance and angle |
| Object-seeking (walk to an item) | High risk | Easily questioned with "why can't it go around" |

> **Teacher's suggestion**: Design a minimal movement scenario — after recognizing the user, the robot walks straight over to interact, showcasing "proactive approach".

**Document strategy**: After the 4/13 project document submission it cannot be modified (submitting files, not links), so **bet on having LiDAR first and write the navigation feature into the document**.

#### Completed work (kept as a foundation)

- D435 obstacle_avoidance_node (7 tests) + LiDAR lidar_obstacle_node (13 tests)
- Two-layer safety architecture + safety guard heartbeat
- Foxglove 3D dashboard visualization
- SLAM/Nav2 Gate A-D verification framework (see `docs/archive/refactor/slam-nav2.md`)
- See [Navigation obstacle avoidance/README.md](../architecture/navigation/README.md) for details

### 5.9 Feature 8: Documentation Website

#### Dual-site strategy

| Site | Positioning | Tech stack |
|------|------|--------|
| **PawAI Studio** | Control site + showcase site | React-based app (tentatively Next.js) |
| **Docs Site** | Documentation site / knowledge base | Astro + Starlight |

**Same repo, two sites, deployed separately.**

#### PawAI Studio includes
- Home / project intro / Showcase
- Chat main entry
- Live demo
- Event timeline
- Robot status
- Skills
- Debug / replay

#### Docs Site includes
- Project intro and architecture docs
- Module specs
- Installation and deployment tutorials
- Development records and pitfall write-ups
- Architecture evolution (old → new comparison)

#### Timeline and deployment (updated 4/8 meeting)
- **Domain**: hosted under Roy's personal domain (e.g., `docs.xxx.xxx` or `pai.xxx.xxx`)
- **Deployment**: GitHub Pages, static files only
- **Skeleton**: Roy completes the Astro + Starlight framework this weekend (before 4/12)
- **Content**: after setting up the blank structure, members add content via PR; use Claude Code to read the project data on GitHub to first generate basic content
- **Reference**: Huang Xu's previously organized Notion as a content source

#### Benchmark references
- Showcase style: [Odin Navigation Stack](https://manifoldtechltd.github.io/Odin-Nav-Stack-Webpage/)
- Documentation structure: [freeCodeCamp Docs](https://contribute.freecodecamp.org/intro/)
- Content depth: [Hiwonder JetAcker Wiki](https://wiki.hiwonder.com/projects/JetAcker/en/jetacker-orin-nano/docs/1.getting_ready.html)

---

## 6. Three-Layer Architecture Overview

### 6.1 Architecture Design Principles

- **Single control authority**: all actions have a single exit at Layer 3, avoiding multiple modules contending for control
- **Event-driven**: each module in Layer 2 publishes events; Layer 3 subscribes and then decides
- **Local floor**: every feature chain still has minimal usable capability when offline
- **The brain suggests, the Executive decides, the Runtime executes safely**

### 6.2 Three-Layer Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Interaction Executive + AI Brain                   │
│  ├─ 事件聚合器 (Event Aggregator)                            │
│  ├─ 狀態機 (State Machine)                                   │
│  ├─ 技能分派器 (Skill Dispatcher)                            │
│  ├─ 安全仲裁器 (Safety Guard)                                │
│  ├─ Brain Adapter → Qwen2.5-7B-Instruct (雲端) 或 0.8B (本地)│
│  └─ PawAI Studio Backend (FastAPI + WebSocket)               │
│  部署：Jetson (Executive) + RTX 8000 (Brain)                 │
└─────────────────────────────────────────────────────────────┘
                          ↑↓ ROS2 Topics + WebSocket
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Perception / Interaction Module Layer               │
│  ├─ 人臉模組 → /state/perception/face, /event/face_identity │
│  ├─ 語音模組 → /event/speech_intent_recognized               │
│  ├─ 手勢模組 → /event/gesture_detected (P1)                  │
│  ├─ 姿勢模組 → /event/pose_detected (P1)                     │
│  └─ 統一輸出：事件 (event) + 狀態 (state)                    │
│  部署：Jetson                                                 │
└─────────────────────────────────────────────────────────────┘
                          ↑↓ ROS2 Topics
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Device / Runtime Layer                              │
│  ├─ Go2 Driver (go2_robot_sdk, WebRTC DataChannel)           │
│  ├─ RealSense D435 (realsense2_camera)                       │
│  ├─ 音訊裝置 (USB 外接喇叭; 筆電麥克風 via Studio)             │
│  ├─ ROS2 Humble                                              │
│  └─ 邊緣模型執行 (ONNX Runtime / CTranslate2 CUDA)           │
│  部署：Jetson Orin Nano + Go2 Pro                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Key ROS2 Topics

**Voice chain**:

| Topic | Use |
|-------|------|
| `/event/speech_intent_recognized` | Speech intent recognition event (JSON) |
| `/asr_result` | ASR text output |
| `/tts` | TTS input text |
| `/webrtc_req` | Go2 WebRTC command |
| `/state/interaction/speech` | Speech state monitoring |

**Face chain**:

| Topic | Use |
|-------|------|
| `/state/perception/face` | Face tracking state (high-frequency) |
| `/event/face_identity` | Face identity event (conditional trigger) |

**System state**:

| Topic | Use |
|-------|------|
| `/state/executive/brain` | Brain decision state |

---

## 7. Team Division of Labor (updated 4/8 meeting)

### 7.1 Team Members

| Member | Role |
|------|------|
| Roy (Lu Po-yu) | Project lead / System Architect / Integration Owner |
| Wei Yu-tong | Frontend development |
| Huang Xu | Gesture/posture research → frontend → docs |
| Chen Ruo-en | Gesture/posture research → voice → docs |
| Dong Wei-feng | Supervising teacher / contact person |

### 7.2 Core Division-of-Labor Strategy

**Key principles**:
- Enable remote members without a robot dog or equipment to develop (using their own camera, at a height of ~30cm to simulate the Go2 viewpoint)
- The voice module is the most suitable to outsource: it runs entirely on cloud GPU and does not need the Go2 body
- After development, Roy integrates and migrates it to the Jetson

### 7.3 Per-Role Responsibilities (4/8 meeting version)

#### Roy — System Architect / Integration Owner

| Item | Notes |
|------|------|
| Face recognition | Handle cooldown, multi-person issues, accuracy tuning |
| Navigation obstacle avoidance | If there's a LiDAR, go all in (SLAM + basic movement) |
| PAI Docs website skeleton | Complete the Astro framework this weekend |
| Project document reinforcement | Expand background knowledge and system limitations (Claude Code assisted) |
| Action-trigger integration | After members decide gesture/posture–action mappings, Roy wires them to the Go2 |

#### Chen Ruo-en — Voice interaction enhancement

| Item | Notes |
|------|------|
| Voice interaction | Connect to the cloud GPU, improve conversation quality, increase answer length and intelligence |
| Plan B script | Design fixed-line Q&A |

#### Members (to be formally assigned at the 4/9 meeting)

| Item | Notes |
|------|------|
| Gesture recognition expansion | Each develops new gesture types and corresponding interaction behaviors using their own camera |
| Posture recognition expansion | Decide which postures to detect and the corresponding behaviors |
| Object recognition filtering | Determine which item categories to detect (COCO filtering for indoor scenarios) |
| Web UI improvement | Beautify the Studio status bar, enrich the feature pages |
| Project documentation | Each is responsible for the User Story and technical description of their module |

#### Huang Xu

| Item | Notes |
|------|------|
| Intro website frontend | Roy to confirm progress on 4/9 |
| Document writing | Each is responsible for their own chapter |

### 7.4 Document Chapter Division of Labor (finalized at 3/26 meeting; submit Ch1-5 before 4/13)

| Chapter | Content | Owner |
|------|------|--------|
| Ch1 | Project intro, background description | Joint (revising the existing version) |
| Ch2 | User Story, requirements analysis | Wei Yu-tong, Huang Xu |
| Ch3 | System architecture, technical details (hardware + models + each module) | Face+navigation+voice (Roy), object+posture (Wei Yu-tong/Huang Xu), gesture (Chen Ruo-en) |
| Ch4 | Problems and shortcomings, future outlook | Brief write-up |
| Ch5 | Contribution table, individual reflections | Each writes their own |

### 7.5 Division-of-Labor Timeline

- **4/9 (Thursday) 12:15 noon**: Teams meeting to formally announce the division of labor, demonstrating current results to Patrick (Teacher Dong)
- **Before 4/13**: each completes their assigned document chapter
- **After 4/13 – 5/18**: feature development sprint (gesture/posture/object/voice/LiDAR)

---

## 8. Demo and Acceptance

### 8.1 Demo Strategy (updated 4/8 meeting)

**Demonstration strategy**: visual interaction as the focus + web-based voice as an aid. The voice entry point moves from the Go2 microphone to the laptop/Studio.

| Demo | Name | Content | Success rate |
|:----:|------|------|:------:|
| A | Main-line closed loop | Person appears → recognition → greeting → voice conversation → Studio sync | >= 90% |
| B | Visual interaction | Gesture/posture/object + action | >= 70% |
| C | Studio showcase | One-click Demo + Chat + Live View + panels | >= 90% |
| D | Movement showcase (if LiDAR available) | After recognizing a person, walk straight over to interact | To be verified |

### 8.2 Demo Flow (4/8 version)

1. The robot powers on, the camera starts
2. Recognize the tester's face → greet (voice + action)
3. (If LiDAR available) the robot walks straight toward the tester
4. Conduct a voice conversation (laptop Studio capture): self-introduction, answer feature-related questions
5. Test gesture interaction: give a thumbs up → the robot responds with a happy action
6. Object recognition showcase: show a cup and other items, the robot says the item names
7. End the interaction: say "goodbye" → the robot waves goodbye

### 8.3 Demo Environment Requirements (4/8 meeting)

- **Sufficient lighting** (lights on), otherwise object recognition fails
- **Clean background**, to reduce clutter causing hallucination misjudgments
- Keep **only one person** within the camera's field of view, to avoid multi-person tracking confusion
- The presenter and the tester **stand in separate positions** (the presenter faces the audience, the robot faces the tester)
- It is recommended to **field-test in the classroom the week before the demo**

### 8.4 Demo Equipment Checklist

- Go2 Pro robot (with all installed equipment)
- Laptop (running PawAI Studio + microphone capture)
- Stable network connection (GPU cloud)
- Backup: Plan B script, recording evidence, GPU logs

### 8.5 Plan B Strategy (handling GPU cloud disconnection)

- Switch to fixed-line script mode to continue the demo
- Show a recording as evidence of the AI conversation feature
- If necessary, show GPU logs to prove it is genuinely a cloud issue and not fabrication
- Studio shows a connection-status indicator light, and the team decides in real time

---

## 9. Risks and Degradation Strategy

### 9.1 Four-Tier Degradation (voice + AI brain)

| Level | Name | Trigger condition | Behavior |
|:-----:|------|----------|------|
| 0 | Cloud full | Network normal | Qwen2.5-7B-Instruct full conversation + Studio full functionality |
| 1 | Local LLM | Cloud disconnected | Qwen2.5-0.8B basic conversation + simplified Studio |
| 2 | Rule mode | Jetson out of memory | Rule Intent + template replies + status display |
| 3 | Minimal floor | Extreme system pressure | Wake + ASR + fixed commands |

### 9.2 Hardware Risks (added 4/8)

| Risk | Severity | Notes | Mitigation |
|------|:------:|------|------|
| **Jetson power cut** | 🔴 | The XL4015 buck board repeatedly cuts power while the Go2 is running (8+ times) | Luck-dependent; minimize simultaneously running features during the demo |
| **GPU cloud disconnection** | 🔴 | The entire voice chain depends on the cloud, which disconnected twice yesterday | Plan B fixed lines + recording evidence |
| **Go2 fan noise** | 🟡 | ~20% recognition rate for the onboard microphone | Resolved: switched to Studio laptop capture |
| **Go2 falls while walking** | 🟡 | Has fallen multiple times after enabling navigation | Minimal movement scenario (straight-line short distance) |

### 9.3 Face Recognition Degradation

Face recognition is local-only, with no cloud dependency. The only risk is reducing the detection frequency when the Jetson is out of memory.

### 9.4 Safety Rules

- The `stop` command has the highest priority and can interrupt any skill
- The AI brain cannot directly control the Go2's low-level motion
- All actions must go through Safety Guard arbitration

---

## 10. Document Navigation

### 10.1 Document Map

> **NOTE** (updated 2026-03-13): Some paths in the document map below are outdated:
> - `vision.md`, `roadmap.md` — archived to `archive/mission/`, replaced by this document
> - `architecture/brain_v1.md` — file does not exist (ghost reference, to be created or removed)
> - `logs/` — archived to `archive/logs/`

```
docs/
├── mission/
│   ├── README.md              # ← 你正在這裡（入口頁）
│   ├── vision.md              # 專案願景
│   ├── roadmap.md             # 開發路線圖
│   └── meeting_notes_supplement.md
│
├── Pawai-studio/              # PawAI Studio 設計文件
│   ├── README.md              # 定位與目標
│   ├── system-architecture.md # 快/慢系統架構
│   ├── event-schema.md        # event/state/command/panel schema
│   ├── ui-orchestration.md    # Agent 動態面板設計
│   └── brain-adapter.md       # LLM 統一介面
│
├── architecture/
│   ├── interaction_contract.md  # 介面契約
│   └── brain_v1.md                 # 大腦架構設計
│
├── 人臉辨識/
│   └── README.md
│
├── 語音功能/
│   ├── README.md
│   └── jetson-MVP測試.md
│
├── 手勢辨識/
│   └── README.md
│
├── 辨識物體/
│   └── README.md
│
├── 導航避障/
│   └── README.md
│
└── setup/
    └── README.md
```

### 10.2 Quick Links

| Purpose | Link |
|------|------|
| PawAI Studio design | [Pawai-studio/README.md](../architecture/studio/README.md) |
| Interface contract spec | [interaction_contract.md](../contracts/interaction_contract.md) |
| Face recognition | [人臉辨識/README.md](../architecture/perception/face/README.md) |
| Voice | [語音功能/README.md](../architecture/speech/README.md) |
| Jetson MVP test | [語音功能/jetson-MVP測試.md](../architecture/speech/archive/jetson-MVP測試.md) |

---

## 11. Module Development SOP

> **Source**: 2026-03-15 voice-module 30-round acceptance, which stepped on 36 pitfalls (30 in the acceptance tooling, 6 in the voice main line). This SOP institutionalizes the lessons and applies to all modules.
>
> **Full design document**: `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-15-module-dev-sop-design.md`

### 11.1 Environment Sync Conventions

| # | Rule |
|---|------|
| 1 | Changes that need on-Jetson verification must be committed first; cross-machine sync or handover must be pushed |
| 2 | Directly editing code on the Jetson is forbidden (except emergency hotfixes); after a hotfix it must be committed back to the repo within 30 minutes |
| 3 | After `colcon build` you must `source install/setup.zsh` + restart the affected node |
| 4 | The Jetson side is fixed to zsh; if a script uses bash it must be self-consistent end to end, with no mixed source |
| 5 | Shell scripts that source the ROS2 setup do not use `set -u` by default |

> For solo fast iteration you can use main directly. When multiple agents run in parallel, each Builder uses a feature branch, merged by the Integrator (see §11.6).

### 11.2 Device Pre-flight Checks

**No build/test until it passes.**

**Core (all modules)**: ROS2 environment available, no unexpected residual nodes.
**Robot-dependent (voice, demo)**: Go2 connected + driver alive.
**Voice-specific**: PulseAudio stopped, microphone available, CUDA available.
**Face-specific**: D435 connected, YuNet model present.
**LLM-specific**: RTX server connected, vLLM healthy.

> See the SOP design document for full commands and pass conditions.

### 11.3 Cross-Node Coordination Design Principles

**General design rules:**
- **State** relies on a latched state topic
- **Events** rely on volatile + correlation id (session_id / track_id / request_id)
- **Control** relies on req/ack (the ack must carry back the request_id)
- **All cross-node contracts are registered in [`interaction_contract.md`](../contracts/interaction_contract.md) before implementation**

**Key principles**: a latched topic publishes its initial value at init; gate/mute must have timeout protection; adding a new intent/event type must synchronously update the shared constants.

### 11.4 Acceptance Tiers and Promotion Conditions

**Core rule: submodules rely on spec + smoke + review; only the integration main line runs YAML acceptance.**

| Tier | Applies to | Form | Pass standard |
|:----:|------|------|----------|
| **Level A** | A single module verifiable independently | spec + smoke test + code review | smoke all green + no blocking issue |
| **Level B** | Connected into the ROS2 main line, interacting with other nodes | YAML cases + automated decision + report | 10+ cases, key metrics meet thresholds |

**Promotion condition (A → B)**: Level A all green, and at least one of: the interface is relatively stable, or it starts affecting the demo main line. **When not met, do not spend time building Level B acceptance tooling.**

### 11.5 Module Integration Checklist

```
Level 1: Standalone → Level 2: Node-level → Level 3: System-level → Level 4: Demo-level
```

**In principle no level skipping; exceptions require recording the reason and risk.**

| Level | Key checklist |
|:----:|---------------|
| **L1** | Runnable on the target platform, has input/output definitions, smoke test all green, no hardcoded paths, code review passed |
| **L2** | Standard launch entry, topic registered in the contract, QoS conforms to §11.3, init publishes initial state, colcon build passes |
| **L3** | Multi-node coexistence, gate/ack has timeout, Level B acceptance, clean/start scripts, preflight coverage |
| **L4** | Demo flow document, 3 consecutive successful cold starts, memory budget confirmed, degradation strategy, pre-show SOP |

**Module integration level snapshot (updated 2026-03-18):**

| Module | Current level | Next step | Notes |
|------|:--------:|--------|------|
| Voice (STT/TTS/LLM Bridge) | Level 3 | Level 4 (Demo SOP + cold-start acceptance) | E2E demo recorded (5/6 rounds passed); "stop" eaten by Whisper hallucination, unstable VAD latency to fix |
| Face (YuNet/SFace) | Level 2 | Level 3 (integration test with voice) | ROS2 package scaffold complete, launch + config + tmux scripts ready |
| AI Brain (Cloud LLM) | Level 2 | Level 3 (multi-module event integration) | Qwen2.5-7B-Instruct on RTX 8000 (vLLM 0.17.1), Jetson E2E passed |
| PawAI Studio | Level 2 | Level 3 (frontend in development) | Mock Server + 4 panel routes + placeholder + spec handover complete |
| Gesture | Researching | Level 1 (solution decided, pending implementation) | README greatly expanded: MediaPipe vs RTMPose evaluation, D435 pitfalls, acceptance SOP; v2.1 gesture enum DEFERRED to 3/25 |
| Posture | Researching | Level 1 (solution decided, pending implementation) | README added 6 chapters: backup, 2D/3D selection, D435 depth, inference cost, minimal demo |

### 11.6 Multi-Agent Parallel Development Flow

| Role | Responsibility |
|------|------|
| **Architect** | Break the feature into submodule specs, define interface contracts, decide integration order |
| **Builder** (×N) | Each develops a submodule in a worktree, passing Level A. **Cannot change shared contracts on their own** |
| **Reviewer** | Code-review the Builders' output |
| **Integrator** | Merge to the main line, decide merge order and conflict priority |
| **Validator** | Run Level B acceptance on the integrated main line |

```
Architect: spec → 拆 N 子模組 → Dispatch N Builder（worktree）
  → Builder: 實作 → smoke → Reviewer → commit
  → Integrator: 按順序 merge
  → Validator: Level B 驗收 → 通過 → main
```

**Prerequisites**: the submodule interface spec is frozen, each Builder only touches their own file scope, and the shared schema is built by the Architect first.

### 11.7 Code Review Conventions

**Default checkpoint-based (fast)**: Builder finishes a chunk → code-reviewer → fix in place if it fails → commit on pass.

**Escalate to PR-based (strict)** conditions (any one): changing event/state/topic/schema, touching the integration branch or main, affecting multi-module interfaces, affecting the demo main line, or changing acceptance tooling or the deployment process (high-risk by default).

| Layer | Timing | Tool | Nature | Status |
|:-----:|------|------|------|:----:|
| 1 | Every Edit/Write | Project-level quick check (py_compile; frontend: eslint) | Automatic, blocking | Existing |
| 2 | Every chunk | code-reviewer agent | Manual, blocking | Existing |
| 3 | PR before integration | code-reviewer + codex/haiku | Formal, blocking | Existing |
| 4 | End of conversation | Stop hook (codex + haiku) | Supplementary opinion only, **not a merge gate** | Existing |

> **Target**: Layer 1 expanded with ruff + full-path eslint.

---

## Appendix: Key Decision Summary (v2.3)

| Decision item | Selected option | Rationale |
|----------|----------|----------|
| Main direction | Multimodal human-machine interaction + daily reminders | Combine LLM + AI recognition, with interactive exchange as the core |
| Voice architecture | **All-cloud main line** + local minimal floor | Local ASR/LLM quality is unusable (confirmed 4/8) |
| Voice entry | **Studio laptop microphone** | Go2 fan noise makes the onboard ASR unusable |
| ASR | SenseVoice Cloud (main line) → Whisper (fallback) | SenseVoice ~430ms, Whisper performs poorly on-device |
| Demo backup | **Plan B fixed-line script** | The cloud GPU is unstable; need a 0.x-second response backup |
| Face solution | Local-only YuNet + SFace | Already covers demo needs, never to the cloud |
| AI brain positioning | The system's central brain | Event understanding + skill dispatch + panel orchestration |
| Cloud main brain | Qwen2.5-7B-Instruct (vLLM) | Qwen3/3.5 abandoned (too smart and uncontrollable) |
| Local fallback | Qwen2.5-0.8B INT4 | **Extremely low IQ, completely unreliable** (confirmed 4/8) |
| Degradation strategy | Four-tier degradation + Plan B | Cloud → 0.8B → Rule → minimal floor → Plan B fixed lines |
| TTS | edge-tts (cloud, ~1s) + Piper (backup) | MeloTTS/ElevenLabs already retired |
| Object recognition | YOLO26n + TensorRT FP16 | Executive integration done, cup ✅ bottle ❌ |
| **Navigation obstacle avoidance** | **External LiDAR under evaluation** | D435 solution discontinued, RPLIDAR A2M12 candidate, finalized 4/14 |
| **Movement strategy** | **Straight-line short distance (minimum viable)** | After recognizing a person, walk straight over, no complex paths |
| Website strategy | Dual sites (Studio + Docs) | Same repo, deployed separately |
| Studio tech stack | Next.js 16 + FastAPI Gateway | On-device verified (4/7) |
| Docs tech stack | Astro + Starlight | Roy builds the skeleton this weekend |
| Action scope | P0-safe first | Prioritize "stable" over "cool" |
| Division-of-labor strategy | Roy integrates + members develop with their own cameras | Height 30cm to simulate the Go2 viewpoint |

---

## 12. Project Document Reinforcement Plan (added 4/8)

### 12.1 Current Status

- The document is currently about **46 pages**, while the historical average is **80-90 pages** — clearly on the short side
- Most of it is written by Roy (Claude Code assisted); other members' contributions contain errors to be corrected
- Many features do not yet have concrete content; sections like the User Story are too vague

### 12.2 Reinforcement Directions

| Item | Estimated pages added | Notes |
|------|:------------:|------|
| Background knowledge expansion | 10-15 pages | Detailed introductions to MediaPipe, YuNet/SFace, YOLO, Qwen, ROS2, etc. |
| System limitation description | 5-10 pages | Go2 Pro hardware limitations, LiDAR issues, development difficulties, power issues |
| Previous failed attempts | 5 pages | Abandoned solutions like YOLOWorld, MeloTTS, local Whisper, D435 obstacle avoidance |
| Feature details | Depends on division of labor | Concrete designs for the gesture, posture, object, and voice modules (members add their own) |
| Navigation obstacle avoidance (if LiDAR available) | 5-10 pages | Add the technical solution and implementation description |
| **Target** | **60-70+ pages** | Narrow the gap with other groups |

### 12.3 Writing Method

- **Claude Code assisted expansion**: read the PAI project documents on GitHub and auto-generate detailed content
- Each member supplements the documentation for their own module
- **Submit on 4/13 (Sunday)**: submitting files, not links; cannot be modified after submission

---

*Last updated: 2026-04-08*
*Maintainer: System Architect*
*Status: v2.3 (+4/8 meeting updates: all hardware installed, voice moved to Studio, navigation LiDAR evaluation, major division-of-labor change, document reinforcement)*
