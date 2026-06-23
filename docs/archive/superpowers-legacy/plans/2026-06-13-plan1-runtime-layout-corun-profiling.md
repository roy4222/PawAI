# Plan 1 — Runtime Layout / Co-run Profiling（S1 runtime layout 決策閘）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫 ID：**plan1**　角色：**Cloud / Fable = planner + reviewer；Codex = builder**
> 隸屬：PawAI Demo Flow Reliability Sprint（Cloud A）｜權威總綱：[2026-06-13-pawai-pre618-final-execution-plan.md](2026-06-13-pawai-pre618-final-execution-plan.md)（§2 supersede 全部 source docs）
> 本份負責 **Q2**：S1 runtime layout 決策。**全程 NO-MOTION**（不發 `goto_relative` / `cmd_vel` / 任何 motion；只量資源 + topic 健康）。

> **既有真相來源（只引用、不重寫）**：
> - [demo-flow-reliability-master-plan](2026-06-13-demo-flow-reliability-master-plan.md)（§2.2 8GB 互斥、§2.3 五幕能力快照）
> - [nav-capability-ladder](../navigation/2026-06-13-nav-capability-ladder.md)（C1–C12 能力標籤）
> - [nav-618-claim-wording](../navigation/2026-06-13-nav-618-claim-wording.md)（S1–S8 可講 / F1–F10 禁講）
> - [nav-incident-runbook](../navigation/2026-06-13-nav-incident-runbook.md)（T0 TF authority、no-motion diagnostics §9）
> - `jetson-status` skill（`/home/roy422/.claude/skills/jetson-status/SKILL.md`，tegrastats/free/thermal snapshot + 30s monitor）

> **跨計畫依賴**：本計畫 **決定 S1 runtime layout 策略**，被以下計畫消費：
> - **plan6（nav）**：S1 第一幕 stack 形態（駐留/換 stack/operator-assisted/影片）的硬前置。本計畫 §11 的「4-branch 決策樹」是 plan6 的輸入。
> - **plan2（conductor / S1 phase）**：s1_nav 幕在 conductor 的呈現（live nav vs Studio evidence vs 影片）依本計畫結論。
> - 本計畫 **不重複** plan6 的 nav 參數鎖定（indoor_tight）、initialpose SOP、motion gate（n=3）；**不重複** plan2 的 `demo_phase` 詞彙與切幕清理。

---

## 1. Goal

用一個 **P0 no-motion co-run profiling 閘門**，量測三個 runtime 配置（A / B / C）的資源（RAM/CPU/GPU/溫度）、延遲、topic Hz，**據此用一棵 4-branch 決策樹選定 6/18 第一幕（S1）的 runtime layout**，而**不預設** nav stack 與 brain stack 是否必須互換。

具體交付：
1. **可執行的 profiling 程序 + 腳本**（tegrastats / free / thermal + `ros2 topic hz` + `jetson-status` snapshot），三配置各跑 3–5 分鐘、**零 motion**。
2. **明確的 watch topic 清單 + 明確 pass threshold**（RAM headroom、溫度、topic Hz、無 node crash、Foxglove 不壓垮 gateway）。
3. **4-branch 決策樹**（C 穩 / B 穩-C 不穩 / B 不穩 / brain baseline 不穩）→ 落成一張 S1 runtime layout 決策表，交給 plan6 + plan2 消費。
4. **8GB 互斥事實表 + brain stack cold-start 成本**（給現場交接時間預算）。

**誠實底線**：本計畫產出的能力分級一律 `proven / needs-HITL / research-only`。profiling 結果在 Roy 在場真機跑出來前一律 `needs-HITL`；對外 nav claim 全部走 [claim-wording](../navigation/2026-06-13-nav-618-claim-wording.md) S1–S8 / F1–F10，**不得**因 profiling 結果而宣稱 autonomous navigation / 即時 SLAM / 動態繞障。

---

## 2. Current state（cite code where known）

### 2.1 兩個 stack 的實體組成（profiling 配置基礎）

**Brain demo stack**（`scripts/start_full_demo_tmux.sh`，13 window）：
- `go2`（go2_robot_sdk robot.launch WebRTC）、`camera`（realsense rs_launch）、`face`（`face_perception.launch.py`：YuNet+SFace CPU）、`vision`（`vision_perception.launch.py`：RTMPose lw CUDA + MediaPipe Hands CPU，`gesture_backend:=recognizer` override）、`executive`（`interaction_executive.launch.py enable_fallen:=false`，`start_full_demo_tmux.sh:177`）、`asr`（`stt_intent_node`，SenseVoice+Whisper warmup ~12s）、`tts`（`tts_node`，`start_full_demo_tmux.sh:206`）、`llm`（`pawai_conversation_graph.launch.py` 或 legacy `llm_bridge_node`）、`camtf`（static TF base_link→camera_link）、`depth_safety`（`depth_safety_node` → `/capability/depth_clear` @5Hz，`start_full_demo_tmux.sh:269`）、`fox`（foxglove_bridge port 8765，`best_effort_qos_topic_whitelist`）、`object`（`object_perception.launch.py`，YOLO26n TRT FP16）、`gateway`（`pawai-studio/gateway/studio_gateway.py` port 8080，`start_full_demo_tmux.sh:289`）。
- Studio frontend（`pawai-studio/start.sh` → port 3000）通常跑在筆電 / WSL，不佔 Jetson 8GB；profiling 只計 gateway（port 8080）在 Jetson 上的占用。

