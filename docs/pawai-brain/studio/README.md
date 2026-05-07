# PawAI Studio

> Status: current（chat-first redesign 已落地，2026-05-04）

> ChatGPT 風純對話為主畫面、6 個 icon-only feature button 開 Sheet、`?dev=1` 開發者模式 — embodied AI studio 統一操作入口。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **chat-first redesign 落地 + mock chat 接 Gemini round-trip 通過**（5/4） |
| 版本/決策 | Next.js 16 + React 19 + Tailwind v4 + `@base-ui/react` 1.3 + lucide-react（前端）/ FastAPI + rclpy（Gateway）/ FastAPI mock_server（離線測試 + opt-in OpenRouter）|
| 完成度 | 主畫面 ChatGPT 風純對話 ✅ + 6 nav modal Sheet ✅ + Dev mode（`?dev=1` / `/studio/dev`）✅ + Mock 真接 Gemini ✅ + design tokens（dark only）✅ + a11y polish ✅ |
| 最後驗證 | 2026-05-04（mock 模式 3 句真 chat round-trip + tsc 0 errors + npm build pass + 221 tests PASS） |
| 入口檔案 | `pawai-studio/gateway/studio_gateway.py`（Jetson 用）、`pawai-studio/backend/mock_server.py`（本機測試用）、`pawai-studio/frontend/`（前端） |
| 測試 | Gateway 18 + mock_text_input 8 + openrouter_chat 16 + interaction_executive 138 + speech_processor 44 = 221 tests PASS、tsc 0 errors |

## 啟動方式（5/4 後）

```bash
# 三種模式由 start-live.sh 統一管理
bash pawai-studio/start-live.sh                    # auto（推薦）— 探測 Jetson，未通自動降級為 mock
bash pawai-studio/start-live.sh --live             # 強制連 Jetson gateway
bash pawai-studio/start-live.sh --mock             # 強制本機 mock_server (port 8080)

# 開啟真聊天（call OpenRouter Gemini 3 Flash）— 需 .env 有 OPENROUTER_KEY
set -a && . ./.env && set +a
MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock

# Banner 會印實際 frontend port（Next 在 3000 被占時 fallback 3001/3002，
# 已偵測真實 port 顯示，不再寫死 3000）
```

> Live mode 預設 Gateway = `http://100.83.109.89:8080`（Tailscale），可用 `GATEWAY_HOST=<ip>` override。

## 核心流程

```
使用者操作（Chat / 技能按鈕 / 面板）
    ↓
Studio Frontend (Next.js React) ← 5 panel 即時顯示 + Live View 三欄影像
    ↓ WebSocket /ws/events（JSON 事件流）
    ↓ WebSocket /ws/video/{source}（JPEG binary 影像流）
    ↓ WebSocket /ws/text + /ws/speech（瀏覽器→ROS2）
Studio Gateway (FastAPI + rclpy, Jetson:8080)
    ↓ rclpy subscribe 5 event topics + 3 Image topics + publish speech intent
ROS2 Topics（face/speech/gesture/pose/object + 3 debug_image）
```

## 主畫面架構（5/4 chat-first redesign）

| 區域 | 內容 |
|------|------|
| Top navbar | Logo 「PawAI Studio」 / 6 個 icon-only feature button / LIVE link / 連線 indicator |
| Status pill | 居中 thin pill：Brain {mode} · obs:ok emg:ok fall:ok tts:idle |
| Main chat | ChatGPT 風 — user bubble cyan（右）/ AI bubble transparent + thin outline（左）+ Sparkles avatar |
| Bottom composer | textarea + mic + send button（max-w-3xl 居中） |
| Floating ⚙ | 只有 `?dev=1` 才浮現（44×44 a11y touch target） |

**6 個 feature button → 點開 Sheet（5/5 起改 center modal；舊 right-side drawer 落地時為過渡）**：

| icon | label | Sheet 內容 |
|------|-------|----------|
| User | 人臉辨識 | `<FacePanel />` |
| Mic | 語音功能 | `<SpeechPanel />` |
| Hand | 手勢辨識 | `<GesturePanel />` |
| PersonStanding | 姿勢辨識 | `<PosePanel />` |
| Box | 辨識物體 | `<ObjectPanel />` |
| Compass | 導航避障 | `<NavigationPanel />`（Nav Gate / Depth Gate / Plan A/B 三 chip）|

