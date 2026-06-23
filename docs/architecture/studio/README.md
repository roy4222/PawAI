# PawAI Studio

**English** | [中文](./README.zh.md)

> **Governance header**
> - **Scope**: The single source-of-truth layer for the PawAI Studio frontend + Gateway + Mock Server (chat-first UI / WebSocket event stream / panel orchestration / scoreboard and provenance display).
> - **Status**: active / source-of-truth (Studio lane) — chat-first redesign landed (2026-05-04).
> - **Owner lane**: brain-studio-lane (`conversation_graph_node` / `interaction_executive` / tts / asr / studio gateway / frontend).
> - **Source-of-truth priority**: Whether a capability passes / whether it can enter the Brain mainline always defers to **(1) Measured evidence** `docs/runbook/baseline-evidence/2026-06-04-hitl/` (trusted, SHA `78fbf36`, readiness=not_ready) ＞ **(2) Convergence audit** `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` ＞ **(3) Capability spec** `docs/architecture/specs/2026-06-18-capability-baseline-spec.md` ＞ **(4) Strategic boundary** `docs/mission/2026-06-18-demo-north-star.md`. Studio's "what may be claimed / what may not be claimed" is bound to the canonical [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md). The ROS2 schema source-of-truth lives in [`docs/contracts/interaction_contract.md`](../../contracts/interaction_contract.md).
> - **Maintained child files**: [`CLAUDE.md`](CLAUDE.md) (working rules), [`AGENT.md`](AGENT.md) (interface contract), [`specs/README.md`](specs/README.md) (specs index: current / legacy / superseded), `specs/*`, `plans/*`.
> - **Archived / legacy boundary**: The RTX 8000 + Redis Event Bus topology in `specs/system-architecture.md` is **legacy** (it conflicts with the current Jetson FastAPI+rclpy direct connection in `pawai-studio/gateway/studio_gateway.py`, see specs index); the three `plans/2026-04-*` documents are **historical, already-implemented plans** (marked by a banner at the top). All of `docs/archive/2026-05-docs-reorg/` is frozen.
> - **What this README is NOT**: Not proof that a capability passes (Studio evidence shows **value but not a capability pass**, unless bound to trusted baseline data — see "Studio claim boundary" below); not a ROS2 contract (go to `docs/contracts/`); not a demo script (go to `docs/mission/README.md`); not frontend source code (in `pawai-studio/frontend/`).

> Status: current (chat-first redesign landed, 2026-05-04)

> ChatGPT-style pure conversation as the main view, 6 icon-only feature buttons that open a Sheet, `?dev=1` developer mode — the unified operation entry point for the embodied AI studio.

## Studio claim boundary (6/18, enforced)

> Studio is an **evidence carrier**, not a capability verifier. "Studio displaying a chip + trace + debug_image in the same frame" proves the demo is real-time perception and not hardcoded, which **has demonstration value**; but it **does not equal that capability passing** — `studio.evidence` itself is still ⚪ insufficient_data in the 6/04 trusted snapshot (n=0, not measured this round).

