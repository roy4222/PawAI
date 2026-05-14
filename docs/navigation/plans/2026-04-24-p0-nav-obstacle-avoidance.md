# P0 Nav Obstacle Avoidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 P0 劇本式導航避障 — Go2 從 A 點自主走到 B 點，遇人/紙箱障礙停下播固定 TTS，障礙移開 3 秒後續行；同時支援鍵盤 hotkey + Studio 按鈕兩路 latched emergency stop。

**Architecture:** 嵌入現有 PawAI Brain 三層架構。Safety Layer 新增 emergency latched FSM + obstacle auto-recovery FSM，優先阻擋 Nav2 cmd_vel；Policy Layer 新增 `patrol_route` skill（deterministic，不經 LLM）呼叫 Nav2 NavigateToPose action；Expression Layer 新增 `safety_tts.py` 固定 6 句模板（永不經 LLM）。twist_mux priority 255/200/100/10 做路由仲裁。

**Tech Stack:** ROS2 Humble / Python 3.10 / pytest / Nav2 (DWB controller, no MPPI) / slam_toolbox online_async / twist_mux / Slamtec RPLIDAR A2M12 via sllidar_ros2 / Unitree Go2 Pro (WebRTC DataChannel)

**Spec:** [`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`](../specs/2026-04-24-p0-nav-obstacle-avoidance-design.md)

**Hard Deadlines:**
- 5/1: Emergency latch hotkey 必須通過（不過不上 Go2）
- 5/6: 家中排練 4/5 KPI（GO/YELLOW/NO-GO）
- 5/11-5/12: Freeze 期，bugfix only
- 5/13: 學校場地重建地圖 + 現場排練

---

## File Structure

**新增（12 個）**：

| 檔案 | 責任 |
|------|------|
| `interaction_executive/interaction_executive/safety_layer.py` | 純 Python FSM（EmergencyFSM + ObstacleFSM），無 ROS2 依賴，100% unit-testable |
| `interaction_executive/interaction_executive/skills/__init__.py` | 空 package init |
| `interaction_executive/interaction_executive/skills/patrol_route_handler.py` | Nav2 ActionClient wrapper，暴露 `start/pause/resume/cancel` |
| `interaction_executive/interaction_executive/safety_tts.py` | 6 句固定模板發佈器（safety + navigation status 合一模組）|
| `scripts/emergency_stop.py` | Jetson 鍵盤 hotkey（q=trigger, r=reset），call ROS2 service |
| `scripts/start_patrol_demo_tmux.sh` | 一鍵啟動全 stack（driver/scan/lidar_obstacle/nav2/executive/tts/hotkey/foxglove）|
| `scripts/build_map.sh` | SLAM 建圖輔助（啟動 slam_toolbox + 等使用者手動繞完 + 存檔）|
| `scripts/verify_twist_mux.sh` | Gate P0-D.5 驗證腳本（發 mock cmd_vel 到不同 priority，觀察 Go2 動作）|
| `pawai-studio/backend/routers/safety.py` | FastAPI 端點 `/safety/trigger` + `/safety/reset` 呼叫 ROS2 service |
| `pawai-studio/frontend/components/EmergencyButton.tsx` | Studio 紅色大按鈕 |
| `interaction_executive/test/test_safety_layer.py` | safety_layer.py unit tests |
| `interaction_executive/test/test_patrol_route_handler.py` | patrol_route_handler.py unit tests |

**修改（7 個）**：

| 檔案 | 改動 |
|------|------|
| `interaction_executive/interaction_executive/state_machine.py` | 加 `PATROL_NAVIGATING`, `PATROL_PAUSED`, `EMERGENCY_LATCHED` 狀態；保留現有 IDLE/GREETING 等不動 |
| `interaction_executive/interaction_executive/interaction_executive_node.py` | 組合 safety_layer + patrol_handler + safety_tts；加 service servers |
| `go2_robot_sdk/config/twist_mux.yaml` | 加 emergency(255)/obstacle(200)/teleop(100)/nav2(10) 四個 input |
| `go2_robot_sdk/config/nav2_params.yaml` | `controller_frequency: 10.0` / `FollowPath.max_vel_x: 0.2` / `general_goal_checker.xy_goal_tolerance: 0.30` + `yaw_goal_tolerance: 0.30` / `behavior_server.behavior_plugins: []` |
| `go2_robot_sdk/launch/robot.launch.py` | Nav2 `/cmd_vel` remap 為 `/cmd_vel_nav` |
| `docs/mission/README.md` | P0 定義更新 |
| `docs/navigation/legacy-readme-from-導航避障.md` | 狀態卡更新 |

**驗證策略**：
- Pure Python modules（safety_layer, patrol_route_handler, safety_tts）走完整 TDD
- YAML / launch 改動用 `ros2 param get` + `ros2 topic echo` 手動驗證
- 整合測試用 mock Nav2 action server + real /scan subscribe
- 上 Go2 前全部 bench test 通過

---

## Task 1: SLAM 建圖流程（Gate P0-B）

**目標**：裝 slam_toolbox、寫建圖腳本、產出 `home_living_room.yaml`。

**Files:**
- Create: `scripts/build_map.sh`
- 本機產出: `/home/jetson/maps/home_living_room.{yaml,pgm}`

- [ ] **Step 1: 裝 slam_toolbox + Nav2 依賴（Jetson）**

Run on Jetson:
```bash
sudo apt update
sudo apt install -y ros-humble-slam-toolbox \
                    ros-humble-nav2-bringup \
                    ros-humble-navigation2 \
                    ros-humble-twist-mux \
                    ros-humble-nav2-map-server \
                    ros-humble-nav2-amcl
```

Expected: 全部安裝成功，無 conflict。

- [ ] **Step 2: 確認 slam_toolbox launch 存在**

Run:
```bash
ros2 launch slam_toolbox online_async_launch.py --show-args 2>&1 | head -20
```

Expected: 列出 `slam_params_file`, `use_sim_time` 等 args。

- [ ] **Step 3: 建立 maps 目錄**

Run on Jetson:
```bash
mkdir -p /home/jetson/maps
ls -la /home/jetson/maps
```

Expected: 目錄存在，owner `jetson`。

- [ ] **Step 4: 寫 `scripts/build_map.sh`**

```bash
#!/bin/bash
# scripts/build_map.sh — SLAM 建圖助手
# Usage: bash scripts/build_map.sh <map_name>
# Example: bash scripts/build_map.sh home_living_room

set -e

MAP_NAME="${1:-home_living_room}"
MAP_DIR="/home/jetson/maps"
OUTPUT_PATH="${MAP_DIR}/${MAP_NAME}"

mkdir -p "$MAP_DIR"

echo "=== SLAM 建圖 — ${MAP_NAME} ==="
echo "前提: RPLIDAR 已在跑 (/scan topic 有資料)"
echo ""
echo "1. 另開一個 terminal 確認 /scan 有資料:"
echo "   ros2 topic hz /scan"
echo ""
echo "2. 本腳本會啟動 slam_toolbox，請在 RViz/Foxglove 看 /map topic 逐漸成形"
echo "3. 手推 LiDAR（或 Go2）慢速繞場地一圈"
echo "4. 繞完按 Ctrl+C 停止本腳本，然後另開 terminal 執行 save:"
echo ""
echo "   ros2 service call /slam_toolbox/save_map \\"
echo "     slam_toolbox/srv/SaveMap \"{name: {data: '${OUTPUT_PATH}'}}\""
echo ""
echo "5. 會產出 ${OUTPUT_PATH}.pgm 與 ${OUTPUT_PATH}.yaml"
echo ""
read -p "確認 RPLIDAR 在跑後，按 Enter 啟動 slam_toolbox..."

source /opt/ros/humble/setup.bash
ros2 launch slam_toolbox online_async_launch.py
```

- [ ] **Step 5: 給執行權限**

Run:
```bash
chmod +x scripts/build_map.sh
ls -l scripts/build_map.sh
```

Expected: 有 `x` 權限。

- [ ] **Step 6: 實測（手動，需 RPLIDAR 在跑）**

```bash
# Jetson terminal 1 (RPLIDAR 已應該在跑；若沒在跑先啟動):
ros2 launch sllidar_ros2 sllidar_a2m12_launch.py

# Jetson terminal 2: 啟動建圖
bash scripts/build_map.sh home_living_room

# 手持 LiDAR 或推 Go2 走一圈（30-60 秒）
# 另開 terminal 3:
ros2 service call /slam_toolbox/save_map \
  slam_toolbox/srv/SaveMap "{name: {data: '/home/jetson/maps/home_living_room'}}"
```

Expected: `/home/jetson/maps/home_living_room.pgm` 和 `.yaml` 產生。用 `file` 或 `ls -la` 驗證。

- [ ] **Step 7: Commit**

```bash
git add scripts/build_map.sh
git commit -m "feat(nav): add build_map.sh SLAM 建圖助手（Gate P0-B）"
```

---

## Task 2: nav2_params.yaml + twist_mux.yaml 調參（Gate P0-C 的 config 前置）

**目標**：修改 Nav2 參數對齊 P0 速度 (0.2 m/s) + goal tolerance (0.30) + 禁用 recovery + controller freq 10Hz；同時擴充 twist_mux input。

**Files:**
- Modify: `go2_robot_sdk/config/nav2_params.yaml`
- Modify: `go2_robot_sdk/config/twist_mux.yaml`

- [ ] **Step 1: 備份現有 yaml**

