#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""ROS2 wrapper around the LangGraph primary conversation engine.

Subscribes /event/speech_intent_recognized.
Runs the 11-node conversation graph (build_graph()).
Publishes /brain/chat_candidate (primary) and /brain/conversation_trace.

Wrapper-level failure boundary:
    graph.invoke() failure → emit error trace + RuleBrain fallback chat_candidate.
    Graph nodes themselves only handle expected errors (bad JSON, empty reply,
    network fail). Unexpected exceptions surface here.
"""
from __future__ import annotations
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool as BoolMsg
from std_msgs.msg import Empty
from std_msgs.msg import String

from .capability.demo_guides_loader import load_demo_guides, load_demo_policy
from .capability.registry import CapabilityRegistry
from .capability.skill_result_memory import SkillResultMemory
from .capability.world_snapshot import WorldStateSnapshot
from .graph import build_graph
from .llm_client import OpenRouterClient, OpenRouterConfig, resolve_openrouter_key
from .memory import ConversationMemory
from .nodes import capability_builder as capability_builder_node
from .nodes import llm_decision as llm_decision_node
from .nodes import memory_builder as memory_builder_node
from .nodes import world_state_builder as world_state_builder_node
from .rule_fallback import fallback_reply
from .schemas import ChatCandidatePayload, TracePayload


TERMINAL_STATUSES = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})

# QoS for /state/tts_playing must match the publisher (tts_node.py:998-999)
_TTS_PLAYING_QOS = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
)

# QoS for /state/pawai_brain (brain_node publishes TRANSIENT_LOCAL @ 2Hz)
_BRAIN_STATE_QOS = QoSProfile(
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
)


# Inline persona used when llm_persona_file is empty / unreadable.
# Mirrors llm_bridge_node SYSTEM_PROMPT spirit but for persona schema.
_INLINE_PERSONA = """\
你是 PawAI，一隻友善的機器狗助手。
只能輸出單一 JSON object: {"reply": "...", "skill": "...", "args": {}}
skill ∈ {chat_reply, say_canned, show_status, self_introduce, null}
reply 用繁體中文，自然像在跟朋友聊天。
"""


def _compact_capabilities(cap: dict) -> list:
    """Extract minimal capability fields for LLM prompt (avoids 5+ KB bloat)."""
    compact_caps = []
    for c in cap.get("capabilities", []):
        entry = {
            "name": c.get("name"),
            "kind": c.get("kind"),
            "display_name": c.get("display_name"),
            "effective_status": c.get("effective_status"),
            "can_execute": c.get("can_execute", False),
            "demo_value": c.get("demo_value", "low"),
        }
        if c.get("reason"):
            entry["reason"] = c["reason"]
        if c.get("requires_confirmation"):
            entry["requires_confirmation"] = True
        if c.get("kind") == "demo_guide":
            entry["intro"] = c.get("intro", "")
            if c.get("related_skills"):
                entry["related_skills"] = list(c.get("related_skills") or [])
        compact_caps.append(entry)
    return compact_caps


def _build_user_message(state) -> str:
    """Build the LLM user message — mode-aware capability injection (1D).

    Phase A.6 essence: the LLM cannot do "self-demonstration" unless it sees
    the capability list, recent skill results, and current limits each turn.
    Adapted from the legacy `env_context` reader to the new world_state shape
    (Phase A.6 dropped env_builder; world_state_builder now owns time/weather).

    OpenClaw-lite 1D: CAPABILITIES.md + capability_context only injected for
    capability_question / action_request modes. identity mode adds [mode_hint].
    chat mode (default): no capability injection — LLM not anchored to tool-menu.
    """
    text = (state.get("user_text") or "").strip()
    mode = state.get("mode") or "chat"
    source = state.get("source") or "speech"

    # 1E: source-based label
    label = "[語音]" if source == "speech" else "[文字]"
    parts = [f"{label} 使用者說：「{text}」"]

    ws = state.get("world_state") or {}
    if ws.get("period") or ws.get("time"):
        line = f"[環境] 台北 {ws.get('period', '')} {ws.get('time', '')}".rstrip()
        if ws.get("weather"):
            line += f"，外面 {ws['weather']}"
        parts.append(line)
    if ws.get("current_speaker") and ws["current_speaker"] != "unknown":
        parts.append(f"[眼前的人] {ws['current_speaker']}")

    # 1D: CAPABILITIES + capability_context — lazy inject only for relevant modes
    # Note: module-level _build_user_message has no _capabilities_md;
    # ConversationGraphNode._build_user_message overrides with instance access.
    cap = state.get("capability_context") or {}
    if mode in ("capability_question", "action_request") and cap:
        compact_caps = _compact_capabilities(cap)
        cap_payload = {
            "capabilities": compact_caps,
            "limits": list(cap.get("limits") or []),
            "recent_skill_results": list(cap.get("recent_skill_results") or []),
        }
        parts.append("[能力 runtime] " + json.dumps(cap_payload, ensure_ascii=False))
    elif cap and mode not in ("capability_question", "action_request"):
        # Legacy behaviour for tests that use module-level function directly:
        # always emit [能力] when cap present (backward compat for test_user_message_builder).
        compact_caps = _compact_capabilities(cap)
        cap_payload = {
            "capabilities": compact_caps,
            "limits": list(cap.get("limits") or []),
            "recent_skill_results": list(cap.get("recent_skill_results") or []),
        }
        parts.append("[能力] " + json.dumps(cap_payload, ensure_ascii=False))

    # mode hint — only for identity
    if mode == "identity":
        parts.append(
            "[mode_hint] 使用者問你是誰。請從性格、生活、剛剛發生的事切入，"
            "不要列功能清單，除非他追問。"
        )

    return "\n".join(parts)


class ConversationGraphNode(Node):
    def __init__(self) -> None:
        super().__init__("conversation_graph_node")

        self._declare_parameters()
        self._read_parameters()

        self._publish_chat = self.create_publisher(String, self.chat_candidate_topic, 10)
        self._publish_trace = self.create_publisher(String, self.trace_topic, 10)

        self.create_subscription(
            String, self.intent_event_topic, self._on_speech_event, 10
        )
        # Studio chat panel text → bypass ASR, go straight to LangGraph.
        # Marks input_origin="studio_text" so /tts gets envelope routing to
        # Gemini TTS (per 5/7 night plan polished-questing-starlight).
        self.create_subscription(
            String, "/brain/text_input", self._on_text_input, 10
        )

        self._memory = ConversationMemory(max_turns=self.chat_history_max_turns)
        self._client = OpenRouterClient(
            config=OpenRouterConfig(
                base_url=self.openrouter_base_url,
                gemini_model=self.openrouter_gemini_model,
                deepseek_model=self.openrouter_deepseek_model,
                request_timeout_s=self.openrouter_request_timeout_s,
                overall_budget_s=self.openrouter_overall_budget_s,
                temperature=self.llm_temperature,
                max_tokens=self.llm_max_tokens,
            ),
            api_key=resolve_openrouter_key(self.enable_openrouter, os.environ),
            logger=lambda m: self.get_logger().warning(m),
        )

        # 1A: _capabilities_md set by _load_persona (directory mode)
        self._capabilities_md: str = ""
        self._system_prompt = self._load_persona()

        # Wire module-level node hooks
        memory_builder_node.set_history_provider(self._memory.recent)
        llm_decision_node.configure(
            client=self._client,
            system_prompt=self._system_prompt,
            user_message_builder=self._build_user_message,
        )

        # Phase A.6 — capability layer
        self._world_snapshot = WorldStateSnapshot()
        self._skill_results = SkillResultMemory(maxlen=5)

        # Locate demo_guides.yaml & demo_policy.yaml from share/
        from ament_index_python.packages import get_package_share_directory
        try:
            share = Path(get_package_share_directory("pawai_brain"))
            guides_path = share / "config" / "demo_guides.yaml"
            policy_path = share / "config" / "demo_policy.yaml"
        except Exception:
            # Fallback to source path during dev
            here = Path(__file__).resolve().parent.parent
            guides_path = here / "config" / "demo_guides.yaml"
            policy_path = here / "config" / "demo_policy.yaml"

        guides = load_demo_guides(guides_path)
        policy = load_demo_policy(policy_path)

        from interaction_executive.skill_contract import SKILL_REGISTRY
        try:
            registry = CapabilityRegistry(skills=SKILL_REGISTRY, guides=guides)
        except ValueError as exc:
            self.get_logger().error(f"CapabilityRegistry build failed: {exc}")
            registry = CapabilityRegistry(skills={}, guides=guides)

        # Wire module-level node hooks
        world_state_builder_node.set_world_provider(lambda: self._world_snapshot)
        world_state_builder_node.set_speaker_provider(lambda: self._recent_face_identity)
        capability_builder_node.configure(
            registry=registry,
            skill_result_provider=self._skill_results.recent,
            policy_provider=lambda: policy,
        )

        # ROS subscribers for world state
        # /state/tts_playing — std_msgs/Bool + TRANSIENT_LOCAL (matches tts_node.py:998-999)
        self.create_subscription(
            BoolMsg, "/state/tts_playing", self._on_tts_playing, _TTS_PLAYING_QOS
        )
        self.create_subscription(
            String, "/state/reactive_stop/status", self._on_reactive_stop, 10
        )
        self.create_subscription(
            String, "/state/nav/safety", self._on_nav_safety, 10
        )
        self.create_subscription(
            String, "/state/pawai_brain", self._on_pawai_brain_state, _BRAIN_STATE_QOS
        )
        self.create_subscription(
            String, "/brain/skill_result", self._on_skill_result, 10
        )

        # P1-2: context reset — clear ConversationMemory on page refresh / new-conversation
        self.create_subscription(
            Empty, "/brain/reset_context", self._on_reset_context, 10
        )

        # 1H: face state subscription for current_speaker context injection
        # Subscribes /state/perception/face (8 Hz JSON from face_identity_node).
        # Maintains _recent_face_identity; world_state_builder writes current_speaker.
        self._recent_face_identity: tuple[str, float] = ("unknown", 0.0)
        # P1-2 fix: after /brain/reset_context, suppress face→speaker writeback
        # for a short window so a fresh "新對話" really feels like a new session
        # even though Roy is still in front of the camera.
        self._speaker_suppress_until: float = 0.0
        self.create_subscription(
            String, "/state/perception/face", self._on_face_state, 10
        )

        self._graph = build_graph()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="convgraph")
        self._lock = threading.Lock()
        self._seen_sessions: set[str] = set()
        self._seen_lock = threading.Lock()

        self.get_logger().info(
            f"conversation_graph_node ready (engine={self.engine_label}, "
            f"openrouter={'on' if self._client.active else 'off'}, "
            f"persona={'file' if self.llm_persona_file else 'inline'})"
        )

    # ── Parameter declaration / reading ─────────────────────────────────

    def _declare_parameters(self) -> None:
        self.declare_parameter("intent_event_topic", "/event/speech_intent_recognized")
        self.declare_parameter("chat_candidate_topic", "/brain/chat_candidate")
        self.declare_parameter("trace_topic", "/brain/conversation_trace")
        self.declare_parameter("engine_label", "langgraph")

        # Same names + defaults as llm_bridge_node so demo script env overrides
        # apply uniformly.
        self.declare_parameter("enable_openrouter", True)
        self.declare_parameter(
            "openrouter_base_url",
            "https://openrouter.ai/api/v1/chat/completions",
        )
        # 5/12 round-2 A/B winner: gpt-5.4-mini live primary; gemini fallback.
        # Param names are legacy slot names — see llm_client.OpenRouterConfig.
        self.declare_parameter("openrouter_gemini_model", "openai/gpt-5.4-mini")
        self.declare_parameter("openrouter_deepseek_model", "google/gemini-3-flash-preview")
        self.declare_parameter("openrouter_request_timeout_s", 4.0)
        self.declare_parameter("openrouter_overall_budget_s", 5.0)
        self.declare_parameter("llm_persona_file", "")
        self.declare_parameter("llm_temperature", 0.8)  # 5/9 review: was 0.2 (greedy → templated); 0.8 = OpenClaw chat sweet spot. Launch arg can still override.
        self.declare_parameter("llm_max_tokens", 500)
        self.declare_parameter("chat_history_max_turns", 5)

    def _read_parameters(self) -> None:
        gp = self.get_parameter

        def s(n: str) -> str:
            return str(gp(n).get_parameter_value().string_value)

        def f(n: str) -> float:
            return float(gp(n).get_parameter_value().double_value)

        def i(n: str) -> int:
            return int(gp(n).get_parameter_value().integer_value)

        def b(n: str) -> bool:
            return bool(gp(n).get_parameter_value().bool_value)

        self.intent_event_topic = s("intent_event_topic")
        self.chat_candidate_topic = s("chat_candidate_topic")
        self.trace_topic = s("trace_topic")
        self.engine_label = s("engine_label") or "langgraph"

        self.enable_openrouter = b("enable_openrouter")
        self.openrouter_base_url = s("openrouter_base_url")
        self.openrouter_gemini_model = s("openrouter_gemini_model")
        self.openrouter_deepseek_model = s("openrouter_deepseek_model")
        self.openrouter_request_timeout_s = f("openrouter_request_timeout_s")
        self.openrouter_overall_budget_s = f("openrouter_overall_budget_s")
        self.llm_persona_file = s("llm_persona_file")
        self.llm_temperature = f("llm_temperature")
        self.llm_max_tokens = i("llm_max_tokens")
        self.chat_history_max_turns = max(1, i("chat_history_max_turns"))

    # ── Persona loader (file/dir dual mode — Roy review #1/#2) ─────────

    def _load_persona(self) -> str:
        """Load persona from file (legacy) or directory (5-file OpenClaw-lite).

        File mode (backward compat): single .txt → whole file as system prompt.
        Directory mode: 5 required files; base concat 4; CAPABILITIES.md cached
        in self._capabilities_md for lazy injection by _build_user_message (1D).
        """
        path_str = (self.llm_persona_file or "").strip()
        if not path_str:
            return _INLINE_PERSONA
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path

        if path.is_file():
            # Legacy mode: single persona.txt (backward compat)
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                self.get_logger().warning(
                    f"[persona] file load failed ({path}): {exc} — using inline persona"
                )
                return _INLINE_PERSONA
            if not content.strip():
                self.get_logger().warning(
                    f"[persona] file empty ({path}) — using inline persona"
                )
                return _INLINE_PERSONA
            self._capabilities_md = ""  # legacy mode: no separate cache
            self.get_logger().info(f"[persona] loaded file {path} ({len(content)} bytes)")
            return content

        if path.is_dir():
            # New mode: directory; 6 files required, base concat 5
            # MISSION.md added 2026-05-10 (Spec 1 Brain Minimum) — 專案定位 + 雙支柱 + 自主尋物敘事
            REQUIRED = ["IDENTITY.md", "MISSION.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md", "CAPABILITIES.md"]
            BASE_ORDER = ["IDENTITY.md", "MISSION.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md"]
            contents = {}
            for fname in REQUIRED:
                f = path / fname
                if not f.is_file():
                    self.get_logger().error(f"[persona] missing required {fname} in {path}")
                    raise FileNotFoundError(f)
                contents[fname] = f.read_text(encoding="utf-8")

            base = "\n\n".join(contents[f] for f in BASE_ORDER)
            self._capabilities_md = contents["CAPABILITIES.md"]
            self.get_logger().info(
                f"[persona] loaded directory {path}, "
                f"6 files verified, base 5 files concat ({len(base)} chars), "
                f"CAPABILITIES.md cached separately ({len(self._capabilities_md)} chars), "
                f"base_sha={hashlib.sha256(base.encode()).hexdigest()[:12]}"
            )
            return base

        self.get_logger().error(f"[persona] path not file or dir: {path}")
        raise FileNotFoundError(path)

    # ── Instance-level _build_user_message (1D: lazy capability inject) ─

    def _build_user_message(self, state) -> str:
        """Instance method: injects self._capabilities_md for capability modes.

        Wraps the module-level _build_user_message but overrides the
        capability injection so CAPABILITIES.md is included only for
        capability_question / action_request modes.
        """
        text = (state.get("user_text") or "").strip()
        mode = state.get("mode") or "chat"
        source = state.get("source") or "speech"

        label = "[語音]" if source == "speech" else "[文字]"
        parts = [f"{label} 使用者說：「{text}」"]

        ws = state.get("world_state") or {}
        if ws.get("period") or ws.get("time"):
            line = f"[環境] 台北 {ws.get('period', '')} {ws.get('time', '')}".rstrip()
            if ws.get("weather"):
                line += f"，外面 {ws['weather']}"
            parts.append(line)
        if ws.get("current_speaker") and ws["current_speaker"] != "unknown":
            parts.append(f"[眼前的人] {ws['current_speaker']}")

        # 1D: lazy inject CAPABILITIES.md + capability_context ONLY for explicit
        # capability/action modes. chat / identity / safety modes do NOT see
        # the skill JSON in their prompt — that's the issue 2 root cause: every
        # turn LLM seeing 17-skill JSON pulls it into "tool listing" persona,
        # making "介紹一下" come back as a feature catalog.
        #
        # capability_context still flows through graph state (skill_policy_gate
        # v2 reads from state.capability_context, not from rendered prompt).
        cap = state.get("capability_context") or {}
        if mode in ("capability_question", "action_request"):
            if self._capabilities_md:
                parts.append("[能力描述]\n" + self._capabilities_md)
            if cap:
                compact_caps = _compact_capabilities(cap)
                cap_payload = {
                    "capabilities": compact_caps,
                    "limits": list(cap.get("limits") or []),
                    "recent_skill_results": list(cap.get("recent_skill_results") or []),
                }
                parts.append("[能力 runtime] " + json.dumps(cap_payload, ensure_ascii=False))
        # else: chat / identity / safety — DELIBERATELY no capability inject.

        if mode == "identity":
            parts.append(
                "[mode_hint] 使用者問你是誰。請從性格、生活、剛剛發生的事切入，"
                "不要列功能清單，除非他追問。"
            )

        return "\n".join(parts)

    # ── Speech event handler ────────────────────────────────────────────

    def _on_speech_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        session_id = str(payload.get("session_id", "")).strip()
        with self._seen_lock:
            if session_id and session_id in self._seen_sessions:
                return
            if session_id:
                self._seen_sessions.add(session_id)
                if len(self._seen_sessions) > 200:
                    self._seen_sessions = set(list(self._seen_sessions)[-100:])

        if str(payload.get("intent", "")).strip() == "hallucination":
            return

        text = str(payload.get("text", "")).strip()
        confidence = float(payload.get("confidence", 0.0))
        if not text:
            return

        self._executor.submit(self._process_one, text, confidence, session_id, None)

    # ── Studio chat panel text-input handler ────────────────────────────

    def _on_text_input(self, msg: String) -> None:
        """Studio chat → LangGraph (no ASR, no buffering).

        studio_gateway POST /api/text_input → /brain/text_input with payload
        {"text", "request_id", "source", "created_at"}. We mark
        input_origin="studio_text" so chat_candidate carries it through to
        the IE-node SAY step, which wraps /tts in a JSON envelope; tts_node
        then routes to the Gemini fallback chain.
        """
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        if not isinstance(payload, dict):
            return
        text = str(payload.get("text") or "").strip()
        if not text:
            return
        # request_id is always present from gateway (studio_gateway.py:500).
        # Match brain_node._on_text_input fallback so session_id is consistent
        # across the buffer pop in _on_chat_candidate.
        session_id = str(
            payload.get("request_id") or f"studio-{time.time_ns()}"
        )
        input_origin = (
            str(payload.get("source") or "studio_text").strip() or "studio_text"
        )
        # Same single-flight worker as speech path; confidence=1.0 (no ASR error).
        self._executor.submit(self._process_one, text, 1.0, session_id, input_origin)

    # ── Worker — invoke graph + publish ─────────────────────────────────

    def _process_one(
        self,
        text: str,
        confidence: float,
        session_id: str,
        input_origin: str | None = None,
    ) -> None:
        # Single-flight guard mirrors llm_bridge_node._llm_lock usage.
        if not self._lock.acquire(blocking=False):
            self.get_logger().warning("graph invocation already in progress — dropping turn")
            return

        try:
            initial_state = {
                "session_id": session_id,
                "source": "text" if input_origin else "speech",
                "user_text": text,
                "input_origin": input_origin,
                "trace": [],
            }
            try:
                final = self._graph.invoke(initial_state)
            except Exception as exc:  # noqa: BLE001 — wrapper-level boundary
                self.get_logger().error(f"graph fatal: {exc}")
                self._publish_error_trace(session_id, str(exc))
                self._publish_fallback_chat_candidate(
                    text, session_id, confidence, input_origin
                )
                return

            self._publish_chat_candidate_from_state(
                final, session_id, confidence, input_origin
            )
            self._publish_traces(session_id, final.get("trace", []))

            # Memory: only remember real chat turns (mirror llm_bridge logic)
            reply = str(final.get("reply_text", "")).strip()
            intent = str(final.get("intent", "")).strip()
            if reply and intent in ("greet", "chat", "status"):
                self._memory.add(text, reply)
        finally:
            self._lock.release()

    # ── Publish helpers ─────────────────────────────────────────────────

    def _publish_chat_candidate_from_state(
        self,
        state: dict,
        session_id: str,
        confidence: float,
        input_origin: str | None = None,
    ) -> None:
        payload = ChatCandidatePayload(
            session_id=session_id,
            reply_text=str(state.get("reply_text", "")),
            intent=str(state.get("intent", "chat")),
            selected_skill=state.get("selected_skill"),
            confidence=float(state.get("confidence", confidence)),
            proposed_skill=state.get("proposed_skill"),
            proposed_args=state.get("proposed_args") or {},
            proposal_reason=str(state.get("proposal_reason", "")),
            engine=self.engine_label,
            input_origin=input_origin or state.get("input_origin"),
        )
        msg = String()
        msg.data = json.dumps(payload.to_dict(), ensure_ascii=False)
        self._publish_chat.publish(msg)
        self.get_logger().info(
            f"Published /brain/chat_candidate: session={session_id} "
            f"reply={payload.reply_text!r} proposed={payload.proposed_skill} "
            f"input_origin={payload.input_origin}"
        )

    def _publish_fallback_chat_candidate(
        self,
        user_text: str,
        session_id: str,
        confidence: float,
        input_origin: str | None = None,
    ) -> None:
        reply, intent, skill = fallback_reply(user_text)
        payload = ChatCandidatePayload(
            session_id=session_id,
            reply_text=reply,
            intent=intent,
            selected_skill=skill,
            confidence=0.5,
            proposed_skill=None,
            proposed_args={},
            proposal_reason="wrapper_fallback",
            engine=self.engine_label,
            input_origin=input_origin,
        )
        msg = String()
        msg.data = json.dumps(payload.to_dict(), ensure_ascii=False)
        self._publish_chat.publish(msg)
        del confidence  # explicitly unused — fallback uses fixed 0.5

    def _publish_traces(self, session_id: str, traces: list) -> None:
        for entry in traces:
            payload = TracePayload(
                session_id=session_id,
                stage=str(entry.get("stage", "")),
                status=str(entry.get("status", "ok")),
                detail=str(entry.get("detail", "")),
                engine=self.engine_label,
            )
            msg = String()
            msg.data = json.dumps(payload.to_dict(), ensure_ascii=False)
            self._publish_trace.publish(msg)

    # ── World-state / skill-result callbacks ────────────────────────────

    def _on_tts_playing(self, msg: BoolMsg) -> None:
        """std_msgs/Bool — direct flag, no JSON parse."""
        self._world_snapshot.apply_tts_playing(bool(msg.data))

    def _on_reactive_stop(self, msg: String) -> None:
        self._world_snapshot.apply_reactive_stop_status_json(msg.data)

    def _on_nav_safety(self, msg: String) -> None:
        self._world_snapshot.apply_nav_safety_json(msg.data)

    def _on_pawai_brain_state(self, msg: String) -> None:
        self._world_snapshot.apply_pawai_brain_state_json(msg.data)

    def _on_skill_result(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return
        status = str(payload.get("status", ""))
        if status not in TERMINAL_STATUSES:
            return
        name = str(payload.get("selected_skill") or "").strip()
        if not name:
            return
        self._skill_results.add({
            "name": name,
            "status": status,
            "detail": str(payload.get("detail", ""))[:80],
            "ts": time.time(),
        })

    def _on_reset_context(self, msg: Empty) -> None:  # noqa: ARG002
        """P1-2: Clear ConversationMemory + seen_sessions on browser reset.

        5/9 review: was only clearing _memory; spec required _seen_sessions
        too. Without clearing, the same session_id (e.g. studio request
        replay) would be silently dropped post-reset because it remained
        in _seen_sessions. Take _seen_lock to prevent race with
        _on_speech_event / _on_text_input writers that mutate _seen_sessions.
        """
        self._memory.clear()
        with self._seen_lock:
            self._seen_sessions.clear()
        self._recent_face_identity = ("unknown", 0.0)
        self._speaker_suppress_until = time.time() + 5.0
        self.get_logger().info(
            "/brain/reset_context: memory + seen_sessions + face_identity cleared "
            "(speaker suppressed for 5s)"
        )

    def _on_face_state(self, msg: String) -> None:
        """1H: /state/perception/face (8 Hz) — track most stable known person.

        Payload: {"stamp": float, "face_count": int, "tracks": [...]}
        Track: {"stable_name": str, "mode": "stable"|"hold", ...}

        Pick first track with stable_name != 'unknown'; update _recent_face_identity.
        """
        try:
            payload = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError):
            return
        if time.time() < self._speaker_suppress_until:
            return  # P1-2 fix: post-reset suppress window
        tracks = payload.get("tracks") or []
        for track in tracks:
            name = str(track.get("stable_name") or "unknown")
            if name and name != "unknown":
                self._recent_face_identity = (name, time.time())
                return

    def _publish_error_trace(self, session_id: str, detail: str) -> None:
        payload = TracePayload(
            session_id=session_id,
            stage="output",
            status="error",
            detail=detail[:200],
            engine=self.engine_label,
        )
        msg = String()
        msg.data = json.dumps(payload.to_dict(), ensure_ascii=False)
        self._publish_trace.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = ConversationGraphNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
