# PawAI Studio 前端分工（4/8-4/13）

每個人負責自己模組的 Studio 功能頁面，把它從「一個小 Panel + 空白」變成完整的模組監控頁。

## 環境啟動（所有人必讀）

### 一鍵啟動（推薦）

```bash
# 從 repo 根目錄執行
bash pawai-studio/start.sh
```

這會自動：
1. 檢查 python3 / node 環境
2. 自動安裝缺少的 Python 依賴（fastapi, uvicorn, pydantic, wsproto）
3. 自動 `npm install`（如果 node_modules 不存在）
4. 啟動 Mock Server（port 8080）
5. 啟動 Frontend（port 3000）

啟動成功後會看到：
```
  🌐 Studio:      http://localhost:3000/studio
  🔧 Mock Server:  http://localhost:8080
  📡 WebSocket:    ws://localhost:8080/ws/events
```

按 `Ctrl+C` 停止全部。

### 手動啟動（如果一鍵啟動有問題）

```bash
# Terminal 1：Mock Server
cd pawai-studio/backend
pip install fastapi uvicorn pydantic wsproto
python3 -m uvicorn mock_server:app --host 0.0.0.0 --port 8080 --ws wsproto
# → http://localhost:8080/docs （API 文件）

# Terminal 2：前端
cd pawai-studio/frontend
npm install
npm run dev
# → http://localhost:3000/studio
```

開好後打開瀏覽器，你會看到每 2 秒自動跳出各模組的模擬資料。

## Mock Server 可用的資料來源

**你不需要 Jetson、不需要 Go2、不需要 ROS2。** Mock server 會模擬所有後端資料。

### 自動推送（WebSocket `/ws/events`）

前端已經透過 `useEventStream()` hook 接好了。Mock server **每 2 秒**隨機推送一個事件，五大模組都有：

| source | event_type | 推送的資料 |
|--------|-----------|-----------|
| `face` | `track_started` / `identity_stable` / `track_lost` | `face_count`, `tracks[]`（每個 track 有 `track_id`, `stable_name`, `sim`, `distance_m`, `bbox`, `mode`） |
| `speech` | `intent_recognized` | `phase`, `last_asr_text`, `last_intent`, `last_tts_text`, `models_loaded[]` |
| `gesture` | `gesture_detected` | `current_gesture`（wave/stop/point/ok）, `confidence`, `hand`（left/right）, `status` |
| `pose` | `pose_detected` | `current_pose`（standing/sitting/crouching/fallen）, `confidence`, `track_id`, `status` |
| `object` | `object_detected` | `objects[]`（每個有 `class_name`, `class_id`, `confidence`, `bbox`） |

### 手動觸發

```bash
# 觸發 Demo A 場景（face → speech → brain 連續事件）
curl -X POST http://localhost:8080/mock/scenario/demo_a

# 觸發指定模組的單一事件
curl -X POST http://localhost:8080/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "pose", "event_type": "pose_detected", "data": {"current_pose": "fallen", "confidence": 0.95, "track_id": 1, "active": true, "status": "active", "stamp": 0}}'

# 觸發 face 事件
curl -X POST http://localhost:8080/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source": "face", "event_type": "identity_stable", "data": {"track_id": 1, "stable_name": "Roy", "sim": 0.92, "distance_m": 1.5}}'
```

### 聊天功能

```bash
# 文字聊天（前端 ChatPanel 已接好）
# WebSocket: ws://localhost:8080/ws/text
# 送出文字 → 回傳 {asr, intent, confidence} + 自動 broadcast TTS 回覆

# 語音聊天（前端 push-to-talk 已接好）
# WebSocket: ws://localhost:8080/ws/speech
# 送出 audio bytes → 回傳 {asr, intent, confidence, latency_ms}
```

### REST API

```bash
# 系統健康狀態
curl http://localhost:8080/api/health

# 大腦狀態
curl http://localhost:8080/api/brain

# 發送指令
curl -X POST http://localhost:8080/api/command \
  -H "Content-Type: application/json" \
  -d '{"skill_id": "hello", "source": "studio"}'
```

## 前端已有的 Hook 和 Store

你寫 component 時可以直接用這些：

```tsx
// 取得即時狀態（Zustand store）
import { useStateStore } from "@/stores/state-store";

const faceState = useStateStore(s => s.faceState);       // 人臉
const gestureState = useStateStore(s => s.gestureState);   // 手勢
const poseState = useStateStore(s => s.poseState);         // 姿勢
const objectState = useStateStore(s => s.objectState);     // 物體
const speechState = useStateStore(s => s.speechState);     // 語音
const lastTtsText = useStateStore(s => s.lastTtsText);     // 最近 TTS

// 取得事件歷史
import { useEventStore } from "@/stores/event-store";
const events = useEventStore(s => s.events);  // 最近 100 筆事件

// 篩選特定模組的事件
const faceEvents = events.filter(e => e.source === "face");
const gestureEvents = events.filter(e => e.source === "gesture");

// WebSocket 影像串流（需要 Gateway，mock 不支援）
import { useVideoStream } from "@/hooks/use-video-stream";
const { blobUrl, fps, isConnected } = useVideoStream("face");
```

## 共用 UI 元件

```tsx
import { PanelCard } from "@/components/shared/panel-card";
import { StatusBadge } from "@/components/shared/status-badge";
import { MetricChip } from "@/components/shared/metric-chip";
import { EventItem } from "@/components/shared/event-item";
import { LiveIndicator } from "@/components/shared/live-indicator";

// shadcn/ui
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
```

## 分工總覽

### Studio 前端頁面

| 負責人 | 頁面 | 前端開發文件 |
|--------|------|------------|
| 鄔雨彤 | `/studio/gesture` | [gesture-assignment.md](gesture-assignment.md) |
| 楊沛蓁 | `/studio/pose` | [pose-assignment.md](pose-assignment.md) |
| 黃旭 | `/studio/object` | [object-assignment.md](object-assignment.md) |

> 人臉頁面 (`/studio/face`) 由 Roy 處理：[face-assignment.md](face-assignment.md)

### Go2 互動設計（4/9 新增）— 偵測到之後做什麼動作 + 說什麼話

| 負責人 | 功能 | 詳細文件（含模型 + 本機復現步驟） |
|--------|------|-------------------------------|
| **鄔雨彤** | 手勢辨識 | [gesture-wu.md](../go2-jetson/gesture-wu.md) |
| **楊沛蓁** | 姿勢辨識 | [pose-yang.md](../go2-jetson/pose-yang.md) |
| **陳若恩** | 語音功能 | [speech-chen.md](../go2-jetson/speech-chen.md) |
| **黃旭** | 物體辨識 | [object-huang.md](../go2-jetson/object-huang.md) |

👉 **[互動設計總覽（Go2 API 參考 + 映射表）](../go2-jetson/interaction-design.md)**

## Git 規範

```bash
# 建立自己的 branch
git checkout -b studio/你的名字

# 只改你自己的檔案
# ✅ app/(studio)/studio/你的模組/page.tsx
# ✅ components/你的模組/*.tsx（可新增檔案）
# ❌ 不要改 stores/、hooks/、components/shared/、其他人的模組

# 每天 push
git add -A && git commit -m "feat(studio): 你做了什麼"
git push origin studio/你的名字
```
