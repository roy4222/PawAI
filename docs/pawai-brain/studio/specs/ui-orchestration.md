# PawAI Studio UI Orchestration

**文件版本**：v1.1
**最後更新**：2026-03-14
**對齊來源**：[mission/README.md](../mission/README.md) v2.0

---

## 設計原則

> **預設像 ChatGPT，一個乾淨的對話入口；需要觀測與控制時，再像 Foxglove 一樣展開即時面板與事件流。**

### 核心規則

1. **Chat 永遠在** — Chat 面板不可隱藏，是使用者的主入口
2. **事件驅動展開** — 面板的出現由系統事件觸發，不由使用者手動開
3. **使用者可收合** — 任何面板都可以手動收合，使用者偏好優先
4. **不超過 4 面板** — 同時可見面板上限 4 個（含 Chat），避免資訊過載
5. **Demo 模式例外** — Demo Showcase 頁面可同時展示更多面板

---

## Layout 系統

### 面板位置

```
┌──────────────────────────────────────────────────┐
│                    top-bar                         │
├──────────────────┬───────────────────────────────┤
│                  │                                │
│    main          │    sidebar                     │
│    (Chat)        │    (Camera / Face / Brain)     │
│                  │                                │
│                  │                                │
├──────────────────┴───────────────────────────────┤
│                    bottom                          │
│    (Timeline / Speech / Health)                    │
└──────────────────────────────────────────────────┘
```

| 位置 | 用途 | 最大面板數 |
|------|------|:---------:|
| `main` | Chat（固定） | 1 |
| `sidebar` | 視覺/狀態面板 | 2 |
| `bottom` | 時間軸/狀態列 | 1 |

### Layout Preset 定義

#### `chat_only`（預設）
```
┌──────────────────────────────────────┐
│                                      │
│              ChatPanel               │
│                                      │
└──────────────────────────────────────┘
```

#### `chat_camera`（偵測到人臉時）
```
┌───────────────────┬──────────────────┐
│                   │                  │
│    ChatPanel      │   CameraPanel    │
│                   │   FacePanel      │
│                   │                  │
└───────────────────┴──────────────────┘
```

#### `chat_speech`（語音互動中）
```
┌──────────────────────────────────────┐
│              ChatPanel               │
├──────────────────────────────────────┤
│           SpeechPanel                │
└──────────────────────────────────────┘
```

#### `chat_camera_speech`（人臉 + 語音同時活躍）
```
┌───────────────────┬──────────────────┐
│                   │   CameraPanel    │
│    ChatPanel      │   FacePanel      │
│                   ├──────────────────┤
│                   │   SpeechPanel    │
└───────────────────┴──────────────────┘
```

#### `chat_gesture`（手勢偵測時）
```
┌───────────────────┬──────────────────┐
│                   │                  │
│    ChatPanel      │   GesturePanel   │
│                   │                  │
└───────────────────┴──────────────────┘
```

#### `chat_pose`（姿勢偵測時）
```
┌───────────────────┬──────────────────┐
│                   │                  │
│    ChatPanel      │   PosePanel      │
│                   │                  │
└───────────────────┴──────────────────┘
```

#### `chat_full`（`active_panels >= 3` 或 3 種以上不同 source 在 10s 內出現）
```
┌───────────────────┬──────────────────┐
│                   │   CameraPanel    │
│    ChatPanel      │   BrainPanel     │
│                   │                  │
├───────────────────┴──────────────────┤
│      TimelinePanel + HealthPanel     │
└──────────────────────────────────────┘
```

#### `demo`（Demo Showcase）
```
┌───────────────────┬──────────────────┐
│                   │   CameraPanel    │
│    ChatPanel      │   BrainPanel     │
│                   │                  │
├───────────────────┴──────────────────┤
│            TimelinePanel             │
└──────────────────────────────────────┘
```

---

## 事件驅動切換規則

### 觸發矩陣

事件欄位使用 `source` + `event_type` 組合匹配（與 [event-schema.md](./event-schema.md) 的 `PawAIEvent` 信封一致）。

