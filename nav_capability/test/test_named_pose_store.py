"""named_pose_store tests."""
import json

import pytest

from nav_capability.lib.named_pose_store import (
    NamedPose,
    NamedPoseStore,
    NamedPoseNotFound,
)


@pytest.fixture
def sample_file(tmp_path):
    p = tmp_path / "named_poses.json"
    p.write_text(json.dumps({
        "schema_version": 1,
        "map_id": "m1",
        "poses": {
            "home": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "kitchen": {"x": 1.5, "y": 0.5, "yaw": 1.57},
        },
    }))
    return str(p)


def test_load_and_lookup(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    pose = store.lookup("home")
    assert isinstance(pose, NamedPose)
    assert pose.x == 0.0


def test_lookup_other(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    pose = store.lookup("kitchen")
    assert pose.x == 1.5 and pose.yaw == 1.57


def test_missing_lookup_raises_with_available(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    with pytest.raises(NamedPoseNotFound) as exc:
        store.lookup("garage")
    msg = str(exc.value)
    assert "garage" in msg
    assert "home" in msg or "kitchen" in msg


def test_list_names(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    assert sorted(store.list_names()) == ["home", "kitchen"]


def test_unknown_schema_version_fails(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"schema_version": 99, "map_id": "x", "poses": {}}))
    with pytest.raises(ValueError, match="schema_version"):
        NamedPoseStore.from_file(str(p))


def test_map_id(sample_file):
    store = NamedPoseStore.from_file(sample_file)
    assert store.map_id == "m1"
