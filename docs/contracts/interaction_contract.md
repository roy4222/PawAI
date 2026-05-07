# ROS2 介面契約 v2.5

**文件定位**：PawAI 系統 ROS2 Topic/Action/Service 介面規格
**適用範圍**：Layer 1-3 所有模組
**版本**：v2.5
**凍結日期**：2026-04-28
**對齊來源**：[mission/README.md](../../mission/README.md) v2.0、[event-schema.md](../../pawai-brain/studio/specs/event-schema.md) v1.0

> **v2.5 變更摘要**：
> - 新增 PawAI Brain MVS topics：`/brain/text_input`、`/brain/skill_request`、`/brain/proposal`、`/brain/skill_result`
> - 新增 `/state/pawai_brain`，作為 Brain Skill Console 的狀態觀測來源
> - Phase A runtime：`brain_node` 負責規則仲裁，`interaction_executive_node` 是 production sport `/webrtc_req` 唯一出口
>
> **v2.2 變更摘要**：
> - 新增 `interaction_executive_node`（取代 `interaction_router` + `event_action_bridge`）
> - 新增 `/executive/status`（v0 implemented，2 Hz state machine 狀態廣播）
> - `/state/executive/brain` 標記為 **planned / not yet implemented**（executive 完整版會統一到此 topic）
> - 新增 `/event/obstacle_detected`（**planned / Day 8**，obstacle_avoidance_node 發布）
> - `interaction_router` → **deprecated**（v0 不再啟動，功能已吸收進 executive）
> - `event_action_bridge` → **deprecated**（v0 不再啟動，功能已吸收進 executive）
> - `/event/interaction/welcome`、`/event/interaction/gesture_command`、`/event/interaction/fall_alert` → **deprecated**（executive 內部處理）
>
> **v2.1 變更摘要**：
> - 新增 interaction_router 三個高層事件 topic：`/event/interaction/welcome`、`/event/interaction/gesture_command`、`/event/interaction/fall_alert`
> - `event_action_bridge` 改訂閱 interaction_router 輸出（不再訂閱 raw gesture/pose events）
> - `event_action_bridge` 新增訂閱 `/state/tts_playing`（TTS guard 邏輯）
> - `/event/gesture_detected` gesture enum 擴充（新增 `thumbs_up`、`thumbs_down`、`victory`、`i_love_you`）
> - 修正 gesture/pose 發布者名稱為 `vision_perception_node`（原誤標為 `gesture_perception_node` / `pose_perception_node`）
> - 修正降級表 LLM 型號為 Qwen2.5-7B-Instruct（Cloud）+ qwen2.5:1.5b（Ollama 本地）
>
> **v2.0 變更摘要**：
> - `/event/face_detected` → `/event/face_identity`（4 種 event_type）
> - `/state/perception/face` 欄位對齊實作（`stable_name` / `sim` / `mode`）
> - 新增 `/state/interaction/speech`、`/state/executive/brain` 完整 schema
> - 新增 P1 topics：`/event/gesture_detected`、`/event/pose_detected`
> - `/event/speech_intent` → `/event/speech_intent_recognized`（對齊現有程式碼）

---

## 1. 介面凍結規則

### 1.1 不可變更項目（v2.0 凍結後）

變更需經 System Architect 核准：

- ✅ Topic 名稱與路徑
- ✅ Message schema（欄位名稱、型別）
- ✅ 常數 enum 值（event_type、Skill ID 等）

### 1.2 可調整項目（內部實作）

- 🔄 演算法實作細節
- 🔄 閾值與參數預設值
- 🔄 內部資料結構
- 🔄 發布頻率（在不影響外部行為前提下）

---

## 2. Topic 總覽

| Topic | 類型 | 頻率 | 說明 | 狀態 |
|-------|------|------|------|:----:|
| `/state/perception/face` | State | 10 Hz | 人臉追蹤狀態 | active |
| `/state/interaction/speech` | State | 5 Hz | 語音管線狀態 | active |
| `/state/executive/brain` | State | 2 Hz | 大腦決策狀態（完整版） | **planned** |
| `/state/pawai_brain` | State | 2 Hz | PawAI Brain MVS 狀態（active plan / safety flags / trace） | **v2.5** active |
| `/executive/status` | State | 2 Hz | Executive v0 state machine 狀態 | **v0 implemented** |
| `/event/face_identity` | Event | 觸發式 | 人臉身份事件 | active |
| `/event/speech_intent_recognized` | Event | 觸發式 | 語音意圖事件 | active |
| `/event/gesture_detected` | Event | 觸發式 | 手勢事件 | active |
| `/event/pose_detected` | Event | 觸發式 | 姿勢事件 | active |
| `/event/object_detected` | Event | 觸���式 | 物體偵測事件（YOLO26n） | active |
| `/event/obstacle_detected` | Event | 觸發式 | 障礙物偵測事件 | **disabled** (Demo 停用，程式碼保留) |
| `/event/interaction/welcome` | Event | 觸發式 | ~~迎賓事件（interaction_router）~~ | **deprecated** |
| `/event/interaction/gesture_command` | Event | 觸發式 | ~~手勢指令事件（interaction_router）~~ | **deprecated** |
| `/event/interaction/fall_alert` | Event | 觸發式 | ~~跌倒警報事件（interaction_router）~~ | **deprecated** |
| `/state/tts_playing` | State | 變更式 | TTS 播放狀態（latched） | active |
| `/state/nav/heartbeat` | State | 1 Hz | nav_capability 平台層心跳 | **v2.3** active |
| `/state/nav/status` | State | 10 Hz | nav 任務狀態 + AMCL covariance JSON | **v2.3** active |
| `/state/nav/safety` | State | 10 Hz | reactive_stop / lidar / driver / amcl health JSON | **v2.3** active |
| `/state/reactive_stop/status` | State | 10 Hz | reactive_stop_node 內部狀態（state_broadcaster 訂閱用） | **v2.3** active |
| `/event/nav/waypoint_reached` | Event | 觸發式 | RunRoute 每個 waypoint 抵達事件 | **v2.3** active |
| `/event/nav/internal/status` | Event | 觸發式 | nav_action_server / route_runner → state_broadcaster 內部 status | **v2.3** active |
| `/state/nav/paused` | State | 變更式 | 全域 pause(latched Bool;route_runner /nav/{pause,resume} 無條件 publish;nav_action_server 訂閱做 cancel + re-send) | **v2.6** active |
| `/capability/nav_ready` | State | 1 Hz | 導航就緒(latched Bool;v0.5 = AMCL freshness + covariance;day 2 升級 lifecycle + costmap healthy) | **v2.6** active |
| `/capability/depth_clear` | State | 5 Hz | D435 ROI 前方無近距離障礙(latched Bool;**fail-closed**:沒 frame / stale > 1s / compute 失敗 → false) | **v2.6** active |
| `/brain/text_input` | Command | 觸發式 | Studio → Brain 文字輸入 | **v2.5** active |
| `/brain/skill_request` | Command | 觸發式 | Studio → Brain skill button request | **v2.5** active |
| `/brain/proposal` | Event | 觸發式 | Brain → Executive SkillPlan proposal | **v2.5** active |
| `/brain/skill_result` | Event | 觸發式 | Executive → Brain/Studio SkillResult lifecycle | **v2.5** active |
| `/brain/conversation_trace` | Event | 觸發式 | Brain → Debug/Studio LLM proposal gate trace（skill_gate stage 完整 enum 見 §`/brain/conversation_trace` 章節，5/8 加 `needs_confirm` / `demo_guide`） | **v2.8** active |
| `/tts` | Command | 觸發式 | TTS 輸入文字 | active |
| `/webrtc_req` | Command | 觸發式 | Go2 WebRTC 命令 | active |

