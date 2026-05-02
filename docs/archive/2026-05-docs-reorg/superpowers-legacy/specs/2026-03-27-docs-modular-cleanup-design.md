# Docs 模組化整理設計規格

**日期**：2026-03-27
**狀態**：APPROVED（含 user feedback 修正）

---

## 目標

每個模組資料夾根目錄只留 3 個入口檔案，其他一律收進子資料夾。打開根目錄就知道模組全貌。

## 根目錄結構規範

```
docs/模組名/
├── README.md      ← 當前真相（50-80 行）
├── CLAUDE.md      ← Claude Code 工作規則
├── AGENT.md       ← 介面契約 + 接手摘要
├── research/      ← 選型研究、benchmark、技術分析
├── archive/       ← 除錯日記、舊方案、歷史版本
└── specs/         ← 設計規格（如有）
```

## README.md 固定模板

```markdown
# 模組名稱

> Status: current / frozen / superseded

> 一句話用途

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | Demo ready / 整合通過 / 開發中 / 空殼 |
| 版本/決策 | 例：YuNet 2023mar + SFace |
| 完成度 | XX% |
| 最後驗證 | YYYY-MM-DD |
| 入口檔案 | `package/package/node.py` |
| 測試 | `python3 -m pytest package/test/ -v` |

## 啟動方式
（3-5 行）

## 核心流程
（10-15 行，只寫真正會跑的資料流）

## 輸入/輸出
（ROS2 topics 表格）

## 已知問題
（3-5 條，只列現在還存在的）

## 下一步
（Sprint 期間要做什麼）

## 子資料夾
| 資料夾 | 內容 |
|--------|------|
| research/ | ... |
| archive/ | ... |
```

**規則**：README 只回答「這是什麼、現在怎樣、怎麼跑、卡在哪」。不回答「我們當初研究過什麼」。

## CLAUDE.md 雙層策略

- `docs/模組/CLAUDE.md` = 模組規則真相來源（人類和其他 agent 也看得到）
- `.claude/rules/*.md` = 薄載入橋接，只保留 path matcher + 關鍵摘要 + 指向模組 CLAUDE.md

## AGENT.md 內容

- 輸入/輸出 topic + JSON schema
- 依賴哪些模組
- 事件流方向（上游→本模組→下游）
- 上下游耦合點
- 接手時先確認什麼

---

## 9 個資料夾具體搬移方案

### 1. 導航避障（最亂，優先處理）

**現況**：7 檔案 + 開源專案/，README 是 3/3 舊 LiDAR 方案 + 3/27 補丁

| 檔案 | 動作 |
|------|------|
| README.MD | **重寫**為 D435 反應式避障的 50-80 行版本，改名 README.md |
| 2026-03-25-reactive-obstacle-avoidance.md | → `research/` |
| 深度攝影機避障.md | → `research/` |
| Go2_低頻感測與BurstGap_研究綜整.md | → `research/`（LiDAR 棄用的證據鏈） |
| 開源專案/ | → `research/open-source-adoption/` |
| 落地計畫_v2.md | → `archive/`（基於已棄用的 LiDAR 方案） |
| weekly_plan.md | → `archive/` |
| 明日報告簡報.md | 刪除 |

**從 docs/archive/ 回收**：
- `archive/refactor/slam-nav2.md` → `research/`（SLAM 路線圖，⭐⭐⭐）
- `archive/logs/2026/01/2026-01-12-dev.md` → `research/`（Go2 LiDAR 頻率根因分析，⭐⭐⭐）
- `archive/testing/reports/slam-phase1_5_test_results.md` → `research/`（SLAM 驗收）

### 2. 人臉辨識

**現況**：README 混歷史除錯 + 2 個過時檔案

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 砍掉 3/8 除錯日記，只留現況 + 架構 + topics |
| 分工.md | → `archive/`（3/8 的初階開發者分工指南，已無人使用） |
| 待研究模型與方向.md | → `research/`（選型研究，YuNet+SFace 已選定但研究過程有價值） |

### 3. 語音功能

**現況**：README 混歷史 + 73K 巨型測試記錄

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 精簡到 50-80 行 |
| jetson-MVP測試.md | → `archive/`（73K，3/15 的 MVP 測試完整記錄） |
| 2026-03-24-speech-pipeline-report.md | → `research/`（pipeline 分析有價值） |

