# PawAI Studio — Chat-First Redesign Design

> **Status**: design spec, awaiting user approval before implementation
> **Date**: 2026-05-04
> **Scope**: 重做 `pawai-studio/frontend` 主畫面為 ChatGPT 風純對話 + 頂部 6 個彈窗按鈕；dev 工具藏到 `?dev=1` 或 `/studio/dev`
> **Implementation skills**: `ui-ux-pro-max`（視覺主導）+ `frontend-design`（元件抽象）

---

## 1. Context

今天（2026-05-04）user 開瀏覽器測 commit `9f45f65` 後的 Studio 看到滿屏 dashboard：5 個側邊面板 + 主畫面 17+5+4 個 skill 按鈕 + Brain Status Strip + Skill Trace + Brain debug bubbles。User 反應：「有夠亂、把不必要的東西拔掉、做成像 ChatGPT 那樣只有聊天」。

Reference image 顯示目標：

```
┌──────────────────────────────────────────────────────┐
│ PawAI Studio │ [6 feature buttons] │ LIVE  ●已連線 │
├──────────────────────────────────────────────────────┤
│           ╭──────────────────────────────╮           │
│           │ Brain 已就緒 obs:ok emg:ok │ 15:56     │
│           ╰──────────────────────────────╯           │
│                                                       │
│                       你好  ◀ user                    │
│                                                       │
│  ◀ AI  好的，已為你打開客廳的燈                       │
│                                                       │
│                       你在看我嗎？  ◀ user            │
│                                                       │
│  ◀ AI  我目前辨識到 1 位使用者...                     │
│                                                       │
├──────────────────────────────────────────────────────┤
│ [傳送訊息給 PawAI...]               [🎙][📤]         │
└──────────────────────────────────────────────────────┘
```

**核心轉變**：Studio 從「工程 dashboard」變成「給使用者用的對話介面，diagnostic 藏起來」。

---

## 2. Final Information Architecture

### 2.1 Routes

| Route | 用途 | nav 顯示 |
|---|---|---|
| `/studio` | **聊天主畫面**（ChatGPT 風） | 預設首頁 |
| `/studio/live` | Live camera stream | 右上 LIVE 鏈 |
| `/studio/dev` | Skill Console + Trace + Plan toggle + Capability gates | 隱藏（直接打 URL 或 `?dev=1`）|
| `/studio/face`、`/studio/gesture`、`/studio/object`、`/studio/pose`、`/studio/speech` | 既有 detail page | **保留檔案，只從 nav 隱藏** |

**不刪舊 route**：組員 / 測試腳本可能直接打 URL，且每個 page 已是「`<Panel />` 包 `<StudioLayout>`」的 thin wrapper，留著 free。Modal 內容用同一個 `<*Panel />` 元件，不會 drift。Phase B 後可視情況再砍。

### 2.2 Top navbar — 6 個彈窗按鈕（icon-only + tooltip）

桌面（≥ md）：6 個 **icon-only 按鈕**，hover 顯示 tooltip 中文 label。圖示用 lucide-react，每顆 32×32，間距 8px。整排靠中央右側對齊，Logo 和它中間留 spacer。

行動（< md）：改成右側「功能」漢堡選單（一顆 `Menu` icon），點開展開 6 條清單列，每條 `icon + 中文 label`。同一個 Sheet 系統，只是 trigger 不同。

| # | 功能 | 中文（tooltip / 行動 label） | icon | modal 內容（重用現有 Panel） |
|---|---|---|---|---|
| 1 | Face | 人臉辨識 | `User` | `<FacePanel />` |
| 2 | Speech | 語音功能 | `Mic` | `<SpeechPanel />` |
| 3 | Gesture | 手勢辨識 | `Hand` | `<GesturePanel />` |
| 4 | Pose | 姿勢辨識 | `PersonStanding` | `<PosePanel />` |
| 5 | Object | 辨識物體 | `Box` | `<ObjectPanel />` |
| 6 | Navigation | 導航避障 | `Compass` | `<NavigationPanel />` *(NEW，含 Nav Gate / Depth Gate / Plan A/B 三個 chip)* |

