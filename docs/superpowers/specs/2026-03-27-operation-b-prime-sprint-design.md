# Operation B-prime: 11-Day Solo Sprint Spec

**日期**：2026-03-27
**期間**：2026/3/28 ~ 4/7（11 天）
**操作者**：Roy（一人全職）
**狀態**：APPROVED

---

## 1. Sprint 哲學

**核心原則**：先建 baseline，再一次只引入一個風險源。

這個專案真正吃人的不是功能開發，而是交互干擾。ROS2 + Jetson + Go2 + 多感知模組的系統，每加一個變數都可能讓之前穩定的東西壞掉。所以排程邏輯是：

1. 先讓現有系統在真實硬體上可重現地跑起來
2. 每天只加一個新東西，加完立刻在完整系統上驗證
3. 不要用 3 天去換一個新 feature；要用那 3 天去買整個 demo 的可控性

---

## 2. 成功定義

### 三級目標

| 層級 | 定義 | 必須/加分 |
|------|------|:---------:|
| **Bronze** | 4 既有模組（face/speech/gesture/pose）+ executive v0 在 Go2 上跑完 5 輪 E2E 無 crash，且有 1 套固定 demo flow 可由同一腳本或 SOP 重現 | **必須** |
| **Silver** | Bronze + 導航避障上線 + 硬體最小上機版 + 30 輪 Demo A ≥ 90% | **目標** |
| **Gold** | Silver + 物體辨識 Phase 0-2 通過 + docs 可交接重組完成 + Starlight scaffold ready | **加分** |

### 砍刀順序（第 8 天時程爆炸時）

1. **物體辨識** — 0% from scratch，最大時間黑洞
2. **硬體上機整合的擴張範圍** — 只保留最小可 demo 版，砍走線美觀、長期固定
3. **interaction_executive 的完整設計** — 降級成 rule-based state machine，不做 AI brain
4. **導航避障** — 最後才砍，成本低回報高，demo 保命層

---

## 3. 每日紀律

- **開工儀式**：`bash scripts/start_full_demo_tmux.sh` 確認昨天的 baseline 還活著
- **收工儀式**：git commit + 更新 `references/project-status.md` + 記錄當日 blocker
- **不加新東西的時段**：每天最後 1 小時只修 bug 和寫文件，不開新功能
- **main 分支紀律**：每天收工前保證 `main` 的 HEAD 是可啟動、可回退的，不留「今天做到一半」狀態過夜。對 solo sprint 很重要，不然第 6 天之後會開始怕 commit

---

## 4. Daily Breakdown

### Day 1（3/28）— Baseline Contract Day

**目標**：鎖定整個 sprint 的「地基」，產出可重現的啟動流程。

| 交付物 | 具體內容 |
|--------|---------|
| Topic Graph 快照 | `ros2 topic list` + `ros2 node list` 存檔，作為 baseline |
| QoS 配置表 | 每個 topic 的 QoS profile 確認（BEST_EFFORT vs RELIABLE） |
| Device Mapping 規則 | USB mic/speaker/D435 的 device index 固定策略（udev rules 或啟動時偵測） |
| 啟動順序文件 | 哪個 node 先起、等多久、怎麼確認 ready |
| 最小 demo 腳本 | 一個 script 能 cold start → 4 模組全跑 → 基本互動 |
| Crash/Restart SOP | 當機時怎麼清環境、怎麼重啟、要殺哪些 process |

**驗收**：
- 3 次 cold start 全部成功
- 1 次 crash recovery drill（手動 kill 關鍵 node，按 SOP 恢復，< 3 分鐘）

---

### Day 2（3/29）— Hardware Bring-up：可跑

**目標**：Jetson + 感測器物理固定到 Go2，能開機帶起全系統。

