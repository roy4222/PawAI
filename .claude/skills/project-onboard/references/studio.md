# PawAI Studio Reference

> 最後更新：2026-03-16

## 模組定位

PawAI Studio 是整個系統的**統一操作與展示入口**。
設計原則：「預設像 ChatGPT（簡潔對話），需要觀測時像 Foxglove 展開即時面板」。

## 權威文件

| 文件 | 用途 |
|------|------|
| `docs/Pawai-studio/README.md` | 規格總綱 |
| `docs/Pawai-studio/event-schema.md` | Event/State/Command JSON schema |
| `docs/Pawai-studio/system-architecture.md` | Gateway、Mock Server、快慢系統 |
| `docs/Pawai-studio/ui-orchestration.md` | Layout preset + 切換規則 |
| `pawai-studio/docs/design-tokens.md` | 色彩、字體、spacing |
| `pawai-studio/docs/{face,speech,gesture,pose}-panel-spec.md` | 各 panel 視覺與互動規範 |

## 技術棧

| 層級 | 技術 |
|------|------|
| 前端 | Next.js 16 + React 19 + TypeScript + Tailwind + shadcn/ui + Zustand |
| 後端 | FastAPI + uvicorn（RTX 8000） |
| 即時通訊 | WebSocket（Gateway ↔ Frontend） |
| 事件總線 | Redis Pub/Sub + Streams + KV |
| 測試/開發 | Mock Event Server（FastAPI, :8001） |

## 核心面板

| 面板 | 資料來源 | 狀態 |
|------|---------|:----:|
| ChatPanel | WebSocket ↔ Gateway | P0 |
| CameraPanel | MJPEG / WebRTC | P0 |
| FacePanel | `/state/perception/face` | P0 |
| SpeechPanel | `/state/interaction/speech` | P0 |
| BrainPanel | `/state/executive/brain` | P0 |
| TimelinePanel | Redis Streams | P0 |
| SystemHealthPanel | `/state/system/health` | P0 |
| SkillButtons | `POST /api/command` | P0 |
| GesturePanel | `/event/gesture_detected` | P1 |
| PosePanel | `/event/pose_detected` | P1 |

## 啟動開發

```bash
# 一鍵啟動（推薦）
bash pawai-studio/start.sh
# → Frontend:    http://localhost:3000/studio
# → Mock Server: http://localhost:8001
# → WebSocket:   ws://localhost:8001/ws/events

# 觸發 Demo A 場景
curl -X POST http://localhost:8001/mock/scenario/demo_a
```

## 前端目錄結構

```
pawai-studio/frontend/
├── app/           # Next.js App Router
├── components/
│   ├── panels/    # 各 Panel 元件（ChatPanel, FacePanel, ...）
│   ├── layout/    # StudioLayout, PanelContainer
│   └── shared/    # PanelCard, StatusBadge, MetricChip（不可直接改）
├── hooks/         # useWebSocket, useEventStream, useLayoutManager（不可直接改）
├── stores/        # Zustand: eventStore, stateStore, layoutStore（不可直接改）
├── contracts/     # TypeScript 型別（不可直接改）
└── public/        # 靜態資源
```

## 分工與開發頁面

| 人 | Panel | URL | Spec |
|----|-------|-----|------|
| 鄔 | FacePanel | `/studio/face` | `face-panel-spec.md` |
| 陳 | SpeechPanel | `/studio/speech` | `speech-panel-spec.md` |
| 黃 | GesturePanel | `/studio/gesture` | `gesture-panel-spec.md` |
| 楊 | PosePanel | `/studio/pose` | `pose-panel-spec.md` |

## 已知陷阱

- `shared/`、`hooks/`、`stores/`、`layout/`、`contracts/` 不可直接改，需開 Issue
- Mock Server 與 Gateway 端點路徑相同，前端切 URL 即可切換真假資料
- Layout 切換由 `source + event_type` 驅動，使用者手動收合優先
- `pose_detected (fallen)` 會強制展開 PosePanel（安全功能）

## 當前狀態

| 里程碑 | 日期 | 狀態 |
|--------|------|------|
| MVP（能看能 review） | 3/16 | [WIP] |
| Alpha（完整視覺 + mock 即時更新） | 3/23 | [PENDING] |
| Beta（真實 Gateway 資料） | 4/6 | [PENDING] |
| Freeze（僅修 bug） | 4/13 | [PENDING] |
