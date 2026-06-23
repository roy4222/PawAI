# Plan6 — Navigation Safety / S1 Fallback（2026-06-13）

> **Plan ID**：plan6　**角色**：Cloud/Fable = planner+reviewer；Codex = builder（依本檔 task packet 實作，**不擴張 scope、不改 runtime claim、未經 Roy 明確授權＋e-stop 就位不得發任何 Go2 motion**）。
> **狀態**：PLAN（本檔零 code、零 motion）。nav motion 維持 **`NOT_DEMO_READY`**。
> **權威來源**：根因分析 [`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-motion-incident-root-cause-plan.md`](../../navigation/2026-06-13-nav-motion-incident-root-cause-plan.md)；runbook [`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-incident-runbook.md`](../../navigation/2026-06-13-nav-incident-runbook.md)；能力階梯 [`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)；對外措辭 [`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)。
> **與其他 plan 的關係（不重複，只引用）**：
> - **plan1（資源 profiling）**：本 plan 的 S1 runtime 佈局（nav stack 能否與 brain 共存）**依賴 plan1 的 no-motion co-run profiling 三組（A brain-only / B brain+raw-LiDAR+Foxglove / C brain+full-nav-stack）結果**。本 plan 不重做 profiling、只在 §5/§11 引用其決策樹。
> - **plan2/conductor（demo_phase）**：`s1_nav=quiet` phase 的詞表/transition cleanup 屬 conductor plan，本 plan 只負責「s1_nav 這一幕的 nav 行為與 fallback 證據」。
> - **plan3/online-offline（台詞/timeout）**：S1 canned 台詞 `我正在移動到巡檢位置。`、`llm_timeout 6s` 屬 fallback plan，本 plan 不重複。
> - **plan5/security（route_id sanitize S8）**：S8 **已在 `route_validator.py` 實作**（見 §2.9），本 plan 僅以 **回歸驗證 task（NS-V1）** 確認 nav 路徑覆蓋，**ownership 歸 plan5**。
> - **Lane 6 nav v2 plan**（`docs/archive/superpowers-legacy/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md`）：indoor_tight 鎖定、initialpose SOP、reactive corridor 等實作細節由 Lane 6 owns；本 plan 的 task 與其對齊、不重抄。

---

## 1. Goal

讓 6/18 的 **s1_nav 這一幕在零自主導航風險下可交付**，並把 nav motion 的真相誠實管理在能力階梯上。具體三條：

