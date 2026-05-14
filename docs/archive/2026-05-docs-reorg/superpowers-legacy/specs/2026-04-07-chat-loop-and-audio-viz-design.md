# PawAI Studio Chat 閉環 + 錄音動畫 — Design Spec

**日期**：2026-04-07
**作者**：Roy + Claude
**狀態**：Draft
**前置**：Live View 實機通過、vLLM Qwen2.5-7B 已上線

---

## 1. 定位

讓 Studio 的聊天功能真正接上機器狗：文字和語音都走 ROS2 → LLM Bridge → TTS pipeline，不建第二條大腦路徑。錄音時顯示音量動畫，讓使用者看得出「有在收音」。

**不做**：Gateway 直連 LLM (`/api/chat`)、多輪 session memory、chat history 持久化、複雜語音串流。

---

## 2. 完整資料流

```
Studio ChatPanel
  │
  ├─ 文字輸入 ──→ WS /ws/text ──→ Gateway publish ──→ /event/speech_intent_recognized
  │                                                           │
  ├─ 語音輸入 ──→ WS /ws/speech ──→ Gateway ASR+classify ──→ /event/speech_intent_recognized
  │                                                           │
  │                                                    llm_bridge_node
  │                                                           │
  │                                              Qwen2.5-7B (cloud vLLM)
  │                                                           │
  │                                                         /tts
  │                                                        ╱    ╲
  │                                              tts_node播放  Gateway 訂閱
  │                                              (USB喇叭)      │
  │                                                       /ws/events 廣播
  │                                                     { source: "tts",
  │                                                       event_type: "tts_speaking",
  │                                                       data: { text, phase, origin } }
  │                                                           │
  └─ ChatPanel 收到 event ─────────────────────────────────────┘
     pendingReply === true → 顯示 AI bubble
     pendingReply === false → 只更新 event ticker / speech panel
```

---

## 3. Gateway — 訂閱 `/tts`

### 3.1 新增訂閱

在 `GatewayNode.__init__` 中新增：

```python
# /tts — plain text, published by llm_bridge_node and interaction_executive_node
self.create_subscription(String, "/tts", self._on_tts_msg, QOS_EVENT)
```

### 3.2 Event 格式

`/tts` 是 `std_msgs/String`，payload 是純中文字（不是 JSON）。Gateway 包成：

```json
{
  "id": "uuid",
  "timestamp": "ISO8601",
  "source": "tts",
  "event_type": "tts_speaking",
  "data": {
    "text": "roy，你好！",
    "phase": "speaking",
    "origin": "unknown"
  }
}
```

- `source` 固定 `"tts"`，**不是** `"speech"`。避免 ChatPanel 把 face greeting、object TTS 誤當聊天回覆。
- `origin` 設為 `"unknown"`，因為 `/tts` topic 的 String msg 不帶 publisher 資訊。未來若需要區分可在 llm_bridge 端加 JSON wrapper，但現在不做。

### 3.3 不加節流

`/tts` 頻率很低（只有實際 TTS 時才發），不需要 throttle。

---

## 4. ChatPanel — 走 `/ws/text` + 等 TTS 回覆

### 4.1 移除 `POST /api/chat`

現有 `handleSend()` 的 `fetch(/api/chat)` 移除，改為透過 `/ws/text` 送出。

### 4.2 新增 pending 機制

```typescript
const pendingRequestIdRef = useRef<string | null>(null)
const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
```

**送出文字時**：
1. 產生 `requestId = uuid()`
2. `pendingRequestIdRef.current = requestId`
3. 顯示 user bubble + thinking dots
4. 透過現有 `/ws/text` WebSocket 送出文字（已實作）
5. 啟動 8 秒 timeout timer

**收到 `tts_speaking` event 時**（在 `useEventStream` 或 ChatPanel 內）：
1. 如果 `pendingRequestIdRef.current !== null`：
   - 顯示 AI bubble（`data.text`）
   - `pendingRequestIdRef.current = null`
   - clear timeout
   - 停止 thinking dots
