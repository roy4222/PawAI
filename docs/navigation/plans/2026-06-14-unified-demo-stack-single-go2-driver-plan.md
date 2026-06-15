# PawAI Unified Demo Stack / Single Go2 Driver Navigation Integration Plan

> **日期**：2026-06-14　**狀態**：PLAN / RESEARCH ONLY（**未實作、未跑、未碰執行中 demo、零 motion**）
> **這份是什麼**：把「brain demo 與 nav stack 各自起一份 Go2 driver」這個架構斷層，收斂成「單一 Go2 driver、brain + nav 共用」的目標架構與分階段計畫。**每一步都標 6/18-able vs post-6/18**，nav 宣稱全綁既有禁講清單。
> **權威關係**：
> - nav 對外措辭與禁講清單以 [`2026-06-13-nav-618-claim-wording.md`](../2026-06-13-nav-618-claim-wording.md)（S1-S8 可講 / F1-F10 禁講）為準；本檔不新增任何可講宣稱。
> - S1（nav 幕）fallback 與「`goto_relative`/`DriveOnHeading` = NOT_DEMO_READY」硬前提以 [`2026-06-13-s1-fallback-decision.md`](../2026-06-13-s1-fallback-decision.md) §0 為準。
> - 撞牆根因（T0 URDF dual-authority / R1 AMCL yaw / R2 overshoot / R3 reactive 沉默 / R5 yaw-blind 閘）以 [`2026-06-13-nav-motion-incident-root-cause-plan.md`](../2026-06-13-nav-motion-incident-root-cause-plan.md) 為準。
> - 共存 profiling 程序與 OOM 判定以 [`2026-06-13-corun-profiling-procedure.md`](../2026-06-13-corun-profiling-procedure.md) 為準。
> - 無 motion 診斷 SOP 以 [`2026-06-13-no-motion-diagnostics-sop.md`](../2026-06-13-no-motion-diagnostics-sop.md) 為準。
> **這份不是什麼**：不是執行授權、不是「nav 已修好」、不是「可以做自主導航」的依據。所有結論皆為 **PLANNED / 待驗證**。

---

## 0. 誠實前提（先講清楚，避免 overclaim）

1. **本檔零 runtime 變更**：不改 launch / config / node，不重啟任何 demo，不對 Go2 發任何 motion。所有「修法」都是**計畫**，標記 `PLANNED`。
2. **nav motion 仍 `NOT_DEMO_READY`**：`goto_relative` 與 `DriveOnHeading` 都不是 6/18 live 主線（[s1-fallback §0](../2026-06-13-s1-fallback-decision.md)）。本檔的「單 driver 統一」**不等於**「nav 可動」——統一 driver 是 connection/TF 層的整理，不解 R1/R2/R3/R5。
3. **單 driver 統一是 launch/process 管理問題，不是兩套程式碼**：兩個 lane 用的是**同一個** `go2_driver_node`，差別純粹是 launch 參數。所以「dual driver」是流程產物，合併不需改 driver 程式碼本身（見 §1）。
4. **nav 宣稱全綁禁講清單**：本檔任一句都不得被當成 F1-F10（自主導航 / 動態繞障 / D435 已融合 / auto-resume / 走到 Roy 身邊 / 未 n=3 的「可靠」/ 1.0m+ 連續 / 三鏡頭參與 / 即時恢復）的依據。

---

## 1. 問題陳述（Problem Statement）

今天 `pawai demo start`（brain）與 nav stack **各自啟動自己的一份 Go2 driver**：

- **Brain demo**：`scripts/start_full_demo_tmux.sh:138-140` 跑 `ros2 launch go2_robot_sdk robot.launch.py enable_lidar:=false enable_tts:=false nav2:=false slam:=false ...` → 起一份 `go2_driver_node`。
- **Nav demo（capability 主線）**：`scripts/start_nav_capability_demo_tmux.sh:89-90` 跑 `ros2 launch go2_robot_sdk robot.launch.py nav2:=true slam:=false ... teleop:=false joystick:=false` → 起**另一份** `go2_driver_node`。
- **Nav demo（AMCL-only 舊路線）**：`scripts/start_nav2_amcl_demo_tmux.sh:60-61` 用 `ros2 run go2_robot_sdk go2_driver_node`（裸起，繞過 launch wrapper）→ 又是**另一份**。

**為什麼這不是一行就能修的事**：

