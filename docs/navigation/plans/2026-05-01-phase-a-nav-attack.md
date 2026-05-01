# PawAI Phase A: Navigation Attack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5/2-5/3 兩天攻破最大不確定性 — 修 nav_capability 兩個 critical bug、落地兩層 Capability Gate(Nav Gate + Depth Gate)、上機驗證兩條主線 nav skill(`nav_demo_point` 5/5 + `approach_person` 1 次 PASS),保證 Storyboard Scene 2 + Scene 7 可執行。

**Architecture:** 既有 `nav_capability` (goto_relative/goto_named action server + reactive_stop)+ `interaction_executive` (Brain MVS + SafetyLayer + SkillRegistry) 上加兩個 capability publisher node 與三段 Pre-action Validate;Brain 規則表加兩條新 skill trigger;Studio Trace Drawer 加兩個 Bool LED。**單一動作出口** — 所有 sport `/webrtc_req` 仍只能由 `interaction_executive_node` publish。

**Tech Stack:** ROS2 Humble + rclpy + Python 3.10 / pytest TDD / **Nav2 BT + AMCL + map_server**(runtime stack — map 由 cartographer 離線建立並存 pbstream/yaml,**slam_toolbox 在本硬體永久棄用**;5/12 demo 不跑 SLAM,只跑 AMCL 載入既有 map)/ RealSense D435 + rplidar_ros2 / Brain MVS dataclasses(SkillContract / SkillPlan / SkillStep / WorldState)。

**Spec:** `docs/superpowers/specs/2026-05-01-pawai-11day-sprint-design.md` §6 (Safety Gate) + §7 (Phase A) + §12 (Stop-loss).

---

## Execution Environment(WSL ↔ Jetson 邊界)

> **WSL = source of truth for code edits + 純 Python unit test(用 Mock 不啟 rclpy)。**
> **Jetson(`jetson-nano` Tailscale 100.83.109.89,repo path `~/elder_and_dog`)= ROS2 runtime + colcon build + 上機 validation 唯一執行端。**

### 工作流程(每個 task 通用)

1. **WSL 端**:編輯 source(`/home/roy422/newLife/elder_and_dog`)+ 跑純 Python unit test(`pytest -v` for tests using `unittest.mock` only;不需 `rclpy.init()`)
2. **Sync to Jetson**:`bash scripts/sync_to_jetson.sh`(或 rsync,**注意 `--exclude build/install/log`**;一次同步 = `~/sync once`)
3. **Jetson 端**(透過 ssh):
   - 任何 `colcon build` / `ros2 run` / `ros2 topic` / `ros2 action` / `ros2 service` / `ros2 launch` 指令
   - 任何 spin-based pytest(用 rclpy spin、需 ROS2 daemon)
   - 上機 smoke test 與 5/5 PASS 驗收

### 範例指令樣板

```bash
# 純 unit test(WSL OK)
pytest interaction_executive/test/test_world_state_capabilities.py -v

# colcon build(必須在 Jetson)
ssh jetson-nano "cd ~/elder_and_dog && \
    source /opt/ros/humble/setup.zsh && \
    colcon build --packages-select nav_capability && \
    source install/setup.zsh"

# 上機 ROS2 cmd(必須在 Jetson)
ssh jetson-nano "cd ~/elder_and_dog && \
    source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
    ros2 topic echo /capability/nav_ready --once"

# tmux demo stack(必須在 Jetson)
ssh -t jetson-nano "cd ~/elder_and_dog && bash scripts/start_nav_capability_demo_tmux.sh"
```

> **全域規則**:本 plan 後續**所有 bash code blocks 預設在 Jetson 跑**(透過上述 ssh prefix)。**例外用 `# [WSL OK]` 標於 block 第一行**,通常是:
> - 純檔案操作(grep / ls / find / cat / git)
> - 純 mock-based pytest(test 檔內 import `unittest.mock`、不 `rclpy.init()`)
>
> 沒有 `[WSL OK]` 標的 bash block 一律視為 **`[JETSON ONLY]`**:`colcon` / `ros2 run|topic|action|service|launch` / 含 `rclpy.init()` 的 pytest / `bash scripts/start_*_tmux.sh`(tmux launchers 啟 ROS2 stack)。
>
> Worker copy-paste 時:`[JETSON ONLY]` block 改成 `ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && <command>"`。

---

## File Structure

### 新建檔案
- `nav_capability/nav_capability/capability_publisher_node.py` — 聚合 Nav2 lifecycle + AMCL covariance + local costmap **health(last_seen ≤ 2s)**,publish `/capability/nav_ready` (Bool);**target-cell cost 不在此 gate**(skill dispatch 時驗)
- `go2_robot_sdk/go2_robot_sdk/depth_safety_node.py` — 訂 D435 `/camera/camera/aligned_depth_to_color/image_raw`(專案 double namespace 慣例;ROS parameter `depth_topic` 可覆寫),計算 ROI 前方 1m 內最近障礙,publish `/capability/depth_clear` (Bool)
- `nav_capability/test/test_capability_publisher_node.py` — TDD 測試
- `go2_robot_sdk/test/test_depth_safety_node.py` — TDD 測試
- `interaction_executive/test/test_safety_gate_three_tier.py` — 三段 Pre-action Validate 測試
- `interaction_executive/test/test_nav_demo_point_skill.py` — skill registry + brain rule 測試
- `interaction_executive/test/test_approach_person_skill.py` — skill registry + brain rule 測試
- `scripts/k1_regression.sh` — BUG #1 K1 baseline 5/5 重跑 wrapper

