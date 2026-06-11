# 系統 Phase 4：Robot Control / Navigation Hardening（4A 控制面 hardening + 4B nav capability ladder）

> **日期**：2026-06-11　**狀態**：PLANNED
> **上游文件**：
> - v2 Master plan：[`2026-06-11-pawai-system-refactor-v2-master.md`](2026-06-11-pawai-system-refactor-v2-master.md)（依賴閘門 G5/G6、附錄 A 決策登記簿 A-1/A-2/A-3/A-9）
> - 安全修補權威：[`../../security/2026-06-11-pawai-hardening-plan.md`](../../security/2026-06-11-pawai-hardening-plan.md)（下稱「hardening plan」；本 plan 的 4A 逐項吸收其控制面項）
> - Findings 真相源：[`../../security/2026-06-11-pawai-security-findings-ledger.md`](../../security/2026-06-11-pawai-security-findings-ledger.md)（下稱「ledger」，94 筆對抗驗證）
> - Nav 實機證據：[`../../navigation/research/2026-06-08-trackB-hitl-results.md`](../../navigation/research/2026-06-08-trackB-hitl-results.md)（6/8 Track B HITL）、[`2026-06-09-nav-vision-hitl-execution.md`](2026-06-09-nav-vision-hitl-execution.md)（6/9 HITL：lunge / orphan 自癒 / REACTIVE_PROFILE）

## 命名消歧（必讀）

本套件有三套互不相干的編號，內文一律寫全名、禁止裸寫「Phase N」：

| 編號系統 | 指什麼 | 範圍 |
|---|---|---|
| **系統重構 Phase 1-5** | 本 v2 套件的大階段（本文件＝系統 Phase 4） | CI → Core Brain/Ops → Vision → Nav/安全 → 收口 |
| **ISM Phase 0-3** | `interaction_state.py` 狀態機自己的實作階段（[ISM plan](2026-06-11-plan-ism-interaction-state-machine.md)） | Brain 內 |
| **安全 hardening P0-P3** | hardening plan 的修補優先級標籤（如「hardening P0-1」= gateway secure-default） | 安全項 |

> **北極星（一句引用，全文見 master plan）**：把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台——Perception Nodes → Perception Router → Interaction State Machine → Policy + Safety Layer → Skill Executor → Trace + Evidence，三支撐＝PawAI CLI v2 / PawAI Studio v2 / pawai_contracts。系統 Phase 4 對應其中第 5 條成功標準：**未授權者不能讓 Go2 動**。

---

## Goal

把兩件事做成可驗證的真相：

1. **4A 控制面 hardening**：把「誰可以讓 Go2 動」收斂成可信控制面——所有能觸發機器人動作的入口（gateway HTTP/WS、DDS topic、foxglove、nav action、`/cmd_vel`、`/webrtc_req`）各有 owner + guard + 實測驗證紀錄。逐項吸收 hardening plan 的控制面項（hardening P0-1 / P0-2 / P1-1 / P1-2 / P1-3 / P1-4 / P3-4），對應三個結構性根因中的 R1（gateway/foxglove 綁 0.0.0.0 無認證）與 R2（DDS 信任邊界與 LAN 重合）。
2. **4B Navigation hardening + capability ladder**：把導航能力變成**誠實的 capability ladder**——`wired_only` / `hardware_proven` / `demo_ready` / `research_prototype` 四級，每格綁 HITL 證據或明標 research；同時根治 6/8-6/9 HITL 暴露的工程債（orphaned-goal、stop-resume lunge、reactive profile 制度化、AMCL 黃帶診斷）。

**全段 post-6/18**（凍結解除 = master plan 閘門 G5；各控制面項另需 G6 的 Roy 決策批次），且幾乎每項都需要實機回歸。

---

## Scope