| 項目 | 完成標準 |
|------|---------|
| Jetson 固定 | 不會因 Go2 行走而鬆脫 |
| D435 固定 | 視角穩定，不會晃 |
| USB 麥克風/喇叭 | 接線不影響 Go2 行走範圍 |
| 供電 | Jetson 供電穩定（Go2 行走時不斷電） |
| Bring-up 測試 | Go2 開機 → Jetson 開機 → 4 模組啟動 → 基本互動 pass |

**不做**：走線美觀、長期固定方案、外殼設計。

---

### Day 3（3/30）— Hardware Bring-up：可用

**目標**：重開機一致性 + 行走穩定性。

| 項目 | 完成標準 |
|------|---------|
| 重開機測試 | Go2 + Jetson 完全斷電重開 3 次，每次 bring-up 成功 |
| 行走測試 | Go2 行走 2 分鐘，Jetson + D435 不鬆脫、不斷電 |
| 熱管理 | 連續運行 30 分鐘，Jetson 溫度 < 75°C |
| Device index 穩定 | 重開機後 USB device 不漂移（udev rules 或偵測腳本生效） |
| 更新 baseline | 上機版的 `start_full_demo_tmux.sh` 確認可跑 |

---

### Day 4（3/31）— Executive v0：State Machine

**目標**：建立 thin orchestrator，統一事件路由。這是 Demo Controller，不是 AI Brain。

#### 輸入

| Topic | 事件 |
|-------|------|
| `/event/face_identity` | WELCOME 觸發（identity_stable） |
| `/event/speech_intent_recognized` | 語音指令（greet/stop/sit/stand/chat） |
| `/event/gesture_detected` | 手勢指令（stop/thumbs_up/wave） |
| `/event/pose_detected` | 姿勢事件（fallen） |
| `/event/obstacle_detected` | 避障事件（Day 6 加入，預留介面） |

#### 狀態機

```
IDLE → GREETING → CONVERSING → EXECUTING → IDLE
任何狀態 + fallen → EMERGENCY
任何狀態 + stop gesture → IDLE
任何狀態 + obstacle → OBSTACLE_STOP（Damp，打斷當前動作/對話 TTS 繼續）
OBSTACLE_STOP + obstacle cleared → 回到前一狀態
每個狀態 timeout 30s → IDLE
```

#### 輸出

| Topic | 用途 |
|-------|------|
| `/tts` | 語音回應 |
| `/webrtc_req` | Go2 動作 |
| `/executive/status` | 系統狀態廣播（state + active_event + timestamp），供 Day 9-10 壓測和除錯用 |

#### 規則

- 同一來源 5s dedup
- 同時多事件優先序：**EMERGENCY > obstacle > stop > speech > gesture > face**
- 每個狀態有 timeout（30s 回 IDLE）
- manual override：ROS2 service `/executive/force_state` 可強制切狀態
- LLM response timeout > **2s** → fallback to RuleBrain（明確時間界線，不是模糊的「太慢就切」）

#### 與現有 bridge 的關係

executive v0 **取代** `event_action_bridge` 和 `interaction_router` 的職責。Day 4 開始時先停用這兩個 node，由 executive v0 統一接管。如果 executive v0 開發受阻，可退回使用現有 bridge 作為 fallback（但接受事件重複觸發的風險）。

**驗收**：人臉觸發 + 語音對話 + 手勢停止，三個場景不互相干擾。

---

### Day 5（4/1）— Executive v0：整合 + 邊界測試

**目標**：executive v0 嵌入真實系統，處理邊界情況。

| 測試場景 | 預期行為 |
|---------|---------|
| 人臉 + 語音同時觸發 | dedup，只回應一次 |
| 對話中收到 stop 手勢 | 立即中斷對話，Go2 停止 |
| 跌倒偵測誤報 | EMERGENCY → 語音確認 → timeout 回 IDLE |
| LLM timeout > 2s | fallback → RuleBrain → 繼續運作 |
| 所有 node crash 後重啟 | executive 能 re-subscribe，不需重啟整個系統 |
| `/executive/status` 驗證 | Foxglove 或 `ros2 topic echo` 可即時看到狀態變化 |