點任一按鈕 → 從**右側滑入** Sheet（用 `@base-ui/react` 的 Dialog primitive 自定 slide-from-right transition）。背景 chat 不消失（半透明 backdrop），Esc / 背景點擊關閉。

**為什麼用 Sheet 不用 Dialog**：Sheet 不打斷對話 focus，使用者一邊聊天一邊偷瞄狗的感知狀態 — 符合 PawAI Demo 場景。Dialog 中央彈出會搶 focus、感覺像「打開設定」。

**為什麼 icon-only 不放中文 label**：6 個 icon + label 在 navbar 等於又把 Studio 變吵。icon-only 配 tooltip 是 ChatGPT / Linear / Notion 都在用的乾淨做法；中文 label 在行動 hamburger 才出現，桌面不擠。

### 2.3 Dev / debug 入口

新 route `/studio/dev` 一頁：
- 上半：**Skill Console**（重用現有 `skill-buttons.tsx` 整檔）
- 下半：**Skill Trace Drawer**（重用現有 `skill-trace-drawer.tsx`）
- 加一條提示：「Dev Mode — 一般使用者請回到 /studio」

**主畫面預設不浮 ⚙ 按鈕**。只有 `?dev=1` query string 出現時，主畫面右下角才浮 ⚙（點開 dev panel 同樣是 Sheet 從右側滑入）。沒帶 flag → 整個 dev 入口在主畫面**完全不存在**，使用者看不到、不會誤點。

組員 / 測試 → 直接打 `/studio/dev` 或 `/studio?dev=1`。

---

## 3. Component Changes

### 3.1 砍

| 檔案 | 動作 |
|---|---|
| `app/(studio)/studio/face/page.tsx` | **保留**（從 nav 隱藏，URL 直連可用） |
| `app/(studio)/studio/gesture/page.tsx` | 同上保留 |
| `app/(studio)/studio/object/page.tsx` | 同上保留 |
| `app/(studio)/studio/pose/page.tsx` | 同上保留 |
| `app/(studio)/studio/speech/page.tsx` | 同上保留 |
| `components/chat/brain/skill-buttons.tsx` 在 ChatPanel 的引用 | 移除 |
| `components/chat/brain/skill-trace-drawer.tsx` 在 ChatPanel 的引用 | 移除 |
| `components/chat/brain/brain-status-strip.tsx` 在 ChatPanel 的引用 | 移除 |
| `components/chat/brain/bubble-{alert,brain-plan,safety,skill-result,skill-step}.tsx` 渲染 | 在 ChatPanel 中**永不渲染**（檔案保留供 `/studio/dev` 內部使用）|

### 3.2 新

| 檔案 | 用途 |
|---|---|
| `components/ui/sheet.tsx` | 通用 Sheet 元件（Base UI Dialog + Tailwind slide-from-right transition） |
| `components/layout/feature-nav.tsx` | 頂部 6 個 icon 按鈕，點擊開啟對應 Sheet |
| `components/layout/nav-tabbar.tsx` | 新 topbar：Logo + FeatureNav + LIVE 鏈 + 連線狀態 |
| `components/navigation/navigation-panel.tsx` | 新 panel：Nav Gate / Depth Gate / Plan A/B（從現有 SkillTraceDrawer 抽取邏輯） |
| `app/(studio)/studio/dev/page.tsx` | dev 工具集中頁 |
| `components/chat/brain-status-pill.tsx` | thin 狀態藥丸（取代 BrainStatusStrip），主畫面頂部居中 |

### 3.3 改

