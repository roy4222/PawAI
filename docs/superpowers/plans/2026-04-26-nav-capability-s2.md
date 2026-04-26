# nav_capability S2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把導航避障封裝成可被互動 / 守護任務呼叫的平台模組（`nav_capability`），暴露 4 actions + 3 services + 狀態廣播，並升級 twist_mux 為 4 層讓 Nav2 與 reactive_stop 同跑。

**Architecture:** 新建 `nav_capability` ROS2 pkg 包裝 Nav2 NavigateToPose 為高階 API；twist_mux 升級為 emergency(255)/obstacle(200)/teleop(100)/nav2(10) + Bool lock；reactive_stop 改發 `/cmd_vel_obstacle`；Nav2 cmd_vel remap 到 `/cmd_vel_nav`。Spec: `docs/superpowers/specs/2026-04-26-nav-capability-s2-design.md`。

**Tech Stack:** ROS2 Humble, Python 3.10, pytest, twist_mux, Nav2 (DWB+AMCL), `nav2_simple_commander`, `geometry_msgs`, `std_srvs`。

---

## File Structure

### 新建檔案

**`go2_interfaces/`（既有 pkg，加 schema）**
- `action/GotoRelative.action`
- `action/GotoNamed.action`
- `action/RunRoute.action`
- `action/LogPose.action`
- `srv/Cancel.srv`

**`nav_capability/`（新 ROS2 pkg, ament_python）**
- `package.xml`
- `setup.py`
- `setup.cfg`
- `resource/nav_capability`
- `nav_capability/__init__.py`
- `nav_capability/lib/__init__.py`
- `nav_capability/lib/relative_goal_math.py`
- `nav_capability/lib/standoff_math.py`
- `nav_capability/lib/route_validator.py`
- `nav_capability/lib/named_pose_store.py`
- `nav_capability/lib/route_fsm.py`
- `nav_capability/nav_action_server_node.py`（goto_relative + goto_named action）
- `nav_capability/route_runner_node.py`（run_route action + pause/resume/cancel services + waypoint_reached event）
- `nav_capability/log_pose_node.py`
- `nav_capability/state_broadcaster_node.py`
- `nav_capability/launch/nav_capability.launch.py`
- `nav_capability/config/named_poses/sample.json`
- `nav_capability/config/routes/sample.json`
- `nav_capability/test/__init__.py`
- `nav_capability/test/test_relative_goal_math.py`
- `nav_capability/test/test_standoff_math.py`
- `nav_capability/test/test_route_validator.py`
- `nav_capability/test/test_named_pose_store.py`
- `nav_capability/test/test_route_fsm.py`
- `nav_capability/test/integration/test_mux_priority.py`
- `nav_capability/test/integration/test_emergency_lock.py`

### 修改檔案

- `go2_robot_sdk/config/twist_mux.yaml` — 升級 4 層 + lock
- `go2_robot_sdk/launch/robot.launch.py` — Nav2 cmd_vel remap
- `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py` — 改 publisher topic + 加 `enable_nav_pause` param
- `go2_interfaces/CMakeLists.txt` — 加 actions + Cancel.srv
- `scripts/send_relative_goal.py` — 改 action client
- `scripts/start_nav2_amcl_demo_tmux.sh` — 加 nav_capability window
- `docs/導航避障/README.md` — Status 更新

### 規約
- 每個 task 完成跑「**該 task 對應的最小驗證**」（不是全部 unit test）
- 每個 Phase 完成跑「**該 Phase 全部累積測試**」作為 Phase gate
- commit message 格式：`feat(nav): <task>` / `test(nav): <task>` / `chore(nav): <task>`
- Phase 順序硬性：Phase 0 → Phase 1 → Phase 1.5 → Phase 2 → ...（不可跳過）
- Phase 0 (scaffold) 必須先做，否則 Phase 1 的 emergency_stop.py / mux test 沒地方放
- Phase 1.5 (Nav2 launch wrapper) 必須在 Phase 1 完成後做，因為 Nav2 cmd_vel 流向是 controller → smoother → /cmd_vel，不能用單純 launch_arg 改

---

## Phase 0 — `nav_capability` minimal scaffold

**Goal**: 在進 Phase 1 之前，先讓 `nav_capability` package 結構存在（package.xml / setup.py / resource / __init__.py），這樣 Phase 1 的 `nav_capability/scripts/emergency_stop.py` 與 `nav_capability/test/integration/test_mux_priority.py` 才有合法歸宿。**不寫任何 node、不解開任何 entry_points。**

### Task 0.1 — 建立 minimal pkg files

**Files:**
- Create: `nav_capability/package.xml`
- Create: `nav_capability/setup.py`
- Create: `nav_capability/setup.cfg`
- Create: `nav_capability/resource/nav_capability` (empty marker)
- Create: `nav_capability/nav_capability/__init__.py` (empty)
- Create: `nav_capability/nav_capability/lib/__init__.py` (empty)
- Create: `nav_capability/scripts/` (空目錄，等 Phase 1.4 放 emergency_stop.py)
- Create: `nav_capability/test/__init__.py`
- Create: `nav_capability/test/integration/__init__.py`

- [ ] **Step 1: 建目錄結構**

```bash
cd /home/roy422/newLife/elder_and_dog
mkdir -p nav_capability/nav_capability/lib
mkdir -p nav_capability/resource nav_capability/launch nav_capability/scripts
mkdir -p nav_capability/config/named_poses nav_capability/config/routes
mkdir -p nav_capability/test/integration
touch nav_capability/resource/nav_capability
touch nav_capability/nav_capability/__init__.py
touch nav_capability/nav_capability/lib/__init__.py
touch nav_capability/test/__init__.py
touch nav_capability/test/integration/__init__.py
```

- [ ] **Step 2: 寫 `nav_capability/package.xml`**

```xml
<?xml version="1.0"?>
<package format="3">
  <name>nav_capability</name>
  <version>0.1.0</version>
  <description>Nav capability platform: high-level navigation actions, route runner, pose logger.</description>
  <maintainer email="roy422roy@gmail.com">roy422</maintainer>
  <license>MIT</license>

  <depend>rclpy</depend>
  <depend>geometry_msgs</depend>
  <depend>std_msgs</depend>
  <depend>std_srvs</depend>
  <depend>nav_msgs</depend>
  <depend>nav2_msgs</depend>
  <depend>nav2_simple_commander</depend>
  <depend>tf2_ros</depend>
  <depend>tf_transformations</depend>
  <depend>go2_interfaces</depend>

  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <test_depend>ament_pep257</test_depend>
  <test_depend>python3-pytest</test_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

- [ ] **Step 3: 寫 `nav_capability/setup.py`（entry_points 全部註解）**

```python
from setuptools import setup, find_packages
import os
from glob import glob

