# 盧柏宇 — 人臉辨識頁 `/studio/face`（參考用）

> **4/11 分工調整**：從 鄔雨彤 改為 盧柏宇（人臉模組屬盧柏宇負責）。

## 你的檔案

| 檔案 | 說明 |
|------|------|
| `app/(studio)/studio/face/page.tsx` | 你的頁面（目前 32 行，很空） |
| `components/face/face-panel.tsx` | 現有 Panel（129 行，有基本功能） |
| `components/face/face-track-card.tsx` | 追蹤卡片子元件（90 行） |
| `components/face/` | 可以在這裡新增任何 .tsx |

## 規格參考

- `pawai-studio/docs/face-panel-spec.md` — 完整功能規格
- `pawai-studio/docs/design-tokens.md` — 顏色、字型、間距

## Mock 資料長什麼樣

Mock server 每 2 秒會推送 face 事件，資料結構：

```json
{
  "source": "face",
  "event_type": "identity_stable",
  "data": {
    "stamp": 1712345678.0,
    "face_count": 2,
    "tracks": [
      {
        "track_id": 1,
        "stable_name": "Roy",
        "sim": 0.92,
        "distance_m": 1.2,
        "bbox": [100, 100, 200, 280],
        "mode": "stable"
      },
      {
        "track_id": 2,
        "stable_name": "unknown",
        "sim": 0.15,
        "distance_m": 2.5,
        "bbox": [250, 100, 350, 280],
        "mode": "hold"
      }
    ]
  }
}
```

在你的 component 裡這樣取：

```tsx
import { useStateStore } from "@/stores/state-store";

const faceState = useStateStore(s => s.faceState);
// faceState.face_count → 目前追蹤人數
// faceState.tracks → 每個人的資訊陣列
```

## 目前的頁面

```
┌─────────────────────────┐
│    FacePanel（小小的）    │
│    + 開發說明文字         │
│                         │
│     （巨大空白）          │
│                         │
└─────────────────────────┘
```

## 建議功能（挑你想做的，自由發揮）

以下是一些建議，你可以全做、挑幾個做、或自己想新功能加上去：

### 1. 統計卡片列（簡單）

頁面頂部放一排數字卡片：

```
┌──────────┐ ┌──────────┐ ┌──────────┐
│ 追蹤人數  │ │ 已辨識次數│ │ 平均相似度│
│    2     │ │    15    │ │   78%    │
└──────────┘ └──────────┘ └──────────┘
```

用 `useEventStore` 過濾 face events 來算計數。

### 2. 事件歷史時間軸（簡單）

現在 face-panel.tsx 有事件歷史但被 `false &&` 隱藏了。你可以：
- 啟用它（改掉那個 `false`）
- 或自己寫一個更好看的版本（卡片式、有時間戳、有顏色區分 event_type）

### 3. 人臉資料庫展示區（中等）

顯示系統裡已註冊的人（Roy、小明等），可以是靜態列表或從 mock 資料推斷。

### 4. 追蹤視覺化（中等）

在一個虛擬畫布上，根據 `bbox` 座標畫出每個人臉的位置方塊，顏色區分 stable/hold/unknown。

### 5. 你自己想加的任何功能

頁面是你的，隨你發揮。只要資料從 `useStateStore` 或 `useEventStore` 來就行。

## 怎麼測試

```bash
# 啟動 mock server
cd pawai-studio/backend && uvicorn mock_server:app --port 8080 --reload

# 啟動前端
cd pawai-studio/frontend && npm run dev

# 打開 http://localhost:3000/studio/face
# 你應該會看到每 2 秒有新的人臉資料跳出來

# 手動觸發特定事件
curl -X POST http://localhost:8080/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "face", "event_type": "identity_stable", "data": {"track_id": 1, "stable_name": "Roy", "sim": 0.92, "distance_m": 1.5, "face_count": 1, "tracks": [{"track_id": 1, "stable_name": "Roy", "sim": 0.92, "distance_m": 1.5, "bbox": [100,100,200,280], "mode": "stable"}], "stamp": 0}}'
```