**收工時**：
- 更新 `interaction_contract.md` v2.2（新增 executive topics + status schema）
- **同步更新 `start_full_demo_tmux.sh`**：移除 `event_action_bridge` 和 `interaction_router` 啟動路徑，改為啟動 executive v0
- **同步更新 Crash/Restart SOP**：recovery 流程對齊新的 node 組合，確保隔天開工儀式不會啟錯舊節點

---

### Day 6（4/2）— 導航避障：D435 Depth

**目標**：50 行 numpy → ROS2 node → Go2 反應式避障。

| 階段 | 內容 | 時間 |
|------|------|:----:|
| 實作 | D435 depth → 256x192 ROI → numpy threshold (< 0.5m) → ObstacleEvent | 2h |
| 整合 | executive v0 訂閱 ObstacleEvent → Go2 Damp/BackMove | 1h |
| 測試 | 室內環境 10 次防撞，記錄 stop latency | 2h |

#### 降級策略（現在就鎖定，不等 Day 7 才決定）

| 場景 | 策略 |
|------|------|
| 避障 metrics 全過 | 全功能啟用（Damp + BackMove） |
| 漏停率 > 10% | 只保留 emergency stop（Damp），關閉 BackMove |
| 誤停率 > 20% | Demo A 啟用、Demo B 關閉（展示但不常駐） |
| 整體不穩定 | 完全停用，不影響其他模組 |

---

### Day 7（4/3）— 導航避障：Hardening + Metrics

**目標**：30 次防撞測試，量化 pass/fail。

| Metric | Pass（全功能） | Warning（Damp-only） | Fail（停用） |
|--------|:-------------:|:-------------------:|:-----------:|
| 漏停率（障礙物 < 0.5m 未停） | ≤ 3% | 4-10% | > 10% |
| 誤停率（無障礙物卻停） | ≤ 10% | 11-20% | > 20% |
| Stop latency（偵測→Go2 停止） | P95 < 500ms | 500-1000ms | P95 > 1000ms |
| Depth frame drop | ≤ 5% | 6-15% | > 15% |

**判定規則**：
- **全指標 Pass** → 全功能啟用（Damp + BackMove）
- **任一指標落入 Warning** → 統一降級為 Damp-only（只急停，不後退），其餘模組不受影響
- **任一指標 Fail** → 按 Day 6 降級策略表處理（可能完全停用）

---

### Day 8（4/4）— 物體辨識 Hard Gate

#### Go 條件（全部同時滿足才開工）

1. 前 7 天 baseline 穩定（Demo A 5 輪 E2E ≥ 4/5 pass）
2. Jetson RAM headroom ≥ 1.5GB（給 YOLO26n 0.6-1.1GB + buffer）
3. GPU 無持續滿載（Whisper 用完會釋放）
4. D435 RGB pipeline 與避障 depth pipeline 不衝突
5. 預估半天內能完成 Phase 0（ultralytics → TensorRT 轉換）

#### 執行規則

- **如果 Go**：Phase 0-1（環境驗證 + 模型轉換），不碰 ROS2 整合
- **如果 No-Go**：直接進入 Day 9 的 freeze，不辯論
- **Timebox**：最多 **4-6 小時**。超時直接停止，不管做到哪裡。Day 8 最容易失控，timebox 是硬限制

---

### Day 9-10（4/5-4/6）— Freeze + Hardening

#### 鐵律

- **不加新功能**
- 只修 demo 失敗路徑
- 只補操作文件與恢復手冊
- 每次修改都回歸完整 E2E
- 如果 Day 8 硬上了 object detection，這兩天絕對不能再變開發日

#### 交付物

| 項目 | 驗收標準 |
|------|---------|
| Demo A 30 輪 | 成功率 ≥ 90%（≥ 27/30） |
| Demo B 5 輪 | 手勢→Go2 真機動作 ≥ 4/5 |
| Crash Recovery SOP | 從完全當機到恢復 < 3 分鐘 |
| Demo 操作手冊 | 非技術人員照著做也能跑起來 |
| `/executive/status` 監控 | 壓測時可即時看到所有狀態轉換 |