| 主線 | 內容 | 主要檔案面 |
|---|---|---|
| 4A | gateway secure-default flip（hardening P0-1）、foxglove clientPublish 降權（hardening P0-2）、CycloneDDS 收斂（hardening P1-1）、`/webrtc_req` whitelist + rate limit（hardening P1-2）、nav action 授權 + route_id 消毒（hardening P1-3）、twist_mux/cmd_vel 來源收斂（hardening P1-4）、reactive_stop 文件債（hardening P3-4） | `pawai-studio/gateway/studio_gateway.py`、`pawai-studio/frontend/`、`.claude/skills/brain-studio-lane/scripts/start.sh`、各 `scripts/start_*.sh` 的 foxglove 行、新 `cyclonedds.xml`、`config/school_demo.env`、`go2_robot_sdk/.../robot_control_service.py`、`nav_capability/`、`go2_robot_sdk/config/twist_mux.yaml`、`CLAUDE.md` / `docs/navigation/CLAUDE.md` |
| 4B | capability ladder 標籤定義 + 逐能力標級表、stop-resume 終局決策落地、orphaned-goal client 根治、REACTIVE_PROFILE 制度化文件 + 驗收矩陣、研究線 spec（fusion / patrol / approach）、AMCL covariance 黃帶診斷 + goal rejection reason server 側分流 | `scripts/send_relative_goal.py`、`nav_capability/nav_action_server_node.py`（message 分流）、`scripts/start_nav_capability_demo_tmux.sh`（REACTIVE_PROFILE 已有）、`docs/navigation/` 新 ladder 文件與 research spec |

### 與系統 Phase 2 的分工（避免重工，依賴圖互補）

安全 ledger 上「未認證 → motion」合流鏈有兩端，**本 phase 只負責 gateway / DDS / driver / nav 側**：

| 修補 | 屬於 | 理由 |
|---|---|---|
| gateway 認證、DDS 收斂、`/webrtc_req` whitelist、nav action 授權、cmd_vel 治理 | **系統 Phase 4（本文件）** | 傳輸面與 driver 縱深，與 Brain 裁決邏輯無關 |
| brain 端 source trust——`source` 不可自稱（hardening P2-1，對應 GAP1-01 / LLM-02） | **系統 Phase 2 的 ISM staged enable**（ISM plan §3.3） | `requires_confirmation` 一律走 CONFIRM_PENDING 是 ISM policy 的職責 |
| SafetyLayer 不信 wire `priority_class`（hardening P2-2，對應 LLM-01） | **系統 Phase 2**（獨立行為變更 commit） | SafetyLayer 是 Brain 內安全閘 |

兩邊合起來才封死「同 LAN 偽造 `source=studio_button` 直發 `/brain/skill_request` → 繞過確認 → motion」（GAP1-01 / GAP2-03）這條鏈：系統 Phase 2 讓 Brain 不信自稱欄位，系統 Phase 4 讓未認證方根本到不了 bus / gateway。

---

## Forbidden scope

1. **6/18 凍結期間不動工**：本 phase 全段在凍結解除（G5）後才開工；唯一例外＝純文件（hardening P3-4 的 reactive_stop 文件債）與本 plan 撰寫本身。
2. **不做 brain 端 source trust / SafetyLayer priority_class 修法**（hardening P2-1 / P2-2）——那是系統 Phase 2 的 ISM staged enable 範疇（見上方分工表），本 phase 不碰 `brain_node.py` 裁決邏輯。
3. **不推倒既有承重牆**（master plan 禁令延續）：twist_mux 優先序架構、reactive_stop 4-mode 狀態機、`StopMove` 路由（`test_robot_control_service.py` 權威測試）、nav_action_server single-goal 模型——只加 guard / 修 bug，不重寫。
4. **研究線不進 runtime、不對外 claim**：D435+LiDAR fusion、patrol、approach person/object 全程 `research_prototype`，demo snapshot forbidden claims 持續有效，取得新 HITL 證據前一律不宣稱。
5. **不在本 phase 做 Studio 側 nav UI 擴張**（goal rejection reason 的前端呈現屬系統 Phase 2B Evidence Center / 系統 Phase 5）；本 phase 只修 server 側 message 分流。
6. **觀測類與政策類永不同 PR**；每項 hardening 是行為變更＝獨立 PR，不與搬家 / 文件混刀。

---

## Inputs / prerequisite docs

