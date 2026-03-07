# PawAI 4/13 P0 執行定案稿

**版本**：v1.0  
**定案日期**：2026-03-07  
**執行期間**：2026-03-07 ~ 2026-04-13  
**關鍵里程碑**：3/16 攻守交換、4/13 完成 80% 並可展示

---

## 專案定位（一句話）

> 以 Unitree Go2 Pro 為載體，建立一套「以人機互動為主、導航避障為輔」的 embodied AI 機器狗系統。  
> 核心不是把每個功能都做到最強，而是做出一個 **可模組化擴充、可多人分工、可實際展示的互動式系統平台**。

---

## 主線與副線（已定案）

| 類型 | 內容 | 說明 |
|------|------|------|
| **主線** | 多模態人機互動 | 人臉辨識 + 中文語音 + 視覺互動 + 回應 |
| **副線** | 基礎移動 / 導航避障輔助 | P2 加分項，不列為 4/13 必交主線 |
| **核心價值** | 模組化 embodied AI 平台 | 介面契約清楚、可替換、可降級 |

---

## 三層架構（執行版）

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Interaction Executive v1（中控層）                  │
│  - 事件聚合、狀態機、技能分派、安全仲裁                       │
│  - 所有動作唯一出口，避免多模組搶控制                        │
└─────────────────────────────────────────────────────────────┘
                              ↑↓ ROS2 Topics/Actions
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Perception / Interaction Module Layer              │
│  - 人臉模組（Face Owner）                                    │
│  - 語音模組（Speech Owner）                                  │
│  - 手勢/姿勢模組（P1，Visual Owner）                         │
│  - 統一輸出：事件（event）+ 狀態（state）                    │
└─────────────────────────────────────────────────────────────┘
                              ↑↓ ROS2 Topics
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Device / Runtime Layer（Architect）                │
│  - Go2 driver、D435、音訊裝置                                 │
│  - ROS2 / SDK / topic / node                                 │
│  - 邊緣端部署與模型執行入口                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 技術選型定案

### AI 大腦：Interaction Executive v1

- **定位**：Rule-based state machine + skill dispatcher
- **目的**：先做「穩定決策」，不是「高智商」
- **部署**：Jetson Orin Nano 8GB
- **更名原因**：避免「rule-based」被誤解為陽春/臨時，強調它是正式的 P0 控制核心

### LLM 選型

| 位置 | 模型 | 說明 |
|------|------|------|
| **雲端腦候選** | Qwen3.5（9B+） | P1 升級路徑，非 P0 核心依賴 |
| **P0 備援** | Qwen2.5-1.5B（INT4） | Jetson 本地可跑，網路差時降級 |

> **關鍵認知**：Qwen3.5 是大型 LLM 主腦路線；ASR/TTS 是獨立系列（Qwen3-ASR/TTS），不應被 LLM 型號綁架。

### ASR/TTS 選型

| 功能 | 雲端（RTX 8000） | 邊緣（Jetson）降級 |
|------|------------------|-------------------|
| **ASR** | Qwen3-ASR-1.7B | Qwen3-ASR-0.6B / Whisper tiny |
| **TTS** | Qwen3-TTS-1.7B | Qwen3-TTS-0.6B / MeloTTS |

### 喚醒詞策略

- **P0**：不做喚醒詞
- **替代方案**：Push-to-talk（網站按鈕）+ 一鍵 Demo 觸發
- **P1**：可評估喚醒詞（獨立成 wakeword node）

---

## 功能優先序（已定案）

### P0（4/13 必交）

| 模組 | 內容 | 負責人 |
|------|------|--------|
| 人臉辨識 | Detection + track_id（session 追蹤，不做持久註冊） | A |
| 語音功能 | 中文 ASR + intent 映射 + TTS 串接 | B |
| AI 大腦 | Interaction Executive v1（state machine + skill dispatcher） | Architect |
| 展示網站 | 一站雙區（Showcase + Docs shell） | C |
| 安全動作 | P0-safe：stand, sit, lie, stop, look_left, look_right | Architect |

