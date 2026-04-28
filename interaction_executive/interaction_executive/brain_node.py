"""brain_node - Skill-first PawAI Brain pure-rules MVS."""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import String

from .safety_layer import SafetyLayer
from .skill_contract import (
    SKILL_REGISTRY,
    PriorityClass,
    SkillPlan,
    SkillResultStatus,
    build_plan,
)
from .world_state import WorldState


_RELIABLE_10 = QoSProfile(depth=10, reliability=QoSReliabilityPolicy.RELIABLE)
_TRANSIENT_LOCAL_1 = QoSProfile(
    depth=1,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    reliability=QoSReliabilityPolicy.RELIABLE,
)


@dataclass
class BufferedSpeech:
    session_id: str
    transcript: str
    enqueued_at: float


@dataclass
class BrainInternalState:
    unknown_face_first_seen: float | None = None
    fallen_first_seen: float | None = None
    last_alert_ts: dict[str, float] = field(default_factory=dict)
    chat_buffer: dict[str, BufferedSpeech] = field(default_factory=dict)
    dedup_cache: dict[tuple[str, str, int], float] = field(default_factory=dict)
    last_plans: deque = field(default_factory=lambda: deque(maxlen=5))
    active_plan: dict[str, Any] | None = None
    active_step: dict[str, Any] | None = None
    fallback_active: bool = False


