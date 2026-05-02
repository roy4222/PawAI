# 3/16 攻守交換：分工交付清單

> **⚠️ 過時警告（2026-03-18）**：此文件反映 2026-03-16 狀態，部分成員分工與時程已更新，請以 [mission/README.md](./README.md) v2.2 為準。

**文件版本**：v1.0
**建立日期**：2026-03-13
**交付期限**：2026-03-16（週一）
**對齊來源**：[mission/README.md](./README.md) v2.0、[interaction_contract.md](../architecture/interaction_contract.md) v2.0

> 3/16 是攻守交換日。Roy 交出架構核心與 Mock 環境，讓所有人在上面開發。
> 3/16 後 Roy 轉做整合（Brain + 手勢姿勢部署 + Demo pipeline），其他人接手前端與文件。

---

## 1. Owner Matrix

### 1.1 3/16 前：誰做什麼

| Owner | 交付項目 | 需要真機 | 可遠端 | 依賴 |
|-------|----------|:--------:|:------:|------|
| **Roy** | 語音閉環（KWS + ASR + TTS + Go2 播放） | ✅ | — | Jetson + Go2 + 麥克風 |
| **Roy** | 人臉閉環（face_identity + state/event topic 發布） | ✅ | — | Jetson + D435 |
| **Roy** | FastAPI Gateway 骨架 + WebSocket 端點 | — | ✅ | RTX 8000 server |
| **Roy** | Mock Event Server（假資料 + Demo A 場景腳本） | — | ✅ | 無 |
| **Roy** | Event Schema 凍結（已完成：event-schema.md v1.0） | — | ✅ | 無 |
| **楊** | 手勢辨識方案報告 | — | ✅ | 無 |
| **楊** | 姿勢辨識方案報告 | — | ✅ | 無 |
| **楊** | 手勢/姿勢小 demo（本機 webcam 可跑） | — | ✅ | 本機 webcam |
| **鄔** | PawAI Studio 專案初始化（Next.js scaffold） | — | ✅ | 無 |
| **鄔** | ChatPanel + SkillButtons 元件（接 Mock Server） | — | ✅ | Mock Event Server |
| **黃** | Astro + Starlight 文件站 scaffold | — | ✅ | 無 |
| **黃** | 首頁 + 專案介紹頁 | — | ✅ | 無 |
| **陳** | 架構圖（Draw.io：三層架構 + 資料流） | — | ✅ | 無 |
| **陳** | 環境建置教學文件 | — | ✅ | 無 |

### 1.2 真機依賴分析

| 需要真機的工作 | 設備 | 只有誰能做 |
|---------------|------|-----------|
| 語音管線端到端 | Jetson + Go2 + 麥克風 | Roy |
| 人臉辨識端到端 | Jetson + D435 | Roy |
| Go2 動作驗證 | Go2 + Jetson | Roy |

**其餘所有工作都不需要真機**，遠端用 Mock Event Server 開發。

---

## 2. Deliverable Checklist

### 2.1 Roy — 3/16 交付物

#### D1: 語音閉環

| 驗收項目 | 驗收標準 | 驗證方式 |
|----------|----------|----------|
| Sherpa-onnx KWS 整合 | 喚醒詞觸發成功率 >= 80%（安靜環境） | Jetson 實測 5 次 |
| ASR 轉寫 | faster-whisper CUDA，中文語句辨識可用 | 「你好」「停止」「拍照」各測 3 次 |
| TTS → Go2 播放 | Piper/MeloTTS 合成 → Go2 喇叭播出 | 發 `/tts` topic，Go2 有聲音 |
| 語音狀態發布 | `/state/interaction/speech` 有 JSON 輸出 | `ros2 topic echo` 確認 |
| 語音事件發布 | `/event/speech_intent_recognized` 有 JSON 輸出 | `ros2 topic echo` 確認 |

#### D2: 人臉閉環

| 驗收項目 | 驗收標準 | 驗證方式 |
|----------|----------|----------|
| 狀態發布 | `/state/perception/face` 符合 contract v2.0 schema | `ros2 topic echo` + JSON 欄位檢查 |
| 事件發布 | `/event/face_identity` 四種 event_type 都能觸發 | 走近（track_started）→ 穩定（identity_stable）→ 離開（track_lost） |
| 欄位完整 | `stable_name` / `sim` / `mode` / `face_count` 全部有值 | JSON 檢查 |

#### D3: FastAPI Gateway 骨架

| 驗收項目 | 驗收標準 | 驗證方式 |
|----------|----------|----------|
| REST 端點可用 | `GET /api/brain`、`GET /api/timeline`、`GET /api/health`、`POST /api/command` 回 200 | curl 測試 |
| WebSocket 可連 | `/ws/events` 可建立連線，收到事件推送 | wscat 或瀏覽器 console 測試 |
| CORS 設定 | 前端 `localhost:3000` 可跨域存取 | 瀏覽器 fetch 測試 |

