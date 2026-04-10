# PawAI Mission 入口頁

> Status: current

**專案名稱**：老人與狗 (Elder and Dog) / PawAI
**文件版本**：v2.3
**定案日期**：2026-03-07
**最後更新**：2026-04-08
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

> **PawAI 是一隻能在家中主動感知、主動回應，並在需要時主動靠近人的居家守護犬。**

它不是一台會聊天的機器狗，也不是固定監視器，而是一個有在場感的家庭守護實體。平常安靜待命；看見家人時主動辨識與互動；看見陌生人、異常情況或收到召喚時，用聲音、動作、警示與靠近行為做出回應。

**為什麼非 Go2 不可**：如果只想做辨識和通知，用攝影機就夠了。但 PawAI 要做的是一個會認人、會回應、必要時會靠近人的守護實體——embodied presence + active response + physical approach，這需要實體機器狗。

**雙版架構**：
- **主案（無雷達）**：定點守護犬 — 熟人辨識、陌生人警戒、語音/手勢互動、異常警示、Studio 遠端觀測
- **升級案（有雷達）**：短距主動守護犬 — 在主案基礎上增加短距安全靠近、預設短路線、到點查看

> 完整設計規格見 [`docs/superpowers/specs/2026-04-10-guardian-dog-design.md`](../superpowers/specs/2026-04-10-guardian-dog-design.md)

**PawAI Studio** 是守護犬的控制台與 Demo 觀測入口：

> 集 chat 語音入口、即時影像串流、感知面板、guardian mode 顯示於一身。Demo 時筆電端開啟 Studio，作為語音收音 + 系統監控的唯一介面。

---

## 3. 專案背景與交付目標

### 3.1 專案起源

本專案以 Unitree Go2 Pro 為載體，打造面向家庭場景的居家守護犬原型。核心不是「更會聊天」，而是「能把家庭情境轉成守護行為」的 embodied guardian agent。

**核心價值**：
- **Guardian Brain**：三層決策架構（Safety → Policy → Expression），harness-oriented design
- **多模態感知**：人臉 + 語音 + 手勢 + 姿勢 + 物體，服務五個守護場景
- **PawAI Studio**：守護犬控制台，即時影像 + guardian mode + 事件推播
- **可降級、可觀測**：四級語音 fallback、skill contract、pre-action validation
- 模組化整合（Clean Architecture + 標準介面），可分工、可遠端開發

**目標場景**：居家守護（熟人辨識、陌生人警戒、召喚回應、異常警示、日常陪伴）。

### 3.2 交付目標 (4/13 硬底線)

| 里程碑 | 日期 | 交付內容 | 狀態 |
|--------|------|----------|:----:|
| 功能閉環凍結 | 3/12 | 8 個功能的本地/雲端拆分確認（本文件） | ✅ |
| 攻守交換 | 3/16 | Roy 交出架構核心，其他成員接手前端與文件 | ✅ |
| 前端網站截止 | 3/26 | 前端頁面完成，Roy 審查後告知修改項目 | ✅ |
| 四功能整合測試 | 3/26 – 4/2 | 人臉 + 語音 + 手勢 + 姿勢整合驗證 | ✅ |
| 五功能整合 + Studio | 4/7 | 物體辨識 + Studio Chat 閉環 + Live View | ✅ |
| P0 穩定化 | 4/6 | Demo 主線成功率 >= 90% | ✅ |
| 外接 LiDAR 定案 | **4/14** | 確認是否採購 + 型號（學校借用 or 新購） | 🔄 |
| **文件繳交** | **4/13** | **專題文件繳交（目標 60+ 頁，目前 46 頁）** | 🔄 |
| PAI Docs 網站骨架 | 4/12 | Astro + Starlight 框架 + 基本內容 | 🔄 |
| **省夜 Demo** | **5/16** | **完整系統展示（省級評審）** | |
| **正式展示** | **5/18** | **最終發表** | |
| 口頭報告 | 6 月 | 口頭報告答辯 | |

---

## 4. 系統載體與算力配置

### 4.1 硬體配置總覽