**Actions（v2.3 新增）**：`/nav/goto_relative` / `/nav/goto_named` / `/nav/run_route` / `/log_pose`（型別於 `go2_interfaces/action/`）
**Services（v2.3 新增）**：`/nav/pause` / `/nav/resume` / `/nav/cancel`（`std_srvs/Trigger` 或 `go2_interfaces/srv/Cancel`）
**Locks（v2.3 新增）**：`/lock/emergency` (Bool, twist_mux lock — engaged 後阻擋所有低優先級 cmd_vel)

---

## 3. State Topics

### 3.1 `/state/perception/face`

**說明**：人臉追蹤狀態（持續發布）
**發布者**：`face_identity_node`（現為 `scripts/face_identity_infer_cv.py`）
**發布頻率**：10 Hz
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":      { "type": "float",  "unit": "seconds (Unix timestamp)" },
  "face_count": { "type": "int",    "description": "當前追蹤人數" },
  "tracks": {
    "type": "array",
    "items": {
      "track_id":    { "type": "int",            "description": "Session-level 追蹤 ID" },
      "stable_name": { "type": "string",         "description": "穩定化後的身份名稱（unknown 表示未識別）" },
      "sim":         { "type": "float",          "range": "[0.0, 1.0]", "description": "SFace 相似度分數" },
      "distance_m":  { "type": "float | null",   "unit": "meters", "description": "深度距離，無深度時 null" },
      "bbox":        { "type": "array[4]",       "items": "int", "description": "邊界框 [x1, y1, x2, y2]" },
      "mode":        { "type": "string",         "enum": ["stable", "hold"], "description": "stable=已穩定, hold=尚在判定中" }
    }
  }
}
```

**範例**：
```json
{
  "stamp": 1773561600.789,
  "face_count": 2,
  "tracks": [
    {
      "track_id": 1,
      "stable_name": "Roy",
      "sim": 0.42,
      "distance_m": 1.25,
      "bbox": [100, 150, 200, 280],
      "mode": "stable"
    },
    {
      "track_id": 2,
      "stable_name": "unknown",
      "sim": 0.18,
      "distance_m": 2.1,
      "bbox": [300, 180, 380, 300],
      "mode": "hold"
    }
  ]
}
```

**欄位說明**：
- `stable_name`：經 Hysteresis 穩定化後的名稱（`stable_hits=2`，`sim_threshold_upper=0.40` / `lower=0.22`；5/8 把 upper 從 0.30→0.40 拉高陌生人門檻避免 demo 誤觸）
- `mode`：`stable` 表示已過穩定化閾值；`hold` 表示追蹤中但尚未達穩定條件
- `sim`：SFace cosine similarity 原始分數，非二值化結果

---

### 3.2 `/state/interaction/speech`

**說明**：語音管線狀態（持續發布）
**發布者**：`stt_intent_node`
**發布頻率**：5 Hz
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":            { "type": "float" },
  "phase":            { "type": "string", "enum": [
                          "idle_wakeword", "wake_ack", "loading_local_stack",
                          "listening", "transcribing", "local_asr_done",
                          "cloud_brain_pending", "speaking", "keep_alive", "unloading"
                        ],
                        "description": "語音狀態機當前階段" },
  "last_asr_text":    { "type": "string",   "description": "最近一次 ASR 文字" },
  "last_intent":      { "type": "string",   "description": "最近一次 Intent 標籤" },
  "models_loaded":    { "type": "array",    "items": "string",
                        "description": "當前已載入的模型 e.g. [\"kws\", \"asr\", \"tts\"]" }
}
```

**範例**：
```json
{
  "stamp": 1773561602.123,
  "phase": "listening",
  "last_asr_text": "你好",
  "last_intent": "greet",
  "models_loaded": ["kws", "asr", "tts"]
}
```

**狀態機流程**：
```
idle_wakeword → wake_ack → loading_local_stack → listening
  → transcribing → local_asr_done → cloud_brain_pending
  → speaking → keep_alive → idle_wakeword
  → (卸載) → unloading → idle_wakeword
```

---

### 3.3 `/state/executive/brain` ⚠️ planned / not yet implemented

**說明**：大腦決策狀態（完整版，持續發布）
**發布者**：`interaction_executive_node`（未來完整版）
**發布頻率**：2 Hz
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

> **v2.2 注記**：此 topic 為 v2.0 設計時規劃，executive 完整版會實作此 schema。
> 目前 v0 使用 `/executive/status`（見 3.5 節）發布簡化版狀態。

**Schema**：
```json
{
  "stamp":                  { "type": "float" },
  "executive_state":        { "type": "string", "enum": ["idle", "observing", "deciding", "executing", "speaking"] },
  "current_intent":         { "type": "string | null", "description": "當前判定的意圖" },
  "selected_skill":         { "type": "string | null", "description": "當前執行的技能" },
  "degradation_level":      { "type": "int",    "range": "[0, 3]", "description": "降級等級" },
  "active_tracks":          { "type": "int",    "description": "追蹤中的人臉數" },
  "cloud_connected":        { "type": "bool",   "description": "雲端 LLM 是否可用" },
  "last_decision_reason":   { "type": "string", "description": "最近決策理由（trace）" }
}
```

**範例**：
```json
{
  "stamp": 1773561603.456,
  "executive_state": "executing",
  "current_intent": "greet",
  "selected_skill": "hello",
  "degradation_level": 0,
  "active_tracks": 1,
  "cloud_connected": true,
  "last_decision_reason": "cloud_brain: Roy detected at 1.4m, greeting appropriate"
}
```

**降級等級對照**：

