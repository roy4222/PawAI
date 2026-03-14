# GesturePanel Spec — 手勢辨識面板

**負責人**：黃
**版本**：v1.0
**建立日期**：2026-03-14

> **本版不依賴特定模型。** MediaPipe Hands / 其他模型皆可，輸出需符合同一 props 介面。
> 模型研究未完成不影響 Panel UI 開發，先用 Mock 資料。

---

## 目標

顯示手勢辨識結果：偵測到的手勢類型、信心度、左右手、事件歷史。

---

## Props 介面

```typescript
interface GesturePanelProps {
  data: GestureState;                   // 即時狀態
  events: GestureEvent[];               // 歷史事件列表
}

// 來自 contracts/types.ts
interface GestureState {
  stamp: number;
  active: boolean;                      // 是否有手勢被偵測
  current_gesture: string | null;       // 當前手勢，null 表示無
  confidence: number;                   // [0.0, 1.0]
  hand: "left" | "right" | null;
  status: "active" | "inactive" | "loading";
}

interface GestureEvent {
  id: string;
  timestamp: string;
  source: "gesture";
  event_type: "gesture_detected";
  data: {
    gesture: string;        // "wave" | "stop" | "point" | "ok"
    confidence: number;
    hand: "left" | "right";
  };
}
```

---

## 資料來源

| 資料 | 來源 Topic | 更新頻率 |
|------|-----------|---------|
| GestureState | `/state/perception/gesture` | 狀態變化時 |
| GestureEvent | `/event/gesture_detected` | 條件觸發 |

---

## 必做元件

### 1. 手勢顯示卡（主體）

偵測到手勢時顯示：

```
┌─────────────────────────────────────────┐
│ ✋ 手勢辨識                    ● Live   │
├─────────────────────────────────────────┤
│                                         │
│        ┌──────────────┐                │
│        │     👋        │                │  ← 大圖示（Lucide icon）
│        │    wave       │                │  ← gesture 名稱
│        └──────────────┘                │
│                                         │
│  信心度  87%          右手              │  ← MetricChip + hand
│                                         │
└─────────────────────────────────────────┘
```

### 2. 手勢圖示對照

| gesture | Lucide Icon | 顯示名稱 |
|---------|------------|---------|
| `wave` | `Hand` | 揮手 |
| `stop` | `HandMetal` | 停止 |
| `point` | `Pointer` | 指向 |
| `ok` | `ThumbsUp` | OK |

### 3. 空狀態

無手勢偵測時：
- 圖示：`Hand`（灰色）
- 文字：「尚未偵測到手勢」
- 次要文字：「請對著攝影機做出手勢」

### 4. 事件歷史

最近 10 筆手勢事件：
```
14:35:02  wave   右手  87%
14:34:45  stop   左手  92%
14:34:30  point  右手  78%
```

---

## 互動規則

| 互動 | 行為 |
|------|------|
| 新手勢偵測 | 圖示從小放大 + 輕微彈跳（200ms） |
| 信心度變化 | 數字 transition（300ms） |
| gesture 切換 | 圖示 crossfade（200ms） |
| 事件項目 hover | `surface-hover` 背景 |
| 無手勢超過 5s | 漸變回空狀態 |

---

## Design Tokens 參考

見 `design-tokens.md`。必須使用：
- `PanelCard` 作為外層容器
- `StatusBadge` 顯示 status
- `MetricChip` 顯示 confidence
- `LiveIndicator` 顯示即時狀態
- `EventItem` 顯示歷史事件

---

## Mock 資料範例

### GestureState（有手勢）

```json
{
  "stamp": 1710400502.123,
  "active": true,
  "current_gesture": "wave",
  "confidence": 0.87,
  "hand": "right",
  "status": "active"
}
```

### GestureState（無手勢）

```json
{
  "stamp": 1710400510.000,
  "active": false,
  "current_gesture": null,
  "confidence": 0.0,
  "hand": null,
  "status": "active"
}
```

### GestureEvent

```json
{
  "id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "timestamp": "2026-03-14T14:35:02.789+08:00",
  "source": "gesture",
  "event_type": "gesture_detected",
  "data": {
    "gesture": "wave",
    "confidence": 0.87,
    "hand": "right"
  }
}
```

---

## 驗收標準

- [ ] 使用 `PanelCard` 包裹，標題顯示「手勢辨識」+ LiveIndicator
- [ ] 偵測到手勢時顯示大圖示 + 名稱 + 信心度 + 左右手
- [ ] 四種手勢都有對應圖示（wave/stop/point/ok）
- [ ] 無手勢時顯示空狀態
- [ ] 事件歷史列表（至少顯示最近 5 筆）
- [ ] 遵守 design-tokens.md 的色板與圓角
- [ ] props 變化時有 transition 動畫（150-300ms）
- [ ] 響應式：sidebar 寬度 280-400px 自適應
- [ ] 接 Mock Server 資料可正常更新

---

## 不要做的事

- 不要處理 WebSocket 連線（已由 hooks 處理，你只接 props）
- 不要自己定義顏色（用 design tokens）
- 不要做模型推理或攝影機輸入
- 不要做 layout 切換邏輯
- 不要做手勢訓練或校正介面（超出範圍）

---

*最後更新：2026-03-14*