| 層級 | 設備 | 規格 | 用途 | 狀態 |
|------|------|------|------|:----:|
| **機器人載體** | Unitree Go2 Pro | 12 關節四足、內建 LiDAR/IMU | 運動執行、環境感知 | ✅ |
| **邊緣運算** | NVIDIA Jetson Orin Nano SUPER | 8GB 統一記憶體、67 TOPS | 即時感知、本地推理、ROS2 runtime | ✅ 已上機 |
| **視覺感測** | Intel RealSense D435 | RGB-D 深度攝影機 | 人臉偵測、手勢/姿勢/物體辨識 | ✅ 已上機 |
| **音訊輸出** | USB 外接喇叭 (CD002-AUDIO) | USB DAC | TTS 語音播放（效果良好） | ✅ 已上機 |
| **音訊輸入（Demo）** | 筆電內建麥克風 | via PawAI Studio 網頁 | Demo 語音收音主線（最乾淨） | ✅ 主線 |
| ~~音訊輸入（機身）~~ | ~~USB 麥克風 (UACDemoV1.0)~~ | ~~mono, 48kHz~~ | ~~Go2 機身收音~~ | ❌ 廢棄 |
| **供電** | XL4015 降壓模組 | Go2 電池 → 20V → Jetson | Jetson 供電 | ⚠️ 不穩 |
| **外接 LiDAR（評估中）** | RPLIDAR A2M12 | 12m / 16000次/秒 / 360° | SLAM 建圖 + 導航避障 | 🔄 4/14 定案 |
| **遠端算力** | 5× NVIDIA Quadro RTX 8000 | 每張 48GB VRAM，總 240GB | LLM 推理、ASR、雲端增強 | ✅ |

> **4/8 確認**：Jetson、D435、外接喇叭、XL4015 已全部正式安裝至 Go2 機體。
>
> **⚠️ 供電風險**：XL4015 降壓板在 Go2 運行中反覆斷電（累計 8+ 次），電壓已調至 20V（Jetson 安全極限 9-20V），同時運行多項功能時耗電增加導致電壓下降觸發強制關機。Demo 時有斷電風險。
>
> **麥克風決策（4/8 會議）**：Go2 風扇噪音極大，機身 USB 麥克風幾乎無法使用（實測需講 5 次才可能聽到 1 次）。Demo 改用筆電端麥克風，透過 PawAI Studio 網頁 WebSocket → Gateway → ROS2 pipeline 收音，效果最乾淨。

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
| 外接 LiDAR driver (rplidar_ros2) | ~0.05 GB | 常駐（若採購） |
| slam_toolbox (online_async) | ~0.3 GB | 常駐（若啟用 SLAM） |
| Nav2 (AMCL + controller, composed) | ~0.5-0.8 GB | 常駐（若啟用導航） |
| 安全餘量 | >= 0.8 GB | 必須保留 |

> **SLAM/Nav2 資源評估（4/8 調查結果）**：
>
> | 指標 | 數據 | 判定 |
> |------|------|:----:|
> | RAM（SLAM+Nav2 新增） | ~0.85-1.15 GB | ✅ 安全（總計 ~3.5-4.7 GB / 8 GB，剩 3.3-4.5 GB） |
> | CPU（slam_toolbox async） | ~70%（x86 基準，ARM 更高） | ⚠️ 風險點 |
> | GPU | 0%（slam_toolbox 純 CPU） | ✅ 無衝突 |
> | LiDAR 頻率需求 | 5-10 Hz（RPLIDAR A2 原生 10Hz，充足） | ✅ |
>
> **結論**：RAM 安全，CPU 是唯一風險。建議 Demo 導航場景時暫時關閉 Gesture Recognizer（省 CPU），因導航不需手勢。
> 配置建議：`online_async` mode + `resolution: 0.15` + `minimum_travel_distance: 0.5` + Nav2 node composition + swap 4-8 GB。
> 參考：Waveshare UGV Beast 已有 Jetson Orin Nano + RPLIDAR + SLAM + Nav2 完整教學，證明硬體層面可行。

---

## 5. 八大功能閉環設計 (v2.3 — 居家守護犬版)

### 5.1 功能總覽與守護犬角色

> **設計原則**：所有功能服務於五個守護場景（熟人回家、使用者召喚、陌生人警戒、異常偵測、日常待命），不是功能拼盤。

