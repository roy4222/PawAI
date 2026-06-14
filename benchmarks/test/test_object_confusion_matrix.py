"""Pure (ROS-free, cv2/ort-free) tests for the object confusion-matrix harness.

Only numpy is required; cv2 + onnxruntime are lazily imported by the harness
and are NOT touched here.
"""
from pathlib import Path

import numpy as np
import pytest

from benchmarks.scripts import object_confusion_matrix as sut


# --------------------------------------------------------------------------- #
# decode_detections                                                           #
# --------------------------------------------------------------------------- #
def test_decode_filters_below_conf_and_keeps_above():
    # rows: x1,y1,x2,y2,conf,class_id
    raw = np.array([
        [10, 10, 50, 50, 0.42, 41],   # cup, kept
        [10, 10, 50, 50, 0.30, 39],   # bottle, below 0.35 -> dropped
        [20, 20, 60, 60, 0.90, 67],   # cell_phone, kept
    ], dtype=np.float32)

    dets = sut.decode_detections(raw, conf=0.35)

    names = sorted(d.class_name for d in dets)
    assert names == ["cell_phone", "cup"]
    cup = next(d for d in dets if d.class_name == "cup")
    assert cup.confidence == pytest.approx(0.42, abs=1e-3)


def test_decode_accepts_batched_300x6_and_drops_invalid_class():
    raw = np.zeros((1, 3, 6), dtype=np.float32)
    raw[0, 0] = [0, 0, 40, 40, 0.9, 41]      # cup
    raw[0, 1] = [0, 0, 40, 40, 0.9, 999]     # out-of-range id -> dropped
    raw[0, 2] = [0, 0, 40, 40, 0.9, 56]      # chair

    dets = sut.decode_detections(raw, conf=0.35)
    assert sorted(d.class_name for d in dets) == ["chair", "cup"]


def test_decode_respects_class_whitelist():
    raw = np.array([
        [0, 0, 40, 40, 0.9, 41],   # cup
        [0, 0, 40, 40, 0.9, 16],   # dog (not whitelisted)
    ], dtype=np.float32)
    dets = sut.decode_detections(raw, conf=0.35, allowed={41})
    assert [d.class_name for d in dets] == ["cup"]


def test_decode_drops_degenerate_bbox():
    raw = np.array([[50, 50, 50, 50, 0.9, 41]], dtype=np.float32)  # zero-area
    assert sut.decode_detections(raw, conf=0.35) == []


def test_decode_rejects_wrong_last_dim():
    with pytest.raises(ValueError, match=r"\(N,6\)"):
        sut.decode_detections(np.zeros((10, 85), dtype=np.float32), conf=0.35)


def test_rescale_bbox_inverts_letterbox_padding():
    # scale 0.5, 8px top/left pad -> canvas (28,28,48,48) maps to (40,40,80,80)
    x1, y1, x2, y2 = sut.rescale_bbox(
        28, 28, 48, 48, scale=0.5, pad_left=8, pad_top=8,
        orig_w=200, orig_h=200,
    )
    assert (x1, y1, x2, y2) == (40.0, 40.0, 80.0, 80.0)


# --------------------------------------------------------------------------- #
# clip discovery / path parsing                                               #
# --------------------------------------------------------------------------- #
def test_parse_distance_token_variants():
    assert sut.parse_distance_token("0.7m") == 0.7
    assert sut.parse_distance_token("1.5 M") == 1.5
    assert sut.parse_distance_token("front") is None


def test_clip_spec_from_nested_object_distance_folder():
    root = Path("/clips")
    spec = sut.clip_spec_from_path(Path("/clips/cup/0.7m"), root)
    assert spec is not None
    assert spec.object_name == "cup"
    assert spec.distance_m == 0.7
    assert spec.is_video is False


def test_clip_spec_from_flat_naming_normalizes_object():
    root = Path("/clips")
    spec = sut.clip_spec_from_path(Path("/clips/cell phone__1.0m"), root)
    assert spec is not None
    assert spec.object_name == "cell_phone"
    assert spec.distance_m == 1.0


