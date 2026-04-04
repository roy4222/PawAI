# PawAI Mission 入口頁

> Status: current

**專案名稱**：老人與狗 (Elder and Dog) / PawAI
**文件版本**：v2.2
**定案日期**：2026-03-07
**最後更新**：2026-03-26
**交付期限**：2026/4/13 文件繳交、5/16 省夜 Demo、5/18 正式展示、6 月口頭報告

> **v2.0 更新**：全面更新功能閉環設計、本地/雲端拆分策略、PawAI Studio 定位、團隊分工方向

---

## 1. 文件定位與閱讀方式

### 這份文件是什麼

這是 PawAI Mission 的**入口頁 (Entry Point)**，負責整合專案的核心決策、系統輪廓、功能閉環與關鍵導覽。

**定位說明**：
- 不取代模組設計文件，而是**摘要 + 連結**
- 不取代介面契約文件，而是**決策脈絡 + 驗收目標**
- 提供**單一真相來源 (Single Source of Truth)** 給全團隊

### 誰應該閱讀

| 角色 | 閱讀重點 | 延伸文件 |
|------|----------|----------|
| 新成員 | 第 1、2、3、7 節 | [setup/README.md](../setup/README.md) |
| 手勢/姿勢研究 (黃旭、陳若恩) | 第 5、6、7 節 | [手勢辨識/README.md](../手勢辨識/README.md) |
| 前端開發 (魏宇同) | 第 5、6、7 節 | [Pawai-studio/README.md](../Pawai-studio/README.md) |
| System Architect | 全篇 + 附錄 | [interaction_contract.md](../architecture/interaction_contract.md) |

---

## 2. 專案一句話定位

> 以 Unitree Go2 Pro 為載體，建立一套「以人機互動為主、導航避障為輔」的 embodied AI 機器狗系統。
>
> 核心是「人臉辨識 + 中文語音互動 + AI 大腦決策」，不是導航或尋物。

**PawAI Studio** 是整個系統的統一入口：

> 一個以 chat 為主入口、可動態展開 Foxglove 式觀測與控制面板的 embodied AI studio。

---

## 3. 專案背景與交付目標

### 3.1 專案起源

本專案旨在打造一套以 Unitree Go2 Pro 為載體的 embodied AI 機器狗平台，整合多模態感知、語音互動、AI 大腦與基礎移動能力，並透過模組化架構支援多人分工、快速整合與實際展示。

**核心價值**：
- 多模態互動（人臉 + 語音 + 手勢 + 姿勢）
- AI 大腦與展示中樞（PawAI Studio）
- 模組化整合（Clean Architecture + 標準介面）
- 可分工、可展示（遠端無設備也能開發）

**可應用場景**：居家陪伴、長者互動、教育展示等。

### 3.2 交付目標 (4/13 硬底線)

| 里程碑 | 日期 | 交付內容 |
|--------|------|----------|
| 功能閉環凍結 | 3/12 | 8 個功能的本地/雲端拆分確認（本文件） |
| 攻守交換 | 3/16 | Roy 交出架構核心，其他成員接手前端與文件 |
| 前端網站截止 | 3/26 | 前端頁面完成，Roy 審查後告知修改項目 |
| 四功能整合測試 | 3/26 – 4/2 | 人臉 + 語音 + 手勢 + 姿勢整合驗證 |
| P0 穩定化 | 4/6 | Demo A/C 成功率 >= 90% |
| **文件繳交** | **4/13** | **七大功能完成 + 專題文件繳交** |
| **展示／驗收** | **五月** | **完整系統展示與發表** |

---

## 4. 系統載體與算力配置

### 4.1 硬體配置總覽

| 層級 | 設備 | 規格 | 用途 |
|------|------|------|------|
| **機器人載體** | Unitree Go2 Pro | 12 關節四足、內建 LiDAR/IMU | 運動執行、環境感知 |
| **邊緣運算** | NVIDIA Jetson Orin Nano SUPER | 8GB 統一記憶體 | 即時感知、本地推理、ROS2 runtime |
| **視覺感測** | Intel RealSense D435 | RGB-D 深度攝影機 | 人臉偵測、深度估計 |
| **音訊輸入** | USB 麥克風 (HyperX SoloCast) | 外接式 | 中文語音輸入（D435 無內建麥克風） |
| **遠端算力** | 5× NVIDIA Quadro RTX 8000 | 每張 48GB VRAM，總 240GB | LLM 推理、雲端增強 |

