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

from .pending_confirm import (
    ConfirmOutcomeKind,
    ConfirmState,
    PendingConfirm,
)
from .safety_layer import SafetyLayer
from .skill_contract import (
    SKILL_REGISTRY,
    PriorityClass,
    SkillPlan,
    SkillResultStatus,
    build_plan,
)
from .world_state import WorldState


# Mirror of object_perception/coco_classes.py:COCO_CLASSES_ZH (whitelist subset)
# and pawai-studio/frontend/components/object/object-config.ts. Three copies are
# self-contained on purpose — sharing a Python module across ROS2 packages would
# couple build/install order. Keep all three in sync when whitelist changes.
OBJECT_CLASS_ZH: dict[str, str] = {
    "cup": "杯子", "bottle": "瓶子", "book": "書",
    "person": "人", "dog": "狗狗", "cat": "貓咪",
    "chair": "椅子", "couch": "沙發", "bed": "床",
    "dining_table": "餐桌", "tv": "電視", "laptop": "筆電",
    "cell_phone": "手機", "remote": "遙控器", "keyboard": "鍵盤",
    "mouse": "滑鼠", "backpack": "背包", "handbag": "手提包",
    "umbrella": "雨傘", "clock": "時鐘", "vase": "花瓶",
    "potted_plant": "盆栽", "teddy_bear": "玩偶", "scissors": "剪刀",
    "wine_glass": "酒杯", "fork": "叉子", "knife": "刀子",
    "spoon": "湯匙", "bowl": "碗", "banana": "香蕉",
    "apple": "蘋果", "orange": "橘子",
}
OBJECT_COLOR_ZH: dict[str, str] = {
    "red": "紅色", "orange": "橘色", "yellow": "黃色", "green": "綠色",
    "cyan": "青色", "blue": "藍色", "purple": "紫色", "pink": "粉紅色",
    "brown": "咖啡色", "black": "黑色", "white": "白色", "gray": "灰色",
}
# Personality phrases — appended AFTER the colour-aware preamble (per 5/6
# user feedback). Never replace the preamble; user wants both colour
# announcement and the playful phrase.
OBJECT_TTS_SPECIAL_SUFFIX: dict[str, str] = {
    "cup": "，你要喝水嗎？",
    "bottle": "，喝點水吧",
    "book": "，在看書啊",
}

# Per-(class, color) speaking dedup. SkillContract.cooldown_s=5 only stops the
# *skill* from re-firing; it doesn't stop the same chair being announced every
# 5s when YOLO keeps detecting it. 60s here means "PAI mentioned this exact
# coloured object recently — shut up." Cleared by _gc_object_remark_seen.
OBJECT_REMARK_DEDUP_S = 60.0


def build_object_tts(class_name: str, color: str | None) -> str | None:
    """Compose object_remark TTS string, or None when class is outside the
    PawAI TTS whitelist (UI still shows it; PawAI just stays quiet).

    Examples:
        build_object_tts("cup", "red")     == "看到紅色的杯子了，你要喝水嗎？"
        build_object_tts("laptop", "blue") == "看到藍色的筆電了"
        build_object_tts("cup", "Unknown") == "看到杯子了，你要喝水嗎？"
        build_object_tts("frisbee", "red") is None
    """
    if not class_name or class_name not in OBJECT_CLASS_ZH:
        return None
    # 5/7 night demo silence: don't say "看到X色的人了". Person detection
    # collides with face/stranger_alert path AND repeats every time YOLO
    # ticks during conversation. Studio chip still shows the detection.
    if class_name == "person":
        return None
    class_zh = OBJECT_CLASS_ZH[class_name]
    if color and color != "Unknown" and color in OBJECT_COLOR_ZH:
        preamble = f"看到{OBJECT_COLOR_ZH[color]}的{class_zh}了"
    else:
        preamble = f"看到{class_zh}了"
    return preamble + OBJECT_TTS_SPECIAL_SUFFIX.get(class_name, "")


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
    sitting_first_seen: float | None = None
    bending_first_seen: float | None = None
    last_alert_ts: dict[str, float] = field(default_factory=dict)
    chat_buffer: dict[str, BufferedSpeech] = field(default_factory=dict)
    dedup_cache: dict[tuple[str, str, int], float] = field(default_factory=dict)
    last_plans: deque = field(default_factory=lambda: deque(maxlen=5))
    active_plan: dict[str, Any] | None = None
    active_step: dict[str, Any] | None = None
    fallback_active: bool = False
    # PendingConfirm gesture tracker (gesture is "live" for 0.5s after seen)
    current_gesture: str | None = None
    current_gesture_ts: float = 0.0