**Nav stack**（`scripts/start_nav_capability_demo_tmux.sh`，9 window）：
- `tf`（static_transform_publisher base_link→laser yaw=π，`start_nav_capability_demo_tmux.sh:72`）、`sllidar`（`sllidar_node` → `/scan_rplidar`，`:77`）、`d435`（realsense align_depth，`:84`）、`robot`（`robot.launch.py nav2:=true slam:=false map:=$MAP`，`:90`）、`reactive`（`reactive_stop_node` profile=`$REACTIVE_PROFILE` mode=progressive，`:111`；參數見 `start_nav_capability_demo_tmux.sh:37` `REACTIVE_PROFILE=open_space|indoor_tight`）、`navcap`（`nav_capability.launch.py`，6 nodes 含 capability_publisher + depth_safety，`:118`，`covariance_threshold:=0.45`）、`pause-enable`（`:125`）、`foxglove`（foxglove_bridge port 8765，`:128`）、`monitor`（`:133`）。

### 2.2 8GB 互斥事實（已知，本計畫量化驗證）

- master plan §2.2：「nav stack 與 brain demo stack **8GB 互斥**（不能同跑）→ S1 是獨立鏡頭」。
- jetson-status skill RAM 預算（`SKILL.md` Resource budgets 表）：總 7.4 GB；warning 5.5–6.5 GB；**critical > 6.5 GB**。
- 兩 stack 各自含一個 realsense（D435）driver（~600 MB）；nav 另含 nav2 lifecycle（amcl + map_server + planner + controller + bt_navigator）。**本計畫的 C 配置 = brain stack + nav stack 同跑，要量的就是「會不會 OOM」這件事到底是不是真的。**

### 2.3 6/13 EOD 硬體狀態（profiling 前置）

- master §2.2 / [nav-incident-runbook](../navigation/2026-06-13-nav-incident-runbook.md) §2.3：Jetson 上 nav stack 還在跑（tmux `nav-cap-demo` 9 windows）；剛發生 Go2 撞擊（`goto_relative 0.3m` 走歪撞牆、Roy e-stop）；D435 **Right MIPI error / Hardware Error**。
- ⟹ profiling **第一件事是清場**（見 §7 J-0），且 **C 配置可能因 D435 故障而退化**（nav 不需 D435，但 brain face/vision 需要；profiling 要記錄 D435 是否在線，並把 D435 缺席視為一個量測變因，不是 fail）。

### 2.4 nav motion 仍 NOT_DEMO_READY（不被本計畫改變）

- [nav-incident-runbook](../navigation/2026-06-13-nav-incident-runbook.md)：T0（go2.urdf `map_joint`/`odom_joint` fixed → `/tf_static` 與 AMCL/driver 動態 TF 雙 authority）、R1（AMCL yaw injection）、R2（0.5m→1.04m 超衝）多因未解。
- 本計畫 **不碰 motion、不解 T0/R1/R2**（那是 plan6 + nav incident plan 的事）。本計畫只回答「**stack 怎麼擺**」，所有結論一律以 **NO-MOTION** 為前提；即使 C 穩，S1 也**不啟 `goto_relative`**，map/LiDAR/pose 只當**視覺證據**。

---

## 3. Scope

- **量**：三配置（A/B/C）的 RAM/CPU/GPU/溫度/延遲/topic-Hz，各 3–5 分鐘，零 motion。
- **決**：4-branch 決策樹 → S1 runtime layout 決策表。
- **寫**：profiling 腳本（pure-software，WSL 可寫可單測，Jetson 上執行）+ 程序文件 + 8GB 互斥事實表 + brain cold-start 成本表。
- **交棒**：決策結論餵 plan6（nav stack 形態）、plan2（S1 phase 呈現）。

## 4. Forbidden scope

- ❌ **任何 motion**：不發 `goto_relative` / `cmd_vel` / `/nav/goto_*` / Move(1008) / 任何會動 Go2 的指令。配置 C 啟 nav stack 但**不發 goal、不設會觸發移動的東西**（只設 `/initialpose` 做 AMCL 健康觀察，AMCL 純定位不動腿）。
- ❌ 不改 `start_full_demo_tmux.sh` / `start_nav_capability_demo_tmux.sh` / `executive.yaml` / `.claude/skills/`（profiling 用**唯讀 attach**：另開 ssh session 跑 snapshot + `ros2 topic hz`，不動既有腳本）。
- ❌ 不解 T0/R1/R2/R3/R5（plan6 + nav incident plan）。
- ❌ 不做 nav 參數鎖定 / initialpose SOP / motion gate n=3（plan6）。
- ❌ 不做 `demo_phase` 詞彙 / 切幕清理 / canned phrase（plan2 / fallback plan）。
- ❌ 不放寬 AMCL covariance 門檻（plan6 §5 hardline）。
- ❌ 不宣稱 autonomous navigation / 即時 SLAM / 動態繞障 / D435 已融合進 Nav2 costmap / fallen detection / 2m 物體 / 可靠顏色 / 19 色。
- ❌ 不 flip 任何 secure-default（route_id sanitize 歸 Security plan；本計畫不碰）。
- ❌ profiling 腳本**不得**把 supervision/metrics 等重函式庫帶進 Jetson runtime（master B-4 / Reader C iron rule：supervision 永不進 runtime）；本腳本只用 `free`/`tegrastats`/`/sys` 讀檔 + `ros2 topic hz`，零額外重依賴。

---

## 5. Tasks

> 標記：`task_type` = `pure_software` | `jetson`（no-motion）| `go2_motion`。每項含 P0/P1/P2、exact files、exact tests、rollback、demo impact、needs_roy、needs_go2_motion。
> **本計畫零 go2_motion 任務**（全 NO-MOTION，符合 Q2 / Gotcha #5）。

### T1 — profiling harness 腳本（pure_software，可 WSL 寫 + 單測）

