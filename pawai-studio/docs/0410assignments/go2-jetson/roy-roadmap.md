# Roy（盧柏宇）— 個人工作路線圖

> System Architect / Guardian Brain Owner / Integration Owner
> 負責：Guardian Brain 三層架構落地、導航避障、人臉升級、四人成果整合、Demo 排練

---

## 時程總覽

| 階段 | 日期 | 重點 |
|------|------|------|
| **文件衝刺** | 4/10 – 4/13 | 守護犬敘事寫入文件 + PAI Docs 網站骨架 + 專題文件 46→60+ 頁 |
| **Guardian Brain + 導航** | 4/14 – 5/11 | 三層架構落地 + RPLIDAR 整合 + 四人成果整合 + Studio 升級 |
| **Demo 準備** | 5/12 – 5/18 | 三場景排練 + Plan B 演練 + 實地預演 |

---

## Phase 1：文件衝刺（4/10 – 4/13）

### 守護犬敘事落地（4/10 已完成大部分）

| 項目 | 狀態 |
|------|:----:|
| guardian-dog-design spec | ✅ 完成 |
| mission README 更新（§2 定位 + §5 功能總覽） | ✅ 完成 |
| CLAUDE.md 更新 | ✅ 完成 |
| 四人分工文件更新（守護犬場景框架） | ✅ 完成 |
| project-status.md 反映新方向 | 🔄 待做 |

### PAI Docs 介紹網站

| 項目 | 說明 | deadline |
|------|------|:--------:|
| Astro + Starlight 骨架建立 | 框架初始化 + 首頁 | **4/12** |
| 部署 | GitHub Pages，`pawai.docs.roy422.dev` | **4/12** |
| 基本內容填充 | 從 GitHub 專案文件自動生成 | **4/13** |

### 專題文件修訂

| 項目 | 說明 | deadline |
|------|------|:--------:|
| 產品定位改寫 | 「居家守護犬」敘事 + 非 Go2 不可論述 | **4/13** |
| Guardian Brain 章節 | 三層架構、harness design、skill contract | **4/13** |
| 背景知識擴寫 | MediaPipe / YuNet / YOLO / Qwen / ROS2（10-15 頁） | **4/13** |
| 系統限制章節 | Go2 硬體限制 / LiDAR / 供電（5-10 頁） | **4/13** |
| 先前失敗嘗試 | D435 避障 / MeloTTS / 本地 Whisper / 本地 LLM（5 頁） | **4/13** |
| 導航功能寫入 | **先賭有 LiDAR**，寫入無雷達/有雷達雙版架構 | **4/13** |

> **4/13（週日）繳交**：交檔案非連結，繳交後無法修改。目標 60+ 頁。

---

## Phase 2：Guardian Brain + 導航（4/14 – 5/11）

### 2A. Guardian Brain 三層落地（Roy 核心任務）

> 完整設計見 `docs/superpowers/specs/2026-04-10-guardian-dog-design.md`

**執行順序**：

| # | 任務 | 檔案 | 說明 | 預估 |
|---|------|------|------|:----:|
| 1 | Skill Contract 定義 | `llm_contract.py` | 每個 skill 加 preconditions / expected_outcome / fallback + tool schema | 半天 |
| 2 | SkillContract dataclass | `state_machine.py` | EventResult 擴展 + guardian_state 欄位 | 半天 |
| 3 | Pre-action Validation | `interaction_executive_node.py` | `_validate_preconditions()` + `/state/guardian` topic | 1 天 |
| 4 | Policy Override + Memory | `llm_bridge_node.py` | `_policy_override()` + `_guardian_memory` dict + Groq 分支 | 1 天 |
| 5 | Groq API 切換 | `llm_bridge_node.py` | Groq endpoint + function calling（若陳若恩測試結果正面） | 半天 |
| 6 | 陌生人警戒邏輯 | `state_machine.py` | unknown stable ≥ 3s + face_count > 0 + not recently_alerted → ALERT | 半天 |
| 7 | Safety Alert Publisher | `event_action_bridge.py` | `/event/guardian/safety_alert` topic | 2 小時 |
| 8 | **Skill Queue + self_introduce** | `state_machine.py` + `interaction_executive_node.py` | Demo 開場 wow moment：action sequencing | 半天 |

