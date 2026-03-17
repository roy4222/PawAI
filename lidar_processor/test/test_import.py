"""Smoke tests: verify entry-point modules are importable."""


def test_import_lidar_to_pointcloud():
    from lidar_processor import lidar_to_pointcloud_node  # noqa: F401


def test_import_pointcloud_aggregator():
    from lidar_processor import pointcloud_aggregator_node  # noqa: F401
