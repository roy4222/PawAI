"""Audit script: find every WebRtcReq publisher in the workspace.

Whitelist:
- interaction_executive/interaction_executive/interaction_executive_node.py
  (sole sport /webrtc_req publisher)
- speech_processor/speech_processor/tts_node.py
  (Megaphone audio publisher; api_ids 4001-4004 enforced by separate test)

Any other file publishing WebRtcReq is a violation of the Brain MVS
single-outlet contract.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

WHITELIST = {
    "interaction_executive/interaction_executive/interaction_executive_node.py",
    "speech_processor/speech_processor/tts_node.py",
    # Phase 0/1 transitional: llm_bridge keeps a publisher object for legacy mode
    # but it's gated by `output_mode == "legacy"` in __init__. Remove this entry
    # when the legacy code path is finally deleted (post-MVS).
    "speech_processor/speech_processor/llm_bridge_node.py",
    # Phase 0/1 transitional: event_action_bridge is gated by launch arg
    # `enable_event_action_bridge` (default true). Brain MVS launches set it
    # false; remove this entry once Brain replaces the bridge fully.
    "vision_perception/vision_perception/event_action_bridge.py",
    # Ad-hoc Megaphone audio A/B test script; not part of runtime stack.
    "scripts/ab_test_audio.py",
}
ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {"build", "install", "log", ".git", "node_modules"}


def find_violations(root: Path) -> list[tuple[Path, int]]:
    violations: list[tuple[Path, int]] = []
    for py in root.rglob("*.py"):
        rel = py.relative_to(root).as_posix()
        if any(part in EXCLUDED_DIRS for part in py.parts):
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # match `self.create_publisher(...)` or `node.create_publisher(...)`
            if not (isinstance(func, ast.Attribute) and func.attr == "create_publisher"):
                continue
            # first positional arg should be the message type
            if not node.args:
                continue
            first = node.args[0]
            type_name = first.id if isinstance(first, ast.Name) else None
            if type_name == "WebRtcReq":
                if rel not in WHITELIST:
                    violations.append((py, node.lineno))
    return violations


def main() -> int:
    violations = find_violations(ROOT)
    if not violations:
        print("OK · only whitelisted files publish WebRtcReq")
        return 0
    print("VIOLATIONS · WebRtcReq publishers outside whitelist:")
    for path, line in violations:
        print(f"  {path.relative_to(ROOT)}:{line}")
    print("\nWhitelist:")
    for w in sorted(WHITELIST):
        print(f"  {w}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
