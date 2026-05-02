# PawAI Studio

> Status: current

> 以 chat 為主入口的 embodied AI studio — 統一操作與展示入口。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **Chat ROS2 閉環 + Live View 實機通過**（4/7） |
| 版本/決策 | Next.js 16（前端）+ FastAPI + rclpy（Gateway） |
| 完成度 | Chat 閉環（文字/語音→LLM→TTS→AI bubble）✅ + Live View 三欄影像 ✅ + 錄音音量動畫 ✅ + 5 panel 即時數據 ✅ |
| 最後驗證 | 2026-04-07（Chat 閉環 + 實機 Demo：face greeting + thumbs_up TTS + stop 手勢） |
| 入口檔案 | `pawai-studio/gateway/studio_gateway.py`（Gateway）、`pawai-studio/frontend/`（前端） |
| 測試 | Gateway 31 tests PASS（15 原有 + 13 video + 3 TTS）、Frontend build PASS |

## 啟動方式

```bash
# 測試站（Mock Server，UI 開發用）
bash pawai-studio/start.sh
# → http://localhost:3000/studio
# → Mock Server: http://localhost:8080

# 正式站（連接 Jetson Gateway，Demo 用）
bash pawai-studio/start-live.sh
# → http://localhost:3000/studio      （主控台）
# → http://localhost:3000/studio/live  （三欄即時影像）
# → Gateway: http://100.83.109.89:8080
# 可用 GATEWAY_HOST=<ip> 指定其他 Jetson
```

## 核心流程

```
使用者操作（Chat / 技能按鈕 / 面板）
    ↓
Studio Frontend (Next.js React) ← 5 panel 即時顯示 + Live View 三欄影像
    ↓ WebSocket /ws/events（JSON 事件流）
    ↓ WebSocket /ws/video/{source}（JPEG binary 影像流）
    ↓ WebSocket /ws/text + /ws/speech（瀏覽器→ROS2）
Studio Gateway (FastAPI + rclpy, Jetson:8080)
    ↓ rclpy subscribe 5 event topics + 3 Image topics + publish speech intent
ROS2 Topics（face/speech/gesture/pose/object + 3 debug_image）
```

## 面板清單

| Panel | 路由 | 狀態 |
|-------|------|------|
| Chat | `/studio` | ✅ Mission Control + **Chat 閉環（ROS2 pipeline）** + 錄音動畫 |
| Face | `/studio/face` | ✅ 即時 track 顯示 |
| Speech | `/studio/speech` | ✅ phase + 對話記錄 |
| Gesture | `/studio/gesture` | ✅ 手勢卡片 + 歷史 |
| Pose | `/studio/pose` | ✅ 姿勢 + 信心度 |
| Object | `/studio/object` | ✅ COCO 物件偵測 |
| **Live View** | `/studio/live` | ✅ **三欄即時影像（Foxglove 替代）** |

所有 panel 可折疊（click header）、sidebar 可拖寬（280-600px）、header 有連結到詳細頁。

### Live View (`/studio/live`)

Foxglove 替代展示牆。三欄即時影像 + 精簡 overlay + 事件 ticker：

- **左欄**：`/face_identity/debug_image`（人臉框+名字+相似度）
- **中欄**：`/vision_perception/debug_image`（骨架+手勢+姿勢）
- **右欄**：`/perception/object/debug_image`（YOLO 框+類別）
- **底部**：Event ticker（即時事件滾動條）
- **頂部**：Gateway 連線狀態 + Jetson 溫度

影像走獨立 WebSocket binary（`/ws/video/{source}`），事件走 `/ws/events` JSON，互不干擾。

### Chat 閉環

文字和語音都走 ROS2 pipeline，不建第二條大腦路徑：

```
文字/語音 → Gateway /ws/text 或 /ws/speech
→ /event/speech_intent_recognized → llm_bridge_node → Qwen2.5-7B
→ /tts → tts_node 播放 + Gateway 訂閱 /tts → /ws/events 回推
→ ChatPanel 顯示 AI bubble
```

- 文字送出後 pending 8s，收到 `source: "tts"` event 即顯示回覆
- 錄音時顯示 7 條音量 bars（Web Audio AnalyserNode）
- 已知限制：`/tts` 無 correlation id，pending 期間其他 TTS 可能被誤當回覆

## Gateway 端點

