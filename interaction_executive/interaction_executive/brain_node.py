"""brain_node - Skill-first PawAI Brain pure-rules MVS."""
from __future__ import annotations

import json
import random
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Bool
from std_msgs.msg import Empty
from std_msgs.msg import String

from . import interaction_state
from .attention_machine import AttentionMachine, AttentionState
# ISM Phase 1 shadow (system Phase 2 / 2A): aliased imports — interaction_state
# has its own Verdict enum that collides with pawai_contracts.trace_schema.Verdict
# (ACCEPT/SUPPRESS/QUEUE/PREEMPT vs ACCEPTED/SUPPRESSED/BLOCKED). Never mix them.
from .interaction_state import (
    Candidate as IsmCandidate,
    Decision as IsmDecision,
    InteractionPolicy as IsmPolicy,
    InteractionState as IsmState,
    InteractionStateMachine,
    Priority as IsmPriority,
    TransitionSignal as IsmSignal,
    TriggerKind as IsmTrigger,
    Verdict as IsmVerdict,
)
from .perception_router import (
    parse_face,
    parse_gesture,
    parse_object,
    parse_pose,
    parse_speech,
)
from .pending_confirm import (
    ConfirmOutcomeKind,
    ConfirmState,
    PendingConfirm,
)
from .safety_layer import SafetyLayer
from .skill_contract import (
    ExecutorKind,
    SKILL_REGISTRY,
    PriorityClass,
    SkillPlan,
    SkillResultStatus,
    build_plan,
)
from .world_state import WorldState


# zh tables single-sourced in pawai_contracts (Plan C3, 2026-06-10 Roy ruling —
# supersedes the old "three copies on purpose" comment). Producer canon:
# object_perception/coco_classes.py; Studio TS copy guarded by parity test.
from pawai_contracts.zh_tables import (
    OBJECT_CLASS_ZH,
    OBJECT_COLOR_ZH,
    OBJECT_TTS_SPECIAL_SUFFIX,
)
# LLM proposal policy single-sourced in pawai_contracts (Plan C4, 2026-06-10).
from pawai_contracts import llm_policy as _llm_policy
from pawai_contracts.trace_schema import TraceEvent, TraceKind, Verdict, make_suppressed

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


# plan3 T3 (2026-06-13): five-phase 3-tier canned phrase table for the 6/18 live
# demo. Only consulted on offline_mode / fallback (online still uses LLM reply /
# existing say_canned). success = real-trigger natural line; degraded =
# detected-but-low-confidence / cloud-slow; generic = no-detection full fallback.
# s5_safety is ALWAYS rule-first reject across all three tiers (LLM may never
# override it).
# PENDING Roy sign-off (6/15) — provisional wording, do not treat as final.
DEMO_CANNED_TABLE: dict[str, dict[str, str]] = {
    "s1_nav": {
        "success": "我正在移動到巡檢位置。",
        "degraded": "我正在前往巡檢位置，請稍等。",
        "generic": "我先在這裡待命。",
    },
    "s2_greet": {
        "success": "Roy，歡迎回來，我看到你了。",
        "degraded": "嗨，歡迎回來。",
        "generic": "哈囉，很高興見到你。",
    },
    "s3_pose_object": {
        "success": "我看到杯子了，記得補充水分。",
        "degraded": "我看到桌上有東西，記得喝水喔。",
        "generic": "記得多喝水、休息一下。",
    },
    "s4_gesture": {
        "success": "你要我 WeGo 一下嗎？比 OK 我就開始。",
        "degraded": "我看到你的手勢了，比 OK 我就開始。",
        "generic": "你可以比個手勢跟我互動。",
    },
    "s5_safety": {
        "success": "這個動作不安全，我不能執行。",
        "degraded": "這個指令我不能做，太危險了。",
        "generic": "為了安全，我不能執行這個動作。",
    },
}


