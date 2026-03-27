# Pose Panel Spec

> 真相來源：[../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.6 PoseState / §1.5 PoseEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

### 共用文件（必讀）

| 文件 | 用途 |
|------|------|
| [testing-playbook.md](testing-playbook.md) | 啟動方式、觸發指令、常見問題 |
| [../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md](../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md) | 交接規則、責任切分、placeholder 規格 |

### Placeholder 圖

Placeholder 圖在 `frontend/public/mock/pose-placeholder.svg`。
**由你自己嵌入你的 panel**，後端不會動你的 .tsx。

嵌入方式：
```tsx
const PLACEHOLDER_SRC = "/mock/pose-placeholder.svg"
const SHOW_PLACEHOLDER = true  // M2 時改 false，換成真實元件

{SHOW_PLACEHOLDER && (
  <div className="rounded-lg overflow-hidden border border-border/20">
    <img src={PLACEHOLDER_SRC} alt="pose placeholder" className="w-full h-auto" />
  </div>
)}
```

Placeholder 只用於版面開發，不代表最終資料呈現方式。以本 spec 為設計依據。

### 你的開發頁面

http://localhost:3000/studio/pose

### 觸發測試事件

見 [testing-playbook.md](testing-playbook.md) 的 pose 欄。

---

## 0. 模組總覽

### 這個模組是幹嘛的

Go2 機器狗透過 D435 攝影機觀察人的全身姿勢。後端會：
1. **偵測人體骨架**（MediaPipe Pose / MoveNet 或類似框架）
2. **辨識姿勢**（分類器，判斷 — 站立/坐著/蹲下/跌倒）
3. **關聯人臉 track**（知道這個姿勢是誰的）

主要用途是讓機器狗理解使用者的身體狀態，做出對應的互動反應（例如看到人坐下就靠過去陪伴）。

這是 P1 功能（楊負責技術選型研究中）。

### 前端要把哪些能力呈現出來

| 後端提供的資料 | 前端要顯示的 |
|--------------|------------|
| `current_pose`（姿勢類型） | 偵測到什麼姿勢（standing / sitting / crouching / fallen） |
| `confidence`（信心度 0-1） | 辨識有多確定（百分比） |
| `track_id`（追蹤 ID） | 這個姿勢是哪個人的（對應人臉的 track_id） |
| `active`（是否啟用） | 模組有沒有在跑 |
| 事件（pose_detected） | 事件歷史：偵測到什麼姿勢 |

### 使用者在畫面上會看到什麼

**場景 1：沒有偵測到姿勢**
→ 空狀態，顯示「等待姿勢偵測...」

**場景 2：人站著**
→ 顯示「站立 🧍」+ 信心度 92% + Track #1

**場景 3：人蹲下**
→ 顯示「蹲下 🏋️」，機器狗可能做出靠近陪伴的反應

---

## 1. 目標

即時顯示姿勢辨識結果：姿勢類型、信心度、追蹤對象、**跌倒警示**。（P1 功能）

---

## 2. 檔案範圍

### 可以改
- `frontend/components/pose/pose-panel.tsx`
- `frontend/components/pose/` 下新增的子元件

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/face/`、`speech/`、`gesture/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { PoseState, PoseEvent } from '@/contracts/types'

// 在元件內：
const poseState = useStateStore((s) => s.poseState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'pose'))
```

---

## 4. Mock Data

```typescript
const MOCK_POSE_STATE: PoseState = {
  stamp: 1773561607.890,
  active: true,
  current_pose: 'standing',
  confidence: 0.92,
  track_id: 1,
  status: 'active',
}

const MOCK_POSE_EVENT: PoseEvent = {
  id: 'evt-pose-001',
  timestamp: '2026-03-14T10:00:07.890+08:00',
  source: 'pose',
  event_type: 'pose_detected',
  data: {
    pose: 'standing',
    confidence: 0.92,
    track_id: 1,
  },
}

const MOCK_FALLEN_STATE: PoseState = {
  stamp: 1773561610.000,
  active: true,
  current_pose: 'fallen',
  confidence: 0.88,
  track_id: 1,
  status: 'active',
}

const MOCK_EMPTY_STATE: PoseState = {
  stamp: 0,
  active: false,
  current_pose: null,
  confidence: 0,
  track_id: null,
  status: 'inactive',
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=Activity, title="姿勢辨識")
├── [若 active] 姿勢卡片
│   ├── 姿勢圖示（standing=🧍 / sitting=🪑 / crouching=⬇️ / fallen=⚠️，或用 lucide icon）
│   ├── 姿勢名稱（粗體）
│   ├── 信心度（MetricChip, value=confidence, unit="%", 乘100顯示）
│   ├── 關聯 track_id（小字灰色，若有值）
│   └── [fallen] 跌倒警示區塊（見下方）
├── [若 !active] 空狀態
│   └── 圖示 + "尚未偵測到姿勢"
└── [可選/M2] 事件歷史（最近 10 筆 PoseEvent）
    └── EventItem 列表，fallen 事件用 destructive 色標示
```

### 跌倒警示（`current_pose === "fallen"`）

這是本 Panel 最重要的特殊狀態：

- PanelCard 邊框改為 `var(--destructive)` 紅色
- 姿勢卡片背景改為 `var(--destructive)/10`
- 圖示改為 `AlertTriangle`（lucide）
- 文字顯示「**偵測到跌倒！**」粗體紅色
- 動畫：border pulse 2s loop（`motion-safe` 尊重）

### 姿勢顏色對照表

| Pose | 顯示文字 | 顏色 |
|------|---------|------|
| `standing` | 站立 | `--success` |
| `sitting` | 坐下 | `--success` |
| `crouching` | 蹲下 | `--warning` |
| `fallen` | 跌倒 | `--destructive` |

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `active === true` 且 `pose !== "fallen"` | 姿勢卡片 | `active` |
| 跌倒警示 | `active === true` 且 `pose === "fallen"` | 警示 UI | `error` |
| 載入中 | `poseState === null` 或 `status === "loading"` | "正在連線..." | `loading` |
| 無資料 | `active === false` | "尚未偵測到姿勢" | `inactive` |
| 錯誤 | store 連線失敗 | "姿勢模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **姿勢切換**：圖示 + 名稱 crossfade 200ms
- **信心度變化**：transition 300ms
- **跌倒偵測**：邊框 pulse 2s loop，`motion-safe` 尊重
- **姿勢卡片 hover**：背景色加深 `var(--surface-hover)`，transition 150ms

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| PoseState / PoseEvent 欄位 | [../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.6 + §1.5 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| MetricChip 用法 | `frontend/components/shared/metric-chip.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`Activity`，title="姿勢辨識"
- [ ] 用 `MOCK_POSE_STATE` 顯示 1 個姿勢卡片
- [ ] 用 `MOCK_FALLEN_STATE` 顯示跌倒警示 UI
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 4 種姿勢各有正確圖示 + 顏色
- [ ] 跌倒警示完整（紅框 + pulse + AlertTriangle + 粗體文字）
- [ ] 信心度 MetricChip 視覺完成
- [ ] 空狀態 + loading 狀態 UI
- [ ] 事件歷史列表（最近 10 筆，fallen 紅色標示）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（pose 快速切換、null pose、未知姿勢字串）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作骨架渲染或影像疊加（可選 P2，不在 M1-M3 範圍）