| source | event_type | 從 | 到 | 條件 |
|--------|-----------|----|----|------|
| `face` | `track_started` | `chat_only` | `chat_camera` | 首次偵測到人臉 |
| `face` | `track_lost` | `chat_camera` | `chat_only` | 所有人臉消失 ≥5s |
| `speech` | `wake_word` | 任何 | 保持 + `SpeechPanel` | 喚醒詞觸發 |
| `speech` | `intent_recognized` | 任何 | 保持 + `SpeechPanel` | 語音意圖識別 |
| `face` + `speech` | 同時活躍 | 任何 | `chat_camera_speech` | face + speech 事件在同一時段 |
| `gesture` | `gesture_detected` | 任何 | 保持 + `GesturePanel` | 手勢偵測 |
| `pose` | `pose_detected` | 任何 | 保持 + `PosePanel` | 姿勢偵測 |
| `pose` | `pose_detected` (fallen) | 任何 | **強制展開** `PosePanel` | Critical：跌倒偵測 |
| `brain` | `skill_dispatched` | 任何 | 保持 + `BrainPanel` | 大腦派遣技能 |
| `system` | `degradation_change` | 任何 | **強制展開** `HealthPanel` | Critical：降級等級變更 |
| `system` | `error` | 任何 | **強制展開** `HealthPanel` | Critical：系統錯誤 |
| — | — | 任何 | `chat_full` | 使用者點擊 "Show All" |
| — | — | 任何 | `demo` | Demo 頁面進入 |

### 切換邏輯（偽代碼）

```typescript
function onEvent(event: PawAIEvent) {
  // 使用 source + event_type 匹配（與 event-schema.md 一致）
  const key = `${event.source}:${event.event_type}`;

  // 使用者手動收合的面板不自動展開
  if (userDismissed.has(panelForKey(key))) return;

  // 同時可見面板不超過 4 個
  const nextPanels = computeNextPanels(currentLayout, key);
  if (nextPanels.length > 4) {
    // 移除優先級最低的面板
    nextPanels.sort(byPriority);
    nextPanels.length = 4;
  }

  setLayout(nextPanels);
}
```

### 面板優先級

| 優先級 | 面板 | 說明 |
|:------:|------|------|
| 1 (最高) | ChatPanel | 永遠可見 |
| 2 | CameraPanel | 有人臉時 |
| 3 | BrainPanel | 大腦在動作時 |
| 4 | SpeechPanel | 語音互動時 |
| 5 | TimelinePanel | Demo 模式 |
| 6 | HealthPanel | 異常時 |
| 7 | SkillButtons | 手動控制 |
| 8 (最低) | GesturePanel / PosePanel | P1，較少觸發 |

---

## Demo Showcase 頁面

### 設計目標

讓評審在 60 秒內理解系統能力。

### 流程

1. **開場**：展示 PawAI 介紹（2-3 句）
2. **Demo A 按鈕**：一鍵啟動主線閉環 Demo
   - 自動切換到 `demo` layout
   - Timeline 即時更新事件
   - Brain Panel 顯示決策過程
3. **Demo B 按鈕**（P1）：手勢互動 Demo
4. **回放**：可重播過去的 Demo 錄影 / 事件序列

### Demo 控制元件

```typescript
interface DemoControl {
  scenarios: ["demo_a", "demo_b", "demo_c"];
  actions: {
    start: () => void;     // 開始 Demo（觸發 Mock 或真機）
    pause: () => void;
    reset: () => void;
    replay: (recording_id: string) => void;
  };
}
```

---

## 響應式設計

| 螢幕 | Layout 行為 |
|------|------------|
| Desktop (>= 1200px) | 完整 sidebar + bottom |
| Tablet (768-1199px) | sidebar 收合為 tabs |
| Mobile (< 768px) | 僅 ChatPanel + 底部 tab 切換 |

---

## 前端元件架構

```
src/
├── components/
│   ├── panels/
│   │   ├── ChatPanel.tsx
│   │   ├── CameraPanel.tsx
│   │   ├── FacePanel.tsx
│   │   ├── SpeechPanel.tsx
│   │   ├── BrainPanel.tsx
│   │   ├── TimelinePanel.tsx
│   │   ├── SystemHealthPanel.tsx
│   │   ├── SkillButtons.tsx
│   │   ├── GesturePanel.tsx
│   │   └── PosePanel.tsx
│   ├── layout/
│   │   ├── StudioLayout.tsx      # 主 layout 容器
│   │   └── PanelContainer.tsx    # 面板位置管理
│   └── demo/
│       └── DemoShowcase.tsx
├── hooks/
│   ├── useWebSocket.ts           # WebSocket 連線管理
│   ├── useEventStream.ts         # 事件流訂閱
│   └── useLayoutManager.ts       # Layout 切換邏輯
├── stores/
│   ├── eventStore.ts             # 事件歷史
│   ├── stateStore.ts             # 系統狀態
│   └── layoutStore.ts            # 面板配置
└── pages/
    ├── index.tsx                  # Studio Home
    ├── debug.tsx                  # Debug Console
    └── demo.tsx                   # Demo Showcase
```

---

*最後更新：2026-03-13*
*維護者：System Architect*