| 衝突軸 | 具體現象 | 依據 |
|---|---|---|
| **WebRTC 單會話** | Go2 對單一 `ROBOT_IP` 只接受**一條** WebRTC peer connection（`Go2Connection.__init__` 一個 `RTCPeerConnection`、一條 DataChannel `id=0`，`infrastructure/webrtc/go2_connection.py:72,107`；`WebRtcAdapter` keyed `connections["0"]`）。兩份 driver = 兩個 RTCPeerConnection 搶同一台 Go2 → ICE FROZEN→FAILED / 指令時靈時不靈。 | thesis §5（`docs/deliverables/thesis/5-系統限制與可行性分析.md:262-264`）、CLAUDE.md「多 driver instance 殘留」 |
| **ROS2 topic 撞名** | 兩份都 sub `/cmd_vel` + `/webrtc_req`、都 pub `/odom`，命令來源不明、重複下達。 | `go2_driver_node.py:318-324` |
| **TF dual authority** | 兩份都發 `odom→base_link`（`ros2_publisher.py:66-91`），雙 publisher 一條 TF edge。 | 6/13 incident T0 同類衝突 |
| **/cmd_vel 語意不同** | nav_capability 走 twist_mux（Nav2→`/cmd_vel_nav`→mux→`/cmd_vel`），nav2_amcl 舊路線**無 mux**、controller 直發 `/cmd_vel`——兩種 `/cmd_vel` 語意不相容，不能同 driver 共存。 | `twist_mux.yaml`、`start_nav2_amcl_demo_tmux.sh`（無 mux window） |
| **清理難** | `killall python3` 只殺 launch parent，C++ 子 process 殘留，需逐一 `pkill -9 go2_driver; robot_state; pointcloud; joy_node; teleop; twist_mux`。 | CLAUDE.md、`docs/pawai_cli/README.md:337`（orphan-driver preflight） |

**結論**：要讓 brain（互動 + 偶發 sport gesture）與 nav（移動）在**同一台 Go2** 上共存，唯一乾淨解是**單一 driver、兩 lane 共用**——但這牽動 connection、TF authority、mux 語意三條線，屬架構整理，非一行 launch 參數。

---

## 2. 現行架構地圖（含 file:line）

### 2.1 Driver 層

- **唯一實作**：`go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py`。lane 行為**全由 launch 參數驅動**（nav2 / slam / teleop / mux / enable_tts / decode_lidar / minimal_state_topics），**不是兩份程式碼**。
- 在 launch 內定義：`robot.launch.py:358-377`（`create_core_nodes`）。
- 訂閱 `/cmd_vel`（`go2_driver_node.py:318-319` → `_on_cmd_vel:402` → `RobotControlService.handle_cmd_vel:407`）。
- 訂閱 `/webrtc_req`（`go2_driver_node.py:321-324` → `_on_webrtc_req` → `handle_webrtc_request`）。
- 發 `/odom`（`go2_driver_node.py:264-265`）+ `odom→base_link` TF（`ros2_publisher.py:66-91`，env `GO2_PUBLISH_ODOM_TF` 預設 `"1"`，`ros2_publisher.py:29`）。
- WebRTC 單會話：`go2_connection.py:72,107`、`webrtc_adapter.py:38-59`。
- ⚠ **`enable_lidar` arg leak**：brain script 傳 `enable_lidar:=false` 給 `robot.launch.py`，但 launch 檔**沒宣告** `enable_lidar`（29 個 `DeclareLaunchArgument` 無此名）→ 在 launch 層被靜默丟棄，driver 自己的 `enable_lidar` param（`go2_driver_node.py:132`）維持預設 `True`。

### 2.2 兩條 motion transport（關鍵：reactive_stop 只蓋其中一條）

- **(A) `/cmd_vel` / twist_mux 路（nav/teleop 走這條）**：
  - mux 優先序（`go2_robot_sdk/config/twist_mux.yaml:18-42`）：emergency `/cmd_vel_emergency`=255 > obstacle `/cmd_vel_obstacle`=200 > teleop `/cmd_vel_joy`=100 > nav2 `/cmd_vel_nav`=10；每輸入 timeout 0.5s；lock `/lock/emergency` priority 255。
  - mux 在 `robot.launch.py:463-475` 起（`mux` arg 預設 true），remap `/cmd_vel_out`→`/cmd_vel`。
  - Nav2 最終輸出 remap 到 `/cmd_vel_nav`（`nav_capability/launch/navigation_remap.launch.py:30-35,214-215`）。
  - reactive_stop 發 `/cmd_vel_obstacle`（`reactive_stop_node.py:93,140`）。
