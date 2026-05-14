# 導航避障（Navigation / Avoidance）文件索引

這組文件整理 PawAI 目前最危險、也最需要現場紀律的模組：RPLIDAR 建圖定位、Nav2 規劃、reactive_stop 反應式停障、twist_mux 仲裁、D435 depth gate、nav_capability action wrapper，以及 Brain/Executive 的安全 gate。

## 快速結論

目前已做到：
- RPLIDAR A2M12 產生 `/scan_rplidar`，作為 Cartographer 建圖、AMCL 定位、Nav2 costmap、reactive_stop 的主感測器。
- 已有 Cartographer 離線建圖流程，地圖主線是 `home_living_room_v8.yaml`。
- 已有 AMCL + Nav2 + DWB runtime，Nav2 final velocity 透過 wrapper remap 到 `/cmd_vel_nav`。
- 已有 `twist_mux` 仲裁：emergency 255 > obstacle 200 > teleop 100 > nav2 10。
- 已有 `reactive_stop_node` 4-mode state machine，5/11 撞牆事件後把 threshold 改成 `danger=1.1m`、`slow=1.7m`。
- 已有 D435 `depth_safety_node`，輸出 `/capability/depth_clear`，但它只是 fail-closed gate，不會直接停車。
- 已有 `nav_capability`：`/nav/goto_relative`、`/nav/goto_named`、`/nav/run_route`、`/nav/pause|resume|cancel`。
- Executive 已訂 `/capability/nav_ready`、`/capability/depth_clear`、`/state/nav/paused`，SafetyLayer 會擋 NAV/MOTION。

目前最重要的限制：
- `progressive` reactive_stop 只在 danger/emergency 發 0，slow/clear 會沉默。若 `/cmd_vel_joy` 還有 hot publisher，mux timeout 後 teleop 100 會贏 nav 10，這就是 5/11 撞牆主因。
- `nav_ready` 目前是 basic gate，只看 AMCL pose age + covariance，還沒檢查 Nav2 lifecycle、TF、costmap freshness。
- `depth_clear=false` 只阻止新 action，被啟動中的 nav goal 不會因 D435 alone 自動停。
- Interaction Executive 的 NAV contract 已存在，但 `interaction_executive_node` 的 NAV executor 仍是 `nav_unimplemented_phase_a`；實機 nav 主要靠 `nav_capability` action/Studio/手動命令。
- `start_nav_capability_demo_tmux_detour.sh` 目前不要直接用，已知有 `safety_only` 舊模式、低 danger threshold、yaml drift、D435 TF 未精校等風險。

## 文件地圖

| 文件 | 用途 |
|------|------|
| [nav/nav-runtime-flow.md](nav/nav-runtime-flow.md) | 系統架構圖、topic/TF/cmd_vel 全資料流 |
| [nav/nav-reactive-stop-and-mux.md](nav/nav-reactive-stop-and-mux.md) | reactive_stop 4-mode、5/11 撞牆 root cause、mux 風險 |
| [nav/nav-capability-brain-integration.md](nav/nav-capability-brain-integration.md) | nav_capability actions、Brain/Executive safety gate、未完成接線 |
| [nav/nav-field-runbook.md](nav/nav-field-runbook.md) | 明天到學校的啟動、preflight、healthcheck、F7 debug 順序 |
| [nav/nav-known-issues-roadmap.md](nav/nav-known-issues-roadmap.md) | 已知問題、文件不一致、demo 後 roadmap |

## 權威來源

| 主題 | 檔案 |
|------|------|
| 5/11 深度研究 | `docs/navigation/research/2026-05-11-nav-avoidance-deep-research.md` |
| 5/11 修法 roadmap | `docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md` |
| Navigation 工作規則 | `docs/navigation/CLAUDE.md` |
| Navigation 入口 | `docs/navigation/README.md` |
| reactive_stop node | `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py` |
| LiDAR 幾何 helper | `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py` |
| twist mux priority | `go2_robot_sdk/config/twist_mux.yaml` |
| Nav2 主設定 | `go2_robot_sdk/config/nav2_params.yaml` |
| Nav2 wrapper/remap | `nav_capability/launch/navigation_remap.launch.py` |
| nav actions | `nav_capability/nav_capability/nav_action_server_node.py` |
| route/pause/resume | `nav_capability/nav_capability/route_runner_node.py` |
| nav_ready gate | `nav_capability/nav_capability/capability_publisher_node.py` |
| D435 depth gate | `go2_robot_sdk/go2_robot_sdk/depth_safety_node.py` |
