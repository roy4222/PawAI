# PawAI Studio 開發交接設計

**版本**：v1.0
**日期**：2026-03-14
**目標**：讓 4 位團隊成員（或其 AI agent）拿到文件就能直接開發 Panel，不需額外口頭補充

---

## 1. 文件結構與導航

### 1.1 角色定義

| 位置 | 角色 | 讀者 |
|------|------|------|
| `pawai-studio/README.md` | **開發者主入口（Developer Launcher）** | 要直接寫 code 的人或 AI agent |
| `pawai-studio/docs/*.md` | **實作層規格（Implementation Specs）** | Panel 開發者 |
| `docs/Pawai-studio/*.md` | **正式設計規格庫（Spec Library）** | 要理解架構決策的人 |

**硬規則**：

> 正式規格以 `docs/Pawai-studio/*.md` 為準；
> `pawai-studio/docs/*.md` 是實作導引與 panel-level spec。
> 若有衝突，以 `docs/Pawai-studio/` 為準。

### 1.2 檔案地圖

```
pawai-studio/
├── README.md                          ← 開發者主入口（重寫）
├── docs/
│   ├── onboarding.md                  ← 新人/AI 5分鐘上手（新增）
│   ├── design-tokens.md               ← 保留不動
│   ├── git-workflow.md                ← 保留不動
│   ├── face-panel-spec.md             ← 重寫為 AI-ready 格式
│   ├── speech-panel-spec.md           ← 重寫為 AI-ready 格式
│   ├── gesture-panel-spec.md          ← 重寫為 AI-ready 格式
│   └── pose-panel-spec.md             ← 重寫為 AI-ready 格式

docs/Pawai-studio/
├── README.md                          ← 加頂部提示指向 pawai-studio/README.md
├── system-architecture.md             ← 不動
├── ui-orchestration.md                ← 不動
├── event-schema.md                    ← 不動（最高真相來源）
└── brain-adapter.md                   ← 不動
```

### 1.3 `pawai-studio/README.md` 結構