| 檔案 | 動作 |
|---|---|
| `components/layout/topbar.tsx` | 砍掉舊的、由 `nav-tabbar.tsx` 取代 |
| `components/layout/studio-layout.tsx` | 砍掉 `sidebarPanels` prop（已不用） |
| `components/chat/chat-panel.tsx` | 移除所有 brain widget imports；**永遠**只渲染 normal user / assistant chat messages 與 input。debug bubble / skill button / trace 不在 chat 流裡出現（即使 `?dev=1`）。**`?dev=1` 的作用只是浮現 ⚙ 按鈕**，點 ⚙ 開 dev sheet 才看 skill / trace — chat stream 永遠乾淨。**目標是「主畫面只有對話」，不是壓行數**；如需拆元件可拆，但別為了短而硬砍流程 |
| `app/(studio)/studio/page.tsx` | 簡化為 `<ChatPanel />`（移除 sidebarPanels 邏輯） |
| `app/(studio)/studio/live/page.tsx` | 保留，nav 外掛右上 LIVE 鏈 |

---

## 4. Mock backend chat（opt-in，預設不打 API）

問題：今天測「你好」→ `say_canned("我聽不太懂")`。原因是 `mock_server.py:/api/text_input` 寫死回 say_canned，**沒接 OpenRouter**。

**設計原則**：mock 預設仍離線（不花錢、不受網路影響）。只有當 `MOCK_OPENROUTER=1` 環境變數設了，才打真 Gemini。

修法：`mock_server.py:/api/text_input` 啟動時讀一次 `os.environ.get("MOCK_OPENROUTER")`：

```
if MOCK_OPENROUTER != "1":
    # 預設行為：離線 mock，回 say_canned("我聽不太懂")
    # 但前端 ChatPanel 可以辨認 mock 標記，UI 會把訊息加上「(mock)」灰字
elif OPENROUTER_KEY exists:
    # 真打 Gemini 3 Flash，broadcast brain:proposal {selected_skill: "chat_reply", text: reply}
else:
    # MOCK_OPENROUTER=1 但沒 key → 啟動時 log error，預設回 say_canned + 加 "(no key)" 標記
```

`bash pawai-studio/start-live.sh --mock` 不開這個 flag → 純離線測 UI。
`MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock` → 開 API call，能真聊天。

**不複用 llm_bridge_node**（避免拉 ROS 依賴進 mock）。直接寫一個輕量 Python 函式 `tools/llm_eval/openrouter_chat.py`，提供 `chat(user_text, persona_path) -> dict`，mock_server 與 live smoke 共用。

---

## 5. 視覺樣式（**先定 token，再寫元件**）

**這是 reset 不是 polish**。先 invoke `ui-ux-pro-max` 跑出 design tokens（palette / typography / spacing / animation / mobile breakpoints），再開始寫元件，避免後期返工 className。

第一輪 token 決策（在實作 step 1）必須產出 `pawai-studio/frontend/lib/design-tokens.ts`（或 tailwind theme extension）涵蓋：

- **palette**：bg-base / bg-surface / bg-bubble-user / bg-bubble-ai / text-primary / text-muted / accent / accent-fg / border / divider，每個有 dark mode 值
- **typography**：font family（中文 + 英文 fallback）、size scale（chat-body / chat-meta / nav-label / sheet-title）、line-height
- **spacing**：tw scale 用既有，只鎖 chat container max-w（建議 `max-w-3xl`）+ horizontal padding（mobile 16, desktop 32）
- **animation**：sheet slide 200ms ease-out / message appear 150ms / dev button fade
- **layout rules**：
  - navbar h-12（不變）
  - sheet width 380px（≥ md）/ full-width（< md）
  - chat container max-w-3xl 居中
  - bubble max-w 70%、padding x-4 y-3、rounded-2xl
- **mobile behavior**：
  - < md：navbar 6 按鈕收進 hamburger
  - < md：sheet 全寬從底部上滑（不是右側），更貼近原生 app

第二輪（step 10 / 11）才是視覺 polish — 微調漸層、陰影、micro-interaction、avatar 風格、message density。

---

## 6. 實作順序

