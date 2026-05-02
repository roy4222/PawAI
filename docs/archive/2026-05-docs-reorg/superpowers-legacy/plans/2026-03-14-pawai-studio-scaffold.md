# PawAI Studio Scaffold Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交出「可開工包」——前端 scaffold + Gateway + Mock Server，讓四人 3/16 開工。

**Architecture:** 單頁動態 Panel 架構（Next.js 14 App Router）。FastAPI 後端同時提供 Gateway 和 Mock Server。前端透過 WebSocket `/ws/events` 接收事件，透過 REST `/api/*` 發送指令。Layout 由 rule-based orchestrator 根據事件查表切換。

**Tech Stack:** Next.js 14, Tailwind CSS, shadcn/ui, Zustand, FastAPI, uvicorn, WebSocket

**Spec:** `docs/superpowers/specs/2026-03-14-pawai-studio-scaffold-design.md`
**Schema 真相來源:** `docs/Pawai-studio/specs/event-schema.md`

---

## Chunk 1: Backend（Gateway + Mock Server）

### File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `pawai-studio/backend/schemas.py` | Pydantic models，對齊 event-schema.md |
| Create | `pawai-studio/backend/mock_server.py` | Mock Event Server + Gateway 端點（Spec 原列 gateway.py 和 mock_server.py 分開，scaffold 階段合併為一個檔案，未來可拆） |
| Create | `pawai-studio/backend/requirements.txt` | Python 依賴 |

---

### Task 1: Pydantic Schemas

**Files:**
- Create: `pawai-studio/backend/schemas.py`

- [ ] **Step 1: Create schemas.py with all event/state/command models**

先實作 scaffold 所需的最小 Pydantic v2 models（Face/Speech/Gesture/Pose/Brain/System + Commands）。
`RobotState`、`LayoutChangeEvent`、`PanelLayout`/`PanelConfig` 等進階型別留到整合階段再補。

```python
"""PawAI Studio schemas — 對齊 docs/Pawai-studio/specs/event-schema.md"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
import uuid

# === Event 信封 ===

class PawAIEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat())
    source: str
    event_type: str
    data: dict

# === Face ===

class FaceIdentityData(BaseModel):
    track_id: int
    stable_name: str
    sim: float
    distance_m: float | None = None

class FaceTrack(BaseModel):
    track_id: int
    stable_name: str
    sim: float
    distance_m: float | None = None
    bbox: tuple[int, int, int, int]
    mode: Literal["stable", "hold"]

class FaceState(BaseModel):
    stamp: float
    face_count: int
    tracks: list[FaceTrack]

# === Speech ===

class SpeechIntentData(BaseModel):
    intent: str | None = None
    text: str
    confidence: float
    provider: str

class SpeechState(BaseModel):
    stamp: float
    phase: Literal[
        "idle_wakeword", "wake_ack", "loading_local_stack", "listening",
        "transcribing", "local_asr_done", "cloud_brain_pending",
        "speaking", "keep_alive", "unloading"
    ]
    last_asr_text: str = ""
    last_intent: str = ""
    last_tts_text: str = ""
    models_loaded: list[str] = []

# === Gesture ===

class GestureData(BaseModel):
    gesture: str
    confidence: float
    hand: Literal["left", "right"]

class GestureState(BaseModel):
    stamp: float
    active: bool
    current_gesture: str | None = None
    confidence: float = 0.0
    hand: Literal["left", "right"] | None = None
    status: Literal["active", "inactive", "loading"]

# === Pose ===

class PoseData(BaseModel):
    pose: str
    confidence: float
    track_id: int

class PoseState(BaseModel):
    stamp: float
    active: bool
    current_pose: str | None = None
    confidence: float = 0.0
    track_id: int | None = None
    status: Literal["active", "inactive", "loading"]

# === Brain ===

class BrainState(BaseModel):
    stamp: float
    executive_state: Literal["idle", "observing", "deciding", "executing", "speaking"]
    current_intent: str | None = None
    selected_skill: str | None = None
    degradation_level: Literal[0, 1, 2, 3] = 0
    active_tracks: int = 0
    cloud_connected: bool = True
    last_decision_reason: str = ""

# === System ===

class SystemHealth(BaseModel):
    stamp: float
    jetson: dict
    modules: list[dict]

# === Commands ===

class SkillCommand(BaseModel):
    command_type: Literal["skill"] = "skill"
    skill_id: str
    priority: Literal[0, 1] = 0
    source: str = "studio_button"

class ChatCommand(BaseModel):
    command_type: Literal["chat"] = "chat"
    text: str
    session_id: str

class MockTrigger(BaseModel):
    event_source: str
    event_type: str
    data: dict = {}
```

