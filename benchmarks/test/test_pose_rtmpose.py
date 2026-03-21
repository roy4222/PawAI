"""RTMPose wholebody adapter tests."""
import os
import numpy as np
import pytest

try:
    from rtmlib import Wholebody
    HAS_RTMLIB = True
except ImportError:
    HAS_RTMLIB = False

from benchmarks.adapters.pose_rtmpose import PoseRTMPoseAdapter


def test_adapter_is_bench_adapter():
    from benchmarks.adapters.base import BenchAdapter
    assert issubclass(PoseRTMPoseAdapter, BenchAdapter)


def test_cleanup_safe_when_not_loaded():
    adapter = PoseRTMPoseAdapter()
    adapter.cleanup()


@pytest.mark.skipif(not HAS_RTMLIB, reason="rtmlib not installed")
def test_load_and_infer(tmp_path):
    """Test with synthetic image on GPU-capable machine."""
    adapter = PoseRTMPoseAdapter()
    adapter.load({"mode": "balanced", "device": "cpu", "backend": "onnxruntime"})
    img = np.random.randint(50, 200, (480, 640, 3), dtype=np.uint8)
    result = adapter.infer(img)
    assert "n_persons" in result
    assert "keypoints_shape" in result
    adapter.cleanup()