1. **先把「事件根因」用 no-motion 診斷查清**（T0 URDF TF authority → R1 AMCL yaw → R2 超衝 → R3 reactive 側向 → R5 yaw-blind 閘），其中 **T0 必須最先用 `ros2 topic echo /tf_static` 排除**（它與 R1 都表現成「走歪」，且 code 級已確認 `go2.urdf` 把 `map→odom`/`odom→base_link` 當 fixed joint 發 `/tf_static`）。
2. **goto_relative 維持 `NOT_DEMO_READY`、且不是 S1 主線**（gotcha #4：R1 AMCL-yaw 注入、R2 0.5m→1.04m 超衝、T0 URDF 衝突）。S1 走**三層 fallback**：① 操作員輔助短前進（**DriveOnHeading body-frame**，僅 T0 修好 + D1-D5 全綠 + θ_error<5° + e-stop + n=3 全過才開）／② 遙控 + Foxglove LiDAR 證據／③ 遙控 + 純影片。
3. **對外措辭一律綁** [`nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md) **S1-S8（可講）/ F1-F10（禁講）**；safe-stop ≠ 繞障；motion HITL gate **降級**——6/18 live **不依賴它**，它只是「plan1 profiling 允許 nav stack 共存 **且** HITL 過」時的 optional upside。

---

## 2. Current State（cite code file:line，已親自讀檔驗證）

### 2.1 T0 — URDF 把 map/odom 當 fixed joint 發 /tf_static（CO-PRIMARY，須最先排除）
- `go2_robot_sdk/urdf/go2.urdf:48-58` = `odom_joint type="fixed"`（parent=`odom` child=`base_link`，identity rpy 0 0 0）。
- `go2_robot_sdk/urdf/go2.urdf:60-64` = `base_footprint_joint type="fixed"`（parent=`base_link` child=`base_footprint`，**保留、不動**）。
- `go2_robot_sdk/urdf/go2.urdf:70-80` = `map_joint type="fixed"`（parent=`map` child=`odom`，identity）。
- `go2_robot_sdk/launch/robot.launch.py:67` 單機載 `go2.urdf`；`:217,224-226,249-251` 起 `robot_state_publisher`（name=`go2_robot_state_publisher`）→ fixed joint 進 `/tf_static`。
- 與 AMCL 動態 `map→odom`（`nav2_params.yaml:38` tf_broadcast:true）+ driver 動態 `odom→base_link`（`ros2_publisher.py:29`，`GO2_PUBLISH_ODOM_TF=1`）形成**同 edge 雙 authority**（REP-105 禁）。

### 2.2 R1 — goto「前方」= AMCL map-frame yaw，無 body-frame 退路
- `nav_capability/nav_capability/lib/relative_goal_math.py:27-31`：`target_heading = current_yaw + yaw_offset` → `goal_x/y = c + d·cos/sin(target_heading)`（已讀檔確認）。
- `nav_action_server_node.py:259-266` `_current_map_pose` 唯一 yaw 來源 = AMCL `/amcl_pose`；goal 一律 `frame_id="map"`（`:462`）。

### 2.3 R2 — goto 不 enforce max_speed → 超衝
- `nav_action_server_node.py:406-414`（已讀檔）：`max_speed>0` 只 `logger.warn`「ignored in v1」，速度由 controller 決定。
- DWB 最低速：`nav2_params.yaml:158-164` `min_vel_x=0.45 / min_speed_xy=0.45 / max_vel_x=0.70`。
- 實測超衝：`docs/archive/navigation-legacy/research/2026-06-13-spec-d435-lidar-fusion.md:14-18`（0.5m goal → 1.04m）。

### 2.4 R3 — reactive_stop 側向幾何沉默
- `scripts/start_nav_capability_demo_tmux.sh:37-49`（已讀檔）：profile `open_space` = `front_arc_deg=30 / danger=1.1 / slow=1.7 / front_offset_rad=π`；`indoor_tight` = `front_arc_deg=18 / danger=1.0 / slow=1.4 / slow_speed=0.2 / normal_speed=0.3`。
- `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py:54-63`（classify）、`:109-112`（progressive 在 slow 回 None=沉默）；`reactive_stop_node.py:276`（active 只在 danger/emergency）。
- `front_arc_deg/danger/slow/front_offset_rad` 只在 `__init__` 讀（`reactive_stop_node.py:173-197` callback 只收 `enable_nav_pause/safety_only/mode`）→ **改 profile 必 kill 重啟**。

### 2.5 R5 — 靜態安全閘 yaw-blind
- `nav_action_server_node.py:252-257`（已讀檔）：`_amcl_covariance_xy` 回 `c[0]+c[7]`，**從不查 `c[35]`**。
- `nav_capability/lib/nav_ready_check.py:30-54`（已讀檔）：`compute_nav_ready` 只用 `covariance_xy`，position-only。
- `scripts/smoke_test_nav_static.sh`（13 KB，2026-06-13 改）：8 項全靜態，無一驗 heading / scan 對齊。

### 2.6 R6/外參 + LiDAR 前向軸
- `scripts/start_nav_capability_demo_tmux.sh:69-72`（已讀檔）：base_link→laser static `x=0.175 y=0 z=0.18 yaw=3.14159`（手設、無 per-session 校正）。
- `reactive_stop front_offset_rad=π` 與 TF yaw=π 是**雙重獨立補正、必須一致**。

### 2.7 DriveOnHeading 已部署（B 方案基礎）
- `nav2_params.yaml:74`（`nav2_drive_on_heading_bt_node`）、`:111`（cancel bt node）、`:347`（behavior_plugins 含 `drive_on_heading`）、`:352-353`（`plugin: nav2_behaviors/DriveOnHeading`）。已讀檔確認。
- nav2 default `speed=0.025`（< Go2 MIN_X 0.5）→ **action 端必須設 speed≥0.45 才會抬腳**（gotcha #4）。

### 2.8 D435 只是 Brain 層 gate，未進 costmap
- `interaction_executive/interaction_executive/safety_layer.py:133-140`（depth_clear/obstacle gate，direct action 不經此）。
- `nav2_params.yaml` costmap observation_sources 只有 `/scan_rplidar`（無 `/scan_d435`）。D435 目前有 Right MIPI / Hardware Error。

### 2.9 route_id sanitize（S8）已實作（plan5 owns）
- `nav_capability/nav_capability/lib/route_validator.py:8` `ROUTE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")`；`:24` `sanitize_route_name` **已拒** `%`（percent-encoding）、`.`/`..`、`/`、`\`（已讀檔確認）。
- 消費點：`log_pose_node.py:88,111-112`、`route_runner_node.py:233`、`nav_action_server_node.py:541`。
- ⟹ S8 **不是新功能**，本 plan 只做 **NS-V1 回歸覆蓋驗證**，主 ownership 在 plan5。

### 2.10 e-stop / 診斷工具皆已存在
- `nav_capability/scripts/emergency_stop.py`（mux pri 255）、`scripts/lidar_front_sector.py`、`scripts/scan_health_check.py`、`scripts/smoke_test_nav_static.sh` 皆在 disk。

### 2.11 今日硬體狀態（6/13 EOD）
- Go2 goto 0.3m 撞牆、e-stop engaged；nav stack 仍在跑（tmux nav-cap-demo）。D435 Right MIPI error。**先 NS-0 收場 + D0 evidence pull**。

---

## 3. Scope（本 plan 負責）

1. **T0 no-motion 診斷（D0/D1）** + **gated T0 remediation**（移除 `go2.urdf` `map_joint`/`odom_joint` fixed joint）。
2. **No-motion 診斷 D2-D5**（AMCL yaw、靜態 yaw-blind 實證、LiDAR 前向軸、reactive 側向幾何、covariance 收斂）的 SOP 文件化 + 缺的 probe 腳本規格。
3. **goto 前置 sanity 軟體閘**（c[35] yaw + 可選 scan-overlay；`nav_ready` 三拆）—— additive、預設寬到不誤擋、旗標可關。
4. **goto 限速/限距 watchdog**（治 R2 超衝）—— additive、旗標可關。
5. **HITL 路徑 fail-closed 前置**（goto 前確認 reactive zone≠danger + depth_clear）。
6. **initialpose yaw 校正 SOP + scan-overlay SOP** 文件。
7. **S1 三層 fallback 決策 + claim wording 鎖定**（每句綁 S1-S8/F1-F10）。
8. **DriveOnHeading speed-port 設定**（speed≥0.45）作為 live-motion option（非主線）。
9. **Motion HITL gate（H1→H2→H3）規格**（降級為 optional upside，依 plan1 profiling + Roy + e-stop）。
10. **NS-V1 route_id sanitize 回歸驗證**（覆蓋確認，ownership plan5）。

**精確檔案範圍**：`go2_robot_sdk/urdf/go2.urdf`、`go2_robot_sdk/launch/robot.launch.py`、`nav_capability/`（`nav_action_server_node.py`、`lib/nav_ready_check.py`、`lib/relative_goal_math.py`、`test/`）、`scripts/`（`nav_covariance_probe.py` 新、`start_nav_capability_demo_tmux.sh`、`smoke_test_nav_static.sh`）、`docs/architecture/navigation/`。

---

## 4. Forbidden Scope（本 plan 不做 / 禁止）

1. **不實作或改任何 runtime claim**——本檔只規劃；code 全交 Codex 依 task packet。
2. **不把 goto_relative 當 S1 主線**，**不讓任何 task 依賴 goto_relative**（gotcha #4）。
3. **不發任何 motion / goto / cmd_vel**——直到 T0 修好 + D1-D5 全綠 + θ_error<5° + e-stop 就位 + Roy 明確授權。
4. **不放寬 covariance 門檻值**（0.30/0.50 硬鎖，Lane 6 §5 禁）——只加 yaw 維度新檢查，不動既有 position 門檻數值。
5. **不寫 live SLAM / autonomous approach Roy / 動態繞障 / auto-resume 進 demo 主線**。
6. **不把 D435+LiDAR costmap fusion 寫成已完成**（只有 `depth_clear` fail-closed gate；fusion = research-only）。
7. **不做 full gateway secure-default flip / SROS2 / DDS isolation / Foxglove clientPublish full-cut**（route_id sanitize 已是唯一 byte-identical 的 confirmed runtime 變更，且 ownership 在 plan5）。
8. **不 claim**：autonomous navigation / fully-automatic live demo / fallen detection / 2m object / reliable color / 19 colors / 「goto 0.3m 就走 0.3m」/「靜態檢查通過＝可安全移動」。
9. **不對移動中的 Go2 送 `Damp`(1001)**；急停只用 `emergency_stop.py engage` + `StopMove`(1003)。
10. **不重複** plan1（profiling）、plan2（conductor 詞表/cleanup）、plan3（S1 台詞/timeout）、plan5（security 主體）的 task。
11. **不動** `start_full_demo_tmux.sh` / `executive.yaml` / `.claude/skills/`（任何改動需獨立 PR + demo smoke full green + Roy approval）。

---

## 5. Tasks（總表；每 task：id / task_type / P0-P2 / files / tests / rollback / demo_impact / needs_roy / needs_go2_motion）

> task_type ∈ `pure_software` | `jetson`（no-motion）| `go2_motion`。
> **P0 = 6/18 floor 必交**；P1 = additive upside；P2 = post-6/18。
> **凡 `go2_motion` 一律 needs_roy=YES + needs_go2_motion=YES，且 gate 在 plan1 profiling 結果 + T0 修好 + D1-D5 全綠 + e-stop。**

| id | 標題 | type | P | files | needs_roy | needs_motion | demo_impact |
|---|---|---|:-:|---|:-:|:-:|---|
| **NS-0** | 收場安全（Go2 停穩 + `pawai demo stop` + 清 nav stack 殘留） | jetson | P0 | — | YES | NO | 阻擋：殘留 stack 會吃 8GB + lock |
| **NS-D0** | 證據回收（`pawai evidence pull` 拉當天 `[PR1a]` + reactive status timeline） | pure_software | P0 | — | NO | NO | 定量 R1/R2/R3，無 demo 行為影響 |
| **NS-D1** | T0 TF authority no-motion 診斷（`echo /tf_static` 等） | jetson | P0 | — | NO | NO | 決定是否做 NS-T0；無行為影響 |
| **NS-T0** | gated T0 remediation：移除 `go2.urdf` map_joint/odom_joint | pure_software→jetson | P0 | `go2_robot_sdk/urdf/go2.urdf`、`go2_robot_sdk/launch/robot.launch.py`、`go2_robot_sdk/test/` | YES（驗收） | NO | 修 TF 衝突；**有 nav-stack regression 風險，必 D1 confirm 才做** |
| **NS-D2** | no-motion 診斷集 D2-D5（AMCL yaw / yaw-blind 實證 / LiDAR 軸 / reactive 側向 / covariance） SOP 化 | jetson | P0 | `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-no-motion-diagnostics-sop.md`（新） | NO | NO | 文件，無行為影響 |
| **NS-1** | goto 前置 yaw/scan sanity 閘 + `nav_ready` 三拆 | pure_software | P1 | `nav_capability/nav_capability/nav_action_server_node.py`、`lib/nav_ready_check.py`、`test/` | NO | NO | additive reject；旗標關＝byte-identical |
| **NS-2** | goto 限速/限距 watchdog（治 R2 超衝） | pure_software | P1 | `nav_capability/nav_capability/nav_action_server_node.py`、`test/` | NO | NO | additive；旗標關＝byte-identical |
| **NS-3** | HITL 路徑 fail-closed 前置（zone≠danger + depth_clear） | pure_software | P1 | `nav_capability/nav_capability/nav_action_server_node.py`、`test/` | NO | NO | additive；旗標關＝byte-identical |
| **NS-4** | covariance probe 腳本（含 c[35]）+ 黃帶決策表 | pure_software→jetson | P1 | `scripts/nav_covariance_probe.py`（新）、`docs/architecture/navigation/...sop.md` | NO | NO | 量測工具，無行為影響 |
| **NS-5** | initialpose yaw 校正 SOP + scan-overlay SOP 文件 | pure_software | P0 | `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-initialpose-yaw-calibration-sop.md`（新） | NO | NO | SOP；S1 fallback② 操作依據 |
| **NS-6** | S1 三層 fallback 決策 + claim wording 鎖定（綁 S1-S8/F1-F10） | pure_software | P0 | `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-s1-fallback-decision.md`（新，或併入既有 s1-nav plan 引用） | YES（D-1 拍板） | NO | 決定 S1 講什麼、演什麼 |
| **NS-7** | DriveOnHeading speed-port 設定（speed≥0.45）— live-motion option | pure_software | P1 | `nav_capability/`（新 thin client 或 action wrapper，**不動 goto_relative**）、`test/` | NO（code）/ YES（啟用） | NO（code） | wired_only，預設不接 demo |
| **NS-H1** | HITL：indoor_tight ±18° 安全錐驗證（safe-stop/clear/no misblock） | go2_motion | P1 | — | YES | YES | upside：過了才可講 S2/S4 現場版 |
| **NS-H2** | HITL：initialpose 朝向校正一輪（θ_error<5°） | go2_motion | P1 | — | YES | YES | upside：H3 前置 |
| **NS-H3** | HITL：短距 DriveOnHeading n=3 全達零撞零超衝 | go2_motion | P1 | — | YES | YES | upside：過了才升 S1 fallback① live |
| **NS-V1** | route_id sanitize 回歸覆蓋驗證（nav 路徑；ownership plan5） | pure_software | P0 | `nav_capability/test/test_route_validator.py`（補測，不改 prod） | NO | NO | byte-identical；確認 S8 nav 覆蓋 |

---

## 6. Pure Software Tasks（可 AFK，全附 tests + rollback；零 motion）

### NS-D0 — 證據回收（P0, pure_software, demo_impact=none, needs_roy=NO, needs_motion=NO）
- **做什麼**：`pawai evidence pull` 拉 `runtime/traces/*.jsonl` + nav_capability 備份（只讀）；在拉回的 nav log 找當天 `[PR1a]` goto ACCEPT/DONE/END（`accept_pose / goal / actual_dist_from_accept / duration`）+ `/state/reactive_stop/status` zone 時間線。
- **檔案**：無（只讀 CLI）。
- **tests**：N/A（讀取動作）；**驗收 = 把 `actual_dist_from_accept`、goal 方向、zone timeline 三個數字貼進 NS-D2 SOP 的「事件定量」欄**。
- **rollback**：只讀，無。

### NS-T0 — gated T0 remediation（P0, pure_software→jetson, demo_impact=修 TF；**有 regression 風險**, needs_roy=YES 驗收, needs_motion=NO）
> **前置硬門檻**：NS-D1 verdict = **CLEAR PASS 才做**（`/tf_static` 確含 `map→odom` 或 `odom→base_link` fixed edge + 雙 broadcaster／echo 卡 identity，見 §7 NS-D1 三值二元樹）。**CLEAR FAIL 或 AMBIGUOUS（含 rerun 後仍無法判定）一律不改 URDF**（AMBIGUOUS 預設 fail-safe = T0-clear、轉查 R1-R5），記錄並轉 R1。
- **做什麼**：移除 `go2_robot_sdk/urdf/go2.urdf` 的 `map` link + `map_joint`（:70-80）與 `odom` link + `odom_joint`（:48-58）；**保留 `base_footprint_joint`（:60-64）**。讓 `map→odom` 唯一 authority = AMCL、`odom→base_link` 唯一 authority = driver。
  - **不採用「換 `go2_on_steroids.urdf`」路徑**（會牽動更多 mount/sensor frame，超出本 task 範圍）。
- **風險（誠實標明，非 risk-free）**：① `robot_state_publisher` 是共享元件，URDF 拓撲改動可能影響其他 frame chain；② 移除 link 後若有節點硬訂 `map`/`odom` frame 自 RSP 取 → 需確認改由 AMCL/driver 發；③ 全 nav-stack regression（必跑 smoke + view_frames 復驗）。
- **檔案**：`go2_robot_sdk/urdf/go2.urdf`、（若 launch 有對 `map`/`odom` link 的硬引用）`go2_robot_sdk/launch/robot.launch.py`、`go2_robot_sdk/test/`。
- **tests**：
  1. **新單測** `go2_robot_sdk/test/test_urdf_tf_authority.py`：解析 `go2.urdf`，assert 不存在 parent=`map`/`odom` 的 fixed joint；assert `base_footprint_joint` 仍在。
  2. **Jetson no-motion 復驗**（驗收）：改後 `ros2 topic echo /tf_static --once` 不再出現 `map→odom`/`odom→base_link`；`ros2 run tf2_ros tf2_echo map odom` 隨 AMCL 變動（非卡 identity）；`bash scripts/smoke_test_nav_static.sh` 仍 8/8 PASS。
- **rollback**：單檔編輯，`git checkout go2_robot_sdk/urdf/go2.urdf go2_robot_sdk/launch/robot.launch.py` 一鍵退回原 `go2.urdf`；退回後 `echo /tf_static` 確認回到原狀。

### NS-1 — goto 前置 yaw/scan sanity 閘 + nav_ready 三拆（P1, pure_software, demo_impact=旗標關即 byte-identical, needs_roy=NO, needs_motion=NO）
- **做什麼**：在 `nav_action_server` goto 路徑加 **additive** 朝向 sanity 前置（**不改 covariance 門檻值**）：
  - 讀 `/amcl_pose` covariance `c[35]`（σ²yaw）：超新 param `yaw_cov_threshold`（預設寬到不誤擋，e.g. 0.50）→ reject reason `nav_not_ready:yaw_uncertain=<v>`。
  - （可選、預設 off）scan-overlay residual：旗標 `enable_scan_overlay_gate`（預設 false）。
  - `nav_ready` 拆 `position_ready / yaw_ready / scan_overlay_ready` 三旗（`compute_nav_ready` 旁加新函式，**不改既有簽名行為**）。
- **檔案**：`nav_capability/nav_capability/nav_action_server_node.py`、`nav_capability/nav_capability/lib/nav_ready_check.py`、`nav_capability/test/`。
- **tests**：`nav_capability/test/test_nav_action_server_rejection_reasons.py` 加 `yaw_uncertain` 路徑（紅綠：c[35] 超閾 → reject、未超 → 不影響 accept）；`test_nav_ready_check.py` 加 `yaw_ready`/三拆單測；**旗標關（`yaw_cov_threshold` 設極大 + scan-overlay off）→ 既有 accept 路徑 byte-identical**（回歸測試證明）。
- **rollback**：純 additive；`ros2 param set` 把 `yaw_cov_threshold` 設極大 + `enable_scan_overlay_gate=false` 即回舊行為；PR 可單獨 revert。

### NS-2 — goto 限速/限距 watchdog（P1, pure_software, demo_impact=旗標關即 byte-identical, needs_roy=NO, needs_motion=NO）
- **做什麼**：治 R2 超衝。二選一（Codex 選 watchdog，較不碰 controller 預設）：
  - **watchdog**（預設實作）：goto 期間累積 `actual_dist`（自 accept_pose 起算），超過 `goal.distance × (1 + overshoot_margin)`（新 param `overshoot_margin` 預設 0.5）→ cancel goal + log `goto_overshoot_cancel`。旗標 `enable_overshoot_watchdog`（預設 **true** 但僅在 goto 路徑生效）。
  - （不採）動態 set DWB `max_vel_x`：列為 Lane 6 後續，不在本 task。
- **檔案**：`nav_capability/nav_capability/nav_action_server_node.py`、`nav_capability/test/`。
- **tests**：`test_nav_action_server_overshoot.py`（新）：mock 位移 > 限 → watchdog 觸發 cancel（紅綠）；mock 位移正常 → 不觸發；`enable_overshoot_watchdog=false` → 完全不介入（byte-identical）。
- **rollback**：`ros2 param set ... enable_overshoot_watchdog false` 回舊行為；PR 單獨 revert。**不動 controller 速度本體值。**

### NS-3 — HITL 路徑 fail-closed 前置（P1, pure_software, demo_impact=旗標關即 byte-identical, needs_roy=NO, needs_motion=NO）
- **做什麼**：goto accept 前確認 `/state/reactive_stop/status` zone≠danger **且**（D435 在線時）`/capability/depth_clear==true`；任一不滿足 → reject `path_not_clear:<reason>`（fail-closed）。旗標 `enable_pregoto_safety_gate`（預設 true）。depth_clear stale>1s 視為 false。
- **檔案**：`nav_capability/nav_capability/nav_action_server_node.py`、`nav_capability/test/`。
- **tests**：`test_nav_action_server_pregoto_gate.py`（新）：zone=danger → reject；depth_clear=false → reject；zone=clear+depth_clear=true → 不影響 accept；旗標 off → byte-identical。
- **rollback**：`ros2 param set ... enable_pregoto_safety_gate false`；PR 單獨 revert。

### NS-4 — covariance probe 腳本 + 黃帶決策表（P1, pure_software→jetson, demo_impact=none, needs_roy=NO, needs_motion=NO）
- **做什麼**：新 `scripts/nav_covariance_probe.py`：訂 `/amcl_pose`，每秒記錄 `c[0]+c[7]`（position）**與 `c[35]`（yaw）**，輸出 CSV（time, cov_xy, cov_yaw）；靜止量收斂曲線。產出「黃帶決策表」（該等 / 該重設 / 該推 Go2 0.3m warmup，**含 yaw 維度**）寫進 NS-D2 SOP。
- **檔案**：`scripts/nav_covariance_probe.py`（新）、`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-no-motion-diagnostics-sop.md`。
- **tests**：`bash -n scripts/nav_covariance_probe.py` 不適用（python）→ 改 `python3 -m py_compile scripts/nav_covariance_probe.py`；新增純函式（covariance 取值 + CSV row 格式）單測 `nav_capability/test/test_nav_covariance_probe.py` 或 `scripts` 旁 test（紅綠）；CSV 輸出可被 re-parse。
- **rollback**：純新增量測工具，刪檔即回退（`git rm scripts/nav_covariance_probe.py`）。

### NS-5 — initialpose yaw 校正 SOP + scan-overlay SOP（P0, pure_software, demo_impact=S1 fallback② 操作依據, needs_roy=NO, needs_motion=NO）
- **做什麼**：寫 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-initialpose-yaw-calibration-sop.md`，步驟（全 no-motion）：
  - S5-1 讀外參：`tf2_echo base_link laser`（期望 yaw≈π）+ `ros2 param get /reactive_stop_node front_offset_rad`（須==π）。
  - S5-2 物理錨定（5/1 黃金標準）：**操作員站 Go2 機鼻 0.5m** → `python3 scripts/lidar_front_sector.py` → 應落 ±180° bin；不對則停、先修外參。
  - S5-3 Foxglove fixed frame：讀 scan 用 `base_link`、讀定位用 `map`。
  - S5-4 設 initialpose 後 `ros2 topic echo /amcl_pose --once` 讀完整 covariance，**人工讀 c[35]**；`tf2_echo map base_link` 比現場真值算 `θ_error`。
  - S5-5 判定：`|θ_error|>5-10°` → 重設、**不准發 goal**（這是 sanity hint，human-readable，**不是 auto-gate**）。
- **檔案**：`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-initialpose-yaw-calibration-sop.md`（新）。
- **tests**：dry-run 檢核（no motion）—— 由 NS-D2 SOP 的 checklist 涵蓋；文件無 code 風險。
- **rollback**：SOP 是流程，刪檔即回退。

### NS-6 — S1 三層 fallback 決策 + claim wording 鎖定（P0, pure_software, demo_impact=決定 S1 演什麼講什麼, needs_roy=YES 拍板 D-1, needs_motion=NO）
- **做什麼**：寫 `docs/archive/navigation-legacy/incident-runbooks/2026-06-13-s1-fallback-decision.md`（或併入 s1-nav plan 並從本 plan 引用），內容：
  - **① live 短距（DriveOnHeading）**：僅 T0 修好 + D1-D5 全綠 + θ_error<5° + e-stop + NS-H3 n=3 全過才開；speech 綁 S1-S8。
  - **② 遙控 + Foxglove LiDAR 證據**（**預設主線**）：遙控/Studio 輔助移動，Studio map + LiDAR 點雲 + reactive 狀態作「邊緣端即時感知」證據；可講 S2（safe-stop 配標準說法）、S4（窄場安全錐）、S6（拒絕有理由）。
  - **③ 遙控 + 純影片**（保底）：S1 已錄影片，旁白用保守版。
  - **claim 鎖定表**：每一句台詞對映 [`nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md) 的 S1-S8（可講）；列禁句 F1-F10（自主導航/動態繞障/D435 已融合/auto-resume/「聽懂就走到 Roy 身邊」/「goto 0.3m 就走 0.3m」/「靜態檢查通過＝可安全移動」）。**safe-stop ≠ 繞障** 標準措辭。
