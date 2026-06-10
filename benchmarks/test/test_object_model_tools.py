"""Pure tests for object model A/B helper scripts."""

import pytest

from scripts import obj_matrix_cap
from scripts.object_model_ab import build_capture_command, parse_model_specs
from scripts.object_model_contract import is_compatible_output_shape


def test_contract_accepts_fixed_yolo_detection_shape():
    assert is_compatible_output_shape([1, 300, 6]) is True


def test_contract_accepts_dynamic_batch_and_detection_count():
    assert is_compatible_output_shape(["batch", "num_detections", 6]) is True


@pytest.mark.parametrize("shape", ([1, 300, 85], [300, 6], [1, 300, "attrs"]))
def test_contract_rejects_non_object_perception_shapes(shape):
    assert is_compatible_output_shape(shape) is False


def test_parse_model_specs_accepts_name_path_pairs():
    specs = parse_model_specs(["yolo26n=/models/n.onnx", "yolo26s=/models/s.onnx"])
    assert [(s.name, s.path) for s in specs] == [
        ("yolo26n", "/models/n.onnx"),
        ("yolo26s", "/models/s.onnx"),
    ]


def test_build_capture_command_includes_metadata_sidecar_fields():
    command = build_capture_command(
        model_name="yolo26n",
        model_path="/home/jetson/models/yolo26n.onnx",
        threshold=0.35,
        input_size=640,
        git_commit="abc1234",
        target_object="cup",
        distance=1.0,
        light="normal",
        angle="front",
        trials=5,
        window=6.0,
        gap=6.0,
        output_csv="artifacts/object_matrix/yolo26n.csv",
    )

    joined = " ".join(command)
    assert command[:2] == ["python3", "scripts/obj_matrix_cap.py"]
    assert "--auto" in command
    assert "model_name=yolo26n" in joined
    assert "model_path=/home/jetson/models/yolo26n.onnx" in joined
    assert "conf=0.35" in joined
    assert "input_size=640" in joined
    assert "git_commit=abc1234" in joined


def test_obj_matrix_timing_rejects_windows_below_cooldown_without_override():
    with pytest.raises(ValueError, match="window"):
        obj_matrix_cap.validate_timing(window=4.9, gap=6.0, auto=True)


def test_obj_matrix_timing_rejects_auto_gap_below_cooldown_without_override():
    with pytest.raises(ValueError, match="gap"):
        obj_matrix_cap.validate_timing(window=6.0, gap=4.9, auto=True)


def test_obj_matrix_timing_allows_demo_safe_defaults():
    assert obj_matrix_cap.validate_timing(window=6.0, gap=6.0, auto=True) == []
