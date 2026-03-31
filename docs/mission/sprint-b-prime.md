# Operation B-prime: 11-Day Sprint

**期間**：2026/3/28 (六) ~ 4/7 (一)
**操作者**：Roy（一人全職）
**核心原則**：先建 baseline，再一次只引入一個風險源

---

## 總目標

把七大模組全部跑在 Go2 機身上，產出可重現的 Demo 流程。

| 層級 | 定義 | 性質 |
|------|------|:----:|
| **Bronze** | 4 既有模組 + executive v0 在 Go2 上 5 輪 E2E 無 crash，1 套固定 demo flow 可由腳本重現 | 必須 |
| **Silver** | Bronze + 導航避障 + 硬體上機 + Demo A 30 輪 ≥ 90% | 目標 |
| **Gold** | Silver + 物體辨識 Phase 0-2 + docs 重組 + Starlight scaffold | 加分 |

---

## 七大模組現況 → Sprint 目標

| # | 模組 | 現況 | Sprint 結束時 | 主要工作日 |
|:-:|------|:----:|-------------|:----------:|
| 1 | 人臉辨識 | 95% | baseline 穩定 + 上機 | Day 1, 3-4 |
| 2 | 語音功能 | 80% → **ASR 替換中** | Cloud ASR + Local fallback，可順暢溝通 | **Day 2** |
| 3 | 手勢辨識 | 90% | 上機 + executive 整合 | Day 3-6 |
| 4 | 姿勢辨識 | 92% | 上機 + fallen→EMERGENCY | Day 3-6 |
| 5 | AI 大腦 | 70% | executive v0 state machine | Day 5-6 |
| 6 | 導航避障 | 5% | D435 depth 反應式避障 | Day 7-8 |
| 7 | 物體辨識 | 0% | Hard Gate → Phase 0（如果 Go） | Day 9 |

---

## 每日紀律

- **開工**：`bash scripts/start_full_demo_tmux.sh` 確認昨天 baseline 還活著
- **收工**：git commit + 更新 `references/project-status.md` + 記錄 blocker
- **最後 1 小時**：只修 bug 和寫文件，不開新功能
- **main 分支**：收工前 HEAD 必須可啟動、可回退，不留半成品過夜

---

## 砍刀順序

第 8 天時程爆炸時，依序砍：
1. 物體辨識（0% from scratch，最大時間黑洞）
2. 硬體上機的擴張範圍（只保留最小可 demo 版）
3. interaction_executive 完整設計（降級成 rule-based）
4. 導航避障（最後才砍，成本低回報高）

> 不要用 3 天換一個新 feature；要用那 3 天買整個 demo 的可控性。

---

## Daily Breakdown

### Day 1（3/28 六）— Baseline Contract Day ✅

> 鎖定地基。產出可重現的啟動流程。

**交付物 checklist：**
- [x] Topic Graph 快照（51 topics, 16 nodes）
- [x] QoS 配置表（靜態推導 + runtime 驗證一致）
- [x] Device Mapping（mic card 24→0 飄移確認，device_detect.sh 解決）
- [x] 啟動順序文件（10 window + sleep + ready 判定）
- [x] 最小 demo 腳本（clean_full_demo.sh + device_detect.sh）
- [x] Crash/Restart SOP（文件化 + 1m26s 恢復）

**驗收：** 3/3 cold start PASS + 1/1 crash recovery PASS（1m26s < 3min）✅

**額外完成：**
- Noisy profile v1：gain=8.0 + VAD=0.02（3 組 A/B 測試）
- ENABLE_ACTIONS 安全門
- 安全修復 #5 #7

---

### Day 2（3/29 日）— ASR 替換：可順暢溝通

> Whisper Small 中文短句+噪音已到上限（64% 正確+部分）。
> 語音是 Demo 核心，不能用就不該上機。先解決語音再碰硬體。

**前置研究（4 個問題先收斂）：**
- [x] SenseVoice 能否在 RTX 8000 穩定提供低延遲 API → ✅ FunASR + FastAPI, ~600ms
- [x] Jetson 端整合：是否只需新增 ASRProvider，不用重寫 stt_intent_node → ✅ 複用 QwenASRProvider（cloud），新增 SenseVoiceLocalProvider（local）
- [x] Fallback 條件定義（timeout? connection error?） → ✅ ConnectionRefused → sensevoice_local → whisper_local
- [x] 固定音檔測試如何沿用到 cloud/local 雙 provider → ✅ 等量三方 A/B 各 25 筆

**交付物 checklist：**
- [x] Cloud ASR 部署在 RTX 8000（SenseVoice + Qwen3-ASR 對比）
- [x] stt_intent_node 新增 cloud + local ASR provider
- [x] Cloud → Local SenseVoice → Whisper 三級 fallback 機制
- [x] 等量 A/B/C 測試（SenseVoice cloud 92% / SenseVoice local 92% / Whisper 52%）

