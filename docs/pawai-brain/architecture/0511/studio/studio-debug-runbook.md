# Studio Debug Runbook — 現場症狀 → 檔案定位

**版本**：2026-05-11 freeze 快照

---

## 快速檢查清單（進 Studio 現場前）

```bash
# 1. Gateway health
curl http://localhost:8080/health
# 預期：{"status":"ok","node":true,"ws_clients":N,"subscriptions":[...10 topics...]}

# 2. WS 連線（從 browser console 看 isConnected）
# Studio 右上角 indicator 必須是綠色

# 3. ROS2 topics 是否在跑
ros2 topic list | grep -E "face|gesture|pose|speech|object|brain|tts|capability"

# 4. mock 模式確認
# http://localhost:8080/api/health  → 應有 stamp + modules
```

---

## 症狀 A：前端顯示 DISCONNECTED / 右上角指示燈紅色

**定位**：`pawai-studio/frontend/hooks/use-websocket.ts`

```
症狀：isConnected = false，WS 一直重試
步驟：
1. 看 browser console — "WebSocket connection failed to wss://..."
2. 確認 GATEWAY_HOST 設定正確（start-live.sh 或 .env.local）
3. 確認 Gateway 在跑：curl http://GATEWAY_HOST:8080/health
4. 確認 WS URL（use-websocket.ts L41）：NEXT_PUBLIC_WS_URL env → getGatewayWsUrl("/ws/events")
5. 如果是 ws://（不是 wss://）卻從 https:// 頁面連 → 混合內容 block
   修法：GATEWAY_HOST 用 http:// 或確保 tunnel 有 https
```

**3s 重連邏輯**（`use-websocket.ts` L80）：
```typescript
ws.onclose = () => {
  reconnectTimer.current = setTimeout(() => connectRef.current(), RECONNECT_DELAY_MS)  // 3000ms
}
```

---

## 症狀 B：面板 Panel 都不更新（WS 已連）

**定位**：事件分派 hook（`use-studio-events.ts`）+ stores

```
步驟：
1. 開 browser devtools → Network → WS frame
   → 確認有 event JSON 進來
2. 如果有 event 但 panel 不動：
   → 看 event.source 是否符合分派規則
   → 看 event.data 的欄位是否符合 FaceState / GestureState 等 interface
3. 如果 source=="gesture" 但 gestureState 沒更新：
   → 確認 Gateway 有加 current_gesture 補充（studio_gateway.py L309-315）
4. mock 模式：periodic_mock_push() 每 2s 推一次，確認 manager.active 有你的 WS
```

---

## 症狀 C：ChatPanel AI 泡泡不出現（「回應逾時」）

**定位**：TTS event 流程

```
路徑追蹤：
/tts topic → GatewayNode._on_tts_msg() → build_tts_event() → broadcast

定位步驟：
1. ROS2 端：ros2 topic echo /tts → 確認 executive/brain 有發 /tts
2. Gateway log：grep "_on_tts_msg" 或 "tts_speaking"
3. WS frame：確認有 {source:"tts",event_type:"tts_speaking"}
4. Frontend：看 state-store.lastTtsText 有沒有更新
   → 確認 appendTtsMessage() 沒被 rate-limit 吃掉（RATE_LIMIT_BYPASS 集合）
```

**mock 模式**：mock_server.py 的 `_emit_text_reply()` 手動廣播 tts_speaking（L511-526）。
如果 mock `/api/text_input` 有回 `ok:true` 但 ChatPanel 沒有 AI 泡泡，看這個函式是否跑完。

---

## 症狀 D：Brain Trace 沒進來 / Trace Drawer 空白

**定位**：`/brain/conversation_trace` topic → Gateway → frontend

```
步驟：
1. ros2 topic echo /brain/conversation_trace → 確認 Brain 有 publish
2. Gateway TOPIC_MAP 中 "/brain/conversation_trace" → "brain:conversation_trace"（studio_gateway.py L82）
3. WS frame：找 {source:"brain",event_type:"conversation_trace"}
4. state-store.conversationTraces（slice(0,50）) — 確認有 appendConversationTrace 被呼叫
5. Trace Drawer 元件讀 useStateStore.conversationTraces
```

**常見原因**：Brain 走 RuleBrain fallback 時只有 1 條 trace（"fallback" status），
正常 12-node 跑完會有多條 trace entry。

