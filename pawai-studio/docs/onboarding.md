# 5 分鐘上手指南

本指南讓你（或你的 AI agent）快速開始 Panel 開發。

---

## Step 1：一鍵啟動

```bash
# 從 repo 根目錄（elder_and_dog/）
bash pawai-studio/start.sh
```

啟動成功後會看到：
```
  Studio:      http://localhost:3000/studio
  Mock Server:  http://localhost:8001
  WebSocket:    ws://localhost:8001/ws/events
```

打開 **http://localhost:3000/studio** → 應該看到 Studio 頁面，左側 Chat，右側面板區。

> **注意**：是 `/studio` 不是 `/`。首頁 `/` 是 landing page。

---

## Step 2：驗證 Mock Server

```bash
# 確認活著
curl http://localhost:8001/api/health

# 觸發 Demo A（6 個事件依序推送到 WebSocket，Studio 會即時顯示）
curl -X POST http://localhost:8001/mock/scenario/demo_a
```

Mock Server 提供與真實 Gateway 完全相同的 WebSocket / REST 介面。

> **手動啟動**（如果一鍵腳本不適用）：
> ```bash
> # Terminal 1
> cd pawai-studio/backend
> pip3 install --user fastapi uvicorn pydantic websockets
> python3 -m uvicorn mock_server:app --port 8001
>
> # Terminal 2
> cd pawai-studio/frontend
> npm install && npm run dev
> ```

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
