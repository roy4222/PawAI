# PawAI Mission 入口頁

**專案名稱**：老人與狗 (Elder and Dog) / PawAI
**文件版本**：v2.0
**定案日期**：2026-03-07
**最後更新**：2026-03-12
**交付期限**：2026/4/13 (硬底線)

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
| 新成員 (黃、陳) | 第 1、2、3、7 節 | [setup/README.md](../setup/README.md) |
| 手勢/姿勢研究 (楊、鄔) | 第 5、6、7 節 | [手勢辨識/README.md](../手勢辨識/README.md) |
| PawAI Studio 前端 (鄔) | 第 5、6、7 節 | [Pawai-studio/README.md](../Pawai-studio/README.md) |
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
| 攻守交換 | 3/16 | Roy 交出架構核心，楊/鄔/黃/陳接手前端與文件 |
| P0 穩定化 | 4/6 | Demo A/C 成功率 >= 90% |
| **最終展示** | **4/13** | **完整系統展示** |

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
│  ├── GPU 0: LLM Brain (Qwen3.5-9B → 27B, vLLM)             │
│  ├── GPU 1: 備用 / 模型實驗                                   │
│  ├── GPU 2-4: 未來擴充（物體辨識、ArcFace 等）                │
│  └── CPU: FastAPI Gateway + Event Bus + PawAI Studio Backend │
└─────────────────────────────────────────────────────────────┘
                          ↑↓ WebSocket / HTTP
┌─────────────────────────────────────────────────────────────┐
│  邊緣端 (Jetson Orin Nano 8GB)                               │
│  ├── 常駐：Sherpa-onnx KWS (~50MB) + YuNet 人臉偵測 (~100MB) │
│  ├── 觸發式：faster-whisper ASR + MeloTTS/Piper              │
│  ├── 降級用：Qwen3.5-0.8B INT4 (~1GB, 僅斷網時載入)          │
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
| MeloTTS / Piper | 0.3-0.8 GB | 觸發式（喚醒後載入） |
| Qwen3.5-0.8B INT4 | ~1.0 GB | 僅斷網降級時載入 |
| 安全餘量 | >= 0.8 GB | 必須保留 |

**省電門禁策略**：喚醒詞觸發前，ASR/LLM/TTS 不載入記憶體。

---

## 5. 八大功能閉環設計 (v1 決策版)

### 5.1 功能總覽與優先序

| # | 功能 | 優先級 | 本地/雲端 | 狀態 |
|---|------|:------:|:---------:|:----:|
| 1 | 語音功能 | **P0** | 本地保底 + 雲端增強 | ✅ 閉環確認 |
| 2 | 人臉辨識 | **P0** | 純本地 | ✅ 閉環確認 |
| 3 | 手勢辨識 | P1 | 本地 | ⏸️ 等研究結論 |
| 4 | 姿勢辨識 | P1 | 本地 | ⏸️ 等研究結論 |
| 5 | AI 大腦 (PawAI Studio) | **P0** | 雲端為主 | ✅ 閉環確認 |
| 6 | 辨識物體 | P2 | 待定 | P0 穩了再做 |
| 7 | 導航避障 | P2 | 待定 | 最保守，最後才碰 |
| 8 | 文件網站 | **P0** | N/A | ✅ 閉環確認 |

### 5.2 功能 1：語音功能

#### 本地保底鏈路（Jetson 8GB）

```
Sherpa-onnx KWS 常駐 (~50MB)
  → 喚醒成功
  → 播預錄「我在」（掩蓋模型載入時間）
  → 載入本地語音堆疊（ASR + TTS，必要時載入本地小 LLM）
  → faster-whisper Tiny/Small (CTranslate2 CUDA)
  → 雲端 LLM 或本地意圖判定
  → MeloTTS / Piper → Go2 喇叭
  → keep-alive 30s（連續對話免喚醒）
  → 超時自動卸載 / 「掰掰」立即卸載
```

#### 雲端增強模式（RTX 8000）

```
本地 ASR 完成 → 文字送雲端 LLM (Qwen3.5-9B/27B)
  → 雲端做深度理解 / 記憶 / 情感 / 長上下文
  → 回覆文字送回本地 → 本地 TTS 合成播放
  → 若雲端超時 (2-4s) → fallback 到本地
```

