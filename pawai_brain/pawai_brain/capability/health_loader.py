"""Load frozen capability health snapshots for capability gate enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pawai_brain.capability.effective_status import CapabilityHealth


SKILL_TO_CAPABILITY: dict[str, str] = {
    "wave_hello": "gesture.wave",
    "sit_along": "nav.short_move",
    "stand": "nav.short_move",
    "wiggle": "nav.short_move",
    "stretch": "nav.short_move",
    "show_status": "content",
    "self_introduce": "content",
    "careful_remind": "content",
}


def _insufficient_data_health() -> CapabilityHealth:
    return CapabilityHealth(
        grade="insufficient_data",
        claim_level="untrusted",
        dependency_role="unknown",
        risk_role="blocked",
        brain_allowed=False,
    )


class FailClosedCapabilityHealth(dict[str, CapabilityHealth]):
    """Capability health mapping that fails closed for unknown capability ids."""

    def __missing__(self, capability_id: str) -> CapabilityHealth:
        health = _insufficient_data_health()
        self[capability_id] = health
        return health

    def get(self, capability_id: str, default: CapabilityHealth | None = None) -> CapabilityHealth:
        del default
        return self[capability_id]


def skill_capability(skill: str) -> str | None:
    """Return the capability id associated with a skill, if one is known."""
    return SKILL_TO_CAPABILITY.get(skill)


def _fail_closed() -> FailClosedCapabilityHealth:
    return FailClosedCapabilityHealth()


def _build_health(raw: dict[str, Any]) -> CapabilityHealth:
    return CapabilityHealth(
        grade=str(raw.get("grade", "insufficient_data")),
        claim_level=str(raw.get("claim_level", "untrusted")),
        dependency_role=str(raw.get("dependency_role", "unknown")),
        risk_role=str(raw.get("risk_role", "blocked")),
        brain_allowed=bool(raw.get("brain_allowed", False)),
    )


def load_capability_health(snapshot_path: str) -> dict[str, CapabilityHealth]:
    """Load a trusted baseline capability health snapshot.

    Any loader error returns a mapping that fails closed for every requested capability id.
    """
    if not snapshot_path:
        return _fail_closed()

    try:
        snapshot = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _fail_closed()

    if not isinstance(snapshot, dict) or snapshot.get("run_trusted") is not True:
        return _fail_closed()

    capabilities = snapshot.get("capabilities")
    if not isinstance(capabilities, dict):
        return _fail_closed()

    loaded: FailClosedCapabilityHealth = FailClosedCapabilityHealth()
    for capability_id, capability in capabilities.items():
        if isinstance(capability_id, str) and isinstance(capability, dict):
            loaded[capability_id] = _build_health(capability)

    return loaded
