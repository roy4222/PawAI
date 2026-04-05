"""Tests for object_perception — COCO 80 classes, letterbox, rescale, dedup."""

import json
import time

import numpy as np
import pytest

from object_perception.coco_classes import COCO_CLASSES, class_color
from object_perception.object_perception_node import ObjectPerceptionNode


# ------------------------------------------------------------------
# COCO 80 class map
# ------------------------------------------------------------------
class TestCocoClasses:
    def test_has_80_classes(self):
        assert len(COCO_CLASSES) == 80

    def test_all_ids_contiguous(self):
        """YOLO uses contiguous 0-79, not the 91-ID scheme from original COCO paper."""
        assert set(COCO_CLASSES.keys()) == set(range(80))

    def test_all_names_underscored(self):
        """No class name should contain a space (JSON consistency)."""
        for name in COCO_CLASSES.values():
            assert " " not in name, f"class name '{name}' contains space"

    def test_class_ids_are_int(self):
        for k in COCO_CLASSES:
            assert isinstance(k, int)

    def test_p0_subset_preserved(self):
        """Original P0 6 classes must remain at correct IDs."""
        assert COCO_CLASSES[0] == "person"
        assert COCO_CLASSES[16] == "dog"
        assert COCO_CLASSES[39] == "bottle"
        assert COCO_CLASSES[41] == "cup"
        assert COCO_CLASSES[56] == "chair"
        assert COCO_CLASSES[60] == "dining_table"

    def test_dining_table_underscore(self):
        """COCO uses 'dining table' but we use 'dining_table' for JSON consistency."""
        assert COCO_CLASSES[60] == "dining_table"
        assert "dining table" not in COCO_CLASSES.values()

    def test_common_underscored_names(self):
        """Spot-check other originally-spaced names are also underscored."""
        assert COCO_CLASSES[67] == "cell_phone"  # was "cell phone"
        assert COCO_CLASSES[9] == "traffic_light"  # was "traffic light"
        assert COCO_CLASSES[77] == "teddy_bear"  # was "teddy bear"
        assert COCO_CLASSES[52] == "hot_dog"  # was "hot dog"


# ------------------------------------------------------------------
# class_color generator
# ------------------------------------------------------------------
class TestClassColor:
    def test_deterministic(self):
        assert class_color(16) == class_color(16)
        assert class_color(0) == class_color(0)

    def test_returns_bgr_tuple(self):
        c = class_color(42)
        assert isinstance(c, tuple)
        assert len(c) == 3
        for v in c:
            assert isinstance(v, int)
            assert 0 <= v <= 255

    def test_distinct_for_common_classes(self):
        """Nearby common classes should get visually distinct colors."""
        colors = {class_color(i) for i in [0, 16, 39, 41, 56, 60, 63, 66, 67, 73]}
        assert len(colors) == 10  # all unique

    def test_covers_all_80_classes(self):
        """No crash for any valid class_id."""
        for i in range(80):
            c = class_color(i)
            assert len(c) == 3


# ------------------------------------------------------------------
# Letterbox
# ------------------------------------------------------------------
class TestLetterbox:
    def test_output_shape_square(self):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        canvas, scale, left, top = ObjectPerceptionNode.letterbox(img, 640)
        assert canvas.shape == (640, 640, 3)

    def test_output_shape_nonsquare(self):
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        canvas, scale, left, top = ObjectPerceptionNode.letterbox(img, 640)
        assert canvas.shape == (640, 640, 3)

    def test_scale_landscape(self):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        _, scale, left, top = ObjectPerceptionNode.letterbox(img, 640)
        assert scale == pytest.approx(1.0, abs=0.01)

    def test_scale_portrait(self):
        img = np.zeros((1280, 720, 3), dtype=np.uint8)
        _, scale, left, top = ObjectPerceptionNode.letterbox(img, 640)
        assert scale == pytest.approx(0.5, abs=0.01)

    def test_padding_color(self):
        """Padding area should be gray (114)."""
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        canvas, _, _, top = ObjectPerceptionNode.letterbox(img, 640)
        if top > 0:
            assert canvas[0, 0, 0] == 114

    def test_content_preserved(self):
        """Non-padding area should contain the resized image."""
        img = np.full((480, 640, 3), 200, dtype=np.uint8)
        canvas, scale, left, top = ObjectPerceptionNode.letterbox(img, 640)
        nh, nw = int(480 * scale), int(640 * scale)
        center_y = top + nh // 2
        center_x = left + nw // 2
        assert canvas[center_y, center_x, 0] == 200


