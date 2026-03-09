# PawAI Studio 計畫書 v1.1

## 一句話定位

**PawAI Studio 是 PawAI Go2 的統一交互中樞。**  
它以對話為主入口，以事件流為系統骨架，以可視化面板為展示方式，把機器人感知、交互決策、技能執行與演示觀測整合到同一個界面中。

---

## PawAI Studio 包含四個核心部分

1. **Studio Frontend**（展示層）  
   對話介面、狀態卡片、時間線、技能控制按鈕

2. **Studio Gateway**（閘道層）  
   FastAPI REST API + WebSocket、Redis Event Bus、ROS2 橋接

3. **Interaction Executive**（決策層）  
   RuleBrain、狀態機、技能分發器、安全仲裁

4. **Perception & Robot Layers**（感知與執行層）  
   語音、人臉、手勢感知，Go2 機器人執行層

---

## 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│  Studio Frontend（展示層）                                   │
│  ├── ChatPanel（對話輸入：文字/語音）                       │
│  ├── BrainStateCard（決策狀態顯示）                         │
│  ├── Timeline（事件時間線）                                 │
│  └── SkillButtons（技能控制）                               │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS / WebSocket
┌────────────────────────┴────────────────────────────────────┐
│  Studio Gateway（閘道層）                                    │
│  ├── FastAPI（REST API：/brain-state, /timeline）          │
│  ├── WebSocketManager（實時狀態推送）                       │
│  └── Redis Event Bus（事件總線）                            │
│      ├── Pub/Sub（實時通知）                                │
│      ├── KV（最新狀態）                                     │
│      └── Streams（時間線，最近1000條）                      │
└────────────────────────┬────────────────────────────────────┘
                         │ Redis Protocol
┌────────────────────────┴────────────────────────────────────┐
│  ROS2 Bridge（橋接層，可選獨立部署）                         │
│  └── 訂閱 ROS2 Topics，寫入 Redis Event Bus                 │
└────────────────────────┬────────────────────────────────────┘
                         │ ROS2 Topics
┌────────────────────────┴────────────────────────────────────┐
│  Interaction Executive（決策層，Jetson）                     │
│  ├── RuleBrain：Intent → Task → Skill 映射                 │
│  ├── State Machine：idle/listening/responding/executing    │
│  └── Skill Dispatcher：技能分發 + 安全仲裁                 │
└────────────────────────┬────────────────────────────────────┘
                         │ ROS2 Topics
┌────────────────────────┴────────────────────────────────────┐
│  Perception Layer（感知層，Jetson）                          │
│  ├── speech_processor：VAD + ASR + Intent                  │
│  │   └── /event/interaction_intent {source: "speech"}      │
│  ├── face_perception：人臉檢測 + 追蹤 + 深度               │
│  │   └── /event/face_detected                              │
│  └── gesture_perception：手勢識別（Wave/Stop）              │
│      └── /event/gesture_detected                           │
└────────────────────────┬────────────────────────────────────┘
                         │ ROS2 Topics / Services
┌────────────────────────┴────────────────────────────────────┐
│  Robot Layer（執行層，Go2）                                  │
│  └── go2_robot_sdk：運動控制 + 傳感器                      │
│      └── /webrtc_req（技能執行）                            │
└─────────────────────────────────────────────────────────────┘
```

---

## MVP 最小閉環

```
使用者操作（網頁文字或語音）
    ↓
統一轉換為 interaction_intent 事件
    ↓
Interaction Executive（RuleBrain）
    ├── 檢查當前狀態（State Gate）
    ├── 選擇安全技能（Skill Selection）
    └── 決定回應策略（Response Planning）
    ↓
機器人執行動作
    ↓
狀態回傳 Redis Event Bus
    ↓