- **id**：T1
- **task_type**：`pure_software`
- **優先級**：**P0**
- **exact files to touch**：
  - 新增 `scripts/corun_profile.sh`（profiling orchestrator：跑 N 個 sample interval，每 interval 抓 jetson snapshot + 一組 `ros2 topic hz` window）
  - 新增 `scripts/corun_profile_parse.py`（把 raw snapshot log 解析成一張 CSV + pass/fail 判定表）
  - 新增 `scripts/corun_topics.txt`（每配置要 watch 的 topic 清單，see §9）
  - 新增 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`（程序文件 + 決策樹 + 結果模板，文件部分）
- **exact tests**：
  - 新增 `scripts/test_corun_profile_parse.py`（pytest，pure-python，無 ROS/無硬體）：
    - `test_parse_ram_from_free_block`：餵一段 `free -h` fixture → 解析出 used GB 正確。
    - `test_parse_temp_max`：餵 thermal_zone fixture（多個 zone）→ 取最大溫度正確。
    - `test_parse_gpu_load`：餵 `/sys/devices/gpu.0/load` fixture（值如 `910`）→ 91.0%。
    - `test_passfail_ram_headroom`：used=6.7GB → critical fail；used=5.0GB → pass；used=6.0GB → warning。
    - `test_oom_abort_sustained_only`：餵一串 sample，單一 spike 6.6GB 後回落 → **不** emit ABORT（只 WARNING）；連續 >6.5GB 跨 ≥10s（依 interval 換算的連續 sample 數）→ emit `OOM-RISK ABORT`（驗 10s sustained 規則，非瞬時）。
    - `test_passfail_topic_hz_band`：`/scan_rplidar` 量到 9.6Hz（期望 ~10Hz ±20%）→ pass；量到 3Hz → fail。
    - `test_passfail_node_crash`：snapshot N 的 `ros2 node list` 比 baseline 少了一個 node → fail（crash 偵測）。
    - `test_config_label_required`：parser 收到無 `config=A|B|C` label → 報錯（防止 A/B/C 結果混淆）。
  - 命令：`cd /home/roy422/newLife/elder_and_dog && python3 -m pytest scripts/test_corun_profile_parse.py -v`
- **rollback**：`git rm scripts/corun_profile.sh scripts/corun_profile_parse.py scripts/corun_topics.txt scripts/test_corun_profile_parse.py docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md && git checkout -- .`（純新增檔案，刪除即回復；不動任何既有檔，byte-identical）
- **demo impact**：無（純工具，不進 demo runtime；不改 demo 腳本）。
- **needs_roy**：否（寫 + 單測 AFK 可做）。
- **needs_go2_motion**：否。

### T2 — 配置 A profiling run（brain-full baseline，jetson no-motion）

- **id**：T2
- **task_type**：`jetson`（no-motion）
- **優先級**：**P0**
- **exact files to touch**：無 code 改動；產出 `runtime/profiling/2026-06-13-configA.csv` + `runtime/profiling/2026-06-13-configA.log`（profiling 產物，寫 `runtime/`，**已在 rsync excludes**，見 CLAUDE.md「deploy 的 rsync `--delete` 曾整棵轟掉 runtime/」）。
- **程序**：`bash scripts/start_full_demo_tmux.sh`（brain 全 stack）→ 等 ASR warmup ~60s → 另開 ssh session 跑 `bash scripts/corun_profile.sh --config A --duration 300 --interval 15`。
- **exact tests / acceptance**（§9 thresholds 之 A 列）：無 OOM；brain `/tts` 可發、trace 寫得出、gateway(8080) alive、object `/perception/object/debug_image` 出圖、face 偵測得到、無 node crash、RAM headroom ≥ 0.8GB、溫度 < 80°C。
- **rollback**：`bash scripts/clean_full_demo.sh`（清 brain 全環境）；profiling 產物 `rm -f runtime/profiling/2026-06-13-configA.*`。
- **demo impact**：無（baseline 量測；若 A 不穩 = 必須先修 brain demo，nav 不談，決策樹 branch 4）。
- **needs_roy**：**是**（Jetson 真機 + 在場判讀 D435/喇叭/face）。
- **needs_go2_motion**：否（Go2 driver 連線但不發 motion；確認 e-stop 就位但本配置不動腿）。

### T3 — 配置 B profiling run（brain + raw-LiDAR + Foxglove，jetson no-motion）

- **id**：T3
- **task_type**：`jetson`（no-motion）
- **優先級**：**P0**
- **exact files to touch**：無 code 改動；產出 `runtime/profiling/2026-06-13-configB.csv` + `.log`。
- **程序**：A 配置已起 → **不關 brain** → 另開 window 起 raw LiDAR（`ros2 run sllidar_ros2 sllidar_node ... -r /scan:=/scan_rplidar`，與 nav 腳本 `:78` 同參數）+ static TF base_link→laser（`:72`，yaw=π）+ 一個額外 foxglove subscribe `/scan_rplidar`。**不起 nav2 / amcl / reactive_stop**（B = raw LiDAR + Foxglove 視覺證據，無導航計算）。→ 跑 `bash scripts/corun_profile.sh --config B --duration 300 --interval 15`。
- **exact tests / acceptance**（§9 thresholds 之 B 列）：A 列全過 + `/scan_rplidar` Hz ~10（±20%）+ Foxglove 加入後 gateway(8080) 仍 alive、`/tts` 延遲未顯著惡化、RAM headroom 仍 ≥ 0.8GB、無 node crash。
- **rollback**：先 `pkill -9 sllidar` + 關掉額外 foxglove window；brain stack 維持或 `bash scripts/clean_full_demo.sh`。
- **demo impact**：B 穩 = S1 可走「brain 駐留 + raw LiDAR/Foxglove 當視覺證據 + operator-assisted」（決策樹 branch 2）。
- **needs_roy**：**是**。
- **needs_go2_motion**：否。

### T4 — 配置 C profiling run（brain + full-nav-stack 同跑，jetson no-motion）

- **id**：T4
- **task_type**：`jetson`（no-motion）
- **優先級**：**P0**
- **exact files to touch**：無 code 改動；產出 `runtime/profiling/2026-06-13-configC.csv` + `.log`。
- **程序**：**這是壓力上限測試**。brain stack 已起（A）→ 另起完整 nav stack：`REACTIVE_PROFILE=indoor_tight bash scripts/start_nav_capability_demo_tmux.sh`（indoor_tight 與 demo 場地一致；理由見 plan6，本計畫只沿用不重定義）。⚠️ **C 啟 nav2 + amcl + reactive_stop 但全程不發 goal、不發 cmd_vel**；可設 `/initialpose` 觀察 AMCL 收斂（純定位，不動腿）。→ 跑 `bash scripts/corun_profile.sh --config C --duration 300 --interval 15`。
- **exact tests / acceptance**（§9 thresholds 之 C 列）：A+B 列全過 + nav `/state/nav/heartbeat` 1Hz、`/state/nav/status` 10Hz、`/state/nav/safety` 10Hz、`/scan_rplidar` ~10Hz **同時** brain `/tts`/face/object 都還活 + RAM **不 OOM 且 headroom ≥ 0.8GB** + 溫度 < 80°C + 無 node crash + Foxglove 不壓垮 gateway。
- **rollback**：`bash scripts/clean_full_demo.sh && pkill -9 -f nav_capability; pkill -9 reactive_stop; pkill -9 sllidar`（兩 stack 都清；遵 CLAUDE.md 多 driver instance 殘留逐一 pkill）。
- **demo impact**：**C 穩 = S1 可避免換 stack**（brain + nav 同跑，map/LiDAR/pose 當視覺證據，**仍不發 goto_relative**）；C 不穩 = 退 branch 2/3。
- **needs_roy**：**是**（最高風險配置，必須在場盯 RAM 與溫度，OOM 立即清場）。
- **needs_go2_motion**：否（nav stack 起來但零 goal/零 motion；e-stop 就位作為硬保險）。

### T5 — 4-branch 決策樹判讀 + S1 runtime layout 決策表（pure_software / 文件）

- **id**：T5
- **task_type**：`pure_software`（判讀 + 寫決策表；數據來自 T2–T4）
- **優先級**：**P0**
- **exact files to touch**：`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`（補 §決策樹結果 + 決策表 + 8GB 互斥事實 + cold-start 成本）。
- **exact tests**：文件 review（無自動測試適用）；但**交叉驗證**：決策表每一格的「可講話術」必須能對映 [claim-wording](../navigation/2026-06-13-nav-618-claim-wording.md) S1–S8 / F1–F10（Cloud review checklist §「overclaim 掃描」逐句檢）。決策表的數字（RAM/溫度/Hz）必須等於 T2–T4 CSV，不得自編。
- **rollback**：`git checkout -- docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`（回到 T1 寫入的模板版本）。
- **demo impact**：**這張表是 S1 runtime layout 的決定**，plan6 + plan2 直接消費；錯了會讓 S1 走錯路（押 live nav 撞牆 / 或過度保守退影片）。
- **needs_roy**：**是**（最終 branch 選定需 Roy 在 6/17 彩排根據實機數據拍板；本計畫提供決策樹，Roy 拍板落點）。
- **needs_go2_motion**：否。

### T6 — brain stack cold-start 成本量測 + 8GB 互斥交接時間（jetson no-motion）

- **id**：T6
- **task_type**：`jetson`（no-motion）
- **優先級**：**P1**（決策樹不依賴它，但現場交接旁白需要）
- **exact files to touch**：`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`（補 cold-start 成本表 + 交接時間預算）。
- **程序**：量 `bash scripts/clean_full_demo.sh` → `bash scripts/start_full_demo_tmux.sh` → 到 `/tts` 可發、face 出圖、ASR warmup done 的牆鐘時間（含 ASR warmup ~12s、object TRT cache hit、gateway up）。同量 nav stack stop→start 到 `/state/nav/heartbeat` 1Hz 的時間。⟹ 推出「S1(nav) 結束 → S2(brain) 開始」的 8GB 交接最短間隔（master open question：1 分鐘 gap 是否需旁白解釋）。
- **exact tests / acceptance**：產出兩個牆鐘數字（brain cold-start s、nav cold-start s）+ 交接間隔建議（s）；數字寫入 CSV `runtime/profiling/2026-06-13-coldstart.csv`，與文件表一致。
- **rollback**：`bash scripts/clean_full_demo.sh`；`rm -f runtime/profiling/2026-06-13-coldstart.csv`。
- **demo impact**：交接時間決定 runbook 旁白（plan2 / runbook plan 消費）；不阻 S1 決策。
- **needs_roy**：**是**（Jetson 真機計時）。
- **needs_go2_motion**：否。

---

## 6. Pure software tasks（可 WSL AFK，不需硬體）

- **T1**（profiling harness 腳本 + parser + 單測 + 程序文件骨幹）：**完全可 AFK**，WSL 寫 + `pytest` 綠。Codex 先做這項。
- **T5**（決策樹判讀 + 決策表）：**寫模板可 AFK**（T1 文件骨幹即含空決策表）；**填數字需 T2–T4 真機跑完**。
- 所有 pure-software 產物都是**純新增檔案**，零既有檔改動 ⟹ byte-identical 退路 = 刪檔即回復；對 ~955 回歸測試零影響。

## 7. Jetson tasks（no-motion）

> **共通前置 J-0（不可省）**：開工第一件事 = 確認 Go2 停穩（Roy e-stop 在手）+ `pawai demo stop` 清場 + `pkill -9 -f nav_capability; pkill -9 reactive_stop; pkill -9 sllidar`（清掉 6/13 EOD 殘留的 nav-cap-demo 9 windows）+ `ros2 node list` 確認乾淨。對映 [roy-hitl-queue](../archive/runbook-legacy/2026-06-13-roy-hitl-queue.md)。

- **J-0**：清場（見上）。`needs_roy`=是；`needs_go2_motion`=否。
- **T2**：配置 A run（brain-full baseline）。
- **T3**：配置 B run（brain + raw-LiDAR + Foxglove）。
- **T4**：配置 C run（brain + full-nav-stack 同跑）。
- **T6**：cold-start + 交接時間。

> **8GB 互斥操作紀律 + OOM abort 精確規則**：T4（C 配置）是唯一兩 stack 同跑的點，**Roy 必須全程盯 RAM**。`corun_profile.sh` 的 OOM abort **以「持續 >6.5GB 達 10s」為準，非瞬時 spike**：parser/harness 維持一個 **10s 移動平均（moving average）**（或連續 sample 視窗，interval 15s 時取最近 ≥1 個完整視窗 + 即時值雙確認），**只有當 RAM used 連續 >6.5GB 超過 10s** 才 `echo "OOM-RISK ABORT"` 並停止 sample loop（**不自動殺 stack**，由 Roy 決定清場）。**瞬時觸頂（touch 6.6GB 一次後回落 <6.5GB）不 abort，只記 WARNING**。Codex 實作：harness 端保留滑動視窗、判「sustained >6.5GB ≥10s」才 emit ABORT；§9.2 的 RAM FAIL 門檻（>6.5GB）用於**最終 stable/unstable 判定**（取量測期 sustained 峰值），abort 只是「現場安全煞車」、不等於該配置自動判 FAIL（abort 後 Roy 可清場重判）。
> **D435 故障處置**：若 D435 Right MIPI 仍故障，C 配置記錄「D435 absent」為變因（nav 不需 D435），不視為 fail；face/vision 在無 D435 時的行為另記。

## 8. Go2 HITL tasks（motion, e-stop）

**本計畫無 go2_motion 任務。** 全部配置（A/B/C）皆 NO-MOTION：Go2 driver 可連線、可設 `/initialpose`，但**不發任何 motion 指令**。e-stop 全程就位**僅作硬保險**（C 配置 nav stack 起來但零 goal）。

> ⚠️ 與 plan6 的界線：**任何 `goto_relative` / `DriveOnHeading` / cmd_vel motion 都不在本計畫**。本計畫量完「stack 能不能共存」後，motion gate（T0 fix + D1–D5 + θ_error<5° + e-stop + n=3）整段歸 plan6，Roy 另行授權。

---

## 9. Tests（watch topics + pass thresholds）

### 9.1 每配置要 watch 的 topic（`scripts/corun_topics.txt`）

| Topic | 期望 Hz | 出現於配置 | 來源 |
|-------|:------:|:----------:|------|
| `/state/perception/face`（人臉狀態） | ~10 Hz | A,B,C | CLAUDE.md 人臉主線 |
| `/face_identity/debug_image` | ~6 Hz | A,B,C | MEMORY 3/18 smoke |
| `/perception/object/debug_image` | ~6–8 Hz | A,B,C | CLAUDE.md object §驗證 |
| `/event/object_detected` | event（≥1 次/分） | A,B,C | CLAUDE.md object |
| `/tts`（發布即量得到延遲） | on-demand | A,B,C | CLAUDE.md 快速驗證 TTS |
| `/capability/depth_clear` | ~5 Hz | A,B,C | `depth_safety_node` |
| `/vision_perception/status_image` | ~8 Hz | A,B,C | CLAUDE.md 視覺儀表板 |
| `/scan_rplidar` | ~10 Hz | **B,C** | nav 腳本 `:78` |
| `/state/nav/heartbeat` | 1 Hz | **C** | nav monitor block |
| `/state/nav/status` | 10 Hz | **C** | nav monitor block |
| `/state/nav/safety` | 10 Hz | **C** | nav monitor block |
| `/capability/nav_ready` | ~1 Hz | **C** | nav monitor block |

> **容差頻帶（單一定義，§9.1 期望值 × §9.2 band）**：本表「期望 Hz」是中心值，**判定一律走 §9.2 的單一頻帶 = PASS 在期望 ±20% / WARNING 期望 ±20–40% / FAIL 偏離 >40% 或 0**。§9.1 不另立容差數字（避免 ±20% vs ±40% 兩套不一致）；所有 topic 共用同一 band。
> `ros2 topic hz` 跑法：每 sample interval 對清單每個 topic 跑 `timeout 6 ros2 topic hz <topic>` 取平均（6s 視窗，足夠收斂；遵 CLAUDE.md「BEST_EFFORT sub 要多次發」不適用此處因 hz 是被動量測）。`/tts` 延遲量法：發 `ros2 topic pub --once /tts std_msgs/msg/String '{data: "測試"}'` 記到喇叭/Megaphone 出聲的牆鐘（或 local playback log 時間戳），**不影響量資源**。

### 9.2 pass thresholds（parser 判定，`corun_profile_parse.py`）

| 指標 | PASS | WARNING | FAIL | 來源 |
|------|:----:|:-------:|:----:|------|
| RAM used（of 7.4 GB） | < 5.5 GB | 5.5–6.5 GB | **> 6.5 GB（OOM-risk）** | jetson-status budget |
| RAM headroom | ≥ 1.9 GB | 0.9–1.9 GB | **< 0.8 GB** | jetson-status budget + Jetson 記憶體預算 §≥0.8GB |
| GPU load | < 95% | 95–99% | 100%（throttle） | jetson-status budget |
| 溫度（max zone） | < 65°C | 65–80°C | **> 80°C** | jetson-status budget |
| 功耗 | < 12W | 12–15W | > 15W（MAXN limit） | jetson-status budget |
| topic Hz（每 watch topic） | 期望 ±20% | ±20–40% | **偏離 > 40% 或 0** | §9.1 期望值 |
| node crash | `ros2 node list` 與 baseline 一致 | — | **少任一 node** | crash 偵測 |
| `/tts` 延遲 | 與 A baseline 比 ≤ +30% | +30–60% | > +60% 或無聲 | 相對 baseline |
| gateway(8080) | curl `/health` 200 | — | 連線 refused / 逾時 | Foxglove 不壓垮 gateway |

> **配置 pass = 全列 PASS 或最多 WARNING 且無 FAIL**。任一 FAIL ⟹ 該配置判 unstable。

### 9.3 pure-software 單測（T1，無硬體）

見 §T1「exact tests」八條 pytest。命令：`python3 -m pytest scripts/test_corun_profile_parse.py -v`（必須全綠才算 T1 done）。

---

## 10. Rollback

| 任務 | rollback 指令 |
|------|--------------|
| T1（腳本） | `git rm scripts/corun_profile.sh scripts/corun_profile_parse.py scripts/corun_topics.txt scripts/test_corun_profile_parse.py docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`（純新增，刪即回復，byte-identical） |
| T2（A run） | `bash scripts/clean_full_demo.sh` + `rm -f runtime/profiling/2026-06-13-configA.*` |
| T3（B run） | `pkill -9 sllidar` + 關額外 foxglove window；`bash scripts/clean_full_demo.sh` + `rm -f runtime/profiling/2026-06-13-configB.*` |
| T4（C run） | `bash scripts/clean_full_demo.sh && pkill -9 -f nav_capability; pkill -9 reactive_stop; pkill -9 sllidar` + `rm -f runtime/profiling/2026-06-13-configC.*` |
| T5（決策表） | `git checkout -- docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md` |
| T6（cold-start） | `bash scripts/clean_full_demo.sh` + `rm -f runtime/profiling/2026-06-13-coldstart.csv` |

> **全域保守退路**：本計畫**不改任何 demo runtime 行為**（只新增 profiling 工具 + 文件）。最壞情況 = profiling 沒跑成 ⟹ S1 直接走決策樹 branch 3（third-person + Studio brain only + map/LiDAR 影片/截圖），這是 master plan 既有的最保守 S1 fallback，零新風險。

---

## 11. Done criteria

1. **T1 綠**：`scripts/corun_profile.sh` + `corun_profile_parse.py` + `corun_topics.txt` 寫好，`pytest scripts/test_corun_profile_parse.py -v` 八條全綠。
2. **T2–T4 三配置各跑 ≥ 3 分鐘**，產出 `runtime/profiling/2026-06-13-config{A,B,C}.csv`，parser 判定每配置 stable/unstable。
3. **4-branch 決策樹落點**：依下表，Roy 在 6/17 彩排根據實機 CSV 拍定 S1 runtime layout，寫進 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md` 決策表。
4. **8GB 互斥事實 + brain cold-start 成本 + 交接時間**（T6）寫入文件。
5. **決策表每句話術過 claim-wording 掃描**（無 F1–F10 禁語、無 autonomous/即時 SLAM/動態繞障）。
6. plan6 / plan2 引用本決策表時，本計畫已凍結（6/17 18:00 前）。

