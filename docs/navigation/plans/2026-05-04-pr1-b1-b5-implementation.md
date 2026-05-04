# PR 1 (B1+B5) — nav_action_server 距離/速度正確性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修 B1(`max_speed` 欄位 ignored,目前只 log warn,讓 0.5m goal 走 1.04m 的 overshoot)+ B5(`actual_distance` 用 send-time pose 而非 goal-accept-time start_pose)。

**Architecture:**
- B1:抽出 `SpeedOverride` helper(`nav_capability/lib/speed_override.py`),用 ROS2 parameter client 動態 set `/controller_server` `FollowPath.max_vel_x`,在 `_execute_relative_inner` / `_execute_named_inner` 兩處用 try/finally 包好 enter/exit。純邏輯部分(target value 決策、prior value 保存)可單元測試;ROS2 client 部分用 mock。
- B5:在 `_execute_relative_inner` 一開始就抓 `start_xy`(in `_amcl_pose` 還沒被 AMCL gating 影響的時間點),`actual_distance` 用 `current - start_xy`。改動小,直接修。

**Tech Stack:** Python 3.10、rclpy(humble)、`rclpy.parameter` API、pytest、unittest.mock

**Spec source:** [`docs/navigation/plans/2026-05-04-phase2-dev-order-spec.md`](2026-05-04-phase2-dev-order-spec.md) commit `f386adf`

---

## Pre-flight Verification(寫 code 之前必做)

### Task 0: 驗證 `/controller_server` `FollowPath.max_vel_x` 是 runtime-mutable param

**為什麼**:Spec 假設動態 `set_parameters` 對 controller_server 的 DWB plugin param 會生效。Nav2 plugin 有些 param 是 plugin 載入時讀一次就不再 sync。如果這個 param 不能 runtime 改,整個 B1 設計要重來(改成兩個 yaml + launch arg switch 或其他機制)。

**Files:** N/A(實機驗證,不寫 code)

- [ ] **Step 1:啟一套 demo stack(可在 WSL,只要 Nav2 起得來)**

```bash
cd ~/newLife/elder_and_dog
bash scripts/start_nav_capability_demo_tmux.sh
# 等 lifecycle active(~30s),不一定要設 initialpose
```

- [ ] **Step 2:讀現值**

```bash
ros2 param get /controller_server FollowPath.max_vel_x
```

Expected: 印出當前值(從 `nav2_params.yaml` 載入,例如 `0.5` 或 `0.45`)。
**若 error 或回 `Parameter not set`**:停。先 `ros2 param list /controller_server | grep -i vel` 找實際 param 名,可能是 `FollowPath.max_vel_x` 或 `controller_server.FollowPath.max_vel_x` 或其他 namespace。

- [ ] **Step 3:嘗試 runtime set 並讀回**

```bash
ros2 param set /controller_server FollowPath.max_vel_x 0.30
ros2 param get /controller_server FollowPath.max_vel_x
```

Expected: 第一行回 `Set parameter successful`,第二行回 `Double value is: 0.30`。

- [ ] **Step 4:還原**

```bash
ros2 param set /controller_server FollowPath.max_vel_x 0.50  # 或原值
```

- [ ] **Step 5:Document outcome 進 plan footer**

在本檔最末「Pre-flight outcomes」段落手動填:
- 實際 param 名(若不是 `FollowPath.max_vel_x`)
- 是否 runtime mutable(YES / NO)
- 若 NO,**STOP** 並告訴 user — Task 1 起的設計要改

---

## File Structure

新建:
- `nav_capability/lib/speed_override.py`(`SpeedOverride` class — pure logic + ROS2 param client wrapper)
- `nav_capability/test/test_speed_override.py`(unit test)

修改:
- `nav_capability/nav_capability/nav_action_server_node.py`(import + 兩處 _execute_*_inner 用 SpeedOverride + B5 start_xy 修正)

不動:
- `nav_capability/lib/relative_goal_math.py`(B5 不影響相對 goal 計算邏輯)
- `nav_capability/launch/nav_capability.launch.py`(本 PR 不需 launch arg)
- `go2_robot_sdk/config/nav2_params.yaml`(B1 是 runtime override,不改 yaml 預設值)

---

## Task 1: SpeedOverride helper — 純邏輯部分(decide_target / saved_value 管理)