Run:
```bash
cp go2_robot_sdk/config/nav2_params.yaml /tmp/nav2_params_backup.yaml
cp go2_robot_sdk/config/twist_mux.yaml /tmp/twist_mux_backup.yaml
```

- [ ] **Step 2: 修改 nav2_params.yaml — `controller_server.controller_frequency`**

Find `controller_server:` section, change:
```yaml
  ros__parameters:
    use_sim_time: False
    controller_frequency: 10.0   # 原 20.0，P0 降速
```

- [ ] **Step 3: 修改 nav2_params.yaml — `general_goal_checker`**

Find `general_goal_checker:` block, change:
```yaml
    general_goal_checker:
      stateful: True
      plugin: "nav2_controller::SimpleGoalChecker"
      xy_goal_tolerance: 0.30   # 原 0.20
      yaw_goal_tolerance: 0.30  # 原 0.70
```

- [ ] **Step 4: 修改 nav2_params.yaml — `FollowPath.max_vel_x`**

Find `FollowPath:` block, change:
```yaml
      max_vel_x: 0.2   # P0 demo 速度
```

（其他 vx_samples / vtheta_samples / sim_time 保留原值）

- [ ] **Step 5: 修改 nav2_params.yaml — 禁用 recovery (主選方案)**

Find `behavior_server:` section, change:
```yaml
behavior_server:
  ros__parameters:
    costmap_topic: local_costmap/costmap_raw
    footprint_topic: local_costmap/published_footprint
    cycle_frequency: 10.0
    behavior_plugins: []   # P0 禁用 recovery（R8 硬規則）
    # （原 spin/backup/drive_on_heading/assisted_teleop/wait 都清空）
```

把後面 `spin:` / `backup:` / `wait:` 等 plugin 配置留著（不會被用到因為 plugins: []），但 behavior_plugins 必須空。

- [ ] **Step 6: 修改 twist_mux.yaml — 定義四個 priority input**

替換整份 `twist_mux.yaml` 為：
```yaml
twist_mux:
  ros__parameters:
    topics:
      emergency:
        topic:    cmd_vel_emergency
        timeout:  0.5
        priority: 255
      obstacle:
        topic:    cmd_vel_obstacle
        timeout:  0.5
        priority: 200
      teleop:
        topic:    cmd_vel_teleop
        timeout:  0.5
        priority: 100
      nav2:
        topic:    cmd_vel_nav
        timeout:  0.5
        priority: 10
```

（若原檔已有其他 input 例如 joystick，保留並納入 priority 100 的 teleop 範圍）

- [ ] **Step 7: YAML 語法驗證**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('go2_robot_sdk/config/nav2_params.yaml'))"
python3 -c "import yaml; yaml.safe_load(open('go2_robot_sdk/config/twist_mux.yaml'))"
```

Expected: 兩個都無 output（無 exception）。

- [ ] **Step 8: Rebuild + source（Jetson）**

Run on Jetson:
```bash
cd ~/elder_and_dog   # 或對應路徑
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
```

Expected: build 成功。

- [ ] **Step 9: live parameter 驗證（需啟動 Nav2）**

Launch Nav2 stack（後續 Task 3 會完整跑，這步先做 quick check）:
```bash
ros2 launch go2_robot_sdk robot.launch.py nav2:=true slam:=false \
  map:=/home/jetson/maps/home_living_room.yaml &
sleep 15
ros2 param get /controller_server FollowPath.max_vel_x
ros2 param get /controller_server general_goal_checker.xy_goal_tolerance
ros2 param get /behavior_server behavior_plugins
pkill -f "ros2 launch"
```

Expected:
```
Double value is: 0.2
Double value is: 0.3
String values are: []
```

若不是 → 檢查是否有 install vs source 路徑問題（slam-nav2.md 踩坑紀錄）。

- [ ] **Step 10: Commit**

```bash
git add go2_robot_sdk/config/nav2_params.yaml go2_robot_sdk/config/twist_mux.yaml
git commit -m "config(nav): P0 參數調整 — 0.2 m/s, tolerance 0.30, recovery 禁用, twist_mux 4 input priority"
```

---

## Task 3: Nav2 載圖 + AMCL 單點到達（Gate P0-C + P0-D）

**目標**：確認 AMCL 收斂 + Nav2 NavigateToPose action 能從 mock 發 goal 到 Go2（或 mock robot）實際移動。

**Files:**
- Modify: `go2_robot_sdk/launch/robot.launch.py`（加 `/cmd_vel` remap）

- [ ] **Step 1: 找 launch.py 中 Nav2 啟動段**

Run:
```bash
grep -n "nav2_bringup\|cmd_vel\|navigation_launch\|bringup_launch" go2_robot_sdk/launch/robot.launch.py | head -20
```

記下行號。

- [ ] **Step 2: 修改 robot.launch.py — Nav2 cmd_vel remap**

在 Nav2 launch include 處（通常是 `IncludeLaunchDescription(nav2_bringup ...)`），加上 remap：

```python
# 在 Nav2 bringup 的 launch_arguments 或 composable_node args 中加：
launch_arguments=[
    ...
    ("cmd_vel_topic", "/cmd_vel_nav"),  # P0: Nav2 輸出到 twist_mux nav2 input
],
# 或用 SetRemap:
remappings=[("cmd_vel", "cmd_vel_nav")],
```

（實際寫法依 robot.launch.py 現有結構調整；關鍵是 Nav2 輸出端 topic 變 `/cmd_vel_nav`）

- [ ] **Step 3: 驗證 remap 生效**

Rebuild + launch:
```bash
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
ros2 launch go2_robot_sdk robot.launch.py nav2:=true slam:=false \
  map:=/home/jetson/maps/home_living_room.yaml &
sleep 20
ros2 topic list | grep cmd_vel
```

Expected: 看到 `/cmd_vel_nav`（Nav2 publisher）而不是 `/cmd_vel`。

- [ ] **Step 4: AMCL 初始 pose 設定**

```bash
bash scripts/set_initial_pose.sh 0.0 0.0 0.0
sleep 3
ros2 topic echo /amcl_pose --once
```

Expected: `/amcl_pose` 有 pose + covariance，pose.covariance[0] < 0.5（x 方差收斂）。

- [ ] **Step 5: Nav2 navigate_to_pose action 測試**

```bash
# 發一個 1m 前方的 goal
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "\
  {pose: {header: {frame_id: 'map'}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, \
   orientation: {w: 1.0}}}}" --feedback
```

Expected: action 接受 goal，feedback 持續回報 `distance_remaining` 逐漸變小（如果 Go2 在真機可以動；若只有手持 LiDAR 模擬則 feedback 有更新代表 planner 在算 path）。

**若 Go2 沒在、只測 planning**：看 `ros2 topic echo /plan` 有 poses 陣列就算 planner OK。

- [ ] **Step 6: Kill 測試**

```bash
pkill -f "ros2 launch"
pkill -9 -f go2_driver_node
```

- [ ] **Step 7: Commit**

```bash
git add go2_robot_sdk/launch/robot.launch.py
git commit -m "feat(nav): robot.launch.py Nav2 cmd_vel remap 為 /cmd_vel_nav"
```

---

## Task 4: twist_mux 路由驗證（Gate P0-D.5）

**目標**：驗證 cmd_vel 從不同 priority input 進去，最高優先級贏。這是隱性 gate，很多失敗是壞在中間 mux 而不是 Nav2 或 obstacle。

**Files:**
- Create: `scripts/verify_twist_mux.sh`

- [ ] **Step 1: 寫 verify_twist_mux.sh**

```bash
#!/bin/bash
# scripts/verify_twist_mux.sh — Gate P0-D.5 twist_mux 路由驗證
# 前提: robot.launch.py 已啟動（含 twist_mux）
# 驗證: publish 到不同 priority input，看 /cmd_vel 輸出（twist_mux output）是否符合優先級

set -e

echo "=== twist_mux 路由驗證（Gate P0-D.5）==="
echo ""

echo "[Test 1] nav2 (priority 10) 單獨發 linear.x=0.1"
timeout 2 ros2 topic pub /cmd_vel_nav geometry_msgs/Twist \
  "{linear: {x: 0.1}}" -r 10 &
sleep 1
X=$(timeout 1 ros2 topic echo /cmd_vel --once 2>/dev/null | grep -A1 linear | grep x | awk '{print $2}')
echo "  /cmd_vel linear.x = $X (expected ~0.1)"
wait

echo ""
echo "[Test 2] nav2 + obstacle (priority 200) 同時發 — obstacle 應該贏"
timeout 2 ros2 topic pub /cmd_vel_nav geometry_msgs/Twist \
  "{linear: {x: 0.1}}" -r 10 &
timeout 2 ros2 topic pub /cmd_vel_obstacle geometry_msgs/Twist \
  "{linear: {x: 0.0}}" -r 10 &
sleep 1
X=$(timeout 1 ros2 topic echo /cmd_vel --once 2>/dev/null | grep -A1 linear | grep x | awk '{print $2}')
echo "  /cmd_vel linear.x = $X (expected 0.0 — obstacle 優先)"
wait

echo ""
echo "[Test 3] nav2 + obstacle + emergency (priority 255) 全發 — emergency 應該贏"
timeout 2 ros2 topic pub /cmd_vel_nav geometry_msgs/Twist \
  "{linear: {x: 0.5}}" -r 10 &
timeout 2 ros2 topic pub /cmd_vel_obstacle geometry_msgs/Twist \
  "{linear: {x: 0.2}}" -r 10 &
