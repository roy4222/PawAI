from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class DoctorCache:
    """File-backed JSON cache with a TTL — used to avoid 5x SSH probes from a team."""

    def __init__(self, path: Path, ttl_seconds: int):
        self.path = path
        self.ttl = ttl_seconds

    def read(self) -> Optional[dict]:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        written_at = payload.get("_cached_at", 0)
        if time.time() - written_at > self.ttl:
            return None
        # Strip metadata before returning
        return {k: v for k, v in payload.items() if k != "_cached_at"}

    def write(self, data: dict) -> None:
        payload = dict(data)
        payload["_cached_at"] = time.time()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload))
