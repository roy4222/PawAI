---
name: nav-avoidance-lane
description: >
  PawAI 導航避障 lane 的標準操作。管 RPLIDAR、D435、go2_driver、Nav2、AMCL、
  cartographer、reactive_stop、nav_capability、twist_mux 等所有 nav stack。
  觸發詞："nav lane"、"啟 nav"、"開 nav"、"導航"、"避障"、"建圖"、
  "/nav-lane"、"AMCL"、"reactive_stop"、"nav_capability"、"場測"。
  在使用者要做 LiDAR 校正、建圖、AMCL 定位、Nav2 場測、reactive_stop 驗證、
  B5 / B6 / B7 burndown 階段時主動建議。也用於 Brain × Nav 切換時的 lane handoff。
  不要在 Brain / LLM / Studio / TTS / persona 場景觸發（那是 brain-studio-lane）。
---

# nav-avoidance-lane

PawAI 導航避障一切 runtime 的固定操作法。把 LiDAR / TF / driver / mux /
reactive_stop / nav2 / amcl 的 4 種啟動組合（建圖 / AMCL demo / capability /
reactive fallback）固化成 mode，搭配 brain-studio-lane 的 cleanup → handoff。

## 為什麼存在

Nav stack 比 Brain 危險 — Go2 是 12kg 機器狗，跑錯指令會撞東西、撞人、撞牆
（B5 已撞過 1.5m 處障礙物）。每次手動拼裝容易漏 `safety_only` 設定、漏
`GO2_PUBLISH_ODOM_TF` env、漏 map 檔。skill 把這些固化成 4 種 mode 並
preflight 擋住已知致命錯誤。

## CLI 介面

```bash
bash .claude/skills/nav-avoidance-lane/scripts/start.sh <mode>
bash .claude/skills/nav-avoidance-lane/scripts/preflight.sh <mode>
bash .claude/skills/nav-avoidance-lane/scripts/healthcheck.sh
bash .claude/skills/nav-avoidance-lane/scripts/cleanup.sh [--handoff brain|none]
```

## Mode 對照表

| mode | 啟什麼 | 用什麼底層 script | 用途 |
|---|---|---|---|
| `mapping` | tf + sllidar + cartographer + foxglove | `scripts/start_lidar_slam_tmux.sh` | 建新地圖。**無 go2_driver**（cartographer 自己 own odom→base_link TF） |
| `amcl` | tf + sllidar + go2_driver + nav2_bringup（map_server + amcl + planner）+ foxglove | `scripts/start_nav2_amcl_demo_tmux.sh` | 已建好圖跑 goto。需手動 `/initialpose` |
| `capability` | + d435 + reactive_stop(`mode=progressive`) + nav_capability 6 nodes | `scripts/start_nav_capability_demo_tmux.sh` | 完整能力層 demo（goto_relative / run_route / depth_safety）。reactive 走 mux priority 200，與 nav planner 漸進協調 |
| `fallback` | tf + sllidar + go2_driver + reactive_stop(standalone, mode="" + 3 段速直驅) | `scripts/start_reactive_stop_tmux.sh` | nav2 失敗時的安全 fallback。**reactive_stop 直發 /cmd_vel 不過 mux**（與 capability 互斥） |

## 預設執行流程

使用者說「啟 nav fallback」「開 nav amcl」「nav 建圖」時：

1. **解析意圖** → 判斷 mode
2. **跑 preflight** — `bash scripts/preflight.sh <mode>`
3. **如果 P0 fail** → 報出原因，問使用者怎麼處理
4. **如果 preflight pass** → `bash scripts/start.sh <mode>`
5. **跑 healthcheck** — 等 30-60s 後 verify topic / node 狀態
6. **告知下一步**（例如 amcl 要在 Foxglove 設 `/initialpose`）

## Preflight 檢查項（P0 / P1 分級）