---

### Day 11（4/7）— Handoff Day

#### 交付物

| 項目 | 給誰 | 內容 |
|------|------|------|
| docs/ 可交接重組 | 全隊 | 中文→英文目錄、`.MD`→`.md`、刪 `.docx`、archive 標記 |
| Starlight scaffold | 4 位成員 | 空框架 + sidebar 目錄結構 + 內容對照表 |
| 分工文件 | 4/9 會議用 | 誰寫哪個頁面、deadline、格式規範 |
| 展示站 wireframe | 視覺組 | Odin 風格 hero + demo 影片位置 + 團隊介紹 |
| 系統狀態快照 | 全隊 | 當前 baseline、已知 bug、操作手冊 |
| Studio backend interface draft | 後端組 | API schema + WebSocket event 規格 + 範圍定義（不承諾立即開發） |

---

## 5. Docs 整理策略

### 原則

docs 整理是**附帶任務**，不是主線。Day 11 做可交接重組，不做歷史清倉式大掃除。

### Sprint 期間（每日收工 15 分鐘）

- 更新 `references/project-status.md`
- 新的 SOP/手冊直接寫進正確位置
- 不搬目錄、不改結構

### Day 11 可交接重組

**做的**：
- 中文資料夾→英文命名（建立 `docs/modules/` 統一入口）
- `README.MD` → `README.md`（統一小寫）
- 刪除 `.docx` 檔案
- `archive/` 加明確 `ARCHIVED` 標記或移出主導航，**不刪除**（避免大量非功能 diff）
- 建立 `docs/website/` 放 Starlight 相關配置

**不做的**：
- 不刪 `archive/`（git tag 後標記即可）
- 不重寫已有的 README 內容
- 不搬 `superpowers/` 的 plan/spec（結構已良好）

### 目標結構

```
docs/
├── mission/          （保留）
├── architecture/     （保留，加 executive v0）
├── research/         （保留）
├── modules/          （新建，統一英文命名）
│   ├── face-recognition/
│   ├── speech/
│   ├── gesture/
│   ├── pose/
│   ├── object-detection/
│   ├── navigation/
│   └── pawai-studio/
├── setup/            （保留）
├── assets/           （保留）
├── superpowers/      （保留）
├── audit/            （保留）
├── website/          （新建）
│   ├── starlight-config.md
│   └── content-assignment.md
└── archive/          （標記 ARCHIVED，不刪除）
```

每個 `modules/*/README.md` 就是未來 Starlight 的一個頁面，目錄結構直接對應 sidebar。

---

## 6. Handoff Package（4/9 會議用）

| 工作包 | 建議負責人 | 內容 | 性質 |
|--------|:---------:|------|:----:|
| Starlight 文件站框架 | 成員 A | `npm create astro` + sidebar config + 搬 `docs/modules/` | 立即開發 |
| 展示站首頁 | 成員 B | Odin 風格 hero + demo 影片 + 團隊介紹 | 立即開發 |
| 模組教學頁面 | 成員 C+D | 每人 2-3 個模組的「從零復現」教學 | 立即開發 |
| Studio backend interface | 待分配 | API schema + WebSocket event 規格 + 範圍定義 | **Interface draft**（先交規格，不承諾立即全面開發） |

---

## 7. 七大模組 Sprint 內目標

| 模組 | 現況 | Sprint 目標 | Day |
|------|------|-------------|:---:|
| 人臉辨識 | 95% | baseline 穩定 + 上機驗證 | 1-3 |
| 語音功能 | 80% | E2E 穩定 + system prompt 調整 | 1-3 |
| 手勢辨識 | 90% | 上機驗證 + executive 整合 | 1-5 |
| 姿勢辨識 | 92% | 上機驗證 + fallen→EMERGENCY | 1-5 |
| AI 大腦 | 70% | executive v0 state machine | 4-5 |
| 導航避障 | 5% | D435 depth → Go2 反應式避障 | 6-7 |
| 物體辨識 | 0% | Hard Gate → Phase 0-1（如果 Go） | 8 |

