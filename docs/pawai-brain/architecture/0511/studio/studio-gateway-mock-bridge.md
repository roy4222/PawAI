# Studio Gateway / Mock Server 雙路徑 + Event Schema 對接

**版本**：2026-05-11 freeze 快照
**真相來源**：`pawai-studio/gateway/studio_gateway.py`、`pawai-studio/backend/mock_server.py`、`pawai-studio/frontend/contracts/types.ts`

---

## 1. 雙路徑對比

| 面向 | Gateway（Jetson 模式） | Mock Server（本機開發）|
|------|----------------------|----------------------|
| 啟動 | `studio_gateway.py`（需 ROS2 + rclpy）| `mock_server.py`（純 FastAPI）|
| WS 事件來源 | ROS2 topic callback → `asyncio.run_coroutine_threadsafe` | `periodic_mock_push()`（2s 隨機）|
| `/api/text_input` | publish `/brain/text_input` → 真 LLM 管線 | `_emit_text_reply("我聽不太懂 (mock)")` |
| `/api/text_input` opt-in | — | `MOCK_OPENROUTER=1` → Gemini 3 Flash 真 LLM |
| `/api/skill_request` | publish `/brain/skill_request` → 真 Executive | 查 `SKILL_REGISTRY`，broadcast proposal+result |
| `/api/capability` | 讀 `self._cap_state`（Bool subscriber tri-state）| 讀 `_mock_capability`（`POST /api/capability` 可覆寫）|
| `/ws/speech` | 真 ASR（SenseVoice → IntentClassifier）| canned `MOCK_ASR_RESPONSES` 隨機 |
| CORS | `allow_origins=["*"]`（5/7 hotfix，L444-449）| `allow_origins=["http://localhost:3000","http://localhost:3001"]`（L310-316）|

---

## 2. PawAIEvent 信封（事件 schema）

真相來源：`pawai-studio/frontend/contracts/types.ts` L12-18

```typescript
export interface PawAIEvent {
  id: string;         // uuid4
  timestamp: string;  // ISO 8601（含時區）
  source: string;     // 下表
  event_type: string; // source 特定
  data: Record<string, unknown>;
}
```

**所有 source 枚舉**：

| source | 產生者 |
|--------|--------|
| `"face"` | face_perception / mock_face_event |
| `"gesture"` | vision_perception / mock_gesture_event |
| `"pose"` | vision_perception / mock_pose_event |
| `"speech"` | speech_processor / mock_speech_event |
| `"object"` | object_perception / mock_object_event |
| `"brain"` | interaction_executive + pawai_brain |
| `"tts"` | `_on_tts_msg()` 包裝 /tts |
| `"capability"` | `_on_capability_msg()` |

---

## 3. 各模組 Data Schema

### Face（`contracts/types.ts` L47-56）
```typescript
interface FaceState {
  stamp: number;
  face_count: number;
  tracks: FaceTrack[];  // {track_id, stable_name, sim, distance_m, bbox, mode}
}
```
Gateway field transform（`studio_gateway.py` L295-299）：face 只做 throttle，不補字段。

### Gesture（`contracts/types.ts` L104-111）
```typescript
interface GestureState {
  stamp: number;
  active: boolean;
  current_gesture: string | null;
  confidence: number;
  hand: "left" | "right" | null;
  status: "active" | "inactive" | "loading";
}
```
Gateway 補充（L309-315）：`current_gesture = data.gesture`，`active=true`，`status="active"`。

### Pose（`contracts/types.ts` L126-133）
```typescript
interface PoseState {
  stamp: number;
  active: boolean;
  current_pose: string | null;
  confidence: number;
  track_id: number | null;
  status: "active" | "inactive" | "loading" | "error";
}
```

### Speech（`contracts/types.ts` L81-88）
```typescript
interface SpeechState {
  stamp: number;
  phase: SpeechPhase;       // "idle_wakeword"|"listening"|"transcribing"|"speaking"|...
  last_asr_text: string;
  last_intent: string;
  last_tts_text: string;
  models_loaded: string[];
}
```
Gateway 補充（L323）：`phase = data.phase ?? "listening"`。

### Object（`contracts/types.ts` L154-171）
```typescript
interface ObjectEvent {
  data: {
    stamp?: number;
    active?: boolean;
    status?: "active" | "inactive" | "loading";
    objects?: ObjectDetection[];
    detected_objects?: ObjectDetection[];  // legacy 路徑
  }
}
```
前端 `normalizeObjectState()`（`lib/object-event.ts`）合併兩個欄位。

