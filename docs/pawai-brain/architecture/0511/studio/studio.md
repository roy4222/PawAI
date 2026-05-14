# PawAI Studio（studio_gateway + mock_server + Next.js 16）— 架構詳述

**版本**：2026-05-11 freeze 快照
**位置**：`pawai-studio/`
**入口**：
- Jetson 模式：`pawai-studio/gateway/studio_gateway.py`（FastAPI + rclpy）
- Mock 模式：`pawai-studio/backend/mock_server.py`（FastAPI 純 Python）
- 前端：`pawai-studio/frontend/`（Next.js 16 + React 19 + Tailwind v4）
**狀態**：5/11 pre-freeze，chat-first redesign 落地，221 tests PASS

---

## 0. 明天開發用閱讀入口

這份 `studio.md` 是總覽與凍結快照。快速定位問題優先讀同資料夾拆出的 4 份文件：

| 文件 | 用途 |
|------|------|
| `studio-runtime-flow.md` | WebSocket 端點、TOPIC_MAP、ROS2 ↔ Gateway 完整資料流 |
| `studio-frontend-components.md` | Next.js panel 拆分、Zustand stores、事件分派規則 |
| `studio-gateway-mock-bridge.md` | Gateway vs Mock 雙路徑對比、event schema、PawAIEvent 信封 |
| `studio-debug-runbook.md` | 現場症狀 → 檔案位置、常見故障排查 |

**快速原則**：
- 怎麼連線：看 `studio-runtime-flow.md` §2 WebSocket 端點
- 前端 panel 不更新：看 `studio-frontend-components.md` §3 事件分派
- Mock 和 Jetson 行為差異：看 `studio-gateway-mock-bridge.md` §1 雙路徑對比
- 症狀定位：直接讀 `studio-debug-runbook.md`

---

## 1. 模組定位

Studio 是 PawAI 系統的**觀測與操作前端**，同時也是**語音替代入口**（demo 現場筆電收音代替機身 mic）。

**三個角色**：
1. **觀測器**：訂閱 ROS2 10 個 topic，把感知事件（face/gesture/pose/object/speech）+ brain 決策（proposal/trace）以 WebSocket 即時推到前端面板
2. **操作器**：前端 ChatPanel 發文字 → `/api/text_input` → `/brain/text_input`；技能按鈕 → `/api/skill_request` → `/brain/skill_request`
3. **語音入口**：麥克風收音 → `/ws/speech` → ASR（SenseVoice Cloud/Local）→ 發布 `/event/speech_intent_recognized`

**設計哲學（chat-first，5/4 落地）**：
- 主畫面是 ChatGPT 風純對話（不是功能面板）
- 6 個感知模組收進 icon-only navbar button → 點開 center modal
- `?dev=1` 才顯示 dev panel（示範場合不暴露調試界面）
- Trace Drawer（Conversation Trace 面板）：每條 trace entry 對應 Brain 12-node 中的一個執行步驟

---

## 2. 雙路徑架構

```
┌─────────────────────── Jetson 模式（production）─────────────────────────┐
│                                                                          │
│  Browser  ←── WebSocket /ws/events ──── GatewayNode ── rclpy.spin()    │
│               WebSocket /ws/speech ──→  GatewayNode ──→ /event/speech  │
│               POST /api/text_input ──→  GatewayNode ──→ /brain/text_   │
│                                         input                           │
│         studio_gateway.py: FastAPI + GatewayNode(Node)                  │
│         GatewayNode.__init__() subscribes TOPIC_MAP (10 topics)         │
│         + /tts + 2 capability Bool topics                               │
│         線程模型：asyncio loop + threading(rclpy.spin)                   │
│         跨線程橋接：asyncio.run_coroutine_threadsafe()                   │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────── Mock 模式（本機開發）──────────────────────────────┐
│                                                                          │
│  Browser  ←── WebSocket /ws/events ──── ConnectionManager              │
│               每 2 秒 periodic_mock_push() 推一個隨機事件                 │
│               mock_server.py: 純 FastAPI，無 ROS2 依賴                   │
│               MOCK_OPENROUTER=1 啟用真 Gemini 3 Flash 對話               │
└──────────────────────────────────────────────────────────────────────────┘
```

**選擇路徑**：
```bash
bash pawai-studio/start-live.sh          # auto 探測（推薦）
bash pawai-studio/start-live.sh --live   # 強制 Jetson
bash pawai-studio/start-live.sh --mock   # 強制 Mock
```

---

## 3. Gateway 核心（studio_gateway.py）

**GatewayNode**（`studio_gateway.py` L160）繼承 `rclpy.node.Node`，在 `lifespan`（L423）中啟動：

```python
# studio_gateway.py L423-434
@asynccontextmanager
async def lifespan(app: FastAPI):
    global node, classifier
    rclpy.init()
    loop = asyncio.get_running_loop()
    node = GatewayNode(loop)
    classifier = IntentClassifier()
    spin_thread = threading.Thread(target=_spin_ros2, args=(node,), daemon=True)
    spin_thread.start()
    yield
```