timeout 2 ros2 topic pub /cmd_vel_emergency geometry_msgs/Twist \
  "{linear: {x: 0.0}}" -r 10 &
sleep 1
X=$(timeout 1 ros2 topic echo /cmd_vel --once 2>/dev/null | grep -A1 linear | grep x | awk '{print $2}')
echo "  /cmd_vel linear.x = $X (expected 0.0 — emergency 優先)"
wait

echo ""
echo "=== 全部 Test 通過才能進 Gate P0-E ==="
```

- [ ] **Step 2: 給執行權限**

```bash
chmod +x scripts/verify_twist_mux.sh
```

- [ ] **Step 3: 啟動 twist_mux + robot driver（或 mock）**

```bash
# 若有 Go2:
ros2 launch go2_robot_sdk robot.launch.py nav2:=true slam:=false \
  map:=/home/jetson/maps/home_living_room.yaml &

# 若無 Go2，只驗證 twist_mux:
ros2 launch twist_mux twist_mux_launch.py \
  config_topics:=go2_robot_sdk/config/twist_mux.yaml &
```

- [ ] **Step 4: 執行驗證**

```bash
bash scripts/verify_twist_mux.sh
```

Expected: 
- Test 1: linear.x ≈ 0.1
- Test 2: linear.x = 0.0（obstacle 贏 nav2）
- Test 3: linear.x = 0.0（emergency 贏全部）

任一不符合 → 檢查 twist_mux.yaml 設定、topic 名稱有沒有打錯。

- [ ] **Step 5: Kill 測試**

```bash
pkill -f "ros2 launch"
pkill -f "ros2 topic pub"
```

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_twist_mux.sh
git commit -m "test(nav): verify_twist_mux.sh — Gate P0-D.5 路由驗證"
```

---

## Task 5: Obstacle FSM 純 Python 模組（Gate P0-E — safety_layer.py part 1）

**目標**：實作 Obstacle auto-recovery FSM，純 Python，無 ROS2 依賴，100% testable。

**Files:**
- Create: `interaction_executive/interaction_executive/safety_layer.py`
- Create: `interaction_executive/test/test_safety_layer.py`

- [ ] **Step 1: 寫失敗測試 — ObstacleFSM 初始狀態**

```python
# interaction_executive/test/test_safety_layer.py
import pytest
import time
from interaction_executive.safety_layer import ObstacleFSM, ObstacleState


def test_obstacle_fsm_initial_state_is_clear():
    fsm = ObstacleFSM(clear_timeout_sec=3.0)
    assert fsm.state == ObstacleState.CLEAR
    assert fsm.is_blocking() is False
```

- [ ] **Step 2: Run test, expect FAIL**

Run:
```bash
cd /home/roy422/newLife/elder_and_dog
python3 -m pytest interaction_executive/test/test_safety_layer.py::test_obstacle_fsm_initial_state_is_clear -v
```

Expected: FAIL with `ModuleNotFoundError: safety_layer`

- [ ] **Step 3: 寫最小實作**

```python
# interaction_executive/interaction_executive/safety_layer.py
"""Safety Layer — Obstacle FSM + Emergency FSM.

純 Python，無 ROS2 依賴。ROS2 integration 在 interaction_executive_node.py。
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ObstacleState(Enum):
    CLEAR = "clear"
    STOP = "stop"


@dataclass
class ObstacleFSM:
    """Obstacle auto-recovery FSM.

    CLEAR --(obstacle detected)--> STOP
    STOP  --(連續 clear_timeout_sec 秒 clear)--> CLEAR
    """
    clear_timeout_sec: float = 3.0
    state: ObstacleState = ObstacleState.CLEAR
    _clear_since: Optional[float] = None
    _tts_played_this_session: bool = False

    def is_blocking(self) -> bool:
        return self.state == ObstacleState.STOP
```

- [ ] **Step 4: Run test, expect PASS**

```bash
python3 -m pytest interaction_executive/test/test_safety_layer.py::test_obstacle_fsm_initial_state_is_clear -v
```

Expected: PASS

- [ ] **Step 5: 寫失敗測試 — 偵測到障礙轉 STOP**

Append to test file:
```python
def test_obstacle_fsm_transitions_to_stop_on_detect():
    fsm = ObstacleFSM(clear_timeout_sec=3.0)
    should_play_tts = fsm.on_obstacle_detected(now=100.0)
    assert fsm.state == ObstacleState.STOP
    assert fsm.is_blocking() is True
    assert should_play_tts is True  # 第一次進 STOP 要播 TTS
```

- [ ] **Step 6: Run, expect FAIL**

Expected: FAIL with `AttributeError: on_obstacle_detected`

- [ ] **Step 7: 實作 on_obstacle_detected**

Append to safety_layer.py:
```python
    def on_obstacle_detected(self, now: float) -> bool:
        """
        Returns: True 若此次轉換觸發 TTS（第一次進 STOP）。
        """
        self._clear_since = None  # 重置清空計時
        if self.state == ObstacleState.CLEAR:
            self.state = ObstacleState.STOP
            self._tts_played_this_session = True
            return True  # 觸發 TTS
        return False  # 已在 STOP，不重播
```

- [ ] **Step 8: Run, expect PASS**

Expected: PASS

- [ ] **Step 9: 寫失敗測試 — 反洗版（同 session 不重播）**

```python
def test_obstacle_fsm_tts_not_replayed_in_same_session():
    fsm = ObstacleFSM(clear_timeout_sec=3.0)
    play1 = fsm.on_obstacle_detected(now=100.0)
    play2 = fsm.on_obstacle_detected(now=101.0)  # obstacle 持續
    play3 = fsm.on_obstacle_detected(now=105.0)  # 還是 obstacle
    assert play1 is True
    assert play2 is False
    assert play3 is False
```

- [ ] **Step 10: Run, expect PASS**（上步實作已涵蓋）

- [ ] **Step 11: 寫失敗測試 — 3 秒 clear 後回 CLEAR**

```python
def test_obstacle_fsm_auto_recovers_after_3s_clear():
    fsm = ObstacleFSM(clear_timeout_sec=3.0)
    fsm.on_obstacle_detected(now=100.0)
    assert fsm.state == ObstacleState.STOP

    fsm.on_obstacle_cleared(now=100.5)  # 障礙剛離開
    assert fsm.state == ObstacleState.STOP  # 還不夠 3 秒

    fsm.on_obstacle_cleared(now=102.0)  # 1.5s 累積
    assert fsm.state == ObstacleState.STOP

    fsm.on_obstacle_cleared(now=103.6)  # 3.1s 累積 → 恢復
    assert fsm.state == ObstacleState.CLEAR
```

- [ ] **Step 12: Run, expect FAIL**

Expected: FAIL (`on_obstacle_cleared` 不存在)

- [ ] **Step 13: 實作 on_obstacle_cleared**

```python
    def on_obstacle_cleared(self, now: float) -> None:
        if self.state == ObstacleState.CLEAR:
            self._clear_since = None
            return
        if self._clear_since is None:
            self._clear_since = now
        elif now - self._clear_since >= self.clear_timeout_sec:
            self.state = ObstacleState.CLEAR
            self._clear_since = None
            self._tts_played_this_session = False  # 重置，下次新 obstacle 可播
```

- [ ] **Step 14: Run, expect PASS**

Expected: PASS

- [ ] **Step 15: 寫失敗測試 — clear 中斷後重新計時**

```python
def test_obstacle_fsm_clear_interrupted_resets_timer():
    fsm = ObstacleFSM(clear_timeout_sec=3.0)
    fsm.on_obstacle_detected(now=100.0)
    fsm.on_obstacle_cleared(now=101.0)  # 1s clear
    fsm.on_obstacle_cleared(now=102.5)  # 2.5s clear（仍未滿 3s）

    fsm.on_obstacle_detected(now=103.0)  # 障礙又出現！計時歸零
    assert fsm.state == ObstacleState.STOP

    fsm.on_obstacle_cleared(now=104.0)  # 再 clear 1s
    assert fsm.state == ObstacleState.STOP  # 沒到 3s
```

- [ ] **Step 16: Run, expect PASS**（`_clear_since = None` in `on_obstacle_detected` 已涵蓋）

- [ ] **Step 17: 寫失敗測試 — obstacle stop 持續 >15s abort**

```python
def test_obstacle_fsm_stop_duration_exceeds_abort_threshold():
    fsm = ObstacleFSM(clear_timeout_sec=3.0, abort_after_sec=15.0)
    fsm.on_obstacle_detected(now=100.0)
    assert fsm.should_abort(now=110.0) is False  # 10s < 15s
    assert fsm.should_abort(now=115.5) is True   # 15.5s > 15s
```

- [ ] **Step 18: Run, expect FAIL**

- [ ] **Step 19: 實作 abort_after_sec + should_abort**

Modify dataclass + add method:
```python
@dataclass
class ObstacleFSM:
    clear_timeout_sec: float = 3.0
    abort_after_sec: float = 15.0
    state: ObstacleState = ObstacleState.CLEAR
    _clear_since: Optional[float] = None
    _stop_since: Optional[float] = None
    _tts_played_this_session: bool = False

    def on_obstacle_detected(self, now: float) -> bool:
        self._clear_since = None
        if self.state == ObstacleState.CLEAR:
            self.state = ObstacleState.STOP
            self._stop_since = now
            self._tts_played_this_session = True
            return True
        return False

    def should_abort(self, now: float) -> bool:
        if self.state != ObstacleState.STOP or self._stop_since is None:
            return False
        return (now - self._stop_since) >= self.abort_after_sec

    # (on_obstacle_cleared 和 is_blocking 不變)
```

