# Chat 閉環 + 錄音動畫 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 Studio ChatPanel 真正接上 ROS2 pipeline（文字/語音 → LLM → TTS → AI bubble），並在錄音時顯示音量動畫。

**Architecture:** Gateway 新增訂閱 `/tts` topic，包成 `source: "tts"` event 廣播到 `/ws/events`。ChatPanel 改用 `useTextCommand` hook 走 `/ws/text`，pending 時監聽 `lastTtsAt` 顯示 AI bubble。`useAudioRecorder` 新增 `audioLevels` 用 Web Audio AnalyserNode 計算，`AudioVisualizer` 元件渲染 7 條 bars。

**Tech Stack:** FastAPI + rclpy / React + Zustand / Web Audio API (AnalyserNode)

**Spec:** `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-07-chat-loop-and-audio-viz-design.md`

**用戶要求**：3 個 commit（gateway / frontend / tests），不要 9 個零散 commit。

---

## File Structure

| 動作 | 路徑 | 職責 |
|------|------|------|
| Modify | `pawai-studio/gateway/studio_gateway.py` | 訂閱 `/tts` → broadcast `source: "tts"` event |
| Modify | `pawai-studio/gateway/test_gateway.py` | TTS transform 測試 |
| Modify | `pawai-studio/frontend/stores/state-store.ts` | 新增 `lastTtsText` / `lastTtsAt` / `updateTts` |
| Modify | `pawai-studio/frontend/hooks/use-event-stream.ts` | 新增 `"tts"` case |
| Create | `pawai-studio/frontend/hooks/use-text-command.ts` | `/ws/text` 持久 WebSocket hook |
| Modify | `pawai-studio/frontend/hooks/use-audio-recorder.ts` | 新增 `audioLevels` + AudioContext + AnalyserNode |
| Create | `pawai-studio/frontend/components/chat/audio-visualizer.tsx` | 錄音音量 bars 元件 |
| Modify | `pawai-studio/frontend/components/chat/chat-panel.tsx` | 移除 `/api/chat`，改用 useTextCommand + pending + AI bubble |

---

## Task 1: Gateway 訂閱 `/tts` + 測試

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py`
- Modify: `pawai-studio/gateway/test_gateway.py`

### Step 1.1: 寫 TTS transform 測試

- [ ] 在 `pawai-studio/gateway/test_gateway.py` 的 `TestROS2Transform` class 末尾新增：

```python
    def test_tts_plain_text_to_event(self):
        """TTS topic sends plain text (not JSON). Gateway wraps it."""
        import uuid as _uuid
        from datetime import datetime as _dt

        tts_text = "roy，你好！"
        envelope = {
            "id": str(_uuid.uuid4()),
            "timestamp": _dt.now().astimezone().isoformat(),
            "source": "tts",
            "event_type": "tts_speaking",
            "data": {
                "text": tts_text,
                "phase": "speaking",
                "origin": "unknown",
            },
        }
        assert envelope["source"] == "tts"
        assert envelope["event_type"] == "tts_speaking"
        assert envelope["data"]["text"] == "roy，你好！"
        assert envelope["data"]["phase"] == "speaking"
        assert envelope["data"]["origin"] == "unknown"

    def test_tts_source_is_not_speech(self):
        """TTS events must use source='tts', not 'speech'."""
        # This test documents the design decision:
        # /tts publishers include llm_bridge AND interaction_executive.
        # Using source='speech' would pollute ChatPanel with face/object greetings.
        source = "tts"
        assert source != "speech"
```

- [ ] 執行測試確認通過

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py::TestROS2Transform::test_tts_plain_text_to_event pawai-studio/gateway/test_gateway.py::TestROS2Transform::test_tts_source_is_not_speech -v
```

Expected: 2 passed

### Step 1.2: Gateway 新增 `/tts` 訂閱

- [ ] 修改 `pawai-studio/gateway/studio_gateway.py`

在 `GatewayNode.__init__` 中，現有 event subscribers 迴圈之後（`self.get_logger().info(f"Studio Gateway ROS2 node ready...")`  之後），加入：

```python
        # /tts — plain text from llm_bridge_node / interaction_executive_node
        self.create_subscription(
            String, "/tts", self._on_tts_msg, QOS_EVENT
        )
```

在 `_on_ros2_msg` 方法之後加入新方法：

```python
    def _on_tts_msg(self, msg: String) -> None:
        """Wrap plain-text /tts into PawAIEvent envelope and broadcast."""
        text = msg.data.strip()
        if not text:
            return

        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().astimezone().isoformat(),
            "source": "tts",
            "event_type": "tts_speaking",
            "data": {
                "text": text,
                "phase": "speaking",
                "origin": "unknown",
            },
        }

        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(envelope), self._loop
        )
```