**驗收標準：**
- ✅ 固定音檔正確+部分 >= 80%（實測 92%）
- ✅ 高風險 intent 誤判 = 0
- ✅ 實際對話測試通過（Day 3 真人自然對話，SenseVoice local 92% 可讀）
- ✅ `ENABLE_ACTIONS=true` 補驗通過（stop→stop_move, thumbs_up→content 各 3 次）

**剩餘（Day 3 前必須完成）：**
- [x] 實際對話測試：真人自然對話 5-10 輪，確認順暢
- [x] 對話通過後 `ENABLE_ACTIONS=true`

**不做：** 硬體上機（等對話驗收通過）、executive v0、導航避障

---

### Day 3-4（3/30-31）— 硬體上機：可跑 + 可用

> 語音驗收通過後，才把 Jetson + 感測器固定到 Go2。

**Day 3 前置驗證（3/30 完成）：**
- [x] 四核心桌測 10/10 PASS（face + speech + gesture + pose）
- [x] Go2 動作補驗 PASS（stop_move + content 各 3 次）
- [x] 驗證工具建立（Foxglove layout + verification observer + JSONL 882 筆）
- [x] 模型策略收斂：ASR SenseVoice 三級 fallback、LLM Cloud→RuleBrain（砍 Ollama）、TTS edge-tts

**Day 3 交付物（可跑）— 3/30 晚完成：**
- [x] Jetson 固定（Go2 BAT 28.8V → XL4015 降壓 19V → DC jack）
- [x] D435 固定
- [x] USB 麥克風/喇叭接線（⚠️ 喇叭 USB 間歇斷開，已束帶固定）
- [x] 供電穩定（Go2 BAT 供電 Jetson 正常運行）
- [x] Bring-up 測試通過（full demo 10 window + ASR/LLM/TTS 鏈路通）

**Day 4 交付物（可用）— 3/31 完成：**
- [x] 3 次完全斷電重開，每次 bring-up 成功
- [x] Go2 行走 2 分鐘，硬體不鬆脫（熱熔膠固定 USB 接頭後解決）
- [x] 連續運行 30 分鐘，Jetson peak 56.2°C < 75°C
- [x] 重開機後 USB device index 不漂移（3 輪 mic=0, spk=plughw:1,0）
- [x] 上機版 `start_full_demo_tmux.sh` 確認可跑（3 次）
- [x] XL4015 電壓調整 18.8V → 19.2V（原值偏低導致行走時斷電）
- [x] USB 喇叭反覆斷連 → 熱熔膠固定解決
- [x] Jetson 啟動腳本同步（SenseVoice 三級 fallback）
- [x] Bug fix: llm_bridge lock race + sensevoice null check + async blocking

---

### Day 5（4/1 三）— Executive v0：State Machine

> 建立 thin orchestrator，統一事件路由。Demo Controller，不是 AI Brain。

**交付物 checklist — 3/31 完成（提前一天）：**
- [x] `interaction_executive` ROS2 package scaffold
- [x] 純 Python state machine + 27 個 unit tests（19 state + 6 api_id alignment + 2 obstacle edge）
- [x] 狀態：IDLE → GREETING → CONVERSING → EXECUTING → EMERGENCY → OBSTACLE_STOP
- [x] 優先序：EMERGENCY > obstacle > stop > speech > gesture > face
- [x] 5s dedup、30s timeout、obstacle debounce 2s
- [x] ROS2 node + `/executive/status` 2Hz 廣播
- [x] launch file + config
- [x] api_id 修正（計畫裡 Damp/Sit/Stand 寫錯，已對齊 robot_commands.py）
- [x] action constants 補 topic/parameter/priority for WebRtcReq
- [x] Jetson 部署驗證：`/executive/status` → `{"state": "idle"}`

**關鍵設計：**
```
輸入：/event/face_identity, /event/speech_intent_recognized,
      /event/gesture_detected, /event/pose_detected,
      /event/obstacle_detected

輸出：/tts, /webrtc_req, /executive/status

規則：一次一個事件，fallback LLM timeout > 2s → RuleBrain
```

**實作細節：** `docs/superpowers/plans/2026-03-27-operation-b-prime.md` Task 3-4

---

### Day 6（4/2 四）— Executive v0：整合 + Bridge 遷移

> executive v0 取代 event_action_bridge + interaction_router。

**交付物 checklist：**
- [ ] 5 個邊界測試通過：
  - 人臉+語音同時 → dedup
  - 對話中 stop 手勢 → 中斷
  - 跌倒誤報 → EMERGENCY → timeout
  - LLM timeout > 2s → RuleBrain
  - crash → restart → re-subscribe
