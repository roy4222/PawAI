# PawAI Event / State / Command / Panel Schema

**文件版本**：v1.0
**最後更新**：2026-03-13
**對齊來源**：[mission/README.md](../mission/README.md) v2.0、[interaction_contract.md](../architecture/interaction_contract.md) v1.0

> 本文件定義 PawAI Studio Gateway 與 Frontend 之間的 JSON schema。
> ROS2 層的 Topic schema 見 [interaction_contract.md](../architecture/interaction_contract.md)。

---

## 1. Event Schema（事件）

事件是**觸發式**的，代表系統中發生了值得記錄的事情。

### 1.1 通用信封

所有事件共用此信封格式，透過 WebSocket `/ws/events` 推送：

```typescript
interface PawAIEvent {
  id: string;              // UUID v4
  timestamp: string;       // ISO 8601, e.g. "2026-03-13T10:00:00.123+08:00"
  source: string;          // 來源模組: "face" | "speech" | "gesture" | "pose" | "brain" | "system"
  event_type: string;      // 事件類型（見下方各模組定義）
  data: Record<string, unknown>;  // 事件資料（各模組不同）
}
```

### 1.2 人臉事件

**來源 ROS2 Topic**：`/event/face_identity`

```typescript
interface FaceIdentityEvent extends PawAIEvent {
  source: "face";
  event_type: "track_started" | "identity_stable" | "identity_changed" | "track_lost";
  data: {
    track_id: number;
    stable_name: string;        // 穩定化後的身份名稱，unknown 表示未識別
    sim: number;                // 相似度分數 [0.0, 1.0]
    distance_m: number | null;  // 深度距離（公尺），無深度時 null
  };
}
```

**觸發規則**：
| event_type | 觸發條件 |
|-----------|----------|
| `track_started` | 新 track_id 首次出現 |
| `identity_stable` | Hysteresis 穩定化達到 stable_hits 閾值 |
| `identity_changed` | 同一 track_id 的 stable_name 變更 |
| `track_lost` | track 連續 max_misses 幀未匹配 |

### 1.3 語音事件

**來源 ROS2 Topic**：`/event/speech_intent_recognized`

```typescript
interface SpeechIntentEvent extends PawAIEvent {
  source: "speech";
  event_type: "intent_recognized" | "asr_result" | "wake_word";
  data: {
    intent?: string;       // greet | come_here | stop | take_photo | status | ...
    text: string;          // ASR 原始文字
    confidence: number;    // [0.0, 1.0]
    provider: string;      // "whisper_local" | "whisper_cloud"
  };
}
```

### 1.4 手勢事件（P1）

**來源 ROS2 Topic**：`/event/gesture_detected`

```typescript
interface GestureEvent extends PawAIEvent {
  source: "gesture";
  event_type: "gesture_detected";
  data: {
    gesture: string;       // "wave" | "stop" | "point" | "ok"
    confidence: number;
    hand: "left" | "right";
  };
}
```

### 1.5 姿勢事件（P1）

**來源 ROS2 Topic**：`/event/pose_detected`

```typescript
interface PoseEvent extends PawAIEvent {
  source: "pose";
  event_type: "pose_detected";
  data: {
    pose: string;          // "standing" | "sitting" | "crouching" | "fallen"
    confidence: number;
    track_id: number;
  };
}
```

### 1.6 大腦事件

```typescript
interface BrainEvent extends PawAIEvent {
  source: "brain";
  event_type: "decision_made" | "skill_dispatched" | "skill_completed" | "fallback_triggered";
  data: {
    intent: string;        // 判定的意圖
    selected_skill: string; // 選擇的技能
    reason: string;        // 決策理由（LLM trace 或 rule match）
    degradation_level: 0 | 1 | 2 | 3;  // 當前降級等級
  };
}
```

### 1.7 系統事件