- **檔案**：`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-s1-fallback-decision.md`（新）。
- **tests**：文件 review（Cloud adversarial overclaim 掃描，見 §Cloud Review Checklist）；無 code。
- **rollback**：刪檔即回退；影片保底永遠在。

### NS-7 — DriveOnHeading speed-port 設定（P1, pure_software code / 啟用 needs_roy, demo_impact=wired_only 預設不接 demo, needs_roy=NO code/YES 啟用, needs_motion=NO code）
- **做什麼**：寫一個 thin action client / wrapper 呼叫 nav2 `/drive_on_heading`，**把 `speed` port 設 ≥0.45**（default 0.025 無法抬腳，gotcha #4）+ `dist_to_travel` 限 ≤0.5m + `time_allowance` 合理。**完全不動 `goto_relative`**。預設不接 demo（wired_only）。
- **檔案**：`nav_capability/nav_capability/`（新 `drive_on_heading_client.py` 或 script）、`nav_capability/test/`。
- **tests**：純函式單測（goal 組裝：speed clamp ≥0.45、dist ≤0.5、frame=body/odom 不依賴 AMCL yaw）；mock action client 路由單測（**不發真 motion**）。
- **rollback**：新獨立檔，刪檔即回退；不影響 goto_relative。

### NS-V1 — route_id sanitize 回歸覆蓋驗證（P0, pure_software, demo_impact=byte-identical, needs_roy=NO, needs_motion=NO；ownership plan5）
- **做什麼**：**不改 prod code**（`route_validator.py` S8 已實作）。補/確認 `test_route_validator.py` 覆蓋：good `[A-Za-z0-9_-]+` 100% pass、bad（`/`、`..`、`%2e%2e`、`a/b`、`a\\b`、空字串、`.`）100% reject；確認 nav 消費點（`log_pose_node.py:88,111-112`、`route_runner_node.py:233`、`nav_action_server_node.py:541`）都過 `sanitize_route_name`。
- **檔案**：`nav_capability/test/test_route_validator.py`（補測）。
- **tests**：`python3 -m pytest nav_capability/test/test_route_validator.py -v`（全綠）。
- **rollback**：只加測試，刪測試即回退。

