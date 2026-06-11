"""Compat shim (Plan C2, 2026-06-10): the real module moved to
pawai_contracts.skill_contract. Every existing import — including the 606-test
regression net — keeps working unchanged. New code should import
pawai_contracts.skill_contract directly. Remove this shim only after a
dedicated migration PR rewrites all imports (post-ISM)."""
from pawai_contracts.skill_contract import *          # noqa: F401,F403
from pawai_contracts.skill_contract import (          # noqa: F401  (explicit re-exports)
    SKILL_REGISTRY,
    MOTION_NAME_MAP,
    BANNED_API_IDS,
    build_plan,
)