| 前置 | 狀態 | 用途 |
|---|---|---|
| G5：6/18 解凍宣告 | OPEN（Roy） | 全 phase 開工閘門 |
| G6：Roy 決策批次（master 附錄 A-1 / A-2 / A-3 / A-9） | OPEN（Roy） | T4A-1 flip 時點、T4A-2 foxglove、T4B-1 S1 簿記、T4B-2 stop-resume |
| S0-2 gateway access-control 機制層（`auth.py`，PR #158，env-gated 預設關） | merged | T4A-1 是其 **enforcement flip + wiring**，機制不需重寫；已真機雙模式驗過 default-off 開放 / auth-on 401+403 |
| hardening plan + ledger + threat model 三件套 | 已 commit | 4A 每 task 的修法與 finding 對應 |
| 6/8 Track B HITL（NAV-1 resolved、reactive 誤擋根因、orphan 機制） | 已 commit | 4B 的實證基線 |
| 6/9 HITL（REACTIVE_PROFILE、orphan 自癒、auto-resume lunge、`lidar_front_sector.py`） | 已 commit | 4B 的實證基線 |
| `goto_max_duration_s=120` backstop + `no_progress_timeout` 自癒 | 已在 `nav_action_server` | T4B-3 只需修 client 側 |
| gateway `/api/nav/initialpose` endpoint | 已存在 | T4A-2 的解鎖前置（initialpose 工作流遷 Studio） |
| `REACTIVE_PROFILE=open_space\|indoor_tight` 一鍵 profile | 已在 `start_nav_capability_demo_tmux.sh`（6/9） | T4B-4 只做制度化文件 + 驗收矩陣 |

---

## Tasks

### 執行紀律（治理原則，繼承 master plan，全 task 適用）

main 永遠可部署；每刀小 PR + CI 綠 + 紅綠驗證才 merge；搬家與行為變更分開 PR；trace/觀測 additive-only；觀測類與政策類永不同 PR；Codex 串行實作 + Fable spec/review；硬體能力宣稱必過 HITL gate；demo snapshot 的 forbidden claims 對所有對外材料持續有效。**本 phase 追加**：每項 hardening 變更先在隔離環境（WSL / isolated mux，遵守「`test_mux_priority.py` 不可在 full stack 跑」鐵則）驗證，再排 nav lane 實機回歸 session。

### 4A：控制面 hardening（吸收 hardening plan 控制面項，保留 hardening 編號）

