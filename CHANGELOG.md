# Changelog

All notable changes to PawAI are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-06-23 — First public release

The repository was repackaged into a clean, public, Clean-Architecture ROS2
workspace built on a fork of
[abizovnuralem/go2_ros2_sdk](https://github.com/abizovnuralem/go2_ros2_sdk).

### Added
- Bilingual top-level README ([English](README.md) / [中文](README.zh.md)) with a
  Mermaid three-layer Clean-Architecture diagram, package table, hardware
  checklist and new-user bring-up path.
- `SECURITY.md` (private vulnerability reporting + deployment guidance).
- `docs/architecture/` — Clean-Architecture documentation layout
  (`brain/`, `perception/`, `speech/`, `studio/`, `navigation/`, `specs/`).
- `archive/` — a `COLCON_IGNORE`-marked zone for deprecated packages/scripts.

### Changed
- Consolidated to **10 core ROS2 packages** across the Interface, Driver,
  Perception, Decision and Capability layers.
- Unified package licenses: in-house packages → **BSD-2-Clause** (matching the
  root `LICENSE`); `go2_robot_sdk` → **Apache-2.0** (matching upstream).
- Reorganised `docs/` so that only current truth-source docs live at clean
  paths; process-exhaust was archived.

### Removed
- Archived two vestigial LiDAR packages (`lidar_processor`,
  `lidar_processor_cpp`) and removed their dead launch wiring.
- Removed internal-only material from the public tree (historical doc archive,
  internal security ledger, team-assignment notes).

### Security
- Scrubbed private network details and personal information (Tailscale/LAN IPs,
  GPU-server credentials, personal paths, usernames/hostnames) from the public
  surface. Example values are now placeholders or RFC-5737 / TEST-NET ranges.
