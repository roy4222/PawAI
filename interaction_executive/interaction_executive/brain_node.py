"""brain_node - Skill-first PawAI Brain pure-rules MVS."""
from __future__ import annotations

import json
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Empty
from std_msgs.msg import String

from .attention_machine import AttentionMachine, AttentionState
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

# Per-class speaking dedup (D-4: key = class_name only, color dropped to prevent
# color-jitter bypass).  SkillContract.cooldown_s=5 only stops the *skill* from
# re-firing; it doesn't stop the same chair being announced every 5s when YOLO
# keeps detecting it. 60s here means "PAI mentioned this class recently — shut up."
# Cleared by _gc_dedup (via _dedup_gc_timer).
OBJECT_REMARK_DEDUP_S = 60.0


# Issue 8 (P3-1a) Idle MVP — canned phrases pool. Selected by random.choice
# with avoid-recent dedup (BrainInternalState.recent_idle_phrases ring buffer).
# Phrases are short (≤ 18 chars), self-talk style; no question marks (don't
# pressure user to respond). Audio tags drive TTS quality lane via 5/9 issue 1.
_IDLE_CANNED: tuple[str, ...] = (
    "[curious] 嗯～好安靜耶。",
    "[playful] 我剛剛看到一隻小蟲耶。",
    "[curious] 外面風好大。",
    "[curious] 有點想睡覺呢。",
    "[curious] 不知道現在幾點了。",
    "[playful] 來，誰要陪我玩？",
    "[curious] 房間有點暗暗的。",
    "[curious] 那個杯子放好久了。",
    "[playful] 我自己跟自己玩好了。",
    "[gentle] 今天好好呀。",
    "[thinking] 等等～剛剛在想什麼來著。",
    "[curious] 嗨～有人在嗎？",
)
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
    # Issue 8 (P3-1a) Idle MVP — all timestamps in time.time() seconds
    # (consistent with rest of brain_node which uses time.time(); 5/9 review).
    last_user_interaction_ts: float | None = None
    last_idle_emit_ts: float | None = None
    recent_idle_phrases: deque = field(default_factory=lambda: deque(maxlen=5))
    # idle_max_per_hour enforcement: ring of recent emit timestamps (time.time()).
    idle_emit_history: deque = field(default_factory=lambda: deque(maxlen=10))