def test_clip_spec_none_when_no_distance():
    root = Path("/clips")
    assert sut.clip_spec_from_path(Path("/clips/random/folder"), root) is None


def test_discover_clips_finds_image_folders_and_videos(tmp_path):
    (tmp_path / "cup" / "0.7m").mkdir(parents=True)
    (tmp_path / "cup" / "0.7m" / "a.jpg").write_bytes(b"x")
    (tmp_path / "cup" / "0.7m" / "b.png").write_bytes(b"x")
    (tmp_path / "bottle").mkdir()
    (tmp_path / "bottle" / "1.5m.mp4").write_bytes(b"x")
    # a non-labelled dir is ignored
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.jpg").write_bytes(b"x")

    clips = sut.discover_clips(tmp_path)
    keys = sorted((c.object_name, c.distance_m, c.is_video) for c in clips)
    assert keys == [("bottle", 1.5, True), ("cup", 0.7, False)]


def test_discover_clips_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        sut.discover_clips(tmp_path / "does_not_exist")


# --------------------------------------------------------------------------- #
# confusion matrix + metric aggregation                                       #
# --------------------------------------------------------------------------- #
def _det(name: str, conf: float = 0.9):
    cid = next(k for k, v in sut.COCO_CLASSES.items() if v == name)
    return sut.Detection(class_id=cid, class_name=name, confidence=conf,
                         bbox=(0, 0, 10, 10))


def test_confusion_matrix_counts_mislabels_per_frame():
    cm = sut.ConfusionMatrix()
    cm.record_frame("cup", [_det("cup"), _det("cup")])        # dup label once
    cm.record_frame("cup", [_det("cell_phone")])              # mislabel
    cm.record_frame("cup", [_det("bottle"), _det("cup")])     # both
    cm.record_frame("cup", [])                                # miss

    assert cm.frame_count("cup") == 4
    assert cm.count("cup", "cup") == 2
    assert cm.count("cup", "cell_phone") == 1
    assert cm.count("cup", "__none__") == 1
    assert cm.confusions("cup") == {"bottle": 1, "cell_phone": 1}


def test_cell_metrics_recall_and_conf_stats():
    cell = sut.CellMetrics(object_name="cup", distance_m=1.5)
    cell.frames = 5
    cell.detected_frames = 4
    cell.confidences = [0.40, 0.55, 0.60, 0.50]

    assert cell.recall == pytest.approx(0.8)
    assert cell.conf_min == pytest.approx(0.40)
    assert cell.conf_max == pytest.approx(0.60)
    assert cell.conf_avg == pytest.approx(0.5125)
    assert cell.detection_count == 4


def test_cell_metrics_empty_conf_is_none():
    cell = sut.CellMetrics(object_name="cup", distance_m=2.0, frames=3)
    assert cell.conf_avg is None
    assert cell.recall == 0.0


@pytest.mark.parametrize("recall,expected", [
    (0.95, "PASS"), (0.80, "PASS"), (0.70, "DEGRADED"),
    (0.60, "DEGRADED"), (0.40, "FAIL"),
])
def test_recall_gate_thresholds(recall, expected):
    assert sut.evaluate_recall_gate(recall) == expected


# --------------------------------------------------------------------------- #
# whitelist parsing + dry-run rendering                                       #
# --------------------------------------------------------------------------- #
def test_parse_whitelist():
    assert sut.parse_whitelist("39, 41 ,56") == {39, 41, 56}
    assert sut.parse_whitelist("") is None
    assert sut.parse_whitelist(None) is None


def test_render_dry_run_lists_objects_and_empty_hint():
    assert "no labelled clips found" in sut.render_dry_run([])
    specs = [sut.ClipSpec("cup", 0.7, Path("/clips/cup/0.7m.mp4"), True)]
    text = sut.render_dry_run(specs)
    assert "1 clip(s) discovered" in text
    assert "cup" in text and "0.70m" in text
