# PawAI Architecture Audit（Phase 1 全 repo 架構盤點）

> 日期：2026-06-10 晚
> 基線：tag `demo-2026-06-snapshot`（commit `24280ef`，已 push）；demo 凍結文件
> `docs/pawai-demo/2026-06-10-demo-snapshot.md`。
> 方法：唯讀多代理盤點 — 10 個子系統 mapper 並行讀碼 → 99 條 findings →
> 99 條逐一對抗性查證（verifier 開證據檔核實；98 supported、1 條 OBJECT-1 部分駁回已修正）
> → 6 個 v2 方向評估。本文件不改任何程式碼、不做任何硬體宣稱。
> 完整 findings 附錄：[`2026-06-10-pawai-architecture-findings-ledger.md`](2026-06-10-pawai-architecture-findings-ledger.md)。
> 約束繼承：`docs/pawai-brain/specs/2026-06-10-pawai-brain-v2-cli-v2-prd.md` §0 已決事項不重議；
> S1 未錄 → 所有 MUST_PRESERVE_FOR_DEMO 項目凍結到 6/18 之後。

---

## 1. Executive Summary

**PawAI 今天是什麼**：一隻以 Unitree Go2 Pro 為載體的居家互動機器狗，
跑在 Jetson Orin Nano 8GB 上的 ROS2 Humble 系統 —— 5 條感知（face/speech/vision
pose+gesture/object）+ 三角色一出口的決策層（規則 proposer `brain_node` +
LangGraph 對話引擎 `conversation_graph_node` + 唯一 actuator 出口
`interaction_executive_node`）+ Nav2/AMCL/reactive_stop 四層導航 + Studio 操作台 +
團隊 CLI。S2-S5 已錄影完成、S5 安全拒絕端到端驗證過；S1 移動段卡在 AMCL
covariance 閘（NAV-1）。

**什麼是好的（保留）**：
- **proposer / executor 分離與唯一 actuator 出口**（interaction_executive_node：
  SafetyLayer、序列佇列、SAFETY/ALERT 搶佔、NAV fail-closed 四重 world gate）——
  S5 HITL 驗證過，PRD 已明定不動。
- **安全核心是撞出來的而且有測試**：driver StopMove-1003 路由 + 1Hz dedupe（11 tests）、
  twist_mux 優先序架構、reactive_stop 4-mode FSM、AMCL covariance 閘 —— 全部有
  5/11、6/8、6/9 HITL 文件背書。
- **測試資產豐厚**：全 repo ~1,345 個 test functions；606 個 Brain 系純 Python 測試
  在 WSL 全綠（本次 audit 實跑驗證），是重構回歸網的地基。
- **HITL 紀律與誠實文化**：trackB / 6-9 執行計畫的「能講/不能講」格式、demo snapshot
  的 forbidden claims 清單、模組 README 的 claim matrix —— 制度已存在，只缺統一格式。
- **模型選型全部站得住**：6/05 模型錦標賽六能力全判 KEEP_CURRENT；模型「智商」
  不是現在的債。

**什麼是脆的（重新設計）**：
- **brain_node 的仲裁結構**：一個 active_plan dict + 複製貼上到每個 callback 的
  not-active gate + 約 14 個 demo flag —— 6/9 stranger_alert 全黑事件的結構性根因，
  目前是「拔掉觸發器」不是「修好結構」（BRAIN-1/3）。
- **觀測黑洞**：TTS 無 request_id/ack（「我講了沒」靠 Bool 猜，BRAIN-2）；nav goal
  被拒絕時 server→gateway→UI 三層把原因全部吞掉（NAV-2/STUDIO-2，就是 Roy 在 S1
  看到的「按開始狗不動沒反應」）；大多數 gate 早退 silent return 無 trace。
- **CI 護城河有大洞**：demo 最關鍵的 4 個套件（interaction_executive / nav_capability /
  go2_robot_sdk / pawai_cli，共 513 個測試函數）不在任何 CI 或 pre-commit gate 裡
  （DEVOPS-1）。
- **操作工具反咬**：`pawai jetson deploy` 偏好未審計的 `~/sync` 腳本，6/10 實證刪掉
  Jetson 的 `.env`（CLI-1）；`pawai demo start` 只看 rc 就報成功（6/4 假成功事件，
  DEVOPS-2）。
- **demo 行為活在 launcher override 裡**：vision 的整套 demo 參數只存在
  `start_full_demo_tmux.sh:163-168`，套件預設是 mock+rtmpose 三重 footgun（VISION-2）。
- **死碼存量大**（~4,400+ LOC）：Executive v0 state_machine、interaction_router +
  event_action_bridge、vision 障礙 stack、vad/asr/intent 三舊節點、MeloTTS、
  move_service/snapshot_service、lidar_processor_cpp、604 行 legacy face script。

**結論**：架構的骨（分層、唯一出口、安全閘、HITL 紀律）是對的；債集中在
brain_node 的仲裁內臟、觀測鏈、CI 覆蓋與操作工具安全。v2 是「換內臟不換骨架」。

---

## 2. Current System Map

逐子系統一句話現況 + 整體 KEEP/TUNE/REFACTOR/REWRITE 判決（模組級判決與 LOC
明細見 ledger 各節）：