| Level | 名稱 | Brain 實作 |
|:-----:|------|-----------|
| 0 | 雲端完整 | CloudBrain (Qwen2.5-7B-Instruct, RTX 8000 vLLM) |
| 1 | 本地 LLM | LocalBrain (qwen2.5:1.5b, Ollama on Jetson) |
| 2 | 規則模式 | RuleBrain (Intent → Task → Skill) |
| 3 | 最小保底 | MinimalBrain (stop/greet/bye only) |

---

### 3.4 `/state/tts_playing`

**說明**：TTS 播放狀態（latched，變更時發布）
**發布者**：`tts_node`
**訂閱者**：`stt_intent_node`（echo gate）、`event_action_bridge`（TTS guard）
**QoS**：Reliable, TransientLocal, depth=1
**Message Type**：`std_msgs/Bool`

**行為**：
- `true`：TTS 正在播放（合成開始到播放完成+cooldown 0.5s 期間）
- `false`：TTS 空閒
- 啟動時立即發布 `false`，確保 latched topic 有初始值

**用途**：
- `stt_intent_node` 用此做 **echo gate**：TTS 播放中 + 結束後 1.0s cooldown 期間靜音麥克風
- `event_action_bridge` ~~用此做 **TTS guard**~~ (deprecated, v2.2)

---

### 3.5 `/executive/status` — v0 implemented

**說明**：Executive v0 state machine 狀態廣播
**發布者**：`interaction_executive_node`
**發布頻率**：2 Hz
**QoS**：BestEffort, TransientLocal, depth=1
**Message Type**：`std_msgs/String` (JSON)

> **v2.2 注記**：此為 v0 簡化版狀態 topic。Executive 完整版會改用 `/state/executive/brain`（見 3.3 節），屆時此 topic 將 deprecated。

**Schema**：
```json
{
  "state":           { "type": "string", "enum": ["idle", "greeting", "conversing", "executing", "emergency", "obstacle_stop"] },
  "previous_state":  { "type": "string", "description": "上一個狀態" },
  "state_duration":  { "type": "float",  "unit": "seconds", "description": "當前狀態持續時間" },
  "timestamp":       { "type": "float",  "unit": "seconds (Unix timestamp)" }
}
```

**範例**：
```json
{
  "state": "greeting",
  "previous_state": "idle",
  "state_duration": 2.3,
  "timestamp": 1773561603.456
}
```

### 3.6 `/state/pawai_brain` — v2.5 active

**說明**：PawAI Brain MVS 狀態廣播，供 Studio Brain Skill Console / Trace Drawer 觀測。
**發布者**：`brain_node`
**發布頻率**：2 Hz
**QoS**：Reliable, TransientLocal, depth=1
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "timestamp": { "type": "float", "unit": "seconds (Unix timestamp)" },
  "mode": { "type": "string", "enum": ["idle", "chat", "skill", "sequence", "alert", "safety_stop"] },
  "active_plan": {
    "type": "object | null",
    "fields": {
      "plan_id": "string",
      "selected_skill": "string",
      "step_index": "int",
      "step_total": "int",
      "started_at": "float",
      "priority_class": "int"
    }
  },
  "active_step": { "type": "object | null", "description": "目前 step executor + args" },
  "fallback_active": { "type": "bool" },
  "safety_flags": {
    "obstacle": "bool",
    "emergency": "bool",
    "fallen": "bool",
    "tts_playing": "bool",
    "nav_safe": "bool"
  },
  "cooldowns": { "type": "object", "description": "cooldown key -> last timestamp" },
  "last_plans": { "type": "array", "description": "recent SkillPlan summaries, max 5" }
}
```

**範例**：
```json
{
  "timestamp": 1777364860.0,
  "mode": "sequence",
  "active_plan": {
    "plan_id": "p-12345678",
    "selected_skill": "self_introduce",
    "step_index": 3,
    "step_total": 10,
    "started_at": 1777364859.0,
    "priority_class": 2
  },
  "active_step": { "executor": "motion", "args": { "name": "sit" } },
  "fallback_active": false,
  "safety_flags": {
    "obstacle": false,
    "emergency": false,
    "fallen": false,
    "tts_playing": false,
    "nav_safe": true
  },
  "cooldowns": { "self_introduce": 1777364859.0 },
  "last_plans": []
}
```

---

## 4. Event Topics

### 4.1 `/event/face_identity`

**說明**：人臉身份事件（條件觸發）
**發布者**：`face_identity_node`
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":       { "type": "float" },
  "event_type":  { "type": "string", "enum": ["track_started", "identity_stable", "identity_changed", "track_lost"] },
  "track_id":    { "type": "int" },
  "stable_name": { "type": "string",       "description": "穩定化身份名稱" },
  "sim":         { "type": "float",        "description": "相似度分數" },
  "distance_m":  { "type": "float | null", "description": "深度距離" }
}
```

**觸發規則**：

| event_type | 觸發條件 |
|-----------|----------|
| `track_started` | 新 track_id 首次出現（IOU 未匹配到既有 track） |
| `identity_stable` | Hysteresis 穩定化達到 `stable_hits` 閾值（`stable_name` 從 unknown → 具名） |
| `identity_changed` | 同一 track_id 的 `stable_name` 變更（例如遮臉後重新辨識為不同人） |
| `track_lost` | track 連續 `tracker_max_lost` 幀未匹配到任何偵測 |

**範例**（identity_stable）：
```json
{
  "stamp": 1773561601.500,
  "event_type": "identity_stable",
  "track_id": 1,
  "stable_name": "Roy",
  "sim": 0.42,
  "distance_m": 1.25
}
```

**範例**（track_lost）：
```json
{
  "stamp": 1773561610.000,
  "event_type": "track_lost",
  "track_id": 1,
  "stable_name": "Roy",
  "sim": 0.0,
  "distance_m": null
}
```

---

### 4.2 `/event/speech_intent_recognized`

**說明**：語音意圖識別事件（觸發式）
**發布者**：`stt_intent_node`
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":       { "type": "float" },
  "event_type":  { "type": "string", "enum": ["intent_recognized", "asr_result", "wake_word"] },
  "intent":      { "type": "string | null", "description": "Intent 標籤（asr_result 時為 null）" },
  "text":        { "type": "string",        "description": "ASR 原始文字" },
  "confidence":  { "type": "float",         "range": "[0.0, 1.0]" },
  "provider":    { "type": "string",        "description": "ASR provider e.g. whisper_local" }
}
```

**觸發規則**：

| event_type | 觸發條件 |
|-----------|----------|
| `wake_word` | Sherpa-onnx KWS 偵測到喚醒詞 |
| `asr_result` | ASR 轉寫完成（不一定有 intent） |
| `intent_recognized` | IntentClassifier 匹配到 intent |

**範例**：
```json
{
  "stamp": 1773561605.789,
  "event_type": "intent_recognized",
  "intent": "greet",
  "text": "你好",
  "confidence": 0.95,
  "provider": "whisper_local"
}
```

---

### 4.3 `/event/gesture_detected`

**說明**：手勢辨識事件（觸發式）
**發布者**：`vision_perception_node`
**訂閱者**：`interaction_executive_node`、`vision_status_display`（~~`interaction_router`~~ deprecated）
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":       { "type": "float" },
  "event_type":  { "type": "string", "enum": ["gesture_detected"] },
  "gesture":     { "type": "string", "enum": ["wave", "stop", "point", "ok", "thumbs_up", "thumbs_down", "victory", "i_love_you"], "description": "手勢類型" },
  "confidence":  { "type": "float",  "range": "[0.0, 1.0]", "description": "vote ratio（緩衝區投票比例），非原始分類器信心值" },
  "hand":        { "type": "string", "enum": ["left", "right"] }
}
```