- **(B) `/webrtc_req` sport 路（brain motion 走這條，完全不經 twist_mux）**：
  - brain 動作 dispatch 走 `/webrtc_req` WebRtcReq api_id（`interaction_executive_node.py:87,326-343`，如 1016 Hello / 1009 Sit）。
  - 唯一 cmd_vel-based brain 動作 `ACTION_FORWARD`（`state_machine.py:58`，`come_here:265` 用）是**dead code**：executive 沒有 cmd_vel publisher、沒有 cmd_vel dispatch 分支。**brain 從不發 cmd_vel**。
  - TTS Megaphone（4001/4003/4002）也走 `/webrtc_req`（`tts_node.py:1173,1502-1540`）——與 brain sport 共用同一條 DataChannel。
- **driver MIN_X / StopMove 路由**（`robot_control_service.py:87-153`）：`MAX_LINEAR_X=0.5`、`DEADBAND=0.01`、`STOP_REFRESH_INTERVAL_S=1.0`；post-deadband 全零 → `send_stop_move_command`（StopMove 1003）含 1Hz dedupe；非零 → `send_movement_command`（Move 1008）。
- **brain demo 無 motion brake**：`start_full_demo_tmux.sh:138-140` `enable_lidar:=false nav2:=false` → 無 sllidar、無 reactive_stop；只有 `depth_safety_node`（`start_full_demo_tmux.sh:269-270`）且**僅 advisory**（`depth_safety_node.py:16-18`：不發 cmd_vel、不 pause Nav2）。

### 2.3 TF / odom 鏈（單 nav stack 現況）

```
map ─(AMCL, dynamic)→ odom ─(go2_driver, dynamic)→ base_link ─(static_tf, yaw=π)→ laser
```

四個 TF authority，定位邊有**兩處雙 publisher 衝突（T0）**：

| # | edge | authority | file:line |
|---|---|---|---|
| 1 | odom→base_link（dynamic） | go2_driver | `ros2_publisher.py:66-91`，env gate `:29` |
| 2 | **map→odom + odom→base_link（static identity）** ⚠ | robot_state_publisher（URDF `go2.urdf`） | `go2.urdf` `odom_joint:49`、`map_joint:71`（皆 `type="fixed"` xyz/rpy=0）→ 發 `/tf_static` |
| 3 | map→odom（dynamic） | AMCL | `nav2_params.yaml:38 tf_broadcast:true` |
| 4 | base_link→laser（static, yaw=π） | launch script `static_transform_publisher` | `start_nav_capability_demo_tmux.sh:69-72` |

- **T0 = dual authority**：`go2.urdf` 把 `map→odom`、`odom→base_link` 當 fixed identity joint 發 `/tf_static`，與 AMCL（map→odom）、driver（odom→base_link）的 dynamic TF 撞同一條 edge。tf2 static「跨全時間有效、首次後不可變」→ 可能永久 shadow dynamic 定位、把 edge 鎖在 (0,0,0)。**CO-PRIMARY 嫌疑、必須 `ros2 topic echo /tf_static` 先排除**。
- **base_link→laser yaw=π double-encoded**：static TF yaw=π + reactive_stop `front_offset_rad=π`（`start_nav_capability_demo_tmux.sh:40,43`）兩處獨立 yaw=π，須一致；改一不改另一 = 5/1 撞箱 footgun（commit e3270da）。
- cartographer（`cartographer_lidar.lua:22-26` `provide_odom_frame=true`）只在建圖跑、與 AMCL 互斥；AMCL demo 時 cartographer off，非第四 concurrent authority。

---

## 3. 今晚已可達成（PROVEN，bench 觀測）

> 來源：本檔合成時的 bench 觀測 + [`corun-profiling-procedure.md`](../2026-06-13-corun-profiling-procedure.md) Config B 路線。**以下是觀測，不是 motion 結論。**