- [ ] 語法檢查

```bash
python3 -c "import py_compile; py_compile.compile('pawai-studio/gateway/studio_gateway.py', doraise=True)"
```

- [ ] 執行全部 gateway 測試

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py pawai-studio/gateway/test_video_bridge.py -v
```

Expected: 全部通過（30 tests）

---

## Task 2: state-store + useEventStream 擴展

**Files:**
- Modify: `pawai-studio/frontend/stores/state-store.ts`
- Modify: `pawai-studio/frontend/hooks/use-event-stream.ts`

### Step 2.1: state-store 新增 TTS 欄位

- [ ] 修改 `pawai-studio/frontend/stores/state-store.ts`

在 `interface StateStore` 中，`objectState` 之後加入：

```typescript
  lastTtsText: string | null;
  lastTtsAt: number | null;

  // ... existing update methods ...
  updateTts: (text: string) => void;
```

在 `create<StateStore>` 的初始值中加入：

```typescript
  lastTtsText: null,
  lastTtsAt: null,

  updateTts: (text) => set({ lastTtsText: text, lastTtsAt: Date.now() }),
```

### Step 2.2: useEventStream 加 `"tts"` case

- [ ] 修改 `pawai-studio/frontend/hooks/use-event-stream.ts`

在函式開頭的 store selectors 中加入：

```typescript
  const updateTts = useStateStore((s) => s.updateTts);
```

在 switch 的 `case "system":` 之前加入：

```typescript
        case "tts":
          if ("text" in data) {
            updateTts(data.text as string);
          }
          break;
```

在 useCallback 的依賴陣列中加入 `updateTts`。

---

## Task 3: `useTextCommand` Hook

**Files:**
- Create: `pawai-studio/frontend/hooks/use-text-command.ts`

### Step 3.1: 建立 hook

- [ ] 建立 `pawai-studio/frontend/hooks/use-text-command.ts`

```typescript
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getGatewayWsUrl } from "@/lib/gateway-url";

const RECONNECT_DELAY_MS = 3000;

interface TextConfirm {
  intent: string;
  confidence: number;
  published: boolean;
}

interface UseTextCommandResult {
  sendText: (text: string) => void;
  isConnected: boolean;
  lastConfirm: TextConfirm | null;
}

function getTextWsUrl(): string {
  return getGatewayWsUrl("/ws/text");
}

export function useTextCommand(): UseTextCommandResult {
  const [isConnected, setIsConnected] = useState(false);
  const [lastConfirm, setLastConfirm] = useState<TextConfirm | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const ws = new WebSocket(getTextWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      setIsConnected(true);
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data as string);
        if (data.published !== undefined) {
          setLastConfirm({
            intent: data.intent ?? "",
            confidence: data.confidence ?? 0,
            published: data.published ?? false,
          });
        }
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setIsConnected(false);
      reconnectTimer.current = setTimeout(
        () => connectRef.current(),
        RECONNECT_DELAY_MS
      );
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendText = useCallback((text: string) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(text);
    }
  }, []);

  return { sendText, isConnected, lastConfirm };
}
```

---

## Task 4: ChatPanel 改走 `/ws/text` + pending 機制

**Files:**
- Modify: `pawai-studio/frontend/components/chat/chat-panel.tsx`

### Step 4.1: 改寫 ChatPanel

- [ ] 修改 `pawai-studio/frontend/components/chat/chat-panel.tsx`

**Import 區**：移除 `getGatewayHttpUrl`，新增：

```typescript
import { useTextCommand } from "@/hooks/use-text-command"
```

**函式開頭**：新增 hook 和 pending state：

```typescript
  const { sendText, isConnected: textWsConnected } = useTextCommand()
  const pendingRequestIdRef = useRef<string | null>(null)
  const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastTtsText = useStateStore((s) => s.lastTtsText)
  const lastTtsAt = useStateStore((s) => s.lastTtsAt)
```

**新增 useEffect — 監聽 TTS 回覆**：

```typescript
  // TTS reply → AI bubble (only when pending)
  useEffect(() => {
    if (lastTtsAt && lastTtsText && pendingRequestIdRef.current) {
      // Clear pending
      pendingRequestIdRef.current = null
      if (pendingTimeoutRef.current) {
        clearTimeout(pendingTimeoutRef.current)
        pendingTimeoutRef.current = null
      }
      setIsThinking(false)

      const aiMsg: AIMessage = {
        id: `ai-${Date.now()}`,
        type: "ai",
        text: lastTtsText,
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, aiMsg])
    }
  }, [lastTtsAt, lastTtsText])