def build_object_tts(class_name: str, color: str | None) -> str | None:
    """Compose object_remark TTS string, or None when class is outside the
    PawAI TTS whitelist (UI still shows it; PawAI just stays quiet).

    Examples:
        build_object_tts("cup", "red")     == "看到紅色的杯子了，你要喝水嗎？今天天氣很熱，要記得補充水分。"
        build_object_tts("laptop", "blue") == "看到藍色的筆電了"
        build_object_tts("cup", "Unknown") == "看到杯子了，你要喝水嗎？今天天氣很熱，要記得補充水分。"
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
    # 2026-05-23 5/27 demo video mode: last seen sitting timestamp
    # 用來判斷 object_detected=cup 是否在 recent sitting context 內觸發複合句
    last_sitting_seen_ts: float = 0.0
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
        # ISM Phase 1 shadow (system Phase 2 / 2A, T2A-2): observe-only. The
        # machine always exists (pure, cheap); every shadow hook early-returns
        # unless ism_shadow_enabled (declared default False = byte-identical).
        # Its Decision NEVER influences emit/return — staged enable is post-6/18
        # behind a separate ism_enabled flag that deliberately does not exist.
        self._ism = InteractionStateMachine(now=time.time())
        self._ism_history_len = 0
        self._ism_last_tts = False
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
        # Plan E (2026-06-10): decision-chain trace. Distinct from
        # /brain/conversation_trace (LLM dialogue stages) — this one answers
        # 「為什麼沒反應」. Persistence belongs to the Studio gateway, NOT here.
        self._pub_trace = self.create_publisher(String, "/brain/trace", _RELIABLE_10)
        self._plan_decision: dict[str, str] = {}   # plan_id → decision_id (GC in _gc_dedup)
        self._current_decision_id: str = ""
        self._trace_throttle: dict[str, float] = {}   # hot-gate trace rate limit
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

        # 2026-06-10 demo: Studio Gesture On/Off toggle — gateway POST /api/gesture_enabled
        # → Bool(/brain/gesture_enabled)。與 `ros2 param set gesture_enabled` 同效，
        # topic 版給 Studio 一鍵切換用（錄影 S4 段開、其餘段關）。
        self.create_subscription(
            Bool, "/brain/gesture_enabled", self._on_gesture_enabled_msg, _RELIABLE_10
        )

        # plan2 T2-3: demo phase control (plan4 hidden buttons publish here).
        # Shares _set_demo_phase with the `ros2 param set demo_phase` path.
        self.create_subscription(
            String, "/brain/demo_phase", self._on_demo_phase_msg, _RELIABLE_10
        )

        self._brain_state_timer = self.create_timer(0.5, self._publish_brain_state)
        self._dedup_gc_timer = self.create_timer(2.0, self._gc_dedup)
        self._confirm_tick_timer = self.create_timer(0.1, self._tick_pending_confirm)  # 10Hz
        self._attention_tick_timer = self.create_timer(0.1, self._tick_attention)  # 10Hz
        # 2026-06-09 demo: runtime param callback（目前只處理 gesture_enabled，
        # 操作員 `ros2 param set /brain_node gesture_enabled false/true` 即時生效）。
        self.add_on_set_parameters_callback(self._on_set_params)
        self.get_logger().info(
            f"brain_node ready skills={len(SKILL_REGISTRY)} "
            f"chat_wait={self.chat_wait_ms}ms dedup={self.dedup_window_s}s"
        )

    def _on_set_params(self, params):
        """Runtime ros2-param callback. 支援 gesture_enabled / stranger_alert_enabled /
        greet_require_sitting 即時切換（demo 現場免重啟）。"""
        from rcl_interfaces.msg import SetParametersResult

        for p in params:
            if p.name == "gesture_enabled":
                self._set_gesture_enabled(bool(p.value), via="param")
            elif p.name == "perception_router_enabled":
                # Plan D Phase 0 instant fallback — the whole point of this
                # param is live rollback to legacy parsing without redeploy.
                self.perception_router_enabled = bool(p.value)
                self.get_logger().info(
                    f"perception_router_enabled set to {self.perception_router_enabled}"
                )
            elif p.name in (
                "stranger_alert_enabled",
                "greet_require_sitting",
                "offline_mode",
                "ism_shadow_enabled",
                "ism_enabled",
                "ism_stage_2a_demo_phase",
                "ism_stage_2b_confirm",
                "ism_stage_2c_executing",
                "ism_stage_2d_speaking",
            ):
                # Plain-bool runtime params share one branch (logs byte-identical
                # to the previous per-param branches). ism_shadow_enabled joined
                # 2026-06-12 — ISM Phase 1 shadow (T2A-2) runtime switch.
                setattr(self, p.name, bool(p.value))
                self.get_logger().info(f"{p.name} set to {getattr(self, p.name)}")
            elif p.name == "greet_sitting_window_s":
                self.greet_sitting_window_s = float(p.value)
                self.get_logger().info(
                    f"greet_sitting_window_s set to {self.greet_sitting_window_s}"
                )
            elif p.name == "greet_cooldown_s":
                self.greet_cooldown_s = float(p.value)
                self.get_logger().info(f"greet_cooldown_s set to {self.greet_cooldown_s}")
            elif p.name == "demo_phase":
                # plan2 T2-3: param + /brain/demo_phase topic share _set_demo_phase
                # so cleanup logic never diverges between the two entry points.
                self._set_demo_phase(str(p.value))
        return SetParametersResult(successful=True)

    def _ism_stage_on(self, stage_attr: str) -> bool:
        return bool(self.ism_enabled) and bool(getattr(self, stage_attr, False))

    # 2026-06-10（Roy 拍板「demo flow controller / phase gate，S2/S3/S4 不搶話」的
    # 最小外科版）：demo_phase 只 gate「自發性社交 proposal」（greet / object_remark /
    # gesture）。安全鏈（fallen/stop/SafetyLayer）、語音/文字明確指令、Studio
    # skill_request 一律不受 phase 影響 — priority: safety > explicit input > phase。
    # 錄影 SOP：ros2 param set /brain_node demo_phase s3_object（換 take 再切）。
    _DEMO_PHASES = frozenset(interaction_state.PHASE_ALLOWED_KINDS)

    def _phase_allows(self, kind: str) -> bool:
        allowed = interaction_state.PHASE_ALLOWED_KINDS.get(self.demo_phase)
        legacy_allow = True if allowed is None else kind in allowed
        allow = legacy_allow
        if self._ism_stage_on("ism_stage_2a_demo_phase"):
            try:
                allow = interaction_state.phase_allows(self.demo_phase, kind)
            except Exception as exc:  # noqa: BLE001 — takeover must never break callbacks
                self.get_logger().debug(f"ism demo_phase policy failed: {exc}")
                allow = legacy_allow
        if allow:
            return True
        self.get_logger().info(
            f"[phase] {kind} proposal suppressed (demo_phase={self.demo_phase})",
            throttle_duration_sec=5.0,
        )
        self._suppressed(gate="demo_phase", reason=f"phase:{self.demo_phase}:{kind}",
                         throttle_key=f"phase:{kind}")
        return False

    def _set_demo_phase(self, raw_value: str) -> None:
        """plan2 T2-3: single source of truth for demo_phase changes.

        Shared by the param-set callback AND the /brain/demo_phase topic so the
        cleanup path (_apply_phase_transition) is identical regardless of entry
        point. Canonicalizes aliases (s2_face->s2_greet); an invalid phase warns
        and keeps the old value. Only a *real* change (new != old after
        canonicalization) runs the cleanup helper — same-value is a no-op
        (byte-identical).
        """
        value = interaction_state.canonicalize_phase(str(raw_value).strip().lower())
        if value not in self._DEMO_PHASES:
            self.get_logger().warn(
                f"unknown demo_phase {raw_value!r} — keep {self.demo_phase!r} "
                f"(valid: {sorted(self._DEMO_PHASES)})"
            )
            return
        old_phase = self.demo_phase
        if value == old_phase:
            return  # no-op — same value, byte-identical (no cleanup, no trace)
        self.demo_phase = value
        self.get_logger().info(f"demo_phase set to {self.demo_phase} (was {old_phase})")
        self._apply_phase_transition(value, old_phase)

    def _on_demo_phase_msg(self, msg: String) -> None:
        """plan2 T2-3: /brain/demo_phase String subscriber (plan4 hidden buttons).

        Contract for plan4: gateway publishes std_msgs/String{data:"s2_greet"}.
        This lane owns only the brain-side subscriber, never the gateway/UI.
        """
        self._set_demo_phase(msg.data)

    def _phase_canned(self, phase: str, tier: str) -> str | None:
        """plan3 T3: look up a canned demo line for (phase, tier).

        Canonicalizes legacy aliases first. Returns None when the phase is not
        in DEMO_CANNED_TABLE (e.g. demo_phase=all / quiet) so callers can fall
        back to their existing behavior (byte-identical). tier ∈
        {success, degraded, generic}.
        """
        canon = interaction_state.canonicalize_phase(str(phase).strip().lower())
        tiers = DEMO_CANNED_TABLE.get(canon)
        if not tiers:
            return None
        return tiers.get(tier)

    def _ism_confirm_preempt_active(self) -> bool:
        """Return True when stage 2b policy preempts CONFIRM_PENDING for ALERT.

        Pure policy check only. Any policy/import failure falls back to legacy
        confirm behavior so pose callbacks never fail because of takeover logic.
        """
        if not self._ism_stage_on("ism_stage_2b_confirm"):
            return False
        try:
            from .interaction_state import (
                Candidate as _Candidate,
                InteractionPolicy as _Policy,
                InteractionState as _State,
                Priority as _Priority,
            )

            decision = _Policy.evaluate(
                _State.CONFIRM_PENDING,
                _Candidate(
                    kind="alert",
                    priority=_Priority.ALERT,
                    source="pose",
                    skill="fallen_alert",
                ),
            )
            return decision.verdict == IsmVerdict.PREEMPT
        except Exception as exc:  # noqa: BLE001 - takeover must never break callbacks
            self.get_logger().debug(f"ism confirm preempt check failed: {exc}")
            return False

    def _ism_speaking_queue_marker(self, source_summary: str) -> None:
        """Additive trace for stage 2d: social candidate QUEUE while SPEAKING.

        Forbidden #6: QUEUE is not replayed in this lane. It is only marked as
        suppress-with-trace evidence while legacy suppress behavior stays intact.
        """
        if not self._ism_stage_on("ism_stage_2d_speaking"):
            return
        try:
            from .interaction_state import (
                Candidate as _Candidate,
                InteractionPolicy as _Policy,
                InteractionState as _State,
                Priority as _Priority,
            )

            decision = _Policy.evaluate(
                _State.SPEAKING,
                _Candidate(kind="social", priority=_Priority.SOCIAL, source="perception"),
            )
            if decision.verdict != IsmVerdict.QUEUE:
                return
            self._trace(TraceEvent(
                decision_id=self._current_decision_id, node="brain_node",
                kind=TraceKind.STATE_TRANSITION, verdict=Verdict.SUPPRESSED,
                gate="speaking", reason="gate:speaking",
                detail={
                    "queue_v2_pending": True,
                    "ism_reason": decision.reason,
                    "source_summary": source_summary,
                },
            ))
        except Exception as exc:  # noqa: BLE001 - takeover must never break callbacks
            self.get_logger().debug(f"ism speaking queue marker failed: {exc}")

    def _set_gesture_enabled(self, enabled: bool, via: str) -> None:
        """gesture_enabled 切換共用路徑（param callback / Studio topic 兩入口）。

        關閉時若有 PendingConfirm 在 flight 一併取消 — 不然 OK 手勢已收不到
        （_on_gesture early-return），confirm 會掛到 30s timeout 才消失。
        """
        self.gesture_enabled = enabled
        self.get_logger().info(f"gesture_enabled set to {enabled} (via {via})")
        if not enabled and self._pending_confirm.state == ConfirmState.PENDING:
            self._pending_confirm.cancel(reason="gesture_disabled")
            self.get_logger().info("PendingConfirm cancelled by gesture_enabled=false")

    def _on_gesture_enabled_msg(self, msg: Bool) -> None:
        """Studio Gesture On/Off toggle（/brain/gesture_enabled Bool）。"""
        self._set_gesture_enabled(bool(msg.data), via="/brain/gesture_enabled")

    def _declare_params(self) -> None:
        # Plan D Phase 0 (2026-06-10): perception parsing extracted to
        # perception_router. False = legacy inline parsing (kept one release
        # as instant fallback). Flip via executive.yaml or ros2 param set.
        self.declare_parameter("perception_router_enabled", True)
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
        # 2026-05-23 PM: 5/27 demo video mode — peace 直接觸發 stretch (繞 PendingConfirm)
        # 預設 False 維持現有「peace 要 OK 二確認」安全行為
        # 設 true → peace 進入 _GESTURE_DIRECT={"peace":"stretch"}，一步觸發、不需 OK
        self.declare_parameter("peace_direct_stretch", False)
        # 2026-06-08 VIS-5 demo gesture mode (Roy「thumbs_up 不要引出 wiggle」):
        # True → thumbs_up 移出 _GESTURE_CONFIRM（不問「比 OK 我就做 wiggle」），
        # 改發一句輕量正向 say_canned；不進 PendingConfirm、不一步觸發 wiggle。
        self.declare_parameter("thumbs_up_demo_ack", False)
        # 2026-06-09 demo: gesture_enabled runtime gate（操作員可在錄影中前段關手勢、
        # take 開）。True=正常處理手勢；False=_on_gesture 直接 early-return、完全不發 plan。
        # 走 add_on_set_parameters_callback 支援 `ros2 param set` runtime 切換。
        self.declare_parameter("gesture_enabled", True)
        # 2026-06-10 demo（Roy 6/9 晚拍板）: stranger_alert 總開關。6/9 HITL 定位
        # face 幻覺會在沒人處鎖 unknown → stranger_alert 的 active plan 卡死
        # cup/greet 的 not-active gate（demo 全黑真兇）。False = _on_face 的
        # unknown 分支整路略過（不累積、不發 plan）。fallen/stop 安全鏈不受影響
        # （走 SafetyLayer hard_rule，不經這裡）。
        self.declare_parameter("stranger_alert_enabled", True)
        # 2026-06-10 demo（Roy 6/9 晚拍板）: WeGo 主手勢改 peace（比耶）。
        # thumbs_up 握杯/托腮易誤觸；true → _GESTURE_CONFIRM["peace"]="wiggle"
        # （兩步確認，禁 direct motion）。thumbs_up 的 confirm 路徑保留，
        # 上機 A/B 後擇一。與 peace_direct_stretch 互斥使用。
        self.declare_parameter("peace_wego_confirm", False)
        # 2026-05-23 PM: 5/27 demo video mode — cup+Roy+sitting 複合句
        # 設 true → 觸發複合句「我看到 Roy 坐著拿著杯子，是口渴了嗎」+ 砍 sit_along TTS
        # 預設 False 維持現有 object_remark + sit_along 獨立行為
        self.declare_parameter("demo_video_cup_compound", False)
        self.declare_parameter("demo_video_silent_sit_along", False)
        self.declare_parameter("capability_gate_enabled", False)
        self.declare_parameter("baseline_snapshot_path", "")
        # 2026-06-08 VIS-4 (Roy「不要距離限制，人臉+姿勢對就講+cooldown」):
        # greet_known_person 原本 gate 在 attention ENGAGED（距離 ≤1.6m + dwell），
        # 但 D435 depth 在 ~1.5-2m 太抖，逼使用者貼著鏡頭不動才觸發。改 gate 在
        # 「known face stable + 最近 greet_sitting_window_s 秒內偵測到 sitting」，
        # 跟台詞「我看到你坐下來了」一致；greet_cooldown_s 防止重複問候。
        # greet_require_sitting=False → 只看人臉 stable(+cooldown)，不要求姿勢。
        self.declare_parameter("greet_require_sitting", True)
        self.declare_parameter("greet_sitting_window_s", 3.0)
        self.declare_parameter("greet_cooldown_s", 20.0)
        # 2026-06-10 demo phase gate（最小版）：all=不 gate（預設、零行為改變）；
        # s2_face / s3_object / s4_gesture = 只放行該段的自發 proposal；quiet=全擋。
        # 只影響 greet/object_remark/gesture 三條社交路徑，safety 與明確指令不受影響。
        self.declare_parameter("demo_phase", "all")
        # plan3 T4 (2026-06-13): offline_mode — default False = byte-identical.
        # True short-circuits the chat/LLM path straight to phase-aware canned
        # (no chat_wait_ms window). Safety is NEVER short-circuited (rule-first
        # always). Runtime-switchable via `ros2 param set offline_mode true`.
        self.declare_parameter("offline_mode", False)
        # ISM Phase 1 shadow (system Phase 2 T2A-2): observe-only wiring, default
        # OFF = emit byte-identical. Runtime-switchable via `ros2 param set`
        # (_on_set_params) — 6/8 reactive_stop "param read once in __init__" lesson;
        # T2A-4 turns shadow on at runtime without touching the frozen demo script.
        self.declare_parameter("ism_shadow_enabled", False)
        self.declare_parameter("ism_enabled", False)
        self.declare_parameter("ism_stage_2a_demo_phase", False)
        self.declare_parameter("ism_stage_2b_confirm", False)
        self.declare_parameter("ism_stage_2c_executing", False)
        self.declare_parameter("ism_stage_2d_speaking", False)
        self.perception_router_enabled = bool(
            self.get_parameter("perception_router_enabled").value
        )
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
        self.peace_direct_stretch = bool(self.get_parameter("peace_direct_stretch").value)
        self.thumbs_up_demo_ack = bool(self.get_parameter("thumbs_up_demo_ack").value)
        self.gesture_enabled = bool(self.get_parameter("gesture_enabled").value)
        self.stranger_alert_enabled = bool(
            self.get_parameter("stranger_alert_enabled").value
        )
        self.peace_wego_confirm = bool(self.get_parameter("peace_wego_confirm").value)
        self.demo_video_cup_compound = bool(self.get_parameter("demo_video_cup_compound").value)
        self.demo_video_silent_sit_along = bool(self.get_parameter("demo_video_silent_sit_along").value)
        self._capability_gate_enabled = bool(
            self.get_parameter("capability_gate_enabled").value
        )
        self._baseline_snapshot_path = str(
            self.get_parameter("baseline_snapshot_path").value or ""
        )
        self.greet_require_sitting = bool(self.get_parameter("greet_require_sitting").value)
        self.greet_sitting_window_s = float(self.get_parameter("greet_sitting_window_s").value)
        self.greet_cooldown_s = float(self.get_parameter("greet_cooldown_s").value)
        self.demo_phase = str(self.get_parameter("demo_phase").value or "all").strip().lower()
        self.offline_mode = bool(self.get_parameter("offline_mode").value)
        self.ism_shadow_enabled = bool(self.get_parameter("ism_shadow_enabled").value)
        self.ism_enabled = bool(self.get_parameter("ism_enabled").value)
        self.ism_stage_2a_demo_phase = bool(
            self.get_parameter("ism_stage_2a_demo_phase").value
        )
        self.ism_stage_2b_confirm = bool(
            self.get_parameter("ism_stage_2b_confirm").value
        )
        self.ism_stage_2c_executing = bool(
            self.get_parameter("ism_stage_2c_executing").value
        )
        self.ism_stage_2d_speaking = bool(
            self.get_parameter("ism_stage_2d_speaking").value
        )
        self._capability_health_cache: dict[str, Any] | None = None
        self._apply_gesture_demo_modes()

    def _apply_gesture_demo_modes(self) -> None:
        """Apply demo-mode gesture mapping mutations from declared flags.

        Idempotent instance-level shadows of the _GESTURE_DIRECT / _GESTURE_CONFIRM
        class attributes — never touch other BrainNode instances or test fixtures.
        Extracted from __init__ so unit tests can build a node and re-run the
        mutation through the real production path (VIS-5).
        """
        if self.gesture_direct_disabled:
            # Instance shadow class attribute — 不影響其他 BrainNode instances 或 test fixtures
            self._GESTURE_DIRECT = {}
        if self.peace_direct_stretch:
            # demo video mode: peace 一步觸發 stretch, 同時砍掉 _GESTURE_CONFIRM["peace"]
            # 避免 peace 同時走 confirm path
            self._GESTURE_DIRECT = {**self._GESTURE_DIRECT, "peace": "stretch"}
            self._GESTURE_CONFIRM = {
                k: v for k, v in self._GESTURE_CONFIRM.items() if k != "peace"
            }
        if self.thumbs_up_demo_ack:
            # 2026-06-08 VIS-5: thumbs_up 不走 confirm（不問 OK）、也不一步觸發 wiggle，
            # 由 _on_gesture 的 demo-ack 分支發輕量正向回應。
            self._GESTURE_CONFIRM = {
                k: v for k, v in self._GESTURE_CONFIRM.items() if k != "thumbs_up"
            }
        if self.peace_wego_confirm:
            # 2026-06-10: peace 改走 WeGo 兩步確認（peace→wiggle），取代預設的
            # peace→stretch 映射。仍要 OK 二確認，無 direct motion。
            self._GESTURE_CONFIRM = {**self._GESTURE_CONFIRM, "peace": "wiggle"}

    def _emit(self, plan: SkillPlan) -> None:
        # ISM shadow ACCEPT-side chokepoint (T2A-2): observe-only, no-op when
        # disabled, runs outside self._lock, never raises, never alters emit.
        self._ism_shadow_on_emit(plan)
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
        # Plan E: decision-chain bookkeeping + plan_emitted trace (additive).
        self._plan_decision[plan.plan_id] = self._current_decision_id
        self._trace(TraceEvent(
            decision_id=self._current_decision_id, node="brain_node",
            kind=TraceKind.PLAN_EMITTED, verdict=Verdict.ACCEPTED,
            gate="", reason=plan.reason, plan_id=plan.plan_id,
            detail={"skill": plan.selected_skill, "source": plan.source,
                    "priority": int(plan.priority_class)},
        ))

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
            # Plan E (additive): chains this proposal to its triggering
            # perception event; IE tolerates unknown fields.
            "decision_id": self._current_decision_id,
        }

    def _trace(self, ev: TraceEvent) -> None:
        """Publish a TraceEvent. NEVER raises — tracing must not break callbacks."""
        try:
            msg = String()
            msg.data = ev.to_json()
            self._pub_trace.publish(msg)
        except Exception as exc:  # noqa: BLE001 — additive instrumentation only
            self.get_logger().debug(f"trace publish failed: {exc}")

    def _suppressed(self, *, gate: str, reason: str, source_summary: str = "",
                    cooldown_remaining_s: float | None = None,
                    throttle_key: str | None = None, throttle_s: float = 5.0) -> None:
        """Emit a suppressed-verdict trace for a gate early-return (Plan E3).

        Reads shared state for the Roy-required context fields; never raises
        (the underlying _trace swallows publish errors, and the state reads are
        guarded here)."""
        if throttle_key is not None:
            now = time.time()
            if now - self._trace_throttle.get(throttle_key, 0.0) < throttle_s:
                return
            self._trace_throttle[throttle_key] = now
        try:
            with self._lock:
                active = self._state.active_plan or {}
            pending = f"{self._pending_confirm.state.name}:" \
                      f"{getattr(self._pending_confirm, 'skill', '') or ''}"
            self._trace(make_suppressed(
                decision_id=self._current_decision_id, node="brain_node",
                gate=gate, reason=reason, demo_phase=self.demo_phase,
                active_plan=str(active.get("selected_skill") or ""),
                pending_confirm=pending,
                cooldown_remaining_s=cooldown_remaining_s,
                source_summary=source_summary,
            ))
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"suppressed trace failed: {exc}")
        # ISM shadow SUPPRESS-side chokepoint (T2A-2): Plan E already funnels all
        # 19 gate early-returns through here, so one pure evaluate() covers them.
        # Throttled repeats return above — shadow volume mirrors legacy volume.
        self._ism_shadow_on_suppressed(gate=gate, reason=reason,
                                       source_summary=source_summary)

    # ── ISM Phase 1 shadow (system Phase 2 / 2A) ─────────────────────────────
    # Observe-only wiring: the shadow machine sees the same events legacy acts
    # on; its verdicts/transitions are published as /brain/trace events with
    # detail.shadow=true. The Decision NEVER influences emit/return. Every hook
    #   - early-returns when ism_shadow_enabled is False (default);
    #   - runs OUTSIDE self._lock (Plan E lock discipline);
    #   - never raises (spec-外 payload shapes must not kill a brain callback).

    def _ism_candidate_from_plan(self, plan: SkillPlan) -> IsmCandidate:
        """Map an emitted SkillPlan to an advisory shadow Candidate.

        priority_class first, then source. `explicit` mirrors §3.4 P2 (speech /
        gesture command / studio / LLM proposal) — shadow metadata for
        arbitration comparison, not an authorization (§3.3 source trust)."""
        pc = int(plan.priority_class)
        src = plan.source or ""
        did = self._current_decision_id
        if pc == int(PriorityClass.SAFETY):
            return IsmCandidate(kind="stop", priority=IsmPriority.SAFETY, source=src,
                                skill=plan.selected_skill, explicit=True,
                                decision_id=did)
        if pc == int(PriorityClass.ALERT):
            return IsmCandidate(kind="alert", priority=IsmPriority.ALERT, source=src,
                                skill=plan.selected_skill, decision_id=did)
        if src == "rule:confirmed":
            return IsmCandidate(kind="confirm_ok", priority=IsmPriority.CONFIRM,
                                source=src, skill=plan.selected_skill,
                                decision_id=did)
        if src == "rule:confirm_request":
            # The say_canned hint stands in for the confirm request itself; the
            # underlying skill rides in reason "awaiting_ok:<skill>".
            skill = plan.reason.split("awaiting_ok:", 1)[-1] \
                if "awaiting_ok:" in plan.reason else ""
            return IsmCandidate(kind="confirm_request", priority=IsmPriority.EXPLICIT,
                                source=src, skill=skill, requires_confirmation=True,
                                explicit=True, decision_id=did)
        if src == "rule:gesture":
            return IsmCandidate(kind="gesture_cmd", priority=IsmPriority.EXPLICIT,
                                source=src, skill=plan.selected_skill, explicit=True,
                                decision_id=did)
        if src in ("llm_bridge", "rule:chat_fallback", "llm_proposal", "studio_button"):
            return IsmCandidate(kind="chat", priority=IsmPriority.EXPLICIT, source=src,
                                skill=plan.selected_skill, explicit=True,
                                decision_id=did)
        # Spontaneous social rules (greet / sit_along / object_remark / idle / …)
        return IsmCandidate(kind=plan.selected_skill or "social",
                            priority=IsmPriority.SOCIAL, source=src,
                            skill=plan.selected_skill, decision_id=did)

    def _ism_candidate_from_suppressed(self, gate: str, reason: str,
                                       source_summary: str) -> IsmCandidate:
        """Advisory candidate for an event legacy gated out (no plan object).
        Family derived from the _suppressed source_summary conventions."""
        ss = source_summary or ""
        did = self._current_decision_id
        if gate == "stranger_alert_enabled":
            return IsmCandidate(kind="stranger_alert", priority=IsmPriority.ALERT,
                                source="face", decision_id=did)
        if ss.startswith("gesture="):
            return IsmCandidate(kind="gesture_cmd", priority=IsmPriority.EXPLICIT,
                                source="gesture", explicit=True, decision_id=did)
        if ss.startswith("class="):
            return IsmCandidate(kind="object_remark", priority=IsmPriority.SOCIAL,
                                source="object", decision_id=did)
        if ss.startswith("identity="):
            return IsmCandidate(kind="greet", priority=IsmPriority.SOCIAL,
                                source="face", decision_id=did)
        if ss.startswith(("skill:", "session=")):
            return IsmCandidate(kind="skill_request", priority=IsmPriority.EXPLICIT,
                                source="speech", explicit=True, decision_id=did)
        if gate == "demo_phase":
            family = reason.rsplit(":", 1)[-1]
            if family == "gesture":
                return IsmCandidate(kind="gesture_cmd", priority=IsmPriority.EXPLICIT,
                                    source="gesture", explicit=True, decision_id=did)
            return IsmCandidate(kind=family or "social", priority=IsmPriority.SOCIAL,
                                source=family or "unknown", decision_id=did)
        if gate == "dedup":
            family = reason.split(":")[1] if ":" in reason else "unknown"
            if family in ("speech", "gesture"):
                return IsmCandidate(kind=f"dedup:{family}",
                                    priority=IsmPriority.EXPLICIT, source=family,
                                    explicit=True, decision_id=did)
            return IsmCandidate(kind=f"dedup:{family}", priority=IsmPriority.SOCIAL,
                                source=family, decision_id=did)
        return IsmCandidate(kind=gate or "unknown", priority=IsmPriority.SOCIAL,
                            source="unknown", decision_id=did)

    def _ism_shadow_on_emit(self, plan: SkillPlan) -> None:
        if not self.ism_shadow_enabled:
            return
        try:
            cand = self._ism_candidate_from_plan(plan)
            pre = self._ism.state.value
            decision = self._ism.propose(cand, time.time())
            self._ism_trace_candidate(cand, decision, pre, legacy_action="emitted")
            self._ism_shadow_drain_transitions(cand.decision_id)
        except Exception as exc:  # noqa: BLE001 — shadow must never break emit
            self.get_logger().debug(f"ism shadow emit hook failed: {exc}")

    def _ism_shadow_on_suppressed(self, gate: str, reason: str,
                                  source_summary: str) -> None:
        if not self.ism_shadow_enabled:
            return
        try:
            cand = self._ism_candidate_from_suppressed(gate, reason, source_summary)
            # evaluate() is PURE — an event legacy dropped must not advance the
            # shadow machine (a counterfactual ACCEPT would corrupt the shadow
            # trajectory and poison the parity data the 6/18 soak collects).
            decision = IsmPolicy.evaluate(self._ism.state, cand)
            self._ism_trace_candidate(cand, decision, self._ism.state.value,
                                      legacy_action="suppressed",
                                      legacy_gate=gate, legacy_reason=reason)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"ism shadow suppress hook failed: {exc}")

    def _ism_shadow_confirm_requested(self, skill: str, source: str) -> None:
        """request_confirm sites that emit no say_canned hint (llm confirm mode).
        Gesture / skill_request confirm paths are covered by the
        rule:confirm_request mapping in _ism_shadow_on_emit — do not double-feed."""
        if not self.ism_shadow_enabled:
            return
        try:
            cand = IsmCandidate(kind="confirm_request", priority=IsmPriority.EXPLICIT,
                                source=source, skill=skill, requires_confirmation=True,
                                explicit=True, decision_id=self._current_decision_id)
            pre = self._ism.state.value
            decision = self._ism.propose(cand, time.time())
            self._ism_trace_candidate(cand, decision, pre,
                                      legacy_action="confirm_requested")
            self._ism_shadow_drain_transitions(cand.decision_id)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"ism shadow confirm hook failed: {exc}")

    def _ism_shadow_confirm_cancelled(self, reason: str) -> None:
        if not self.ism_shadow_enabled:
            return
        try:
            if self._ism.state is not IsmState.CONFIRM_PENDING:
                return  # drifted — the 30s grace watchdog reconciles; don't fabricate
            cand = IsmCandidate(kind="confirm_cancel", priority=IsmPriority.CONFIRM,
                                source="confirm",
                                decision_id=self._current_decision_id)
            pre = self._ism.state.value
            decision = self._ism.propose(cand, time.time())
            self._ism_trace_candidate(cand, decision, pre,
                                      legacy_action=f"confirm_cancelled:{reason}")
            self._ism_shadow_drain_transitions(cand.decision_id)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"ism shadow cancel hook failed: {exc}")

    def _ism_shadow_on_skill_result(self, status, plan_id,
                                    payload: dict[str, Any]) -> None:
        if not self.ism_shadow_enabled:
            return
        try:
            # Wire statuses are lowercase ("started"/"completed"); the machine's
            # lifecycle table is uppercase — normalize here, nowhere else.
            st = str(status or "").upper()
            detail: dict[str, Any] = {"status": st, "plan_id": str(plan_id or "")}
            if st == "STARTED":
                detail["priority_class"] = int(
                    payload.get("priority_class", int(PriorityClass.SKILL))
                )
                contract = SKILL_REGISTRY.get(str(payload.get("selected_skill") or ""))
                # §3.6 watchdog consumes SkillContract.timeout_s — the wire
                # payload doesn't carry it, so look it up registry-side.
                detail["timeout_s"] = float(contract.timeout_s) if contract else 0.0
            did = self._plan_decision.get(str(plan_id), "")
            self._ism.apply_signal(
                IsmSignal(trigger=IsmTrigger.SKILL_RESULT, detail=detail,
                          decision_id=did),
                now=time.time())
            self._ism_shadow_drain_transitions(did)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"ism shadow skill_result hook failed: {exc}")

    def _ism_shadow_signal(self, trigger: IsmTrigger, detail: dict[str, Any]) -> None:
        if not self.ism_shadow_enabled:
            return
        try:
            self._ism.apply_signal(IsmSignal(trigger=trigger, detail=detail),
                                   now=time.time())
            self._ism_shadow_drain_transitions("")
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"ism shadow signal hook failed: {exc}")

    def _ism_shadow_tick(self) -> None:
        """10Hz piggyback on the attention tick (no new timer, per spec):
        /state/tts_playing Bool edge → TTS_ACK signal, then watchdog tick."""
        if not self.ism_shadow_enabled:
            return
        try:
            now = time.time()
            tts = bool(self._world.snapshot().tts_playing)
            if tts != self._ism_last_tts:
                self._ism_last_tts = tts
                self._ism.apply_signal(
                    IsmSignal(trigger=IsmTrigger.TTS_ACK,
                              detail={"event": "start" if tts else "end"}),
                    now=now)
            prev_plan_id = str(getattr(self._ism, "_active_plan_id", "") or "")
            decision = self._ism.tick(now)
            self._ism_shadow_drain_transitions("")
            if (
                decision is not None
                and str(decision.reason).startswith("watchdog_timeout:executing")
                and self._ism_stage_on("ism_stage_2c_executing")
            ):
                self._watchdog_reset_active_plan(prev_plan_id)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"ism shadow tick failed: {exc}")

    def _watchdog_reset_active_plan(self, plan_id: str) -> None:
        try:
            with self._lock:
                active = self._state.active_plan
                if active is not None and (not plan_id or active.get("plan_id") == plan_id):
                    cleared_id = active.get("plan_id")
                    self._state.active_plan = None
                    self._state.active_step = None
                else:
                    cleared_id = None
            if cleared_id is not None:
                trace_plan_id = str(plan_id or cleared_id or "")
                self._trace(TraceEvent(
                    decision_id=self._plan_decision.get(trace_plan_id, ""),
                    node="brain_node", kind=TraceKind.STATE_TRANSITION,
                    verdict=Verdict.SUPPRESSED, gate="watchdog",
                    reason=f"watchdog_timeout:executing:{trace_plan_id}",
                    detail={"watchdog": True, "plan_id": trace_plan_id,
                            "cleanup": "active_plan_reset"},
                ))
                self.get_logger().warn(
                    "[watchdog] EXECUTING timeout - active_plan cleared "
                    f"(plan_id={trace_plan_id})"
                )
        except Exception as exc:  # noqa: BLE001
            self.get_logger().debug(f"watchdog reset failed: {exc}")

    def _ism_shadow_drain_transitions(self, decision_id: str) -> None:
        """Emit STATE_TRANSITION traces for machine history appended since the
        last drain. History is a 64-entry ring — on truncation just resync."""
        hist = self._ism.history
        if len(hist) < self._ism_history_len:
            self._ism_history_len = max(0, len(hist) - 1)
        for ts, frm, to, trigger in hist[self._ism_history_len:]:
            self._trace(TraceEvent(
                decision_id=decision_id, node="brain_node",
                kind=TraceKind.STATE_TRANSITION, verdict=Verdict.ACCEPTED,
                gate="ism_shadow", reason=f"{frm}->{to}:{trigger}",
                detail={"shadow": True, "from_state": frm, "to_state": to,
                        "trigger": trigger, "machine_ts": ts},
            ))
        self._ism_history_len = len(hist)

    def _ism_trace_candidate(self, cand: IsmCandidate, decision: IsmDecision,
                             pre_state: str, legacy_action: str,
                             legacy_gate: str = "", legacy_reason: str = "") -> None:
        verdict = (Verdict.ACCEPTED
                   if decision.verdict in (IsmVerdict.ACCEPT, IsmVerdict.PREEMPT)
                   else Verdict.SUPPRESSED)
        self._trace(TraceEvent(
            decision_id=cand.decision_id, node="brain_node",
            kind=TraceKind.CANDIDATE, verdict=verdict, gate="ism_shadow",
            reason=decision.reason,
            detail={"shadow": True, "ism_state": pre_state,
                    "ism_state_after": self._ism.state.value,
                    "ism_verdict": decision.verdict.value,
                    "ism_reason": decision.reason,
                    "candidate_kind": cand.kind,
                    "candidate_priority": int(cand.priority),
                    "candidate_skill": cand.skill,
                    "legacy_action": legacy_action,
                    "legacy_gate": legacy_gate, "legacy_reason": legacy_reason},
        ))

    def _cooldown_remaining(self, key: str, cooldown_s: float) -> float:
        last = self._state.last_alert_ts.get(key)
        if last is None:
            return 0.0
        return max(0.0, cooldown_s - (time.time() - last))

    def _in_cooldown(self, key: str, cooldown_s: float) -> bool:
        last = self._state.last_alert_ts.get(key)
        return last is not None and (time.time() - last) < cooldown_s

    def _mark_cooldown(self, key: str) -> None:
        self._state.last_alert_ts[key] = time.time()

    def _capability_health_block(self, skill: str) -> str | None:
        if not self._capability_gate_enabled:
            return None

        # Lazy import: keep brain_node importable (IE standalone tests) without
        # pawai_brain on the path; only the gate-ON runtime path needs it.
        from pawai_brain.capability.health_loader import (
            load_capability_health,
            skill_capability,
        )

        capability_id = skill_capability(skill)
        if capability_id == "content":
            return None
        if capability_id is None:
            if self._skill_has_motion_or_nav(skill):
                return f"{skill}:unmapped_motion_capability"
            return None

        if self._capability_health_cache is None:
            self._capability_health_cache = load_capability_health(self._baseline_snapshot_path)

        health = self._capability_health_cache.get(capability_id)
        grade = str(health.grade)
        if grade in {"fail", "degraded", "insufficient_data"} or not health.brain_allowed:
            return f"{skill}:{capability_id}:{grade}"
        return None

    def _skill_has_motion_or_nav(self, skill: str) -> bool:
        contract = SKILL_REGISTRY.get(skill)
        if contract is None:
            return True
        motion_executors = {ExecutorKind.MOTION, ExecutorKind.NAV}
        return any(step.executor in motion_executors for step in (contract.steps or []))

    def _check_dedup(self, source: str, key: str) -> bool:
        if not key:
            key = "_empty"
        now = time.time()
        bucket = int(now / max(self.dedup_window_s, 0.001))
        cache_key = (source, key, bucket)
        with self._lock:
            hit = cache_key in self._state.dedup_cache
            if not hit:
                self._state.dedup_cache[cache_key] = now
        if hit:
            self._suppressed(gate="dedup", reason=f"dedup:{source}:{key}",
                             throttle_key=f"dedup:{source}:{key}")
            return True
        return False

    def _gc_dedup(self) -> None:
        cutoff = time.time() - 5.0
        with self._lock:
            self._state.dedup_cache = {
                key: ts for key, ts in self._state.dedup_cache.items() if ts > cutoff
            }
        # Plan E: bound the plan→decision map (insertion-ordered dict).
        while len(self._plan_decision) > 200:
            self._plan_decision.pop(next(iter(self._plan_decision)))
        # Plan E: expire stale trace-throttle entries (same 5s horizon family).
        tcut = time.time() - 60.0
        self._trace_throttle = {
            k: ts for k, ts in self._trace_throttle.items() if ts > tcut
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
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"speech-{uuid.uuid4().hex[:12]}"
        if self.perception_router_enabled:
            ev = parse_speech(payload)
            transcript, session_id = ev.transcript, ev.session_id
        else:  # legacy parse — Phase 0 fallback, byte-identical semantics
            transcript = str(payload.get("transcript") or payload.get("text") or "").strip()
            session_id = str(
                payload.get("session_id") or payload.get("request_id")
                or f"speech-{time.time_ns()}"
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

        # plan3 T4: offline_mode short-circuits the cloud chat/LLM path straight
        # to canned (0s, no chat_wait_ms window, no LLM request). Reached only
        # AFTER safety hard_rule + unsafe-keyword + explicit paths above, so
        # safety stays rule-first. demo_phase=all/quiet (no table entry) keeps
        # the legacy 「我聽不太懂」fallback string.
        if self.offline_mode:
            text = self._phase_canned(self.demo_phase, "generic") or "我聽不太懂"
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": text},
                    source="rule:chat_fallback",
                    reason="offline_mode",
                    session_id=session_id,
                )
            )
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
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"chat-{uuid.uuid4().hex[:12]}"
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
            self._suppressed(gate="llm_allowlist", reason=f"skill:{proposed_skill}",
                             source_summary=f"session={session_id}")
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="rejected_not_allowed",
                detail=proposed_skill,
            )
            return

        reason = self._capability_health_block(proposed_skill)
        if reason:
            self._suppressed(gate="capability_health", reason=str(reason),
                             source_summary=f"skill:{proposed_skill}")
            self._emit_trace(
                session_id=session_id,
                engine=engine,
                stage="skill_gate",
                status="blocked",
                detail=reason,
            )
            return

        cd = SKILL_REGISTRY[proposed_skill].cooldown_s
        if self._in_cooldown(proposed_skill, cd):
            self._suppressed(
                gate="skill_cooldown", reason=f"{proposed_skill}:cooldown",
                source_summary=f"skill:{proposed_skill}",
                cooldown_remaining_s=self._cooldown_remaining(proposed_skill, cd))
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
            # ISM shadow: this request_confirm site emits no say_canned hint, so
            # the rule:confirm_request emit mapping never sees it — feed directly.
            self._ism_shadow_confirm_requested(proposed_skill, source="speech")
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
    # Single-sourced in pawai_contracts (Plan C4). Class-attr assignment keeps
    # self.LLM_PROPOSABLE_SKILLS / self.LLM_PROPOSAL_EXECUTE references unchanged.
    LLM_PROPOSABLE_SKILLS = _llm_policy.LLM_PROPOSABLE_SKILLS
    LLM_PROPOSAL_EXECUTE = _llm_policy.LLM_PROPOSAL_EXECUTE

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
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"gesture-{uuid.uuid4().hex[:12]}"
        if self.perception_router_enabled:
            gesture = parse_gesture(payload).gesture
        else:  # legacy parse — Phase 0 fallback, byte-identical semantics
            gesture = str(
                payload.get("gesture") or payload.get("type") or payload.get("label") or ""
            ).strip().lower()
        if not gesture:
            return

        # 2026-06-09 demo: runtime gate — 操作員關閉時手勢完全不發 plan。
        # (Plan E: /brain/trace 的 suppressed 仍發 — 它就是回答「為什麼沒反應」的通道。)
        if not self.gesture_enabled:
            self._suppressed(gate="gesture_enabled", reason="gesture_enabled=false",
                             source_summary=f"gesture={gesture}",
                             throttle_key=f"gesture_off:{gesture}")
            return
        # 2026-06-10 demo phase gate（all=不擋）
        if not self._phase_allows("gesture"):
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
            self._suppressed(gate="pending_confirm", reason="confirm_in_flight",
                             source_summary=f"gesture={gesture}")
            return

        if self._has_active_skill_or_sequence():
            self._suppressed(gate="active_plan", reason="skill_or_sequence_active",
                             source_summary=f"gesture={gesture}")
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
                self._suppressed(gate="conversation_gate",
                                 reason=f"conversation_gate:{reason_str}",
                                 source_summary=f"gesture={gesture}")
                if tts_playing:
                    self._ism_speaking_queue_marker(source_summary=f"gesture={gesture}")
                self._emit_trace(
                    session_id=f"gesture-{int(time.time())}",
                    engine="brain_node",
                    stage="gesture_gate",
                    status="blocked",
                    detail=f"{gesture}:{reason_str}",
                )
                return

        if self.thumbs_up_demo_ack and gesture == "thumbs_up":
            # VIS-5 demo: 簡單正向回應，不引出 wiggle confirmation
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": "[happy] 收到，謝謝你！"},
                    source="rule:gesture",
                    reason="gesture:thumbs_up:demo_ack",
                )
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
            # 2026-06-09 demo: WeGo 台詞綁在 wiggle 技能上（thumbs_up 或 peace 進來
            # 都講同一句，6/10 改 keyed-on-skill 支援 peace_wego_confirm），
            # 其餘手勢維持泛用句「比 OK 我就做 {skill}」。
            confirm_text = (
                "[curious] 你要我 WeGo 一下嗎？比 OK 我就開始。"
                if skill == "wiggle"
                else f"[curious] 比 OK 我就做 {skill}"
            )
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": confirm_text},
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
            # ISM shadow: tick-driven cancel (timeout) has no emit to piggyback on.
            self._ism_shadow_confirm_cancelled(outcome.reason)

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
        # ISM shadow: TTS Bool edge + watchdog tick piggyback (outside _lock).
        self._ism_shadow_tick()

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
            remaining = self._cooldown_remaining(skill, cd)
            self._suppressed(
                gate="skill_cooldown", reason=f"cooldown:{skill}:{remaining:.1f}s",
                source_summary=f"skill:{skill}", cooldown_remaining_s=remaining,
                throttle_key=f"skill_cd:{skill}")
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
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"face-{uuid.uuid4().hex[:12]}"
        if self.perception_router_enabled:
            ev = parse_face(payload)
            identity, stable = ev.identity, ev.stable
            distance_m, event_type = ev.distance_m, ev.event_type
        else:  # legacy parse — Phase 0 fallback, byte-identical semantics
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
            # distance_m may be in the payload (depth cameras); None if absent.
            distance_m = None
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
                # 2026-06-10 demo: stranger_alert_enabled=False 時擋發射不擋累積
                # （6/9 HITL：face 幻覺餵爆 unknown → active plan 霸佔 brain，
                # cup/greet 全黑的根因）。runtime param set 開回時立即恢復。
                if not self.stranger_alert_enabled:
                    self._suppressed(gate="stranger_alert_enabled",
                                     reason="stranger_alert_enabled=false",
                                     source_summary=f"identity={identity}",
                                     throttle_key="stranger_alert_enabled")
                if (
                    self.stranger_alert_enabled
                    and not self._in_cooldown("stranger_alert", 30.0)
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
        # 2026-06-10 demo phase gate（all=不擋）
        if not self._phase_allows("greet"):
            return
        # 5/8 [#F-confirm]: PENDING 期間不發 greet_known_person，避免蓋掉 confirm 流
        tts_in_parts = bool(self._world.snapshot().tts_playing)
        if not stable or self._has_active_skill_or_sequence() \
                or self._pending_confirm.state == ConfirmState.PENDING \
                or tts_in_parts:
            # 5/9 review: also block during TTS to avoid mid-sentence interrupt.
            parts = []
            if not stable:
                parts.append("not_stable")
            if self._has_active_skill_or_sequence():
                parts.append("active_plan")
            if self._pending_confirm.state == ConfirmState.PENDING:
                parts.append("pending_confirm")
            if tts_in_parts:
                parts.append("tts_playing")
            self._suppressed(gate="greet_gate", reason=",".join(parts) or "greet_gate",
                             source_summary=f"identity={identity}",
                             throttle_key=f"greet_gate:{identity}")
            if tts_in_parts:
                self._ism_speaking_queue_marker(source_summary=f"identity={identity}")
            return
        # 2026-06-08 VIS-4 (Roy): drop the ENGAGED distance/dwell gate. D435 depth at
        # ~1.5-2m is too noisy — a distance threshold forced the user to hold an exact
        # spot and the greeting almost never fired. Replace with "known face stable +
        # recently sitting" (matches the line「我看到你坐下來了」). greet_cooldown_s
        # prevents repeating the greeting. greet_require_sitting=False → face-only.
        if self.greet_require_sitting:
            last_sit = self._state.last_sitting_seen_ts
            if last_sit <= 0.0 or (time.time() - last_sit) > self.greet_sitting_window_s:
                self._suppressed(gate="greet_sitting_window",
                                 reason=f"sitting_window:{self.greet_sitting_window_s}s",
                                 source_summary=f"identity={identity}",
                                 throttle_key=f"greet_sitting:{identity}")
                return  # not currently sitting → don't greet
        # known face stable (+ sitting) is real engagement → reset idle clock
        self._touch_user_interaction()
        cooldown_key = f"greet_known_person:{identity}"
        if self._in_cooldown(cooldown_key, self.greet_cooldown_s):
            self._suppressed(
                gate="greet_cooldown", reason=f"cooldown:greet:{identity}",
                source_summary=f"identity={identity}",
                cooldown_remaining_s=self._cooldown_remaining(
                    cooldown_key, self.greet_cooldown_s),
                throttle_key=f"greet_cooldown:{identity}")
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
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"pose-{uuid.uuid4().hex[:12]}"
        if self.perception_router_enabled:
            pose = parse_pose(payload).pose
        else:  # legacy parse — Phase 0 fallback, byte-identical semantics
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
                    if self._pending_confirm.state == ConfirmState.PENDING \
                            and self._ism_confirm_preempt_active():
                        self._pending_confirm.cancel(reason="preempt:fallen")
                        self._ism_shadow_confirm_cancelled("preempt:fallen")
                        self.get_logger().info(
                            "PendingConfirm preempted by fallen (ism_stage_2b)"
                        )
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
            # 2026-05-23: last_sitting_seen_ts 持續更新 (for cup+Roy+sitting 複合句 check)
            self._state.last_sitting_seen_ts = now
            if self._state.sitting_first_seen is None:
                self._state.sitting_first_seen = now
            elif (now - self._state.sitting_first_seen) >= 1.0 and not confirm_pending:
                # 2026-05-23 5/27 demo video mode: sit_along TTS「會不會太累」
                # 跟 cup+Roy+sitting 複合句語意打架 → 設 param 砍 sit_along auto-fire
                if not self.demo_video_silent_sit_along:
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
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"object-{uuid.uuid4().hex[:12]}"

        if self.perception_router_enabled:
            ev = parse_object(payload)
            class_name, color = ev.class_name, ev.color
        else:  # legacy parse — Phase 0 fallback, byte-identical semantics
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
                    payload.get("class_name") or payload.get("label")
                    or payload.get("class") or ""
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
        # 2026-06-10 demo phase gate（all=不擋；含 compound 句路徑）
        if not self._phase_allows("object"):
            return

        snap = self._world.snapshot()
        # 5/9 final review: was reading self._attention.state without lock —
        # 3rd race-condition hole alongside stranger_alert / greet_known_person
        # which already use _attention_state_snapshot(). Fix: same helper.
        if self._attention_state_snapshot() != AttentionState.ENGAGED:
            self._suppressed(gate="attention_engaged",
                             reason=f"attention:{self._attention_state_snapshot().name}",
                             source_summary=f"class={class_name}",
                             throttle_key=f"obj_engaged:{class_name}")
            return  # IDLE / NOTICED / INTERACTING — stay quiet
        if self._has_active_skill_or_sequence():
            self._suppressed(gate="active_plan", reason="skill_or_sequence_active",
                             source_summary=f"class={class_name}",
                             throttle_key=f"obj_active:{class_name}")
            return
        if self._pending_confirm.state == ConfirmState.PENDING:
            self._suppressed(gate="pending_confirm", reason="confirm_in_flight",
                             source_summary=f"class={class_name}")
            return
        if snap.tts_playing:
            self._suppressed(gate="tts_playing", reason="tts_playing",
                             source_summary=f"class={class_name}",
                             throttle_key=f"obj_tts:{class_name}")
            self._ism_speaking_queue_marker(source_summary=f"class={class_name}")
            return  # Don't insert object remark while PAI is speaking

        # 2026-05-23 5/27 demo video mode: cup + Roy + recent sitting → 複合句
        # Roy 5/23 PM 指定 demo 句:「我看到 Roy 坐著拿著杯子，是口渴了嗎」
        # 觸發條件:
        #   - class_name == "cup"
        #   - last_stable_identity_name == "Roy" (5/12 face cache, ≤30s 算 fresh)
        #   - last_sitting_seen_ts 在最近 10s 內 (Roy 真的坐著且 brain 看到)
        # 5/28+ 設 demo_video_cup_compound=false 即可 revert
        now = time.time()
        if (
            self.demo_video_cup_compound
            and class_name == "cup"
        ):
            with self._lock:
                cached_name = self._last_stable_identity_name
                cached_age = now - self._last_stable_identity_ts
            recent_sitting = (now - self._state.last_sitting_seen_ts) < 10.0
            if cached_name == "Roy" and cached_age <= 30.0 and recent_sitting:
                # 直接 emit say_canned 固定句，跳過 object_remark
                compound_key = ("cup_compound_roy_sitting",)
                last_compound = self._object_remark_seen.get(compound_key, 0.0)
                if now - last_compound >= 60.0:
                    self._object_remark_seen[compound_key] = now
                    self._emit(
                        build_plan(
                            "say_canned",
                            args={"text": "我看到 Roy 坐著拿著杯子，是口渴了嗎？"},
                            source="rule:demo_video_cup_compound",
                            reason="cup+Roy+sitting",
                        )
                    )
                    return

        # Compose zh-TW TTS — None means class is outside the speaking whitelist.
        text = build_object_tts(class_name, color)
        if text is None:
            return

        # D-4: dedup key = class_name only (drop color).
        # Rationale: YOLO color labels jitter on the same object (brown_chair →
        # coffee_chair → dark_chair within seconds), which previously bypassed
        # the 60s dedup.  class_name-only key gives stable dedup across color noise.
        seen_key = (class_name,)
        last = self._object_remark_seen.get(seen_key, 0.0)
        if now - last < OBJECT_REMARK_DEDUP_S:
            self._suppressed(
                gate="object_remark_dedup",
                reason=f"remark_dedup:{class_name}",
                source_summary=f"class={class_name}",
                cooldown_remaining_s=max(0.0, OBJECT_REMARK_DEDUP_S - (now - last)),
                throttle_key=f"obj_dedup:{class_name}")
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
    # 6/10 issue #129: move_forward 加入 bypass — 操作員按鈕本身就是 explicit
    # confirm（NAV executor 另有 nav_executor_enabled + 4 重 world gate
    # fail-closed 防線，預設不會動）。
    _STUDIO_BUTTON_BYPASS_CONFIRM = frozenset({"nav_demo_point", "move_forward"})

    def _on_skill_request(self, msg: String) -> None:
        payload = self._load_json(msg)
        if payload is None:
            return
        # Plan E: one decision_id per inbound event — chains gate verdicts,
        # plan and skill_result (single-threaded executor → serial-safe).
        self._current_decision_id = f"skill_request-{uuid.uuid4().hex[:12]}"
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
            # 2026-06-10 review blocker: STEP_FAILED 在 executive 端就是 plan 終結
            # （兩條 STEP_FAILED 路徑都緊跟 self._queue.pop()，不會再有 terminal
            # status）。若不在此清 active_plan，一次 NAV step 失敗（例如忘了開
            # nav_executor_enabled / goal rejected / timeout）會讓 active_plan
            # 永久卡住 → not-active gate 把 cup/greet/gesture/語音全黑（重演 6/9）。
            # Status set shared with the Plan E skill_result trace
            # (_TERMINAL_RESULT_STATUSES) so the two can never drift.
            elif status in self._TERMINAL_RESULT_STATUSES:
                if self._state.active_plan and self._state.active_plan["plan_id"] == plan_id:
                    self._state.active_plan = None
                    self._state.active_step = None

            for plan in self._state.last_plans:
                if plan.get("plan_id") == plan_id:
                    if status == SkillResultStatus.BLOCKED_BY_SAFETY.value:
                        plan["accepted"] = False
                    break

        # Plan E: skill_result trace on terminal/blocked statuses (additive).
        self._trace_skill_result(status, plan_id, payload)
        # ISM shadow: skill lifecycle is transition driver #1 (§3.2).
        self._ism_shadow_on_skill_result(status, plan_id, payload)

    _TERMINAL_RESULT_STATUSES = frozenset({
        SkillResultStatus.COMPLETED.value,
        SkillResultStatus.ABORTED.value,
        SkillResultStatus.BLOCKED_BY_SAFETY.value,
        SkillResultStatus.STEP_FAILED.value,
    })

    def _trace_skill_result(self, status, plan_id, payload: dict[str, Any]) -> None:
        """Plan E: emit a skill_result trace for terminal/blocked statuses."""
        if status not in self._TERMINAL_RESULT_STATUSES:
            return
        blocked = status == SkillResultStatus.BLOCKED_BY_SAFETY.value
        self._trace(TraceEvent(
            decision_id=self._plan_decision.get(str(plan_id), ""),
            node="brain_node", kind=TraceKind.SKILL_RESULT,
            verdict=Verdict.BLOCKED if blocked else Verdict.ACCEPTED,
            gate="safety" if blocked else "",
            reason=str(payload.get("reason") or status), plan_id=str(plan_id or ""),
            detail={"status": status},
        ))

    def _on_reset_context(self, msg: Empty) -> None:  # noqa: ARG002
        """P1-2: Cancel PendingConfirm when browser requests a context reset.

        Active plans and attention state are preserved — we only cancel any
        in-progress confirmation flow that the user is walking away from.
        """
        with self._lock:
            if self._pending_confirm.state == ConfirmState.PENDING:
                self._pending_confirm.cancel(reason="page_reset")
                self.get_logger().info("PendingConfirm cancelled by /brain/reset_context")
            # 2026-06-10 demo: 重錄 take 時 reset 也清 object_remark 的兩層 dedup
            # （60s per-class seen + skill cooldown），不然第二個 take 的 cup 台詞
            # 會被上一個 take 吃掉。其他 alert cooldown（stranger/greet）刻意保留。
            if self._object_remark_seen:
                self._object_remark_seen.clear()
                self.get_logger().info("object_remark dedup cleared by /brain/reset_context")
            self._state.last_alert_ts.pop("object_remark", None)
            self._state.active_plan = None
        # ISM shadow: operator reset is transition driver #4 (outside _lock).
        self._ism_shadow_signal(IsmTrigger.OPERATOR, {"op": "reset"})

    # Gesture-driven skills whose stale cooldown could shadow a re-fire after a
    # phase switch (e.g. switching back into s4 to re-record a take). Union of
    # _GESTURE_DIRECT + _GESTURE_CONFIRM values.
    _GESTURE_SKILL_COOLDOWN_KEYS = frozenset(
        {"wave_hello", "system_pause", "enter_mute_mode", "enter_listen_mode",
         "wiggle", "stretch", "content", "stop_move"}
    )

    @staticmethod
    def _guarded(fn, logger, label):
        """Run a cleanup substep; swallow + debug-log any failure (never raises)."""
        try:
            fn()
            return True
        except Exception as exc:  # noqa: BLE001 — cleanup must never break callback
            logger.debug(f"phase transition {label} failed: {exc}")
            return False

    def _clear_pending_confirm_for_phase(self, canon_new: str, cleared: list) -> None:
        if self._pending_confirm.state == ConfirmState.PENDING:
            self._pending_confirm.cancel(reason=f"phase_switch:{canon_new}")
            cleared.append("pending_confirm")

    def _clear_gesture_cooldown(self, cleared: list) -> None:
        for key in self._GESTURE_SKILL_COOLDOWN_KEYS:
            self._state.last_alert_ts.pop(key, None)
        self._state.dedup_cache = {
            k: ts for k, ts in self._state.dedup_cache.items()
            if not (isinstance(k, tuple) and k and k[0] == "gesture")
        }
        self._state.current_gesture = None
        self._state.current_gesture_ts = 0.0
        cleared.append("gesture_cd")

    def _clear_object_dedup(self, cleared: list) -> None:
        if self._object_remark_seen:
            self._object_remark_seen.clear()
        self._state.last_alert_ts.pop("object_remark", None)
        cleared.append("object_remark")

    def _clear_greet_cooldown_keys(self, cleared: list) -> None:
        for key in [k for k in self._state.last_alert_ts
                    if k.startswith("greet_known_person:")]:
            self._state.last_alert_ts.pop(key, None)
        cleared.append("greet_cooldown")

    def _apply_phase_transition(self, new_phase, old_phase, *,
                                clear_object=None, clear_greet=None) -> None:
        """plan2 T2-2: clear stale interaction state on a real phase change.

        MUST clear: pending_confirm (if PENDING) + active_plan + gesture
        cooldown. MUST NOT clear attention (人在框不需重進場 — same rule as
        _on_reset_context :2193). clear_object/clear_greet default to None ->
        decided by the *target* phase (entering/recording s3 clears object dedup;
        entering s2 clears per-person greet cooldown). Emits ONE STATE_TRANSITION
        trace via the existing channel (no new schema). Never raises — every
        substep is independently guarded so the calling param/topic callback
        cannot be broken by cleanup.
        """
        canon_new = interaction_state.canonicalize_phase(str(new_phase))
        if clear_object is None:
            clear_object = canon_new == "s3_pose_object"
        if clear_greet is None:
            clear_greet = canon_new == "s2_greet"
        log = self.get_logger()
        cleared: list[str] = []

        # ① pending_confirm — cancel if PENDING (equiv _on_reset_context :2197).
        self._guarded(lambda: self._clear_pending_confirm_for_phase(canon_new, cleared),
                      log, "pending_confirm clear")

        with self._lock:
            # ② active_plan (:2207).
            self._guarded(lambda: (setattr(self._state, "active_plan", None),
                                   cleared.append("active_plan")),
                          log, "active_plan clear")
            # ③ gesture cooldown — skill cooldowns + gesture dedup + live tracker.
            self._guarded(lambda: self._clear_gesture_cooldown(cleared),
                          log, "gesture_cd clear")
            # ④ clear_object — object_remark dedup (:2203-2206).
            if clear_object:
                self._guarded(lambda: self._clear_object_dedup(cleared),
                              log, "object_remark clear")
            # ⑤ clear_greet — per-person greet cooldown keys (greet_known_person:*).
            if clear_greet:
                self._guarded(lambda: self._clear_greet_cooldown_keys(cleared),
                              log, "greet_cooldown clear")
            # NOTE: attention intentionally NOT cleared (:2193).

        # Transition trace (existing STATE_TRANSITION schema; never raises via _trace).
        self._guarded(lambda: self._trace(TraceEvent(
            decision_id=self._current_decision_id, node="brain_node",
            kind=TraceKind.STATE_TRANSITION, verdict=Verdict.ACCEPTED,
            gate="demo_phase",
            reason=f"transition:{old_phase}->{canon_new}",
            detail={"from_phase": str(old_phase), "to_phase": canon_new,
                    "cleared": cleared, "transition_type": "real_trigger"},
        )), log, "transition trace")

        # ISM shadow: phase switch is an operator reset (transition driver #4).
        self._ism_shadow_signal(IsmTrigger.OPERATOR, {"op": "reset"})

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
