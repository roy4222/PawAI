# Face Panel Spec

> 真相來源：[../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.1 FaceState / §1.2 FaceIdentityEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

### 共用文件（必讀）

| 文件 | 用途 |
|------|------|
| [testing-playbook.md](testing-playbook.md) | 啟動方式、觸發指令、常見問題 |
| [../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md](../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md) | 交接規則、責任切分、placeholder 規格 |

### Placeholder 圖

Placeholder 圖在 `frontend/public/mock/face-placeholder.svg`。
**由你自己嵌入你的 panel**，後端不會動你的 .tsx。

嵌入方式：
```tsx
const PLACEHOLDER_SRC = "/mock/face-placeholder.svg"
const SHOW_PLACEHOLDER = true  // M2 時改 false，換成真實元件

{SHOW_PLACEHOLDER && (
  <div className="rounded-lg overflow-hidden border border-border/20">
    <img src={PLACEHOLDER_SRC} alt="face placeholder" className="w-full h-auto" />
  </div>
)}
```

Placeholder 只用於版面開發，不代表最終資料呈現方式。以本 spec 為設計依據。

### 你的開發頁面

http://localhost:3000/studio/face

### 觸發測試事件

見 [testing-playbook.md](testing-playbook.md) 的 face 欄。

---

## 0. 模組總覽

### 這個模組是幹嘛的

Go2 機器狗身上裝了一顆 Intel RealSense D435 攝影機。當有人走到攝影機前面，後端會：
1. **偵測人臉**（YuNet，知道「有人」）
2. **辨識身份**（SFace，知道「是誰」— 例如 Roy、小明）
3. **追蹤多人**（IOU tracker，持續追蹤每個人的位置）
4. **估算距離**（D435 深度感測器，知道「多遠」）

這些結果會透過 WebSocket 即時推送到前端。

### 前端要把哪些能力呈現出來

| 後端提供的資料 | 前端要顯示的 |
|--------------|------------|
| `stable_name`（身份名稱） | 這個人是誰（Roy / 小明 / 未知人物） |
| `sim`（相似度 0-1） | 辨識有多確定（百分比） |
| `distance_m`（距離，公尺） | 這個人離機器狗多遠 |
| `mode`（stable / hold） | 辨識狀態：已確認 or 還在判定中 |
| `track_id`（追蹤 ID） | 多人時區分誰是誰 |
| `face_count`（人數） | 目前看到幾個人 |
| 事件（identity_stable / track_lost 等） | 事件歷史：誰來了、誰走了 |

### 使用者在畫面上會看到什麼

**場景 1：沒人**
→ 空狀態，顯示「尚未偵測到人臉」

**場景 2：Roy 走近**
→ 出現一張人物卡片：「Roy · 相似度 42% · 距離 1.2m · 已穩定」

**場景 3：兩個人同時在鏡頭前**
→ 兩張人物卡片並列，各自顯示身份/距離/狀態

**場景 4：Roy 離開**
→ 人物卡片消失，事件歷史顯示「追蹤消失」

---

## 1. 目標

即時顯示人臉辨識結果：身份名稱、相似度、距離、追蹤狀態（stable/hold）、多人列表。

---

## 2. 檔案範圍

### 可以改
- `frontend/components/face/face-panel.tsx`
- `frontend/components/face/` 下新增的子元件（例如 `face-track-card.tsx`）

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/speech/`、`gesture/`、`pose/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

Panel 不接收 props，從 Zustand store 取資料：

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { FaceState, FaceTrack, FaceIdentityEvent } from '@/contracts/types'

// 在元件內：
const faceState = useStateStore((s) => s.faceState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'face'))
```

---

## 4. Mock Data

開發時直接用這些假資料測試 UI：

```typescript
const MOCK_FACE_STATE: FaceState = {
  stamp: 1773561600.789,
  face_count: 2,
  tracks: [
    {
      track_id: 1,
      stable_name: 'Roy',
      sim: 0.42,
      distance_m: 1.25,
      bbox: [100, 150, 200, 280],
      mode: 'stable',
    },
    {
      track_id: 2,
      stable_name: 'unknown',
      sim: 0.18,
      distance_m: 2.1,
      bbox: [300, 180, 380, 300],
      mode: 'hold',
    },
  ],
}

const MOCK_FACE_EVENT: FaceIdentityEvent = {
  id: 'evt-face-001',
  timestamp: '2026-03-14T10:00:01.500+08:00',
  source: 'face',
  event_type: 'identity_stable',
  data: {
    track_id: 1,
    stable_name: 'Roy',
    sim: 0.42,
    distance_m: 1.25,
  },
}

const MOCK_EMPTY_STATE: FaceState = {
  stamp: 0,
  face_count: 0,
  tracks: [],
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=User, title="人臉辨識", count=face_count)
├── [若 face_count > 0] 追蹤人物列表
│   └── 每個 FaceTrack 一張卡片：
│       ├── stable_name（粗體）
│       ├── 相似度 bar（MetricChip, value=sim, unit="%", 乘100顯示）
│       ├── 距離（MetricChip, value=distance_m, unit="m"）
│       ├── mode badge（stable=綠/hold=黃）
│       └── track_id（小字灰色）
├── [若 face_count === 0] 空狀態
│   └── 圖示 + "尚未偵測到人臉"
└── [可選/M2] 事件歷史（最近 10 筆 FaceIdentityEvent）
    └── EventItem 列表
```

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `face_count > 0` | 追蹤人物列表 | `active` |
| 載入中 | `faceState === null` | "正在連線..." | `loading` |
| 無資料 | `face_count === 0` | "尚未偵測到人臉" 空狀態 | `inactive` |
| 錯誤 | store 連線失敗（由上層處理） | "人臉模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **人物卡片 hover**：背景色加深 `var(--surface-hover)`，transition 150ms
- **新追蹤人物出現**：slide-in 動畫 200ms
- **track_lost 後**：短暫保留後淡出（實作預設 5s，可調）
- **相似度 bar**：數值變化時 transition 300ms
- **mode 切換（hold → stable）**：badge 顏色 transition 150ms

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| FaceState / FaceTrack / FaceIdentityEvent 欄位 | [../../docs/Pawai-studio/specs/event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) §2.1 + §1.2 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| MetricChip 用法 | `frontend/components/shared/metric-chip.tsx` |
| EventItem 用法 | `frontend/components/shared/event-item.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`User`，title="人臉辨識"
- [ ] 用 `MOCK_FACE_STATE` 顯示 1-2 個追蹤人物卡片
- [ ] `face_count` 顯示在 PanelCard 的 count prop
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 多人追蹤列表（≥2 人）正常顯示
- [ ] 相似度 bar + 距離 MetricChip 視覺完成
- [ ] mode badge（stable 綠 / hold 黃）正確
- [ ] 空狀態、loading 狀態有意義的 UI
- [ ] hover / slide-in / 淡出動畫符合 design-tokens.md
- [ ] 事件歷史列表（最近 10 筆）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（缺欄位、格式異常、track 快速增減）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作 bbox 繪製或影像 overlay（那是 CameraPanel 的事）
