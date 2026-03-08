# PawAI Mission 入口頁

**專案名稱**：老人與狗 (Elder and Dog) / PawAI  
**文件版本**：v1.1  
**定案日期**：2026-03-07  
**最後更新**：2026-03-08  
**交付期限**：2026/4/13 (硬底線)

> **v1.1 更新**：修正 D435 麥克風錯誤資訊、新增會議紀錄補充文件連結

---

## 1. 文件定位與閱讀方式

### 這份文件是什麼

這是 PawAI Mission 的**入口頁 (Entry Point)**，負責整合專案的核心決策、系統輪廓、主副線分工與關鍵導覽。

**定位說明**：
- 不取代模組設計文件，而是**摘要 + 連結**
- 不取代介面契約文件，而是**決策脈絡 + 驗收目標**
- 提供**單一真相來源 (Single Source of Truth)** 給全團隊

### 誰應該閱讀

| 角色 | 閱讀重點 | 延伸文件 |
|------|----------|----------|
| 新成員 (黃、陳) | 第 1、2、3、7 節 | [setup/README.md](../setup/README.md) |
| Face Owner (楊) | 第 5、6、7 節 | [人臉辨識/README.md](../人臉辨識/README.md) |
| Speech Owner (鄔) | 第 5、6、7 節 | [語音功能/README.md](../語音功能/README.md) |
| Frontend (鄔) | 第 6、7、8 節 | [face_dashboard_nextjs/README.md](../../face_dashboard_nextjs/README.md) |
| System Architect | 全篇 + 附錄 | [interaction_v1_contract.md](../architecture/interaction_v1_contract.md) |

### 閱讀順序建議

1. **快速瀏覽**：讀第 2 節 (一句話定位) + 第 6 節 (主副線)
2. **理解架構**：讀第 4、5 節 (硬體與三層架構)
3. **確認分工**：讀第 7 節 (團隊分工)
4. **執行細節**：點選各模組連結深入閱讀

---

## 2. 專案一句話定位

> 以 Unitree Go2 Pro 為載體，建立一套「以人機互動為主、導航避障為輔」的 embodied AI 機器狗系統。
>
> 核心不是把每個功能都做到最強，而是做出一個 **可模組化擴充、可多人分工、可實際展示的互動式系統平台**。

**關鍵詞解讀**：
- **人機互動為主**：人臉辨識、中文語音對話、視覺互動是核心展示價值
- **導航避障為輔**：基礎移動能力支援互動場景，但不追求完整自主導航
- **可模組化**：Layer 2 各感知模組透過標準介面與 Layer 3 大腦連接
- **可展示**：4/13 必須能跑通 Demo A/B/C，成功率高於 90%

---

## 3. 專案背景與交付目標

### 3.1 專案起源

本專案為輔仁大學資管系專題，目標是打造一台「懂爺爺奶奶」的 AI 居家陪伴機器狗。從最初的「尋物功能」逐步演進為「智能互動 AI 夥伴」，核心價值轉向**多模態人機互動**與**情感陪伴**。

### 3.2 為什麼是這個方向

教授會議決議 (2025/12/17)：
> 「尋物功能似不太能發揮亮點，我們再一起想想如何讓 Go2 用 MCP 發揮更多用途」

戰略轉向：
- 尋物只是功能之一，不是全部
- Go2 具備 35+ 內建動作，可透過 MCP 調用
- 目標是「聽得懂人話」的多元互動體驗

### 3.3 交付目標 (4/13 硬底線)

| 里程碑 | 日期 | 交付內容 | 驗收標準 |
|--------|------|----------|----------|
| 介面凍結 | 3/9 | 介面契約 v1、Demo 腳本 | 文件簽核完成 |
| 攻守交換 | 3/16 | 所有模組標準交付 | 各 Owner 提交 DELIVERABLE.md |
| 穩定化 | 4/6 | P0 完成度達標 | Demo A/C 成功率 >= 90% |
| **最終展示** | **4/13** | **完整系統展示** | **三條 Demo 可現場執行** |

### 3.4 展示場景設定

模擬居家客廳：
- 地上有紙箱作為障礙物
- 桌上放著水瓶作為互動道具
- 機器狗能辨識人物、回應語音指令、執行動作

---

## 4. 系統載體與算力配置

### 4.1 硬體配置總覽