### 修改檔案
- `nav_capability/nav_capability/nav_action_server_node.py` — **訂 `/state/nav/paused` (latched Bool) 並 cancel cached Nav2 NavigateToPose goal handle**(BUG #2 修法,不直接 gate cmd_vel)
- `nav_capability/nav_capability/route_runner_node.py` — `_svc_pause` / `_svc_resume` **無條件 publish `/state/nav/paused`**(global pause state,不依賴 route FSM 是否能 cancel;BUG #2 修法核心)
- `nav_capability/nav_capability/route_runner_node.py`(或相關)— K2-lite WP_n=start 短路修(BUG #4,先 investigate 找 root cause)
- `interaction_executive/interaction_executive/skill_contract.py` — 新增 `nav_demo_point` + `approach_person` SkillContract
- `interaction_executive/interaction_executive/brain_node.py` — 新增兩條 rule:`speech_nav_demo` + `face_wave_approach`
- `interaction_executive/interaction_executive/safety_layer.py` — `validate()` 擴三段(NAV / high-risk MOTION / low-risk social MOTION)
- `interaction_executive/interaction_executive/world_state.py` — 訂 `/capability/nav_ready` + `/capability/depth_clear` 進 snapshot
- `interaction_executive/launch/interaction_executive.launch.py` — include 兩個新 capability node
- `pawai-studio/frontend/src/components/chat/skill-trace-drawer.tsx` — 加 2 個 Bool LED(Nav Gate / Depth Gate)

---

## Task 1: 環境驗證 + 既有架構確認

**Files:**
- Read: `nav_capability/nav_capability/nav_action_server_node.py`
- Read: `interaction_executive/interaction_executive/safety_layer.py`
- Read: `interaction_executive/interaction_executive/world_state.py`

- [ ] **Step 1: 確認 Brain MVS topic 與 dataclass 名稱**

```bash
# [WSL OK] 純檔案 grep
grep -n "SafetyValidationResult\|class WorldState\|snapshot()" interaction_executive/interaction_executive/safety_layer.py interaction_executive/interaction_executive/world_state.py
```
Expected:看到 `WorldState.snapshot()` 回傳的 dataclass 欄位名(會用在 Task 7)

- [ ] **Step 2: 確認 nav action server 現有結構**

```bash
# [WSL OK] 純檔案 grep
grep -n "ActionServer\|create_subscription\|self\." nav_capability/nav_capability/nav_action_server_node.py | head -40
```
Expected:看到 `goto_relative` action handler 的進入點,大致 line ~200 左右

- [ ] **Step 3: 確認 K2-lite WP_n=start 在哪邊判定**

```bash
# [WSL OK] 純檔案 grep
grep -rn "K2-lite\|WP.*start\|distance.*tolerance\|xy_goal_tolerance" nav_capability/ go2_robot_sdk/config/nav2_params.yaml docs/導航避障/ | head -20
```
記錄 BUG #4 root cause 候選位置給 Task 3 使用

- [ ] **Step 4: 確認 D435 depth topic name**

```bash
ros2 topic list 2>/dev/null | grep -i depth || grep -rn "aligned_depth\|depth_to_color" go2_robot_sdk/ | head -10
```
記錄正確 topic name(會用在 Task 6),專案標準是 `/camera/camera/aligned_depth_to_color/image_raw`(double namespace,per `docs/architecture/contracts/interaction_contract.md:895` + `docs/thesis/背景知識/4-10-D435.md:55`)

- [ ] **Step 5: 不 commit,純 reconnaissance**

---

## Task 2: BUG #2 — nav_action_server 響應 /nav/pause via 共享 state topic(TDD)

**問題澄清**:
- `/nav/pause` 與 `/nav/resume` 是 `std_srvs/Trigger` **service**(不是 topic),已在 `route_runner_node.py:111-117` 註冊
- `reactive_stop_node.py:99-100` 偵測障礙時 call 這兩個 service
- service handler 只 cancel `route_runner` 自己的 Nav2 goal,**不會通知 `nav_action_server`**
- `nav_action_server_node.py` 走 Nav2 `NavigateToPose` action client,**不直接 publish `/cmd_vel`**(Nav2 自己控速),所以「gate cmd_vel」approach 無效

**修法**(共用 cancel/resume pattern):
1. `route_runner_node` 的 `_svc_pause` / `_svc_resume` 處理器**額外 publish `/state/nav/paused` (std_msgs/Bool, latched TRANSIENT_LOCAL)** 通知系統
2. `nav_action_server_node` **訂 `/state/nav/paused`**;paused=true 時 **cancel 自己 cache 的 Nav2 NavigateToPose goal handle**;paused=false 不自動 re-send(讓 caller 重發,v0 簡化)

**Files:**
- Modify: `nav_capability/nav_capability/route_runner_node.py:111-117 + _svc_pause / _svc_resume handler`
- Modify: `nav_capability/nav_capability/nav_action_server_node.py:42-90 (init) + send_goal 後加 active goal handle cache + on_paused callback`
- Test: `nav_capability/test/test_nav_pause_state_topic.py` (NEW)
- Test: `nav_capability/test/test_nav_action_server_pause_response.py` (NEW)

- [ ] **Step 1: 寫 route_runner state-publish 失敗測試**

```python
# nav_capability/test/test_nav_pause_state_topic.py
"""route_runner 的 /nav/pause + /nav/resume service 必須額外 publish
/state/nav/paused (std_msgs/Bool, latched) 讓其他 nav node 共享 pause state。"""
import pytest
import rclpy
from std_msgs.msg import Bool
from std_srvs.srv import Trigger
from nav_capability.route_runner_node import RouteRunnerNode


@pytest.fixture
def rclpy_ctx():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_state_topic_published_on_pause(rclpy_ctx):
    rr = RouteRunnerNode()
    received: list[bool] = []
    rr.create_subscription(Bool, "/state/nav/paused",
                            lambda m: received.append(m.data), 10)
    # 觸發 pause service
    rr._svc_pause(Trigger.Request(), Trigger.Response())
    # spin 收 latched
    end = rclpy.get_default_context().now() if False else None
    for _ in range(10):
        rclpy.spin_once(rr, timeout_sec=0.05)
    assert True in received, "expected paused=true on /state/nav/paused"
    rr.destroy_node()


def test_state_topic_published_on_resume(rclpy_ctx):
    rr = RouteRunnerNode()
    received: list[bool] = []
    rr.create_subscription(Bool, "/state/nav/paused",
                            lambda m: received.append(m.data), 10)
    rr._svc_resume(Trigger.Request(), Trigger.Response())
    for _ in range(10):
        rclpy.spin_once(rr, timeout_sec=0.05)
    assert False in received, "expected paused=false on /state/nav/paused"
    rr.destroy_node()
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
cd /home/roy422/newLife/elder_and_dog
source /opt/ros/humble/setup.zsh && source install/setup.zsh
pytest nav_capability/test/test_nav_pause_state_topic.py -v
```
Expected: `assert True/False in []` 因為 publisher 未實作

- [ ] **Step 3: route_runner 加 latched state publisher(無條件 publish,不依賴 FSM)**

> **關鍵修法**:`/state/nav/paused` 是 **global pause state**,**必須在 service handler 第一行就 publish**,不能等 route FSM cancel 成功才發。否則 goto_relative 跑而 route_runner idle 時,reactive_stop call /nav/pause → route_runner 內部 `cannot_pause` → state topic 永遠不發,nav_action_server 收不到 → goto_relative 不會取消。

```python
# nav_capability/nav_capability/route_runner_node.py
# 在 imports 段(~line 33 附近):
from rclpy.qos import QoSProfile, DurabilityPolicy

# 在 RouteRunnerNode.__init__ 內(在 services 註冊之前):
_LATCHED_QOS = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
self._paused_state_pub = self.create_publisher(
    Bool, "/state/nav/paused", _LATCHED_QOS,
)
# 啟動時 publish 初始 false,新 subscriber 接得到 latched
init_msg = Bool(); init_msg.data = False
self._paused_state_pub.publish(init_msg)

# 修改 _svc_pause:**第一行就 publish state**,然後才嘗試 route 內部 cancel
def _svc_pause(self, req, resp):
    # ① Global pause state 永遠 publish(這是給 nav_action_server 等其他訂閱者用的)
    state_msg = Bool(); state_msg.data = True
    self._paused_state_pub.publish(state_msg)
    # ② 試著 cancel route_runner 自己的 nav goal(可能因 FSM idle 而 no-op,沒關係)
    try:
        # ... 既有 route FSM cancel logic ...
        resp.success = True
        resp.message = "paused"
    except Exception as exc:  # noqa: BLE001
        resp.success = True  # global pause 已生效,即使 route FSM 沒事可做
        resp.message = f"global pause published; route idle ({exc})"
    return resp

# 同理 _svc_resume:
def _svc_resume(self, req, resp):
    state_msg = Bool(); state_msg.data = False
    self._paused_state_pub.publish(state_msg)
    try:
        # ... 既有 route FSM resume logic ...
        resp.success = True
        resp.message = "resumed"
    except Exception as exc:  # noqa: BLE001
        resp.success = True
        resp.message = f"global resume published; route idle ({exc})"
    return resp
```

- [ ] **Step 4: 跑測試 pass**

```bash
colcon build --packages-select nav_capability && source install/setup.zsh
pytest nav_capability/test/test_nav_pause_state_topic.py -v
```
Expected:2 PASS

- [ ] **Step 5: 寫 nav_action_server pause 響應失敗測試**

> **Note**:`node.subscriptions` 不是 rclpy 公開 stable API,測 init 是否註冊訂閱用 `unittest.mock.patch.object(Node, 'create_subscription')` 攔截 + 檢查 args 比較可靠。`_on_nav_paused` callback 行為直接 invoke 測。

```python
# nav_capability/test/test_nav_action_server_pause_response.py
"""nav_action_server 訂 /state/nav/paused;paused=true 時 cancel cached Nav2 goal handle。"""
from unittest.mock import MagicMock, patch
import pytest
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from nav_capability.nav_action_server_node import NavActionServerNode


@pytest.fixture
def rclpy_ctx():
    rclpy.init()
    yield
    rclpy.shutdown()


def test_subscribes_to_nav_paused_state(rclpy_ctx):
    """攔截 Node.create_subscription,確認 init 期間 /state/nav/paused 有被 subscribe"""
    original = Node.create_subscription
    captured: list[str] = []

    def spy(self, msg_type, topic, callback, qos, **kwargs):
        captured.append(topic)
        return original(self, msg_type, topic, callback, qos, **kwargs)

    with patch.object(Node, "create_subscription", spy):
        node = NavActionServerNode()
    assert "/state/nav/paused" in captured
    node.destroy_node()


def test_pause_cancels_active_nav2_goal_handle(rclpy_ctx):
    node = NavActionServerNode()
    fake_handle = MagicMock()
    fake_handle.cancel_goal_async = MagicMock(return_value=MagicMock())
    node._active_nav2_goal_handle = fake_handle
    msg = Bool(); msg.data = True
    node._on_nav_paused(msg)
    fake_handle.cancel_goal_async.assert_called_once()
    node.destroy_node()


def test_resume_does_not_call_cancel(rclpy_ctx):
    node = NavActionServerNode()
    fake_handle = MagicMock()
    fake_handle.cancel_goal_async = MagicMock()
    node._active_nav2_goal_handle = fake_handle
    msg = Bool(); msg.data = False
    node._on_nav_paused(msg)
    fake_handle.cancel_goal_async.assert_not_called()
    node.destroy_node()
```

- [ ] **Step 6: 跑測試確認 fail**

```bash
pytest nav_capability/test/test_nav_action_server_pause_response.py -v
```
Expected: `AssertionError: '/state/nav/paused' not in ...` 或 `AttributeError: _on_nav_paused`

- [ ] **Step 7: nav_action_server 加 subscriber + cache active goal handle(對齊既有 async/await flow)**

> **實際既有結構**(grep 過 `nav_action_server_node.py` 確認):
> - **action client 屬性是 `self._nav_client`**(line 79),不是 `_nav2_client`
> - 真正執行的 inner 函式是 `_execute_relative_inner`(line 194)與 `_execute_named_inner`(line 332);outer `_execute_relative`/`_execute_named` 只是 try/except wrapper
> - send goal pattern(line 278-280):
>   ```python
>   send_future = self._nav_client.send_goal_async(nav_goal)
>   nav_handle = await send_future
>   if not nav_handle.accepted: ... return
>   ```
> - 既有 cancel 機制:`while not nav_result_future.done()` 內檢查 `goal_handle.is_cancel_requested`,call `await nav_handle.cancel_goal_async()`(line ~290)
>
> **修法**:**不要改成 `add_done_callback`** — 既有 async/await + 輪詢已經有 cancel 支援。只要在 await accept 後 cache handle,讓 `_on_nav_paused` callback 也能 call `cancel_goal_async()`,並在 inner 函式末端 try/finally 清空 cache。

```python
# nav_capability/nav_capability/nav_action_server_node.py

# imports 段(~line 16 附近):
from std_msgs.msg import Bool
from rclpy.qos import QoSProfile, DurabilityPolicy

# 在 NavActionServerNode.__init__(class line 42)加:
_LATCHED_QOS = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
self._active_nav2_goal_handle = None  # 由 _execute_*_inner cache;finally 清空
self.create_subscription(
    Bool, "/state/nav/paused", self._on_nav_paused, _LATCHED_QOS,
)

# 修改 _execute_relative_inner(line 194):
#   既有 line 278-280:
#     send_future = self._nav_client.send_goal_async(nav_goal)
#     nav_handle = await send_future
#     if not nav_handle.accepted: ...
#
#   改成:在 accepted 檢查後 cache handle,把後續輪詢/result 處理整段包進 try/finally。

async def _execute_relative_inner(self, goal_handle):
    # ... 既有 setup / pose 計算 / nav_goal 建立(line 194-271)...

    if not self._nav_client.wait_for_server(timeout_sec=5.0):
        goal_handle.abort()
        result.success = False
        result.message = "nav2_unavailable"
        return result

    send_future = self._nav_client.send_goal_async(nav_goal)
    nav_handle = await send_future
    if not nav_handle.accepted:
        goal_handle.abort()
        result.success = False
        result.message = "nav2_rejected_goal"
        return result

    # NEW: cache accepted handle 讓 _on_nav_paused 可 cancel(障礙觸發 reactive_stop)
    self._active_nav2_goal_handle = nav_handle
    try:
        # 既有輪詢 + cancel propagation(line ~289-end of inner)整段保留不動:
        nav_result_future = nav_handle.get_result_async()
        while not nav_result_future.done():
            if goal_handle.is_cancel_requested:
                self.get_logger().info("client cancel requested; cancelling Nav2 goal")
                await nav_handle.cancel_goal_async()
                nav_result = await nav_result_future
                # ... 既有 cancel 處理 ...
            # ... 既有輪詢 sleep / feedback ...
        # ... 既有 result 處理 / fill action result ...
        return result
    finally:
        # 清掉 cache(SUCCEEDED / CANCELED / ABORTED / exception 都會走到這)
        self._active_nav2_goal_handle = None
```

**同樣 pattern 套到 `_execute_named_inner`(line 332)** — 既有 line 440 已是 `nav_handle = await self._nav_client.send_goal_async(nav_goal)`,只要在 accepted 檢查後加 cache + 用 try/finally 包後續輪詢/result 處理。

加 `_on_nav_paused` callback(class method):

```python
def _on_nav_paused(self, msg: Bool) -> None:
    """obstacle pause → cancel cached Nav2 goal handle;resume → no-op(caller 重發)。

    `cancel_goal_async()` 會讓 await 中的 `nav_result_future` 結束(status=CANCELED),
    inner 函式的 finally 自動清空 `_active_nav2_goal_handle`。"""
    if msg.data and self._active_nav2_goal_handle is not None:
        self.get_logger().info("/state/nav/paused=true → cancel active Nav2 goal")
        self._active_nav2_goal_handle.cancel_goal_async()
    elif not msg.data:
        self.get_logger().debug("/state/nav/paused=false (resume signal received)")
```

- [ ] **Step 8: 跑測試 pass**

```bash
colcon build --packages-select nav_capability && source install/setup.zsh
pytest nav_capability/test/ -v
```
Expected:全 PASS(含既有 nav test)

- [ ] **Step 9: 上機冒煙 + Commit**

```bash
ros2 run nav_capability route_runner_node &
ros2 run nav_capability nav_action_server_node &
ros2 service call /nav/pause std_srvs/srv/Trigger
ros2 topic echo /state/nav/paused --once  # 應 data: true
ros2 service call /nav/resume std_srvs/srv/Trigger
ros2 topic echo /state/nav/paused --once  # 應 data: false
```

```bash
git add nav_capability/nav_capability/route_runner_node.py \
        nav_capability/nav_capability/nav_action_server_node.py \
        nav_capability/test/test_nav_pause_state_topic.py \
        nav_capability/test/test_nav_action_server_pause_response.py
git commit -m "fix(nav): BUG #2 — share /nav/pause via /state/nav/paused topic so nav_action_server cancels Nav2 goal on obstacle"
```

---

## Task 3: BUG #4 — K2-lite WP_n=start 短路 investigate + fix

**Files:**
- Investigate: `nav_capability/nav_capability/route_runner_node.py` 或 `nav_action_server_node.py` 的 goal 距離判定
- Modify: 找到的位置
- Test: `nav_capability/test/test_wp_start_short_circuit.py` (NEW)

- [ ] **Step 1: 找 root cause**

```bash
# [WSL OK] 純檔案 grep
grep -rn "xy_goal_tolerance\|goal_pose\|current_pose\|distance.*tolerance\|reach.*goal" nav_capability/ | head -30
grep -rn "compute_path\|set_goal\|nav_to_pose" nav_capability/ | head -30
```
記錄:K2-lite 是 BT (behavior tree) 內部判定還是 nav_capability 自己判定?如果是 BT 內部(`xy_goal_tolerance` 從 `nav2_params.yaml`),修法是參數調整;如果是 nav_capability 自己,修法是程式碼。從 spec §12 描述「BT 內部 goal_pose ≈ current_pose 直接 SUCCEEDED」推測是 BT 行為。

- [ ] **Step 2: 寫驗收測試(不論 root cause 在哪)**

```python
# nav_capability/test/test_wp_start_short_circuit.py
"""BUG #4: K2-lite 路線當 WP_n 與當前位置距離 < tolerance 時不應直接 SUCCEEDED,
需要至少強制 yaw 變化 or skip 該 WP 進入下一個。"""
import pytest
import math
from nav_capability.route_runner_node import _should_skip_waypoint

def test_close_waypoint_with_same_yaw_should_skip():
    """距離 0.10m + yaw 相同 → 應該 skip(或產 yaw-only goal)"""
    current = (0.0, 0.0, 0.0)
    waypoint = (0.05, 0.05, 0.0)
    skip, reason = _should_skip_waypoint(current, waypoint, xy_tol=0.15, yaw_tol=0.1)
    assert skip is True
    assert "too close" in reason.lower() or "skip" in reason.lower()

def test_close_waypoint_with_different_yaw_should_not_skip():
    """距離很近但 yaw 大不同 → 不 skip(yaw-only 動作仍有意義)"""
    current = (0.0, 0.0, 0.0)
    waypoint = (0.05, 0.05, math.pi)
    skip, _ = _should_skip_waypoint(current, waypoint, xy_tol=0.15, yaw_tol=0.1)
    assert skip is False

def test_distant_waypoint_normal():
    """正常距離 → 不 skip"""
    current = (0.0, 0.0, 0.0)
    waypoint = (1.0, 0.0, 0.0)
    skip, _ = _should_skip_waypoint(current, waypoint, xy_tol=0.15, yaw_tol=0.1)
    assert skip is False
```

- [ ] **Step 3: 跑測試確認 fail**

```bash
pytest nav_capability/test/test_wp_start_short_circuit.py -v
```
Expected:ImportError or AttributeError 因 `_should_skip_waypoint` 不存在

- [ ] **Step 4: 在 `route_runner_node.py` 加 helper + 在 send_goal 前呼叫**

```python
# nav_capability/nav_capability/route_runner_node.py
import math

def _should_skip_waypoint(
    current: tuple[float, float, float],
    waypoint: tuple[float, float, float],
    xy_tol: float = 0.15,
    yaw_tol: float = 0.1,
) -> tuple[bool, str]:
    """BUG #4 fix — close-and-same-yaw 直接 BT SUCCEEDED 會讓 Go2 不動。
    回傳 (skip, reason)。skip=True 時上層應該跳到下一個 waypoint。"""
    dx = waypoint[0] - current[0]
    dy = waypoint[1] - current[1]
    dist = math.hypot(dx, dy)
    dyaw = abs(math.atan2(math.sin(waypoint[2] - current[2]),
                          math.cos(waypoint[2] - current[2])))
    if dist < xy_tol and dyaw < yaw_tol:
        return True, f"too close (dist={dist:.3f}m, dyaw={dyaw:.3f}rad)"
    return False, ""
```

在 `RouteRunnerNode` 的 send_goal 處(grep `send_goal` / `nav_to_pose`)加 guard:

```python
# 在送 goal 之前
skip, reason = _should_skip_waypoint(current_pose, next_wp, xy_tol=0.15)
if skip:
    self.get_logger().info(f"BUG #4 guard: skip WP {idx} — {reason}")
    self._advance_to_next_waypoint()
    return  # 不送 goal,進下一個 WP
```

- [ ] **Step 5: 跑測試 pass**

```bash
pytest nav_capability/test/test_wp_start_short_circuit.py -v
```
Expected:3 PASS

- [ ] **Step 6: Commit**

```bash
git add nav_capability/nav_capability/route_runner_node.py nav_capability/test/test_wp_start_short_circuit.py
git commit -m "fix(nav): BUG #4 — skip too-close-and-same-yaw waypoints to prevent BT SUCCEEDED short-circuit"
```

---

## Task 4: BUG #1 K1 baseline 5/5 regression 腳本

**Files:**
- Create: `scripts/k1_regression.sh`

- [ ] **Step 1: 確認 K1 baseline 跑法**

```bash
ls scripts/start_nav_capability_demo_tmux.sh scripts/start_reactive_stop_tmux.sh 2>&1
cat docs/導航避障/research/2026-04-30* 2>/dev/null | head -30 || ls docs/導航避障/research/ | tail -10
```
參考最近的 K1 PASS 紀錄(commit `42cc478` `docs(nav): K1 baseline 5/5 PASS`)

- [ ] **Step 2: 寫腳本**

```bash
# scripts/k1_regression.sh
#!/usr/bin/env bash
# BUG #1 / yaw=π mount fix 迴歸:K1 baseline 5/5(5 個直線 1.0m goal 全成功)
set -euo pipefail
echo "[K1 regression] 假設 nav_capability_demo_tmux 已啟動 (foxglove + AMCL + nav2 + reactive_stop)"
echo "[K1 regression] 也假設 /initialpose 已在 Foxglove/RViz 設好"
PASS=0
FAIL=0
for i in 1 2 3 4 5; do
    echo "[K1 regression] Round $i/5"
    ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
        "{distance: 1.0, yaw_offset: 0.0, max_speed: 0.5}" --feedback 2>&1 | tee /tmp/k1_$i.log
    if grep -q "STATUS_SUCCEEDED" /tmp/k1_$i.log; then
        PASS=$((PASS+1))
        echo "  PASS"
    else
        FAIL=$((FAIL+1))
        echo "  FAIL"
    fi
    sleep 2
done
echo "==============="
echo "K1 baseline: $PASS/5 PASS, $FAIL/5 FAIL"
[[ $PASS -eq 5 ]] && exit 0 || exit 1
```

- [ ] **Step 3: chmod + 跑(需上機環境)**

```bash
chmod +x scripts/k1_regression.sh
bash scripts/start_nav_capability_demo_tmux.sh  # 在另一 terminal/tmux
# 等 50s lifecycle active + 在 Foxglove 設 initialpose
bash scripts/k1_regression.sh
```
Expected:5/5 PASS(若不過,先回 Task 2/3 確認 BUG #2/#4 沒回退)

- [ ] **Step 4: Commit 腳本(實機驗證結果記錄到 daily log)**

```bash
git add scripts/k1_regression.sh
git commit -m "test(nav): add K1 baseline 5/5 regression script"
```

---

## Task 5: capability_publisher_node — Nav Gate(TDD)

**Scope 澄清(Phase A v0)**:
Nav Gate publisher 是「**通用 health gate**」,不知道任何特定 goal/target 的存在。三個 sub-condition:
1. **Nav2 lifecycle = active**(BT navigator 啟動)
2. **AMCL covariance < 0.20**(定位收斂)
3. **Local costmap healthy**(`/local_costmap/costmap` 在最近 N 秒內有 update)

**「目標 cell cost < threshold」這條件不在 Nav Gate publisher 裡** — 因為通用 publisher 沒有當前 goal 的概念。target-cell 驗證應該在 **skill dispatch 時**(`approach_person` / `nav_demo_point` 算出 goal pose 後)直接查 costmap。Phase A 先把這個延後,5/12 dry run 若沒問題就保留;若有 false-positive,Phase B 補。

**Files:**
- Create: `nav_capability/nav_capability/capability_publisher_node.py`
- Create: `nav_capability/test/test_capability_publisher_node.py`
- Modify: `nav_capability/setup.py` (entry_point)
- Modify: `scripts/start_nav_capability_demo_tmux.sh`(Task 11)include 此 node

- [ ] **Step 1: 寫失敗測試**

```python
# nav_capability/test/test_capability_publisher_node.py
"""Nav Gate publisher 聚合 Nav2 lifecycle + AMCL covariance + local costmap health
成 /capability/nav_ready (Bool)。target-cell cost 不在此 gate(由 skill dispatch 時驗)。"""
import pytest
from nav_capability.capability_publisher_node import (
    is_nav2_active, amcl_converged, costmap_recent, NavGate,
)

def test_amcl_converged_low_cov():
    cov = [0.0]*36
    cov[0] = 0.05; cov[7] = 0.05; cov[35] = 0.05
    assert amcl_converged(cov, threshold=0.20) is True

def test_amcl_not_converged_high_cov():
    cov = [0.0]*36
    cov[0] = 0.30
    assert amcl_converged(cov, threshold=0.20) is False

def test_costmap_recent_within_window():
    """costmap last_seen 在 2 秒內 → healthy"""
    assert costmap_recent(seconds_since_last=1.0, max_staleness_sec=2.0) is True

def test_costmap_stale_beyond_window():
    assert costmap_recent(seconds_since_last=5.0, max_staleness_sec=2.0) is False

def test_costmap_never_received():
    assert costmap_recent(seconds_since_last=None, max_staleness_sec=2.0) is False

def test_is_nav2_active_state_3():
    assert is_nav2_active(3) is True  # lifecycle ACTIVE

def test_is_nav2_inactive_other_states():
    assert is_nav2_active(2) is False  # INACTIVE
    assert is_nav2_active(0) is False  # UNKNOWN

def test_nav_gate_all_true():
    gate = NavGate()
    gate.nav2_active = True
    gate.amcl_cov_max = 0.10
    gate.costmap_seconds_since_last = 0.5
    assert gate.compute() is True

def test_nav_gate_amcl_fail():
    gate = NavGate()
    gate.nav2_active = True
    gate.amcl_cov_max = 0.50
    gate.costmap_seconds_since_last = 0.5
    assert gate.compute() is False

def test_nav_gate_costmap_stale():
    gate = NavGate()
    gate.nav2_active = True
    gate.amcl_cov_max = 0.10
    gate.costmap_seconds_since_last = 10.0
    assert gate.compute() is False
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
pytest nav_capability/test/test_capability_publisher_node.py -v
```
Expected:ImportError(module 不存在)

- [ ] **Step 3: 實作 publisher node**

```python
# nav_capability/nav_capability/capability_publisher_node.py
"""Nav Gate publisher — 對應 spec §6.1 Nav Gate。

聚合 Nav2 lifecycle + AMCL covariance + local costmap health,
publish /capability/nav_ready (std_msgs/Bool, 5 Hz)。

Note: target-cell cost 驗證不在這個通用 publisher 裡 — 通用 gate 不知道
specific goal pose。Skill dispatch 時(approach_person / nav_demo_point 算出
goal pose 後)直接查 costmap 算 target-cell cost,作為 per-goal validation。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid


def amcl_converged(cov: list[float], threshold: float = 0.20) -> bool:
    """AMCL pose covariance 6x6 (x,y,_,_,_,yaw)。x/y/yaw 對角元 < threshold 算收斂。"""
    if len(cov) < 36:
        return False
    return cov[0] < threshold and cov[7] < threshold and cov[35] < threshold


def costmap_recent(seconds_since_last: Optional[float],
                    max_staleness_sec: float = 2.0) -> bool:
    """Local costmap 在 max_staleness_sec 秒內有 update 算 healthy。None = 從未收到。"""
    if seconds_since_last is None:
        return False
    return seconds_since_last <= max_staleness_sec


def is_nav2_active(state: int) -> bool:
    """Nav2 lifecycle state 3 = ACTIVE (per lifecycle_msgs/msg/State)。"""
    return state == 3


@dataclass
class NavGate:
    nav2_active: bool = False
    amcl_cov_max: float = 999.0
    costmap_seconds_since_last: Optional[float] = None

    def compute(self, amcl_threshold: float = 0.20,
                costmap_max_staleness_sec: float = 2.0) -> bool:
        return (
            self.nav2_active
            and self.amcl_cov_max < amcl_threshold
            and costmap_recent(self.costmap_seconds_since_last,
                                costmap_max_staleness_sec)
        )


class CapabilityPublisherNode(Node):
    def __init__(self):
        super().__init__("capability_publisher_node")
        self.declare_parameter("amcl_pose_topic", "/amcl_pose")
        self.declare_parameter("costmap_topic", "/local_costmap/costmap")
        self.declare_parameter("lifecycle_service", "/bt_navigator/get_state")
        self.declare_parameter("amcl_threshold", 0.20)
        self.declare_parameter("costmap_max_staleness_sec", 2.0)

        self._gate = NavGate()
        self._last_costmap_stamp: Optional[float] = None
        self._pub = self.create_publisher(Bool, "/capability/nav_ready", 10)

        self.create_subscription(
            PoseWithCovarianceStamped,
            self.get_parameter("amcl_pose_topic").value,
            self._on_amcl_pose, 10,
        )
        self.create_subscription(
            OccupancyGrid,
            self.get_parameter("costmap_topic").value,
            self._on_costmap, 10,
        )

        self._lifecycle_client = self.create_client(
            GetState, self.get_parameter("lifecycle_service").value,
        )
        self.create_timer(1.0, self._poll_nav2_lifecycle)
        self.create_timer(0.2, self._publish_gate)

        self.get_logger().info("capability_publisher_node ready (/capability/nav_ready 5Hz)")

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped) -> None:
        cov = list(msg.pose.covariance)
        x_var = cov[0] if len(cov) > 0 else 999.0
        y_var = cov[7] if len(cov) > 7 else 999.0
        yaw_var = cov[35] if len(cov) > 35 else 999.0
        self._gate.amcl_cov_max = max(x_var, y_var, yaw_var)

    def _on_costmap(self, _msg: OccupancyGrid) -> None:
        # 只用收到時間判斷 health,不檢查 cell cost
        self._last_costmap_stamp = self.get_clock().now().nanoseconds * 1e-9

    def _refresh_costmap_age(self) -> None:
        if self._last_costmap_stamp is None:
            self._gate.costmap_seconds_since_last = None
            return
        now = self.get_clock().now().nanoseconds * 1e-9
        self._gate.costmap_seconds_since_last = now - self._last_costmap_stamp

    def _poll_nav2_lifecycle(self) -> None:
        if not self._lifecycle_client.service_is_ready():
            self._gate.nav2_active = False
            return
        future = self._lifecycle_client.call_async(GetState.Request())
        future.add_done_callback(self._on_lifecycle_response)

    def _on_lifecycle_response(self, future) -> None:
        try:
            result = future.result()
            self._gate.nav2_active = is_nav2_active(result.current_state.id)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f"lifecycle check failed: {exc}")
            self._gate.nav2_active = False

    def _publish_gate(self) -> None:
        self._refresh_costmap_age()
        amcl_th = self.get_parameter("amcl_threshold").value
        cm_max = self.get_parameter("costmap_max_staleness_sec").value
        msg = Bool()
        msg.data = self._gate.compute(amcl_th, cm_max)
        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CapabilityPublisherNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 加 entry_point**

修改 `nav_capability/setup.py`,在 `entry_points["console_scripts"]` 加:
```python
"capability_publisher_node = nav_capability.capability_publisher_node:main",
```

- [ ] **Step 5: 跑測試 pass**

```bash
colcon build --packages-select nav_capability && source install/setup.zsh
pytest nav_capability/test/test_capability_publisher_node.py -v
```
Expected:9 PASS

- [ ] **Step 6: 上機冒煙**

```bash
ros2 run nav_capability capability_publisher_node &
ros2 topic echo /capability/nav_ready --once
```
Expected:看到 `data: false`(因 AMCL/Nav2 都還沒起);完整 demo stack 起來後應為 `true`

- [ ] **Step 7: Commit**

```bash
git add nav_capability/nav_capability/capability_publisher_node.py \
        nav_capability/test/test_capability_publisher_node.py \
        nav_capability/setup.py
git commit -m "feat(nav): add capability_publisher_node — /capability/nav_ready Nav Gate"
```

---

## Task 6: depth_safety_node — Depth Gate(TDD)

**Files:**
- Create: `go2_robot_sdk/go2_robot_sdk/depth_safety_node.py`
- Create: `go2_robot_sdk/test/test_depth_safety_node.py`
- Modify: `go2_robot_sdk/setup.py` (entry_point)

- [ ] **Step 1: 寫失敗測試**

```python
# go2_robot_sdk/test/test_depth_safety_node.py
"""Depth Gate — 用 D435 aligned depth image 計算前方 ROI 1m 內最近障礙距離,
< 0.4m 判定 unsafe,publish /capability/depth_clear (Bool)。"""
import numpy as np
import pytest
from go2_robot_sdk.depth_safety_node import compute_min_depth_in_roi, depth_clear

def test_compute_min_depth_clear_field():
    """全 2.0m 深度 → min = 2.0m"""
    depth = np.full((480, 640), 2000, dtype=np.uint16)  # mm
    min_m = compute_min_depth_in_roi(depth, roi=(160, 160, 480, 320), max_range_m=1.0)
    assert min_m == pytest.approx(2.0, abs=0.01) or min_m is None  # 超過 max_range 視為 None/ignore

def test_compute_min_depth_obstacle_at_50cm():
    """ROI 中央有 0.5m 障礙 → min = 0.5m"""
    depth = np.full((480, 640), 2000, dtype=np.uint16)
    depth[200:280, 280:360] = 500  # mm
    min_m = compute_min_depth_in_roi(depth, roi=(160, 160, 480, 320), max_range_m=1.0)
    assert min_m == pytest.approx(0.5, abs=0.05)

def test_compute_min_depth_ignores_zero():
    """深度 0 = 無效讀值,不應影響 min"""
    depth = np.full((480, 640), 2000, dtype=np.uint16)
    depth[200:300, 200:300] = 0  # invalid
    depth[300:320, 300:320] = 600
    min_m = compute_min_depth_in_roi(depth, roi=(160, 160, 480, 320), max_range_m=1.0)
    assert min_m == pytest.approx(0.6, abs=0.05)

def test_depth_clear_above_threshold():
    assert depth_clear(min_dist_m=0.6, threshold_m=0.4) is True

def test_depth_clear_below_threshold():
    assert depth_clear(min_dist_m=0.3, threshold_m=0.4) is False

def test_depth_clear_none_treated_as_clear():
    """ROI 內無有效讀值(全 0 或全超過 max_range) → 視為 clear(避免 false positive 攔下 demo)"""
    assert depth_clear(min_dist_m=None, threshold_m=0.4) is True
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
pytest go2_robot_sdk/test/test_depth_safety_node.py -v
```
Expected:ImportError

- [ ] **Step 3: 實作**

```python
# go2_robot_sdk/go2_robot_sdk/depth_safety_node.py
"""Depth Gate publisher — 對應 spec §6.1 Depth Gate。

訂 D435 aligned depth image,計算前方 ROI 1m 內最近障礙距離,
< 0.4m 判定 unsafe,publish /capability/depth_clear (std_msgs/Bool, 10 Hz)。"""
from __future__ import annotations
from typing import Optional

import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool


def compute_min_depth_in_roi(
    depth_mm: np.ndarray,
    roi: tuple[int, int, int, int],  # (x_min, y_min, x_max, y_max)
    max_range_m: float = 1.0,
) -> Optional[float]:
    """回傳 ROI 內 max_range_m 範圍內最近的 depth(m),無有效讀值回 None。"""
    x0, y0, x1, y1 = roi
    sub = depth_mm[y0:y1, x0:x1]
    valid = sub[(sub > 0) & (sub < max_range_m * 1000)]
    if valid.size == 0:
        return None
    return float(valid.min()) / 1000.0


def depth_clear(min_dist_m: Optional[float], threshold_m: float = 0.4) -> bool:
    """min_dist_m 為 None 時視為 clear(無有效讀值不擋 demo)。"""
    if min_dist_m is None:
        return True
    return min_dist_m >= threshold_m


class DepthSafetyNode(Node):
    def __init__(self):
        super().__init__("depth_safety_node")
        self._bridge = CvBridge()
        self._latest_min_m: Optional[float] = None

        # ROI (640x480 image, 中央前方 1/2 寬 × 上下 1/2)
        self._roi = (160, 160, 480, 320)

        # D435 aligned depth — 專案慣例 double namespace `/camera/camera/...`
        # (per docs/architecture/contracts/interaction_contract.md:895)
        # **必須用 SensorDataQoS (BEST_EFFORT)** — RealSense image/depth publisher
        # 預設是 BEST_EFFORT,reliable QoS subscriber 會收不到任何 frame。
        from rclpy.qos import qos_profile_sensor_data
        self.declare_parameter(
            "depth_topic", "/camera/camera/aligned_depth_to_color/image_raw",
        )
        depth_topic = self.get_parameter("depth_topic").value
        self.create_subscription(
            Image, depth_topic, self._on_depth, qos_profile_sensor_data,
        )

        self._pub = self.create_publisher(Bool, "/capability/depth_clear", 10)

        # Publish at 10 Hz
        self.create_timer(0.1, self._publish_gate)

        self.get_logger().info(
            "depth_safety_node ready (/capability/depth_clear 10Hz, ROI=%s, threshold=0.4m)" % str(self._roi)
        )

    def _on_depth(self, msg: Image) -> None:
        try:
            depth = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            if depth.dtype != np.uint16:
                depth = depth.astype(np.uint16)
            self._latest_min_m = compute_min_depth_in_roi(
                depth, self._roi, max_range_m=1.0,
            )
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f"depth conversion failed: {exc}")

    def _publish_gate(self) -> None:
        msg = Bool()
        msg.data = depth_clear(self._latest_min_m, threshold_m=0.4)
        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = DepthSafetyNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 加 entry_point**

`go2_robot_sdk/setup.py` 加:
```python
"depth_safety_node = go2_robot_sdk.depth_safety_node:main",
```

- [ ] **Step 5: 跑測試 pass**

```bash
colcon build --packages-select go2_robot_sdk && source install/setup.zsh
pytest go2_robot_sdk/test/test_depth_safety_node.py -v
```
Expected:6 PASS

- [ ] **Step 6: 上機冒煙**

```bash
# D435 already running
ros2 run go2_robot_sdk depth_safety_node &
ros2 topic echo /capability/depth_clear --once
# 把手放在 D435 前 30cm → 應該變 false
# 移開 → 變 true
```

- [ ] **Step 7: Commit**

```bash
git add go2_robot_sdk/go2_robot_sdk/depth_safety_node.py \
        go2_robot_sdk/test/test_depth_safety_node.py \
        go2_robot_sdk/setup.py
git commit -m "feat(safety): add depth_safety_node — /capability/depth_clear Depth Gate"
```

---

## Task 7: WorldState 訂兩個 Capability Bool(TDD)

**Files:**
- Modify: `interaction_executive/interaction_executive/world_state.py`
- Test: `interaction_executive/test/test_world_state_capabilities.py` (NEW)

- [ ] **Step 1: 寫失敗測試**

```python
# interaction_executive/test/test_world_state_capabilities.py
"""WorldState 必須訂 /capability/nav_ready + /capability/depth_clear,
snapshot() 回傳的 dataclass 含 nav_ready: bool + depth_clear: bool。

Note: 現有 WorldState.__init__ 直接 node.create_subscription(),不支援 None。
測試用 unittest.mock.Mock() 取代 node,驗 init 行為與 callback 行為。"""
from unittest.mock import MagicMock
from std_msgs.msg import Bool
from interaction_executive.world_state import WorldState


def _fresh_ws_with_mock_node():
    fake_node = MagicMock()
    fake_node.create_subscription = MagicMock()
    return WorldState(node=fake_node), fake_node


def test_snapshot_default_nav_ready_false():
    ws, _ = _fresh_ws_with_mock_node()
    snap = ws.snapshot()
    assert snap.nav_ready is False


def test_snapshot_default_depth_clear_true():
    """depth_clear 預設 true(無讀值不擋)"""
    ws, _ = _fresh_ws_with_mock_node()
    snap = ws.snapshot()
    assert snap.depth_clear is True


def test_subscriptions_registered():
    """確認 init 真的呼叫了 node.create_subscription 兩次給 nav_ready / depth_clear"""
    _, fake = _fresh_ws_with_mock_node()
    topics = [call.args[1] for call in fake.create_subscription.call_args_list]
    assert "/capability/nav_ready" in topics
    assert "/capability/depth_clear" in topics


def test_on_nav_ready_callback():
    ws, _ = _fresh_ws_with_mock_node()
    msg = Bool(); msg.data = True
    ws._on_nav_ready(msg)
    assert ws.snapshot().nav_ready is True


def test_on_depth_clear_callback():
    ws, _ = _fresh_ws_with_mock_node()
    msg = Bool(); msg.data = False
    ws._on_depth_clear(msg)
    assert ws.snapshot().depth_clear is False
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
pytest interaction_executive/test/test_world_state_capabilities.py -v
```
Expected:`AttributeError: nav_ready` 或 init 失敗

- [ ] **Step 3: 修改 WorldState**

(對齊 Task 1 Step 1 grep 找到的既有 `WorldState` 結構,在 `__init__` 加 capability flags,在 snapshot dataclass 加欄位,在 callback 處理 Bool。)

```python
# interaction_executive/interaction_executive/world_state.py — 增量修改

# 在 WorldStateSnapshot dataclass 加:
@dataclass
class WorldStateSnapshot:
    # ... existing fields ...
    nav_ready: bool = False
    depth_clear: bool = True  # 預設 true 避免 false positive

# 在 WorldState.__init__ 加(假設 node 不為 None):
class WorldState:
    def __init__(self, node):
        # ... existing init ...
        self._nav_ready = False
        self._depth_clear = True
        if node is not None:
            from std_msgs.msg import Bool
            node.create_subscription(Bool, "/capability/nav_ready",
                                     self._on_nav_ready, 10)
            node.create_subscription(Bool, "/capability/depth_clear",
                                     self._on_depth_clear, 10)

    def _on_nav_ready(self, msg) -> None:
        self._nav_ready = bool(msg.data)

    def _on_depth_clear(self, msg) -> None:
        self._depth_clear = bool(msg.data)

    def snapshot(self) -> WorldStateSnapshot:
        return WorldStateSnapshot(
            # ... existing fields ...
            nav_ready=self._nav_ready,
            depth_clear=self._depth_clear,
        )
```

- [ ] **Step 4: 跑測試 pass**

```bash
# [JETSON ONLY] colcon build + 含 ROS2 import 的 pytest run
colcon build --packages-select interaction_executive && source install/setup.zsh
pytest interaction_executive/test/test_world_state_capabilities.py -v
```
Expected:5 PASS。**現有 WorldState 既有 test 也要全 pass**(跑 `pytest interaction_executive/test/ -v`)

> Note:Task 7 測試本身用 `unittest.mock.MagicMock()` 替 node,**不會 `rclpy.init()`**;但 import `from interaction_executive.world_state import WorldState` 需 package 已 colcon build,所以 colcon + pytest 仍走 Jetson。若 WSL 端有同步好 build artifact 也可在 WSL 跑此測試。

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/world_state.py \
        interaction_executive/test/test_world_state_capabilities.py
git commit -m "feat(executive): WorldState subscribe /capability/nav_ready + /capability/depth_clear"
```

---

## Task 8: SafetyLayer.validate 三段 Pre-action Validate(TDD)

**Files:**
- Modify: `interaction_executive/interaction_executive/safety_layer.py`
- Test: `interaction_executive/test/test_safety_gate_three_tier.py` (NEW)

- [ ] **Step 1: 寫失敗測試**

```python
# interaction_executive/test/test_safety_gate_three_tier.py
"""對應 spec §6.1 三段 Pre-action Validate:
- NAV: nav_ready AND depth_clear
- High-risk MOTION: depth_clear AND robot_stable
- Low-risk social MOTION: 不走 gate
- SAY: 永遠允許"""
import pytest
from interaction_executive.safety_layer import SafetyLayer
from interaction_executive.skill_contract import SkillPlan, SkillStep, ExecutorKind, PriorityClass
from interaction_executive.world_state import WorldStateSnapshot

HIGH_RISK_SKILLS = {"wiggle", "stretch", "dance", "approach_person",
                     "follow_me", "follow_person"}
LOW_RISK_SOCIAL = {"wave_hello", "sit_along", "careful_remind",
                    "akimbo_react", "knee_kneel_react"}

def _snap(nav_ready=True, depth_clear=True, robot_stable=True):
    return WorldStateSnapshot(nav_ready=nav_ready, depth_clear=depth_clear,
                              robot_stable=robot_stable)

def _plan(skill_id: str, kind: ExecutorKind):
    return SkillPlan(
        plan_id="p1", skill_id=skill_id,
        priority_class=PriorityClass.SKILL,
        steps=[SkillStep(kind=kind, payload={})],
    )

def test_nav_step_requires_both_gates():
    sl = SafetyLayer()
    plan = _plan("nav_demo_point", ExecutorKind.NAV)
    assert sl.validate(plan, _snap(nav_ready=True, depth_clear=True)).ok is True
    assert sl.validate(plan, _snap(nav_ready=False, depth_clear=True)).ok is False
    assert sl.validate(plan, _snap(nav_ready=True, depth_clear=False)).ok is False

def test_high_risk_motion_requires_depth_and_stable():
    sl = SafetyLayer()
    plan = _plan("wiggle", ExecutorKind.MOTION)
    assert sl.validate(plan, _snap(depth_clear=True, robot_stable=True)).ok is True
    assert sl.validate(plan, _snap(depth_clear=False, robot_stable=True)).ok is False
    assert sl.validate(plan, _snap(depth_clear=True, robot_stable=False)).ok is False

def test_low_risk_social_motion_no_gate():
    sl = SafetyLayer()
    plan = _plan("wave_hello", ExecutorKind.MOTION)
    # 即使 nav_ready/depth_clear 都 false,social motion 仍應 allow
    assert sl.validate(plan, _snap(nav_ready=False, depth_clear=False, robot_stable=True)).ok is True

def test_say_step_always_allowed():
    sl = SafetyLayer()
    plan = _plan("chat_reply", ExecutorKind.SAY)
    assert sl.validate(plan, _snap(nav_ready=False, depth_clear=False)).ok is True

def test_degradation_reason_human_readable():
    sl = SafetyLayer()
    plan = _plan("approach_person", ExecutorKind.NAV)
    result = sl.validate(plan, _snap(nav_ready=False, depth_clear=True))
    assert result.ok is False
    assert "nav" in result.reason.lower() or "定位" in result.reason or "導航" in result.reason
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
pytest interaction_executive/test/test_safety_gate_three_tier.py -v
```
Expected:多數 FAIL,因 SafetyLayer 還沒分三段邏輯

- [ ] **Step 3: 實作三段邏輯**

(找 `SafetyLayer.validate` 既有實作,擴增三段判斷;假設 `WorldStateSnapshot` 已含 `robot_stable`,若沒有先補)

```python
# interaction_executive/interaction_executive/safety_layer.py — 擴增 validate
HIGH_RISK_MOTION_SKILLS = {
    "wiggle", "stretch", "dance",
    "approach_person", "follow_me", "follow_person",
}
LOW_RISK_SOCIAL_MOTION_SKILLS = {
    "wave_hello", "sit_along", "careful_remind",
    "akimbo_react", "knee_kneel_react",
}


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


class SafetyLayer:
    def validate(self, plan: SkillPlan, snapshot: WorldStateSnapshot) -> ValidationResult:
        # 既有 hard rule (stop / safety) 先處理 ...
        # ... 既有邏輯 ...

        # 三段 Pre-action Validate
        for step in plan.steps:
            if step.kind == ExecutorKind.NAV:
                if not snapshot.nav_ready:
                    return ValidationResult(False, "nav 尚未準備:Nav2 未啟動或定位未收斂")
                if not snapshot.depth_clear:
                    return ValidationResult(False, "前方有近距離障礙,先讓我看清楚")
            elif step.kind == ExecutorKind.MOTION:
                if plan.skill_id in HIGH_RISK_MOTION_SKILLS:
                    if not snapshot.depth_clear:
                        return ValidationResult(False, "前方有障礙,我不適合做大動作")
                    if not snapshot.robot_stable:
                        return ValidationResult(False, "我還沒站穩,等一下再做")
                elif plan.skill_id in LOW_RISK_SOCIAL_MOTION_SKILLS:
                    pass  # 不走 gate
            elif step.kind == ExecutorKind.SAY:
                pass  # 永遠允許

        return ValidationResult(True)
```

(若 `WorldStateSnapshot` 還沒 `robot_stable` 欄位,順手補上,預設 True;真正 IMU 接入留 Phase B 補。)

- [ ] **Step 4: 跑測試 pass**

```bash
colcon build --packages-select interaction_executive && source install/setup.zsh
pytest interaction_executive/test/test_safety_gate_three_tier.py interaction_executive/test/ -v
```
Expected:5 PASS + 既有 test 全 pass

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/safety_layer.py \
        interaction_executive/interaction_executive/world_state.py \
        interaction_executive/test/test_safety_gate_three_tier.py
git commit -m "feat(executive): SafetyLayer three-tier Pre-action Validate (NAV / high-risk MOTION / social)"
```

---

## Task 9: Skill Registry 加 nav_demo_point + approach_person(TDD)

**Files:**
- Modify: `interaction_executive/interaction_executive/skill_contract.py`
- Test: `interaction_executive/test/test_nav_skills_registry.py` (NEW)

- [ ] **Step 1: 寫失敗測試**

```python
# interaction_executive/test/test_nav_skills_registry.py
"""新增兩條 nav skill,對齊 spec §4.1 Active Set + §7 A3。"""
import pytest
from interaction_executive.skill_contract import (
    SKILL_REGISTRY, build_plan, ExecutorKind, PriorityClass,
)

def test_nav_demo_point_registered():
    assert "nav_demo_point" in SKILL_REGISTRY
    skill = SKILL_REGISTRY["nav_demo_point"]
    assert skill.priority_class == PriorityClass.SKILL
    # 一步 NAV
    assert any(s.kind == ExecutorKind.NAV for s in skill.steps)

def test_approach_person_registered():
    """Registry metadata check only。NAV/SAY steps 由 build_plan 動態產生(因為要算 face centroid),
    SkillContract.steps 預期為空 list,**不要在這測 NAV/SAY step**(放到 build_plan 測)。"""
    assert "approach_person" in SKILL_REGISTRY
    skill = SKILL_REGISTRY["approach_person"]
    assert skill.priority_class == PriorityClass.SKILL
    assert "nav_ready" in skill.safety_requirements
    assert "depth_clear" in skill.safety_requirements
    assert skill.fallback_skill == "say_canned"
    # steps 預期為 [](由 build_plan 動態填),這裡不檢查內容

def test_nav_demo_point_build_plan():
    plan = build_plan("nav_demo_point", args={"distance": 1.0})
    assert plan.skill_id == "nav_demo_point"
    assert plan.steps[0].kind == ExecutorKind.NAV
    assert plan.steps[0].payload.get("action") == "goto_relative"

def test_approach_person_build_plan_with_face_centroid():
    plan = build_plan("approach_person",
                      args={"face_centroid_dx": 1.5, "face_centroid_dy": 0.2,
                            "stop_at": 1.0})
    assert plan.skill_id == "approach_person"
    # NAV step 檢查(動態產生)
    nav_step = next(s for s in plan.steps if s.kind == ExecutorKind.NAV)
    # 計算後 distance ≈ √(1.5² + 0.2²) - 1.0 ≈ 0.513
    assert nav_step.payload["distance"] == pytest.approx(0.513, abs=0.05)
    # SAY step 檢查(也由 build_plan 產生)
    say_step = next(s for s in plan.steps if s.kind == ExecutorKind.SAY)
    assert "text_template" in say_step.payload
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
pytest interaction_executive/test/test_nav_skills_registry.py -v
```
Expected:`KeyError: nav_demo_point`

- [ ] **Step 3: 加兩條 SkillContract**

```python
# interaction_executive/interaction_executive/skill_contract.py — 加在 SKILL_REGISTRY 既有 dict 結尾

SKILL_REGISTRY["nav_demo_point"] = SkillContract(
    skill_id="nav_demo_point",
    priority_class=PriorityClass.SKILL,
    steps=[
        SkillStep(
            kind=ExecutorKind.NAV,
            payload={"action": "goto_relative", "distance": 1.0,
                     "yaw_offset": 0.0, "max_speed": 0.5},
        ),
        SkillStep(
            kind=ExecutorKind.SAY,
            payload={"text_template": "[excited]我成功走到了!"},
        ),
    ],
    cooldown_sec=10.0,
    safety_requirements=["nav_ready", "depth_clear"],
    fallback_skill="say_canned",
    enabled_when=["map_loaded", "nav2_active"],
    description="Studio 觸發或語音「往前走」,短距 1m goto_relative,Scene 2 主秀",
)


def _build_approach_person_plan(args: dict) -> list[SkillStep]:
    """根據 face centroid 計算 distance/yaw_offset。"""
    import math
    dx = args.get("face_centroid_dx", 1.5)
    dy = args.get("face_centroid_dy", 0.0)
    stop_at = args.get("stop_at", 1.0)
    full_dist = math.hypot(dx, dy)
    distance = max(0.0, full_dist - stop_at)
    yaw_offset = math.atan2(dy, dx)
    return [
        SkillStep(
            kind=ExecutorKind.NAV,
            payload={"action": "goto_relative", "distance": distance,
                     "yaw_offset": yaw_offset, "max_speed": 0.5},
        ),
        SkillStep(
            kind=ExecutorKind.SAY,
            payload={"text_template": "[happy]我來啦!"},
        ),
    ]


SKILL_REGISTRY["approach_person"] = SkillContract(
    skill_id="approach_person",
    priority_class=PriorityClass.SKILL,
    steps=[],  # 由 build_plan 動態填(因為要 args)
    cooldown_sec=15.0,
    safety_requirements=["nav_ready", "depth_clear", "face_stable"],
    fallback_skill="say_canned",
    enabled_when=["map_loaded", "nav2_active"],
    description="face stable + Wave/ComeHere → 算 face centroid → goto_relative 至 1m 前",
)
```

修改 `build_plan` 函式,加 approach_person 的 dynamic steps 處理:

```python
def build_plan(skill_id: str, args: dict | None = None, ...) -> SkillPlan:
    args = args or {}
    contract = SKILL_REGISTRY[skill_id]
    if skill_id == "approach_person":
        steps = _build_approach_person_plan(args)
    else:
        steps = list(contract.steps)
    # ... 既有 args 替換邏輯(text_template) ...
    return SkillPlan(
        plan_id=new_plan_id(),
        skill_id=skill_id,
        priority_class=contract.priority_class,
        steps=steps,
    )
```

- [ ] **Step 4: 跑測試 pass**

```bash
colcon build --packages-select interaction_executive && source install/setup.zsh
pytest interaction_executive/test/test_nav_skills_registry.py interaction_executive/test/ -v
```
Expected:4 PASS + 既有全 pass

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/skill_contract.py \
        interaction_executive/test/test_nav_skills_registry.py
git commit -m "feat(brain): add nav_demo_point + approach_person SkillContracts"
```

---

## Task 10: Brain rules — speech_nav_demo + face_wave_approach(TDD)

**Files:**
- Modify: `interaction_executive/interaction_executive/brain_node.py`
- Test: `interaction_executive/test/test_brain_nav_rules.py` (NEW)

- [ ] **Step 1: 寫失敗測試**

```python
# interaction_executive/test/test_brain_nav_rules.py
"""Brain 規則:
- speech 含「往前走 / 走過去 / 過來」→ nav_demo_point
- face_state.stable_name 非空 + recent gesture in {Wave, ComeHere} → approach_person"""
import pytest
from interaction_executive.brain_node import BrainNode

def test_speech_nav_demo_keyword():
    bn = BrainNode(test_mode=True)
    plan = bn._dispatch_speech_intent({"transcript": "PawAI 往前走"})
    assert plan is not None
    assert plan.skill_id == "nav_demo_point"

def test_face_wave_triggers_approach():
    bn = BrainNode(test_mode=True)
    bn._update_face_state({"stable_name": "Roy", "centroid_dx": 1.5, "centroid_dy": 0.2})
    plan = bn._dispatch_gesture({"gesture": "Wave"})
    assert plan is not None
    assert plan.skill_id == "approach_person"

def test_face_unknown_does_not_trigger_approach():
    bn = BrainNode(test_mode=True)
    bn._update_face_state({"stable_name": "", "centroid_dx": 1.5, "centroid_dy": 0.2})
    plan = bn._dispatch_gesture({"gesture": "Wave"})
    # unknown face + Wave → 還是會觸發 wave_hello,但不是 approach_person
    assert plan is None or plan.skill_id != "approach_person"

def test_face_stable_no_gesture_does_not_trigger_approach():
    bn = BrainNode(test_mode=True)
    bn._update_face_state({"stable_name": "Roy"})
    # 沒有 Wave/ComeHere → 走 greet_known_person 而非 approach
    plan = bn._tick_face_only()
    assert plan is None or plan.skill_id != "approach_person"
```

- [ ] **Step 2: 跑測試確認 fail**

```bash
pytest interaction_executive/test/test_brain_nav_rules.py -v
```
Expected:多數 FAIL

- [ ] **Step 3: 加 rule 邏輯**

```python
# interaction_executive/interaction_executive/brain_node.py — 增量

NAV_DEMO_KEYWORDS = ["往前走", "走過去", "走一下", "向前", "前進"]
APPROACH_GESTURES = {"Wave", "wave", "ComeHere", "come_here"}

class BrainNode(...):
    def _dispatch_speech_intent(self, payload: dict):
        transcript = payload.get("transcript", "")
        # 既有規則 first ...
        for kw in NAV_DEMO_KEYWORDS:
            if kw in transcript:
                return build_plan("nav_demo_point", args={"distance": 1.0})
        # ... 既有 fallback ...

    def _dispatch_gesture(self, payload: dict):
        gesture = payload.get("gesture", "")
        if gesture in APPROACH_GESTURES:
            face = self._face_state
            if face.get("stable_name"):
                # face stable + Wave/ComeHere → approach_person
                return build_plan(
                    "approach_person",
                    args={
                        "face_centroid_dx": face.get("centroid_dx", 1.5),
                        "face_centroid_dy": face.get("centroid_dy", 0.0),
                        "stop_at": 1.0,
                    },
                )
            else:
                # 不認識 + Wave → wave_hello(既有)
                return build_plan("wave_hello")
        # ... 既有規則 ...

    def _update_face_state(self, msg: dict) -> None:
        self._face_state = msg
```

- [ ] **Step 4: 跑測試 pass**

```bash
colcon build --packages-select interaction_executive && source install/setup.zsh
pytest interaction_executive/test/test_brain_nav_rules.py -v
```
Expected:4 PASS

- [ ] **Step 5: Commit**

```bash
git add interaction_executive/interaction_executive/brain_node.py \
        interaction_executive/test/test_brain_nav_rules.py
git commit -m "feat(brain): add speech_nav_demo + face_wave_approach rules"
```

---

## Task 11: Launch — 加兩個 capability node

**Files:**
- Modify: `interaction_executive/launch/interaction_executive.launch.py`
- 或建新 launch:`nav_capability/launch/capability_publishers.launch.py`

- [ ] **Step 1: 在 demo tmux 啟動腳本中 include 兩個新 node**

```bash
# 找出主啟動腳本
grep -l "nav_action_server\|interaction_executive_node" scripts/*.sh
# 預期: scripts/start_nav_capability_demo_tmux.sh
```

修改該腳本,在 navcap window 加兩個 node:

```bash
# scripts/start_nav_capability_demo_tmux.sh — 加在 navcap window 段
ros2 run nav_capability capability_publisher_node &
ros2 run go2_robot_sdk depth_safety_node &
```

(或更乾淨:寫一個 ros2 launch file include 進去)

- [ ] **Step 2: 上機驗證兩個 node 都啟動**

```bash
bash scripts/start_nav_capability_demo_tmux.sh
sleep 50
ros2 topic hz /capability/nav_ready  # 應該 5Hz
ros2 topic hz /capability/depth_clear  # 應該 10Hz
ros2 topic echo /capability/nav_ready --once
ros2 topic echo /capability/depth_clear --once
```
Expected:兩個 topic 都有訊息

- [ ] **Step 3: Commit**

```bash
git add scripts/start_nav_capability_demo_tmux.sh
git commit -m "chore(scripts): include capability_publisher + depth_safety in demo tmux"
```

---

## Task 12: Studio Trace Drawer — Nav Gate / Depth Gate LED

**Files:**
- Modify: `pawai-studio/frontend/src/components/chat/skill-trace-drawer.tsx`
- Modify: `pawai-studio/backend/...`(gateway 加 ws broadcast 兩個 capability topic)

- [ ] **Step 1: 找 Studio gateway 訂 ROS2 topic 的 dispatch**

```bash
grep -rn "subscribe\|create_subscription\|brain/proposal" pawai-studio/backend/ | head -20
```

- [ ] **Step 2: gateway 訂兩個 capability topic + WS broadcast**

```python
# pawai-studio/backend/.../gateway.py — 增量
from std_msgs.msg import Bool

# 在 ROS2 node 初始化區段加:
self.create_subscription(Bool, "/capability/nav_ready",
                          lambda m: self._broadcast("capability.nav_ready", {"value": m.data}), 10)
self.create_subscription(Bool, "/capability/depth_clear",
                          lambda m: self._broadcast("capability.depth_clear", {"value": m.data}), 10)
```

- [ ] **Step 3: Frontend trace drawer 加 2 LED**

```tsx
// pawai-studio/frontend/src/components/chat/skill-trace-drawer.tsx
// 在 drawer header 區段加:
<div className="flex gap-3 items-center">
  <Led label="Nav Gate" active={navReady} />
  <Led label="Depth Gate" active={depthClear} />
</div>

// LED 元件:
function Led({ label, active }: { label: string; active: boolean }) {
  return (
    <span className="flex items-center gap-1 text-xs">
      <span className={`w-2 h-2 rounded-full ${active ? 'bg-green-500' : 'bg-red-500'}`} />
      {label}
    </span>
  );
}
```

WebSocket handler 接 `capability.nav_ready` / `capability.depth_clear` 更新 state。

- [ ] **Step 4: 開 Studio 看燈號**

```bash
bash pawai-studio/start.sh  # 含 backend + frontend
# 訪問 http://localhost:3000/studio
# Trace Drawer 應顯示 2 顆 LED,顏色隨 capability 變化
```

- [ ] **Step 5: Commit**

```bash
git add pawai-studio/frontend/src/components/chat/skill-trace-drawer.tsx \
        pawai-studio/backend/
git commit -m "feat(studio): add Nav Gate + Depth Gate LED in skill trace drawer"
```

---

## Task 13: nav_demo_point 上機驗證 5/5 PASS

**Files:**
- Use: `scripts/k1_regression.sh`(Task 4 寫的)+ Studio Skill Button

- [ ] **Step 1: 上機**

```bash
bash scripts/start_nav_capability_demo_tmux.sh  # 含所有新 node
sleep 50  # 等 lifecycle active
# Foxglove 設 /initialpose
```

- [ ] **Step 2: 跑 5 輪 nav_demo_point**

```bash
for i in 1 2 3 4 5; do
    echo "Round $i"
    ros2 topic pub --once /brain/skill_request std_msgs/msg/String \
        "{data: '{\"skill_id\":\"nav_demo_point\",\"args\":{\"distance\":1.0}}'}"
    sleep 8
done
```
記錄結果到 `docs/導航避障/research/2026-05-02-nav-demo-point-validation.md`

Expected:**5/5 PASS** — Go2 走完 1m 並 SAY 「我成功走到了!」

- [ ] **Step 3: 若不過,debug 順序**

1. `/capability/nav_ready` 是否 true?(若 false → 看 AMCL cov / Nav2 lifecycle / costmap cost)
2. `/capability/depth_clear` 是否 true?(若 false → 看 D435 ROI 是否被擋)
3. `/brain/proposal` 有沒有發?
4. `/cmd_vel` 有沒有真的發到 Go2?
5. Go2 sport mode min 0.50 m/s 門檻 — DWB `min_vel_x` 是否 ≥ 0.45?

- [ ] **Step 4: Commit 驗證紀錄**

```bash
git add docs/導航避障/research/2026-05-02-nav-demo-point-validation.md
git commit -m "docs(nav): nav_demo_point 5/5 PASS validation log"
```

---

## Task 14: approach_person 上機驗證 1 PASS

**Files:**
- Use: 既有 Studio + face_perception + vision_perception(Wave gesture)

- [ ] **Step 1: 啟全 stack**

```bash
bash scripts/start_nav_capability_demo_tmux.sh
bash scripts/start_face_identity_tmux.sh  # 在另一 session
ros2 launch vision_perception vision_perception.launch.py inference_backend:=rtmpose use_camera:=true gesture_backend:=recognizer
```

- [ ] **Step 2: 觸發 approach_person**

1. 站在 Go2 前 ~1.5m,讓 face_perception 認出
2. 確認 `/event/face_identity` 發 `identity_stable: roy`
3. 對 Go2 揮手(Wave)
4. 觀察 `/brain/proposal` 是否發 `approach_person` plan

Expected:Go2 走過來停在 ~1m 處,SAY「我來啦!」

- [ ] **Step 3: 若不過,debug**

- BrainNode 是否有 face_state cache?(`grep _face_state interaction_executive/`)
- Wave gesture event 是否進來?(`ros2 topic echo /event/gesture_detected`)
- approach_person SkillPlan 計算的 distance 是否合理?(< 0.5m 不該觸發 nav)
- 4-cond gate 攔截?(看 Studio Trace Drawer 兩個 LED)

- [ ] **Step 4: 紀錄到 daily log + Commit**

```bash
git add docs/導航避障/research/2026-05-03-approach-person-validation.md
git commit -m "docs(nav): approach_person 1 PASS validation log"
```

---

## Task 15: 30 分鐘供電連續測試

**Files:**
- Create: `docs/導航避障/research/2026-05-03-power-30min-test.md`

- [ ] **Step 1: 全 stack 同時跑**

```bash
# Window 1
bash scripts/start_nav_capability_demo_tmux.sh
# Window 2
bash scripts/start_face_identity_tmux.sh
# Window 3
ros2 launch vision_perception vision_perception.launch.py
# 監測供電
ssh jetson "tegrastats" > /tmp/tegrastats.log &
```

- [ ] **Step 2: 30 分鐘內持續發 nav_demo_point + 動作**

```bash
END=$(($(date +%s) + 1800))
while [[ $(date +%s) -lt $END ]]; do
    ros2 topic pub --once /brain/skill_request std_msgs/msg/String \
        "{data: '{\"skill_id\":\"nav_demo_point\",\"args\":{\"distance\":1.0}}'}"
    sleep 30
    ros2 topic pub --once /brain/skill_request std_msgs/msg/String \
        "{data: '{\"skill_id\":\"wiggle\"}'}"
    sleep 30
done
```

- [ ] **Step 3: 紀錄結果**

寫 `docs/導航避障/research/2026-05-03-power-30min-test.md`,包含:
- 是否斷電?(若有,在第幾分鐘?)
- Jetson 電壓最低值
- Jetson 溫度最高值
- Go2 battery 起始 / 結束 %

Expected:0 次斷電(若有 → Phase A 不能結束,要等 KREE DL241910 到貨或備案)

- [ ] **Step 4: Commit**

```bash
git add docs/導航避障/research/2026-05-03-power-30min-test.md
git commit -m "docs(power): 30-min continuous power test result"
```

---

## Task 16: 5/3 晚上停損點 — manual_motion_demo skill 預備(若 Nav2 不過才啟用)

**Files:**
- Modify(條件式):`interaction_executive/interaction_executive/skill_contract.py`
- Test(條件式):`interaction_executive/test/test_manual_motion_demo.py` (NEW)

> **若 Task 13 nav_demo_point 5/5 PASS 且 Task 14 approach_person 至少 1 PASS,跳過 Task 16。**
> **若不過,進 Plan B:加一條 `manual_motion_demo` skill,只走 stationary motion(不需 nav_ready)。**

- [ ] **Step 1: 寫測試**

```python
# interaction_executive/test/test_manual_motion_demo.py
"""manual_motion_demo: 5/3 stop-loss Plan B,只要求 depth_clear,
做 stand → sit → wiggle 3 步 stationary motion + SAY 解釋。"""
from interaction_executive.skill_contract import SKILL_REGISTRY, build_plan, ExecutorKind

def test_manual_motion_demo_registered():
    assert "manual_motion_demo" in SKILL_REGISTRY
    skill = SKILL_REGISTRY["manual_motion_demo"]
    assert "depth_clear" in skill.safety_requirements
    assert "nav_ready" not in skill.safety_requirements
```

- [ ] **Step 2: 加 SkillContract**

```python
SKILL_REGISTRY["manual_motion_demo"] = SkillContract(
    skill_id="manual_motion_demo",
    priority_class=PriorityClass.SKILL,
    steps=[
        SkillStep(kind=ExecutorKind.SAY,
                  payload={"text_template": "[curious]我的腳還在學走路,我先給你看別的!"}),
        SkillStep(kind=ExecutorKind.MOTION, payload={"api_id": 1002, "name": "stand"}),
        SkillStep(kind=ExecutorKind.MOTION, payload={"api_id": 1009, "name": "sit"}),
        SkillStep(kind=ExecutorKind.MOTION, payload={"api_id": 1033, "name": "wiggle"}),
        SkillStep(kind=ExecutorKind.SAY,
                  payload={"text_template": "[happy]怎麼樣!"}),
    ],
    cooldown_sec=20.0,
    safety_requirements=["depth_clear"],  # 不要 nav_ready
    fallback_skill="say_canned",
    enabled_when=[],  # 5/3 才開
    description="Plan B: Nav2 沒起來時的替代展示,純 stationary motion",
)
```

- [ ] **Step 3: 測試 + Commit**

```bash
pytest interaction_executive/test/test_manual_motion_demo.py -v
git add interaction_executive/interaction_executive/skill_contract.py \
        interaction_executive/test/test_manual_motion_demo.py
git commit -m "feat(brain): add manual_motion_demo skill (5/3 Plan B,not enabled by default)"
```

---

## Phase A 完成驗收

5/3 晚上必須拿到的成果:

- [ ] 5/5 nav_demo_point PASS(Task 13)
- [ ] 1/1 approach_person PASS(Task 14;若不過,Scene 7 砍,Scene 2 保留 nav_demo_point)
- [ ] 0 次斷電(Task 15)
- [ ] 兩層 Capability Gate publisher + Studio LED 顯示正常
- [ ] BUG #2 / #4 / #1 全 fix + regression 通過

**若 Task 13 也不過 → 啟 Task 16 manual_motion_demo Plan B。**

驗收完成後:
- 收尾 daily log → `references/project-status.md` 更新
- 進 Phase B(獨立 plan,5/4 開始)

---

## Self-Review Notes

- Spec §6.1 三段 Pre-action Validate → Task 8 ✓
- Spec §6.1 兩層 Capability Gate publisher → Task 5 + 6 ✓
- Spec §7 A1 BUG #2 / #4 / #1 → Task 2 / 3 / 4 ✓
- Spec §7 A2 Studio Trace LED → Task 12 ✓
- Spec §7 A3 nav_demo_point + approach_person → Task 9 + 10 + 13 + 14 ✓
- Spec §7 A4 30 分鐘供電 → Task 15 ✓
- Spec §7 A5 / §12 5/3 停損 manual_motion_demo → Task 16 ✓
- 全 16 task 都 TDD discipline(test 先行)
- 全 task 都 commit 收尾