| 子系統 | 現況一句話 | 總判決 |
|---|---|---|
| **Brain**（interaction_executive 1664+506+759 LOC + pawai_brain ~4,000 LOC）| 三角色一出口：brain_node 規則 proposer（唯一 /brain/proposal 作者）+ conversation_graph（LangGraph 12 節點，CONVERSATION_ENGINE 預設）只出 /brain/chat_candidate 再被 brain_node re-gate + IE 唯一 actuator。606 tests 綠 | IE/safety/contract/confirm/attention **KEEP**；brain_node **REFACTOR（post-demo）**；state_machine.py **刪**；conversation_graph_node **TUNE**（1118 LOC god-wrapper 拆模組）|
| **Studio**（gateway 1333 LOC + frontend ~9.2k LOC + mock 979 LOC）| 單檔 FastAPI+rclpy gateway 橋 16+ topics 到 WS envelope；6/10 新增 S1 操作員 nav FSM（64 gateway tests）；mock twin 已漂移；trace 只活在 50/200 ring buffer | nav FSM 設計 **KEEP+TUNE**（busy guard + rejection UX）；gateway **REFACTOR（post-demo 拆 5 模組）**；mock **TUNE 補 parity**；Plan A/B 假開關 **拆或接線** |
| **CLI**（~2.8k LOC Click，main.py 1370 行單體）| lock/platform/network 模組是 repo 裡工程品質最高的；但 deploy 刪 .env（已被團隊棄用）、demo start 假成功、144 tests 不在 CI | lock/platform/shell/network/cache **KEEP**；main.py **REFACTOR（v2 Typer 分組遷移）**；deploy sync 路徑 **REWRITE-small（立刻）** |
| **Face**（680 LOC node，3/25 起 code-frozen）| 證據最硬的感知（6/04 baseline n=9 recall 1.0/false-accept 0）；債在 face_db 衛生（ghost-identity 訓練）、event-as-state 消費端、無 camera liveness | 模型 **KEEP**；node **TUNE（post-demo）**；brain 端 _on_face 消費 **REWRITE（Brain v2 ①②）**；legacy 604 行腳本 **歸檔** |
| **Speech**（stt 1209 + tts 1611 + llm_bridge 1140 LOC）| 鏈最成熟（ASR 三層、TTS 雙 lane、LLM OpenRouter→RuleBrain）；債在 utterance 所有權碎 5 處、LLM 鏈雙實作已漂移、stt_intent_node 零直測、tts_node god-node | 模型全 **KEEP**；tts_node **REFACTOR（post-demo）**；llm_bridge **REWRITE-to-retire**；vad/asr/intent 舊節點 **刪** |
| **Vision**（608 LOC node + 純邏輯層）| 純邏輯層 138 tests 全綠；demo 全套參數只在 launcher override；router/bridge/障礙 stack ~1,950 LOC 殭屍碼；手勢詞彙表三處不一致 | 分類器/voting/event_builder **KEEP**；node `_tick` **REFACTOR（post-demo）**；殭屍碼 **刪（post-demo）**；預設值 **翻成 demo 矩陣（post-demo）** |
| **Object**（559 LOC node）| YOLO26n@640 TRT FP16，cup@1m 5/5 HITL 證；A/B 機制全備（env 切換+TRT cache 分流+harness）但候選 ONNX 只在 gitignored .tmp；消費端 objects[0]-only + 三層 cooldown | node **KEEP/TUNE**；brain object slice **REFACTOR（post-demo）**；A/B 資產 **入 git（立刻）** |
| **Nav**（nav_capability + reactive_stop + Nav2 + mux）| 架構誠實、HITL 注記最密；已證 envelope 遠窄於已建 surface（短 goto/safe-stop/indoor_tight/log_pose 證過，route/named/1m+ 全沒證過）；S1 卡 covariance 閘三處不同數字 | server 短 goto 路徑 **TUNE**；route_runner **KEEP frozen**；reactive_stop **REFACTOR（搬家+runtime params，post-demo）**；detour 腳本 **加 guard 歸檔（立刻）** |
| **Go2 runtime**（go2_robot_sdk fork）| 兩執行緒模型 + StopMove 安全路由皆 HITL 證；WebRTC 靠 private-API monkeypatch + aiortc 1.9.0 pin 活著（load-bearing）；93 tests 不在 CI；MCP 殭屍服務含 mux-bypass 隱患 | driver 核心 **KEEP**；webrtc adapter **TUNE（health topic）**；move/snapshot_service **刪（post-demo）**；robot.launch.py **TUNE（拆 per-stack）** |
| **DevOps**（54 scripts ~7.1k LOC + CI + skills + benchmarks）| lane skills 編碼了最好的 HITL 安全知識；CI fast gate 只跑 4 suite/35 檔；preflight 四套並存一套已壞（demo-preflight 指向不存在的腳本）；HITL 證據四個 doc tree 散裝 | lane scripts **KEEP→post-demo 搬家**；jetson-verify **KEEP 當唯一 preflight 引擎**；demo-preflight skill **REWRITE（指標已壞）**；6 個死腳本 **歸檔（立刻）** |

---

## 3. Runtime Data Flow

實際路徑（全部經 code 證據核實，完整 122 條 flow 邊見 ledger 來源資料）：

### 3.1 感知 → Brain → 動作（demo 主鏈）

```
D435 RGB ─┬→ face_identity_node ──/event/face_identity（稀疏轉變事件）──┐
          ├→ vision_perception_node ──/event/gesture_detected ─────────┤
          │                        └──/event/pose_detected ────────────┤
          └→ object_perception_node ──/event/object_detected（5s 類別冷卻）┤
USB mic ──→ stt_intent_node（VAD+ASR 三層）──/event/speech_intent_recognized ┤
                                                                        ▼
                       ┌──────────────── brain_node（唯一 proposer）─────┐
   conversation_graph ─┤  /brain/chat_candidate → re-gate（allowlist →   │
   （LangGraph，預設） │  capability health → cooldown）                  │
                       └────────────── /brain/proposal（SkillPlan）──────┘
                                                                        ▼
                interaction_executive_node（唯一 actuator 出口）
                SafetyLayer.validate → 序列佇列 → SAFETY/ALERT 搶佔
                ├─ SAY    → /tts → tts_node（雙 lane）→ USB 喇叭（demo）/Megaphone
                ├─ MOTION → /webrtc_req（BANNED_API_IDS 過濾）→ go2_driver
                └─ NAV    → action /nav/goto_relative（default-off，4 重 fail-closed）
```

關鍵特性：speech 事件**平行**進 brain_node 和 conversation_graph（兩者都訂閱）；
chat_candidate 只是候選，**一定**被 brain_node 再 gate 一次才成 plan；
/brain/skill_result 回流到 brain_node（plan 生命週期）和 conversation_graph（LLM 記憶）。
回授閉環的弱點：`/state/tts_playing` 是無 id 的 latched Bool（BRAIN-2）。

### 3.2 Nav 鏈（S1 路徑）

```
sllidar /scan_rplidar（~10-11.5Hz）─┬→ AMCL ──/amcl_pose──→ nav_action_server covariance 閘
                                    └→ reactive_stop_node（4-mode）
Studio /api/nav/start → gateway nav FSM → action /nav/goto_relative
  → nav_action_server（cov 閘：>0.5 拒 / 0.3-0.5 只准 ≤0.5m）→ Nav2 → /cmd_vel_nav
twist_mux：emergency 255 > obstacle 200（reactive_stop）> teleop 100 > nav 10（最低）
  → /cmd_vel → go2_driver（零速→StopMove 1003；非零→Move 1008，MIN_X 0.5 地板）
danger zone → gateway cancel goal → paused_confirm（操作員確認續走，無 auto-resume）
```