| 層級 | 設備 | 規格 | 用途 |
|------|------|------|------|
| **機器人載體** | Unitree Go2 Pro | 12 關節四足、內建 LiDAR/IMU | 運動執行、環境感知 |
| **邊緣運算** | NVIDIA Jetson Orin Nano SUPER | 8GB VRAM、ARM 架構 | 即時感知、本地決策、ROS2 runtime |
| **視覺感測** | Intel RealSense D435 | RGB-D 深度攝影機 | 人臉偵測、深度估計、手勢辨識 |
| **音訊輸入** | USB 麥克風（待採購） | 外接式 | 中文語音輸入（⚠️ D435 無內建麥克風） |
| **遠端算力** | NVIDIA Quadro RTX 8000 | 48GB VRAM × 5 張 | ASR/TTS/LLM、模型訓練、雲端推理 |

### 4.2 算力分工策略

```
┌─────────────────────────────────────────────────────────────┐
│  雲端端 (5×RTX 8000)                                        │
│  ├── 卡 1-2：Qwen2.5-72B-INT4 (對話 LLM)                    │
│  ├── 卡 3：Qwen3-ASR-1.7B (中文語音辨識)                    │
│  └── 卡 4-5：Qwen3-TTS-1.7B + 備援 (語音合成)               │
└─────────────────────────────────────────────────────────────┘
                              ↑↓ 網路 (WebSocket/HTTP)
┌─────────────────────────────────────────────────────────────┐
│  邊緣端 (Jetson Orin Nano 8GB)                              │
│  ├── YuNet + SFace (人臉偵測/識別)                          │
│  ├── ROS2 Humble (系統整合)                                 │
│  ├── Interaction Executive v1 (中控決策)                    │
│  ├── Silero VAD (語音活動偵測)                              │
│  └── USB 麥克風驅動 (ALSA/PulseAudio)                       │
└─────────────────────────────────────────────────────────────┘
                              ↑↓ USB/網路
┌─────────────────────────────────────────────────────────────┐
│  機器人 (Go2 Pro)                                           │
│  ├── 運動控制 (stand/sit/lie/wave/spin)                     │
│  └── 內建感測 (LiDAR/IMU/關節狀態)                          │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 關鍵數字

| 指標 | 數值 | 說明 |
|------|------|------|
| Jetson 可用記憶體 | ~6.5 GB (扣除系統) | 需同時跑視覺+語音+ROS2 |
| D435 影像串流 | 640×480 @ 30 FPS | RGB + Depth 對齊 |
| 人臉偵測延遲 | < 100 ms (YuNet) | Jetson CUDA 優化後 |
| 語音總延遲預算 | < 2.0 秒 | ASR + LLM + TTS 總和 |
| 網路備援切換 | < 3 秒 | 雲端失效時降級本地 |

---

## 5. 三層架構總覽

### 5.1 架構設計原則

- **單一控制權**：所有動作唯一出口在 Layer 3，避免多模組搶控制
- **事件驅動**：Layer 2 各模組發布事件，Layer 3 訂閱後決策
- **介面凍結**：3/9 後 topic/schema/action 不再變更

### 5.2 三層架構圖

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Interaction Executive v1（中控層）                  │
│  ├─ 事件聚合器 (Event Aggregator)                           │
│  ├─ 狀態機 (State Machine)                                  │
│  ├─ 技能分派器 (Skill Dispatcher)                           │
│  ├─ 安全仲裁器 (Safety Guard)                               │
│  └─ 控制權管理 (Control Arbitration)                        │
│  部署：Jetson Orin Nano 8GB                                  │
└─────────────────────────────────────────────────────────────┘
                              ↑↓ ROS2 Topics / Actions
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Perception / Interaction Module Layer              │
│  ├─ 人臉模組 (Face Owner: 楊)                               │
│  │   └─ 輸出：/event/face_detected, /state/perception/face  │
│  ├─ 語音模組 (Speech Owner: 鄔)                             │
│  │   └─ 輸出：/event/speech_intent_recognized               │
│  ├─ 手勢/姿勢模組 (Visual Owner: 楊/鄔)                     │
│  │   └─ 輸出：/event/gesture_detected (P1)                  │
│  └─ 統一輸出：事件 (event) + 狀態 (state)                   │
│  部署：Jetson + 雲端混合                                     │
└─────────────────────────────────────────────────────────────┘
                              ↑↓ ROS2 Topics
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Device / Runtime Layer                             │
│  ├─ Go2 Driver (go2_robot_sdk)                              │
│  ├─ RealSense D435 (realsense2_camera)                      │
│  ├─ 音訊裝置 (ALSA/PulseAudio)                              │
│  ├─ ROS2 Humble (rclpy/rclcpp)                              │
│  └─ 邊緣模型執行 (ONNX Runtime/TensorRT)                    │
│  部署：Jetson Orin Nano + Go2 Pro                           │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 資料流示意

**主線互動流程 (Demo A)**：

```
使用者說話
    ↓