**從 docs/archive/ 回收**：
- `archive/logs/2025/12/2025-12-23-dev.md` → `research/`（語音系統完整驗證，⭐⭐⭐）

### 4. Pawai-studio

**現況**：README + 4 個設計文件散落

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 精簡到 50-80 行 |
| brain-adapter.md | → `specs/` |
| event-schema.md | → `specs/` |
| system-architecture.md | → `specs/` |
| ui-orchestration.md | → `specs/` |

### 5. 辨識物體

**現況**：README + feasibility 研究

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 精簡到 50-80 行 |
| 2026-03-25-object-detection-feasibility.md | → `research/` |

### 6. architecture

**現況**：索引 README + contract + 3 設計文件 + 1 SUPERSEDED

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 更新文件清單，移除 SUPERSEDED 引用 |
| interaction_contract.md | 保留原位（凍結文件） |
| clean_architecture.md | 保留原位 |
| data_flow.md | 保留原位 |
| face_perception.md | → `archive/`（標示 SUPERSEDED） |
| proposals/ | 保留原位 |

### 7. mission

**現況**：大致健康，微調

| 檔案 | 動作 |
|------|------|
| README.md | 保留（已是真相來源） |
| sprint-b-prime.md | 保留 |
| handoff_316.md | 保留 |
| meeting_notes_supplement.md | → `archive/`（3/8 會議補充，已過時） |

### 8. 手勢辨識

**現況**：README 1 份但 36K 太長

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 精簡到 50-80 行，選型過程和 benchmark 比較段落 → `research/選型過程.md` |

### 9. 姿勢辨識

**現況**：README 1 份但 32K 太長

| 檔案 | 動作 |
|------|------|
| README.md | **重寫** — 精簡到 50-80 行，選型過程和 benchmark 段落 → `research/選型過程.md` |

---

## docs/archive/ 精華回收

從 `docs/archive/` 回收到各模組 `research/`：

| 來源 | 目標模組 | 價值 |
|------|---------|:----:|
| `archive/2026-02-11-restructure/guides/go2_sdk/go2_ros2_sdk_architecture.md` | go2-robot-sdk（新建 docs 目錄或留 archive 加索引） | ⭐⭐⭐⭐ |
| `archive/refactor/slam-nav2.md` | 導航避障/research/ | ⭐⭐⭐ |
| `archive/logs/2026/01/2026-01-12-dev.md` | 導航避障/research/ | ⭐⭐⭐ |
| `archive/logs/2025/12/2025-12-23-dev.md` | 語音功能/research/ | ⭐⭐⭐ |
| `archive/testing/reports/slam-phase1_5_test_results.md` | 導航避障/research/ | ⭐⭐⭐ |
| `archive/2026-02-11-restructure/guides/cyclonedds_guide.md` | setup/ 或 architecture/ | ⭐⭐⭐ |

**其餘 archive 內容**：不搬動，保持現狀加 ARCHIVED 標記。

---

## 連帶更新

### project-onboard skill

`/.claude/skills/project-onboard/SKILL.md` 中的權威文件索引表（9 行）+ 7 個 reference 文件中的 33 處 docs 路徑需同步更新。

### .claude/rules/

現有 7 個 rules 檔案改為薄載入器，內容指向模組內 CLAUDE.md：

```markdown
---
paths:
  - "face_perception/**"
  - "docs/人臉辨識/**"
---
# face_perception 規則
詳見 `docs/人臉辨識/CLAUDE.md`（模組內規則真相來源）
## 快速提醒
- 模型路徑 /home/jetson/face_models/
- OpenCV 4.5.4 限制
- QoS BEST_EFFORT
```

### CLAUDE.md（根目錄）

確認引用的 docs 路徑仍然正確（README 位置不變，只是內容重寫）。

---

## 執行順序

一個模組一個 commit，最複雜先做：

1. 導航避障（7 檔案 + archive 回收）
2. 人臉辨識（3 檔案 + README 重寫）
3. 語音功能（3 檔案 + 73K archive）
4. Pawai-studio（5 檔案 → specs/）
5. 辨識物體
6. architecture
7. mission
8. 手勢辨識（README 瘦身 36K → 50-80 行）
9. 姿勢辨識（README 瘦身 32K → 50-80 行）
10. 更新 project-onboard skill + references
11. 瘦化 .claude/rules/ 為薄載入器

每完成一個模組就 commit，不要攢到最後。
