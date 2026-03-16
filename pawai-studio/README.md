# PawAI Studio — Developer Launcher

> **正式規格以 [`../docs/Pawai-studio/*.md`](../docs/Pawai-studio/) 為準；**
> `docs/*.md` 是實作導引與 panel-level spec。若有衝突，以 `docs/Pawai-studio/` 為準。

---

## Quick Start

### 一鍵啟動（推薦）

```bash
# 從 repo 根目錄
bash pawai-studio/start.sh
```

啟動後打開 **http://localhost:3000/studio** 就能看到 Studio。
Ctrl+C 停止，或 `bash pawai-studio/stop.sh`。

### 手動啟動

**需求**：Python 3.10+、Node >= 18、npm

```bash
# Terminal 1: Mock Server
cd pawai-studio/backend
pip3 install --user fastapi uvicorn pydantic websockets  # 第一次才需要
python3 -m uvicorn mock_server:app --port 8001
# → http://localhost:8001

# Terminal 2: Frontend
cd pawai-studio/frontend
npm install  # 第一次才需要
npm run dev
# → http://localhost:3000/studio
```

### 驗證

```bash
# Mock Server 活著嗎？
curl http://localhost:8001/api/health

# 觸發 Demo A 場景（6 個事件依序推送到 WebSocket）
curl -X POST http://localhost:8001/mock/scenario/demo_a
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
| **3/16** | 能看、能 review — stub + 基本 UI + store-based mock data + 4 種狀態 |
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