---

## 症狀 E：/api/text_input 發出後 Brain 沒反應

**定位**：Gateway publisher → ROS2

```
步驟：
1. curl -X POST http://GATEWAY_HOST:8080/api/text_input -H "Content-Type: application/json" -d '{"text":"你好"}'
   → 應回 {"ok":true,"request_id":"txt-...","text":"你好"}
2. Gateway log 確認 "Published text_input"
3. ros2 topic echo /brain/text_input → 確認有 JSON message
4. 如果沒有：
   → node is None 檢查：curl /health 看 "node": true
   → lifespan 確認（studio_gateway.py L423 GatewayNode 初始化）
```

**CORS 問題**（5/7 hotfix）：
Gateway 已設 `allow_origins=["*"]`（L444-449）。
若從非 localhost 發 POST 被 block，確認 Gateway 是走 `studio_gateway.py` 不是舊版。

---

## 症狀 F：Capability chip 永遠顯示「unknown」

**定位**：`/capability/nav_ready`、`/capability/depth_clear` Bool topics

```
步驟：
1. ros2 topic echo /capability/nav_ready → 確認有 Bool message
2. Gateway GatewayNode._on_capability_msg() 訂閱（studio_gateway.py L202-209）
3. curl http://GATEWAY_HOST:8080/api/capability → 看 tri-state snapshot
   → "unknown" = 從未收到 Bool（ROS2 topic 沒有 publisher）
4. mock 模式：_mock_capability 預設 {"nav_ready":"true","depth_clear":"true"}
   可用 POST /api/capability {"name":"nav_ready","state":"false"} 切換
```

---

## 症狀 G：start-live.sh --mock 沒有事件推入

**定位**：`mock_server.py` `periodic_mock_push()`

```
步驟：
1. 確認 mock_server 在跑：curl http://localhost:8080/api/health
2. WS 連線確認：看 browser devtools WS 是否連上 ws://localhost:8080/ws/events
3. periodic_mock_push() 每 2s 推一次，只有 manager.active 非空才推（mock_server.py L225-226）
4. 確認 browser WS 有被 accept（mock_server.py L320-321 ws_events handler）
```

---

## 症狀 H：Mock text_input 回 mock 但 ChatPanel 沒 AI 泡泡

```
原因：mock_server.py _emit_text_reply() 廣播 tts_speaking 前需等 proposal/result 廣播成功
定位：mock_server.py L511-526 — 確認 manager.active 非空才能 broadcast
修法：確認同時有 WS /ws/events 連線
```

---

## 症狀 I：Gesture / Pose Panel 更新但 GestureState.current_gesture 是 null

**定位**：Gateway field transform

Gateway `_on_ros2_msg()`（L309-315）補 `current_gesture`：
```python
if source == "gesture" and "gesture" in data:
    data.setdefault("current_gesture", data.get("gesture"))
```

如果 ROS2 `/event/gesture_detected` 的 payload 用 `"gesture"` 欄位（非 `"current_gesture"`），
Gateway 才會補。確認 `vision_perception` 的 publish 格式。

---

## 常用偵錯指令

```bash
# Gateway 啟動（Jetson）
source /opt/ros/humble/setup.zsh && source install/setup.zsh
python3 pawai-studio/gateway/studio_gateway.py

# 確認 Gateway WS 端點
wscat -c ws://localhost:8080/ws/events  # 需 npm install -g wscat

# 手動觸發 mock 場景
curl -X POST http://localhost:8080/mock/scenario/demo_a
curl -X POST http://localhost:8080/mock/scenario/self_introduce

# Mock capability 切換
curl -X POST http://localhost:8080/api/capability \
  -H "Content-Type: application/json" \
  -d '{"name":"nav_ready","state":"false"}'

# 確認 brain trace 進來
ros2 topic echo /brain/conversation_trace | head -20

# 確認所有 TOPIC_MAP 都有 publisher
for topic in /state/perception/face /event/gesture_detected /event/pose_detected \
  /event/speech_intent_recognized /event/object_detected /state/pawai_brain \
  /brain/proposal /brain/skill_result /brain/conversation_trace /tts; do
  echo "=== $topic ===" && ros2 topic info $topic | head -3
done
```
