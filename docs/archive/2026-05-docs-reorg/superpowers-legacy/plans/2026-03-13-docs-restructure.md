# Docs 完整重構實作計畫

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重構 docs/ 結構，消除幽靈文件，建立文件治理規則，確保所有文件與程式碼正相關。

**Architecture:** 四步主幹文件改動（根 README → docs/README → architecture/README → CLAUDE.md），加上標記步驟處理歷史文件。每步獨立可暫停，Step 4 依賴前三步。

**Spec:** `docs/superpowers/specs/2026-03-13-docs-restructure-design.md`

---

## Chunk 1: 主幹入口重寫

### Task 1: 根目錄 README.md → 純入口頁

**Files:**
- Modify: `README.md` (全文重寫，從 540 行砍到 ~40 行)

**目標**：讓第一次進 repo 的人 30 秒內知道「這是什麼」+「去哪看」。

- [ ] **Step 1: 備份確認**

Run: `wc -l README.md`
Expected: ~540 行（確認是當前的 mission 複製版）

- [ ] **Step 2: 重寫根 README.md**

完整內容如下：

```markdown
# PawAI — 老人與狗

> 以 Unitree Go2 Pro 為載體的 embodied AI 互動平台。
> 核心是「人臉辨識 + 中文語音互動 + AI 大腦決策」。

**硬底線**：2026/4/13 展示

完整專案說明請見 [`docs/mission/README.md`](docs/mission/README.md)。

---

## 文件入口

| 文件 | 說明 |
|------|------|
| [`docs/mission/README.md`](docs/mission/README.md) | 專案方向、功能閉環、分工、Demo 定義 |
| [`docs/architecture/README.md`](docs/architecture/README.md) | 技術契約、資料流、Clean Architecture |
| [`docs/Pawai-studio/README.md`](docs/Pawai-studio/README.md) | Studio / Gateway / Brain / Frontend |
| [`docs/setup/README.md`](docs/setup/README.md) | 環境建置、Jetson 設定、操作手冊 |

---

## Quick Start

```bash
# Jetson 上建構
source /opt/ros/humble/setup.zsh
colcon build
source install/setup.zsh

# 啟動 Go2 驅動（最小模式）
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

詳細環境建置見 [`docs/setup/README.md`](docs/setup/README.md)。
```

- [ ] **Step 3: 驗證**

Run: `wc -l README.md`
Expected: ~35-40 行

Run: 目視確認 4 個連結路徑正確（docs/mission/README.md、docs/architecture/README.md、docs/Pawai-studio/README.md、docs/setup/README.md）

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: 砍薄根目錄 README 為純入口頁

540 行 mission 複製版 → 40 行純入口。
專案說明導向 docs/mission/README.md，
環境建置導向 docs/setup/README.md。"
```

---

### Task 2: docs/README.md → 二級導航

**Files:**
- Modify: `docs/README.md` (全文重寫，從 ~80 行重寫為 ~80 行但內容更精準)

**目標**：docs 內的導航頁，只列有效文件，底部附精簡版治理規則。

- [ ] **Step 1: 重寫 docs/README.md**

完整內容如下：

```markdown
# PawAI 文件中心

**專案**：老人與狗 (Elder and Dog) / PawAI

> 新成員先看 mission，再看 architecture，再看 Pawai-studio。

---

## 主幹文件

| 文件 | 說明 |
|------|------|
| [mission/README.md](./mission/README.md) | **專案真相來源** — 功能閉環、P0/P1/P2、Demo、分工、降級策略 |
| [mission/handoff_316.md](./mission/handoff_316.md) | **3/16 分工交付清單** — 誰做什麼、驗收標準、攻守交換 |
| [architecture/interaction_contract.md](./architecture/interaction_contract.md) | **技術契約** — ROS2 Topic schema、節點參數、QoS |
| [architecture/README.md](./architecture/README.md) | 架構文件導航 |
| [Pawai-studio/README.md](./Pawai-studio/README.md) | **PawAI Studio** — system-architecture / event-schema / ui-orchestration / brain-adapter |

---

## 功能模組

| 模組 | 文件 | 優先級 |
|------|------|:------:|
| 人臉辨識 | [人臉辨識/README.md](./人臉辨識/README.md) | P0 |
| 語音功能 | [語音功能/README.md](./語音功能/README.md)、[jetson-MVP測試.md](./語音功能/jetson-MVP測試.md) | P0 |
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

## 文件治理規則

### 目標目錄結構

```
docs/
├── mission/          # 專案方向、決策、分工
├── architecture/     # 技術契約、資料流、分層原則
├── Pawai-studio/     # Studio / Gateway / Brain / Frontend
├── modules/          # 功能模組文件（規劃中）
├── setup/            # 環境、部署、操作手冊
├── archive/          # 歸檔區（不列入主導航）
└── assets/           # 文件媒體資產
```

### 衝突仲裁

- 專案方向、P0/P1/P2、分工、Demo → 以 `mission/` 為準
- ROS2 介面、schema、QoS、跨模組契約 → 以 `architecture/` 為準
- Studio / Gateway / Brain / Frontend → 以 `Pawai-studio/` 為準
- 模組內部設計 → 以各模組 README 為準
- 安裝、部署、操作步驟 → 以 `setup/` 為準

完整治理規則見 [設計規格](./superpowers/specs/2026-03-13-docs-restructure-design.md)。

---

*維護者：System Architect*
```