**遠端伺服器詳細規格**：
- CPU：2× Intel Xeon Gold 6248R（96 threads）
- RAM：754 GiB
- CUDA runtime：13.0 / nvcc toolkit：12.0

### 4.2 本地/雲端算力拆分策略

**核心原則**：
- **低延遲需求** → 留在本地（Jetson）
- **高品質理解** → 交給雲端（RTX 8000）
- **安全控制** → 永遠不交給雲端直接執行

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

### 4.3 Jetson 記憶體預算

| 項目 | 預估占用 | 模式 |
|------|----------|------|
| Ubuntu + ROS2 基礎系統 | 1.5-2.0 GB | 常駐 |
| D435 + 影像串流 | 0.6-1.0 GB | 常駐 |
| YuNet 人臉偵測 | ~0.1 GB | 常駐 |
| Sherpa-onnx 喚醒詞 | ~0.05 GB | 常駐 |
| faster-whisper Tiny/Small | 0.4-1.0 GB | 觸發式（喚醒後載入） |
| Piper TTS | 0.3-0.5 GB | 觸發式（喚醒後載入） |
| Qwen2.5-0.8B INT4 | ~1.0 GB | 僅斷網降級時載入 |
| 安全餘量 | >= 0.8 GB | 必須保留 |

**省電門禁策略**：喚醒詞觸發前，ASR/LLM/TTS 不載入記憶體。

---

## 5. 八大功能閉環設計 (v1 決策版)

### 5.1 功能總覽與優先序

| # | 功能 | 優先級 | 本地/雲端 | 狀態 |
|---|------|:------:|:---------:|:----:|
| 1 | 語音功能 | **P0** | 本地保底 + 雲端增強 | ✅ E2E 已驗證 |
| 2 | 人臉辨識 | **P0** | 純本地 | ✅ ROS2 package 完成 |
| 3 | 手勢辨識 | **P1** | 本地 | ✅ MediaPipe Gesture Recognizer（CPU 7.2 FPS），RTMPose 備援 |
| 4 | 姿勢辨識 | **P1** | 本地 | ✅ MediaPipe Pose（CPU 18.5 FPS），RTMPose 備援 |
| 5 | AI 大腦 (PawAI Studio) | **P0** | 雲端為主 | ✅ 閉環確認 |
| 6 | 辨識物體 | **P1** | 本地（YOLO） | 核心五功能之一，4/13 前需完成 |
| 7 | 導航避障 | P2 | 待定 | **Demo 停用**（D435 鏡頭角度限制，詳見 [demo-scope.md](demo-scope.md)） |
| 8 | 文件網站 | **P0** | N/A | ✅ 閉環確認 |

### 5.2 功能 1：語音功能

#### 本地保底鏈路（Jetson 8GB）

```
Energy VAD 持續監聽（always-on，無喚醒詞）
  → 語音偵測
  → Whisper Small (faster-whisper CUDA float16, ~12s warmup)
  → Intent 分類（高信心 ≥ 0.8 → fast path 跳過 LLM）
  → 雲端 LLM（Cloud Qwen2.5-7B）或本地 LLM（Ollama 1.5B）或 RuleBrain fallback
  → edge-tts 雲端合成（P50 0.72s）或 Piper 本地 fallback
  → USB 外接喇叭（主線）或 Go2 Megaphone DataChannel
```

#### 雲端增強模式（RTX 8000）

```
本地 ASR 完成 → 文字送雲端 LLM (Qwen2.5-7B-Instruct)
  → 雲端做深度理解 / 記憶 / 情感 / 長上下文
  → 回覆文字送回本地 → 本地 TTS 合成播放
  → 若雲端超時 (2-4s) → fallback 到本地
```

#### 四級降級策略

| Level | 條件 | 行為 |
|:-----:|------|------|
| 0 | 雲端正常 | Cloud Qwen2.5-7B 完整對話 + edge-tts + Studio 全功能 |
| 1 | 雲端 LLM 斷線 | 自動切換 Ollama qwen2.5:1.5b 基本對話 + edge-tts |
| 2 | 雲端全斷（LLM+TTS） | RuleBrain 模板回覆 + Piper 本地 TTS |
| 3 | 最小保底 | ASR + Intent fast path + RuleBrain + Piper（停止/掰掰/打招呼） |