```markdown
# PawAI Studio — Developer Launcher

> 正式規格以 `../docs/Pawai-studio/*.md` 為準；
> `docs/*.md` 是實作導引與 panel-level spec。

## Quick Start
- Backend: cd pawai-studio/backend → uv pip install -r requirements.txt → python mock_server.py → :8001
- Frontend: cd pawai-studio/frontend → npm install → npm run dev → :3000

## 分工速查表
| 負責人 | Panel | Spec | 可改檔案 |
|--------|-------|------|----------|
| 鄔 | FacePanel | docs/face-panel-spec.md | components/face/* |
| 陳 | SpeechPanel | docs/speech-panel-spec.md | components/speech/* |
| 黃 | GesturePanel | docs/gesture-panel-spec.md | components/gesture/* |
| 楊 | PosePanel | docs/pose-panel-spec.md | components/pose/* |

> 共用元件（shared/、hooks/、stores/、layout/）不得直接修改；
> 若需新增或擴充共用元件，先提 Issue。

## Milestones
- **3/16**：能看、能 review — stub + 基本 UI + mock props + 4 種狀態
- **3/23**：可 demo — 完整視覺 + mock 資料即時更新 + 互動
- **4/6**：整合穩定 — 真實 Gateway 對接 + 邊界 case + soak test
- **4/13**：展示版 freeze — 只修 bug

## 真相來源索引
| 需求 | 路徑 |
|------|------|
| Event/State Schema | ../docs/Pawai-studio/event-schema.md |
| Design Tokens | docs/design-tokens.md |
| Git Workflow | docs/git-workflow.md |
| 新人上手 | docs/onboarding.md |
| 系統架構 | ../docs/Pawai-studio/system-architecture.md |
| UI 編排規則 | ../docs/Pawai-studio/ui-orchestration.md |

## 技術棧
Next.js 16 + React 19 + TypeScript + Tailwind CSS + shadcn/ui + Zustand
```

### 1.4 `pawai-studio/docs/onboarding.md` 結構

```markdown
# 5 分鐘上手指南

## Step 1：啟動前端
cd pawai-studio/frontend
npm install
npm run dev
# → http://localhost:3000

## Step 2：啟動 Mock Server
cd pawai-studio/backend
uv pip install -r requirements.txt
python mock_server.py
# → http://localhost:8001

## Step 3：找到你的 Panel
你的檔案在 frontend/components/<你的功能>/<你的功能>-panel.tsx

## Step 4：看你的 Spec
pawai-studio/docs/<你的功能>-panel-spec.md
裡面有完整的型別定義、mock 資料、UI 結構、驗收 checklist

## Step 5：參考 ChatPanel
frontend/components/chat/chat-panel.tsx 是唯一完整範例
看它怎麼用 PanelCard、StatusBadge、EventItem

## Step 6：送 PR
看 docs/git-workflow.md
- Branch: feat/<你的功能>-panel
- 只改 components/<你的功能>/ 目錄
- PR title: feat(<scope>): <描述>
- 若發生衝突，先通知 maintainer，不要自己亂解
```

### 1.5 `docs/Pawai-studio/README.md` 改動

在檔案頂部加：

```markdown
> **開發者請直接看 [pawai-studio/README.md](../../pawai-studio/README.md)**
> 本目錄是正式設計規格庫，非日常開發入口。
```

---

## 2. Panel Spec 標準格式（AI-Ready）

每份 Panel Spec 使用以下固定結構。目標：人或 AI 拿到就能直接寫出正確的 Panel。

### 2.1 統一模板

```markdown
# [Feature] Panel Spec

> 真相來源：../../docs/Pawai-studio/event-schema.md
> 參考實作：../frontend/components/chat/chat-panel.tsx
> Design Tokens：design-tokens.md

## 1. 目標
一句話：這個 Panel 解決什麼問題。

## 2. 檔案範圍

### 可以改
- frontend/components/<feature>/<feature>-panel.tsx
- frontend/components/<feature>/ 下新增的子元件

### 不可以改（改了 PR 會被退）
- frontend/contracts/types.ts
- frontend/stores/*
- frontend/hooks/*
- frontend/components/layout/*
- frontend/components/chat/*
- 其他人的 frontend/components/<別人>/

### 不得直接修改現有 shared 元件；若需新增或擴充共用元件，先提 Issue
- frontend/components/shared/

## 3. Store Selectors 與使用型別

Panel 不接收 props，從 Zustand store 取資料：

import { useEventStore } from '@/stores/event-store'
import { useStateStore } from '@/stores/state-store'

// 使用的型別（從 contracts/types.ts import）
import type { XxxState, XxxEvent } from '@/contracts/types'

## 4. Mock Data
可直接複製貼上的測試資料（完整欄位，每個都有值）。

## 5. UI 結構

### 必要區塊
- 用 PanelCard 包裹（icon, title, status）
- 內容區塊列表

### 狀態矩陣
| 狀態 | 顯示內容 | StatusBadge |
|------|---------|-------------|
| 正常運作 | ... | active |
| 載入中 | ... | loading |
| 無資料 / 空狀態 | ... | inactive |
| 錯誤 / 離線 | ... | error |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

## 6. 互動規則
- hover / click / animation 的具體行為
- 引用 design-tokens.md 的動畫規範

## 7. 參考來源
| 需求 | 看哪裡 |
|------|--------|
| Event/State 欄位定義 | ../../docs/Pawai-studio/event-schema.md |
| 色彩/字體/間距 | design-tokens.md |
| PanelCard 用法 | frontend/components/shared/panel-card.tsx |
| StatusBadge 用法 | frontend/components/shared/status-badge.tsx |
| 完整 Panel 範例 | frontend/components/chat/chat-panel.tsx |

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] PanelCard 包裹，icon + title 正確
- [ ] 內部用假資料顯示核心 UI（至少 1 張卡片）
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] npm run lint + npm run build 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 完整視覺（色彩、動畫、間距符合 design-tokens.md）
- [ ] 空狀態、錯誤狀態有意義的提示文字與圖示
- [ ] 基本互動（hover、展開/收合）
- [ ] npm run lint + npm run build 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理真實資料邊界 case（缺欄位、格式異常、斷線重連）
- [ ] 與其他 Panel 共存不衝突（在設計上限內，例如 Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] npm run lint + npm run build 通過

## 9. Out of Scope（不要做）
- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
```

### 2.2 四份 Spec 差異點

模板固定，以下是每份 spec 的差異部分：

| | FacePanel | SpeechPanel | GesturePanel | PosePanel |
|--|-----------|-------------|--------------|-----------|
| **型別** | `FaceState`, `FaceIdentityEvent`, `FaceTrack` | `SpeechState`, `SpeechIntentEvent`, `SpeechPhase` | `GestureState`, `GestureEvent` | `PoseState`, `PoseEvent` |
| **icon** | `User` (lucide) | `Mic` (lucide) | `Hand` (lucide) | `Activity` (lucide) |
| **核心 UI** | 人物卡片（名字+相似度 bar+距離）、多人列表 | 狀態機 phase 顯示、ASR 轉寫文字、Intent badge | 手勢卡片（名稱+信心度+左右手） | 姿勢卡片（名稱+信心度）、跌倒警示 |
| **特殊狀態** | `track_lost` → 短暫保留後淡出（實作預設 5s，可調） | 10 種 phase 各有對應顏色與文字 | 無手勢時空狀態 | `fall_detected` → destructive 警示 |
| **M1 重點** | 顯示 1 個假人物卡 | 顯示假 phase + 假轉寫文字 | 顯示 1 個假手勢卡 | 顯示 1 個假姿勢卡 |
| **M2 重點** | 多人追蹤列表、相似度 bar 動態更新 | Phase 狀態機動畫、對話歷史捲動 | 手勢歷史列表 | 跌倒警示動畫、信心度顯示 |

---

## 3. 分工啟動

### 3.1 分工總表

| | 鄔 | 陳 | 黃 | 楊 |
|--|----|----|----|----|
| **Panel** | FacePanel | SpeechPanel | GesturePanel | PosePanel |
| **Branch** | `feat/face-panel` | `feat/speech-panel` | `feat/gesture-panel` | `feat/pose-panel` |
| **Spec** | `docs/face-panel-spec.md` | `docs/speech-panel-spec.md` | `docs/gesture-panel-spec.md` | `docs/pose-panel-spec.md` |
| **可改檔案** | `components/face/*` | `components/speech/*` | `components/gesture/*` | `components/pose/*` |
| **共用元件** | 不得直接修改現有；新增需先提 Issue | 同左 | 同左 | 同左 |
| **禁碰** | contracts/、stores/、hooks/、layout/、chat/、其他人的 components/ | 同左 | 同左 | 同左 |

### 3.2 Milestone 交付定義

#### M1（3/16）：能看、能 review

每人交付：
- [ ] `<Feature>Panel` 用 `PanelCard` 包裹，icon + title 正確
- [ ] 內部用假資料顯示核心 UI（至少 1 張卡片）
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過
- [ ] PR 開到 `main`，title 格式：`feat(<scope>): <描述>`

#### M2（3/23）：可 demo 的前端版本

每人交付：
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 視覺完成（色彩、動畫、間距符合 design-tokens.md）
- [ ] 空狀態、錯誤狀態有意義的提示文字與圖示
- [ ] 基本互動（hover、展開/收合）
- [ ] `npm run lint` + `npm run build` 通過

#### M3（4/6）：整合穩定版

每人交付：
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理真實資料邊界 case（缺欄位、格式異常、斷線重連）
- [ ] 與其他 Panel 共存不衝突（在設計上限內，例如 Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

#### 4/13：展示版 freeze

- Code freeze，只修 bug
- Demo A/B/C 全流程跑通

### 3.3 PR 流程

```
1. git checkout -b feat/<你的功能>-panel
2. 只改你的 components/<feature>/ 目錄
3. 送 PR 前先同步 main（若發生衝突，先通知 maintainer，不要自己亂解）
4. git push origin feat/<你的功能>-panel -u
5. 開 PR → title: feat(<scope>): <描述>
6. CI 自動跑 lint + build
7. Review 通過 → merge
```

### 3.4 卡住怎麼辦

| 情況 | 做法 |
|------|------|
| 需要新的 shared component | 開 Issue，描述需求，等核准後再做 |
| 發現 `contracts/types.ts` 缺型別 | 開 Issue，附上你需要的 interface，不要自己改 |
| Mock Server 缺你要的事件 | 開 Issue 或直接跟後端說，不要在前端 hardcode |
| 不確定設計要求 | 看你的 panel spec → 看 design-tokens.md → 看 ChatPanel → 再問 |
| Build 壞了不是你的問題 | 在 PR 裡標注，不要嘗試修別人的 code |

---

## 4. 最小接口核對

### 4.1 來源層級

| 層級 | 來源 | 角色 |
|------|------|------|
| L1 | `docs/Pawai-studio/event-schema.md` | Studio/Gateway JSON 真相來源 |
| L2 | `docs/architecture/interaction_contract.md` | ROS2 Topic 真相來源 |
| L3 | `types.ts` / `schemas.py` | 實作鏡像（應對齊 L1） |

### 4.2 核對結果

| 型別 | 狀態 | 差異類型 | 差異描述 | 以誰為準 | 修正動作 |
|------|------|----------|----------|----------|----------|
| FaceState | ✅ 一致 | — | L1/L2/L3 欄位名稱、型別、結構完全對齊 | — | 不動 |
| FaceIdentityEvent | ✅ 一致 | `projection_ok` | L2（ROS2）扁平 JSON，L1（Gateway）包進 PawAIEvent 信封。Gateway 投影行為，合理 | L1 管 Studio，L2 管 ROS2 | 不動 |
| SpeechState | ⚠️ 有差異 | `projection_ok` | `last_tts_text` 存在於 L1、types.ts、schemas.py，但 L2 沒有。此欄位由 Gateway 從 TTS 狀態聚合填入，非 ROS2 原生欄位 | L1（Gateway 投影欄位） | 在 event-schema.md 加註「Gateway-derived field」 |
| SpeechIntentEvent | ✅ 一致 | `projection_ok` | 同 FaceIdentityEvent — L2 扁平，L1 包信封。欄位與 enum 完全對齊 | L1 管 Studio，L2 管 ROS2 | 不動 |
| GestureState | ✅ 一致 | — | L1/L3 欄位名稱、型別、enum 完全對齊（active, current_gesture, confidence, hand, status） | — | 不動 |
| GestureEvent | ✅ 一致 | `projection_ok` | 同上 envelope 投影模式。gesture/confidence/hand 欄位與 enum 一致 | L1 管 Studio，L2 管 ROS2 | 不動 |
| PoseState | ✅ 一致 | — | L1/L3 欄位名稱、型別、enum 完全對齊（active, current_pose, confidence, track_id, status） | — | 不動 |
| PoseEvent | ✅ 一致 | `projection_ok` | 同上 envelope 投影模式。pose/confidence/track_id 欄位與 enum 一致 | L1 管 Studio，L2 管 ROS2 | 不動 |

### 4.3 結論

- 8 組型別全部通過，無 `drift_bug`
- 唯一差異是 `SpeechState.last_tts_text` 的層級歸屬，屬於 `projection_ok`
- `types.ts` 和 `schemas.py` 不需修改
- `event-schema.md` 加一行註解即可

### 4.4 額外發現（記錄備查，不在本次修正範圍）

| 項目 | 說明 |
|------|------|
| `schemas.py` 的 `SystemHealth.jetson` 用 `dict` | 應改成具型別的 Pydantic model，對齊 types.ts |
| `schemas.py` 的 `SystemHealth.modules` 用 `list[dict]` | 應改成 `list[ModuleHealth]`，對齊 types.ts 的 `ModuleHealth` interface |
| `schemas.py` 的 `FaceTrack.bbox` 是 `tuple[int, int, int, int]` | JSON 序列化等同 array，功能一致，不動 |

---

## 5. 實作清單摘要

本設計文件確認後，需要執行以下實作：

1. **新增 `pawai-studio/README.md`** — Developer Launcher 格式
2. **新增 `pawai-studio/docs/onboarding.md`** — 5 分鐘上手指南
3. **重寫 4 份 Panel Spec** — 統一 AI-ready 格式（Section 2 模板）
4. **修改 `docs/Pawai-studio/README.md`** — 加頂部導向提示
5. **修改 `docs/Pawai-studio/event-schema.md`** — `last_tts_text` 加「Gateway-derived field」註解

---

*最後更新：2026-03-14*
*維護者：System Architect*