| 端點 | 方向 | 用途 |
|------|------|------|
| `GET /health` | — | 健康檢查 |
| `WS /ws/events` | ROS2→瀏覽器 | 感知事件廣播（face/gesture/pose/speech/object） |
| `WS /ws/text` | 瀏覽器→ROS2 | 文字輸入 → intent → publish |
| `WS /ws/speech` | 瀏覽器→ROS2 | 錄音 → ASR → intent → publish（5MB cap） |
| `WS /ws/video/face` | ROS2→瀏覽器 | JPEG binary — 人臉 debug image（5fps, q70） |
| `WS /ws/video/vision` | ROS2→瀏覽器 | JPEG binary — 手勢+姿勢 debug image |
| `WS /ws/video/object` | ROS2→瀏覽器 | JPEG binary — 物體 debug image |
| `GET /speech` | — | push-to-talk 獨立測試頁 |

## Brain Skill Console（2026-04-28 Phase 2 完成）

Chat 頁從「聊天框」升級為「Brain 決策觀測中樞」。當 brain_node + interaction_executive_node 啟動時，Chat 流會即時渲染 Brain 的每個決策步驟。

### 新元件（`pawai-studio/frontend/components/chat/brain/`）

| 元件 | 角色 |
|------|------|
| `BrainStatusStrip` | 頂部即時狀態列（mode / active skill / step 進度 / safety flags）|
| `SkillButtons` | 5 個按鈕：自我介紹 / 停 / OK / 打招呼 / 去廚房（disabled，hover 顯示「Phase B 才整合 nav_capability」）|
| `SkillTraceDrawer` | 摺疊面板，列最近 proposal + world/safety snapshot |
| `BubbleBrainPlan` | 藍色 — 一般 SkillPlan 提案 |
| `BubbleAlert` | 紅色 — `priority_class === 1` ALERT 提案 |
| `BubbleSafety` | 紅底 — `blocked_by_safety` 或 `selected_skill === "stop_move"` |
| `BubbleSkillStep` | 步驟 — `step_started/success/failed` |
| `BubbleSkillResult` | 完成 — `completed/aborted` |

### 新 Brain topic ↔ UI 對應

| 訂閱 ROS2 → broadcast WS | Studio 渲染位置 |
|------------------------|----------------|
| `/state/pawai_brain` | Brain Status Strip |
| `/brain/proposal` | Brain Plan / Alert bubble + Trace Drawer |
| `/brain/skill_result` | Skill Step / Safety / Result bubble |

### 新 REST 端點（gateway + mock 共用）

- `POST /api/skill_request` → 發 ROS2 `/brain/skill_request`（Skill Buttons 用）
- `POST /api/text_input` → 發 ROS2 `/brain/text_input`（Chat 文字輸入用）
- `POST /mock/scenario/self_introduce`（mock 限定）→ 廣播完整 10-step self_introduce trace，**離線即可開發 / Demo**

### WS envelope 慣例

`source: "brain"` + `event_type: "state" | "proposal" | "skill_result"` — 沿用既有 face/speech/... 慣例（不混進 source 名稱）。

### 既有路徑保留

- `useTextCommand`（`/ws/text` → `/event/speech_intent_recognized`）保留為 legacy fallback，不刪不改
- 既有 face/speech/gesture/pose/object sidebar panels 完全不動

## 已知問題

- Object 精準度受限於 YOLO26n（小物件偵測率低，yolo26s 升級排在後續）
- Face greeting 重複觸發（短時間內同一人被 greet 多次，cooldown 需調整）
- Jetson 供電不穩（XL4015 降壓問題，Demo 風險項）
- **Brain Skill Console UI 樣式為 MVS 雛型**，留待 5/13 freeze 後用 ui-ux-pro-max skill 一次重做（不在 5/16 demo 前動）

## 下一步

- 4/30 教授會議後：接 4 隊員 push（手勢 mapping / 跌倒 TTS / 物體 whitelist / 語音正向表列）→ 加 brain rule + skill_contract 條目 + bubble 文案
- 5/14-5/18：UI 重做（freeze 後）— 用 ui-ux-pro-max skill 配 demo 完整資料流一次重做
- Phase B：Studio Trace Drawer 加「Capability Status」分頁（5/19 後）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| specs/ | brain-adapter、event-schema、system-architecture、ui-orchestration 設計 |
