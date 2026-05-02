# PawAI Studio Reference

## 定位

以 chat 為主入口、可動態展開觀測與控制面板的 embodied AI studio。
整個 PawAI 系統的統一操作與展示入口。

## 權威文件

- **Studio 設計規格**：`docs/pawai-brain/studio/README.md`
- **系統架構**：`docs/pawai-brain/studio/specs/system-architecture.md`
- **事件 Schema**：`docs/pawai-brain/studio/specs/event-schema.md`
- **UI 編排**：`docs/pawai-brain/studio/specs/ui-orchestration.md`
- **Brain Adapter**：`docs/pawai-brain/studio/specs/brain-adapter.md`
- **開發者入口**：`pawai-studio/README.md`

## 核心程式

| 路徑 | 用途 |
|------|------|
| `pawai-studio/` | 前端 Next.js 專案根目錄 |
| `pawai-studio/start.sh` | 一鍵啟動（含 Mock Server） |

## 技術棧

- Frontend：Next.js (React)
- 即時通訊：WebSocket
- Backend：FastAPI + WebSocket (Studio Gateway)
- Event Bus：Redis (Pub/Sub + KV + Streams)
- Mock：Mock Event Server (FastAPI) @ localhost:8001

## 面板

ChatPanel / CameraPanel / FacePanel / SpeechPanel / GesturePanel / PosePanel / TimelinePanel / SystemHealthPanel / BrainPanel / SkillButtons / DemoShowcase

## 啟動

```bash
bash pawai-studio/start.sh
# → http://localhost:3000/studio
# → Mock Server: http://localhost:8001
```

## 里程碑

- 前端截止：3/26
- Demo Showcase 頁面用於 4/13 展示