**Why TDD here**:`SpeedOverride` 的「決定要 set 什麼 / 結束時 restore 什麼」邏輯純 Python,單元測試最快。ROS2 client 互動部分留 Task 2 整合進來。

**Files:**
- Create: `nav_capability/lib/speed_override.py`
- Create: `nav_capability/test/test_speed_override.py`

- [ ] **Step 1:寫 failing test — `decide_target_value`**

`nav_capability/test/test_speed_override.py`:
```python
"""Unit test for SpeedOverride logic (B1)."""
import pytest

from nav_capability.lib.speed_override import decide_target_value


def test_decide_target_zero_means_skip():
    """goal.max_speed = 0.0 → return None (skip override)."""
    assert decide_target_value(0.0) is None


def test_decide_target_negative_means_skip():
    """negative max_speed → invalid, return None."""
    assert decide_target_value(-0.1) is None


def test_decide_target_positive_returns_value():
    """positive max_speed → return as-is."""
    assert decide_target_value(0.30) == 0.30


def test_decide_target_clamps_to_minimum():
    """Go2 sport mode min_vel_x = 0.50 m/s 硬限。
    若 caller 傳 0.30 會讓 Go2 拒抬腳。clamp 到 GO2_MIN_VEL_X = 0.45。"""
    from nav_capability.lib.speed_override import decide_target_value, GO2_MIN_VEL_X
    assert GO2_MIN_VEL_X == 0.45
    assert decide_target_value(0.30) == 0.45  # clamped


def test_decide_target_above_min_passes_through():
    assert decide_target_value(0.50) == 0.50
    assert decide_target_value(0.80) == 0.80
```

- [ ] **Step 2:Run test to verify it fails**

```bash
cd ~/newLife/elder_and_dog
python3 -m pytest nav_capability/test/test_speed_override.py -v --no-cov
```

Expected: `ImportError: No module named 'nav_capability.lib.speed_override'` 或 collect error.

- [ ] **Step 3:寫 minimal implementation**

`nav_capability/lib/speed_override.py`:
```python
"""SpeedOverride helper (B1) — dynamic FollowPath.max_vel_x param control.

Splits pure logic (decide_target_value) from ROS2 parameter client wiring
(SpeedOverride class, Task 2). Pure logic is unit-tested; ROS2 client is
exercised via integration in nav_action_server_node.
"""
from typing import Optional

# Go2 sport mode min_vel_x hard limit (firmware): 0.50 m/s. DWB min_vel_x must
# be ≥ 0.45 or Go2 refuses to lift legs. Even when caller passes a lower
# max_speed (e.g. for "go slow during demo"), we clamp here.
GO2_MIN_VEL_X = 0.45


def decide_target_value(requested: float) -> Optional[float]:
    """Return the value to push to controller_server, or None to skip override.

    Args:
        requested: goal.max_speed from action client. 0.0 means "use default".

    Returns:
        None if no override should be applied (skip), or a float clamped to
        GO2_MIN_VEL_X if requested below.
    """
    if requested <= 0.0:
        return None
    if requested < GO2_MIN_VEL_X:
        return GO2_MIN_VEL_X
    return requested
```

- [ ] **Step 4:Run test to verify it passes**

```bash
python3 -m pytest nav_capability/test/test_speed_override.py -v --no-cov
```

Expected: 5 passed.

- [ ] **Step 5:Commit**

```bash
git add nav_capability/lib/speed_override.py nav_capability/test/test_speed_override.py
git commit -m "feat(nav): SpeedOverride decide_target_value helper (B1 part 1)

Pure logic for B1: clamp goal.max_speed to GO2_MIN_VEL_X=0.45
(Go2 sport mode firmware limit) and skip override on 0.0/negative.

ROS2 param client wiring follows in next commit."
```

---

## Task 2: SpeedOverride context-manager class(ROS2 param client wrapper)

**Files:**
- Modify: `nav_capability/lib/speed_override.py`
- Modify: `nav_capability/test/test_speed_override.py`

- [ ] **Step 1:寫 failing test for `SpeedOverride` 用法 with mocked param client**

