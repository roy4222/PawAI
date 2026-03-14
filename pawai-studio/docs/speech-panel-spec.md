# Speech Panel Spec

> 真相來源：[../../docs/Pawai-studio/event-schema.md](../../docs/Pawai-studio/event-schema.md) §2.2 SpeechState / §1.3 SpeechIntentEvent
> 參考實作：[../frontend/components/chat/chat-panel.tsx](../frontend/components/chat/chat-panel.tsx)
> Design Tokens：[design-tokens.md](design-tokens.md)

---

## 1. 目標

即時顯示語音互動狀態：狀態機 phase、ASR 轉寫文字、Intent 辨識結果、已載入模型。

---

## 2. 檔案範圍

### 可以改
- `frontend/components/speech/speech-panel.tsx`
- `frontend/components/speech/` 下新增的子元件

### 不可以改（改了 PR 會被退）
- `frontend/contracts/types.ts`
- `frontend/stores/*`
- `frontend/hooks/*`
- `frontend/components/layout/*`
- `frontend/components/chat/*`
- 其他人的 `frontend/components/face/`、`gesture/`、`pose/`

### 不得直接修改現有 shared 元件；若需新增或擴充，先提 Issue
- `frontend/components/shared/*`

---

## 3. Store Selectors 與使用型別

```typescript
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { SpeechState, SpeechPhase, SpeechIntentEvent } from '@/contracts/types'

// 在元件內：
const speechState = useStateStore((s) => s.speechState)
const events = useEventStore((s) => s.events.filter((e) => e.source === 'speech'))
```

---

## 4. Mock Data

```typescript
const MOCK_SPEECH_STATE: SpeechState = {
  stamp: 1773561602.123,
  phase: 'listening',
  last_asr_text: '你好，請問你是誰？',
  last_intent: 'greet',
  last_tts_text: '哈囉！我是 PawAI，很高興認識你！',
  models_loaded: ['kws', 'asr', 'tts'],
}

const MOCK_SPEECH_EVENT: SpeechIntentEvent = {
  id: 'evt-speech-001',
  timestamp: '2026-03-14T10:00:05.789+08:00',
  source: 'speech',
  event_type: 'intent_recognized',
  data: {
    intent: 'greet',
    text: '你好',
    confidence: 0.95,
    provider: 'whisper_local',
  },
}

const MOCK_IDLE_STATE: SpeechState = {
  stamp: 0,
  phase: 'idle_wakeword',
  last_asr_text: '',
  last_intent: '',
  last_tts_text: '',
  models_loaded: ['kws'],
}
```

---

## 5. UI 結構

### 必要區塊

```
PanelCard (icon=Mic, title="語音互動")
├── Phase 狀態指示
│   ├── 當前 phase 名稱 + 對應顏色圓點
│   └── [listening 狀態] 3-dot pulse 動畫
├── 最近轉寫區
│   ├── ASR 文字（last_asr_text）
│   ├── Intent badge（last_intent + confidence%）
│   └── Provider 標籤（小字灰色）
├── 已載入模型
│   └── Chip 列表（已載=綠 success / 未載=灰 muted）
│       可能的模型：kws, asr, tts
├── [若 idle_wakeword 且無事件] 空狀態
│   └── 圖示 + "等待喚醒詞..."
└── [可選/M2] 事件歷史（最近 10 筆 SpeechIntentEvent）
    └── EventItem 列表
```

### Phase 顏色對照表

| Phase | 顯示文字 | 顏色 |
|-------|---------|------|
| `idle_wakeword` | 等待喚醒 | `--muted-foreground` |
| `wake_ack` | 喚醒確認 | `--warning` |
| `loading_local_stack` | 載入模型中 | `--warning` |
| `listening` | 聆聽中 | `--success` |
| `transcribing` | 轉寫中 | `--primary` |
| `local_asr_done` | ASR 完成 | `--primary` |
| `cloud_brain_pending` | 等待大腦 | `--warning` |
| `speaking` | 播放中 | `--success` |
| `keep_alive` | 保持連線 | `--muted-foreground` |
| `unloading` | 卸載中 | `--muted-foreground` |

### 狀態矩陣

| 狀態 | 條件 | 顯示內容 | StatusBadge |
|------|------|---------|-------------|
| 正常運作 | `phase !== "idle_wakeword"` | Phase + 轉寫 + Intent | `active` |
| 載入中 | `speechState === null` | "正在連線..." | `loading` |
| 無資料 | `phase === "idle_wakeword"` 且無事件 | "等待喚醒詞..." | `inactive` |
| 錯誤 | store 連線失敗 | "語音模組離線" | `error` |

### 響應式
- sidebar 寬度：固定 360px（以 design-tokens.md 為準）
- main area：自適應
- 不需要做 mobile layout

---

## 6. 互動規則

- **Phase 切換**：顏色 transition 150ms
- **ASR 文字更新**：typing effect（逐字顯示，可用 CSS animation）
- **Intent badge 出現**：scale 200ms bounce
- **Model chip 載入/卸載**：fade 200ms
- **listening 狀態**：3-dot pulse 動畫（2s loop，`motion-safe` 尊重）

---

## 7. 參考來源

| 需求 | 看哪裡 |
|------|--------|
| SpeechState / SpeechPhase / SpeechIntentEvent 欄位 | [../../docs/Pawai-studio/event-schema.md](../../docs/Pawai-studio/event-schema.md) §2.2 + §1.3 |
| 色彩 / 字體 / 間距 | [design-tokens.md](design-tokens.md) |
| PanelCard 用法 | `frontend/components/shared/panel-card.tsx` |
| StatusBadge 用法 | `frontend/components/shared/status-badge.tsx` |
| 完整 Panel 範例 | `frontend/components/chat/chat-panel.tsx` |

---

## 8. Milestones

### M1（3/16）：能看、能 review
- [ ] `PanelCard` 包裹，icon=`Mic`，title="語音互動"
- [ ] 用 `MOCK_SPEECH_STATE` 顯示 phase + ASR 文字 + intent
- [ ] Phase 圓點顏色正確（至少 listening / idle_wakeword）
- [ ] 4 種狀態（active / loading / inactive / error）都有對應畫面
- [ ] `npm run lint` + `npm run build` 通過

### M2（3/23）：可 demo 的前端版本
- [ ] Panel 能正確反映由 store 注入的 mock 資料更新
- [ ] 10 種 phase 全部有對應顏色和文字
- [ ] listening 的 3-dot pulse 動畫
- [ ] Intent badge + confidence% 顯示
- [ ] 已載入模型 chip 列表
- [ ] 空狀態 + loading 狀態 UI
- [ ] 事件歷史列表（最近 10 筆）
- [ ] `npm run lint` + `npm run build` 通過

### M3（4/6）：整合穩定版
- [ ] Panel 能正確反映由 store 注入的真實 Gateway 資料
- [ ] 處理邊界 case（phase 快速切換、空 ASR 文字、未知 phase）
- [ ] 與其他 Panel 共存不衝突（Chat + 2 panels）
- [ ] 5 分鐘無當機 soak test
- [ ] `npm run lint` + `npm run build` 通過

---

## 9. Out of Scope（不要做）

- 不要自己加新的 shared component（先提 Issue）
- 不要改 layout 邏輯
- 不要加 Panel 之間的直接通訊
- 不要引入新的 npm 依賴（除非先提 Issue）
- 不要實作語音輸入功能（那是 ChatPanel / stt_intent_node 的事）
