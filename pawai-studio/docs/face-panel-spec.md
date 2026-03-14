# FacePanel Spec — 人臉辨識面板

**負責人**：鄔
**版本**：v1.0
**建立日期**：2026-03-14
**真相來源**：`docs/Pawai-studio/event-schema.md`（若與本文件衝突，以 event-schema.md 為準）

---

## 目標

顯示即時人臉辨識結果：誰在鏡頭前、距離多遠、辨識信心度、追蹤狀態。

---

## Props 介面

```typescript
interface FacePanelProps {
  data: FaceState;                    // 即時狀態（10Hz 更新）
  events: FaceIdentityEvent[];        // 歷史事件列表
}

// 來自 contracts/types.ts
interface FaceState {
  stamp: number;
  face_count: number;
  tracks: FaceTrack[];
}

interface FaceTrack {
  track_id: number;
  stable_name: string;      // 身份名稱，"unknown" 表示未識別
  sim: number;               // 相似度 [0.0, 1.0]
  distance_m: number | null; // 距離（公尺），null 表示無深度
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  mode: "stable" | "hold";  // stable=已穩定, hold=判定中
}

interface FaceIdentityEvent {
  id: string;
  timestamp: string;
  source: "face";
  event_type: "track_started" | "identity_stable" | "identity_changed" | "track_lost";
  data: {
    track_id: number;
    stable_name: string;
    sim: number;
    distance_m: number | null;
  };
}
```

---

## 資料來源

| 資料 | 來源 Topic | 更新頻率 |
|------|-----------|---------|
| FaceState | `/state/perception/face` | 10 Hz |
| FaceIdentityEvent | `/event/face_identity` | 條件觸發 |

---

## 必做元件

### 1. 追蹤人物卡片（主體）

每個被追蹤的人顯示一張卡片：

```
┌─────────────────────────────────┐
│ 👤 小明                   stable │  ← stable_name + StatusBadge(mode)
│                                 │
│  信心度  92%        距離  1.2m  │  ← MetricChip x2
│  Track #3                      │  ← track_id
└─────────────────────────────────┘
```

- `mode: "stable"` → 綠色 StatusBadge
- `mode: "hold"` → 黃色 StatusBadge
- `stable_name: "unknown"` → 顯示「未識別」+ 灰色頭像
- 多人時，卡片垂直排列

### 2. 空狀態

無人臉時顯示：
- 圖示（Lucide: `UserX` 或 `ScanFace`）
- 文字：「尚未偵測到人臉」
- 次要文字：「請走到攝影機前方」

### 3. 人臉計數

Panel 標題旁顯示當前人數：
```
人臉辨識 (2)     ● Live
```

### 4. 事件歷史（可選，加分項）

底部可收合區域，顯示最近 10 筆 FaceIdentityEvent：
```
14:32:05  identity_stable  小明 (92%)
14:32:01  track_started    Track #3
14:31:58  track_lost       Track #2
```
使用 `EventItem` 共用元件。

---

## 互動規則

| 互動 | 行為 |
|------|------|
| 人物卡片 hover | `surface-hover` 背景 + 微微放大 (scale 1.01) |
| 信心度變化 | 數字有 transition 動畫（300ms） |
| 新人出現 | 卡片從右滑入（200ms） |
| 人離開 | 卡片淡出（200ms），延遲 2s 後移除 |
| mode 切換 | StatusBadge 顏色漸變（150ms） |

---

## Design Tokens 參考

見 `design-tokens.md`。必須使用：
- `PanelCard` 作為外層容器
- `StatusBadge` 顯示 mode
- `MetricChip` 顯示 sim 和 distance_m
- `LiveIndicator` 顯示即時狀態

---

## Mock 資料範例

### FaceState（有人）

```json
{
  "stamp": 1710400325.123,
  "face_count": 2,
  "tracks": [
    {
      "track_id": 3,
      "stable_name": "小明",
      "sim": 0.92,
      "distance_m": 1.2,
      "bbox": [120, 80, 280, 320],
      "mode": "stable"
    },
    {
      "track_id": 5,
      "stable_name": "unknown",
      "sim": 0.15,
      "distance_m": 2.8,
      "bbox": [400, 100, 520, 300],
      "mode": "hold"
    }
  ]
}
```

### FaceState（無人）

```json
{
  "stamp": 1710400330.456,
  "face_count": 0,
  "tracks": []
}
```

### FaceIdentityEvent

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "timestamp": "2026-03-14T14:32:05.123+08:00",
  "source": "face",
  "event_type": "identity_stable",
  "data": {
    "track_id": 3,
    "stable_name": "小明",
    "sim": 0.92,
    "distance_m": 1.2
  }
}
```

---

## 驗收標準

- [ ] 使用 `PanelCard` 包裹，標題顯示「人臉辨識」+ 人數 + LiveIndicator
- [ ] 顯示 stable_name、sim（百分比格式）、distance_m（帶單位）
- [ ] 多人追蹤時顯示多張卡片
- [ ] `mode=stable` 綠色 badge，`mode=hold` 黃色 badge
- [ ] `stable_name="unknown"` 顯示「未識別」
- [ ] 無人臉時顯示空狀態（圖示 + 提示文字）
- [ ] 遵守 design-tokens.md 的色板與圓角
- [ ] props 變化時有 transition 動畫（150-300ms）
- [ ] 響應式：sidebar 寬度 280-400px 自適應
- [ ] 接 Mock Server 資料可正常更新

---

## 不要做的事

- 不要處理 WebSocket 連線（已由 hooks 處理，你只接 props）
- 不要自己定義顏色（用 design tokens）
- 不要做攝影機影像顯示（那是 CameraPanel，不是你的範圍）
- 不要做 layout 切換邏輯（LayoutOrchestrator 會處理）

---

*最後更新：2026-03-14*
