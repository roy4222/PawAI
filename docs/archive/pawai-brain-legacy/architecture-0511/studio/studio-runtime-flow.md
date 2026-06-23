# Studio Runtime Flow — WebSocket 端點 + ROS2 ↔ Gateway 訊息流

**版本**：2026-05-11 freeze 快照
**真相來源**：`pawai-studio/gateway/studio_gateway.py`

---

## 1. 完整訊息流圖

```
Browser (Next.js 16)
    │
    ├─── WebSocket /ws/events ──────────────────────────────┐
    │       ↑ PawAIEvent JSON broadcast（所有感知 + Brain）  │
    │                                                        │
    ├─── WebSocket /ws/speech ─────────────────────────────┐│
    │       → 上傳 audio bytes                             ││
    │       ← ASR result JSON                              ││
    │                                                       ││
    ├─── WebSocket /ws/text ──────────────────────────────┐│││
    │       → 送文字                                      ││││
    │       ← intent + ASR echo                           ││││
    │                                                      │││
    ├─── POST /api/text_input ──────────────────────────┐  │││
    │       → {text, request_id}                        │  │││
    │       ← {ok, request_id, text}                    │  │││
    │                                                   │  │││
    └─── POST /api/skill_request ─────────────────────┐ │  │││
            → {skill, args, request_id}               │ │  │││
            ← {ok, request_id}                        │ │  │││
                                                      │ │  │││
=== Jetson Gateway (studio_gateway.py) ===============│=│==│││=====
                                                      │ │  │││
GatewayNode (rclpy.Node)                              │ │  │││
    │                                                 │ │  │││
    ├─ Publishers:                                    │ │  │││
    │   speech_pub  → /event/speech_intent_recognized ◄──  │││
    │   text_input_pub → /brain/text_input ───────────◄──  │││
    │   skill_request_pub → /brain/skill_request ─────◄────│││
    │   _reset_pub → /brain/reset_context                  │││
    │                                                       │││
    └─ Subscribers → broadcast via asyncio.run_coroutine_threadsafe()
        TOPIC_MAP (10 topics) → ws_manager.broadcast()  ───►│
        /tts → build_tts_event() → broadcast()          ───►│
        /capability/nav_ready → capability_snapshot()   ───►│
        /capability/depth_clear → capability_snapshot() ───►│
                                                            ││
=== ROS2 Topics =============================================││======
                                                            ││
  /state/perception/face         (face_perception pkg)  ────►
  /event/gesture_detected        (vision_perception)    ────►
  /event/pose_detected           (vision_perception)    ────►
  /event/speech_intent_recognized (speech_processor)   ─────►
  /event/object_detected         (object_perception)   ─────►
  /state/pawai_brain             (interaction_executive)─────►
  /brain/proposal                (interaction_executive)─────►
  /brain/skill_result            (interaction_executive)─────►
  /brain/conversation_trace      (pawai_brain)          ─────►
  /brain/conversation_trace_shadow (pawai_brain)        ─────►
  /tts                           (interaction_executive)─────►（/ws/events 中的 source="tts"）
  /capability/nav_ready          (nav2 stack)           ─────►（tri-state Bool）
  /capability/depth_clear        (reactive_stop)        ─────►（tri-state Bool）
```

---

## 2. WebSocket 端點詳述

### /ws/events（L599-607）— 主要廣播通道

```python
# studio_gateway.py L599
@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive / ping
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
```

- **方向**：Server → Browser（只廣播，不接指令）
- **payload**：PawAIEvent JSON（見 §4）
- **重連**：前端 3s 重連（`hooks/use-websocket.ts` L13）

### /ws/speech（L680-749）— 語音輸入

```python
# studio_gateway.py L680 — 完整 ASR 管線：audio_bytes → WAV resample → SenseVoice → intent
audio_bytes = await ws.receive_bytes()          # 1. 接收 audio bytes
wav16k = await asyncio.to_thread(resample_to_wav16k, audio_bytes)   # 2. 重採樣
asr_result = await asyncio.to_thread(transcribe, wav16k, ASR_URL)    # 3. ASR
text = to_traditional_tw(text)                  # 4. 簡→繁（ENABLE_S2TWP）
match = classifier.classify(text)               # 5. Intent 分類
node.publish_speech_event(payload)              # 6. 發布 ROS2
```

