# PawAI — 老人與狗

> 基於多模態感知融合的具身互動機器狗。
> D435 + RPLIDAR 整合：能看懂人、理解語音、辨識物體，並安全地做出語音、動作與導航回應。

**硬底線**：2026/5/12 學校 Demo
**5/12 主作戰地圖**：[`docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md`](docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md)
**Phase A 導航攻堅執行計畫**：[`docs/navigation/plans/2026-05-01-phase-a-nav-attack.md`](docs/navigation/plans/2026-05-01-phase-a-nav-attack.md)

---

## 一句話定位

> LiDAR 讓 PawAI 走得穩，D435 讓 PawAI 看得懂與停得安全，Brain 讓 PawAI 知道為什麼要走。

不是聊天機器人，也不是各功能分開展示的辨識系統，而是「**看懂 → 理解 → 決策 → 行動**」串起來的具身互動機器狗：

1. **看懂** — D435 RGB（人臉/手勢/姿勢/物體）+ D435 Depth（safety stop）+ RPLIDAR（2D map / Nav2 障礙）
2. **理解** — PawAI Brain 接事件，LLM 產生 intent / skill / reply_text；Persona 是「PawAI 感」：活潑、好奇、有在場感、有守護溫度
3. **決策** — Skill Registry ~25 條，Brain 只提 SkillPlan，Executive 做 safety gate
4. **行動** — 說話（Gemini TTS / fallback）+ 動作（Go2 sport API）+ 導航（RPLIDAR + Nav2）+ 安全（D435 emergency stop）

---

## 四大核心難點

1. **跨層耦合** — ASR/LLM/TTS/ROS2/WebRTC/Go2 firmware 任一層偏差都表現成「沒聲音」或「不好用」
2. **可觀測性不足** — 多層只看到 `send success`，看不到裝置端真實狀態
3. **環境不穩定且不可完全控** — Jetson 資源、網路、韌體、裝置回應都會漂移
4. **整合成本遠高於功能開發** — 寫新 node 一天，真機 30 分鐘穩定跑常常更久

---

## 硬體規格

- **載體**：Unitree Go2 Pro
- **邊緣運算**：NVIDIA Jetson Orin Nano SUPER 8GB
- **視覺感測**：Intel RealSense D435（RGB-D）
- **光達**：RPLIDAR-A2M12（12 m，16000 次/秒）
- **遠端算力**：5× Quadro RTX 8000（48 GB × 5 = 240 GB VRAM）+ 2× Xeon Gold 6248R（96 threads）+ 754 GiB RAM
- **架構原則**：Clean Architecture（分層、單向依賴、感知/決策/驅動分離）

---

## 八大功能模組

| # | 模組 | 主線文件 | 5/12 主線 |
|:-:|------|---------|-----------|
| 1 | 人臉辨識 | [`docs/pawai-brain/perception/face/`](docs/pawai-brain/perception/face/README.md) | 認熟人打招呼、陌生人警報（YuNet + SFace + IOU 追蹤，本地 < 30ms） |
| 2 | 語音 / LLM / TTS | [`docs/pawai-brain/speech/`](docs/pawai-brain/speech/README.md) | 雲端 LLM（Gemini 3 Flash / DeepSeek / Qwen 候選）+ Gemini 3.1 Flash TTS；本地 fallback：VAD + faster-whisper + RuleBrain + Piper |
| 3 | 手勢辨識 | [`docs/pawai-brain/perception/gesture/`](docs/pawai-brain/perception/gesture/README.md) | 7 種手勢（Palm/OK/Wave/Thumb/Peace/Fist/Index），高風險動作 OK 二次確認 |
| 4 | 姿勢辨識 | [`docs/pawai-brain/perception/pose/`](docs/pawai-brain/perception/pose/README.md) | 坐下→`sit_along`、彎腰→`careful_remind`；可選跌倒警報 |
| 5 | 物體辨識 | [`docs/pawai-brain/perception/object/`](docs/pawai-brain/perception/object/README.md) | YOLO26n 本地（< 200ms）+ HSV 顏色 + D435 3D 座標（0.3-3 m）；Demo 後升級 YOLO26x / Qwen-VL 雲端 |
| 6 | 導航避障 | [`docs/navigation/`](docs/navigation/README.md) | RPLIDAR + slam_toolbox 建圖、AMCL 定位、Nav2 規劃、D435 reactive safety stop |
| 7 | PawAI Brain × Studio | [`docs/pawai-brain/`](docs/pawai-brain/README.md) | Skill Registry 26 條（Active 17 / Hidden 5 / Disabled 4 / Retired 1）、Brain 只提案、Executive 唯一出口；Studio = ChatGPT/OpenClaw 風格 + AI 版 Foxglove |
| 8 | 文件網站 | （組員主責，5/12 後產出） | — |

---

## 5/12 Demo Storyboard（4:30，8 scene）

System Ready → Nav Backbone → Personality → 熟人 → 手勢 → 物體 → Sensor Fusion → safety stop

詳見 [`docs/pawai-brain/README.md`](docs/pawai-brain/README.md) 與 [Sprint design](docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md)。

---

## 三層降級鏈（Demo 不能斷）

| 層 | 主線 | Fallback 1 | Fallback 2 |
|----|------|-----------|-----------|
| **LLM** | OpenRouter (Gemini 3 Flash / DeepSeek V4) | Ollama qwen2.5:1.5b 本地 | RuleBrain 規則式 |
| **TTS** | Gemini 3.1 Flash TTS（含 audio tag） | edge-tts 雲端 | Piper 本地離線 |
| **ASR** | SenseVoice cloud (FunASR) | SenseVoice local (sherpa-onnx int8) | faster-whisper local |
| **Plan** | Plan A 8 場景動態 | Plan B 固定台詞 | — |

---

## 文件入口

| 路線 | 入口 | 用途 |
|------|------|------|
| [`docs/README.md`](docs/README.md) | 7 主線導覽 | 找不到時看這裡 |
| [`docs/pawai-brain/`](docs/pawai-brain/README.md) | 互動主線 | 感知 / 語音 / Studio / Brain |
| [`docs/navigation/`](docs/navigation/README.md) | 移動主線 | LiDAR / Nav2 / AMCL / D435 depth |
| [`docs/contracts/`](docs/contracts/README.md) | 跨主線契約 | ROS2 topic / action schema |
| [`docs/runbook/`](docs/runbook/README.md) | Demo 救火 SOP | Jetson / Network / GPU / Go2 操作 |
| [`docs/mission/`](docs/mission/README.md) | 專案定位 | Demo 劇本 / 八大功能 SoT / 會議紀錄 |
| [`docs/deliverables/thesis/`](docs/deliverables/thesis/) | 學期繳交素材 | 論文 / 報告 |

---

## Quick Start

```bash
# Jetson 上建構（zsh）
source /opt/ros/humble/setup.zsh
colcon build
source install/setup.zsh

# 啟動 Go2 驅動（最小模式）
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false

# 一鍵 Demo（語音 + LLM 主線）
bash scripts/start_llm_e2e_tmux.sh

# 一鍵 Demo（nav_capability 平台層）
bash scripts/start_nav_capability_demo_tmux.sh

# 一鍵 Demo（人臉辨識）
bash scripts/start_face_identity_tmux.sh
```

詳細環境建置與救火 SOP 見 [`docs/runbook/`](docs/runbook/README.md)。
完整建構/執行 / 已知陷阱見 [`CLAUDE.md`](CLAUDE.md)。