- [ ] **Step 2: 驗證**

Run: `wc -l docs/README.md`
Expected: ~75-85 行

目視確認：
- 沒有「歷史與研究」區塊
- 沒有「僅供參考」措辭
- archive 不出現在主導航
- 治理規則區塊 ≤ 20 行

- [ ] **Step 3: Commit**

```bash
git add docs/README.md
git commit -m "docs: 重寫 docs/README.md 為二級導航

移除歷史與研究區塊、模糊措辭。
新增文件治理規則專區（目錄結構 + 衝突仲裁）。"
```

---

### Task 3: architecture/README.md → 純導航頁

**Files:**
- Modify: `docs/architecture/README.md` (從 200 行砍到 ≤50 行)

**目標**：不再重複 mission 的架構圖，只做文件導航。

- [ ] **Step 1: 重寫 architecture/README.md**

完整內容如下：

```markdown
# PawAI 架構文件

本目錄管技術契約、架構原則、資料流。專案方向見 [mission/README.md](../mission/README.md)，Studio 設計見 [Pawai-studio/README.md](../Pawai-studio/README.md)。

---

## 文件清單

| 文件 | 說明 | 狀態 |
|------|------|------|
| [interaction_contract.md](./interaction_contract.md) | ROS2 介面契約 v2.0 — Topic/Action/schema/QoS | **凍結** |
| [clean_architecture.md](./clean_architecture.md) | Clean Architecture 分層原則（Layer 2 模組適用） | 有效 |
| [data_flow.md](./data_flow.md) | 系統資料流圖 | 有效（部分節點名稱待對齊） |
| [face_perception.md](./face_perception.md) | ~~歷史人臉模組設計~~ — 已被 `interaction_contract.md` 與 [人臉辨識/README.md](../人臉辨識/README.md) 取代 | SUPERSEDED |

---

## 閱讀建議

- **整合者**：先看 `interaction_contract.md`，再看 `data_flow.md`
- **新模組開發者**：先看 `clean_architecture.md`，再看 `interaction_contract.md`
- **前端/Studio 開發者**：直接看 [Pawai-studio/](../Pawai-studio/README.md)，此目錄非必讀

---

## 邊界

本目錄只管技術契約與架構原則。專案方向與分工見 `mission/`，Studio 設計見 `Pawai-studio/`，安裝部署見 `setup/`。

---

*維護者：System Architect*
*最後更新：2026-03-13*
```

- [ ] **Step 2: 驗證**

Run: `wc -l docs/architecture/README.md`
Expected: ≤ 35 行

目視確認：
- 無三層架構圖
- 無模組現況表
- 無專案結構樹
- `face_perception.md` 標為 SUPERSEDED

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/README.md
git commit -m "docs: 砍薄 architecture/README.md 為純導航頁

200 行 → 35 行。移除重複的三層架構圖、模組列表。
face_perception.md 標為 SUPERSEDED。"
```

---

## Chunk 2: CLAUDE.md 瘦身 + 標記

### Task 4: CLAUDE.md → 操作速查卡 + 引用

**Files:**
- Modify: `CLAUDE.md` (從 ~304 行精簡，移除完整規格表，改引用)

**目標**：保留操作型高價值內容，正式規格全部改引用連結。

**重要**：以下 Step 1-4 按 heading 文字定位（`## 三層系統架構`、`## ROS2 套件與節點` 等），不依賴行號。每個 heading 從該行到下一個 `## ` 或 `---` 之間的內容全部替換。建議從檔案底部往上編輯，避免行號偏移問題。

