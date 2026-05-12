import time
from pathlib import Path
from pawai_cli.cache import DoctorCache


def test_cache_returns_none_when_no_file(tmp_path: Path):
    c = DoctorCache(tmp_path / "cache.json", ttl_seconds=30)
    assert c.read() is None


def test_cache_round_trip(tmp_path: Path):
    c = DoctorCache(tmp_path / "cache.json", ttl_seconds=30)
    c.write({"status": "green", "topology": ["row1", "row2"]})
    assert c.read() == {"status": "green", "topology": ["row1", "row2"]}


def test_cache_expires(tmp_path: Path):
    c = DoctorCache(tmp_path / "cache.json", ttl_seconds=0)  # immediate expiry
    c.write({"x": 1})
    time.sleep(0.05)
    assert c.read() is None