| 檢查項 | 級別 | 失敗動作 |
|---|---|---|
| Jetson SSH 通 | **P0** | 擋 |
| `/dev/rplidar` 存在於 Jetson | **P0** | 擋（USB LiDAR 沒接 / udev rule 沒 load） |
| Go2 `ROBOT_IP` ping 通（非 mapping mode）| **P0** | 擋（mapping mode 不需 driver 所以不檢） |
| `MAP_YAML` 檔案存在（amcl/capability mode）| **P0** | 擋 |
| `reactive_stop` mode 設置正確（capability=`progressive` / fallback=standalone empty mode） | **P0** | 擋（B5 撞牆教訓 — 早期 `safety_only=true` alias 在 hold_brake，clear zone 沉默讓 mux timeout 降級） |
| `~/elder_and_dog/runtime/nav_capability/{named_poses,routes}/` 存在（capability mode）| **P0** | 擋 |
| 沒有 `pawai_brain` tmux session 在跑 | **P1** | warn — 建議先 brain cleanup --handoff nav |
| D435 USB 偵測到（capability mode）| **P1** | warn — depth_safety_node 會 fail 但 nav 仍可跑 |
| `~/rplidar_ws/install/setup.zsh` 存在 | **P0** | 擋（sllidar_ros2 沒裝在 overlay） |

## Healthcheck 驗證項

| 項目 | 怎麼檢 | 應該看到 |
|---|---|---|
| `/scan_rplidar` 有 publisher | `ros2 topic hz /scan_rplidar` ≥ 10 Hz | ✅ |
| `/tf` 含 base_link→laser | `ros2 run tf2_ros tf2_echo base_link laser` | translation x≈0.175 z≈0.18 yaw≈π |
| `/odom` 有 publisher（非 mapping） | `ros2 topic hz /odom` ≥ 5 Hz | ✅ |
| `/amcl_pose` published（amcl/capability） | `ros2 topic echo /amcl_pose --once` | ✅ |
| `/cmd_vel_obstacle` publisher（capability/fallback）| reactive_stop 在跑 | ✅ |
| `/capability/nav_ready` true（capability） | nav_capability 內 `capability_publisher_node` | true |
| `/cartographer_node` alive（mapping）| `ros2 node list` | ✅ |

## Handoff 邏輯

`--handoff` 旗標**目前不影響清的範圍**（兩 lane cleanup 都會清 go2_driver），
只影響 cleanup 完的下一步提示文字。

理由：brain lane 的 e2e/full mode 也會自啟 driver（沒 reuse 機制），若
cleanup 不清 driver，brain 啟動後會雙 driver。為避免衝突，兩 lane 都
unconditional 清 driver。

| 用法 | 行為 |
|---|---|
| `cleanup --handoff brain` | 清全部 nav process + driver + D435，提示「下一步建議跑 brain-studio-lane start」 |
| `cleanup --handoff none`（或不帶）| 清全部 nav process + driver + D435，提示「完整清理完成」 |

未來若實作「brain start 偵測既有 driver 跳過自啟」，再讓 handoff 真正影響
是否保留 driver。目前先以 unconditional 清 driver 換取安全。

## ⚠️ 已知致命組合（preflight 必擋）

