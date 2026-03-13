# PawAI 文件中心

**專案**：老人與狗 (Elder and Dog) / PawAI
**最後更新**：2026-03-13

---

## 主幹文件（你該從這裡開始）

| 文件 | 說明 |
|------|------|
| [mission/README.md](./mission/README.md) | **專案總覽 v2.0** — 單一真相來源：功能閉環、本地/雲端拆分、團隊分工 |
| [mission/handoff_316.md](./mission/handoff_316.md) | **3/16 分工交付清單** — 誰做什麼、驗收標準、攻守交換 |
| [architecture/interaction_contract.md](./architecture/interaction_contract.md) | **ROS2 介面契約 v2.0** — Topic schema、節點參數、QoS |
| [Pawai-studio/README.md](./Pawai-studio/README.md) | **PawAI Studio 設計入口** — 含 system-architecture / event-schema / ui-orchestration / brain-adapter |

---

## 閱讀順序

**新成員（黃、陳）**：
1. `mission/README.md` — 專案全貌
2. `mission/handoff_316.md` — 你的交付物
3. `architecture/interaction_contract.md` — 系統接口
4. `Pawai-studio/README.md` — Studio 概覽

**前端開發（鄔）**：
1. `Pawai-studio/README.md` — 面板清單與技術棧
2. `Pawai-studio/event-schema.md` — 事件/狀態/指令 TypeScript 型別
3. `Pawai-studio/ui-orchestration.md` — 面板切換規則

**整合者（Roy）**：
1. `mission/README.md` — 功能閉環與降級策略
2. `architecture/interaction_contract.md` — ROS2 介面規格
3. `Pawai-studio/brain-adapter.md` — LLM 統一介面

---

## 功能模組文件

| 模組 | 文件 | 優先級 |
|------|------|:------:|
| 語音功能 | [語音功能/README.md](./語音功能/README.md)、[jetson-MVP測試.md](./語音功能/jetson-MVP測試.md) | P0 |
| 人臉辨識 | [人臉辨識/README.md](./人臉辨識/README.md) | P0 |
| 手勢辨識 | [手勢辨識/README.md](./手勢辨識/README.md) | P1 |
| 辨識物體 | [辨識物體/README.md](./辨識物體/README.md) | P2 |
| 導航避障 | [導航避障/README.MD](./導航避障/README.MD) | P2 |

---

## 環境與部署

| 文件 | 說明 |
|------|------|
| [setup/README.md](./setup/README.md) | 環境建置總覽 |
| [setup/hardware/](./setup/hardware/) | Jetson 設定、GPU 連接 |
| [setup/software/](./setup/software/) | 基礎操作說明 |

---

## 歷史與研究（僅供參考，不作為主線依據）

以下文件保留歷史脈絡，但**已不反映系統現況**。主線規格以上方主幹文件為準。

| 目錄/文件 | 狀態 | 說明 |
|----------|------|------|
| [mission/vision.md](./mission/vision.md) | OUTDATED | 早期願景，含過時定位與錯誤年份 |
| [mission/roadmap.md](./mission/roadmap.md) | SUPERSEDED | 舊版時程，已被 mission/README.md v2.0 取代 |
| [mission/agentic_embodied_ai_roadmap.md](./mission/agentic_embodied_ai_roadmap.md) | ARCHIVED | 早期大規模技術路線，非 4/13 展示主線 |
| [design/](./design/) | OUTDATED | 舊設計文件，已被 Pawai-studio/ + architecture/ 取代 |
| [refactor/](./refactor/) | ARCHIVED | 早期重構計畫 |
| [logs/](./logs/) | ARCHIVED | 開發日誌（2025/11 ~ 2026/02），不作為主線依據 |
| [archive/](./archive/) | ARCHIVED | 2026-02-11 前舊結構備份 |
| [testing/](./testing/) | ARCHIVED | 早期測試報告（SLAM Phase 1.5 等），新驗收紀錄仍可放入此目錄 |

---

*維護者：System Architect*
*狀態：v5.0（主幹導航版）*
