# Studio 前端測試劇本

> 規格來源：[../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md](../../docs/superpowers/specs/2026-03-16-studio-handoff-design.md)

---

## 啟動

```bash
# 從 repo 根目錄
bash pawai-studio/start.sh
```

啟動後：
- Backend: http://localhost:8001
- Frontend: http://localhost:3000/studio

停止：`Ctrl+C` 或 `bash pawai-studio/stop.sh`

---

## 打開你的頁面

| 負責人 | URL | 改的檔案 |
|--------|-----|---------|
| 鄔 | http://localhost:3000/studio/face | `components/face/face-panel.tsx` |
| 陳 | http://localhost:3000/studio/speech | `components/speech/speech-panel.tsx` |
| 黃 | http://localhost:3000/studio/gesture | `components/gesture/gesture-panel.tsx` |
| 楊 | http://localhost:3000/studio/pose | `components/pose/pose-panel.tsx` |
| 全部整合 | http://localhost:3000/studio | — |

---

## 觸發測試事件

### 全模組（Demo A 場景）

```bash
curl -X POST http://localhost:8001/mock/scenario/demo_a
```

推送 face + speech 的完整 Demo A 流程（6 個事件，每 1.5 秒一個）。

### 各模組獨立觸發

> **注意**：以下 trigger payload 是 **UI 測試捷徑**，把 event_type 和 state data 混在一起推，
> 方便前端一次收到完整 state 更新。**這不是真實的 event schema**。
> 真實 event 和 state 是分開的，以 [event-schema.md](../../docs/Pawai-studio/specs/event-schema.md) 為準。

**Face**
```bash
curl -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source":"face","event_type":"identity_stable","data":{"face_count":2,"tracks":[{"track_id":1,"stable_name":"Roy","sim":0.42,"distance_m":1.25,"bbox":[100,150,200,280],"mode":"stable"},{"track_id":2,"stable_name":"unknown","sim":0.18,"distance_m":2.1,"bbox":[300,180,380,300],"mode":"hold"}],"stamp":0}}'
```

**Speech**
```bash
curl -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source":"speech","event_type":"intent_recognized","data":{"phase":"listening","last_asr_text":"你好","last_intent":"greet","last_tts_text":"哈囉！","models_loaded":["kws","asr","tts"],"stamp":0}}'
```

**Gesture**
```bash
curl -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source":"gesture","event_type":"gesture_detected","data":{"active":true,"current_gesture":"wave","confidence":0.85,"hand":"right","status":"active","stamp":0}}'
```

**Pose**
```bash
curl -X POST http://localhost:8001/mock/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_source":"pose","event_type":"pose_detected","data":{"active":true,"current_pose":"standing","confidence":0.92,"track_id":1,"status":"active","stamp":0}}'
```

---

## 預期看到

觸發對應指令後：
- Panel 內的資料即時更新（文字、數值、badge）
- StatusBadge 從 `inactive` 變成 `active`
- 如果有嵌入 placeholder 圖，圖片區域會顯示
- Chat 區會出現事件卡片

Mock Server 也會每 2 秒自動推送隨機事件。

---

## 你的工作流程

1. 改 `components/{你的功能}/{你的功能}-panel.tsx`
2. 存檔 → 瀏覽器自動刷新（Hot Reload）
3. 觸發上面的 curl 指令看資料變化
4. 看你的 `docs/{功能}-panel-spec.md` 的 M1 checklist

---

## 資料來源對照

| Panel 內容 | 來源 |
|-----------|------|
| 文字數據（sim、distance、phase 等） | Zustand store ← WebSocket mock event |
| Placeholder 圖 | `public/mock/*.svg`（靜態，僅供排版參考） |
| StatusBadge 狀態 | Zustand store |
| 事件歷史 | EventStore ← WebSocket |

**重要**：Placeholder 圖只用於版面開發，不代表最終資料呈現方式。以各 panel-spec.md 為設計依據。

---

## 常見問題

| 問題 | 解法 |
|------|------|
| 看不到資料 | 確認 Mock Server 在跑：`curl http://localhost:8001/api/health` |
| WebSocket 斷線 | 前端會自動重連（3 秒），確認 backend port 8001 在聽 |
| Panel 空白 | 用上面的 curl 觸發對應事件，或等 2-4 秒讓隨機事件到 |
| `npm run dev` 報錯 | 先 `npm install`，確認 Node >= 18 |
| Port 3000 被占用 | `bash pawai-studio/stop.sh` 先清掉舊 process |
| 改了 .tsx 沒反應 | 確認你改的是 `frontend/components/` 下的檔案，不是 `build/` |