1. **invoke `ui-ux-pro-max`** → 產出 design tokens（palette / typography / spacing / animation / mobile rules）寫進 `lib/design-tokens.ts` + tailwind theme
2. **新 NavTabbar + Sheet 通用元件**（icon-only buttons + tooltip + hamburger fallback；空 sheet 殼）
3. **舊 routes 從 nav 隱藏**（`/studio/face|gesture|object|pose|speech` 留檔不刪）
4. **ChatPanel 改成只渲染 chat messages + input**（debug bubble / skill button / trace 預設不出現）
5. **dev mode**：`?dev=1` 主畫面右下浮 ⚙（無 flag 時主畫面完全沒此 element）；`/studio/dev` 直連永遠可用
6. **6 個 feature panel 塞 Sheet**（重用現有 FacePanel / SpeechPanel / GesturePanel / PosePanel / ObjectPanel）
7. **NavigationPanel 新做**（Nav Gate + Depth Gate + Plan A/B 三 chip，從 SkillTraceDrawer 抽邏輯）
8. **mock_server `/api/text_input`** 加 `MOCK_OPENROUTER=1` env flag 支援；預設仍離線 say_canned
9. **驗證**：`npx tsc --noEmit` 0 errors → `npm run build` → 瀏覽器手動測（含 `MOCK_OPENROUTER=1` 跑一輪真 chat round-trip）
10. **invoke `frontend-design`** review 元件抽象、a11y、message stream 結構正確性

`ui-ux-pro-max` 在 step 1 用，不延後。`frontend-design` 在 step 10 review，是品質閘門不是 polish。

---

## 7. 驗證

### 7.1 自動測試

- TypeScript：`npx tsc --noEmit` 0 errors
- 既有測試：`pawai-studio/gateway/test_gateway.py` 18 passed
- Build smoke：`npm run build`（catch SSR / hydration）

### 7.2 瀏覽器手動

**離線 UI 測試**（預設、不打 API）：
```bash
bash pawai-studio/start-live.sh --mock
# http://localhost:3001/studio
# 輸入「你好」→ 看到 say_canned 回覆 + (mock) 標記，UI 流程跑通
```

**真 chat round-trip 測試**（明確 opt-in）：
```bash
set -a && . ./.env && set +a
MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock
# 輸入「你好」→ 收到 Gemini 真回覆
```

驗收：
1. 主畫面只剩 nav + 狀態 pill + chat + input — 沒有 skill button、沒有 trace、沒有 ⚙
2. 點 navbar 6 個 icon → tooltip 顯示中文 / Sheet 從右滑入 / Esc 關閉
3. < md 螢幕：6 個 icon 收進 hamburger menu
4. `?dev=1` → 主畫面右下角才出現 ⚙ 按鈕 → 點開看到 skill console + trace
5. 沒帶 `?dev=1`：⚙ 完全不出現
6. `/studio/dev` 直連 → 看到完整 dev 工具
7. `/studio/face` 等舊 route 直接打 URL 仍可用（從 nav 看不到，但檔案沒砍）
8. `MOCK_OPENROUTER=1`：「你好」→ Gemini 回覆（含 audio tag）
9. 沒 `MOCK_OPENROUTER`：「你好」→ say_canned + UI 顯示 (mock) 標記

### 7.3 Mock 控制（驗證 chat round-trip）

**沒 `MOCK_OPENROUTER` 時**（預設離線）：
```bash
bash pawai-studio/start-live.sh --mock
curl -X POST -H 'Content-Type: application/json' \
  -d '{"text":"你好","request_id":"t1"}' \
  http://localhost:8080/api/text_input
# 預期：mock reply（say_canned「我聽不太懂」+ UI 標 (mock)）
```

**`MOCK_OPENROUTER=1` 時**（明確 opt-in）：
```bash
set -a && . ./.env && set +a
MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock
curl -X POST -H 'Content-Type: application/json' \
  -d '{"text":"你好","request_id":"t1"}' \
  http://localhost:8080/api/text_input
# 預期：回傳含 Gemini reply 的 brain:proposal 事件
```