Append to `nav_capability/test/test_speed_override.py`:
```python
from unittest.mock import MagicMock

from nav_capability.lib.speed_override import SpeedOverride


class _FakeParamClient:
    """Minimal stand-in for rclpy AsyncParameterClient or similar.

    Real client uses futures + spin; for unit test we make get/set synchronous.
    """
    def __init__(self, current_value: float):
        self._value = current_value
        self.get_calls = 0
        self.set_calls: list[float] = []

    def get_max_vel_x(self) -> float:
        self.get_calls += 1
        return self._value

    def set_max_vel_x(self, value: float) -> bool:
        self.set_calls.append(value)
        self._value = value
        return True


def test_speed_override_skip_when_no_override():
    fake = _FakeParamClient(0.50)
    logger = MagicMock()
    with SpeedOverride(fake, requested=0.0, logger=logger) as applied:
        assert applied is False
    assert fake.set_calls == []  # never touched param


def test_speed_override_applies_and_restores():
    fake = _FakeParamClient(0.50)
    logger = MagicMock()
    with SpeedOverride(fake, requested=0.45, logger=logger) as applied:
        assert applied is True
        assert fake._value == 0.45  # entered: param now lowered
    # exited: restored
    assert fake._value == 0.50
    assert fake.set_calls == [0.45, 0.50]


def test_speed_override_clamps_below_min():
    fake = _FakeParamClient(0.50)
    logger = MagicMock()
    with SpeedOverride(fake, requested=0.30, logger=logger) as applied:
        assert applied is True
        assert fake._value == 0.45  # clamped to GO2_MIN_VEL_X
    assert fake._value == 0.50  # restored


def test_speed_override_restores_on_exception():
    fake = _FakeParamClient(0.50)
    logger = MagicMock()
    try:
        with SpeedOverride(fake, requested=0.45, logger=logger):
            raise RuntimeError("simulated nav failure")
    except RuntimeError:
        pass
    # Even on exception, must restore to original 0.50
    assert fake._value == 0.50


def test_speed_override_handles_set_failure():
    """If param set fails, log warn but don't raise — caller continues without override."""
    fake = _FakeParamClient(0.50)
    fake.set_max_vel_x = MagicMock(return_value=False)
    logger = MagicMock()
    with SpeedOverride(fake, requested=0.45, logger=logger) as applied:
        assert applied is False  # fell back to no-override
    logger.warn.assert_called()
```

- [ ] **Step 2:Run test to verify it fails**

```bash
python3 -m pytest nav_capability/test/test_speed_override.py -v --no-cov
```

Expected: 5 prior pass, 5 new fail with `ImportError` for `SpeedOverride`.

- [ ] **Step 3:Add `SpeedOverride` class to `speed_override.py`**

Append to `nav_capability/lib/speed_override.py`:
```python
class SpeedOverride:
    """Context manager that lowers /controller_server FollowPath.max_vel_x for
    the duration of a Nav2 goal, then restores it.

    Usage:
        with SpeedOverride(param_client, requested=goal.max_speed, logger=logger) as applied:
            # send Nav2 goal here; controller obeys lowered max_vel_x while inside
            ...
        # exit: original max_vel_x restored even on exception

    The param_client must expose:
        - get_max_vel_x() -> float
        - set_max_vel_x(value: float) -> bool

    `applied` is True if override actually took effect (else caller knows to log).
    """

    def __init__(self, param_client, requested: float, logger):
        self._client = param_client
        self._requested = requested
        self._logger = logger
        self._target: Optional[float] = decide_target_value(requested)
        self._original: Optional[float] = None
        self._applied: bool = False

    def __enter__(self) -> bool:
        if self._target is None:
            return False  # skip — caller passed 0 or invalid

        try:
            self._original = self._client.get_max_vel_x()
        except Exception as exc:
            self._logger.warn(
                f"SpeedOverride: failed to read current max_vel_x ({exc}); "
                f"skipping override (Nav2 will use yaml default)"
            )
            return False

        ok = self._client.set_max_vel_x(self._target)
        if not ok:
            self._logger.warn(
                f"SpeedOverride: set max_vel_x={self._target:.2f} returned False; "
                f"skipping override"
            )
            self._original = None
            return False

        self._logger.info(
            f"SpeedOverride: max_vel_x {self._original:.2f} -> {self._target:.2f} "
            f"(requested={self._requested:.2f})"
        )
        self._applied = True
        return True

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._applied or self._original is None:
            return
        try:
            ok = self._client.set_max_vel_x(self._original)
            if ok:
                self._logger.info(
                    f"SpeedOverride: max_vel_x restored to {self._original:.2f}"
                )
            else:
                self._logger.error(
                    f"SpeedOverride: FAILED to restore max_vel_x to "
                    f"{self._original:.2f} — controller still at {self._target:.2f}!"
                )
        except Exception as restore_exc:
            self._logger.error(
                f"SpeedOverride: exception while restoring max_vel_x: {restore_exc}"
            )
```

