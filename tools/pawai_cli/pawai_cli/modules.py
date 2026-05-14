from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModuleInfo:
    key: str
    title: str
    packages: tuple[str, ...]
    docs: tuple[str, ...]
    tests: tuple[str, ...]
    logs: tuple[str, ...]
    go2_access: str
    notes: tuple[str, ...] = ()


MODULES: dict[str, ModuleInfo] = {
    "face": ModuleInfo(
        key="face",
        title="人臉辨識",
        packages=("face_perception",),
        docs=("docs/pawai-brain/architecture/0511/face.md",),
        tests=("python3 -m pytest face_perception/test -v",),
        logs=("demo:face",),
        go2_access="none",
        notes=("YuNet + SFace + face_db sync",),
    ),
    "speech": ModuleInfo(
        key="speech",
        title="語音功能",
        packages=("speech_processor",),
        docs=("docs/pawai-brain/architecture/0511/speech.md",),
        tests=("python3 -m pytest speech_processor/test -v",),
        logs=("demo:asr", "demo:tts"),
        go2_access="TTS via Megaphone",
        notes=("ASR provider chain + TTS fallback chain",),
    ),
    "gesture": ModuleInfo(
        key="gesture",
        title="手勢辨識",
        packages=("vision_perception",),
        docs=("docs/pawai-brain/architecture/0511/gesture.md",),
        tests=("python3 -m pytest vision_perception/test -v -k gesture",),
        logs=("demo:vision",),
        go2_access="indirect via interaction skills",
        notes=("Shares vision_perception with pose/object perception cache.",),
    ),
    "pose": ModuleInfo(
        key="pose",
        title="姿勢辨識",
        packages=("vision_perception",),
        docs=("docs/pawai-brain/architecture/0511/pose.md",),
        tests=("python3 -m pytest vision_perception/test -v -k pose",),
        logs=("demo:vision",),
        go2_access="fallen_alert can stop Go2",
        notes=("Shares vision_perception with gesture.",),
    ),
    "object": ModuleInfo(
        key="object",
        title="辨識物體",
        packages=("object_perception",),
        docs=("docs/pawai-brain/architecture/0511/object.md",),
        tests=("python3 -m pytest object_perception/test -v",),
        logs=("demo:object",),
        go2_access="none",
        notes=("YOLO26n + HSV color path; brain consumes /event/object_detected.",),
    ),
    "nav": ModuleInfo(
        key="nav",
        title="導航避障功能",
        packages=("go2_robot_sdk",),
        docs=(".claude/skills/nav-avoidance-lane/SKILL.md", "docs/navigation/CLAUDE.md"),
        tests=("python3 -m pytest go2_robot_sdk/test -v",),
        logs=("demo:go2", "nav-cap-demo:nav_action", "reactive-stop:reactive"),
        go2_access="direct motion",
        notes=("Architecture doc not consolidated yet; using lane references.",),
    ),
    "brain": ModuleInfo(
        key="brain",
        title="PawAI Brain",
        packages=("pawai_brain", "interaction_executive"),
        docs=("docs/pawai-brain/architecture/0511/brain.md",),
        tests=(
            "python3 -m pytest pawai_brain/test -v",
            "python3 -m pytest interaction_executive/test -v",
        ),
        logs=("demo:llm", "demo:executive", "pawai_brain:conv_graph"),
        go2_access="via interaction_executive",
        notes=("LangGraph + skill policy + trace.",),
    ),
    "studio": ModuleInfo(
        key="studio",
        title="PawAI Brain x PawAI Studio",
        packages=(),
        docs=(
            ".claude/skills/brain-studio-lane/SKILL.md",
            ".claude/skills/brain-studio-lane/references/runtime-topology.md",
            "pawai-studio/docs",
        ),
        tests=("cd pawai-studio/frontend && npm run lint",),
        logs=("local:/tmp/studio_frontend.log", "demo:gateway"),
        go2_access="none",
        notes=("Frontend/backend/gateway; no colcon package.",),
    ),
}


ALIASES = {
    "vision": "gesture",
    "object-perception": "object",
    "speech-processor": "speech",
    "pawai-brain": "brain",
}


def get_module(name: str) -> ModuleInfo:
    key = ALIASES.get(name, name)
    if key not in MODULES:
        valid = ", ".join(sorted(MODULES))
        raise KeyError(f"unknown module '{name}'. Valid modules: {valid}")
    return MODULES[key]


def existing_docs(module: ModuleInfo, root: Path) -> list[str]:
    return [doc for doc in module.docs if (root / doc).exists()]


_DOC_ALIASES: dict[str, str] = {
    "onboarding": "docs/pawai_cli/team-onboarding.md",
    "contract": "docs/contracts/interaction_contract.md",
}


def arch_doc_path(name: str, root: Path) -> Path | None:
    """Map module name to its architecture/0511/<name>/<name>.md (or alias target)."""
    if name in _DOC_ALIASES:
        path = root / _DOC_ALIASES[name]
        return path if path.exists() else None

    # Module: try architecture/0511/<name>/<name>.md, then architecture/0511/<name>.md
    candidates = [
        root / f"docs/pawai-brain/architecture/0511/{name}/{name}.md",
        root / f"docs/pawai-brain/architecture/0511/{name}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def all_doc_targets() -> list[str]:
    """Names accepted by `pawai docs`."""
    return list(MODULES.keys()) + list(_DOC_ALIASES.keys())
