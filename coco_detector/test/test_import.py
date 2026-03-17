"""Smoke tests: verify entry-point modules are importable."""


def test_import_coco_detector_node():
    from coco_detector import coco_detector_node  # noqa: F401
