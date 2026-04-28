"""interaction_executive_node - Brain-driven single action outlet."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String

try:
    from go2_interfaces.msg import WebRtcReq
except ImportError:  # pragma: no cover - local unit environments may lack generated msgs
    WebRtcReq = None

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


class InteractionExecutiveNode(Node):
    def __init__(self) -> None:
        super().__init__("interaction_executive_node")
        self.declare_parameter("step_settle_s", 0.4)
        self.declare_parameter("tts_idle_timeout_s", 6.0)
        self.step_settle_s = float(self.get_parameter("step_settle_s").value)
        self.tts_idle_timeout_s = float(self.get_parameter("tts_idle_timeout_s").value)

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

        self.create_subscription(String, "/brain/proposal", self._on_proposal, _RELIABLE_10)
        self._tick = self.create_timer(0.1, self._worker_tick)
        self.get_logger().info("interaction_executive_node ready (Brain MVS)")

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
            return

        self._emit_result(plan, None, SkillResultStatus.ACCEPTED, detail=plan.selected_skill)
        if plan.priority_class in (PriorityClass.SAFETY, PriorityClass.ALERT):
            preempted = self._queue.clear(reason="preempted")
            for item in preempted:
                self._emit_result(item.plan, None, SkillResultStatus.ABORTED, detail=item.reason)
            with self._lock:
                if self._active is not None:
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
            )
            plan._next_index += 1

    def _active_step_done(self, active: _ActiveStep) -> bool:
        age = time.time() - active.started_at
        if age < self.step_settle_s:
            return False
        if not active.is_tts_step:
            return True
        snap = self._world.snapshot()
        return not snap.tts_playing or age >= self.tts_idle_timeout_s

    def _dispatch_step(self, step: SkillStep) -> tuple[bool, str]:
        if step.executor == ExecutorKind.SAY:
            text = str(step.args.get("text", ""))
            if not text:
                return False, "empty_tts_text"
            msg = String()
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
            self.get_logger().warn(f"NAV executor is not implemented in Phase A: {step.args}")
            return False, "nav_unimplemented_phase_a"

        return False, f"unknown_executor:{step.executor}"

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