#### 四級降級策略

| Level | 條件 | 行為 |
|:-----:|------|------|
| 0 | 雲端正常 | Qwen3.5-9B/27B 完整對話 + Studio 全功能 |
| 1 | 雲端斷線 | 本地 Qwen3.5-0.8B 基本對話 + 簡化 Studio |
| 2 | Jetson 記憶體不足 | Rule Intent + 模板回覆 + 狀態顯示 |
| 3 | 最小保底 | 喚醒 + ASR + 固定指令（停止/掰掰/打招呼） |

#### 語音狀態機

```
idle_wakeword → wake_ack → loading_local_stack → listening
  → transcribing → local_asr_done → cloud_brain_pending
  → speaking → keep_alive → idle_wakeword
  → (雲端超時) → fallback_local_reply → speaking
  → (卸載) → unloading → idle_wakeword
```

#### 關鍵技術選型

| 模組 | 選型 | 說明 |
|------|------|------|
| 喚醒詞 | Sherpa-onnx KWS | 中文原生、離線、Apache 2.0 |
| ASR | faster-whisper (CTranslate2 CUDA) | Whisper Tiny/Small，本地離線 |
| 本地 LLM | Qwen3.5-0.8B INT4 | 僅斷網 fallback 時動態載入，非常駐、非每次必載 |
| 雲端 LLM | Qwen3.5-9B → 27B (vLLM) | 系統中樞大腦 |
| TTS | MeloTTS / Piper | 本地合成，低延遲 |

#### 核心檔案

- `speech_processor/speech_processor/stt_intent_node.py` — ASR + Intent 整合節點
- `speech_processor/speech_processor/tts_node.py` — TTS + Go2 播放
- `speech_processor/speech_processor/intent_tts_bridge_node.py` — Intent → 模板回覆
- `scripts/start_asr_tts_no_vad_tmux.sh` — 主線啟動腳本

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

### 5.4 功能 3：手勢辨識 ⏸️

等楊/鄔 3/16 研究結論後更新。預計方向：MediaPipe Hands，4 種基本手勢（揮手、指向、OK、停止）。

### 5.5 功能 4：姿勢辨識 ⏸️

等楊/鄔 3/16 研究結論後更新。預計方向：MediaPipe Pose / MoveNet，4 種基本姿勢（站立、坐下、蹲下、跌倒）。

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
MiniMax-M2.5 / Qwen3.5 提建議
  → Interaction Executive 做決策
  → Runtime 安全執行