2. 如果 `pendingRequestIdRef.current === null`：
   - 不顯示 AI bubble
   - 只更新 event ticker / speech panel

**Timeout 觸發時**：
1. 如果 `pendingRequestIdRef.current` 仍等於當初的 `requestId`（未被取消）：
   - 顯示 timeout 訊息（「回應逾時，請確認 LLM 是否在線」）
   - `pendingRequestIdRef.current = null`
   - 停止 thinking dots

**連續送出保護**：每次新送出時 clear 上一個 timeout + 覆蓋 `pendingRequestIdRef`，避免舊 timeout 干擾。

### 4.3 `useTextCommand` Hook

新建 `useTextCommand` hook 管理 `/ws/text` WebSocket 連線：

```typescript
interface UseTextCommandResult {
  sendText: (text: string) => void;
  isConnected: boolean;
  lastConfirm: { intent: string; published: boolean } | null;
}
```

- 持久 WebSocket 連到 `/ws/text`，自動重連
- `sendText()` 送出文字，server 回傳 `{ asr, intent, confidence, published }` 確認
- ChatPanel 呼叫 `sendText()` 後進入 pending 狀態，等 `tts_speaking` event

ChatPanel **不再** `fetch(/api/chat)`，也不自己建 WebSocket。

### 4.4 ChatPanel 收 TTS event 的機制

`useEventStream` 在收到 `source: "tts"` 時，更新 `state-store` 的 `lastTtsText` + `lastTtsAt`（不塞進 `speechState`，避免 face/object TTS 污染 speech panel）。

ChatPanel 用 `useEffect` 監聽 `lastTtsAt` 變化：
- `pendingRequestIdRef.current !== null` → 顯示 AI bubble → clear pending
- `pendingRequestIdRef.current === null` → 忽略（只更新 event ticker）

### 4.5 語音輸入同理

`useAudioRecorder` 已經走 `/ws/speech`，收到 ASR 結果後顯示 voice bubble。接著同樣進入 pending 狀態等 `tts_speaking`。

### 4.6 已知限制

`/tts` 沒有 request correlation id。pending 期間如果 face/object 也發 TTS，可能被 ChatPanel 誤當成回覆。短期靠 demo discipline（不在聊天時觸發其他 TTS），長期需在 `llm_bridge` 端加 structured event 或 correlation id。

---

## 5. Event 處理 — `useEventStream` + `state-store` 擴展

### 5.1 `state-store` 新增 TTS 欄位

```typescript
interface StateStore {
  // ... existing fields ...
  lastTtsText: string | null;
  lastTtsAt: number | null;  // Date.now() timestamp
  updateTts: (text: string) => void;
}
```

獨立於 `speechState`，避免 face/object TTS 污染 speech panel。

### 5.2 `useEventStream` 新增 `"tts"` case

```typescript
case "tts":
  if ("text" in data) {
    updateTts(data.text as string);
  }
  break;
```

`updateTts` 同時設 `lastTtsText` 和 `lastTtsAt = Date.now()`。ChatPanel 用 `useEffect` 監聽 `lastTtsAt` 變化判斷 pending。

---

## 6. 錄音音量動畫

### 6.1 `useAudioRecorder` 擴展

新增 `audioLevels: number[]`（7 個值，0-1 範圍），由 hook 內部計算：

```typescript
interface UseAudioRecorderResult {
  isRecording: boolean;
  isProcessing: boolean;
  audioLevels: number[];  // 新增：7 bins, 0.0-1.0
  lastResult: AsrResult | null;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}
```

**內部實作**：
```
startRecording():
  stream = getUserMedia({ audio: true })
  audioCtx = new AudioContext()
  source = audioCtx.createMediaStreamSource(stream)
  analyser = audioCtx.createAnalyser()
  analyser.fftSize = 256
  source.connect(analyser)

  requestAnimationFrame loop:
    getByteFrequencyData(dataArray)
    取前 7 bin → 除以 255 → setAudioLevels([...])

stopRecording():
  cancel animationFrame
  audioCtx.close()
  setAudioLevels([])  // 清零
```