```typescript
interface SystemEvent extends PawAIEvent {
  source: "system";
  event_type: "module_online" | "module_offline" | "degradation_change" | "error";
  data: {
    module: string;        // "face" | "speech" | "brain" | "gateway" | ...
    message: string;
    level: "info" | "warning" | "error";
  };
}
```

---

## 2. State Schema（狀態）

狀態是**持續更新**的，代表系統當前快照。透過 WebSocket `/ws/events` 統一推送（與事件共用同一 endpoint），或 REST `GET /api/{resource}` 拉取。

### 2.1 人臉狀態

**來源 ROS2 Topic**：`/state/perception/face`
**更新頻率**：10 Hz

```typescript
interface FaceState {
  stamp: number;           // Unix timestamp (seconds)
  face_count: number;      // 當前追蹤人數
  tracks: FaceTrack[];
}

interface FaceTrack {
  track_id: number;
  stable_name: string;     // 穩定化後的身份名稱
  sim: number;             // 相似度
  distance_m: number | null;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  mode: "stable" | "hold"; // stable=已穩定, hold=尚在判定中
}
```

### 2.2 語音狀態

**來源 ROS2 Topic**：`/state/interaction/speech`

```typescript
interface SpeechState {
  stamp: number;
  phase: "idle_wakeword" | "wake_ack" | "loading_local_stack" | "listening"
       | "transcribing" | "local_asr_done" | "cloud_brain_pending"
       | "speaking" | "keep_alive" | "unloading";
  last_asr_text: string;
  last_intent: string;
  last_tts_text: string;   // Gateway-derived field — 由 Gateway 從 TTS 狀態聚合填入，非直接對應單一 ROS2 topic 欄位
  models_loaded: string[];  // ["kws"] | ["kws","asr","tts"] | ...
}
```

### 2.3 大腦狀態

**來源 ROS2 Topic**：`/state/executive/brain`

```typescript
interface BrainState {
  stamp: number;
  executive_state: "idle" | "observing" | "deciding" | "executing" | "speaking";
  current_intent: string | null;
  selected_skill: string | null;
  degradation_level: 0 | 1 | 2 | 3;
  active_tracks: number;      // 追蹤中的人臉數
  cloud_connected: boolean;
  last_decision_reason: string;
}
```

### 2.4 系統健康狀態

**來源**：Gateway 定期從 Jetson 收集

```typescript
interface SystemHealth {
  stamp: number;
  jetson: {
    cpu_percent: number;
    gpu_percent: number;
    ram_used_mb: number;
    ram_total_mb: number;    // 8192
    temperature_c: number;
  };
  modules: ModuleHealth[];
}

interface ModuleHealth {
  name: string;             // "face" | "speech" | "brain" | "kws" | "asr" | "tts"
  status: "active" | "inactive" | "loading" | "error";
  latency_ms: number | null;
  last_heartbeat: number;   // Unix timestamp
}
```

### 2.5 手勢狀態

**來源 ROS2 Topic**：`/state/perception/gesture`
**更新頻率**：狀態變化時

```typescript
interface GestureState {
  stamp: number;
  active: boolean;                      // 是否有手勢被偵測
  current_gesture: string | null;       // "wave" | "stop" | "point" | "ok" | null
  confidence: number;                   // [0.0, 1.0]
  hand: "left" | "right" | null;
  status: "active" | "inactive" | "loading";
}
```

### 2.6 姿勢狀態

**來源 ROS2 Topic**：`/state/perception/pose`
**更新頻率**：狀態變化時

```typescript
interface PoseState {
  stamp: number;
  active: boolean;
  current_pose: string | null;          // "standing" | "sitting" | "crouching" | "fallen" | null
  confidence: number;                   // [0.0, 1.0]
  track_id: number | null;             // 對應的人臉 track_id
  status: "active" | "inactive" | "loading";
}
```

### 2.7 機器人狀態

**來源**：go2_driver_node

```typescript
interface RobotState {
  stamp: number;
  mode: "idle" | "interaction" | "executing_skill";
  posture: "stand" | "sit" | "lie" | "unknown";
  battery_percent: number;
  current_skill: string | null;
  webrtc_connected: boolean;
}
```