### 3.3 Studio 觀測路徑

gateway（單 rclpy node spin 於 daemon thread）訂 16+ topics → uuid/ts/source/event_type
envelope → WS `/ws/events` → frontend Zustand stores（50/200 ring buffer，**無持久化**）。
回程：text/skill/gesture toggle/reset/nav 控制走 REST → gateway publish 回 ROS。
盲區：goal 拒絕原因進了 store 但 UI 只在 paused 分支渲染（STUDIO-2）；
晚連上的瀏覽器拿不到 latched topic 快照（無 hello snapshot）。

### 3.4 Deploy / 啟動路徑

```
WSL → pawai jetson deploy →（偏好 ~/sync once【危險，CLI-1】｜內建安全 rsync）
    → ssh colcon build → .pawai-last-deploy
pawai demo start → lock（flock，lane=brain|nav_capability）
    → .claude/skills/*/scripts/start.sh →（SSH 背景化、輸出丟棄【DEVOPS-2】）
    → scripts/start_full_demo_tmux.sh（raw source .env【CRLF 無防線，DEVOPS-3】）
    → 13-window tmux；healthcheck.sh 存在但沒被接上
```

---

## 4. Ownership Boundaries

每個元件「擁有什麼／錯誤擁有什麼／該下放什麼」的濃縮表（逐條證據見 ledger）：

| 元件 | 正當擁有 | 錯誤擁有（代表例） | 該下放給誰 |
|---|---|---|---|
| brain_node | 事件→plan 仲裁、社交/安全觸發規則 | demo 錄影流程控制（demo_phase）；展示字串（zh 表三份拷貝）；LLM execute-mode map 獨本 | demo phase→操作員工具；感知去抖/門檻→Router（v2 ①）；14 flags→policy 表（v2 ③）|
| interaction_executive_node | 唯一 actuator、安全驗證、搶佔 | TTS 完成偵測靠猜（tts_node 沒給 ack，所有權漏進 executor）| ack 契約→tts_node（v2 Phase 3）|
| pawai_brain | LLM 對話、persona、JSON 修復、skill 政策閘 | 與 interaction_executive **雙向循環依賴**（conversation_graph import skill_contract；brain_node lazy import health_loader）| 共用 schema→`pawai_contracts` 新套件 |
| Studio gateway | ROS↔browser 橋、S1 操作員 nav FSM、video bridge | 自己跑 IntentClassifier（sys.path hack）+ 硬編 provider 名；nav goal 生命週期第三套狀態機；地圖真相硬編在前端；無消費者的 _PLAN_MODE | intent→speech lane；nav 狀態真相→nav_action_server；map meta→gateway 讀 Nav2 同一份 yaml |
| CLI | 部署、lock、診斷、face_db 管理 | 招生 demo 內容+直接機器人驅動（api_id 1036 inline rclpy）；tmux 命名真相與 lane scripts 重複；信任未審計 ~/sync | sync→單一審計過的 rsync 契約；school→scripts/或 skill；session 真相→lane manifest |
| face_perception | 偵測/識別/追蹤管線、face_db 模型生命週期 | runtime node `__init__` 裡做 blocking 訓練（空 DB 直接 crash）；GUI 分支在熱迴圈 | 訓練→`pawai face` 工具鏈；presence/unknown 語意→face 端發顯式 state（brain 不該從稀疏事件重建）|
| speech_processor | VAD/ASR 鏈、TTS 合成與播放、echo gate | llm_bridge legacy 模式直接 publish /webrtc_req（繞過 IE）；tts_node 用內容啟發式決定 lane（Brain 層決策漏到播放層）；Megaphone 協議狀態機（DataChannel 狀態屬 driver）| RuleBrain 模板三合一；OpenRouter client 單一實作（llm_client.py）；Megaphone→go2 driver |
| vision_perception | 手勢/姿勢分類、voting、debug 視覺化 | event_action_bridge 從感知套件直接發 Go2 動作+TTS（已死但可誤啟，雙觸發隱患）；nav 域障礙偵測（與 reactive_stop 重複，已停用）| 動作→interaction_executive（已完成，刪殘骸）；手勢 enum→單一共用模組 |
| object_perception | YOLO 推理、letterbox、HSV、debug overlay | 5s 類別冷卻=說話政策的一部分（感知決定 brain 看得到什麼，迫使 harness 硬編常數）| 「何時說」全部→brain；zh 表→單一生成物 |
| nav_capability | goal 編排、cov 閘、路線 FSM、capability 廣播 | —（方向正確）；但 cov 政策三處三個數字（0.3/0.5 硬編 vs 0.45 launch vs 0.20 lib）| 統一進 nav_policy lib；nav_ready Bool→band enum |
| go2_robot_sdk | WebRTC、cmd_vel 安全路由、遙測、TF | reactive_stop/depth_safety（nav 域安全政策住在 driver 套件）；robot.launch.py 內嵌死的 elevenlabs tts_node + 整套 nav/viz bringup；MCP 殭屍 move_service 直發 raw /cmd_vel 繞 mux | 安全政策節點→nav/safety 層（純搬家）；bringup→per-stack launch |
| DevOps/scripts | 啟動編排、清理、quality gates、benchmarks | demo 正確參數活在 launcher 不在套件 config；生產 start/stop 住在 .claude/skills/（agent 目錄成為 load-bearing ops infra）| 預設值→套件 yaml（post-demo flip）；lane scripts→scripts/lanes/ 或 CLI package data |

---

## 5. Architecture Problems

99 條 findings 按類別歸納（編號→ledger）：

- **fragile_runtime（32 條，最大宗）**：核心母題是「**安全與正確性靠紀律不靠 code**」——
  mux teleop 100 > nav 10 只靠 launch flag 防（NAV-4）；auto-resume lunge 路徑仍 live
  只靠 gateway 繞道（NAV-5）；reactive_stop 幾何參數 init-only、`ros2 param set` 靜默
  無效（NAV-3/GO2RT-8）；echo gate 在 robot-playback 失敗路徑黏死（SPEECH-2）；
  deploy/start 鏈三處假成功（CLI-1/2、DEVOPS-2/3）。
