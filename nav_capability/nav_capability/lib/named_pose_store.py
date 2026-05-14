"""Named pose store: 從 JSON 載入命名 pose，提供 lookup。"""
import json
from dataclasses import dataclass
from typing import Dict, Iterable

SUPPORTED_SCHEMA_VERSIONS = {1}


@dataclass(frozen=True)
class NamedPose:
    x: float
    y: float
    yaw: float


class NamedPoseNotFound(KeyError):
    pass


class NamedPoseStore:
    def __init__(self, map_id: str, poses: Dict[str, NamedPose]):
        self.map_id = map_id
        self._poses = dict(poses)

    @classmethod
    def from_file(cls, path: str) -> "NamedPoseStore":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sv = data.get("schema_version")
        if sv not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version {sv} not supported (require {SUPPORTED_SCHEMA_VERSIONS})"
            )
        map_id = data.get("map_id", "")
        poses = {
            name: NamedPose(x=p["x"], y=p["y"], yaw=p["yaw"])
            for name, p in data.get("poses", {}).items()
        }
        return cls(map_id=map_id, poses=poses)

    def lookup(self, name: str) -> NamedPose:
        if name not in self._poses:
            available = sorted(self._poses.keys())
            raise NamedPoseNotFound(
                f"named pose '{name}' not found; available: {available}"
            )
        return self._poses[name]

    def list_names(self) -> Iterable[str]:
        return list(self._poses.keys())