| # | 功能 | 守護犬角色 | 本地/雲端 | 狀態 |
|---|------|-----------|:---------:|:----:|
| 1 | 語音功能 | 輔助互動層：問候、簡答、警示 | 雲端主線 + 本地 fallback | ✅ Chat 閉環 12 句通過（4/8），E2E ~2s |
| 2 | 人臉辨識 | **核心支柱**：熟人/陌生人區分 | 純本地 | ✅ greeting 可靠化（4/6），缺陌生人警戒邏輯 |
| 3 | 手勢辨識 | 互動控制層：wave=過來、stop=停 | 本地 | ✅ 上機 5/5 PASS（4/4），缺 wave/point 映射 |
| 4 | 姿勢辨識 | 狀態感知層：次要警示 | 本地 | ✅ 上機 4/4 PASS（4/4），跌倒幻覺高、不押主賣點 |
| 5 | AI 大腦 (Guardian Brain) | **系統核心**：三層決策引擎 | 雲端為主 | 🔄 從規則機升級中 |
| 6 | 辨識物體 | 場景強化器：少量白名單提醒 | 本地（YOLO26n） | ✅ Executive 整合完成（4/6），cup ✅ bottle ❌ |
| 7 | 導航避障 | 候選升級能力：短距安全移動 | 外接 LiDAR + 本地 | 🔄 D435 停用，RPLIDAR 評估中（4/14 定案） |
| 8 | PawAI Studio | 守護犬控制台：遠端觀測+互動 | N/A | ✅ Chat + Live View 閉環通過（4/7） |

### 5.1.1 Guardian Brain 架構（4/10 新增）

```
Guardian Brain（高階決策）→ Executive（唯一動作出口）→ Go2
Brain 不直接執行，Executive 才執行。
```

三層：
- **Layer A Safety**（Executive 內）：stop / obstacle / emergency / banned_api / pre-action validation — 永遠 deterministic，不經 LLM
- **Layer B Policy**（Brain）：guardian context → 意圖判斷 → skill selection → tool selection — 規則 + 記憶 + function calling
- **Layer C Expression**（Brain）：reply_text / tone / wording / Studio trace — LLM 語言能力

降級：LLM 掛 → 固定台詞 / Groq 掛 → RuleBrain / 全掛 → Safety Layer 仍跑

### 5.1.2 Demo P0 場景（5/16 省夜 Demo，3 分鐘）

| 時間 | 場景 | 演出重點 |
|------|------|---------|
| 0:00-0:20 | 日常待命（開場帶過） | 安靜待命，Studio 顯示 guardian idle |
| 0:20-1:00 | **熟人回家** | 辨識→個人化問候→動作，回答「不是攝影機」 |
| 1:00-1:45 | **使用者召喚** | 語音/手勢→回應→互動，回答「不是聊天 bot」 |
| 1:45-2:30 | **陌生人警戒** | 未註冊→警戒→Studio 推播，回答「為什麼是守護犬」 |
| 2:30-3:00 | 收尾 | 口頭補異常偵測+雷達升級 |

### 5.2 功能 1：語音功能

#### Demo 主線鏈路（4/8 會議定案：全雲端 + Studio 語音入口）

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

> **機身 ASR 已廢棄**：Go2 風扇噪音導致機身 USB 麥克風辨識率 ~20%，改走 Studio 網頁收音。

#### 本地保底鏈路（Jetson 8GB，斷網用）

```
Energy VAD 持續監聽（always-on，無喚醒詞）
  → Whisper Small (faster-whisper CUDA float16, ~12s warmup)
  → Intent 分類 → RuleBrain 模板回覆
  → Piper 本地 TTS → USB 外接喇叭
```

#### 四級降級策略

| Level | 條件 | 行為 |
|:-----:|------|------|
| 0 | 雲端正常 | Cloud Qwen2.5-7B 完整對話 + edge-tts + Studio 全功能 |
| 1 | 雲端 LLM 斷線 | 自動切換 Ollama qwen2.5:1.5b 基本對話 + edge-tts |
| 2 | 雲端全斷（LLM+TTS） | RuleBrain 模板回覆 + Piper 本地 TTS |
| 3 | 最小保底 | ASR + Intent fast path + RuleBrain + Piper（停止/掰掰/打招呼） |
| **B** | **Demo 緊急（Plan B）** | **固定台詞腳本模式（~0.x 秒回應）**：預設問答如「你好」「你叫什麼名字」「你有什麼功能」等，ASR 判斷意圖後直接匹配固定回答。Studio 顯示連線狀態燈號，團隊即時判斷是否切換。 |