- **observability（13 條）**：S1「按了沒反應」是這一類的代表作——拒絕原因三層全吞
  （NAV-2/STUDIO-2）；gate 早退無 trace（BRAIN-8/OBJECT-8）；driver 命令 fire-and-forget、
  ConnectionHealth 零消費者（GO2RT-6）；HITL 證據無 schema 四處散（DEVOPS-7）。
- **duplication（11 條）**：zh 表三份（BRAIN-5）；LLM 鏈雙實作已漂移 temperature 0.8 vs 0.2
  （SPEECH-3）；RuleBrain 模板三份（SPEECH-1）；covariance 政策三個數字（NAV-7）；
  pause/goal 監督三套協議（NAV-6）；mock↔gateway 路由漂移（STUDIO-4）。
- **missing_tests（10 條）**：513 個測試函數不在任何自動 gate（DEVOPS-1/GO2RT-1/CLI-3）；
  擋掉 S1 的 covariance 閘分支零測試（NAV-8）；stt_intent_node 1209 LOC 零直測（SPEECH-5）。
- **dead_code（9 條，~4,400+ LOC）**：state_machine.py+測試 646 LOC（BRAIN-6）、
  router+bridge ~1,030 LOC（VISION-3）、障礙 stack 656 LOC（VISION-6）、語音三舊節點
  768 LOC（SPEECH-7）、MCP 服務（GO2RT-3）、lidar_processor_cpp 1,384 LOC（NAV map）、
  legacy face 腳本 604 LOC（FACE-4）、死腳本 ~750 LOC（DEVOPS-6）。
- **ownership（8 條）**：§4 表已列；根源都是「先長出來、還沒搬家」。
- **overclaim_risk（8 條）**：capability gate 休眠中（BRAIN-10）；contract 手勢 enum 與
  兩條 producer 路徑都不符（VISION-1/4）；docs 寫 sensevoice_cloud 但 code 是 qwen_cloud
  （SPEECH-4）；nav 已建 surface 遠大於已證 envelope（NAV-10）。
- **demo_hack（6 條）**：14 flags（BRAIN-1）、8 層 gate/dedup 跨 3 節點（BRAIN-7）、
  demo 參數只活在 launcher（VISION-2）、地圖 meta 硬編前端（STUDIO-6）、detour 腳本
  危險參數（NAV-9）——全部是已知繃帶，snapshot 有列管。
- **missing_hitl（2 條）**：object A/B env 傳遞鏈未驗（OBJECT-5）、wave bypass FP 率
  未量（VISION-7）。

---

## 6. Demo Snapshot Compatibility

每條 finding 已對照 `docs/pawai-demo/2026-06-10-demo-snapshot.md` 標記
（OBJECT-1 查證改判後）：

| 標籤 | 數量 | 意義 |
|---|---:|---|
| SAFE_TO_REFACTOR_NOW | 32 | 不碰 demo runtime（CI/docs/前端顯示/mock/測試新增/死腳本歸檔），**現在就能開工** |
| POST_DEMO_ONLY | 47 | 動到 demo 部署套件或 runtime 行為，6/18 後 |
| MUST_PRESERVE_FOR_DEMO | 13 | demo 直接依賴，逐字凍結（executive.yaml、start_full_demo_tmux.sh override、gateway nav FSM 語意、地圖 meta、LOCAL_PLAYBACK、mux 紀律、REACTIVE_PROFILE、CLI 硬化語意清單等）|
| NEEDS_HITL | 6 | 需上機才能定論（S1 閘、object A/B 鏈、wave FP、track churn 重調、NAV enabled-path、brain flag-flip smoke）|
| NEEDS_RESEARCH | 1 | WebRTC aiortc/aioice 升級路徑（GO2RT-5，pin 是 load-bearing）|

**S1 補錄相容性（最急）**：解 S1 的三選一中，(A) 0.5m goal 與 (C) 設準 initialpose
都是零 code 改動；audit 新增的觀測修復（nav-control idle 渲染原因 + gateway
result.message 透傳 + covariance band chip）全部 display-only / additive，
被 NAV-2、STUDIO-2 判 SAFE_TO_REFACTOR_NOW —— **可以趕在補錄前上，直接把
「按了沒反應」變成「看得到為什麼被拒」**。(B) 放寬 covariance 閘被 nav 方向評估
明確 REJECT（動零測試的安全字面值、demo 前 8 天、1.1-1.5m 淨空房間）。

---

## 7. Target Architecture（高層）

六個領域的目標形狀（細節在 §8-§13）：

1. **Brain v2**：5 層（Router → ISM → Policy → Executor → Trace），interaction_executive
   原樣保留為第 ④ 層；新增 ROS-free `pawai_contracts` 共用套件破除循環依賴；
   全程 feature flag 可降級回 v1。
2. **Studio v2**：從展示頁變「操作與證據中心」——operator/presentation 模式硬切
   （gateway 端 enforcement）、gateway 拆 5 模組、JSONL trace 持久化 + decision trace
   panel、envelope v2（additive：v/seq/session_id + WS hello 快照）。
3. **CLI v2**：Typer+Rich 增量遷移（新命令先行、lock-bearing 命令最後）、deploy sync
   安全契約（單一 exclude 真相源 + 優先序反轉 + post-sync guard）、雙模式 packaging
   （repo-dev 全功能 / pipx operator 白名單）、PawaiError registry。
4. **感知 stack**：模型全 KEEP；唯一真 A/B 是 object（n@960 → s@640 → s@960 順序）；
   pose 先補 observer 量 two-class、不穩才跑 backend probe；gesture 調參不換模型；
   face_db 生命週期整個搬進 CLI。
5. **Nav stack**：nav_policy lib 統一 covariance 政策（三個數字→一份）；goal 監督
   統一到 nav_action_server（resume_policy=auto|operator_confirm）；reactive_stop 純搬家
   出 driver 套件再做 runtime params；D435 fusion / patrol / lunge 全走 research spec
   不做承諾。
6. **Deploy/preflight/release**：jetson-verify YAML 引擎為唯一 preflight substrate
   （四層：doctor → profile → lane → post-start healthcheck 閘）；HITL 一頁式 gate 模板
   + `docs/hitl/` 落地；證據回收（evidence_pull.sh → benchmarks/results）+
   readiness fail-closed 判定為 release gate。

---

## 8. Brain v2 Direction

（完整方向見 audit 產出的 Brain v2 評估；從現有 PRD **深化**而非重開，已決事項不重議。）