### 11.1 4-branch 決策樹（Q2 鎖定，本計畫核心交付）

> **「stable / unstable」的精確定義（無模糊）**：一個配置 `stable` = §9.2 **每一指標都是 PASS，或最多 WARNING 且零 FAIL**；`unstable` = **任一指標 FAIL**。FAIL 的精確門檻直接引 §9.2：RAM used >6.5GB、RAM headroom <0.8GB、溫度 >80°C、任一 watch topic Hz 偏離期望 >40% 或 0、任一 node crash、`/tts` 延遲 >+60% 或無聲、gateway(8080) 連線 refused。**判讀者不得自行加減門檻**——只查 §9.2 表格逐列。

```
量完 A/B/C（NO-MOTION）後，自上而下取第一個 match 的 branch：

┌─ branch 4 "BRAIN-FIRST"：A（brain baseline）unstable
│     觸發 = A 配置任一 §9.2 指標 FAIL（如 RAM used >6.5GB / 溫度 >80°C /
│            brain topic（face/object/tts）任一 crash 或 Hz 偏離 >40%）。
│     → 先修 brain demo，nav 完全不談。S1 退第三人稱 + Studio brain only，
│       map/LiDAR 走影片/截圖。（若 A unstable，B/C 不必再判，直接此 branch。）
│
├─ branch 1 "C-CORESIDENT"：A stable 且 C（brain + full-nav-stack）stable
│     觸發 = C 配置全指標 PASS（RAM used <5.5GB 且 headroom ≥0.8GB 且
│            溫度 <80°C 且每 watch topic Hz 在期望 ±20% 且無 node crash）。
│     → S1 可避免換 stack（brain + nav 同跑）。
│       ★ 仍不發 goto_relative ★ — map/LiDAR/pose 只當「視覺證據」。
│       S1 形態交 plan6 決定 live 證據呈現。
│
├─ branch 2 "B-RESIDENT-LIDAR"：A stable、C unstable、B stable
│     觸發 = C 任一指標 FAIL（RAM >6.5GB 或 headroom <0.8GB 或溫度 >80°C 或
│            topic Hz 偏離 >40% 或 node crash），但 B 全指標 PASS。
│     → brain 駐留 + raw LiDAR/Foxglove 當視覺證據 + operator-assisted。
│       不跑 nav2/amcl（省 RAM）。
│
└─ branch 3 "A-ONLY-VIDEO"：A stable、B 也 unstable
      觸發 = B 任一指標 FAIL，但 A 全指標 PASS（或最多 WARNING）。
      → S1 live = 第三人稱 + Studio brain only；map/LiDAR 走影片/截圖。
```