### P0-demo-only（4/13 展示用，風險較高）

| 動作 | 說明 |
|------|------|
| wave | 招手 |
| spin_left / spin_right | 旋轉 |

> 這些動作較容易暴露整合問題，若時間不夠可優先確保 P0-safe。

### P1（第二波，3/16 後接）

| 模組 | 內容 |
|------|------|
| 手勢辨識 | 視覺互動分支（若手勢不穩可改姿勢或簡化指向） |
| 姿勢辨識 | 備選方案 |
| 模組事件統合 | 完善多模態互動 |

### P2（加分/研究項）

| 項目 | 說明 |
|------|------|
| 導航避障 | 基礎移動、簡單避障、站點間移動（不做完整自主導航） |
| 喚醒詞 | 評估後實作 |
| 雲端 LLM 升級 | Qwen3.5 整合 |

---

## 介面契約凍結規則（3/9 凍結）

### 3/9 凍結內容（外部契約，不可變更）

- Topic 名稱
- Message schema
- Action 名稱
- Intent enum
- Skill enum
- State enum
- 驗收格式

### 3/9 後仍可調整（內部實作）

- 模型種類
- 模型權重
- 閾值
- 前處理策略
- 內部 pipeline 實作

---

## 最小介面契約（v1）

### Event Topics（發生了什麼）

| Topic | 說明 |
|-------|------|
| `/event/face/detected` | 人臉偵測事件 |
| `/event/speech/intent_recognized` | 語音意圖識別事件 |
| `/event/brain/state_changed` | 大腦狀態變更事件 |
| `/event/action/executed` | 動作執行事件 |
| `/event/tts/started` | TTS 開始事件 |
| `/event/tts/finished` | TTS 結束事件 |

### State Topics（現在狀態）

| Topic | 說明 |
|-------|------|
| `/state/perception/face` | 人臉感知狀態 |
| `/state/interaction/speech` | 語音互動狀態 |
| `/state/brain` | 大腦狀態 |
| `/state/robot/posture` | 機器人姿態 |
| `/state/system/network` | 系統網路狀態 |

### Action

**`ExecuteSkill.action`**

```
# Request
string skill           # stand, sit, lie, wave, look_left, look_right, spin_left, spin_right, stop
go2_interfaces/KeyValue[] params
uint8 priority
float32 timeout_sec

---
# Result
bool success
string message

---
# Feedback
string phase
float32 progress
```

### 原則

- **人臉**：session tracking，不做持久註冊（person_id 可為空或 "unknown"）
- **語音**：中文 + 固定 intent 集，不先追 full agent
- **控制權**：所有動作只透過 brain 發出，避免多模組搶控制

---

## 分工矩陣（定案版）

### System Architect / Integration Owner（你）

**負責（R/A）：**
- 介面契約 v1 凍結與變更流程
- Interaction Executive v1（state machine + skill dispatcher）
- Safety guard 與 command router
- 系統 bring-up（單一 launch/啟動流程）+ 故障排查手冊
- 網路降級策略（Cloud On/Off + 本地替代流程）
- 最終整合與 demo pipeline

**協作（C）：**
- 與 A 協調 face event 欄位
- 與 B 協調 intent label/slots
- 與 C 協調 website 顯示所需的 brain state/事件流

### A（Face Owner）

**負責（R）：**
- Face module（RGB frame → FaceDetections）
- track_id 穩定策略（session 內穩定）
- confidence/bbox 輸出

**交付：**
- `DELIVERABLE.md`（啟動指令、輸入輸出、需求、限制、驗證方式）
- demo 距離/光線下可用（成功率/延遲達標）

### B（Speech Owner）

**負責（R）：**
- 中文 ASR → intent（固定 intent 集）
- Push-to-talk 流程設計
- 與 TTS node 串接

