# PawAI for paper readers

This page is the entry point for readers of the manuscript

> P.-Y. Lu and W.-F. Tung, "A Multimodal Quadruped Robot with Hybrid Edge–Cloud Deployment and Deterministic LLM Skill Arbitration," *IEEE Access* [under review].

**Evaluated code = commit `81e50185d82caa52ccee8652ab97e0e4d7db6605` (81e5018); release `ieee-access-2026` adds documentation only** (the paper section of the top-level README, this `docs/paper/` folder, and `CITATION.cff`); no source, launch, or configuration file differs from 81e5018. All links below are permanent links to 81e5018; line numbers refer to it. `main` continues to change after the release.

**Evaluation artifacts** (measurement harness, utterance bank, injected cases, analysis and plotting scripts, per-run summaries behind Tables VII–XVI and Figs. 6–15): [roy4222/pawai-ieee-access-artifacts](https://github.com/roy4222/pawai-ieee-access-artifacts).

Contents: [1. Terminology](#1-terminology) · [2. Section-to-code map](#2-section-to-code-map) · [3. Evaluated configuration](#3-evaluated-configuration) · [4. Differences from the top-level README](#4-differences-from-the-top-level-readme) · [5. Known gaps stated in the paper](#5-known-gaps-stated-in-the-paper) · [中文摘要](#中文摘要)

## 1. Terminology

The paper uses functional names; the code uses historical package and node names.

| Paper term | Name in the code | Location |
|---|---|---|
| dialogue graph | LangGraph conversation graph in package `pawai_brain` | [`pawai_brain/pawai_brain/graph.py#L44`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/graph.py#L44), [`conversation_graph_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/conversation_graph_node.py) |
| dialogue manager | **`brain_node`, in package `interaction_executive`** (not in `pawai_brain`) | [`interaction_executive/interaction_executive/brain_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/brain_node.py) |
| executive | `interaction_executive_node` | [`interaction_executive_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/interaction_executive_node.py) |
| skill registry | `SKILL_REGISTRY`, `PriorityClass` | [`pawai_contracts/pawai_contracts/skill_contract.py#L155`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/skill_contract.py#L155), [`#L29`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/skill_contract.py#L29) |
| LLM mode (execute / confirm / trace only) | `LLM_PROPOSABLE_SKILLS`, `LLM_PROPOSAL_EXECUTE` | [`pawai_contracts/pawai_contracts/llm_policy.py#L10`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/llm_policy.py#L10), [`#L21`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/llm_policy.py#L21) |
| rule-based responder | RuleBrain (`rule_fallback`) | [`pawai_brain/pawai_brain/rule_fallback.py#L55`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/rule_fallback.py#L55) |
| console, inspection tool | PawAI Studio (frontend and gateway) | [`pawai-studio/gateway/studio_gateway.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai-studio/gateway/studio_gateway.py), `pawai-studio/frontend/` |
| interaction core | `brain_node` + conversation graph + executive together | (no single folder) |

**Two different "three layers".** The paper's *three arbitration layers* are (1) normalization and blocked marking in the dialogue graph's policy gate, (2) the dialogue manager's checks on LLM skill suggestions, and (3) the executive's safety layer (Algorithm 1); see Section 2, IV-B. The top-level README's *three-layer decision engine (Safety → Policy → Expression)* ([`README.md#L23-L24`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/README.md#L23-L24), [`CONTEXT.md#L16`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/CONTEXT.md#L16)) describes the design layers of the robot's behavior logic as a whole. They are not the same decomposition: the paper's layers are the places where an LLM suggestion is checked on its way to the robot.

## 2. Section-to-code map

| Paper | Component | Location |
|---|---|---|
| III-A | Go2 WebRTC driver (fork of go2_ros2_sdk) | `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/`, [`presentation/go2_driver_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py), [`launch/robot.launch.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/go2_robot_sdk/launch/robot.launch.py) |
| III-A | Console gateway on the Jetson | [`pawai-studio/gateway/studio_gateway.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai-studio/gateway/studio_gateway.py) |
| III-B | D435 at 640×480, 15 fps | [`scripts/start_full_demo_tmux.sh#L147-L149`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/start_full_demo_tmux.sh#L147-L149) |
| III-B | YuNet + SFace | [`face_perception/face_perception/face_identity_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/face_perception/face_perception/face_identity_node.py), [`face_perception/config/face_perception.yaml`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/face_perception/config/face_perception.yaml) |
| III-B | MediaPipe gesture and pose | [`vision_perception/vision_perception/gesture_recognizer_backend.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/vision_perception/vision_perception/gesture_recognizer_backend.py), [`mediapipe_pose.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/vision_perception/vision_perception/mediapipe_pose.py), [`vision_perception_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/vision_perception/vision_perception/vision_perception_node.py) |
| III-B | YOLO26n, ONNX Runtime TensorRT EP FP16, 7 classes | [`object_perception/object_perception/object_perception_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/object_perception/object_perception/object_perception_node.py); class list [`object_perception/config/object_perception.yaml#L21`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/object_perception/config/object_perception.yaml#L21) |
| III-B | Depth-safety flag (central ROI, fail-closed) | [`go2_robot_sdk/go2_robot_sdk/depth_safety_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/go2_robot_sdk/go2_robot_sdk/depth_safety_node.py), [`depth_geometry.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/go2_robot_sdk/go2_robot_sdk/depth_geometry.py) |
| III-C | Remote SenseVoiceSmall server (FastAPI) | [`scripts/sensevoice_server.py#L62`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/sensevoice_server.py#L62) |
| III-C | Gateway ASR client (5-s timeout) | [`pawai-studio/gateway/asr_client.py#L49`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai-studio/gateway/asr_client.py#L49) |
| III-C | Keyword intents | [`speech_processor/speech_processor/intent_classifier.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/speech_processor/speech_processor/intent_classifier.py) |
| III-C | Two TTS lanes (12-unit threshold, stop/caution keywords) | [`speech_processor/speech_processor/tts_node.py#L773-L779`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/speech_processor/speech_processor/tts_node.py#L773-L779) |
| III-C | edge-tts / Gemini TTS / Piper providers | [`speech_processor/speech_processor/tts_node.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/speech_processor/speech_processor/tts_node.py), [`tts_provider.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/speech_processor/speech_processor/tts_provider.py) |
| III-D | LLM chain, 4-s / 5-s budget, 0.3-s rule | [`pawai_brain/pawai_brain/llm_client.py#L57-L60`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/llm_client.py#L57-L60), [`#L109-L122`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/llm_client.py#L109-L122) |
| III-D | JSON validation → rule-based responder | [`pawai_brain/pawai_brain/nodes/json_validator.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/nodes/json_validator.py), [`rule_fallback.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/rule_fallback.py) |
| III-D | No candidate within 5.5 s → canned reply | `chat_wait_ms: 5500` in [`interaction_executive/config/executive.yaml#L11`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/config/executive.yaml#L11) (the node default in `brain_node.py#L809` is 1500; the launch file loads the YAML) |
| III-D | Offline mode (parameter or console) | [`brain_node.py#L173`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/brain_node.py#L173), [`#L354-L359`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/brain_node.py#L354-L359), [`studio_gateway.py#L280`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai-studio/gateway/studio_gateway.py#L280) |
| III-E | Reactive-stop node | [`go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py#L67-L94`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py#L67-L94) (parameter values: see Section 3) |
| III-E | Arbitration subscribes to the LiDAR status | [`interaction_executive/interaction_executive/world_state.py#L53`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/world_state.py#L53), [`#L92`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/world_state.py#L92) |
| IV-A | LLM reply schema | [`pawai_brain/pawai_brain/schemas.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/schemas.py) |
| IV-A | Table III skills, classes, cooldowns | [`skill_contract.py#L155`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/skill_contract.py#L155), [`llm_policy.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/llm_policy.py) |
| IV-B layer 1 | Normalization, blocked marking | [`pawai_brain/pawai_brain/nodes/skill_policy_gate.py#L70-L88`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/nodes/skill_policy_gate.py#L70-L88) |
| IV-B layer 2 | Allowlist, mode | [`brain_node.py#L1700`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/brain_node.py#L1700), [`#L1740`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/brain_node.py#L1740) |
| IV-B layer 2 | OK-gesture confirmation (30 s) | [`brain_node.py#L265`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/brain_node.py#L265), [`pending_confirm.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/pending_confirm.py) |
| IV-B layer 3 | Algorithm 1 (safety layer) | [`interaction_executive/interaction_executive/safety_layer.py#L87-L97`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/safety_layer.py#L87-L97) |
| IV-B layer 3 | MotionMap, BannedAPIs | [`skill_contract.py#L110`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/skill_contract.py#L110), [`#L134`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/skill_contract.py#L134) |
| IV-B layer 3 | World state; `depth_clear` defaults to false | [`world_state.py#L37`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/world_state.py#L37) |
| IV-B | Queue and preemption | [`interaction_executive/interaction_executive/skill_queue.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/skill_queue.py) |
| IV-C | Trace events | [`pawai_contracts/pawai_contracts/trace_schema.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_contracts/pawai_contracts/trace_schema.py), [`pawai_brain/pawai_brain/nodes/trace_emitter.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai_brain/pawai_brain/nodes/trace_emitter.py) |
| IV-C | Console stores traces as JSON Lines | [`pawai-studio/gateway/trace_store.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai-studio/gateway/trace_store.py) |
| V-B | Startup of the interaction stack | [`scripts/start_full_demo_tmux.sh`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/start_full_demo_tmux.sh) |
| V-B | Qwen2.5-7B on the remote server (vLLM) | not in this repository (server-side setup) |
| VI | Harness, bank, cases, analysis, summaries | [pawai-ieee-access-artifacts](https://github.com/roy4222/pawai-ieee-access-artifacts) |

Hardware, firmware (Go2 v1.1.7), JetPack 6.2, and the full software-version list of Tables IV–V are given in the paper; `requirements-jetson.txt` pins only part of them.

## 3. Evaluated configuration

Some values used in the paper come from startup scripts or YAML files, not from node defaults. A reader who only looks at a node's `declare_parameter` defaults will see different numbers.

| What | Value in the paper | Where it is set | Node default |
|---|---|---|---|
| Interaction stack | — | `scripts/start_full_demo_tmux.sh` (driver, camera, perception, executive, speech, TTS, conversation graph, gateway) | — |
| On-board speech recognition | stopped after startup (`stt_intent_node`) | the measurement harness kills the `demo:asr` tmux window after `start_full_demo_tmux.sh` | — |
| Speech recognition path | console microphone → gateway → remote SenseVoiceSmall; single tier, no fallback | [`asr_client.py#L49`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/pawai-studio/gateway/asr_client.py#L49), [`scripts/sensevoice_server.py`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/sensevoice_server.py) | — |
| LLM chain | GPT-5.4 mini → Gemini 3 Flash → rule-based | [`start_full_demo_tmux.sh#L56-L57`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/start_full_demo_tmux.sh#L56-L57), [`#L229-L235`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/start_full_demo_tmux.sh#L229-L235) (`openrouter_gemini_model` is the primary slot, `openrouter_deepseek_model` the backup slot; the names are historical) | same models in `llm_client.py#L57-L58` |
| LLM budget | 4 s primary, 5 s overall, max 2,000 output tokens | `start_full_demo_tmux.sh#L232-L234` | 4 s / 5 s / 500 tokens |
| Wait for a dialogue candidate | 5.5 s | `interaction_executive/config/executive.yaml#L11` | 1,500 ms |
| Object classes | 7 (bottle, cup, bowl, chair, laptop, cell phone, book) | `object_perception/config/object_perception.yaml#L21` | all 80 COCO classes |
| Camera | 640×480 at 15 fps | `start_full_demo_tmux.sh#L147-L149` | — |
| LiDAR configuration | scanner driver + reactive-stop node with its control loop disabled | `scripts/start_lidar_monitor_tmux.sh` (scanner and TF only) plus the reactive-stop command line of [`scripts/start_reactive_forward_demo.sh#L80`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/scripts/start_reactive_forward_demo.sh#L80) with `enable:=false` (the measurement harness runs this command from `harness/jetson/reactive_window.sh` in the artifacts repository) | — |
| Reactive stop | ±18° sector, stop below 1.5 m, 1.8-m slow zone at the same speed | `start_reactive_forward_demo.sh#L37`, `#L80` (`front_arc_deg:=18`, `danger_distance_m:=1.5`, `slow_distance_m:=1.8`) | 30°, 1.1 m, 1.7 m |
| Cloud failures (Section VI-D) | invalid model or voice name, 0.05-s request timeout, remote recognizer stopped, offline mode via the console API | startup parameters of the conversation-graph and TTS nodes; see the artifacts repository (`harness/pawexp/faults.py`) | — |

The exact commands the measurement harness sent to the robot are in the artifacts repository (`harness/pawexp/ops.py`, `harness/jetson/*.sh`).

## 4. Differences from the top-level README

The top-level README describes the product and its optional components. The paper evaluates one configuration (Table II of the paper). Where they differ:

| Topic | Top-level README | Paper (evaluated configuration) |
|---|---|---|
| LLM fallback | OpenRouter → local Qwen → RuleBrain (Reliability table) | GPT-5.4 mini → Gemini 3 Flash → rule-based responder; local and remote open models were only benchmarked (Tables IX and XIV) |
| Speech recognition | SenseVoice cloud → SenseVoice local → faster-whisper | Remote SenseVoiceSmall only; the on-board node is stopped, so there is no fallback |
| Object detection | 80-class detection | 7 household classes (`object_perception.yaml#L21`) |
| "Three layers" | Safety → Policy → Expression decision engine | Three arbitration layers (policy gate → dialogue manager → safety layer); see Section 1 |

## 5. Known gaps stated in the paper

These are disclosed in the paper; they are listed here so that readers of the code do not mistake them for new findings.

- The arbitration layer subscribes to the reactive-stop status topic, but the fields it reads are not present in the published message, so the LiDAR state never reaches arbitration ([`world_state.py#L92`](https://github.com/roy4222/PawAI/blob/81e50185d82caa52ccee8652ab97e0e4d7db6605/interaction_executive/interaction_executive/world_state.py#L92)).
- Network loss is not detected automatically; offline mode is switched by an operator, and it affects dialogue only.
- Some early-exit paths do not yet emit trace events, and timer-driven fallbacks can be mis-attributed (Section IV-C of the paper; Table XII quantifies trace coverage).
- The executive reports a motion step as successful about 0.5 s after publishing the Sport API request; it receives no acknowledgement from the robot (Section VI-E).

---

## 中文摘要

- 本頁對應論文第 III–V 章。**評估的程式碼 = commit `81e5018`；release `ieee-access-2026` 只新增文件**（README 論文段、`docs/paper/`、`CITATION.cff`），程式碼與 81e5018 相同；上方所有連結都固定在 81e5018。
- **名稱落差：** 論文的 dialogue manager 是 `interaction_executive` 套件裡的 `brain_node.py`，不在 `pawai_brain`；dialogue graph 才是 `pawai_brain` 的 LangGraph。
- **兩種「三層」：** 論文的三層仲裁＝對話圖的 policy gate → dialogue manager 的 LLM 提案檢查 → executive 的 safety layer；README 的「Safety → Policy → Expression」是整體行為邏輯的設計分層，兩者不是同一件事。
- **評估組態不在節點預設值：** reactive-stop 的 ±18°／1.5 m／1.8 m 來自 `scripts/start_reactive_forward_demo.sh`（節點預設 30°／1.1 m／1.7 m）；5.5 s 等候來自 `executive.yaml`（節點預設 1.5 s）；物件 7 類來自 `object_perception.yaml`（節點預設 80 類）；LLM 模型與 2,000 tokens 來自 `start_full_demo_tmux.sh`。
- **與 README 的差異：** README 的 LLM 本地 Qwen 備援、ASR 三層、物件 80 類是其他組態；論文評估是 GPT-5.4 mini → Gemini 3 Flash → 規則式、ASR 單層無備援、物件 7 類。
- 評估工具、句庫、案例、分析腳本與彙整數據在 [pawai-ieee-access-artifacts](https://github.com/roy4222/pawai-ieee-access-artifacts)。