- **May claim**: Studio displays evidence / provenance (chip status + trace + debug_image), proving perception is real-time.
- **May not claim**: Treating "Studio displayed a green chip" as verification that "the capability passes"; marking `studio.evidence` as pass. A chip's pass/fail may only cite the trusted baseline (`docs/runbook/baseline-evidence/2026-06-04-hitl/`); Studio may not claim it on its own.
- **Source of truth**: What status each capability chip should display and what may be claimed links to the canonical [`docs/mission/2026-06-18-capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md); this file does not duplicate the whole thing.

## 6/4 Scoreboard / Provenance display (bound to trusted baseline)

> Studio's capability chips and provenance badges always use the **6/04 HITL trusted snapshot** as the sole data source (`docs/runbook/baseline-evidence/2026-06-04-hitl/`, SHA `78fbf36`, readiness=`not_ready`). A chip's color must not be decided as pass by the frontend / mock on its own; it can only reflect the trusted baseline's grade. The full claim boundary links to [`capability-claim-matrix.md`](../../mission/2026-06-18-capability-claim-matrix.md); the detailed measurement protocol links to [`capability-baseline-spec.md`](../specs/2026-06-18-capability-baseline-spec.md).

### The four capability-chip states (bound to 6/04 grades, not duplicating the whole matrix)

| chip state | color | corresponding 6/04 capability (trusted) |
|---|---|---|
| `pass` | green | face.recognition (narrow version, registered persons only) ｜voice.command (fixed command intent) ｜object.cup (**only ~1m close range, cup-only**) |
| `degraded` | orange | (no such state on 6/04, reserved for future narrow-version degradation) |
| `fail` | red | gesture.wave (recall=0.0, wave_pub=False) ｜voice.stop (success=0.667, **not a safety-stop**) |
| `insufficient` | gray | pose.basic / pose.fall｜nav.* (safe_stop / no_auto_resume / short_move / dynamic_avoidance)｜brain.skill_gate / brain.trace｜cli.readiness｜studio.evidence |

> **Chip copy discipline** (consistent with the claim matrix, no overclaiming):
> - face: recognizes only **registered acquaintances + greeting**; idle=empty scene, **does not display stranger rejection / guardian / "never misidentifies"**.
> - object: **only the object.cup close-range narrow version**; does not display generic object detection / object finding / color reliability.
> - voice.command: fixed-command intent classification; **does not display voice latency / mic_stop**.
> - voice.stop: currently **fail**; **must not be labeled safety-stop / emergency stop**.
> - gesture.wave: currently **fail**; static gestures (thumbs_up/ok) are a demo-only fallback, **not a gesture.wave pass**.
> - pose: **Studio-only / insufficient**; fall detection is future, **not an emergency behavior**.
> - nav: always **insufficient_data**; only displays the LiDAR point cloud / depth / map, **does not claim dynamic obstacle avoidance / autonomous movement**; the dry-run only proves fail-closed + action chain.
> - brain: may display deterministic safety / allowlist rejection (the mechanism exists + unit tested), **does not display "anti-hallucination pass" / "non-hallucinating autonomous agent"**.

### Provenance badge

A provenance badge is displayed next to each chip, indicating the data source and trustworthiness, to avoid misreading "the mechanism exists" as "verified end-to-end":

| badge | meaning |
|---|---|
| `trusted: 6/04 HITL (78fbf36)` | From the trusted snapshot, can serve as a pass/fail basis |
| `insufficient: n=0` | Not measured this round, no grade may be claimed |
| `live (unverified)` | On-site real-time event stream, **display only**, not baseline verification |
| `mock` | Generated by mock_server, pure UI / offline testing, **must never count as capability evidence** |

> ⚠️ All events in mock mode (`start-live.sh --mock`) carry `mock` provenance, and **must under no circumstances count as capability pass evidence**. The 6/03 first-trusted-face snapshot is **historical**, has been superseded by 6/04, and no longer serves as a chip data source.

## Status card

| Item | Value |
|------|---|
| Status | **chat-first redesign landed + mock chat Gemini round-trip passed** (5/4) |
| Version/decision | Next.js 16 + React 19 + Tailwind v4 + `@base-ui/react` 1.3 + lucide-react (frontend) / FastAPI + rclpy (Gateway) / FastAPI mock_server (offline testing + opt-in OpenRouter) |
| Completeness | Main view ChatGPT-style pure conversation ✅ + 6 nav modal Sheet ✅ + Dev mode (`?dev=1` / `/studio/dev`) ✅ + Mock really connects to Gemini ✅ + design tokens (dark only) ✅ + a11y polish ✅ |
| Last verified | 2026-05-04 (mock mode 3-sentence real chat round-trip + tsc 0 errors + npm build pass + 221 tests PASS) |
| Entry-point files | `pawai-studio/gateway/studio_gateway.py` (for Jetson), `pawai-studio/backend/mock_server.py` (for local testing), `pawai-studio/frontend/` (frontend) |
| Tests | Gateway 18 + mock_text_input 8 + openrouter_chat 16 + interaction_executive 138 + speech_processor 44 = 221 tests PASS, tsc 0 errors |

## How to start (after 5/4)

```bash
# Three modes managed uniformly by start-live.sh
bash pawai-studio/start-live.sh                    # auto（推薦）— 探測 Jetson，未通自動降級為 mock
bash pawai-studio/start-live.sh --live             # 強制連 Jetson gateway
bash pawai-studio/start-live.sh --mock             # 強制本機 mock_server (port 8080)

# 開啟真聊天（call OpenRouter Gemini 3 Flash）— 需 .env 有 OPENROUTER_KEY
set -a && . ./.env && set +a
MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock

# Banner 會印實際 frontend port（Next 在 3000 被占時 fallback 3001/3002，
# 已偵測真實 port 顯示，不再寫死 3000）
```

> In Live mode the Gateway defaults to `http://YOUR_JETSON_IP:8080` (Tailscale), overridable with `GATEWAY_HOST=<ip>`.

## Core flow

```
使用者操作（Chat / 技能按鈕 / 面板）
    ↓
Studio Frontend (Next.js React) ← 5 panel + nav map 面板（6/9 Task A: map v8+pose 三角形+固定 goal+直線，Canvas2D，display-only 不宣稱自走/避障）+ Live View 三欄影像
    ↓ WebSocket /ws/events（JSON 事件流）
    ↓ WebSocket /ws/video/{source}（JPEG binary 影像流）
    ↓ WebSocket /ws/text + /ws/speech（瀏覽器→ROS2）
Studio Gateway (FastAPI + rclpy, Jetson:8080)
    ↓ rclpy subscribe 5 event topics + 3 Image topics + 3 nav state topics（6/9 Task A，latched）+ publish speech intent
ROS2 Topics（face/speech/gesture/pose/object + 3 debug_image + nav: /amcl_pose[latched TRANSIENT_LOCAL] · /state/reactive_stop/status · /state/nav/paused）
```

## Main-view architecture (5/4 chat-first redesign)

| Area | Content |
|------|------|
| Top navbar | Logo "PawAI Studio" / 6 icon-only feature buttons / LIVE link / connection indicator |
| Status pill | Centered thin pill: Brain {mode} · obs:ok emg:ok fall:ok tts:idle |
| Main chat | ChatGPT-style — user bubble cyan (right) / AI bubble transparent + thin outline (left) + Sparkles avatar |
| Bottom composer | textarea + mic + send button (max-w-3xl centered) |
| Floating ⚙ | Appears only with `?dev=1` (44×44 a11y touch target) |

**6 feature buttons → click to open a Sheet (changed to a center modal from 5/5; the old right-side drawer was a transition when it landed)**:

| icon | label | Sheet content |
|------|-------|----------|
| User | Face recognition | `<FacePanel />` |
| Mic | Speech features | `<SpeechPanel />` |
| Hand | Gesture recognition | `<GesturePanel />` |
| PersonStanding | Pose recognition | `<PosePanel />` |
| Box | Object recognition | `<ObjectPanel />` |
| Compass | Navigation & obstacle avoidance | `<NavigationPanel />` (Nav Gate / Depth Gate / Plan A/B three chips) |

Below the `< md` breakpoint they automatically collapse into the top-right hamburger menu (a single Menu icon → opens the "nav-menu" Sheet listing 6 buttons).

## Modal-mode migration (5/5 sidebar → center modal)

**Current state** (landed 5/4): The Sheet slides in from the right (`md:right-0 md:top-0 md:h-screen md:w-[var(--sheet-w)]` 380px wide, desktop fixed right column; mobile slides up from the bottom).

**Target** (5/5+): center modal — a centered card form, closer to the "focus on one panel" visual the demo presentation needs, avoiding the right column covering the main conversation area.

```tsx
// 預計改 components/ui/sheet.tsx 約 L60-72：
// 從  "md:inset-x-auto md:bottom-0 md:top-0 md:right-0 md:h-screen md:w-[var(--sheet-w)] md:rounded-l-2xl"
// 改為 "md:inset-0 md:flex md:items-center md:justify-center md:p-6"
//      + 內層卡片 "max-w-3xl w-full max-h-[85vh] rounded-2xl bg-[var(--sheet-bg)]"
```

**Template reference**: PR #41's pose history modal already uses the center style (`fixed inset-0 bg-black/65` backdrop + inner card), which can be copied directly as a baseline.

**Scope of impact**:
- The 6 panels' trigger paths do not change (still use `useSheetStore.open(value)`)
- mobile behavior keeps the bottom slide (the `< md` breakpoint is unchanged)
- backdrop opacity / animation token reuses the existing `--anim-sheet-slide` (CSS var unchanged)

## Routes

| Route | Purpose | nav display |
|-------|------|---------|
| `/studio` | **Chat main view** (ChatGPT-style) | ✅ default home page |
| `/studio/live` | Live camera three-column images (Foxglove replacement) | ✅ top-right LIVE link |
| `/studio/dev` | Developer full page — Skill Console + SkillTraceContent | ❌ hidden, direct URL access |
| `/studio?dev=1` | Main view floats ⚙ → click to open Dev Sheet (same dev panel content) | ❌ flag-only |
| `/studio/{face,gesture,object,pose,speech}` | Legacy single-page panels — files kept for direct URL access | ❌ hidden from nav |

**Key design**: dev mode is a session-wide flag — any `/studio/*?dev=1` will float ⚙, but the `/studio/dev` page itself does not float (a pathname guard avoids a duplicate entry point).

### Live View (`/studio/live`)

A Foxglove replacement display wall. Three-column real-time images + minimal overlay + event ticker:

- **Left column**: `/face_identity/debug_image` (face box + name + similarity)
- **Center column**: `/vision_perception/debug_image` (skeleton + gesture + pose)
- **Right column**: `/perception/object/debug_image` (YOLO box + class)
- **Bottom**: Event ticker (real-time event scrolling bar)
- **Top**: Gateway connection status + Jetson temperature

Images go over a dedicated WebSocket binary stream (`/ws/video/{source}`), events go over `/ws/events` JSON, without interfering with each other.

### Chat closed loop (after 5/4)

Two paths: **Live mode** goes through the Jetson real ROS2 pipeline, **Mock mode** can optionally opt-in to really call Gemini:

**Live mode**:
```
文字/語音 → Gateway POST /api/text_input 或 WS /ws/speech
→ ROS2 /brain/text_input → llm_bridge_node._try_openrouter_chain
→ Gemini 3 Flash（fallback: DeepSeek V4 → vLLM Qwen-7B → Ollama → RuleBrain）
→ /tts publish → Gateway 訂閱 → /ws/events broadcast
→ ChatPanel useEffect on lastTtsText → render AI bubble
```

**Mock mode** (`bash pawai-studio/start-live.sh --mock`):
- Offline by default: returns say_canned("我聽不太懂") + " (mock)" marker
- `MOCK_OPENROUTER=1` opt-in: mock_server directly calls Gemini 3 Flash (via `tools/llm_eval/openrouter_chat.py`, no ROS dependency)
- Both modes broadcast the `tts:tts_speaking` event to ChatPanel for rendering (mirroring the real Jetson behavior)

**Important implementation points**:
- ChatPanel `pendingRequestIdRef` is armed **before** the `await fetch` (to avoid a race — within ~2s of Gemini responding, the tts event may arrive earlier than the fetch resolves)
- The pending 8s timeout falls back to a "回應逾時" inline message
- During recording it shows 7 volume bars (Web Audio AnalyserNode)
- Known limitation: `/tts` has no correlation id, so during the pending window other TTS may be mistaken for the reply

## Gateway / Mock endpoints

> The Gateway has added CORS middleware (`allow_origins=["*"]`) since the night of 5/7, so the Studio frontend on a laptop (e.g. `YOUR_LAPTOP_IP:3000`) POSTing to the Jetson Gateway (`192.168.x.x:8080`) will not be blocked by the browser. WebSocket is not subject to CORS, and all `/ws/*` are always available. Acceptable risk on the demo intranet (commit `67c28ce`).


| Endpoint | Direction | Purpose | live | mock |
|------|------|------|:----:|:----:|
| `GET /health` | — | Health check | ✅ | ✅ |
| `WS /ws/events` | ROS2→browser | Perception event broadcast + brain proposal/result + capability + tts | ✅ | ✅ |
| `POST /api/text_input` | browser→ROS2 | Text input → /brain/text_input (live) / Gemini call (mock + MOCK_OPENROUTER). **Added a return `text` field on the night of 5/9**: the gateway returns it after applying s2twp, the frontend updates the user bubble to display Traditional Chinese (issue 6 frontend follow-up) | ✅ | ✅ |
| `POST /api/skill_request` | browser→ROS2 | Studio button triggers a skill | ✅ | ✅ |
| `GET /api/skill_registry` | — | 26+1 SKILL_REGISTRY JSON (active/hidden/disabled/retired buckets) | ✅ | ✅ |
| `GET/POST /api/capability` | — | tri-state capability snapshot (mock can POST to change values to test the UI) | ✅ live read-only | ✅ both |
| `GET/POST /api/plan_mode` | — | Plan A/B toggle (in-memory flag) | ✅ | ✅ |
| `WS /ws/speech` | browser→ROS2 | Recording → ASR (added OpenCC s2twp Traditional conversion on 5/9) → intent (5MB cap) | ✅ | ✅ |
| `WS /ws/video/{face,vision,object}` | ROS2→browser | JPEG binary debug images | ✅ | ❌ |
| `GET /speech` | — | Standalone push-to-talk test page | ✅ | ✅ |
| `POST /api/reset` | browser→ROS2 | **Added 5/9**: reset the conversation context — publish `/brain/reset_context` (std_msgs/Empty), conversation_graph_node clears `_memory + _seen_sessions`, brain_node cancels `_pending_confirm`. **Does not clear** `_active_plans` / `_state.attention`. | ✅ | ✅ |
| `GET /api/trace/export` | — | **Added 6/12 (Evidence Center first slice)**: streams `runtime/traces/*.jsonl` (x-ndjson). `?since=<ts>` filters, `?redact=0` full export. Auth exception rules see the next section. | ✅ | ❌ |

### 6/12 addendum: Evidence Center first slice (system Phase 2 / 2B, PR #161)

> Truth chain (Roy D5): schema=`pawai_contracts.trace_schema`, emission=Brain/IE,
> **persistence=gateway, CLI read-only**. This section documents the three things: persistence/export/presentation.

- **Persistence**: `gateway/trace_store.py` (a ROS-free pure module). `/brain/trace` events are **fully**
  written to `runtime/traces/{session_id}.jsonl` (Jetson local machine only); `append()` only enqueues
  (zero file I/O in the ROS callback), and a daemon writer flushes every second; each file rotates at ~20MB, keeping the newest
  20 files. Env: `PAWAI_TRACE_STORE_ENABLED=0` disables it (back to a pure bridge), `PAWAI_TRACE_DIR`
  changes the path. deploy will not clear it (since 6/12 `tools/sync/rsync-excludes.txt` excludes
  `runtime/` + `artifacts/`).
- **Conservative PII default (T2B-0, decided by Roy on 6/12)**: any **off-device** path (`/ws/events` broadcast +
  default export) always passes through `redact_trace_event()` — `source_summary`/`transcript`/
  `name`/`image_path` etc. → `[private]`, name segments within reason are masked
  (`cooldown:greet:Roy`→`cooldown:greet:[private]`); gate/kind/verdict/ism_*
  and other safe summaries remain visible as usual.
- **Export auth (A-11)**: `auth.export_access()` — when auth-on, GET export **does not get**
  the S0-2 safe-method exemption (no token → 401); `redact=0` full export when the token system
  is disabled is always **403** (PII never leaves the device unauthenticated); under the default-off posture redacted export
  is open.
- **Frontend viewer**: `brain:trace` events from `/ws/events` → `brainTraces` store slice
  (cap 50) → the "為什麼沒反應 · Suppressed" area of `SkillTraceContent`
  (shared by the DevPanel sheet and `/studio/dev`; ISM shadow events carry a purple `shadow` badge).
- **CLI integration**: `pawai evidence pull` (see `docs/pawai_cli/README.md`).
- **6/12 on-device verification**: JSONL 46→192 lines, export redacted 200 / full without auth 403 /
  `since` filter ✓, the WS stream contains the shadow marker and `[private]` ✓ (checkpoint report §8).
- The Mock server does not have this endpoint (the STUDIO-4 trace simulation row is an optional follow-up, not part of the first slice).

### 5/9 addendum: "New conversation" button + dev-only F5 auto-detect (issue 7)

The ChatPanel header adds a "新對話" button (`handleNewConversation`); on click:
1. `window.confirm("將清除目前所有對話記憶，包括其他開啟的 Studio 視窗。確定？")`
2. `fetch('/api/reset', {method: 'POST'})` → backend clears brain memory + seen_sessions
3. `setMessages([])` clears frontend messages
4. `useStateStore.setState({ ttsMessages: [] })` clears the ring buffer
5. `lastSeenTtsIdRef.current = null`

**Dev-only F5 hybrid auto-detect** (off by default for demos):
- env flag `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=false` (default)
- set `=true` to enable: layout registers `beforeunload` to write `sessionStorage.paw_refresh_at`, `use-websocket.ts onopen` checks within 5s → auto POST `/api/reset`
- During demos it is recommended to rely on the manual button, because brain memory is a global singleton, and a single F5 on one machine will clear the whole brain

### 5/9 night addendum: ChatPanel stick-to-bottom (issue 9)

`chat-panel.tsx` originally had `useEffect(() => bottomRef.scrollIntoView(), [messages, isThinking])` which unconditionally pulls the view back to the bottom every time messages change, so when a user scrolls up to see old messages they get interrupted by new ones.

Fix (commit `87e2d5d`): mimic the Slack/Discord stick-to-bottom pattern
- add `scrollContainerRef` + `shouldAutoScrollRef`
- the scroll container's `onScroll` handler: `scrollHeight - scrollTop - clientHeight < 30` counts as "attached to the bottom"
- change the useEffect condition to `if (shouldAutoScrollRef.current) bottomRef.scrollIntoView()`

Verification: talk 10 sentences in a row with the dog, scroll up to see the 1st sentence → incoming messages will not pull the view back to the bottom; scroll back to the very bottom → incoming messages auto-follow.

### 5/10 night addendum: Composer absolute-bottom layout refactor (Spec 6 P0)

After the 5/9 stick-to-bottom fix, real-world testing showed that although the scroll behavior was correct, the composer (input box) would be pushed off the bottom of the viewport, and sending a long message had a blank catch-up window. A series of attempts (`flex h-full flex-col overflow-hidden` + `min-h-0` + `shrink-0` + `behavior: "auto"` + `isAutoScrollingRef` to lock programmatic scroll events) only solved some of the symptoms.

Root cause: the composer is in the message flex flow and relies on flex sizing to maintain its position; any of textarea auto-grow / skill strip toggle / a sudden surge of messages will cause a small jump.

Fix (commit `fdd5c93`): extract Composer + ChatGPT-like absolute layout
- new file `components/chat/composer.tsx` — a pure view, props feed state/handlers, the `useAudioRecorder` owner remains in ChatPanel
- ChatPanel conversation view root: `relative h-full overflow-hidden`
- three-layer structure:
  - header (normal flow, `headerRef` measures height)
  - scroll area (`absolute inset-x-0` + dynamic `style={{ top: headerH, bottom: composerBarH }}`)
  - composer bar (`absolute inset-x-0 bottom-0 z-20` wrapping skill strip + Composer)
- `ResizeObserver` observes header + composer bar, writing into useState; initial values 44/96 to avoid the first frame's top:0 covering the header
- z-index convention: composer z-20 < DevButton z-30 < Sheet z-40/50 (driven by dev-button.tsx:22)
- empty state is unchanged (hero + composer centered)

Design plan: `~/.claude/plans/subagent-pawai-studio-frontend-vectorized-bunny.md`
Acceptance document: Spec 6 checklist §4

Verification: 4/4 cases pass + composer always sticks to the bottom + when typing a long message the composer grows / the scroll bottom shrinks accordingly + DevButton z-30 is not covered.

### 5/9 night addendum: OpenCC API name silent fail fix

`text_normalization.py` (in both gateway + speech_processor) originally had `OpenCC("s2twp.json")`, and `opencc-python-reimplemented` automatically appends `.json` → tries to load `s2twp.json.json` → FileNotFoundError → falls into the except → silently falls back to the original text.

Fix: change to `OpenCC("s2twp")`. Since PR #52, all three ASR / text Simplified→Traditional entry points had been silently failing, and this was only caught now (commit `756aeb0`).

### 5/9 addendum: ChatPanel full-utterance display (issue 5) — already smoke-confirmed on 5/8

state-store `ttsMessages: TtsMessage[]` is a 200-entry ring buffer + dedup by id + rate-limit (spontaneous 5s/source; bypass `chat_reply` / `skill_say` / `say_canned`). ChatPanel listens for `ttsMessages` array appends (no longer using `pendingRequestIdRef` to gate display). Three CSS colors: `source=skill_say` green / `say_canned` orange / `chat_reply or pending` normal gray / no-source spontaneous light gray + ⏰ icon.

The source field is injected into the SAY step args by `interaction_executive/skill_contract.py:_resolve_say_source()` during `build_plan`, the IE-node `_dispatch_step` carries it into the `/tts` JSON envelope, and after the gateway `_parse_tts_payload` parses it, `build_tts_event` carries it into the ws/events broadcast.

## 4-PR frontend consolidation plan (from 5/5, `B6-1 ~ B6-4`)

Per the MOC spec: the 4 perception features each have an independent PR on GitHub, and the frontend code is consolidated into each of this studio's respective pages. **Not a wholesale move** — pick the clean parts to integrate into the existing panels; the backend Python (`pose_infer_server.py` etc.) is not copied, going through the existing ROS2 pipeline.

| PR | Title | Main new files / copy-in strategy | Notes |
|---|---|---|---|
| **[#38](https://github.com/roy4222/PawAI/pull/38) Gesture (Yamiko)** | Gesture recognition panel + WS image stream | Copy `components/gesture/local-camera-card.tsx` (87L) + the WS image pattern → integrate into the existing `gesture-panel.tsx` | Discard the PR's changes to ChatPanel (the chat logic was finished with the chat-first redesign on 5/4) |
| **[#40](https://github.com/roy4222/PawAI/pull/40) Object (object_syu)** | YOLO detection + tab UI (Detect/History/Whitelist) | Copy all 6 components: `components/object/{local-camera, object-config, history-feed, live-detection, object-stats, object-event}.tsx` (~751L) + `lib/object-event.ts`; refactor object-panel.tsx to be tab-based | **Largest PR** (+2295/-143), the most worth carefully aligning with contracts/types.ts |
| **[#41](https://github.com/roy4222/PawAI/pull/41) Pose (Gua)** | MediaPipe pose + history modal | Copy `components/pose/{pose-client, pose-mapper, pose-types, use-pose-stream}.ts`; the history modal pattern **serves as the studio-wide center modal template** | `pose_infer_server.py` is not copied (backend Python is out of scope; goes through the existing vision_perception ROS2 pipeline) |
| **[#42](https://github.com/roy4222/PawAI/pull/42) Speech (Katie)** | dual-layout speech panel + ASR/LLM/TTS bridge | **Not a wholesale copy**; only copy the `useAudioRecorder` hook improvement (hooks/use-audio-recorder.ts +14/-1) | Conflicts with the ChatPanel mic; the division of labor is specified below |

### Resolving the PR #42 speech vs ChatPanel mic conflict

> MOC §10 is explicit: "PR #42 overlaps with the PawAI Brain × Studio home page; design the frontends separately"

**Division of labor**:

| Component | Path | mic usage | WebSocket | Conflict guarantee |
|---|---|---|---|---|
| **ChatPanel** | `/studio` home page main conversation | The user's voice conversation entry point | gateway `/ws/events` + `/ws/speech` (port 8080) | The only mic on the main view |
| **SpeechPanel** | `/studio/speech` standalone dev page + Sheet panel | dev/debug usage, to see ASR/intent/TTS details | Still goes through the gateway by default; PR #42's `/ws/speech_interaction:5000` is not adopted (to avoid dual WebSockets) | Sheet/Modal mutual exclusion — when SpeechPanel is open the main view is already covered by a modal |

**What we will not attempt**: merging the two audio pipelines, auto-switching the mic owner, sharing a React audio context — all over-engineering; relying on modal mutual exclusion is the simplest guarantee.

## Dev mode (after 5/4)

The chat main view has **absolutely no** dev elements by default. The ⚙ button (44×44) floats only when the `?dev=1` flag appears in the URL; `/studio/dev` is the full-page direct-access entry point. The content is the same `<SkillTraceContent />` + `<SkillButtons />`.

### Component tree

```
StudioLayout (root mount)
├─ NavTabbar
│  ├─ FeatureNav (6 icon-only buttons + mobile hamburger)
│  └─ LIVE link + LiveIndicator
├─ <main>{children}</main>
├─ FeatureSheet (single Sheet driven by sheet-store)
│  ├─ FacePanel | SpeechPanel | GesturePanel | PosePanel
│  ├─ ObjectPanel | NavigationPanel | DevPanel
│  └─ NavMenuList (mobile hamburger inline branch)
└─ DevButton (?dev=1 + pathname guard)
```

### Brain widgets (files kept, but ChatPanel never renders them)

`components/chat/brain/{bubble-*.tsx, brain-status-strip.tsx, skill-buttons.tsx, skill-trace-drawer.tsx, skill-trace-content.tsx}` are all kept, used only by the dev panel / dev page. **The chat stream is always clean**, and the user does not see brain debug.

`SkillTraceContent` (extracted 5/4) = pure trace + GateChip + Plan toggle rendering, without the drawer toggle. `SkillTraceDrawer` is a legacy collapsible wrapper that internally renders `SkillTraceContent`. Shared + avoids drawer-in-sheet nesting.

### Phase 0.5 Conversation Trace chips (5/6 night, commit `c65db0d`)

`SkillTraceContent` adds a **Conversation Trace · N** block below the existing brain proposals list, rendering the two topics `/brain/conversation_trace` and `/brain/conversation_trace_shadow` (the gateway already added them to topic_map in commit `fe0297e`).

| Status | color | trigger |
|---|---|---|
| `accepted` / `ok` | emerald-500/20 | brain accepts the LLM proposal and actually executes (e.g. `show_status` / `wave_hello` / `sit_along` / `careful_remind` / `greet_known_person`) |
| `accepted_trace_only` | emerald-50/20 | brain accepts but the policy is trace_only (`self_introduce` does not auto-run motion, the 10-step sequence goes through a Studio button) |
| `proposed` | slate | the engine generated the proposal (pre-gate) |
| `needs_confirm` | yellow-500/20 | **Added 5/8** — confirm-mode skills like wiggle / stretch: brain_node has already `_pending_confirm.request_confirm`, waiting for the user to gesture OK before executing |
| `demo_guide` | blue-500/20 | **Added 5/8** — kind=demo_guide proposals (the 6 pseudo-skills face / speech / gesture / pose / object / navigation), pure trace not entering chat_candidate / proposal |
| `blocked` / `fallback` / `retry` | amber | cooldown / safety / OpenRouter fallback chain (including the 5/8 capability layer's `blocked:not_in_capability_context`, blocking an unknown-but-allowlisted skill at the pawai_brain layer) |
| `rejected_not_allowed` / `error` | rose | the proposal is not in the brain `LLM_PROPOSABLE_SKILLS` allowlist (expanded to 8 on 5/8) |

Event flow:
```
/event/speech_intent_recognized
  → llm_bridge_node（output_mode=brain）
  → /brain/chat_candidate { reply_text, proposed_skill, ... , engine: "legacy" }
  → brain_node._on_chat_candidate
  → 永遠先 enqueue chat_reply
  → 提案另走 allowlist → /brain/proposal + /brain/conversation_trace
  → studio_gateway → WS event_type="conversation_trace" / "conversation_trace_shadow"
  → use-event-stream.ts → state-store.appendConversationTrace
  → SkillTraceContent
```

Detailed Schema + status enum: `docs/contracts/interaction_contract.md` v2.7 (Phase 0.5 section) + spec `docs/architecture/specs/2026-05-06-conversation-engine-langgraph-design.md` §4.

### Brain topic ↔ UI mapping

| subscribe ROS2 → broadcast WS | Studio rendering location |
|------------------------|----------------|
| `/state/pawai_brain` | BrainStatusPill (top of chat) + SkillTraceContent World flags |
| `/brain/proposal` | SkillTraceContent proposals list (dev only) |
| `/brain/skill_result` | SkillTraceContent (dev only) |
| `/capability/{nav_ready,depth_clear}` | NavigationPanel GateChip + SkillTraceContent header |
| `/tts` | ChatPanel `lastTtsText` → AI bubble |

### Design tokens

`pawai-studio/frontend/lib/design-tokens.ts` + the "Chat-first redesign tokens" block inside `app/globals.css`. dark mode only, the CSS var namespace:

- `--bubble-user-bg` (cyan #0EA5E9) / `--bubble-user-fg` / `--bubble-ai-border`
- `--pill-bg` / `--pill-border` / `--pill-fg` / `--pill-fg-emphasis`
- `--nav-icon-fg` / `--nav-icon-active-fg` (cyan) / `--nav-icon-hover-bg`
- `--sheet-bg` / `--sheet-border` / `--sheet-backdrop`
- `--dev-button-bg` / `--dev-badge-bg` (amber)
- `--gate-ok` / `--gate-block` / `--gate-unknown` (tri-state)
- `--anim-sheet-slide` / `--anim-message-appear` / `--anim-bubble-hover` (`@media prefers-reduced-motion` automatically backs off to 0ms)

Full rationale: [`specs/2026-05-04-design-tokens.md`](specs/2026-05-04-design-tokens.md)

## Architecture references (external)

> MOC §10 lists explicitly: this studio architecture is inspired by [openclaw](https://github.com/openclaw/openclaw) + [hermes-agent](https://github.com/nousresearch/hermes-agent), with the goal of being "not just a chatbot, but having the actual ability to decide what action to take".

### OpenClaw correspondence points

| OpenClaw concept | PawAI Studio correspondence |
|---|---|
| Gateway abstraction (device → API → web) | `pawai-studio/gateway/studio_gateway.py` (FastAPI + rclpy) |
| Typed event (a unified schema for multimodal events) | `frontend/contracts/types.ts` + `backend/schemas.py` |
| Lifecycle / capability gate | `/capability/{nav_ready,depth_clear}` + GateChip |
| Centralized skill registry management | `GET /api/skill_registry` returns the 26+1 SKILL_REGISTRY |

### Hermes-Agent correspondence points

| Hermes concept | PawAI correspondence |
|---|---|
| LLMProvider adapter (multiple providers, same interface) | `llm_bridge_node._try_openrouter_chain` five-level fallback |
| TTSProvider adapter | `speech_processor/tts_node` Stage 4 chain (Despina → edge_tts → Piper) |
| Persona / system prompt templating | `say_template` references the `{name}` / `{class}` / `{color}` variables |
| Tool call → action arbitration | Brain proposal → SafetyLayer → `/skill_result` (the sole action exit) |

**Boundary**: the above is an **inspiration reference**, not a direct fork of the code. PawAI takes an independent architecture, avoiding a dual source-of-truth for the Python ↔ TS skill registry.

## Known issues

- Object accuracy is limited by YOLO26n (low small-object detection rate, the yolo26s upgrade is scheduled later)
- Face greeting triggers repeatedly (the same person gets greeted multiple times in a short period, the cooldown needs adjustment)
- Jetson power is unstable (the XL4015 step-down issue, a demo risk item)
- The `/tts` event has no correlation id — during the pending window other TTS may be mistaken for the reply
- The Sheet does not have a swipe-to-close handle wired up (Base UI Dialog.Handle is known to exist, a phase C bonus)
- The voice bubble visual is the same color as the user bubble + cyan border is visually redundant (feedback doc follow-up)

## Next steps (5/5+)

- **B6-1 ~ B6-4 PR consolidation** (see the "4-PR frontend consolidation plan" section; MOC §10 correspondence):
  - B6-1 PR #38 gesture local-camera-card → gesture-panel.tsx
  - B6-2 PR #40 object 6 components + tab UI refactor
  - B6-3 PR #41 pose usePoseStream hook + center modal pattern template
  - B6-4 PR #42 speech partial consolidation (useAudioRecorder + ChatPanel/SpeechPanel separation)
- **Modal-mode migration** (sheet right-side → center modal) — planned to be done together with B6-3
- **Jetson session**: on-device smoke the OpenRouter Gemini chain (commit `fda1b3c`) + Go2 real TTS hardware + 8-scene Plan A/B back-to-back runs
- B7: 60 min continuous power stress test
- Full voice → ASR → LLM → TTS → Megaphone E2E
- The follow-up items from the ui-ux-pro-max review feedback (voice bubble visual, Sheet swipe handle, Sheet header glass) — phase C scope

## Subfolders

| Folder | Content |
|--------|------|
| specs/ | brain-adapter, event-schema, system-architecture, ui-orchestration designs |