#### 語音狀態機

```
idle_listening (Energy VAD 持續監聽)
  → voice_detected → recording → transcribing (Whisper CUDA)
  → intent_classified → [high confidence] fast_path → speaking
                       → [low confidence]  llm_pending (Cloud→Ollama→RuleBrain)
  → reply_ready → tts_synthesizing (edge-tts / Piper fallback)
  → speaking → echo_cooldown → idle_listening
```

#### 關鍵技術選型

| 模組 | 選型 | 說明 |
|------|------|------|
| 喚醒詞 | 未實作（always-on listening） | Sherpa-onnx KWS 評估後暫緩，目前用 Energy VAD 持續監聽 |
| ASR | Whisper Small (faster-whisper CUDA float16) | 本地離線，RTF 0.13，有幻覺問題（過濾規則已建） |
| 本地 LLM | Ollama qwen2.5:1.5b | 雲端斷線 fallback，JSON 穩定，中文可用 |
| 雲端 LLM | Qwen2.5-7B-Instruct (vLLM) | 系統中樞大腦，Prefix Cache 後延遲 ~1.5s |
| TTS | edge-tts（雲端主線）+ Piper（本地 fallback） | edge-tts P50 0.72s vs Piper 2.0s，MeloTTS 已淘汰 |

#### 核心檔案

- `speech_processor/speech_processor/stt_intent_node.py` — ASR + Intent 整合節點
- `speech_processor/speech_processor/tts_node.py` — TTS + Go2/USB 播放（edge-tts/Piper/MeloTTS/ElevenLabs）
- `speech_processor/speech_processor/llm_bridge_node.py` — LLM 三級 fallback + Go2 動作
- `scripts/start_llm_e2e_tmux.sh` — 主線啟動腳本（edge-tts + USB 外接設備）

### 5.3 功能 2：人臉辨識

#### 定位

**純本地主線，不上雲。** YuNet + SFace + IOU 追蹤已覆蓋 4/13 Demo 核心需求。

#### 核心檔案

**`scripts/face_identity_infer_cv.py`** — 這是 4/13 展示主線，已包含：

- YuNet 偵測（多人，det_score_threshold=0.90）
- SFace 識別（cosine similarity，centroid + sample matching）
- IOU 追蹤（multi-face tracking，track_max_misses=10）
- Hysteresis 穩定化（sim_threshold_upper=0.35 / lower=0.25，stable_hits=3）
- 深度距離估計（D435 aligned depth，median filtering）
- Debug 影像 + 比對影像發布

#### 4/13 前改動

在現有 script 補兩類標準 ROS2 輸出：

**`/state/perception/face`**（高頻持續發布）：
- `track_id` — 追蹤 ID
- `stable_name` — 穩定化後的身份名稱
- `sim` — 相似度分數
- `distance_m` | null — 深度距離（可能取不到）
- `bbox` — 邊界框
- `mode` — stable / hold
- `face_count` — 目前追蹤人數

**`/event/face_identity`**（低頻條件觸發）：
- `event_type` — track_started / identity_stable / identity_changed / track_lost
- `track_id`
- `stable_name`
- `sim`
- `distance_m` | null

#### 4/13 後

回收成 Clean Architecture ROS2 package。

### 5.4 功能 3：手勢辨識 🔄

**主線：MediaPipe Gesture Recognizer**（CPU 7.2 FPS，0.10.18 aarch64 wheel）。

> 3/21 benchmark 後選定。MediaPipe 0.10.18 提供 aarch64 wheel（之後版本移除），CPU-only 但 FPS 足夠。Google 明確不支援 Jetson GPU 加速。

- **主線**：MediaPipe Gesture Recognizer（stop / point / thumbs_up / ok）
- **備援**：RTMPose wholebody（rtmlib + onnxruntime-gpu）
- 目標成功率 ≥ 70%
- Phase 1 完成（23 unit tests pass），Jetson 場景驗證通過

> 詳見 [`docs/手勢辨識/README.md`](../手勢辨識/README.md)

### 5.5 功能 4：姿勢辨識 🔄

**主線：MediaPipe Pose**（CPU 18.5 FPS，17 keypoints COCO format）。