同時在 `on_obstacle_cleared` 轉回 CLEAR 時重置 `_stop_since = None`。

- [ ] **Step 20: Run all tests, expect PASS**

```bash
python3 -m pytest interaction_executive/test/test_safety_layer.py -v
```

Expected: 5 tests PASS

- [ ] **Step 21: Commit**

```bash
git add interaction_executive/interaction_executive/safety_layer.py \
        interaction_executive/test/test_safety_layer.py
git commit -m "feat(safety): ObstacleFSM auto-recovery + TTS 反洗版 + 15s abort"
```

---

## Task 6: Emergency FSM（Gate P0-F — safety_layer.py part 2，5/1 硬截止）

**目標**：加 EmergencyFSM latched state machine。

**Files:**
- Modify: `interaction_executive/interaction_executive/safety_layer.py`
- Modify: `interaction_executive/test/test_safety_layer.py`

- [ ] **Step 1: 寫失敗測試 — EmergencyFSM 初始 NORMAL**

Append to test file:
```python
from interaction_executive.safety_layer import EmergencyFSM, EmergencyState


def test_emergency_fsm_initial_state_is_normal():
    fsm = EmergencyFSM()
    assert fsm.state == EmergencyState.NORMAL
    assert fsm.is_latched() is False
```

- [ ] **Step 2: Run, expect FAIL**（EmergencyFSM 不存在）

- [ ] **Step 3: 實作 EmergencyFSM**

Append to safety_layer.py:
```python
class EmergencyState(Enum):
    NORMAL = "normal"
    LATCHED = "latched"


@dataclass
class EmergencyFSM:
    """Latched emergency state.

    NORMAL --(trigger_emergency)--> LATCHED
    LATCHED --(reset_emergency)--> NORMAL
    Repeated trigger in LATCHED = idempotent (no-op).
    """
    state: EmergencyState = EmergencyState.NORMAL

    def is_latched(self) -> bool:
        return self.state == EmergencyState.LATCHED

    def trigger(self) -> bool:
        """Returns True if state changed (first trigger)."""
        if self.state == EmergencyState.NORMAL:
            self.state = EmergencyState.LATCHED
            return True
        return False  # Already latched = idempotent

    def reset(self) -> bool:
        """Returns True if state changed."""
        if self.state == EmergencyState.LATCHED:
            self.state = EmergencyState.NORMAL
            return True
        return False
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: 寫失敗測試 — trigger/reset 語義**

```python
def test_emergency_fsm_trigger_latches():
    fsm = EmergencyFSM()
    changed = fsm.trigger()
    assert changed is True
    assert fsm.is_latched() is True


def test_emergency_fsm_repeated_trigger_is_idempotent():
    fsm = EmergencyFSM()
    fsm.trigger()
    changed = fsm.trigger()  # 再觸發
    assert changed is False  # 沒變化
    assert fsm.is_latched() is True


def test_emergency_fsm_reset_unlatches():
    fsm = EmergencyFSM()
    fsm.trigger()
    changed = fsm.reset()
    assert changed is True
    assert fsm.is_latched() is False


def test_emergency_fsm_reset_when_normal_is_noop():
    fsm = EmergencyFSM()
    changed = fsm.reset()
    assert changed is False  # 本來就 normal
    assert fsm.is_latched() is False
```

- [ ] **Step 6: Run, expect PASS**（實作已涵蓋）

- [ ] **Step 7: 寫失敗測試 — 組合：emergency override obstacle**

```python
def test_safety_layer_emergency_overrides_obstacle():
    """EMERGENCY_LATCHED 時，obstacle 事件不參與控制決策。"""
    from interaction_executive.safety_layer import SafetyLayer

    layer = SafetyLayer()
    layer.emergency.trigger()
    # 此時 obstacle 偵測到，但 emergency 優先
    layer.obstacle.on_obstacle_detected(now=100.0)

    # 最終決策：blocked by emergency (不是 obstacle)
    decision = layer.decide(now=100.0)
    assert decision.blocked_by == "emergency"
    assert decision.should_publish_obstacle_cmd_vel is False
    assert decision.should_publish_emergency_cmd_vel is True
```

- [ ] **Step 8: Run, expect FAIL**（SafetyLayer / decide 不存在）

- [ ] **Step 9: 實作 SafetyLayer 聚合器**

Append to safety_layer.py:
```python
@dataclass
class SafetyDecision:
    blocked_by: Optional[str]  # "emergency" | "obstacle" | None
    should_publish_emergency_cmd_vel: bool
    should_publish_obstacle_cmd_vel: bool
    should_play_safety_tts: Optional[str]  # template key | None


@dataclass
class SafetyLayer:
    """Top-level safety aggregator.

    Priority: emergency > obstacle > pass-through
    """
    emergency: EmergencyFSM = field(default_factory=EmergencyFSM)
    obstacle: ObstacleFSM = field(default_factory=ObstacleFSM)

    def decide(self, now: float) -> SafetyDecision:
        if self.emergency.is_latched():
            return SafetyDecision(
                blocked_by="emergency",
                should_publish_emergency_cmd_vel=True,
                should_publish_obstacle_cmd_vel=False,
                should_play_safety_tts=None,  # TTS 由 trigger 時另發
            )
        if self.obstacle.is_blocking():
            return SafetyDecision(
                blocked_by="obstacle",
                should_publish_emergency_cmd_vel=False,
                should_publish_obstacle_cmd_vel=True,
                should_play_safety_tts=None,
            )
        return SafetyDecision(
            blocked_by=None,
            should_publish_emergency_cmd_vel=False,
            should_publish_obstacle_cmd_vel=False,
            should_play_safety_tts=None,
        )
```

- [ ] **Step 10: Run all tests, expect PASS**

```bash
python3 -m pytest interaction_executive/test/test_safety_layer.py -v
```

Expected: 所有 tests PASS（5 obstacle + 4 emergency + 1 combined = 10）

- [ ] **Step 11: Commit**

```bash
git add interaction_executive/interaction_executive/safety_layer.py \
        interaction_executive/test/test_safety_layer.py
git commit -m "feat(safety): EmergencyFSM latched + SafetyLayer aggregator（Gate P0-F）"
```

---

## Task 7: patrol_route_handler.py（Gate P0-E 的 Nav2 wrapper）

**目標**：Nav2 NavigateToPose ActionClient 包裝成 handler，支援 start/pause/resume/cancel 語義。

**Files:**
- Create: `interaction_executive/interaction_executive/skills/__init__.py`（空）
- Create: `interaction_executive/interaction_executive/skills/patrol_route_handler.py`
- Create: `interaction_executive/test/test_patrol_route_handler.py`

- [ ] **Step 1: 建 skills package**

```bash
mkdir -p interaction_executive/interaction_executive/skills
touch interaction_executive/interaction_executive/skills/__init__.py
```

- [ ] **Step 2: 寫失敗測試 — PatrolRouteHandler 初始 IDLE**

```python
# interaction_executive/test/test_patrol_route_handler.py
import pytest
from unittest.mock import MagicMock
from interaction_executive.skills.patrol_route_handler import (
    PatrolRouteHandler, PatrolState, Waypoint,
)


def test_handler_initial_state_is_idle():
    node = MagicMock()  # 假 ROS2 node
    handler = PatrolRouteHandler(node)
    assert handler.state == PatrolState.IDLE
```

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: 實作骨架**

```python
# interaction_executive/interaction_executive/skills/patrol_route_handler.py
"""Patrol Route Handler — Nav2 NavigateToPose ActionClient wrapper.

State machine: IDLE / NAVIGATING / PAUSED / COMPLETED / CANCELLED
"""
from dataclasses import dataclass
from enum import Enum


class PatrolState(Enum):
    IDLE = "idle"
    NAVIGATING = "navigating"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Waypoint:
    x: float
    y: float
    yaw: float = 0.0


class PatrolRouteHandler:
    def __init__(self, node):
        self._node = node
        self.state = PatrolState.IDLE
        self._goal_handle = None

    def start(self, waypoint: Waypoint) -> bool:
        """Returns True if goal sent."""
        if self.state != PatrolState.IDLE:
            return False
        # 實作 send_goal 在下一 step
        self.state = PatrolState.NAVIGATING
        return True

    def pause(self) -> bool:
        if self.state == PatrolState.NAVIGATING:
            self.state = PatrolState.PAUSED
            return True
        return False

    def resume(self) -> bool:
        if self.state == PatrolState.PAUSED:
            self.state = PatrolState.NAVIGATING
            return True
        return False

    def cancel(self) -> bool:
        if self.state in (PatrolState.NAVIGATING, PatrolState.PAUSED):
            # 實際 cancel_goal_async 在整合 step
            self.state = PatrolState.CANCELLED
            return True
        return False

    def mark_completed(self) -> None:
        """Called by action result callback."""
        if self.state == PatrolState.NAVIGATING:
            self.state = PatrolState.COMPLETED
```

- [ ] **Step 5: Run, expect PASS**

- [ ] **Step 6: 寫失敗測試 — start 後 state=NAVIGATING**

```python
def test_handler_start_transitions_to_navigating():
    node = MagicMock()
    handler = PatrolRouteHandler(node)
    sent = handler.start(Waypoint(x=1.0, y=0.0, yaw=0.0))
    assert sent is True
    assert handler.state == PatrolState.NAVIGATING


