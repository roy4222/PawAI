"""通用 perception baseline observer (v0.1, 選項 B)。

純比對邏輯（dev-機 TDD）：把 operator 宣告的 round_meta（expected_label/scenario/distance）
與該 round 內觀測到的 (label, confidence, ts) 比對，產一筆 CapabilityResult-shaped dict。
idle round（expected_label in {"none",""}）：任何觀測 = false_trigger。
positive round：observed 含 expected → pass（latency=首個命中相對 window_start）；否則 miss（fail）。

ROS node wrapper（Jetson 跑，不在 CI）：訂 /event/{gesture_detected,object_detected}（face 見 Task 4b），
依 round_meta 檔（operator 宣告每 round 的 capability/scenario/expected/window）切窗，
把每 topic 正規化成 (label, confidence, ts) → evaluate_round → append JSONL。

idle 切窗規則（spec §4/§5）：idle round 以**固定長度窗**為單位各生一筆 record（gesture=60s×10 段、
object=60s/窗），每窗 `scenario_kind="idle"`、`false_trigger`=該窗內有無誤報；aggregator 的
unknown_false_accept_rate = 誤觸窗數/總窗數。positive round 則每次「擺好→宣告→觀測」生一筆。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

_IDLE_LABELS = {"none", "idle", ""}


@dataclass
class RoundMeta:
    capability_id: str
    scenario_id: str
    expected_label: str            # "none"/"" = idle round（預期零事件）
    distance_m: Optional[float] = None
    distance_source: str = "manual_declared"
    window_start_ts: float = 0.0
    scenario_kind: Optional[str] = None

    def __post_init__(self) -> None:
        if self.scenario_kind is None:
            self.scenario_kind = "idle" if self.expected_label in _IDLE_LABELS else "positive"


def normalize_gesture_event(data: dict) -> list[tuple]:
    """把 gesture event JSON 正規化成 evaluate_round 可吃的觀測 tuple。"""
    gesture = data.get("gesture")
    if not gesture:
        return []
    return [(gesture, data.get("confidence"), data.get("stamp"))]


def normalize_object_event(data: dict) -> list[tuple]:
    """把 object event JSON 正規化成 evaluate_round 可吃的觀測 tuple。"""
    stamp = data.get("stamp")
    observations = []
    for obj in data.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        label = obj.get("class_name")
        if label:
            observations.append((label, obj.get("confidence"), stamp))
    return observations


def filter_window(observations: list[tuple], start_ts: float, end_ts: float | None) -> list[tuple]:
    """回傳 ts 落在 [start_ts, end_ts] 的觀測；end_ts=None 表示不設上界。"""
    windowed = []
    for observation in observations:
        if len(observation) < 3:
            continue
        ts = observation[2]
        if ts is None:
            continue
        if ts < start_ts:
            continue
        if end_ts is not None and ts > end_ts:
            continue
        windowed.append(observation)
    return sorted(windowed, key=lambda observation: observation[2])


def load_round_meta(path: str) -> list[RoundMeta]:
    """讀取 operator 宣告的 round meta YAML，轉成 RoundMeta list。"""
    import yaml

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    rounds = raw.get("rounds", [])
    return [
        RoundMeta(
            capability_id=round_data["capability_id"],
            scenario_id=round_data["scenario_id"],
            expected_label=str(round_data.get("expected_label") or ""),
            distance_m=(
                float(round_data["distance_m"])
                if round_data.get("distance_m") is not None
                else None
            ),
            distance_source=round_data.get("distance_source", "manual_declared"),
            window_start_ts=float(round_data.get("window_start_ts") or 0.0),
            scenario_kind=round_data.get("scenario_kind"),
        )
        for round_data in rounds
    ]


def enrich_record(record: dict, run_id: str, git_commit: str | None) -> dict:
    """補 baseline run 欄位，但不覆蓋 record 既有 key。"""
    from datetime import datetime, timezone

    enriched = dict(record)
    enriched.setdefault("run_id", run_id)
    enriched.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    enriched.setdefault("git_commit", git_commit)
    return enriched


def evaluate_round(meta: RoundMeta, observations: list) -> dict:
    """observations: list[(label:str, confidence:float|None, ts:float)]，限定該 round 窗內。"""
    is_idle = meta.expected_label in _IDLE_LABELS

    if is_idle:
        ft = len(observations) > 0
        predicted = observations[0][0] if observations else "none"
        return _record(meta, predicted_label=predicted,
                       pass_fail=("fail" if ft else "pass"),
                       false_trigger=ft, confidence=None, latency_ms=None)

    # positive round
    matches = [o for o in observations if o[0] == meta.expected_label]
    if matches:
        label, conf, ts = matches[0]
        return _record(meta, predicted_label=label, pass_fail="pass", false_trigger=False,
                       confidence=conf, latency_ms=(ts - meta.window_start_ts) * 1000.0)
    # miss（沒看到 expected）：認錯或沒看到都算 miss，不是 false_trigger
    predicted = observations[0][0] if observations else "none"
    return _record(meta, predicted_label=predicted, pass_fail="fail", false_trigger=False,
                   confidence=None, latency_ms=None)


def _record(meta: RoundMeta, *, predicted_label: str, pass_fail: str,
            false_trigger: bool, confidence: Optional[float], latency_ms: Optional[float]) -> dict:
    return {
        "capability_id": meta.capability_id,
        "scenario_id": meta.scenario_id,
        # F2：scenario_kind 供 aggregate 分離算 recall vs false-accept（idle round=預期零事件）
        "scenario_kind": "idle" if meta.expected_label in _IDLE_LABELS else "positive",
        "expected_label": meta.expected_label,
        "predicted_label": predicted_label,
        "pass_fail": pass_fail,
        "false_trigger": false_trigger,
        "confidence": confidence,
        "latency_ms": latency_ms,
        "distance_m": meta.distance_m,
        "distance_source": meta.distance_source,
    }


def count_false_triggers(round_records: list[dict]) -> int:
    return sum(1 for r in round_records if r.get("false_trigger"))


def main(argv: list[str] | None = None) -> None:
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

    def _load_run_id(path: str) -> str:
        import yaml

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return str(raw.get("run_id", "perception-baseline"))

    def _git_commit() -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        commit = result.stdout.strip()
        return commit or None

    def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    class PerceptionBaselineObserver(Node):
        def __init__(self, gesture_topic: str, object_topic: str) -> None:
            super().__init__("perception_baseline_observer")
            self._lock = threading.Lock()
            self._observations: list[tuple] = []
            self.create_subscription(String, gesture_topic, self._on_gesture, 10)
            self.create_subscription(String, object_topic, self._on_object, 10)
            self.get_logger().info(
                f"PerceptionBaselineObserver 訂閱 {gesture_topic} 與 {object_topic}"
            )

        def snapshot(self) -> list[tuple]:
            with self._lock:
                return list(self._observations)

        def _on_gesture(self, msg: String) -> None:
            self._ingest(msg.data, normalize_gesture_event, "gesture")

        def _on_object(self, msg: String) -> None:
            self._ingest(msg.data, normalize_object_event, "object")

        def _ingest(self, payload: str, normalizer: Any, source: str) -> None:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as exc:
                self.get_logger().warning(f"{source} event JSON 解析失敗：{exc}")
                return
            if not isinstance(data, dict):
                self.get_logger().warning(f"{source} event JSON root 不是 object，略過")
                return

            observations = []
            for label, confidence, ts in normalizer(data):
                if label is None or ts is None:
                    continue
                try:
                    observations.append((str(label), confidence, float(ts)))
                except (TypeError, ValueError):
                    self.get_logger().warning(f"{source} event stamp 非數值，略過：{ts!r}")
            if not observations:
                return

            with self._lock:
                self._observations.extend(observations)
                self._observations.sort(key=lambda observation: observation[2])

    parser = argparse.ArgumentParser()
    parser.add_argument("--round-meta", required=True)
    parser.add_argument("--out", default="artifacts/baseline/baseline_result.jsonl")
    parser.add_argument("--gesture-topic", default="/event/gesture_detected")
    parser.add_argument("--object-topic", default="/event/object_detected")
    args = parser.parse_args(argv)

    round_meta = load_round_meta(args.round_meta)
    run_id = _load_run_id(args.round_meta)
    git_commit = _git_commit()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init(args=None)
    node = PerceptionBaselineObserver(args.gesture_topic, args.object_topic)
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    try:
        total = len(round_meta)
        for index, meta in enumerate(round_meta, start=1):
            input(
                f"Round {index}/{total}：{meta.capability_id} "
                f"expect={meta.expected_label} kind={meta.scenario_kind} — 按 Enter 開始"
            )
            window_start = time.time()
            print("按 Enter 結束")
            input()
            window_end = time.time()

            observations = filter_window(node.snapshot(), window_start, window_end)
            meta_with_window = replace(meta, window_start_ts=window_start)
            record = evaluate_round(meta_with_window, observations)
            enriched = enrich_record(record, run_id, git_commit)
            _append_jsonl(out_path, enriched)
            print(
                f"結果：pass_fail={enriched['pass_fail']} "
                f"false_trigger={enriched['false_trigger']} "
                f"predicted={enriched['predicted_label']}"
            )
    except KeyboardInterrupt:
        print("收到中斷，結束 perception baseline observer。")
    finally:
        node.destroy_node()
        rclpy.shutdown()
        spin_thread.join(timeout=2.0)


if __name__ == "__main__":
    main()