| Task | hardening 編號 | 內容 | 載體 | 驗證 |
|---|---|---|---|---|
| **T4A-1** | **P0-1** | **gateway secure-default flip bundle**：① bind `127.0.0.1`（或強制 `GATEWAY_HOST` 顯式設定，禁止隱含 0.0.0.0）+ 強制 token；② 前端 13 個 HTTP endpoints + 4 個 WS 全帶 token（header / `?token=`）；③ `brain-studio-lane` `start.sh` 注入 token（**需 `.claude/skills/` 解凍**）；④ **認證後簽章（nonce/HMAC，hardening P0-1 延伸）**——gateway 認證後對注入 bus 的 `/brain/skill_request` 簽章、brain 驗章（系統 Phase 2 source trust 表明標此項屬系統 Phase 4，本 task 承接，勿落空）。機制層 S0-2（PR #158）已 ship 且預設關——本 task 是 **enforcement flip + wiring**，不重寫 auth（④ 簽章為新增機制）。CORS 白名單 + WS Origin 檢查（GW-04）一併翻入 enforced 模式 | Roy 決策（A-3 時點 + token 發放流程）→ Fable spec → Codex 實作 | **auth-on 模式 demo 全流程可用**（Studio 按鈕 / push-to-talk / video / nav panel 全綠）+ 未授權請求 401/403（沿用 S0-2 真機雙模式驗法）；CLI status gateway probe 帶 token 不假成功；④ 簽章：無有效簽章的偽造 `/brain/skill_request` 被 brain 拒絕（與 T4A-3 DDS 面雙封） |
| **T4A-2** | **P0-2** | **foxglove clientPublish 降權（Roy 決策項，master 附錄 A-2）**。兩個 fix 已備：`-p capabilities:='["connectionGraph"]'`（降唯讀）或 `-p address:=127.0.0.1`（僅本機）。**卡點**＝會斷「nav `/initialpose`-via-Foxglove」工作流與筆電可視化。**解鎖前置**：先把 initialpose 工作流遷到 Studio nav control（gateway `/api/nav/initialpose` 已存在，前端接上 + 實機驗 AMCL 收到 pose）→ 再降權 foxglove。涵蓋全部 **8 處** `start_*.sh` foxglove 啟動行：hardening P0-2 列的 6 處（full_demo:274 / nav2_amcl:73 / nav_capability:130 / lidar_slam:55 / face_identity:78 / vision_debug:32）＋ 2 個 deprecated 但仍可執行的腳本——`start_nav2_demo_tmux.sh:85`（archived）與 `start_nav_capability_demo_tmux_detour.sh:103`（已知 4 bug「不要直接用」）——後兩者在本 task 一併降權，或配合 master 附錄 A-5 dead-code 歸檔原則移入 `scripts/archive/` | Roy 決策（A-2）→ Codex 實作（兩 PR：先遷工作流、再降權） | 遷移 PR：Studio 設 initialpose → AMCL `Setting pose` log + `map→odom` TF 出現；降權 PR：Foxglove 仍可看 topic/影像、瀏覽器 client 無法 advertise/publish `/cmd_vel`（EXP-02 封閉） |
| **T4A-3** | **P1-1** | **CycloneDDS 綁 interface + domain 隔離**：repo 內新增 `cyclonedds.xml`（NetworkInterface 限定 Go2/Jetson 直連 iface、`AllowMulticast=false`、明列 unicast Peers）；`config/school_demo.env` + 各 `start_*.sh` export `CYCLONEDDS_URI`；`ROS_DOMAIN_ID` 改非預設值。**長期評估線**：SROS2（enclave + DDS-Security），是唯一真正關掉 R2 的方法，本 task 出評估報告不強制落地。對應系統級根因 **LLM-10**（全 `/brain/*` / `/event/*` 在無 SROS2 下對同 DDS domain 零認證） | Fable spec（含 SROS2 評估）→ Codex 實作 → Roy HITL | Go2↔Jetson 全鏈路回歸（WebRTC 不可斷、5 感知 + brain + nav topic 全通）；第二台同 LAN 主機（未列 Peers）`ros2 topic list` 看不到 / pub 不進 bus |
| **T4A-4** | **P1-2** | **go2_driver `/webrtc_req` api_id 白名單 + rate limit**：`robot_control_service.py` 的 `handle_webrtc_request` 目前**零過濾、直接轉發**（ledger MOT-01「無 api_id 白名單」位置即此處）；**新增 whitelist 模式**（明列 demo/nav 需要的 api_id，其餘拒絕 + log），並參考 brain 層 `BANNED_API_IDS`（`speech_processor/llm_contract.py`，3 條：1030/1031/1301，現由 `interaction_executive/safety_layer.py` 引用、不在 driver）確保該三條永在拒絕清單；加速率限制防 DataChannel buffer flood（MOT-08，曾觀測 86KB+ backlog）。此檔 routing 權威測試 `test_robot_control_service.py`（11 條）必同步擴充 | Codex 實作（TDD：先紅後綠） | 單測：whitelist 內放行 / 外拒絕 / StopMove(1003) 永遠放行 / rate limit 不擋 1 Hz dedupe StopMove；實機：Go2 動作 demo 全流程不破（MOT-01 封閉） |
| **T4A-5** | **P1-3** | **nav_capability action server 授權 + route_id 路徑消毒**：① `/nav/goto_*`、`/nav/run_route`、`/log_pose` 動作入口加授權（demo lock owner / token，或限定只接受 Brain Executive 轉發）；② `route_id` / `name` 用 `os.path.basename` + 白名單字元過濾，拒絕 `../`（MOT-04 路徑穿越）。對應 **MOT-05（critical，critic 升級）**：同 LAN 主機可命令機器人導航到任意座標 | Codex 實作 | 單測：惡意 route_id 全拒；實機：合法 goto/run_route 流程不破、未授權 action send_goal 被 reject（MOT-05 封閉） |
| **T4A-6** | **P1-4** | **twist_mux / cmd_vel 來源收斂 + emergency 速度 clamp**：driver 改訂 mux 輸出專屬 topic（裸 `/cmd_vel` 不直連 driver，封 MOT-02 繞 mux 注入）；emergency lane（priority 255）加速度 clamp（MOT-03：emergency 不驗速度值）；`/lock/emergency` 來源治理（MOT-10）。**hardening plan 明標「需 nav lane 實機回歸」**——會動 reactive_stop / nav 既有行為鏈（mux priority 200 / teleop 100 / 4-mode 狀態機） | Fable spec → Codex 實作 → **Roy HITL（nav lane 實機回歸 session 必須）** | 隔離 mux 環境先驗 priority 行為；實機回歸：danger 停 → clear 放行 → nav goto 通 → emergency engage/release 全鏈不變；clamp 後 emergency lane 注入超速值被截 |
| **T4A-7** | **P3-4** | **reactive_stop 文件債（防誤設 `hold_brake` 鎖死 nav）**：修正 CLAUDE.md 過時宣稱「`safety_only=true` 必須用於 mux 模式」（GAP3-01：與實際腳本 `mode:=progressive` 矛盾；`safety_only=true` 會 promote 成 `hold_brake` 永久煞車）；腳本 REACTIVE_PARAMS 旁加 inline 註解；demo-preflight 加「遮 LiDAR 驗 `/cmd_vel_obstacle` 發 0」檢項。GAP3-02（主線無 safety-hold 腳本）作觀察記錄一併寫清 | Fable 撰寫（doc PR）；preflight 檢項 Codex 實作 | 文件與 `reactive_stop_node.py` 4-mode 實作逐字對照無矛盾；preflight 新檢項在 Jetson 實跑一次通過。**doc 部分（CLAUDE.md / docs/navigation 修正）可凍結期先做；preflight 檢項碰 `.claude/skills/`（demo-preflight skill 位於凍結面）、腳本 inline 註解碰 `scripts/`，皆排 G5 後**（與 §6/18 freeze constraint 措辭一致） |

