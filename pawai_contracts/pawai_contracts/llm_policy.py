"""LLM proposal policy — single source (Plan C4, 2026-06-10).

Previously: canonical set in pawai_brain/nodes/skill_policy_gate.py + mirror in
brain_node guarded only by an AST parity test; the execute-mode map had NO
guard at all. Values are 1:1 from brain_node.py @ post-demo-refactor-baseline.
"""

# Phase 0.5 LLM proposal gate (spec 2026-05-06 §6)
# Phase A.6 (5/8 expansion): 8 skills + new "confirm" mode
LLM_PROPOSABLE_SKILLS: frozenset[str] = frozenset({
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
LLM_PROPOSAL_EXECUTE: dict[str, str] = {
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
