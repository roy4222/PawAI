"""response_repair — Phase 1 first-pass + N3-C reply verifier rules.

Plan §3 row 8: only flip repair_failed=True when downstream needs to fall
back. We DON'T re-call the LLM yet (deferred to Phase 2).

N3-C (2026-05-11): on top of pass-through, run light rule checks and emit
trace entries with stage='verifier', status='warn' when reply violates one
of three demo-host expectations. Never affects repair_failed; warnings are
purely observational so Roy can tune persona later (Osmani: every mistake
becomes a rule).
"""
from __future__ import annotations

from ..state import ConversationState


_MIN_REPLY_CHARS = 8
_FOLLOWUP_MARKERS = ("?", "？", "嗎", "要不要", "想看", "下一步", "好不好")


def _extract_reply_text(state: ConversationState) -> str:
    """Best-effort reply extraction — N3-C verifier reads from llm_json first
    (validator's source-of-truth) and falls back to top-level reply_text.
    """
    llm_json = state.get("llm_json") or {}
    if isinstance(llm_json, dict):
        candidate = llm_json.get("reply") or llm_json.get("reply_text")
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    fallback = state.get("reply_text") or ""
    return fallback if isinstance(fallback, str) else ""


def _collect_skill_names(state: ConversationState) -> list[str]:
    """Pull display-able skill / demo-guide names from capability_context.

    N3-C review fix: don't hardcode a Chinese skill table — read from
    state.capability_context.capabilities so the verifier stays in sync with
    SkillContract automatically. Fall back to empty list when capabilities
    haven't been built (e.g. fallback mode), in which case the
    'no_specific_skill' rule is silently skipped to avoid false positives.
    """
    names: list[str] = []
    cap = state.get("capability_context") or {}
    for entry in cap.get("capabilities") or []:
        if not isinstance(entry, dict):
            continue
        for key in ("display_name", "zh_name", "name"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    # Also surface candidate_next from demo_session — those are the labels
    # PawAI is being primed to suggest, so they count as 'specific skills'.
    session = cap.get("demo_session") or {}
    for label in session.get("candidate_next") or []:
        if isinstance(label, str) and label.strip():
            names.append(label.strip())
    # Deduplicate while preserving order.
    seen = set()
    out: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _check_content_rules(state: ConversationState) -> list[str]:
    """Return a list of warning reasons. Empty list = pass."""
    reply = _extract_reply_text(state).strip()
    if not reply:
        return []  # validator already covers empty replies — no double-warn.

    warnings: list[str] = []

    if len(reply) < _MIN_REPLY_CHARS:
        warnings.append("too_short")

    mode = state.get("mode") or "chat"
    if mode == "capability_question":
        skill_names = _collect_skill_names(state)
        if skill_names:
            if not any(name in reply for name in skill_names):
                warnings.append("no_specific_skill")
        # else: capabilities not built yet → skip rule (avoid false positive)

    cap = state.get("capability_context") or {}
    session = cap.get("demo_session") or {}
    if session.get("active") is True:
        if not any(marker in reply for marker in _FOLLOWUP_MARKERS):
            warnings.append("no_followup_invitation")

    return warnings


def response_repair(state: ConversationState) -> ConversationState:
    if state.get("validation_error"):
        state["repair_failed"] = True
        state.setdefault("trace", []).append(
            {
                "stage": "repair",
                "status": "fallback",
                "detail": state["validation_error"],
            }
        )
        return state

    state["repair_failed"] = False
    state.setdefault("trace", []).append(
        {"stage": "repair", "status": "ok", "detail": "pass_through"}
    )

    # N3-C: rule-only verifier — observe failures, never block.
    warnings = _check_content_rules(state)
    if warnings:
        state.setdefault("trace", []).append(
            {
                "stage": "verifier",
                "status": "warn",
                "detail": "; ".join(warnings),
            }
        )

    return state
