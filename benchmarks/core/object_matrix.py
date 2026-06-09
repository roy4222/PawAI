"""Object detection 矩陣量測純邏輯（CI-safe，無 rclpy）。

把每個 cell（object × distance × light × angle）的多次 trial 觀測，聚合成一筆
矩陣 row：success_rate / avg_confidence / bbox / misclass / verdict。

ROS wrapper 見 scripts/obj_matrix_cap.py（訂 /event/object_detected，固定窗切 trial）。
/event/object_detected schema（object_perception_node）：
    {"event_type": "object_detected", "stamp": ..., "objects":
        [{"class_name": "chair", "confidence": 0.87, "bbox": [x1,y1,x2,y2], ...}]}

判定 gate（6/9 demo 決策規則）：
    success_rate ≥ 0.8 → PASS（主秀候選）
    success_rate ≥ 0.6 → DEGRADED（備援）
    其他              → FAIL（不上台）
    avg_confidence < 0.45 → 另標 low_conf（不當主秀）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

CSV_HEADER = [
    "timestamp", "object", "distance_m", "light", "angle",
    "trials", "success", "success_rate", "avg_confidence",
    "bbox", "misclass", "verdict", "low_conf", "notes",
]

PASS_RATE = 0.8
DEGRADED_RATE = 0.6
LOW_CONF = 0.45


def detections_for(event: dict, target: str) -> list:
    """從一筆 object event JSON 抽出 target class 的 (confidence, bbox) list。"""
    hits = []
    for obj in event.get("objects") or []:
        if isinstance(obj, dict) and obj.get("class_name") == target:
            hits.append((obj.get("confidence"), obj.get("bbox")))
    return hits


def other_labels(events: list, target: str) -> list:
    """window 內出現過、非 target 的 class label（誤認/共現），去重排序。"""
    seen = set()
    for ev in events:
        for obj in ev.get("objects") or []:
            if isinstance(obj, dict):
                cn = obj.get("class_name")
                if cn and cn != target:
                    seen.add(cn)
    return sorted(seen)


@dataclass
class TrialResult:
    detected: bool
    confidence: Optional[float]   # max target confidence in the trial window, None if miss
    bbox: Optional[list]          # bbox of the max-confidence target detection


def summarize_trial(events: list, target: str, conf_min: float) -> TrialResult:
    """一個 trial 窗內的多筆 events → 是否偵測到 target（conf ≥ conf_min）+ 最佳 conf/bbox。"""
    best_conf = None
    best_bbox = None
    for ev in events:
        for conf, bbox in detections_for(ev, target):
            if conf is None or conf < conf_min:
                continue
            if best_conf is None or conf > best_conf:
                best_conf = conf
                best_bbox = bbox
    return TrialResult(detected=best_conf is not None, confidence=best_conf, bbox=best_bbox)


def verdict_for(success_rate: float, avg_conf: Optional[float]) -> tuple:
    """(verdict, low_conf_flag)。verdict ∈ {PASS, DEGRADED, FAIL}。"""
    if success_rate >= PASS_RATE:
        v = "PASS"
    elif success_rate >= DEGRADED_RATE:
        v = "DEGRADED"
    else:
        v = "FAIL"
    low = avg_conf is not None and avg_conf < LOW_CONF
    return v, low


def summarize_cell(trials: list) -> dict:
    """trials: list[TrialResult] → 矩陣 row 的聚合欄位（timestamp/維度/misclass/notes 由 wrapper 補）。"""
    n = len(trials)
    success = sum(1 for t in trials if t.detected)
    rate = (success / n) if n else 0.0
    confs = [t.confidence for t in trials if t.detected and t.confidence is not None]
    avg_conf = (sum(confs) / len(confs)) if confs else None
    # representative bbox = 信心最高那次成功 trial 的 bbox
    best = None
    for t in trials:
        if not (t.detected and t.confidence is not None):
            continue
        if best is None or t.confidence > best.confidence:
            best = t
    bbox = best.bbox if best is not None else None
    verdict, low = verdict_for(rate, avg_conf)
    return {
        "trials": n,
        "success": success,
        "success_rate": round(rate, 3),
        "avg_confidence": round(avg_conf, 3) if avg_conf is not None else None,
        "bbox": bbox,
        "verdict": verdict,
        "low_conf": low,
    }


def csv_row(cell: dict) -> list:
    """完整 row dict → 依 CSV_HEADER 順序的字串 list（list/tuple 用 | 串接）。"""
    def s(v):
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return "|".join(str(x) for x in v)
        return str(v)
    return [s(cell.get(k)) for k in CSV_HEADER]