> **無論落哪個 branch，S1 都不啟 `goto_relative` 當主線**（Gotcha #4 / nav NOT_DEMO_READY）。live-motion 選項（若有）= plan6 的 DriveOnHeading，且須 T0 fix + D1–D5 + θ_error<5° + e-stop + n=3，**不在本計畫**。

---

## 12. Execution order

1. **T1（pure_software，AFK）**：Codex 寫 harness + parser + 單測 + 文件骨幹（含空決策表 + 空閾值表）→ `pytest` 綠 → 小 PR。**這步不需硬體、不需 Roy。**
2. **J-0（Jetson，Roy 在場）**：清場（Go2 停穩 + demo stop + pkill 殘留）。
3. **T2 → T3 → T4（Jetson no-motion，Roy 在場）**：依序 A→B→C 跑 profiling，每配置 ≥3 分鐘。C 是壓力上限，OOM 立即清場。
4. **T6（Jetson no-motion）**：cold-start + 交接時間（可與 T2 清場/起場順手量）。
5. **T5（pure_software 判讀，Roy 6/17 彩排拍板）**：依 CSV 走 4-branch 決策樹，填決策表，過 claim-wording 掃描。
6. **凍結（硬時間閘，解 plan4 runbook 循環依賴）**：**profiling CSV 6/15 EOD 定稿**（滑期 → S1 直接採 §11.1 branch 3 A-ONLY-VIDEO，不阻塞 runbook）；**4-branch 決策樹 + S1 runtime layout 決策表 6/16 09:00 鎖定**（之後不得改 S1 runtime layout）；plan4-P4-13 P1 於 6/15 下午回填、P4-11 dry-run（6/16）用回填後 runbook。最終定稿仍納入 6/17 18:00 main 凍結，plan6 / plan2 引用。