> **Plan B 設計（4/8 會議決定）**：需準備兩版 Demo 對話腳本——Plan A（雲端 AI 正常對話）和 Plan B（本地固定台詞）。GPU 雲端曾意外斷線兩次，Plan B 為必備保險。必要時出示錄影作為 AI 對話功能佐證。

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
| ASR（雲端主線） | SenseVoice Cloud (FunASR, RTX 8000) | ~430ms，三級 fallback：cloud → SenseVoice local → Whisper |
| ASR（本地 fallback） | Whisper Small (faster-whisper CUDA float16) | 本地離線，RTF 0.13，有幻覺問題（過濾規則已建）。**上機後表現極差，長句辨識失敗，噪音干擾嚴重** |
| 本地 LLM | Ollama qwen2.5:1.5b | 雲端斷線 fallback。**4/8 會議確認：智商極低，胡言亂語，完全不靠譜** |
| 雲端 LLM | Qwen2.5-7B-Instruct (vLLM) | 系統中樞大腦，Prefix Cache 後延遲 ~1.5s |
| TTS（雲端主線） | edge-tts（微軟） | P50 0.72s，速度極快（~1 秒內完成合成） |
| TTS（本地 fallback） | Piper huayan | 速度尚可，比雲端稍慢（~2.0s）。**可作為斷網備案** |

> **本地方案總結（4/8 會議確認）**：Whisper 本地 ❌、Qwen 0.8B 本地 ❌、Piper 本地 ⚠️ 僅備案。語音全鏈路依賴雲端，因此 Plan B 固定台詞腳本為必備保險。

#### 核心檔案

- `speech_processor/speech_processor/stt_intent_node.py` — ASR + Intent 整合節點
- `speech_processor/speech_processor/tts_node.py` — TTS + Go2/USB 播放（edge-tts/Piper/MeloTTS/ElevenLabs）
- `speech_processor/speech_processor/llm_bridge_node.py` — LLM 三級 fallback + Go2 動作
- `scripts/start_llm_e2e_tmux.sh` — 主線啟動腳本（edge-tts + USB 外接設備）

### 5.3 功能 2：人臉辨識

#### 定位

**純本地主線，不上雲。** YuNet + SFace + IOU 追蹤，greeting 可靠化完成（4/6）。

#### 核心能力

- YuNet 2023mar 偵測（CPU 71.3 FPS）+ SFace 2021dec 識別
- IOU 追蹤（multi-face tracking）
- Hysteresis 穩定化（sim_threshold_upper=**0.30** / lower=**0.22**，stable_hits=**2**）
- 深度距離估計（D435 aligned depth，median filtering）
- 2 分鐘 smoke test：`identity_stable: roy` 21 次（調前 1-3 次），零誤認

#### 已知問題（4/8 會議確認）

- **重複觸發打招呼**：同一人短時間內重複觸發，尚未設定冷卻時間（待 Roy 修）
- **光線不足誤判**：低光環境偶爾出現誤判（如顯示錯誤人名）
- **無人幻覺**：無人時偶爾誤判有人臉存在
- **多人骨架亂跳**：多人同時出現時追蹤混亂，無法正確區分
- track 抖動仍在（45 tracks/2min，目標 ≤5），根因是 YuNet 偵測不穩定

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

> 3/21 benchmark 後選定。CPU-only 但 FPS 足夠。上機驗收 5/5 PASS（4/4）。

- **主線**：MediaPipe Gesture Recognizer（stop / thumbs_up / ok / fist / wave / point）
- **備援**：RTMPose wholebody（rtmlib + onnxruntime-gpu）
- **有效距離**：約 **2m**（距離過遠不精準）
- **限制**：僅支援單人偵測，多人時會混亂
- **待擴充（4/8 會議）**：組員各自開發新增手勢種類與對應互動行為
- 上機驗收通過：stop/thumbs_up/非白名單/距離/dedup 全 PASS

> 詳見 [`docs/手勢辨識/README.md`](../手勢辨識/README.md)

### 5.5 功能 4：姿勢辨識 🔄

**主線：MediaPipe Pose**（CPU 18.5 FPS，17 keypoints COCO format）。

> 3/21 benchmark 選定。上機驗收 4/4 PASS（4/4）。