---

## 3. Command Schema（指令）

前端透過 REST 或 WebSocket 向 Gateway 發送指令。

### 3.1 技能指令

```typescript
// POST /api/command
interface SkillCommand {
  command_type: "skill";
  skill_id: string;           // "hello" | "balance_stand" | "sit" | "rise_sit" | "stop_move"
  priority: 0 | 1;            // 0=normal, 1=urgent (stop)
  source: "studio_button" | "studio_chat" | "brain";
}
```

**Skill 對照**：

| skill_id | api_id | Go2 動作 | 安全等級 |
|----------|--------|----------|----------|
| `hello` | 1016 | 揮手打招呼 | 安全 |
| `balance_stand` | 1002 | 平衡站立 | 安全 |
| `sit` | 1009 | 坐下 | 安全 |
| `rise_sit` | 1010 | 起身 | 安全 |
| `stop_move` | 1003 | 停止移動 | 安全 |

### 3.2 對話指令

```typescript
// POST /api/chat
interface ChatCommand {
  command_type: "chat";
  text: string;               // 使用者輸入文字
  session_id: string;         // 對話 session UUID
}
```

### 3.3 Mock 指令

```typescript
// POST /mock/trigger
interface MockTrigger {
  event_source: string;       // "face" | "speech" | "gesture" | ...
  event_type: string;
  data: Record<string, unknown>;
}
```

---

## 4. Panel Schema（面板配置）

大腦或 Executive 決定當前應顯示哪些面板。

### 4.1 Layout 定義

```typescript
type LayoutPreset = "chat_only" | "chat_camera" | "chat_speech"
                  | "chat_camera_speech" | "chat_gesture" | "chat_pose"
                  | "chat_full" | "demo";

interface PanelLayout {
  preset: LayoutPreset;
  panels: PanelConfig[];
}

interface PanelConfig {
  panel_id: string;           // "chat" | "camera" | "face" | "speech" | "timeline" | "brain" | "health" | "skills" | "gesture" | "pose"
  visible: boolean;
  position: "main" | "sidebar" | "bottom" | "overlay";
  size: "small" | "medium" | "large";
}
```

### 4.2 預設 Layout

| Preset | 可見面板 | 觸發條件 |
|--------|---------|----------|
| `chat_only` | Chat | 預設、無事件時 |
| `chat_camera` | Chat + Camera + Face | 偵測到人臉 |
| `chat_speech` | Chat + Speech | 語音互動中 |
| `chat_full` | 全部面板（含 Robot Status + Health） | Debug 或主動展開 |
| `demo` | Chat + Camera + Timeline + Brain | Demo Showcase 頁面 |

### 4.3 Layout 切換事件

```typescript
interface LayoutChangeEvent extends PawAIEvent {
  source: "brain";
  event_type: "layout_change";
  data: {
    previous: LayoutPreset;
    current: LayoutPreset;
    reason: string;           // "face_detected" | "speech_active" | "user_toggle" | "demo_start"
  };
}
```

---

## 5. 前端開發指南

### 5.1 WebSocket 訂閱流程

```typescript
// 1. 連接
const ws = new WebSocket("ws://gateway:8000/ws/events");

// 2. 接收事件
ws.onmessage = (msg) => {
  const event: PawAIEvent = JSON.parse(msg.data);
  switch (event.source) {
    case "face":    handleFaceEvent(event); break;
    case "speech":  handleSpeechEvent(event); break;
    case "brain":   handleBrainEvent(event); break;
    // ...
  }
};
```

### 5.2 Mock 開發模式

前端開發時，將 Gateway URL 指向 Mock Event Server：

```bash
# .env.development
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001/ws/events
```

Mock Server 提供完全相同的 WebSocket 和 REST 介面，差別只在資料來源是假資料。

---

*最後更新：2026-03-13*
*維護者：System Architect*
