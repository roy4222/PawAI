# Docs 完整重構設計規格

**建立日期**：2026-03-13
**狀態**：定稿
**目標**：消除幽靈文件、建立文件治理規則、讓所有文件與程式碼正相關

---

## 1. 核心決策摘要

| # | 決策 | 結論 |
|---|------|------|
| 1 | 中文模組資料夾 | D：原地不動，中期收編 `docs/modules/`，傾向保留中文名 |
| 2 | 幽靈文件 | B：逐一審查 → 抽有價值內容進主幹 → 歸檔 `archive/` |
| 3 | `architecture/README.md` | A：砍薄成純導航頁 |
| 4 | 根 README vs docs/README | A：兩層入口，根 README 薄、docs/README 中等 |
| 5 | `CLAUDE.md` | D(B+C)：砍薄成操作速查卡，規格回主幹 + 引用連結 |

---

## 2. 目標目錄樹（Step 0 定稿）

```
docs/
├── README.md              # docs 二級導航 + 文件治理規則
├── CHANGELOG.md           # docs 變更紀錄（保留）
├── mission/               # 專案方向、決策、分工
├── architecture/          # 系統架構、契約、資料流、分層原則
├── Pawai-studio/          # Studio / Gateway / Brain / Frontend
├── modules/               # 功能模組文件（中期建立，現階段為規劃目標）
├── setup/                 # 環境、部署、操作手冊
├── archive/               # 歸檔區
└── assets/                # 文件媒體資產存放區
```

### 現有 → 目標對照表

| 現有一級目錄 | 目標狀態 | 去向 |
|-------------|---------|------|
| `mission/` | **保留** | 原地 |
| `architecture/` | **保留** | README 砍薄 |
| `Pawai-studio/` | **保留** | 原地 |
| `setup/` | **保留** | 原地 |
| `assets/` | **保留** | 原地 |
| `archive/` | **保留** | 接收歸檔文件 |
| `人臉辨識/` | 中期併入 | → `modules/人臉辨識/` |
| `語音功能/` | 中期併入 | → `modules/語音功能/` |
| `手勢辨識/` | 中期併入 | → `modules/手勢辨識/` |
| `導航避障/` | 中期併入 | → `modules/導航避障/` |
| `辨識物體/` | 中期併入 | → `modules/辨識物體/` |
| `design/` | 歸檔 | → `archive/design/`（先審查抽有價值內容） |
| `refactor/` | 歸檔 | → `archive/refactor/` |
| `logs/` | 歸檔 | → `archive/logs/` |
| `testing/` | 歸檔 | → `archive/testing/` |

---

## 3. 各目錄責任邊界

### 治理規則總綱

> **`mission` 定方向，`architecture` 定契約，`Pawai-studio` 定 Studio，`modules` 定模組，`setup` 定操作，`code` 定現況，`CLAUDE.md` 不定規格。**

### 3.1 `mission/`

| 項目 | 定義 |
|------|------|
| **角色** | 專案級真相來源 |
| **能放** | 專案定位、功能閉環、P0/P1/P2、Demo 定義、團隊分工、降級策略、handoff 清單、影響現行決策的會議結論 |
| **不能放** | Topic schema 細節、程式碼層級的實作說明、模組內部設計 |
| **主文件** | `README.md`（真相來源）、`handoff_316.md`（交付清單） |

### 3.2 `architecture/`

| 項目 | 定義 |
|------|------|
| **角色** | 技術契約與架構原則真相來源 |
| **能放** | ROS2 介面契約（Topic/Action/schema/QoS）、Clean Architecture 分層原則、系統資料流、模組間連接方式、本地/雲端部署邊界、runtime ownership |
| **不能放** | 專案方向與分工、Studio UI 設計、模組內部實作細節、安裝/部署操作步驟 |
| **主文件** | `interaction_contract.md`（技術契約）、`README.md`（純導航） |

### 3.3 `Pawai-studio/`

| 項目 | 定義 |
|------|------|
| **角色** | Studio / Gateway / Brain / Frontend 設計真相來源 |
| **能放** | event-schema（**Studio/Gateway 投影層型別**，非 ROS2 topic 契約本體）、system-architecture、ui-orchestration、brain-adapter、面板設計、前端技術棧 |
| **不能放** | ROS2 Topic 正式規格（引用 architecture）、專案分工（引用 mission） |
| **主文件** | `README.md`（Studio 入口） |

### 3.4 `modules/`（中期建立，現階段為規劃目標）

| 項目 | 定義 |
|------|------|
| **角色** | 各功能模組的設計與使用文件 |
| **能放** | 模組 README、啟動方式、I/O 摘要、限制與已知問題、模組專屬驗收/deliverable、與該模組直接相關的研究結論 |
| **不能放** | 跨模組介面規格、專案方向、跨模組研究 |

### 3.5 `setup/`

| 項目 | 定義 |
|------|------|
| **角色** | 環境建置與操作手冊真相來源 |
| **能放** | Jetson 設定、GPU 連接、網路配置、ROS2 安裝、前端環境、操作說明 |
| **不能放** | 架構設計、專案決策、模組設計 |
| **規則** | CLAUDE.md 中重複的操作步驟改為引用此處 |

### 3.6 `archive/`

| 項目 | 定義 |
|------|------|
| **角色** | 歷史文件歸檔區 |
| **能放** | 所有已過時、已被取代、純歷史的文件 |
| **不能放** | 任何現行有效的規格或決策 |
| **組織方式** | 按來源子目錄：`archive/design/`、`archive/refactor/`、`archive/logs/`、`archive/testing/` |
| **規則** | 歸檔後不再維護；**不得出現在任何主導航入口** |