> 跨計畫順序：本計畫 T5 **先於** plan6 的 S1 形態定稿、plan2 的 S1 phase 呈現定稿、plan4-P4-13 交接決策。plan6 / plan2 / plan4 不得在本決策表落點前先寫死 S1 為 live nav；plan4 runbook 用 P4-13 P0 template（placeholder）先成文、不卡 profiling。

---

## 13. Codex Implementation Prompt

> 你是 Codex（builder）。只做 plan1 的 **T1**（pure_software），其餘（T2–T6）需 Jetson 真機 + Roy 在場，**不要做、不要假裝跑過**。

**任務**：在 `/home/roy422/newLife/elder_and_dog` 新增 co-run profiling harness，全部**純新增檔案**，不改任何既有檔。

**要做**：
1. `scripts/corun_topics.txt`：照本計畫 §9.1 表列 topic（含每行 `topic,expected_hz,configs`，例 `/scan_rplidar,10,BC`）。
2. `scripts/corun_profile.sh`：bash（用 `bash -c` 相容，勿假設 zsh）。參數 `--config A|B|C`、`--duration <s>`、`--interval <s>`。每 interval：
   - ssh-local 或本機讀 `free -h`、`/sys/devices/gpu.0/load`、`/sys/devices/virtual/thermal/thermal_zone*/temp`、`ps aux`（沿用 `jetson-status` SKILL snapshot 寫法）；
   - 對 `corun_topics.txt` 中 match 本 config 的 topic 跑 `timeout 6 ros2 topic hz <topic>`；
   - 寫一行 raw 進 `runtime/profiling/2026-06-13-config<X>.log`；
   - 若 RAM used > 6.5GB → `echo "OOM-RISK ABORT"` 並 break（不殺 stack）。
   - 全程**零 motion 指令**（不得出現 `goto`/`cmd_vel`/`/nav/`/Move）。