- **LangGraph 判決：CONTAIN，不升格、不替換**。graph 是 stateless-per-invoke 的對話
  管線（5s budget、每句一跑）；仲裁是 10Hz 連續過程 + 搶佔，執行模型不合。pawai_brain
  留作「chat skill 的內臟」，其 proposal 與其他候選一樣進 Policy 層。
- **5 層對應到現有檔案**：① Router = 抽出 brain_node 五個 callback 的 JSON 解析 +
  accumulate timers + dedup（Phase 0，行為凍結、golden fixture 驗證）；② ISM = 整併
  demo_phase / active_plan / PendingConfirm / AttentionMachine / chat_buffer 五個散裝
  狀態碎片，**感知事件永不直接改狀態**，加 plan watchdog（治 6/9 全黑這一類）；
  ③ Policy 表 = 14 flags + gesture map 變異 + LLM allowlist/execute-mode 全收進一張
  宣告式表（LLM 政策移進 SkillContract 欄位，退役 AST parity hack）；④ 不動；
  ⑤ Trace = decision_id 串鏈的 `/brain/trace`（每個 gate 早退都發 suppressed 事件）
  + Jetson 端 JSONL 持久化。
- **前置**：`pawai_contracts` ROS-free 套件（SKILL_REGISTRY + allowlist + zh 表 +
  PerceptionEvent + policy 表 + trace schema），一刀解 BRAIN-4 循環依賴 + BRAIN-5
  三份拷貝——但要 Roy 推翻「三份拷貝是故意的」的舊決定。
- **demo_phase 的未來**：不進 ISM，升格為操作員 scene mask（latched topic，Studio/CLI
  發布，policy 表消費，每次變更本身是 trace 事件）。
- **遷移順序**：contracts 抽取 → Phase 0 Router →（並行）Trace v1 → Phase 1 ISM →
  Phase 2 Policy 表 → Phase 3 TTS ack。每段 feature flag、單行 flip commit、
  executive.yaml 最後動；606 tests 是回歸地板。

## 9. Studio v2 Direction

- **模式分離**：presentation（唯讀、capability chip 綁 trusted baseline）vs operator
  （全控制面）；**enforcement 在 gateway**（mutating endpoints 查 operator credential）
  ——現狀任何拿到 URL 的內網裝置都能叫 12kg 的狗移動，v2 不該繼承。
- **第一張票（pre-demo SAFE）**：S1 可見性三件套——idle 狀態渲染 rejection reason、
  gateway 透傳 result.message、covariance band chip（gateway 已廣播 covariance_xy，
  純前端）。沒有 cov chip，S1 選項 (C)「等 cov 變綠」根本無法操作。
- **Evidence center（主菜）**：gateway 把所有 brain:*/nav/capability envelope 落
  `runtime/studio_traces/{session_id}.jsonl` + export 按鈕；decision trace panel 先拼
  現有三流，Brain v2 ⑤ 落地後直接吃 /brain/trace。
- **Gateway 拆分**（行為不變）：app / ros_bridge / nav_control / evidence / speech 五模組
  + nav_start busy guard（現在第二個 REST 呼叫會 orphan 在飛 goal）+ wait_for_server
  改 to_thread（現在凍 event loop 2s）。