- **brain demo + raw LiDAR 共跑（單一 Go2 driver）**：在 brain demo 既有的**單一** `go2_driver_node` 之上，加一個 raw LiDAR（sllidar `/scan_rplidar`）monitor window，**不啟 nav2 / AMCL / mux 改路**。
  - **RAM 增量 ≈ +0.1 GB**（落在 corun-profiling §9.2「OK / headroom ≥ 1.9 GB」綠帶內，遠低於 6.5GB OOM-risk）。
  - **scan ≈ 12 Hz**（RPLIDAR A2M12 健康頻率，非 Go2 內建 LiDAR 的 <2Hz）。
  - **零 motion**：只是把 LiDAR 點雲 / scan 當「邊緣端即時感知」證據顯示，Go2 不動。
- **6/18 可現場展示 live LiDAR 證據**：這正是 [nav-618 claim §5 fallback②](../2026-06-13-nav-618-claim-wording.md) +「nav 在 Studio/Foxglove 顯示即時感知環境（非寫死）」可講句的硬依據——**不需 nav motion、不碰 F-清單**。
- ⚠ **這不是「nav 共存已驗」**：本項只證「單 driver + raw LiDAR monitor」記憶體安全且 scan 健康；**nav2/AMCL/reactive_stop 疊上去的完整共存**仍須照 corun-profiling Config A 量（見 §5 LT-0），8GB 是否撐得住 = 待測。

---

## 4. 目標架構：Single Go2 Driver（PLANNED）

> 一句話：**一份 driver、brain + nav 共用；nav stack 不再自起 driver；`/cmd_vel` 經 twist_mux 統一；reactive_stop 當共享安全層（priority brake）；TF/odom 單一 authority（先解 T0 URDF fixed-joint 衝突）。**

```
                         ┌──────────── ONE go2_driver_node ────────────┐
   brain sport/TTS ──/webrtc_req──────────────────────────────────────▶│ WebRTC DataChannel (single session)
                                                                        │
   nav2 ──/cmd_vel_nav(10)─┐                                            │
   teleop ─/cmd_vel_joy(100)┤                                           │
   reactive_stop ─/cmd_vel_obstacle(200)┤──twist_mux──/cmd_vel─────────▶│ handle_cmd_vel (MIN_X / StopMove)
   emergency ─/cmd_vel_emergency(255)───┘                               │
                                                                        │ odom→base_link (GO2_PUBLISH_ODOM_TF=1)
   AMCL ── map→odom ───────────────────────────────────────────────────┘
```

四項目標屬性（皆 PLANNED）：

1. **單 driver**：全 stack 只有一個 `go2_driver_node`（`ros2 node list` 期望剛好一個）。brain 偶發 sport（Hello/Sit/wiggle）走 `/webrtc_req`、nav 走 `/cmd_vel`→mux，**兩者在 driver 收斂、各走各 transport，不在 mux 互搶**。
2. **`/cmd_vel` 統一經 twist_mux**：消除「有 mux / 無 mux」兩種 `/cmd_vel` 語意。nav2_amcl 舊路線若保留，須改 remap 到 `/cmd_vel_nav` 走 mux（對齊 `navigation_remap.launch.py:214-215`）。
3. **reactive_stop = 共享安全層**：`/cmd_vel_obstacle` priority 200 可覆寫 nav(10)；emergency 走 `/cmd_vel_emergency`(255) + `/lock/emergency`。⚠ **只蓋 transport (A)**——brain `/webrtc_req` Move 不經 mux，故 brain translation 不在此 brake 範圍（見 §6 RISK）。
4. **TF/odom 單一 authority**：保持 `GO2_PUBLISH_ODOM_TF=1`（driver 擁 odom→base_link）、AMCL 擁 map→odom；**先移除 `go2.urdf` 的 `map_joint`/`odom_joint`（T0）**，確保每 edge 剛好一個 publisher。

---

## 5. 分階段計畫

### SHORT-TERM（6/18 前）— 不硬整合完整 nav

> **原則**：6/18 **不**把完整 nav stack（nav2+AMCL+reactive_stop）硬疊進 brain demo。nav 段照 [s1-fallback §1](../2026-06-13-s1-fallback-decision.md) 三層走（預設 fallback② 遙控+Foxglove 證據 / fallback③ 影片保底）。Act1 motion 若要 live safe-stop，用**獨立分段（separate-segment）的 standalone reactive_stop**，與 brain demo **分時、不同鏡頭**（8GB 互斥，[nav-618 §5 鐵則](../2026-06-13-nav-618-claim-wording.md)）。