**任務 8 細節（Agent-Generated Self Demo）**：
- 新增 `skill_queue: deque[SkillContract]` 到 state machine
- `self_introduce` meta skill 呼叫時 push 預設 sequence 進 queue
- Executive tick 時若 queue 非空 → 取下一個 skill 執行
- 每個 skill 仍走 `_validate_preconditions()`
- Safety event（stop/emergency/fallen）清空 queue
- guardian_state 新增 `active_sequence: str | None` + `sequence_progress: int`
- Studio 訂閱後可顯示 queue 進度

**驗收標準**：
- `guardian_state` topic 正常發布，Studio 可訂閱
- 熟人辨識 → greeting，陌生人 → alert，兩條路徑都走通
- pre-action validation 能擋住 emergency 狀態下的非 stop 動作
- Groq function calling 能正確選 skill（或 fallback 到 RuleBrain）
- **self_introduce 能跑完 6-step sequence，中途可被 stop 手勢打斷，Studio 顯示 queue 進度**

### 2B. 導航避障 — 外接 LiDAR（若採購）

| 日期 | 動作 |
|------|------|
| **4/14** | **定案**：學校有舊 LiDAR or 採購 RPLIDAR A2M12 |
| 到貨 Day 1 | USB 連接 + `rplidar_ros2` driver + `/scan` Hz 確認 + **odom bag 錄製**（30s） |
| Day 1 驗證 | odom 漂移 > 0.3m/10s → SLAM NO-GO，僅做反應式避障 |
| Day 2-3 | `slam_toolbox` 建圖（若 odom OK）+ `nav2_collision_monitor` 避障 |
| Day 4-5 | 「簡單靠近」整合：人臉距離 > 2m → cmd_vel 前進 → collision_monitor 擋 |
| Day 6+ | 整合進 Executive：APPROACH state + skill contract |

**目標**：
- **最低限度**：360° 反應式避障（即使 SLAM 失敗也值得）
- **理想**：辨識到人 → 前進 1-2m → 停在安全距離
- **不承諾**：全屋巡邏、多房間導航

### 2C. 人臉辨識改善

| 項目 | 說明 | 優先 |
|------|------|:----:|
| 陌生人警戒邏輯 | unknown stable ≥ 3s → ALERT（含 anti-false-positive） | **P0** |
| greeting 冷卻調整 | 同一人 5-10 分鐘內不重複觸發 | **P0** |
| face_db 擴充 | Demo 需要加評審/組員的臉 | P1 |
| track 抖動修復 | 目標 ≤5 tracks/5min（目前 45/2min） | P1 |

### 2D. 四人成果整合

| 功能 | 負責人 | 整合到哪裡 | 預估 |
|------|--------|-----------|:----:|
| 手勢映射 | 鄔雨彤 | `event_action_bridge.py` GESTURE_ACTION_MAP | 2 小時 |
| 姿勢映射 | 楊沛蓁 | `event_action_bridge.py` POSE_ACTION_MAP | 2 小時 |
| 守護犬 prompt | 陳若恩 | `llm_bridge_node.py` SYSTEM_PROMPT + max_tokens | 半天 |
| Plan B 台詞 | 陳若恩 | `llm_bridge_node.py` RuleBrain fallback 擴充 | 半天 |
| 物體白名單 | 黃旭 | `object_perception_node.py` + `state_machine.py` TTS | 2 小時 |
| Studio PR 審查 | 全員 | gesture / pose / object 頁面 | 每人 1-2 小時 |

### 2E. PawAI Studio 升級

