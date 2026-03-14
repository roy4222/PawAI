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
| Event / State Schema | [`../docs/Pawai-studio/event-schema.md`](../docs/Pawai-studio/event-schema.md) |
| Design Tokens | [`docs/design-tokens.md`](docs/design-tokens.md) |
| Git Workflow | [`docs/git-workflow.md`](docs/git-workflow.md) |
| 新人上手 | [`docs/onboarding.md`](docs/onboarding.md) |
| 系統架構 | [`../docs/Pawai-studio/system-architecture.md`](../docs/Pawai-studio/system-architecture.md) |
| UI 編排規則 | [`../docs/Pawai-studio/ui-orchestration.md`](../docs/Pawai-studio/ui-orchestration.md) |
| Brain Adapter | [`../docs/Pawai-studio/brain-adapter.md`](../docs/Pawai-studio/brain-adapter.md) |

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