- **ASR_URL**：`PAWAI_ASR_URL`（env override，預設 `http://127.0.0.1:8001/v1/audio/transcriptions`）
- **payload cap**：5MB（L86: `MAX_AUDIO_BYTES = 5 * 1024 * 1024`）

### /ws/text（L631-675）— 文字輸入（舊 WS 路徑）

直接 Intent 分類後 publish，**不走 LLM**（LLM 走 `/api/text_input`）。
用於不需要 LLM 回覆的純 intent dispatch 場景。

### /ws/video/{source}（L611-627）— 影像流

- Binary JPEG frames（僅 Jetson 有 cv2 + cv_bridge 時啟用）
- source 必須在 `VIDEO_TOPIC_MAP` 內
- 無 cv2：`_VIDEO_AVAILABLE = False`，端點回 4003

---

## 3. 跨線程橋接模型

Gateway 有兩個線程：
1. **asyncio event loop**：FastAPI + WebSocket handlers
2. **rclpy.spin() daemon thread**：ROS2 callback 執行

ROS2 callback 廣播到 WS 必須用（`studio_gateway.py` L266, L337, L351）：
```python
asyncio.run_coroutine_threadsafe(ws_manager.broadcast(envelope), self._loop)
```

`self._loop` 在 `GatewayNode.__init__(loop)` 時從 `asyncio.get_running_loop()` 傳入（L161-163）。

---

## 4. PawAIEvent 信封

每個廣播訊息都是此格式（`studio_gateway.py` L329-336，`contracts/types.ts` L12-18）：

```json
{
  "id": "uuid4",
  "timestamp": "2026-05-11T14:30:00+08:00",
  "source": "gesture",
  "event_type": "gesture_detected",
  "data": {
    "gesture": "wave",
    "current_gesture": "wave",
    "active": true,
    "status": "active",
    "confidence": 0.88,
    "hand": "right"
  }
}
```

**Field transforms**（`_on_ros2_msg()` L309-326）：
- `source == "gesture"`：補 `current_gesture` + `active=true` + `status="active"`
- `source == "pose"`：補 `current_pose` + `active=true` + `status="active"`
- `source == "speech"`：補 `phase="listening"`

**TTS 路徑**（`_on_tts_msg()` L341-353）：
`/tts` → `_parse_tts_payload()` → `build_tts_event()` → broadcast
TTS event 的 `source="tts"`, `event_type="tts_speaking"`，包含 `origin`（`"tts"` / `"studio_text"` / …）

---

## 5. Capability Tri-State 流（L255-276）

```
/capability/nav_ready (Bool) → _on_capability_msg("nav_ready", msg)
    → self._cap_state["nav_ready"] = value
    → broadcast {"source":"capability","event_type":"capability_nav_ready","data":{"tri_state":"true|false"}}

/capability/depth_clear (Bool) → 同上
```

`GET /api/capability` 回傳快照，未收到 Bool 時 `tri_state = "unknown"`。

---

## 6. s2twp 簡→繁正規化

```python
# studio_gateway.py L63
ENABLE_S2TWP = os.getenv("PAWAI_ENABLE_S2TWP", "true").lower() == "true"
```

三個路徑都有：`/ws/speech`（L704）、`/ws/text`（L643）、`/api/text_input`（L572）。
關閉：`PAWAI_ENABLE_S2TWP=false`。

---

## 7. Mock Server 對應端點

Mock（`mock_server.py`）實作相同端點介面，但用 `periodic_mock_push()`（L222-232）每 2 秒隨機推一個 `MOCK_GENERATORS` 事件：
```python
MOCK_GENERATORS = {
    "face": mock_face_event,
    "speech": mock_speech_event,
    "gesture": mock_gesture_event,
    "pose": mock_pose_event,
    "object": mock_object_event,
}
```

差異：Mock 無 ROS2、無 cv_bridge、`/ws/speech` 回 canned ASR（`MOCK_ASR_RESPONSES` L331-337）。