---

## 7. Jetson Tasks（no-motion，全在 Go2 站立不動下執行）

### NS-0 — 收場安全（P0, jetson, needs_roy=YES, needs_motion=NO）
- 確認 Go2 已停穩（e-stop engaged）→ `pawai demo stop`（依 lock lane 路由清 nav stack/driver）→ `tmux ls` + `ros2 node list` 確認殘留清空。**8GB 互斥：S1 nav stack 必須停掉，brain demo（S2-S5）才能起**（依 plan1 profiling 決策）。
- **tests**：`ros2 node list` 無 nav_capability/driver 殘留；`nvidia-smi`/`tegrastats` 確認 RAM 釋放。
- **rollback**：無（清理動作）。

### NS-D1 — T0 TF authority no-motion 診斷（P0, jetson, needs_roy=NO, needs_motion=NO）
> **最先做、其他診斷的前置門檻。** 全唯讀。
```bash
ros2 topic echo /tf_static --once          # ❗ 若含 frame_id=map child=odom 或 frame_id=odom child=base_link → T0 成立
ros2 run tf2_tools view_frames             # frames.pdf：map→odom / odom→base_link broadcaster 是否 >1
ros2 run tf2_ros tf2_echo map odom         # 動（AMCL 修正）vs 卡 identity(0,0,0)
ros2 run tf2_ros tf2_echo odom base_link   # 隨 odom 變 vs 卡 identity
ros2 run tf2_ros tf2_monitor               # 每 edge broadcaster 數量
```
- **判讀（三值二元樹，消歧義；含 AMBIGUOUS 預設行為）**：
```
NS-D1 verdict tree（逐項判，全 no-motion）：

CLEAR PASS（T0 成立 → gate 開、做 NS-T0）
   = /tf_static 明確含 (frame_id=map child=odom) 或 (frame_id=odom child=base_link) 的 fixed edge
     【且】tf2_monitor 顯示該 edge broadcaster 數 >1（RSP + AMCL/driver 雙發）
     或 tf2_echo map odom 卡 identity(0,0,0) 不隨 AMCL 動。
   → T0 確認，觸發 NS-T0 remediation。

CLEAR FAIL（T0 不成立 → 跳過 NS-T0、不改 URDF、轉查 R1-R5）
   = /tf_static 完全不含 map→odom 也不含 odom→base_link
     【且】tf2_echo map odom 隨 AMCL 正常變動。
   → T0 反證，記錄、不改 URDF、改查 R1（AMCL yaw）等。

AMBIGUOUS（部分輸出 / 只見一條 edge / echo timeout / broadcaster 數讀不出）
   → 先 rerun：ros2 topic echo /tf_static（去 --once，看完整快照）
              + ros2 run tf2_ros tf2_monitor（跑 ≥10s 取 broadcaster 統計）
              + tf2_echo map odom 跑 ≥5s 觀察是否變動。
   → 若 rerun 後落 CLEAR PASS / CLEAR FAIL → 照該 branch。
   → 若仍 AMBIGUOUS（無法判定）→ **DEFAULT = 視為 T0-clear（CLEAR FAIL 處理）**：
        ★ 不改 URDF ★、不做 NS-T0、記錄為「T0 inconclusive」、轉查 R1-R5。
        （理由：URDF 改動有 nav-stack regression 風險，不確定時 fail-safe = 不動 URDF。）
```
- **tests**：判讀輸出（落哪個 verdict + 原始 echo/monitor log）存檔進 NS-D2 SOP。**rollback**：只讀，無。