- [ ] **Step 1: 精簡專案概述區塊**

找到 `## 專案概述` heading，將整個區塊（包含優先序表和硬體配置表）替換為：

```markdown
## 專案概述

**專題名稱：老人與狗 / PawAI**
**硬底線：2026/4/13 展示**
**當前日期：2026-03-13（Phase 1 基礎建設期尾端）**

以 Unitree Go2 Pro 為載體的 **embodied AI 互動陪伴平台**。核心是「人臉辨識 + 中文語音互動 + AI 大腦決策」，不是導航或尋物。

> 完整專案定位、P0/P1/P2、硬體配置見 [`docs/mission/README.md`](docs/mission/README.md)
```

- [ ] **Step 2: 精簡三層系統架構區塊**

找到 `## 三層系統架構` heading，替換為：

```markdown
## 三層系統架構

> 詳見 [`docs/mission/README.md`](docs/mission/README.md) §5

Layer 3（中控）→ Layer 2（感知）→ Layer 1（驅動/硬體）。事件驅動、單一控制權。
```

- [ ] **Step 3: 精簡 ROS2 套件與節點區塊**

找到 `## ROS2 套件與節點` heading，替換為：

```markdown
## ROS2 套件與節點

> 完整節點清單與參數見 [`docs/architecture/contracts/interaction_contract.md`](docs/architecture/contracts/interaction_contract.md)

**核心套件速查**：
- `go2_robot_sdk` — Go2 驅動，Clean Architecture 分層，WebRTC DataChannel 通訊
- `speech_processor` — 語音模組（stt_intent_node / tts_node / intent_tts_bridge_node）
- `go2_interfaces` — 自訂 ROS2 訊息（`WebRtcReq.msg`）

**WebRTC 音訊播放速查**（完整表見 interaction_contract.md）：
- `4001` 開始播放 → `4003` 音訊資料塊 → `4002` 停止播放
```

- [ ] **Step 4: 精簡關鍵 ROS2 Topic 區塊**

找到 `## 關鍵 ROS2 Topic` heading，替換為：

```markdown
## 關鍵 ROS2 Topic

> 完整 Topic 列表見 [`docs/architecture/contracts/interaction_contract.md`](docs/architecture/contracts/interaction_contract.md)

**語音主線**：`/event/speech_intent_recognized`（Intent 事件 JSON）
**人臉主線**：`/state/perception/face`（人臉狀態 10Hz JSON）
```

- [ ] **Step 5: 更新關鍵文件索引**

找到 `## 關鍵文件索引` heading，替換為：

```markdown
## 關鍵文件索引

| 領域 | 真相來源 |
|------|---------|
| 專案方向、分工、Demo | [`docs/mission/README.md`](docs/mission/README.md) |
| 3/16 交付清單 | [`docs/mission/handoff_316.md`](docs/mission/handoff_316.md) |
| ROS2 介面契約 | [`docs/architecture/contracts/interaction_contract.md`](docs/architecture/contracts/interaction_contract.md) |
| PawAI Studio 設計 | [`docs/Pawai-studio/README.md`](docs/Pawai-studio/README.md) |
| 語音模組 | [`docs/語音功能/README.md`](docs/語音功能/README.md) |
| 人臉模組 | [`docs/人臉辨識/README.md`](docs/人臉辨識/README.md) |
| 環境建置 | [`docs/setup/README.md`](docs/setup/README.md) |

### 配置檔
- `go2_robot_sdk/config/` — SLAM/Nav2/CycloneDDS/Joystick 參數
- `speech_processor/config/speech_processor.yaml` — 語音模組參數
- `go2_robot_sdk/launch/robot.launch.py` — 主 launch（修改後不需 rebuild）

### 測試腳本
- `scripts/start_asr_tts_no_vad_tmux.sh` — 語音 MVP no-VAD 主線一鍵啟動
- `scripts/start_speech_e2e_tmux.sh` — 端到端語音測試
```

- [ ] **Step 6: 驗證**

Run: `wc -l CLAUDE.md`
Expected: ~200-220 行（從 304 行減少約 80-100 行）

目視確認：
- 無完整 api_id 四行表（只剩速查一行）
- 無完整節點清單六行表（只剩三個核心套件）
- 無完整 Topic 列表（只剩語音 + 人臉各 1 條）
- 關鍵文件索引改為引用表
- 建構/除錯/開發環境/已知陷阱/常見情境 完整保留

