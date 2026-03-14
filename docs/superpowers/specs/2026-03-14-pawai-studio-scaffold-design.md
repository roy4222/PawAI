# PawAI Studio Scaffold & 分工設計

**建立日期**：2026-03-14
**對齊來源**：mission/README.md v2.0、handoff_316.md、event-schema.md v1.0、ui-orchestration.md v1.0

---

## 1. 設計目標

禮拜一（3/16）交出「可開工包」，讓四人（鄔、陳、黃、楊）不問 Roy 就能開始開發。

### 硬門檻

1. 前端可跑（`npm run dev`），四個功能區都有空殼元件
2. Mock Server 可推 face / speech / gesture / pose 事件
3. `POST /api/command` 有 response
4. 文件足夠讓四人自主開工

---

## 2. 架構決策

### 2.1 單頁動態 Panel 架構

**核心概念**：ChatGPT 式入口 + Foxglove 式面板動態展開。

- 初始狀態：只有 Chat 輸入框（`chat_only` preset）
- 事件觸發後：Rule-based 查表展開對應 Panel
- 使用者可手動收合任一 Panel

**不做 LLM 驅動面板編排**（3/16 前），先用 rule-based，後續可升級。

### 2.2 技術棧

| 層級 | 技術 |
|------|------|
| Frontend | Next.js 14 (App Router) + Tailwind CSS + shadcn/ui |
| Backend | FastAPI + WebSocket + uvicorn |
| 通訊 | WebSocket (`/ws/events`) + REST (`/api/*`) |
| 圖示 | Lucide Icons（shadcn 預設） |
| 狀態管理 | Zustand（輕量） |

### 2.3 資料來源切換

用 HTTP header `X-Data-Source: mock | live` 或環境變數 `DATA_SOURCE` 切換，不用 query param。

```bash
# .env.development（Mock 模式）
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8001
NEXT_PUBLIC_WS_URL=ws://localhost:8001/ws
DATA_SOURCE=mock
```

---

## 3. 專案結構

```
pawai-studio/
├── frontend/
│   ├── app/
│   │   ├── layout.tsx              # 全站 layout（Topbar + Sidebar nav）
│   │   ├── page.tsx                # / → redirect to /studio
│   │   └── (studio)/
│   │       └── studio/
│   │           └── page.tsx        # 主入口（Chat + 動態 Panels）
│   ├── components/
│   │   ├── layout/
│   │   │   ├── topbar.tsx
│   │   │   ├── studio-layout.tsx   # 主 layout 容器
│   │   │   └── panel-container.tsx # 面板位置管理
│   │   ├── shared/
│   │   │   ├── panel-card.tsx      # 統一面板卡片
│   │   │   ├── status-badge.tsx    # 三色狀態 badge
│   │   │   ├── event-item.tsx      # 事件列表項目
│   │   │   ├── metric-chip.tsx     # 數值指標
│   │   │   └── live-indicator.tsx  # 綠色脈衝點
│   │   ├── chat/
│   │   │   └── chat-panel.tsx      # Roy 做
│   │   ├── face/
│   │   │   └── face-panel.tsx      # 鄔做（空殼）
│   │   ├── speech/
│   │   │   └── speech-panel.tsx    # 陳做（空殼）
│   │   ├── gesture/
│   │   │   └── gesture-panel.tsx   # 黃做（空殼）
│   │   └── pose/
│   │       └── pose-panel.tsx      # 楊做（空殼）
│   ├── hooks/
│   │   ├── use-websocket.ts        # WebSocket 連線管理
│   │   ├── use-event-stream.ts     # 事件流訂閱
│   │   └── use-layout-manager.ts   # Layout 切換邏輯
│   ├── stores/
│   │   ├── event-store.ts          # 事件歷史（Zustand）
│   │   ├── state-store.ts          # 系統狀態
│   │   └── layout-store.ts         # 面板配置
│   ├── contracts/
│   │   └── types.ts                # 從 event-schema.md 產生的 TS 型別
│   ├── tailwind.config.ts
│   └── package.json
│
├── backend/
│   ├── gateway.py                  # Studio Gateway（REST + WebSocket）
│   ├── mock_server.py              # Mock Event Server（假資料 + 場景重播）
│   ├── schemas.py                  # Pydantic models（真相來源）
│   └── requirements.txt
│
└── docs/
    ├── face-panel-spec.md
    ├── speech-panel-spec.md
    ├── gesture-panel-spec.md
    ├── pose-panel-spec.md
    ├── design-tokens.md
    └── git-workflow.md
```