**P0 Intents（建議 12 個）：**
- `greet`, `who_am_i`, `repeat`, `stop`
- `start_demo_a`, `start_demo_b`, `start_demo_c`
- `skill_stand`, `skill_sit`, `skill_lie`, `skill_wave`, `skill_spin`

**交付：**
- `DELIVERABLE.md`
- 延遲量測方式

### C（Frontend / Showcase Owner）

**負責（R）：**
- 一站雙區網站（基於 `face_dashboard_nextjs/`）
- Showcase：事件時間線、brain state、技能按鈕、demo 一鍵彩排
- Docs shell：介面規格、部署手冊

**明確限縮：**
- **不負責填滿所有 docs 內容**（內容由 Architect 與各 Owner 提供）
- 只負責 docs 的結構與呈現

**P1：**
- 接手勢或姿勢其一（與 Architect 協調）

---

## 3/16 前必交（攻守交換）

| 交付物 | 負責人 | 說明 |
|--------|--------|------|
| 介面契約 v1 | Architect | topic/msg/action/intents/skills/QoS |
| Demo A/B/C 腳本 | Architect | 每條 demo 的事件流與降級路徑 |
| Face module `DELIVERABLE.md` | A | 套用標準模板 |
| Speech module `DELIVERABLE.md` | B | 套用標準模板 |
| Website `DELIVERABLE.md` | C | 套用標準模板 |
| Brain `DELIVERABLE.md` | Architect | 狀態機規則表 |
| Bring-up 手冊 | Architect | 新成員 10 分鐘內能跑起 demo |
| 降級方案 | Architect | Cloud On/Off + 本地替代流程 |

---

## 4/13 三條 Demo 驗收線（量化）

### Demo A：辨識 + 語音 + 回應（P0 主線）

**流程：**
1. Face module 發布 `FaceDetections`
2. 使用者 Push-to-talk 說中文指令
3. Speech module 發布 `SpeechIntent`
4. Brain 更新 `/state/brain`
5. Brain 發布 `/tts`（中文回應）

**驗收：**
- 成功率：10 次中 ≥ 9 次成功（≥ 90%）
- 語音延遲：Push-to-talk 放開到 `/tts` 發布 ≤ 2.0 秒
- 視覺更新：FaceDetections ≥ 10 Hz
- 可觀測性：Website 事件流看到 SpeechIntent → BrainState → TTS

### Demo B：視覺互動分支（P1 展示亮點）

**流程：**
1. FaceDetections 有 focused_track_id
2. 視覺互動事件（手勢/姿勢/指向）
3. Brain 觸發 `ExecuteSkill.action`
4. 回覆 `/tts` + `/state/brain` 更新

**驗收：**
- 成功率：10 次中 ≥ 7 次成功（≥ 70%）
- 延遲：視覺事件到 Skill 開始 ≤ 1.0 秒；到 TTS ≤ 2.0 秒
- 安全：`stop` 必須可打斷其他 skill（最高優先級）
- **彈性**：若手勢不穩，可改姿勢或簡化指向

### Demo C：語音 + 網站同步（產品感）

**流程：**
1. 使用者 Push-to-talk 或按網站「Demo C」
2. Brain 進入 `mode=demo`，逐步更新 `/state/brain`
3. Website 顯示進度條/狀態轉移/最後輸出

**驗收：**
- 成功率：10 次中 ≥ 9 次成功（≥ 90%）
- 同步延遲：BrainState 更新到 Website 畫面 ≤ 300 ms
- 降級保證：拔掉雲端仍可用按鈕完整跑完 Demo C

---

## 網路降級策略（正式驗收項）

### 連線模式分級

| 模式 | 名稱 | 說明 |
|------|------|------|
| **Mode 0** | Cloud Full | 預設，ASR/LLM 走遠端 GPU |
| **Mode 1** | Cloud Limited | 網路抖動，部分回本地規則 |
| **Mode 2** | Local Demo | 無雲端，按鈕 intent + 預錄 TTS |
| **Mode 3** | Playback | 保底，rosbag 回放 |

