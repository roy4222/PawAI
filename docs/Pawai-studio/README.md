# PawAI Studio

> Status: current

> 以 chat 為主入口的 embodied AI studio — 統一操作與展示入口。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Gateway 文字模式 E2E 通過**（4/6） |
| 版本/決策 | Next.js（前端）+ FastAPI + rclpy（Gateway） |
| 完成度 | Gateway speech bridge ✅，前端面板接真實數據待做 |
| 最後驗證 | 2026-04-06 |
| 入口檔案 | `pawai-studio/gateway/`（Gateway）、`pawai-studio/frontend/`（前端） |
| 測試 | Gateway: `python3 pawai-studio/gateway/studio_gateway.py` → http://JETSON_IP:8080/speech |

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
Studio Frontend (Next.js React) ← 前端面板
    ↓ WebSocket
Studio Gateway (FastAPI + rclpy, Jetson:8080) ← **已建，speech bridge 通過**
    ↓ rclpy 直接 publish（本機，無跨機 DDS）
ROS2 Topics（face/speech/gesture/pose/brain）
```

## 面板清單

Chat / Camera / Face / Speech / Gesture / Pose / Timeline / SystemHealth / Brain / SkillButtons / DemoShowcase

## 已知問題

- 後端 WebSocket bridge 不存在（4/9 後啟動）
- Mock Server 與實際 ROS2 topic 的對接是黑盒
- 前端已截止 3/26

## 下一步

- 4/9 後由團隊接手後端開發
- Sprint Day 11：交 Studio backend interface draft

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| specs/ | brain-adapter、event-schema、system-architecture、ui-orchestration 設計 |
