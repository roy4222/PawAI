"""interaction_executive_node - Brain-driven single action outlet."""
from __future__ import annotations

import functools
import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String

try:
    from go2_interfaces.msg import WebRtcReq
except ImportError:  # pragma: no cover - local unit environments may lack generated msgs
    WebRtcReq = None

try:
    from go2_interfaces.action import GotoRelative
except ImportError:  # pragma: no cover - local unit environments may lack generated actions
    GotoRelative = None

from pawai_contracts.trace_schema import TraceEvent, TraceKind, Verdict

from .safety_layer import SafetyLayer
from .skill_contract import (
    BANNED_API_IDS,
    MOTION_NAME_MAP,
    ExecutorKind,
    PriorityClass,
    SkillPlan,
    SkillResultStatus,
    SkillStep,
)
from .skill_queue import SkillQueue
from .world_state import WorldState


_RELIABLE_10 = QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE)
_RELIABLE_20 = QoSProfile(depth=20, reliability=QoSReliabilityPolicy.RELIABLE)


@dataclass
class _ActiveStep:
    plan: SkillPlan
    step_index: int
    started_at: float
    is_tts_step: bool
    is_nav_step: bool = False


# 2026-06-10 issue #129: NAV step 的 goal 參數安全上限（demo 室內短距）。
_NAV_DISTANCE_MIN_M = -1.0
_NAV_DISTANCE_MAX_M = 1.5
_NAV_YAW_MAX_RAD = 1.57