**Fallback**：如果 `AudioContext` 不可用 → `audioLevels` 永遠是空陣列 `[]`，UI 退回 pulse animation。

### 6.2 `AudioVisualizer` 元件

```typescript
interface AudioVisualizerProps {
  levels: number[];  // 0.0-1.0, 通常 7 個
  isActive: boolean;
}
```

**渲染**：
- 7 條垂直 bars，水平排列，間距 2px
- 每條寬度 3px，高度 = `4px + level * 20px`（4px-24px）
- 顏色：紅色（`bg-red-400`），延續現有錄音紅色主題
- `transition-all duration-75` 讓跳動流暢
- 圓角 `rounded-full`

**位置**：取代現有 Mic 按鈕的 icon。錄音時 Mic 按鈕從 `w-8` 擴展到 `w-24`（pill shape），內含 AudioVisualizer + Stop icon。

**Fallback**（`levels.length === 0`）：顯示現有的 `animate-pulse` 紅色 Mic icon。

---

## 7. 硬限制

| 項目 | 值 |
|------|---|
| TTS 回覆 timeout | 8 秒 |
| `/tts` event source | 固定 `"tts"`，不是 `"speech"` |
| audioLevels bins | 7 個，0.0-1.0 |
| AnalyserNode fftSize | 256 |
| 不做 Gateway 直連 LLM | — |
| 不做多輪 memory | — |

---

## 8. 檔案變動

| 動作 | 路徑 | 改什麼 |
|------|------|--------|
| Modify | `pawai-studio/gateway/studio_gateway.py` | 訂閱 `/tts` → 包成 `source: "tts"` event 廣播 |
| Modify | `pawai-studio/gateway/test_gateway.py` | 補 TTS transform 測試 |
| Modify | `pawai-studio/frontend/components/chat/chat-panel.tsx` | 移除 `/api/chat`，改用 `useTextCommand` + pending + tts event → AI bubble |
| Create | `pawai-studio/frontend/components/chat/audio-visualizer.tsx` | 錄音音量 bars 元件 |
| Create | `pawai-studio/frontend/hooks/use-text-command.ts` | `/ws/text` WebSocket 持久連線 hook |
| Modify | `pawai-studio/frontend/hooks/use-audio-recorder.ts` | 新增 `audioLevels` + AudioContext + AnalyserNode |
| Modify | `pawai-studio/frontend/hooks/use-event-stream.ts` | 新增 `"tts"` case → `updateTts` |
| Modify | `pawai-studio/frontend/stores/state-store.ts` | 新增 `lastTtsText` / `lastTtsAt` / `updateTts` |

---

## 9. 實作順序

| Step | 內容 |
|:----:|------|
| 1 | Gateway 訂閱 `/tts` + test |
| 2 | `useEventStream` 加 `"tts"` case |
| 3 | ChatPanel 改走 `/ws/text` + pending 機制 |
| 4 | `useAudioRecorder` 加 `audioLevels` |
| 5 | `AudioVisualizer` 元件 |
| 6 | ChatPanel 整合 AudioVisualizer |
| 7 | 實機 E2E 驗證 |

---

## 10. 風險與 Fallback

| 風險 | 影響 | Fallback |
|------|------|---------|
| LLM 不回覆（timeout） | 使用者等 8s 看到 timeout | 訊息提示「請確認 LLM 是否在線」 |
| `/tts` 收到非聊天回覆（face greeting 等） | 可能誤顯示 AI bubble | `pendingRequestIdRef` 保護：只有 pending 時才當回覆 |
| AudioContext 被瀏覽器 block | 拿不到音量 | `audioLevels = []` → fallback pulse animation |
| 連續快速送出 | timeout 互相干擾 | `pendingRequestIdRef` 每次覆蓋 + clear 舊 timeout |
| `/ws/text` WebSocket 斷線 | 送不出去 | 顯示錯誤，走現有重連邏輯 |