**gesture enum 說明**：

| gesture | 來源 | 說明 |
|---------|------|------|
| `stop` | Gesture Recognizer (Open_Palm) / MediaPipe Hands | 停止 |
| `ok` | Gesture Recognizer (Closed_Fist → COMPAT_MAP) | OK |
| `point` | Gesture Recognizer (Pointing_Up) / MediaPipe Hands | 指向 |
| `wave` | MediaPipe Hands（時序分析） | 揮手 |
| `thumbs_up` | Gesture Recognizer (Thumb_Up) | 讚 |
| `thumbs_down` | Gesture Recognizer (Thumb_Down) | 倒讚 |
| `victory` | Gesture Recognizer (Victory) | 勝利 |
| `i_love_you` | Gesture Recognizer (ILoveYou) | 我愛你 |

> **Note**：`fist` 在 event_builder 的 `GESTURE_COMPAT_MAP` 中映射為 `ok`，下游收到的一律是 `ok`。

---

### 4.4 `/event/pose_detected`

**說明**：姿勢辨識事件（觸發式）
**發布者**：`vision_perception_node`
**訂閱者**：`interaction_executive_node`、`vision_status_display`（~~`interaction_router`~~ deprecated）
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":       { "type": "float" },
  "event_type":  { "type": "string", "enum": ["pose_detected"] },
  "pose":        { "type": "string", "enum": ["standing", "sitting", "crouching", "fallen"] },
  "confidence":  { "type": "float",  "range": "[0.0, 1.0]" },
  "track_id":    { "type": "int",    "description": "關聯的人臉 track_id（若可對應）" }
}
```

---

### 4.5 `/event/interaction/welcome` ⚠️ deprecated (v2.2)

> **v2.2**：此 topic 由 `interaction_executive_node` 內部處理，不再外部發布。保留文件供參考。

**說明**：迎賓事件（已知人臉首次穩定辨識時觸發）
**發布者**：~~`interaction_router`~~ (deprecated)
**訂閱者**：~~`event_action_bridge`~~ (deprecated)
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":       { "type": "float" },
  "event_type":  { "type": "string", "enum": ["welcome"] },
  "track_id":    { "type": "int",            "description": "人臉 track_id" },
  "name":        { "type": "string",         "description": "穩定化身份名稱" },
  "sim":         { "type": "float",          "description": "SFace 相似度分數" },
  "distance_m":  { "type": "float | null",   "description": "深度距離" }
}
```

**觸發規則**：
- 來源事件：`/event/face_identity` 中 `event_type == "identity_stable"` 且 `stable_name != "unknown"`
- 同一 track_id 在一個 session 中只觸發一次
- 同一 name 在 30 秒內不重複觸發（name-based debounce）
- `track_lost` 事件會清除該 track 的 welcome 記錄，重新進入可再觸發

**範例**：
```json
{
  "stamp": 1773561601.800,
  "event_type": "welcome",
  "track_id": 1,
  "name": "Roy",
  "sim": 0.42,
  "distance_m": 1.25
}
```

---

### 4.6 `/event/interaction/gesture_command` ⚠️ deprecated (v2.2)

> **v2.2**：此 topic 由 `interaction_executive_node` 內部處理，不再外部發布。保留文件供參考。