[USB 麥克風] ──→ Layer 1 音訊擷取
    ↓
[雲端 ASR] ──→ 文字轉錄
    ↓
Layer 2 語音模組發布 /event/speech_intent_recognized
    ↓
Layer 3 Interaction Executive 接收事件
    ↓
狀態機決策 → 查詢當前 face_state → 決定回應策略
    ↓
呼叫 TTS 服務 → 發布 /tts 話題
    ↓
Go2 播放語音回應 + 執行對應動作 (wave/stand/look_left)
```

> **注意**：D435 無內建麥克風，需外接 USB 麥克風。詳見 [會議紀錄補充文件](./meeting_notes_supplement.md)

### 5.4 介面契約摘要

**關鍵 Topic**：

| Topic | 類型 | 說明 |
|-------|------|------|
| `/event/face_detected` | Event | 人臉出現/消失事件 |
| `/event/speech_intent_recognized` | Event | 語音意圖識別結果 |
| `/state/perception/face` | State | 人臉追蹤狀態 (10 Hz) |
| `/state/interaction/speech` | State | 語音互動狀態 (5 Hz) |
| `/state/executive/brain` | State | 大腦決策狀態 (5 Hz) |
| `/execute_skill` | Action | 技能執行請求 |

**完整介面規格**請見：[interaction_v1_contract.md](../architecture/interaction_v1_contract.md)

---

## 6. 主線/副線/優先序 (P0/P1/P2)

### 6.1 功能分級總表

| 優先級 | 類型 | 內容 | 4/13 要求 | 負責人 |
|:------:|:----:|------|:---------:|:------:|
| **P0** | 主線 | 人臉辨識 (detection + track_id) | 必交 | 楊 |
| **P0** | 主線 | 中文語音互動 (ASR + TTS) | 必交 | 鄔 |
| **P0** | 主線 | AI 大腦 (Interaction Executive v1) | 必交 | System Architect |
| **P0** | 主線 | 展示網站 (FastAPI + Next.js) | 必交 | 鄔 |
| **P0** | 主線 | 安全動作 (stand/sit/lie/stop) | 必交 | System Architect |
| P1 | 副線 | 手勢辨識 (wave/stop) | 展示亮點 | 楊/鄔 |
| P1 | 副線 | 姿勢辨識 (point/come_here) | 展示亮點 | 楊/鄔 |
| P1 | 副線 | 雲端 LLM 升級 (Qwen3.5) | 備援用 | System Architect |
| P2 | 輔助 | 基礎導航/避障 | 加分項 | System Architect |
| P2 | 輔助 | 喚醒詞 | 加分項 | - |

### 6.2 P0 詳細說明

**人臉辨識**：
- 採用 YuNet + SFace 方案
- 輸出：track_id (session 追蹤)、distance_m (深度距離)
- 不做持久註冊，只做 session-level 追蹤
- 詳見：[人臉辨識/README.md](../人臉辨識/README.md)

**中文語音**：
- 雲端優先 + 離線備援架構
- ASR：Qwen3-ASR-1.7B (RTX 8000)
- TTS：Qwen3-TTS-1.7B (RTX 8000)
- 離線降級：Whisper tiny + MeloTTS (Jetson)
- 延遲預算：< 2.0 秒 (push-to-talk 到 TTS 播放)
- 詳見：[語音功能/README.md](../語音功能/README.md)

**展示網站**：
- 一站雙區：Showcase (實時監控) + Docs (文件展示)
- 技術棧：FastAPI (後端) + Next.js (前端)
- 功能：事件時間線、brain state 監控、一鍵 Demo、技能按鈕

### 6.3 時程與優先序對照

| 週次 | 日期 | 重點 | 交付目標 |
|------|------|------|----------|
| W1 | 3/7-3/9 | 定案 + 介面凍結 | 本文件 v1.0、介面契約凍結 |
| W2 | 3/10-3/16 | 模組開發 | 各 Owner 提交 DELIVERABLE.md |
| W3 | 3/17-3/23 | P0 穩定化 | Demo A/C 成功率 >= 85% |
| W4 | 3/24-3/30 | P1-1 | 手勢或姿勢上一個，Demo B >= 70% |
| W5 | 3/31-4/6 | P1-2 | 補齊另一個，Website 達標 |
| W6 | 4/7-4/13 | 總彩排 | 凍結功能、只修穩定度 |
| **最終** | **4/13** | **展示日** | **三條 Demo 現場執行** |

---

## 7. 五人分工與責任邊界

### 7.1 RACI 風格分工表

| 任務 | System Architect (你) | 楊 (Face) | 鄔 (Speech/Web) | 黃 | 陳 |
|------|:---------------------:|:---------:|:---------------:|:--:|:--:|
| **專案架構設計** | R/A | C | C | I | I |
| **介面契約凍結** | R/A | C | C | I | I |
| **Go2/Jetson 底層** | R/A | C | I | I | I |
| **人臉模組開發** | C | R | I | C | C |
| **語音模組開發** | C | I | R | C | C |
| **手勢/姿勢研究** | A | R | R | C | C |
| **前端展示開發** | C | I | R/A | C | C |
| **AI 大腦 (Executive)** | R/A | C | C | C | C |
| **系統整合測試** | R/A | C | C | C | C |
| **文件整理** | A | C | C | R | R |
| **Demo 腳本/彩排** | R/A | C | C | C | C |

**符號說明**：
- **R** (Responsible)：執行者，負責完成任務
- **A** (Accountable)：責任者，最終負責、需核准
- **C** (Consulted)：諮詢者，提供意見
- **I** (Informed)：知會者，事後告知

### 7.2 各角色詳細職責

#### System Architect / Integration Owner

**負責 (R/A)**：
- 三層架構設計與介面契約凍結
- Interaction Executive v1 (state machine + skill dispatcher)
- Safety guard 與 control arbitration
- Layer 1 (Go2 driver、Jetson runtime、D435、音訊)
- 系統 bring-up (單一 launch 流程)
- 網路降級策略 (Cloud On/Off + 本地備援)
- 最終整合與 demo pipeline

**協作 (C)**：
- 與 Face Owner 協調 face event 欄位
- 與 Speech Owner 協調 intent label/slots
- 與 Frontend Owner 協調 website 顯示所需狀態流

#### Face Owner (楊)

**負責 (R)**：
- Face module (RGB frame → FaceDetections)
- track_id 穩定策略 (session 內穩定)
- confidence/bbox/distance_m 輸出
- 3/16 前：手勢/姿勢研究
- 3/16 後：轉攻語音/人臉應用層 (依 Architect 調度)

**交付**：
- `DELIVERABLE.md` (啟動指令、輸入輸出、需求、限制、驗證方式)
- Demo 成功率達標 (90%)

#### Speech Owner / Frontend Lead (鄔)

**負責 (R)**：
- 中文 ASR → intent (固定 intent 集)
- Push-to-talk 流程設計
- TTS node 串接
- 展示網站 (FastAPI + Next.js)
- 3/16 前：手勢/姿勢研究
- 3/16 後：前端展示主力 + 語音/人臉應用層

**交付**：
- Speech module `DELIVERABLE.md`
- Website `DELIVERABLE.md`
- 延遲量測報告

#### 支援成員 (黃、陳)

**負責 (R)**：
- 文件整理與歸檔
- 支援各模組測試
- 後續切入技術工作 (依進度調度)

**交付**：
- 文件維護
- 測試報告

---

## 8. Demo 與驗收重點

### 8.1 三條 Demo 路線

| Demo | 名稱 | 內容 | 成功率要求 | 延遲要求 |
|:----:|------|------|:----------:|----------|
| A | 主線閉環 | 人臉 + 語音 + 回應 | >= 90% (9/10) | 語音 < 2.0s |
| B | 視覺互動 | 手勢/姿勢 + 動作 | >= 70% (7/10) | 視覺 < 1.0s |
| C | 網站同步 | 一鍵 Demo + 狀態顯示 | >= 90% (9/10) | 同步 < 300ms |

### 8.2 Demo A：人臉 + 語音 + 回應 (P0 主線)

**流程**：
1. Face module 發布 `/event/face_detected`
2. 使用者 Push-to-talk 說中文指令
3. Speech module 發布 `/event/speech_intent_recognized`
4. Brain 更新 `/state/executive/brain`
5. Brain 發布 `/tts` (中文回應)

**驗收標準**：
- 成功率：10 次中 >= 9 次成功
- 語音延遲：Push-to-talk 放開到 `/tts` 發布 <= 2.0 秒
- 視覺更新：FaceDetections >= 10 Hz
- 可觀測性：Website 事件流看到完整鏈路

### 8.3 Demo B：視覺互動分支 (P1 亮點)

**流程**：
1. FaceDetections 有 focused_track_id
2. 手勢/姿勢事件觸發
3. Brain 觸發 `ExecuteSkill.action`
4. 回覆 `/tts` + `/state/brain` 更新

**驗收標準**：
- 成功率：10 次中 >= 7 次成功
- 延遲：視覺事件到 Skill 開始 <= 1.0 秒
- 安全：`stop` 必須可打斷其他 skill (最高優先級)
- 彈性：若手勢不穩，可改姿勢或簡化指向

### 8.4 Demo C：網站同步展示 (產品感)

**流程**：
1. 使用者 Push-to-talk 或按網站「Demo C」按鈕
2. Brain 進入 `mode=demo`，逐步更新 `/state/brain`
3. Website 顯示進度條、狀態轉移、最終輸出

**驗收標準**：
- 成功率：10 次中 >= 9 次成功
- 同步延遲：BrainState 更新到 Website 畫面 <= 300 ms
- 降級保證：拔掉雲端仍可用按鈕完整跑完 Demo C

### 8.5 立即行動清單 (3/7-3/9)

- [ ] **Architect**：宣布介面契約 v1 於 3/9 凍結
- [ ] **全員**：收到 DELIVERABLE.md 模板後填寫骨架
- [ ] **鄔**：先把 Website 做出「一鍵 Demo + brain state 監控」
- [ ] **Architect**：準備 Bring-up 手冊與故障排查第一版

### 8.6 未定事項與決策時程

以下項目會議紀錄標示「未定」，需依時程決定：

| 未定項目 | 建議決策時程 | 負責人 | 詳見補充文件 |
|----------|-------------|--------|-------------|
| 麥克風硬體方案 | **3/12 前** | 鄔 | 第 1 節 |
| 手勢對應行為 | **3/16 前** | 楊/鄔 | 第 3 節 |
| 尋物簡化程度 | **3/16 前** | 全員 | 第 4 節 |
| AI 大腦最終深度 | **維持開放** | Architect | 第 5 節 |
| 展示場地規格 | **3/30 前** | 全員 | 第 6 節 |

**詳細選項分析**請見：[會議紀錄補充文件](./meeting_notes_supplement.md)

---

## 9. 風險與降級策略

### 9.1 Top 5 風險與對策

| 風險 | 影響 | 對策 | 負責人 | 期限 |
|------|------|------|--------|------|
| 網路不穩導致 ASR/LLM 失效 | Demo 中斷 | Mode 2 本地降級 + 一鍵 Demo 按鈕 | Architect + 鄔 | 3/15 |
| Face track_id 不穩 | 互動混亂 | Brain 短期黏著策略 + 置信度門檻 | 楊 + Architect | 3/12 |
| 中文語音現場誤識別 | 錯誤回應 | 小詞表 + 關鍵字規則 + 文字輸入替代 | 鄔 | 3/14 |
| Go2 技能執行不穩 | 動作失敗 | Safety guard (速度上限、超時 stop) | Architect | 3/12 |
| Website 與 ROS 串接受限 | 無法展示 | web-bridge proxy 備案 + 同網段筆電 | 鄔 + Architect | 3/13 |

**導航避障風險說明**：
會議紀錄指出「導航避障風險高」。具體技術瓶頸：Go2 LiDAR 感測頻率過低（<2Hz，需 ≥10Hz），資料間隙可達 1.85 秒，無法支援安全連續避障。詳見[會議紀錄補充文件](./meeting_notes_supplement.md)第 2 節。

### 9.2 網路降級策略 (正式驗收項)

**連線模式分級**：

| 模式 | 名稱 | 說明 |
|:----:|------|------|
| Mode 0 | Cloud Full | 預設，ASR/LLM/TTS 走遠端 GPU |
| Mode 1 | Cloud Limited | 網路抖動，部分回本地規則 |
| Mode 2 | Local Demo | 無雲端，按鈕 intent + 預錄 TTS |
| Mode 3 | Playback | 保底，rosbag 回放 |

**P0 必備備援**：
- Website 一鍵 Demo A/B/C
- 一鍵技能 (stand/sit/lie/wave/spin/stop)
- 一鍵切換「Cloud On/Off」
- Brain 超時保護 (雲端請求超時自動降級)
- `stop` 最高優先級打斷

### 9.3 介面契約凍結規則

**3/9 凍結內容 (外部契約，不可變更)**：
- Topic 名稱
- Message schema
- Action 名稱
- Intent enum / Skill enum / State enum
- 驗收格式

**3/9 後仍可調整 (內部實作)**：
- 模型種類與權重
- 閾值與前處理策略
- 內部 pipeline 實作

---

## 10. 文件導航與延伸閱讀

### 10.1 核心文件地圖

```
docs/
├── mission/
│   ├── README.md          # ← 你正在這裡 (入口頁)
│   ├── meeting_notes_supplement.md  # 會議紀錄補充（未定事項細節）
│   ├── vision.md          # 專案願景 (待撰寫)
│   └── roadmap.md         # 開發路線圖 (待撰寫)
│
├── architecture/
│   ├── interaction_v1_contract.md  # 介面契約 v1 (凍結)
│   └── brain_v1.md                 # 大腦架構設計
│
├── 人臉辨識/
│   └── README.md          # 人臉模組詳細設計
│
├── 語音功能/
│   └── README.md          # 語音模組詳細設計
│
├── 手勢辨識/
│   └── README.md          # 手勢/姿勢模組設計
│
├── setup/
│   ├── README.md          # 環境建置總覽
│   ├── hardware/          # 硬體設置指南
│   ├── software/          # 軟體安裝指南
│   └── network/           # 網路配置指南
│
└── logs/                  # 開發日誌 (依日期)
```

### 10.2 快速連結

| 目的 | 連結 |
|------|------|
| **會議紀錄補充** | [meeting_notes_supplement.md](./meeting_notes_supplement.md) |
| **人臉模組設計** | [人臉辨識/README.md](../人臉辨識/README.md) |
| **語音模組設計** | [語音功能/README.md](../語音功能/README.md) |
| **介面契約規格** | [interaction_v1_contract.md](../architecture/interaction_v1_contract.md) |
| **環境建置指南** | [setup/README.md](../setup/README.md) |
| **前端展示程式** | [face_dashboard_nextjs/README.md](../../face_dashboard_nextjs/README.md) |
| **後端 API 程式** | [face_dashboard_fastapi/README.md](../../face_dashboard_fastapi/README.md) |
| **開發日誌** | [logs/README.md](../logs/README.md) |

### 10.3 專案根目錄關鍵路徑

| 路徑 | 內容 |
|------|------|
| `go2_robot_sdk/` | Go2 driver + launch + config |
| `go2_interfaces/` | ROS2 msg/srv/action 定義 |
| `ros-mcp-server/` | MCP server 實作 |
| `face_dashboard_fastapi/` | 展示網站後端 |
| `face_dashboard_nextjs/` | 展示網站前端 |
| `scripts/` | 測試與開發腳本 |

---

## 附錄：關鍵決策摘要

| 決策項目 | 選定方案 | 決策理由 |
|----------|----------|----------|
| 主線方向 | 多模態人機互動 | 與專案「以跟人的互動為主」一致 |
| 大腦架構 | Interaction Executive v1 | 先做穩定決策，P1 再追高智商 |
| 人臉方案 | YuNet + SFace | 輕量、Jetson 可跑、OpenCV 原生支援 |
| 語音方案 | 雲端優先 + 離線備援 | Qwen ASR/TTS 中文效果最佳 |
| LLM 路線 | Qwen3.5 放 P1 | 它是雲端腦候選，ASR/TTS 獨立評估 |
| 喚醒詞 | P0 不做 | Push-to-talk 更穩定，喚醒詞列 P1 |
| 人臉註冊 | Session 追蹤 | 更快交付，demo 夠用 |
| 動作範圍 | P0-safe 優先 | 以「穩」為準，不是「酷」 |
| 網站架構 | 一站雙區 | Showcase + Docs shell |
| 降級策略 | 正式驗收項 | Cloud On/Off + 本地替代流程 |

---

**這是 4/13 前的 P0/P1 執行架構，不再討論大方向，只討論接口與交付。**

---

*最後更新：2026-03-08*  
*維護者：System Architect*  
*狀態：v1.1（修正麥克風資訊、補充會議未定事項）*
