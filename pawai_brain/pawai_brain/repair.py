"""Response repair — first-pass conservative implementation.

Plan §3 row 8: response_repair runs at most 1 retry; failure flips
state.repair_failed = True so downstream can degrade gracefully.

Phase 1 first-pass (this file): we DON'T re-call the LLM. The function
inspects the raw response; if validator already produced a usable dict
we pass it through untouched. If not, we surface the failure for
output_builder to fall back to RuleBrain.

Phase 2 will add an actual retry-prompt to OpenRouterClient.
"""
from __future__ import annotations
from .validator import parse_persona_json


def try_repair(raw: str | None, *, attempts: int = 1) -> dict | None:
    """Best-effort repair of a persona JSON response.

    Phase 1 first-pass behaviour:
      - raw None → None
      - strict parse succeeds → return parsed dict
      - strict parse fails → return None (caller flips repair_failed)

    `attempts` is currently unused; reserved for Phase 2 retry-prompt logic.
    """
    del attempts  # Phase 2 will use this
    if raw is None:
        return None
    return parse_persona_json(raw)