Studio 同步顯示：狀態、決策摘要、事件時間線
```

---

## UI 設計概念：ChatGPT × Foxglove 混合風格

### 設計原則

> **預設像 ChatGPT，一個乾淨的對話入口；需要觀測與控制時，再像 Foxglove 一樣展開即時面板與事件流。**

### 主介面概念圖

```
┌──────────────────────────────────────────────────────────────┐
│                        PawAI Studio                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌───────────────────┐   ┌──────────────────────────────┐   │
│   │ Chat / Voice      │   │ Live Robot View             │   │
│   │-------------------│   │------------------------------│   │
│   │ User: 你現在看到誰│   │ [Camera Feed]                │   │
│   │                   │   │ Roy / 0.91 / 1.4m            │   │
│   │ PawAI: 偵測到 Roy │   │ [Detection Overlay]          │   │
│   │ 距離 1.4m         │   │                              │   │
│   │                   │   │                              │   │
│   │ [input.......] 🎤 │   │                              │   │
│   │                   │   │                              │   │
│   │ Quick Actions:    │   │                              │   │
│   │ [招呼][停止][拍照]│   │                              │   │
│   └───────────────────┘   └──────────────────────────────┘   │
│                                                              │
│   ┌───────────────────┐   ┌──────────────────────────────┐   │
│   │ Brain State       │   │ Robot Status / Skills        │   │
│   │-------------------│   │------------------------------│   │
│   │ State: observing  │   │ Mode: interaction            │   │
│   │ Intent: ask_id    │   │ Skill: idle                  │   │
│   │ Safety: clear     │   │ Battery: 85%                 │   │
│   │ Layout: chat_c... │   │ [wave] [stop] [photo]        │   │
│   └───────────────────┘   └──────────────────────────────┘   │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │ Event Timeline / Trace                              │   │
│   │------------------------------------------------------│   │
│   │ 18:22:01 face_detected → Roy                         │   │
│   │ 18:22:02 executive → observing                       │   │
│   │ 18:22:03 intent → ask_identity                       │   │
│   │ 18:22:03 layout → chat_camera_face                   │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 頁面類型

| 頁面 | 用途 | 主要內容 |
|------|------|----------|
| **Studio Home** | 主操作頁 | Chat + Live View + Brain State + Timeline |
| **Debug Console** | 開發測試 | Topics Inspector + State Monitor + Manual Trigger |
| **Demo Showcase** | 評審展示 | 簡化版，強調故事線與互動流程 |

### 動態面板策略

- **預設**: 乾淨對話介面（像 ChatGPT）
- **觸發條件**: 
  - 使用者輸入特定 intent → 展開相關面板
  - 系統進入特定 state → 自動切換 layout
- **面板類型**: chat_only, chat_camera, chat_speech, chat_status, chat_full

---

## 關鍵缺口

| 模組 | 狀態 | 說明 |
|------|------|------|
| go2_robot_sdk | ✅ 已存在 | Clean Architecture 完整，可直接使用 |
| speech_processor | 🔄 部分 | TTS + VAD 完成，**STT/Intent 缺失** |
| face_perception | ❌ 不存在 | **需從零建立** |
| gesture_perception | ❌ 不存在 | **需從零建立（Wave/Stop 二選一）** |
| interaction_executive | ❌ 空骨架 | **需從零建立** |
| Studio Gateway | 🔄 設計中 | FastAPI + Redis，W1 完成 |
| Studio Frontend | ❌ 不存在 | **需從零建立** |

---

## 統一事件格式

所有使用者輸入（無論語音、文字、手勢）統一發布為：

```python
# Topic: /event/interaction_intent
{
    "intent": "greet",           # 統一意圖標籤
    "source": "web_text",        # 來源：web_text | speech | gesture
    "confidence": 1.0,           # 置信度（語音/手勢可能 < 1.0）
    "raw_input": "你好",         # 原始輸入
    "timestamp": "2026-03-09T10:00:00+08:00",
    "session_id": "uuid"
}
```

---

## 三層映射表

### Intent（使用者意圖）

```python
INTENTS = [
    "greet",        # 打招呼
    "stop",         # 停止
    "take_photo",   # 拍照
    "show_status",  # 顯示狀態
    "wave_back",    # 揮手回應（取代 come_here，更安全）
]
```

### Task（系統任務）

```python
TASKS = {
    "greet": "perform_greeting",      # 執行打招呼流程
    "stop": "halt_robot",             # 停止機器人
    "take_photo": "capture_photo",    # 拍照
    "show_status": "report_status",   # 報告狀態
    "wave_back": "perform_wave",      # 揮手回應
}
```