### NS-D2 — no-motion 診斷集 D2-D5 SOP 化（P0, jetson, needs_roy=NO, needs_motion=NO）
- 把以下唯讀診斷寫成可貼上的 SOP（`docs/archive/navigation-legacy/incident-runbooks/2026-06-13-no-motion-diagnostics-sop.md`）：
  - **D2 AMCL yaw/covariance**：`ros2 topic echo /amcl_pose --once`（讀 c[0]/c[7]/c[35]）+ `tf2_echo map base_link` vs 現場 + `ros2 topic echo /capability/nav_ready --once`（yaw 大錯時是否仍 true → 證 R5）。
  - **D3 LiDAR 前向軸**：`tf2_echo base_link laser` + `ros2 param get /reactive_stop_node front_offset_rad`（須==π）+ `python3 scripts/lidar_front_sector.py`（人站機鼻→±180° bin）+ `python3 scripts/scan_health_check.py`。
  - **D4 reactive 側向幾何**（只移障礙物、零 Go2 motion）：`ros2 param get /reactive_stop_node front_arc_deg` + 移箱到 +25°/1.65m → `ros2 topic echo /state/reactive_stop/status`（預期 slow/active=false）+ `ros2 topic hz /scan_rplidar`。
  - **D5 靜態 smoke**：`bash scripts/smoke_test_nav_static.sh`（8/8 但提醒「過了≠朝向對」）+ `ros2 action list | grep -E "goto_relative|drive_on_heading"` + `ros2 topic echo /capability/depth_clear --once`。
  - **D（covariance 曲線）**：`python3 scripts/nav_covariance_probe.py`（NS-4 產出）。