```

#### 雲端主腦 Roadmap

1. **第一版**：Qwen3.5-9B（先跑通大腦鏈路）
2. **第二版**：Qwen3.5-27B（品質升級）
3. **第三版（候選）**：Qwen3.5-35B-A3B 或 MiniMax-M2.5（尚未實測，作為研究候選）

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

### 5.7 功能 6：辨識物體 (P2)

P0 穩了再做。比導航更容易出 Demo 效果，優先於功能 7。

候選方向：YOLO26n（本地，候選）+ YOLO26x（雲端，候選），6 類 P0 物體。模型尚未實測。

### 5.8 功能 7：導航避障 (P2 / 最後才碰 / 不作為主交付依賴)

最保守，最後才碰，**不作為任何 P0 功能的前置依賴**。Go2 LiDAR 頻率過低（<2Hz），完整自主導航不可行。

若 P0 全部穩定且有餘力，僅做極小範圍的 D435 深度避障展示。

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
│  ├─ Brain Adapter → Qwen3.5-9B/27B (雲端) 或 0.8B (本地)    │
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

## 7. 團隊分工（3/12 更新版）

### 7.1 核心分工策略

**3/16 前**：Roy 完成架構核心，讓其他人能在上面開發。
**3/16 後**：楊/鄔轉攻 PawAI Studio 前端與應用層，黃/陳主攻文件網站。

**關鍵原則**：讓遠端沒有機器狗和設備的人也能進行分工。

### 7.2 各角色職責

#### Roy — System Architect / Integration Owner

**3/16 前交付**：
- 語音閉環：stt_intent_node + tts_node + Go2 播放
- 人臉閉環：face_identity_infer_cv.py + 標準 state/event topic
- FastAPI Gateway 骨架 + Event Schema 凍結
- Mock Event Server（讓前端不用等真機就能開發）

**3/16 後**：
- 手勢/姿勢模組部署到 Jetson
- Brain Adapter + Qwen3.5-9B 接入
- 端到端整合測試 + Demo pipeline

#### 鄔 — PawAI Studio 前端主力

**前端元件清單**（不需硬體，純 Next.js + WebSocket）：

| 元件 | 說明 |
|------|------|
| `ChatPanel` | 對話主入口，WebSocket 接 Gateway |
| `CameraPanel` | D435 即時影像 + 人臉框 |
| `FacePanel` | 辨識結果、stable_name、信心度、距離 |
| `SpeechPanel` | ASR 轉寫、Intent、對話歷史 |
| `GesturePanel` | 手勢即時顯示 |
| `PosePanel` | 姿勢狀態 + 骨架渲染 |
| `TimelinePanel` | 事件流時間軸 |
| `SystemHealthPanel` | Jetson CPU/GPU/RAM、模組狀態、延遲 |
| `BrainPanel` | current intent / selected skill / trace |
| `SkillButtons` | Stand / Sit / Wave / Stop 技能按鈕 |
| Demo 頁 | 完整 Demo 流程展示 |

#### 楊 — 手勢/姿勢研究 → 3/16 後轉應用層

| 週次 | 交付物 |
|------|--------|
| 3/16 前 | 手勢方案報告 + 姿勢方案報告 + 小 demo |
| 3/16 後 | Studio 裡的 gesture/pose 互動邏輯、Intent 擴充 |

#### 黃、陳 — 文件網站 + Mock Server

| 交付物 | 說明 |
|--------|------|
| Astro + Starlight 文件站 | 架構演進、踩坑紀錄、環境建置、API 參考 |
| 展示站首頁整合 | Hero 影片 + 功能亮點 + 團隊介紹 |
| Mock Event Server | FastAPI 假資料生成器（讓前端不用等真機） |
| 架構圖 | Draw.io 系統架構、資料流、新舊對比 |

---

## 8. Demo 與驗收

### 8.1 Demo 主線

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
| 0 | 雲端完整 | 網路正常 | Qwen3.5-9B/27B 完整對話 + Studio 全功能 |
| 1 | 本地 LLM | 雲端斷線 | Qwen3.5-0.8B 基本對話 + 簡化 Studio |
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

## 附錄：關鍵決策摘要 (v2.0)

| 決策項目 | 選定方案 | 決策理由 |
|----------|----------|----------|
| 主線方向 | 多模態人機互動 | 核心是人臉+語音+AI 大腦，不是導航 |
| 語音架構 | 本地保底 + 雲端增強 | ASR/TTS 本地低延遲，LLM 雲端高品質 |
| 喚醒詞 | Sherpa-onnx KWS | 中文原生、離線、Apache 2.0、省電門禁 |
| 人臉方案 | 純本地 YuNet + SFace | 已覆蓋 Demo 需求，不上雲 |
| AI 大腦定位 | 系統中樞大腦 | 事件理解 + 技能調度 + panel orchestration |
| 雲端主腦 | Qwen3.5-9B → 27B | 先跑通再升級，不直接衝最大 |
| 降級策略 | 四級降級 | 雲端 → 0.8B → Rule → 最小保底 |
| 網站策略 | 雙站（Studio + Docs） | 同 repo、分開部署，各司其職 |
| Studio 技術棧 | React-based（暫定 Next.js） | 待正式確認 |
| Docs 技術棧 | Astro + Starlight | 效能高、現代、適合文件 |
| 動作範圍 | P0-safe 優先 | 以「穩」為準，不是「酷」 |
| 分工策略 | Roy 做地基，其他人做應用 | 讓遠端無設備的人也能分工 |

---

*最後更新：2026-03-12*
*維護者：System Architect*
*狀態：v2.0（功能閉環決策版）*