- [ ] **Step 2: Verify import works**

Run: `cd pawai-studio/backend && python -c "from schemas import *; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/backend/schemas.py
git commit -m "feat(backend): add Pydantic schemas aligned with event-schema.md"
```

---

### Task 2: Mock Server + Gateway

**Files:**
- Create: `pawai-studio/backend/mock_server.py`
- Create: `pawai-studio/backend/requirements.txt`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
pydantic>=2.0.0
websockets>=14.0
```

- [ ] **Step 2: Install dependencies**

Run: `cd pawai-studio/backend && uv pip install -r requirements.txt`

- [ ] **Step 3: Create mock_server.py**

```python
"""PawAI Studio — Gateway + Mock Event Server

啟動: uvicorn mock_server:app --host 0.0.0.0 --port 8001 --reload
"""
from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schemas import (
    BrainState,
    ChatCommand,
    FaceIdentityData,
    FaceState,
    FaceTrack,
    GestureData,
    GestureState,
    MockTrigger,
    PawAIEvent,
    PoseData,
    PoseState,
    SkillCommand,
    SpeechIntentData,
    SpeechState,
    SystemHealth,
)

# ── WebSocket 連線管理 ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                self.active.remove(ws)

manager = ConnectionManager()

# ── Mock 資料產生器 ──────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().astimezone().isoformat()

def _uid() -> str:
    return str(uuid.uuid4())

def mock_face_event() -> dict:
    names = ["小明", "小華", "unknown"]
    name = random.choice(names)
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="face",
        event_type=random.choice(["track_started", "identity_stable", "track_lost"]),
        data=FaceIdentityData(
            track_id=random.randint(1, 10),
            stable_name=name,
            sim=round(random.uniform(0.3, 0.98), 2),
            distance_m=round(random.uniform(0.5, 3.0), 1),
        ).model_dump(),
    ).model_dump()

def mock_speech_event() -> dict:
    intents = [
        ("greet", "你好"),
        ("come_here", "過來"),
        ("stop", "停止"),
        ("take_photo", "幫我拍照"),
        ("status", "你好嗎"),
    ]
    intent, text = random.choice(intents)
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="speech",
        event_type="intent_recognized",
        data=SpeechIntentData(
            intent=intent, text=text,
            confidence=round(random.uniform(0.7, 0.99), 2),
            provider="whisper_local",
        ).model_dump(),
    ).model_dump()

def mock_gesture_event() -> dict:
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="gesture",
        event_type="gesture_detected",
        data=GestureData(
            gesture=random.choice(["wave", "stop", "point", "ok"]),
            confidence=round(random.uniform(0.7, 0.95), 2),
            hand=random.choice(["left", "right"]),
        ).model_dump(),
    ).model_dump()

def mock_pose_event() -> dict:
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="pose",
        event_type="pose_detected",
        data=PoseData(
            pose=random.choice(["standing", "sitting", "crouching", "fallen"]),
            confidence=round(random.uniform(0.75, 0.98), 2),
            track_id=random.randint(1, 5),
        ).model_dump(),
    ).model_dump()

MOCK_GENERATORS = {
    "face": mock_face_event,
    "speech": mock_speech_event,
    "gesture": mock_gesture_event,
    "pose": mock_pose_event,
}

# ── 背景推送任務 ────────────────────────────────────────────────────

async def periodic_mock_push() -> None:
    """每 2 秒推送一個隨機事件"""
    while True:
        await asyncio.sleep(2)
        if manager.active:
            source = random.choice(list(MOCK_GENERATORS.keys()))
            event = MOCK_GENERATORS[source]()
            await manager.broadcast(event)

# ── Demo A 場景 ─────────────────────────────────────────────────────

