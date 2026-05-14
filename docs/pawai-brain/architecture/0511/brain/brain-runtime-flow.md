# PawAI Brain Runtime Flow

**目的**：明天到學校 debug 時，快速知道 PawAI Brain 收哪些 topic、存哪些快取、跑哪條 graph、最後 publish 到哪裡。

**權威程式**：
- `pawai_brain/pawai_brain/conversation_graph_node.py`
- `pawai_brain/pawai_brain/graph.py`
- `pawai_brain/pawai_brain/schemas.py`

---

## 1. Runtime 總架構

```text
ASR / speech_processor
  /event/speech_intent_recognized
        |
        |  JSON: text, intent, confidence, session_id
        v
Studio Gateway / Chat Panel
  /brain/text_input
        |
        |  JSON: text, request_id, source="studio_text"
        v
┌──────────────────────────────────────────────────────────────┐
│ conversation_graph_node                                      │
│ pawai_brain/pawai_brain/conversation_graph_node.py           │
│                                                              │
│  _on_speech_event() / _on_text_input()                       │
│        |                                                     │
│        v                                                     │
│  ThreadPoolExecutor(max_workers=2)                           │
│        |                                                     │
│        v                                                     │
│  _process_one()                                              │
│        |                                                     │
│        v                                                     │
│  self._graph.invoke(initial_state)                           │
│        |                                                     │
│        v                                                     │
│  LangGraph build_graph()                                     │
│  input -> mode_classifier -> safety_gate                     │
│    -> world_state -> capability -> memory -> llm             │
│    -> validator -> repair -> skill_gate -> output -> trace   │
│                                                              │
│        +--> /brain/chat_candidate                            │
│        +--> /brain/conversation_trace                        │
└──────────────────────────────────────────────────────────────┘
        |
        v
interaction_executive / brain_node
  reads /brain/chat_candidate
  decides SAY / MOTION / NAV / confirm / reject
```

Brain 是「建議者」，不是動作唯一出口。`/brain/chat_candidate` 裡的 `proposed_skill` 還要經過 `interaction_executive` 才會變成 TTS 或 Go2 動作。

---

## 2. 旁路狀態資料流

Brain 每一輪 LLM prompt 不是只靠使用者文字，還會從多個 topic 快取 world state。

```text
/state/tts_playing
/state/reactive_stop/status
/state/nav/safety
/state/pawai_brain
/event/object_detected
        |
        v
WorldStateSnapshot
pawai_brain/pawai_brain/capability/world_snapshot.py
        |
        v
world_state_builder()
pawai_brain/pawai_brain/nodes/world_state_builder.py

/state/perception/face
        |
        v
_recent_face_identity = (name, ts)
        |
        v
current_speaker, stale after 3s

/event/pose_detected
        |
        v
_recent_pose = (pose, ts)
        |
        v
current_pose, stale after 10s

/event/gesture_detected
        |
        v
_recent_gesture = (gesture, ts)
        |
        v
current_gesture, stale after 5s

/brain/skill_result
        |
        v
SkillResultMemory(maxlen=5)
        |
        v
capability_builder()

/brain/demo_segment
        |
        v
demo_session cache
        |
        v
capability_builder() + prompt [demo]
```

---

## 3. Subscribers