---

## 8. 風險矩陣

| 風險 | 影響 | 嚴重度 | 緩解 |
|------|------|:------:|------|
| Go2 OTA 自動更新 | Demo 當天爆掉 | **高** | Ethernet 直連 + 網路隔離 |
| USB device index 漂移 | 重開機後收不到音 | **高** | udev rules 或啟動偵測腳本（Day 1） |
| Jetson 記憶體溢出 | 系統當機 | **高** | 監控 + 保留 ≥ 0.8GB 餘量 |
| 硬體上機卡住 | 壓縮 Day 4+ 時間 | **中** | Day 2 只求可跑，Day 3 再求可用 |
| Executive v0 與現有 bridge 衝突 | 事件重複觸發 | **中** | 明確移除舊 bridge 路徑 |
| RTMPose + Whisper GPU 搶佔 | FPS 掉 | **中** | 備援：全 MediaPipe CPU-only |
| Cloud LLM 斷線 | 對話品質下降 | **中** | Ollama → RuleBrain 三級降級 |
| 物體辨識吃掉 Day 8 | 沒有 freeze 時間 | **中** | 4-6h timebox 硬限制 |

---

## 附錄 A：現有模組深度調查數據

### 程式碼與測試覆蓋

| 模組 | 程式碼行數 | 測試案例 | 測試覆蓋率 |
|------|:---------:|:-------:|:---------:|
| face_perception | 802 | 13 | 10.8% |
| speech_processor | 4,455 | 60 | 14.6% |
| vision_perception (gesture) | 146 | 12 | 19.9% |
| vision_perception (pose) | 114 | 11 | 67.5% |
| llm_bridge_node | 624 | 0 | 0% |
| 物體辨識 | 0 | 0 | 0% |
| 導航避障 | 0 | 0 | 0% |

### Jetson 資源快照（3/25 基線）

- 已用 RAM：~5.0GB（D435 + YuNet + MediaPipe + Whisper + ROS2）
- 剩餘 RAM：~2.6GB
- GPU：91-99%（RTMPose balanced，若用 MediaPipe 則 0%）
- 溫度：52-66°C（安全）
- 功耗：18.9W（上限 ~25W）

### Benchmark 覆蓋

| 模組 | L1 基線 | L2 共存 | L3 全棧 |
|------|:------:|:------:|:------:|
| face (YuNet) | 71.3 FPS | -6% w/ pose | 通過 |
| pose (MediaPipe) | 18.5 FPS | -20% w/ whisper | 通過 |
| gesture (Recognizer) | 7.2 FPS | — | 通過 |
| stt (Whisper small) | RTF 0.13 | — | 通過 |
| tts (edge-tts) | P50 1.13s | — | 通過 |
| object detection | 待測 | — | — |
| navigation | 待測 | — | — |

---

## 附錄 B：關鍵里程碑

| 日期 | 事項 | 狀態 |
|------|------|:----:|
| **3/28** | Sprint 啟動 — Baseline Contract Day | 預訂 |
| **3/29-30** | 硬體上機（可跑→可用） | 預訂 |
| **3/31-4/1** | Executive v0 開發 + 整合 | 預訂 |
| **4/2-3** | 導航避障開發 + 30 次防撞 | 預訂 |
| **4/4** | 物體辨識 Hard Gate | 預訂 |
| **4/5-6** | Freeze + Hardening | 預訂 |
| **4/7** | Handoff Day | 預訂 |
| **4/9** | 教授會議 + 團隊分工啟動 | 預訂 |
| **4/13** | 文件繳交（硬底線） | — |
| **5/16** | 省夜 Demo | — |
| **5/18** | 正式展示 | — |