- [ ] **Step 7: Commit**

Note: Step 1 (專案概述精簡) 的日期更新已包含在內，不再需要獨立的日期更新步驟。

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md 瘦身為操作速查卡

三層架構改引用 mission、節點清單改引用 contract、
Topic 列表改引用 contract、文件索引改真相來源表。
保留建構指令、除錯指令、已知陷阱、常見情境。"
```

---

### Task 5: mission/README.md §10 文件地圖標記

**Files:**
- Modify: `docs/mission/README.md:535-576` (只改文件地圖區塊，不動主體)

**目標**：標記失效連結，不改主體內容。

- [ ] **Step 1: 在文件地圖區塊加 NOTE**

找到 `docs/mission/README.md` 中的 `### 10.1 文件地圖`（第 537 行），在該標題下方、code fence 之前插入：

```markdown
> **NOTE**：以下文件地圖部分路徑待更新：
> - `architecture/brain_v1.md` — 檔案不存在（幽靈引用，待建立或移除）
> - `logs/` — 為歷史資料，不作主導航依據；後續將移至 `archive/`（此引用在 §10.2 快速連結中）
```

- [ ] **Step 2: 驗證**

Run: 在 `docs/mission/README.md` 搜尋 `NOTE`，確認出現在 `### 10.1 文件地圖` 下方
Expected: 看到新增的 NOTE 區塊

- [ ] **Step 3: Commit**

```bash
git add docs/mission/README.md
git commit -m "docs: 標記 mission/README.md 文件地圖的失效連結

brain_v1.md 為幽靈引用，logs/ 為歷史資料。
只加 NOTE，不改主體內容。"
```

---

### Task 6: architecture/ 現有文件核對

**Files:**
- Read only: `docs/architecture/designs/clean_architecture.md`
- Read only: `docs/architecture/designs/data_flow.md`

**目標**：確認 banner 是否充分揭露目前偏差；若不足，補充具體偏差清單。

- [ ] **Step 1: 核對 clean_architecture.md**

確認事項：
- 第 1 行已有 `⚠️ PARTIALLY OUTDATED` banner ✓
- **已知偏差**：內文適用範圍寫 `face_perception`、`speech_processor`、`gesture_module`，但 `gesture_module` 尚未建立、`face_perception` 的實際分層可能與文件描述不完全一致
- 檢查 `go2_robot_sdk/` 和 `face_perception/` 的實際目錄結構是否符合文件描述的四層
- 在既有 banner 中補充具體偏差清單（哪些模組未落地、哪些分層描述不準確）

- [ ] **Step 2: 核對 data_flow.md**

確認事項：
- 第 1 行已有 `⚠️ OUTDATED` banner ✓
- Banner 目前說「節點名稱未對齊實作」，但實際偏差不只節點名稱——整個資料流路徑可能已與 interaction_contract.md v2.0 有結構性差異
- 比對 `data_flow.md` 的流程圖與 `interaction_contract.md` v2.0 的 Topic 列表，列出具體偏差
- 在 banner 中補充：哪些節點已更名/不存在、哪些 Topic 路徑已變更、整體流程與 v2.0 的差異程度

- [ ] **Step 3: Commit（僅在有改動時）**

```bash
# 只有在有改動時才 commit
git diff --quiet docs/architecture/ || {
  git add docs/architecture/designs/clean_architecture.md docs/architecture/designs/data_flow.md
  git commit -m "docs: 核對 architecture/ 現有文件，補充 NOTE"
}
```

---

## 驗收標準

完成所有 Task 後，整體驗收：

| 驗收項目 | 標準 |
|---------|------|
| 根 README.md | ≤ 45 行，只有入口連結 + quick start |
| docs/README.md | 有主幹/模組/環境/治理四個區塊，無「歷史與研究」 |
| architecture/README.md | ≤ 50 行，純導航，無架構圖 |
| CLAUDE.md | 無完整規格表，有引用連結，保留操作指令 |
| mission/README.md §10 | 有 NOTE 標記 brain_v1.md 和 logs/ |
| architecture/ 現有文件 | banner 與實際程式碼一致 |
| 所有主導航 | archive/ 不出現在任何入口頁 |

---

*計畫建立：2026-03-13*
*對齊規格：`docs/superpowers/specs/2026-03-13-docs-restructure-design.md`*