- **主線**：MediaPipe Pose（standing / sitting / crouching / fallen / bending）
- **備援**：RTMPose lightweight（GPU，與 Whisper 共存需注意 VRAM）
- **跌倒偵測**：`enable_fallen` 已參數化（4/6），Demo 可關閉避免誤報
- **限制**：僅支援單人追蹤，多人時只追蹤一人
- **已知問題（4/8 會議確認）**：跌倒幻覺仍頻繁（無人時誤判有人跌倒，鎖定衣架等物體）。因專題已不以老人照護為主題，**跌倒偵測功能可考慮弱化**
- L3 壓測 60s 通過（RAM 1.2GB, 52°C, GPU 0%）

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

**核心五功能之一**（3/18 會議定案）。Executive 整合完成（4/6）。

**模型**：YOLO26n ONNX + onnxruntime-gpu TensorRT EP FP16，Jetson 上 15 FPS 穩定。

**策略**：預設目標辨識（指定日常物品），非自由搜尋。COCO 80 class 全開，白名單篩選。

**實測結果（4/6 上機驗證）**：

| 物品 | 結果 | 備註 |
|------|:----:|------|
| 杯子 (cup) | ✅ | threshold 0.5，觸發 TTS「你要喝水嗎？」 |
| 手機 | ✅ | 適當光線下可辨識 |
| 行李箱 | ✅ | 較大物體偵測良好 |
| 書本 (book) | ⚠️ | 平放時困難，翻開展示可辨識（threshold 0.3 下偶爾偵測） |
| 水瓶 (bottle) | ❌ | 未偵測到，Demo 不展示 |

**已知限制**：
- **光線不足時小物體幾乎無法辨識**
- 物體需在一定高度且正對攝影機角度才能偵測到
- YOLO26n 小物件偵測率低，yolo26s 升級為後續改善方向
- **待決定**：組員篩選適合室內場景的 COCO 類別

### 5.8 功能 7：導航避障 (P2 → 外接 LiDAR 評估中)

#### 現況

**D435 方案停用**（4/3）— 鏡頭角度限制，軟體無法克服。
**外接 LiDAR 方案評估中**（4/8 會議）— 老師同意嘗試，4/14 前定案。

#### D435 方案失敗歷史

LiDAR 正式放棄（3/26）→ D435 反應式避障實作 + 桌測通過（4/1）→ Go2 上機 3 輪防撞測試全失敗（4/3）→ 停用。根因：鏡頭裝太高，低處障礙物只有 ~0.4m 才進 FOV + 延遲鏈 ~1-1.5s。

#### 外接 LiDAR 方案（4/8 會議新增）

**背景**：Go2 Pro 內建 LiDAR 覆蓋率僅 18%（22/120 有效點），全網確認沒有人使用 Go2 Pro 成功開發導航功能。外接 LiDAR 直連 Jetson USB，完全繞過 Go2 WebRTC + voxel 解碼瓶頸。

**候選產品**：Slamtec RPLIDAR A2M12（$7,530，12m，16000次/秒，360°）

**評估時程**：
1. 4/9：老師確認學校（黃老師實驗室）是否有舊 LiDAR 可借
2. 若無 → 4/14 前確定採購型號與預算（一萬以下較容易核銷）
3. 到貨後：安裝 + rplidar_ros2 driver + SLAM 建圖 + Nav2 調參

**技術評估（4/8 調查完成）**：
- **RAM：安全** — SLAM + Nav2 新增 ~0.85-1.15 GB，總計 ~3.5-4.7 GB / 8 GB
- **CPU：風險點** — slam_toolbox ~70% CPU（x86 基準），Demo 導航時建議暫關 Gesture Recognizer
- **GPU：無衝突** — slam_toolbox 純 CPU，不搶 GPU
- **LiDAR 頻率：充足** — RPLIDAR A2 原生 10Hz，slam_toolbox 需 5-10Hz
- **供電風險** — LiDAR 馬達加 ~2-5W 可能加劇 XL4015 斷電問題
- **參考案例** — Waveshare UGV Beast 已有 Jetson Orin Nano + RPLIDAR + SLAM + Nav2 完整教學
- 詳見 §4.3 記憶體預算

**移動方案討論（4/8 會議）**：

| 方案 | 可行性 | 說明 |
|------|:------:|------|
| 完全不移動 | 安全但尷尬 | 機器狗不能走路會被質疑 |
| **直線短距移動** | **最小可行** | 辨識到人後直線走 2-3 步，不做左右轉 |
| 辨識後走向人 | 有互動感 | 需控制距離與角度 |
| 尋物（走到物品旁） | 風險高 | 容易被追問「為什麼不能繞過去」 |