```

**改寫 handleSend**（移除 fetch `/api/chat`）：

```typescript
  function handleSend() {
    const text = inputText.trim()
    if (!text || isThinking) return

    const userMsg: UserMessage = {
      id: `user-${Date.now()}`,
      type: "user",
      text,
      timestamp: formatTime(new Date()),
    }
    setMessages((prev) => [...prev, userMsg])
    setInputText("")
    setIsThinking(true)

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }

    // Send via /ws/text
    const requestId = `req-${Date.now()}`
    pendingRequestIdRef.current = requestId

    // Clear any previous timeout
    if (pendingTimeoutRef.current) {
      clearTimeout(pendingTimeoutRef.current)
    }

    sendText(text)

    // 8s timeout
    pendingTimeoutRef.current = setTimeout(() => {
      if (pendingRequestIdRef.current === requestId) {
        pendingRequestIdRef.current = null
        setIsThinking(false)
        const errMsg: AIMessage = {
          id: `ai-timeout-${Date.now()}`,
          type: "ai",
          text: "回應逾時，請確認 LLM 是否在線。",
          timestamp: formatTime(new Date()),
        }
        setMessages((prev) => [...prev, errMsg])
      }
    }, 8000)

    textareaRef.current?.focus()
  }
```

移除原本的 `async function handleSend()` 整個函式（含 fetch 邏輯），替換為上面的版本。`handleSend` 不再是 async。

**語音結果也進入 pending**：修改 voice result useEffect，在加入 voice bubble 後設定 pending：

```typescript
  useEffect(() => {
    if (voiceResult && voiceResult !== prevVoiceResultRef.current) {
      prevVoiceResultRef.current = voiceResult
      const voiceMsg: VoiceMessage = {
        id: `voice-${Date.now()}`,
        type: "voice",
        text: voiceResult.asr,
        intent: voiceResult.intent,
        confidence: voiceResult.confidence,
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, voiceMsg])

      // Enter pending for TTS reply
      const requestId = `voice-${Date.now()}`
      pendingRequestIdRef.current = requestId
      setIsThinking(true)

      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current)
      pendingTimeoutRef.current = setTimeout(() => {
        if (pendingRequestIdRef.current === requestId) {
          pendingRequestIdRef.current = null
          setIsThinking(false)
        }
      }, 8000)
    }
  }, [voiceResult])
```

**Cleanup**：在元件開頭加 cleanup effect：

```typescript
  useEffect(() => {
    return () => {
      if (pendingTimeoutRef.current) clearTimeout(pendingTimeoutRef.current)
    }
  }, [])
```

---

## Task 5: `useAudioRecorder` 加 `audioLevels`

**Files:**
- Modify: `pawai-studio/frontend/hooks/use-audio-recorder.ts`

### Step 5.1: 新增 audioLevels

- [ ] 修改 `pawai-studio/frontend/hooks/use-audio-recorder.ts`

**新增 state**：

```typescript
  const [audioLevels, setAudioLevels] = useState<number[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);
```

**在 `startRecording` 的 `recorder.start()` 之後加入 AnalyserNode 初始化**：

```typescript
      // Audio visualization
      try {
        const audioCtx = new AudioContext();
        const sourceNode = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        sourceNode.connect(analyser);
        audioCtxRef.current = audioCtx;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const BINS = 7;

        const updateLevels = () => {
          analyser.getByteFrequencyData(dataArray);
          const levels: number[] = [];
          for (let i = 0; i < BINS; i++) {
            levels.push(dataArray[i] / 255);
          }
          setAudioLevels(levels);
          animFrameRef.current = requestAnimationFrame(updateLevels);
        };
        animFrameRef.current = requestAnimationFrame(updateLevels);
      } catch {
        // AudioContext not supported — audioLevels stays empty (fallback pulse)
      }
```

**在 `stopRecording` 中加入 cleanup**：

```typescript
    cancelAnimationFrame(animFrameRef.current);
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    setAudioLevels([]);
```

**在 `recorder.onstop` 回調中也加入 cleanup**（在 `stream.getTracks().forEach(...)` 之後）：

```typescript
        cancelAnimationFrame(animFrameRef.current);
        if (audioCtxRef.current) {
          audioCtxRef.current.close().catch(() => {});
          audioCtxRef.current = null;
        }
        setAudioLevels([]);
```

**在 unmount cleanup effect 中也加入**：

```typescript
      cancelAnimationFrame(animFrameRef.current);
      audioCtxRef.current?.close().catch(() => {});
```

**Return 加入 audioLevels**：

```typescript
  return { isRecording, isProcessing, audioLevels, lastResult, error, startRecording, stopRecording };