#### 4A findings 對照表（ledger 編號 → 本 phase 歸屬）

| Finding | 一句話 | 修補歸屬 |
|---|---|---|
| GW-03 | 未認證 Browser→ROS 注入（ws/text、ws/speech、`/api/skill_request`、`/api/text_input` 直灌 brain topic；gateway 硬寫 source） | T4A-1（gateway 認證後，gateway 端 source 才可信；brain 端不信自稱屬系統 Phase 2） |
| GAP2-03 | 同 LAN / 同 DDS 任何主機可無認證 pub `/brain/skill_request` 直發 MOTION skill | T4A-1 + T4A-3（HTTP 面 + DDS 面雙封）；brain 側 confirm 收緊屬系統 Phase 2 |
| LLM-10 | 全 `/brain/*` / `/event/*` 零認證（R2 根因） | T4A-3（DDS 收斂 + 長期 SROS2） |
| MOT-01 / MOT-08 | `/webrtc_req` 無白名單 / 無速率限制 | T4A-4 |
| MOT-05 / MOT-04 | nav action 無認證（critical）/ route_id 路徑穿越 | T4A-5 |
| MOT-02 / MOT-03 / MOT-10 | 裸 cmd_vel 繞 mux / emergency 不驗速度 / `/lock/emergency` 無認證 | T4A-6 |
| EXP-02 | foxglove_bridge clientPublish 未認證可 publish `/cmd_vel` | T4A-2 |
| EXP-03 / GAP3-03 | 無 SROS2、DDS 未綁 interface、domain 0 | T4A-3 |
| GAP3-01 / GAP3-02 | reactive_stop 文件債 | T4A-7 |
| GAP1-01 / LLM-02（source 自稱）、LLM-01（priority_class 短路） | brain 端信任 wire 欄位 | **系統 Phase 2**（hardening P2-1 / P2-2，本 phase 不做） |

