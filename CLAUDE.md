# CLAUDE.md

Public-facing guidance for Claude Code and other AI coding agents working in this repository.
For humans, start with [`README.md`](README.md) and [`docs/README.md`](docs/README.md).

## Language And Tooling

- Reply in Traditional Chinese unless the user asks otherwise.
- Use `uv pip install` instead of bare `pip install`.
- Prefer `rg` / `rg --files` for search.
- Keep edits scoped. Do not revive archived packages or scripts unless the user explicitly asks.
- Log or re-raise exceptions; do not silently suppress failures.

## Repository Shape

This repository is a ROS2 Humble workspace for PawAI, a Unitree Go2 Pro embodied-interaction robot dog.
The active system is intentionally small:

| Layer | Packages / folders | Role |
|---|---|---|
| Contracts | `go2_interfaces`, `pawai_contracts` | ROS2 and ROS-free shared contracts |
| Driver | `go2_robot_sdk` | Go2 WebRTC driver and robot-facing services |
| Perception | `face_perception`, `vision_perception`, `object_perception` | Face, pose/gesture and object events |
| Speech | `speech_processor` | ASR, intent bridge and TTS |
| Decision | `pawai_brain`, `interaction_executive` | Brain policy and single robot-action arbiter |
| Navigation | `nav_capability` | Experimental navigation capability surface |
| Operator UI | `pawai-studio` | Studio frontend and gateway |
| Tooling | `tools/pawai_cli`, `scripts`, `benchmarks` | Team CLI, launchers, tests and model benchmarks |

Deprecated code stays under [`archive/`](archive/README.md), which is excluded from colcon by `COLCON_IGNORE`.
The removed internal document archive is not part of the public tree.

## Architecture Rules

- `go2_robot_sdk/go2_robot_sdk/domain` must not import ROS2 or presentation-layer code.
- `pawai_brain` proposes intent; `interaction_executive` owns safety gating and robot actions.
- Keep robot-body commands flowing through one explicit arbiter. Avoid extra `/cmd_vel` or `/webrtc_req` publishers.
- Treat navigation and motion claims as evidence-bound. If hardware/HITL evidence is missing, document the capability as experimental or insufficiently verified.
- Public docs should point to active truth sources: `docs/README.md`, `docs/contracts/`, `docs/architecture/`, `docs/runbook/`, and `docs/adr/`.

## Development Topology

Source of truth is the WSL workspace:

```bash
cd /home/roy422/newLife/elder_and_dog
```

Runtime, GPU and ROS2 hardware checks run on the Jetson:

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && <command>"
```

Use the one-way sync helper before Jetson builds:

```bash
~/sync start
~/sync status
~/sync once
~/sync stop
```

Do not edit source directly on the Jetson. Build artifacts belong on the Jetson, not in git.

## Common Commands

```bash
# Local / WSL
rg --files
python3 -m compileall <package-or-script>
python3 scripts/ci/check_topic_contracts.py

# Jetson / ROS2
source /opt/ros/humble/setup.bash
source install/setup.bash
colcon build --packages-select go2_robot_sdk
colcon test --packages-select go2_robot_sdk

# CLI
pawai doctor
pawai status
pawai demo start
pawai demo stop
pawai docs brain
pawai contract check
```

## Verification Expectations

Use the narrowest check that proves the change:

- Python source change: syntax check plus the package's focused pytest set.
- ROS2 interface/topic change: `scripts/ci/check_topic_contracts.py` plus affected tests.
- Driver or launch change: package tests and, when hardware behavior changes, a Jetson/HITL note.
- Documentation-only change: tracked markdown link check or direct proof that touched links resolve.

Never claim hardware or robot-motion readiness from local tests alone.

## Documentation Map

- Project overview: [`README.md`](README.md)
- Documentation index: [`docs/README.md`](docs/README.md)
- Architecture: [`docs/architecture/README.md`](docs/architecture/README.md)
- Contracts: [`docs/contracts/interaction_contract.md`](docs/contracts/interaction_contract.md)
- Runbooks: [`docs/runbook/README.md`](docs/runbook/README.md)
- ADRs: [`docs/adr/README.md`](docs/adr/README.md)
- Deprecated packages/scripts: [`archive/README.md`](archive/README.md)