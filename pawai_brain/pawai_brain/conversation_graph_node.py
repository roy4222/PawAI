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
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .graph import build_graph
from .llm_client import OpenRouterClient, OpenRouterConfig, resolve_openrouter_key
from .memory import ConversationMemory
from .nodes import llm_decision as llm_decision_node
from .nodes import memory_builder as memory_builder_node
from .rule_fallback import fallback_reply
from .schemas import ChatCandidatePayload, TracePayload


# Inline persona used when llm_persona_file is empty / unreadable.
# Mirrors llm_bridge_node SYSTEM_PROMPT spirit but for persona schema.
_INLINE_PERSONA = """\
你是 PawAI，一隻友善的機器狗助手。
只能輸出單一 JSON object: {"reply": "...", "skill": "...", "args": {}}
skill ∈ {chat_reply, say_canned, show_status, self_introduce, null}
reply 用繁體中文，自然像在跟朋友聊天。
"""


def _build_user_message(state) -> str:
    text = (state.get("user_text") or "").strip()
    env = state.get("env_context") or {}
    parts = [f"[語音輸入] 使用者說：「{text}」"]
    if env:
        line = f"[環境] 台北 {env.get('period', '')} {env.get('time', '')}"
        if env.get("weather"):
            line += f"，外面 {env['weather']}"
        parts.append(line)
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

        self._system_prompt = self._load_persona()

        # Wire module-level node hooks
        memory_builder_node.set_history_provider(self._memory.recent)
        llm_decision_node.configure(
            client=self._client,
            system_prompt=self._system_prompt,
            user_message_builder=_build_user_message,
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
        self.declare_parameter("openrouter_gemini_model", "google/gemini-3-flash-preview")
        self.declare_parameter("openrouter_deepseek_model", "deepseek/deepseek-v4-flash")
        self.declare_parameter("openrouter_request_timeout_s", 4.0)
        self.declare_parameter("openrouter_overall_budget_s", 5.0)
        self.declare_parameter("llm_persona_file", "")
        self.declare_parameter("llm_temperature", 0.2)
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

    # ── Persona loader (mirrors llm_bridge_node._load_system_prompt) ────

    def _load_persona(self) -> str:
        path_str = (self.llm_persona_file or "").strip()
        if not path_str:
            return _INLINE_PERSONA
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.get_logger().warning(
                f"llm_persona_file load failed ({path}): {exc} — using inline persona"
            )
            return _INLINE_PERSONA
        if not content.strip():
            self.get_logger().warning(
                f"llm_persona_file empty ({path}) — using inline persona"
            )
            return _INLINE_PERSONA
        self.get_logger().info(f"Loaded persona from {path} ({len(content)} bytes)")
        return content

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

        self._executor.submit(self._process_one, text, confidence, session_id)

    # ── Worker — invoke graph + publish ─────────────────────────────────

    def _process_one(self, text: str, confidence: float, session_id: str) -> None:
        # Single-flight guard mirrors llm_bridge_node._llm_lock usage.
        if not self._lock.acquire(blocking=False):
            self.get_logger().warning("graph invocation already in progress — dropping turn")
            return

        try:
            initial_state = {
                "session_id": session_id,
                "source": "speech",
                "user_text": text,
                "trace": [],
            }
            try:
                final = self._graph.invoke(initial_state)
            except Exception as exc:  # noqa: BLE001 — wrapper-level boundary
                self.get_logger().error(f"graph fatal: {exc}")
                self._publish_error_trace(session_id, str(exc))
                self._publish_fallback_chat_candidate(text, session_id, confidence)
                return

            self._publish_chat_candidate_from_state(final, session_id, confidence)
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
        self, state: dict, session_id: str, confidence: float
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
        )
        msg = String()
        msg.data = json.dumps(payload.to_dict(), ensure_ascii=False)
        self._publish_chat.publish(msg)
        self.get_logger().info(
            f"Published /brain/chat_candidate: session={session_id} "
            f"reply={payload.reply_text!r} proposed={payload.proposed_skill}"
        )

    def _publish_fallback_chat_candidate(
        self, user_text: str, session_id: str, confidence: float
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