---

## 4. 視覺規範

### 4.1 風格定位

**AI-Native Dark Studio** — 參考 Claude / Cursor 的「低調但有互動感」。

### 4.2 Design Tokens

| Token | 值 | 用途 |
|-------|-----|------|
| `--background` | `#0A0A0F` | 全站背景（近黑，不是純黑） |
| `--surface` | `#141419` | 卡片、Panel 背景 |
| `--surface-hover` | `#1C1C24` | 卡片 hover |
| `--border` | `#2A2A35` | 邊框、分隔線 |
| `--text-primary` | `#F0F0F5` | 主文字 |
| `--text-secondary` | `#8B8B9E` | 次要文字 |
| `--text-muted` | `#55556A` | 提示文字 |
| `--accent` | `#7C6BFF` | 主色調（AI 紫） |
| `--accent-hover` | `#9585FF` | 主色 hover |
| `--success` | `#22C55E` | 狀態正常 / 連線中 |
| `--warning` | `#F59E0B` | 警告 |
| `--destructive` | `#EF4444` | 錯誤 / 離線 |
| `--radius` | `12px` | 卡片圓角 |
| `--radius-sm` | `8px` | 按鈕/badge 圓角 |
| `--radius-full` | `9999px` | 頭像/圓形 |

### 4.3 字體

| 用途 | 字體 | 備註 |
|------|------|------|
| 標題/UI | Inter | 乾淨現代，shadcn 預設 |
| 程式碼/數據 | Fira Code | Monospace，延遲/數值 |
| 中文 | Noto Sans TC | 繁體中文 fallback |

---

## 5. Layout Orchestration

### 5.1 Layout Preset 規則表

| Preset | 觸發條件 | 顯示 |
|--------|---------|------|
| `chat_only` | 初始 / 無事件 | Chat 全寬 |
| `chat_face` | `face:track_started` 或 `face:identity_stable` | Chat + FacePanel |
| `chat_speech` | `speech:intent_recognized` 或 `speech:wake_word` | Chat + SpeechPanel |
| `chat_face_speech` | face + speech 事件同時活躍 | Chat + Face + Speech |
| `chat_gesture` | `gesture:gesture_detected` | Chat + GesturePanel |
| `chat_pose` | `pose:pose_detected` | Chat + PosePanel |
| `chat_full` | `active_panels >= 3` 或 3 種以上不同 source 在 10s 內出現 | Chat + 最多 3 panels |

### 5.2 規則

- Chat **永遠在左，不消失**
- 右側 sidebar **最多同時 3 個 Panel**，超過時依優先級替換
- Panel 優先級：Face(1) > Speech(2) > Brain(3) > Gesture(4) > Pose(5)
- 使用者可手動收合任一 Panel
- 收合後該 Panel 不自動回來，直到新事件觸發
- **例外**：`critical` 事件（system:error、degradation_change、stop 指令）可強制重新展開被收合的 Panel

---

## 6. ChatPanel 互動設計

### 6.1 五個核心元素

| 元素 | 說明 | 互動 |
|------|------|------|
| AI 訊息 | 深色氣泡 `surface` + 左側紫色條 | streaming 逐字出現 |
| User 訊息 | `accent/10` 淡紫底，靠右 | 送出後淡入 |
| Event Card | 嵌在訊息流裡的狀態卡片 | 點擊展開對應 Panel |
| Status Chip | Thinking / Listening / Speaking | 脈衝動畫 |
| Timeline | 底部事件流（可收合） | 點事件高亮對應訊息 |

### 6.2 必做互動