### 3.7 `assets/`

| 項目 | 定義 |
|------|------|
| **角色** | 文件媒體資產存放區 |
| **能放** | `.png`、`.drawio`、`.svg`、`.gif`、影片截圖、錄影縮圖等 |
| **不能放** | Markdown 文件、程式碼 |
| **組織方式** | `assets/diagrams/`（架構圖）、可擴充 `assets/screenshots/` 等 |

### 衝突仲裁規則（依問題類型）

| 問題類型 | 仲裁來源 |
|---------|---------|
| 專案方向、P0/P1/P2、分工、Demo 定義 | `mission/` |
| ROS2 介面、schema、command、QoS、跨模組技術契約 | `architecture/` |
| Studio / Gateway / Brain / Frontend 設計 | `Pawai-studio/`（不得違反 `architecture/`） |
| 模組內部設計與模組專屬操作 | `modules/`（對外介面不得違反 `architecture/`） |
| 安裝、部署、環境與操作步驟 | `setup/` |
| 歷史參考 | `archive/`（**不參與現行仲裁**） |

---

## 4. 主幹文件改動規劃

### Step 1：根目錄 `README.md` → 砍薄成純入口

**保留**：
- 專案一句話定位（從 mission 摘錄，≤3 行）
- 快速連結表（4-5 個連結指向主幹文件）
- 最小可用 quick start（3-5 行指令）
- 詳細環境指向 `docs/setup/README.md`

**刪除**：
- 三層架構圖、硬體配置表、完整 Topic 列表、模組詳細說明、開發環境操作指南

### Step 2：`docs/README.md` → 重寫為二級導航

**保留/新增**：
- 主幹文件區（mission / architecture / Pawai-studio 各一行連結）
- 功能模組區（指向現有中文資料夾，中期改指 modules/）
- 環境部署區（指向 setup/）
- 一句閱讀順序建議（「新成員先看 mission，再看 architecture，再看 Pawai-studio」）
- 底部「文件治理規則」專區（目標目錄樹 + 各目錄一句話責任 + 衝突仲裁 5 條，要短）

**刪除**：
- 整個「歷史與研究」區塊（archive 不出現在主導航）
- 模糊的「僅供參考」措辭

### Step 3：`architecture/README.md` → 砍到 ≤50 行純導航

**保留**：
- 一句話角色說明
- 文件清單表（`interaction_contract.md`、`clean_architecture.md`、`data_flow.md`）
- `face_perception.md` 在表中標為：「歷史人臉模組設計，已被 `interaction_contract.md` 與 `docs/人臉辨識/README.md` 取代」
- 閱讀建議（按角色，3 行以內）
- 邊界聲明

**刪除**：
- 三層架構圖、模組現況表、Clean Architecture 程式碼範例、專案結構樹、資料流示意

### Step 4：`CLAUDE.md` → 砍薄 + 改引用（最後做，依賴前 3 步）

**保留**（操作型高價值）：
- 語言與工具約定
- 專案概述（精簡到 ≤10 行）
- 建構與執行指令
- 常用除錯指令
- 開發環境要點
- 已知陷阱
- 常見開發情境

**改為引用**：
- 三層架構圖 → 「詳見 `docs/mission/README.md` §5」
- 完整 Topic 表 → 「詳見 `docs/architecture/interaction_contract.md`」
- WebRTC api_id 完整表 → 「詳見 `docs/architecture/interaction_contract.md`」
- 完整節點清單 → 「詳見 `docs/architecture/interaction_contract.md`」

**保留摘要**（嚴格限制）：
- 語音主線 1 條 topic 速查
- 人臉主線 1 條 topic 速查
- 1 個最常用 WebRTC 指令範例
- 其餘全部引用，不重複全表

---

## 5. 只標記（這一輪不搬不改內容）

| 對象 | 動作 |
|------|------|
| `architecture/face_perception.md` | 在 `architecture/README.md` 文件表中標歷史 |
| `architecture/clean_architecture.md` | 核對與現行程式碼一致性，必要時補 NOTE |
| `architecture/data_flow.md` | 核對與現行程式碼一致性，必要時補 NOTE |
| 中文模組資料夾（5 個） | 不動，中期收編 `modules/` |

---

## 6. 延後（幽靈文件審查 + 歸檔）

| 優先序 | 對象 | 動作 |
|:------:|------|------|
| 1 | `mission/vision.md` | 審查 → 抽有價值內容 → 歸檔 |
| 2 | `mission/roadmap.md` | 審查 → 抽有價值內容 → 歸檔 |
| 3 | `design/` | 審查 → 歸檔至 `archive/design/` |
| 4 | `refactor/` | 直接歸檔至 `archive/refactor/` |
| 5 | `logs/` | 直接歸檔至 `archive/logs/` |
| 6 | `mission/agentic_embodied_ai_roadmap.md` | 直接歸檔 |
| 7 | `testing/` | 直接歸檔至 `archive/testing/` |
| 8 | `mission/meeting_notes_supplement.md` | 延後審查，決定保留或歸檔 |

---

## 7. 不動清單

| 對象 | 原因 |
|------|------|
| `mission/README.md` | 已確認正確 |
| `mission/handoff_316.md` | 已確認正確 |
| `architecture/interaction_contract.md` | 已確認正確（凍結） |
| `Pawai-studio/*.md` | 已確認正確 |
| `setup/` | 不在這一輪範圍 |
| `assets/` | 不需改動 |
| `CHANGELOG.md` | 保留 |

---

*設計定稿：2026-03-13*
*維護者：System Architect*