3. `scripts/corun_profile_parse.py`：讀 log → 解析 RAM/temp/GPU/topic-Hz/node-list → 套 §9.2 thresholds → 輸出 `runtime/profiling/2026-06-13-config<X>.csv` + stdout 判定（PASS/WARNING/FAIL 逐指標 + 配置 stable/unstable）。要求 `--config` label，缺則報錯。
4. `scripts/test_corun_profile_parse.py`：§T1 八條 pytest，用 inline fixture（不碰硬體、不碰 ROS）。
5. `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`：程序文件骨幹 — 含 §9 watch topics 表、§9.2 thresholds 表、§11.1 4-branch 決策樹、**空白決策表**（待 T5 填）、空白 8GB/cold-start 表（待 T6 填）。

**驗收**：`python3 -m pytest scripts/test_corun_profile_parse.py -v` 八條全綠；`bash -n scripts/corun_profile.sh` 語法檢查過；grep `scripts/corun_profile.sh` 確認**無**任何 motion 關鍵字（`goto`/`cmd_vel`/`Move`/`/nav/`）。

**禁止**：不改 `start_full_demo_tmux.sh` / `start_nav_capability_demo_tmux.sh` / `executive.yaml` / 任何既有檔；不引 supervision/重依賴；不寫 motion；不擴 scope；不改任何 runtime 行為宣稱。回報 diff + test 結果 + 風險。

---

## Codex Implementation Packet

**exact files（只新增）**：
- `scripts/corun_topics.txt`
- `scripts/corun_profile.sh`
- `scripts/corun_profile_parse.py`
- `scripts/test_corun_profile_parse.py`
- `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md`

**exact tests**：
- `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest scripts/test_corun_profile_parse.py -v`（八條全綠）
- `bash -n scripts/corun_profile.sh`（語法）
- `grep -nE "goto|cmd_vel|/nav/|Move\(|api_id" scripts/corun_profile.sh || echo "NO-MOTION OK"`（必須無 match）