### Skill（機器人技能）

```python
SKILLS = {
    "perform_greeting": ["wave", "tts_speak"],  # wave + 語音問候
    "halt_robot": ["stop"],                      # 緊急停止
    "capture_photo": ["photo"],                  # 拍照
    "report_status": ["tts_speak"],              # 語音報告（純回應）
    "perform_wave": ["wave"],                    # 揮手動作
}
```

**說明**：
- Intent → Task：一對一映射（使用者想做什麼）
- Task → Skills：一對多（完成任務需要哪些技能組合）
- Skills：實際執行的機器人動作

---

## Demo 定義

### Demo A：語音/文字閉環

**場景**：使用者通過文字或語音與機器狗對話

**流程**：
```
使用者說「你好」
    ↓
stt_intent_node 識別為 intent="greet"
    ↓
RuleBrain 映射為 Task="perform_greeting"
    ↓
選擇 Skills=["wave", "tts_speak"]
    ↓
機器狗揮手 + 說「哈囉，你好」
    ↓
Studio 顯示完整事件時間線
```

**成功標準**：成功率 ≥ 90%

### Demo B：視覺閉環（手勢）

**場景**：使用者對機器狗做手勢

**流程**：
```
使用者舉手掌（Stop 手勢）
    ↓
gesture_perception 識別為 intent="stop"
    ↓
RuleBrain 映射為 Task="halt_robot"
    ↓
執行 Skills=["stop"]
    ↓
機器狗停止動作
    ↓
Studio 顯示手勢觸發事件
```

**成功標準**：成功率 ≥ 70%

**說明**：  
- 只保留手勢路徑（Wave + Stop）
- 人臉檢測 → 自動 wave 移到 Demo A 強化版，不算 Demo B 主體
- 完全不做人臉觸發的獨立 Demo B

### Demo C：Studio 同步展示

**場景**：網站實時同步顯示機器人狀態

**顯示內容**：
- 當前 Brain State（idle/listening/responding/executing）
- 最近事件時間線（face/speech/gesture/skill）
- 技能控制按鈕（可手動觸發）
- 對話歷史

**成功標準**：網站狀態延遲 < 300ms，成功率 ≥ 90%

---

## 5 週執行計畫

### Phase 0: 本週（W1）
**目標**：凍結契約 + 建立 Mock

**交付物**：
- [ ] 契約文檔 v1（本文件）
- [ ] Mock backbone：可重播 Demo A/B/C 事件序列
- [ ] stt_intent_node：支持 5 個固定 intent
- [ ] FastAPI Gateway + Redis：基礎 API + WebSocket

**負責人**：
- Architect: 契約 + Mock
- 鄔: STT + Gateway

### Phase 1: W2
**目標**：語音主線閉環

**交付物**：
- [ ] RuleBrain v1：Intent → Task → Skill 三層映射
- [ ] Skill Dispatcher：5 個安全技能
- [ ] Studio Frontend Shell：Chat + Brain State + Timeline
- [ ] Demo A 完整鏈路

**負責人**：
- Architect: RuleBrain + Dispatcher
- 鄔: 前端 + 語音整合

### Phase 2: W3
**目標**：多模態整合

**交付物**：
- [ ] face_perception：人臉檢測 + 追蹤 + 深度
- [ ] gesture_perception：手勢識別（Wave/Stop）
- [ ] Demo A 強化版：人臉檢測 → 自動 wave
- [ ] Demo B 雛形：手勢觸發技能

**負責人**：
- 楊: Face + Gesture
- 鄔: Timeline + 前端整合

### Phase 3: W4
**目標**：技能與安全 + LLM 接入（可選）

**交付物**：
- [ ] Safety Guard：Stop 打斷、超時保護、技能互斥
- [ ] Demo B 完整：手勢成功率 ≥ 70%
- [ ] **可選**：接入 Qwen2.5-72B 驗證結構化輸出

**負責人**：
- Architect: Safety + 整合
- 楊: 視覺優化

### Phase 4: W5
**目標**：整合與彩排

**交付物**：
- [ ] 每日 3 次完整 Demo 測試
- [ ] Fallback 演練
- [ ] Demo Script 操作手冊
- [ ] 最終彩排：Demo A/C ≥ 90%，Demo B ≥ 70%

