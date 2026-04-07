# PawAI Studio

> Status: current

> 以 chat 為主入口的 embodied AI studio — 統一操作與展示入口。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **即時觀測台 + Mission Control UI**（4/7） |
| 版本/決策 | Next.js 16（前端）+ FastAPI + rclpy（Gateway） |
| 完成度 | Gateway ROS2 bridge ✅ + 前端 5 panel 即時數據 ✅ + Mission Control 首頁 ✅ |
| 最後驗證 | 2026-04-07 |
| 入口檔案 | `pawai-studio/gateway/studio_gateway.py`（Gateway）、`pawai-studio/frontend/`（前端） |
| 測試 | Gateway 15 tests PASS、Frontend build PASS |

## 啟動方式

```bash
bash pawai-studio/start.sh
# → http://localhost:3000/studio
# → Mock Server: http://localhost:8001
```

## 核心流程

```
使用者操作（Chat / 技能按鈕 / 面板）
    ↓
Studio Frontend (Next.js React) ← 5 panel 即時顯示
    ↓ WebSocket /ws/events（ROS2→瀏覽器）
    ↓ WebSocket /ws/text + /ws/speech（瀏覽器→ROS2）
Studio Gateway (FastAPI + rclpy, Jetson:8080)
    ↓ rclpy subscribe 5 topics + publish speech intent
ROS2 Topics（face/speech/gesture/pose/object）
```

## 面板清單

| Panel | 路由 | 狀態 |
|-------|------|------|
| Chat | `/studio` | ✅ Mission Control 首頁 |
| Face | `/studio/face` | ✅ 即時 track 顯示 |
| Speech | `/studio/speech` | ✅ phase + 對話記錄 |
| Gesture | `/studio/gesture` | ✅ 手勢卡片 + 歷史 |
| Pose | `/studio/pose` | ✅ 姿勢 + 信心度 |
| Object | `/studio/object` | ✅ COCO 物件偵測 |

所有 panel 可折疊（click header）、sidebar 可拖寬（280-600px）、header 有連結到詳細頁。

## Gateway 端點

| 端點 | 方向 | 用途 |
|------|------|------|
| `GET /health` | — | 健康檢查 |
| `WS /ws/events` | ROS2→瀏覽器 | 感知事件廣播（face/gesture/pose/speech/object） |
| `WS /ws/text` | 瀏覽器→ROS2 | 文字輸入 → intent → publish |
| `WS /ws/speech` | 瀏覽器→ROS2 | 錄音 → ASR → intent → publish（5MB cap） |
| `GET /speech` | — | push-to-talk 獨立測試頁 |

## 已知問題

- Speech push-to-talk 尚未併入 Studio 主面板（仍在獨立 `/speech` 頁）
- 真機驗證待 Jetson 部署
- Object panel 偵測率受限於 YOLO26n

## 下一步

- 下午：Speech bridge 併入 Studio chat
- 4/9：團隊接手 UI 打磨 + 文書分工

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| specs/ | brain-adapter、event-schema、system-architecture、ui-orchestration 設計 |
