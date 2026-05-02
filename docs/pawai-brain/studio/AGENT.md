# PawAI Studio — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟 Studio 互動。

## 模組邊界

- **前端**：`pawai-studio/frontend/`（Next.js React）
- **後端**：`pawai-studio/backend/`（FastAPI，待建大部分）
- **上游**：所有 ROS2 感知 topics
- **下游**：使用者瀏覽器

## 介面（現有）

| 端點 | 類型 | 說明 |
|------|------|------|
| `http://localhost:3000/studio` | HTTP | 前端入口 |
| `http://localhost:8001` | HTTP | Mock Event Server |
| `/api/command` | REST | Go2 指令 |
| `/api/chat` | REST | 對話輸入 |
| `/api/brain` | REST | Brain 狀態 |
| `/api/health` | REST | 健康檢查 |

## 待建介面（4/9 後）

- WebSocket Gateway（即時事件廣播）
- Redis Pub/Sub（ROS2 → Studio bridge）
- ROS2 Bridge node

## 事件流

```
ROS2 Topics → [ROS2 Bridge 待建] → Redis → Studio Gateway → WebSocket → Browser
Browser → REST API → Studio Gateway → [ROS2 Bridge 待建] → /webrtc_req
```

## 接手確認清單

- [ ] `bash pawai-studio/start.sh` 能啟動？
- [ ] `http://localhost:3000/studio` 可開啟？
- [ ] Mock server `http://localhost:8001/api/health` 回 200？
- [ ] 設計規格在 `docs/pawai-brain/studio/specs/` 下