- [ ] **Step 4:Run test to verify all pass**

```bash
python3 -m pytest nav_capability/test/test_speed_override.py -v --no-cov
```

Expected: 10 passed.

- [ ] **Step 5:Commit**

```bash
git add nav_capability/lib/speed_override.py nav_capability/test/test_speed_override.py
git commit -m "feat(nav): SpeedOverride context manager (B1 part 2)

Wraps controller_server FollowPath.max_vel_x get/set with try/finally
restore semantics. Skip on 0.0 requested or set failure (warn + continue).
Tested with FakeParamClient — no rclpy spin needed."
```

---

## Task 3: ROS2 AsyncParameterClient adapter

**Why separate task**:Task 2 的 `SpeedOverride` 不依賴 rclpy。Task 3 寫 thin adapter 讓 `nav_action_server_node` 可以 call。這層**不**單元測試(全是 rclpy I/O,mock 沒意義),靠 Task 5 整合測試覆蓋。

**Files:**
- Modify: `nav_capability/lib/speed_override.py`(加一個 adapter class)

- [ ] **Step 1:Add `RclpyParamClient` adapter to `speed_override.py`**

Append to `nav_capability/lib/speed_override.py`:
```python
import asyncio

from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import GetParameters, SetParameters


class RclpyParamClient:
    """Thin sync adapter over rclpy GetParameters/SetParameters services for
    /controller_server FollowPath.max_vel_x.

    Uses MultiThreadedExecutor-friendly blocking call_sync via service client
    spin_until_future_complete with a timeout.
    """

    PARAM_NAME = "FollowPath.max_vel_x"
    SERVICE_TIMEOUT_S = 1.0

    def __init__(self, node, target_node_name: str = "/controller_server"):
        self._node = node
        self._get_cli = node.create_client(
            GetParameters, f"{target_node_name}/get_parameters"
        )
        self._set_cli = node.create_client(
            SetParameters, f"{target_node_name}/set_parameters"
        )
        self._target_node = target_node_name

    def _wait_ready(self, cli) -> bool:
        return cli.wait_for_service(timeout_sec=self.SERVICE_TIMEOUT_S)

    def get_max_vel_x(self) -> float:
        if not self._wait_ready(self._get_cli):
            raise RuntimeError(
                f"{self._target_node}/get_parameters not available within "
                f"{self.SERVICE_TIMEOUT_S}s"
            )
        req = GetParameters.Request()
        req.names = [self.PARAM_NAME]
        future = self._get_cli.call_async(req)
        # MultiThreadedExecutor — block this callback thread on future
        rclpy_executor = self._node.executor
        if rclpy_executor is None:
            raise RuntimeError("RclpyParamClient: node has no executor attached")
        rclpy_executor.spin_until_future_complete(future, timeout_sec=self.SERVICE_TIMEOUT_S)
        if not future.done():
            raise RuntimeError("get_parameters timed out")
        result = future.result()
        if not result or not result.values:
            raise RuntimeError(f"get_parameters: empty result for {self.PARAM_NAME}")
        return float(result.values[0].double_value)

    def set_max_vel_x(self, value: float) -> bool:
        if not self._wait_ready(self._set_cli):
            return False
        req = SetParameters.Request()
        param = Parameter()
        param.name = self.PARAM_NAME
        param.value = ParameterValue()
        param.value.type = ParameterType.PARAMETER_DOUBLE
        param.value.double_value = float(value)
        req.parameters = [param]
        future = self._set_cli.call_async(req)
        rclpy_executor = self._node.executor
        if rclpy_executor is None:
            return False
        rclpy_executor.spin_until_future_complete(future, timeout_sec=self.SERVICE_TIMEOUT_S)
        if not future.done():
            return False
        result = future.result()
        if not result or not result.results:
            return False
        return bool(result.results[0].successful)
```

- [ ] **Step 2:py_compile sanity**

```bash
python3 -m py_compile nav_capability/lib/speed_override.py
```

Expected: no output(success).

- [ ] **Step 3:Verify existing tests still pass**

```bash
python3 -m pytest nav_capability/test/test_speed_override.py -v --no-cov
```

Expected: 10 passed.

- [ ] **Step 4:Commit**