def test_handler_cannot_start_twice():
    node = MagicMock()
    handler = PatrolRouteHandler(node)
    handler.start(Waypoint(1.0, 0.0))
    sent = handler.start(Waypoint(2.0, 0.0))  # 已在 NAVIGATING
    assert sent is False
    assert handler.state == PatrolState.NAVIGATING
```

- [ ] **Step 7: Run, expect PASS**

- [ ] **Step 8: 寫失敗測試 — pause/resume 語義**

```python
def test_handler_pause_from_navigating():
    node = MagicMock()
    handler = PatrolRouteHandler(node)
    handler.start(Waypoint(1.0, 0.0))
    paused = handler.pause()
    assert paused is True
    assert handler.state == PatrolState.PAUSED


def test_handler_resume_from_paused():
    node = MagicMock()
    handler = PatrolRouteHandler(node)
    handler.start(Waypoint(1.0, 0.0))
    handler.pause()
    resumed = handler.resume()
    assert resumed is True
    assert handler.state == PatrolState.NAVIGATING


def test_handler_pause_from_idle_is_noop():
    node = MagicMock()
    handler = PatrolRouteHandler(node)
    paused = handler.pause()
    assert paused is False
    assert handler.state == PatrolState.IDLE


def test_handler_cancel_from_navigating():
    node = MagicMock()
    handler = PatrolRouteHandler(node)
    handler.start(Waypoint(1.0, 0.0))
    cancelled = handler.cancel()
    assert cancelled is True
    assert handler.state == PatrolState.CANCELLED
```

- [ ] **Step 9: Run, expect PASS**（實作已涵蓋）

- [ ] **Step 10: Commit**

```bash
git add interaction_executive/interaction_executive/skills/ \
        interaction_executive/test/test_patrol_route_handler.py
git commit -m "feat(nav): PatrolRouteHandler state machine skeleton（Gate P0-E）"
```

---

## Task 8: safety_tts.py 固定模板發佈器（Gate P0-G）

**目標**：實作 safety_tts + navigation status_tts 6 句固定模板，永不經 LLM。

**Files:**
- Create: `interaction_executive/interaction_executive/safety_tts.py`

- [ ] **Step 1: 寫失敗測試 — 模板字典存在**

Append to `test_safety_layer.py`:
```python
def test_safety_tts_templates_exist():
    from interaction_executive.safety_tts import SAFETY_TTS_TEMPLATES
    assert SAFETY_TTS_TEMPLATES["obstacle_warning"] == "前方有障礙，請讓路"
    assert SAFETY_TTS_TEMPLATES["emergency_triggered"] == "緊急停止，請協助處理"


def test_navigation_status_tts_templates_exist():
    from interaction_executive.safety_tts import NAVIGATION_STATUS_TTS_TEMPLATES
    assert NAVIGATION_STATUS_TTS_TEMPLATES["patrol_start"] == "開始巡邏"
    assert NAVIGATION_STATUS_TTS_TEMPLATES["arrived"] == "已到達目的地"
    assert NAVIGATION_STATUS_TTS_TEMPLATES["patrol_abort"] == "定位失準，停止巡邏"
    assert NAVIGATION_STATUS_TTS_TEMPLATES["patrol_timeout"] == "巡邏超時，已停止"
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: 寫最小實作**

```python
# interaction_executive/interaction_executive/safety_tts.py
"""Safety / Navigation Status TTS — 固定模板，永不經 LLM（R3 硬規則）.

本模組負責兩類：
- safety_tts: 安全提醒（obstacle / emergency）
- navigation status_tts: 導航狀態（巡邏開始/到達/abort/timeout）

兩類合併在同一模組管理，避免過度拆分。
"""
from typing import Optional


SAFETY_TTS_TEMPLATES = {
    "obstacle_warning":    "前方有障礙，請讓路",
    "emergency_triggered": "緊急停止，請協助處理",
}

NAVIGATION_STATUS_TTS_TEMPLATES = {
    "patrol_start":   "開始巡邏",
    "arrived":        "已到達目的地",
    "patrol_abort":   "定位失準，停止巡邏",
    "patrol_timeout": "巡邏超時，已停止",
}


class SafetyTTSPublisher:
    """Publishes safety_tts to /tts topic. Never uses LLM."""

    def __init__(self, ros_publisher):
        """
        Args:
            ros_publisher: rclpy Publisher[std_msgs/String] on /tts
        """
        self._pub = ros_publisher

    def publish_safety(self, template_key: str) -> bool:
        """Returns True if published, False if template key not found."""
        text = SAFETY_TTS_TEMPLATES.get(template_key)
        if text is None:
            return False
        from std_msgs.msg import String
        msg = String()
        msg.data = text
        self._pub.publish(msg)
        return True

    def publish_navigation_status(self, template_key: str) -> bool:
        text = NAVIGATION_STATUS_TTS_TEMPLATES.get(template_key)
        if text is None:
            return False
        from std_msgs.msg import String
        msg = String()
        msg.data = text
        self._pub.publish(msg)
        return True
```

- [ ] **Step 4: Run, expect PASS**

- [ ] **Step 5: 寫測試 — 未知 key 回 False**

```python
def test_publisher_unknown_key_returns_false():
    from interaction_executive.safety_tts import SafetyTTSPublisher
    from unittest.mock import MagicMock
    pub = SafetyTTSPublisher(MagicMock())
    assert pub.publish_safety("unknown_key") is False
    assert pub.publish_navigation_status("made_up") is False
```

- [ ] **Step 6: Run, expect PASS**

- [ ] **Step 7: 寫測試 — 已知 key 呼叫 publish**

```python
def test_publisher_known_key_calls_publish():
    from interaction_executive.safety_tts import SafetyTTSPublisher
    from unittest.mock import MagicMock
    mock_pub = MagicMock()
    pub = SafetyTTSPublisher(mock_pub)

    result = pub.publish_safety("obstacle_warning")
    assert result is True
    mock_pub.publish.assert_called_once()
    call_arg = mock_pub.publish.call_args[0][0]
    assert call_arg.data == "前方有障礙，請讓路"
```

- [ ] **Step 8: Run, expect PASS**

- [ ] **Step 9: Commit**

```bash
git add interaction_executive/interaction_executive/safety_tts.py \
        interaction_executive/test/test_safety_layer.py
git commit -m "feat(tts): safety_tts.py — 6 句固定模板（R3 永不經 LLM）"
```

---

## Task 9: emergency_stop.py hotkey（Gate P0-F 的使用者入口）

**目標**：Jetson 鍵盤 hotkey script — 按 `q` 呼叫 `/pawai/safety/trigger_emergency`，按 `r` 呼叫 `/pawai/safety/reset_emergency`。

**Files:**
- Create: `scripts/emergency_stop.py`

- [ ] **Step 1: 寫 script**

```python
#!/usr/bin/env python3
# scripts/emergency_stop.py
"""Primary kill switch — 鍵盤 hotkey for emergency trigger/reset.

Usage (Jetson):
    python3 scripts/emergency_stop.py

    q  → call /pawai/safety/trigger_emergency
    r  → call /pawai/safety/reset_emergency
    Ctrl+C → exit
"""
import sys
import termios
import tty
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


class EmergencyHotkey(Node):
    def __init__(self):
        super().__init__("emergency_hotkey_client")
        self._trigger_cli = self.create_client(Trigger, "/pawai/safety/trigger_emergency")
        self._reset_cli = self.create_client(Trigger, "/pawai/safety/reset_emergency")
        self.get_logger().info("Waiting for safety services...")
        self._trigger_cli.wait_for_service(timeout_sec=10.0)
        self._reset_cli.wait_for_service(timeout_sec=10.0)
        self.get_logger().info("Ready. Press 'q' to TRIGGER, 'r' to RESET, Ctrl+C to exit.")

    def trigger(self):
        req = Trigger.Request()
        future = self._trigger_cli.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
        if future.result() is not None:
            self.get_logger().warn(f"TRIGGER emergency: {future.result().message}")
        else:
            self.get_logger().error("TRIGGER service call failed!")

    def reset(self):
        req = Trigger.Request()
        future = self._reset_cli.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
        if future.result() is not None:
            self.get_logger().info(f"RESET emergency: {future.result().message}")
        else:
            self.get_logger().error("RESET service call failed!")


def read_char():
    """Non-blocking single char read."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def main():
    rclpy.init()
    node = EmergencyHotkey()
    try:
        while True:
            ch = read_char()
            if ch == "q":
                node.trigger()
            elif ch == "r":
                node.reset()
            elif ch == "\x03":  # Ctrl+C
                break
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 給執行權限**

```bash
chmod +x scripts/emergency_stop.py
```

- [ ] **Step 3: 驗證 Python import ok（WSL 端先 syntax check）**

```bash
python3 -c "import ast; ast.parse(open('scripts/emergency_stop.py').read())"
```

Expected: 無 error。

- [ ] **Step 4: 整合測試會在 Task 10 完成後做（需要 service 在 executive_node 實作完）**

先跳過，Task 10 完整整合後再跑完整 e2e。

- [ ] **Step 5: Commit**

```bash
git add scripts/emergency_stop.py
git commit -m "feat(safety): emergency_stop.py 鍵盤 hotkey client（Gate P0-F）"
```

---

## Task 10: interaction_executive_node.py 整合（Gate P0-F 完整整合）

**目標**：把 SafetyLayer + PatrolRouteHandler + SafetyTTSPublisher 串起來，加兩個 Service server。這是 5/1 硬截止 gate 的最後一塊。

**Files:**
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py`

