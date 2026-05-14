# PawAI Studio 前端交接設計

**版本**：v1.0
**日期**：2026-03-16
**目的**：定義後端（Roy）交給前端（鄔/陳/黃/楊）的最小可測試開發環境
**驗收標準**：前端開發者 clone repo → 一鍵啟動 → 看到有資料的面板 + placeholder 圖 → 可以開始改自己的 panel

---

## 1. 交接範圍

### 後端（Roy）負責

1. Mock Server 推正確格式的 state/event（已完成）
2. 6 張 placeholder SVG 放到 `public/mock/`（本 spec）
3. 測試劇本 `testing-playbook.md`（本 spec）
4. 每個模組的 mock scenario endpoint（demo_a / demo_gesture / demo_pose）

### 前端（各負責人）負責

1. 照 `docs/{panel}-panel-spec.md` 開發自己的 panel
2. **自己把 placeholder 圖嵌入自己的 panel**（後端只提供圖檔，不碰你的 .tsx）
3. 接 Zustand store 的即時資料
4. placeholder 嵌入方式見 §3

### 不做

- 後端不改任何 panel 的 .tsx（Roy 不碰前端元件）
- 不做假 camera 串流
- 不做影音 mock

---

## 2. Mock Assets

### 2.1 位置

```
pawai-studio/frontend/public/mock/
├── face-placeholder.svg
├── speech-placeholder.svg
├── gesture-placeholder.svg
├── pose-placeholder.svg
├── camera-placeholder.svg
└── brain-placeholder.svg
```

### 2.2 統一規格

| 規格 | 值 |
|------|-----|
| 格式 | SVG（全部統一，包括 camera） |
| 比例 | 16:9（寬 360px × 高 202px） |
| 背景 | `#0A0A0F`（design-tokens `--background`） |
| 線條 | `#F0F0F5` 50% opacity（design-tokens `--foreground`） |
| 重點色 | 各模組對應的 source color（見 event-item.tsx） |
| 文字 | Inter / Noto Sans TC，12-14px |
| 風格 | wireframe 風格 — 線條 + 標註 + icon，不是真實截圖 |

### 2.3 各圖內容

**face-placeholder.svg**
- 深色背景上 1-2 個方框（模擬人臉 bbox）
- 方框上方標註 "Roy" / "unknown"
- 方框旁小字：sim 42% · 1.2m · stable
- 用 `#3B82F6`（face blue）作為方框顏色

**speech-placeholder.svg**
- 上半部：waveform 示意線條
- 下半部：對話氣泡 "你好" → "哈囉，我在這裡。"
- 右上角：phase badge "listening"
- 用 `#7C6BFF`（primary purple）

**gesture-placeholder.svg**
- 手掌輪廓線條
- 手掌旁標註 "wave 👋" + "confidence 85%"
- 用 `#22C55E`（success green）

**pose-placeholder.svg**
- 簡化骨架人形（頭、肩、手、腳 的圓點 + 線段）
- 人形旁標註 "standing" + "confidence 92%"
- 用 `#F97316`（pose orange）

**camera-placeholder.svg**
- 攝影機取景框（16:9 框線 + 四角標記）
- 中央大字 "D435 RGB-D"
- 下方小字 "640×480 · 30fps"
- 用 `#8B8B9E`（muted）

**brain-placeholder.svg**
- 決策卡片示意：三行
  - intent: greet
  - skill: hello
  - reasoning: "偵測到熟人，打招呼"
- 用 `#F59E0B`（warning yellow / brain）

---

## 3. Panel Placeholder 模式

### 3.1 共用 pattern（不改 shared 元件）

在各 panel 的 `.tsx` 裡用統一模式，方便之後替換：

```tsx
// 每個 panel 內部使用
const PLACEHOLDER_SRC = "/mock/{panel}-placeholder.svg"
const SHOW_PLACEHOLDER = true  // 前端開發者之後設 false 替換成真實元件

// JSX 裡
{SHOW_PLACEHOLDER && (
  <div className="rounded-lg overflow-hidden border border-border/20">
    <img
      src={PLACEHOLDER_SRC}
      alt="{panel} placeholder"
      className="w-full h-auto"
    />
  </div>
)}
```

### 3.2 為什麼不做成 shared component

- 只有 6 個地方用
- 每個 panel 之後替換方式不同（有的換 canvas，有的換 video）
- 做 shared 反而增加耦合

### 3.3 替換路徑

前端開發者在做 M2（3/23）時：
1. 把 `SHOW_PLACEHOLDER` 改成 `false`
2. 用真實元件取代 `<img>` 區塊
3. 刪掉 `PLACEHOLDER_SRC` 常數

---

## 4. 測試劇本

放在 `pawai-studio/docs/testing-playbook.md`。