class BrainNode(Node):
    def __init__(self) -> None:
        super().__init__("brain_node")
        self._declare_params()

        self._lock = threading.Lock()
        self._state = BrainInternalState()
        self._safety = SafetyLayer()
        self._world = WorldState(self)
        self._chat_timeouts: dict[str, rclpy.timer.Timer] = {}
        self._pending_confirm = PendingConfirm(timeout_s=5.0, stable_s=0.5)
        self._gesture_live_window_s = 0.5
        # Per-(class, color) → last-emit-ts. See OBJECT_REMARK_DEDUP_S.
        self._object_remark_seen: dict[tuple[str, str], float] = {}

        self._pub_proposal = self.create_publisher(String, "/brain/proposal", _RELIABLE_10)
        self._pub_brain_state = self.create_publisher(
            String, "/state/pawai_brain", _TRANSIENT_LOCAL_1
        )
        self.conversation_trace_pub = self.create_publisher(
            String, "/brain/conversation_trace", _RELIABLE_10
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
        self._confirm_tick_timer = self.create_timer(0.1, self._tick_pending_confirm)  # 10Hz
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

        # Note: self_introduce + show_status keyword bypasses removed 2026-05-05.
        # Reasons:
        #   1. self_introduce contains MOTION steps which SafetyLayer blocks
        #      when D435 sees the user up close → silent failure.
        #   2. The persona already handles 「你是誰」/「狀態」 naturally via
        #      chat_reply, with full conversation memory + audio tags.
        #   3. Keeping fewer keyword bypasses = more "pet-like" personality
        #      driven by LLM, less rule-driven.
        # MOTION-version self_introduce can still be triggered via Studio button.

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
        engine = str(payload.get("engine") or "legacy")
        if not session_id:
            return

        with self._lock:
            buffered = self._state.chat_buffer.pop(session_id, None)
            self._state.fallback_active = False

        # Stale candidate (session already timed out / unknown) — drop everything.
        if buffered is None:
            return

        # 1. Always speak the reply (if non-empty).
        if reply_text:
            timer = self._chat_timeouts.pop(session_id, None)
            if timer is not None:
                self.destroy_timer(timer)
            # input_origin: forwarded from pawai_brain ChatCandidatePayload.
            # When set ("studio_text"), IE-node SAY wraps /tts as JSON envelope
            # so tts_node routes to Gemini chain. None → plain text → edge_tts.
            input_origin = payload.get("input_origin")
            plan_args: dict[str, Any] = {"text": reply_text}
            if input_origin:
                plan_args["input_origin"] = input_origin
            self._emit(
                build_plan(
                    "chat_reply",
                    args=plan_args,
                    source="llm_bridge",
                    reason="chat_candidate_match",
                    session_id=session_id,
                )
            )

        # 2. Optional skill proposal — independent side effect.
        proposed_skill = payload.get("proposed_skill")
        if not isinstance(proposed_skill, str) or not proposed_skill:
            return
        proposed_args = payload.get("proposed_args") or {}
        if not isinstance(proposed_args, dict):
            proposed_args = {}

        if proposed_skill not in self.LLM_PROPOSABLE_SKILLS:
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="rejected_not_allowed",
                detail=proposed_skill,
            )
            return

        cd = SKILL_REGISTRY[proposed_skill].cooldown_s
        if self._in_cooldown(proposed_skill, cd):
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="blocked",
                detail=f"{proposed_skill}:cooldown",
            )
            return

        mode = self.LLM_PROPOSAL_EXECUTE.get(proposed_skill, "trace_only")
        if mode == "execute":
            self._emit_with_cooldown(
                proposed_skill,
                args=proposed_args,
                source="llm_proposal",
                reason=f"llm_proposal:{proposed_skill}",
            )
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="accepted",
                detail=proposed_skill,
            )
        elif mode == "confirm":
            # Reuse the gesture-confirm machinery — LLM's chat_reply already
            # asked the user to OK, so we don't emit an extra say_canned hint
            # (avoids "好啊我搖一下 + 比 OK 我就做 wiggle" double prompt).
            self._pending_confirm.request_confirm(
                proposed_skill, proposed_args, time.time()
            )
            self.get_logger().info(
                f"PendingConfirm requested via llm_proposal skill={proposed_skill}"
            )
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="needs_confirm",
                detail=proposed_skill,
            )
        else:  # trace_only
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="accepted_trace_only",
                detail=proposed_skill,
            )

    # Phase 0.5 LLM proposal gate (spec 2026-05-06 §6)
    # Phase A.6 (5/8 expansion): 8 skills + new "confirm" mode
    LLM_PROPOSABLE_SKILLS = frozenset({
        "show_status",
        "self_introduce",
        "wave_hello",
        "sit_along",
        "greet_known_person",
        "careful_remind",
        "wiggle",
        "stretch",
    })
    LLM_PROPOSAL_EXECUTE = {
        "show_status": "execute",
        "self_introduce": "trace_only",
        "wave_hello": "execute",
        "sit_along": "execute",
        "greet_known_person": "execute",
        "careful_remind": "execute",
        "wiggle": "confirm",
        "stretch": "confirm",
    }

    # Phase B v1 gesture mapping (spec §4.2 + impl notes 2026-05-04 §2):
    #   wave         → wave_hello       (low-risk, direct)
    #   palm         → system_pause     (safety-immediate, direct)
    #   thumbs_up    → wiggle           (high-risk, request OK confirm)
    #   peace        → stretch          (high-risk, request OK confirm)
    #   ok           → consumed by PendingConfirm.tick (no direct skill fire)
    _GESTURE_DIRECT = {"wave": "wave_hello", "palm": "system_pause"}
    _GESTURE_CONFIRM = {"thumbs_up": "wiggle", "peace": "stretch"}

    def _on_gesture(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        gesture = str(
            payload.get("gesture") or payload.get("type") or payload.get("label") or ""
        ).strip().lower()
        if not gesture:
            return

        # Update gesture tracker so PendingConfirm tick can see it.
        with self._lock:
            self._state.current_gesture = gesture
            self._state.current_gesture_ts = time.time()

        # If a confirm is already in flight, gestures only feed the state machine
        # via the periodic tick — don't fire new skills.
        if self._pending_confirm.state == ConfirmState.PENDING:
            return

        if self._has_active_sequence():
            return
        if self._check_dedup("gesture", gesture):
            return

        if gesture in self._GESTURE_DIRECT:
            skill = self._GESTURE_DIRECT[gesture]
            self._emit_with_cooldown(
                skill,
                source="rule:gesture",
                reason=f"gesture:{gesture}",
            )
            return

        if gesture in self._GESTURE_CONFIRM:
            skill = self._GESTURE_CONFIRM[gesture]
            cd = SKILL_REGISTRY[skill].cooldown_s
            if self._in_cooldown(skill, cd):
                return
            self._pending_confirm.request_confirm(skill, {}, time.time())
            self.get_logger().info(f"PendingConfirm requested skill={skill} via gesture={gesture}")
            # Voice hint asking for OK (uses say_canned, has audio tag stripped).
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": f"[curious] 比 OK 我就做 {skill}"},
                    source="rule:confirm_request",
                    reason=f"awaiting_ok:{skill}",
                )
            )

    def _tick_pending_confirm(self) -> None:
        """10Hz tick — feed live gesture into PendingConfirm and act on outcome."""
        if self._pending_confirm.state == ConfirmState.IDLE:
            return
        now = time.time()
        with self._lock:
            gesture = self._state.current_gesture
            ts = self._state.current_gesture_ts
        if gesture and (now - ts) > self._gesture_live_window_s:
            gesture = None  # stale — treat as no gesture
        outcome = self._pending_confirm.tick(now, gesture)
        if outcome.kind == ConfirmOutcomeKind.CONFIRMED:
            skill = outcome.skill
            assert skill is not None
            self._mark_cooldown(skill)
            self._emit(
                build_plan(
                    skill,
                    args=outcome.args,
                    source="rule:confirmed",
                    reason=f"confirmed_via_ok:{skill}",
                )
            )
        elif outcome.kind == ConfirmOutcomeKind.CANCELLED:
            self.get_logger().info(f"PendingConfirm CANCELLED reason={outcome.reason}")

    def _emit_with_cooldown(
        self,
        skill: str,
        args: dict[str, Any] | None = None,
        source: str = "rule",
        reason: str = "",
        session_id: str | None = None,
    ) -> bool:
        """Build + emit a plan if skill is not in cooldown. Returns True if emitted."""
        contract = SKILL_REGISTRY[skill]
        cd = contract.cooldown_s
        if cd > 0 and self._in_cooldown(skill, cd):
            return False
        try:
            plan = build_plan(
                skill,
                args=args or {},
                source=source,
                reason=reason or f"emit:{skill}",
                session_id=session_id,
            )
        except (KeyError, ValueError) as exc:
            self.get_logger().warn(f"emit_with_cooldown blocked skill={skill!r}: {exc}")
            return False
        if cd > 0:
            self._mark_cooldown(skill)
        self._emit(plan)
        return True

    def _emit_trace(
        self,
        *,
        session_id: str,
        engine: str,
        stage: str,
        status: str,
        detail: str = "",
    ) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "session_id": session_id,
                "engine": engine,
                "stage": stage,
                "status": status,
                "detail": detail,
                "ts": time.time(),
            },
            ensure_ascii=False,
        )
        self.conversation_trace_pub.publish(msg)

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
        now = time.time()

        # ---- fallen (highest priority among poses) ----
        if pose == "fallen":
            if self._state.fallen_first_seen is None:
                self._state.fallen_first_seen = now
            elif (now - self._state.fallen_first_seen) >= self.fallen_accumulate_s:
                if not self._in_cooldown("fallen_alert", 15.0):
                    self._mark_cooldown("fallen_alert")
                    self._world.set_fallen(True)
                    name = str(payload.get("name") or payload.get("identity") or "有人").strip()
                    self._emit(
                        build_plan(
                            "fallen_alert",
                            args={"name": name},
                            source="rule:pose_fallen_2s",
                            reason="pose_fallen_stable_2s",
                        )
                    )
                    self._state.fallen_first_seen = None
            self._state.sitting_first_seen = None
            self._state.bending_first_seen = None
            return

        self._state.fallen_first_seen = None
        self._world.set_fallen(False)

        # ---- sitting → sit_along (low-risk social) ----
        if pose == "sitting":
            if self._state.sitting_first_seen is None:
                self._state.sitting_first_seen = now
            elif (now - self._state.sitting_first_seen) >= 1.0:
                self._emit_with_cooldown(
                    "sit_along", source="rule:pose_sitting", reason="pose_sitting_stable_1s"
                )
                self._state.sitting_first_seen = None
            self._state.bending_first_seen = None
            return

        # ---- bending → careful_remind (low-risk social) ----
        if pose == "bending":
            if self._state.bending_first_seen is None:
                self._state.bending_first_seen = now
            elif (now - self._state.bending_first_seen) >= 1.0:
                self._emit_with_cooldown(
                    "careful_remind",
                    source="rule:pose_bending",
                    reason="pose_bending_stable_1s",
                )
                self._state.bending_first_seen = None
            self._state.sitting_first_seen = None
            return

        # other / standing / unknown — clear timers
        self._state.sitting_first_seen = None
        self._state.bending_first_seen = None

    def _on_object(self, msg: String) -> None:
        """Handle /event/object_detected.

        Production payload from object_perception_node:
            {"stamp": ..., "event_type": "object_detected", "objects": [
                {"class_name": "cup", "confidence": 0.9, "bbox": [...],
                 "color": "red", "color_confidence": 0.7}, ...]}

        Legacy/test payload (kept for backwards-compat with existing tests):
            {"label": "cup", "color": "red"}
        """
        payload = self._load_json(msg)
        if payload is None:
            return

        # Production format: take the first detection in the array.
        # Legacy format: payload itself is the single-object dict.
        objects = payload.get("objects")
        if isinstance(objects, list) and objects:
            det = objects[0]
            class_name = str(
                det.get("class_name") or det.get("label") or det.get("class") or ""
            ).strip()
            color = str(det.get("color") or "").strip()
        else:
            class_name = str(
                payload.get("class_name") or payload.get("label") or payload.get("class") or ""
            ).strip()
            color = str(payload.get("color") or "").strip()

        if not class_name:
            return
        if self._has_active_sequence():
            return

        # Compose zh-TW TTS — None means class is outside the speaking whitelist.
        text = build_object_tts(class_name, color)
        if text is None:
            return

        # Per-(class, color) dedup: same coloured object only spoken once per
        # OBJECT_REMARK_DEDUP_S. Otherwise YOLO keeps re-detecting a static
        # chair and PAI shouts "看到咖啡色的椅子了" every 5s — verified painful
        # in 5/7 night live test.
        now = time.time()
        seen_key = (class_name, color or "")
        last = self._object_remark_seen.get(seen_key, 0.0)
        if now - last < OBJECT_REMARK_DEDUP_S:
            return
        self._object_remark_seen[seen_key] = now

        self._emit_with_cooldown(
            "object_remark",
            args={"text": text, "label": class_name, "color": color},
            source="rule:object_detected",
            reason=f"object:{color}{class_name}",
        )

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

    # Per spec §4.2 / impl notes 2026-05-04 §2: only nav_demo_point may bypass
    # PendingConfirm via Studio button (the button itself is the confirmation).
    # All other requires_confirmation skills must go through OK confirm even
    # when launched from Studio.
    _STUDIO_BUTTON_BYPASS_CONFIRM = frozenset({"nav_demo_point"})

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
        source = str(payload.get("source") or "studio_button")
        is_studio_button = source == "studio_button"

        # High-risk skills require OK confirm. Studio button only bypasses for
        # explicitly-allowlisted skills (nav_demo_point).
        if contract.requires_confirmation and not (
            is_studio_button and skill in self._STUDIO_BUTTON_BYPASS_CONFIRM
        ):
            cd = contract.cooldown_s
            if cd > 0 and self._in_cooldown(skill, cd):
                return
            self._pending_confirm.request_confirm(skill, args, time.time())
            self.get_logger().info(
                f"PendingConfirm requested via skill_request skill={skill} source={source}"
            )
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": f"[curious] 比 OK 我就做 {skill}"},
                    source="rule:confirm_request",
                    reason=f"awaiting_ok:{skill}",
                )
            )
            return

        if contract.cooldown_s > 0 and self._in_cooldown(skill, contract.cooldown_s):
            return
        try:
            plan = build_plan(
                skill,
                args=args,
                source=source,
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
