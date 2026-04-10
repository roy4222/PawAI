# 楊沛蓁 — 姿勢辨識頁 `/studio/pose`

> **4/11 分工調整**：從 陳如恩 改為 楊沛蓁（陳如恩專注語音模組）。

## 你的檔案

| 檔案 | 說明 |
|------|------|
| `app/(studio)/studio/pose/page.tsx` | 你的頁面（目前 32 行，很空） |
| `components/pose/pose-panel.tsx` | 現有 Panel（94 行，是最簡陋的一個） |
| `components/pose/` | 可以在這裡新增任何 .tsx |

## 規格參考

- `pawai-studio/docs/pose-panel-spec.md` — 完整功能規格
- `pawai-studio/docs/design-tokens.md` — 顏色、字型、間距

## Mock 資料長什麼樣

Mock server 每 2 秒會推送 pose 事件，資料結構：

```json
{
  "source": "pose",
  "event_type": "pose_detected",
  "data": {
    "stamp": 1712345678.0,
    "active": true,
    "current_pose": "standing",
    "confidence": 0.92,
    "track_id": 1,
    "status": "active"
  }
}
```

可能的 `current_pose` 值：`"standing"`, `"sitting"`, `"crouching"`, `"fallen"`

在你的 component 裡這樣取：

```tsx
import { useStateStore } from "@/stores/state-store";

const poseState = useStateStore(s => s.poseState);
// poseState.current_pose → "standing"
// poseState.confidence → 0.92
// poseState.track_id → 1
```

## 目前的頁面

```
┌─────────────────────────┐
│   PosePanel（最簡陋）     │
│    + 開發說明文字         │
│                         │
│     （巨大空白）          │
│                         │
└─────────────────────────┘
```

這是五個模組頁面裡最需要擴充的一個（才 94 行），發揮空間最大。

## 建議功能（挑你想做的，自由發揮）

### 1. 跌倒警報全頁效果（重要，建議優先做）

當 `current_pose === "fallen"` 時，整個頁面要有明顯警報效果：

```
┌─ 紅色邊框 pulse 動畫 ─────────────────┐
│  ⚠️ 偵測到跌倒！                       │
│                                       │
│     [巨大的跌倒圖示或 Emoji]           │
│     信心度 95%                         │
│     Track ID: 1                       │
│                                       │
│  請立即確認使用者安全                   │
└───────────────────────────────────────┘
```

Tailwind 參考：
```tsx
// 正常狀態
<div className="border border-border">

// 跌倒警報
<div className="border-2 border-red-500 animate-pulse bg-red-50">
```

### 2. 姿勢圖示顯示（簡單）

用大圖示表示目前姿勢：

```
🧍 standing（站立）
🪑 sitting（坐下）
🧎 crouching（蹲下）
🚨 fallen（跌倒）← 紅色 + 閃爍
```

### 3. 姿勢歷史時間軸（簡單）

最近 20 筆姿勢變化，跌倒事件標紅：

```
10:30:05  🧍 standing   92%
10:30:07  🪑 sitting    88%
10:30:12  🚨 fallen     95%  ← 紅色背景
10:30:15  🧍 standing   90%
```

### 4. 統計卡片（簡單）

```
┌──────────┐ ┌──────────┐ ┌──────────┐
│ 目前姿勢  │ │ 跌倒次數  │ │ 平均信心度│
│ standing │ │    2     │ │   89%    │
└──────────┘ └──────────┘ └──────────┘
```

### 5. 技術說明折疊區（簡單）

介紹 MediaPipe Pose 33 個關鍵點、跌倒偵測邏輯（vertical_ratio guard）、已知限制（單人追蹤、側面角度依賴）。內容從 `docs/姿勢辨識/README.md` 複製。

### 6. 你自己想加的任何功能

頁面是你的，隨你發揮。

## 怎麼測試

```bash
# 啟動 mock server
cd pawai-studio/backend && uvicorn mock_server:app --port 8080 --reload

# 啟動前端
cd pawai-studio/frontend && npm run dev

# 打開 http://localhost:3000/studio/pose
# 每 2 秒有隨機姿勢事件（包括 fallen！）

# 手動觸發跌倒事件（測試你的跌倒警報效果）
curl -X POST http://localhost:8080/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "pose", "event_type": "pose_detected", "data": {"stamp": 0, "active": true, "current_pose": "fallen", "confidence": 0.95, "track_id": 1, "status": "active"}}'

# 手動觸發站立（恢復正常）
curl -X POST http://localhost:8080/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "pose", "event_type": "pose_detected", "data": {"stamp": 0, "active": true, "current_pose": "standing", "confidence": 0.90, "track_id": 1, "status": "active"}}'
```