- [ ] `/executive/status` 可在 Foxglove 即時看到
- [ ] **同步更新 `start_full_demo_tmux.sh`**（移除 bridge/router，改啟 executive）
- [ ] **同步更新 Crash/Restart SOP**
- [ ] 更新 `interaction_contract.md` v2.2

**實作細節：** `docs/superpowers/plans/2026-03-27-operation-b-prime.md` Task 5

---

### Day 7（4/3 五）— 導航避障：D435 Depth

> 50 行 numpy → ROS2 node → Go2 反應式避障。

**交付物 checklist：**
- [ ] `obstacle_detector.py`（純 Python/numpy）+ 7 個 unit tests（TDD）
- [ ] `obstacle_avoidance_node.py`（ROS2 node，訂閱 D435 depth）
- [ ] executive v0 訂閱 `/event/obstacle_detected` → Go2 Damp
- [ ] 室內 10 次防撞測試，記錄 stop latency
- [ ] 更新 `start_full_demo_tmux.sh` 加入 obstacle window

**降級策略（現在鎖定）：**

| 場景 | 策略 |
|------|------|
| metrics 全過 | Damp + BackMove |
| 漏停 > 10% | Damp-only |
| 誤停 > 20% | Demo A 用、Demo B 關 |
| 整體不穩 | 完全停用 |

**實作細節：** `docs/superpowers/plans/2026-03-27-operation-b-prime.md` Task 6

---

### Day 8（4/4 六）— 導航避障：Hardening

> 30 次防撞測試，量化 pass/fail/warning。

| Metric | Pass | Warning (Damp-only) | Fail (停用) |
|--------|:----:|:-------------------:|:-----------:|
| 漏停率 | ≤ 3% | 4-10% | > 10% |
| 誤停率 | ≤ 10% | 11-20% | > 20% |
| Stop latency | P95 < 500ms | 500-1000ms | > 1s |
| Frame drop | ≤ 5% | 6-15% | > 15% |

**任一落灰區 → 統一降 Damp-only。**

**實作細節：** `docs/superpowers/plans/2026-03-27-operation-b-prime.md` Task 7

---

### Day 9（4/5 日）— 物體辨識 Hard Gate

> Go/No-Go。最多 4-6 小時 timebox。

**Go 條件（全部同時滿足）：**
1. 前 7 天 baseline 穩定（Demo A 5 輪 ≥ 4/5）
2. Jetson RAM headroom ≥ 1.5GB
3. GPU 無持續滿載
4. D435 pipeline 不衝突
5. 半天內能完成 Phase 0

**如果 Go：** Phase 0-1（ultralytics → TensorRT 轉換），不碰 ROS2
**如果 No-Go：** 直接進 Day 9，不辯論
**超時：** 4-6h 到就停，不管做到哪

**實作細節：** `docs/superpowers/plans/2026-03-27-operation-b-prime.md` Task 8

---

### Day 10（4/6 一）— Freeze + Hardening

> 不加新功能。只修 demo 失敗路徑。

**交付物 checklist：**
- [ ] Demo A 30 輪語音測試 → 目標 ≥ 90% (27/30)
- [ ] Demo B 5 輪手勢→Go2 真機 → 目標 ≥ 4/5
- [ ] Crash recovery drill 3 輪，每輪 < 3 分鐘
- [ ] Demo 操作手冊（非技術人員照做也能跑）
- [ ] `/executive/status` 壓測監控驗證
- [ ] 最終 E2E regression pass
- [ ] 每次修改都回歸完整 E2E

---

### Day 11（4/7 二）— Handoff Day

> 整理交付。為 4/9 會議準備。

**交付物 checklist：**
- [ ] docs/ 可交接重組（中文→英文目錄、`.MD`→`.md`、刪 `.docx`）
- [ ] Starlight scaffold（空框架 + sidebar + 內容對照表）
- [ ] 4/9 會議分工文件（誰寫哪個頁面）
- [ ] 展示站 wireframe
- [ ] 系統狀態快照
- [ ] Studio backend interface draft

---

## 後續（4/9 後由團隊接手）

| 工作包 | 負責人 | 性質 |
|--------|:------:|:----:|
| Starlight 文件站 | 成員 A | 立即開發 |
| 展示站首頁 | 成員 B | 立即開發 |
| 模組教學頁面 | 成員 C+D | 立即開發 |
| Studio backend | 待分配 | Interface draft 先行 |

---

## 關聯文件

| 文件 | 用途 |
|------|------|
| `docs/superpowers/specs/2026-03-27-operation-b-prime-sprint-design.md` | 完整設計規格（風險矩陣、成功定義、每日紀律） |
| `docs/superpowers/plans/2026-03-27-operation-b-prime.md` | 實作計畫（每步驟的程式碼、命令、測試） |
| `references/project-status.md` | 每日更新的系統狀態 |
| `docs/operations/baseline-contract.md` | Day 1 產出的基線契約（啟動順序、QoS、SOP） |