- **Resilience**：per-source freshness heartbeat + staleness chips；WS connect 時 hello
  全量快照（解 latched topic 晚連者問題）；mock 補 /api/nav/* + route-parity pytest
  （結構性防再漂移）。
- **Web vs CLI 鐵律**：Studio 永不 shell out/SSH；CLI 永不渲染 live dashboard；
  共用真相（readiness/scoreboard）抽 shared lib。operator mode 宣告 tablet/laptop 起跳
  （手機點圖設 initialpose 實際不可操作）。

## 10. CLI v2 Direction

- **Ticket #1（週 1 可出貨）**：deploy sync 安全契約——`tools/sync/rsync-excludes.txt`
  單一真相源（CLI 與新 `scripts/sync_to_jetson.sh` 同讀）、`~/sync` 降級顯式 opt-in、
  post-sync protected-file guard（.env 消失→非零 exit+還原指引）、補上「唯一咬過人
  卻唯一沒測」的優先序分支測試。團隊已繞過 CLI deploy，改它零 demo 風險。
- **命令樹補洞**：face delete / object test（包 obj_matrix_cap）/ nav goto（三層硬閘：
  env 開關 + confirm 不可被 -y 跳過 + clamp ≤0.5m；安全邏輯永不寫在 CLI 本地）/
  smoke brain|vision|nav|full / demo preflight / health nav / studio open。
- **Typer 遷移三段**：Phase A 新命令用 Typer sub-app 掛進 Click root（demo 前可做）；
  Phase B 無 lock 語意的 leaf group 逐一搬；Phase C lock-bearing 命令最後（144 tests +
  訊息字串斷言當回歸網，`PAWAI_CLI_V1=1` 可切回）。
- **pipx 雙模式**：repo-dev 全功能 / operator 白名單（純 SSH 命令）；repo-dependent
  命令無 repo 時給明確錯誤不 crash。
- **錯誤模型**：PawaiError registry（stable id + next_steps 至少一條可複製指令）+
  `pawai errors --markdown` 生成 usage-guide §7，測試鎖防文件漂移。
- **post-demo**：demo start 接 healthcheck 閘（pass 才 transition lock 到 running，
  終結 6/4 假成功鏈）；lane-blind cleanup 修復；school 命令遷出；lane scripts 搬家。

## 11. Perception Direction

| 子系統 | 模型判決 | 系統判決 | 關鍵動作 |
|---|---|---|---|
| Face | **KEEP** | TUNE | face_db ghost-dir 黑名單 + jpg 支援 + hash staleness；訓練搬出 runtime node；camera-liveness 欄位；brain 端 event-as-state 重寫屬 Brain v2 ①② |
| Speech | **KEEP** | TUNE+REFACTOR | utterance 所有權收斂（skill_contract 唯一 canned 源 + RuleBrain 三合一 + llm_client 單一實作）；llm_bridge 退役前決策 Ollama 層去留；tts_node 拆解 post-demo |
| Pose | **TUNE 先行** | TUNE | 先補 pose observer → 量 two-class 修法（recall ≥70% gate）→ 不穩才跑 pose_backend_probe（MediaPipe vs yolo26n-pose 同分類器同幀 A/B）；fallen 在 demo profile 結構性關閉=禁講守護 |
| Gesture | **KEEP（recognizer）** | TUNE | 調參協議：min_amplitude_px 50→75 或 reversals 2→3，不動 vote_frames；wave bypass FP 率要量；手勢 enum 單一模組（palm→system_pause 安全路徑經過它）|
| Object | **A-B-TEST（唯一真 A/B）** | TUNE+消費端 REFACTOR | 順序 n@960 → s@640 → s@960；鎖定條件 cup ≥1m 5/5 + ≥4Hz + 溫度正常；曝光鎖定 SOP 先行；**9cm 杯@2m≈21-28px 是物理上限，960 也救不了，2m cup 永遠禁講**；消費端契約 rev（depth_m/instance_id/multi-object）獨立於模型 A/B |

Jetson 8GB 預算（只引實測）：idle 13-window 3.65/7.6GB、告警線 RAM>5.5GB / TEMP>65°C；
nav+全感知互斥（6/7 HITL）；nav+gateway 可共跑（6/10，剩 5.2GB）；任何 A/B 必須在
full demo stack 下量、RAM headroom ≥0.8GB 硬規則。

## 12. Navigation Direction

**Capability ladder（誠實分級，逐級附證據，完整表見 nav 方向評估）**：

| 能力 | 等級 |
|---|---|
| goto_relative ≤0.5m、正面 safe-stop、indoor_tight 去誤擋、log_pose、initialpose 重定位（跳點）、orphan ~10s 自癒 | **HARDWARE_PROVEN**（前二為 DEMO_READY）|
| stop-resume auto | HARDWARE_PROVEN **但 demo 禁用**（lunge 0.21m 貼牆）|
| stop-resume operator-confirm（Studio）| WIRED_RUNTIME（部分 HITL；完整 start→danger→confirm→resume→done 迴圈沒在硬體上跑完過）|
| goto 1m+、goto_named、run_route/K4、IE move_forward | WIRED_RUNTIME / EXISTING_CODE，**零硬體證據** |
| reactive patrol v0、approach-person/object、D435 fusion、動態繞障 | **NOT_BUILT / 禁講** |

- **S1 唯一 pre-demo 事項**：選 (A) 0.5m（推薦主案；離散步進實走 ~0.27m，鏡頭收緊或
  兩個 0.5m 接龍）；(C) initialpose 當 warmup 副案；**(B) 放寬閘 demo 前 REJECT**。
  搭配 SAFE 的原因透傳三件套（server 訊息分流 amcl_no_pose/amcl_red/amcl_yellow_distance
  + gateway 透傳 + UI 渲染）。
- **post-demo 結構**：nav_policy lib（covariance band enum 單一真相，nav_ready Bool→band）；
  goal 監督統一（resume_policy param，gateway FSM 瘦成 server 狀態的 view）；
  reactive_stop 純搬家→runtime params（不在 callback 的參數必須 fail-loud 拒絕）；
  mux 安全從紀律變 runtime guard（teleop publisher watchdog；中期評估
  nav2_collision_monitor 取代自製節點）。
- **research specs（量測決策文件，不是功能承諾）**：lunge 研究（MIN_X 地板 ×
  clearance-conditioned resume × collision_monitor Approach）；D435 fusion ①shadow→
  ②costmap→③detour→④patrol（Roy 6/9 順序 binding）；patrol v0 照 6/9 Phase 1.5 規格。

## 13. Test and HITL Strategy

**四層金字塔綁執行環境**（數字皆實測）：

- **L0 WSL 純 Python（CI fast gate）**：現 35 檔 ~640 funcs → 補進 IE 9 檔、nav_cap 8、
  go2_sdk 4、pawai_cli 6、object 1、jetson-verify 3 → **~1,150+ funcs，全程 <1 分鐘**。
  每個叫 `test/` 的 suite 一個獨立 pytest invocation（套件 top-level `test` 撞名，
  沿用現有兩-invocation 前例）。`test_mux_priority.py` **永不自動化**（真 publisher
  會灌 0.30 m/s，4/26 撞過）。
- **L1 WSL + rclpy（本機）**：IE 4 檔 + reactive_stop node 檔 + pawai_brain 1 檔；
  入口 = ros2-test-suite skill（PACKAGES dict 從 4 擴到 11 目錄）。
- **L2 Jetson colcon + 真感測器**：deploy 後 smoke/probe（colcon test baseline 待一次性
  盤點，NEEDS_HITL）。
- **L3 Go2 HITL（batched session）**：一律走一頁式 gate。

**Preflight 統一**：jetson-verify YAML 引擎為唯一 substrate；四層 = pawai doctor（WSL）
→ verify.py profile（環境）→ lane preflight（動態互斥）→ post-start healthcheck 閘
（6/18 後接進 demo start）。demo-preflight skill 指向不存在的腳本，現在就改寫成指向
verify.py 的薄 runbook。

**HITL 一頁式 gate 模板**（標準化 6/8-6/10 的 de-facto 最佳格式）：header（日期/場地/
deploy SHA/stack）→ precondition（preflight JSON）→ 逐項（指令/測前宣告 pass criteria/
結果 enum `PASS_HW_PROVEN|PASS_SENSING_ONLY|DEGRADED|FAIL|NOT_RUN`/證據路徑）→
claim delta（同步 forbidden-claims）→ spawned backlog（開 issue 不留 prose）。
落地 `docs/hitl/`（需 Roy 核 docs 治理）；**首戰 = S1 補錄 session**；
首批消費者 = 開著的 #132/#133/#134。

**證據回收**：Jetson `test_results/<topic>/<ts>/` 約定 + `scripts/evidence_pull.sh`
收尾回收 → `benchmarks/results/raw|summary`（現為空殼）→ build_scoreboard →
readiness fail-closed 判定 = release gate 核心（現成 code）。

## 14. Refactor Roadmap

```
Wave 0（現在，6/18 前，只做 SAFE_TO_REFACTOR_NOW；demo runtime 一行不碰）
 ├ S1 可見性：UI 渲染拒絕原因 + gateway result.message 透傳 + cov band chip
 │  + server 訊息分流（字串 only）+ gateway 距離 env 化 + detour 腳本 guard
 ├ CLI deploy sync 安全修復全套（exclude 契約/優先序反轉/guard/測試/sync_to_jetson.sh）
 ├ CI/pre-commit 擴張（6 個新 pytest invocations + smart-scope）+ ros2-test-suite dict
 ├ HITL 模板 + docs/hitl/ + smoke profile YAML authoring（不動既有 demo.yaml）
 ├ 文件漂移批次（qwen_cloud 命名/face 閾值與 schema/vision fist→ok 殭屍規則/
 │  contract 殭屍 publisher/AGENT.md 預設值）+ demo-preflight skill 改指 verify.py
 ├ 死腳本歸檔（6 個）+ .tmp/yolo_export 匯出腳本與 hash manifest 入 git
 └ 純測試補齊（stt fallback/face train_model/object HSV/WaveDetector/前端 nav 數學）
Wave 1（6/18 後第 1 週）
 ├ S1 經驗收尾：nav_policy lib + AMCL 閘節點級測試（先鎖現行為再重構）
 ├ CLI v2 spec 2-3（命令樹 Phase A + lane contract）+ demo start healthcheck 閘
 ├ Brain：pawai_contracts 抽取（獨立 PR）+ 死碼第一刀（state_machine 等）
 └ Phase 7 I4（lane preflight YAML 化 + .env loader 統一）
Wave 2
 ├ Brain v2 Phase 0 Router + Trace v1（並行）
 ├ Studio gateway 模組化（行為不變）+ busy guard + to_thread
 └ 感知 HITL batch：object A/B 矩陣 + pose observer/two-class 量測 + gesture 協議
Wave 3
 ├ Brain v2 Phase 1 ISM → Phase 2 Policy 表（分開 PR）
 ├ Studio evidence center（trace 持久化→panel→confidence panels）+ 模式分離
 └ reactive_stop 純搬家 → runtime params
Wave 4
 ├ Brain v2 Phase 3 TTS ack（順手根治 SPEECH-2）
 ├ Speech 收斂：RuleBrain 三合一 → llm_client 單一化 → llm_bridge 退役 → tts_node 拆解
 └ Nav research specs：lunge 研究 / D435 shadow test / patrol v0（全 HITL-gated）
持續：Phase 7 I1-I5 增量（不是最後一個 phase，是貫穿全程的護欄）
```

對應 Roy 的 Phase 編號：Phase 2 Brain v2 spec = Wave 1-3 的 Brain 線；Phase 3 CLI
early slice = Wave 0-1 的 CLI 線（**提前了，照你 6/10 早上的傾向**）；Phase 4 Studio
v2 spec = Wave 2-3；Phase 5 感知 A/B = Wave 2；Phase 6 nav research = Wave 4；
Phase 7 = 貫穿。

## 15. Codex Execution Notes

**現在就能給 Codex 的（全 SAFE，demo runtime 零接觸）**：
1. **CI 擴張批**：ros_build.yaml 新 invocations（每 suite 獨立 PR 或最多兩個低風險
   suite 一批；PR 附 Actions log 證明新 invocation 真的跑且測試數 >0）、pre-commit
   scope（獨立 PR）、ros2-test-suite dict。
2. **S1 可見性批**：nav-control.tsx idle reason 渲染、gateway result.message 透傳、
   cov chip、server 訊息分流（**字串 only，不碰哪個分支觸發**）、
   NAV_DEFAULT_DISTANCE_M env 化、detour guard、send_relative_goal SIGINT 修復。
3. **CLI deploy 安全批**：exclude 契約檔 + 優先序反轉 + post-sync guard + 反向優先序
   測試 + scripts/sync_to_jetson.sh + 文件修正。
4. 文件漂移批、死腳本歸檔批、純測試補齊批（測試 PR 不得夾帶任何行為變更）。

**絕不可同批（彙整自六份方向評估，WritingPlan 必須照抄）**：
- 觀測類（訊息字串/顯示）≠ 政策類（閘值/accept-reject 行為）——rollback 域不同。
- 任何「純搬家」PR（reactive_stop 搬出 driver、gateway 模組拆分、contracts 抽取）
  必須零行為 diff，行為修正疊在搬家之後的獨立 PR。
- Brain Phase 0 Router 抽取**零 gate 語意變更**——任何「順手修 dedup 窗口」都會讓
  73 條 brain-rules 測試失去回歸網意義。
- Trace v1 additive-only，不與 gate 邏輯同批（否則 trace diff 分不出儀表 vs 行為）。
- CI suite 新增 ≠ `--import-mode=importlib` 切換（單變量）。
- deploy sync 修復 ≠ Typer 框架遷移；demo start/stop 任何改動永遠單獨 PR。
- 契約 rev（加欄位，向後相容）≠ 消費端改寫（兩段、各掛 flag）。
- 手勢 enum 正規化不得搭任何 demo 窗口期 PR（palm→system_pause 安全路徑經過它）。

**必須等 HITL 的**（code 可先合但功能不可宣稱）：nav goto / object test CLI 命令、
object A/B 結論、pose backend 結論、wave FP 率、stranger_alert 重啟用、
nav_executor_enabled=true 全鏈、TTS ack 的 Megaphone lane、smoke profile 門檻校準、
修復後 deploy 首跑、post-start healthcheck 閘三模式驗證。

**每 PR 驗證閘**：對應 suite pytest 全綠（基線：IE 258 / pawai_brain 348 / speech 202 /
vision 138 / gateway 64 / CLI 144 / nav_cap 49 / go2_sdk 90）+ `pawai contract check` +
新 core .py blocking flake8 max-line=100 + 涉硬體效果的 PR 掛名 HITL gate。
Codex 只在主 repo 工作；demo 前禁改 `.claude/skills/` 任何檔案。

---

## Top 10 Findings

1. **CLI-1/DEVOPS-4**：`pawai jetson deploy` 偏好未審計 `~/sync`，HITL 實證刪掉 Jetson
   `.env`，團隊已棄用 CLI deploy——唯一咬過人的路徑正是唯一沒測的路徑。SAFE 立修。
2. **NAV-1/NAV-2/STUDIO-2**：S1 blocker 全鏈定位——yellow 閘（0.3<cov≤0.5 只准 ≤0.5m）
   硬編 vs Studio 預設 1.2m；三個 abort 分支同一句 'amcl_lost'，gateway 丟棄
   result.message，UI 只在 paused 分支渲染原因 → 操作員看到「按了沒反應」。
   觀測修復 SAFE，可趕補錄前。
3. **DEVOPS-1/GO2RT-1/CLI-3**：demo 最關鍵 4 套件共 513 個測試函數不在任何 CI/pre-commit
   gate；StopMove 安全路由 11 條測試只靠本機紀律保護。SAFE 立修。
4. **BRAIN-1/BRAIN-3**：~14 個 demo flag + 單一 active_plan 槽 + gate 複製貼上 =
   6/9 stranger 全黑的結構性根因，現在是拔觸發器不是修結構。Brain v2 Phase 1/2 主菜。
5. **BRAIN-2/SPEECH-2**：TTS 無 request_id/ack（SAY 完成靠 Bool 猜，有 settle<合成延遲
   的提前完成 race）+ echo gate 在 robot-playback WAV 失敗路徑黏死（demo 只因
   LOCAL_PLAYBACK=true 而倖免）。Phase 3 一起根治。
6. **VISION-2**：出貨預設 mock+rtmpose 是三重 footgun（裸 launch 會把合成 keypoint
   當真事件發、wave 永不觸發）；demo 行為 100% 活在 start_full_demo_tmux.sh override。
   demo 後翻預設 + 禁 mock+camera 組合。
7. **SPEECH-1/SPEECH-3**：「PawAI 說什麼」碎在 4 套件 5 處（RuleBrain 模板三份拷貝）；
   LLM fallback 鏈雙實作已漂移（temperature 0.8 vs 0.2）；demo 主線離線=直降 canned，
   文件宣稱的本地 LLM 層只存在於 legacy 引擎。
8. **FACE-1/FACE-2**：brain 把稀疏轉變事件當 presence state 用（stranger 真兇的上游）+
   face_db 訓練把所有子目錄當人名（backup 目錄=競爭身份，max-over-samples 比 centroid
   稀釋更糟）。greet 的單點故障。
9. **DEVOPS-2/3、CLI-2**：demo start 假成功鏈——SSH 背景化輸出丟棄、rc-only 判定、
   Jetson 端 raw `source .env` 無 CRLF 防線（6/4 實證）。post-demo 接 healthcheck 閘。
10. **NAV-4/NAV-5/GO2RT-8**：nav 運動安全靠紀律不靠 code——teleop 100 > nav 10 只有
    launch flag 防（5/11 撞牆機制原樣存在）；auto-resume lunge 路徑仍 live（gateway
    繞道是唯一防線）；reactive_stop 幾何參數 runtime 改了靜默無效。

## Recommended Refactor Order

§14 Wave 0-4。一句話版：**先把「看不見」和「沒護欄」修掉（Wave 0：S1 可見性、
deploy 安全、CI 擴張），再動手術（Brain v2 增量五刀），手術全程開著儀表（Trace 先行）
和保險（feature flag + 606 測試地板）**。CLI 線提前與 Brain 研究並行（Codex 串行、
research 並行）。

## First Five Fable Specs

1. **S1 unblock + 可見性 spec**（nav+studio 合一）：0.5m 錄製路徑、gateway 距離 env、
   server 拒絕原因分流、UI 渲染、cov band chip；零閘值變更。〔本週〕
2. **CLI deploy-sync 安全 spec**：exclude 契約、優先序反轉、post-sync guard、
   144 tests 接 CI。〔本週〕
3. **Phase 7 I1+I2 spec**：CI/pre-commit 覆蓋擴張（6 invocations）+ HITL 一頁式模板
   與 docs/hitl/ 落地（S1 session 首用）。〔本週〕
4. **Brain v2 Spec 1：pawai_contracts 抽取**：ROS-free 共用套件破循環依賴、零行為
   變更（需 Roy 先核 open question 1）。〔6/18 後第一刀〕
5. **Brain v2 Spec 2：Phase 0 Perception Event Router**：typed PerceptionEvent +
   in-process router、golden fixture、byte-identical /brain/proposal。〔接續〕

（候補第 6：object model A/B measurement spec——若 Roy 准 6/18 前獨立 session 就升格。）

## First Three Codex Implementation Plans

1. **Plan A「CI 護城河」**：ros_build.yaml 6 個新 pytest invocations（分 PR）+
   pre-commit smart-scope + ros2-test-suite PACKAGES——純 CI/hook，附 Actions 證據。
2. **Plan B「S1 可見性」**：nav-control idle reason + gateway result.message 透傳 +
   cov chip + server 訊息分流（字串 only）+ NAV_DEFAULT_DISTANCE_M env + detour guard
   + send_relative_goal SIGINT 修復——display/additive only，gateway 64 tests +
   nav_cap 49 tests 回歸。
3. **Plan C「deploy 安全」**：rsync-excludes.txt + 優先序反轉 + post-sync guard +
   反向測試 + scripts/sync_to_jetson.sh + usage-guide §2.5 修正。

## Open Questions（Roy 決策清單）

1. **S1 三選一正式拍板**：建議 (A) 0.5m 主案 +（C）initialpose warmup 副案；
   以及：可見性三件套（SAFE）要不要趕在補錄前上？
2. **CLI v2 先行正式拍板**（你 6/10 早上傾向 CLI 先；audit 排程已照此假設）。
3. **`pawai_contracts` 共用套件**：接受新 colcon 套件耦合三個套件的 build、推翻
   「zh 表三份拷貝是故意的」？這是 Brain v2 Phase 1-3 的前置。
4. **capability_gate_enabled** 是否在 v2 預設 true（「只宣稱已驗證能力」從文件規則
   變 runtime 不變量）？
5. **demo_phase 的未來**：升格 operator scene mask（建議）或錄完即刪？
6. **Studio operator enforcement 強度**：token header / 第二 port / 信任內網。
7. **Ollama 本地 LLM 層去留**：搬進 langgraph 主線（+~1GB RAM）/ 留 legacy 至退役 /
   正式放棄離線智能只留 canned。
8. **object A/B 排程**：6/18 前獨立 session（動 demo Jetson 環境的風險）或嚴格 demo 後。
9. **stop-resume 終局**：operator-confirm 永久化（刪 auto-resume）或留 resume_policy=auto
   給大場地——決定 lunge 研究值不值得開。後續安全層投資：強化自製 reactive_stop
   vs 遷移 nav2_collision_monitor。
10. **HITL 證據治理**：新開 `docs/hitl/`（docs-convention 變更需你核）+ raw artifacts
    進 git 的粒度（全 commit vs 只 summary）。
11. **lane scripts 永久位置**：CLI package data（支援 pipx operator demo start）vs
    scripts/lanes/（repo 慣例）。
12. **`~/sync` 與 demo school 命運**：完全移除 vs opt-in 降級；school 遷出或棄用。