- **tests**：SOP dry-run（逐條跑過、判讀填表）。**rollback**：文件，刪檔回退。

---

## 8. Go2 HITL Tasks（motion，全 needs_roy=YES + needs_go2_motion=YES + e-stop）

> **降級聲明**：本節 motion HITL gate **是 optional upside，6/18 live 不依賴它**。只有當 **plan1 profiling 顯示 nav stack 可與 brain 共存（或可分時切換）** **且** 下列 H1→H2→H3 全過，S1 才升級到 fallback① live 短距；否則 S1 走 fallback②（遙控+Foxglove）或 ③（影片）。
>
> **硬前置（全 PASS 才可開始任何 motion）**：NS-T0 修好（D1 復驗 `/tf_static` 乾淨）+ NS-D2 全綠（θ_error<5° 已用 SOP 校正）+ `indoor_tight` profile（kill 重啟帶 `REACTIVE_PROFILE=indoor_tight`）+ e-stop（`nav_capability/scripts/emergency_stop.py engage` 終端就位 + 口頭確認）+ 淨空場地。
> **硬性 abort（沿用 Lane 6 §8）**：非命令方向移動 / 該停沒停 / 機鼻<0.3m 仍動 → **當場 e-stop + 該項 FAIL**。**不對移動中 Go2 送 Damp(1001)**。

### NS-H1 — indoor_tight ±18° 安全錐驗證（P1, go2_motion, needs_roy=YES, needs_motion=YES）
- **做什麼**：indoor_tight profile 下，人/箱進正前 0.8-1.0m → 看 reactive danger 停（safe-stop）；移開 → zone 回 clear/slow；確認 ±18° 不誤擋右前角 off-path 家具（6/9 HITL 模式）。**這步可只測 reactive stop（Go2 站立、僅推障礙），最小 motion。**
- **中止**：e-stop / `pawai demo stop`。
- **升級對象**：ladder C4（safe-stop with limit 復驗）；過了才可講「現場 S2/S4」。
- **rollback**：profile 切換是 kill 重啟，回 open_space 即原狀；無持久變更。

### NS-H2 — initialpose 朝向校正一輪（P1, go2_motion 前置 no-motion 為主, needs_roy=YES, needs_motion=YES 僅 S5-4 極小自轉）
- **做什麼**：依 NS-5 SOP 設 initialpose → 物理錨定 → 讀 c[35] → 算 θ_error；**S5-4 極小角度自轉（≤30°，operator 手動、e-stop 待命）**確認 scan 朝向同步、無跳變。目標 `θ_error<5°`。
- **中止**：e-stop。**升級對象**：NS-H3 前置。
- **rollback**：不改 AMCL 參數；重設 initialpose 即可。

### NS-H3 — 短距 DriveOnHeading n=3（P1, go2_motion, needs_roy=YES, needs_motion=YES）
- **做什麼**：NS-7 wrapper（speed≥0.45、dist≤0.3m）發 DriveOnHeading × n=3，每發記 actual 位移 + 方向 + covariance（含 c[35]）。**全 3 發達零撞、零超衝（actual ≤ dist×1.2）、方向正確才 PASS**。
  - **明確不用 goto_relative**（gotcha #4：DriveOnHeading 不靠 AMCL yaw，繞過 R1）。
- **中止**：e-stop / `pawai demo stop`。**升級對象**：ladder C1 升級候選 + S1 fallback① 解鎖。任一發 FAIL → S1 退 fallback②/③。
- **rollback**：DriveOnHeading 是既有 nav2 behavior，停止發 action 即無 motion；無持久變更。

---

## 9. Tests（彙整；每項對映 task）

**Pure-software 單測（Codex 必跑、必綠）**
```bash
# NS-T0
python3 -m pytest go2_robot_sdk/test/test_urdf_tf_authority.py -v
# NS-1
python3 -m pytest nav_capability/test/test_nav_action_server_rejection_reasons.py -v
python3 -m pytest nav_capability/test/test_nav_ready_check.py -v
# NS-2
python3 -m pytest nav_capability/test/test_nav_action_server_overshoot.py -v
# NS-3
python3 -m pytest nav_capability/test/test_nav_action_server_pregoto_gate.py -v
# NS-4
python3 -m py_compile scripts/nav_covariance_probe.py
python3 -m pytest nav_capability/test/test_nav_covariance_probe.py -v
# NS-7
python3 -m pytest nav_capability/test/test_drive_on_heading_client.py -v
# NS-V1
python3 -m pytest nav_capability/test/test_route_validator.py -v
# 既有回歸（不得退）
python3 -m pytest nav_capability/test/ -v
cd go2_robot_sdk && python3 -m pytest test/test_reactive_stop_node.py --no-cov && cd ..
```

**Byte-identical 回歸（NS-1/2/3 旗標關）**：在旗標全關（`yaw_cov_threshold` 極大、`enable_scan_overlay_gate=false`、`enable_overshoot_watchdog=false`、`enable_pregoto_safety_gate=false`）下，既有 goto accept/reject 行為與改前一致（用既有 `test_nav_action_server_*` 既有 case 證明未變）。

**Jetson no-motion 驗收（NS-T0/NS-D1/NS-D2，零 motion）**：見 §7 指令集；NS-T0 後 `echo /tf_static` 乾淨 + `tf2_echo map odom` 隨 AMCL 動 + smoke 8/8。

**Go2 HITL（NS-H1/H2/H3，needs_roy + e-stop）**：見 §8 PASS/abort 標準。

---

## 10. Rollback（彙整）

| task | rollback 指令 / 動作 |
|---|---|
| NS-T0 | `git checkout go2_robot_sdk/urdf/go2.urdf go2_robot_sdk/launch/robot.launch.py` → `echo /tf_static` 復驗回原狀 |
| NS-1 | `ros2 param set /nav_action_server yaw_cov_threshold 1e9 && ros2 param set /nav_action_server enable_scan_overlay_gate false`；或 revert PR |
| NS-2 | `ros2 param set /nav_action_server enable_overshoot_watchdog false`；或 revert PR |
| NS-3 | `ros2 param set /nav_action_server enable_pregoto_safety_gate false`；或 revert PR |
| NS-4 | `git rm scripts/nav_covariance_probe.py`（純工具） |
| NS-5/NS-6/NS-D2 | 刪文件即回退（流程文件，無 code 風險） |
| NS-7 | 刪 `drive_on_heading_client.py`（wired_only，不影響 goto_relative） |
| NS-V1 | 刪測試（不改 prod） |
| HITL H1/H2/H3 | 現場 e-stop / `pawai demo stop`；profile/pose 無持久變更 |

> **param-set rollback 的失效模式（誠實標明）**：NS-1/2/3 的 `ros2 param set` rollback **假設 ROS2 bridge 仍可回應**。若 bridge down / node 已掛 / param 服務無回應（`ros2 param set` timeout）→ **param-set 路徑不可用**，改走**第二退路 = `git revert <sha>` + `colcon build --packages-select nav_capability` + 重啟 nav stack**（旗標純 additive，revert 後 byte-identical）。**第三退路 = 整 stack 退場**（`pawai demo stop --force` → S1 走 fallback②/③ 影片，nav 完全不啟）。三退路任一成立，不依賴單一 param-set 成功。

