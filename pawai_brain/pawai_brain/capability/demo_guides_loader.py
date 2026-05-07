"""Load DemoGuide pseudo-skills from yaml."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_VALID_DEMO_GUIDE_BASELINES = frozenset({"explain_only", "studio_only", "disabled"})
_VALID_DEMO_VALUES = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class DemoGuide:
    name: str
    display_name: str
    baseline_status: str
    demo_value: str
    intro: str
    related_skills: list = field(default_factory=list)
    kind: str = "demo_guide"

    @classmethod
    def from_yaml_entry(cls, name: str, entry: dict) -> "DemoGuide":
        baseline = entry.get("baseline_status", "")
        if baseline not in _VALID_DEMO_GUIDE_BASELINES:
            raise ValueError(
                f"DemoGuide {name!r} baseline_status={baseline!r} invalid; "
                f"allowed: {sorted(_VALID_DEMO_GUIDE_BASELINES)}"
            )
        demo_value = entry.get("demo_value", "low")
        if demo_value not in _VALID_DEMO_VALUES:
            raise ValueError(
                f"DemoGuide {name!r} demo_value={demo_value!r} invalid; "
                f"allowed: {sorted(_VALID_DEMO_VALUES)}"
            )
        return cls(
            name=name,
            display_name=str(entry.get("display_name", name)),
            baseline_status=baseline,
            demo_value=demo_value,
            intro=str(entry.get("intro", "")),
            related_skills=list(entry.get("related_skills") or []),
        )


def load_demo_guides(path: Path) -> list:
    """Load demo guides from yaml. Returns [] on file missing / parse error."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("demo_guides yaml not loaded (%s): %s", path, exc)
        return []
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        logger.warning("demo_guides yaml parse failed (%s): %s", path, exc)
        return []
    if not isinstance(data, dict):
        logger.warning("demo_guides yaml root must be a mapping (%s)", path)
        return []
    guides = []
    for name, entry in data.items():
        if not isinstance(entry, dict):
            logger.warning("demo_guides skipping non-dict entry %s", name)
            continue
        try:
            guides.append(DemoGuide.from_yaml_entry(str(name), entry))
        except ValueError as exc:
            logger.warning("demo_guides skipping invalid entry %s: %s", name, exc)
    return guides


def load_demo_policy(path: Path) -> dict:
    """Load demo_policy yaml. Returns sensible defaults on failure."""
    defaults = {"limits": [], "max_motion_per_turn": 1}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return defaults
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return defaults
    if not isinstance(data, dict):
        return defaults
    return {
        "limits": list(data.get("limits") or []),
        "max_motion_per_turn": int(data.get("max_motion_per_turn") or 1),
    }