- Streaming text（逐字出現）
- Thinking/status chip（3-dot pulse + 狀態文字）
- Inline event cards（face/speech/gesture/pose 事件嵌入聊天流）
- Timeline jump（點事件卡片跳到對應 Panel）
- 固定底部 input bar

---

## 7. 分工方案

### 7.1 四人交付物

| 人 | 元件 | Props 介面 | 模型依賴 |
|----|------|-----------|---------|
| 鄔 | `<FacePanel data={FaceState} events={FaceIdentityEvent[]} />` | FaceState, FaceIdentityEvent | 無（純 UI） |
| 陳 | `<SpeechPanel data={SpeechState} events={SpeechIntentEvent[]} />` | SpeechState, SpeechIntentEvent | 無（純 UI） |
| 黃 | `<GesturePanel data={GestureState} events={GestureEvent[]} />` | GestureState, GestureEvent | 無（模型無關） |
| 楊 | `<PosePanel data={PoseState} events={PoseEvent[]} />` | PoseState, PoseEvent | 無（模型無關） |

### 7.2 模型無關原則

- GestureState、PoseState 使用通用欄位：`label`、`confidence`、`timestamp`、`source`、`status`
- MediaPipe / MoveNet / 其他模型皆可，輸出需符合同一 props 介面
- Mock 先跑起來，真機模型接入時只換資料來源，不改 UI

### 7.3 四人不碰的層

```
四人的 Panel（只碰 props）
    ↓ props
LayoutOrchestrator（Roy 做）
    ↓ subscribe
useWebSocket hook（Roy 做）
    ↓ ws://
Gateway / Mock Server（Roy 做）
    ↓ redis / direct
ros2_bridge_node（Roy 做）
    ↓ ROS2
Jetson 真機
```

### 7.4 共用元件（四人必須用）

| 元件 | shadcn 基礎 | 規範 |
|------|-------------|------|
| `PanelCard` | `Card` | `bg-surface border-border rounded-[12px]` |
| `StatusBadge` | `Badge` | 三色：success/warning/destructive + pulse |
| `EventItem` | 自建 | 時間戳 + 事件類型 + 摘要，hover 高亮 |
| `MetricChip` | `Badge variant=outline` | 數值 + 單位 + 趨勢箭頭 |
| `LiveIndicator` | 自建 | 綠色圓點 + pulse animation |

---

## 8. 前後端連通保證

### 8.1 型別產生鏈

```
event-schema.md（真相來源）
    ↓ 手動對齊
backend/schemas.py（Pydantic models）
    ↓ 產生
frontend/contracts/types.ts（TS 型別）
```

四人只需 import `contracts/types.ts`，不需要看 backend 或 event-schema.md。

### 8.2 Mock Server 規格

| 端點 | 方法 | 用途 |
|------|------|------|
| `/ws/events` | WebSocket | 事件推送（與 Gateway 相同） |
| `/api/command` | POST | 技能指令（回 200 + echo） |
| `/api/chat` | POST | 對話（回模板回覆） |
| `/api/brain` | GET | 大腦狀態 |
| `/api/health` | GET | 系統健康 |
| `/mock/trigger` | POST | 手動觸發任意事件 |
| `/mock/scenario/demo_a` | POST | 重播 Demo A 事件序列 |

### 8.3 Mock 事件推送行為

- 連接 WebSocket 後，每 2s 推送一個隨機事件
- Demo A 場景：按時序推送完整事件鏈（face → speech → brain → skill）
- 手動觸發：`POST /mock/trigger` 立即推送指定事件

---

## 9. 下午真機閉環（獨立任務）

與上午的 Studio scaffold 無關，在 Jetson 上做：

```
face_identity_infer_cv.py 發布 /event/face_identity
    → 新增 glue node：face_event_handler
    → 訂閱 /event/face_identity
    → identity_stable 時發 /tts「{stable_name}你好！」
    → 同時發 /webrtc_req wave 動作
```

只做最小主線，不開新需求。

---

*最後更新：2026-03-14*
*維護者：Roy (System Architect)*
