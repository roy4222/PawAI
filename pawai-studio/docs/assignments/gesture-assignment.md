# 黃旭 — 手勢辨識頁 `/studio/gesture`

## 你的檔案

| 檔案 | 說明 |
|------|------|
| `app/(studio)/studio/gesture/page.tsx` | 你的頁面（目前 32 行，很空） |
| `components/gesture/gesture-panel.tsx` | 現有 Panel（174 行，有基本功能） |
| `components/gesture/` | 可以在這裡新增任何 .tsx |

## 規格參考

- `pawai-studio/docs/gesture-panel-spec.md` — 完整功能規格
- `pawai-studio/docs/design-tokens.md` — 顏色、字型、間距

## Mock 資料長什麼樣

Mock server 每 2 秒會推送 gesture 事件，資料結構：

```json
{
  "source": "gesture",
  "event_type": "gesture_detected",
  "data": {
    "stamp": 1712345678.0,
    "active": true,
    "current_gesture": "stop",
    "confidence": 0.87,
    "hand": "right",
    "status": "active"
  }
}
```

可能的 `current_gesture` 值：`"wave"`, `"stop"`, `"point"`, `"ok"`

在你的 component 裡這樣取：

```tsx
import { useStateStore } from "@/stores/state-store";

const gestureState = useStateStore(s => s.gestureState);
// gestureState.current_gesture → "stop"
// gestureState.confidence → 0.87
// gestureState.hand → "right"
```

## 目前的頁面

```
┌─────────────────────────┐
│  GesturePanel（小小的）   │
│    + 開發說明文字         │
│                         │
│     （巨大空白）          │
│                         │
└─────────────────────────┘
```

## 建議功能（挑你想做的，自由發揮）

### 1. 手勢參考圖卡（簡單）

頁面上方用 grid 列出所有支援的手勢：

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  👋 wave │ │  ✋ stop │ │  👆 point│ │  👌 ok  │
│  揮手    │ │  停止    │ │  指向    │ │  OK     │
│ →招呼   │ │ →停止Go2│ │ →[無]   │ │ →開心   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

讓觀眾一眼知道可以比哪些手勢、每個手勢會觸發什麼動作。

### 2. 即時手勢大字顯示（簡單）

偵測到手勢時在頁面中央大字+大 Emoji 顯示，幾秒後淡出：

```
        ✋
      STOP
   信心度 87%
```

### 3. 手勢歷史統計圖（中等）

用長條圖或圓餅圖顯示各手勢觸發次數。可以用純 CSS bar：

```
wave  ████████ 8
stop  ████████████ 12
point ███ 3
ok    █████ 5
```

用 `useEventStore` 過濾 gesture events 來統計。

### 4. 事件歷史列表（簡單）

列出最近 20 筆手勢事件，每筆顯示：時間 + 手勢名稱 + 信心度 + 左/右手

### 5. 技術說明折疊區（簡單）

底部加一個可展開/收起的說明區，介紹 MediaPipe Gesture Recognizer 的原理、支援手勢、有效距離（1-3m）。內容可以從 `docs/手勢辨識/README.md` 複製。

### 6. 你自己想加的任何功能

頁面是你的，隨你發揮。

## 怎麼測試

```bash
# 啟動 mock server
cd pawai-studio/backend && uvicorn mock_server:app --port 8001 --reload

# 啟動前端
cd pawai-studio/frontend && npm run dev

# 打開 http://localhost:3000/studio/gesture
# 每 2 秒有隨機手勢事件

# 手動觸發 stop 手勢
curl -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "gesture", "event_type": "gesture_detected", "data": {"stamp": 0, "active": true, "current_gesture": "stop", "confidence": 0.95, "hand": "right", "status": "active"}}'

# 手動觸發 wave 手勢
curl -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "gesture", "event_type": "gesture_detected", "data": {"stamp": 0, "active": true, "current_gesture": "wave", "confidence": 0.88, "hand": "left", "status": "active"}}'
```
