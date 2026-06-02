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
from typing import Optional

_IDLE_LABELS = {"none", "idle", ""}


@dataclass
class RoundMeta:
    capability_id: str
    scenario_id: str
    expected_label: str            # "none"/"" = idle round（預期零事件）
    distance_m: Optional[float] = None
    distance_source: str = "manual_declared"
    window_start_ts: float = 0.0


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


# --- ROS node wrapper（Jetson 跑，v0.1 不在 CI；保持薄）---
# class PerceptionBaselineObserver(Node):
#   - 訂 /event/gesture_detected, /event/object_detected（face 見 Task 4b）
#   - _normalize(topic, msg) -> list[(label, confidence, ts)]
#   - 依 round_meta 檔（operator 宣告 capability/scenario/expected/window_start/window_end）切窗
#   - round 結束時 evaluate_round(meta, obs) → 補 run_id/timestamp/git_commit（current_run_meta）
#     → CapabilityResult(...).to_record() → append baseline_result.jsonl