```bash
git add nav_capability/lib/speed_override.py
git commit -m "feat(nav): RclpyParamClient adapter for SpeedOverride (B1 part 3)

Thin sync wrapper over /controller_server get_parameters / set_parameters
services. Uses node's MultiThreadedExecutor.spin_until_future_complete to
block within action callback. Service timeout 1.0s — fail-soft (set returns
False on timeout, get raises RuntimeError caught by SpeedOverride.__enter__)."
```

---

## Task 4: Wire SpeedOverride into `_execute_relative_inner` (B1 main fix)

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1:Add imports + create RclpyParamClient in `__init__`**

Edit `nav_action_server_node.py` imports section (after existing imports around line 30):

```python
from nav_capability.lib.speed_override import RclpyParamClient, SpeedOverride
```

In `__init__`, after the existing `self._nav_client = ActionClient(...)` block (around line 108):

```python
        # B1 — SpeedOverride param client for /controller_server FollowPath.max_vel_x
        self._speed_param_client = RclpyParamClient(self, "/controller_server")
```

- [ ] **Step 2:Replace the warn-only block in `_execute_relative_inner` (lines 318-326)**

Find this block:
```python
        # max_speed 在 v1 不會 enforce（Nav2 NavigateToPose 沒 per-goal speed override；
        # 速度上限由 nav2_params.yaml controller 設）。明確 warn 告知 caller，避免誤以為已生效。
        # 列入 spec §14 T5 範疇之後升級 (動態 set controller param)。
        if goal.max_speed > 0.0:
            self.get_logger().warn(
                f"goto_relative max_speed={goal.max_speed:.2f} ignored in v1 "
                f"(speed governed by nav2_params controller_server.{{min,max}}_vel_x). "
                f"Use ros2 param set to override controller speed if needed."
            )
```

This block stays **before** the AMCL gating but is now just a placeholder; the actual override happens around the Nav2 goal call. **Delete** this block entirely.

- [ ] **Step 3:Wrap the `_execute_nav_goal_with_pause_aware` call with `SpeedOverride`**

Find the existing call (around line 387):
```python
        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
```

Replace with:
```python
        with SpeedOverride(
            self._speed_param_client,
            requested=goal.max_speed,
            logger=self.get_logger(),
        ):
            success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
```

- [ ] **Step 4:py_compile + grep no leftover warn**

```bash
python3 -m py_compile nav_capability/nav_capability/nav_action_server_node.py
grep -n "ignored in v1" nav_capability/nav_capability/nav_action_server_node.py
```