**說明**：手勢指令事件（白名單手勢觸發，附帶人臉上下文）
**發布者**：~~`interaction_router`~~ (deprecated)
**訂閱者**：~~`event_action_bridge`~~ (deprecated)
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":          { "type": "float" },
  "event_type":     { "type": "string", "enum": ["gesture_command"] },
  "gesture":        { "type": "string", "enum": ["stop", "ok", "thumbs_up"], "description": "白名單手勢" },
  "confidence":     { "type": "float",  "range": "[0.0, 1.0]" },
  "hand":           { "type": "string", "enum": ["left", "right", "unknown"] },
  "who":            { "type": "string | null", "description": "最近已知人臉名稱（無已知人臉時 null）" },
  "face_track_id":  { "type": "int | null",    "description": "對應的人臉 track_id" }
}
```

**觸發規則**：
- 僅白名單手勢觸發：`stop`、`ok`、`thumbs_up`（由 `interaction_rules.GESTURE_WHITELIST` 定義）
- `stop` 手勢不受 cooldown 限制（安全優先）
- 其他手勢有 `gesture_cooldown`（預設 2.0 秒）

**範例**：
```json
{
  "stamp": 1773561605.200,
  "event_type": "gesture_command",
  "gesture": "stop",
  "confidence": 0.85,
  "hand": "right",
  "who": "Roy",
  "face_track_id": 1
}
```

---

### 4.7 `/event/interaction/fall_alert` ⚠️ deprecated (v2.2)

> **v2.2**：此 topic 由 `interaction_executive_node` 內部處理，不再外部發布。保留文件供參考。

**說明**：跌倒警報事件（fallen 姿勢持續超過閾值時觸發）
**發布者**：~~`interaction_router`~~ (deprecated)
**訂閱者**：~~`event_action_bridge`~~ (deprecated)
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**：
```json
{
  "stamp":          { "type": "float" },
  "event_type":     { "type": "string", "enum": ["fall_alert"] },
  "pose":           { "type": "string", "enum": ["fallen"] },
  "confidence":     { "type": "float",  "range": "[0.0, 1.0]" },
  "persist_sec":    { "type": "float",  "description": "fallen 持續秒數" },
  "who":            { "type": "string | null", "description": "最近已知人臉名稱（無已知人臉時 null）" },
  "face_track_id":  { "type": "int | null",    "description": "對應的人臉 track_id" }
}
```

**觸發規則**：
- `fallen` 姿勢持續超過 `fallen_persist_sec`（預設 2.0 秒）
- 有 `fall_alert_cooldown`（預設 15.0 秒），避免連續告警
- 姿勢恢復後計時器重置

**範例**：
```json
{
  "stamp": 1773561620.500,
  "event_type": "fall_alert",
  "pose": "fallen",
  "confidence": 1.0,
  "persist_sec": 2.15,
  "who": "Roy",
  "face_track_id": 1
}
```

---

### 4.8 `/event/object_detected`

**說明**：物體偵測事件（COCO 80 class，預設全開；per-class cooldown 5s 去重）
**發布者**：`object_perception_node`
**訂閱者**：`interaction_executive_node`（5/6 起 brain_node `_on_object` 直接拆 `objects[]`；TTS whitelist ≈ 30 class，模板：`看到{COLOR_ZH}的{class_zh}了` + 可選 personality suffix）
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**（v2.5 5/6 補 `color` / `color_confidence`）：
```json
{
  "stamp":       { "type": "float",  "unit": "seconds (Unix timestamp)" },
  "event_type":  { "type": "string", "enum": ["object_detected"] },
  "objects":     { "type": "array", "items": {
    "class_name":        { "type": "string", "description": "COCO 80 class name (underscored)，完整列表見 object_perception/object_perception/coco_classes.py" },
    "confidence":        { "type": "float",  "range": "[0.0, 1.0]" },
    "bbox":              { "type": "array[4]", "items": "int", "description": "[x1, y1, x2, y2] pixel coords" },
    "color":             { "type": "string?", "enum": ["red","orange","yellow","green","cyan","blue","purple","pink","brown","black","white","gray"], "optional": true,
                           "description": "HSV-derived dominant colour from 12-class per-pixel classifier (5/6 expanded from 4). Brown gated on warm hue + dark V; black/white/gray on S/V achromatic. Field OMITTED when peak/total < 0.25 (too fragmented to commit)." },
    "color_confidence":  { "type": "float?",  "range": "[0.0, 1.0]", "optional": true,
                           "description": "peak colour mask pixels / total pixels in bbox. Always paired with `color` when present." }
  }}
}
```

**`class_id` 不在 publish payload**：`object_perception_node._publish_events` 顯式 strip 內部欄位（line ~306）；前端若需 id 應透過 `class_name` 反查 `coco_classes.py`。

**類別範圍**：COCO 80 class（YOLO 0-79 contiguous IDs）。原名含空格者統一底線（例：`dining table` → `dining_table`、`cell phone` → `cell_phone`、`traffic light` → `traffic_light`）。完整映射見 `object_perception/object_perception/coco_classes.py`。

**常用 P0 subset**（demo 展示目標，可用 `class_whitelist` 參數縮減）：

| Class | COCO ID | 命名 |
|-------|:-------:|------|
| person | 0 | `person` |
| dog | 16 | `dog` |
| bottle | 39 | `bottle` |
| cup | 41 | `cup` |
| chair | 56 | `chair` |
| dining table | 60 | `dining_table` |

**觸發規則**：
- 預設 `class_whitelist=[]` 表示 COCO 80 class 全開
- `class_whitelist=[0,16,39,41,56,60]` 可縮減為原 P0 6 class
- 新 class 出現且 per-class cooldown（預設 5s）過期時發布
- 同 class 連續偵測不重複發 event

---

### 4.9 `/event/obstacle_detected` ⛔ disabled (Demo 停用)

> **v2.2**：已實作（obstacle_avoidance_node + lidar_obstacle_node），但因 D435 鏡頭角度限制導致防撞不可靠，Demo 停用。程式碼與 schema 保留供未來改善。

**說明**：障礙物偵測事件（D435 depth 前方有近距離障礙物時觸發）
**發布者**：`obstacle_avoidance_node`（planned）
**訂閱者**：`interaction_executive_node`
**QoS**：BestEffort, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**（暫定）：
```json
{
  "stamp":           { "type": "float",  "unit": "seconds (Unix timestamp)" },
  "event_type":      { "type": "string", "enum": ["obstacle_detected"] },
  "distance_min":    { "type": "float",  "unit": "meters", "description": "最近障礙物距離" },
  "obstacle_ratio":  { "type": "float",  "range": "[0.0, 1.0]", "description": "ROI 內障礙物佔比" },
  "zone":            { "type": "string", "enum": ["danger"], "description": "判定區域（只在 danger 時發布）" }
}
```

---

## 5. Command Topics

### 5.0 PawAI Brain MVS command/event topics — v2.5 active

#### `/brain/text_input`

**說明**：Studio 文字輸入注入 Brain，等價於 synthetic speech intent。
**發布者**：`studio_gateway`
**訂閱者**：`brain_node`
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

```json
{
  "request_id": "string",
  "text": "string",
  "source": "studio_text",
  "created_at": "float"
}
```

#### `/brain/skill_request`

**說明**：Studio Skill Button request，仍需經 Brain registry 與 safety 驗證。
**發布者**：`studio_gateway`
**訂閱者**：`brain_node`
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

```json
{
  "request_id": "string",
  "skill": "string",
  "args": "object",
  "source": "studio_button",
  "created_at": "float"
}
```

#### `/brain/proposal`

**說明**：Brain 仲裁後送往 Executive 的 SkillPlan。
**發布者**：`brain_node`
**訂閱者**：`interaction_executive_node`、`studio_gateway`（觀測）
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

```json
{
  "plan_id": "string",
  "selected_skill": "string",
  "steps": [{ "executor": "say|motion|nav", "args": "object" }],
  "reason": "string",
  "source": "string",
  "priority_class": "int",
  "session_id": "string | null",
  "created_at": "float"
}
```

#### `/brain/skill_result`

**說明**：Executive 回報 SkillPlan / SkillStep lifecycle。Brain 訂閱此 topic 以維護 active sequence guard；Studio Gateway 訂閱作 UI trace。
**發布者**：`interaction_executive_node`
**訂閱者**：`brain_node`、`studio_gateway`
**QoS**：Reliable, Volatile, depth=20
**Message Type**：`std_msgs/String` (JSON)

```json
{
  "plan_id": "string",
  "step_index": "int | null",
  "status": "accepted|started|step_started|step_success|step_failed|completed|aborted|blocked_by_safety",
  "detail": "string",
  "selected_skill": "string",
  "priority_class": "int",
  "step_total": "int",
  "step_args": "object",
  "timestamp": "float"
}
```

#### `/brain/chat_candidate`

**說明**：Brain conversation engine 每輪對話提案。包含 LLM 回覆文字與選擇性的 skill 提案。
**發布者**：`llm_bridge_node`（legacy）、`pawai_brain` conversation engine（未來）
**訂閱者**：`brain_node`（中控仲裁）、`studio_gateway`（trace 觀測）
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema** (v2.7 Phase 0.5)：
```json
{
  "session_id":       { "type": "string",           "description": "speech session ID（如 speech-173...）" },
  "reply_text":       { "type": "string",           "description": "LLM 生成的自然回答文字" },
  "intent":           { "type": "string | null",    "description": "Intent 分類（如 chat, greet, confirm）" },
  "selected_skill":   { "type": "string | null",    "description": "legacy diagnostic，僅 4 條 P0 skill（已遺留，Brain 不採用）" },
  "reasoning":        { "type": "string",           "description": "決策來源（如 openrouter:eval_schema）" },
  "confidence":       { "type": "float",            "range": "[0.0, 1.0]" },
  
  "proposed_skill":   { "type": "string | null",    "description": "Phase 0.5：LLM 提案的 skill（如 self_introduce, show_status；null = 無提案）" },
  "proposed_args":    { "type": "object",           "description": "Phase 0.5：該 skill 的參數 dict" },
  "proposal_reason":  { "type": "string",           "description": "Phase 0.5：提案來源（如 openrouter:eval_schema, studio_button）" },
  "engine":           { "type": "string",           "enum": ["legacy", "langgraph"], "description": "Phase 0.5：識別發布者是哪個 engine" }
}
```

**範例**（含 skill 提案）：
```json
{
  "session_id": "speech-1730000000",
  "reply_text": "我是 PawAI，很高興認識你！",
  "intent": "greet",
  "selected_skill": null,
  "reasoning": "openrouter:eval_schema",
  "confidence": 0.88,
  "proposed_skill": "self_introduce",
  "proposed_args": {},
  "proposal_reason": "user asked who I am",
  "engine": "legacy"
}
```

**Phase 0.5 欄位說明**：
- `proposed_skill`：由 LLM JSON persona 的 `skill` 欄帶入（不過 `adapt_eval_schema` 的 SKILL_TO_CMD 過濾）。值為 null 時無 skill 提案，LLM 自然回答正常講出。
- `proposed_args`：該 skill 需要的參數（如座標、名稱、音量等），如無則空 dict。
- `proposal_reason`：紀錄提案來源以便除錯與 trace。
- `engine`：區分是 legacy primary 或 langgraph shadow，供 studio_gateway 觀測。
- `selected_skill`：保留向後相容，但 Brain MVS 不採用做提案來源；仍由 `adapt_eval_schema` 填入（診斷用）。

---

#### `/brain/conversation_trace`

**說明**：Primary conversation engine（legacy 或 langgraph）的執行 trace。每個 pipeline 階段發一筆，供 Studio Skill Trace Drawer 可視化決策過程。
**發布者**：`llm_bridge_node`（legacy 時發）、`pawai_brain` conversation engine（langgraph 時發）
**訂閱者**：`studio_gateway`（展示 trace）、除錯工具
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema** (v2.8)：
```json
{
  "session_id": { "type": "string",                              "description": "speech session ID，與 chat_candidate 一致" },
  "engine":     { "type": "string",                              "enum": ["legacy", "langgraph"], "description": "發布來源引擎" },
  "stage":      { "type": "string",                              "enum": ["input", "safety_gate", "world_state", "capability", "memory", "llm_decision", "json_validate", "repair", "skill_gate", "output"], "description": "pipeline 階段（5/7 起 langgraph engine 把 context+env 併進 world_state，並新增 capability stage）" },
  "status":     { "type": "string",                              "description": "階段狀態（見下表）" },
  "detail":     { "type": "string",                              "description": "階段特定訊息（如錯誤原因、skill 名稱、fallback 理由）" },
  "ts":         { "type": "float",                               "unit": "seconds (Unix timestamp)" }
}
```

**`status` enum 按 stage 分類**：

| stage | 適用 status | 說明 |
|-------|-----------|------|
| `input` | `ok` \| `error` | 輸入驗證 |
| `safety_gate` | `ok` \| `hit` \| `blocked` \| `error` | 安全層檢查；`hit` 為短路命中關鍵字 |
| `world_state` | `ok` \| `error` | env + perception 狀態快照（5/7 langgraph 引入） |
| `capability` | `ok` \| `error` | 33 條能力快照組裝（5/7 langgraph 引入；27 SkillContract + 6 DemoGuide） |
| `memory` | `ok` \| `error` | 記憶查詢 |
| `llm_decision` | `ok` \| `fallback` \| `error` | LLM 調用（失敗 → fallback） |
| `json_validate` | `ok` \| `retry` \| `error` | JSON 格式驗證 |
| `repair` | `ok` \| `fallback` \| `error` | JSON 修復（失敗 → fallback） |
| `skill_gate` | `proposed` \| `accepted` \| `accepted_trace_only` \| `blocked` \| `rejected_not_allowed` \| `needs_confirm` \| `demo_guide` | Brain 的 skill allowlist + safety 檢查；`needs_confirm`/`demo_guide` 為 5/8 langgraph 新增 |
| `output` | `ok` \| `fallback` \| `error` | 最終輸出（如 publish chat_candidate） |

**範例**（skill 被 allowlist 過濾）：
```json
{
  "session_id": "speech-1730000000",
  "engine": "legacy",
  "stage": "skill_gate",
  "status": "rejected_not_allowed",
  "detail": "proposed_skill='undefined_skill' not in allowlist",
  "ts": 1730000000.456
}
```

**範例**（skill 通過核可）：
```json
{
  "session_id": "speech-1730000000",
  "engine": "legacy",
  "stage": "skill_gate",
  "status": "accepted",
  "detail": "show_status",
  "ts": 1730000000.457
}
```

**範例**（LLM 落地到 fallback）：
```json
{
  "session_id": "speech-1730000000",
  "engine": "legacy",
  "stage": "llm_decision",
  "status": "fallback",
  "detail": "openrouter timeout; fallback to RuleBrain",
  "ts": 1730000000.123
}
```

---

#### `/brain/conversation_trace_shadow`

**說明**：Shadow conversation engine（LangGraph 或其他試驗版）的執行 trace。Schema 同 `/brain/conversation_trace`，但發布者為 shadow engine，**禁止** publish `/brain/chat_candidate` 或 `/brain/conversation_trace`。
**發布者**：`pawai_brain` shadow engine（如 LangGraph shadow）
**訂閱者**：`studio_gateway`（trace 展示）、除錯工具、A/B 比較系統
**QoS**：Reliable, Volatile, depth=10
**Message Type**：`std_msgs/String` (JSON)

**Schema**（同 `/brain/conversation_trace`）：
```json
{
  "session_id": { "type": "string" },
  "engine":     { "type": "string",                              "enum": ["legacy", "langgraph", "shadow"] },
  "stage":      { "type": "string",                              "enum": ["input", "safety_gate", "world_state", "capability", "memory", "llm_decision", "json_validate", "repair", "skill_gate", "output"] },
  "status":     { "type": "string" },
  "detail":     { "type": "string" },
  "ts":         { "type": "float",                               "unit": "seconds (Unix timestamp)" }
}
```

**用途與約束**：
- Shadow engine 可用 `engine="langgraph"` 或 `engine="shadow"` 標記自己（供前端 UI 分組顯示）
- **禁止** shadow 發 `/brain/chat_candidate`（確保 primary 唯一性）
- **禁止** shadow 發 `/brain/conversation_trace`（primary 專用）
- shadow 的決策結果（如 proposed_skill）只作 trace，不驅動執行，完全隔離主線
- Studio Trace Drawer 可同時展示 primary 與 shadow 的 stage 流程，用不同顏色/分欄區別

---

### 5.1 `/webrtc_req`

**說明**：Go2 WebRTC 命令（Skill 執行、音訊播放）
**訂閱者**：`go2_driver_node`
**Message Type**：`go2_interfaces/WebRtcReq`

**Schema**：
```
int64   id          # Message ID，0 表示自動分配
string  topic       # WebRTC topic
int64   api_id      # Skill command ID 或 audio api_id
string  parameter   # JSON 參數或 command ID 字串
uint8   priority    # 0=normal, 1=priority
```

**常用 topic 值**：

| topic | 用途 |
|-------|------|
| `rt/api/sport/request` | 運動指令 |
| `rt/api/audiohub/request` | 音訊播放 |

### 5.2 `/tts`

**說明**：TTS 輸入文字
**訂閱者**：`tts_node`
**Message Type**：`std_msgs/String`

**範例**：
```python
msg = String()
msg.data = "哈囉，你好！"
self.publisher.publish(msg)
```

---

## 6. Skill 命令對照表

### 6.1 P0 安全動作

| Skill 名稱 | api_id | 參數 | 說明 | 安全等級 |
|-----------|--------|------|------|----------|
| `Hello` | 1016 | `"1016"` | 揮手打招呼 | 安全 |
| `BalanceStand` | 1002 | `"1002"` | 平衡站立 | 安全 |
| `Sit` | 1009 | `"1009"` | 坐下 | 安全 |
| `RiseSit` | 1010 | `"1010"` | 起身 | 安全 |
| `StopMove` | 1003 | `"1003"` | 停止移動 | 安全 |

### 6.2 P1 展示動作

| Skill 名稱 | api_id | 說明 | 安全等級 |
|-----------|--------|------|----------|
| `Stretch` | 1017 | 伸展 | 中等 |
| `Content` | 1020 | 開心/滿足 | 安全 |
| `FingerHeart` | 1036 | 比心 | 安全 |
| `WiggleHips` | 1033 | 搖屁股 | 安全 |

### 6.3 高風險動作（禁止使用）

| Skill 名稱 | api_id | 說明 | 風險 |
|-----------|--------|------|------|
| `FrontFlip` | 1030 | 前空翻 | 危險 |
| `FrontJump` | 1031 | 前跳 | 危險 |
| `Handstand` | 1301 | 倒立 | 不穩定 |

### 6.4 音訊播放指令（api_id）

| api_id | 動作 | parameter |
|--------|------|-----------|
| 4004 | 設定音量 | `"80"` (0-100) |
| 4001 | 開始播放 | `""` |
| 4003 | 音訊資料塊 | `{"current_block_index":N, "total_block_number":M, "block_content":"base64..."}` |
| 4002 | 停止播放 | `""` |

**完整命令列表**：參見 `go2_robot_sdk/go2_robot_sdk/domain/constants/robot_commands.py`

---

## 7. 節點參數規格

### 7.1 FaceIdentityNode 參數

**現有實作**：`scripts/face_identity_infer_cv.py`
**4/13 後回收為**：ROS2 package `face_perception`

> 現為 argparse CLI 參數（`--xxx` 格式），4/13 後回收為 ROS2 `declare_parameter` 時保持同名。

#### 核心對外契約參數

會直接影響 `/state/perception/face` 和 `/event/face_identity` 輸出行為的參數：

| CLI 參數 | 型別 | 預設值 | 說明 |
|----------|------|--------|------|
| `--color-topic` | string | `/camera/camera/color/image_raw` | RGB 影像來源 |
| `--depth-topic` | string | `/camera/camera/aligned_depth_to_color/image_raw` | 深度影像來源 |
| `--model-path` | string | `/home/jetson/face_db/model_sface.pkl` | SFace 人臉資料庫路徑 |
| `--db-dir` | string | `/home/jetson/face_db` | 人臉資料庫目錄 |
| `--det-score-threshold` | float | `0.90` | YuNet 偵測閾值 |
| `--sim-threshold-upper` | float | `0.35` | Hysteresis 上閾值 |
| `--sim-threshold-lower` | float | `0.25` | Hysteresis 下閾值 |
| `--stable-hits` | int | `3` | 穩定化所需連續命中幀數 |
| `--track-iou-threshold` | float | `0.3` | IOU 匹配閾值 |
| `--track-max-misses` | int | `10` | 最大遺失幀數 |
| `--max-faces` | int | `5` | 最大同時追蹤人數 |
| `--publish-fps` | float | `8.0` | 狀態發布幀率 |

#### 實作 / 除錯參數

不影響對外介面行為，僅影響內部偵測品質或除錯輸出：

| CLI 參數 | 型別 | 預設值 | 說明 |
|----------|------|--------|------|
| `--yunet-model` | string | *(見原始碼)* | YuNet ONNX 模型路徑 |
| `--sface-model` | string | *(見原始碼)* | SFace ONNX 模型路徑 |
| `--det-nms-threshold` | float | `0.30` | YuNet NMS 閾值 |
| `--det-top-k` | int | `5000` | YuNet 偵測候選框上限 |
| `--unknown-grace-s` | float | `1.2` | 新 track 暫緩判 unknown 的寬限秒數 |
| `--min-face-area-ratio` | float | `0.02` | 最小人臉面積佔比（過小忽略） |
| `--tick-period` | float | `0.05` | 主迴圈 timer 週期（秒） |
| `--no-publish-compare-image` | flag | `false` | 停止發布比對 debug 影像 |
| `--headless` | flag | `false` | 無 GUI 模式（不顯示 cv2 視窗） |
| `--save-debug-jpeg` | flag | `false` | 儲存 debug JPEG 到磁碟 |

### 7.2 STTIntentNode 參數

**實作**：`speech_processor/speech_processor/stt_intent_node.py`

| 參數名 | 型別 | 預設值 | 說明 |
|--------|------|--------|------|
| `provider_order` | string[] | `["qwen_cloud", "whisper_local"]` | ASR provider 優先序 |
| `input_device` | int | `-1` | ALSA 錄音裝置 index（-1 = 系統預設） |
| `sample_rate` | int | `16000` | 目標取樣率 |
| `capture_sample_rate` | int | `16000` | 麥克風原生取樣率（Jetson 實測需改 44100） |
| `max_record_seconds` | float | `6.0` | 單次錄音最長秒數 |
| `energy_vad.enabled` | bool | `true` | 是否啟用 Energy VAD |
| `energy_vad.start_threshold` | float | `0.015` | Energy VAD 啟動閾值 |
| `energy_vad.stop_threshold` | float | `0.01` | Energy VAD 停止閾值 |
| `energy_vad.silence_duration_ms` | int | `800` | 靜音持續判定（毫秒） |
| `energy_vad.min_speech_ms` | int | `300` | 最短語音段（毫秒） |

> **注意**：Energy VAD 參數為 namespaced 格式。ROS2 啟動時指定方式：
> ```bash
> ros2 run speech_processor stt_intent_node --ros-args \
>   -p energy_vad.start_threshold:=0.10 \
>   -p energy_vad.silence_duration_ms:=450
> ```
> 使用者在 Jetson 上實測調整過的值（`start=0.10, stop=0.03, silence=450, min_speech=900`）與程式碼預設值不同，部署時需覆蓋。

---

## 8. QoS 規格

### 8.1 State Topics

| Topic | Reliability | Durability | Depth | 頻率 | 狀態 |
|-------|-------------|------------|-------|------|:----:|
| `/state/perception/face` | Reliable | Volatile | 10 | 10 Hz | active |
| `/state/interaction/speech` | Reliable | Volatile | 10 | 5 Hz | active |
| `/state/executive/brain` | Reliable | Volatile | 10 | 2 Hz | planned |
| `/executive/status` | BestEffort | TransientLocal | 1 | 2 Hz | v0 |
| `/state/tts_playing` | Reliable | TransientLocal | 1 | 變更式 | active |
| `/state/nav/paused` | Reliable | TransientLocal | 1 | 變更式 | v2.6 active |
| `/capability/nav_ready` | Reliable | TransientLocal | 1 | 1 Hz | v2.6 active |
| `/capability/depth_clear` | Reliable | TransientLocal | 1 | 5 Hz | v2.6 active |

### 8.2 Event Topics

| Topic | Reliability | Durability | Depth | 狀態 |
|-------|-------------|------------|-------|:----:|
| `/event/face_identity` | Reliable | Volatile | 10 | active |
| `/event/speech_intent_recognized` | Reliable | Volatile | 10 | active |
| `/event/gesture_detected` | Reliable | Volatile | 10 | active |
| `/event/pose_detected` | Reliable | Volatile | 10 | active |
| `/event/object_detected` | Reliable | Volatile | 10 | active |
| `/event/obstacle_detected` | BestEffort | Volatile | 10 | disabled |
| `/event/interaction/welcome` | Reliable | Volatile | 10 | deprecated |
| `/event/interaction/gesture_command` | Reliable | Volatile | 10 | deprecated |
| `/event/interaction/fall_alert` | Reliable | Volatile | 10 | deprecated |

### 8.3 Command Topics

| Topic | Reliability | Durability | Depth |
|-------|-------------|------------|-------|
| `/webrtc_req` | Reliable | Volatile | 10 |
| `/tts` | Reliable | Volatile | 10 |

---

## 9. 錯誤處理

### 9.1 無效訊息處理

接收方應該：
1. 驗證 JSON schema
2. 無效訊息記錄警告但不中斷流程
3. 繼續處理下一筆訊息

```python
try:
    payload = json.loads(msg.data)
