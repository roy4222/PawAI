"""人臉 baseline observer：針對 /state/perception/face 連續狀態流做 baseline 評估。

人臉 benchmark 刻意和手勢/物件事件 observer 分開。人臉身份事件只在穩定身份轉換時發出，
因此這裡評估的是每個 tick 含全部 tracks 的連續狀態流。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_IDLE_LABELS = {"unknown", "none", "idle", ""}


@dataclass
class FaceStateSnapshot:
    ts: float
    tracks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FaceRoundMeta:
    capability_id: str
    scenario_id: str
    expected_label: str
    distance_m: float | None = None
    distance_source: str = "manual_declared"
    window_start_ts: float = 0.0
    scenario_kind: str = "positive"


def parse_face_state(data: dict[str, Any]) -> FaceStateSnapshot:
    """把人臉狀態 JSON dict 轉成快照；缺 stamp 時保守落到 0.0。"""
    return FaceStateSnapshot(
        ts=float(data.get("stamp", 0.0)),
        tracks=list(data.get("tracks", [])),
    )


def filter_face_window(
    snapshots: list[FaceStateSnapshot],
    start_ts: float,
    end_ts: float | None,
) -> list[FaceStateSnapshot]:
    """取出落在 [start_ts, end_ts] 的快照；end_ts=None 代表沒有上界。"""
    return sorted(
        (
            snap
            for snap in snapshots
            if snap.ts >= start_ts and (end_ts is None or snap.ts <= end_ts)
        ),
        key=lambda snap: snap.ts,
    )


def load_face_round_meta(path: str) -> list[FaceRoundMeta]:
    """讀取人臉 round_meta YAML，轉成 FaceRoundMeta list。"""
    return _rounds_from_meta_document(_load_round_meta_document(path))


def enrich_record(record: dict[str, Any], run_id: str, git_commit: str | None) -> dict[str, Any]:
    """補 baseline JSONL 共用欄位；既有 key 不覆蓋。"""
    from datetime import datetime, timezone

    enriched = dict(record)
    enriched.setdefault("run_id", run_id)
    enriched.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    enriched.setdefault("git_commit", git_commit)
    return enriched


def _load_round_meta_document(path: str) -> dict[str, Any]:
    """延後載入 yaml，讓 module import 不依賴 ROS 執行環境。"""
    from pathlib import Path

    import yaml

    with Path(path).open("r", encoding="utf-8") as file:
        document = yaml.safe_load(file) or {}

    if not isinstance(document, dict):
        raise ValueError(f"round_meta YAML 必須是 mapping：{path}")
    return document


def _rounds_from_meta_document(document: dict[str, Any]) -> list[FaceRoundMeta]:
    rounds = document.get("rounds", [])
    if not isinstance(rounds, list):
        raise ValueError("round_meta YAML 的 rounds 必須是 list")

    return [_round_from_mapping(round_data) for round_data in rounds]


def _round_from_mapping(round_data: dict[str, Any]) -> FaceRoundMeta:
    if not isinstance(round_data, dict):
        raise ValueError("round_meta.rounds 每一筆都必須是 mapping")

    expected_label = str(round_data.get("expected_label") or "")
    distance_m = round_data.get("distance_m")
    return FaceRoundMeta(
        capability_id=str(round_data.get("capability_id") or ""),
        scenario_id=str(round_data.get("scenario_id") or ""),
        expected_label=expected_label,
        distance_m=float(distance_m) if distance_m is not None else None,
        distance_source=str(round_data.get("distance_source", "manual_declared")),
        window_start_ts=float(round_data.get("window_start_ts", 0.0)),
        scenario_kind=str(
            round_data.get("scenario_kind")
            or ("idle" if expected_label in _IDLE_LABELS else "positive")
        ),
    )


def _round_meta_run_id(path: str) -> str:
    document = _load_round_meta_document(path)
    return str(document.get("run_id", "face-baseline") or "face-baseline")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _known_tracks(snap: FaceStateSnapshot) -> list[dict[str, Any]]:
    return [track for track in snap.tracks if track.get("stable_name", "unknown") != "unknown"]


def evaluate_face_round(meta: FaceRoundMeta, snapshots: list[FaceStateSnapshot]) -> dict[str, Any]:
    is_idle = meta.expected_label in _IDLE_LABELS

    if is_idle:
        for snap in snapshots:
            known = _known_tracks(snap)
            if known:
                track = known[0]
                return _face_record(
                    meta,
                    predicted_label=track["stable_name"],
                    pass_fail="fail",
                    false_trigger=True,
                    confidence=track.get("sim"),
                    distance_m=track.get("distance_m"),
                )

        return _face_record(
            meta,
            predicted_label="unknown",
            pass_fail="pass",
            false_trigger=False,
            confidence=None,
            distance_m=None,
        )

    for snap in snapshots:
        for track in snap.tracks:
            if track.get("stable_name") == meta.expected_label:
                return _face_record(
                    meta,
                    predicted_label=meta.expected_label,
                    pass_fail="pass",
                    false_trigger=False,
                    confidence=track.get("sim"),
                    distance_m=track.get("distance_m"),
                    latency_ms=(snap.ts - meta.window_start_ts) * 1000.0,
                )

    for snap in snapshots:
        known = _known_tracks(snap)
        if known:
            track = known[0]
            return _face_record(
                meta,
                predicted_label=track["stable_name"],
                pass_fail="fail",
                false_trigger=True,
                confidence=track.get("sim"),
                distance_m=track.get("distance_m"),
            )

    return _face_record(
        meta,
        predicted_label="unknown",
        pass_fail="fail",
        false_trigger=False,
        confidence=None,
        distance_m=None,
    )


def _face_record(
    meta: FaceRoundMeta,
    *,
    predicted_label: str,
    pass_fail: str,
    false_trigger: bool,
    confidence: float | None,
    distance_m: float | None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "capability_id": meta.capability_id,
        "scenario_id": meta.scenario_id,
        "scenario_kind": "idle" if meta.expected_label in _IDLE_LABELS else "positive",
        "expected_label": meta.expected_label,
        "predicted_label": predicted_label,
        "pass_fail": pass_fail,
        "false_trigger": false_trigger,
        "confidence": round(confidence, 4) if confidence is not None else None,
        "latency_ms": latency_ms,
        "distance_m": distance_m if distance_m is not None else meta.distance_m,
        "distance_source": "d435_depth" if distance_m is not None else meta.distance_source,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import subprocess
    import threading
    import time
    from dataclasses import replace
    from pathlib import Path

    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    parser = argparse.ArgumentParser(
        description="Jetson runtime 的 /state/perception/face baseline observer。"
    )
    parser.add_argument("--round-meta", required=True)
    parser.add_argument("--out", default="artifacts/baseline/baseline_result.jsonl")
    parser.add_argument("--state-topic", default="/state/perception/face")
    args = parser.parse_args(argv)

    rounds = load_face_round_meta(args.round_meta)
    run_id = _round_meta_run_id(args.round_meta)
    output_path = Path(args.out)
    try:
        git_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            capture_output=True,
            check=True,
            text=True,
        )
        git_commit = git_result.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        git_commit = None

    class FaceBaselineObserver(Node):
        """訂閱人臉狀態，將每個 tick 的全部 tracks 存進時間排序 buffer。"""

        def __init__(self, state_topic: str) -> None:
            super().__init__("face_baseline_observer")
            self._lock = threading.Lock()
            self._buffer: list[FaceStateSnapshot] = []
            self._subscription = self.create_subscription(
                String,
                state_topic,
                self._on_face_state,
                10,
            )
            self.get_logger().info(f"訂閱 face state topic：{state_topic}")

        def _on_face_state(self, msg: Any) -> None:
            try:
                payload = json.loads(msg.data)
                if not isinstance(payload, dict):
                    raise ValueError("face state JSON 必須是 object")
                snapshot = parse_face_state(payload)
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                self.get_logger().warning(f"略過無效 face state：{exc}")
                return

            with self._lock:
                self._buffer.append(snapshot)
                self._buffer.sort(key=lambda snap: snap.ts)

        def snapshot(self) -> list[FaceStateSnapshot]:
            with self._lock:
                return list(self._buffer)

    rclpy.init(args=None)
    node = FaceBaselineObserver(args.state_topic)
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    try:
        total = len(rounds)
        for index, meta in enumerate(rounds, start=1):
            kind = meta.scenario_kind
            input(
                f"Round {index}/{total}：{meta.capability_id} "
                f"expect={meta.expected_label} kind={kind} — 按 Enter 開始"
            )
            window_start = time.time()
            print("按 Enter 結束")
            input()
            window_end = time.time()

            snapshots = filter_face_window(node.snapshot(), window_start, window_end)
            record = evaluate_face_round(
                replace(meta, window_start_ts=window_start),
                snapshots,
            )
            enriched = enrich_record(record, run_id, git_commit)
            _append_jsonl(output_path, enriched)
            print(
                "結果："
                f"pass_fail={enriched.get('pass_fail')} "
                f"false_trigger={enriched.get('false_trigger')} "
                f"predicted_label={enriched.get('predicted_label')}"
            )
    except KeyboardInterrupt:
        print("收到中斷，準備關閉 face baseline observer。")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        spin_thread.join(timeout=2.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