### P0 必備備援

- Website 一鍵 Demo A/B/C
- 一鍵技能（stand/sit/lie/wave/spin/stop）
- 一鍵切換「Cloud On/Off」
- Brain 超時保護（雲端請求超時自動降級）
- `stop` 最高優先級打斷

---

## 里程碑時間軸

### Phase 1: 3/7 ~ 3/16（介面凍結與基礎建設）

| 日期 | 里程碑 | 關鍵交付 |
|------|--------|----------|
| 3/7 | 定案日 | 本文件 v1.0 發布 |
| 3/9 | 介面凍結 | 介面契約 v1、Demo 腳本草案 |
| 3/12 | Brain v1 | Interaction Executive 可運作 |
| 3/14 | 第一次彩排 | Demo A/C 可跑通 8/10 次 |
| 3/15 | 降級保證 | 拔網路演練可完成 demo |
| **3/16** | **攻守交換** | **所有模組標準交付完成** |

### Phase 2: 3/17 ~ 4/13（整合與穩定化）

| 週次 | 重點 |
|------|------|
| W1 (3/17-23) | P0 穩定化（去抖、超時、重試、斷線偵測），Demo A/C ≥ 85% |
| W2 (3/24-30) | P1-1：手勢或姿勢上一個，Demo B ≥ 70% |
| W3 (3/31-4/6) | P1-2：補齊另一個，Website 完成度達標 |
| W4 (4/7-13) | 總彩排，只修穩定度，凍結功能 |
| **4/13** | **最終展示** |

---

## 風險與對策（Top 5）

| 風險 | 對策 | 負責人 | 期限 |
|------|------|--------|------|
| 網路不穩導致 ASR/LLM 失效 | Mode 2 本地降級 + 一鍵 Demo 按鈕 | Architect + B + C | 3/15 |
| Face track_id 不穩 | Brain 短期黏著策略 + 最小 bbox/置信度門檻 | A + Architect | 3/12 |
| 中文語音現場誤識別 | 小詞表 + 關鍵字規則 + 文字輸入替代 | B + C | 3/14 |
| Go2 技能執行不穩 | Safety guard（速度上限、超時 stop、stop 優先級） | Architect | 3/12 |
| Website 與 ROS 串接受限 | web-bridge proxy 備案 + 同網段筆電展示 | C + Architect | 3/13 |

---

## 立即行動清單（今天）

1. **Architect**：宣布「介面契約 v1 於 3/9 凍結，3/16 只收標準交付格式」
2. **全員**：收到 `DELIVERABLE.md` 模板後，各自填寫骨架
3. **C**：先把 Website 做出「一鍵 Demo + brain state 監控」
4. **Architect**：準備 Bring-up 手冊與故障排查第一版

---

## 附錄：關鍵決策摘要

| 決策 | 選項 | 理由 |
|------|------|------|
| 主線 | 多模態人機互動 | 與專案總覽「以跟人的互動為主」一致 |
| 大腦 | Interaction Executive v1 | 先做穩定決策，P1 再追高智商 |
| LLM | Qwen3.5 放 P1 | 它是雲端腦候選，ASR/TTS 獨立評估 |
| 喚醒詞 | P0 不做 | Push-to-talk 更穩定，喚醒詞列 P1 |
| 人臉註冊 | Session 追蹤 | 更快交付，demo 夠用 |
| 動作範圍 | P0-safe 優先 | 以「穩」為準，不是「酷」 |
| 網站 | 一站雙區 | Showcase + Docs shell |
| 降級 | 正式驗收項 | Cloud On/Off + 本地替代流程 |

---

**這是 4/13 前的 P0/P1 執行架構，不再討論大方向，只討論接口與交付。**