### 內容大綱

```markdown
# Studio 前端測試劇本

## 啟動
bash pawai-studio/start.sh
→ Backend: http://localhost:8001
→ Frontend: http://localhost:3000/studio

## 打開你的頁面
| 人 | URL |
|----|-----|
| 鄔 | localhost:3000/studio/face |
| 陳 | localhost:3000/studio/speech |
| 黃 | localhost:3000/studio/gesture |
| 楊 | localhost:3000/studio/pose |
| 全部 | localhost:3000/studio |

## 觸發事件（依你負責的模組選）

| 你負責 | 觸發指令 | 推送內容 |
|--------|---------|---------|
| 全部 | `curl -X POST http://localhost:8001/mock/scenario/demo_a` | face + speech 完整 Demo A 流程 |
| face | `curl -X POST http://localhost:8001/mock/trigger -H "Content-Type: application/json" -d '{"event_source":"face","event_type":"identity_stable","data":{"face_count":2,"tracks":[{"track_id":1,"stable_name":"Roy","sim":0.42,"distance_m":1.25,"bbox":[100,150,200,280],"mode":"stable"},{"track_id":2,"stable_name":"unknown","sim":0.18,"distance_m":2.1,"bbox":[300,180,380,300],"mode":"hold"}]}}'` | 2 人追蹤 state |
| speech | `curl -X POST http://localhost:8001/mock/trigger -H "Content-Type: application/json" -d '{"event_source":"speech","event_type":"intent_recognized","data":{"phase":"listening","last_asr_text":"你好","last_intent":"greet","last_tts_text":"哈囉！","models_loaded":["kws","asr","tts"],"stamp":0}}'` | 語音 state |
| gesture | `curl -X POST http://localhost:8001/mock/trigger -H "Content-Type: application/json" -d '{"event_source":"gesture","event_type":"gesture_detected","data":{"active":true,"current_gesture":"wave","confidence":0.85,"hand":"right","status":"active","stamp":0}}'` | 手勢 state |
| pose | `curl -X POST http://localhost:8001/mock/trigger -H "Content-Type: application/json" -d '{"event_source":"pose","event_type":"pose_detected","data":{"active":true,"current_pose":"standing","confidence":0.92,"track_id":1,"status":"active","stamp":0}}'` | 姿勢 state |

## 預期看到
- Placeholder 圖片顯示在 panel 內（你自己嵌入的）
- 觸發對應 trigger 後，panel 資料即時更新
- demo_a 觸發後，face/speech 事件依序出現在 chat 區
- 每 2 秒也有隨機事件推送

## 你的工作
1. 改 components/{你的功能}/{你的功能}-panel.tsx
2. 存檔 → 瀏覽器自動刷新
3. 看 docs/{你的功能}-panel-spec.md 的 M1 checklist

## 資料來源對照
| panel 內容 | 來源 |
|-----------|------|
| 文字數據（sim、distance、phase） | Zustand store ← WebSocket mock event |
| Placeholder 圖 | /public/mock/*.svg（靜態，僅供排版參考） |
| StatusBadge 狀態 | Zustand store |
| 事件歷史 | EventStore ← WebSocket |

## 重要提醒
Placeholder 圖只用於版面開發，不代表最終資料呈現方式。
前端開發者應以 panel-spec.md 為設計依據，不是以 placeholder 圖為準。

## 常見問題
| 問題 | 解法 |
|------|------|
| 看不到資料 | 確認 Mock Server 在跑：curl http://localhost:8001/api/health |
| WebSocket 斷線 | 前端會自動重連（3 秒），確認 backend port 8001 在聽 |
| Panel 空白 | 跑一次 demo_a，或等 2-4 秒讓隨機事件到 |
| npm run dev 報錯 | 先 npm install，確認 Node >= 18 |
```

---

## 5. 開會摘要（20:30 用）

> **已完成**
> 1. Cloud LLM（Qwen3.5-9B on RTX 8000）已部署，語音/人臉 → LLM → TTS 鏈路通過 Phase 1
> 2. PawAI Studio Mock Server + Frontend 可用
> 3. 每個人有獨立開發頁面（/studio/face 等）
> 4. Spec、design tokens、測試劇本都寫好了
>
> **前端接手條件**
> - `bash pawai-studio/start.sh` → 看到面板 + placeholder 圖 + mock 資料
> - 改自己的 `.tsx` → 存檔自動刷新
> - 不需要機器狗、不需要 ROS2、不需要 Jetson
>
> **下一步**
> - Roy：Jetson Phase 2 真機測試（語音 + 人臉 + Go2 動作）
> - 鄔/陳/黃/楊：照 spec 開發各自 panel，M1 目標 3/16 交

---

*維護者：System Architect*