> 3/21 benchmark 選定。CPU 模式效能足夠且不佔 GPU（留給 Whisper CUDA）。

- **主線**：MediaPipe Pose（standing / sitting / crouching / fallen / bending）
- **備援**：RTMPose lightweight（GPU，與 Whisper 共存需注意 VRAM）
- 跌倒偵測為安全功能，持續 2s 觸發語音警報
- Phase 1 完成，Jetson 場景驗證通過，L3 壓測 60s 通過（RAM 1.2GB, 52°C, GPU 0%）

> 詳見 [`docs/姿勢辨識/README.md`](../姿勢辨識/README.md)

### 5.6 功能 5：AI 大腦 (PawAI Studio)

#### 定位

**系統中樞大腦**，不只是聊天模型。

PawAI Studio = ChatGPT / OpenClaw 風格主入口 + AI 版 Foxglove 的機器狗控制中樞。

#### AI 大腦職責

**負責**：
- 事件理解（face / speech / gesture / pose → 可理解的上下文）
- 高階意圖判斷（結合多模態感知 + 機器狗狀態）
- 技能調度建議（greet_person / answer_question / follow_person / stop）
- Panel orchestration（決定 Studio 展開哪些面板）
- 記憶與摘要（對話記憶、人物記憶、trace summary）
- 自然語言回覆生成

**不負責**：
- 低階控制（不直接控 Go2 馬達）
- 即時安全控制（避障、stop、safety gate）
- 毫秒級反應（wakeword、VAD、ASR 前段、face detect）

#### 架構關係

```
Qwen2.5-7B-Instruct 提建議
  → Interaction Executive 做決策
  → Runtime 安全執行
```

#### 雲端主腦現況

- **現行**：Qwen2.5-7B-Instruct on RTX 8000（vLLM，已驗證 E2E）
- **升級候選**：更大參數模型，視伺服器穩定度決定
- **本地 fallback**：Qwen2.5-0.8B（Jetson，雲端斷線時備援，智商待測）

#### PawAI Studio 組成

| 元素 | 說明 |
|------|------|
| Chat 主入口 | 文字 / 語音輸入的統一入口 |
| Live Feed | D435 即時影像 + 人臉框 |
| Robot Status | executive / perception / battery / posture |
| Skills 控制台 | Stand / Sit / Wave / Stop 技能按鈕 |
| Event Timeline | 事件流時間軸（區別於普通 chat 的核心差異） |
| Brain / Trace Panel | current intent / selected skill / why this action |
| Module Health Panel | face / speech / cloud brain 的 active/inactive / latency |

### 5.7 功能 6：辨識物體 (P1 — 核心五功能)

**教授定案為核心功能之一**（2026-03-18 會議）。核心五功能：人臉辨識、語音互動、手勢辨識、姿勢辨識、物體辨識。

**策略調整（3/26 會議）**：改為**預設目標**辨識（指定日常物品如水杯、藥罐等），非自由搜尋。參考 AI Expo 業界做法 — 展場約 1/4 廠商做辨識類應用，多數採「預設目標物」模式。

候選方向：YOLO26n（專為邊緣裝置設計），保底方案為 Go2 SDK 自帶 COCO + MobileNet。4/2 後啟動開發。

### 5.8 功能 7：導航避障 (P2 / Demo 停用)

**Demo 停用**（2026-04-03 決定）。程式碼保留但不啟用。

**停用原因**：D435 鏡頭裝在 Go2 頭上偏上方，低於鏡頭高度的障礙物只有在 ~0.4m 才進入 FOV，煞車距離不足（延遲鏈 ~1-1.5s）反覆撞上。3 輪 come_here 防撞測試（threshold 1.2→1.5→2.0m）全部失敗，屬硬體鏡頭角度問題，軟體無法克服。

**歷史**：LiDAR 正式放棄（3/26）→ D435 反應式避障實作 + 桌測通過（4/1）→ Go2 上機測試全失敗（4/3）→ 停用。

**已完成的工作**（保留作為未來改善基礎）：
- D435 obstacle_avoidance_node（7 tests）+ LiDAR lidar_obstacle_node（13 tests）
- 雙層安全架構 + safety guard heartbeat
- Foxglove 3D dashboard 可視化
- 詳見 [導航避障/README.md](../導航避障/README.md)