`< md` breakpoint 自動收進右上 hamburger menu（一顆 Menu icon → 開「nav-menu」Sheet 列出 6 條 button list）。

## 跳窗模式遷移（5/5 sidebar → center modal）

**現況**（5/4 落地）：Sheet 從右側滑入（`md:right-0 md:top-0 md:h-screen md:w-[var(--sheet-w)]` 380px 寬，desktop fixed 右欄；mobile 從底部上滑）。

**目標**（5/5+）：center modal — 卡片形式置中，更接近 demo 演示需要的「focus 一個 panel」視覺，避免右側欄遮住主對話區。

```tsx
// 預計改 components/ui/sheet.tsx 約 L60-72：
// 從  "md:inset-x-auto md:bottom-0 md:top-0 md:right-0 md:h-screen md:w-[var(--sheet-w)] md:rounded-l-2xl"
// 改為 "md:inset-0 md:flex md:items-center md:justify-center md:p-6"
//      + 內層卡片 "max-w-3xl w-full max-h-[85vh] rounded-2xl bg-[var(--sheet-bg)]"
```

**範本參考**：PR #41 pose history modal 已用 center 樣式（`fixed inset-0 bg-black/65` backdrop + 內層 card），可直接抄為 baseline。

**影響範圍**：
- 6 panel 觸發路徑不動（仍用 `useSheetStore.open(value)`）
- mobile 行為保留 bottom slide（`< md` breakpoint 不變）
- backdrop opacity / animation token 沿用既有 `--anim-sheet-slide`（CSS var 不變）

## Routes

| Route | 用途 | nav 顯示 |
|-------|------|---------|
| `/studio` | **聊天主畫面**（ChatGPT 風） | ✅ 預設首頁 |
| `/studio/live` | Live camera 三欄影像（Foxglove 替代） | ✅ 右上 LIVE link |
| `/studio/dev` | 開發者全頁 — Skill Console + SkillTraceContent | ❌ 隱藏，URL 直連 |
| `/studio?dev=1` | 主畫面浮 ⚙ → 點開 Dev Sheet（同 dev panel 內容） | ❌ flag 才開 |
| `/studio/{face,gesture,object,pose,speech}` | 舊版單頁 panel — 檔案保留供 URL 直連 | ❌ nav 隱藏 |

**關鍵設計**：dev mode 是 session-wide flag — 任何 `/studio/*?dev=1` 都會浮 ⚙，但 `/studio/dev` 自己頁面不浮（pathname guard 避免重複入口）。

### Live View (`/studio/live`)

Foxglove 替代展示牆。三欄即時影像 + 精簡 overlay + 事件 ticker：

- **左欄**：`/face_identity/debug_image`（人臉框+名字+相似度）
- **中欄**：`/vision_perception/debug_image`（骨架+手勢+姿勢）
- **右欄**：`/perception/object/debug_image`（YOLO 框+類別）
- **底部**：Event ticker（即時事件滾動條）
- **頂部**：Gateway 連線狀態 + Jetson 溫度

影像走獨立 WebSocket binary（`/ws/video/{source}`），事件走 `/ws/events` JSON，互不干擾。

### Chat 閉環（5/4 後）

兩條路徑：**Live 模式**走 Jetson 真 ROS2 pipeline，**Mock 模式**可選 opt-in 真打 Gemini：

**Live 模式**：
```
文字/語音 → Gateway POST /api/text_input 或 WS /ws/speech
→ ROS2 /brain/text_input → llm_bridge_node._try_openrouter_chain
→ Gemini 3 Flash（fallback: DeepSeek V4 → vLLM Qwen-7B → Ollama → RuleBrain）
→ /tts publish → Gateway 訂閱 → /ws/events broadcast
→ ChatPanel useEffect on lastTtsText → render AI bubble
```

**Mock 模式**（`bash pawai-studio/start-live.sh --mock`）：
- 預設離線：回 say_canned("我聽不太懂") + " (mock)" marker
- `MOCK_OPENROUTER=1` opt-in：mock_server 直接 call Gemini 3 Flash（透過 `tools/llm_eval/openrouter_chat.py`，不依賴 ROS）
- 兩種模式都 broadcast `tts:tts_speaking` event 給 ChatPanel 渲染（鏡像真 Jetson 行為）

