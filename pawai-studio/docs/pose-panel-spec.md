# PosePanel Spec — 姿勢辨識面板

**負責人**：楊
**版本**：v1.0
**建立日期**：2026-03-14
**真相來源**：`docs/Pawai-studio/event-schema.md`（若與本文件衝突，以 event-schema.md 為準）

> **本版不依賴特定模型。** MediaPipe Pose / MoveNet / 其他模型皆可，輸出需符合同一 props 介面。
> 模型研究未完成不影響 Panel UI 開發，先用 Mock 資料。

---

## 目標

顯示姿勢辨識結果：偵測到的姿勢類型、信心度、追蹤對象、事件歷史。特別注意跌倒偵測的警示顯示。

---

## Props 介面

```typescript
interface PosePanelProps {
  data: PoseState;                      // 即時狀態
  events: PoseEvent[];                  // 歷史事件列表
}

// 來自 contracts/types.ts
interface PoseState {
  stamp: number;
  active: boolean;
  current_pose: string | null;          // 當前姿勢，null 表示無
  confidence: number;                   // [0.0, 1.0]
  track_id: number | null;             // 對應的人臉 track_id
  status: "active" | "inactive" | "loading";
}

interface PoseEvent {
  id: string;
  timestamp: string;
  source: "pose";
  event_type: "pose_detected";
  data: {
    pose: string;           // "standing" | "sitting" | "crouching" | "fallen"
    confidence: number;
    track_id: number;
  };
}
```

---

## 資料來源

| 資料 | 來源 Topic | 更新頻率 |
|------|-----------|---------|
| PoseState | `/state/perception/pose` | 狀態變化時 |
| PoseEvent | `/event/pose_detected` | 條件觸發 |

---

## 必做元件

### 1. 姿勢顯示卡（主體）

```
┌─────────────────────────────────────────┐
│ 🧍 姿勢辨識                    ● Live  │
├─────────────────────────────────────────┤
│                                         │
│        ┌──────────────┐                │
│        │     🧍        │                │  ← 大圖示
│        │   standing    │                │  ← pose 名稱
│        └──────────────┘                │
│                                         │
│  信心度  94%       Track #3            │  ← MetricChip + track_id
│                                         │
└─────────────────────────────────────────┘
```

### 2. 姿勢圖示與警示等級

| pose | Lucide Icon | 顯示名稱 | 警示等級 |
|------|------------|---------|---------|
| `standing` | `PersonStanding` | 站立 | 正常（success） |
| `sitting` | `Armchair` | 坐下 | 正常（success） |
| `crouching` | `ChevronDown` | 蹲下 | 注意（warning） |
| `fallen` | `AlertTriangle` | 跌倒 | 危險（destructive） |

### 3. 跌倒警示（重要）

偵測到 `fallen` 時，Panel 需要明顯警示：

```
┌─────────────────────────────────────────┐
│ ⚠️ 姿勢辨識                   ● Live   │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │  ⚠ 偵測到跌倒！                    │ │  ← destructive 背景
│ │  信心度: 89%    Track #3           │ │
│ │  14:36:02                           │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

- 邊框變 `destructive` 色
- Panel header 的 icon 變 `AlertTriangle`
- 此為 `critical` 事件，即使使用者收合過 Panel，也會強制重新展開

### 4. 空狀態

無姿勢偵測時：
- 圖示：`PersonStanding`（灰色）
- 文字：「尚未偵測到姿勢」
- 次要文字：「請確認攝影機可見完整身體」

### 5. 事件歷史

最近 10 筆姿勢事件：
```
14:36:02  fallen     Track #3  89%    ⚠
14:35:45  crouching  Track #3  82%
14:35:30  standing   Track #3  94%
```
`fallen` 事件用 destructive 色標示。

---

## 互動規則

| 互動 | 行為 |
|------|------|
| 新姿勢偵測 | 圖示切換 + crossfade（200ms） |
| fallen 偵測 | 邊框閃紅（pulse 2 次）+ 強制展開 Panel |
| 信心度變化 | 數字 transition（300ms） |
| 事件項目 hover | `surface-hover` 背景 |
| fallen → 其他姿勢 | 紅色邊框漸變回正常（500ms） |

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

### PoseState（站立）

```json
{
  "stamp": 1710400602.123,
  "active": true,
  "current_pose": "standing",
  "confidence": 0.94,
  "track_id": 3,
  "status": "active"
}
```

### PoseState（跌倒）

```json
{
  "stamp": 1710400662.456,
  "active": true,
  "current_pose": "fallen",
  "confidence": 0.89,
  "track_id": 3,
  "status": "active"
}
```

### PoseState（無偵測）

```json
{
  "stamp": 1710400700.000,
  "active": false,
  "current_pose": null,
  "confidence": 0.0,
  "track_id": null,
  "status": "active"
}
```

### PoseEvent

```json
{
  "id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
  "timestamp": "2026-03-14T14:36:02.456+08:00",
  "source": "pose",
  "event_type": "pose_detected",
  "data": {
    "pose": "fallen",
    "confidence": 0.89,
    "track_id": 3
  }
}
```

---

## 驗收標準

- [ ] 使用 `PanelCard` 包裹，標題顯示「姿勢辨識」+ LiveIndicator
- [ ] 偵測到姿勢時顯示大圖示 + 名稱 + 信心度 + track_id
- [ ] 四種姿勢都有對應圖示和警示等級
- [ ] **fallen（跌倒）有明顯紅色警示 + 邊框閃紅**
- [ ] 無姿勢偵測時顯示空狀態
- [ ] 事件歷史列表（至少最近 5 筆），fallen 事件紅色標示
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
- 不要做骨架渲染（Skeleton rendering，那是進階功能，本版不做）
- 不要做跌倒後的自動撥打電話等後續邏輯

---

*最後更新：2026-03-14*