### 5.9 功能 8：文件網站

#### 雙站策略

| 站點 | 定位 | 技術棧 |
|------|------|--------|
| **PawAI Studio** | 控制站 + 展示站 | React-based app（暫定 Next.js） |
| **Docs Site** | 文件站 / 知識庫 | Astro + Starlight |

**同 repo、兩個站、分開部署。**

#### PawAI Studio 包含
- 首頁 / 專案介紹 / Showcase
- Chat 主入口
- Live demo
- Event timeline
- Robot status
- Skills
- Debug / replay

#### Docs Site 包含
- 專案介紹與架構文件
- 模組規格
- 安裝部署教學
- 開發紀錄與踩坑整理
- 架構演進（舊 → 新對比）

#### 標竿參考
- 展示風格：[Odin Navigation Stack](https://manifoldtechltd.github.io/Odin-Nav-Stack-Webpage/)
- 文件架構：[freeCodeCamp Docs](https://contribute.freecodecamp.org/intro/)
- 內容深度：[Hiwonder JetAcker Wiki](https://wiki.hiwonder.com/projects/JetAcker/en/jetacker-orin-nano/docs/1.getting_ready.html)

---

## 6. 三層架構總覽

### 6.1 架構設計原則

- **單一控制權**：所有動作唯一出口在 Layer 3，避免多模組搶控制
- **事件驅動**：Layer 2 各模組發布事件，Layer 3 訂閱後決策
- **本地保底**：每個功能鏈路在斷網時仍有最小可用能力
- **大腦提建議、Executive 做決策、Runtime 安全執行**

### 6.2 三層架構圖

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
│  ├─ 音訊裝置 (ALSA, USB 麥克風)                               │
│  ├─ ROS2 Humble                                              │
│  └─ 邊緣模型執行 (ONNX Runtime / CTranslate2 CUDA)           │
│  部署：Jetson Orin Nano + Go2 Pro                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 關鍵 ROS2 Topic

**語音鏈路**：

| Topic | 用途 |
|-------|------|
| `/event/speech_intent_recognized` | 語音意圖識別事件 (JSON) |
| `/asr_result` | ASR 文字輸出 |
| `/tts` | TTS 輸入文字 |
| `/webrtc_req` | Go2 WebRTC 命令 |
| `/state/interaction/speech` | 語音狀態監控 |

**人臉鏈路**：

| Topic | 用途 |
|-------|------|
| `/state/perception/face` | 人臉追蹤狀態（高頻） |
| `/event/face_identity` | 人臉身份事件（條件觸發） |

**系統狀態**：

| Topic | 用途 |
|-------|------|
| `/state/executive/brain` | 大腦決策狀態 |

---

## 7. 團隊分工（3/18 會議更新）

### 7.1 團隊成員

| 成員 | 角色 |
|------|------|
| Roy | 專案負責人 / System Architect / Integration Owner |
| 魏宇同 | 前端開發 |
| 黃旭 | 手勢/姿勢研究 → 前端 → 文件 |
| 陳若恩 | 手勢/姿勢研究 → 前端 → 文件 |
| 董為鳳 | 聯絡人 |

### 7.2 核心分工策略

**關鍵原則**：讓遠端沒有機器狗和設備的人也能進行分工。

### 7.3 各角色職責與時程

#### Roy — System Architect / Integration Owner

| 時段 | 任務 |
|------|------|
| 本週（3/18–3/26） | 手勢/姿勢框架測試（Jetson GPU 模型） |
| 3/23 | 審查前端網站成果 |
| 3/26 後 | 接手前端修改、四功能整合（人臉+語音+手勢+姿勢） |
| 4/2 後 | 加入導航避障等額外功能；穩定度優化、文件整理 |

#### 魏宇同 — 前端開發

| 時段 | 任務 |
|------|------|
| 至 3/26 | 前端網站頁面開發 |
| 4/2 後 | 文件網站 + 物體辨識研究 |

#### 黃旭、陳若恩 — 研究 → 前端 → 文件

| 時段 | 任務 |
|------|------|
| 3/19 | 報告手勢/姿勢辨識研究成果（MediaPipe 結論 + 測試結果） |
| 至 3/26 | 完成各自前端頁面 |
| 4/2 後 | 文件網站 + 專題報告 |

#### 文件章節分工（3/26 會議定案，4/13 前繳交 Ch1-5）

| 章節 | 內容 | 負責人 |
|------|------|--------|
| Ch1 | 專題介紹、背景說明 | 共同（參考現有版本修訂） |
| Ch2 | User Story、需求分析 | 魏宇同、黃旭 |
| Ch3 | 系統架構、技術細節（硬體+模型+各模組） | 人臉+導航+語音（Roy）、物體+姿勢（魏宇同/黃旭）、手勢（陳若恩） |
| Ch4 | 問題與缺點、未來展望 | 簡單撰寫 |
| Ch5 | 分工貢獻表、個人心得 | 各自撰寫 |

> 文件撰寫原則：不花太多時間，重心放功能實作與介紹網站。Go2 動作尚未實作完成的部分先模糊帶過。

---

## 8. Demo 與驗收

### 8.1 Demo 策略（3/18 會議定案）

**展示策略**：預設腳本為主、自由對話為輔（自由對話標註「效果不保證」）。

| Demo | 名稱 | 內容 | 成功率 |
|:----:|------|------|:------:|
| A | 主線閉環 | 人出現→辨識→對話→回應→Studio 同步 | >= 90% |
| B | 視覺互動 | 手勢/姿勢 + 動作 (P1) | >= 70% |
| C | Studio 展示 | 一鍵 Demo + 面板 + 事件流 | >= 90% |

### 8.2 Demo A 流程

1. 使用者走近 → YuNet 偵測人臉
2. SFace 辨識身份 → `/event/face_identity` (identity_stable)
3. 使用者說喚醒詞 → Sherpa-onnx 觸發
4. Go2 播「我在」→ 載入 ASR/TTS
5. 使用者說話 → ASR 轉文字 → 雲端 LLM 理解
6. LLM 生成回覆 → 本地 TTS → Go2 播放
7. PawAI Studio 同步顯示事件流與系統狀態

---

## 9. 風險與降級策略

### 9.1 四級降級（語音 + AI 大腦）

| Level | 名稱 | 觸發條件 | 行為 |
|:-----:|------|----------|------|
| 0 | 雲端完整 | 網路正常 | Qwen2.5-7B-Instruct 完整對話 + Studio 全功能 |
| 1 | 本地 LLM | 雲端斷線 | Qwen2.5-0.8B 基本對話 + 簡化 Studio |
| 2 | 規則模式 | Jetson 記憶體不足 | Rule Intent + 模板回覆 + 狀態顯示 |
| 3 | 最小保底 | 系統壓力極大 | 喚醒 + ASR + 固定指令 |

### 9.2 人臉辨識降級

人臉辨識為純本地，無雲端依賴。唯一風險是 Jetson 記憶體不足時降低偵測頻率。

### 9.3 安全規則

- `stop` 命令最高優先級，可打斷任何 skill
- AI 大腦不能直接控制 Go2 低階運動
- 所有動作必須經過 Safety Guard 仲裁

---

## 10. 文件導航

### 10.1 文件地圖

> **NOTE**（2026-03-13 更新）：以下文件地圖部分路徑已過時：
> - `vision.md`、`roadmap.md` — 已歸檔至 `archive/mission/`，由本文件取代
> - `architecture/brain_v1.md` — 檔案不存在（幽靈引用，待建立或移除）
> - `logs/` — 已歸檔至 `archive/logs/`

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

### 10.2 快速連結

| 目的 | 連結 |
|------|------|
| PawAI Studio 設計 | [Pawai-studio/README.md](../Pawai-studio/README.md) |
| 介面契約規格 | [interaction_contract.md](../architecture/interaction_contract.md) |
| 人臉辨識 | [人臉辨識/README.md](../人臉辨識/README.md) |
| 語音功能 | [語音功能/README.md](../語音功能/README.md) |
| Jetson MVP 測試 | [語音功能/jetson-MVP測試.md](../語音功能/jetson-MVP測試.md) |

---

## 11. 模組開發 SOP

> **來源**：2026-03-15 語音模組 30 輪驗收，踩了 36 個坑（30 個在驗收工具，6 個在語音主線）。本 SOP 將教訓制度化，適用於所有模組。
>
> **完整設計文件**：[`docs/superpowers/specs/2026-03-15-module-dev-sop-design.md`](../superpowers/specs/2026-03-15-module-dev-sop-design.md)

### 11.1 環境同步規範

| # | 規則 |
|---|------|
| 1 | 要上 Jetson 驗證的變更必須先 commit；需跨機同步或交接時必須 push |
| 2 | Jetson 上禁止直接改 code（除緊急 hotfix），hotfix 完必須 30 分鐘內 commit 回 repo |
| 3 | `colcon build` 後必須 `source install/setup.zsh` + 重啟受影響 node |
| 4 | Jetson 端固定 zsh，腳本若採 bash 需整段自洽，不可混 source |
| 5 | 會 source ROS2 setup 的 shell script 預設不用 `set -u` |

> 單人快速迭代可直接用 main。多 agent 並行時，Builder 各用功能分支，由 Integrator merge（見 §11.6）。

### 11.2 裝置前置檢查

**不通過不進入 build/test。**

**Core（所有模組）**：ROS2 環境可用、無非預期殘留 node。
**Robot-dependent（語音、demo）**：Go2 連線 + driver 存活。
**語音專屬**：PulseAudio 已停、麥克風可用、CUDA 可用。
**人臉專屬**：D435 連線、YuNet 模型存在。
**LLM 專屬**：RTX server 連線、vLLM health。

> 完整指令與通過條件見 [SOP 設計文件](../superpowers/specs/2026-03-15-module-dev-sop-design.md)。

### 11.3 跨 Node 協調設計原則

**設計總則：**
- **狀態**靠 latched state topic
- **事件**靠 volatile + correlation id（session_id / track_id / request_id）
- **控制**靠 req/ack（ack 必須帶回 request_id）
- **所有跨 node 契約先在 [`interaction_contract.md`](../architecture/interaction_contract.md) 登記再實作**

**關鍵原則**：latched topic init 時發初始值、gate/mute 必須有 timeout 保護、新增 intent/event type 必須同步更新共享常數。

### 11.4 驗收分級與切換條件

**核心規則：子模組靠 spec + smoke + review，整合主線才跑 YAML 驗收。**

| 級別 | 適用 | 形式 | 通過標準 |
|:----:|------|------|----------|
| **Level A** | 單一模組可獨立驗證 | spec + smoke test + code review | smoke 全綠 + 無 blocking issue |
| **Level B** | 接進 ROS2 主線、與其他 node 互動 | YAML case + 自動判定 + 報表 | 10+ case、關鍵指標達門檻 |

**升級條件（A → B）**：Level A 全綠，且至少滿足其一：介面已相對穩定、開始影響 demo 主線。**不滿足時禁止花時間做 Level B 驗收工具。**

### 11.5 模組整合 Checklist

```
Level 1: Standalone → Level 2: Node-level → Level 3: System-level → Level 4: Demo-level
```

**原則上不可跳級；例外需記錄理由與風險。**

| 等級 | 關鍵 Checklist |
|:----:|---------------|
| **L1** | 目標平台可執行、有 input/output 定義、smoke test 全綠、無硬編碼路徑、code review 通過 |
| **L2** | 標準啟動入口、topic 登記在 contract、QoS 符合 §11.3、init publish 初始狀態、colcon build 通過 |
| **L3** | 多 node 共存、gate/ack 有 timeout、Level B 驗收、clean/start 腳本、preflight 涵蓋 |
| **L4** | Demo 流程文件、連續 3 次 cold start 成功、記憶體預算確認、降級策略、展示前 SOP |

**模組整合等級快照（2026-03-18 更新）：**

| 模組 | 當前等級 | 下一步 | 備註 |
|------|:--------:|--------|------|
| 語音（STT/TTS/LLM Bridge） | Level 3 | Level 4（Demo SOP + cold start 驗收） | E2E demo 已錄（5/6 輪通過）；「停止」被 Whisper 幻覺吃掉、VAD 延遲不穩待修 |
| 人臉（YuNet/SFace） | Level 2 | Level 3（與語音整合測試） | ROS2 package scaffold 完成、launch + config + tmux 腳本就緒 |
| AI 大腦（Cloud LLM） | Level 2 | Level 3（多模組事件整合） | Qwen2.5-7B-Instruct on RTX 8000（vLLM 0.17.1），Jetson E2E 已通 |
| PawAI Studio | Level 2 | Level 3（前端開發中） | Mock Server + 4 panel routes + placeholder + spec 交接完成 |
| 手勢 | 研究中 | Level 1（方案確定，待實作） | README 大幅擴充：MediaPipe vs RTMPose 評估、D435 坑、驗收 SOP；v2.1 gesture enum DEFERRED 到 3/25 |
| 姿勢 | 研究中 | Level 1（方案確定，待實作） | README 補 6 章節：備案、2D/3D 選型、D435 depth、推論成本、最小 Demo |

### 11.6 多 Agent 並行開發流程

| 角色 | 職責 |
|------|------|
| **Architect** | 拆功能為子模組 spec、定義介面契約、決定整合順序 |
| **Builder** (×N) | 各自在 worktree 開發子模組，通過 Level A。**不可自行變更共享契約** |
| **Reviewer** | 對 Builder 產出做 code review |
| **Integrator** | merge 到主線，決定合併順序與衝突優先級 |
| **Validator** | 對整合後主線跑 Level B 驗收 |

```
Architect: spec → 拆 N 子模組 → Dispatch N Builder（worktree）
  → Builder: 實作 → smoke → Reviewer → commit
  → Integrator: 按順序 merge
  → Validator: Level B 驗收 → 通過 → main
```

**前提**：子模組介面 spec 層凍結、Builder 只碰自己的檔案範圍、共享 schema 由 Architect 先建好。

### 11.7 Code Review 規範

**預設 checkpoint-based（快）**：Builder 完成 chunk → code-reviewer → 不通過就地修 → 通過 commit。

**升級 PR-based（嚴）** 條件（任一）：改 event/state/topic/schema、碰整合分支或 main、影響多模組介面、影響 demo 主線、改驗收工具或部署流程（預設高風險）。

| Layer | 時機 | 工具 | 性質 | 狀態 |
|:-----:|------|------|------|:----:|
| 1 | 每次 Edit/Write | 專案級快檢（py_compile；前端：eslint） | 自動，阻擋 | 已有 |
| 2 | 每個 chunk | code-reviewer agent | 手動，阻擋 | 已有 |
| 3 | 整合前 PR | code-reviewer + codex/haiku | 正式，阻擋 | 已有 |
| 4 | 對話結束 | Stop hook (codex + haiku) | 僅補充意見，**不作 merge gate** | 已有 |

> **Target**：Layer 1 擴充 ruff + 全路徑 eslint。

---

## 附錄：關鍵決策摘要 (v2.0)

| 決策項目 | 選定方案 | 決策理由 |
|----------|----------|----------|
| 主線方向 | 多模態人機互動 | 核心是人臉+語音+AI 大腦，不是導航 |
| 語音架構 | 本地保底 + 雲端增強 | ASR/TTS 本地低延遲，LLM 雲端高品質 |
| 喚醒詞 | Sherpa-onnx KWS | 中文原生、離線、Apache 2.0、省電門禁 |
| 人臉方案 | 純本地 YuNet + SFace | 已覆蓋 Demo 需求，不上雲 |
| AI 大腦定位 | 系統中樞大腦 | 事件理解 + 技能調度 + panel orchestration |
| 雲端主腦 | Qwen2.5-7B-Instruct (vLLM) | Qwen3.5-9B 不可用（多模態，啟動過慢） |
| 本地 fallback | Qwen2.5-0.8B INT4 | 雲端斷線備援（智商待測） |
| 降級策略 | 四級降級 | 雲端 → 0.8B → Rule → 最小保底 |
| TTS | edge-tts（雲端主線）+ Piper（本地 fallback） | edge-tts 速度快音質佳；MeloTTS/ElevenLabs 已淘汰 |
| 網站策略 | 雙站（Studio + Docs） | 同 repo、分開部署，各司其職 |
| Studio 技術棧 | React-based（暫定 Next.js） | 待正式確認 |
| Docs 技術棧 | Astro + Starlight | 效能高、現代、適合文件 |
| 動作範圍 | P0-safe 優先 | 以「穩」為準，不是「酷」 |
| 分工策略 | Roy 做地基，其他人做應用 | 讓遠端無設備的人也能分工 |

---

*最後更新：2026-03-26*
*維護者：System Architect*
*狀態：v2.3（+3/26 會議更新：時程至 6 月、文件分工、物體辨識策略、LiDAR 放棄）*