| ID | 做什麼 | 變更檔 | 6/18-able | 風險 |
|---|---|---|---|---|
| **ST-1** | **brain demo + raw LiDAR monitor**（§3 已驗）：單 driver 不變，加 sllidar `/scan_rplidar` + Foxglove 顯示，當 live 感知證據 | 文件 + 既有 sllidar 啟動指令（**不改 launch/config**；本檔不執行） | ✅ 6/18-able | 低；只讀 LiDAR，零 motion |
| **ST-2** | **靜態 connection/TF 驗證（no-motion）**：單一 `robot.launch.py` 起後跑 `ros2 node list`（期望剛好一個 `go2_driver_node`）、`ros2 topic info /webrtc_req -v` + `/cmd_vel -v`（各一 subscriber=driver）、`tf2_echo odom base_link`（一 publisher）、`echo /tts` smoke——**全程不命令 Go2 移動** | 無（純診斷，照 [no-motion SOP](../2026-06-13-no-motion-diagnostics-sop.md)） | ✅ 6/18-able | 低 |
| **ST-3** | **T0 診斷（no-motion）**：`ros2 topic echo /tf_static` + `tf2_tools view_frames` + `tf2_monitor`，確認 `map→odom`/`odom→base_link` 是否 >1 broadcaster（runbook §9-D1） | 無 | ✅ 6/18-able | 低；只診斷不修 |
| **ST-4** | **Act1 safe-stop = 獨立分段 standalone reactive_stop**：若要 live 演 safe-stop，用 `start_reactive_stop_tmux.sh`（standalone，與 nav2-amcl 互斥），**分時、獨立鏡頭**，台詞綁 [S2](../2026-06-13-nav-618-claim-wording.md)+§3 標準說法（safe-stop≠繞障）。**預設仍走 fallback②/③**，本項僅在 Roy 授權 + e-stop 就位下作 live 選項 | 無（用既有 script；本檔不執行、不授權） | ⚠ live 部分 = Roy 授權 + e-stop（motion）；**架構面 6/18-able** | 中；任何 live = motion，須 e-stop + 操作員監督 |
| **ST-5** | **文件/流程禁令**：把「禁止同時起兩份 nav/brain driver」寫進 `pawai demo` lock collision（lane 機制已存在）；記錄「brain demo 目前無 LiDAR brake、depth_safety 僅 advisory、demo 限 in-place sport gesture」 | 文件（CLAUDE.md / CLI docs；本檔不執行，列為後續 doc task） | ✅ 6/18-able | 低 |

**SHORT-TERM 不做（明確排除，post-6/18）**：合併兩 launcher 的 driver/mux 架構、改 nav2_amcl 走 mux、always-on reactive_stop 疊進 full demo、任何 goto/DriveOnHeading/cmd_vel live motion 驗證——皆改 `/cmd_vel` 真實路由或需真機 motion，與 nav `NOT_DEMO_READY` 一致。

### LONG-TERM（6/18 後）— Single Go2 Driver refactor