### 4B：Navigation hardening + capability ladder

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T4B-1** | **capability ladder 標籤定義 + 逐能力標級**：定義四級——`wired_only`（程式接通、無實機證據）/ `hardware_proven`（有 HITL 證據 + 限制條款）/ `demo_ready`（可對外演示 + 操作 SOP）/ `research_prototype`（研究線、禁 claim）——並把每個 nav 能力（短距 goto、正前 safe-stop、stop-resume、goto_named、run_route、巡邏、物體導向）標進表格，每格附證據路徑（如 6/8 Track B：goto 0.3m `reached actual=0.270m`、reactive danger 停 0 撞 0 暴衝、blocked-goal 278s 存活）。**前置＝Roy 的 S1 簿記決策（master 附錄 A-1）**：S1 最後用哪方案錄成（A 0.5m / C initialpose / 遙控輔助）決定 operator-confirm 迴圈標 `hardware_proven` 還是 `wired_only` | Roy 決策（A-1）→ Fable 撰寫 ladder 文件 | 表完成且每格有 HITL 證據路徑或明標 `research_prototype`；與 capability baseline spec 既有標籤對齊（mapping 註記）；無「未測但已宣稱」格 |
| **T4B-2** | **stop-resume 終局決策落地（master 附錄 A-9）**：operator-confirm 永久化 vs `resume_policy=auto` 留大場地。實證約束（6/9）：**tight space 禁 auto-resume**——resume 以 Go2 sport-mode `MIN_X` floor ~0.5 m/s lunge、短 goal 曾貼牆 0.21m。決策後落地為 param + 文件 + ladder 標級（auto-resume 若保留只標大場地 `hardware_proven`，須補大場地 HITL） | Roy 決策（A-9）→ Codex 實作 | 決策記入 master 附錄 A；tight profile 下 auto-resume 被 param 拒絕（單測 + 實機）；大場地 resume 若啟用附 HITL 紀錄 |
| **T4B-3** | **orphaned-goal 根治（client 側）**：goto client 正解＝`rclpy.init(signal_handler_options=NO)` + 自管 SIGINT → cancel goal → 單次 shutdown（6/9 結論：rclpy 預設 SIGINT 先關 context → RCLError 非 KeyboardInterrupt → cancel 沒送出）；同步修 `send_relative_goal.py` double-`rcl_shutdown` bug（6/8 backlog #1：try/finally 正確 cancel）。server 側**不需改**——`goto_max_duration_s=120` backstop + `no_progress_timeout` 自癒已 ship（6/9 驗證 orphan 可自癒、不需重啟） | Codex 實作 | 實機：goto 進行中 Ctrl-C / kill client → server log 出現 cancel、立即可接受下一筆 goto（不再 `another goto still active`）；SSH 斷線情境重演通過 |
| **T4B-4** | **REACTIVE_PROFILE 制度化**：`open_space`／`indoor_tight` 一鍵 profile 已在 `start_nav_capability_demo_tmux.sh`（6/9），本 task 補正式文件 + 驗收矩陣：每 profile 列 `front_arc_deg` / `danger_distance_m` / 速度上限 / 適用場地 / HITL 證據（6/8：±15° 修法 zone danger→slow/clear 已驗；6/9：indoor_tight ±18° 誤擋修正 front 0.97→1.22m）。**硬規則寫進文件**：窄錐（±15-20°）必綁低速 ≤0.2 m/s；`front_arc_deg`/`danger_distance_m` 只在 `__init__` 讀一次、改 profile 必 kill 重啟；`lidar_front_sector.py` 列為現場分辨真障礙 vs 側前家具的標準工具 | Fable 撰寫 + Roy HITL（矩陣重跑一輪） | 文件矩陣每格有實測數據；兩 profile 各在對應場地實跑一次（danger 停 / clear 放行 / 無誤擋）並記錄 |
| **T4B-5** | **研究線 spec 先行（`research_prototype`，禁 claim）**：三條各寫獨立 research spec + 獨立 safety gate，spec 通過前不寫 code——① **D435+LiDAR costmap fusion**（歷史：5/3 詳測 L3 FAIL，根因＝nav_action_server `max_speed` 不 enforce + AMCL plateau，spec 必須先解這兩個根因；另有 6/8 backlog 的 depth→`/scan_d435` light 版路線）；② **patrol prototype**（run_route 巡邏，需大場地）；③ **approach person/object**（物體導向導航，6/8 估 4 層新開發 ≈ 4-5 天）。三者全程標 `research_prototype`，任何對外材料不得宣稱 | Fable 撰寫 spec → Roy 決策排期 | 每 spec 含：根因前置清單、safety gate 定義、HITL 升級條件（何時可升 `hardware_proven`）；ladder 表上三項標 `research_prototype` |
| **T4B-6** | **AMCL covariance 黃帶診斷 + goal rejection reason 透傳（server 側）**：S1 卡點根源＝AMCL covariance 卡 0.45 抖、nav 閘拒 goal。① 診斷 task：固定 SOP 量測 covariance 收斂曲線（initialpose 後靜置 vs 0.3m warmup），輸出「黃帶下該等 / 該推 / 該放寬」決策表；② architecture audit NAV-2 工程債（出自 [`2026-06-10-pawai-architecture-audit.md`](../specs/2026-06-10-pawai-architecture-audit.md) 的 NAV-2/STUDIO-2，**非** 6/8 Track B HITL 編號的 NAV-2「安全停 ✅」）：goal rejection reason 被三層吞掉——本 phase 修 **server 側分流 message**（`nav_action_server` reject 時帶結構化 reason：`nav_not_ready:covariance=0.45` / `another_goto_active:<goal_id>` / `paused` 等）；Studio 側呈現屬系統 Phase 2B Evidence Center / 系統 Phase 5，本 phase 不做前端 | Codex 實作（reason 分流）+ Roy HITL（covariance SOP） | 單測：各 reject 路徑 message 含結構化 reason；實機：黃帶拒 goal 時 `ros2 action send_goal` 回傳可讀 reason，不再裸 reject；covariance 決策表附實測曲線 |

