# AGENTS.md

Guidance for AI coding agents (Codex, Claude Code, etc.) working in this repo.
Humans should start with [`README.md`](README.md); the authoritative build/run
matrix, conventions and known pitfalls live in [`CLAUDE.md`](CLAUDE.md).

## What this is

**PawAI** — a multimodal embodied-interaction robot dog on the Unitree Go2 Pro,
built as a single ROS2 (Humble) workspace following **Clean Architecture**.
The repo root *is* the colcon workspace `src`.

## Layout

```
├── go2_interfaces/         # Contracts — ROS2 msg/srv/action
├── pawai_contracts/        # Contracts — ROS-free domain contracts (skill registry, policy, trace)
├── go2_robot_sdk/          # Driver — Go2 WebRTC driver (domain/application/infrastructure/presentation)
├── face_perception/        # Perception — face detection + identity
├── vision_perception/      # Perception — gesture + pose
├── object_perception/      # Perception — YOLO26n object detection
├── speech_processor/       # Speech I/O — ASR / intent / LLM bridge / TTS
├── pawai_brain/            # Decision — LangGraph conversation/decision engine
├── interaction_executive/  # Decision — state machine, safety gate, single action arbiter
├── nav_capability/         # Capability — navigation actions (experimental)
├── pawai-studio/           # Operator web UI (Next.js frontend + FastAPI gateway)
├── benchmarks/             # Model-selection benchmark framework
├── scripts/                # Demo launchers, cleanup, smoke tests
├── tools/pawai_cli/        # Team CLI (deploy / demo / status)
├── docs/                   # Documentation (see docs/README.md)
└── archive/                # Deprecated packages & scripts (COLCON_IGNORE)
```

## Conventions

- **Respond in Traditional Chinese** (繁體中文).
- **`uv pip install`**, never bare `pip install`.
- ROS2 Humble + colcon. Rebuild after Python changes: `colcon build --packages-select <pkg>` then re-`source install/setup.bash` (`.zsh` on the Jetson).
- Clean Architecture: `go2_robot_sdk/.../domain` must have **no ROS2 deps**.
- `interaction_executive` is the single exit to the robot body; `pawai_brain`
  only proposes. The two never import each other (both depend on `pawai_contracts`).
- Don't suppress exceptions silently; log via the ROS2 logger or re-raise.

## Dev topology

Code is edited on a Linux/WSL2 dev machine and run on a Jetson Orin Nano
(ROS2 runtime, GPU, hardware). Source of truth is the dev machine; sync to the
Jetson with `tools/sync/`, then `colcon build` on the Jetson. See
[`CLAUDE.md`](CLAUDE.md) for the full workflow and the `pawai` CLI.

## Quality gates

`git commit` runs a pre-commit hook (py_compile + topic-contract check +
scoped tests). CI (`.github/workflows/`) runs lint, pure-Python tests and a
colcon build of the core packages. Keep both green.