#### D4: Mock Event Server

| 驗收項目 | 驗收標準 | 驗證方式 |
|----------|----------|----------|
| Demo A 場景可重播 | `POST /mock/scenario/demo_a` → WebSocket 收到完整事件序列 | wscat 確認事件順序 |
| 手動觸發可用 | `POST /mock/trigger` 可發射任意事件 | curl + wscat 確認 |
| 與 Gateway 相同介面 | Mock 的 WebSocket / REST 端點路徑與 Gateway 完全一致 | 前端切 URL 即可切換真假資料 |

#### D5: 文件交付

| 文件 | 狀態 | 位置 |
|------|------|------|
| mission/README.md v2.0 | ✅ 已完成 | `docs/mission/README.md` |
| interaction_contract.md v2.0 | ✅ 已完成 | `docs/contracts/interaction_contract.md` |
| Pawai-studio/ 五份設計文件 | ✅ 已完成 | `docs/pawai-brain/studio/` |
| 本交付清單 | ✅ 已完成 | `docs/mission/handoff_316.md` |

---

### 2.2 楊 — 3/16 交付物

#### R1: 手勢辨識方案報告

| 驗收項目 | 驗收標準 |
|----------|----------|
| 技術選型 | 明確選定框架（MediaPipe Hands / 其他），附理由 |
| 手勢清單 | 列出 4/13 Demo 要支援的手勢（建議：wave / stop / point / ok） |
| 延遲評估 | 在本機 webcam 上量測推理延遲，記錄數值 |
| Jetson 可行性 | 評估 Jetson 8GB 記憶體佔用，是否與 face + speech 共存 |
| 交付格式 | Markdown 文件，放 `docs/pawai-brain/perception/gesture/research_report.md` |

#### R2: 姿勢辨識方案報告

| 驗收項目 | 驗收標準 |
|----------|----------|
| 技術選型 | 明確選定框架（MediaPipe Pose / MoveNet / 其他），附理由 |
| 姿勢清單 | 列出 4/13 Demo 要支援的姿勢（建議：standing / sitting / crouching / fallen） |
| 延遲評估 | 在本機 webcam 上量測推理延遲，記錄數值 |
| Jetson 可行性 | 記憶體佔用評估 |
| 交付格式 | Markdown 文件，放 `docs/pawai-brain/perception/pose/research_report.md` |

#### R3: 小 Demo

| 驗收項目 | 驗收標準 |
|----------|----------|
| 可執行 | 本機 webcam 可跑，至少辨識 2 種手勢或姿勢 |
| 輸出格式 | 終端印出 JSON 格式（對齊 `/event/gesture_detected` 或 `/event/pose_detected` schema） |
| 程式碼位置 | `scripts/gesture_demo.py` 或 `scripts/pose_demo.py` |

---

### 2.3 鄔 — 3/16 交付物

#### S1: Next.js 專案初始化

| 驗收項目 | 驗收標準 |
|----------|----------|
| 專案建立 | `pawai-studio/` 目錄下可 `npm run dev` 啟動 |
| 路由架構 | 至少有 `/`（Studio Home）、`/debug`、`/demo` 三個頁面骨架 |
| WebSocket hook | `useWebSocket.ts` 可連接 Mock Server |

#### S2: ChatPanel + SkillButtons

| 驗收項目 | 驗收標準 |
|----------|----------|
| ChatPanel | 可輸入文字 → 送 `POST /api/chat` → 顯示回覆 |
| SkillButtons | 4 個按鈕（Stand / Sit / Wave / Stop）→ 送 `POST /api/command` |
| Mock 連通 | 接 Mock Event Server 可收到假事件並顯示在 chat 區 |

---

### 2.4 黃 — 3/16 交付物

#### W1: Astro + Starlight 文件站

| 驗收項目 | 驗收標準 |
|----------|----------|
| 專案建立 | `docs-site/` 目錄下可 `npm run dev` 啟動 |
| 首頁 | 有 PawAI 專案介紹、功能亮點（文字即可，不需影片） |
| 導覽結構 | sidebar 有：專案介紹 / 架構文件 / 環境建置 / API 參考 |

---

### 2.5 陳 — 3/16 交付物

#### W2: 架構圖

| 驗收項目 | 驗收標準 |
|----------|----------|
| 三層架構圖 | Draw.io，含 Layer 1/2/3 + 節點 + Topic 連線 |
| 資料流圖 | 從感知到執行的完整資料流（face/speech → Executive → Go2） |
| 格式 | `.drawio` 原始檔 + 匯出 PNG，放 `docs/archive/2026-05-docs-reorg/architecture-misc/diagrams/` |

#### W3: 環境建置文件