**TOPIC_MAP**（`studio_gateway.py` L72-83）— 10 個 String topic：

| ROS2 Topic | Frontend source |
|---|---|
| `/state/perception/face` | `"face"` |
| `/event/gesture_detected` | `"gesture"` |
| `/event/pose_detected` | `"pose"` |
| `/event/speech_intent_recognized` | `"speech"` |
| `/event/object_detected` | `"object"` |
| `/state/pawai_brain` | `"brain:state"` |
| `/brain/proposal` | `"brain:proposal"` |
| `/brain/skill_result` | `"brain:skill_result"` |
| `/brain/conversation_trace` | `"brain:conversation_trace"` |
| `/brain/conversation_trace_shadow` | `"brain:conversation_trace_shadow"` |

**額外訂閱**（L196-210）：
- `/tts`（String）→ `build_tts_event()` 包裝後廣播
- `/capability/nav_ready`（Bool）→ tri-state 更新
- `/capability/depth_clear`（Bool）→ tri-state 更新

**Face 節流**（L85、L295-299）：face topic 10Hz → 2Hz（`FACE_THROTTLE_S = 0.5`）

---

## 4. PawAIEvent 信封（event schema）

真相來源：`pawai-studio/frontend/contracts/types.ts` L12-18

```typescript
export interface PawAIEvent {
  id: string;          // uuid4
  timestamp: string;   // ISO 8601
  source: string;      // "face" | "gesture" | "pose" | "speech" | "object" | "brain" | "tts" | "capability"
  event_type: string;  // source 特定，如 "gesture_detected" / "brain:proposal" / "tts_speaking"
  data: Record<string, unknown>;
}
```

Gateway `_on_ros2_msg()`（L287）把 ROS2 JSON → PawAIEvent 信封，同時做 field transforms（L309-326）：
- gesture：補 `current_gesture` + `status: "active"`
- pose：補 `current_pose` + `status: "active"`
- speech：補 `phase: "listening"`

---

## 5. 前端入口

**主頁面**：`pawai-studio/frontend/app/studio/page.tsx`（或 `page.tsx` 在 app router）
**WebSocket hook**：`pawai-studio/frontend/hooks/use-websocket.ts` — 連 `/ws/events`，3s 重連（L13: `RECONNECT_DELAY_MS = 3000`）
**State stores**（Zustand）：
- `stores/state-store.ts`：各模組 state + TTS messages（ring buffer max 200，L95: `brainResults.slice(0, 200)`）
- `stores/event-store.ts`：raw event log（max 200，L7: `MAX_EVENTS = 200`）
- `stores/layout-store.ts`：panel 配置
- `stores/sheet-store.ts`：modal 開關狀態

**6 個 feature button → center modal（Sheet）**：
Face / Speech / Gesture / Pose / Object / Navigation 各對應一個 Panel 元件

---

## 6. REST API 端點速查

| 端點 | 方法 | 功能 |
|------|------|------|
| `/api/text_input` | POST | 文字 → Brain（`/brain/text_input`），s2twp 正規化 |
| `/api/skill_request` | POST | 技能請求 → `skill_request_pub`（`/brain/skill_request`）|
| `/api/reset` | POST | 清 conversation memory（`/brain/reset_context`）|
| `/api/skill_registry` | GET | SKILL_REGISTRY JSON（來自 `interaction_executive.skill_contract`）|
| `/api/capability` | GET | tri-state capability 快照 |
| `/api/plan_mode` | GET/POST | Plan A/B toggle |
| `/health` | GET | WS clients 數 + 訂閱 topic 列表 |

---

## 7. 5/11 pre-freeze 對照

| 項目 | 5/4 | 5/11 |
|------|-----|------|
| TTS 顯示 | plain-text | tts_speaking event（含 origin/source 分類）|
| Brain trace | 無 | Trace Drawer（12-node 可視化）|
| Capability gate | 無 | Nav Gate / Depth Gate tri-state chip |
| skill_request | Studio 按鈕 | 接 SKILL_REGISTRY，按 bucket/enabled_when 分類 |
| Plan mode | 無 | A/B toggle（Plan A=全 skill stack, B=canned script）|
| CORS | ws only | `/api/*` 全開（5/7 hotfix `allow_origins=["*"]`）|

---

## 8. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| Gateway 核心 | `pawai-studio/gateway/studio_gateway.py` |
| Mock Server | `pawai-studio/backend/mock_server.py` |
| Event schema（TS） | `pawai-studio/frontend/contracts/types.ts` |
| WS 狀態機 | `pawai-studio/frontend/hooks/use-websocket.ts` |
| State stores | `pawai-studio/frontend/stores/state-store.ts` |
| Event ring buffer | `pawai-studio/frontend/stores/event-store.ts` |
| Studio 設計文件 | `docs/pawai-brain/studio/README.md` |
| Studio 工作規則 | `docs/pawai-brain/studio/CLAUDE.md` |
| Mock server schemas | `pawai-studio/backend/schemas.py` |