| Topic | Callback | 資料用途 | 注意 |
|------|----------|----------|------|
| `/event/speech_intent_recognized` | `_on_speech_event()` | 語音主入口 | 用 `session_id` 去重；`intent=hallucination` 直接丟掉 |
| `/brain/text_input` | `_on_text_input()` | Studio 文字輸入 | 設 `input_origin="studio_text"`，讓下游 TTS 走 quality lane envelope |
| `/state/tts_playing` | `_on_tts_playing()` | capability gate、避免 SAY skill 插話 | QoS 必須和 TTS node 一致：TRANSIENT_LOCAL + RELIABLE |
| `/state/reactive_stop/status` | `_on_reactive_stop()` | obstacle flag | 影響 motion skill `blocked` |
| `/state/nav/safety` | `_on_nav_safety()` | nav_safe flag | 影響 nav skill `blocked` |
| `/state/pawai_brain` | `_on_pawai_brain_state()` | active_skill / step | QoS TRANSIENT_LOCAL |
| `/brain/skill_result` | `_on_skill_result()` | 最近 skill 結果 | 只記 terminal status |
| `/event/object_detected` | `_on_object_detected()` | recent_objects cache | 只保留 class/color/ts，沒有 bbox/confidence |
| `/brain/demo_segment` | `_on_demo_segment()` | demo 進度提示 | lock 保護，provider 回 defensive copy |
| `/event/gesture_detected` | `_on_gesture_detected()` | 最近手勢 | 只存 name + timestamp |
| `/event/pose_detected` | `_on_pose_detected()` | 最近姿勢 | 只存 name + timestamp，這是目前 pose grounding 弱點 |
| `/brain/reset_context` | `_on_reset_context()` | 清 session | 清 memory、seen_sessions、face/gesture/pose/demo cache |
| `/state/perception/face` | `_on_face_state()` | current_speaker | 只取第一個 `stable_name != unknown` |

---

## 4. Publishers

| Topic | Publisher | Schema | 下游 |
|------|-----------|--------|------|
| `/brain/chat_candidate` | `_publish_chat_candidate_from_state()` | `ChatCandidatePayload` | `interaction_executive` |
| `/brain/conversation_trace` | `_publish_traces()` / `_publish_error_trace()` | `TracePayload` | Studio / debug |

`ChatCandidatePayload` 在 `pawai_brain/pawai_brain/schemas.py`：

```json
{
  "session_id": "speech-...",
  "reply_text": "[playful] 好啊，比 OK 我就搖",
  "intent": "chat",
  "selected_skill": null,
  "confidence": 0.8,
  "proposed_skill": "wiggle",
  "proposed_args": {},
  "proposal_reason": "openrouter:eval_schema",
  "engine": "langgraph",
  "input_origin": null
}
```

`proposed_skill` 只是提案。`selected_skill` 是 legacy 欄位，目前只保留少數 P0 診斷用途。

---

## 5. Single-Flight 行為

`_process_one()` 進 graph 前會拿 `self._lock.acquire(blocking=False)`。

```text
第一個 turn 正在跑 graph / LLM
第二個 turn 進來
  -> log: graph invocation already in progress — dropping turn
  -> 第二個 turn 被丟掉
```

這是 demo 穩定性取向：避免多輪 LLM 同時跑造成 TTS/skill 亂序。現場如果覺得「講話沒反應」，要看 log 是否出現這行。

---

## 6. Reset Context 的真實效果

`/brain/reset_context` 會清：
- `ConversationMemory`
- `_seen_sessions`
- `_recent_face_identity`
- `_recent_gesture`
- `_recent_pose`
- `_demo_session_state`

另外會設 `_speaker_suppress_until = now + 5s`。原因：使用者按新對話後，即使 Roy 還站在鏡頭前，也不要立刻把 `[眼前的人] Roy` 注回 prompt，避免新對話不像新對話。

不會清：
- OpenRouter client
- persona
- capability registry
- world snapshot 裡的 tts/nav/reactive state

---

## 7. 檔案位置速查

| 想查什麼 | 檔案 |
|----------|------|
| ROS2 wrapper / topic / callback | `pawai_brain/pawai_brain/conversation_graph_node.py` |
| LangGraph topology | `pawai_brain/pawai_brain/graph.py` |
| chat_candidate / trace schema | `pawai_brain/pawai_brain/schemas.py` |
| Graph state schema | `pawai_brain/pawai_brain/state.py` |
| world snapshot cache | `pawai_brain/pawai_brain/capability/world_snapshot.py` |
| skill result cache | `pawai_brain/pawai_brain/capability/skill_result_memory.py` |
| OpenRouter client | `pawai_brain/pawai_brain/llm_client.py` |

