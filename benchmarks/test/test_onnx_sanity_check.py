import numpy as np

from benchmarks.scripts import onnx_sanity_check as sut


def test_generate_synthetic_bgr_image_shape_and_dtype():
    image = sut.generate_synthetic_bgr(width=320, height=240, seed=7)

    assert image.shape == (240, 320, 3)
    assert image.dtype == np.uint8
    assert image.min() >= 0
    assert image.max() <= 255


def test_preprocess_bgr_for_onnx_letterboxes_to_nchw_float32():
    image = np.zeros((120, 240, 3), dtype=np.uint8)
    image[..., 2] = 255

    blob, meta = sut.preprocess_bgr_for_onnx(image, imgsz=640)

    assert blob.shape == (1, 3, 640, 640)
    assert blob.dtype == np.float32
    assert meta.output_shape == (640, 640, 3)
    assert meta.resized_shape == (320, 640)
    assert meta.pad_top == 160
    assert meta.pad_left == 0
    assert 0.0 <= float(blob.min()) <= float(blob.max()) <= 1.0


def test_output_shape_check_delegates_to_object_model_contract(monkeypatch):
    calls = []

    def fake_is_compatible_output_shape(shape):
        calls.append(shape)
        return shape == [1, 300, 6]

    monkeypatch.setattr(
        sut.object_model_contract,
        "is_compatible_output_shape",
        fake_is_compatible_output_shape,
    )

    assert sut.is_object_output_shape_compatible([1, 300, 6]) is True
    assert sut.is_object_output_shape_compatible([1, 8400, 84]) is False
    assert calls == [[1, 300, 6], [1, 8400, 84]]