> **老師建議**：設計最小移動場景——機器人辨識到使用者後直線走過來互動，展現「主動靠近」。

**文件策略**：4/13 專題文件繳交後不可修改（交檔案非連結），**先賭有 LiDAR，文件中寫入導航功能**。

#### 已完成的工作（保留作為基礎）

- D435 obstacle_avoidance_node（7 tests）+ LiDAR lidar_obstacle_node（13 tests）
- 雙層安全架構 + safety guard heartbeat
- Foxglove 3D dashboard 可視化
- SLAM/Nav2 Gate A-D 驗證框架（見 `docs/archive/refactor/slam-nav2.md`）
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

#### 時程與部署（4/8 會議更新）
- **網域**：掛在 Roy 個人網域下（如 `docs.xxx.xxx` 或 `pai.xxx.xxx`）
- **部署**：GitHub Pages，僅靜態文件
- **骨架**：Roy 本週末（4/12 前）完成 Astro + Starlight 框架
- **內容**：開好空白結構後，組員透過 PR 補充內容；使用 Claude Code 讀取 GitHub 上的專案資料先生成基本內容
- **參考**：黃旭之前整理的 Notion 作為內容來源

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
│  ├─ 音訊裝置 (USB 外接喇叭; 筆電麥克風 via Studio)             │
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

## 7. 團隊分工（4/8 會議更新）

### 7.1 團隊成員

| 成員 | 角色 |
|------|------|
| Roy（盧柏宇） | 專案負責人 / System Architect / Integration Owner |
| 魏宇同 | 前端開發 |
| 黃旭 | 手勢/姿勢研究 → 前端 → 文件 |
| 陳若恩 | 手勢/姿勢研究 → 語音 → 文件 |
| 董威鋒 | 指導老師 / 聯絡人 |

### 7.2 核心分工策略

**關鍵原則**：
- 讓遠端沒有機器狗和設備的人也能開發（用自己的鏡頭，高度 ~30cm 模擬 Go2 視角）
- 語音模組最適合外包：全走雲端 GPU，不需要 Go2 本體
- 開發完成後由 Roy 整合搬移到 Jetson

### 7.3 各角色職責（4/8 會議版）

#### Roy — System Architect / Integration Owner

| 項目 | 說明 |
|------|------|
| 人臉辨識 | 處理冷卻時間、多人問題、精準度調整 |
| 導航避障 | 若有 LiDAR 則全力衝刺（SLAM + 基礎移動） |
| PAI Docs 網站骨架 | 本週末完成 Astro 框架 |
| 專題文件補強 | 背景知識、系統限制擴寫（Claude Code 輔助） |
| 動作觸發整合 | 組員決定手勢/姿勢對應動作後，由 Roy 接上 Go2 |

#### 陳若恩 — 語音互動強化

| 項目 | 說明 |
|------|------|
| 語音互動 | 連接 GPU 雲端，改善對話品質、增加回答長度與智慧度 |
| Plan B 腳本 | 設計固定台詞問答 |

#### 組員（待 4/9 會議正式分配）

| 項目 | 說明 |
|------|------|
| 手勢辨識擴充 | 各自用鏡頭開發新手勢種類與對應互動行為 |
| 姿勢辨識擴充 | 決定偵測哪些姿勢及對應行為 |
| 物體辨識篩選 | 確定要偵測哪些物品類別（室內場景 COCO 篩選） |
| Web UI 改善 | Studio 狀態欄美化、功能頁面充實 |
| 專題文件 | 各自負責模組的 User Story、技術說明 |

#### 黃旭

| 項目 | 說明 |
|------|------|
| 介紹網站前端 | 4/9 由 Roy 確認進度 |
| 文件撰寫 | 各自負責章節 |

### 7.4 文件章節分工（3/26 會議定案，4/13 前繳交 Ch1-5）

| 章節 | 內容 | 負責人 |
|------|------|--------|
| Ch1 | 專題介紹、背景說明 | 共同（參考現有版本修訂） |
| Ch2 | User Story、需求分析 | 魏宇同、黃旭 |
| Ch3 | 系統架構、技術細節（硬體+模型+各模組） | 人臉+導航+語音（Roy）、物體+姿勢（魏宇同/黃旭）、手勢（陳若恩） |
| Ch4 | 問題與缺點、未來展望 | 簡單撰寫 |
| Ch5 | 分工貢獻表、個人心得 | 各自撰寫 |