DEMO_A_SEQUENCE = [
    ("face", "track_started", lambda: FaceIdentityData(
        track_id=1, stable_name="unknown", sim=0.15, distance_m=2.5
    ).model_dump()),
    ("face", "identity_stable", lambda: FaceIdentityData(
        track_id=1, stable_name="小明", sim=0.92, distance_m=1.2
    ).model_dump()),
    ("speech", "wake_word", lambda: SpeechIntentData(
        text="", confidence=0.95, provider="sherpa_kws"
    ).model_dump()),
    ("speech", "intent_recognized", lambda: SpeechIntentData(
        intent="greet", text="你好", confidence=0.95, provider="whisper_local"
    ).model_dump()),
    ("brain", "decision_made", lambda: {
        "intent": "greet", "selected_skill": "hello",
        "reason": "identity_stable + greet intent", "degradation_level": 0,
    }),
    ("brain", "skill_dispatched", lambda: {
        "intent": "greet", "selected_skill": "hello",
        "reason": "executing wave greeting", "degradation_level": 0,
    }),
]

async def run_demo_a() -> None:
    for source, event_type, data_fn in DEMO_A_SEQUENCE:
        event = PawAIEvent(
            id=_uid(), timestamp=_ts(),
            source=source, event_type=event_type, data=data_fn(),
        ).model_dump()
        await manager.broadcast(event)
        await asyncio.sleep(1.5)

# ── State 快照 ──────────────────────────────────────────────────────

current_face_state = FaceState(stamp=time.time(), face_count=0, tracks=[])
current_speech_state = SpeechState(stamp=time.time(), phase="idle_wakeword")
current_brain_state = BrainState(stamp=time.time(), executive_state="idle")
current_gesture_state = GestureState(stamp=time.time(), active=False, status="inactive")
current_pose_state = PoseState(stamp=time.time(), active=False, status="inactive")

# ── App ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(periodic_mock_push())
    yield
    task.cancel()

app = FastAPI(title="PawAI Studio Gateway + Mock", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket ───────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)

# ── REST: Gateway 端點 ──────────────────────────────────────────────

@app.post("/api/command")
async def post_command(cmd: SkillCommand):
    event = PawAIEvent(
        id=_uid(), timestamp=_ts(), source="brain",
        event_type="skill_dispatched",
        data={"intent": "manual", "selected_skill": cmd.skill_id,
              "reason": f"studio {cmd.source}", "degradation_level": 0},
    ).model_dump()
    await manager.broadcast(event)
    return {"status": "ok", "skill_id": cmd.skill_id}

@app.post("/api/chat")
async def post_chat(cmd: ChatCommand):
    reply = f"收到你的訊息：「{cmd.text}」（這是 Mock 回覆）"
    return {"status": "ok", "reply": reply, "session_id": cmd.session_id}

@app.get("/api/brain")
async def get_brain():
    return current_brain_state.model_dump()

@app.get("/api/health")
async def get_health():
    return SystemHealth(
        stamp=time.time(),
        jetson={"cpu_percent": 45.2, "gpu_percent": 30.1,
                "ram_used_mb": 5120, "ram_total_mb": 8192, "temperature_c": 52.3},
        modules=[
            {"name": "face", "status": "active", "latency_ms": 12, "last_heartbeat": time.time()},
            {"name": "speech", "status": "active", "latency_ms": 8, "last_heartbeat": time.time()},
            {"name": "brain", "status": "active", "latency_ms": 150, "last_heartbeat": time.time()},
        ],
    ).model_dump()

# ── REST: Mock 控制端點 ─────────────────────────────────────────────

@app.post("/mock/trigger")
async def mock_trigger(trigger: MockTrigger):
    event = PawAIEvent(
        id=_uid(), timestamp=_ts(),
        source=trigger.event_source,
        event_type=trigger.event_type,
        data=trigger.data,
    ).model_dump()
    await manager.broadcast(event)
    return {"status": "ok", "event_id": event["id"]}

@app.post("/mock/scenario/demo_a")
async def mock_demo_a():
    asyncio.create_task(run_demo_a())
    return {"status": "started", "scenario": "demo_a", "steps": len(DEMO_A_SEQUENCE)}
