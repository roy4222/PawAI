"""Output schemas — wire format for /brain/chat_candidate and /brain/conversation_trace.

Schema mirrors legacy llm_bridge_node._emit_chat_candidate
(speech_processor/speech_processor/llm_bridge_node.py:1078-1098), with two
langgraph-specific additions:
  - engine="langgraph" instead of "legacy"
  - optional input_origin for per-message TTS routing (studio_text →
    Gemini TTS chain in tts_node; None → edge_tts default)
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import time


@dataclass
class ChatCandidatePayload:
    """Schema mirrored from llm_bridge_node._emit_chat_candidate."""
    session_id: str
    reply_text: str
    intent: str
    selected_skill: str | None
    confidence: float
    proposed_skill: str | None
    proposed_args: dict
    proposal_reason: str
    engine: str = "langgraph"
    source: str = "pawai_brain"
    input_origin: str | None = None  # studio_text → Gemini TTS; None → edge_tts default
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# TracePayload.status enum (extended in Phase A.6):
#   pipeline / LLM stages: ok | retry | fallback | error
#   skill_gate stage:      proposed | accepted | accepted_trace_only |
#                          blocked | rejected_not_allowed |
#                          needs_confirm    (← Phase A.6)
#                          demo_guide       (← Phase A.6)
#   verifier stage:        warn             (← 2026-05-11 N3, rule-only reply check)
@dataclass
class TracePayload:
    """Schema for /brain/conversation_trace entries.

    Mirrors spec §4.2 of conversation-engine-langgraph-design.md.
    """
    session_id: str
    stage: str       # input | safety_gate | world_state | capability | memory |
                     # llm_decision | json_validate | repair | verifier |
                     # skill_gate | output
                     # (verifier added 2026-05-11 N3)
    status: str      # ok | warn | retry | fallback | error
                     # | proposed | accepted | accepted_trace_only
                     # | blocked | rejected_not_allowed | hit
                     # (warn added 2026-05-11 N3 for verifier stage)
    detail: str
    engine: str = "langgraph"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)