except json.JSONDecodeError:
    self.get_logger().warning("Ignore invalid JSON")
    return

# 驗證必要欄位（以 face_identity 為例）
required = {"stamp", "event_type", "track_id"}
if not required.issubset(payload.keys()):
    self.get_logger().warning(f"Missing required fields: {required - payload.keys()}")
    return
```

### 9.2 超時處理

| 情境 | 超時時間 | 行為 |
|------|----------|------|
| Skill 執行 | 10 秒 | 記錄錯誤，不回應 |
| State 更新 | 2 秒 | 標記為 stale |
| Event 處理 | 1 秒 | 丟棄過期事件 |
| 雲端 LLM 回應 | 3 秒 | fallback 到下一級 Brain |

---

## 10. 版本歷史

| 版本 | 日期 | 變更內容 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-03-09 | 介面凍結 | System Architect |
| v2.0 | 2026-03-13 | 對齊 mission v2.0：face_identity 事件、speech/brain state schema、P1 topics | System Architect |
| v2.1 | 2026-03-25 | interaction_router 三事件、/state/tts_playing、gesture enum 擴充、發布者名稱修正、LLM 型號修正 | System Architect |
| v2.2 | 2026-04-01 | Executive v0 取代 router+bridge；新增 `/executive/status`(v0)、`/event/obstacle_detected`(planned)；deprecate interaction_router/event_action_bridge 及其 3 個 topic；`/state/executive/brain` 標記 planned | System Architect |
| v2.3 | 2026-04-05 | 新增 `/event/object_detected`（YOLO26n 物體偵測，多物件 objects 陣列 schema）；obstacle_detected 章節重編號 4.8→4.9 | System Architect |
| v2.4 | 2026-04-05 | `/event/object_detected` 擴充至 COCO 80 class（預設全開）；`class_name` enum → reference `coco_classes.py`；新增 `class_whitelist` 參數可縮減 | System Architect |
| v2.7 | 2026-05-06 | Phase 0.5 Conversation Engine：`/brain/chat_candidate` 新增 4 欄位（`proposed_skill` / `proposed_args` / `proposal_reason` / `engine`）；新增 `/brain/conversation_trace` 與 `/brain/conversation_trace_shadow` topics | System Architect |
| v2.8 | 2026-05-08 | Phase A.6 Capability Awareness：`/brain/conversation_trace.stage` enum 把 `context` 換成 `world_state` + `capability`（langgraph engine）；`skill_gate.status` 加 `needs_confirm` / `demo_guide`；`/state/perception/face` 的 `sim_threshold_upper` 從 0.30 拉高到 **0.40**（5/8 demo 期陌生人誤觸抑制）；`/brain/chat_candidate` schema 不變（DemoGuide 只進 conversation_trace，Brain contract 維持乾淨） | System Architect |

---

## 11. 相關文件

- [mission/README.md](../../mission/README.md) — 專案總覽與功能閉環設計
- [Pawai-studio/specs/event-schema.md](../../pawai-brain/studio/specs/event-schema.md) — Studio Gateway JSON schema（WebSocket 層）
- [Pawai-studio/specs/brain-adapter.md](../../pawai-brain/studio/specs/brain-adapter.md) — Brain Adapter 介面與四級降級

---

*維護者：System Architect*
*狀態：v2.7 active（Phase 0.5 Conversation Engine）*