```

- [ ] **Step 4: Test server starts**

Run: `cd pawai-studio/backend && timeout 5 uvicorn mock_server:app --host 0.0.0.0 --port 8001 || true`
Expected: server starts, shows "Uvicorn running on http://0.0.0.0:8001"

- [ ] **Step 5: Commit**

```bash
git add pawai-studio/backend/
git commit -m "feat(backend): add Gateway + Mock Server with WebSocket + REST"
```

---

## Chunk 2: Frontend Scaffold

### File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `pawai-studio/frontend/` | Next.js 14 project |
| Create | `pawai-studio/frontend/contracts/types.ts` | TS 型別（對齊 event-schema.md） |
| Create | `pawai-studio/frontend/app/layout.tsx` | 全站 layout |
| Create | `pawai-studio/frontend/app/page.tsx` | / redirect |
| Create | `pawai-studio/frontend/app/globals.css` | Design tokens + Tailwind |
| Create | `pawai-studio/frontend/app/(studio)/studio/page.tsx` | 主入口頁 |
| Create | `pawai-studio/frontend/hooks/use-websocket.ts` | WebSocket hook |
| Create | `pawai-studio/frontend/hooks/use-event-stream.ts` | 事件訂閱 hook |
| Create | `pawai-studio/frontend/hooks/use-layout-manager.ts` | Layout 切換 |
| Create | `pawai-studio/frontend/stores/event-store.ts` | Zustand event store |
| Create | `pawai-studio/frontend/stores/state-store.ts` | Zustand state store |
| Create | `pawai-studio/frontend/stores/layout-store.ts` | Zustand layout store |
| Create | `pawai-studio/frontend/components/shared/*.tsx` | 5 個共用元件 |
| Create | `pawai-studio/frontend/components/layout/*.tsx` | layout 元件 |
| Create | `pawai-studio/frontend/components/chat/chat-panel.tsx` | ChatPanel |
| Create | `pawai-studio/frontend/components/face/face-panel.tsx` | 空殼 |
| Create | `pawai-studio/frontend/components/speech/speech-panel.tsx` | 空殼 |
| Create | `pawai-studio/frontend/components/gesture/gesture-panel.tsx` | 空殼 |
| Create | `pawai-studio/frontend/components/pose/pose-panel.tsx` | 空殼 |

---

### Task 3: Next.js Project Init

**Files:**
- Create: `pawai-studio/frontend/` (entire Next.js project)

- [ ] **Step 1: Create Next.js project**

```bash
cd pawai-studio
npx create-next-app@latest frontend --yes \
  --typescript --tailwind --eslint --app \
  --src-dir=false --import-alias="@/*" \
  --use-npm --no-turbopack
```

- [ ] **Step 2: Install additional dependencies**

```bash
cd pawai-studio/frontend
npm install zustand lucide-react
npx shadcn@latest init -d
```

shadcn init 時選擇：
- Style: Default
- Base color: Slate
- CSS variables: Yes

- [ ] **Step 3: Install shadcn components**

```bash
cd pawai-studio/frontend
npx shadcn@latest add card badge button input scroll-area separator
```

- [ ] **Step 4: Verify dev server starts**

Run: `cd pawai-studio/frontend && npm run dev &` then `sleep 3 && curl -s http://localhost:3000 | head -5`
Expected: HTML output

- [ ] **Step 5: Create .env.development**

```bash
cat > pawai-studio/frontend/.env.development << 'EOF'
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001/ws/events
DATA_SOURCE=mock
EOF
```

- [ ] **Step 6: Commit**

```bash
git add pawai-studio/frontend/
git commit -m "feat(frontend): init Next.js 14 + Tailwind + shadcn/ui"
```

---

### Task 4: Design Tokens + globals.css

**Files:**
- Modify: `pawai-studio/frontend/app/globals.css`
- Modify: `pawai-studio/frontend/tailwind.config.ts`

- [ ] **Step 1: Replace globals.css with design tokens**

Replace the entire `globals.css` with the design tokens from `pawai-studio/docs/design-tokens.md`. Key CSS variables:

```css
@import "tailwindcss";
@import "tw-animate-css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-surface: var(--surface);
  --color-surface-hover: var(--surface-hover);
  --color-border: var(--border);
  --color-success: var(--success);
  --color-warning: var(--warning);
  --color-destructive: var(--destructive);
  --color-info: var(--info);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-muted-foreground: var(--muted-foreground);
  --font-mono: "Fira Code", ui-monospace, monospace;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 12px;
}

:root {
  --background: #0A0A0F;
  --foreground: #F0F0F5;
  --surface: #141419;
  --surface-hover: #1C1C24;
  --border: #2A2A35;
  --muted-foreground: #8B8B9E;
  --primary: #7C6BFF;
  --primary-hover: #9585FF;
  --primary-foreground: #FFFFFF;
  --success: #22C55E;
  --warning: #F59E0B;
  --destructive: #EF4444;
  --info: #3B82F6;
  --card: #141419;
  --card-foreground: #F0F0F5;
  --accent: #1C1C24;
  --accent-foreground: #F0F0F5;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: "Inter", "Noto Sans TC", sans-serif;
}
```

- [ ] **Step 2: Add Google Fonts to layout.tsx**

Import Inter, Fira Code, and Noto Sans TC via `next/font/google`.

- [ ] **Step 3: Verify dark theme renders**

Run: `npm run dev`, open `http://localhost:3000`, confirm dark background `#0A0A0F`.

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/frontend/app/globals.css pawai-studio/frontend/tailwind.config.ts pawai-studio/frontend/app/layout.tsx
git commit -m "feat(frontend): apply design tokens — dark theme + AI purple"
```

---

### Task 5: TypeScript Contracts

**Files:**
- Create: `pawai-studio/frontend/contracts/types.ts`

- [ ] **Step 1: Create types.ts**

Mirror all interfaces from `docs/Pawai-studio/specs/event-schema.md` into TypeScript. Include: PawAIEvent, FaceIdentityEvent, FaceState, FaceTrack, SpeechIntentEvent, SpeechState, GestureEvent, GestureState, PoseEvent, PoseState, BrainState, SystemHealth, SkillCommand, ChatCommand, MockTrigger, LayoutPreset.

- [ ] **Step 2: Verify no TS errors**

Run: `cd pawai-studio/frontend && npx tsc --noEmit contracts/types.ts`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/contracts/
git commit -m "feat(frontend): add TS contracts aligned with event-schema.md"
```

---

### Task 6: Zustand Stores

**Files:**
- Create: `pawai-studio/frontend/stores/event-store.ts`
- Create: `pawai-studio/frontend/stores/state-store.ts`
- Create: `pawai-studio/frontend/stores/layout-store.ts`

- [ ] **Step 1: Create event-store.ts**

Zustand store that holds event history (max 200 items), supports `addEvent()` and `getEventsBySource()`.

- [ ] **Step 2: Create state-store.ts**

Holds latest state snapshots: `faceState`, `speechState`, `gestureState`, `poseState`, `brainState`, `systemHealth`. Each has `updateXxx()` action.

- [ ] **Step 3: Create layout-store.ts**

Holds `currentPreset` (LayoutPreset), `activePanels` (Set), `dismissedPanels` (Set). Actions: `showPanel()`, `hidePanel()`, `dismissPanel()`, `resetDismissed()`. Implements the rule-based layout switching from spec section 5.

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/frontend/stores/
git commit -m "feat(frontend): add Zustand stores — events, state, layout"
```

---

### Task 7: WebSocket + Event Stream Hooks

**Files:**
- Create: `pawai-studio/frontend/hooks/use-websocket.ts`
- Create: `pawai-studio/frontend/hooks/use-event-stream.ts`
- Create: `pawai-studio/frontend/hooks/use-layout-manager.ts`

- [ ] **Step 1: Create use-websocket.ts**

Custom hook: connects to `NEXT_PUBLIC_WS_URL` (`/ws/events`), auto-reconnects on disconnect (3s delay), exposes `isConnected` state. Parses incoming JSON and calls `onMessage` callback.

- [ ] **Step 2: Create use-event-stream.ts**

Combines `useWebSocket` with Zustand stores. On each event:
1. `eventStore.addEvent(event)`
2. If event is a state update, update `stateStore`
3. Call `layoutStore` to evaluate layout change

- [ ] **Step 3: Create use-layout-manager.ts**

Rule-based layout orchestrator. Given an event, looks up the trigger matrix (spec section 5.1) and calls `layoutStore.showPanel()`. Handles:
- Panel priority replacement when > 4 visible
- `dismissedPanels` bypass (except critical events)
- Critical event forced re-open

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/frontend/hooks/
git commit -m "feat(frontend): add WebSocket + event stream + layout manager hooks"
```

---

### Task 8: Shared Components

**Files:**
- Create: `pawai-studio/frontend/components/shared/panel-card.tsx`
- Create: `pawai-studio/frontend/components/shared/status-badge.tsx`
- Create: `pawai-studio/frontend/components/shared/event-item.tsx`
- Create: `pawai-studio/frontend/components/shared/metric-chip.tsx`
- Create: `pawai-studio/frontend/components/shared/live-indicator.tsx`

- [ ] **Step 1: Create PanelCard**

Wraps shadcn `Card`. Props: `title: string`, `icon: ReactNode`, `status: "active" | "loading" | "error" | "inactive"`, `count?: number`, `onDismiss?: () => void`, `children: ReactNode`. Fixed header with title + StatusBadge + LiveIndicator + dismiss button. Body renders children. Uses `bg-surface border-border rounded-[12px] p-4`.

- [ ] **Step 2: Create StatusBadge**

Wraps shadcn `Badge`. Props: `status: "active" | "loading" | "error" | "inactive"`. Maps to: active=success+pulse, loading=warning+pulse, error=destructive, inactive=gray.

- [ ] **Step 3: Create LiveIndicator**

Props: `active: boolean`. Green dot (6px) with `animate-pulse` when active, gray when inactive.

- [ ] **Step 4: Create MetricChip**

Wraps shadcn `Badge variant="outline"`. Props: `label: string`, `value: number`, `unit?: string`, `trend?: "up" | "down" | "stable"`. Shows `label: value unit` with optional trend arrow icon.

- [ ] **Step 5: Create EventItem**

Props: `timestamp: string`, `eventType: string`, `source: string`, `summary: string`, `onClick?: () => void`. Single row: timestamp (mono font) + event type badge + summary text. Hover state with `surface-hover`.

- [ ] **Step 6: Verify all components render**

Create a temporary test page or use Storybook-like approach to verify.

- [ ] **Step 7: Commit**

```bash
git add pawai-studio/frontend/components/shared/
git commit -m "feat(frontend): add 5 shared components — PanelCard, StatusBadge, EventItem, MetricChip, LiveIndicator"
```

---

### Task 9: Layout Components

**Files:**
- Create: `pawai-studio/frontend/components/layout/topbar.tsx`
- Create: `pawai-studio/frontend/components/layout/studio-layout.tsx`
- Create: `pawai-studio/frontend/components/layout/panel-container.tsx`

- [ ] **Step 1: Create Topbar**

Fixed top bar. Left: PawAI logo + "PawAI Studio" text. Right: connection status (LiveIndicator) + settings icon button. Height: 48px. Background: `surface`. Border bottom: `border`.

- [ ] **Step 2: Create PanelContainer**

Renders a list of Panel components in the sidebar position. Props: `panels: ReactNode[]`, `position: "sidebar" | "bottom"`. Sidebar: vertical stack, max 2 items. Bottom: horizontal, max 1 item. Transition animations (200ms) on panel enter/exit.

- [ ] **Step 3: Create StudioLayout**

The main layout container. Uses `useLayoutManager` to decide which panels to show. Structure:
```
Topbar (fixed)
├── main (Chat, always visible)
├── sidebar (PanelContainer, 0-2 panels)
└── bottom (PanelContainer, 0-1 panel)
```

Uses CSS Grid: `grid-template-columns: 1fr auto`, `grid-template-rows: 1fr auto`.

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/frontend/components/layout/
git commit -m "feat(frontend): add layout components — Topbar, StudioLayout, PanelContainer"
```

---

### Task 10: ChatPanel (Minimal)

**Files:**
- Create: `pawai-studio/frontend/components/chat/chat-panel.tsx`

- [ ] **Step 1: Create ChatPanel**

Minimal working ChatPanel for scaffold:
- Message list (scrollable, auto-scroll to bottom)
- Fixed bottom input bar with send button
- Message types: user (right-aligned, accent/10 bg) and ai (left-aligned, surface bg + left purple border)
- POST to `/api/chat` on send, display reply
- Event cards rendered inline when events arrive from `useEventStream`
- Status chip (Thinking... with 3-dot pulse) while waiting for reply

This is Roy's component, not a stub. Should be functional.

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/frontend/components/chat/
git commit -m "feat(frontend): add ChatPanel with message list + input + event cards"
```

---

### Task 11: Four Panel Stubs

**Files:**
- Create: `pawai-studio/frontend/components/face/face-panel.tsx`
- Create: `pawai-studio/frontend/components/speech/speech-panel.tsx`
- Create: `pawai-studio/frontend/components/gesture/gesture-panel.tsx`
- Create: `pawai-studio/frontend/components/pose/pose-panel.tsx`

- [ ] **Step 1: Create FacePanel stub**

```tsx
"use client";
import { PanelCard } from "@/components/shared/panel-card";
import { User } from "lucide-react";
import type { FaceState, FaceIdentityEvent } from "@/contracts/types";

interface FacePanelProps {
  data: FaceState;
  events: FaceIdentityEvent[];
}

export function FacePanel({ data, events }: FacePanelProps) {
  return (
    <PanelCard title="人臉辨識" icon={<User className="h-4 w-4" />} status={data.face_count > 0 ? "active" : "inactive"} count={data.face_count}>
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
        <p>TODO: 鄔負責實作（見 face-panel-spec.md）</p>
      </div>
    </PanelCard>
  );
}
```

- [ ] **Step 2: Create SpeechPanel stub**

Same pattern, title="語音互動", icon=`Mic`, status based on `data.phase !== "idle_wakeword"`.

- [ ] **Step 3: Create GesturePanel stub**

Same pattern, title="手勢辨識", icon=`Hand`, status based on `data.active`.

- [ ] **Step 4: Create PosePanel stub**

Same pattern, title="姿勢辨識", icon=`PersonStanding`, status based on `data.active`.

- [ ] **Step 5: Commit**

```bash
git add pawai-studio/frontend/components/face/ pawai-studio/frontend/components/speech/ pawai-studio/frontend/components/gesture/ pawai-studio/frontend/components/pose/
git commit -m "feat(frontend): add 4 panel stubs for team members (face/speech/gesture/pose)"
```

---

### Task 12: Studio Page + Wiring

**Files:**
- Modify: `pawai-studio/frontend/app/layout.tsx`
- Create: `pawai-studio/frontend/app/(studio)/studio/page.tsx`
- Modify: `pawai-studio/frontend/app/page.tsx`

- [ ] **Step 1: Update root layout**

Add `className="dark"` to `<html>` tag. Add Topbar. Set body to full height.

- [ ] **Step 2: Create /studio page**

Wire everything together:
- `useEventStream()` to connect WebSocket and populate stores
- `useLayoutManager()` to get current panel layout
- Render `StudioLayout` with `ChatPanel` in main, feature panels in sidebar/bottom based on layout store

- [ ] **Step 3: Update root page.tsx**

Redirect `/` to `/studio` using `redirect()` from `next/navigation`.

- [ ] **Step 4: Verify full flow**

1. Start Mock Server: `cd pawai-studio/backend && uvicorn mock_server:app --port 8001`
2. Start frontend: `cd pawai-studio/frontend && npm run dev`
3. Open `http://localhost:3000` → should redirect to `/studio`
4. Should see ChatPanel, events arriving every 2s, panels appearing in sidebar
5. Type a message → POST to `/api/chat` → see mock reply

- [ ] **Step 5: Commit**

```bash
git add pawai-studio/frontend/app/
git commit -m "feat(frontend): wire up Studio page — Chat + dynamic panels + WebSocket"
```

---

### Task 13: Smoke Test All Endpoints

- [ ] **Step 1: Test Mock Server endpoints**

```bash
# Start server
cd pawai-studio/backend && uvicorn mock_server:app --port 8001 &

# Test REST endpoints
curl -s http://localhost:8001/api/health | python -m json.tool
curl -s http://localhost:8001/api/brain | python -m json.tool
curl -s -X POST http://localhost:8001/api/command \
  -H "Content-Type: application/json" \
  -d '{"command_type":"skill","skill_id":"hello","priority":0,"source":"studio_button"}'
curl -s -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"command_type":"chat","text":"你好","session_id":"test-123"}'
curl -s -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source":"face","event_type":"identity_stable","data":{"track_id":1,"stable_name":"小明","sim":0.92,"distance_m":1.2}}'
curl -s -X POST http://localhost:8001/mock/scenario/demo_a
```

Expected: All return JSON with `"status": "ok"` or valid data.

- [ ] **Step 2: Test WebSocket**

```bash
# If wscat is installed
wscat -c ws://localhost:8001/ws/events
# Should receive events every 2 seconds
```

- [ ] **Step 3: Test Frontend renders**

Open `http://localhost:3000/studio`:
1. Chat input visible at bottom
2. Events appearing in chat flow as inline cards
3. Panels appearing in sidebar when face/speech events arrive
4. Can type a message and get mock reply

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: PawAI Studio scaffold complete — ready for team handoff"
```

---

## Chunk 3: 真機閉環（下午獨立任務）

> 此 Chunk 與 Chunk 1-2 完全獨立，在 Jetson 上執行。

### File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `speech_processor/speech_processor/face_greet_node.py` | 人臉事件 → 語音打招呼 + wave 動作 |
| Modify | `speech_processor/setup.py` | 新增 entry_point |

---

### Task 14: Face → Greet → Wave Node

**Files:**
- Create: `speech_processor/speech_processor/face_greet_node.py`
- Modify: `speech_processor/setup.py`

- [ ] **Step 1: Create face_greet_node.py**

ROS2 node 訂閱 `/event/face_identity`（std_msgs/String, JSON），當 `event_type == "identity_stable"` 時：
1. 發布 `/tts`：「{stable_name}你好！」
2. 發布 `/webrtc_req`（WebRtcReq）：`api_id=1016`（wave 動作）

```python
"""人臉辨識 → 語音打招呼 + wave 動作"""
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from go2_interfaces.msg import WebRtcReq

class FaceGreetNode(Node):
    def __init__(self):
        super().__init__("face_greet_node")
        self.sub = self.create_subscription(
            String, "/event/face_identity", self.on_face_event, 10
        )
        self.tts_pub = self.create_publisher(String, "/tts", 10)
        self.webrtc_pub = self.create_publisher(WebRtcReq, "/webrtc_req", 10)
        self._last_greeted: dict[int, float] = {}  # track_id -> timestamp
        self._greet_cooldown = 30.0  # 同一人 30 秒內不重複打招呼
        self.get_logger().info("FaceGreetNode started")

    def on_face_event(self, msg: String):
        try:
            event = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if event.get("event_type") != "identity_stable":
            return

        data = event.get("data", {})
        track_id = data.get("track_id", -1)
        name = data.get("stable_name", "unknown")

        if name == "unknown":
            return

        # Cooldown check
        now = self.get_clock().now().nanoseconds / 1e9
        last = self._last_greeted.get(track_id, 0)
        if now - last < self._greet_cooldown:
            return

        self._last_greeted[track_id] = now

        # Publish TTS
        tts_msg = String()
        tts_msg.data = f"{name}你好！"
        self.tts_pub.publish(tts_msg)
        self.get_logger().info(f"Greeting: {name}")

        # Publish wave action
        wave_msg = WebRtcReq()
        wave_msg.api_id = 1016
        wave_msg.topic = ""
        wave_msg.parameter = "{}"
        self.webrtc_pub.publish(wave_msg)
        self.get_logger().info("Wave action sent")

def main(args=None):
    rclpy.init(args=args)
    node = FaceGreetNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add entry_point to setup.py**

Add `"face_greet_node = speech_processor.face_greet_node:main"` to `console_scripts` in `speech_processor/setup.py`.

- [ ] **Step 3: Build and source**

```bash
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
colcon build --packages-select speech_processor go2_robot_sdk
source install/setup.zsh
```

- [ ] **Step 4: Test on Jetson**

Terminal 1: Start Go2 driver
Terminal 2: Start face_identity_infer_cv.py
Terminal 3: `ros2 run speech_processor face_greet_node`
Terminal 4: `ros2 topic echo /tts`

Walk in front of camera → should see `/tts` publish "{name}你好！" and wave action on Go2.

- [ ] **Step 5: Commit**

```bash
git add speech_processor/
git commit -m "feat: add face_greet_node — face identity triggers greeting + wave"
```

---

## Execution Order

| 順序 | Task | 預估時間 | 環境 |
|:----:|------|---------|------|
| 1 | Task 1: Pydantic Schemas | 10 min | 開發機 |
| 2 | Task 2: Mock Server | 20 min | 開發機 |
| 3 | Task 3: Next.js Init | 5 min | 開發機 |
| 4 | Task 4: Design Tokens | 10 min | 開發機 |
| 5 | Task 5: TS Contracts | 10 min | 開發機 |
| 6 | Task 6: Zustand Stores | 15 min | 開發機 |
| 7 | Task 7: Hooks | 20 min | 開發機 |
| 8 | Task 8: Shared Components | 20 min | 開發機 |
| 9 | Task 9: Layout Components | 15 min | 開發機 |
| 10 | Task 10: ChatPanel | 25 min | 開發機 |
| 11 | Task 11: Panel Stubs | 10 min | 開發機 |
| 12 | Task 12: Wiring | 15 min | 開發機 |
| 13 | Task 13: Smoke Test | 10 min | 開發機 |
| 14 | Task 14: Face Greet Node | 20 min | Jetson |