**exact commands（Codex 本機跑）**：
```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest scripts/test_corun_profile_parse.py -v
bash -n scripts/corun_profile.sh
grep -nE "goto|cmd_vel|/nav/|Move\(|api_id" scripts/corun_profile.sh || echo "NO-MOTION OK"
git add scripts/corun_*.* scripts/test_corun_profile_parse.py docs/archive/navigation-legacy/incident-runbooks/2026-06-13-corun-profiling-procedure.md
```

**acceptance**：
- 八條 pytest 全綠。
- `corun_profile.sh` 語法過 + 無 motion 關鍵字。
- parser 對 §9.2 每條 threshold 都有對映判定分支（review 逐條對）。
- 所有檔案純新增；`git status` 不顯示任何既有檔被改。
- 對 ~955 回歸測試零影響（純新增 + 不進 CI blocking 路徑；若 CI 收 `scripts/test_*.py`，確認本測試獨立可跑、不依賴硬體）。

---

## Cloud Review Checklist

Cloud（Fable）收 Codex 產出後逐項驗：
1. **scope**：是否只新增 5 個檔、零既有檔改動？（`git diff --stat` 確認）
2. **NO-MOTION**：`corun_profile.sh` / parser / 文件是否完全無 `goto`/`cmd_vel`/`/nav/ send_goal`/`Move`/`api_id` 寫入？（grep 掃）
3. **無重依賴**：parser 是否只用 stdlib（不 import supervision/cv2/torch）？（`grep -n "^import\|^from" scripts/corun_profile_parse.py`）
4. **threshold 正確**：§9.2 每個數字是否與 jetson-status budget 一致（RAM 6.5GB critical、溫度 80°C、headroom 0.8GB）？
5. **topic 清單正確**：§9.1 每個 topic 名稱與 source（nav monitor block / CLAUDE.md）逐字對？
6. **單測真有效**：八條 pytest 是否真的覆蓋 parse + passfail + crash + label，不是空 assert？
7. **rollback 可執行**：§10 每條 rollback 指令是否真能回復（純新增 = 刪檔）？
8. **overclaim 掃描**：文件 / 決策表 / 註解是否出現 autonomous navigation / 即時 SLAM / 動態繞障 / D435 已融合 / fallen / 2m 物體 / 可靠顏色 / 19 色？（任一出現 = reject）
9. **byte-identical**：確認不改 demo runtime；最壞退路 = profiling 沒跑 → S1 branch 3，零新風險。
10. **跨計畫不重複**：未混入 plan6（nav 參數/initialpose/n=3）或 plan2（demo_phase 詞彙/切幕）的任務。

---

## Stop Conditions

**立即停（Codex / 執行者）**：
- profiling 腳本中出現**任何 motion 指令** → 停，移除，重審（Q2 / Gotcha #5 硬規）。
- C 配置量測中 RAM used > 6.5GB 且仍上升 → `corun_profile.sh` 自動 `OOM-RISK ABORT`；Roy 決定清場，**不續跑**。
- Go2 在任何配置中**未經授權移動**（理論上不該發生，因零 motion 指令）→ Roy e-stop，全停，記錄為 incident，本計畫暫停。
- Codex 想改 `start_full_demo_tmux.sh` / nav 腳本 / `executive.yaml` 才能跑 → 停（本計畫用唯讀 attach，不改既有腳本）。
- 決策表想把 S1 寫成 live autonomous nav → 停（違 NOT_DEMO_READY + claim-wording）。

**升級給 Roy**：
- A 配置 unstable（brain baseline 不穩）→ 觸發 branch 4，本計畫產出「BRAIN-FIRST」結論並停止 B/C 量測（先修 brain）。
- D435 故障無法在 6/18 前修 → 記錄 face/vision 在無 D435 的行為，C 配置標 D435-absent，Roy 決定 S1 是否仍走含 face 證據的路徑。

---

## Required Evidence

T1 done 證據（pure_software）：
- `git diff --stat`（顯示 5 新檔、零既有檔改）。
- `pytest scripts/test_corun_profile_parse.py -v` 全綠輸出。
- `bash -n` + grep NO-MOTION 輸出。

T2–T6 done 證據（Jetson no-motion，Roy 在場）：
- `runtime/profiling/2026-06-13-config{A,B,C}.csv`（三配置各 ≥3 分鐘、每指標 PASS/WARNING/FAIL）。
- `runtime/profiling/2026-06-13-config{A,B,C}.log`（raw snapshot 時間序列）。
- `runtime/profiling/2026-06-13-coldstart.csv`（brain/nav cold-start + 交接間隔）。
- 每配置一張 `jetson-status` 30s monitor 輸出（佐證 RAM/溫度 趨勢）。
- T5 決策表填妥（4-branch 落點 + Roy 6/17 拍板簽註）+ claim-wording 掃描通過記錄。

> **誠實標註**：T1 = `proven`（單測綠 = pure-software 可宣稱）。T2–T6 在 Roy 真機跑出 CSV 前一律 `needs-HITL`；決策樹落點在 6/17 彩排前一律 `needs-HITL`，**不得**對外宣稱「已確定 S1 用 X layout」直到實機 CSV + Roy 拍板。

---

## Rollback Plan（整體）

1. **未上機前**（只有 T1）：`git rm` 5 新檔即完全回復，byte-identical，零 runtime 影響。
2. **上機量測中異常**：依 §10 各配置 rollback（clean_full_demo + pkill nav）；profiling 產物在 `runtime/profiling/`（已在 rsync excludes，不會被 deploy `--delete` 轟掉）。
3. **決策樹無法定論**（數據不足 / 時間不夠）：S1 直接採 branch 3（第三人稱 + Studio brain only + map/LiDAR 影片/截圖）——這是 master plan 既有最保守 S1，零新風險、零新行為。
4. **本計畫整體放棄**：刪工具檔 + 文件保留為「未執行」記錄；S1 走 branch 3。對 demo runtime 與 ~955 回歸測試零影響。
