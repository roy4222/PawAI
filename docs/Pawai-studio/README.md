> **開發者請直接看 [pawai-studio/README.md](../../pawai-studio/README.md)**
> 本目錄是正式設計規格庫，非日常開發入口。

---

# PawAI Studio 設計文件

**文件版本**：v2.1
**最後更新**：2026-03-16
**對齊來源**：[mission/README.md](../mission/README.md) v2.0

---

## 一句話定位

> PawAI Studio 是一個以 chat 為主入口、可動態展開 Foxglove 式觀測與控制面板的 embodied AI studio。

**不是**聊天機器人前端。**是**整個 PawAI 系統的統一操作與展示入口。

---

## 核心目標

| 目標 | 說明 |
|------|------|
| **統一入口** | 文字 / 語音輸入 → 統一 interaction_intent 事件 |
| **即時觀測** | D435 影像、人臉辨識、語音狀態、大腦決策全部即時同步 |
| **技能控制** | Stand / Sit / Wave / Stop 一鍵觸發 |
| **事件溯源** | Event Timeline 完整記錄每一筆感知、決策、執行事件 |
| **展示導向** | Demo Showcase 頁面，一鍵跑完 Demo A/B/C 流程 |
| **無硬體開發** | Mock Event Server 讓前端團隊不用等真機就能開發 |

---

## 面板清單

| 面板 | 元件名 | 資料來源 | 說明 |
|------|--------|----------|------|
| 對話 | `ChatPanel` | WebSocket ↔ Gateway | 文字/語音輸入主入口 |
| 即時影像 | `CameraPanel` | MJPEG / WebRTC | D435 RGB + 人臉框 overlay |
| 人臉辨識 | `FacePanel` | `/state/perception/face` | stable_name、sim、distance、mode |
| 語音狀態 | `SpeechPanel` | `/state/interaction/speech` | ASR 轉寫、Intent、對話歷史 |
| 手勢 | `GesturePanel` | `/event/gesture_detected` | 手勢即時顯示（P1） |
| 姿勢 | `PosePanel` | `/event/pose_detected` | 姿勢狀態 + 骨架渲染（P1） |
| 事件時間軸 | `TimelinePanel` | Event Bus (Redis Streams) | 全部事件流，可篩選、可捲動 |
| 系統健康 | `SystemHealthPanel` | `/state/system/health` | Jetson CPU/GPU/RAM、模組狀態、延遲 |
| 大腦決策 | `BrainPanel` | `/state/executive/brain` | current intent / selected skill / trace |
| 技能按鈕 | `SkillButtons` | → `POST /api/command` → Gateway → `/webrtc_req` | Stand / Sit / Wave / Stop |
| Demo 頁 | `DemoShowcase` | 複合 | 完整 Demo 流程展示 |

---

## 頁面類型

| 頁面 | 用途 | 主要面板 |
|------|------|----------|
| **Studio Home** | 主操作頁 | Chat + Live View + Brain State + Timeline |
| **Debug Console** | 開發測試 | Topics Inspector + State Monitor + Manual Trigger |
| **Demo Showcase** | 評審展示 | 簡化版，強調故事線與互動流程 |

---

## 技術棧

| 層級 | 技術 | 說明 |
|------|------|------|
| Frontend | React-based（暫定 Next.js） | 待正式確認 |
| 即時通訊 | WebSocket | Gateway → Frontend 雙向推送 |
| Backend | FastAPI + WebSocket | Studio Gateway |
| Event Bus | Redis (Pub/Sub + KV + Streams) | 事件總線 |
| ROS2 橋接 | ros2_bridge_node | ROS2 Topics → Redis |
| Mock | Mock Event Server (FastAPI) | 假資料生成，前端開發用 |

---

## 前端開發入口（2026-03-16 新增）

**一鍵啟動**：`bash pawai-studio/start.sh`

**每人獨立開發頁面**：

| 負責人 | URL | Spec |
|--------|-----|------|
| 鄔 | `/studio/face` | `pawai-studio/docs/face-panel-spec.md` |
| 陳 | `/studio/speech` | `pawai-studio/docs/speech-panel-spec.md` |
| 黃 | `/studio/gesture` | `pawai-studio/docs/gesture-panel-spec.md` |
| 楊 | `/studio/pose` | `pawai-studio/docs/pose-panel-spec.md` |
| 全部整合 | `/studio` | — |

**測試劇本**：`pawai-studio/docs/testing-playbook.md`
**交接設計**：`docs/superpowers/specs/2026-03-16-studio-handoff-design.md`
**Placeholder 圖**：`pawai-studio/frontend/public/mock/*.svg`（前端自行嵌入）

---

## 與系統的關係

```
PawAI Studio Frontend (Next.js)
        ↑↓ WebSocket / HTTP
Studio Gateway (FastAPI, RTX 8000 server)
        ↑↓ Redis Event Bus
ros2_bridge_node (Jetson)
        ↑↓ ROS2 Topics
Interaction Executive + Perception Modules (Jetson)
        ↑↓ WebRTC DataChannel
Go2 Pro (運動 + 音訊)
```

---

## 延伸文件

| 文件 | 說明 |
|------|------|
| [system-architecture.md](./system-architecture.md) | 快/慢系統架構、Gateway 設計 |
| [event-schema.md](./event-schema.md) | event / state / command / panel schema |
| [ui-orchestration.md](./ui-orchestration.md) | 動態面板策略與 layout 規則 |
| [brain-adapter.md](./brain-adapter.md) | LLM 統一介面（Brain Adapter） |

---

## Demo 驗收標準

| Demo | 名稱 | 成功率 |
|:----:|------|:------:|
| A | 主線閉環（人出現→辨識→對話→回應→Studio 同步） | >= 90% |
| B | 視覺互動（手勢/姿勢 + 動作，P1） | >= 70% |
| C | Studio 展示（一鍵 Demo + 面板 + 事件流） | >= 90% |

**Studio 特定要求**：狀態延遲 < 300ms、面板切換 < 100ms。

---

## 開發時程（3/26 會議更新）

| 時段 | 任務 |
|------|------|
| 至 3/26 | 前端頁面開發（已截止） |
| **4/9 後** | **Studio Backend 開發啟動**（FastAPI Gateway + WebSocket bridge） |
| 4/13 前 | Backend MVP：至少基本使用者登入 + 互動資料記錄 |
| 5/16 前 | Demo C 完整度：Chat + Live View + Event Timeline |

> 後端工作排在功能穩定後再分工，預計 4/9 開會後啟動。資料庫部分 Roy 負責。

---

*最後更新：2026-03-26*
*維護者：System Architect*
*狀態：v2.1（+3/26 後端時程）*
