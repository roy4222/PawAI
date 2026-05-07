"""capability_builder — merge SkillContract + DemoGuide + world_state into LLM-facing context."""
from __future__ import annotations
from typing import Callable

from ..capability.effective_status import WorldFlags
from ..capability.registry import CapabilityRegistry
from ..state import ConversationState


_registry: CapabilityRegistry | None = None
_skill_result_provider: Callable[[], list[dict]] = lambda: []
_policy_provider: Callable[[], dict] = lambda: {"limits": [], "max_motion_per_turn": 1}


def configure(
    registry: CapabilityRegistry,
    skill_result_provider: Callable[[], list[dict]],
    policy_provider: Callable[[], dict],
) -> None:
    global _registry, _skill_result_provider, _policy_provider
    _registry = registry
    _skill_result_provider = skill_result_provider
    _policy_provider = policy_provider


def _world_flags_from_state(state: ConversationState) -> WorldFlags:
    ws = state.get("world_state") or {}
    return WorldFlags(
        tts_playing=bool(ws.get("tts_playing", False)),
        obstacle=bool(ws.get("obstacle", False)),
        nav_safe=bool(ws.get("nav_safe", True)),
    )


def capability_builder(state: ConversationState) -> ConversationState:
    if _registry is None:
        state.setdefault("trace", []).append(
            {"stage": "capability", "status": "error", "detail": "not_configured"}
        )
        state["capability_context"] = {"capabilities": [], "limits": [],
                                        "demo_session": _placeholder_session(),
                                        "recent_skill_results": []}
        return state

    world = _world_flags_from_state(state)
    recent = _skill_result_provider()
    entries = _registry.build_entries(world, recent)
    policy = _policy_provider()

    capability_context = {
        "capabilities": [e.to_llm_dict() for e in entries],
        "limits": list(policy.get("limits", [])),
        "demo_session": _placeholder_session(),
        "recent_skill_results": list(recent),
    }

    state["capability_context"] = capability_context
    state["recent_skill_results"] = list(recent)  # also surface at top level for convenience

    n_skill = sum(1 for e in entries if e.kind == "skill")
    n_guide = sum(1 for e in entries if e.kind == "demo_guide")
    state.setdefault("trace", []).append(
        {
            "stage": "capability",
            "status": "ok",
            "detail": f"{n_skill} skills + {n_guide} guides",
        }
    )
    return state


def _placeholder_session() -> dict:
    return {"active": False, "shown_skills": [], "candidate_next": []}