| ID | 做什麼 | 變更檔 | tag | 風險 |
|---|---|---|---|---|
| **LT-0** | **完整共存 profiling**：照 [corun-profiling Config A](../2026-06-13-corun-profiling-procedure.md) 量「brain 全感知 + nav2+AMCL+reactive_stop+RPLIDAR」8GB 是否撐住（RAM/溫度/Hz）；FAIL → 維持分時 Config B | 無（量測） | post-6/18 | 中；可能直接判定「不可常駐共存」→ 分時 |
| **LT-1（P0）** | **T0 修法**：從 single-mode URDF 移除 `map`/`odom` link + `map_joint`/`odom_joint`（保留 `base_footprint_joint`），每 edge 一 authority。修後 `echo /tf_static` 不得含 map→odom/odom→base_link。**單檔、一鍵 revert** | `go2_robot_sdk/urdf/go2.urdf`（`:49,:71`） | post-6/18（修是純編輯可 6/18-able；**驗證走直需 motion → post-6/18**） | 中；須 audit 是否有 consumer 依賴 URDF 的 map/odom frame |
| **LT-1-alt** | **T0 修法替代**：`robot.launch.py:67` single-mode 預設 URDF 由 `go2.urdf` 換 `go2_on_steroids.urdf`（已驗無 map/odom link、起於 base_link、附 calibrated `lidar_joint`）；須與 yaw=π laser 慣例 reconcile | `robot.launch.py:67` | post-6/18 | 中；`go2_on_steroids.urdf` 的 base_link→lidar(yaw=0) 與 script base_link→laser(yaw=π) 會撞，須擇一 laser mount 來源 |
| **LT-2** | **單 driver superset launch**：一條 `robot.launch.py nav2:=true mux:=true teleop:=false joystick:=false`，brain 感知/speech + nav 共用此 driver；nav lane **不再自起 driver**（用 lock 強制單一 owner） | `start_full_demo_tmux.sh` / `start_nav_capability_demo_tmux.sh` 收斂 | post-6/18 | 高；改 `/cmd_vel` 路由語意 + 8GB 預算（需 LT-0 通過） |
| **LT-3** | **nav2_amcl 舊路線收斂**：改走 `robot.launch.py`(nav2:=true)+同一 twist_mux，controller remap 到 `/cmd_vel_nav`，消除無-mux 直發 `/cmd_vel` 語意 | `start_nav2_amcl_demo_tmux.sh` | post-6/18 | 高；失去「driver 直發 /cmd_vel 最短路」，短距改評估 DriveOnHeading |
| **LT-4** | **enable_lidar arg leak 修法**：把 `enable_lidar` plumb 進 `robot.launch.py`（`:363-375` driver params block）讓 brain 的 `enable_lidar:=false` 真的生效，避免 LiDAR decode 意外吃 8GB | `robot.launch.py`（`DeclareLaunchArgument` + driver params） | post-6/18（純編輯可 6/18-able，**但屬 runtime 行為變更 → 排 post-6/18 一起驗**） | 低-中；改變 topic 集合 |
| **LT-5** | **共享 brake 涵蓋 brain transport（決策層，軟體）**：brain SafetyLayer 訂 `/state/reactive_stop/status`，zone∈{danger,emergency} 時拒派任何 MOTION/NAV step（鏡像既有 nav world-gate `interaction_executive_node.py:357`）。default-off / 無 danger 事件時 byte-identical | `interaction_executive` brain SafetyLayer | post-6/18（軟體可 WSL fake-event 測 → **架構 6/18-able**，但併入 brake 整體 post-6/18 驗） | 中；不蓋 actuation、只蓋 decision |
| **LT-6** | **共享 brake 涵蓋 actuation（driver interlock，需真機）**：driver `RobotControlService` 加 obstacle/emergency interlock，同時擋非零 `handle_cmd_vel` Move **與** forward webrtc Move(1008)；default-off env/param gated | `robot_control_service.py:137-151` | post-6/18 | 高；改 actuation，須對齊 MIN_X=0.5 lunge + reactive 閾值真機校 |

---

## 6. Per-step 風險與 6/18 綁定（彙整）

> 每項風險都連回既有事故與禁講清單；本檔不解 R1/R2/R3/R5，只解 connection/topic/TF 層。