| 驗收項目 | 驗收標準 |
|----------|----------|
| 開發機設定 | VS Code + SSH 到 Jetson 的步驟 |
| Jetson 環境 | ROS2 Humble + Python 依賴安裝步驟 |
| 前端環境 | Node.js + Next.js + Mock Server 啟動步驟 |
| 交付位置 | `docs/runbook/README.md` 或 Astro 文件站內 |

---

## 3. Handoff Checklist（攻守交換）

### 3.1 Roy → 鄔（前端接手）

3/16 後鄔接手 PawAI Studio 全部前端開發。

| 交接項目 | 內容 | 位置 |
|----------|------|------|
| **Gateway API 文件** | REST + WebSocket 端點規格 | `docs/pawai-brain/studio/specs/system-architecture.md` |
| **Event Schema** | 所有事件/狀態的 TypeScript 型別 | `docs/pawai-brain/studio/specs/event-schema.md` |
| **UI Orchestration** | 面板切換規則 + layout preset | `docs/pawai-brain/studio/specs/ui-orchestration.md` |
| **Mock Server** | 啟動方式 + 端點說明 | `docs/pawai-brain/studio/specs/system-architecture.md` § Mock Event Server |
| **面板元件清單** | 11 個面板的資料來源對應 | `docs/pawai-brain/studio/README.md` § 面板清單 |
| **啟動指令** | Mock Server + Gateway 啟動 | Roy 口頭 + README |

**鄔接手後獨立開發條件**：
- [ ] Mock Server 可啟動，`ws://localhost:8001/ws/events` 有假事件
- [ ] `POST /mock/scenario/demo_a` 可重播完整 Demo A
- [ ] event-schema.md 的 TypeScript 型別可直接 copy 到前端

---

### 3.2 Roy → 楊（手勢姿勢部署）

3/16 後 Roy 負責把楊的研究成果部署到 Jetson。

| 交接項目 | 楊需要交出 | 格式 |
|----------|-----------|------|
| **研究報告** | 技術選型 + 理由 + 延遲數據 + 記憶體評估 | Markdown |
| **Demo 腳本** | 本機 webcam 可跑的 Python script | `.py` |
| **模型檔案** | 如有自訂模型，提供下載連結或檔案 | `.onnx` / `.tflite` |
| **輸出 schema** | 對齊 `/event/gesture_detected` 或 `/event/pose_detected` | JSON 範例 |

**Roy 接手後會做**：
- 包成 ROS2 node（`gesture_perception_node` / `pose_perception_node`）
- 部署到 Jetson + 驗證記憶體共存
- 接入 Interaction Executive

---

### 3.3 Roy → 黃、陳（文件站）

| 交接項目 | 內容 | 位置 |
|----------|------|------|
| **docs/ 全部文件** | mission / architecture / Pawai-studio / 語音 / 人臉 | `docs/` |
| **CLAUDE.md** | 專案背景 + 建構指令 + 架構說明 | 專案根目錄 |
| **架構決策** | 為什麼選這個方案（附錄決策摘要） | `docs/mission/README.md` § 附錄 |

**黃、陳獨立開發條件**：
- [ ] `docs/` 下所有 Markdown 可直接搬進 Astro Starlight
- [ ] CLAUDE.md 的建構指令區塊可直接作為「環境建置」頁面內容
- [ ] 架構圖的原始資料在 `docs/mission/README.md` § 三層架構

---

### 3.4 3/16 後各人主要任務

| 人 | 3/16 → 4/6 | 4/6 → 4/13 |
|----|-------------|-------------|
| **Roy** | Brain Adapter + Qwen3.5-9B 接入 + 手勢姿勢 Jetson 部署 | 端到端整合 + Demo pipeline |
| **鄔** | 全部 Studio 面板（Camera/Face/Speech/Timeline/Brain/Health） | Demo Showcase 頁面 + 最終微調 |
| **楊** | Studio gesture/pose 互動邏輯 + Intent 擴充 | 整合測試 + Demo B 微調 |
| **黃** | 文件站內容填充（架構 / API / 踩坑） | 展示站首頁（Hero 影片 + 功能亮點） |
| **陳** | 架構圖完善 + 環境建置文件完善 | 團隊介紹頁 + 最終校對 |

---

## 4. 風險與應對

| 風險 | 影響 | 應對 |
|------|------|------|
| Roy 3/16 前沒做完 Gateway + Mock | 鄔無法開工 | 最低限度：先交 Mock Server，Gateway 延到 3/18 |
| 楊的手勢方案不可行 | Demo B 受影響 | Demo B 是 P1，不影響 P0；最差只做 wave + stop |
| 鄔/黃/陳不熟悉 ROS2 | 開發效率低 | 不需要懂 ROS2，只需要懂 WebSocket + JSON；Mock Server 隔離了 ROS2 |
| 真機測試時間不夠 | 整合風險 | 3/16 前 Roy 每天至少跑一次端到端測試 |

---

*最後更新：2026-03-13*
*維護者：System Architect*