---

## Tests / verification

1. **每項 hardening 變更＝獨立 PR + 紅綠驗證**：先在隔離環境（WSL 單測 / isolated mux）證明會抓（紅）、修後過（綠），才排實機。
2. **nav lane 實機回歸 session**：T4A-6（twist_mux/cmd_vel）**必須**完整 nav lane 回歸（danger 停 → clear 放行 → goto → emergency engage/release）；T4A-3 / T4A-4 / T4A-5 各需一次 Go2 連線回歸；T4B-2 / T4B-3 / T4B-4 / T4B-6 各有實機驗證項（見各 task 驗證欄）。**本 phase 並須把上述 nav 回歸清單固化為可重複執行的腳本／檢查表 artifact**（落 `docs/navigation/` 或 `scripts/`），明標 handoff 給系統 Phase 5 `pawai smoke nav`（T5A-2）直接包裝——對照系統 Phase 3 V3-3 的 handoff 模式，不留散文。
3. **滲透式安全驗收清單（4A exit gate）**：以**同 LAN 未授權主機**逐項嘗試，全部必須被擋並留紀錄——
   - 直 pub `/brain/skill_request`（偽造 `source=studio_button`）→ DDS 面到不了 bus（T4A-3）；
   - `curl` gateway 各狀態變更 endpoint（無 token）→ 401/403（T4A-1）；
   - WS 連 `/ws/*`（無 token / 偽 Origin）→ 拒絕（T4A-1）；
   - Foxglove client advertise + publish `/cmd_vel` → 拒絕（T4A-2）;
   - 直 pub 裸 `/cmd_vel` / `/cmd_vel_emergency` 超速值 → driver 不直收 / clamp（T4A-6）；
   - 直 pub `/webrtc_req` whitelist 外 api_id（如 backflip）→ 拒絕 + log（T4A-4）；
   - `ros2 action send_goal /nav/goto_relative`（未授權）→ reject（T4A-5）；
   - `route_id: "../../etc/x"` → 消毒拒絕（T4A-5）。
4. **回歸不破網**：`test_robot_control_service.py`（11 條 routing 權威）+ `test_reactive_stop_node.py`（27 cases；`docs/navigation/CLAUDE.md` 仍載舊數 17，T4A-7 文件債一併同步）+ 既有 fast-gate 全綠；auth-on 模式 demo 全流程（Studio 操作 → brain → Go2 動作 → trace 可見）真機走一輪。
5. **ladder 驗收**：T4B-1 表逐格抽查——每個 `hardware_proven`/`demo_ready` 格能指出具體 HITL 文件路徑；`research_prototype` 格在對外材料 grep 不到對應 claim。

---

## Jetson / Go2 requirement

**本 phase 是全套件 HITL 最重的一段：全段需要 Jetson + Go2 + Roy 在場，且不只一個 session。**

| 項 | Jetson | Go2 | 說明 |
|---|---|---|---|
| T4A-1 / T4A-2 | 需要 | 低度 | Studio/gateway/foxglove 回歸以 Jetson 為主；initialpose 遷移驗證需 nav stack 在跑 |
| T4A-3 / T4A-4 | 需要 | **需要（連線回歸，WebRTC 不可斷）** | DDS 收斂與 webrtc whitelist 直接動 Go2 通訊鏈，每改必驗 Go2↔Jetson 全鏈路 |
| T4A-5 / T4A-6 | 需要 | **需要（motion 回歸）** | nav action 授權與 mux 收斂動到「Go2 會不會動 / 停」本體，T4A-6 必排完整 nav lane session |
| T4B-2 / T4B-3 / T4B-4 / T4B-6 | 需要 | **需要（motion）** | lunge / orphan / profile / covariance 全是實機現象，WSL 不可重現 |
| T4B-1 / T4B-5 / T4A-7 | 不需 | 不需 | 純文件 / spec（但 T4B-1 依賴既有 HITL 證據與 A-1 決策） |