**重要實作點**：
- ChatPanel `pendingRequestIdRef` 在 `await fetch` **之前**就 arm（避免 race — Gemini 回應 ~2s 內 tts event 可能比 fetch resolve 還早到）
- pending 8s timeout fallback 為 "回應逾時" inline message
- 錄音時顯示 7 條音量 bars（Web Audio AnalyserNode）
- 已知限制：`/tts` 無 correlation id，pending 期間其他 TTS 可能被誤當回覆

## Gateway / Mock 端點

> Gateway 5/7 night 起加 CORS middleware (`allow_origins=["*"]`)，Studio frontend 在筆電（如 `100.101.41.4:3000`）POST 到 Jetson Gateway（`192.168.0.222:8080`）不會被瀏覽器擋。WebSocket 不受 CORS 限制，所有 `/ws/*` 一律可用。Demo 內網 acceptable risk（commit `67c28ce`）。


| 端點 | 方向 | 用途 | live | mock |
|------|------|------|:----:|:----:|
| `GET /health` | — | 健康檢查 | ✅ | ✅ |
| `WS /ws/events` | ROS2→瀏覽器 | 感知事件廣播 + brain proposal/result + capability + tts | ✅ | ✅ |
| `POST /api/text_input` | 瀏覽器→ROS2 | 文字輸入 → /brain/text_input（live）/ Gemini call（mock + MOCK_OPENROUTER）| ✅ | ✅ |
| `POST /api/skill_request` | 瀏覽器→ROS2 | Studio button 觸發 skill | ✅ | ✅ |
| `GET /api/skill_registry` | — | 26+1 SKILL_REGISTRY JSON（active/hidden/disabled/retired bucket）| ✅ | ✅ |
| `GET/POST /api/capability` | — | tri-state capability snapshot（mock 可 POST 改值測 UI）| ✅ live read-only | ✅ both |
| `GET/POST /api/plan_mode` | — | Plan A/B toggle（in-memory flag）| ✅ | ✅ |
| `WS /ws/speech` | 瀏覽器→ROS2 | 錄音 → ASR → intent（5MB cap） | ✅ | ✅ |
| `WS /ws/video/{face,vision,object}` | ROS2→瀏覽器 | JPEG binary debug images | ✅ | ❌ |
| `GET /speech` | — | push-to-talk 獨立測試頁 | ✅ | ✅ |

## 4 PR 前端整併計畫（5/5 起，`B6-1 ~ B6-4`）

依 MOC 規格：4 個感知功能在 GitHub 上各有獨立 PR，前端碼整併到本 studio 各自頁面。**不全套搬**，挑乾淨的整進現有 panel；後端 Python（`pose_infer_server.py` 等）不抄，走既有 ROS2 pipeline。

