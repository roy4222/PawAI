# 楊沛蓁 — 物體辨識頁 `/studio/object`

## 你的檔案

| 檔案 | 說明 |
|------|------|
| `app/(studio)/studio/object/page.tsx` | 你的頁面（目前 28 行，很空） |
| `components/object/object-panel.tsx` | 現有 Panel（158 行，有基本功能） |
| `components/object/` | 可以在這裡新增任何 .tsx |

## 規格參考

- 無獨立 spec，參考 `docs/Pawai-studio/README.md` 的物體辨識段落
- `pawai-studio/docs/design-tokens.md` — 顏色、字型、間距

## Mock 資料長什麼樣

Mock server 每 2 秒會推送 object 事件，資料結構：

```json
{
  "source": "object",
  "event_type": "object_detected",
  "data": {
    "stamp": 1712345678.0,
    "active": true,
    "status": "active",
    "objects": [
      {
        "class_name": "cup",
        "class_id": 41,
        "confidence": 0.85,
        "bbox": [120, 150, 280, 350]
      },
      {
        "class_name": "book",
        "class_id": 73,
        "confidence": 0.72,
        "bbox": [300, 100, 450, 250]
      }
    ]
  }
}
```

Mock 會隨機產生的物體：`cup`(41), `bottle`(39), `chair`(56), `person`(0), `dog`(16), `book`(73)

在你的 component 裡這樣取：

```tsx
import { useStateStore } from "@/stores/state-store";

const objectState = useStateStore(s => s.objectState);
// objectState.detected_objects → 物體陣列
// 每個物體有 class_name, class_id, confidence, bbox
```

## 目前的頁面

```
┌─────────────────────────┐
│  ObjectPanel（小小的）    │
│    + 開發說明文字         │
│                         │
│     （巨大空白）          │
│                         │
└─────────────────────────┘
```

## 建議功能（挑你想做的，自由發揮）

### 1. 物體偵測卡片 Grid（簡單）

每個偵測到的物體一張卡片，用 grid 排列：

```
┌──────────┐ ┌──────────┐
│  ☕ cup  │ │  📖 book │
│  85%     │ │  72%     │
│ ██████░░ │ │ █████░░░ │
└──────────┘ └──────────┘
```

信心度用 progress bar 表示。每個 COCO 類別配一個 Emoji。

### 2. COCO 類別對照表（簡單）

折疊式表格列出常見的 COCO 物體中英對照，標記哪些會觸發 TTS：

```
| class_id | 英文    | 中文   | 會觸發互動？ |
|----------|--------|--------|:----------:|
| 41       | cup    | 杯子   | ✅ 「你要喝水嗎？」|
| 39       | bottle | 瓶子   | ✅ 「喝點水吧」   |
| 73       | book   | 書本   | ✅ 「在看書啊」   |
| 56       | chair  | 椅子   | ❌              |
| 0        | person | 人     | ❌              |
```

### 3. 偵測歷史統計（中等）

用長條圖統計各類別偵測次數：

```
cup     ████████████ 12
person  ████████ 8
book    █████ 5
chair   ███ 3
bottle  ██ 2
dog     █ 1
```

### 4. 即時偵測 Feed（中等）

像 Twitter feed 一樣，最新偵測到的物體滾動顯示：

```
10:30:05  ☕ cup (85%) + 📖 book (72%)
10:30:07  🧑 person (91%)
10:30:12  🪑 chair (78%) + 🐕 dog (65%)
```

### 5. 你自己想加的任何功能

頁面是你的，隨你發揮。

## 怎麼測試

```bash
# 啟動 mock server
cd pawai-studio/backend && uvicorn mock_server:app --port 8080 --reload

# 啟動前端
cd pawai-studio/frontend && npm run dev

# 打開 http://localhost:3000/studio/object
# 每 2 秒有隨機物體事件

# 手動觸發指定物體
curl -X POST http://localhost:8080/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "object", "event_type": "object_detected", "data": {"stamp": 0, "active": true, "status": "active", "objects": [{"class_name": "cup", "class_id": 41, "confidence": 0.92, "bbox": [100,100,250,300]}, {"class_name": "bottle", "class_id": 39, "confidence": 0.78, "bbox": [300,150,400,350]}], "detected_objects": [{"class_name": "cup", "class_id": 41, "confidence": 0.92, "bbox": [100,100,250,300]}, {"class_name": "bottle", "class_id": 39, "confidence": 0.78, "bbox": [300,150,400,350]}]}}'

# 觸發 Demo A 場景（連續事件流）
curl -X POST http://localhost:8080/mock/scenario/demo_a
```