---

## 8. 不做的事

- 不重寫 chat-panel 之外的 component 結構（Brain bubble 元件檔案保留供 `/studio/dev` 使用，但 ChatPanel 中**永不渲染**它們）
- 不改 mock_server 其他 endpoint（skill_registry / capability / plan_mode 都保留供 dev page 使用）
- 不改 `llm_bridge_node`（ROS 端、commit fda1b3c 已完成 OpenRouter chain）
- 不刪 `components/chat/brain/*.tsx`（dev mode 還會用）
- 不動 backend gateway（`pawai-studio/gateway/studio_gateway.py` 在 Jetson 用，與 mock 不同檔）

---

## 9. 已知風險

| 風險 | 緩解 |
|---|---|
| Sheet 動畫在 Next 16 + React 19 + Base UI 1.3 衝突 | 先做最小 PoC（單按鈕單 sheet）通過再往下 |
| ChatPanel 重構風險 | 先保持 message pipeline 不動（user / assistant 流仍正常），再分次拔掉 brain widget 與 import；不以行數為目標 |
| OpenRouter call 在 mock_server 拖慢啟動 | 改 lazy import + 第一次 call 才連線 |
| 6 個按鈕在小螢幕（< 1024px）擠不下 | < md 變漢堡選單，items 改成 popover 列表 |
| dev mode (`?dev=1`) URL 在 Next App Router 取得方式 | `useSearchParams()` from `next/navigation`（client-side） |

---

## 10. 變更紀錄

- **2026-05-04 v1**：初版，鎖定 chat-first IA、6 modal nav、Sheet on Base UI、dev 藏入 `?dev=1` / `/studio/dev`、mock_server 接 OpenRouter。
- **2026-05-04 v2**：根據 user review 改 6 點：
  1. 舊 route 不刪只從 nav 隱藏（保護組員 / 直連 URL 用）
  2. navbar icon-only + tooltip（< md hamburger），不放 6 個中文 label
  3. mock OpenRouter 改 opt-in（`MOCK_OPENROUTER=1` 才打 API）
  4. ChatPanel 目標改「只渲染 chat messages + input」，不以行數為 KPI
  5. 主畫面預設**沒有** ⚙；只有 `?dev=1` 才浮現
  6. 視覺 token 提前到 step 1（`ui-ux-pro-max`），不在最後 polish
- **2026-05-04 v2.1**：再修 3 個內部矛盾（user re-review）：
  1. §7.3 curl 範例補 `MOCK_OPENROUTER=1` 雙路徑（離線預期 mock reply / opt-in 預期 Gemini）
  2. §8 「Brain bubbles 改條件渲染」改成「ChatPanel 永不渲染，元件檔保留供 dev 用」
  3. §9 風險表移除「砍到 < 200 行」V1 遺留，改「不以行數為目標」
  + `.gitignore` 加 `*Zone.Identifier` + repo root 圖片（防止 mock screenshot 誤 commit）

---

## Appendix A — 可重用既有資產

| 用途 | 路徑 |
|---|---|
| Chat bubble 結構 | `components/chat/chat-panel.tsx`（砍剩 user/assistant 部分） |
| Audio recorder hook | `hooks/use-audio-recorder.ts` |
| Audio visualizer | `components/chat/audio-visualizer.tsx` |
| Face / Gesture / Pose / Object / Speech panels | `components/{face,gesture,pose,object,speech}/*-panel.tsx`（直接塞進 Sheet） |
| Capability tri-state chip | `components/chat/brain/skill-trace-drawer.tsx:GateChip`（抽出來給 NavigationPanel 用） |
| Plan A/B toggle | `skill-trace-drawer.tsx:togglePlanMode`（抽到 NavigationPanel） |
| state-store | `stores/state-store.ts`（capability / planMode 已在了） |
| OpenRouter call 邏輯 | `tools/llm_eval/run_eval.py:call_openrouter` 抽成 `openrouter_chat.py` 共用 |