class BrainNode(Node):
    def __init__(self) -> None:
        super().__init__("brain_node")
        self._declare_params()

        self._lock = threading.Lock()
        self._state = BrainInternalState()
        self._safety = SafetyLayer()
        self._world = WorldState(self)
        self._chat_timeouts: dict[str, rclpy.timer.Timer] = {}

        self._pub_proposal = self.create_publisher(String, "/brain/proposal", _RELIABLE_10)
        self._pub_brain_state = self.create_publisher(
            String, "/state/pawai_brain", _TRANSIENT_LOCAL_1
        )

        self.create_subscription(
            String, "/event/speech_intent_recognized", self._on_speech_intent, _RELIABLE_10
        )
        self.create_subscription(String, "/event/gesture_detected", self._on_gesture, _RELIABLE_10)
        self.create_subscription(String, "/event/face_identity", self._on_face, _RELIABLE_10)
        self.create_subscription(String, "/event/pose_detected", self._on_pose, _RELIABLE_10)
        self.create_subscription(String, "/event/object_detected", self._on_object, _RELIABLE_10)

        self.create_subscription(
            String, "/brain/chat_candidate", self._on_chat_candidate, _RELIABLE_10
        )
        self.create_subscription(String, "/brain/text_input", self._on_text_input, _RELIABLE_10)
        self.create_subscription(
            String, "/brain/skill_request", self._on_skill_request, _RELIABLE_10
        )
        self.create_subscription(String, "/brain/skill_result", self._on_skill_result, _RELIABLE_10)

        self._brain_state_timer = self.create_timer(0.5, self._publish_brain_state)
        self._dedup_gc_timer = self.create_timer(2.0, self._gc_dedup)
        self.get_logger().info(
            f"brain_node ready skills={len(SKILL_REGISTRY)} "
            f"chat_wait={self.chat_wait_ms}ms dedup={self.dedup_window_s}s"
        )

    def _declare_params(self) -> None:
        self.declare_parameter("chat_wait_ms", 1500)
        self.declare_parameter("dedup_window_s", 1.0)
        self.declare_parameter("unknown_face_accumulate_s", 3.0)
        self.declare_parameter("fallen_accumulate_s", 2.0)
        self.chat_wait_ms = int(self.get_parameter("chat_wait_ms").value)
        self.dedup_window_s = float(self.get_parameter("dedup_window_s").value)
        self.unknown_face_accumulate_s = float(
            self.get_parameter("unknown_face_accumulate_s").value
        )
        self.fallen_accumulate_s = float(self.get_parameter("fallen_accumulate_s").value)

    def _emit(self, plan: SkillPlan) -> None:
        payload = self._plan_to_dict(plan)
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._pub_proposal.publish(msg)
        with self._lock:
            self._state.last_plans.appendleft(
                {
                    "plan_id": plan.plan_id,
                    "selected_skill": plan.selected_skill,
                    "source": plan.source,
                    "priority": int(plan.priority_class),
                    "accepted": True,
                    "reason": plan.reason,
                    "created_at": plan.created_at,
                }
            )
        self.get_logger().info(
            f"PROPOSAL {plan.selected_skill} src={plan.source} reason={plan.reason}"
        )

    def _plan_to_dict(self, plan: SkillPlan) -> dict[str, Any]:
        return {
            "plan_id": plan.plan_id,
            "selected_skill": plan.selected_skill,
            "steps": [
                {"executor": step.executor.value, "args": step.args} for step in plan.steps
            ],
            "reason": plan.reason,
            "source": plan.source,
            "priority_class": int(plan.priority_class),
            "session_id": plan.session_id,
            "created_at": plan.created_at,
        }

    def _in_cooldown(self, key: str, cooldown_s: float) -> bool:
        last = self._state.last_alert_ts.get(key)
        return last is not None and (time.time() - last) < cooldown_s

    def _mark_cooldown(self, key: str) -> None:
        self._state.last_alert_ts[key] = time.time()

    def _check_dedup(self, source: str, key: str) -> bool:
        if not key:
            key = "_empty"
        now = time.time()
        bucket = int(now / max(self.dedup_window_s, 0.001))
        cache_key = (source, key, bucket)
        with self._lock:
            if cache_key in self._state.dedup_cache:
                return True
            self._state.dedup_cache[cache_key] = now
            return False

    def _gc_dedup(self) -> None:
        cutoff = time.time() - 5.0
        with self._lock:
            self._state.dedup_cache = {
                key: ts for key, ts in self._state.dedup_cache.items() if ts > cutoff
            }

    def _has_active_sequence(self) -> bool:
        with self._lock:
            active = self._state.active_plan
            return bool(active and active.get("priority_class") == int(PriorityClass.SEQUENCE))

    def _on_speech_intent(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
        session_id = str(
            payload.get("session_id") or payload.get("request_id") or f"speech-{time.time_ns()}"
        )

        plan = self._safety.hard_rule(transcript)
        if plan is not None:
            plan.session_id = session_id
            self._emit(plan)
            return

        for keyword in ("介紹你自己", "自我介紹", "你是誰"):
            if keyword in transcript:
                if not self._in_cooldown("self_introduce", 60.0):
                    self._mark_cooldown("self_introduce")
                    self._emit(
                        build_plan(
                            "self_introduce",
                            source="rule:self_introduce_keyword",
                            reason=f"keyword:{keyword}",
                            session_id=session_id,
                        )
                    )
                return

        if self._has_active_sequence() or self._check_dedup("speech", session_id):
            return

        with self._lock:
            self._state.chat_buffer[session_id] = BufferedSpeech(
                session_id=session_id,
                transcript=transcript,
                enqueued_at=time.time(),
            )
        timer = self.create_timer(
            self.chat_wait_ms / 1000.0, lambda sid=session_id: self._on_chat_timeout(sid)
        )
        self._chat_timeouts[session_id] = timer

    def _on_chat_timeout(self, session_id: str) -> None:
        timer = self._chat_timeouts.pop(session_id, None)
        if timer is not None:
            self.destroy_timer(timer)
        with self._lock:
            buffered = self._state.chat_buffer.pop(session_id, None)
            self._state.fallback_active = buffered is not None
        if buffered is None:
            return
        self._emit(
            build_plan(
                "say_canned",
                args={"text": "我聽不太懂"},
                source="rule:chat_fallback",
                reason="chat_candidate_timeout",
                session_id=session_id,
            )
        )

    def _on_chat_candidate(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        session_id = str(payload.get("session_id") or "")
        reply_text = str(payload.get("reply_text") or "").strip()
        if not session_id or not reply_text:
            return
        with self._lock:
            buffered = self._state.chat_buffer.pop(session_id, None)
            self._state.fallback_active = False
        if buffered is None:
            return
        timer = self._chat_timeouts.pop(session_id, None)
        if timer is not None:
            self.destroy_timer(timer)
        self._emit(
            build_plan(
                "chat_reply",
                args={"text": reply_text},
                source="llm_bridge",
                reason="chat_candidate_match",
                session_id=session_id,
            )
        )

    def _on_gesture(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        gesture = str(
            payload.get("gesture") or payload.get("type") or payload.get("label") or ""
        ).strip().lower()
        if gesture not in {"wave", "ok", "thumbs_up"}:
            return
        if self._has_active_sequence():
            return
        if self._check_dedup("gesture", gesture):
            return
        if self._in_cooldown("acknowledge_gesture", 3.0):
            return
        self._mark_cooldown("acknowledge_gesture")
        self._emit(
            build_plan(
                "acknowledge_gesture",
                args={"gesture": gesture},
                source="rule:gesture_ack",
                reason=f"gesture:{gesture}",
            )
        )

    def _on_face(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        identity = str(
            payload.get("identity")
            or payload.get("stable_name")
            or payload.get("name")
            or "unknown"
        ).strip()
        stable = bool(
            payload.get("identity_stable")
            or payload.get("stable")
            or payload.get("event_type") == "identity_stable"
        )

        if not identity:
            self._state.unknown_face_first_seen = None
            return
        if identity == "unknown":
            now = time.time()
            if self._state.unknown_face_first_seen is None:
                self._state.unknown_face_first_seen = now
            elif (now - self._state.unknown_face_first_seen) >= self.unknown_face_accumulate_s:
                if not self._in_cooldown("stranger_alert", 30.0):
                    self._mark_cooldown("stranger_alert")
                    self._emit(
                        build_plan(
                            "stranger_alert",
                            source="rule:unknown_face_3s",
                            reason="unknown_face_stable_3s",
                        )
                    )
                    self._state.unknown_face_first_seen = None
            return

        self._state.unknown_face_first_seen = None
        if not stable or self._has_active_sequence():
            return
        cooldown_key = f"greet_known_person:{identity}"
        if self._in_cooldown(cooldown_key, 20.0):
            return
        self._mark_cooldown(cooldown_key)
        self._emit(
            build_plan(
                "greet_known_person",
                args={"name": identity},
                source="rule:known_face",
                reason=f"identity:{identity}",
            )
        )

    def _on_pose(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        pose = str(payload.get("pose") or payload.get("posture") or "").strip().lower()
        if pose != "fallen":
            self._state.fallen_first_seen = None
            self._world.set_fallen(False)
            return
        now = time.time()
        if self._state.fallen_first_seen is None:
            self._state.fallen_first_seen = now
        elif (now - self._state.fallen_first_seen) >= self.fallen_accumulate_s:
            if not self._in_cooldown("fallen_alert", 15.0):
                self._mark_cooldown("fallen_alert")
                self._world.set_fallen(True)
                self._emit(
                    build_plan(
                        "fallen_alert",
                        source="rule:pose_fallen_2s",
                        reason="pose_fallen_stable_2s",
                    )
                )
                self._state.fallen_first_seen = None

    def _on_object(self, msg: String) -> None:
        del msg

    def _on_text_input(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        text = str(payload.get("text") or "").strip()
        if not text:
            return
        synthetic = String()
        synthetic.data = json.dumps(
            {
                "transcript": text,
                "session_id": payload.get("request_id") or f"studio-{time.time_ns()}",
                "intent": "chat",
                "confidence": 1.0,
                "source": "studio_text",
            },
            ensure_ascii=False,
        )
        self._on_speech_intent(synthetic)

    def _on_skill_request(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        skill = str(payload.get("skill") or "").strip()
        args = payload.get("args") or {}
        if skill not in SKILL_REGISTRY:
            self.get_logger().warn(f"unknown skill_request skill={skill!r}")
            return
        contract = SKILL_REGISTRY[skill]
        if contract.cooldown_s > 0 and self._in_cooldown(skill, contract.cooldown_s):
            return
        try:
            plan = build_plan(
                skill,
                args=args,
                source=str(payload.get("source") or "studio_button"),
                reason=f"studio_request:{skill}",
                session_id=payload.get("request_id"),
            )
        except (KeyError, ValueError) as exc:
            self.get_logger().warn(f"blocked skill_request skill={skill!r}: {exc}")
            return
        if contract.cooldown_s > 0:
            self._mark_cooldown(skill)
        self._emit(plan)

    def _on_skill_result(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        status = payload.get("status")
        plan_id = payload.get("plan_id")
        with self._lock:
            if status == SkillResultStatus.STARTED.value:
                self._state.active_plan = {
                    "plan_id": plan_id,
                    "selected_skill": payload.get("selected_skill"),
                    "step_index": 0,
                    "step_total": payload.get("step_total"),
                    "started_at": payload.get("timestamp", time.time()),
                    "priority_class": int(payload.get("priority_class", PriorityClass.SKILL)),
                }
            elif status == SkillResultStatus.STEP_STARTED.value:
                if self._state.active_plan and self._state.active_plan["plan_id"] == plan_id:
                    self._state.active_plan["step_index"] = payload.get("step_index")
                    self._state.active_step = {
                        "executor": payload.get("detail"),
                        "args": payload.get("step_args", {}),
                    }
            elif status in (
                SkillResultStatus.COMPLETED.value,
                SkillResultStatus.ABORTED.value,
                SkillResultStatus.BLOCKED_BY_SAFETY.value,
            ):
                if self._state.active_plan and self._state.active_plan["plan_id"] == plan_id:
                    self._state.active_plan = None
                    self._state.active_step = None

            for plan in self._state.last_plans:
                if plan.get("plan_id") == plan_id:
                    if status == SkillResultStatus.BLOCKED_BY_SAFETY.value:
                        plan["accepted"] = False
                    break

    def _publish_brain_state(self) -> None:
        snap = self._world.snapshot()
        with self._lock:
            active_plan = dict(self._state.active_plan) if self._state.active_plan else None
            active_step = dict(self._state.active_step) if self._state.active_step else None
            last_plans = list(self._state.last_plans)
            cooldowns = dict(self._state.last_alert_ts)
            fallback_active = self._state.fallback_active
        mode = self._mode_from_active(active_plan)
        payload = {
            "timestamp": time.time(),
            "mode": mode,
            "active_plan": active_plan,
            "active_step": active_step,
            "fallback_active": fallback_active,
            "safety_flags": {
                "obstacle": snap.obstacle,
                "emergency": snap.emergency,
                "fallen": snap.fallen,
                "tts_playing": snap.tts_playing,
                "nav_safe": snap.nav_safe,
            },
            "cooldowns": cooldowns,
            "last_plans": last_plans,
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._pub_brain_state.publish(msg)

    def _mode_from_active(self, active_plan: dict[str, Any] | None) -> str:
        if not active_plan:
            return "idle"
        priority = int(active_plan.get("priority_class", PriorityClass.SKILL))
        if priority == int(PriorityClass.SAFETY):
            return "safety_stop"
        if priority == int(PriorityClass.ALERT):
            return "alert"
        if priority == int(PriorityClass.SEQUENCE):
            return "sequence"
        if priority == int(PriorityClass.CHAT):
            return "chat"
        return "skill"

    def _load_json(self, msg: String) -> dict[str, Any] | None:
        try:
            data = json.loads(msg.data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None


def main(args=None):
    rclpy.init(args=args)
    node = BrainNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