1. **standalone reactive_stop（fallback mode 直發 /cmd_vel）+ nav2 同跑**：reactive 直接 shadow nav planner 的指令，Go2 行為混亂。fallback 與 capability/amcl 互斥。
2. **`mode=hold_brake`（或 `safety_only=true` legacy alias）+ nav2 同跑**：reactive 永遠 publish 0 到 `/cmd_vel_obstacle`，mux priority 200 永遠贏 → nav 指令永遠不會被執行 → Go2 完全不動。`hold_brake` 只用於 B5 safety 驗證 / demo emergency hold，**不是**正常 nav demo。
3. **`mode=progressive` + 有 teleop hot publisher**：mux 真實 priority 是 emergency 255 / obstacle 200 / **teleop 100 / nav 10**（nav 是最低）。reactive progressive 在 clear zone 沉默 → 0.5s mux timeout obstacle 200 過期 → 剩 teleop 100 與 nav 10 競爭 → **teleop 100 永遠贏 nav 10** → Go2 吃 teleop 持續發的舊速度（5/11 撞牆 root cause）。capability mode 安全前提是「**沒有 teleop hot publisher 在跑**」，這樣 obstacle 沉默後就只剩 nav 10，nav 接管。
4. **`danger_distance_m < 1.0` + Go2 0.5 m/s 速度**：LiDAR 在 base_link 前 17.5cm，機鼻在前 50-60cm，看到 0.6m 時機鼻只剩 0.2m，**必撞**（5/11 真實撞牆教訓）。capability mode 已固定 1.1m。
5. **`GO2_PUBLISH_ODOM_TF=0` + amcl mode**：driver 不發 odom→base_link TF → AMCL 拿不到 odom → 定位不收斂。建圖才需要這個 env。
6. **多個 driver instance**：`pkill python3` 只殺 launch parent，C++ 子 process 殘留 → 下次啟動會雙 publisher。preflight 會檢查殘留並擋住。

## 常見場景速查

**剛搬到新場地，要建圖**：
```
nav-avoidance-lane start mapping
→ 走完一圈，跑 build_map.sh 三步驟存圖
→ 圖落在 ~/maps/<name>.{pgm,yaml,pbstream}
```

**有圖了，測 goto 點對點**：
```
MAP_YAML=/home/jetson/maps/home_living_room_v8.yaml \
  nav-avoidance-lane start amcl
→ Foxglove 設 /initialpose
→ ros2 topic pub /goal_pose ... -r 2 --times 5
```

**Nav 不穩，先驗 reactive_stop 安全層**：
```
nav-avoidance-lane start fallback
→ 推紙箱靠近 → Go2 應停
→ 移開 → ⚠️ 要重新發 /cmd_vel_joy 才會走（沉默升級已修）
```

**完整能力層 demo（5/12 後場測用）**：
```
nav-avoidance-lane start capability
→ ros2 action send_goal /nav/goto_relative ...
→ ros2 action send_goal /nav/run_route ...
```

**切回 brain**：
```
nav-avoidance-lane cleanup --handoff brain
brain-studio-lane start e2e --studio
```

## reactive_stop 4-mode 速查

`reactive_stop_node` 是 4-mode state machine（runtime 可切 ROS param `mode`）：

| mode | 行為 | 用途 | cmd_vel_topic |
|---|---|---|---|
| `hold_brake` | 永遠 publish 0 | B5 safety / demo emergency hold | `/cmd_vel_obstacle`（mux 200）|
| `progressive` | danger=0、slow/clear 沉默 | capability mode 搭 nav | `/cmd_vel_obstacle`（mux 200）|
| `released` | 不 publish 但 LiDAR/zone 還在更新 | 操作員主動釋放給 nav | — |
| `disabled` | 完全 off | 全停 reactive 影響 | — |
| (空 `mode` + `safety_only=false`) | standalone 3 段速直驅 | fallback mode | `/cmd_vel`（無 mux）|

`safety_only=true` legacy alias = 自動 promote 成 `mode=hold_brake`。

完整 mode 設計與 5/11 B5 burndown：`go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py` 開頭 docstring + `docs/navigation/2026-05-11-architecture-deep-audit-and-fix-roadmap.md §6 B0`。

## 進一步閱讀

- `references/runtime-topology.md` — 4 種 mode 啟哪些 node、TF 樹、cmd_vel mux
- `references/sensor-stack.md` — LiDAR/TF/D435 校正、`/dev/rplidar` udev、安裝座標
- `references/troubleshooting.md` — 10+ 條已踩過的坑（含 5/11 B5 burndown findings）