| 項目 | 說明 |
|------|------|
| Guardian Mode 顯示 | 訂閱 `/state/guardian` → 顯示當前狀態（idle/greeting/alert/emergency） |
| 陌生人推播 | alert 事件 → Studio 彈出截圖 + 時間戳 |
| Plan B 模式 UI | 連線狀態燈號 + 自動切換指示 |
| 四人 Studio PR 合併 | gesture / pose / object 頁面 |

---

## Phase 3：Demo 準備（5/12 – 5/18）

### 三場景 Demo 排練

| 項目 | 說明 | deadline |
|------|------|:--------:|
| 場景 1 排練 | 熟人回家：辨識→問候→動作 | 5/12 |
| 場景 2 排練 | 使用者召喚：語音/手勢→回應 | 5/12 |
| 場景 3 排練 | 陌生人警戒：未註冊→alert→Studio 推播 | 5/13 |
| **全流程 3 輪驗收** | 3 分鐘完整劇本跑 3 次，成功率 ≥ 2/3 | **5/14** |
| **教室實地預演** | 到 Demo 場地測光線、距離、網路 | **5/11 前** |
| Plan B 演練 | GPU 斷線 → 自動切固定台詞 → 驗證 | 5/15 |
| 錄影備份 | 完整 Demo 錄一份，萬一現場失敗可播放 | 5/15 |
| **省夜 Demo** | 省級評審，3 分鐘 | **5/16** |
| **正式展示** | 最終發表 | **5/18** |
| 口頭報告 | 答辯 | 6 月 |

### Demo 劇本（3 分鐘）

```
0:00-0:10  開場：Go2 安靜待命
0:10-0:45  ★ Wow：「PawAI，介紹你自己」→ self_introduce sequence 自主執行 6 個動作
0:45-1:15  場景 1：熟人回家（辨識→問候→動作）
1:15-1:50  場景 2：使用者召喚（語音/手勢→回應）
1:50-2:30  場景 3：陌生人警戒（未註冊→alert→Studio 推播）
2:30-3:00  收尾：口頭補異常偵測+雷達升級
```

**開場 Wow Moment 是這份專案最能展示 Guardian Brain 的瞬間**。評審會看到的不是「觸發→反應」，而是「自主規劃的 agent」。答辯可以直接講「embodied agent orchestration」。

---

## 風險追蹤

| 風險 | 嚴重度 | 狀態 | 應對 |
|------|:------:|:----:|------|
| Jetson 斷電（XL4015） | 🔴 | 未解 | Demo 減少同時功能 / 固定電源 |
| GPU 雲端斷線 | 🔴 | 未解 | Plan B 固定台詞 + 錄影佐證 |
| Groq 免費額度用完 | 🟡 | 待測 | 30 RPM / 1000 req/day，Demo 當天夠用但練習會消耗 |
| LiDAR 來不及整合 | 🟡 | 評估中 | 回退到無雷達版（主案不受影響） |
| odom 漂移導致 SLAM 失敗 | 🟡 | 未驗證 | Day 1 bag 錄製驗證，最壞仍有 360° 避障 |
| 陌生人警戒誤報 | 🟡 | 邏輯未實作 | anti-false-positive policy（3s 穩定 + face_count） |
| 組員映射表延遲 | 🟡 | — | 4/13 deadline，逾期 Roy 代填 |
| 文件頁數不足 | 🟡 | 46/60+ | 守護犬敘事 + Guardian Brain 章節可補 10+ 頁 |

---

## 參考文件

| 文件 | 說明 |
|------|------|
| `docs/superpowers/specs/2026-04-10-guardian-dog-design.md` | **居家守護犬系統設計規格**（4/10 定稿） |
| `docs/mission/README.md` | 專案入口頁 v2.3（已更新守護犬定位） |
| `docs/導航避障/research/2026-04-08-external-lidar-feasibility.md` | LiDAR 可行性研究 |
| `pawai-studio/docs/0410assignments/README.md` | 四人分工概覽（守護犬版） |
| `references/project-status.md` | 每日狀態 |