**負責人**：全員

---

## 技術決策

### 1. Rule-based Brain（MVP 階段）

**理由**：
- 5 週內 LLM 風險過高
- Rule-based 更可控、可預測、可解釋
- 後續可無縫替換為 LLM（Brain Adapter 設計）

**範圍**：
- Intent → Task → Skill 三層映射
- State Gate（狀態檢查）
- Response Template（固定回應模板）

**不做**：自由對話、記憶、複雜規劃

### 2. 手勢而非姿勢

**理由**：
- MediaPipe Hands 更簡單、延遲更低
- Wave + Stop 兩個手勢足夠 Demo B
- Pointing/Come_here 風險高，4 天內難以穩定

### 3. Redis Event Bus（簡化版）

**只用 3 個功能**：
- Pub/Sub：實時事件通知
- KV：最新狀態儲存
- Streams：時間線（最近 1000 條）

**不做**：Consumer Groups、複雜流處理、分散式事務

### 4. 固定 Layout（5 種）

- `chat_only`: 純對話
- `chat_camera`: 對話 + 相機
- `chat_speech`: 對話 + 語音狀態
- `chat_status`: 對話 + 機器人狀態
- `chat_full`: 完整監控

**不做**：動態 UI generation

### 5. LLM Brain 策略（非 MVP 阻塞項）

**重要**：LLM Brain Adapter 為擴充路線，**不列入 W1-W3 阻塞條件**

| 角色 | 模型 | 用途 | 接入時機 |
|------|------|------|----------|
| **MVP 主腦** | Rule-based Brain | Intent → Task → Skill | W1-W3（必做）|
| **W4 可選** | Qwen2.5-72B | 結構化輸出驗證 | W4（如時間允許）|
| **W4+ 可選** | Qwen3-235B-A22B | Task planning, panel selection | W4（核心閉環穩定後）|
| **W5 後實驗** | MiniMax-M2.5 | Agentic 能力測試 | 非 MVP |

**MVP 策略**：
- W1-W3：純 RuleBrain，完全不依賴 LLM
- W4：若核心閉環穩定，才接入一個 LLM 作為 enhancement
- W5：凍結模型，不做切換

---

## 凍結接口 v1.0

### State Topics（10 Hz）

```
/state/perception/face          # 人臉狀態
/state/interaction/speech       # 語音狀態
/state/executive/brain          # 大腦決策狀態
```

### Event Topics（觸發式）

```
/event/interaction_intent       # 統一意圖事件（語音/文字/手勢）
/event/face_detected            # 人臉檢測事件
/event/gesture_detected         # 手勢檢測事件
```

### Control Topics

```
/webrtc_req                     # 技能執行（沿用現有）
```

### Brain State

```python
BRAIN_STATES = ["idle", "listening", "responding", "executing"]
```

---

## 風險與對策

| 風險 | 對策 |
|------|------|
| W1 過載 | 只保留 4 個核心任務，其他後移 |
| Face 不穩定 | 降只做 detection + track，不做 identity |
| 手勢不穩定 | 只做 Wave + Stop，Pointing 放棄 |
| come_here 風險 | MVP 改用 wave_back，come_here 移到 P1 |
| LLM 不穩定 | MVP 純 Rule-based，LLM 作為可選 enhancement |
| 整合太晚 | W1 建立 Mock，全程並行開發 |

---

## 立即行動

### 今天（T+0）

1. **Architect**: 發出契約凍結 v1 文件，召集全員 review
2. **鄔**: 確認 stt_intent_node 技術方案
3. **楊**: 確認 face_perception 技術方案
4. **全員**: 確認 Wave 1 範圍，同意「只做 4 件事」

### 本週結束（T+7）

- ✅ 契約文檔 v1 凍結，全員簽署
- ✅ Mock backbone 可運行 Demo A 事件序列
- ✅ stt_intent_node 可發布 5 個固定 intent
- ✅ FastAPI Gateway 基礎 API 可用

---

**狀態**: 計畫凍結 v1.1  
**最後更新**: 2026-03-09  
**下次更新**: W1 結束時（僅修 bug，不改範圍）