**全域保守 fallback**：6/18 S1 任何時刻退到 fallback③（純影片 + 遙控），nav 段全用保守旁白。**covariance 門檻值零變動**（Lane 6 §5）。

---

## 11. Done Criteria（6/18 floor 與 upside 分離）

**FLOOR（P0，必達，6/18 可交）**
1. NS-0 收場乾淨（Go2 停穩、nav stack 清、8GB 釋放可起 brain）。
2. NS-D0 拿到當天 `[PR1a]` + reactive timeline，R1/R2/R3 定量寫進 SOP。
3. NS-D1 完成（T0 confirm/反證有結論）；**若 T0 confirm → NS-T0 修好 + `/tf_static` 復驗乾淨 + smoke 8/8**。
4. NS-D2 / NS-5 SOP 成文且 dry-run 過。
5. NS-6 S1 三層 fallback 決策 + claim wording 鎖定（Roy 拍板 D-1）；每句綁 S1-S8、無 F1-F10。
6. NS-V1 route_id sanitize nav 覆蓋回歸全綠。
7. **S1 主線預設 = fallback②（遙控+Foxglove）**，影片③保底就緒。

**UPSIDE（P1，依 plan1 profiling + HITL，過了才升）**
- NS-1/NS-2/NS-3/NS-4/NS-7 軟體 merged + 單測綠 + 旗標關 byte-identical（standby，不接 demo 也可）。
- **僅當 plan1 profiling 允許 nav stack 共存/分時 且 NS-H1→H2→H3 全過** → S1 升 fallback① live 短距（DriveOnHeading），claim 才加「單點短距、n=3」（仍不講 autonomous/reliable）。

**永不（post-6/18 / DO_NOT_CLAIM）**：autonomous navigation、動態繞障、auto-resume、D435+LiDAR costmap fusion、1.0m+ 連續導航、approach person、自由巡邏。

---

## 12. Execution Order

```
Step 0（收場，最先）       NS-0  → Go2 停穩、清 nav stack（needs_roy）
Step 1（證據，dev 機）      NS-D0 → evidence pull、定量事件
Step 2（T0 診斷，最先做的 Jetson 項） NS-D1 → echo /tf_static 排除/確認 T0
   ⚠ 順序乾淨度：NS-D1 須在 plan1 config-C profiling【之前或之後另起乾淨 nav-only session】跑，
     不在 config-C 量測中途插入。/tf_static 是 robot_state_publisher 開機 latch（AMCL 動態 TF 走 /tf 非 /tf_static），
     故 AMCL 在跑【不會】污染 /tf_static 的 fixed-edge 判讀；但 tf2_monitor 的 broadcaster 計數會受同時起的節點影響
     → 跑 NS-D1 時記錄「當下起了哪些節點」，避免把 profiling 期的額外 broadcaster 誤算進 T0 雙 authority 判定。
Step 3（gated 修法）        NS-T0（僅 D1 confirm）→ 改 URDF + 復驗 /tf_static + smoke
Step 4（no-motion SOP）     NS-D2 / NS-5 → 診斷集 + initialpose SOP 成文
Step 5（決策 + 措辭）       NS-6（Roy D-1）→ S1 三層 fallback + claim 鎖定
                          NS-V1 → route_id sanitize 覆蓋
── 以上完成即 6/18 FLOOR 可交（S1=fallback②） ──
Step 6（軟體 upside，可 AFK 並行 Step 4-5） NS-1 / NS-2 / NS-3 / NS-4 / NS-7
Step 7（HITL upside，needs plan1 profiling + Roy + e-stop） NS-H1 → NS-H2 → NS-H3
                          全過 → S1 升 fallback① live；否則維持 fallback②/③
```

**跨 plan 依賴**：Step 7 的「能不能跑 nav stack」**等 plan1 profiling 三組決策樹**（C stable → nav 可共存/分時；B stable / C not → fallback②；B unstable → fallback③ 影片）。Step 5 的 S1 台詞與 plan3（台詞/timeout）、plan2（s1_nav=quiet phase）對齊。

---

## 13. Codex Implementation Prompt

> 你是 builder。依本檔 task packet 實作 **NS-T0 / NS-1 / NS-2 / NS-3 / NS-4 / NS-7 / NS-V1**（pure-software 與 gated URDF）。**嚴禁**：擴張 scope、改 runtime claim、依賴或修改 `goto_relative`、放寬 covariance 門檻值、發任何 Go2 motion。每個 task 一個小 PR，附 diff + test 結果 + risk。所有新行為旗標預設 **關＝byte-identical**（NS-2/NS-3 預設 on 但只在 goto 路徑生效，且關掉可回舊行為）。NS-T0 **僅在 Cloud 確認 NS-D1 `/tf_static` 真含 `map→odom`/`odom→base_link` 後**才動 URDF；先寫 `test_urdf_tf_authority.py`（red）再改。完成回報：①改了哪些 file:line ②跑哪些 test、結果貼上 ③旗標關的 byte-identical 證明 ④風險與 rollback 指令。

---

# Codex Implementation Packet

