"""Tests for pure utility functions in face_identity_node.

These tests require cv2 and rclpy (run on Jetson or with ROS2 installed).
Run: python3 -m pytest face_perception/test/test_utilities.py -v
  or: colcon test --packages-select face_perception
"""
import numpy as np
import pytest

from face_perception.face_identity_node import (
    FaceIdentityNode,
    cosine_similarity,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_returns_zero(self):
        a = np.array([0.0, 0.0])
        assert cosine_similarity(a, a) == 0.0


class TestBboxIou:
    def test_identical_boxes(self):
        box = (10, 10, 50, 50)
        assert FaceIdentityNode.bbox_iou(box, box) == pytest.approx(1.0)

    def test_no_overlap(self):
        a = (0, 0, 10, 10)
        b = (20, 20, 30, 30)
        assert FaceIdentityNode.bbox_iou(a, b) == 0.0

    def test_partial_overlap(self):
        a = (0, 0, 10, 10)
        b = (5, 5, 15, 15)
        # intersection = 5*5 = 25, union = 100+100-25 = 175
        assert FaceIdentityNode.bbox_iou(a, b) == pytest.approx(25.0 / 175.0)

    def test_contained_box(self):
        outer = (0, 0, 100, 100)
        inner = (10, 10, 20, 20)
        # intersection = 10*10 = 100, union = 10000+100-100 = 10000
        assert FaceIdentityNode.bbox_iou(outer, inner) == pytest.approx(
            100.0 / 10000.0
        )


class TestToBbox:
    def test_normal_face(self):
        face_row = np.array([10, 20, 50, 60, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        assert result == (10, 20, 60, 80)

    def test_clamp_to_image(self):
        face_row = np.array([-5, -5, 100, 100, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        assert result == (0, 0, 95, 95)

    def test_zero_size_still_produces_bbox(self):
        face_row = np.array([10, 20, 0, 0, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        # fw=0 → max(1,0)=1 → x2=11, fh=0 → max(1,0)=1 → y2=21
        assert result is not None

    def test_face_outside_image_returns_none(self):
        face_row = np.array([700, 500, 50, 50, 0.95])
        result = FaceIdentityNode.to_bbox(face_row, 640, 480)
        # x1=640 (clamped), x2=640 (clamped) → x2<=x1 → None
        assert result is None
