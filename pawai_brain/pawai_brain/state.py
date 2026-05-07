"""ConversationState — TypedDict carried through the LangGraph nodes.

Phase 1 primary cutover: only fields the 11 nodes actually need.
Future phases (perception context, multi-source) will extend this.
"""
from __future__ import annotations
from typing import Any, TypedDict


class ConversationState(TypedDict, total=False):
    # ── Input ─────────────────────────────────────────────────────────
    session_id: str
    source: str  # "speech" today; reserved: "studio_text"
    user_text: str

    # ── Context (filled by builders) ──────────────────────────────────
    perception_context: dict  # context_builder stub today
    env_context: dict         # env_builder: {"period", "time", "weather"}
    history: list             # memory_builder: [{"role","content"}, ...]

    # ── LLM I/O ───────────────────────────────────────────────────────
    llm_raw: str | None       # raw content from OpenRouter
    llm_json: dict | None     # parsed persona JSON

    # ── Validation / repair flags ─────────────────────────────────────
    validation_error: str
    repair_failed: bool

    # ── Safety short-circuit ──────────────────────────────────────────
    safety_hit: bool          # True → output bypasses LLM, emits stop_move

    # ── Output (built by skill_policy_gate + output_builder) ─────────
    reply_text: str
    selected_skill: str | None       # legacy diagnostic (4 P0 skills)
    intent: str
    reasoning: str
    confidence: float
    proposed_skill: str | None
    proposed_args: dict
    proposal_reason: str

    # ── Trace accumulation (each node may append) ─────────────────────
    trace: list[dict[str, Any]]