1. **WebRTC 單會話殘留**：任何 stale `go2_driver_node` 殘留（`killall` 只殺 parent）→ 統一 launch 的新 RTCPeerConnection 與 orphan 互搶 → FROZEN→FAILED。**統一啟動前必逐一 `pkill -9 go2_driver; robot_state; pointcloud; joy_node; teleop; twist_mux`**（CLAUDE.md）。
2. **T0 dual TF authority**：code-confirmed（`go2.urdf:49,71`）但**runtime 是否真 shadow 待 `echo /tf_static` 證實**——可能是主因、也可能被 RSP transient_local 覆寫成 non-issue。修 T0 是**必要非充分**：R1/R2/R3/R5 仍在，**不得把 T0 修法 over-claim 成「nav 修好」**。
3. **mux priority shadowing**：統一 stack 必須 `teleop:=false joystick:=false`（hot `/cmd_vel_joy`(100) > nav(10) = 重現 5/11 撞牆）；reactive_stop `safety_only=true` 用於 mux 模式。**brain sport 必走 `/webrtc_req`、不走 `/cmd_vel`**，否則 brain motion 與 nav 在 mux 互爭。
4. **brain `/webrtc_req` Move 繞過 mux**：任何 mux-based / `/cmd_vel`-based brake 對 brain-發起的 walking **盲**；只有 driver-level interlock（LT-6）能補。今天被 mask 僅因 `ACTION_FORWARD` 是 dead code、gesture 全 in-place。**6/18 demo 限 in-place sport gesture（含 S4 wiggle）**，在 brake 落地前**不得**接 brain translation。
5. **reactive_stop 參數只在 `__init__` 讀一次**（`front_arc_deg`/`danger_distance_m`/`front_offset_rad`，`reactive_stop_node.py:120-121；CLAUDE.md`）：切 lane 必 kill 重啟帶參數，`ros2 param set` 無效。
6. **8GB 預算**：brain 全感知（face+vision+object+ASR+TTS+LLM）疊 nav2+AMCL+reactive_stop+RPLIDAR 可能 OOM；brain demo 現以 `nav2:=false slam:=false` 釋資源正是此故。**常駐共存 = LT-0 量過才談；否則維持分時**。
7. **enable_lidar leak**：假設 `enable_lidar:=false` 已關 LiDAR decode 是錯的（被靜默丟棄，driver 預設 True）；統一前須 LT-4 修。
8. **Megaphone 重啟脆弱**：mid-session 重啟 `tts_node` 致 Go2 Megaphone silent fail、須連 driver 重啟（MEMORY）。單 driver 下，重啟 tts 修 audio 會連 nav 一起斷——brain-audio 復原與 nav 可用性耦合。
9. **MIN_X=0.5 resume lunge**：任何 auto-resume 以 ~0.5 m/s 衝（tight space 0.21m 貼牆，6/9 HITL）；resume **必 operator-gated**，綁 [F4/F5 禁講](../2026-06-13-nav-618-claim-wording.md)。
10. **orphaned active goal**：`nav_action_server`(single-goal) 在 client crash / SSH 斷後留 active goal → 後續 goto 全拒；合併 driver 重啟流程須連帶清。

### nav 宣稱綁定（禁講清單對齊）

本檔**不新增**任何可講宣稱。與單 driver 統一相關的對外措辭只能用 [nav-618 §2](../2026-06-13-nav-618-claim-wording.md) 既有可講句（S1-S8 帶限制詞），且**絕不**碰：
- **F1** 自由/自主巡邏、**F2** 動態繞障/自動繞開、**F3** D435 已融合進 costmap、**F4/F5** auto-resume/「不會再走」、**F6** 「聽懂過來就走到 Roy 身邊」、**F7** 未 n=3 的「可靠導航」、**F8** 1.0m+ 連續乾淨導航、**F9** 三鏡頭參與導航、**F10** 即時恢復（orphan 是 ~10s 自癒）。
- safe-stop 一律用 [§3 標準說法](../2026-06-13-nav-618-claim-wording.md)：「停下等待、不轉向繞行（`angular.z=0`）」。

---

## 7. 誠實聲明（PLANNED / research 標記）

- 本檔**全為計畫 / research**，零 runtime 變更、零 motion、未碰執行中 demo。
- §3「已可達成」僅指 **brain demo + raw LiDAR monitor（單 driver、+0.1GB、scan~12Hz）的 bench 觀測**；**不是** nav2/AMCL/reactive_stop 完整共存已驗，**不是** nav motion 可動。
- §4 目標架構、§5 LONG-TERM 全部 `PLANNED`，**待 LT-0 profiling + Roy 授權 + e-stop + 真機 motion HITL** 才逐項驗證。
- nav motion 維持 `NOT_DEMO_READY`；S1 nav 幕預設 fallback②（遙控+Foxglove 證據）、影片③ 保底。
- 任何把本檔當「nav 已修 / 可自主導航 / 可常駐共存」的引用 = overclaim，駁回。

---

## 8. OPEN 書記（待閉合）

| 書記 | 內容 | 閉合條件 |
|---|---|---|
| O-1（T0 runtime） | `go2.urdf` static identity 是否**真**shadow dynamic TF | ST-3 `echo /tf_static` 實測 |
| O-2（完整共存） | brain 全感知 + 完整 nav 8GB 是否撐住 | LT-0 corun-profiling Config A CSV |
| O-3（laser mount 單源） | 若走 LT-1-alt，`go2_on_steroids.urdf` lidar(yaw=0) vs script laser(yaw=π) 擇一 | reconcile + person-stands-at-snout 驗（no-motion） |
| O-4（單 driver motion 驗） | T0 修後 Go2 是否真走直（M1 n=3） | Roy + e-stop，post-6/18 |
| O-5（lock 強制單 driver） | 把 dual-driver 禁令寫進 `pawai demo` lock collision | doc task（ST-5） |
