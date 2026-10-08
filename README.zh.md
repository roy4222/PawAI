<div align="center">

<img src="docs/assets/logo.png" alt="PawAI logo" width="220">

# 🐾 PawAI — 居家互動機器狗

[English](./README.md) | **中文**

*以 Unitree Go2 Pro 為載體的多模態具身互動機器狗。*

[![ROS2](https://img.shields.io/badge/ROS2-Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/en/humble/)
[![Python](https://img.shields.io/badge/python-3.10-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/edge-Jetson%20Orin%20Nano-76B900?logo=nvidia&logoColor=white)](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/)
[![Robot](https://img.shields.io/badge/robot-Unitree%20Go2%20Pro-orange.svg)](https://www.unitree.com/go2)
[![Architecture](https://img.shields.io/badge/architecture-Clean-brightgreen.svg)](#-架構)
[![License](https://img.shields.io/badge/license-BSD--2-yellow.svg)](./LICENSE)

</div>

> **PawAI 看得懂、聽得懂、會決策、能行動。** 它認得熟人、讀手勢與姿勢、聽懂語音、
> 辨識日常物體，並透過三層決策引擎（**Safety → Policy → Expression**）在邊緣端
> 安全地以語音、動作與導航回應。

PawAI 不是聊天機器人，也不是各功能分開展示的辨識系統，而是一條
**具身互動迴路**——*看懂 → 理解 → 決策 → 行動*——跑在 Unitree Go2 Pro ＋
NVIDIA Jetson Orin Nano 上。整個程式庫遵循 **Clean Architecture**：感知、決策、
驅動三層清楚分離、依賴單向。

<div align="center">

### 🎬 Demo 影片

<a href="https://youtu.be/rTVchCmYQuw">
  <img src="docs/assets/pawai-hardware-overview.jpg" width="640" alt="在 YouTube 觀看 PawAI demo">
</a>

▶️ **[YouTube 觀看 — IM4308：PawAI · 基於多模態感知融合之自主尋物與具身互動](https://youtu.be/rTVchCmYQuw)**

</div>

---

## ✨ 核心能力

| 能力 | 做什麼 | 技術 |
|------|--------|------|
| 👤 **人臉** | 認熟人打招呼、陌生人警示 | YuNet + SFace + IOU 追蹤（本地 < 30 ms） |
| ✋ **手勢** | 7 種手勢 → 動作，OK 二次確認 | MediaPipe Gesture Recognizer / RTMPose |
| 🧍 **姿勢** | 坐下 / 彎腰 / 跌倒提示 | MediaPipe Pose |
| 🥤 **物體** | 80 類偵測 + 3D 座標 | YOLO26n ONNX + D435 深度 |
| 🗣️ **語音** | ASR → LLM 意圖 → TTS 回覆 | SenseVoice / Whisper · LangGraph · Gemini / edge-tts / Piper |
| 🧠 **大腦** | 人格 + 技能策略 + 安全閘 | LangGraph 決策引擎 |
| 🧭 **導航**（實驗性） | 相對目標、路線、反應式停障 | RPLIDAR + Nav2 + AMCL + D435 安全停 |

---

## 📄 論文與評估版本

本 repo 是論文〈*A Multimodal Quadruped Robot with Hybrid Edge–Cloud Deployment and Deterministic LLM Skill Arbitration*〉（P.-Y. Lu、W.-F. Tung，*IEEE Access*，審查中）的參考實作。

- **評估的程式碼：** commit [`81e5018`](https://github.com/roy4222/PawAI/tree/81e50185d82caa52ccee8652ab97e0e4d7db6605)（`81e50185d82caa52ccee8652ab97e0e4d7db6605`）。Release [`ieee-access-2026`](https://github.com/roy4222/PawAI/tree/ieee-access-2026) 只新增文件（本節、`docs/paper/`、`CITATION.cff`），程式碼與 81e5018 相同。要重現論文請 `git checkout ieee-access-2026`。
- `main` 在這個 commit 之後會繼續演進；之後的修改不在論文評估範圍內。
- 論文評估使用的組態與本 README 描述的預設不同（例如 LLM 備援鏈、語音辨識只有單一層、物件偵測 7 類）。評估組態、論文用語與章節到原始碼的對照、以及與本 README 的差異，見 **[docs/paper/](docs/paper/README.md)**。
- 評估工具、句庫、注入案例、分析腳本與各實驗彙整：[roy4222/pawai-ieee-access-artifacts](https://github.com/roy4222/pawai-ieee-access-artifacts)。

## 🔖 引用

使用 PawAI 時請引用論文（審查結束後更新書目資訊）：

```bibtex
@article{lu2026pawai,
  author  = {Lu, Po-Yu and Tung, Wei-Feng},
  title   = {A Multimodal Quadruped Robot with Hybrid Edge--Cloud Deployment and Deterministic {LLM} Skill Arbitration},
  journal = {IEEE Access},
  year    = {2026},
  note    = {[under review]}
}
```

根目錄另有 [`CITATION.cff`](CITATION.cff)（GitHub 的「Cite this repository」會讀它）。

## 🗂️ Repo 結構

| 路徑 | 內容 |
|---|---|
| `face_perception/`、`vision_perception/`、`object_perception/` | ROS 2 感知套件（人臉身分、手勢與姿態、物件偵測） |
| `speech_processor/` | ROS 2 語音套件（語音意圖節點、TTS 節點、意圖分類器） |
| `pawai_brain/` | 產生對話候選的 LangGraph 對話圖（論文的 *dialogue graph*） |
| `interaction_executive/` | `brain_node`（論文的 *dialogue manager*）、interaction executive、safety layer、world state、技能佇列 |
| `pawai_contracts/` | 共用契約：技能註冊表、LLM 政策、trace schema |
| `go2_robot_sdk/`、`go2_interfaces/` | Go2 WebRTC 驅動（go2_ros2_sdk 的 fork，Apache-2.0）、深度安全與 reactive-stop 節點 |
| `nav_capability/` | 實驗性導航能力（不在論文評估範圍） |
| `pawai-studio/` | PawAI Studio 網頁主控台：前端與 gateway（語音、trace、離線模式） |
| `scripts/` | 啟動腳本（例如 `start_full_demo_tmux.sh`）與遠端 ASR 伺服器 `sensevoice_server.py` |
| `config/`、`foxglove/` | 部署設定範本與 Foxglove 版面 |
| `tools/pawai_cli/`、`benchmarks/`、`tests/` | 操作 CLI、模型基準測試、機上驗證 |
| `docs/` | 架構、契約、runbook、ADR；`docs/paper/` 給論文讀者；`docs/deliverables/` 是課程繳交物 |
| `archive/` | 退役程式，不參與 build（`COLCON_IGNORE`） |
| `.claude/`、`AGENTS.md`、`CLAUDE.md`、`CONTEXT.md`、`references/`、`docs/agents/` | 給 AI coding agent 的工作規則；建置與執行 PawAI 不需要 |
| `logs/`、`test_results/`、`test_scripts/` | 執行時輸出位置與臨時測試輸入 |

---

## 🏗️ 架構

PawAI 是單一 ROS2 workspace，由 **10 個職責單一的套件**組成，依賴方向永遠
*向內*指向共享契約。

```mermaid
flowchart TD
    subgraph Perception["👁️ 感知層"]
        FACE[face_perception]
        VISION[vision_perception<br/>手勢 · 姿勢]
        OBJ[object_perception]
        SPEECH_IN[speech_processor<br/>ASR · 意圖]
    end

    subgraph Decision["🧠 決策層"]
        BRAIN[pawai_brain<br/>LangGraph 引擎]
        EXEC[interaction_executive<br/>ISM · 安全閘 · 唯一動作出口]
    end

    subgraph Action["🦿 行動層"]
        SPEECH_OUT[speech_processor<br/>TTS]
        DRIVER[go2_robot_sdk<br/>WebRTC 驅動 · 反應式停障]
        NAV[nav_capability]
    end

    subgraph Contracts["📜 共享契約"]
        IFACE[go2_interfaces<br/>msg · srv · action]
        PCON[pawai_contracts<br/>技能註冊 · 策略 · trace schema]
    end

    Perception --> Decision --> Action
    Decision -. 依賴 .-> Contracts
    Action -. 依賴 .-> Contracts
    Perception -. 依賴 .-> Contracts
```

> **唯一硬規則：** `interaction_executive` 是機器狗身體的*唯一*出口。
> `pawai_brain` 只提案，executive 才執行（安全閘優先）。兩者互不 import，
> 皆只依賴 `pawai_contracts`。

<div align="center">

**系統架構**

<img src="docs/assets/architecture-system.png" alt="PawAI 系統架構" width="820">

**PawAI Brain 架構**

<img src="docs/assets/architecture-brain.png" alt="PawAI Brain 架構" width="820">

**PawAI Studio 架構**

<img src="docs/assets/architecture-studio.png" alt="PawAI Studio 架構" width="820">

</div>

### 套件一覽

| 套件 | 層 | 職責 |
|------|----|------|
| [`go2_interfaces`](go2_interfaces/) | 契約 | Go2 的 ROS2 訊息 / 服務 / 動作定義 |
| [`pawai_contracts`](pawai_contracts/) | 契約 | 不含 ROS 的領域契約：技能註冊、LLM 策略、trace schema |
| [`go2_robot_sdk`](go2_robot_sdk/) | 驅動 | Go2 WebRTC 驅動（Clean Arch：domain / application / infrastructure / presentation）、反應式安全停障 |
| [`face_perception`](face_perception/) | 感知 | 人臉偵測 + 身份識別 + 追蹤 |
| [`vision_perception`](vision_perception/) | 感知 | 手勢與姿勢辨識 |
| [`object_perception`](object_perception/) | 感知 | YOLO26n 物體偵測 + 3D 定位 |
| [`speech_processor`](speech_processor/) | 語音 I/O | ASR、意圖、LLM 橋接、TTS |
| [`pawai_brain`](pawai_brain/) | 決策 | LangGraph 對話 / 決策引擎 + 人格 |
| [`interaction_executive`](interaction_executive/) | 決策 | 狀態機、安全閘、唯一動作出口 |
| [`nav_capability`](nav_capability/) | 能力 | 相對目標 / 路線導航動作（實驗性、HITL） |

---

## 🤖 硬體

PawAI 可以分層上手。只跑 Go2 driver 不需要所有外設；完整多模態 Demo 才需要全套硬體。

| 上手目標 | 需要的硬體 |
|----------|------------|
| **最小 Go2 driver** | Unitree **Go2 Pro** + 一台在 Go2 網路內的 Ubuntu 22.04 / ROS2 Humble 機器 |
| **完整 PawAI 互動 Demo** | Go2 Pro + NVIDIA **Jetson Orin Nano Super 8 GB** + Intel RealSense **D435** + USB 麥克風 + USB 喇叭 |
| **物體 / 深度感知** | 固定在機器狗或測試架上的 Intel RealSense **D435** |
| **實驗性導航** | **RPLIDAR A2M12** + 穩固支架 + 外接供電餘裕 + 人在旁邊看守安全 |
| **操作端 UI** | 可連到 PawAI Studio 的筆電或桌機瀏覽器 |

實際 Go2 Pro 配置建議準備：

- D435 的 USB 3 線材與固定支架。
- USB 麥克風與喇叭，或等效的 Go2 音訊播放路徑。
- 若要做導航實驗，RPLIDAR 需要穩固固定、5 V 供電與急停流程。
- 一台開發機負責改 code；Jetson 負責 ROS2 runtime、GPU 推理與機器狗 I/O。

---

## 📋 系統需求

| 系統 | ROS2 版本 |
|------|-----------|
| Ubuntu 22.04（Jetson / x86） | Humble |

---

## 🧭 新使用者上手路徑

1. 先跑 **最小 Go2 driver**，確認 WebRTC 控制能通。
2. 加上 **D435**，分別驗證人臉、物體、姿勢感知。
3. 等攝影機與感知穩定後，再接語音與 TTS。
4. 單一路徑都通過後，再啟 PawAI Studio 與完整多模態 Demo。
5. 導航仍屬實驗性能力：只在有人看守、有明確停機流程的環境中測。

---

## ⚙️ 安裝

```bash
# Clone 進 colcon workspace（此 repo 根目錄本身就是 workspace 的 src）
git clone --recurse-submodules https://github.com/roy4222/PawAI.git src
cd src

# Python 依賴（專案使用 uv）
uv pip install -r requirements.txt          # Jetson 上再加 requirements-jetson.txt

# 建構
source /opt/ros/humble/setup.bash           # Jetson 用 setup.zsh
colcon build
source install/setup.bash
```

---

## 🚀 快速開始

```bash
# 最小 Go2 驅動
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false

# 語音 + LLM 端到端（一鍵 tmux）
bash scripts/start_llm_e2e_tmux.sh

# 完整多模態 Demo（感知 + 大腦 + Studio）
bash scripts/start_full_demo_tmux.sh

# 人臉辨識 pipeline
bash scripts/start_face_identity_tmux.sh
```

完整建構 / 執行矩陣與已知陷阱見 [`CLAUDE.md`](CLAUDE.md)，
Demo 操作 SOP 見 [`docs/runbook/`](docs/runbook/README.md)。

---

## 🛟 可靠性 — 三層降級鏈

每個雲端優先的能力都有本地 fallback，Demo 不會斷：

| 層 | 主線 | Fallback 1 | Fallback 2 |
|----|------|-----------|-----------|
| **LLM** | OpenRouter（Gemini / GPT-mini） | 本地 Qwen | RuleBrain |
| **TTS** | Gemini Flash TTS | edge-tts | Piper（離線） |
| **ASR** | SenseVoice 雲端 | SenseVoice 本地 | faster-whisper 本地 |

---

## 🖥️ PawAI Studio

操作端網頁 UI（「ChatGPT 風格主控台 ＋ AI 版 Foxglove」），用來驅動與觀測機器狗。

```bash
bash pawai-studio/start.sh      # → http://localhost:3000/studio
```

---

## 📚 文件

| 領域 | 入口 |
|------|------|
| 專案定位與 Demo 範圍 | [`docs/mission/`](docs/mission/README.md) |
| ROS2 介面契約 | [`docs/contracts/`](docs/contracts/interaction_contract.md) |
| 大腦 / 感知 / 語音 / Studio | [`docs/architecture/`](docs/architecture/README.md) |
| 導航與避障 | [`docs/architecture/navigation/`](docs/architecture/navigation/README.md) |
| 操作 runbook（Demo SOP） | [`docs/runbook/`](docs/runbook/README.md) |
| 架構決策（ADR） | [`docs/adr/`](docs/adr/README.md) |

內部歷史文件不包含在公開版；
已退役的套件與腳本在 [`archive/`](archive/README.md)。

---

## 🙏 基於 go2_ros2_sdk

PawAI 起初是 [**abizovnuralem/go2_ros2_sdk**](https://github.com/abizovnuralem/go2_ros2_sdk)
的 fork——由 [@abizovnuralem](https://github.com/abizovnuralem) 與
[@tfoldi](https://github.com/tfoldi) 打造、出色的 Unitree Go2 ROS2 / WebRTC 整合。
`go2_robot_sdk`、`go2_interfaces` 與驅動層皆承襲自該專案；PawAI 在其上加入感知、
大腦、語音、導航與 Studio 各層。

> 🧭 *未來工作：* 容器化部署（`docker/`）與文件網站已規劃但尚未產出。

---

## 授權

[BSD 2-Clause](./LICENSE) — 承襲自上游 `go2_ros2_sdk` 專案。
