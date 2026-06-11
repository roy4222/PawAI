"""LLM proposal policy parity tests (Plan C4)."""


def test_execute_map_keys_subset_of_allowlist():
    from pawai_contracts.llm_policy import LLM_PROPOSABLE_SKILLS, LLM_PROPOSAL_EXECUTE
    assert set(LLM_PROPOSAL_EXECUTE) == set(LLM_PROPOSABLE_SKILLS)


def test_every_proposable_skill_exists_in_registry():
    from pawai_contracts.llm_policy import LLM_PROPOSABLE_SKILLS
    from pawai_contracts.skill_contract import SKILL_REGISTRY
    missing = LLM_PROPOSABLE_SKILLS - set(SKILL_REGISTRY)
    assert not missing, missing


def test_modes_are_valid():
    from pawai_contracts.llm_policy import LLM_PROPOSAL_EXECUTE
    assert set(LLM_PROPOSAL_EXECUTE.values()) <= {"execute", "confirm", "trace_only"}
