"""YuNet face detection adapter tests.
Uses a synthetic test image since real D435 images may not be available.
"""
import os
import numpy as np
import pytest

try:
    import cv2
    HAS_OPENCV_FACE = hasattr(cv2, "FaceDetectorYN")
except ImportError:
    HAS_OPENCV_FACE = False
    cv2 = None

YUNET_MODEL = os.environ.get(
    "YUNET_MODEL_PATH",
    "/home/jetson/face_models/face_detection_yunet_legacy.onnx",
)
HAS_MODEL_FILE = os.path.isfile(YUNET_MODEL)

from benchmarks.adapters.face_yunet import FaceYuNetAdapter


def test_adapter_is_bench_adapter():
    from benchmarks.adapters.base import BenchAdapter
    assert issubclass(FaceYuNetAdapter, BenchAdapter)


@pytest.mark.skipif(not HAS_OPENCV_FACE,
                    reason="OpenCV not available")
def test_prepare_input_returns_ndarray(tmp_path):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "test.jpg"), img)
    path = str(tmp_path / "test.jpg")

    adapter = FaceYuNetAdapter()
    result = adapter.prepare_input(path)
    assert isinstance(result, np.ndarray)
    assert result.shape == (480, 640, 3)


@pytest.mark.skipif(not HAS_OPENCV_FACE or not HAS_MODEL_FILE,
                    reason="OpenCV face module or YuNet model file not available")
def test_load_and_infer_synthetic():
    """Test with a synthetic image — may detect 0 faces, that's OK."""
    adapter = FaceYuNetAdapter()
    adapter.load({
        "model_path": YUNET_MODEL,
        "score_threshold": 0.5,
        "input_size": [320, 320],
    })
    img = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
    result = adapter.infer(img)
    assert "boxes" in result
    assert "scores" in result
    assert "n_faces" in result
    assert isinstance(result["n_faces"], int)
    adapter.cleanup()


def test_cleanup_safe_when_not_loaded():
    adapter = FaceYuNetAdapter()
    adapter.cleanup()  # Should not raise