- [ ] **Step 1: 讀現有 node 檔案開頭**

```bash
head -50 interaction_executive/interaction_executive/interaction_executive_node.py
```

確認 imports / __init__ 區塊位置。

- [ ] **Step 2: 加 imports 區（檔案頂部）**

在現有 import 區加入：
```python
from std_srvs.srv import Trigger
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose

from .safety_layer import SafetyLayer, SafetyDecision
from .safety_tts import SafetyTTSPublisher
from .skills.patrol_route_handler import PatrolRouteHandler, PatrolState, Waypoint
```

- [ ] **Step 3: 在 `__init__` 加入 safety + publishers**

在 `self._pub_cmd_vel` 行附近加：
```python
# Safety Layer publishers（twist_mux priority）
self._pub_cmd_vel_emergency = self.create_publisher(Twist, "/cmd_vel_emergency", 10)
self._pub_cmd_vel_obstacle = self.create_publisher(Twist, "/cmd_vel_obstacle", 10)
# Nav2 原本的 cmd_vel 現在走 /cmd_vel_nav（透過 launch remap）
# 保留 self._pub_cmd_vel 不用（legacy，P1 再清）

# Safety Layer 狀態
self._safety = SafetyLayer()
self._safety_tts = SafetyTTSPublisher(self._pub_tts)
self._patrol = PatrolRouteHandler(self)

# Service servers
self._srv_trigger = self.create_service(
    Trigger, "/pawai/safety/trigger_emergency", self._on_trigger_emergency
)
self._srv_reset = self.create_service(
    Trigger, "/pawai/safety/reset_emergency", self._on_reset_emergency
)

# 10Hz tick — 發 emergency/obstacle cmd_vel
self._safety_tick_timer = self.create_timer(0.1, self._safety_tick)
```

- [ ] **Step 4: 加 service callback 實作**

在 class 內加新 method：
```python
def _on_trigger_emergency(self, request, response):
    import time
    changed = self._safety.emergency.trigger()
    if changed:
        # 1. 立刻發 StopMove
        req = WebRtcReq()
        req.api_id = 1003  # StopMove
        req.topic = "rt/api/sport/request"
        self._pub_webrtc.publish(req)
        # 2. 播固定 TTS
        self._safety_tts.publish_safety("emergency_triggered")
        # 3. Cancel patrol 如果在跑
        self._patrol.cancel()
        self.get_logger().warn("EMERGENCY LATCHED")
    response.success = True
    response.message = "emergency_latched" if self._safety.emergency.is_latched() else "normal"
    return response

def _on_reset_emergency(self, request, response):
    changed = self._safety.emergency.reset()
    response.success = True
    response.message = "reset_ok" if changed else "was_already_normal"
    if changed:
        self.get_logger().info("EMERGENCY RESET → NORMAL")
    return response
```

- [ ] **Step 5: 加 safety_tick 實作（10Hz 發 zero Twist）**

```python
def _safety_tick(self):
    import time
    now = time.monotonic()

    # obstacle abort 檢查
    if self._safety.obstacle.should_abort(now):
        self._patrol.cancel()
        self._safety_tts.publish_navigation_status("patrol_timeout")
        self._safety.obstacle.state = ObstacleState.CLEAR  # 重置
        return

    decision = self._safety.decide(now)
    zero = Twist()
    if decision.should_publish_emergency_cmd_vel:
        self._pub_cmd_vel_emergency.publish(zero)
    if decision.should_publish_obstacle_cmd_vel:
        self._pub_cmd_vel_obstacle.publish(zero)
```

還要在頂部 import `from .safety_layer import ObstacleState`

- [ ] **Step 6: 修改 `_on_obstacle` callback 串 SafetyLayer.obstacle**

找現有 `_on_obstacle` method，改為：
```python
def _on_obstacle(self, msg: String):
    import time
    try:
        data = json.loads(msg.data)
    except json.JSONDecodeError:
        return

    now = time.monotonic()
    zone = data.get("zone", "clear")

    if self._safety.emergency.is_latched():
        # R5: emergency 鎖定所有恢復類行為，observe only
        return

    if zone == "danger":
        should_play = self._safety.obstacle.on_obstacle_detected(now)
        if should_play:
            self._safety_tts.publish_safety("obstacle_warning")
            self._patrol.pause()
    elif zone == "clear":
        was_blocking = self._safety.obstacle.is_blocking()
        self._safety.obstacle.on_obstacle_cleared(now)
        if was_blocking and not self._safety.obstacle.is_blocking():
            # 剛從 STOP 回到 CLEAR
            self._patrol.resume()
```

- [ ] **Step 7: Rebuild + source**

Run:
```bash
cd ~/elder_and_dog
colcon build --packages-select interaction_executive
source install/setup.zsh
```

Expected: build success.

- [ ] **Step 8: 單元測試**

```bash
python3 -m pytest interaction_executive/test/ -v
```

Expected: 全部 PASS（之前 Task 5-8 的 tests 仍通過）。

- [ ] **Step 9: 整合測試 — 啟動 executive + 測 service**

```bash
ros2 run interaction_executive interaction_executive_node &
sleep 3

# 確認 service 存在
ros2 service list | grep pawai/safety
# Expected: /pawai/safety/trigger_emergency
#           /pawai/safety/reset_emergency

# 呼叫 trigger
ros2 service call /pawai/safety/trigger_emergency std_srvs/srv/Trigger {}
# Expected: success: true, message: "emergency_latched"

# 看 /cmd_vel_emergency 有沒有在發（10Hz）
timeout 2 ros2 topic hz /cmd_vel_emergency
# Expected: ~10 Hz

# Reset
ros2 service call /pawai/safety/reset_emergency std_srvs/srv/Trigger {}
# Expected: success: true, message: "reset_ok"

# Kill
pkill -f interaction_executive_node
```

- [ ] **Step 10: hotkey 整合測試（Jetson terminal）**

```bash
# Terminal 1
ros2 run interaction_executive interaction_executive_node

# Terminal 2
python3 scripts/emergency_stop.py
# 按 q → Terminal 1 應看到 "EMERGENCY LATCHED"
# 按 r → Terminal 1 應看到 "EMERGENCY RESET"
```

Expected: 雙向觸發都 work。

- [ ] **Step 11: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_executive_node.py
git commit -m "feat(safety): executive 整合 SafetyLayer + service + hotkey（Gate P0-F 完成）"
```

---

## Task 11: state_machine.py 加 patrol 狀態（Gate P0-E 尾聲）

**目標**：現有 `state_machine.py` 加 `PATROL_NAVIGATING`, `PATROL_PAUSED`, `EMERGENCY_LATCHED` 三個 state。

**Files:**
- Modify: `interaction_executive/interaction_executive/state_machine.py`

- [ ] **Step 1: 找現有 ExecutiveState enum**

```bash
grep -n "class ExecutiveState\|IDLE\|GREETING" interaction_executive/interaction_executive/state_machine.py | head -10
```

- [ ] **Step 2: 加三個新狀態**

在 ExecutiveState enum 中加：
```python
class ExecutiveState(Enum):
    IDLE = "idle"
    # ... 其他現有 state ...
    PATROL_NAVIGATING = "patrol_navigating"  # P0 新增
    PATROL_PAUSED = "patrol_paused"          # P0 新增
    EMERGENCY_LATCHED = "emergency_latched"  # P0 新增
```

- [ ] **Step 3: 驗證 build**

```bash
colcon build --packages-select interaction_executive
source install/setup.zsh
python3 -m pytest interaction_executive/test/ -v
```

Expected: 所有 test PASS（加新 enum 不破壞現有 state machine）。

- [ ] **Step 4: Commit**

```bash
git add interaction_executive/interaction_executive/state_machine.py
git commit -m "feat(executive): 加 PATROL/EMERGENCY_LATCHED 狀態到 state_machine"
```

---

## Task 12: start_patrol_demo_tmux.sh 一鍵啟動（Gate P0-H 準備）

**目標**：Demo 啟動腳本，自動開 tmux 並跑所有必要 node。

**Files:**
- Create: `scripts/start_patrol_demo_tmux.sh`

- [ ] **Step 1: 寫腳本**

```bash
#!/bin/bash
# scripts/start_patrol_demo_tmux.sh — P0 Demo 一鍵啟動
set -e

SESSION="patrol_demo"
MAP_PATH="${MAP_PATH:-/home/jetson/maps/home_living_room.yaml}"

if [ ! -f "$MAP_PATH" ]; then
    echo "ERROR: 地圖不存在 $MAP_PATH"
    echo "先跑 bash scripts/build_map.sh 建圖"
    exit 1
fi

# 先清場
echo "=== 清場 ==="
bash scripts/go2_ros_preflight.sh prelaunch || true
sleep 2

# 建 tmux session
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -n main

SETUP_CMD="source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh"

# Window 1: go2_driver + Nav2
tmux rename-window -t "$SESSION:0" driver
tmux send-keys -t "$SESSION:driver" \
  "${SETUP_CMD} && ros2 launch go2_robot_sdk robot.launch.py \
    nav2:=true slam:=false map:=${MAP_PATH}" C-m

sleep 8

# Window 2: RPLIDAR
tmux new-window -t "$SESSION" -n rplidar
tmux send-keys -t "$SESSION:rplidar" \
  "${SETUP_CMD} && source ~/rplidar_ws/install/setup.bash && \
   ros2 launch sllidar_ros2 sllidar_a2m12_launch.py" C-m