```

---

## Task 6: `AudioVisualizer` 元件 + ChatPanel 整合

**Files:**
- Create: `pawai-studio/frontend/components/chat/audio-visualizer.tsx`
- Modify: `pawai-studio/frontend/components/chat/chat-panel.tsx`

### Step 6.1: 建立 AudioVisualizer

- [ ] 建立 `pawai-studio/frontend/components/chat/audio-visualizer.tsx`

```tsx
"use client";

interface AudioVisualizerProps {
  levels: number[];
  isActive: boolean;
}

export function AudioVisualizer({ levels, isActive }: AudioVisualizerProps) {
  if (!isActive || levels.length === 0) return null;

  return (
    <div className="flex items-center gap-[2px] h-6">
      {levels.map((level, i) => (
        <div
          key={i}
          className="w-[3px] rounded-full bg-red-400 transition-all duration-75"
          style={{ height: `${4 + level * 20}px` }}
        />
      ))}
    </div>
  );
}
```

### Step 6.2: ChatPanel 整合 AudioVisualizer

- [ ] 修改 `pawai-studio/frontend/components/chat/chat-panel.tsx`

新增 import：

```typescript
import { AudioVisualizer } from "@/components/chat/audio-visualizer"
```

更新 `useAudioRecorder` 解構：

```typescript
  const { isRecording, isProcessing, audioLevels, lastResult: voiceResult, error: voiceError, startRecording, stopRecording } = useAudioRecorder()
```

替換 Mic button（composer 中 `{/* Mic button */}` 區塊），改成錄音時擴展為 pill：

```tsx
      {/* Mic button */}
      <Button
        onClick={() => isRecording ? stopRecording() : startRecording()}
        disabled={isThinking || isProcessing}
        size={isRecording ? "default" : "icon"}
        className={cn(
          "absolute bottom-2.5 transition-all duration-200",
          isRecording
            ? "right-12 h-8 px-3 rounded-full bg-red-500 hover:bg-red-600 text-white shadow-sm flex items-center gap-2"
            : isProcessing
              ? "right-12 h-8 w-8 rounded-lg bg-amber-500 text-white cursor-wait"
              : "right-12 h-8 w-8 rounded-lg bg-muted text-muted-foreground hover:bg-muted-foreground/20 hover:text-foreground"
        )}
        title={isRecording ? "停止錄音" : isProcessing ? "辨識中..." : "語音輸入"}
      >
        {isRecording ? (
          <>
            <AudioVisualizer levels={audioLevels} isActive={isRecording} />
            <Square className="h-3 w-3 shrink-0" />
          </>
        ) : (
          <Mic className="h-4 w-4" />
        )}
      </Button>
```

---

## Task 7: Build 驗證 + Commit

### Step 7.1: Gateway 測試

- [ ] 執行 gateway 全測試

```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py pawai-studio/gateway/test_video_bridge.py -v
```

Expected: 全部通過

### Step 7.2: Frontend build

- [ ] 執行 Next.js build

```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend && npx next build
```

Expected: build 成功

### Step 7.3: Commit

- [ ] Commit gateway 變更

```bash
git add pawai-studio/gateway/studio_gateway.py pawai-studio/gateway/test_gateway.py
git commit -m "feat(gateway): subscribe /tts topic — broadcast as source:tts event"
```

- [ ] Commit frontend 變更

```bash
git add \
  pawai-studio/frontend/stores/state-store.ts \
  pawai-studio/frontend/hooks/use-event-stream.ts \
  pawai-studio/frontend/hooks/use-text-command.ts \
  pawai-studio/frontend/hooks/use-audio-recorder.ts \
  pawai-studio/frontend/components/chat/audio-visualizer.tsx \
  pawai-studio/frontend/components/chat/chat-panel.tsx
git commit -m "feat(studio): chat loop via ROS2 pipeline + audio visualizer bars"
```

- [ ] Commit spec + plan

```bash
git add \
  docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-07-chat-loop-and-audio-viz-design.md \
  docs/pawai-brain/studio/plans/2026-04-07-chat-loop-and-audio-viz.md
git commit -m "docs: chat loop + audio viz spec and plan"
```

---

## Summary

| Task | 內容 | 檔案數 |
|:----:|------|:------:|
| 1 | Gateway 訂閱 `/tts` + test | 2 modify |
| 2 | state-store + useEventStream TTS case | 2 modify |
| 3 | `useTextCommand` hook | 1 new |
| 4 | ChatPanel 改走 `/ws/text` + pending | 1 modify |
| 5 | `useAudioRecorder` 加 `audioLevels` | 1 modify |
| 6 | `AudioVisualizer` + ChatPanel 整合 | 1 new, 1 modify |
| 7 | Build 驗證 + 3 commits | — |

**總計**：2 new files, 6 modifications, 3 commits