class BrainNode(Node):
    def __init__(self) -> None:
        super().__init__("brain_node")
        self._declare_params()

        self._lock = threading.Lock()
        self._state = BrainInternalState()
        self._safety = SafetyLayer()
        self._world = WorldState(self)
        self._chat_timeouts: dict[str, rclpy.timer.Timer] = {}
        # 5/8 [#F-confirm-timeout]: 5s → 30s — 給 user 等 say_canned 講完 + 走過去比手勢的時間。
        # 新語音 intent 進來會主動 cancel（_on_speech_intent），所以 30s 只是硬尾線防止永久卡住。
        self._pending_confirm = PendingConfirm(timeout_s=30.0, stable_s=0.5)
        # 5/8 [#F-confirm-gesture-rate]: 0.5s → 5.0s
        # vision_perception_node 發 gesture event 的 rate 是 ~3-4s 一個（不是 10Hz tick），
        # live_window 0.5s 會讓 tick 把 fresh OK event 立刻當 stale → reset stability →
        # 永遠累積不到 stable_s=0.5s。拉到 5s 讓單一 OK event 維持 5s active state，
        # 配合 vision 的 sparse event rate 仍能達成 confirm。
        self._gesture_live_window_s = 5.0
        # Per-class → last-emit-ts (D-4: key is class_name only, not (class, color)).
        # See OBJECT_REMARK_DEDUP_S.
        self._object_remark_seen: dict[tuple[str, ...], float] = {}

        # D-1/D-2 Attention Machine — 4-state pure Python state machine.
        # Driven by 10Hz tick timer; face callback feeds face_visible + distance.
        # Spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md P2-1
        self._attention = AttentionMachine()
        # Latest face payload for attention tick (updated in _on_face)
        self._attention_face_visible: bool = False
        self._attention_distance_m: float | None = None
        self._attention_speech_this_tick: bool = False
        # 5/12: Latest stable face identity for fallen_alert name injection.
        # _on_face updates when stable + non-unknown; _on_pose fallen reads
        # to populate skill args["name"] (raw pose payload has no name field).
        # 30s freshness gate applied at read site.
        self._last_stable_identity_name: str | None = None
        self._last_stable_identity_ts: float = 0.0

        # N6: conversation-active gate — only chat input (speech/text) updates
        # this, NOT face/gesture. Used by _on_gesture to suppress
        # wave/fist/index auto-fire while user is actively talking, so the
        # dog doesn't blurt "嗨～我是 PawAI！" or "我在聽" mid-conversation.
        # Palm (system_pause / safety) is exempt from this gate.
        self._last_chat_input_ts: float = 0.0

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

        # P1-2: context reset — cancel PendingConfirm on page refresh / new-conversation
        self.create_subscription(Empty, "/brain/reset_context", self._on_reset_context, _RELIABLE_10)

        self._brain_state_timer = self.create_timer(0.5, self._publish_brain_state)
        self._dedup_gc_timer = self.create_timer(2.0, self._gc_dedup)
        self._confirm_tick_timer = self.create_timer(0.1, self._tick_pending_confirm)  # 10Hz
        self._attention_tick_timer = self.create_timer(0.1, self._tick_attention)  # 10Hz
        self.get_logger().info(
            f"brain_node ready skills={len(SKILL_REGISTRY)} "
            f"chat_wait={self.chat_wait_ms}ms dedup={self.dedup_window_s}s"
        )

    def _declare_params(self) -> None:
        self.declare_parameter("chat_wait_ms", 1500)
        self.declare_parameter("dedup_window_s", 1.0)
        self.declare_parameter("unknown_face_accumulate_s", 3.0)
        self.declare_parameter("fallen_accumulate_s", 2.0)
        # Issue 8 (P3-1a) Idle MVP params — default OFF per spec.
        # idle_threshold_s 600 = Roy's "閒置超過十分鐘" home profile.
        # idle_cooldown_s 600 to avoid clustering. max_per_hour caps total chatter.
        self.declare_parameter("idle_enabled", False)
        self.declare_parameter("idle_threshold_s", 600.0)
        self.declare_parameter("idle_cooldown_s", 600.0)
        self.declare_parameter("idle_max_per_hour", 4)
        # 2026-05-23 5/27 demo record mode: 砍 gesture direct trigger（手勢只供 Studio trace）
        # 預設 False 維持現有 wave/palm/fist/index → direct skill 行為
        # 設 true → 改用語音 keyword 觸發（intent_classifier greet 等）+ palm safety 改走語音「停」
        self.declare_parameter("gesture_direct_disabled", False)
        self.chat_wait_ms = int(self.get_parameter("chat_wait_ms").value)
        self.dedup_window_s = float(self.get_parameter("dedup_window_s").value)
        self.unknown_face_accumulate_s = float(
            self.get_parameter("unknown_face_accumulate_s").value
        )
        self.fallen_accumulate_s = float(self.get_parameter("fallen_accumulate_s").value)
        self.idle_enabled = bool(self.get_parameter("idle_enabled").value)
        self.idle_threshold_s = float(self.get_parameter("idle_threshold_s").value)
        self.idle_cooldown_s = float(self.get_parameter("idle_cooldown_s").value)
        self.idle_max_per_hour = int(self.get_parameter("idle_max_per_hour").value)
        self.gesture_direct_disabled = bool(self.get_parameter("gesture_direct_disabled").value)
        if self.gesture_direct_disabled:
            # Instance shadow class attribute — 不影響其他 BrainNode instances 或 test fixtures
            self._GESTURE_DIRECT = {}

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

    def _has_active_skill_or_sequence(self) -> bool:
        """Return True when a SKILL or SEQUENCE priority plan is actively running.

        D-4: Previously only checked SEQUENCE.  Extending to also block SKILL
        fixes the bug where an active wiggle/wave_hello (SKILL priority) did not
        prevent object_remark from inserting itself mid-skill.
        """
        with self._lock:
            active = self._state.active_plan
            if not active:
                return False
            pc = active.get("priority_class", -1)
            return pc in (int(PriorityClass.SEQUENCE), int(PriorityClass.SKILL))

    def _on_speech_intent(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
        session_id = str(
            payload.get("session_id") or payload.get("request_id") or f"speech-{time.time_ns()}"
        )

        # Issue 8: speech is unambiguous user interaction → reset idle clock
        self._touch_user_interaction()
        # N6: also mark chat-active for gesture gating
        with self._lock:
            self._last_chat_input_ts = time.time()

        # D-2: Speech intent always advances attention regardless of state.
        # Speech is an explicit engagement signal — flag for next attention tick.
        with self._lock:
            self._attention_speech_this_tick = True

        plan = self._safety.hard_rule(transcript)
        if plan is not None:
            plan.session_id = session_id
            self._emit(plan)
            return

        # 2026-05-23: 5/27 demo § 5 — unsafe action keyword rejection
        # 對齊 ADR-0001 非接觸式 + 5/27 spec § 5 設計
        # 偵測「翻跟斗 / 後空翻 / 倒立 / backflip / handstand」等危險動作關鍵字
        # → 兩個 plan：(1) say_canned TTS 拒絕 (2) request_backflip 觸發 SafetyLayer
        #   reject → Studio BLOCKED_BY_SAFETY 紅色 highlight
        # LLM whitelist 完全不動 / BANNED_API_IDS 不動 / execution 100% 阻擋
        unsafe_result = self._safety.unsafe_request(transcript)
        if unsafe_result is not None:
            say_plan, motion_plan = unsafe_result
            say_plan.session_id = session_id
            motion_plan.session_id = f"{session_id}-unsafe-visual"
            self._emit(say_plan)
            self._emit(motion_plan)
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

        if self._has_active_skill_or_sequence() or self._check_dedup("speech", session_id):
            return

        # 5/8 [#F-confirm-timeout]: user 換新話題 → cancel 任何 pending confirm。
        # 設計：「持續辨識直到下次語音」— 比 5s/15s timeout 更符合對話直覺。
        if self._pending_confirm.state == ConfirmState.PENDING:
            self._pending_confirm.cancel(reason="new_speech_intent")
            self.get_logger().info("PendingConfirm cancelled by new speech intent")

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
            # N8: pass current gesture so PendingConfirm requires release first
            # when user's hand is already at OK (prevents instant trigger).
            with self._lock:
                cur_gesture = self._state.current_gesture
            self._pending_confirm.request_confirm(
                proposed_skill, proposed_args, time.time(),
                current_gesture=cur_gesture,
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
        "stand",
        "greet_known_person",
        "careful_remind",
        "wiggle",
        "stretch",
    })
    LLM_PROPOSAL_EXECUTE = {
        # Bucket 1 — execute (direct)
        "show_status": "execute",
        "wave_hello": "execute",
        "sit_along": "execute",
        "stand": "execute",
        "careful_remind": "execute",
        # Bucket 2 — confirm (needs OK gesture)
        "wiggle": "confirm",
        "stretch": "confirm",
        # Bucket 3 — trace_only (LLM can mention, system does not fire motion)
        "self_introduce": "trace_only",
        "greet_known_person": "trace_only",  # 1G: was execute; face stable detection handles greet
    }

    # Phase B v1 gesture mapping (spec §4.2 + impl notes 2026-05-04 §2;
    # 2026-05-12 added fist/index per 測試功能清單 6 static gestures):
    #   wave         → wave_hello         (low-risk, direct)
    #   palm         → system_pause       (safety-immediate, direct)
    #   fist         → enter_mute_mode    (mode switch, direct)
    #   index        → enter_listen_mode  (mode switch, direct)
    #   thumbs_up    → wiggle             (high-risk, request OK confirm)
    #   peace        → stretch            (high-risk, request OK confirm)
    #   ok           → consumed by PendingConfirm.tick (no direct skill fire)
    _GESTURE_DIRECT = {
        "wave": "wave_hello",
        "palm": "system_pause",
        "fist": "enter_mute_mode",
        "index": "enter_listen_mode",
    }
    _GESTURE_CONFIRM = {"thumbs_up": "wiggle", "peace": "stretch"}
    # 2026-05-23 5/27 demo record mode (Roy 5/22 P0「手勢狂誤觸」):
    # ROS param `gesture_direct_disabled=true` 時，brain_node __init__ 會把
    # instance-level _gesture_direct 設成 {} → 手勢只供 Studio trace 視覺化、
    # 不直接觸發 Go2 motion。
    # 對應 5/27 demo § 4：「手勢觸發互動」demo 鏡頭改走語音 keyword
    #   wave_hello → 講「打招呼」(intent_classifier greet → wave_hello)
    #   system_pause → 講「停」(SafetyLayer.hard_rule 已 cover)
    # _GESTURE_CONFIRM (thumbs_up→wiggle / peace→stretch) 保留 (需 OK 二確認 = 安全)
    # N6: gestures that produce social skills (wave/hello) or mode switches
    # (mute/listen) get suppressed when chat is active in the last 30s.
    # palm/system_pause is SAFETY and NEVER gated.
    _CONVERSATION_GATED_GESTURES = frozenset({"wave", "fist", "index"})
    _CONVERSATION_GATE_S = 30.0

    def _on_gesture(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        gesture = str(
            payload.get("gesture") or payload.get("type") or payload.get("label") or ""
        ).strip().lower()
        if not gesture:
            return

        # Issue 8: gesture is intentional user signal → reset idle clock
        self._touch_user_interaction()

        # Update gesture tracker so PendingConfirm tick can see it.
        with self._lock:
            self._state.current_gesture = gesture
            self._state.current_gesture_ts = time.time()

        # If a confirm is already in flight, gestures only feed the state machine
        # via the periodic tick — don't fire new skills.
        if self._pending_confirm.state == ConfirmState.PENDING:
            return

        if self._has_active_skill_or_sequence():
            return
        if self._check_dedup("gesture", gesture):
            return

        # N6/N8: conversation-active gate — wave / fist / index don't fire
        # mid-conversation. Palm (safety) bypasses this gate.
        # Two independent reasons to block:
        #   1. recent chat input (speech/text within 30s)
        #   2. PawAI is currently speaking (tts_playing)
        # Either suffices — both are defended against because the C2 demo
        # log shows multiple gestures arriving during/after LLM reply, and
        # the original `last_chat_input_ts` lone gate failed (most likely
        # stale-build on Jetson but adding tts_playing as belt-and-suspenders).
        if gesture in self._CONVERSATION_GATED_GESTURES:
            with self._lock:
                last_chat = self._last_chat_input_ts
            since_chat = time.time() - last_chat
            chat_active = last_chat > 0.0 and since_chat < self._CONVERSATION_GATE_S
            tts_playing = bool(self._world.snapshot().tts_playing)
            if chat_active or tts_playing:
                reason = []
                if chat_active:
                    reason.append(f"chat_{since_chat:.1f}s")
                if tts_playing:
                    reason.append("tts_playing")
                reason_str = ",".join(reason)
                self.get_logger().info(
                    f"[gate] gesture={gesture} suppressed ({reason_str})"
                )
                self._emit_trace(
                    session_id=f"gesture-{int(time.time())}",
                    engine="brain_node",
                    stage="gesture_gate",
                    status="blocked",
                    detail=f"{gesture}:{reason_str}",
                )
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

    def _tick_attention(self) -> None:
        """10Hz attention machine tick. Uses time.monotonic() for fake-clock compatibility."""
        now = time.monotonic()
        with self._lock:
            face_visible = self._attention_face_visible
            distance_m = self._attention_distance_m
            active_plan = self._state.active_plan is not None
            speech_intent = self._attention_speech_this_tick
            self._attention_speech_this_tick = False  # consume
            # 5/9 review: attention.tick mutates state — keep inside lock so
            # any reader using _attention_state_snapshot() sees consistent value.
            self._attention.tick(
                now=now,
                face_visible=face_visible,
                distance_m=distance_m,
                active_plan=active_plan,
                speech_intent=speech_intent,
            )
        # Issue 8 (P3-1a) idle check — uses time.time() (consistent with rest
        # of brain_node cooldowns/timestamps; 5/9 final review). Cheap when
        # idle_enabled=False (early return).
        self._maybe_emit_idle(time.time())

    # ── Issue 8 (P3-1a) Idle MVP ──────────────────────────────────────────
    def _touch_user_interaction(self, now: float | None = None) -> None:
        """Mark that user just interacted (speech/gesture/face engaged/text).

        Called from _on_speech_intent, _on_gesture, _on_face (when stable
        known person), _on_text_input. Resets the idle clock so the dog
        won't blurt out idle chatter while user is actively present.

        5/9 final review: now uses time.time() (was time.monotonic()) to be
        consistent with rest of brain_node cooldowns/timestamps.
        """
        ts = now if now is not None else time.time()
        with self._lock:
            self._state.last_user_interaction_ts = ts

    def _maybe_emit_idle(self, now: float) -> None:
        """Issue 8 (P3-1a): emit canned idle utterance when long-idle.

        Default DISABLED (idle_enabled param). When enabled:
        1. last_user_interaction_ts older than idle_threshold_s
        2. last_idle_emit_ts older than idle_cooldown_s (or never)
        3. not active_plan, not pending_confirm, not tts_playing
        4. attention.state == IDLE (no person engaged) — locked snapshot
        5. idle_max_per_hour cap (real enforcement; 5/9 final review)
        6. pick phrase not in recent_idle_phrases ring (5)
        """
        if not self.idle_enabled:
            return
        # Locked snapshot of all decision inputs
        with self._lock:
            last_ui = self._state.last_user_interaction_ts
            last_emit = self._state.last_idle_emit_ts
            recent = list(self._state.recent_idle_phrases)
            active = self._state.active_plan
            # Drop stale emit timestamps (>1h old) so deque only holds last hour
            cutoff = now - 3600.0
            while self._state.idle_emit_history and self._state.idle_emit_history[0] < cutoff:
                self._state.idle_emit_history.popleft()
            emits_last_hour = len(self._state.idle_emit_history)
        # Gate 1: user freshly active → silent
        if last_ui is not None and (now - last_ui) < self.idle_threshold_s:
            return
        # Gate 2: cooldown
        if last_emit is not None and (now - last_emit) < self.idle_cooldown_s:
            return
        # Gate 3: not safe to interrupt
        if active is not None:
            return
        if self._pending_confirm.state == ConfirmState.PENDING:
            return
        if self._world.snapshot().tts_playing:
            return
        # Gate 4: attention IDLE (locked snapshot helper — race safe)
        if self._attention_state_snapshot() != AttentionState.IDLE:
            return
        # Gate 5: REAL max-per-hour enforcement (5/9 final review)
        if emits_last_hour >= self.idle_max_per_hour:
            return
        # Gate 6: pick phrase avoiding recent
        candidates = [p for p in _IDLE_CANNED if p not in recent]
        if not candidates:
            candidates = list(_IDLE_CANNED)
        phrase = random.choice(candidates)
        # Atomic update + emit
        with self._lock:
            self._state.last_idle_emit_ts = now
            self._state.recent_idle_phrases.append(phrase)
            self._state.idle_emit_history.append(now)
        self._emit(
            build_plan(
                "say_canned",
                args={"text": phrase},
                source="rule:idle",
                reason="idle_long_silence",
            )
        )
        self.get_logger().info(
            f"[idle] emit say_canned: {phrase!r} (emits/hr={emits_last_hour + 1}/{self.idle_max_per_hour})"
        )

    def _attention_state_snapshot(self) -> "AttentionState":
        """Thread-safe snapshot of current attention state for gating decisions.

        5/9 review: callers in _on_face/_on_object/etc. previously read
        self._attention.state without lock — race against _tick_attention's
        mutation. This helper takes self._lock to ensure consistent read.
        """
        with self._lock:
            return self._attention.state

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

        # D-2: Feed attention machine with face visibility and distance.
        # distance_m may be in the payload (depth-equipped cameras); None if absent.
        distance_m: float | None = None
        raw_dist = payload.get("distance_m") or payload.get("depth_m")
        if raw_dist is not None:
            try:
                distance_m = float(raw_dist)
            except (TypeError, ValueError):
                distance_m = None
        event_type = str(payload.get("event_type") or "")
        face_visible_now = bool(identity) and event_type != "track_lost"
        with self._lock:
            self._attention_face_visible = face_visible_now
            if face_visible_now:
                self._attention_distance_m = distance_m
            # 5/12: Cache stable non-unknown identity for fallen_alert name
            # injection (raw pose event has no name; bridge audible path
            # disabled — Brain skill is sole audible path now).
            if stable and identity and identity != "unknown":
                self._last_stable_identity_name = identity
                self._last_stable_identity_ts = time.time()

        if not identity:
            self._state.unknown_face_first_seen = None
            return
        if identity == "unknown":
            now = time.time()
            if self._state.unknown_face_first_seen is None:
                self._state.unknown_face_first_seen = now
            elif (now - self._state.unknown_face_first_seen) >= self.unknown_face_accumulate_s:
                # 5/9 review: stranger_alert had only NOTICED+ + 3s gate. That allowed it
                # to ALERT-priority preempt active wiggle / pending confirm / TTS playback —
                # exactly the bug Roy hit on smoke. Add same guards as greet_known_person:
                # not active skill, not pending confirm, not currently speaking.
                # Safety override path (fallen / stop) is unchanged — that goes through
                # SafetyLayer hard_rule, not this branch.
                attention_state = self._attention_state_snapshot()
                if (
                    not self._in_cooldown("stranger_alert", 30.0)
                    and attention_state != AttentionState.IDLE
                    and not self._has_active_skill_or_sequence()
                    and self._pending_confirm.state != ConfirmState.PENDING
                    and not self._world.snapshot().tts_playing
                ):
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
        # 5/8 [#F-confirm]: PENDING 期間不發 greet_known_person，避免蓋掉 confirm 流
        # D-3: greet_known_person gates on ENGAGED (person stopped and dwelled).
        # This fixes "路過比 OK 被打招呼" — person must be close + dwelling, not
        # just walking past.
        if not stable or self._has_active_skill_or_sequence() \
                or self._pending_confirm.state == ConfirmState.PENDING \
                or self._world.snapshot().tts_playing:
            # 5/9 review: also block during TTS to avoid mid-sentence interrupt.
            return
        # 5/9 review: greet_known_person is ENGAGED-only (NOT INTERACTING).
        # When already INTERACTING (skill running / speech intent active),
        # firing greet causes SAY interrupt. spec P2-1 originally said ENGAGED only.
        if self._attention_state_snapshot() != AttentionState.ENGAGED:
            return  # person just passing by, or already mid-interaction
        # Issue 8: known-face stable + ENGAGED is real engagement → reset idle
        self._touch_user_interaction()
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
                    # 5/12: prefer raw pose payload name; fallback to last
                    # stable face identity (≤30s freshness); fallback "有人".
                    raw_name = str(payload.get("name") or payload.get("identity") or "").strip()
                    if not raw_name:
                        with self._lock:
                            cached = self._last_stable_identity_name
                            cached_age = time.time() - self._last_stable_identity_ts
                        if cached and cached_age <= 30.0:
                            raw_name = cached
                    name = raw_name or "有人"
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

        # 5/8 [#F-confirm]: PENDING 期間 sitting/bending auto-rule 不發 plan
        confirm_pending = self._pending_confirm.state == ConfirmState.PENDING

        # ---- sitting → sit_along (low-risk social) ----
        if pose == "sitting":
            if self._state.sitting_first_seen is None:
                self._state.sitting_first_seen = now
            elif (now - self._state.sitting_first_seen) >= 1.0 and not confirm_pending:
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
            elif (now - self._state.bending_first_seen) >= 1.0 and not confirm_pending:
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

        # D-3 emit gate: object_remark only when ENGAGED and no active plan/TTS.
        # Fixes "chat_reply SAY in progress → object_remark interrupts" (Roy 5/9 smoke).
        # Condition:
        #   1. attention.state == ENGAGED (person stopped near dog; not just passing by)
        #   2. not active_plan (no skill/sequence currently running — D-4 helper)
        #   3. not pending_confirm (middle of gesture confirmation flow)
        #   4. not tts_playing (TTS currently speaking — don't interrupt mid-SAY)
        snap = self._world.snapshot()
        # 5/9 final review: was reading self._attention.state without lock —
        # 3rd race-condition hole alongside stranger_alert / greet_known_person
        # which already use _attention_state_snapshot(). Fix: same helper.
        if self._attention_state_snapshot() != AttentionState.ENGAGED:
            return  # IDLE / NOTICED / INTERACTING — stay quiet
        if self._has_active_skill_or_sequence():
            return
        if self._pending_confirm.state == ConfirmState.PENDING:
            return
        if snap.tts_playing:
            return  # Don't insert object remark while PAI is speaking

        # Compose zh-TW TTS — None means class is outside the speaking whitelist.
        text = build_object_tts(class_name, color)
        if text is None:
            return

        # D-4: dedup key = class_name only (drop color).
        # Rationale: YOLO color labels jitter on the same object (brown_chair →
        # coffee_chair → dark_chair within seconds), which previously bypassed
        # the 60s dedup.  class_name-only key gives stable dedup across color noise.
        now = time.time()
        seen_key = (class_name,)
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
        # Issue 8: Studio text input is unambiguous user interaction → reset idle
        self._touch_user_interaction()
        # N6: also mark chat-active for gesture gating
        with self._lock:
            self._last_chat_input_ts = time.time()
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

    def _on_reset_context(self, msg: Empty) -> None:  # noqa: ARG002
        """P1-2: Cancel PendingConfirm when browser requests a context reset.

        Active plans and attention state are preserved — we only cancel any
        in-progress confirmation flow that the user is walking away from.
        """
        with self._lock:
            if self._pending_confirm.state == ConfirmState.PENDING:
                self._pending_confirm.cancel(reason="page_reset")
                self.get_logger().info("PendingConfirm cancelled by /brain/reset_context")

    def _publish_brain_state(self) -> None:
        snap = self._world.snapshot()
        with self._lock:
            active_plan = dict(self._state.active_plan) if self._state.active_plan else None
            active_step = dict(self._state.active_step) if self._state.active_step else None
            last_plans = list(self._state.last_plans)
            cooldowns = dict(self._state.last_alert_ts)
            fallback_active = self._state.fallback_active
        # D-2: attention state for Studio Trace Drawer — read outside lock (atomic reads)
        attention_state = self._attention.state.value
        attention_since = self._attention.state_since
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
            "attention": {
                "state": attention_state,
                "since_ts": attention_since,
            },
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