# Window 3: lidar_obstacle_node
tmux new-window -t "$SESSION" -n obstacle
tmux send-keys -t "$SESSION:obstacle" \
  "${SETUP_CMD} && ros2 run vision_perception lidar_obstacle_node" C-m

# Window 4: interaction_executive
tmux new-window -t "$SESSION" -n executive
tmux send-keys -t "$SESSION:executive" \
  "${SETUP_CMD} && ros2 run interaction_executive interaction_executive_node" C-m

# Window 5: TTS
tmux new-window -t "$SESSION" -n tts
tmux send-keys -t "$SESSION:tts" \
  "${SETUP_CMD} && ros2 run speech_processor tts_node" C-m

# Window 6: emergency_stop hotkey
tmux new-window -t "$SESSION" -n hotkey
tmux send-keys -t "$SESSION:hotkey" \
  "${SETUP_CMD} && python3 ~/elder_and_dog/scripts/emergency_stop.py" C-m

# Window 7: foxglove_bridge
tmux new-window -t "$SESSION" -n foxglove
tmux send-keys -t "$SESSION:foxglove" \
  "${SETUP_CMD} && ros2 run foxglove_bridge foxglove_bridge" C-m

# Window 8: 空白（下 initial pose 指令用）
tmux new-window -t "$SESSION" -n pose
tmux send-keys -t "$SESSION:pose" \
  "${SETUP_CMD}" C-m

echo ""
echo "=== tmux session '${SESSION}' 已啟動 ==="
echo "tmux attach -t ${SESSION}"
echo ""
echo "下一步:"
echo "1. 等 AMCL 啟動（~15s）"
echo "2. 切到 pose window 跑: bash scripts/set_initial_pose.sh 0.0 0.0 0.0"
echo "3. Foxglove 連 ws://jetson-nano:8765 看狀態"
echo "4. 發 patrol goal: ros2 action send_goal /navigate_to_pose ..."
echo "5. 準備好按 Ctrl+Q 切到 hotkey window，q=emergency, r=reset"
```

- [ ] **Step 2: 權限**

```bash
chmod +x scripts/start_patrol_demo_tmux.sh
```

- [ ] **Step 3: 驗證 bash 語法**

```bash
bash -n scripts/start_patrol_demo_tmux.sh
```

Expected: 無輸出（無 syntax error）。

- [ ] **Step 4: Commit**

```bash
git add scripts/start_patrol_demo_tmux.sh
git commit -m "feat(demo): start_patrol_demo_tmux.sh 一鍵啟動全 stack"
```

---

## Task 13: Go2 實機整合測試（Gate P0-H）

**目標**：Go2 接上穩定電源、跑完 start_patrol_demo_tmux.sh、驗證 /cmd_vel_nav → twist_mux → Go2 實際移動。

**Files:** 無新檔案，manual integration。

- [ ] **Step 1: Pre-flight checklist**

```bash
# 確認 Jetson 接穩定電源（不用 Go2 供電）
# 確認 RPLIDAR 兩條 USB 線都接好
# 確認 D435 + 麥克風 + 喇叭 可選（P0 不需要，節省 USB 頻寬）
# 確認地圖檔存在: ls /home/jetson/maps/home_living_room.yaml
```

- [ ] **Step 2: 啟動 Demo**

```bash
ssh jetson-nano
cd ~/elder_and_dog
bash scripts/start_patrol_demo_tmux.sh
```

等 15 秒讓所有 node 啟動。

- [ ] **Step 3: 設 initial pose**

```bash
tmux attach -t patrol_demo
# 切到 pose window: Ctrl+b 然後按數字鍵 7
bash scripts/set_initial_pose.sh 0.0 0.0 0.0
sleep 3
ros2 topic echo /amcl_pose --once
```

Expected: pose.covariance[0] < 0.5。

- [ ] **Step 4: 送 patrol goal**

```bash
# 假設 B 點在 (2.0, 0.0) — 從地圖測量調整
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}, pose: {position: {x: 2.0, y: 0.0, z: 0.0}, \
   orientation: {w: 1.0}}}}" --feedback
```

Expected: Go2 開始走（0.2 m/s），feedback `distance_remaining` 遞減。

- [ ] **Step 5: 測 obstacle pause/resume**

走到一半，站到 Go2 前方 0.5m：
- 預期：Go2 停下
- Foxglove 看 `/state/pawai_brain` safety_flags.obstacle = true
- 聽到 「前方有障礙，請讓路」
- 離開 Go2 前方
- 3 秒後 Go2 繼續走
- 不應重播 TTS

- [ ] **Step 6: 測 emergency 按 q**

Go2 移動中，切到 hotkey window 按 `q`：
- 預期：Go2 立刻停
- 聽到 「緊急停止，請協助處理」
- Go2 不會自己動（無論 obstacle 是否清空）
- 切到 executive window 看 log 有 `EMERGENCY LATCHED`

按 `r` reset：
- Go2 仍不動（goal 已 cancel）
- 需要重新發 action goal 才會動

- [ ] **Step 7: 記錄結果**

在 `docs/mission/demo-script-p0.md` 記錄這次試跑結果（建立檔案）：
```markdown
# P0 Demo 試跑紀錄

## 2026-05-04 Gate P0-H 首次合體

- [ ] Go2 接收 cmd_vel → 移動：OK / FAIL
- [ ] Obstacle pause → resume：OK / FAIL
- [ ] Emergency hotkey q：OK / FAIL
- [ ] Reset r：OK / FAIL
- [ ] 到達 B 點 TTS「已到達目的地」：OK / FAIL

備註：...
```

- [ ] **Step 8: Commit（結果記錄）**

```bash
git add docs/mission/demo-script-p0.md
git commit -m "docs(demo): 2026-05-04 Gate P0-H Go2 合體首次試跑紀錄"
```

---

## Task 14: Home 排練 5/5 KPI（Gate P0-I — 5/6 P0 cutoff）

**目標**：5 次完整劇本 E，目標 4/5 成功（GO），記錄每次結果。

**Files:**
- Modify: `docs/mission/demo-script-p0.md`

- [ ] **Step 1: 準備場地**

- 客廳清出 3-4m 直線
- A 點（起點）、B 點（終點）用膠帶貼標記
- 準備紙箱 1 個當靜態障礙

- [ ] **Step 2: 跑 5 次劇本 E**

每次記錄：

| Run | 到達 B | 反應時間 | 續行時間 | 撞擊 | Emergency | TTS | Verdict |
|:---:|:----:|:------:|:------:|:----:|:--------:|:---:|:------:|
| 1 | ✅/❌ | ?s | ?s | Y/N | Y/N | OK/FAIL | PASS/FAIL |
| 2 | ... | | | | | | |
| 3 | ... | | | | | | |
| 4 | ... | | | | | | |
| 5 | ... | | | | | | |

PASS 定義：到達 B 誤差 <30cm + 反應 <1.5s + 續行 <4s + 無撞擊 + 無 emergency 觸發。

- [ ] **Step 3: 判定**

- 4-5 PASS = **GO**（進 5/7 Stretch C）
- 3 PASS = **YELLOW**（不做 C，全力補 P0）
- ≤2 PASS = **NO-GO**（降級 Demo 改錄影 + 純反應式停）

- [ ] **Step 4: 更新 demo-script-p0.md**

寫入 KPI 結果 + 判定。

- [ ] **Step 5: Commit**

```bash
git add docs/mission/demo-script-p0.md
git commit -m "docs(demo): 2026-05-06 Gate P0-I 家中排練 KPI — [GO/YELLOW/NO-GO]"
```

---

## Task 15: Studio Emergency 按鈕（PR #6，雨桐負責）

**目標**：PawAI Studio 前端紅色大按鈕，呼叫 ROS2 service。

**Files:**
- Create: `pawai-studio/backend/routers/safety.py`
- Create: `pawai-studio/frontend/components/EmergencyButton.tsx`
- Modify: `pawai-studio/backend/app.py`（掛 router）

- [ ] **Step 1: 寫 FastAPI router**

```python
# pawai-studio/backend/routers/safety.py
from fastapi import APIRouter, HTTPException
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

router = APIRouter(prefix="/safety", tags=["safety"])

_node = None  # 全域 rclpy node（backend init 時建立）


def init_node(node: Node):
    global _node
    _node = node


async def _call_trigger(service_name: str):
    if _node is None:
        raise HTTPException(500, "ROS node not initialized")
    cli = _node.create_client(Trigger, service_name)
    if not cli.wait_for_service(timeout_sec=2.0):
        raise HTTPException(503, f"Service {service_name} unavailable")
    future = cli.call_async(Trigger.Request())
    rclpy.spin_until_future_complete(_node, future, timeout_sec=2.0)
    if future.result() is None:
        raise HTTPException(504, "Service call timed out")
    return {"success": future.result().success, "message": future.result().message}


@router.post("/trigger")
async def trigger_emergency():
    return await _call_trigger("/pawai/safety/trigger_emergency")


@router.post("/reset")
async def reset_emergency():
    return await _call_trigger("/pawai/safety/reset_emergency")
```

- [ ] **Step 2: 掛進 `pawai-studio/backend/app.py`**

```python
# 在 FastAPI app 建立後：
from .routers import safety
safety.init_node(ros_node)  # ros_node = backend init 時建立的 rclpy node
app.include_router(safety.router)
```

- [ ] **Step 3: 寫前端 EmergencyButton.tsx**

```tsx
// pawai-studio/frontend/components/EmergencyButton.tsx
"use client";

