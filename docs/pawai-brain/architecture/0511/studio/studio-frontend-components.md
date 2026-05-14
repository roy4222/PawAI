# Studio Frontend Components — Next.js 16 panel 元件拆分

**版本**：2026-05-11 freeze 快照
**真相來源**：`pawai-studio/frontend/`

---

## 1. 應用結構（App Router）

```
pawai-studio/frontend/
├── app/
│   └── studio/
│       ├── page.tsx          ← 主入口（chat-first 主畫面）
│       └── dev/page.tsx      ← ?dev=1 開發者模式
├── components/               ← UI 元件
│   ├── ui/sheet.tsx          ← center modal（feature panel container）
│   ├── chat-panel.tsx        ← 主對話界面
│   ├── face-panel.tsx        ← 人臉辨識 Sheet 內容
│   ├── speech-panel.tsx      ← 語音功能 Sheet 內容
│   ├── gesture-panel.tsx     ← 手勢辨識 Sheet 內容
│   ├── pose-panel.tsx        ← 姿勢辨識 Sheet 內容
│   ├── object-panel.tsx      ← 物體辨識 Sheet 內容
│   └── navigation-panel.tsx  ← 導航避障 Sheet 內容
├── hooks/
│   ├── use-websocket.ts      ← WebSocket 連線管理（L23: useWebSocket）
│   └── use-studio-events.ts  ← 事件分派到 stores
├── stores/
│   ├── state-store.ts        ← 各模組 state + TTS messages（Zustand）
│   ├── event-store.ts        ← raw event ring buffer（max 200）
│   ├── layout-store.ts       ← panel 配置 / layout preset
│   ├── sheet-store.ts        ← modal 開關狀態
│   └── types.ts              ← store internal types
├── contracts/
│   └── types.ts              ← PawAIEvent + 各模組 TS 型別（真相）
└── lib/
    ├── gateway-url.ts        ← Gateway HTTP/WS URL resolver
    └── object-event.ts       ← normalizeObjectState()（合併 objects/detected_objects）
```

---

## 2. 主畫面架構（chat-first，5/4 落地）

```
┌─────────────── Top Navbar ───────────────────────────────┐
│ Logo "PawAI Studio"  [Face][Mic][Hand][Person][Box][Compass]  [LIVE]  ● │
└──────────────────────────────────────────────────────────┘
     ↓ 每個 icon 按一下 → open Sheet（center modal）

┌────────────── Status Pill（居中 thin pill）───────────────┐
│  Brain {mode} · obs:{ok|hit} emg:{ok|hit} fall:{ok|hit} tts:{idle|playing} │
└──────────────────────────────────────────────────────────┘

┌────────────── Main Chat（flex-col，max-w-3xl 居中）───────┐
│                                                          │
│  [AI bubble, transparent + thin outline, Sparkles avatar] │
│                                              [User bubble, cyan, right] │
│  ...                                                     │
└──────────────────────────────────────────────────────────┘

┌────────────── Bottom Composer ────────────────────────────┐
│  [textarea]                           [mic]  [send]       │
└──────────────────────────────────────────────────────────┘
```

**6 個 feature button → Sheet**（`docs/pawai-brain/studio/README.md` §主畫面架構）：

| Icon | Label | Panel |
|------|-------|-------|
| User | 人臉辨識 | `<FacePanel />` |
| Mic | 語音功能 | `<SpeechPanel />` |
| Hand | 手勢辨識 | `<GesturePanel />` |
| PersonStanding | 姿勢辨識 | `<PosePanel />` |
| Box | 辨識物體 | `<ObjectPanel />` |
| Compass | 導航避障 | `<NavigationPanel />`（含 Nav Gate / Depth Gate / Plan A/B chip）|

---

## 3. 事件分派規則（use-studio-events.ts）

WebSocket → stores 的分派邏輯（hook 訂閱 `useWebSocket`，callback dispatch）：

| source | event_type | 分派目標 |
|--------|-----------|---------|
| `"face"` | any | `updateFaceState(data as FaceState)` |
| `"gesture"` | `"gesture_detected"` | `updateGestureState(data as GestureState)` |
| `"pose"` | `"pose_detected"` | `updatePoseState(data as PoseState)` |
| `"speech"` | `"intent_recognized"` | `updateSpeechState(data as SpeechState)` |
| `"object"` | `"object_detected"` | `updateObjectState(normalizeObjectState(data))` |
| `"brain"` | `"state"` | `updateBrainState(data)` |
| `"brain"` | `"proposal"` | `appendBrainProposal(data as SkillPlan)` |
| `"brain"` | `"skill_result"` | `appendBrainResult(data as SkillResult)` |
| `"brain"` | `"conversation_trace"` | `appendConversationTrace(data)` |
| `"tts"` | `"tts_speaking"` | `updateTts(data.text)` + `appendTtsMessage(msg)` |
| `"capability"` | `"capability_nav_ready"` | `updateCapability("nav_ready", tri_state)` |
| `"capability"` | `"capability_depth_clear"` | `updateCapability("depth_clear", tri_state)` |
| any | any | `addEvent(event)` — 永遠記入 event store |

