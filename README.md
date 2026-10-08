<div align="center">

<img src="docs/assets/logo.png" alt="PawAI logo" width="220">

# 🐾 PawAI — Home Companion Robot Dog

**English** | [中文](./README.zh.md)

*A multimodal, embodied-interaction robot dog built on the Unitree Go2 Pro.*

[![ROS2](https://img.shields.io/badge/ROS2-Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/humble/)
[![Python](https://img.shields.io/badge/python-3.10-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/edge-Jetson%20Orin%20Nano-76B900?logo=nvidia&logoColor=white)](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)
[![Robot](https://img.shields.io/badge/robot-Unitree%20Go2%20Pro-orange.svg)](https://www.unitree.com/go2)
[![Architecture](https://img.shields.io/badge/architecture-Clean-brightgreen.svg)](#-architecture)
[![License](https://img.shields.io/badge/license-BSD--2-yellow.svg)](./LICENSE)

</div>

> **PawAI sees, understands, decides and acts.** It recognises familiar faces,
> reads hand gestures and body posture, understands spoken language, detects
> everyday objects, and responds safely with voice, motion and navigation —
> all orchestrated on the edge by a three-layer decision engine
> (**Safety → Policy → Expression**).

PawAI is not a chatbot, and not a pile of disconnected demos. It is an
**embodied interaction loop** — *See → Understand → Decide → Act* — running on a
Unitree Go2 Pro with an NVIDIA Jetson Orin Nano. The codebase follows
**Clean Architecture**: perception, decision and driver layers are cleanly
separated with a single, unidirectional dependency direction.

<div align="center">

### 🎬 Demo

<a href="https://youtu.be/rTVchCmYQuw">
  <img src="docs/assets/pawai-hardware-overview.jpg" width="640" alt="Watch the PawAI demo on YouTube">
</a>

▶️ **[Watch on YouTube — IM4308: PawAI · multimodal-fusion autonomous object-finding &amp; embodied interaction](https://youtu.be/rTVchCmYQuw)**

</div>

---

## ✨ Highlights

| Capability | What it does | Stack |
|------------|--------------|-------|
| 👤 **Face** | Greets known people, flags strangers | YuNet + SFace + IOU tracking (local, < 30 ms) |
| ✋ **Gesture** | 7 gestures → actions, OK as confirm | MediaPipe Gesture Recognizer / RTMPose |
| 🧍 **Pose** | Sit / crouch / fall cues | MediaPipe Pose |
| 🥤 **Object** | 80-class detection + 3D position | YOLO26n ONNX + D435 depth |
| 🗣️ **Speech** | ASR → LLM intent → TTS reply | SenseVoice / Whisper · LangGraph · Gemini / edge-tts / Piper |
| 🧠 **Brain** | Persona + skill policy + safety gate | LangGraph decision engine |
| 🧭 **Navigation** *(experimental)* | Relative goals, routes, reactive stop | RPLIDAR + Nav2 + AMCL + D435 safety stop |

---

## 📄 Paper & Evaluated Version

This repository is the reference implementation of the manuscript *"A Multimodal Quadruped Robot with Hybrid Edge–Cloud Deployment and Deterministic LLM Skill Arbitration"* (P.-Y. Lu and W.-F. Tung, *IEEE Access*, under review).

- **Evaluated code:** commit [`81e5018`](https://github.com/roy4222/PawAI/tree/81e50185d82caa52ccee8652ab97e0e4d7db6605) (`81e50185d82caa52ccee8652ab97e0e4d7db6605`). Release [`ieee-access-2026`](https://github.com/roy4222/PawAI/tree/ieee-access-2026) adds documentation only (this section, `docs/paper/`, `CITATION.cff`); its code is identical to 81e5018. To reproduce the paper, `git checkout ieee-access-2026`.
- `main` keeps evolving after that commit; later changes are not covered by the paper's evaluation.
- The configuration evaluated in the paper differs from the defaults described in this README (for example, the LLM chain, the single-tier speech recognition, and the 7 object classes). See **[docs/paper/](docs/paper/README.md)** for the evaluated configuration, a map from the paper's terms and sections to source files, and the differences from this README.
- Evaluation harness, utterance bank, injected cases, analysis scripts, and per-run summaries: [roy4222/pawai-ieee-access-artifacts](https://github.com/roy4222/pawai-ieee-access-artifacts).

## 🔖 Citation

If you use PawAI, please cite the paper (details will be updated after review):

```bibtex
@article{lu2026pawai,
  author  = {Lu, Po-Yu and Tung, Wei-Feng},
  title   = {A Multimodal Quadruped Robot with Hybrid Edge--Cloud Deployment and Deterministic {LLM} Skill Arbitration},
  journal = {IEEE Access},
  year    = {2026},
  note    = {[under review]}
}
```

A machine-readable [`CITATION.cff`](CITATION.cff) is provided (GitHub's "Cite this repository").

## 🗂️ Repository Layout

| Path | What it is |
|---|---|
| `face_perception/`, `vision_perception/`, `object_perception/` | ROS 2 perception packages (face identity, gesture and pose, object detection) |
| `speech_processor/` | ROS 2 speech package (speech-intent node, TTS node, intent classifier) |
| `pawai_brain/` | LangGraph conversation graph that produces dialogue candidates (the paper's *dialogue graph*) |
| `interaction_executive/` | `brain_node` (the paper's *dialogue manager*), the interaction executive, safety layer, world state, skill queue |
| `pawai_contracts/` | Shared contracts: skill registry, LLM policy, trace schema |
| `go2_robot_sdk/`, `go2_interfaces/` | Go2 WebRTC driver (fork of go2_ros2_sdk, Apache-2.0), depth-safety and reactive-stop nodes |
| `nav_capability/` | Experimental navigation capability (not part of the paper's evaluation) |
| `pawai-studio/` | PawAI Studio web console: frontend and gateway (speech, traces, offline mode) |
| `scripts/` | Startup scripts (e.g., `start_full_demo_tmux.sh`) and the remote ASR server `sensevoice_server.py` |
| `config/`, `foxglove/` | Deployment configuration templates and Foxglove layouts |
| `tools/pawai_cli/`, `benchmarks/`, `tests/` | Operator CLI, model benchmarks, on-device verification |
| `docs/` | Architecture, contracts, runbooks, ADRs; `docs/paper/` for paper readers; `docs/deliverables/` holds course deliverables (Chinese) |
| `archive/` | Retired code, excluded from the build (`COLCON_IGNORE`) |
| `.claude/`, `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `references/`, `docs/agents/` | Working rules for AI coding agents; not needed to build or run PawAI |
| `logs/`, `test_results/`, `test_scripts/` | Runtime output locations and ad-hoc test inputs |

---

## 🏗️ Architecture

PawAI is a single ROS2 workspace of **10 focused packages**, layered so that
dependencies only ever point *inward* toward the shared contracts.

```mermaid
flowchart TD
    subgraph Perception["👁️ Perception Layer"]
        FACE[face_perception]
        VISION[vision_perception<br/>gesture · pose]
        OBJ[object_perception]
        SPEECH_IN[speech_processor<br/>ASR · intent]
    end

    subgraph Decision["🧠 Decision Layer"]
        BRAIN[pawai_brain<br/>LangGraph engine]
        EXEC[interaction_executive<br/>ISM · safety gate · single action arbiter]
    end

    subgraph Action["🦿 Action Layer"]
        SPEECH_OUT[speech_processor<br/>TTS]
        DRIVER[go2_robot_sdk<br/>WebRTC driver · reactive stop]
        NAV[nav_capability]
    end

    subgraph Contracts["📜 Shared Contracts"]
        IFACE[go2_interfaces<br/>msg · srv · action]
        PCON[pawai_contracts<br/>skill registry · policy · trace schema]
    end

    Perception --> Decision --> Action
    Decision -. depends on .-> Contracts
    Action -. depends on .-> Contracts
    Perception -. depends on .-> Contracts
```

> **One rule, strictly enforced:** `interaction_executive` is the *only* exit
> to the robot's body. `pawai_brain` proposes; the executive disposes (safety
> gate first). The two never import each other — both depend only on
> `pawai_contracts`.

<div align="center">

**System**

<img src="docs/assets/architecture-system.png" alt="PawAI system architecture" width="820">

**PawAI Brain**

<img src="docs/assets/architecture-brain.png" alt="PawAI Brain architecture" width="820">

**PawAI Studio**

<img src="docs/assets/architecture-studio.png" alt="PawAI Studio architecture" width="820">

</div>

### Packages

| Package | Layer | Responsibility |
|---------|-------|----------------|
| [`go2_interfaces`](go2_interfaces/) | Contracts | ROS2 message / service / action definitions for the Go2 |
| [`pawai_contracts`](pawai_contracts/) | Contracts | ROS-free domain contracts: skill registry, LLM policy, trace schema |
| [`go2_robot_sdk`](go2_robot_sdk/) | Driver | Go2 WebRTC driver (Clean Arch: domain / application / infrastructure / presentation), reactive safety stop |
| [`face_perception`](face_perception/) | Perception | Face detection + identity recognition + tracking |
| [`vision_perception`](vision_perception/) | Perception | Hand-gesture and body-pose recognition |
| [`object_perception`](object_perception/) | Perception | YOLO26n object detection with 3D positioning |
| [`speech_processor`](speech_processor/) | Speech I/O | ASR, intent, LLM bridge, TTS |
| [`pawai_brain`](pawai_brain/) | Decision | LangGraph conversation / decision engine + persona |
| [`interaction_executive`](interaction_executive/) | Decision | State machine, safety gate, single action arbiter |
| [`nav_capability`](nav_capability/) | Capability | Relative-goal / route navigation actions *(experimental, HITL)* |

---

## 🤖 Hardware

PawAI can be brought up in layers. You do **not** need every peripheral to run
the base Go2 driver, but the full multimodal demo expects the full kit.

| Bring-up goal | Required hardware |
|---------------|-------------------|
| **Minimal Go2 driver** | Unitree **Go2 Pro** + Ubuntu 22.04 / ROS2 Humble machine on the Go2 network |
| **Full PawAI interaction demo** | Go2 Pro + NVIDIA **Jetson Orin Nano Super 8 GB** + Intel RealSense **D435** + USB microphone + USB speaker |
| **Object / depth perception** | Intel RealSense **D435** mounted rigidly on the robot or test rig |
| **Experimental navigation** | **RPLIDAR A2M12** + stable mount + external power budget + human-in-the-loop safety observer |
| **Operator UI** | A laptop or desktop browser connected to PawAI Studio |

Accessory checklist for a practical Go2 Pro setup:

- USB 3 cable and mount for the D435.
- USB microphone and speaker, or an equivalent Go2 audio path.
- Reliable 5 V power and mounting for the RPLIDAR if navigation experiments are enabled.
- A development machine for editing plus a Jetson for ROS2 runtime, GPU inference and robot I/O.

---

## 📋 System Requirements

| System | ROS2 distro |
|--------|-------------|
| Ubuntu 22.04 (Jetson / x86) | Humble |

---

## 🧭 New User Path

1. Start with the **Minimal Go2 driver** path and confirm WebRTC control works.
2. Add the **D435** and run face / object / pose perception independently.
3. Add speech and TTS after the camera pipeline is stable.
4. Start PawAI Studio and the full multimodal demo only after the individual lanes pass.
5. Treat navigation as experimental: run it only with a safety observer and clear stop procedure.

---

## ⚙️ Installation

```bash
# Clone into a colcon workspace (this repo root *is* the workspace src)
git clone --recurse-submodules https://github.com/roy4222/PawAI.git src
cd src

# Python deps (project uses uv)
uv pip install -r requirements.txt          # add requirements-jetson.txt on the Jetson

# Build
source /opt/ros/humble/setup.bash           # use setup.zsh on the Jetson
colcon build
source install/setup.bash
```

---

## 🚀 Quick Start

```bash
# Minimal Go2 driver
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false

# Speech + LLM end-to-end (one-shot tmux)
bash scripts/start_llm_e2e_tmux.sh

# Full multimodal demo (perception + brain + Studio)
bash scripts/start_full_demo_tmux.sh

# Face-recognition pipeline
bash scripts/start_face_identity_tmux.sh
```

See [`CLAUDE.md`](CLAUDE.md) for the full build / run matrix and known pitfalls,
and [`docs/runbook/`](docs/runbook/README.md) for demo operation SOPs.

---

## 🛟 Reliability — Graceful Degradation

Every cloud-first capability falls back to a local path, so a demo never goes
dark:

| Stage | Primary | Fallback 1 | Fallback 2 |
|-------|---------|-----------|-----------|
| **LLM** | OpenRouter (Gemini / GPT-mini) | local Qwen | RuleBrain |
| **TTS** | Gemini Flash TTS | edge-tts | Piper (offline) |
| **ASR** | SenseVoice cloud | SenseVoice local | faster-whisper local |

---

## 🖥️ PawAI Studio

An operator web UI (a "ChatGPT-style console meets AI Foxglove") for driving and
observing the robot.

```bash
bash pawai-studio/start.sh      # → http://localhost:3000/studio
```

---

## 📚 Documentation

| Area | Entry point |
|------|-------------|
| Project mission & demo scope | [`docs/mission/`](docs/mission/README.md) |
| ROS2 interface contracts | [`docs/contracts/`](docs/contracts/interaction_contract.md) |
| Brain / perception / speech / studio | [`docs/architecture/`](docs/architecture/README.md) |
| Navigation & obstacle avoidance | [`docs/architecture/navigation/`](docs/architecture/navigation/README.md) |
| Operation runbooks (demo SOPs) | [`docs/runbook/`](docs/runbook/README.md) |
| Architecture decisions (ADRs) | [`docs/adr/`](docs/adr/README.md) |

Internal historical docs are intentionally omitted from the public tree;
deprecated packages and scripts live under [`archive/`](archive/README.md).

---

## 🙏 Built on go2_ros2_sdk

PawAI began as a fork of [**abizovnuralem/go2_ros2_sdk**](https://github.com/abizovnuralem/go2_ros2_sdk)
— the excellent ROS2 / WebRTC integration for the Unitree Go2 by
[@abizovnuralem](https://github.com/abizovnuralem) and [@tfoldi](https://github.com/tfoldi).
The `go2_robot_sdk`, `go2_interfaces` and driver layers descend from that work;
PawAI adds the perception, brain, speech, navigation and Studio layers on top.

> 🧭 *Future work:* containerised deployment (`docker/`) and a documentation
> website are planned but not yet shipped.

---

## License

[BSD 2-Clause](./LICENSE) — inherited from the upstream `go2_ros2_sdk` project.