package_name = "nav_capability"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config", "named_poses"), glob("config/named_poses/*.json")),
        (os.path.join("share", package_name, "config", "routes"), glob("config/routes/*.json")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="roy422",
    maintainer_email="roy422roy@gmail.com",
    description="Nav capability platform layer.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            # 全部註解，等對應 node 在 Phase 4-7 寫完再解開
            # "nav_action_server_node = nav_capability.nav_action_server_node:main",
            # "route_runner_node = nav_capability.route_runner_node:main",
            # "log_pose_node = nav_capability.log_pose_node:main",
            # "state_broadcaster_node = nav_capability.state_broadcaster_node:main",
        ],
    },
)
```

- [ ] **Step 4: 寫 `nav_capability/setup.cfg`**

```ini
[develop]
script_dir=$base/lib/nav_capability
[install]
install_scripts=$base/lib/nav_capability
```

- [ ] **Step 5: colcon build 確認 pkg 認得**

```bash
colcon build --packages-select nav_capability 2>&1 | tail -5
```

Expected: `Finished <<< nav_capability` (no error)。

- [ ] **Step 6: Stage + commit**

Stage: `nav_capability/`
Commit message: `feat(nav): scaffold nav_capability minimal pkg (Phase 0 — pre Phase 1)`

---

## Phase 0 完成檢查

- [ ] Task 0.1 — minimal scaffold ✅

✅ Phase 0 通過 → 進 Phase 1。

---

## Phase 1 — 地基層：cmd_vel 路由（用戶硬性指定順序）

**Goal**: twist_mux 升 4 層 + reactive_stop publisher 改 + emergency CLI + mux fake-publisher 驗證。完成後 reactive_stop 跟 Nav2 可同跑（透過 mux）。

> **重要**：Nav2 的 `/cmd_vel` 出口處理留到 **Phase 1.5**（單獨 task）— 因為 Humble navigation_launch.py 沒有 `cmd_vel_topic` launch_arg，且最終出口在 `velocity_smoother` 不是 controller，必須複製 launch wrapper 才能改。

### Task 1.1 — twist_mux 4 層 yaml 升級

**Files:**
- Modify: `go2_robot_sdk/config/twist_mux.yaml`
- Test: `nav_capability/test/integration/test_mux_priority.py`（先建空 placeholder，1.5 完整實作）

- [ ] **Step 1: 讀現有 yaml 確認格式**

```bash
cat go2_robot_sdk/config/twist_mux.yaml
```

Expected output 應包含 `joy` 和 `navigation` 兩個 dict-style topic（既有 v3 yaml format）。

- [ ] **Step 2: 升級 yaml 為 4 層 + lock**

替換 `/twist_mux:` 區塊（保留 `/go2_teleop_node:` 區塊不動）：

```yaml
/twist_mux:
  ros__parameters:
    topics:
      emergency:
        topic   : /cmd_vel_emergency
        timeout : 0.5
        priority: 255
      obstacle:
        topic   : /cmd_vel_obstacle
        timeout : 0.5
        priority: 200
      teleop:
        topic   : /cmd_vel_joy
        timeout : 0.5
        priority: 100
      nav2:
        topic   : /cmd_vel_nav
        timeout : 0.5
        priority: 10
    locks:
      e_stop_lock:
        topic   : /lock/emergency
        timeout : 0.0
        priority: 255
```

- [ ] **Step 3: yaml 語法驗證**

```bash
python3 -c "import yaml; yaml.safe_load(open('go2_robot_sdk/config/twist_mux.yaml'))" && echo "yaml ok"
```

Expected: `yaml ok`

- [ ] **Step 4: Commit**

```bash
git add go2_robot_sdk/config/twist_mux.yaml
git commit -m "feat(nav): upgrade twist_mux to 4-layer priority (emergency/obstacle/teleop/nav2) + Bool lock"
```

---

### Task 1.2 — Nav2 cmd_vel routing（**移到 Phase 1.5**）

> **此 task 從 Phase 1 移除**。原本想用 launch_arg 改 Nav2 cmd_vel，但 Humble 的 `navigation_launch.py` **沒有 `cmd_vel_topic` launch_arg**，且最終出口在 `velocity_smoother`（line 182-183）不是 controller。要改 Nav2 final cmd_vel output **必須複製 wrapper launch**，工作量大、風險高，獨立成 Phase 1.5。
>
> Phase 1 內 reactive_stop / mux / emergency 仍可獨立完成測試（reactive_stop 的 `/cmd_vel_obstacle` 不受 Nav2 影響）。

跳到 [Task 1.3](#task-13)。

---

### Task 1.3 — `reactive_stop_node` 改 publisher 到 `/cmd_vel_obstacle` + 加 `enable_nav_pause` param

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py:26-52`
- Test: `go2_robot_sdk/test/test_reactive_stop_node.py`（既有，加 regression）

- [ ] **Step 1: Write regression test 確認 publisher topic 改了**

加到 `go2_robot_sdk/test/test_reactive_stop_node.py` 末尾：

```python
def test_publisher_topic_is_cmd_vel_obstacle():
    """Reactive stop must publish to /cmd_vel_obstacle (mux priority 200), not /cmd_vel."""
    import rclpy
    from go2_robot_sdk.reactive_stop_node import ReactiveStopNode

    rclpy.init()
    try:
        node = ReactiveStopNode()
        topic_names = [t for t, _ in node.get_topic_names_and_types()]
        # publisher should expose /cmd_vel_obstacle
        publisher_topics = [
            info.topic_name for info in node.get_publishers_info_by_topic("/cmd_vel_obstacle")
        ]
        # Test via internal attribute (set in __init__)
        assert hasattr(node, "_cmd_pub")
        # Resolve publisher topic name
        resolved = node._cmd_pub.topic_name
        assert resolved.endswith("/cmd_vel_obstacle"), f"got {resolved}"
        node.destroy_node()
    finally:
        rclpy.shutdown()


def test_enable_nav_pause_param_default_false():
    """enable_nav_pause must default to false (reactive runs alone safely)."""
    import rclpy
    from go2_robot_sdk.reactive_stop_node import ReactiveStopNode

    rclpy.init()
    try:
        node = ReactiveStopNode()
        param = node.get_parameter("enable_nav_pause")
        assert param.value is False
        node.destroy_node()
    finally:
        rclpy.shutdown()
```

- [ ] **Step 2: Run tests verify they fail**

```bash
cd /home/roy422/newLife/elder_and_dog
colcon build --packages-select go2_robot_sdk 2>&1 | tail -5
source install/setup.zsh
python3 -m pytest go2_robot_sdk/test/test_reactive_stop_node.py::test_publisher_topic_is_cmd_vel_obstacle -v
```

Expected: FAIL — `_cmd_pub.topic_name` ends in `/cmd_vel`, not `/cmd_vel_obstacle`.

- [ ] **Step 3: 修改 reactive_stop_node.py**

修改 `__init__` 中 publisher 初始化（line ~52）：

```python
        # OLD:
        # self._cmd_pub = self.create_publisher(Twist, "/cmd_vel", QOS_CMD)
        # NEW:
        self.declare_parameter("cmd_vel_topic", "/cmd_vel_obstacle")
        self.declare_parameter("enable_nav_pause", False)
        cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
        self._cmd_pub = self.create_publisher(Twist, cmd_vel_topic, QOS_CMD)
        self._enable_nav_pause = self.get_parameter("enable_nav_pause").value
```

- [ ] **Step 4: Run tests verify pass**

```bash
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
python3 -m pytest go2_robot_sdk/test/test_reactive_stop_node.py -v
```

Expected: 全部 19 cases pass（既有 17 + 新 2）。

- [ ] **Step 5: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py go2_robot_sdk/test/test_reactive_stop_node.py
git commit -m "feat(nav): reactive_stop publishes /cmd_vel_obstacle + add enable_nav_pause param"
```

---

### Task 1.4 — Emergency lock topic publisher（CLI helper）

**Files:**
- Create: `nav_capability/scripts/emergency_stop.py`

> 註：Emergency 觸發源完整實作（joy button 等）列入 spec §14 T2，本 task 只做 CLI helper 用於測試。

- [ ] **Step 1: Write CLI helper**

```python
#!/usr/bin/env python3
"""Emergency stop CLI helper.

Publishes:
  /cmd_vel_emergency: geometry_msgs/Twist (zero velocity)
  /lock/emergency: std_msgs/Bool (true to engage, false to release)

Usage:
  python3 emergency_stop.py engage    # lock 鎖死所有 cmd_vel
  python3 emergency_stop.py release   # 解鎖
"""
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool


class EmergencyStopCLI(Node):
    def __init__(self, engage: bool):
        super().__init__("emergency_stop_cli")
        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel_emergency", 10)
        self._lock_pub = self.create_publisher(Bool, "/lock/emergency", 10)
        # Latch by publishing for 2s
        end = time.time() + 2.0
        while time.time() < end and rclpy.ok():
            self._cmd_pub.publish(Twist())  # zero velocity
            self._lock_pub.publish(Bool(data=engage))
            rclpy.spin_once(self, timeout_sec=0.05)
            time.sleep(0.1)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("engage", "release"):
        print(__doc__)
        sys.exit(1)
    rclpy.init()
    EmergencyStopCLI(engage=(sys.argv[1] == "engage"))
    rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

```bash
mkdir -p nav_capability/scripts
chmod +x nav_capability/scripts/emergency_stop.py
```

- [ ] **Step 3: Smoke test (no Go2 needed)**

```bash
# Terminal A:
ros2 topic echo /lock/emergency &

# Terminal B:
python3 nav_capability/scripts/emergency_stop.py engage
```

Expected: Terminal A 顯示 `data: true` 持續 2s。

- [ ] **Step 4: Commit**

```bash
git add nav_capability/scripts/emergency_stop.py
git commit -m "feat(nav): add emergency_stop CLI helper publishing /cmd_vel_emergency + /lock/emergency"
```

---

### Task 1.5 — Mux priority fake publisher integration test

**Files:**
- Create: `nav_capability/test/integration/test_mux_priority.py`
- Create: `nav_capability/test/integration/__init__.py`

- [ ] **Step 1: Write integration test**

```python
"""Verify twist_mux 4-layer priority routing.

Strategy: 啟動 twist_mux + 4 個 fake publishers，分別發到 emergency/obstacle/teleop/nav2，
echo /cmd_vel mux output 確認 highest priority active source 勝出。
"""
import threading
import time

import pytest
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool


class FakePublisher(Node):
    """Publishes a fixed Twist at 10Hz to a target topic."""

    def __init__(self, name: str, topic: str, vx: float):
        super().__init__(name)
        self._pub = self.create_publisher(Twist, topic, 10)
        self._vx = vx
        self._timer = self.create_timer(0.1, self._tick)

    def _tick(self):
        msg = Twist()
        msg.linear.x = self._vx
        self._pub.publish(msg)


class CmdVelSink(Node):
    """Subscribe to /cmd_vel mux output, record latest linear.x."""

    def __init__(self):
        super().__init__("cmd_vel_sink")
        self.latest_vx = None
        self.create_subscription(Twist, "/cmd_vel", self._cb, 10)

    def _cb(self, msg: Twist):
        self.latest_vx = msg.linear.x


@pytest.fixture
def ros_context():
    rclpy.init()
    yield
    rclpy.shutdown()


def _spin_briefly(nodes, secs: float):
    end = time.time() + secs
    while time.time() < end:
        for n in nodes:
            rclpy.spin_once(n, timeout_sec=0.01)


def test_nav2_alone_passes_through(ros_context):
    """Only nav2 source active → mux output == nav2 vx (0.30)."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    sink = CmdVelSink()
    _spin_briefly([nav, sink], 1.5)
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx - 0.30) < 0.01
    nav.destroy_node()
    sink.destroy_node()


def test_obstacle_overrides_nav2(ros_context):
    """obstacle (priority 200) > nav2 (priority 10) → mux output == obstacle vx (0.0)."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    obs = FakePublisher("fake_obs", "/cmd_vel_obstacle", 0.0)
    sink = CmdVelSink()
    _spin_briefly([nav, obs, sink], 1.5)
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx) < 0.01  # obstacle's 0.0 wins
    nav.destroy_node()
    obs.destroy_node()
    sink.destroy_node()


def test_teleop_overrides_nav2_but_not_obstacle(ros_context):
    """teleop (100) > nav2 (10) but < obstacle (200)."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    teleop = FakePublisher("fake_teleop", "/cmd_vel_joy", 0.50)
    sink = CmdVelSink()
    _spin_briefly([nav, teleop, sink], 1.5)
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx - 0.50) < 0.01
    nav.destroy_node()
    teleop.destroy_node()
    sink.destroy_node()


def test_emergency_overrides_all(ros_context):
    """emergency (255) is highest, beats all."""
    nav = FakePublisher("fake_nav", "/cmd_vel_nav", 0.30)
    teleop = FakePublisher("fake_teleop", "/cmd_vel_joy", 0.50)
    obs = FakePublisher("fake_obs", "/cmd_vel_obstacle", 0.20)
    emer = FakePublisher("fake_emer", "/cmd_vel_emergency", 0.0)
    sink = CmdVelSink()
    _spin_briefly([nav, teleop, obs, emer, sink], 1.5)
    assert sink.latest_vx is not None
    assert abs(sink.latest_vx) < 0.01
    for n in [nav, teleop, obs, emer, sink]:
        n.destroy_node()
```

- [ ] **Step 2: Build empty integration dir + create __init__**

```bash
mkdir -p nav_capability/test/integration
touch nav_capability/test/integration/__init__.py
```

- [ ] **Step 3: Run test (要求 twist_mux node 已起)**

> ⚠️ `twist_mux_launch.py` 預設：
> - `cmd_vel_out` = `'twist_mux/cmd_vel'`（**不是 `/cmd_vel`**），需明確覆寫
> - `config_topics` 與 `config_locks` 是兩個獨立 launch args，必須**都傳同一份 yaml**（我們的 yaml 同時包含 `topics:` 與 `locks:` 兩段）
> 否則：mux output 不在 `/cmd_vel`、emergency lock 不會生效。

```bash
# Terminal A: 啟動 twist_mux，明確指定 config_topics + config_locks + cmd_vel_out
ros2 launch twist_mux twist_mux_launch.py \
  config_topics:=$(pwd)/go2_robot_sdk/config/twist_mux.yaml \
  config_locks:=$(pwd)/go2_robot_sdk/config/twist_mux.yaml \
  cmd_vel_out:=/cmd_vel &
TM_PID=$!
sleep 3

# 確認 mux 起來
ros2 node list | grep twist_mux
ros2 topic list | grep -E "/cmd_vel$"

# Terminal B:
python3 -m pytest nav_capability/test/integration/test_mux_priority.py -v

# 收尾:
kill $TM_PID
```

Expected: 4 cases pass，且 `ros2 topic list` 出現 `/cmd_vel`（mux output）。

- [ ] **Step 4: Commit**

```bash
git add nav_capability/test/integration/
git commit -m "test(nav): mux 4-layer priority integration tests (4 cases pass)"
```

---

## Phase 1 完成檢查

- [ ] Task 1.1 — twist_mux yaml 升級 ✅
- [ ] Task 1.2 — Nav2 cmd_vel routing（已移到 Phase 1.5）⏭️
- [ ] Task 1.3 — reactive_stop publisher 改 + enable_nav_pause param ✅
- [ ] Task 1.4 — emergency_stop.py CLI ✅
- [ ] Task 1.5 — mux priority 4 cases pass ✅

✅ Phase 1 通過 → 進 Phase 1.5（Nav2 launch wrapper）。
❌ 任一 task 失敗 → 修完才能繼續。

**Phase 1 對應 KPI**：K8（mux 4 層優先級）部分達成（fake publisher 級）。實機 K7（emergency lock）+ K8 整合留 Phase 10。

---

## Phase 1.5 — Nav2 launch wrapper（cmd_vel routing 真正落地）

**Goal**: 解決 Phase 1.2 留下的 Nav2 final cmd_vel 出口問題。複製 `navigation_launch.py` 為 `nav_capability/launch/navigation_remap.launch.py`，把 `velocity_smoother` 的 output `cmd_vel_smoothed → cmd_vel` 改成 `cmd_vel_smoothed → cmd_vel_nav`，同時把 controller 內部 publish 改用一個獨立中間 topic 避免衝突。

### 背景：為何 Phase 1 launch_arg 方案行不通

實際讀 `/opt/ros/humble/share/nav2_bringup/launch/navigation_launch.py` 證實：

| Line | 元件 | remap |
|------|------|-------|
| 122 | `controller_server` | `('cmd_vel', 'cmd_vel_nav')` — controller publishes 到 `cmd_vel_nav`（中間 topic）|
| 182-183 | `velocity_smoother` | `('cmd_vel', 'cmd_vel_nav')` 訂閱 + `('cmd_vel_smoothed', 'cmd_vel')` publish — 從 `cmd_vel_nav` 讀進，平滑後 publish 到 `/cmd_vel` |
| 205 | `controller_server` (composable) | 同 line 122 |
| 241-242 | `velocity_smoother` (composable) | 同 line 182-183 |

**關鍵事實**：Nav2 final cmd_vel 出口是 **velocity_smoother 的 publish**（`/cmd_vel`），不是 controller_server。也沒有 `cmd_vel_topic` launch_arg。

### Task 1.5.1 — 建立 navigation_remap.launch.py wrapper

**Files:**
- Create: `nav_capability/launch/navigation_remap.launch.py`

- [ ] **Step 1: 複製 navigation_launch.py**

```bash
cp /opt/ros/humble/share/nav2_bringup/launch/navigation_launch.py \
   nav_capability/launch/navigation_remap.launch.py
```

- [ ] **Step 2: 改 4 處 remap（避開 controller / smoother 中間 topic 名稱衝突）**

打開 `nav_capability/launch/navigation_remap.launch.py`，改下面 4 處：

**修改 1**（line ~122，非 composition controller）:

```python
# OLD:
remappings=remappings + [('cmd_vel', 'cmd_vel_nav')]),
# NEW:
remappings=remappings + [('cmd_vel', 'cmd_vel_unsmoothed')]),
```

**修改 2**（line ~182-183，非 composition smoother）:

```python
# OLD:
remappings=remappings +
        [('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', 'cmd_vel')]),
# NEW:
remappings=remappings +
        [('cmd_vel', 'cmd_vel_unsmoothed'), ('cmd_vel_smoothed', 'cmd_vel_nav')]),
```

**修改 3**（line ~205，composition controller）：同修改 1。

**修改 4**（line ~241-242，composition smoother）：同修改 2。

效果：
- `controller_server` publishes 到 `cmd_vel_unsmoothed`（內部中間 topic）
- `velocity_smoother` 讀 `cmd_vel_unsmoothed`、publishes 到 `cmd_vel_nav`（**最終 Nav2 出口，進 mux**）
- `cmd_vel_unsmoothed` 與 `cmd_vel_nav` 兩個 topic 不衝突
- velocity_smoother 功能完整保留（demo 內 acceleration limiting 仍生效）

- [ ] **Step 3: 在 setup.py 註冊 launch 檔**

`nav_capability/setup.py` 的 `data_files` 已有 `glob("launch/*.launch.py")`，無需修改。

- [ ] **Step 4: 修改 `go2_robot_sdk/launch/robot.launch.py` 改用 wrapper**

替換 line 524-542 的 Nav2 IncludeLaunchDescription：

```python
            # Nav2 (enabled when nav2=true AND mcp_mode=false)
            # 使用 nav_capability wrapper：把 final cmd_vel output 從 /cmd_vel 改到 /cmd_vel_nav
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    [
                        os.path.join(
                            get_package_share_directory("nav_capability"),
                            "launch",
                            "navigation_remap.launch.py",
                        )
                    ]
                ),
                condition=IfCondition(nav2_enabled),
                launch_arguments={
                        "params_file": self.config.config_paths["nav2"],
                        "use_sim_time": use_sim_time,
                        "autostart": with_autostart,
                    }.items(),
            ),
```

對 `localization_launch.py` 區塊不需改（AMCL 不發 cmd_vel）。

- [ ] **Step 5: build + smoke**

```bash
colcon build --packages-select nav_capability go2_robot_sdk
source install/setup.zsh
```

啟動 Nav2 stack（不接 Go2，dry mode）：

```bash
# 開新 terminal
ros2 launch nav_capability navigation_remap.launch.py \
  params_file:=$(pwd)/go2_robot_sdk/config/nav2_params.yaml &
NAV_PID=$!
sleep 10  # 等 lifecycle active

# 檢查 final cmd_vel 出口
ros2 node info /velocity_smoother | grep -i Publishers -A 5
# Expected: /cmd_vel_nav (被改了的 cmd_vel_smoothed remap 結果)

# 確認 controller publish 到 unsmoothed
ros2 node info /controller_server | grep -i Publishers -A 10
# Expected: /cmd_vel_unsmoothed

# 確認 /cmd_vel 不再有 nav publisher
ros2 topic info /cmd_vel | head -10
# Expected: 無 nav 相關 publisher（只剩 mux output）

kill $NAV_PID
```

- [ ] **Step 6: Stage + commit**

Stage: `nav_capability/launch/navigation_remap.launch.py`、`go2_robot_sdk/launch/robot.launch.py`
Commit message: `feat(nav): nav_capability wrapper launch — Nav2 final cmd_vel output remapped to /cmd_vel_nav (controller→unsmoothed→smoother→cmd_vel_nav)`

---

## Phase 1.5 完成檢查

- [ ] Task 1.5.1 — navigation_remap.launch.py + robot.launch.py 改用 wrapper ✅

✅ Phase 1.5 通過 → 進 Phase 2。

> 此時 cmd_vel 完整路徑：
> ```
> Nav2 controller → /cmd_vel_unsmoothed → velocity_smoother → /cmd_vel_nav
>                                                                 ↓
>                                                      twist_mux (priority 10)
>                                                                 ↓
>                                                      → /cmd_vel → go2_driver
> ```
> reactive_stop 走 `/cmd_vel_obstacle`（priority 200）可隨時覆寫。
> emergency 走 `/cmd_vel_emergency` + `/lock/emergency`（priority 255）覆寫所有。

---


## Phase 2 — `go2_interfaces` schema + sample JSON

**Goal**: 加 4 action schema + Cancel.srv 到 `go2_interfaces`（既有 CMake pkg，rosidl 友善），sample JSON 已有 Phase 0 scaffold 過後的目錄。

> Phase 0 已 scaffold `nav_capability` minimal pkg，本 phase 不再做 pkg scaffold，只做 interface schema 與 sample JSON。原 Task 2.1 (pkg scaffold) 移到 Phase 0。

### Task 2.1 — `nav_capability` pkg 骨架（**已移到 Phase 0**）

> 此 task 已被 Phase 0 Task 0.1 取代。Phase 2 從 Task 2.2（既有編號保留以維持後續引用穩定）開始。直接跳到 [Task 2.2](#task-22-加-4-個-actions--cancelsrv-到-go2_interfaces)。

**Files (already done in Phase 0):**
- Create: `nav_capability/package.xml`
- Create: `nav_capability/setup.py`
- Create: `nav_capability/setup.cfg`
- Create: `nav_capability/resource/nav_capability` (empty)
- Create: `nav_capability/nav_capability/__init__.py` (empty)
- Create: `nav_capability/nav_capability/lib/__init__.py` (empty)

- [x] **Steps 1-6 已在 Phase 0 Task 0.1 完成**（pkg scaffold + colcon build 通過）

---

### Task 2.2 — 加 4 個 actions + Cancel.srv 到 go2_interfaces

**Files:**
- Create: `go2_interfaces/action/GotoRelative.action`
- Create: `go2_interfaces/action/GotoNamed.action`
- Create: `go2_interfaces/action/RunRoute.action`
- Create: `go2_interfaces/action/LogPose.action`
- Create: `go2_interfaces/srv/Cancel.srv`
- Modify: `go2_interfaces/CMakeLists.txt`
- Modify: `go2_interfaces/package.xml`

- [ ] **Step 1: 建 action 目錄**

```bash
mkdir -p go2_interfaces/action
```

- [ ] **Step 2: 寫 `go2_interfaces/action/GotoRelative.action`**

```
# Goal
float32 distance
float32 yaw_offset
float32 max_speed
---
# Result
bool success
string message
float32 actual_distance
---
# Feedback
float32 progress
float32 distance_to_goal
```

- [ ] **Step 3: 寫 `go2_interfaces/action/GotoNamed.action`**

```
# Goal
string name
float32 standoff
bool align_yaw_to_target
float32 max_speed
---
# Result
bool success
string message
geometry_msgs/Pose final_pose
---
# Feedback
float32 progress
string current_state
```

- [ ] **Step 4: 寫 `go2_interfaces/action/RunRoute.action`**

```
# Goal
string route_id
bool loop
---
# Result
bool success
uint32 waypoints_completed
uint32 waypoints_total
string message
---
# Feedback
uint32 current_waypoint_index
string current_waypoint_id
string current_state
```

- [ ] **Step 5: 寫 `go2_interfaces/action/LogPose.action`**

```
# Goal
string name
string note
string log_target
string route_id
string task_type
---
# Result
bool success
string saved_path
geometry_msgs/Pose recorded_pose
```

- [ ] **Step 6: 寫 `go2_interfaces/srv/Cancel.srv`**

```
# Request
bool safe_stop
---
# Response
bool success
```

- [ ] **Step 7: 修改 `go2_interfaces/CMakeLists.txt`**

在 `find_package(rosidl_default_generators REQUIRED)` 後加：

```cmake
find_package(action_msgs REQUIRED)
```

替換 `rosidl_generate_interfaces` 區塊（保留所有既有 msg），在 `# Custom services` 區塊後加 actions：

```cmake
  # Custom services
  "srv/MoveForDuration.srv"
  "srv/Cancel.srv"

  # Custom actions (nav_capability)
  "action/GotoRelative.action"
  "action/GotoNamed.action"
  "action/RunRoute.action"
  "action/LogPose.action"
  DEPENDENCIES builtin_interfaces geometry_msgs action_msgs
```

- [ ] **Step 8: 修改 `go2_interfaces/package.xml` 加 action_msgs**

```xml
<depend>action_msgs</depend>
```

(放在既有 `<depend>geometry_msgs</depend>` 附近)

- [ ] **Step 9: colcon build**

```bash
colcon build --packages-select go2_interfaces 2>&1 | tail -15
```

Expected: 看到 `Generating .../GotoRelative.action`、`Cancel.srv` 等，build 通過。

- [ ] **Step 10: Verify 可 import**

```bash
source install/setup.zsh
python3 -c "from go2_interfaces.action import GotoRelative, GotoNamed, RunRoute, LogPose; from go2_interfaces.srv import Cancel; print('all schemas importable')"
```

Expected: `all schemas importable`

- [ ] **Step 11: Commit**

```bash
git add go2_interfaces/action/ go2_interfaces/srv/Cancel.srv go2_interfaces/CMakeLists.txt go2_interfaces/package.xml
git commit -m "feat(go2_interfaces): add 4 nav_capability actions + Cancel.srv"
```

---

### Task 2.3 — 建立 sample named_poses + sample route JSON

**Files:**
- Create: `nav_capability/config/named_poses/sample.json`
- Create: `nav_capability/config/routes/sample.json`

- [ ] **Step 1: 寫 sample named_poses**

`nav_capability/config/named_poses/sample.json`:

```json
{
  "schema_version": 1,
  "map_id": "sample_map",
  "poses": {
    "home": {"x": 0.0, "y": 0.0, "yaw": 0.0},
    "kitchen": {"x": 1.5, "y": 0.5, "yaw": 1.57},
    "door": {"x": 2.0, "y": -0.5, "yaw": 3.14}
  }
}
```

- [ ] **Step 2: 寫 sample route**

`nav_capability/config/routes/sample.json`:

```json
{
  "schema_version": 1,
  "route_id": "sample",
  "frame_id": "map",
  "map_id": "sample_map",
  "created_at": "2026-04-26T00:00:00+08:00",
  "initial_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
  "waypoints": [
    {
      "id": "wp1",
      "task": "normal",
      "pose": {"x": 1.0, "y": 0.0, "yaw": 0.0},
      "tolerance": 0.30,
      "timeout_sec": 30
    },
    {
      "id": "wp2",
      "task": "wait",
      "pose": {"x": 1.5, "y": 0.5, "yaw": 1.57},
      "tolerance": 0.30,
      "timeout_sec": 30,
      "wait_sec": 3
    },
    {
      "id": "wp3",
      "task": "tts",
      "pose": {"x": 2.0, "y": 0.5, "yaw": 3.14},
      "tolerance": 0.30,
      "timeout_sec": 30,
      "tts_text": "我到了"
    }
  ]
}
```

- [ ] **Step 3: JSON 語法驗證**

```bash
python3 -c "import json; json.load(open('nav_capability/config/named_poses/sample.json')); json.load(open('nav_capability/config/routes/sample.json')); print('json ok')"
```

Expected: `json ok`

- [ ] **Step 4: Commit**

```bash
git add nav_capability/config/
git commit -m "feat(nav): sample named_poses + route JSON for nav_capability config"
```

---

## Phase 2 完成檢查

- [x] Task 2.1 — nav_capability pkg scaffold（已在 Phase 0 完成）⏭️
- [ ] Task 2.2 — 4 actions + Cancel.srv（schema 統一在 `go2_interfaces`）✅
- [ ] Task 2.3 — sample JSON ✅

✅ Phase 2 通過 → 進 Phase 3。

---

## Phase 3 — L1 純邏輯 unit tests

**Goal**: 5 個 lib module + 對應 unit tests，全部離線（no ROS），CI < 5s。預期 38 test cases。

### Task 3.1 — `relative_goal_math` (yaw + distance → map-frame goal pose)

**Files:**
- Create: `nav_capability/nav_capability/lib/relative_goal_math.py`
- Create: `nav_capability/test/test_relative_goal_math.py`

- [ ] **Step 1: Write tests first (TDD)**

```python
# nav_capability/test/test_relative_goal_math.py
"""Tests for relative_goal_math: 從 map-frame current pose + (distance, yaw_offset) 算目標。"""
import math

from nav_capability.lib.relative_goal_math import compute_relative_goal


def test_forward_no_yaw_offset_zero_heading():
    gx, gy, gyaw = compute_relative_goal(0.0, 0.0, 0.0, 1.0, 0.0)
    assert abs(gx - 1.0) < 1e-6
    assert abs(gy) < 1e-6
    assert abs(gyaw) < 1e-6


def test_forward_heading_pi_over_2():
    gx, gy, gyaw = compute_relative_goal(0.0, 0.0, math.pi / 2, 1.0, 0.0)
    assert abs(gx) < 1e-6
    assert abs(gy - 1.0) < 1e-6
    assert abs(gyaw - math.pi / 2) < 1e-6


def test_negative_distance_means_backward():
    gx, _, _ = compute_relative_goal(0.0, 0.0, 0.0, -0.5, 0.0)
    assert abs(gx - (-0.5)) < 1e-6


def test_yaw_offset_rotates_direction_and_final_heading():
    gx, gy, gyaw = compute_relative_goal(1.0, 2.0, 0.0, 1.0, math.pi / 2)
    assert abs(gx - 1.0) < 1e-6
    assert abs(gy - 3.0) < 1e-6
    assert abs(gyaw - math.pi / 2) < 1e-6


def test_offset_origin_added_correctly():
    gx, gy, _ = compute_relative_goal(5.0, -3.0, 0.0, 2.0, 0.0)
    assert abs(gx - 7.0) < 1e-6
    assert abs(gy - (-3.0)) < 1e-6
```

- [ ] **Step 2: Run tests verify fail**

```bash
python3 -m pytest nav_capability/test/test_relative_goal_math.py -v
```

Expected: ModuleNotFoundError for `nav_capability.lib.relative_goal_math`。

- [ ] **Step 3: Write implementation**

```python
# nav_capability/nav_capability/lib/relative_goal_math.py
"""Relative goal math: 從 map-frame current pose + (distance, yaw_offset) 算目標。

純函式，no ROS 依賴。
"""
import math
from typing import Tuple


def compute_relative_goal(
    current_x: float,
    current_y: float,
    current_yaw: float,
    distance: float,
    yaw_offset: float,
) -> Tuple[float, float, float]:
    """Return (goal_x, goal_y, goal_yaw) in same frame as current_*.

    Args:
        current_x, current_y: 當前 map-frame 位置 (m)
        current_yaw: 當前 yaw (rad)
        distance: 沿 (current_yaw + yaw_offset) 走多少 (m)，可為負
        yaw_offset: 相對當前 heading 的偏移角 (rad)

    Returns:
        (goal_x, goal_y, goal_yaw)，goal_yaw = current_yaw + yaw_offset
    """
    target_heading = current_yaw + yaw_offset
    goal_x = current_x + distance * math.cos(target_heading)
    goal_y = current_y + distance * math.sin(target_heading)
    goal_yaw = target_heading
    return goal_x, goal_y, goal_yaw
```

- [ ] **Step 4: Run tests verify pass**

```bash
python3 -m pytest nav_capability/test/test_relative_goal_math.py -v
```

Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/lib/relative_goal_math.py nav_capability/test/test_relative_goal_math.py
git commit -m "feat(nav): relative_goal_math + 5 unit tests"
```

---

### Task 3.2 — `standoff_math` (target + standoff → goal pose facing target)

**Files:**
- Create: `nav_capability/nav_capability/lib/standoff_math.py`
- Create: `nav_capability/test/test_standoff_math.py`

- [ ] **Step 1: Write tests first**

```python
# nav_capability/test/test_standoff_math.py
"""standoff_math: 給目標 (x, y) + robot 當前位置 → 算 stand-off goal pose。"""
import math

from nav_capability.lib.standoff_math import compute_standoff_goal


def test_robot_west_of_target_standoff_1m():
    gx, gy, gyaw = compute_standoff_goal(3.0, 0.0, 0.0, 0.0, 1.0)
    assert abs(gx - 2.0) < 1e-6
    assert abs(gy) < 1e-6
    assert abs(gyaw) < 1e-6


def test_robot_north_of_target_standoff_05m():
    gx, gy, gyaw = compute_standoff_goal(0.0, 0.0, 0.0, 2.0, 0.5)
    assert abs(gx) < 1e-6
    assert abs(gy - 0.5) < 1e-6
    assert abs(gyaw - (-math.pi / 2)) < 1e-6


def test_zero_standoff_at_target():
    gx, gy, _ = compute_standoff_goal(1.0, 1.0, 0.0, 0.0, 0.0)
    assert abs(gx - 1.0) < 1e-6
    assert abs(gy - 1.0) < 1e-6


def test_robot_at_target_returns_target_yaw_zero():
    gx, gy, gyaw = compute_standoff_goal(2.0, 2.0, 2.0, 2.0, 0.5)
    assert abs(gx - 2.0) < 1e-6
    assert abs(gy - 2.0) < 1e-6
    assert abs(gyaw) < 1e-6


def test_diagonal_45deg():
    s = math.sqrt(2) / 2
    gx, gy, gyaw = compute_standoff_goal(1.0, 1.0, 0.0, 0.0, s)
    assert abs(gx - 0.5) < 1e-3
    assert abs(gy - 0.5) < 1e-3
    assert abs(gyaw - math.pi / 4) < 1e-3
```

- [ ] **Step 2: Run tests verify fail**

```bash
python3 -m pytest nav_capability/test/test_standoff_math.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: Write implementation**

```python
# nav_capability/nav_capability/lib/standoff_math.py
"""Standoff goal math: stand 在 target 前 N 公尺、面向 target。"""
import math
from typing import Tuple


def compute_standoff_goal(
    target_x: float,
    target_y: float,
    robot_x: float,
    robot_y: float,
    standoff: float,
) -> Tuple[float, float, float]:
    """Return (goal_x, goal_y, goal_yaw) for stand-off positioning.

    goal 在 robot→target 直線上、距離 target 為 standoff。
    goal_yaw 朝向 target。
    Edge case: robot 已在 target → goal=target, yaw=0。
    """
    dx = target_x - robot_x
    dy = target_y - robot_y
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return target_x, target_y, 0.0
    ux = dx / dist
    uy = dy / dist
    goal_x = target_x - ux * standoff
    goal_y = target_y - uy * standoff
    goal_yaw = math.atan2(dy, dx)
    return goal_x, goal_y, goal_yaw
```

- [ ] **Step 4: Run tests verify pass**

```bash
python3 -m pytest nav_capability/test/test_standoff_math.py -v
```

Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/lib/standoff_math.py nav_capability/test/test_standoff_math.py
git commit -m "feat(nav): standoff_math + 5 unit tests"
```

---

### Task 3.3 — `route_validator` (JSON schema 校驗)

**Files:**
- Create: `nav_capability/nav_capability/lib/route_validator.py`
- Create: `nav_capability/test/test_route_validator.py`

- [ ] **Step 1: Write tests first**

```python
# nav_capability/test/test_route_validator.py
"""Tests for route_validator (schema_version=1)."""
import pytest

from nav_capability.lib.route_validator import (
    RouteValidationError,
    validate_route,
)


VALID = {
    "schema_version": 1,
    "route_id": "test1",
    "frame_id": "map",
    "map_id": "m1",
    "created_at": "2026-04-26T00:00:00+08:00",
    "initial_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
    "waypoints": [
        {"id": "wp1", "task": "normal", "pose": {"x": 1.0, "y": 0.0, "yaw": 0.0},
         "tolerance": 0.3, "timeout_sec": 30},
    ],
}


def test_valid_passes():
    validate_route(VALID)


def test_missing_schema_version_fails():
    bad = {k: v for k, v in VALID.items() if k != "schema_version"}
    with pytest.raises(RouteValidationError, match="schema_version"):
        validate_route(bad)


def test_unknown_schema_version_fails():
    bad = {**VALID, "schema_version": 99}
    with pytest.raises(RouteValidationError, match="schema_version"):
        validate_route(bad)


def test_missing_frame_id_fails():
    bad = {k: v for k, v in VALID.items() if k != "frame_id"}
    with pytest.raises(RouteValidationError, match="missing required keys"):
        validate_route(bad)


def test_frame_id_must_be_map():
    bad = {**VALID, "frame_id": "odom"}
    with pytest.raises(RouteValidationError, match="frame_id"):
        validate_route(bad)


def test_waypoints_empty_fails():
    bad = {**VALID, "waypoints": []}
    with pytest.raises(RouteValidationError, match="waypoints"):
        validate_route(bad)


def test_waypoint_unknown_task_fails():
    bad = {**VALID, "waypoints": [
        {"id": "x", "task": "object_scan", "pose": {"x": 0, "y": 0, "yaw": 0},
         "tolerance": 0.3, "timeout_sec": 30},
    ]}
    with pytest.raises(RouteValidationError, match="task"):
        validate_route(bad)


def test_waypoint_wait_requires_wait_sec():
    bad = {**VALID, "waypoints": [
        {"id": "x", "task": "wait", "pose": {"x": 0, "y": 0, "yaw": 0},
         "tolerance": 0.3, "timeout_sec": 30},
    ]}
    with pytest.raises(RouteValidationError, match="wait_sec"):
        validate_route(bad)


def test_waypoint_tts_requires_tts_text():
    bad = {**VALID, "waypoints": [
        {"id": "x", "task": "tts", "pose": {"x": 0, "y": 0, "yaw": 0},
         "tolerance": 0.3, "timeout_sec": 30},
    ]}
    with pytest.raises(RouteValidationError, match="tts_text"):
        validate_route(bad)
```

- [ ] **Step 2: Run tests verify fail**

```bash
python3 -m pytest nav_capability/test/test_route_validator.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: Write implementation**

```python
# nav_capability/nav_capability/lib/route_validator.py
"""Route JSON schema validator (schema_version=1)."""
from typing import Any, Dict

SUPPORTED_SCHEMA_VERSIONS = {1}
ALLOWED_TASKS = {"normal", "wait", "tts"}
REQUIRED_TOP_KEYS = {
    "schema_version", "route_id", "frame_id", "map_id",
    "initial_pose", "waypoints",
}
REQUIRED_WAYPOINT_KEYS = {"id", "task", "pose", "tolerance", "timeout_sec"}


class RouteValidationError(ValueError):
    """Raised when route JSON fails schema validation."""


def validate_route(route: Dict[str, Any]) -> None:
    """Raise RouteValidationError if route is not v1-compliant."""
    if not isinstance(route, dict):
        raise RouteValidationError("route must be a dict")

    missing = REQUIRED_TOP_KEYS - set(route.keys())
    if missing:
        raise RouteValidationError(f"missing required keys: {missing}")

    sv = route["schema_version"]
    if sv not in SUPPORTED_SCHEMA_VERSIONS:
        raise RouteValidationError(
            f"schema_version {sv} not supported (require {SUPPORTED_SCHEMA_VERSIONS})"
        )

    if route["frame_id"] != "map":
        raise RouteValidationError(
            f"frame_id must be 'map', got '{route['frame_id']}'"
        )

    waypoints = route["waypoints"]
    if not isinstance(waypoints, list) or len(waypoints) == 0:
        raise RouteValidationError("waypoints must be a non-empty list")

    for i, wp in enumerate(waypoints):
        prefix = f"waypoints[{i}]"
        if not isinstance(wp, dict):
            raise RouteValidationError(f"{prefix}: must be a dict")
        missing_wp = REQUIRED_WAYPOINT_KEYS - set(wp.keys())
        if missing_wp:
            raise RouteValidationError(f"{prefix}: missing keys {missing_wp}")
        task = wp["task"]
        if task not in ALLOWED_TASKS:
            raise RouteValidationError(
                f"{prefix}: task '{task}' not in {ALLOWED_TASKS}"
            )
        if task == "wait" and "wait_sec" not in wp:
            raise RouteValidationError(f"{prefix}: task=wait requires wait_sec")
        if task == "tts" and "tts_text" not in wp:
            raise RouteValidationError(f"{prefix}: task=tts requires tts_text")
        for k in ("x", "y", "yaw"):
            if k not in wp["pose"]:
                raise RouteValidationError(f"{prefix}.pose missing '{k}'")
```

- [ ] **Step 4: Run tests verify pass**

```bash
python3 -m pytest nav_capability/test/test_route_validator.py -v
```

Expected: 9 passed。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/lib/route_validator.py nav_capability/test/test_route_validator.py
git commit -m "feat(nav): route_validator + 9 unit tests"
```

---

### Task 3.4 — `named_pose_store` (JSON load + lookup)

**Files:**
- Create: `nav_capability/nav_capability/lib/named_pose_store.py`
- Create: `nav_capability/test/test_named_pose_store.py`

- [ ] **Step 1: Write tests first**

```python
# nav_capability/test/test_named_pose_store.py
"""named_pose_store tests."""
import json

import pytest

from nav_capability.lib.named_pose_store import (
    NamedPose,
    NamedPoseStore,
    NamedPoseNotFound,
)


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "named_poses.json"
    p.write_text(json.dumps({
        "schema_version": 1,
        "map_id": "m1",
        "poses": {
            "home": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "kitchen": {"x": 1.5, "y": 0.5, "yaw": 1.57},
        },
    }))
    return str(p)


def test_load_and_lookup(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    pose = store.lookup("home")
    assert isinstance(pose, NamedPose)
    assert pose.x == 0.0


def test_lookup_other(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    pose = store.lookup("kitchen")
    assert pose.x == 1.5 and pose.yaw == 1.57


def test_missing_lookup_raises_with_available(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    with pytest.raises(NamedPoseNotFound) as exc:
        store.lookup("garage")
    msg = str(exc.value)
    assert "garage" in msg
    assert "home" in msg or "kitchen" in msg


def test_list_names(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    assert sorted(store.list_names()) == ["home", "kitchen"]


def test_unknown_schema_version_fails(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": 99, "map_id": "x", "poses": {}}))
    with pytest.raises(ValueError, match="schema_version"):
        NamedPoseStore.from_file(str(p))


def test_map_id(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    assert store.map_id == "m1"
```

- [ ] **Step 2: Run tests verify fail**

```bash
python3 -m pytest nav_capability/test/test_named_pose_store.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: Write implementation**

```python
# nav_capability/nav_capability/lib/named_pose_store.py
"""Named pose store: 從 JSON 載入命名 pose，提供 lookup。"""
import json
from dataclasses import dataclass
from typing import Dict, Iterable

SUPPORTED_SCHEMA_VERSIONS = {1}


@dataclass(frozen=True)
class NamedPose:
    x: float
    y: float
    yaw: float


class NamedPoseNotFound(KeyError):
    pass


class NamedPoseStore:
    def __init__(self, map_id: str, poses: Dict[str, NamedPose]):
        self.map_id = map_id
        self._poses = dict(poses)

    @classmethod
    def from_file(cls, path: str) -> "NamedPoseStore":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sv = data.get("schema_version")
        if sv not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version {sv} not supported (require {SUPPORTED_SCHEMA_VERSIONS})"
            )
        map_id = data.get("map_id", "")
        poses = {
            name: NamedPose(x=p["x"], y=p["y"], yaw=p["yaw"])
            for name, p in data.get("poses", {}).items()
        }
        return cls(map_id=map_id, poses=poses)

    def lookup(self, name: str) -> NamedPose:
        if name not in self._poses:
            available = sorted(self._poses.keys())
            raise NamedPoseNotFound(
                f"named pose '{name}' not found; available: {available}"
            )
        return self._poses[name]

    def list_names(self) -> Iterable[str]:
        return list(self._poses.keys())
```

- [ ] **Step 4: Run tests verify pass**

```bash
python3 -m pytest nav_capability/test/test_named_pose_store.py -v
```

Expected: 6 passed。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/lib/named_pose_store.py nav_capability/test/test_named_pose_store.py
git commit -m "feat(nav): named_pose_store + 6 unit tests"
```

---

### Task 3.5 — `route_fsm` (8 states + transitions)

**Files:**
- Create: `nav_capability/nav_capability/lib/route_fsm.py`
- Create: `nav_capability/test/test_route_fsm.py`

- [ ] **Step 1: Write tests first**

```python
# nav_capability/test/test_route_fsm.py
"""Pure-logic FSM tests."""
import pytest

from nav_capability.lib.route_fsm import RouteFSM, RouteState, IllegalTransition


def test_initial_state_is_idle():
    assert RouteFSM().state == RouteState.IDLE


def test_start_to_planning():
    fsm = RouteFSM()
    fsm.start_route(total_waypoints=3)
    assert fsm.state == RouteState.PLANNING
    assert fsm.current_waypoint_index == 0


def test_planning_to_moving():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    assert fsm.state == RouteState.MOVING


def test_normal_advances():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    assert fsm.state == RouteState.PLANNING
    assert fsm.current_waypoint_index == 1


def test_wait_enters_waiting():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="wait")
    assert fsm.state == RouteState.WAITING


def test_tts_enters_tts():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="tts")
    assert fsm.state == RouteState.TTS


def test_waiting_complete_advances():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="wait")
    fsm.task_complete()
    assert fsm.state == RouteState.PLANNING
    assert fsm.current_waypoint_index == 1


def test_last_normal_succeeds():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    assert fsm.state == RouteState.SUCCEEDED


def test_pause_from_moving():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.pause()
    assert fsm.state == RouteState.PAUSED


def test_resume_re_enters_planning():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.pause()
    fsm.resume()
    assert fsm.state == RouteState.PLANNING


def test_cancel_to_failed():
    fsm = RouteFSM()
    fsm.start_route(2)
    fsm.goal_accepted()
    fsm.cancel()
    assert fsm.state == RouteState.FAILED


def test_pause_from_idle_raises():
    fsm = RouteFSM()
    with pytest.raises(IllegalTransition):
        fsm.pause()


def test_pause_resume_preserves_index():
    fsm = RouteFSM()
    fsm.start_route(3)
    fsm.goal_accepted()
    fsm.waypoint_reached(task="normal")
    fsm.goal_accepted()
    fsm.pause()
    fsm.resume()
    assert fsm.current_waypoint_index == 1
```

- [ ] **Step 2: Run tests verify fail**

```bash
python3 -m pytest nav_capability/test/test_route_fsm.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: Write implementation**

```python
# nav_capability/nav_capability/lib/route_fsm.py
"""Route Runner FSM (pure logic, no ROS)."""
from enum import Enum, auto


class RouteState(Enum):
    IDLE = auto()
    PLANNING = auto()
    MOVING = auto()
    PAUSED = auto()
    WAITING = auto()
    TTS = auto()
    SUCCEEDED = auto()
    FAILED = auto()


ACTIVE_STATES = {
    RouteState.PLANNING, RouteState.MOVING,
    RouteState.PAUSED, RouteState.WAITING, RouteState.TTS,
}


class IllegalTransition(RuntimeError):
    pass


class RouteFSM:
    def __init__(self):
        self.state: RouteState = RouteState.IDLE
        self.current_waypoint_index: int = 0
        self._total: int = 0

    def start_route(self, total_waypoints: int) -> None:
        if self.state != RouteState.IDLE:
            raise IllegalTransition(f"cannot start_route from {self.state}")
        if total_waypoints <= 0:
            raise ValueError("total_waypoints must be > 0")
        self._total = total_waypoints
        self.current_waypoint_index = 0
        self.state = RouteState.PLANNING

    def goal_accepted(self) -> None:
        if self.state != RouteState.PLANNING:
            raise IllegalTransition(f"cannot goal_accepted from {self.state}")
        self.state = RouteState.MOVING

    def waypoint_reached(self, task: str) -> None:
        if self.state != RouteState.MOVING:
            raise IllegalTransition(f"cannot waypoint_reached from {self.state}")
        if task == "normal":
            self._advance_or_finish()
        elif task == "wait":
            self.state = RouteState.WAITING
        elif task == "tts":
            self.state = RouteState.TTS
        else:
            raise ValueError(f"unknown task: {task}")

    def task_complete(self) -> None:
        if self.state not in (RouteState.WAITING, RouteState.TTS):
            raise IllegalTransition(f"cannot task_complete from {self.state}")
        self._advance_or_finish()

    def pause(self) -> None:
        if self.state not in (RouteState.PLANNING, RouteState.MOVING):
            raise IllegalTransition(f"cannot pause from {self.state}")
        self.state = RouteState.PAUSED

    def resume(self) -> None:
        if self.state != RouteState.PAUSED:
            raise IllegalTransition(f"cannot resume from {self.state}")
        self.state = RouteState.PLANNING

    def cancel(self) -> None:
        if self.state not in ACTIVE_STATES:
            raise IllegalTransition(f"cannot cancel from {self.state}")
        self.state = RouteState.FAILED

    def _advance_or_finish(self) -> None:
        self.current_waypoint_index += 1
        if self.current_waypoint_index >= self._total:
            self.state = RouteState.SUCCEEDED
        else:
            self.state = RouteState.PLANNING
```

- [ ] **Step 4: Run all Phase 3 tests together**

```bash
python3 -m pytest nav_capability/test/ -v --ignore=nav_capability/test/integration
```

Expected: 30 passed (5+5+9+6+5)。CI < 5s。

> **註**：Task 3.5 寫了 13 個 test cases；以上 5+5+9+6+13 = 38。實際數字可能略差 1-2 視 edge case 補強。Phase 3 通過標準是 ≥ 30 cases pass。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/lib/route_fsm.py nav_capability/test/test_route_fsm.py
git commit -m "feat(nav): route_fsm + 13 unit tests; Phase 3 L1 complete"
```

---

## Phase 3 完成檢查

- [ ] Task 3.1 — relative_goal_math (5 tests) ✅
- [ ] Task 3.2 — standoff_math (5 tests) ✅
- [ ] Task 3.3 — route_validator (9 tests) ✅
- [ ] Task 3.4 — named_pose_store (6 tests) ✅
- [ ] Task 3.5 — route_fsm (13 tests) ✅

✅ 38 cases pass、CI < 5s → 進 Phase 4。

---

## Phase 4 — goto_relative action server

**Goal**: 實作 `nav_action_server_node`，提供 `/nav/goto_relative` action，內部包裝 Nav2 NavigateToPose。完成後可實機跑 0.5m / 0.8m goal。

### Task 4.1 — `nav_action_server_node` 骨架 + TF lookup helper

**Files:**
- Create: `nav_capability/nav_capability/nav_action_server_node.py`
- Create: `nav_capability/nav_capability/lib/tf_pose_helper.py`
- Create: `nav_capability/test/test_tf_pose_helper.py`

- [ ] **Step 1: Write tf_pose_helper test (純邏輯，把 quat → yaw)**

```python
# nav_capability/test/test_tf_pose_helper.py
"""Tests for tf_pose_helper: quaternion → yaw 轉換 (純數學)。"""
import math

from nav_capability.lib.tf_pose_helper import (
    quat_to_yaw,
    yaw_to_quat,
)


def test_yaw_zero_to_quat():
    qx, qy, qz, qw = yaw_to_quat(0.0)
    assert abs(qz) < 1e-6
    assert abs(qw - 1.0) < 1e-6


def test_yaw_pi_over_2_to_quat():
    qx, qy, qz, qw = yaw_to_quat(math.pi / 2)
    assert abs(qz - math.sin(math.pi / 4)) < 1e-6
    assert abs(qw - math.cos(math.pi / 4)) < 1e-6


def test_quat_to_yaw_zero():
    yaw = quat_to_yaw(0.0, 0.0, 0.0, 1.0)
    assert abs(yaw) < 1e-6


def test_quat_to_yaw_pi():
    yaw = quat_to_yaw(0.0, 0.0, 1.0, 0.0)
    assert abs(abs(yaw) - math.pi) < 1e-6


def test_round_trip():
    for yaw in [0.0, 0.5, -1.2, math.pi / 3, -math.pi / 4]:
        q = yaw_to_quat(yaw)
        yaw_back = quat_to_yaw(*q)
        assert abs(yaw_back - yaw) < 1e-6
```

- [ ] **Step 2: Run tests verify fail**

```bash
python3 -m pytest nav_capability/test/test_tf_pose_helper.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: Write tf_pose_helper**

```python
# nav_capability/nav_capability/lib/tf_pose_helper.py
"""TF / quaternion helpers (pure math, no ROS)。"""
import math
from typing import Tuple


def yaw_to_quat(yaw: float) -> Tuple[float, float, float, float]:
    """Yaw (rad, around z-axis) → (qx, qy, qz, qw)."""
    half = yaw / 2.0
    return 0.0, 0.0, math.sin(half), math.cos(half)


def quat_to_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    """Quaternion → yaw (rad)。 z-axis only (planar)。"""
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)
```

- [ ] **Step 4: Run tests verify pass**

```bash
python3 -m pytest nav_capability/test/test_tf_pose_helper.py -v
```

Expected: 5 passed。

- [ ] **Step 5: Write nav_action_server_node 骨架（只 init，不接 action 邏輯）**

```python
# nav_capability/nav_capability/nav_action_server_node.py
"""Nav action server: 提供 /nav/goto_relative 與 /nav/goto_named action。

包裝 Nav2 NavigateToPose 為高階 API。
v1: 一律走 map frame（需要 AMCL 在線）；純 odom path 列入 spec T5。
"""
import math
from typing import Optional, Tuple

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy
from nav2_msgs.action import NavigateToPose

from go2_interfaces.action import GotoRelative
from nav_capability.lib.relative_goal_math import compute_relative_goal
from nav_capability.lib.tf_pose_helper import yaw_to_quat, quat_to_yaw

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class NavActionServerNode(Node):
    def __init__(self):
        super().__init__("nav_action_server_node")
        self._cb_group = ReentrantCallbackGroup()

        # Latest AMCL pose
        self._amcl_pose: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, AMCL_QOS,
            callback_group=self._cb_group,
        )

        # Nav2 NavigateToPose client
        self._nav_client = ActionClient(
            self, NavigateToPose, "/navigate_to_pose",
            callback_group=self._cb_group,
        )

        # GotoRelative action server
        self._relative_server = ActionServer(
            self,
            GotoRelative,
            "/nav/goto_relative",
            execute_callback=self._execute_relative,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
            callback_group=self._cb_group,
        )

        self.get_logger().info("nav_action_server_node ready")

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl_pose = msg

    def _accept_goal(self, _goal):
        return GoalResponse.ACCEPT

    def _cancel_goal(self, _goal):
        return CancelResponse.ACCEPT

    def _amcl_covariance_xy(self) -> Optional[float]:
        """Return σ²x + σ²y from /amcl_pose covariance, or None if no pose."""
        if self._amcl_pose is None:
            return None
        c = self._amcl_pose.pose.covariance
        return c[0] + c[7]  # diagonal x + y

    def _current_map_pose(self) -> Optional[Tuple[float, float, float]]:
        if self._amcl_pose is None:
            return None
        p = self._amcl_pose.pose.pose
        yaw = quat_to_yaw(
            p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w
        )
        return p.position.x, p.position.y, yaw

    async def _execute_relative(self, goal_handle):
        goal = goal_handle.request

        # AMCL covariance gating (E1)
        cov = self._amcl_covariance_xy()
        if cov is None:
            goal_handle.abort()
            result = GotoRelative.Result()
            result.success = False
            result.message = "amcl_lost"
            return result
        if cov > 0.5:
            goal_handle.abort()
            result = GotoRelative.Result()
            result.success = False
            result.message = "amcl_lost"
            return result
        if 0.3 < cov <= 0.5 and abs(goal.distance) > 0.5:
            goal_handle.abort()
            result = GotoRelative.Result()
            result.success = False
            result.message = "amcl_lost"
            return result

        # Compute map-frame goal
        cur = self._current_map_pose()
        if cur is None:
            goal_handle.abort()
            result = GotoRelative.Result()
            result.success = False
            result.message = "amcl_lost"
            return result
        cx, cy, cyaw = cur
        gx, gy, gyaw = compute_relative_goal(cx, cy, cyaw, goal.distance, goal.yaw_offset)

        # Wrap as Nav2 NavigateToPose
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x = gx
        nav_goal.pose.pose.position.y = gy
        qx, qy, qz, qw = yaw_to_quat(gyaw)
        nav_goal.pose.pose.orientation.x = qx
        nav_goal.pose.pose.orientation.y = qy
        nav_goal.pose.pose.orientation.z = qz
        nav_goal.pose.pose.orientation.w = qw

        # Send + wait for result
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            goal_handle.abort()
            result = GotoRelative.Result()
            result.success = False
            result.message = "nav2_unavailable"
            return result

        send_future = self._nav_client.send_goal_async(nav_goal)
        nav_handle = await send_future
        if not nav_handle.accepted:
            goal_handle.abort()
            result = GotoRelative.Result()
            result.success = False
            result.message = "nav2_rejected_goal"
            return result

        nav_result_future = nav_handle.get_result_async()
        nav_result = await nav_result_future

        result = GotoRelative.Result()
        if nav_result.status == GoalStatus.STATUS_SUCCEEDED:
            result.success = True
            result.message = "reached"
            cur_after = self._current_map_pose()
            if cur_after is not None:
                ax, ay, _ = cur_after
                result.actual_distance = math.hypot(ax - cx, ay - cy)
            goal_handle.succeed()
        else:
            result.success = False
            result.message = "nav2_failed"
            goal_handle.abort()
        return result


def main():
    rclpy.init()
    node = NavActionServerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 解開 setup.py 對應 entry point**

修改 `nav_capability/setup.py` 中 `entry_points`：

```python
        "console_scripts": [
            "nav_action_server_node = nav_capability.nav_action_server_node:main",
            # 其他 3 個 Phase 5-6 再解開
        ],
```

- [ ] **Step 7: colcon build**

```bash
colcon build --packages-select nav_capability
source install/setup.zsh
ros2 pkg executables nav_capability | grep nav_action_server_node
```

Expected: `nav_capability nav_action_server_node`

- [ ] **Step 8: Smoke test (no AMCL needed for boot)**

```bash
ros2 run nav_capability nav_action_server_node &
NS_PID=$!
sleep 2
ros2 action list | grep goto_relative
kill $NS_PID
```

Expected: 看到 `/nav/goto_relative`。

- [ ] **Step 9: Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py \
        nav_capability/nav_capability/lib/tf_pose_helper.py \
        nav_capability/test/test_tf_pose_helper.py \
        nav_capability/setup.py
git commit -m "feat(nav): nav_action_server_node + GotoRelative action (wraps Nav2 NavigateToPose)"
```

---

## Phase 4 完成檢查

- [ ] Task 4.1 — nav_action_server_node + GotoRelative + tf helper (5 tests) ✅

✅ Phase 4 通過 → 進 Phase 5。

實機驗收延後到 Phase 10 (對應 K1+K2)。

---

## Phase 5 — goto_named + log_pose action servers

**Goal**: 在 `nav_action_server_node` 加 `/nav/goto_named` action（含 standoff option）。新建 `log_pose_node` 提供 `/log_pose` action。

### Task 5.1 — 把 GotoNamed action 加到 nav_action_server_node

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1: 加 NamedPoseStore + standoff_math import**

在 `nav_action_server_node.py` 頂部 import 區加：

```python
import os
from ament_index_python.packages import get_package_share_directory

from go2_interfaces.action import GotoNamed
from nav_capability.lib.named_pose_store import (
    NamedPoseStore, NamedPoseNotFound,
)
from nav_capability.lib.standoff_math import compute_standoff_goal
```

- [ ] **Step 2: 在 __init__ 載入 named_poses + 加 GotoNamed server**

在 `__init__` 末尾（`self.get_logger().info(...)` 前）加：

```python
        # Named poses (load from share)
        self.declare_parameter("named_poses_file", "")
        named_file = self.get_parameter("named_poses_file").value
        if not named_file:
            named_file = os.path.join(
                get_package_share_directory("nav_capability"),
                "config", "named_poses", "sample.json",
            )
        try:
            self._named_store = NamedPoseStore.from_file(named_file)
            self.get_logger().info(
                f"loaded named_poses from {named_file}: {list(self._named_store.list_names())}"
            )
        except Exception as exc:
            self.get_logger().warn(f"failed to load named_poses: {exc}")
            self._named_store = None

        # GotoNamed server
        self._named_server = ActionServer(
            self,
            GotoNamed,
            "/nav/goto_named",
            execute_callback=self._execute_named,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
            callback_group=self._cb_group,
        )
```

- [ ] **Step 3: 加 `_execute_named` callback**

在 class 內加 method（_execute_relative 後）：

```python
    async def _execute_named(self, goal_handle):
        goal = goal_handle.request
        result = GotoNamed.Result()

        if self._named_store is None:
            goal_handle.abort()
            result.success = False
            result.message = "named_pose_store_not_loaded"
            return result

        try:
            named = self._named_store.lookup(goal.name)
        except NamedPoseNotFound as exc:
            goal_handle.abort()
            result.success = False
            result.message = str(exc)
            return result

        # AMCL gating
        cov = self._amcl_covariance_xy()
        if cov is None or cov > 0.5:
            goal_handle.abort()
            result.success = False
            result.message = "amcl_lost"
            return result

        # Determine final goal: with optional standoff transform
        target_x, target_y, target_yaw = named.x, named.y, named.yaw
        if goal.standoff > 0.0:
            cur = self._current_map_pose()
            if cur is None:
                goal_handle.abort()
                result.success = False
                result.message = "amcl_lost"
                return result
            rx, ry, _ = cur
            gx, gy, gyaw_face = compute_standoff_goal(
                target_x, target_y, rx, ry, goal.standoff
            )
            final_yaw = gyaw_face if goal.align_yaw_to_target else target_yaw
            final_x, final_y = gx, gy
        else:
            final_x, final_y, final_yaw = target_x, target_y, target_yaw

        # Build Nav2 goal
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x = final_x
        nav_goal.pose.pose.position.y = final_y
        qx, qy, qz, qw = yaw_to_quat(final_yaw)
        nav_goal.pose.pose.orientation.x = qx
        nav_goal.pose.pose.orientation.y = qy
        nav_goal.pose.pose.orientation.z = qz
        nav_goal.pose.pose.orientation.w = qw

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            goal_handle.abort()
            result.success = False
            result.message = "nav2_unavailable"
            return result

        nav_handle = await self._nav_client.send_goal_async(nav_goal)
        if not nav_handle.accepted:
            goal_handle.abort()
            result.success = False
            result.message = "nav2_rejected_goal"
            return result

        nav_result = await nav_handle.get_result_async()
        if nav_result.status == GoalStatus.STATUS_SUCCEEDED:
            result.success = True
            result.message = "reached"
            result.final_pose.position.x = final_x
            result.final_pose.position.y = final_y
            qx, qy, qz, qw = yaw_to_quat(final_yaw)
            result.final_pose.orientation.x = qx
            result.final_pose.orientation.y = qy
            result.final_pose.orientation.z = qz
            result.final_pose.orientation.w = qw
            goal_handle.succeed()
        else:
            result.success = False
            result.message = "nav2_failed"
            goal_handle.abort()
        return result
```

- [ ] **Step 4: colcon build + smoke test**

```bash
colcon build --packages-select nav_capability
source install/setup.zsh
ros2 run nav_capability nav_action_server_node &
NS_PID=$!
sleep 2
ros2 action list | grep -E "goto_relative|goto_named"
kill $NS_PID
```

Expected: 看到兩個 action `/nav/goto_relative` `/nav/goto_named`。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py
git commit -m "feat(nav): add GotoNamed action with optional standoff transform"
```

---

### Task 5.2 — `log_pose_node`

**Files:**
- Create: `nav_capability/nav_capability/log_pose_node.py`

- [ ] **Step 1: Write log_pose_node**

```python
# nav_capability/nav_capability/log_pose_node.py
"""Log pose action server: 記錄當前 /amcl_pose 到 named_poses 或 route JSON。"""
import json
import os
from datetime import datetime
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.action import ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy

from go2_interfaces.action import LogPose
from nav_capability.lib.tf_pose_helper import quat_to_yaw, yaw_to_quat

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class LogPoseNode(Node):
    def __init__(self):
        super().__init__("log_pose_node")
        self._cb = ReentrantCallbackGroup()

        self.declare_parameter("named_poses_file", "")
        self.declare_parameter("routes_dir", "")
        self.declare_parameter("map_id", "unknown_map")

        self._amcl: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, AMCL_QOS,
            callback_group=self._cb,
        )

        self._server = ActionServer(
            self,
            LogPose,
            "/log_pose",
            execute_callback=self._execute,
            callback_group=self._cb,
        )

        self.get_logger().info("log_pose_node ready")

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl = msg

    async def _execute(self, goal_handle):
        goal = goal_handle.request
        result = LogPose.Result()

        if self._amcl is None:
            goal_handle.abort()
            result.success = False
            result.saved_path = ""
            return result

        p = self._amcl.pose.pose
        yaw = quat_to_yaw(
            p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w
        )
        recorded = {"x": p.position.x, "y": p.position.y, "yaw": yaw}
        result.recorded_pose = p

        if goal.log_target == "named_poses":
            path = self.get_parameter("named_poses_file").value
            if not path:
                goal_handle.abort()
                result.success = False
                result.saved_path = ""
                return result
            self._upsert_named(path, goal.name, recorded)
            result.saved_path = path
        elif goal.log_target == "route":
            routes_dir = self.get_parameter("routes_dir").value
            if not routes_dir or not goal.route_id:
                goal_handle.abort()
                result.success = False
                result.saved_path = ""
                return result
            path = os.path.join(routes_dir, f"{goal.route_id}.json")
            self._append_waypoint(path, goal.route_id, goal.name, goal.task_type, recorded)
            result.saved_path = path
        else:
            goal_handle.abort()
            result.success = False
            result.saved_path = ""
            return result

        result.success = True
        goal_handle.succeed()
        return result

    def _upsert_named(self, path: str, name: str, pose: dict) -> None:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "schema_version": 1,
                "map_id": self.get_parameter("map_id").value,
                "poses": {},
            }
        data.setdefault("poses", {})[name] = pose
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _append_waypoint(
        self, path: str, route_id: str, wp_id: str, task_type: str, pose: dict
    ) -> None:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "schema_version": 1,
                "route_id": route_id,
                "frame_id": "map",
                "map_id": self.get_parameter("map_id").value,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "initial_pose": pose,
                "waypoints": [],
            }
        wp = {
            "id": wp_id,
            "task": task_type or "normal",
            "pose": pose,
            "tolerance": 0.30,
            "timeout_sec": 30,
        }
        data.setdefault("waypoints", []).append(wp)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    rclpy.init()
    node = LogPoseNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 解開 setup.py entry point**

```python
        "console_scripts": [
            "nav_action_server_node = nav_capability.nav_action_server_node:main",
            "log_pose_node = nav_capability.log_pose_node:main",
            # state_broadcaster + route_runner Phase 6-7 再解開
        ],
```

- [ ] **Step 3: colcon build + smoke test**

```bash
colcon build --packages-select nav_capability
source install/setup.zsh
ros2 run nav_capability log_pose_node &
LP_PID=$!
sleep 2
ros2 action list | grep log_pose
kill $LP_PID
```

Expected: `/log_pose`

- [ ] **Step 4: Commit**

```bash
git add nav_capability/nav_capability/log_pose_node.py nav_capability/setup.py
git commit -m "feat(nav): log_pose_node — record /amcl_pose to named_poses or route JSON"
```

---

## Phase 5 完成檢查

- [ ] Task 5.1 — GotoNamed (含 standoff option) ✅
- [ ] Task 5.2 — log_pose_node ✅

✅ Phase 5 通過 → 進 Phase 6。

---

## Phase 6 — state broadcaster + 3 services (pause/resume/cancel)

**Goal**: `state_broadcaster_node` 持續發 heartbeat + status + safety；3 service 端點接 route_runner（Phase 7 整合）。

### Task 6.1 — `state_broadcaster_node`

**Files:**
- Create: `nav_capability/nav_capability/state_broadcaster_node.py`

- [ ] **Step 1: Write node**

```python
# nav_capability/nav_capability/state_broadcaster_node.py
"""State broadcaster: 持續發 heartbeat + status + safety JSON。

訂閱:
  /amcl_pose                       (covariance for safety)
  /scan_rplidar                    (alive heartbeat for safety)
  /event/nav/internal/status       (custom from nav_action / route_runner)

發布:
  /state/nav/heartbeat (1Hz, std_msgs/Header)
  /state/nav/status    (10Hz, std_msgs/String JSON)
  /state/nav/safety    (10Hz, std_msgs/String JSON)
"""
import json
from typing import Optional

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Header, String

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)
SCAN_QOS = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)


class StateBroadcasterNode(Node):
    def __init__(self):
        super().__init__("state_broadcaster_node")

        self._latest_status_payload: dict = {
            "state": "idle",
            "active_goal": None,
            "distance_to_goal": 0.0,
            "eta_sec": 0.0,
            "amcl_covariance_xy": 0.0,
        }
        self._latest_amcl_cov: Optional[float] = None
        self._last_scan_time: float = 0.0

        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, AMCL_QOS,
        )
        self.create_subscription(
            LaserScan, "/scan_rplidar", self._on_scan, SCAN_QOS,
        )
        # Internal status feed from action servers
        self.create_subscription(
            String, "/event/nav/internal/status", self._on_internal_status, 10,
        )

        self._heartbeat_pub = self.create_publisher(Header, "/state/nav/heartbeat", 10)
        self._status_pub = self.create_publisher(String, "/state/nav/status", 10)
        self._safety_pub = self.create_publisher(String, "/state/nav/safety", 10)

        self.create_timer(1.0, self._tick_heartbeat)
        self.create_timer(0.1, self._tick_status_safety)

        self.get_logger().info("state_broadcaster_node ready")

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        c = msg.pose.covariance
        self._latest_amcl_cov = c[0] + c[7]
        self._latest_status_payload["amcl_covariance_xy"] = self._latest_amcl_cov

    def _on_scan(self, _msg: LaserScan) -> None:
        self._last_scan_time = self.get_clock().now().nanoseconds / 1e9

    def _on_internal_status(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
            self._latest_status_payload.update(payload)
        except json.JSONDecodeError:
            self.get_logger().warn(f"bad internal status JSON: {msg.data}")

    def _amcl_health(self) -> str:
        cov = self._latest_amcl_cov
        if cov is None:
            return "red"
        if cov < 0.3:
            return "green"
        if cov <= 0.5:
            return "yellow"
        return "red"

    def _lidar_alive(self) -> bool:
        if self._last_scan_time == 0.0:
            return False
        now = self.get_clock().now().nanoseconds / 1e9
        return (now - self._last_scan_time) < 1.0

    def _tick_heartbeat(self) -> None:
        h = Header()
        h.stamp = self.get_clock().now().to_msg()
        h.frame_id = "nav_capability"
        self._heartbeat_pub.publish(h)

    def _tick_status_safety(self) -> None:
        # Status
        s = String()
        s.data = json.dumps(self._latest_status_payload)
        self._status_pub.publish(s)

        # Safety
        safety_payload = {
            "reactive_stop_active": False,  # 由 reactive_stop_node 自己廣播 future
            "obstacle_distance": 0.0,
            "obstacle_zone": "normal",
            "lidar_alive": self._lidar_alive(),
            "amcl_health": self._amcl_health(),
            "pause_count_recent_10s": 0,
        }
        sf = String()
        sf.data = json.dumps(safety_payload)
        self._safety_pub.publish(sf)


def main():
    rclpy.init()
    node = StateBroadcasterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 解開 setup.py entry**

```python
        "console_scripts": [
            "nav_action_server_node = nav_capability.nav_action_server_node:main",
            "log_pose_node = nav_capability.log_pose_node:main",
            "state_broadcaster_node = nav_capability.state_broadcaster_node:main",
        ],
```

- [ ] **Step 3: colcon build + smoke**

```bash
colcon build --packages-select nav_capability
source install/setup.zsh
ros2 run nav_capability state_broadcaster_node &
SB_PID=$!
sleep 2
timeout 3 ros2 topic hz /state/nav/heartbeat
timeout 3 ros2 topic hz /state/nav/status
kill $SB_PID
```

Expected: heartbeat ~1Hz, status ~10Hz。

- [ ] **Step 4: Commit**

```bash
git add nav_capability/nav_capability/state_broadcaster_node.py nav_capability/setup.py
git commit -m "feat(nav): state_broadcaster_node — heartbeat + status + safety JSON"
```

---

### Task 6.2 — pause/resume/cancel services（先在 nav_action_server_node 加 stub，Phase 7 接 route_runner）

> 註：實際 pause/resume 邏輯在 route_runner（Phase 7.3 完整接線）。本 task 先建 service 端點。

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1: Import services + add stubs**

在 `nav_action_server_node.py` 頂部 import 加：

```python
from std_srvs.srv import Trigger
from go2_interfaces.srv import Cancel
```

在 `__init__` 末尾加（`self.get_logger().info(...)` 前）：

```python
        # Pause / Resume / Cancel services (Phase 7 will wire to route_runner)
        # 此版只是端點記錄；route_runner 從 Phase 7.3 開始接管實際 FSM。
        self._pause_state = "idle"  # idle | paused
        self.create_service(Trigger, "/nav/pause", self._handle_pause)
        self.create_service(Trigger, "/nav/resume", self._handle_resume)
        self.create_service(Cancel, "/nav/cancel", self._handle_cancel)
```

加 method:

```python
    def _handle_pause(self, _req, resp):
        # NOTE: full FSM coupling to route_runner is in Phase 7.3
        if self._pause_state == "idle":
            self._pause_state = "paused"
            resp.success = True
            resp.message = "paused"
        else:
            resp.success = False
            resp.message = "already_paused"
        return resp

    def _handle_resume(self, _req, resp):
        if self._pause_state == "paused":
            self._pause_state = "idle"
            resp.success = True
            resp.message = "resumed"
        else:
            resp.success = False
            resp.message = "no_paused_goal"
        return resp

    def _handle_cancel(self, _req, resp):
        # safe_stop param read but full impl pending route_runner
        resp.success = True
        return resp
```

- [ ] **Step 2: build + smoke**

```bash
colcon build --packages-select nav_capability
source install/setup.zsh
ros2 run nav_capability nav_action_server_node &
NS_PID=$!
sleep 2
ros2 service list | grep nav
ros2 service call /nav/pause std_srvs/srv/Trigger
ros2 service call /nav/resume std_srvs/srv/Trigger
kill $NS_PID
```

Expected: 看到三個 service，pause/resume 各回 `success=True`。

- [ ] **Step 3: Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py
git commit -m "feat(nav): pause/resume/cancel service stubs (route_runner wires in Phase 7)"
```

---

## Phase 6 完成檢查

- [ ] Task 6.1 — state_broadcaster_node ✅
- [ ] Task 6.2 — pause/resume/cancel service 端點 ✅

✅ Phase 6 通過 → 進 Phase 7。

---

## Phase 7 — Route Runner（核心編排層）

**Goal**: `route_runner_node` 提供 `/nav/run_route` action，逐 waypoint 派 Nav2 goal，遇 `wait` / `tts` task 暫停執行。pause/resume 接 reactive_stop。發 `/event/nav/waypoint_reached`。

### Task 7.1 — `route_runner_node` 骨架 + JSON 載入

**Files:**
- Create: `nav_capability/nav_capability/route_runner_node.py`

- [ ] **Step 1: Write route_runner_node skeleton**

```python
# nav_capability/nav_capability/route_runner_node.py
"""Route Runner: 跑 multi-waypoint route，FSM 驅動，遇 wait/tts 暫停執行。"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

import rclpy
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from nav2_msgs.action import NavigateToPose

from go2_interfaces.action import RunRoute
from go2_interfaces.srv import Cancel
from nav_capability.lib.route_validator import (
    RouteValidationError, validate_route,
)
from nav_capability.lib.route_fsm import RouteFSM, RouteState, IllegalTransition
from nav_capability.lib.tf_pose_helper import yaw_to_quat

AMCL_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)


class RouteRunnerNode(Node):
    def __init__(self):
        super().__init__("route_runner_node")
        self._cb = ReentrantCallbackGroup()

        self.declare_parameter("routes_dir", "")

        self._fsm = RouteFSM()
        self._current_route: Optional[dict] = None
        self._current_nav_handle = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # default: not paused

        self._amcl: Optional[PoseWithCovarianceStamped] = None
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, AMCL_QOS,
            callback_group=self._cb,
        )

        self._nav_client = ActionClient(
            self, NavigateToPose, "/navigate_to_pose",
            callback_group=self._cb,
        )

        self._tts_pub = self.create_publisher(String, "/tts", 10)
        self._waypoint_event_pub = self.create_publisher(
            String, "/event/nav/waypoint_reached", 10,
        )
        self._internal_status_pub = self.create_publisher(
            String, "/event/nav/internal/status", 10,
        )

        self._run_server = ActionServer(
            self, RunRoute, "/nav/run_route",
            execute_callback=self._execute_run_route,
            goal_callback=self._accept_goal,
            cancel_callback=self._cancel_goal,
            callback_group=self._cb,
        )

        # Override pause/resume/cancel services to drive route FSM
        self.create_service(Trigger, "/nav/pause", self._svc_pause, callback_group=self._cb)
        self.create_service(Trigger, "/nav/resume", self._svc_resume, callback_group=self._cb)
        self.create_service(Cancel, "/nav/cancel", self._svc_cancel, callback_group=self._cb)

        self.get_logger().info("route_runner_node ready")

    def _on_amcl(self, msg: PoseWithCovarianceStamped) -> None:
        self._amcl = msg

    def _accept_goal(self, _g):
        return GoalResponse.ACCEPT

    def _cancel_goal(self, _g):
        return CancelResponse.ACCEPT

    def _publish_internal_status(self, extra: dict) -> None:
        payload = {
            "state": self._fsm.state.name.lower(),
            "active_goal": extra.get("active_goal"),
        }
        payload.update(extra)
        m = String()
        m.data = json.dumps(payload)
        self._internal_status_pub.publish(m)

    def _load_route(self, route_id: str) -> dict:
        routes_dir = self.get_parameter("routes_dir").value
        if not routes_dir:
            routes_dir = os.path.join(
                get_package_share_directory("nav_capability"),
                "config", "routes",
            )
        path = os.path.join(routes_dir, f"{route_id}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate_route(data)
        return data

    def _build_nav_goal(self, wp: dict) -> NavigateToPose.Goal:
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose.header.frame_id = "map"
        nav_goal.pose.header.stamp = self.get_clock().now().to_msg()
        nav_goal.pose.pose.position.x = wp["pose"]["x"]
        nav_goal.pose.pose.position.y = wp["pose"]["y"]
        qx, qy, qz, qw = yaw_to_quat(wp["pose"]["yaw"])
        nav_goal.pose.pose.orientation.x = qx
        nav_goal.pose.pose.orientation.y = qy
        nav_goal.pose.pose.orientation.z = qz
        nav_goal.pose.pose.orientation.w = qw
        return nav_goal

    async def _execute_run_route(self, goal_handle):
        result = RunRoute.Result()
        feedback = RunRoute.Feedback()
        try:
            route = self._load_route(goal_handle.request.route_id)
        except (FileNotFoundError, RouteValidationError) as exc:
            goal_handle.abort()
            result.success = False
            result.message = f"bad_route: {exc}"
            return result

        self._current_route = route
        waypoints = route["waypoints"]
        try:
            self._fsm.start_route(total_waypoints=len(waypoints))
        except IllegalTransition:
            # Reset and retry
            self._fsm = RouteFSM()
            self._fsm.start_route(total_waypoints=len(waypoints))

        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            goal_handle.abort()
            result.success = False
            result.message = "nav2_unavailable"
            return result

        while self._fsm.state not in (RouteState.SUCCEEDED, RouteState.FAILED):
            # Wait if paused
            await self._pause_event.wait()

            idx = self._fsm.current_waypoint_index
            wp = waypoints[idx]

            feedback.current_waypoint_index = idx
            feedback.current_waypoint_id = wp["id"]
            feedback.current_state = self._fsm.state.name.lower()
            goal_handle.publish_feedback(feedback)
            self._publish_internal_status({"active_goal": {
                "type": "route",
                "id": route["route_id"],
                "started_at": datetime.now(timezone.utc).isoformat(),
            }, "current_waypoint_index": idx})

            # PLANNING → MOVING
            nav_goal = self._build_nav_goal(wp)
            send_future = self._nav_client.send_goal_async(nav_goal)
            nav_handle = await send_future
            if not nav_handle.accepted:
                self._fsm.cancel()
                continue
            self._current_nav_handle = nav_handle
            self._fsm.goal_accepted()

            timeout_sec = float(wp.get("timeout_sec", 30))
            try:
                nav_result = await asyncio.wait_for(
                    nav_handle.get_result_async(), timeout=timeout_sec
                )
            except asyncio.TimeoutError:
                self.get_logger().warn(f"waypoint {wp['id']} timeout")
                self._fsm.cancel()
                continue

            if nav_result.status != GoalStatus.STATUS_SUCCEEDED:
                if self._fsm.state == RouteState.PAUSED:
                    # Pause caused cancel → loop iterates again with FSM.PLANNING
                    continue
                self._fsm.cancel()
                continue

            # MOVING → next state per task
            task = wp["task"]
            self._fsm.waypoint_reached(task=task)

            # Emit waypoint_reached event
            self._emit_waypoint_reached(route["route_id"], wp)

            # Handle WAITING / TTS
            if self._fsm.state == RouteState.WAITING:
                wait_sec = float(wp.get("wait_sec", 0))
                await asyncio.sleep(wait_sec)
                self._fsm.task_complete()
            elif self._fsm.state == RouteState.TTS:
                tts_msg = String()
                tts_msg.data = wp.get("tts_text", "")
                self._tts_pub.publish(tts_msg)
                await asyncio.sleep(0.5)  # let tts pipeline accept the message
                self._fsm.task_complete()

        if self._fsm.state == RouteState.SUCCEEDED:
            result.success = True
            result.waypoints_completed = len(waypoints)
            result.waypoints_total = len(waypoints)
            result.message = "completed"
            goal_handle.succeed()
        else:
            result.success = False
            result.waypoints_completed = self._fsm.current_waypoint_index
            result.waypoints_total = len(waypoints)
            result.message = "cancelled_or_failed"
            goal_handle.abort()
        return result

    def _emit_waypoint_reached(self, route_id: str, wp: dict) -> None:
        payload = {
            "route_id": route_id,
            "waypoint_id": wp["id"],
            "task": wp["task"],
            "pose": wp["pose"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        m = String()
        m.data = json.dumps(payload)
        self._waypoint_event_pub.publish(m)

    # === Services ===
    def _svc_pause(self, _req, resp):
        try:
            self._fsm.pause()
        except IllegalTransition as exc:
            resp.success = False
            resp.message = f"cannot_pause: {exc}"
            return resp
        # Cancel current Nav2 goal so DWB releases /cmd_vel_nav
        if self._current_nav_handle is not None:
            self._current_nav_handle.cancel_goal_async()
        self._pause_event.clear()
        resp.success = True
        resp.message = "paused"
        return resp

    def _svc_resume(self, _req, resp):
        try:
            self._fsm.resume()
        except IllegalTransition as exc:
            resp.success = False
            resp.message = f"cannot_resume: {exc}"
            return resp
        # Re-send same waypoint goal: simply unblock, loop will re-plan
        self._pause_event.set()
        resp.success = True
        resp.message = "resumed"
        return resp

    def _svc_cancel(self, _req, resp):
        try:
            self._fsm.cancel()
        except IllegalTransition:
            pass
        if self._current_nav_handle is not None:
            self._current_nav_handle.cancel_goal_async()
        self._pause_event.set()  # unblock so loop exits
        resp.success = True
        return resp


def main():
    rclpy.init()
    node = RouteRunnerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 解開 setup.py 第 4 個 entry**

```python
        "console_scripts": [
            "nav_action_server_node = nav_capability.nav_action_server_node:main",
            "log_pose_node = nav_capability.log_pose_node:main",
            "state_broadcaster_node = nav_capability.state_broadcaster_node:main",
            "route_runner_node = nav_capability.route_runner_node:main",
        ],
```

- [ ] **Step 3: 移除 nav_action_server_node 的 pause/resume/cancel stub**

route_runner_node 接管後，nav_action_server_node 的 stub 變成衝突。回 `nav_action_server_node.py` 把 Phase 6.2 加的 service 與 `_handle_pause/resume/cancel` 三個 method、`self._pause_state` 屬性全刪掉。

- [ ] **Step 4: colcon build + smoke**

```bash
colcon build --packages-select nav_capability
source install/setup.zsh
ros2 run nav_capability route_runner_node &
RR_PID=$!
sleep 2
ros2 action list | grep run_route
ros2 service list | grep -E "nav/(pause|resume|cancel)"
kill $RR_PID
```

Expected: `/nav/run_route` + 三個 service。

- [ ] **Step 5: Commit**

```bash
git add nav_capability/nav_capability/route_runner_node.py \
        nav_capability/nav_capability/nav_action_server_node.py \
        nav_capability/setup.py
git commit -m "feat(nav): route_runner_node — RunRoute action + pause/resume/cancel services + waypoint_reached event"
```

---

### Task 7.2 — Reactive_stop 整合：`enable_nav_pause=true` 時自動 call /nav/pause /nav/resume

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`

- [ ] **Step 1: 加 service client + 觸發邏輯**

在 `reactive_stop_node.py` import 區加：

```python
from std_srvs.srv import Trigger
```

在 `__init__` 加（既有 publisher 後）：

```python
        # Nav pause/resume client (used when enable_nav_pause=true)
        self._pause_client = self.create_client(Trigger, "/nav/pause")
        self._resume_client = self.create_client(Trigger, "/nav/resume")
        self._nav_paused = False
```

在 `_tick`（送出 cmd_vel 的方法）內，當 zone 從 normal 變 danger 且 `enable_nav_pause` 為 true，call pause；反之 call resume：

```python
    def _maybe_call_nav_pause(self, was_zone: str, now_zone: str) -> None:
        if not self._enable_nav_pause:
            return
        if was_zone != "danger" and now_zone == "danger" and not self._nav_paused:
            if self._pause_client.service_is_ready():
                self._pause_client.call_async(Trigger.Request())
                self._nav_paused = True
        elif was_zone == "danger" and now_zone != "danger" and self._nav_paused:
            if self._resume_client.service_is_ready():
                self._resume_client.call_async(Trigger.Request())
                self._nav_paused = False
```

在 zone transition 處呼叫 `self._maybe_call_nav_pause(prev_zone, new_zone)`。

- [ ] **Step 2: build + check tests still pass**

```bash
colcon build --packages-select go2_robot_sdk
source install/setup.zsh
python3 -m pytest go2_robot_sdk/test/test_reactive_stop_node.py -v
```

Expected: 全 pass（19+ cases）。

- [ ] **Step 3: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py
git commit -m "feat(nav): reactive_stop calls /nav/pause /nav/resume when enable_nav_pause=true"
```

---

## Phase 7 完成檢查

- [ ] Task 7.1 — route_runner_node + RunRoute action + pause/resume/cancel ✅
- [ ] Task 7.2 — reactive_stop 整合 nav pause/resume ✅

✅ Phase 7 通過 → 進 Phase 8。

---

## Phase 8 — Watchdogs（driver heartbeat / odom）

**Goal**: 把 spec §8 E5 的 watchdog 邏輯落實。AMCL covariance 與 RPLIDAR watchdog 已在前面 phase 內建。

### Task 8.1 — Driver heartbeat publisher（spec T1）

**Files:**
- Modify: `go2_robot_sdk/go2_robot_sdk/main.py`

> spec §13 / review #3：**只新增 status publisher，不改 RobotControlService 控制橋邏輯**。

- [ ] **Step 1: 在 driver 主節點加 heartbeat timer**

```python
# 在 go2_driver_node __init__ 末端：
from std_msgs.msg import Header
self._heartbeat_pub = self.create_publisher(Header, "/state/driver/heartbeat", 10)
self.create_timer(1.0, self._publish_heartbeat)

def _publish_heartbeat(self):
    h = Header()
    h.stamp = self.get_clock().now().to_msg()
    h.frame_id = "go2_driver"
    self._heartbeat_pub.publish(h)
```

- [ ] **Step 2: build + smoke**

Run: `colcon build --packages-select go2_robot_sdk && source install/setup.zsh`
Smoke: `ros2 topic list | grep driver/heartbeat`（連 Go2 後）

- [ ] **Step 3: Stage + commit**

Stage: `go2_robot_sdk/go2_robot_sdk/main.py`
Commit message: `feat(nav): driver heartbeat publisher /state/driver/heartbeat (T1)`

---

### Task 8.2 — `/odom` watchdog 在 `nav_action_server_node`（E5）

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1: 訂閱 /odom 並追蹤 last_seen**

```python
# 在 __init__ 加：
from nav_msgs.msg import Odometry
self._last_odom_time = 0.0
self.create_subscription(
    Odometry, "/odom", self._on_odom,
    QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT),
    callback_group=self._cb_group,
)

def _on_odom(self, _msg):
    self._last_odom_time = self.get_clock().now().nanoseconds / 1e9

def _odom_alive(self) -> bool:
    if self._last_odom_time == 0.0:
        return False
    now = self.get_clock().now().nanoseconds / 1e9
    return (now - self._last_odom_time) < 2.0
```

- [ ] **Step 2: 在 `_execute_relative` / `_execute_named` 起始加 odom check**

```python
if not self._odom_alive():
    goal_handle.abort()
    result = GotoRelative.Result()
    result.success = False
    result.message = "odom_lost_driver_disconnected"
    return result
```

(GotoNamed 同樣加)

- [ ] **Step 3: build + Stage + commit**

Run: `colcon build --packages-select nav_capability`
Stage: `nav_capability/nav_capability/nav_action_server_node.py`
Commit message: `feat(nav): /odom watchdog (E5) — abort actions when driver disconnected`

---

## Phase 8 完成檢查

- [ ] Task 8.1 — driver heartbeat ✅
- [ ] Task 8.2 — /odom watchdog ✅

> AMCL covariance 三段門檻 (E1) 已在 Phase 4.1 nav_action_server 內建；RPLIDAR watchdog (E4) 已在 Phase 6.1 state_broadcaster 內建。

✅ Phase 8 通過 → 進 Phase 9。

---

## Phase 9 — Launch + Tmux + send_relative_goal.py 改寫

**Goal**: 一鍵 launch 4 個 nav_capability node。Tmux 整合進 nav2-amcl demo。CLI 改 action client。

### Task 9.1 — `nav_capability.launch.py`

**Files:**
- Create: `nav_capability/launch/nav_capability.launch.py`

- [ ] **Step 1: Write launch file**

```python
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("nav_capability")
    default_named = os.path.join(pkg_share, "config", "named_poses", "sample.json")
    default_routes = os.path.join(pkg_share, "config", "routes")

    named_arg = DeclareLaunchArgument("named_poses_file", default_value=default_named)
    routes_arg = DeclareLaunchArgument("routes_dir", default_value=default_routes)
    map_id_arg = DeclareLaunchArgument("map_id", default_value="unknown_map")

    nav_action = Node(
        package="nav_capability", executable="nav_action_server_node",
        name="nav_action_server_node", output="screen",
        parameters=[{"named_poses_file": LaunchConfiguration("named_poses_file")}],
    )
    route_runner = Node(
        package="nav_capability", executable="route_runner_node",
        name="route_runner_node", output="screen",
        parameters=[{"routes_dir": LaunchConfiguration("routes_dir")}],
    )
    log_pose = Node(
        package="nav_capability", executable="log_pose_node",
        name="log_pose_node", output="screen",
        parameters=[{
            "named_poses_file": LaunchConfiguration("named_poses_file"),
            "routes_dir": LaunchConfiguration("routes_dir"),
            "map_id": LaunchConfiguration("map_id"),
        }],
    )
    state_bcast = Node(
        package="nav_capability", executable="state_broadcaster_node",
        name="state_broadcaster_node", output="screen",
    )

    return LaunchDescription([
        named_arg, routes_arg, map_id_arg,
        nav_action, route_runner, log_pose, state_bcast,
    ])
```

- [ ] **Step 2: build + smoke**

Build: `colcon build --packages-select nav_capability && source install/setup.zsh`
Smoke: `ros2 launch nav_capability nav_capability.launch.py`，檢查 4 nodes 起、4 actions、3 services、heartbeat ~1Hz。

- [ ] **Step 3: Stage + commit**

Stage: `nav_capability/launch/`
Commit message: `feat(nav): nav_capability.launch.py — boots all 4 nodes`

---

### Task 9.2 — 升級 `start_nav2_amcl_demo_tmux.sh`

**Files:**
- Modify: `scripts/start_nav2_amcl_demo_tmux.sh`

- [ ] **Step 1: 加兩個 window**

依既有 5-window pattern 加：

```bash
# Window 6: nav_capability
tmux new-window -t "$SESSION:6" -n "navcap"
tmux send-keys -t "$SESSION:6" \
    "cd ~/elder_and_dog && source install/setup.zsh && \
     ros2 launch nav_capability nav_capability.launch.py" C-m

# Window 7: 啟用 reactive_stop nav_pause（15s 後）
tmux new-window -t "$SESSION:7" -n "navpause-enable"
tmux send-keys -t "$SESSION:7" \
    "sleep 15 && ros2 param set /reactive_stop_node enable_nav_pause true && \
     echo 'nav_pause enabled'" C-m
```

- [ ] **Step 2: 語法檢查 + Stage + commit**

Run: `bash -n scripts/start_nav2_amcl_demo_tmux.sh`
Stage: `scripts/start_nav2_amcl_demo_tmux.sh`
Commit message: `feat(nav): tmux demo script adds nav_capability + reactive_stop nav_pause enable`

---

### Task 9.3 — `send_relative_goal.py` 改 action client

**Files:**
- Modify: `scripts/send_relative_goal.py`

- [ ] **Step 1: 重寫**

```python
#!/usr/bin/env python3
"""Send GotoRelative action."""
import argparse
import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from go2_interfaces.action import GotoRelative


class GotoRelativeClient(Node):
    def __init__(self):
        super().__init__("send_relative_goal_cli")
        self._client = ActionClient(self, GotoRelative, "/nav/goto_relative")

    def send(self, distance, yaw_offset, max_speed):
        if not self._client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("action server not available within 10s")
            return False
        goal = GotoRelative.Goal()
        goal.distance = distance
        goal.yaw_offset = yaw_offset
        goal.max_speed = max_speed
        send_future = self._client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        handle = send_future.result()
        if not handle.accepted:
            self.get_logger().error("goal rejected")
            return False
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result
        self.get_logger().info(
            f"result: success={result.success} message={result.message}"
        )
        return result.success


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--distance", type=float, required=True)
    parser.add_argument("--yaw-offset", type=float, default=0.0)
    parser.add_argument("--max-speed", type=float, default=0.5)
    args = parser.parse_args()
    rclpy.init()
    try:
        node = GotoRelativeClient()
        ok = node.send(args.distance, args.yaw_offset, args.max_speed)
        node.destroy_node()
        sys.exit(0 if ok else 1)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 語法 check + Stage + commit**

Run: `python3 -c "import ast; ast.parse(open('scripts/send_relative_goal.py').read())"`
Stage: `scripts/send_relative_goal.py`
Commit message: `feat(nav): send_relative_goal.py rewritten as GotoRelative action client`

---

## Phase 9 完成檢查

- [ ] Task 9.1 — nav_capability.launch.py ✅
- [ ] Task 9.2 — tmux script 整合 ✅
- [ ] Task 9.3 — send_relative_goal.py action client ✅

✅ Phase 9 通過 → 進 Phase 10（實機驗收）。

---

## Phase 10 — 實機 KPI 驗收（P0 8 項）

**Goal**: 在 Jetson + Go2 + 教室 / 客廳跑完 P0 8 項 KPI 全綠燈 = S2 完工。

> 前置：reactive_stop_node 啟動後（tmux Window 7 已自動執行）`enable_nav_pause=true`。
> 統一啟動：`bash scripts/start_nav2_amcl_demo_tmux.sh`。

### Task 10.1 — K1 + K2（goto_relative 0.5m × 5 + 0.8m × 5）

- [ ] **Step 1: 啟動 stack + 設 initial pose（Foxglove）**

- [ ] **Step 2: K1 (0.5m × 5)**

```bash
for i in 1 2 3 4 5; do
  echo "=== K1 run $i ==="
  python3 scripts/send_relative_goal.py --distance 0.5
  sleep 5
done
```

通過：≥ 4/5 success。

- [ ] **Step 3: K2 (0.8m × 5)**

```bash
for i in 1 2 3 4 5; do
  echo "=== K2 run $i ==="
  python3 scripts/send_relative_goal.py --distance 0.8
  sleep 8
done
```

通過：≥ 4/5 success。

- [ ] **Step 4: 紀錄 + 影片**

寫進 `docs/導航避障/research/2026-MM-DD-nav-capability-validation.md`。

---

### Task 10.2 — K4（run_route 3-waypoint × 3）

- [ ] **Step 1: 用 log_pose 記錄 3 waypoint**

把 Go2 推到 wp1 → 發 `log_pose name=wp1 task=normal`；
推到 wp2 → 發 `log_pose name=wp2 task=wait`；
推到 wp3 → 發 `log_pose name=wp3 task=tts`。

```bash
ros2 action send_goal /log_pose go2_interfaces/action/LogPose \
  "{name: 'wp1', log_target: 'route', route_id: 'k4_test', task_type: 'normal'}"
# wp2 / wp3 同樣
```

- [ ] **Step 2: 編輯 k4_test.json 補 wait_sec / tts_text**

wp2 加 `"wait_sec": 3`；wp3 加 `"tts_text": "我到了"`。

- [ ] **Step 3: K4 × 3**

```bash
for i in 1 2 3; do
  ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \
    "{route_id: 'k4_test', loop: false}"
  sleep 5
done
```

通過：3/3 全 succeeded。

---

### Task 10.3 — K5（Pause/Resume × 3）

- [ ] **Step 1: 跑 route 後人走進 0.6m**

```bash
ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \
  "{route_id: 'k4_test'}" &
sleep 5
# 人走到 Go2 前方 0.6m → 應立即停 + state=paused
sleep 5
# 人走開 → < 5s 內續行
```

- [ ] **Step 2: 觀察 /state/nav/status**

`ros2 topic echo /state/nav/status --once`
Expected: state 經過 moving → paused → moving，續行 < 5s。

通過：3/3 次成功。

---

### Task 10.4 — K7（Emergency lock × 3）

- [ ] **Step 1: 跑 route + emergency**

```bash
ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \
  "{route_id: 'k4_test'}" &
sleep 5
python3 nav_capability/scripts/emergency_stop.py engage
# Go2 應於 < 1s 停下
sleep 3
python3 nav_capability/scripts/emergency_stop.py release
```

通過：3/3 次 < 1s 停下。

---

### Task 10.5 — K8（mux 4 priorities 實機驗證）

- [ ] **Step 1: 啟動 nav stack 後跑 fake publisher tests**

```bash
bash scripts/start_nav2_amcl_demo_tmux.sh
sleep 10
python3 -m pytest nav_capability/test/integration/test_mux_priority.py -v
```

通過：4/4 cases pass。

---

### Task 10.6 — K9（state topic 不間斷 60s）

- [ ] **Step 1: 60s rate 驗收**

```bash
timeout 60 ros2 topic hz /state/nav/heartbeat   # ≥ 0.95 Hz
timeout 60 ros2 topic hz /state/nav/status      # ≥ 9 Hz
timeout 60 ros2 topic hz /state/nav/safety      # ≥ 9 Hz
```

通過：三條 topic 達到 rate threshold。

---

### Task 10.7 — K10（log_pose × 5 寫入讀回一致）

- [ ] **Step 1: log 5 個 pose**

```bash
for n in alpha beta gamma delta epsilon; do
  ros2 action send_goal /log_pose go2_interfaces/action/LogPose \
    "{name: '$n', log_target: 'named_poses'}"
  sleep 1
done
```

- [ ] **Step 2: 讀回比對**

```bash
cat $(ros2 param get /log_pose_node named_poses_file --hide-type)
```

通過：5/5 名稱在檔內，pose 數值一致。

---

## Phase 10 完成檢查（P0 KPI）

- [ ] K1 — goto_relative 0.5m × 5 ≥ 4/5 ✅
- [ ] K2 — goto_relative 0.8m × 5 ≥ 4/5 ✅
- [ ] K4 — run_route 3-waypoint × 3 全 succeeded ✅
- [ ] K5 — Pause/Resume × 3 全續行 ✅ ⭐
- [ ] K7 — Emergency lock × 3 全 < 1s ✅ ⭐
- [ ] K8 — twist_mux 4 層優先級 ✅ ⭐
- [ ] K9 — State topic ≥ rate threshold ✅ ⭐
- [ ] K10 — log_pose × 5 寫入讀回一致 ✅

P0 全綠燈 → S2 完工 → 進 5/13 demo 整合測試（buffer 1.5 天）。

---

## 全域完成 checklist

- [ ] **Phase 0 ✅ nav_capability minimal scaffold**（pkg.xml / setup.py / dirs，0.3 天）
- [ ] Phase 1 ✅ 地基層 (twist_mux 4 層 + reactive_stop publisher + emergency CLI + mux test)（1 天）
- [ ] **Phase 1.5 ✅ Nav2 launch wrapper**（navigation_remap.launch.py：controller→unsmoothed→smoother→cmd_vel_nav，0.5 天）
- [ ] Phase 2 ✅ go2_interfaces 4 actions + Cancel.srv + sample JSON（pkg scaffold 移到 Phase 0）（0.3 天）
- [ ] Phase 3 ✅ L1 unit tests (38 cases)（1 天）
- [ ] Phase 4 ✅ goto_relative action server（0.5 天）
- [ ] Phase 5 ✅ goto_named + log_pose（1 天）
- [ ] Phase 6 ✅ state broadcaster + service stubs（0.5 天）
- [ ] Phase 7 ✅ Route Runner + reactive_stop pause/resume（1.5 天）
- [ ] Phase 8 ✅ watchdogs (driver heartbeat + odom)（0.5 天）
- [ ] Phase 9 ✅ launch + tmux + CLI（0.5 天）
- [ ] Phase 10 ✅ 實機 KPI P0 全綠燈（1.5 天）

時程：~7 天淨工作（多了 Phase 0 + 1.5 共 0.8 天）。5/13 前 buffer 仍留 1-1.5 天給 demo 整合 + 修 bug + 場地建圖。

P1 KPI（K3 / K6 / K11）列為 5/13 後加分項，不阻塞主線。

---

## Spec 對應追溯

| Spec 章節 | Plan Phase | 對應 KPI |
|---|---|---|
| §3.1 A1 GotoRelative | Phase 4 | K1, K2 |
| §3.1 A2 GotoNamed | Phase 5.1 | K3 (P1) |
| §3.1 A3 RunRoute | Phase 7.1 | K4, K5, K6 |
| §3.1 A4 LogPose | Phase 5.2 | K10 |
| §3.2 services | Phase 6.2 + 7.1 | K5 |
| §3.3 waypoint_reached event | Phase 7.1 | (5/13 後給 interaction_executive 接) |
| §3.4 state topics | Phase 6.1 | K9 |
| §4 twist_mux 升級 | Phase 1.1 + 1.5 | K7, K8 |
| §5 Route JSON v2 | Phase 2.3 + 3.3 (validator) | — |
| §6 Named Poses | Phase 2.3 + 3.4 (store) | — |
| §7 Data Flow A/B/C | Phase 4 + 7 + 1.4 | K5, K7 |
| §8 Error Handling E1-E10 | Phase 4 (E1) + 8 (E5) + 7 (E3, E9) | — |
| §10 KPI P0 (8 items) | Phase 10 | K1, K2, K4, K5, K7, K8, K9, K10 |
| §10 KPI P1 (3 items) | （5/13 後）| K3, K6, K11 |

---

**Plan END**
