"""CLI wrapper for building a baseline scoreboard snapshot from JSONL results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .grader import Criterion
from .scoreboard import aggregate, load_results, write_snapshot
from .scoreboard_schema import current_run_meta

DEFAULT_OUT_PATH = "artifacts/baseline/baseline_snapshot.json"

DEFAULT_CRITERIA: dict[str, list[Criterion]] = {
    "face.recognition": [
        Criterion("registered_recall", 0.80, 0.60, higher_is_better=True),
        Criterion("unknown_false_accept_rate", 0.03, 0.10, higher_is_better=False),
        Criterion("wrong_person_count", 0, 0, higher_is_better=False),
    ],
    "voice.command": [
        Criterion("success_rate", 0.80, 0.70, higher_is_better=True),
    ],
    "voice.stop": [
        # 規格 §2b：voice.stop FN 硬性=0 —— 任一漏聽即 fail，故 pass 需 success_rate==1.0。
        Criterion("success_rate", 1.0, 1.0, higher_is_better=True),
    ],
    "gesture.wave": [
        Criterion("success_rate", 0.90, 0.80, higher_is_better=True),
        # 規格 §4：手勢 idle 誤觸只看 scenario_kind=idle 的 unknown_false_accept_rate。
        Criterion("unknown_false_accept_rate", 0.10, 0.30, higher_is_better=False),
    ],
    "object.cup": [
        Criterion("success_rate", 0.80, 0.60, higher_is_better=True),
        # 規格 §5：物件 idle 誤觸只看 scenario_kind=idle 的 unknown_false_accept_rate。
        Criterion("unknown_false_accept_rate", 0.01, 0.10, higher_is_better=False),
    ],
}


def _load_json(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_criteria(path: Optional[str]) -> Optional[dict[str, list[Criterion]]]:
    raw = _load_json(path)
    if raw is None:
        return None
    return {capability: [Criterion(**item) for item in items] for capability, items in raw.items()}


def build_scoreboard(
    jsonl_path: str,
    manifest_path: Optional[str] = None,
    preflight_path: Optional[str] = None,
    criteria: Optional[dict[str, list[Criterion]]] = None,
    out_path: str = DEFAULT_OUT_PATH,
) -> str:
    records = load_results(jsonl_path)
    run_meta = current_run_meta(
        jetson_manifest=_load_json(manifest_path),
        layer0_preflight=_load_json(preflight_path),
    )
    scores = aggregate(records, criteria or DEFAULT_CRITERIA)
    out = Path(out_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    write_snapshot(scores, run_meta, str(out))
    return str(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl")
    parser.add_argument("--manifest")
    parser.add_argument("--preflight")
    parser.add_argument("--criteria")
    parser.add_argument("--out", default=DEFAULT_OUT_PATH)
    args = parser.parse_args()

    path = build_scoreboard(
        args.jsonl,
        manifest_path=args.manifest,
        preflight_path=args.preflight,
        criteria=_load_criteria(args.criteria),
        out_path=args.out,
    )
    print(f"snapshot -> {path}")


if __name__ == "__main__":
    main()