### TTS（`studio_gateway.py` L115-130）
```typescript
// build_tts_event() 輸出：
{
  id: uuid4,
  timestamp: ISO8601,
  source: "tts",
  event_type: "tts_speaking",
  data: {
    text: string,
    phase: "speaking",
    origin: "tts" | "studio_text" | ...,
    source?: string  // "chat_reply" | "skill_say" | "say_canned"
  }
}
```

### Brain（`contracts/types.ts` L183-276）

| event_type | data 型別 |
|-----------|---------|
| `"state"` | `PawAIBrainState` |
| `"proposal"` | `SkillPlan`（plan_id, steps[], priority_class）|
| `"skill_result"` | `SkillResult`（status: accepted/started/step_started/step_success/completed/aborted/blocked_by_safety）|
| `"conversation_trace"` | `ConversationTracePayload`（stage, status, detail, ts）|

**ConversationTracePayload stages**（`contracts/types.ts` L432-449）：
`input` / `safety_gate` / `context` / `world_state` / `capability` / `memory` / `llm_decision` / `json_validate` / `repair` / `verifier` / `gesture_gate` / `skill_gate` / `output`

---

## 4. Mock 技能模擬（mock_server.py）

`POST /api/skill_request` 查 `SKILL_REGISTRY`（`interaction_executive.skill_contract`）：

```python
# mock_server.py L415-473
contract = SKILL_REGISTRY.get(skill)
if not contract.static_enabled or contract.enabled_when:
    # → broadcast skill_result{status="blocked_by_safety"}
else:
    # → broadcast proposal + skill_result{status="completed"}
```

技能 bucket 路由（L431-432）：
- `disabled / enabled_when` → `blocked_by_safety`（Trace Drawer 顯示紅色）
- `active` → proposal → completed（Trace Drawer 顯示綠色）

---

## 5. Mock OpenRouter 路徑（mock_server.py L541-595）

```python
# mock_server.py L43
_MOCK_OPENROUTER_ENABLED = os.environ.get("MOCK_OPENROUTER", "").strip() == "1"
```

啟用後：`POST /api/text_input` → `asyncio.to_thread(_openrouter_chat, text)` → Gemini 3 Flash（`tools/llm_eval/openrouter_chat.py`）→ `_emit_text_reply()` 廣播 `proposal + skill_result + tts_speaking`。

`_emit_text_reply()`（L475-527）同時廣播 `tts:tts_speaking`，**否則 ChatPanel 看不到 AI 回覆**（L511-526 注釋說明）。

---

## 6. Demo A 場景（mock_server.py L236-266）

```python
DEMO_A_SEQUENCE = [
    ("face", "track_started", ...FaceIdentityData(stable_name="unknown")),
    ("face", "identity_stable", ...FaceIdentityData(stable_name="小明", sim=0.92)),
    ("speech", "wake_word", ...),
    ("speech", "intent_recognized", ...SpeechIntentData(intent="greet", text="你好")),
    ("brain", "decision_made", ...),
    ("brain", "skill_dispatched", ...),
]
```

觸發：`POST /mock/scenario/demo_a` → 1.5s/step broadcast。

---

## 7. 啟動指令

```bash
# Mock 模式（本機開發）
bash pawai-studio/start-live.sh --mock
# → frontend: http://localhost:3000/studio
# → mock API: http://localhost:8080

# Mock + 真 Gemini 對話（需 .env 有 OPENROUTER_KEY）
set -a && . ./.env && set +a
MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock

# Jetson 模式（需 source ROS2 + colcon build）
bash pawai-studio/start-live.sh --live
# GATEWAY_HOST override（預設 Tailscale 100.83.109.89:8080）
GATEWAY_HOST=192.168.0.222 bash pawai-studio/start-live.sh --live

# Gateway 單獨啟動（Jetson 上）
source /opt/ros/humble/setup.zsh && source install/setup.zsh
python3 pawai-studio/gateway/studio_gateway.py
```

---

## 8. 已知差異 / 陷阱

- **CORS 差異**：Gateway `allow_origins=["*"]`（5/7 hotfix），Mock 只允許 localhost。Jetson 跨 Tailscale IP 要靠 Gateway 的 wildcard。
- **`/tts` → tts_speaking**：只有 Gateway 和 Mock 的 `_emit_text_reply()` 才廣播，純 WS 路徑不補。
- **skill_registry path**：Gateway 從 `interaction_executive` import（需 ROS2 PYTHONPATH）；Mock 也 import 同樣的 `SKILL_REGISTRY`，import 失敗時 `SKILL_REGISTRY = {}` silent fallback（mock_server.py L29-31）。
- **Video streaming**：只有 Gateway 支援（cv2 + cv_bridge），Mock 無。