Expected: py_compile no output. grep should still find ONE match (in `_execute_named_inner` line ~451 — that's Task 6).

- [ ] **Step 5:Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py
git commit -m "fix(nav): B1 enforce max_speed in goto_relative via SpeedOverride

Replace v1 warn-only block with SpeedOverride context manager wrapping
the Nav2 goal call. controller_server.FollowPath.max_vel_x is lowered
to goal.max_speed (clamped to GO2_MIN_VEL_X=0.45) on goal accept, restored
on goal end (success/abort/cancel/exception)."
```

---

## Task 5: B5 — capture `start_xy` at goal accept, fix `actual_distance`

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1:Add `start_xy` capture early in `_execute_relative_inner`**

Find the function definition (line 303):
```python
    async def _execute_relative_inner(self, goal_handle):
        goal = goal_handle.request
        result = GotoRelative.Result()
```

Add `start_xy` capture right after `result = ...`:
```python
    async def _execute_relative_inner(self, goal_handle):
        goal = goal_handle.request
        result = GotoRelative.Result()

        # B5 — Capture start_xy at goal accept (before AMCL gating + nav goal computation).
        # actual_distance is later computed as |current - start_xy|, so the reference must
        # be locked at goal-accept-time, not "send-time" after gating delays.
        start_xy = self._current_xy()  # may be None if amcl_pose not yet received
```

- [ ] **Step 2:Update `actual_distance` computation to use `start_xy`**

Find the current block (around line 388-394):
```python
        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
        # (after Task 4 this is wrapped in SpeedOverride)
        if success:
            result.success = True
            result.message = msg
            cur_after = self._current_map_pose()
            if cur_after is not None:
                ax, ay, _ = cur_after
                result.actual_distance = float(math.hypot(ax - cx, ay - cy))
            goal_handle.succeed()
```

Replace with:
```python
        if success:
            result.success = True
            result.message = msg
            cur_after = self._current_map_pose()
            if cur_after is not None and start_xy is not None:
                ax, ay, _ = cur_after
                sx, sy = start_xy
                result.actual_distance = float(math.hypot(ax - sx, ay - sy))
            goal_handle.succeed()
```

(Note: `cx, cy` was the pose used for `compute_relative_goal` — we keep that for the *goal* computation but use `start_xy` for *measurement*. They will usually be the same pose, but B5 acknowledges they can drift if AMCL gating takes >0.1s.)

- [ ] **Step 3:py_compile + ensure existing tests pass**

```bash
python3 -m py_compile nav_capability/nav_capability/nav_action_server_node.py
python3 -m pytest nav_capability/test/ -v --no-cov 2>&1 | tail -20
```

Expected: py_compile clean. Existing 8 test files all still pass(`test_speed_override.py` 10 passed,others unchanged).

- [ ] **Step 4:Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py
git commit -m "fix(nav): B5 use start_xy at goal accept for actual_distance

Previously actual_distance referenced cx,cy captured AFTER AMCL gating
(line 354 in pre-fix code), which could drift up to ~100ms. Now lock
start_xy at the very top of _execute_relative_inner and reference that
for the |current - start| measurement. compute_relative_goal still uses
the post-gating pose since that is what defines the relative offset."
```

---

## Task 6: Wire SpeedOverride into `_execute_named_inner` (B1 named-pose consistency)

**Why**:`_execute_named_inner` 也有同樣的 `max_speed ignored in v1` warn(line 447-452)。為一致性 + demo Wow C `approach_person` 走 `goto_named` 時可降速,一起修。

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1:Delete warn-only block at lines 447-452**

Find:
```python
        # max_speed advisory (same v1 caveat as goto_relative)
        if goal.max_speed > 0.0:
            self.get_logger().warn(
                f"goto_named max_speed={goal.max_speed:.2f} ignored in v1 "
                f"(speed governed by nav2_params controller_server)."
            )
```

Delete this block entirely.

- [ ] **Step 2:Wrap the `_execute_nav_goal_with_pause_aware` call (around line 523)**

Find:
```python
        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
```

Replace with:
```python
        with SpeedOverride(
            self._speed_param_client,
            requested=goal.max_speed,
            logger=self.get_logger(),
        ):
            success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
```

- [ ] **Step 3:Verify no more `ignored in v1` warns**

```bash
grep -n "ignored in v1" nav_capability/nav_capability/nav_action_server_node.py
```

Expected: 0 matches.

- [ ] **Step 4:py_compile**

```bash
python3 -m py_compile nav_capability/nav_capability/nav_action_server_node.py
```

Expected: no output.

- [ ] **Step 5:Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py
git commit -m "fix(nav): B1 enforce max_speed in goto_named (consistency)

goto_named had same warn-only block as goto_relative. Wrap with same
SpeedOverride context manager so approach_person (and any other
goto_named caller) can also benefit from per-goal speed control."
```

---

## Task 7: Full unit test sweep + check pkg manifests

**Files:**
- Modify: `nav_capability/setup.py`(若 lib/ 沒在 packages 列表)
- Read-only: `nav_capability/setup.cfg`、`nav_capability/test/`

- [ ] **Step 1:Confirm `nav_capability.lib` is exported**

```bash
grep -A 3 "packages=" nav_capability/setup.py
```

Expected: 看到 `packages=['nav_capability', 'nav_capability.lib']` 或 `find_packages()` 自動含。如果只有 `'nav_capability'`,加上 `'nav_capability.lib'`。

- [ ] **Step 2:Full nav_capability test sweep**

```bash
python3 -m pytest nav_capability/test/ -v --no-cov 2>&1 | tail -30
```

Expected: 全部 pass(包含 10 new test_speed_override + 既有 test files)。

- [ ] **Step 3:Run flake8 on changed files**

```bash
python3 -m flake8 nav_capability/lib/speed_override.py nav_capability/nav_capability/nav_action_server_node.py --max-line-length=120 2>&1 | head -20
```

Expected: 0 errors.如有 warning 修掉。

- [ ] **Step 4:Topic contract check (pre-commit hook 等價)**

```bash
bash scripts/hooks/check_topic_contract.sh 2>&1 | tail -10
```

Expected: PASS(B1+B5 沒動 topic schema)。

- [ ] **Step 5:Commit any cleanup if needed (otherwise skip)**

```bash
# If setup.py needed update
git add nav_capability/setup.py
git commit -m "chore(nav): ensure nav_capability.lib exported in setup.py"
```

---

## Task 8: Pre-merge實機驗收(V1 acceptance from spec)

**Why**:Unit tests cover 純邏輯。實機才能驗 0.5m goal → 0.45–0.55m 的 spec 要求。

**Files:** N/A(實機 + log)

- [ ] **Step 1:Deploy to Jetson**

按照 jetson-deploy skill 流程 sync 到 Jetson:
```bash
# 在 WSL
rsync -avz --exclude='build' --exclude='install' --exclude='log' \
  nav_capability go2_robot_sdk jetson-nano:~/elder_and_dog/
```

(注意:不帶 `--delete`、source 不帶 trailing slash — 5/3 災難教訓)

Jetson 上**不**跑 colcon build(setuptools 不相容),**editable install** 已在(若 entry_points 缺,append `~/.local/lib/python3.10/site-packages/nav_capability-*.dist-info/entry_points.txt`)。

- [ ] **Step 2:啟 demo stack**

```bash
ssh jetson-nano
cd ~/elder_and_dog
bash scripts/start_nav_capability_demo_tmux.sh
# 等 ~50s lifecycle active,Foxglove 設 initialpose
```

- [ ] **Step 3:跑 3 連發 0.5m goal,記錄 actual_distance**

```bash
# 在 monitor window
for i in 1 2 3; do
  echo "=== Run $i ==="
  ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
    "{distance: 0.5, max_speed: 0.45}" --feedback 2>&1 | tail -20
  sleep 5
done
```

Expected: 每次 result 中的 `actual_distance` 在 `[0.425, 0.575]`(target × [0.85, 1.15])。

- [ ] **Step 4:對照 max_vel_x runtime 變化**

第二個 terminal 同步監看:
```bash
watch -n 0.5 'ros2 param get /controller_server FollowPath.max_vel_x'
```

Expected: goal active 期間值降到 0.45,goal end 後恢復原值。

- [ ] **Step 5:Document outcomes in plan footer**

如果 3 連發都 PASS,寫入本檔最末「V1 Acceptance log」。如果有 fail,**停下來**先 debug 再繼續 PR 2。

---

## Pre-flight outcomes(Task 0 結果填這)

```
Date: ___
Param 實際名稱: ___
Runtime mutable: YES / NO
備註: ___
```

## V1 Acceptance log(Task 8 結果填這)

```
Date: ___
Run 1 actual_distance: ___ m  (PASS / FAIL)
Run 2 actual_distance: ___ m  (PASS / FAIL)
Run 3 actual_distance: ___ m  (PASS / FAIL)
max_vel_x watched: enter ___ → goal-end ___ → restored ___
備註: ___
```

---

## Self-Review Checklist

**Spec coverage**:
- B1 max_speed enforce → Tasks 1–4, 6 ✓
- B5 actual_distance start_pose → Task 5 ✓
- Acceptance: 0.5m → [0.425, 0.575] over 3 runs → Task 8 ✓
- Pre-flight verification (param mutable check) → Task 0 ✓

**Placeholders**:無 TBD/TODO,所有 step 皆有具體 code 與 expected output。

**Type consistency**:`SpeedOverride(client, requested, logger)` 在 Task 2/4/6 簽名一致;`RclpyParamClient.get_max_vel_x` / `set_max_vel_x` 在 Task 3/4 一致;`start_xy` 為 `Optional[Tuple[float, float]]`,Task 5 都用 None-guard。

**Out of scope / future PRs**:
- B3(`capability_publisher` param callback)、B4(YELLOW gate threshold launch param)→ PR 3 砍掉
- PR 2(B2 AMCL plateau)→ 獨立 plan
- 動態調整 PathAlign / GoalAlign 等其他 DWB params → 不在本 PR

---

## Execution Handoff

**Plan complete and saved to** `docs/navigation/plans/2026-05-04-pr1-b1-b5-implementation.md`。

兩個 execution 選項:

1. **Subagent-Driven(推薦)** — 每個 task dispatch 一個 fresh subagent,task 之間我 review 進度
2. **Inline Execution** — 用 `superpowers:executing-plans` 在這個 session 連續執行,checkpoint 給你 review

**選哪一個?** 或者你想自己手動跑(我不執行,只在卡住時 review)?
