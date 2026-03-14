# SpeechPanel Spec — 語音互動面板

**負責人**：陳
**版本**：v1.0
**建立日期**：2026-03-14
**真相來源**：`docs/Pawai-studio/event-schema.md`（若與本文件衝突，以 event-schema.md 為準）

---

## 目標

顯示語音互動的即時狀態：ASR 轉寫文字、辨識的意圖、語音狀態機階段、對話歷史。

---

## Props 介面

```typescript
interface SpeechPanelProps {
  data: SpeechState;                      // 即時狀態
  events: SpeechIntentEvent[];            // 歷史事件列表
}

// 來自 contracts/types.ts
interface SpeechState {
  stamp: number;
  phase: "idle_wakeword" | "wake_ack" | "loading_local_stack" | "listening"
       | "transcribing" | "local_asr_done" | "cloud_brain_pending"
       | "speaking" | "keep_alive" | "unloading";
  last_asr_text: string;
  last_intent: string;
  last_tts_text: string;
  models_loaded: string[];   // ["kws"] | ["kws","asr","tts"] | ...
}

interface SpeechIntentEvent {
  id: string;
  timestamp: string;
  source: "speech";
  event_type: "intent_recognized" | "asr_result" | "wake_word";
  data: {
    intent?: string;        // greet | come_here | stop | take_photo | status
    text: string;           // ASR 原始文字
    confidence: number;     // [0.0, 1.0]
    provider: string;       // "whisper_local" | "qwen_asr" | 其他（依部署決定）
  };
}
```

---

## 資料來源

| 資料 | 來源 Topic | 更新頻率 |
|------|-----------|---------|
| SpeechState | `/state/interaction/speech` | 狀態變化時 |
| SpeechIntentEvent | `/event/speech_intent_recognized` | 條件觸發 |

---

## 必做元件

### 1. 狀態機顯示（主體）

顯示當前語音處理階段：

```
┌─────────────────────────────────────────┐
│ 🎤 語音互動                    ● Live   │
├─────────────────────────────────────────┤
│                                         │
│  狀態：listening                        │  ← phase，用 StatusBadge
│  ●●● 正在聆聽...                        │  ← 3-dot pulse 動畫
│                                         │
│  ┌─ 最近轉寫 ─────────────────────────┐ │
│  │ "你好，可以幫我拍個照嗎"           │ │  ← last_asr_text
│  │ Intent: take_photo (85%)           │ │  ← last_intent + confidence
│  │ Provider: whisper_local            │ │
│  └────────────────────────────────────┘ │
│                                         │
│  已載入模型: kws, asr, tts             │  ← models_loaded chips
└─────────────────────────────────────────┘
```

### 2. Phase 狀態對照

| phase | 顯示文字 | 顏色 | 動畫 |
|-------|---------|------|------|
| `idle_wakeword` | 等待喚醒 | 灰色 | 無 |
| `wake_ack` | 喚醒成功！ | 綠色 | 閃一下 |
| `loading_local_stack` | 載入模型中... | 黃色 | pulse |
| `listening` | 正在聆聽 | 綠色 | 3-dot pulse |
| `transcribing` | 轉寫中... | 黃色 | pulse |
| `local_asr_done` | 轉寫完成 | 綠色 | 無 |
| `cloud_brain_pending` | AI 思考中... | 紫色(accent) | pulse |
| `speaking` | 正在說話 | 綠色 | 音波動畫 |
| `keep_alive` | 待命中 | 藍色 | 緩慢呼吸 |
| `unloading` | 卸載模型... | 灰色 | 淡出 |

### 3. 空狀態

phase 為 `idle_wakeword` 且無歷史事件時：
- 圖示：`Mic` 或 `MicOff`
- 文字：「語音系統待命中」
- 次要文字：「說出喚醒詞開始互動」

### 4. 模型載入狀態

用小 chips 顯示 `models_loaded` 陣列：
```
已載入: [KWS] [ASR] [TTS]      ← 綠色 chips
未載入: [LLM]                    ← 灰色 chips
```

### 5. 事件歷史（可選，加分項）

最近 10 筆語音事件：
```
14:33:02  intent_recognized  greet (95%)  "你好"
14:32:58  asr_result         "你好"       whisper_local
14:32:55  wake_word          —            —
```

---

## 互動規則

| 互動 | 行為 |
|------|------|
| phase 切換 | StatusBadge 顏色漸變（150ms） |
| 新 ASR 文字 | 從空白逐字出現（typing effect，可選） |
| intent 出現 | intent badge 從小放大（200ms） |
| models_loaded 變化 | chip 淡入/淡出（200ms） |
| 轉寫文字 hover | 顯示完整 provider 和 confidence 資訊 |

---

## Design Tokens 參考

見 `design-tokens.md`。必須使用：
- `PanelCard` 作為外層容器
- `StatusBadge` 顯示 phase 狀態
- `MetricChip` 顯示 confidence
- `LiveIndicator` 顯示即時狀態

---

## Mock 資料範例

### SpeechState（聆聽中）

```json
{
  "stamp": 1710400385.789,
  "phase": "listening",
  "last_asr_text": "",
  "last_intent": "",
  "last_tts_text": "",
  "models_loaded": ["kws", "asr", "tts"]
}
```

### SpeechState（轉寫完成）

```json
{
  "stamp": 1710400390.123,
  "phase": "local_asr_done",
  "last_asr_text": "你好，可以幫我拍個照嗎",
  "last_intent": "take_photo",
  "last_tts_text": "",
  "models_loaded": ["kws", "asr", "tts"]
}
```

### SpeechState（待機）

```json
{
  "stamp": 1710400400.000,
  "phase": "idle_wakeword",
  "last_asr_text": "",
  "last_intent": "",
  "last_tts_text": "",
  "models_loaded": ["kws"]
}
```

### SpeechIntentEvent

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-14T14:33:02.456+08:00",
  "source": "speech",
  "event_type": "intent_recognized",
  "data": {
    "intent": "greet",
    "text": "你好",
    "confidence": 0.95,
    "provider": "whisper_local"
  }
}
```

---

## 驗收標準

- [ ] 使用 `PanelCard` 包裹，標題顯示「語音互動」+ LiveIndicator
- [ ] 顯示當前 phase，文字 + 顏色對照表正確
- [ ] listening 狀態有 3-dot pulse 動畫
- [ ] 顯示 last_asr_text（轉寫文字）
- [ ] 顯示 last_intent + confidence（百分比格式）
- [ ] 顯示 models_loaded chips
- [ ] idle_wakeword 且無事件時顯示空狀態
- [ ] 遵守 design-tokens.md 的色板與圓角
- [ ] props 變化時有 transition 動畫（150-300ms）
- [ ] 響應式：sidebar 寬度 360px 自適應
- [ ] 接 Mock Server 資料可正常更新

---

## 不要做的事

- 不要處理 WebSocket 連線（已由 hooks 處理，你只接 props）
- 不要自己定義顏色（用 design tokens）
- 不要做麥克風輸入或音訊處理（那是 Jetson 端的工作）
- 不要做 layout 切換邏輯
- 不要做 ChatPanel 裡的語音氣泡（那是 ChatPanel 的範圍）

---

*最後更新：2026-03-14*