import { useState } from "react";

export function EmergencyButton() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"normal" | "latched">("normal");

  const call = async (action: "trigger" | "reset") => {
    setLoading(true);
    try {
      const res = await fetch(`/api/safety/${action}`, { method: "POST" });
      const data = await res.json();
      if (action === "trigger" && data.success) setStatus("latched");
      if (action === "reset" && data.success) setStatus("normal");
    } catch (e) {
      alert(`Service call failed: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-3 p-4 border rounded">
      <button
        onClick={() => call("trigger")}
        disabled={loading || status === "latched"}
        className="w-32 h-32 rounded-full bg-red-600 text-white text-xl font-bold
                   hover:bg-red-700 disabled:bg-gray-400 shadow-lg"
      >
        {status === "latched" ? "LATCHED" : "EMERGENCY"}
      </button>
      <button
        onClick={() => call("reset")}
        disabled={loading || status === "normal"}
        className="px-6 py-2 rounded bg-green-600 text-white hover:bg-green-700
                   disabled:bg-gray-400"
      >
        RESET
      </button>
      <div className="text-sm text-gray-600">
        Status: <span className={status === "latched" ? "text-red-600 font-bold" : "text-green-600"}>
          {status.toUpperCase()}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 加進 Studio dashboard**

在 `pawai-studio/frontend/app/studio/page.tsx` 或主 dashboard 加入：
```tsx
import { EmergencyButton } from "@/components/EmergencyButton";

// 在 dashboard grid 某處加：
<EmergencyButton />
```

- [ ] **Step 5: 本機測試**

```bash
cd pawai-studio
bash start.sh
# 瀏覽 http://localhost:3000/studio
# 確認紅色按鈕顯示
# 前提：ROS2 environment 要有 executive_node 跑著
```

- [ ] **Step 6: Commit**

```bash
git add pawai-studio/backend/routers/safety.py \
        pawai-studio/frontend/components/EmergencyButton.tsx \
        pawai-studio/backend/app.py \
        pawai-studio/frontend/app/studio/page.tsx  # 若有改
git commit -m "feat(studio): Emergency Button + /safety/{trigger,reset} endpoint"
```

---

## Task 16: Docs 狀態卡更新

**Files:**
- Modify: `docs/mission/README.md`
- Modify: `docs/navigation/legacy-readme-from-導航避障.md`

- [ ] **Step 1: 更新 `docs/navigation/legacy-readme-from-導航避障.md` 狀態卡**

- 原 "Status: D435 停用 / 外接 LiDAR 評估中" → "Status: **RPLIDAR A2M12 已驗證，P0 劇本式導航開發中**"
- 「架構決策（2026-04-01 最終判定）」章節加註：「**Supersedes: 本章節由 2026-04-24 P0 設計翻案 — Full SLAM / Nav2 路線從『永久關閉』改為 P0 主線，基於 RPLIDAR A2M12 實測 10.5Hz > 7Hz SLAM 門檻**」
- 更新「完成度」欄位

- [ ] **Step 2: 更新 `docs/mission/README.md` P0 定義**

在 demo 場景章節加：
```markdown
### 導航避障（P0 主線，2026-04-24 新增）

劇本式 A→B 自主巡邏 + 停障 + 續行：
- 預建 4-6m 小會議室 2D 地圖
- Go2 0.2 m/s 走 3-4m 直線
- 遇人/紙箱停下，播「前方有障礙，請讓路」
- 障礙移開 3 秒續行
- 到達 B 播「已到達目的地」

詳細設計見 [P0 Nav Obstacle Avoidance Design](../archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md)
```

- [ ] **Step 3: Commit**

```bash
git add docs/mission/README.md docs/navigation/legacy-readme-from-導航避障.md
git commit -m "docs: 狀態卡同步 — P0 導航避障翻案，LiDAR 主線"
```

---

## Self-Review

**Spec coverage check**（逐章對照 spec → task）：

| Spec 章節 | Task | OK |
|----------|------|:--:|
| §1 目標與範圍 + KPI | Task 14 | ✅ |
| §2 三層架構整合 | Task 10, 11 | ✅ |
| §3.1 Emergency FSM | Task 6 | ✅ |
| §3.2 Service 介面 | Task 10 step 4 | ✅ |
| §3.3 Obstacle FSM | Task 5 | ✅ |
| §3.4 safety_tts 架構規則 | Task 8 | ✅ |
| §3.5 twist_mux priority | Task 2 step 6 | ✅ |
| §3.6 Pre-action validation | Task 7（skeleton）| ⚠️ preconditions 實際串接可在 patrol skill contract dispatch 完成 |
| §4.1 patrol_route Skill Contract | Task 7 | ✅ |
| §4.2 Nav2 ActionClient | Task 7 | ⚠️ 骨架已有，完整 send_goal_async 可在 Task 13 實機驗證時補 |
| §4.3 Map 載入 | Task 1, 13 | ✅ |
| §4.4 Brain 觸發 | Task 13 step 4（手動發 goal 代替 Brain）| ⚠️ P0 可手動發，之後加 Brain dispatch |
| §4.5 Obstacle Timeline | Task 10 step 5-6 | ✅ |
| §4.6 降級路徑 | Task 10 step 5（obstacle abort）| ⚠️ AMCL 漂移 / odom 無 progress 偵測 P1 再加 |
| §5 硬規則 R1-R10 | 分散在各 task | ✅ |
| §6.2 Gate P0-A~J | Task 1, 3, 4, 5-11, 12, 13, 14 | ✅ |
| §7 風險矩陣 | Task 13 step 1（穩定電源）+ Task 14 KPI | ✅ |
| §8 時程 | Task 截止日期對齊 | ✅ |
| §9.1-§9.5 實作清單 | File structure + 16 tasks | ✅ |
| §10 `/state/pawai_brain` 擴充 | ⚠️ 未明確涵蓋 | 需新增 task 補 publish /state/pawai_brain 擴充欄位 |
| §11 Demo 當天 checklist | Task 13 step 1 | ✅ |

**Gap fix — 新增 Task 17**：

---

## Task 17: `/state/pawai_brain` 狀態擴充（spec §10）

**目標**：Executive 發佈擴充後的 `/state/pawai_brain`，含 safety_flags / patrol_progress。

**Files:**
- Modify: `interaction_executive/interaction_executive/interaction_executive_node.py`

- [ ] **Step 1: 在 executive 加 `_publish_pawai_brain_state` method**

```python
def _publish_pawai_brain_state(self):
    state_dict = {
        "timestamp": time.time(),
        "executive_state": self._patrol.state.value if self._patrol.state != PatrolState.IDLE
                           else "emergency" if self._safety.emergency.is_latched()
                           else "idle",
        "active_skill": "patrol_route" if self._patrol.state in (
            PatrolState.NAVIGATING, PatrolState.PAUSED
        ) else None,
        "patrol_progress": {
            "current_waypoint": 0,
            "total_waypoints": 1,
            "distance_to_goal_m": None,  # optional, P0 可 null
            "eta_sec": None,              # optional
        },
        "safety_flags": {
            "emergency_latched": self._safety.emergency.is_latched(),
            "obstacle_active": self._safety.obstacle.is_blocking(),
            "obstacle_direction_deg": None,  # TODO: from last obstacle event
            "tts_playing": False,            # TODO: track TTS state
            "tts_source": None,
        },
        "nav_stack_ready": True,     # TODO: check /amcl_pose freshness
        "scan_heartbeat_ok": True,   # TODO: check /scan freshness
        "amcl_converged": True,      # TODO: covariance check
    }
    msg = String()
    msg.data = json.dumps(state_dict)
    # 使用現有 self._pub_status 或建新 publisher
    # 建議：新建 /state/pawai_brain publisher
```

- [ ] **Step 2: 加 publisher + 2Hz timer**

在 `__init__` 加：
```python
self._pub_pawai_brain = self.create_publisher(String, "/state/pawai_brain", QOS_STATE)
self._pawai_brain_timer = self.create_timer(0.5, self._publish_pawai_brain_state)
```

- [ ] **Step 3: Build + 驗證**

```bash
colcon build --packages-select interaction_executive
source install/setup.zsh
ros2 run interaction_executive interaction_executive_node &
sleep 3
ros2 topic echo /state/pawai_brain --once
pkill -f interaction_executive_node
```

Expected: JSON 含 safety_flags / patrol_progress 全部欄位。

- [ ] **Step 4: Commit**

```bash
git add interaction_executive/interaction_executive/interaction_executive_node.py
git commit -m "feat(observability): /state/pawai_brain 擴充 safety_flags/patrol_progress（spec §10）"
```

---

## 最終交付

17 個 task 完成後：
- 12 新檔、7 改檔（含 demo-script-p0.md 於 Task 13 建立）
- 全部 unit tests pass
- Gate P0-A~J 全通過
- 5/6 家中排練 KPI 4/5
- 5/13 學校場地重建地圖 + 現場排練

**優先順序（硬截止優先）**：
1. Task 1, 2, 3 → 4/28 前
2. Task 4 → 4/29（P0-D.5）
3. Task 5, 7, 11 → 4/30 obstacle stack 完成
4. Task 6, 9, 10 → **5/1 emergency hard cutoff**
5. Task 8 → 5/2
6. Task 15 → 5/3（雨桐）
7. Task 12, 13 → 5/4 Go2 合體
8. Task 14 → 5/5-5/6 KPI
9. Task 16, 17 → 與其他 task 平行
