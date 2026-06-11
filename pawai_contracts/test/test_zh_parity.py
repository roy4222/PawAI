"""zh tables single-source parity (Plan C3). Guards: contracts == producer
canon (object_perception COLOR_ZH) == Studio TS copy. Replaces the
'three copies kept in sync by comment' regime (old brain_node.py:37-40)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_color_zh_matches_object_perception_canon():
    from pawai_contracts.zh_tables import OBJECT_COLOR_ZH
    sys.path.insert(0, str(ROOT / "object_perception"))
    from object_perception.coco_classes import COLOR_ZH
    assert OBJECT_COLOR_ZH == COLOR_ZH


def test_studio_ts_copy_matches_contracts():
    from pawai_contracts.zh_tables import OBJECT_CLASS_ZH, OBJECT_COLOR_ZH
    ts = (ROOT / "pawai-studio/frontend/components/object/object-config.ts").read_text("utf-8")
    # NOTE: spec regex r'["\']?([a-z_]+)["\']?\s*:\s*["\']([^"\']+)["\']' causes a
    # false-positive collision: `dog` is extracted from inside `hot_dog: "熱狗"` and
    # overwrites the correct `dog: "狗狗"` entry.  Word-boundary anchoring fixes this
    # without changing the intent (verify TS translations match contracts).
    pairs = dict(re.findall(r'(?<![a-z_])([a-z_]+)(?![a-z_])\s*:\s*["\']([^"\']+)["\']', ts))
    for key, zh in {**OBJECT_CLASS_ZH, **OBJECT_COLOR_ZH}.items():
        # TS may have extra UI entries; contract keys must match.
        if key in pairs:
            assert pairs[key] == zh, f"{key}: contracts={zh} ts={pairs[key]}"
    missing = [k for k in OBJECT_COLOR_ZH if k not in pairs]
    assert not missing, f"Studio object-config.ts missing colour keys: {missing}"