### 共同規範
- **語言**：程式碼/param/path identifier 一律 verbatim（`yaw_cov_threshold`、`enable_overshoot_watchdog`、`enable_pregoto_safety_gate`、`enable_scan_overlay_gate`、`drive_on_heading`、`sanitize_route_name`）。
- **commit 結尾**：`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- **不碰**：`start_full_demo_tmux.sh`、`executive.yaml`、`.claude/skills/`、covariance 門檻值（0.30/0.50）、`goto_relative` 行為。

### Packet NS-T0（gated；先等 Cloud 給 D1 confirm 綠燈）
- **exact files**：`go2_robot_sdk/urdf/go2.urdf`（移除 lines 47-58 `odom` link+`odom_joint`、lines 69-80 `map` link+`map_joint`；**保留** lines 60-64 `base_footprint_joint`）、必要時 `go2_robot_sdk/launch/robot.launch.py`（若有硬引用 `map`/`odom` link）、新 `go2_robot_sdk/test/test_urdf_tf_authority.py`。
- **exact tests**：`python3 -m pytest go2_robot_sdk/test/test_urdf_tf_authority.py -v`（assert 無 parent=map/odom 的 fixed joint、base_footprint_joint 仍在）。
- **exact commands**：`colcon build --packages-select go2_robot_sdk && source install/setup.bash`（驗 RSP 仍起）。
- **acceptance**：單測綠 + Cloud 確認 Jetson 復驗 `echo /tf_static` 乾淨 + smoke 8/8（Cloud 主持，Codex 不上 Jetson）。

### Packet NS-1
- **exact files**：`nav_capability/nav_capability/nav_action_server_node.py`（加 `yaw_cov_threshold` declare + goto 前 c[35] 讀取/reject）、`nav_capability/nav_capability/lib/nav_ready_check.py`（加 `compute_nav_ready_split` 回 position/yaw/scan 三旗，**不改 `compute_nav_ready`**）、`nav_capability/test/test_nav_action_server_rejection_reasons.py`、`nav_capability/test/test_nav_ready_check.py`。
- **exact tests**：見 §9 NS-1 兩條。**acceptance**：yaw_uncertain 紅綠過 + 旗標關（threshold 1e9）既有 case 全綠。

### Packet NS-2
- **exact files**：`nav_capability/nav_capability/nav_action_server_node.py`（加 `overshoot_margin` + `enable_overshoot_watchdog` declare + goto 累積 actual_dist watchdog）、`nav_capability/test/test_nav_action_server_overshoot.py`（新）。
- **exact tests**：見 §9 NS-2。**acceptance**：mock 超距 cancel 紅綠過 + 旗標 off byte-identical。

### Packet NS-3
- **exact files**：`nav_capability/nav_capability/nav_action_server_node.py`（加 `enable_pregoto_safety_gate` declare + 訂 `/state/reactive_stop/status` + `/capability/depth_clear` + accept 前 fail-closed 檢查）、`nav_capability/test/test_nav_action_server_pregoto_gate.py`（新）。
- **exact tests**：見 §9 NS-3。**acceptance**：zone=danger / depth_clear=false reject 紅綠 + 旗標 off byte-identical。

### Packet NS-4
- **exact files**：`scripts/nav_covariance_probe.py`（新，訂 `/amcl_pose`、輸出 CSV time/cov_xy/cov_yaw）、`nav_capability/test/test_nav_covariance_probe.py`（純函式：covariance 取值 + CSV row）。
- **exact tests**：`python3 -m py_compile scripts/nav_covariance_probe.py` + pytest。**acceptance**：CSV 可 re-parse、c[35] 有寫入。

### Packet NS-7
- **exact files**：`nav_capability/nav_capability/drive_on_heading_client.py`（新，thin action client，speed clamp ≥0.45、dist ≤0.5、**不依賴 AMCL yaw**、wired_only）、`nav_capability/test/test_drive_on_heading_client.py`（mock client，不發真 motion）。
- **exact tests**：見 §9 NS-7。**acceptance**：speed/dist clamp 單測過；確認**不 import** `relative_goal_math` / `goto_relative` 路徑。

### Packet NS-V1
- **exact files**：`nav_capability/test/test_route_validator.py`（補測，**不改 prod**）。
- **exact tests**：`python3 -m pytest nav_capability/test/test_route_validator.py -v`。**acceptance**：good 全 pass、bad（`/`/`..`/`%2e%2e`/`a/b`/`a\b`/空/`.`）全 reject。

---

# Cloud Review Checklist

審 Codex 每個 PR 時，Cloud（Fable）逐條確認：

1. **零 motion**：diff 不含任何 `cmd_vel` publish / `Move(1008)` / `goto_relative` 觸發（除 NS-7 的 wired_only mock client，且其單測不發真 action）。
2. **不依賴 goto_relative**：NS-7 不 import `relative_goal_math`，不靠 AMCL yaw。
3. **byte-identical**：NS-1/2/3 旗標關時既有 `test_nav_action_server_*` case 全綠（要求 Codex 貼旗標關的回歸輸出）。
4. **covariance 門檻零變動**：grep diff 確認沒動 `0.30`/`0.50`/`covariance_threshold` 既有值（只加 yaw 維度新 param）。
5. **NS-T0 gate**：確認 Codex 收到 Cloud 的 D1 confirm 才改 URDF；`base_footprint_joint` 保留；單測先 red 後 green。
6. **overclaim 掃描**（NS-5/NS-6 文件）：無「autonomous / reliable nav / 繞障 / D435 已融合 / fallen / auto-resume / goto 0.3m 就走 0.3m / 靜態通過＝可安全移動」；每句台詞對得上 S1-S8。
7. **demo-break 掃描**：未動 `start_full_demo_tmux.sh` / `executive.yaml` / `.claude/skills/`；新 param 都有 declare 預設、不需 yaml。
8. **rollback 可執行**：每 PR 附 §10 對映的 rollback 指令，且 Cloud 實際確認旗標 set 能回舊行為。
9. **test 真跑**：要求 test 結果原文（非「應該會過」），紅綠都看。
10. **scope**：無「順便清理/重構」；只動 packet 列的 file。

---

# Stop Conditions

**立即停止（不得繼續）**
1. 任何時刻 Go2 非命令方向移動 / 該停沒停 / 機鼻<0.3m 仍動 → e-stop（`emergency_stop.py engage`）+ 該 motion 項 FAIL。
2. e-stop 未就位 → **不開始任何 motion 項**（NS-H1/H2/H3 全擋）。
3. **NS-D1 未做 / `/tf_static` 結論未知** → 不發任何 goto、不做 NS-T0。
4. **θ_error 未知或 >5-10°**（NS-D2/NS-5 未過）→ 不發任何 goto。
5. profile=open_space（±30°）在窄客廳 → 不發短 goto（必先 `REACTIVE_PROFILE=indoor_tight` kill 重啟）。
6. **plan1 profiling 顯示 nav stack 無法共存/分時** → 不啟 nav stack 做 HITL，S1 直接走 fallback②/③。
7. Codex PR 改了 covariance 門檻值 / 動了 goto_relative / 動了 forbidden 檔案 → reject、要求重做。
8. NS-T0 改後 smoke 不再 8/8 或 `tf2_echo map odom` 卡 identity → 立即 `git checkout` 退回原 URDF。

**Rollback 觸發**：見 §10。任一 HITL FAIL 不連坐——ladder 照實標、claim wording 對應降級。

---

# Required Evidence

交付前必須附（Cloud 驗收憑據）：

| 項目 | 證據 | 來源 |
|---|---|---|
| 事件定量 | 當天 `[PR1a]` goal 方向 + `actual_dist_from_accept` + duration + reactive zone timeline | NS-D0 `pawai evidence pull` |
| T0 結論 | `echo /tf_static` 輸出（含/不含 map→odom、odom→base_link）+ `tf2_monitor` broadcaster 數 | NS-D1 |
| T0 修好 | 改後 `echo /tf_static` 乾淨 + `tf2_echo map odom` 隨 AMCL 動 + `smoke_test_nav_static.sh` 8/8 | NS-T0 復驗 |
| 軟體單測 | NS-T0/1/2/3/4/7/V1 pytest 全綠原文 + 旗標關 byte-identical 回歸 | Codex PR |
| SOP dry-run | NS-D2 / NS-5 逐條判讀填表 | NS-D2/NS-5 |
| S1 決策 | NS-6 三層 fallback + claim 鎖定表（Roy D-1 簽核） | NS-6 |
| HITL（如做） | NS-H1 safe-stop 截圖/log、NS-H2 θ_error<5°、NS-H3 n=3 actual/方向/c[35] | §8（needs_roy+e-stop） |

---

## Rollback Plan（總綱，呼應 §10）

- **軟體（NS-1/2/3/4/7/V1）**：全 additive / 旗標預設可關回 byte-identical；各自獨立 PR，`git revert <sha>` 或 `ros2 param set` 即退。
- **URDF（NS-T0）**：單檔，`git checkout go2_robot_sdk/urdf/go2.urdf` 一鍵退；退後 `echo /tf_static` 復驗回原狀；保留原 `go2.urdf` 為 baseline。
- **文件（NS-5/6/D2）**：刪檔即退，無 runtime 風險。
- **HITL motion**：現場 e-stop / `pawai demo stop` 路由 nav lane cleanup；profile/pose 無持久變更。
- **全域**：6/18 S1 任何時刻退 fallback③（影片 + 遙控 + 保守旁白）；nav motion 維持 `NOT_DEMO_READY`，能力階梯與 claim wording 對應降級。
</content>
</invoke>