### 7.5 分工時程

- **4/9（週四）中午 12:15**：Teams 會議正式宣布分工，向 Patrick（董老師）展示目前成果
- **4/13 前**：各自完成文件負責章節
- **4/13 後 – 5/18**：功能開發衝刺（手勢/姿勢/物體/語音/LiDAR）

---

## 8. Demo 與驗收

### 8.1 Demo 策略（4/8 會議更新）

**展示策略**：視覺互動為主 + 網頁語音輔助。語音入口從 Go2 麥克風移到筆電/Studio。

| Demo | 名稱 | 內容 | 成功率 |
|:----:|------|------|:------:|
| A | 主線閉環 | 人出現→辨識→打招呼→語音對話→Studio 同步 | >= 90% |
| B | 視覺互動 | 手勢/姿勢/物體 + 動作 | >= 70% |
| C | Studio 展示 | 一鍵 Demo + Chat + Live View + 面板 | >= 90% |
| D | 移動展示（若有 LiDAR） | 辨識到人後直線走向互動 | 待驗證 |

### 8.2 Demo 流程（4/8 版）

1. 機器人開機，攝影機啟動
2. 辨識到測試者人臉 → 打招呼（語音 + 動作）
3. （若有 LiDAR）機器人直線走向測試者
4. 進行語音對話（筆電 Studio 收音）：自我介紹、回答功能相關問題
5. 測試手勢互動：比 thumbs up → 機器人回應開心動作
6. 物體辨識展示：展示杯子等物品，機器人說出物品名稱
7. 結束互動：說「再見」→ 機器人揮手告別

### 8.3 Demo 環境要求（4/8 會議）

- **光線充足**（開燈），否則物體辨識失效
- **背景乾淨**，減少雜物造成幻覺誤判
- 攝影機視野內**僅保持一人**，避免多人追蹤混亂
- 報告者與測試者**分開站位**（報告者面對觀眾，機器人面對測試者）
- 建議 **Demo 前一週到教室實地測試**

### 8.4 Demo 設備清單

- Go2 Pro 機器人（含全部上機設備）
- 筆電（運行 PawAI Studio + 麥克風收音）
- 穩定網路連線（GPU 雲端）
- 備用：Plan B 腳本、錄影佐證、GPU 日誌

### 8.5 Plan B 策略（GPU 雲端斷線應對）

- 切換固定台詞腳本模式繼續 Demo
- 出示錄影作為 AI 對話功能佐證
- 必要時展示 GPU 日誌證明確實是雲端問題而非造假
- Studio 顯示連線狀態燈號，團隊即時判斷

---

## 9. 風險與降級策略

### 9.1 四級降級（語音 + AI 大腦）

| Level | 名稱 | 觸發條件 | 行為 |
|:-----:|------|----------|------|
| 0 | 雲端完整 | 網路正常 | Qwen2.5-7B-Instruct 完整對話 + Studio 全功能 |
| 1 | 本地 LLM | 雲端斷線 | Qwen2.5-0.8B 基本對話 + 簡化 Studio |
| 2 | 規則模式 | Jetson 記憶體不足 | Rule Intent + 模板回覆 + 狀態顯示 |
| 3 | 最小保底 | 系統壓力極大 | 喚醒 + ASR + 固定指令 |

### 9.2 硬體風險（4/8 新增）

| 風險 | 嚴重度 | 說明 | 應對 |
|------|:------:|------|------|
| **Jetson 供電斷電** | 🔴 | XL4015 降壓板在 Go2 運行中反覆斷電（8+ 次） | 運氣成分，Demo 時盡量減少同時運行功能 |
| **GPU 雲端斷線** | 🔴 | 語音全鏈路依賴雲端，昨天斷線 2 次 | Plan B 固定台詞 + 錄影佐證 |
| **Go2 風扇噪音** | 🟡 | 機身麥克風 ~20% 辨識率 | 已解決：改用 Studio 筆電收音 |
| **Go2 行走摔倒** | 🟡 | 開啟導航後曾多次摔倒 | 最小移動場景（直線短距） |