| PR | 標題 | 主要新檔 / 抄入策略 | 注意事項 |
|---|---|---|---|
| **[#38](https://github.com/roy4222/PawAI/pull/38) Gesture (Yamiko)** | 手勢辨識 panel + WS 影像串流 | 抄 `components/gesture/local-camera-card.tsx` (87L) + WS 影像 pattern → 整進現有 `gesture-panel.tsx` | 丟棄 PR 對 ChatPanel 的改動（chat 邏輯 5/4 已 chat-first redesign 完成）|
| **[#40](https://github.com/roy4222/PawAI/pull/40) Object (object_syu)** | YOLO 偵測 + tab UI（Detect/History/Whitelist）| 抄 6 元件全套：`components/object/{local-camera, object-config, history-feed, live-detection, object-stats, object-event}.tsx`（~751L）+ `lib/object-event.ts`；object-panel.tsx 重構 tab-based | **最大 PR**（+2295/-143），最值得仔細對齊 contracts/types.ts |
| **[#41](https://github.com/roy4222/PawAI/pull/41) Pose (Gua)** | MediaPipe pose + history modal | 抄 `components/pose/{pose-client, pose-mapper, pose-types, use-pose-stream}.ts`；history modal pattern **作為全 studio center modal 範本** | `pose_infer_server.py` 不抄（後端 Python 不在 scope；走 vision_perception ROS2 既有 pipeline） |
| **[#42](https://github.com/roy4222/PawAI/pull/42) Speech (Katie)** | dual-layout speech panel + ASR/LLM/TTS bridge | **不抄整套**；只抄 `useAudioRecorder` hook 改善（hooks/use-audio-recorder.ts +14/-1）| 與 ChatPanel mic 衝突，下方明定分工 |

### PR #42 speech 與 ChatPanel mic 衝突解法

> MOC §10 明確：「PR #42 會跟 PawAI Brain × Studio 首頁重複，分開設計前端」

**分工**：

| 元件 | 路徑 | mic 用途 | WebSocket | 衝突保證 |
|---|---|---|---|---|
| **ChatPanel** | `/studio` 主頁主對話 | 使用者語音對話入口 | gateway `/ws/events` + `/ws/speech` (port 8080) | 主畫面唯一 mic |
| **SpeechPanel** | `/studio/speech` 獨立 dev page + Sheet panel | dev/debug 用途，看 ASR/intent/TTS 細節 | 預設仍走 gateway；PR #42 的 `/ws/speech_interaction:5000` 不採用（避免雙 WebSocket） | Sheet/Modal 互斥 — 開 SpeechPanel 時主畫面已被 modal 蓋住 |

**不嘗試**：合併兩條 audio pipeline、自動切換 mic owner、共用 React audio context — 全部過度設計，靠 modal 互斥保證最簡。

## Dev mode（5/4 後）

Chat 主畫面預設**完全沒有** dev 元素。`?dev=1` flag 出現在 URL 才浮 ⚙ 按鈕（44×44）；`/studio/dev` 是全頁版直連入口。內容都是同一份 `<SkillTraceContent />` + `<SkillButtons />`。

### 元件樹

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

### Brain widgets（保留檔案，但 ChatPanel 永不渲染）

`components/chat/brain/{bubble-*.tsx, brain-status-strip.tsx, skill-buttons.tsx, skill-trace-drawer.tsx, skill-trace-content.tsx}` 全部保留，只用於 dev panel / dev page。**Chat stream 永遠乾淨**，使用者看不到 brain debug。

`SkillTraceContent`（5/4 抽出）= 純 trace + GateChip + Plan toggle 渲染，不含 drawer 開關。`SkillTraceDrawer` 是 legacy collapsible wrapper，內部 render `SkillTraceContent`。共用 + 避免 drawer-in-sheet 巢狀。

### Phase 0.5 Conversation Trace chips（5/6 night, commit `c65db0d`）

`SkillTraceContent` 在既有 brain proposals 列表下方新增 **Conversation Trace · N** 區塊，渲染 `/brain/conversation_trace` 與 `/brain/conversation_trace_shadow` 兩條 topic（gateway 已在 commit `fe0297e` 加進 topic_map）。

| Status | 顏色 | 觸發 |
|---|---|---|
| `accepted` / `ok` | emerald-500/20 | brain 接受 LLM 提案並真執行（如 `show_status` / `wave_hello` / `sit_along` / `careful_remind` / `greet_known_person`） |
| `accepted_trace_only` | emerald-50/20 | brain 接受但 policy 是 trace_only（`self_introduce` 不自動跑 motion，10 步序列走 Studio button） |
| `proposed` | slate | engine 端產生提案（pre-gate） |
| `needs_confirm` | yellow-500/20 | **5/8 新增** — wiggle / stretch 等 confirm 模式 skill：brain_node 已 `_pending_confirm.request_confirm`，等使用者比 OK 才執行 |
| `demo_guide` | blue-500/20 | **5/8 新增** — kind=demo_guide 的提案（face / speech / gesture / pose / object / navigation 6 條 pseudo-skill），純 trace 不進 chat_candidate / proposal |
| `blocked` / `fallback` / `retry` | amber | cooldown / safety / OpenRouter fallback chain（含 5/8 capability layer 的 `blocked:not_in_capability_context`，把 unknown-but-allowlisted skill 擋在 pawai_brain 層） |
| `rejected_not_allowed` / `error` | rose | 提案不在 brain `LLM_PROPOSABLE_SKILLS` allowlist（5/8 已擴 8 條） |

事件流：
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

詳細 Schema + status enum：`docs/contracts/interaction_contract.md` v2.7（Phase 0.5 章節）+ spec `docs/pawai-brain/specs/2026-05-06-conversation-engine-langgraph-design.md` §4。

### Brain topic ↔ UI 對應

| 訂閱 ROS2 → broadcast WS | Studio 渲染位置 |
|------------------------|----------------|
| `/state/pawai_brain` | BrainStatusPill（chat 頂部）+ SkillTraceContent World flags |
| `/brain/proposal` | SkillTraceContent proposals list（dev only）|
| `/brain/skill_result` | SkillTraceContent（dev only） |
| `/capability/{nav_ready,depth_clear}` | NavigationPanel GateChip + SkillTraceContent header |
| `/tts` | ChatPanel `lastTtsText` → AI bubble |

### Design tokens

`pawai-studio/frontend/lib/design-tokens.ts` + `app/globals.css` 內「Chat-first redesign tokens」block。dark mode only，CSS var 命名空間：

- `--bubble-user-bg` (cyan #0EA5E9) / `--bubble-user-fg` / `--bubble-ai-border`
- `--pill-bg` / `--pill-border` / `--pill-fg` / `--pill-fg-emphasis`
- `--nav-icon-fg` / `--nav-icon-active-fg` (cyan) / `--nav-icon-hover-bg`
- `--sheet-bg` / `--sheet-border` / `--sheet-backdrop`
- `--dev-button-bg` / `--dev-badge-bg` (amber)
- `--gate-ok` / `--gate-block` / `--gate-unknown`（tri-state）
- `--anim-sheet-slide` / `--anim-message-appear` / `--anim-bubble-hover`（`@media prefers-reduced-motion` 自動退讓 0ms）

完整 rationale: [`specs/2026-05-04-design-tokens.md`](specs/2026-05-04-design-tokens.md)

## 架構參考（外部）

> MOC §10 明列：本 studio 架構靈感來自 [openclaw](https://github.com/openclaw/openclaw) + [hermes-agent](https://github.com/nousresearch/hermes-agent)，目的是「不只是 chatbot，還有實際決定做什麼動作的能力」。

### OpenClaw 對應點

| OpenClaw 概念 | PawAI Studio 對應 |
|---|---|
| Gateway 抽象（device → API → web）| `pawai-studio/gateway/studio_gateway.py`（FastAPI + rclpy）|
| Typed event（多模態事件統一 schema）| `frontend/contracts/types.ts` + `backend/schemas.py` |
| Lifecycle / capability gate | `/capability/{nav_ready,depth_clear}` + GateChip |
| Skill registry 集中管理 | `GET /api/skill_registry` 回 26+1 SKILL_REGISTRY |

### Hermes-Agent 對應點

| Hermes 概念 | PawAI 對應 |
|---|---|
| LLMProvider adapter（多 provider 同介面）| `llm_bridge_node._try_openrouter_chain` 五級 fallback |
| TTSProvider adapter | `speech_processor/tts_node` Stage 4 chain（Despina → edge_tts → Piper）|
| Persona / system prompt 模板化 | `say_template` 引用 `{name}` / `{class}` / `{color}` 變數 |
| Tool call → action arbitration | Brain proposal → SafetyLayer → `/skill_result`（唯一動作出口）|

**邊界**：上述是**靈感參考**，不直接 fork 程式碼。PawAI 走獨立架構，避免 Python ↔ TS skill registry 雙真相。

## 已知問題

- Object 精準度受限於 YOLO26n（小物件偵測率低，yolo26s 升級排在後續）
- Face greeting 重複觸發（短時間內同一人被 greet 多次，cooldown 需調整）
- Jetson 供電不穩（XL4015 降壓問題，Demo 風險項）
- `/tts` event 無 correlation id — pending 期間其他 TTS 可能被誤當回覆
- Sheet 沒接 swipe-to-close handle（Base UI Dialog.Handle 已知存在，phase C 加分）
- Voice bubble 視覺與 user bubble 同色 + cyan border 視覺冗餘（feedback doc follow-up）

## 下一步（5/5+）

- **B6-1 ~ B6-4 PR 整併**（見「4 PR 前端整併計畫」段；MOC §10 對應）：
  - B6-1 PR #38 gesture local-camera-card → gesture-panel.tsx
  - B6-2 PR #40 object 6 元件 + tab UI 重構
  - B6-3 PR #41 pose usePoseStream hook + center modal pattern 範本
  - B6-4 PR #42 speech 部分整併（useAudioRecorder + ChatPanel/SpeechPanel 分離）
- **跳窗模式遷移**（sheet right-side → center modal）— 預計連帶 B6-3 一起做
- **Jetson session**：實機 smoke OpenRouter Gemini chain（commit `fda1b3c`）+ Go2 真 TTS hardware + 8 scene Plan A/B 連跑
- B7：60 min 連續供電壓測
- 完整 voice → ASR → LLM → TTS → Megaphone E2E
- ui-ux-pro-max review feedback 中 follow-up 項（voice bubble 視覺、Sheet swipe handle、Sheet header glass）— phase C 範圍

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| specs/ | brain-adapter、event-schema、system-architecture、ui-orchestration 設計 |