---

## 4. Zustand Stores

### state-store.ts（`stores/state-store.ts`）

**StateStore interface**（L33-64）主要欄位：
```typescript
faceState: FaceState | null
speechState: SpeechState | null
gestureState: GestureState | null
poseState: PoseState | null
brainState: BrainState | null           // PawAIBrainState
brainProposals: SkillPlan[]             // ring buffer slice(0, 50)
brainResults: SkillResult[]             // ring buffer slice(0, 200)
conversationTraces: ConversationTracePayload[]  // slice(0, 50)
ttsMessages: TtsMessage[]               // ring buffer max 200
capability: CapabilityState             // {nav_ready, depth_clear} tri-state
planMode: PlanMode                      // "A" | "B"
```

**TTS rate-limit**（L1-5）：自發性 TTS（非 chat_reply / skill_say / say_canned）限 5s 一次：
```typescript
const RATE_LIMIT_BYPASS = new Set(["chat_reply", "skill_say", "say_canned"])
const RATE_LIMIT_WINDOW_MS = 5000
```

### event-store.ts（`stores/event-store.ts`）

原始事件 ring buffer，max 200（L7）：
```typescript
const MAX_EVENTS = 200
export const useEventStore = create<EventStore>((set, get) => ({
  events: [],
  addEvent: (event) => { ... updated.slice(0, MAX_EVENTS) }
  getEventsBySource: (source) => get().events.filter(e => e.source === source)
  clearEvents: () => set({ events: [] })
}))
```

---

## 5. WebSocket 連線狀態機（use-websocket.ts）

```
CLOSED ──connect()──► CONNECTING
                           │
                    ws.onopen ──► OPEN (setIsConnected(true))
                           │
                    ws.onclose ──► setTimeout(3s) ──► CONNECTING（重連）
                           │
                    ws.onerror ──► ws.close() ──► onclose 觸發
                           │
                unmount ──► unmountedRef=true，清 timer，ws.close()
```

關鍵實作（`use-websocket.ts`）：
- L13：`RECONNECT_DELAY_MS = 3000`
- L27：`onMessageRef`（useRef）保持 callback 最新但不觸發 reconnect
- L41-43：URL 優先序：`NEXT_PUBLIC_WS_URL` env → `getGatewayWsUrl("/ws/events")`
- L57-64：`NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=true` 才開 F5 auto-reset（demo 預設關）

---

## 6. ChatPanel 對話邏輯

**使用者送文字**：
1. `textarea` 送出 → `POST /api/text_input`（JSON body）
2. Gateway publish `/brain/text_input`
3. Brain 決策 → Executive → `/tts` topic
4. Gateway `_on_tts_msg()` → broadcast `{source:"tts",event_type:"tts_speaking"}`
5. Frontend `appendTtsMessage()` → ChatPanel 渲染 AI bubble

**AI bubble 顯示條件**：`lastTtsText` + `lastTtsAt` 更新時渲染（state-store `updateTts()`）。

**「回應逾時」症狀**：`tts_speaking` event 沒到達前端 → chatPanel 看起來卡住。
定位：看 Gateway log 是否有 `_on_tts_msg()` 觸發 + 看 WS 是否 connected。

---

## 7. Navigation Panel（Trace Drawer）

`<NavigationPanel />` 包含三個 capability chip：
- **Nav Gate**（`nav_ready`）：tri-state chip（green=true / red=false / gray=unknown）
- **Depth Gate**（`depth_clear`）：tri-state chip
- **Plan Mode**（A/B）：`GET/POST /api/plan_mode`

數據來源：`useStateStore.capability` + `useStateStore.planMode`。

Trace Drawer（Conversation Trace 面板）在每個 `brain:conversation_trace` 事件進來時更新，顯示 Brain 12-node 執行路徑（`ConversationTracePayload.stage + status + detail`）。

---

## 8. 測試

```bash
# TypeScript 型別檢查
cd pawai-studio/frontend && npx tsc --noEmit

# 前端單元測試
cd pawai-studio/frontend && npx vitest run

# E2E（Mock 模式）
bash pawai-studio/start-live.sh --mock
# → open http://localhost:3000/studio
```

5/11 狀態：221 tests PASS, tsc 0 errors（`docs/pawai-brain/studio/README.md` §狀態卡）。