### 9.3 人臉辨識降級

人臉辨識為純本地，無雲端依賴。唯一風險是 Jetson 記憶體不足時降低偵測頻率。

### 9.4 安全規則

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

## 附錄：關鍵決策摘要 (v2.3)

| 決策項目 | 選定方案 | 決策理由 |
|----------|----------|----------|
| 主線方向 | 多模態人機互動 + 日常提醒 | 結合 LLM + AI 辨識，互動交流為核心 |
| 語音架構 | **全雲端主線** + 本地最小保底 | 本地 ASR/LLM 品質不可用（4/8 確認） |
| 語音入口 | **Studio 筆電麥克風** | Go2 風扇噪音導致機身 ASR 不可用 |
| ASR | SenseVoice Cloud（主線）→ Whisper（fallback） | SenseVoice ~430ms，Whisper 上機後表現差 |
| Demo 備案 | **Plan B 固定台詞腳本** | GPU 雲端不穩，需 0.x 秒回應備案 |
| 人臉方案 | 純本地 YuNet + SFace | 已覆蓋 Demo 需求，不上雲 |
| AI 大腦定位 | 系統中樞大腦 | 事件理解 + 技能調度 + panel orchestration |
| 雲端主腦 | Qwen2.5-7B-Instruct (vLLM) | Qwen3/3.5 棄用（太聰明不受控） |
| 本地 fallback | Qwen2.5-0.8B INT4 | **智商極低，完全不靠譜**（4/8 確認） |
| 降級策略 | 四級降級 + Plan B | 雲端 → 0.8B → Rule → 最小保底 → Plan B 固定台詞 |
| TTS | edge-tts（雲端，~1s）+ Piper（備案） | MeloTTS/ElevenLabs 已淘汰 |
| 物體辨識 | YOLO26n + TensorRT FP16 | Executive 整合完成，cup ✅ bottle ❌ |
| **導航避障** | **外接 LiDAR 評估中** | D435 方案停用，RPLIDAR A2M12 候選，4/14 定案 |
| **移動策略** | **直線短距（最小可行）** | 辨識到人後直線走過來，不做複雜路徑 |
| 網站策略 | 雙站（Studio + Docs） | 同 repo、分開部署 |
| Studio 技術棧 | Next.js 16 + FastAPI Gateway | 已實機驗證（4/7） |
| Docs 技術棧 | Astro + Starlight | Roy 本週末建骨架 |
| 動作範圍 | P0-safe 優先 | 以「穩」為準，不是「酷」 |
| 分工策略 | Roy 整合 + 組員各自鏡頭開發 | 高度 30cm 模擬 Go2 視角 |

---

## 12. 專題文件補強計畫（4/8 新增）

### 12.1 現況

- 目前文件約 **46 頁**，歷屆平均 **80-90 頁**，明顯偏少
- 大部分由 Roy 撰寫（Claude Code 輔助），其他組員貢獻部分有錯誤待修正
- 許多功能尚未確定具體內容，User Story 等章節過於籠統

### 12.2 補強方向

| 項目 | 預估可增加頁數 | 說明 |
|------|:------------:|------|
| 背景知識擴寫 | 10-15 頁 | MediaPipe、YuNet/SFace、YOLO、Qwen、ROS2 等技術詳細介紹 |
| 系統限制說明 | 5-10 頁 | Go2 Pro 硬體限制、LiDAR 問題、開發困難、供電問題 |
| 先前失敗嘗試 | 5 頁 | YOLOWorld、MeloTTS、本地 Whisper、D435 避障等被棄用方案 |
| 功能細節 | 依分工 | 手勢、姿勢、物體、語音各模組的具體設計（組員各自補充） |
| 導航避障（若有 LiDAR） | 5-10 頁 | 新增技術方案與實作說明 |
| **目標** | **60-70+ 頁** | 縮小與其他組的落差 |

### 12.3 撰寫方式

- **Claude Code 輔助擴寫**：讀取 GitHub 上的 PAI 專案文件，自動生成詳細版內容
- 各組員補充各自負責模組的文件
- **4/13（週日）繳交**：交檔案非連結，繳交後無法修改

---

*最後更新：2026-04-08*
*維護者：System Architect*
*狀態：v2.3（+4/8 會議更新：硬體全上機、語音轉 Studio、導航 LiDAR 評估、分工大改、文件補強）*
