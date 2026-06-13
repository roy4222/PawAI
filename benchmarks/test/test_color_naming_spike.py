import numpy as np

from benchmarks.scripts import color_naming_spike as sut


def _solid_bgr(color):
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    image[:, :] = color
    return image


def test_lab_lut_names_primary_color_blocks_in_zh():
    assert sut.name_lab_color(_solid_bgr((0, 0, 255)), (0, 0, 20, 20)).name == "紅色"
    assert sut.name_lab_color(_solid_bgr((255, 0, 0)), (0, 0, 20, 20)).name == "藍色"
    assert sut.name_lab_color(_solid_bgr((0, 255, 0)), (0, 0, 20, 20)).name == "綠色"


def test_center_half_bbox_keeps_center_and_halves_size():
    assert sut.center_half_bbox((10, 20, 110, 220)) == (35, 70, 85, 170)
    assert sut.center_half_bbox((0, 0, 9, 9)) == (2, 2, 7, 7)
