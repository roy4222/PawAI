# PawAI Studio 開發交接 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 PawAI Studio 文件整理到「人或 AI 拿到就能直接開發 Panel」的程度

**Architecture:** 兩層文件結構 — `pawai-studio/README.md` 當開發者主入口，`docs/Pawai-studio/` 退成被引用的規格庫。每份 Panel Spec 重寫為 AI-ready 格式（含 store selectors、mock data、狀態矩陣、milestone checklist）。Panel stubs 同步更新為 store-based 模式。

**Tech Stack:** Markdown, TypeScript (Next.js 16 + React 19 + Zustand)

**Spec:** `docs/superpowers/specs/2026-03-14-pawai-studio-dev-handoff-design.md`

---

## Chunk 1: Documentation Infrastructure

### Task 1: Create `pawai-studio/README.md` (Developer Launcher)

**Files:**
- Create: `pawai-studio/README.md`

- [ ] **Step 1: Create the file**

```markdown
# PawAI Studio — Developer Launcher

> **正式規格以 [`../docs/Pawai-studio/*.md`](../docs/Pawai-studio/) 為準；**
> `docs/*.md` 是實作導引與 panel-level spec。若有衝突，以 `docs/Pawai-studio/` 為準。

---

## Quick Start

### 前端

```bash
cd pawai-studio/frontend
npm install
npm run dev
# → http://localhost:3000
```

### Mock Server（前端開發用）

```bash
cd pawai-studio/backend
uv pip install -r requirements.txt
python mock_server.py
# → http://localhost:8001
```

---

## 分工速查表

| 負責人 | Panel | Spec | 可改檔案 |
|--------|-------|------|----------|
| 鄔 | FacePanel | [docs/face-panel-spec.md](docs/face-panel-spec.md) | `frontend/components/face/*` |
| 陳 | SpeechPanel | [docs/speech-panel-spec.md](docs/speech-panel-spec.md) | `frontend/components/speech/*` |
| 黃 | GesturePanel | [docs/gesture-panel-spec.md](docs/gesture-panel-spec.md) | `frontend/components/gesture/*` |
| 楊 | PosePanel | [docs/pose-panel-spec.md](docs/pose-panel-spec.md) | `frontend/components/pose/*` |

> **共用元件（`shared/`、`hooks/`、`stores/`、`layout/`）不得直接修改。**
> 若需新增或擴充共用元件，先提 Issue。

---

## Milestones

| 日期 | 交付定義 |
|------|---------|
| **3/16** | 能看、能 review — stub + 基本 UI + mock props + 4 種狀態 |
| **3/23** | 可 demo — 完整視覺 + mock 資料即時更新 + 互動 |
| **4/6** | 整合穩定 — Panel 正確反映真實 Gateway 資料 + 邊界 case |
| **4/13** | 展示版 freeze — 只修 bug |

---

## 真相來源索引

| 需求 | 路徑 |
|------|------|
| Event / State Schema | [`../docs/Pawai-studio/specs/event-schema.md`](../docs/Pawai-studio/specs/event-schema.md) |
| Design Tokens | [`docs/design-tokens.md`](docs/design-tokens.md) |
| Git Workflow | [`docs/git-workflow.md`](docs/git-workflow.md) |
| 新人上手 | [`docs/onboarding.md`](docs/onboarding.md) |
| 系統架構 | [`../docs/Pawai-studio/specs/system-architecture.md`](../docs/Pawai-studio/specs/system-architecture.md) |
| UI 編排規則 | [`../docs/Pawai-studio/specs/ui-orchestration.md`](../docs/Pawai-studio/specs/ui-orchestration.md) |
| Brain Adapter | [`../docs/Pawai-studio/specs/brain-adapter.md`](../docs/Pawai-studio/specs/brain-adapter.md) |

---

## 技術棧

Next.js 16 + React 19 + TypeScript + Tailwind CSS + shadcn/ui + Zustand

---

## 卡住怎麼辦

| 情況 | 做法 |
|------|------|
| 需要新的 shared component | 開 Issue，描述需求，等核准後再做 |
| 發現 `contracts/types.ts` 缺型別 | 開 Issue，附上你需要的 interface，不要自己改 |
| Mock Server 缺你要的事件 | 開 Issue 或直接跟後端說，不要在前端 hardcode |
| 不確定設計要求 | 看你的 panel spec → 看 design-tokens.md → 看 ChatPanel → 再問 |
| Build 壞了不是你的問題 | 在 PR 裡標注，不要嘗試修別人的 code |
```

- [ ] **Step 2: Verify no broken links**

Run: `ls pawai-studio/docs/design-tokens.md pawai-studio/docs/git-workflow.md docs/Pawai-studio/specs/event-schema.md docs/Pawai-studio/specs/system-architecture.md docs/Pawai-studio/specs/ui-orchestration.md docs/Pawai-studio/specs/brain-adapter.md`
Expected: all files exist

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/README.md
git commit -m "docs: add pawai-studio Developer Launcher README"
```

---

### Task 2: Create `pawai-studio/docs/onboarding.md`

**Files:**
- Create: `pawai-studio/docs/onboarding.md`

- [ ] **Step 1: Create the file**

```markdown
# 5 分鐘上手指南

本指南讓你（或你的 AI agent）快速開始 Panel 開發。

---

## Step 1：啟動前端

```bash
cd pawai-studio/frontend
npm install
npm run dev
```

打開 http://localhost:3000 → 應該看到 Studio 頁面，左側 Chat，右側空白面板區

---

## Step 2：啟動 Mock Server

```bash
cd pawai-studio/backend
uv pip install -r requirements.txt
python mock_server.py
```

Mock Server 跑在 http://localhost:8001，提供與真實 Gateway 完全相同的 WebSocket / REST 介面

---

## Step 3：找到你的 Panel

你的檔案在：

```
frontend/components/<你的功能>/<你的功能>-panel.tsx
```

例如鄔負責 FacePanel → `frontend/components/face/face-panel.tsx`

---

## Step 4：看你的 Spec

```
pawai-studio/docs/<你的功能>-panel-spec.md
```

裡面有：
- 完整 TypeScript 型別定義
- 可直接複製的 Mock 資料
- UI 結構與狀態矩陣
- 每個 Milestone 的驗收 checklist

---

## Step 5：參考 ChatPanel

`frontend/components/chat/chat-panel.tsx` 是唯一完整範例。

看它怎麼：
- 用 `PanelCard` 包裹整個 Panel（`frontend/components/shared/panel-card.tsx`）
- 用 `StatusBadge` 顯示狀態（`frontend/components/shared/status-badge.tsx`）
- 用 `EventItem` 顯示事件（`frontend/components/shared/event-item.tsx`）
- 用 `MetricChip` 顯示指標（`frontend/components/shared/metric-chip.tsx`）

---

## Step 6：送 PR

完整規則見 [docs/git-workflow.md](git-workflow.md)，快速版：

1. `git checkout -b feat/<你的功能>-panel`
2. 只改你的 `components/<feature>/` 目錄
3. 送 PR 前先同步 main（若衝突，先通知 maintainer，不要自己亂解）
4. `git push origin feat/<你的功能>-panel -u`
5. 開 PR → title 格式：`feat(<scope>): <描述>`
6. CI 自動跑 `npm run lint` + `npm run build`
7. Review 通過 → merge
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/docs/onboarding.md
git commit -m "docs: add 5-minute onboarding guide for panel developers"
```

---

### Task 3: Modify `docs/Pawai-studio/README.md` — add redirect banner

**Files:**
- Modify: `docs/Pawai-studio/README.md:1` (add at top)

- [ ] **Step 1: Add redirect banner at file top**

Insert before line 1:

```markdown
> **開發者請直接看 [pawai-studio/README.md](../../pawai-studio/README.md)**
> 本目錄是正式設計規格庫，非日常開發入口。

---

```

- [ ] **Step 2: Commit**

```bash
git add docs/Pawai-studio/README.md
git commit -m "docs: add developer redirect banner to Pawai-studio README"
```

---

### Task 4: Annotate `event-schema.md` — mark `last_tts_text` as Gateway-derived

**Files:**
- Modify: `docs/Pawai-studio/specs/event-schema.md:173`

- [ ] **Step 1: Add annotation to `last_tts_text` field**

In the SpeechState interface (around line 173), change:

```typescript
  last_tts_text: string;
```

to:

```typescript
  last_tts_text: string;   // Gateway-derived field — 由 Gateway 從 TTS 狀態聚合填入，非直接對應單一 ROS2 topic 欄位
```

- [ ] **Step 2: Commit**

```bash
git add docs/Pawai-studio/specs/event-schema.md
git commit -m "docs: annotate SpeechState.last_tts_text as Gateway-derived field"
```

---

### Task 5: Verify build still passes

- [ ] **Step 1: Run frontend build**

Run: `cd pawai-studio/frontend && npm run lint && npm run build`
Expected: no errors (docs changes shouldn't break build)

---

## Chunk 2: Panel Specs Rewrite (AI-Ready Format)

### Task 6: Rewrite `face-panel-spec.md`

**Files:**
- Rewrite: `pawai-studio/docs/face-panel-spec.md`
- Reference: `docs/Pawai-studio/specs/event-schema.md` (FaceState, FaceIdentityEvent, FaceTrack)
- Reference: `pawai-studio/frontend/contracts/types.ts:24-52`
- Reference: `pawai-studio/frontend/stores/state-store.ts` (useStateStore → faceState)
- Reference: `pawai-studio/frontend/components/shared/panel-card.tsx`
- Reference: `pawai-studio/frontend/components/chat/chat-panel.tsx`

- [ ] **Step 1: Rewrite the spec**

```markdown
# Face Panel Spec

> 真相來源：[../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.1 FaceState / §1.2 FaceIdentityEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

---

## 1. 目標

即時顯示人臉辨識結果：身份名稱、相似度、距離、追蹤狀態（stable/hold）、多人列表。

---

## 2. 檔案範圍

### 可以改
- `frontend/components/face/face-panel.tsx`
- `frontend/components/face/` 下新增的子元件（例如 `face-track-card.tsx`）

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/speech/`、`gesture/`、`pose/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

Panel 不接收 props，從 Zustand store 取資料：

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { FaceState, FaceTrack, FaceIdentityEvent } from '@/contracts/types'

// 在元件內：
const faceState = useStateStore((s) => s.faceState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'face'))
```

---

## 4. Mock Data

開發時直接用這些假資料測試 UI：

```typescript
const MOCK_FACE_STATE: FaceState = {
  stamp: 1773561600.789,
  face_count: 2,
  tracks: [
    {
      track_id: 1,
      stable_name: 'Roy',
      sim: 0.42,
      distance_m: 1.25,
      bbox: [100, 150, 200, 280],
      mode: 'stable',
    },
    {
      track_id: 2,
      stable_name: 'unknown',
      sim: 0.18,
      distance_m: 2.1,
      bbox: [300, 180, 380, 300],
      mode: 'hold',
    },
  ],
}

const MOCK_FACE_EVENT: FaceIdentityEvent = {
  id: 'evt-face-001',
  timestamp: '2026-03-14T10:00:01.500+08:00',
  source: 'face',
  event_type: 'identity_stable',
  data: {
    track_id: 1,
    stable_name: 'Roy',
    sim: 0.42,
    distance_m: 1.25,
  },
}

const MOCK_EMPTY_STATE: FaceState = {
  stamp: 0,
  face_count: 0,
  tracks: [],
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=User, title="人臉辨識", count=face_count)
├── [若 face_count > 0] 追蹤人物列表
│   └── 每個 FaceTrack 一張卡片：
│       ├── stable_name（粗體）
│       ├── 相似度 bar（MetricChip, value=sim, unit="%", 乘100顯示）
│       ├── 距離（MetricChip, value=distance_m, unit="m"）
│       ├── mode badge（stable=綠/hold=黃）
│       └── track_id（小字灰色）
├── [若 face_count === 0] 空狀態
│   └── 圖示 + "尚未偵測到人臉"
└── [可選/M2] 事件歷史（最近 10 筆 FaceIdentityEvent）
    └── EventItem 列表
```

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `face_count > 0` | 追蹤人物列表 | `active` |
| 載入中 | `faceState === null` | "正在連線..." | `loading` |
| 無資料 | `face_count === 0` | "尚未偵測到人臉" 空狀態 | `inactive` |
| 錯誤 | store 連線失敗（由上層處理） | "人臉模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **人物卡片 hover**：背景色加深 `var(--surface-hover)`，transition 150ms
- **新追蹤人物出現**：slide-in 動畫 200ms
- **track_lost 後**：短暫保留後淡出（實作預設 5s，可調）
- **相似度 bar**：數值變化時 transition 300ms
- **mode 切換（hold → stable）**：badge 顏色 transition 150ms

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| FaceState / FaceTrack / FaceIdentityEvent 欄位 | [../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.1 + §1.2 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| MetricChip 用法 | `frontend/components/shared/metric-chip.tsx` |
| EventItem 用法 | `frontend/components/shared/event-item.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`User`，title="人臉辨識"
- [ ] 用 `MOCK_FACE_STATE` 顯示 1-2 個追蹤人物卡片
- [ ] `face_count` 顯示在 PanelCard 的 count prop
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 多人追蹤列表（≥2 人）正常顯示
- [ ] 相似度 bar + 距離 MetricChip 視覺完成
- [ ] mode badge（stable 綠 / hold 黃）正確
- [ ] 空狀態、loading 狀態有意義的 UI
- [ ] hover / slide-in / 淡出動畫符合 design-tokens.md
- [ ] 事件歷史列表（最近 10 筆）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（缺欄位、格式異常、track 快速增減）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作 bbox 繪製或影像 overlay（那是 CameraPanel 的事）
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/docs/face-panel-spec.md
git commit -m "docs(face): rewrite panel spec to AI-ready format"
```

---

### Task 7: Rewrite `speech-panel-spec.md`

**Files:**
- Rewrite: `pawai-studio/docs/speech-panel-spec.md`
- Reference: `docs/Pawai-studio/specs/event-schema.md` (SpeechState, SpeechIntentEvent)
- Reference: `pawai-studio/frontend/contracts/types.ts:58-88`

- [ ] **Step 1: Rewrite the spec**

```markdown
# Speech Panel Spec

> 真相來源：[../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.2 SpeechState / §1.3 SpeechIntentEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

---

## 1. 目標

即時顯示語音互動狀態：狀態機 phase、ASR 轉寫文字、Intent 辨識結果、已載入模型。

---

## 2. 檔案範圍

### 可以改
- `frontend/components/speech/speech-panel.tsx`
- `frontend/components/speech/` 下新增的子元件

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/face/`、`gesture/`、`pose/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { SpeechState, SpeechPhase, SpeechIntentEvent } from '@/contracts/types'

// 在元件內：
const speechState = useStateStore((s) => s.speechState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'speech'))
```

---

## 4. Mock Data

```typescript
const MOCK_SPEECH_STATE: SpeechState = {
  stamp: 1773561602.123,
  phase: 'listening',
  last_asr_text: '你好，請問你是誰？',
  last_intent: 'greet',
  last_tts_text: '哈囉！我是 PawAI，很高興認識你！',
  models_loaded: ['kws', 'asr', 'tts'],
}

const MOCK_SPEECH_EVENT: SpeechIntentEvent = {
  id: 'evt-speech-001',
  timestamp: '2026-03-14T10:00:05.789+08:00',
  source: 'speech',
  event_type: 'intent_recognized',
  data: {
    intent: 'greet',
    text: '你好',
    confidence: 0.95,
    provider: 'whisper_local',
  },
}

const MOCK_IDLE_STATE: SpeechState = {
  stamp: 0,
  phase: 'idle_wakeword',
  last_asr_text: '',
  last_intent: '',
  last_tts_text: '',
  models_loaded: ['kws'],
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=Mic, title="語音互動")
├── Phase 狀態指示
│   ├── 當前 phase 名稱 + 對應顏色圓點
│   └── [listening 狀態] 3-dot pulse 動畫
├── 最近轉寫區
│   ├── ASR 文字（last_asr_text）
│   ├── Intent badge（last_intent + confidence%）
│   └── Provider 標籤（小字灰色）
├── 已載入模型
│   └── Chip 列表（已載=綠 success / 未載=灰 muted）
│       可能的模型：kws, asr, tts
├── [若 idle_wakeword 且無事件] 空狀態
│   └── 圖示 + "等待喚醒詞..."
└── [可選/M2] 事件歷史（最近 10 筆 SpeechIntentEvent）
    └── EventItem 列表
```

### Phase 顏色對照表

| Phase | 顯示文字 | 顏色 |
|-------|---------|------|
| `idle_wakeword` | 等待喚醒 | `--muted-foreground` |
| `wake_ack` | 喚醒確認 | `--warning` |
| `loading_local_stack` | 載入模型中 | `--warning` |
| `listening` | 聆聽中 | `--success` |
| `transcribing` | 轉寫中 | `--primary` |
| `local_asr_done` | ASR 完成 | `--primary` |
| `cloud_brain_pending` | 等待大腦 | `--warning` |
| `speaking` | 播放中 | `--success` |
| `keep_alive` | 保持連線 | `--muted-foreground` |
| `unloading` | 卸載中 | `--muted-foreground` |

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `phase !== "idle_wakeword"` | Phase + 轉寫 + Intent | `active` |
| 載入中 | `speechState === null` | "正在連線..." | `loading` |
| 無資料 | `phase === "idle_wakeword"` 且無事件 | "等待喚醒詞..." | `inactive` |
| 錯誤 | store 連線失敗 | "語音模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **Phase 切換**：顏色 transition 150ms
- **ASR 文字更新**：typing effect（逐字顯示，可用 CSS animation）
- **Intent badge 出現**：scale 200ms bounce
- **Model chip 載入/卸載**：fade 200ms
- **listening 狀態**：3-dot pulse 動畫（2s loop，`motion-safe` 尊重）

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| SpeechState / SpeechPhase / SpeechIntentEvent 欄位 | [../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.2 + §1.3 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`Mic`，title="語音互動"
- [ ] 用 `MOCK_SPEECH_STATE` 顯示 phase + ASR 文字 + intent
- [ ] Phase 圓點顏色正確（至少 listening / idle_wakeword）
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 10 種 phase 全部有對應顏色和文字
- [ ] listening 的 3-dot pulse 動畫
- [ ] Intent badge + confidence% 顯示
- [ ] 已載入模型 chip 列表
- [ ] 空狀態 + loading 狀態 UI
- [ ] 事件歷史列表（最近 10 筆）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（phase 快速切換、空 ASR 文字、未知 phase）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作語音輸入功能（那是 ChatPanel / stt_intent_node 的事）
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/docs/speech-panel-spec.md
git commit -m "docs(speech): rewrite panel spec to AI-ready format"
```

---

### Task 8: Rewrite `gesture-panel-spec.md`

**Files:**
- Rewrite: `pawai-studio/docs/gesture-panel-spec.md`
- Reference: `docs/Pawai-studio/specs/event-schema.md` (GestureState, GestureEvent)
- Reference: `pawai-studio/frontend/contracts/types.ts:94-111`

- [ ] **Step 1: Rewrite the spec**

```markdown
# Gesture Panel Spec

> 真相來源：[../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.5 GestureState / §1.4 GestureEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

---

## 1. 目標

即時顯示手勢辨識結果：手勢類型、信心度、左右手、事件歷史。（P1 功能）

---

## 2. 檔案範圍

### 可以改
- `frontend/components/gesture/gesture-panel.tsx`
- `frontend/components/gesture/` 下新增的子元件

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/face/`、`speech/`、`pose/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { GestureState, GestureEvent } from '@/contracts/types'

// 在元件內：
const gestureState = useStateStore((s) => s.gestureState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'gesture'))
```

---

## 4. Mock Data

```typescript
const MOCK_GESTURE_STATE: GestureState = {
  stamp: 1773561605.456,
  active: true,
  current_gesture: 'wave',
  confidence: 0.87,
  hand: 'right',
  status: 'active',
}

const MOCK_GESTURE_EVENT: GestureEvent = {
  id: 'evt-gesture-001',
  timestamp: '2026-03-14T10:00:05.456+08:00',
  source: 'gesture',
  event_type: 'gesture_detected',
  data: {
    gesture: 'wave',
    confidence: 0.87,
    hand: 'right',
  },
}

const MOCK_EMPTY_STATE: GestureState = {
  stamp: 0,
  active: false,
  current_gesture: null,
  confidence: 0,
  hand: null,
  status: 'inactive',
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=Hand, title="手勢辨識")
├── [若 active] 手勢卡片
│   ├── 手勢圖示（wave=👋 / stop=✋ / point=👉 / ok=👌，或用 lucide icon）
│   ├── 手勢名稱（粗體）
│   ├── 信心度（MetricChip, value=confidence, unit="%", 乘100顯示）
│   └── 左右手 badge（left=左手 / right=右手）
├── [若 !active] 空狀態
│   └── 圖示 + "尚未偵測到手勢"
└── [可選/M2] 事件歷史（最近 10 筆 GestureEvent）
    └── EventItem 列表
```

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `active === true` | 手勢卡片 | `active` |
| 載入中 | `gestureState === null` 或 `status === "loading"` | "正在連線..." | `loading` |
| 無資料 | `active === false` | "尚未偵測到手勢" | `inactive` |
| 錯誤 | store 連線失敗 | "手勢模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **新手勢偵測**：bounce 動畫 200ms
- **信心度變化**：transition 300ms
- **手勢切換**：crossfade 200ms
- **手勢卡片 hover**：背景色加深 `var(--surface-hover)`，transition 150ms

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| GestureState / GestureEvent 欄位 | [../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.5 + §1.4 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| MetricChip 用法 | `frontend/components/shared/metric-chip.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`Hand`，title="手勢辨識"
- [ ] 用 `MOCK_GESTURE_STATE` 顯示 1 個手勢卡片
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 手勢圖示 + 名稱 + 信心度 + 左右手 視覺完成
- [ ] bounce / crossfade / transition 動畫符合 design-tokens.md
- [ ] 空狀態 + loading 狀態 UI
- [ ] 事件歷史列表（最近 10 筆）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（快速手勢切換、null gesture、未知手勢字串）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作手勢辨識模型或影像處理
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/docs/gesture-panel-spec.md
git commit -m "docs(gesture): rewrite panel spec to AI-ready format"
```

---

### Task 9: Rewrite `pose-panel-spec.md`

**Files:**
- Rewrite: `pawai-studio/docs/pose-panel-spec.md`
- Reference: `docs/Pawai-studio/specs/event-schema.md` (PoseState, PoseEvent)
- Reference: `pawai-studio/frontend/contracts/types.ts:117-134`

- [ ] **Step 1: Rewrite the spec**

```markdown
# Pose Panel Spec

> 真相來源：[../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.6 PoseState / §1.5 PoseEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

---

## 1. 目標

即時顯示姿勢辨識結果：姿勢類型、信心度、追蹤對象、**跌倒警示**。（P1 功能）

---

## 2. 檔案範圍

### 可以改
- `frontend/components/pose/pose-panel.tsx`
- `frontend/components/pose/` 下新增的子元件

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/face/`、`speech/`、`gesture/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { PoseState, PoseEvent } from '@/contracts/types'

// 在元件內：
const poseState = useStateStore((s) => s.poseState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'pose'))
```

---

## 4. Mock Data

```typescript
const MOCK_POSE_STATE: PoseState = {
  stamp: 1773561607.890,
  active: true,
  current_pose: 'standing',
  confidence: 0.92,
  track_id: 1,
  status: 'active',
}

const MOCK_POSE_EVENT: PoseEvent = {
  id: 'evt-pose-001',
  timestamp: '2026-03-14T10:00:07.890+08:00',
  source: 'pose',
  event_type: 'pose_detected',
  data: {
    pose: 'standing',
    confidence: 0.92,
    track_id: 1,
  },
}

const MOCK_FALLEN_STATE: PoseState = {
  stamp: 1773561610.000,
  active: true,
  current_pose: 'fallen',
  confidence: 0.88,
  track_id: 1,
  status: 'active',
}

const MOCK_EMPTY_STATE: PoseState = {
  stamp: 0,
  active: false,
  current_pose: null,
  confidence: 0,
  track_id: null,
  status: 'inactive',
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=Activity, title="姿勢辨識")
├── [若 active] 姿勢卡片
│   ├── 姿勢圖示（standing=🧍 / sitting=🪑 / crouching=⬇️ / fallen=⚠️，或用 lucide icon）
│   ├── 姿勢名稱（粗體）
│   ├── 信心度（MetricChip, value=confidence, unit="%", 乘100顯示）
│   ├── 關聯 track_id（小字灰色，若有值）
│   └── [fallen] 跌倒警示區塊（見下方）
├── [若 !active] 空狀態
│   └── 圖示 + "尚未偵測到姿勢"
└── [可選/M2] 事件歷史（最近 10 筆 PoseEvent）
    └── EventItem 列表，fallen 事件用 destructive 色標示
```

### 跌倒警示（`current_pose === "fallen"`）

這是本 Panel 最重要的特殊狀態：

- PanelCard 邊框改為 `var(--destructive)` 紅色
- 姿勢卡片背景改為 `var(--destructive)/10`
- 圖示改為 `AlertTriangle`（lucide）
- 文字顯示「**偵測到跌倒！**」粗體紅色
- 動畫：border pulse 2s loop（`motion-safe` 尊重）

### 姿勢顏色對照表

| Pose | 顯示文字 | 顏色 |
|------|---------|------|
| `standing` | 站立 | `--success` |
| `sitting` | 坐下 | `--success` |
| `crouching` | 蹲下 | `--warning` |
| `fallen` | 跌倒 | `--destructive` |

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `active === true` 且 `pose !== "fallen"` | 姿勢卡片 | `active` |
| 跌倒警示 | `active === true` 且 `pose === "fallen"` | 警示 UI | `error` |
| 載入中 | `poseState === null` 或 `status === "loading"` | "正在連線..." | `loading` |
| 無資料 | `active === false` | "尚未偵測到姿勢" | `inactive` |
| 錯誤 | store 連線失敗 | "姿勢模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **姿勢切換**：圖示 + 名稱 crossfade 200ms
- **信心度變化**：transition 300ms
- **跌倒偵測**：邊框 pulse 2s loop，`motion-safe` 尊重
- **姿勢卡片 hover**：背景色加深 `var(--surface-hover)`，transition 150ms

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| PoseState / PoseEvent 欄位 | [../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.6 + §1.5 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| MetricChip 用法 | `frontend/components/shared/metric-chip.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`Activity`，title="姿勢辨識"
- [ ] 用 `MOCK_POSE_STATE` 顯示 1 個姿勢卡片
- [ ] 用 `MOCK_FALLEN_STATE` 顯示跌倒警示 UI
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 4 種姿勢各有正確圖示 + 顏色
- [ ] 跌倒警示完整（紅框 + pulse + AlertTriangle + 粗體文字）
- [ ] 信心度 MetricChip 視覺完成
- [ ] 空狀態 + loading 狀態 UI
- [ ] 事件歷史列表（最近 10 筆，fallen 紅色標示）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（pose 快速切換、null pose、未知姿勢字串）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作骨架渲染或影像疊加（可選 P2，不在 M1-M3 範圍）
```

- [ ] **Step 2: Commit**

```bash
git add pawai-studio/docs/pose-panel-spec.md
git commit -m "docs(pose): rewrite panel spec to AI-ready format"
```

---

## Chunk 3: Panel Stub Alignment

現有 4 個 panel stub 用 props 模式（`{ data: FaceState, events: FaceIdentityEvent[] }`），但 spec 定義 panel 從 store 取資料。需要同步更新 stubs，避免新開發者看到 props 混亂。

### Task 10: Update `face-panel.tsx` stub to store-based

**Files:**
- Modify: `pawai-studio/frontend/components/face/face-panel.tsx`

- [ ] **Step 1: Rewrite stub to use store selectors**

```tsx
'use client'

import { User } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { FaceState } from '@/contracts/types'

export function FacePanel() {
  const faceState = useStateStore((s) => s.faceState) as FaceState | null
  const events = useEventStore((s) => s.events.filter((e) => e.source === 'face'))

  const status = !faceState
    ? 'loading' as const
    : faceState.face_count > 0
      ? 'active' as const
      : 'inactive' as const

  return (
    <PanelCard
      title="人臉辨識"
      icon={<User className="h-4 w-4" />}
      status={status}
      count={faceState?.face_count}
    >
      {/* TODO: 鄔 — 看 docs/face-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 face-panel-spec.md
      </div>
    </PanelCard>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd pawai-studio/frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/components/face/face-panel.tsx
git commit -m "refactor(face): update stub to store-based pattern"
```

---

### Task 11: Update `speech-panel.tsx` stub to store-based

**Files:**
- Modify: `pawai-studio/frontend/components/speech/speech-panel.tsx`

- [ ] **Step 1: Rewrite stub**

```tsx
'use client'

import { Mic } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { SpeechState } from '@/contracts/types'

export function SpeechPanel() {
  const speechState = useStateStore((s) => s.speechState) as SpeechState | null
  const events = useEventStore((s) => s.events.filter((e) => e.source === 'speech'))

  const status = !speechState
    ? 'loading' as const
    : speechState.phase !== 'idle_wakeword'
      ? 'active' as const
      : 'inactive' as const

  return (
    <PanelCard
      title="語音互動"
      icon={<Mic className="h-4 w-4" />}
      status={status}
    >
      {/* TODO: 陳 — 看 docs/speech-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 speech-panel-spec.md
      </div>
    </PanelCard>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd pawai-studio/frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/components/speech/speech-panel.tsx
git commit -m "refactor(speech): update stub to store-based pattern"
```

---

### Task 12: Update `gesture-panel.tsx` stub to store-based

**Files:**
- Modify: `pawai-studio/frontend/components/gesture/gesture-panel.tsx`

- [ ] **Step 1: Rewrite stub**

```tsx
'use client'

import { Hand } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { GestureState } from '@/contracts/types'

export function GesturePanel() {
  const gestureState = useStateStore((s) => s.gestureState) as GestureState | null
  const events = useEventStore((s) => s.events.filter((e) => e.source === 'gesture'))

  const status = !gestureState
    ? 'loading' as const
    : gestureState.active
      ? 'active' as const
      : 'inactive' as const

  return (
    <PanelCard
      title="手勢辨識"
      icon={<Hand className="h-4 w-4" />}
      status={status}
    >
      {/* TODO: 黃 — 看 docs/gesture-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 gesture-panel-spec.md
      </div>
    </PanelCard>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd pawai-studio/frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/components/gesture/gesture-panel.tsx
git commit -m "refactor(gesture): update stub to store-based pattern"
```

---

### Task 13: Update `pose-panel.tsx` stub to store-based

**Files:**
- Modify: `pawai-studio/frontend/components/pose/pose-panel.tsx`

- [ ] **Step 1: Rewrite stub**

```tsx
'use client'

import { Activity } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { PoseState } from '@/contracts/types'

export function PosePanel() {
  const poseState = useStateStore((s) => s.poseState) as PoseState | null
  const events = useEventStore((s) => s.events.filter((e) => e.source === 'pose'))

  const status = !poseState
    ? 'loading' as const
    : poseState.current_pose === 'fallen'
      ? 'error' as const
      : poseState.active
        ? 'active' as const
        : 'inactive' as const

  return (
    <PanelCard
      title="姿勢辨識"
      icon={<Activity className="h-4 w-4" />}
      status={status}
    >
      {/* TODO: 楊 — 看 docs/pose-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 pose-panel-spec.md
      </div>
    </PanelCard>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd pawai-studio/frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/frontend/components/pose/pose-panel.tsx
git commit -m "refactor(pose): update stub to store-based pattern"
```

---

### Task 14: Update callers of panel stubs (if needed)

**Files:**
- Check: `pawai-studio/frontend/app/(studio)/studio/page.tsx`
- Check: `pawai-studio/frontend/components/layout/panel-container.tsx`

- [ ] **Step 1: Check if panels are called with props**

Search for `<FacePanel`, `<SpeechPanel`, `<GesturePanel`, `<PosePanel` in the codebase to find callers and verify they don't pass props that we removed.

- [ ] **Step 2: Update callers if needed**

If any caller passes `data=` or `events=` props, remove those props since panels now read from store directly.

- [ ] **Step 3: Final build verification**

Run: `cd pawai-studio/frontend && npm run lint && npm run build`
Expected: PASS — all panels compile, no unused prop warnings

- [ ] **Step 4: Commit (if changes needed)**

```bash
git add pawai-studio/frontend/app/ pawai-studio/frontend/components/
git commit -m "refactor: remove panel props from callers — panels now use store"
```
