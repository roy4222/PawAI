# Roy（盧柏宇）— 個人工作路線圖

> System Architect / Integration Owner
> 其他四人做完功能測試+填映射表+前端頁面後，由 Roy 整合到 Jetson + Go2 上。

---

## 時程總覽

| 階段 | 日期 | 重點 |
|------|------|------|
| **文件衝刺** | 4/9 – 4/13 | PAI Docs 網站骨架 + 專題文件最後修訂（46→60+ 頁） |
| **整合衝刺** | 4/14 – 5/11 | 四人映射表整合 + LiDAR 導航（若採購）+ Studio 全功能串接 |
| **Demo 準備** | 5/12 – 5/18 | 整合測試 + 場景排練 + 實地預演 |

---

## Phase 1：文件衝刺（4/9 – 4/13）

### PAI Docs 介紹網站

| 項目 | 說明 | deadline |
|------|------|:--------:|
| Astro + Starlight 骨架建立 | 框架初始化 + 左側導航結構 + 首頁 | **4/12** |
| 網域設定 | `pawai.docs.roy422.dev` 固定好 | **4/12** |
| 部署 | GitHub Pages，僅靜態文件 | **4/12** |
| 基本內容填充 | Claude Code 讀 GitHub 專案資料自動生成 | **4/13** |
| 交接 | 開好空白結構後，其他組員透過 PR 補內容 | **4/13 後** |

**技術決策**：
- 框架：Astro + Starlight（Roy 部落格同款）
- 網域：`pawai.docs.roy422.dev`
- 部署：GitHub Pages
- 內容來源：黃旭 Notion + GitHub 專案文件 + Claude Code 生成

### 專題文件最後修訂

| 項目 | 說明 | deadline |
|------|------|:--------:|
| 背景知識擴寫 | MediaPipe / YuNet / YOLO / Qwen / ROS2 技術介紹（10-15 頁） | **4/13** |
| 系統限制章節 | Go2 Pro 硬體限制 / LiDAR / 供電 / 開發困難（5-10 頁） | **4/13** |
| 先前失敗嘗試 | YOLOWorld / MeloTTS / 本地 Whisper / D435 避障（5 頁） | **4/13** |
| 導航功能寫入 | **先賭有 LiDAR**，文件中寫入導航方案（4/13 後不可改） | **4/13** |
| 各組員章節審查 | Ch1-5 內容校對 + 錯誤修正 | **4/13** |

> **4/13（週日）繳交**：交檔案非連結，繳交後無法修改。目標 60+ 頁。

---

## Phase 2：整合衝刺（4/14 – 5/11）

### 四人映射表整合（收到映射表後 1-2 天內完成）

| 功能 | 負責人 | 整合到哪裡 | 工作量 |
|------|--------|-----------|:------:|
| 手勢→動作 | 鄔雨彤 | `event_action_bridge.py` GESTURE_ACTION_MAP | 小 |
| 姿勢→動作 | 楊沛蓁 | `event_action_bridge.py` POSE_ACTION_MAP | 小 |
| 語音 prompt | 陳若恩 | `llm_bridge_node.py` SYSTEM_PROMPT + max_tokens | 中 |
| Plan B 台詞 | 陳若恩 | `llm_bridge_node.py` RuleBrain fallback 擴充 | 中 |
| 物體白名單 | 黃旭 | `object_perception_node.py` class_whitelist + `state_machine.py` TTS | 小 |

### 人臉辨識改善（Roy 自己做）

| 項目 | 說明 |
|------|------|
| greeting 冷卻時間 | 同一人不重複觸發（cooldown 60s 已有，需調整或加 UI 顯示） |
| 多人問題 | track 抖動修復（目標 ≤5 tracks/5min） |
| face_db 擴充 | Demo 可能需要加更多人臉 |
| 光線/幻覺 | 評估是否需要 detection threshold 調整 |

### 導航避障 — 外接 LiDAR（若採購）

| 日期 | 動作 |
|------|------|
| **4/14** | **定案**：學校有舊 LiDAR or 採購 A2M12 |
| 到貨 Day 1 | USB 連接 + `rplidar_ros2` driver 驗證 + `/scan` Hz 確認 |
| Day 2-3 | `slam_toolbox` 建圖 + 參數調整（async, resolution 0.15） |
| Day 4-5 | Nav2 導航 + 防撞測試 |
| Day 6+ | 整合進 Executive + Demo 場景（直線短距移動） |

**目標**：辨識到人後直線走 2-3 步靠近，不做複雜路徑。
**SLAM 配置**：online_async + resolution 0.15 + Nav2 composition + swap 4-8GB。
**CPU 管理**：導航場景暫關 Gesture Recognizer。
**可行性研究**：`docs/導航避障/research/2026-04-08-external-lidar-feasibility.md`

### PawAI Studio 整合

| 項目 | 說明 |
|------|------|
| 四人 Studio PR 審查+合併 | gesture / pose / object 頁面 |
| Chat 品質改善 | 陳若恩改好 prompt 後整合，放寬回答長度 |
| Plan B 模式 UI | 連線狀態燈號 + 自動切換 |
| Live View 優化 | 已通過但可能需微調 |
| 動作按鈕擴充 | 把新的手勢/姿勢映射加入 Skills 控制台 |

---

## Phase 3：Demo 準備（5/12 – 5/18）

| 項目 | 說明 | deadline |
|------|------|:--------:|
| 全功能整合測試 | 人臉+語音+手勢+姿勢+物體+（導航）同跑 | 5/12 |
| Demo 場景排練 | 完整流程 3 輪驗收 | 5/14 |
| **教室實地預演** | 老師建議 Demo 前一週到教室測試 | **5/11 前** |
| Plan B 演練 | GPU 斷線切換 + 錄影備份 | 5/15 |
| **省夜 Demo** | 省級評審 | **5/16** |
| **正式展示** | 最終發表 | **5/18** |
| 口頭報告 | 答辯 | 6 月 |

---

## 風險追蹤

| 風險 | 嚴重度 | 狀態 | 應對 |
|------|:------:|:----:|------|
| Jetson 斷電（XL4015） | 🔴 | 未解 | Demo 減少同時功能 / 固定電源（失去機動性） |
| GPU 雲端斷線 | 🔴 | 未解 | Plan B 固定台詞 + 錄影佐證 |
| LiDAR 來不及整合 | 🟡 | 評估中 | Demo 不移動（尷尬但安全） |
| 組員映射表延遲 | 🟡 | — | 4/13 deadline，逾期 Roy 代填 |
| 文件頁數不足 | 🟡 | 46/60+ | Claude Code 擴寫 |

---

## 參考文件

| 文件 | 說明 |
|------|------|
| `docs/mission/README.md` | 專案入口頁 v2.3 |
| `docs/導航避障/research/2026-04-08-external-lidar-feasibility.md` | LiDAR 可行性研究 |
| `pawai-studio/docs/0410assignments/README.md` | 四人分工概覽 |
| `references/project-status.md` | 每日狀態 |