場地：indoor_tight 項在 Roy 家客廳可做；stop-resume auto / patrol / 歪斜診斷需大場地（學校）。安全紀律沿用 nav lane 既有鐵則（移動中禁 Damp、emergency_stop.py engage 為唯一移動中急停、teleop 嚴格 kill）。

---

## Done criteria

1. **入口清單封閉**：所有「能讓 Go2 動」的入口——gateway HTTP、gateway WS、DDS topic（`/brain/skill_request`、`/cmd_vel*`、`/webrtc_req`、`/tts_audio_raw`）、foxglove、nav action（`/nav/goto_*`、`/nav/run_route`）——逐項列表，**各有 owner + guard + 滲透驗證紀錄**（Tests §3 清單全擋）。
2. **gateway secure-default ON 常態化**：auth-on 模式下 Studio / CLI probe / demo 流程實機全綠，default-off 僅作緊急 fallback 保留。
3. **nav capability ladder 表完成**：每格有 HITL 證據路徑或明標 `research_prototype`；S1 簿記（A-1）、stop-resume 終局（A-9）兩決策 RESOLVED 並回寫。
4. **6/8-6/9 工程債清零**：orphaned-goal client 根治實機驗證、REACTIVE_PROFILE 驗收矩陣落檔、goal rejection reason 結構化、reactive_stop 文件債修畢。
5. **權威測試網擴充且全綠**：`test_robot_control_service.py` 含 whitelist/rate-limit 條目、nav_capability 含授權/消毒條目、fast-gate 無回歸。
6. 對應 master plan 系統 Phase 4 exit gate 四條（入口 owner+guard、secure-default 實機全綠、ladder 綁 HITL、每變更附回歸 session）全過。

---

## Rollback / fallback

- **每項 env-gated 或單 PR revert**：4A 各 task 獨立 PR，可單刀回退；不互相疊依賴（T4A-2 的兩 PR 例外：降權 PR 依賴遷移 PR，回退時先退降權）。
- **gateway flip 可退回 default-off**：S0-2 機制層的 env 開關保留，翻 default 後出問題一個 env 設回 default-off（已驗 byte-identical）。
- **foxglove 降權**：附原 launch 參數回復步驟（拿掉 `capabilities`/`address` 參數即回原行為）。
- **DDS 改動保留舊配置**：`cyclonedds.xml` 採新檔案 + `CYCLONEDDS_URI` 指向，回退＝unset env；`ROS_DOMAIN_ID` 改動記錄舊值於 `school_demo.env` 註解。
- **`/webrtc_req` whitelist**：whitelist 誤殺 demo 動作時 param 一鍵切到 **blacklist-only fallback mode**（行為等同現狀 + 拒絕 1030/1031/1301 三條）。注意：driver 現狀零過濾、**無既有黑名單路徑可「保留」**，此 fallback mode 須在 T4A-4 隨 whitelist 一併新建。
- **twist_mux / cmd_vel 收斂**：mux 拓撲變更前 tag；實機回歸不過即 revert，不帶病前進。
- **全域回滾點**：tag `post-demo-refactor-baseline-2026-06-10`（=`b1f0bc4`）+ `demo-2026-06-snapshot`。main 紅燈＝停新刀先修復。

---

## 6/18 freeze constraint

- **本 phase 全段在凍結解除（G5，6/18 期末發表結束）後才開工。** 理由：T4A-1③ 碰 `.claude/skills/`、T4A-2 碰 `start_*.sh` 與 demo 可視化工作流、T4A-3/4/5/6 動 Go2 通訊與 motion 鏈——全部命中凍結面或需要 demo 期不可承受的實機回歸。
- **唯一例外**：純文件工作——hardening P3-4（T4A-7 的 doc 部分）、本 plan 撰寫、T4B-1/T4B-5 的 spec 草擬——不碰 `executive.yaml` / `scripts/start_full_demo_tmux.sh` / `.claude/skills/` 三凍結面即可先行。
- **凍結期不翻任何 enforcement**：gateway access-control 維持 PR #158 的預設關（byte-identical 已驗）；foxglove 維持現狀（nav initialpose 工作流 demo 期仍依賴 Foxglove）。
- **demo snapshot forbidden claims 持續有效**：6/18 前後所有對外材料不得宣稱 ladder 上無 HITL 證據的能力；解除逐條走新 HITL 證據（T4B-1 表為登記處）。
