# PawAI Studio

> Status: current

> 以 chat 為主入口的 embodied AI studio — 統一操作與展示入口。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 前端開發截止，後端 4/9 後啟動 |
| 版本/決策 | Next.js + FastAPI + Redis |
| 完成度 | 50%（前端框架完成，後端 WebSocket bridge 不存在） |
| 最後驗證 | 2026-03-16 |
| 入口檔案 | `pawai-studio/frontend/` |
| 測試 | `cd pawai-studio && bash start.sh` |

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
Studio Frontend (Next.js React)
    ↓ WebSocket
Studio Gateway (FastAPI) ← 待建
    ↓ Redis Pub/Sub
ROS2 Bridge ← 待建
    ↓
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