# ------------------------------------------------------------------
# Rescale bbox (reverse letterbox)
# ------------------------------------------------------------------
class TestRescaleBbox:
    def test_identity(self):
        """No padding, scale=1 should return same coords."""
        x1, y1, x2, y2 = ObjectPerceptionNode.rescale_bbox(
            100, 100, 200, 200, 1.0, 0, 0, 640, 480
        )
        assert (x1, y1, x2, y2) == (100, 100, 200, 200)

    def test_with_scale_and_padding(self):
        """scale=0.5, pad_left=80, pad_top=0 → coords should be doubled and shifted."""
        x1, y1, x2, y2 = ObjectPerceptionNode.rescale_bbox(
            130, 50, 230, 150, 0.5, 80, 0, 1280, 720
        )
        assert x1 == 100
        assert y1 == 100
        assert x2 == 300
        assert y2 == 300

    def test_clamp_to_image(self):
        """Coords outside image should be clamped."""
        x1, y1, x2, y2 = ObjectPerceptionNode.rescale_bbox(
            -10, -10, 700, 700, 1.0, 0, 0, 640, 480
        )
        assert x1 == 0
        assert y1 == 0
        assert x2 == 639
        assert y2 == 479

    def test_returns_python_int(self):
        """Must return Python int, not np.int32, for JSON serialization."""
        x1, y1, x2, y2 = ObjectPerceptionNode.rescale_bbox(
            100.5, 100.5, 200.5, 200.5, 1.0, 0, 0, 640, 480
        )
        assert type(x1) is int
        assert type(y1) is int
        assert type(x2) is int
        assert type(y2) is int


# ------------------------------------------------------------------
# Roundtrip: letterbox → rescale should recover original coords
# ------------------------------------------------------------------
class TestRoundtrip:
    def test_letterbox_rescale_roundtrip(self):
        """A point in the original image should survive letterbox → rescale."""
        orig_h, orig_w = 480, 640
        img = np.zeros((orig_h, orig_w, 3), dtype=np.uint8)
        _, scale, pad_left, pad_top = ObjectPerceptionNode.letterbox(img, 640)

        # Original bbox
        ox1, oy1, ox2, oy2 = 100, 50, 300, 250

        # Forward: original → letterbox space
        lx1 = ox1 * scale + pad_left
        ly1 = oy1 * scale + pad_top
        lx2 = ox2 * scale + pad_left
        ly2 = oy2 * scale + pad_top

        # Reverse: letterbox → original
        rx1, ry1, rx2, ry2 = ObjectPerceptionNode.rescale_bbox(
            lx1, ly1, lx2, ly2, scale, pad_left, pad_top, orig_w, orig_h
        )

        assert abs(rx1 - ox1) <= 1
        assert abs(ry1 - oy1) <= 1
        assert abs(rx2 - ox2) <= 1
        assert abs(ry2 - oy2) <= 1


# ------------------------------------------------------------------
# Event dedup / cooldown
# ------------------------------------------------------------------
class TestDedup:
    """Test the cooldown dict logic without ROS2 (extract the core logic)."""

    def test_new_class_emits_event(self):
        cooldowns = {}
        cooldown_sec = 5.0
        now = time.time()

        det = {"class_name": "cup", "confidence": 0.9, "bbox": [0, 0, 10, 10]}
        last = cooldowns.get(det["class_name"], 0.0)
        should_emit = (now - last) >= cooldown_sec
        if should_emit:
            cooldowns[det["class_name"]] = now

        assert should_emit is True

    def test_same_class_within_cooldown_skipped(self):
        cooldowns = {"cup": time.time()}
        cooldown_sec = 5.0
        now = time.time()

        det = {"class_name": "cup", "confidence": 0.9, "bbox": [0, 0, 10, 10]}
        last = cooldowns.get(det["class_name"], 0.0)
        should_emit = (now - last) >= cooldown_sec

        assert should_emit is False

    def test_different_class_emits(self):
        cooldowns = {"cup": time.time()}
        cooldown_sec = 5.0
        now = time.time()

        det = {"class_name": "person", "confidence": 0.8, "bbox": [0, 0, 10, 10]}
        last = cooldowns.get(det["class_name"], 0.0)
        should_emit = (now - last) >= cooldown_sec

        assert should_emit is True

    def test_expired_cooldown_re_emits(self):
        cooldowns = {"cup": time.time() - 10.0}
        cooldown_sec = 5.0
        now = time.time()

        det = {"class_name": "cup", "confidence": 0.9, "bbox": [0, 0, 10, 10]}
        last = cooldowns.get(det["class_name"], 0.0)
        should_emit = (now - last) >= cooldown_sec

        assert should_emit is True


# ------------------------------------------------------------------
# Event JSON schema
# ------------------------------------------------------------------
class TestEventSchema:
    def test_schema_structure(self):
        event = {
            "stamp": time.time(),
            "event_type": "object_detected",
            "objects": [
                {"class_name": "cup", "confidence": 0.9, "bbox": [10, 20, 100, 200]},
                {"class_name": "person", "confidence": 0.85, "bbox": [50, 50, 300, 400]},
            ],
        }
        s = json.dumps(event)
        parsed = json.loads(s)

        assert parsed["event_type"] == "object_detected"
        assert isinstance(parsed["stamp"], float)
        assert isinstance(parsed["objects"], list)
        assert len(parsed["objects"]) == 2

    def test_bbox_is_list_of_int(self):
        event = {
            "stamp": time.time(),
            "event_type": "object_detected",
            "objects": [
                {"class_name": "chair", "confidence": 0.7, "bbox": [10, 20, 100, 200]},
            ],
        }
        s = json.dumps(event)
        parsed = json.loads(s)
        bbox = parsed["objects"][0]["bbox"]
        assert len(bbox) == 4
        for v in bbox:
            assert isinstance(v, int)
