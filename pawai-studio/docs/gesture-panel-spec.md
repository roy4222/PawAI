# Gesture Panel Spec

> 真相來源：[../../docs/Pawai-studio/event-schema.md](../../docs/Pawai-studio/event-schema.md) §2.5 GestureState / §1.4 GestureEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

### 共用文件（必讀）

| 文件 | 用途 |
|------|------|
| [testing-playbook.md](testing-playbook.md) | 啟動方式、觸發指令、常見問題 |
| [../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md](../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md) | 交接規則、責任切分、placeholder 規格 |

### Placeholder 圖

Placeholder 圖在 `frontend/public/mock/gesture-placeholder.svg`。
**由你自己嵌入你的 panel**，後端不會動你的 .tsx。

嵌入方式：
```tsx
const PLACEHOLDER_SRC = "/mock/gesture-placeholder.svg"
const SHOW_PLACEHOLDER = true  // M2 時改 false，換成真實元件

{SHOW_PLACEHOLDER && (
  <div className="rounded-lg overflow-hidden border border-border/20">
    <img src={PLACEHOLDER_SRC} alt="gesture placeholder" className="w-full h-auto" />
  </div>
)}
```

Placeholder 只用於版面開發，不代表最終資料呈現方式。以本 spec 為設計依據。

### 你的開發頁面

http://localhost:3000/studio/gesture

### 觸發測試事件

見 [testing-playbook.md](testing-playbook.md) 的 gesture 欄。

---

## 0. 模組總覽

### 這個模組是幹嘛的

Go2 機器狗透過 D435 攝影機看到人的手部動作。後端會：
1. **偵測手部**（MediaPipe Hands 或類似框架，定位手掌位置）
2. **辨識手勢**（分類器，判斷手勢類型 — 揮手/停止/指向/OK）
3. **判斷左右手**

辨識結果會透過 WebSocket 推送到前端。這是 P1 功能（手勢/姿勢研究中，楊負責技術選型）。

### 前端要把哪些能力呈現出來

| 後端提供的資料 | 前端要顯示的 |
|--------------|------------|
| `current_gesture`（手勢類型） | 偵測到什麼手勢（wave / stop / point / ok） |
| `confidence`（信心度 0-1） | 辨識有多確定（百分比） |
| `hand`（左/右手） | 哪隻手做的手勢 |
| `active`（是否啟用） | 模組有沒有在跑 |
| 事件（gesture_detected） | 事件歷史：偵測到什麼手勢 |

### 使用者在畫面上會看到什麼

**場景 1：沒有手勢**
→ 空狀態，顯示「等待手勢偵測...」

**場景 2：使用者揮手**
→ 顯示手勢「wave 👋」+ 信心度 85% + 右手

**場景 3：使用者比停止**
→ 顯示手勢「stop ✋」，Go2 會停下來

---

## 1. 目標

即時顯示手勢辨識結果：手勢類型、信心度、左右手、事件歷史。（P1 功能）

---

## 2. 檔案範圍

### 可以改
- `frontend/components/gesture/gesture-panel.tsx`
- `frontend/components/gesture/` 下新增的子元件

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/face/`、`speech/`、`pose/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { GestureState, GestureEvent } from '@/contracts/types'

// 在元件內：
const gestureState = useStateStore((s) => s.gestureState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'gesture'))
```

---

## 4. Mock Data

```typescript
const MOCK_GESTURE_STATE: GestureState = {
  stamp: 1773561605.456,
  active: true,
  current_gesture: 'wave',
  confidence: 0.87,
  hand: 'right',
  status: 'active',
}

const MOCK_GESTURE_EVENT: GestureEvent = {
  id: 'evt-gesture-001',
  timestamp: '2026-03-14T10:00:05.456+08:00',
  source: 'gesture',
  event_type: 'gesture_detected',
  data: {
    gesture: 'wave',
    confidence: 0.87,
    hand: 'right',
  },
}

const MOCK_EMPTY_STATE: GestureState = {
  stamp: 0,
  active: false,
  current_gesture: null,
  confidence: 0,
  hand: null,
  status: 'inactive',
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=Hand, title="手勢辨識")
├── [若 active] 手勢卡片
│   ├── 手勢圖示（wave=👋 / stop=✋ / point=👉 / ok=👌，或用 lucide icon）
│   ├── 手勢名稱（粗體）
│   ├── 信心度（MetricChip, value=confidence, unit="%", 乘100顯示）
│   └── 左右手 badge（left=左手 / right=右手）
├── [若 !active] 空狀態
│   └── 圖示 + "尚未偵測到手勢"
└── [可選/M2] 事件歷史（最近 10 筆 GestureEvent）
    └── EventItem 列表
```

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `active === true` | 手勢卡片 | `active` |
| 載入中 | `gestureState === null` 或 `status === "loading"` | "正在連線..." | `loading` |
| 無資料 | `active === false` | "尚未偵測到手勢" | `inactive` |
| 錯誤 | store 連線失敗 | "手勢模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **新手勢偵測**：bounce 動畫 200ms
- **信心度變化**：transition 300ms
- **手勢切換**：crossfade 200ms
- **手勢卡片 hover**：背景色加深 `var(--surface-hover)`，transition 150ms

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| GestureState / GestureEvent 欄位 | [../../docs/Pawai-studio/event-schema.md](../../docs/Pawai-studio/event-schema.md) §2.5 + §1.4 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| MetricChip 用法 | `frontend/components/shared/metric-chip.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`Hand`，title="手勢辨識"
- [ ] 用 `MOCK_GESTURE_STATE` 顯示 1 個手勢卡片
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 手勢圖示 + 名稱 + 信心度 + 左右手 視覺完成
- [ ] bounce / crossfade / transition 動畫符合 design-tokens.md
- [ ] 空狀態 + loading 狀態 UI
- [ ] 事件歷史列表（最近 10 筆）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（快速手勢切換、null gesture、未知手勢字串）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作手勢辨識模型或影像處理