class InteractionExecutiveNode(Node):
    def __init__(self) -> None:
        super().__init__("interaction_executive_node")
        self.declare_parameter("step_settle_s", 0.4)
        self.declare_parameter("tts_idle_timeout_s", 6.0)
        # 2026-06-10 issue #129: NAV executor（/nav/goto_relative bridge）。
        # 安全預設關 — false 時 NAV step 一律 fail-closed（nav_executor_disabled）。
        # 上機 nav stack 測試時 `ros2 param set /interaction_executive_node
        # nav_executor_enabled true` 即時打開（runtime callback 支援）。
        self.declare_parameter("nav_executor_enabled", False)
        self.declare_parameter("nav_step_timeout_s", 30.0)
        self.step_settle_s = float(self.get_parameter("step_settle_s").value)
        self.tts_idle_timeout_s = float(self.get_parameter("tts_idle_timeout_s").value)
        self.nav_executor_enabled = bool(self.get_parameter("nav_executor_enabled").value)
        self.nav_step_timeout_s = float(self.get_parameter("nav_step_timeout_s").value)
        self.add_on_set_parameters_callback(self._on_set_params)

        self._safety = SafetyLayer()
        self._world = WorldState(self)
        self._queue = SkillQueue()
        self._active: _ActiveStep | None = None
        self._lock = threading.Lock()

        self._pub_tts = self.create_publisher(String, "/tts", 10)
        self._pub_webrtc = (
            self.create_publisher(WebRtcReq, "/webrtc_req", 10)
            if WebRtcReq is not None
            else None
        )
        self._pub_skill_result = self.create_publisher(
            String, "/brain/skill_result", _RELIABLE_20
        )
        # Plan E: decision-chain trace mirror — IE reports safety BLOCKED
        # verdicts on the same /brain/trace channel as brain_node.
        self._pub_trace = self.create_publisher(String, "/brain/trace", _RELIABLE_20)

        # NAV action client lazy-created on first NAV step（避免無 nav stack 環境
        # 建 client 的 discovery 開銷）；_nav_state 是當前 in-flight goal 的狀態。
        self._nav_client = None
        self._nav_state: dict[str, Any] | None = None

        self.create_subscription(String, "/brain/proposal", self._on_proposal, _RELIABLE_10)
        self._tick = self.create_timer(0.1, self._worker_tick)
        self.get_logger().info("interaction_executive_node ready (Brain MVS)")

    def _on_set_params(self, params):
        """Runtime param callback — demo 現場免重啟切 NAV executor。"""
        from rcl_interfaces.msg import SetParametersResult

        for p in params:
            if p.name == "nav_executor_enabled":
                self.nav_executor_enabled = bool(p.value)
                self.get_logger().info(
                    f"nav_executor_enabled set to {self.nav_executor_enabled}"
                )
            elif p.name == "nav_step_timeout_s":
                self.nav_step_timeout_s = float(p.value)
                self.get_logger().info(f"nav_step_timeout_s set to {self.nav_step_timeout_s}")
        return SetParametersResult(successful=True)

    def _trace_safety_block(self, data: dict[str, Any], plan, reason) -> None:
        """Plan E: mirror a safety BLOCKED verdict onto /brain/trace.

        decision_id comes from the proposal payload (additive field, empty for
        pre-Plan-E senders). NEVER raises — additive instrumentation only."""
        try:
            trace_msg = String()
            trace_msg.data = TraceEvent(
                decision_id=str(data.get("decision_id") or ""),
                node="interaction_executive", kind=TraceKind.SKILL_RESULT,
                verdict=Verdict.BLOCKED, gate="safety",
                reason=str(reason or "blocked_by_safety"),
                plan_id=str(plan.plan_id or ""),
                detail={"skill": plan.selected_skill},
            ).to_json()
            self._pub_trace.publish(trace_msg)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"trace publish failed: {exc}")

    def _on_proposal(self, msg: String) -> None:
        data = self._load_json(msg)
        if data is None:
            return
        try:
            plan = self._plan_from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            self.get_logger().warn(f"invalid SkillPlan payload: {exc}")
            return

        validation = self._safety.validate(plan, self._world.snapshot())
        if not validation.ok:
            self._emit_result(
                plan,
                None,
                SkillResultStatus.BLOCKED_BY_SAFETY,
                detail=validation.reason,
            )
            self._trace_safety_block(data, plan, validation.reason)
            return

        self._emit_result(plan, None, SkillResultStatus.ACCEPTED, detail=plan.selected_skill)
        if plan.priority_class in (PriorityClass.SAFETY, PriorityClass.ALERT):
            preempted = self._queue.clear(reason="preempted")
            for item in preempted:
                self._emit_result(item.plan, None, SkillResultStatus.ABORTED, detail=item.reason)
            with self._lock:
                if self._active is not None:
                    # 2026-06-10 review blocker: SAFETY/ALERT 搶佔（含 fallen/stop）
                    # 必須先取消 in-flight NAV goal，否則 Go2 會在緊急事件當下繼續
                    # 走完 goto，且 single-goal nav_action_server 會被 orphaned goal
                    # 卡住後續所有 goto（6/8 Track B 已知陷阱）。
                    if self._active.is_nav_step:
                        self._cancel_active_nav_goal()
                    self._emit_result(
                        self._active.plan,
                        self._active.step_index,
                        SkillResultStatus.ABORTED,
                        detail="preempted_by_higher_priority",
                    )
                    self._active = None
            self._queue.push_front(plan)
        else:
            self._queue.push(plan)

    def _worker_tick(self) -> None:
        with self._lock:
            if self._active is not None:
                if not self._active_step_done(self._active):
                    return
                active = self._active
                # NAV step 是唯一「started 之後還可能失敗」的 step：
                # action result 失敗 / timeout → STEP_FAILED + 丟棄整個 plan。
                nav_fail_detail = self._consume_nav_step_failure(active)
                if nav_fail_detail is not None:
                    self._emit_result(
                        active.plan,
                        active.step_index,
                        SkillResultStatus.STEP_FAILED,
                        detail=nav_fail_detail,
                        step_args=active.plan.steps[active.step_index].args,
                    )
                    self._active = None
                    self._queue.pop()
                    return
                self._emit_result(
                    active.plan,
                    active.step_index,
                    SkillResultStatus.STEP_SUCCESS,
                    detail=active.plan.steps[active.step_index].executor.value,
                    step_args=active.plan.steps[active.step_index].args,
                )
                self._active = None

            plan = self._queue.peek()
            if plan is None:
                return
            if not getattr(plan, "_started", False):
                self._emit_result(plan, None, SkillResultStatus.STARTED)
                plan._started = True
                plan._next_index = 0

            if plan._next_index >= len(plan.steps):
                self._emit_result(plan, None, SkillResultStatus.COMPLETED)
                self._queue.pop()
                return

            step = plan.steps[plan._next_index]
            step_index = plan._next_index
            self._emit_result(
                plan,
                step_index,
                SkillResultStatus.STEP_STARTED,
                detail=step.executor.value,
                step_args=step.args,
            )
            ok, detail = self._dispatch_step(step)
            if not ok:
                self._emit_result(
                    plan,
                    step_index,
                    SkillResultStatus.STEP_FAILED,
                    detail=detail,
                    step_args=step.args,
                )
                self._queue.pop()
                return
            self._active = _ActiveStep(
                plan=plan,
                step_index=step_index,
                started_at=time.time(),
                is_tts_step=step.executor == ExecutorKind.SAY,
                is_nav_step=step.executor == ExecutorKind.NAV,
            )
            plan._next_index += 1

    def _consume_nav_step_failure(self, active: _ActiveStep) -> str | None:
        """NAV step 結束時收割結果；回傳失敗 detail（None=成功）。同時清 _nav_state。"""
        if not active.is_nav_step:
            return None
        state = self._nav_state
        self._nav_state = None
        if state is None:
            return "nav_state_lost"
        if not state.get("ok", False):
            return str(state.get("detail") or "nav_failed")
        return None

    def _active_step_done(self, active: _ActiveStep) -> bool:
        age = time.time() - active.started_at
        if age < self.step_settle_s:
            return False
        if active.is_nav_step:
            return self._nav_step_done(age)
        if not active.is_tts_step:
            return True
        snap = self._world.snapshot()
        return not snap.tts_playing or age >= self.tts_idle_timeout_s

    def _nav_step_done(self, age: float) -> bool:
        """Poll in-flight NAV goal — done 條件：action 結束 或 timeout（cancel 後收掉）。"""
        state = self._nav_state
        if state is None:
            return True  # defensive — 沒有 state 視為失敗結束（worker 會報 nav_state_lost）
        if state.get("phase") == "done":
            return True
        if age >= self.nav_step_timeout_s:
            handle = state.get("goal_handle")
            if handle is not None and not state.get("cancel_sent"):
                try:
                    handle.cancel_goal_async()
                except Exception as exc:  # pragma: no cover — best-effort cancel
                    self.get_logger().warn(f"NAV cancel failed: {exc}")
                state["cancel_sent"] = True
            state["phase"] = "done"
            state["ok"] = False
            state["detail"] = "nav_timeout"
            self.get_logger().warn(f"NAV step timeout after {age:.1f}s — goal cancelled")
            return True
        return False

    def _dispatch_step(self, step: SkillStep) -> tuple[bool, str]:
        if step.executor == ExecutorKind.SAY:
            text = str(step.args.get("text", ""))
            if not text:
                return False, "empty_tts_text"
            # input_origin: per-message TTS routing hint (5/7 plan
            # polished-questing-starlight). studio_text → tts_node Gemini
            # chain; absent → plain text → edge_tts default. All perception
            # SAY steps (no input_origin AND no source) keep byte-identical wire format.
            input_origin = step.args.get("input_origin")
            source = step.args.get("source")
            msg = String()
            if input_origin or source:
                envelope: dict = {"text": text}
                if input_origin:
                    envelope["input_origin"] = input_origin
                if source:
                    envelope["source"] = source
                msg.data = json.dumps(envelope, ensure_ascii=False)
            else:
                msg.data = text
            self._pub_tts.publish(msg)
            return True, "ok"

        if step.executor == ExecutorKind.MOTION:
            name = step.args.get("name")
            api_id = MOTION_NAME_MAP.get(name)
            if api_id is None:
                return False, f"unknown_motion:{name!r}"
            if api_id in BANNED_API_IDS:
                return False, f"banned_api:{api_id}"
            if self._pub_webrtc is None or WebRtcReq is None:
                self.get_logger().warn(f"WebRtcReq unavailable; dry-run motion {name}")
                return True, "dry_run_webrtc_unavailable"
            req = WebRtcReq()
            req.id = 0
            req.topic = "rt/api/sport/request"
            req.api_id = int(api_id)
            req.parameter = str(api_id)
            req.priority = 0
            self._pub_webrtc.publish(req)
            return True, "ok"

        if step.executor == ExecutorKind.NAV:
            return self._dispatch_nav(step)

        return False, f"unknown_executor:{step.executor}"

    def _dispatch_nav(self, step: SkillStep) -> tuple[bool, str]:
        """2026-06-10 issue #129: NAV step → /nav/goto_relative action（async dispatch）。

        Fail-closed 鏈（typed reasons，依序）：
          nav_executor_enabled=False → nav_executor_disabled（預設，保 Phase A 行為）
          action != goto_relative   → nav_action_unsupported:<action>
          go2_interfaces 缺 action  → nav_interfaces_unavailable
          world gate 不過           → nav_gate:{nav_ready|depth_clear|nav_paused|emergency}
          action server 不在        → nav_server_unavailable
        dispatch 不阻塞（single-threaded executor）：goal 非同步送出，
        完成/失敗/timeout 由 _nav_step_done @10Hz tick 輪詢。
        """
        if not self.nav_executor_enabled:
            self.get_logger().warn(f"NAV executor disabled — skipping {step.args}")
            return False, "nav_executor_disabled"
        action = str(step.args.get("action") or "")
        if action != "goto_relative":
            return False, f"nav_action_unsupported:{action}"
        if GotoRelative is None:
            return False, "nav_interfaces_unavailable"

        snap = self._world.snapshot()
        if not snap.nav_ready:
            return False, "nav_gate:nav_ready"
        if not snap.depth_clear:
            return False, "nav_gate:depth_clear"
        if snap.nav_paused:
            return False, "nav_gate:nav_paused"
        if snap.emergency:
            return False, "nav_gate:emergency"

        distance = float(step.args.get("distance", 0.5))
        distance = max(_NAV_DISTANCE_MIN_M, min(_NAV_DISTANCE_MAX_M, distance))
        yaw_offset = float(step.args.get("yaw_offset", 0.0))
        yaw_offset = max(-_NAV_YAW_MAX_RAD, min(_NAV_YAW_MAX_RAD, yaw_offset))

        if self._nav_client is None:
            self._nav_client = ActionClient(self, GotoRelative, "/nav/goto_relative")
        if not self._nav_client.server_is_ready():
            return False, "nav_server_unavailable"

        goal = GotoRelative.Goal()
        goal.distance = float(distance)
        goal.yaw_offset = float(yaw_offset)
        goal.max_speed = 0.0  # v1 advisory — 實際速度由 nav2 controller 管
        self._nav_state = {
            "phase": "sending",
            "ok": False,
            "detail": "nav_pending",
            "goal_handle": None,
            "cancel_sent": False,
        }
        send_future = self._nav_client.send_goal_async(goal)
        # 2026-06-10 review: callback 綁定「自己這次 goal 的 state dict」（functools.partial），
        # 不讀 self._nav_state — 否則舊 goal 的遲到 result 會寫進下一個 NAV step 的 state、
        # 污染新 goal 的 lifecycle（timeout cancel 後 ~10-200ms 必有遲到 CANCELED）。
        send_future.add_done_callback(functools.partial(self._on_nav_goal_response, self._nav_state))
        self.get_logger().info(
            f"NAV goto_relative dispatched distance={distance:.2f}m yaw={yaw_offset:.2f}rad"
        )
        return True, f"nav_goal_sent:{distance:.2f}m"

    def _cancel_active_nav_goal(self) -> None:
        """Best-effort cancel 當前 in-flight NAV goal 並棄置其 state（搶佔/緊急用）。

        呼叫端需持 self._lock。state dict 一旦置 None，遲到的 send/result callback
        會因 'state is not self._nav_state' guard 直接 no-op。
        """
        state = self._nav_state
        self._nav_state = None
        if state is None:
            return
        handle = state.get("goal_handle")
        if handle is not None and not state.get("cancel_sent"):
            try:
                handle.cancel_goal_async()
            except Exception as exc:  # pragma: no cover — best-effort cancel
                self.get_logger().warn(f"NAV preempt cancel failed: {exc}")
            state["cancel_sent"] = True
        self.get_logger().info("NAV in-flight goal cancelled (preempted)")

    def _on_nav_goal_response(self, state, future) -> None:
        # state 是 dispatch 時綁定的那次 goal 的 dict；若已被 timeout/preempt 換掉就 no-op。
        if state is not self._nav_state:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:  # noqa: BLE001 — action send 失敗一律收斂成 step fail
            state.update(phase="done", ok=False, detail=f"nav_send_error:{exc}")
            return
        if not goal_handle.accepted:
            state.update(phase="done", ok=False, detail="nav_goal_rejected")
            self.get_logger().warn("NAV goal rejected by /nav/goto_relative")
            return
        state["goal_handle"] = goal_handle
        state["phase"] = "active"
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(functools.partial(self._on_nav_result, state))

    def _on_nav_result(self, state, future) -> None:
        if state is not self._nav_state:
            return
        try:
            result = future.result().result
        except Exception as exc:  # noqa: BLE001
            state.update(phase="done", ok=False, detail=f"nav_result_error:{exc}")
            return
        success = bool(getattr(result, "success", False))
        message = str(getattr(result, "message", ""))
        actual = float(getattr(result, "actual_distance", 0.0))
        state.update(
            phase="done",
            ok=success,
            detail=(
                f"nav_reached:{actual:.2f}m" if success else f"nav_failed:{message or 'unknown'}"
            ),
        )
        self.get_logger().info(
            f"NAV result success={success} message={message!r} actual={actual:.2f}m"
        )

    def _emit_result(
        self,
        plan: SkillPlan,
        step_index: int | None,
        status: SkillResultStatus,
        *,
        detail: str = "",
        step_args: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "plan_id": plan.plan_id,
            "step_index": step_index,
            "status": status.value,
            "detail": detail,
            "selected_skill": plan.selected_skill,
            "priority_class": int(plan.priority_class),
            "step_total": len(plan.steps),
            "step_args": step_args or {},
            "timestamp": time.time(),
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._pub_skill_result.publish(msg)

    def _plan_from_dict(self, data: dict[str, Any]) -> SkillPlan:
        return SkillPlan(
            plan_id=str(data["plan_id"]),
            selected_skill=str(data["selected_skill"]),
            steps=[
                SkillStep(ExecutorKind(step["executor"]), dict(step.get("args") or {}))
                for step in data["steps"]
            ],
            reason=str(data.get("reason", "")),
            source=str(data.get("source", "")),
            priority_class=PriorityClass(int(data["priority_class"])),
            session_id=data.get("session_id"),
            created_at=float(data.get("created_at", time.time())),
        )

    def _load_json(self, msg: String) -> dict[str, Any] | None:
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None


def main(args=None):
    rclpy.init(args=args)
    node = InteractionExecutiveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
