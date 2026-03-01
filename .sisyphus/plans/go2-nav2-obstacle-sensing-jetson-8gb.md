# Go2 Nav2 Obstacle Sensing Combos (Jetson Orin Nano 8GB)

## TL;DR
> **Summary**: Keep LiDAR-derived `/scan` as the primary obstacle source; add Intel RealSense D435 depth as a near-field gap filler by converting depth to a secondary LaserScan and fusing it into Nav2 *local* costmap only.
> **Deliverables**: Launch-optional D435 + depth->scan pipeline; Nav2 params variant for dual-scan local costmap; verification gates and rollback.
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: Add optional RealSense launch → depth->scan topic → Nav2 local costmap dual-source → on-robot validation

## Context
### Original Request
- “目前有哪些方案？Go2 雷達 / Go2 相機 / Intel RealSense D435 怎麼組合比較好？要能跑在 Jetson Orin Nano SUPER Dev Kit 8GB。仔細調查。”

### Interview Summary
- Top priority hazards: **Low/Thin obstacles** (chair legs, small boxes, poles).

### Metis Review (gaps addressed)
- Add explicit TF/topic-rate/compute guardrails and rollback.
- Avoid pushing D435 into global costmap; keep it local-only.
- Prefer depth->LaserScan over depth pointcloud voxel layer for Jetson 8GB.

## Work Objectives
### Core Objective
- Provide a compute-safe, robust sensor combination for Nav2 local obstacle avoidance on Jetson Orin Nano 8GB using existing Go2 LiDAR pipeline + optional D435.

### Deliverables
- D1. Launch-optional RealSense D435 bringup integrated into `go2_robot_sdk/launch/robot.launch.py` and `go2_robot_sdk/launch/robot_cpp.launch.py`.
- D2. Launch-optional `depthimage_to_laserscan` node producing `/realsense/scan`.
- D3. New Nav2 parameter file for dual-scan local costmap fusion (LiDAR `/scan` + D435 `/realsense/scan`), with depth marking-only.
- D4. Verification gates (commands + pass/fail criteria) and rollback steps to disable D435 cleanly.

### Definition of Done (agent-verifiable)
- `ros2 launch go2_robot_sdk robot.launch.py slam:=false nav2:=true use_realsense:=false` continues to work (baseline unchanged).
- `ros2 launch go2_robot_sdk robot.launch.py slam:=false nav2:=true use_realsense:=true` produces:
  - `/camera/camera/depth/image_rect_raw` at a stable rate (target ≥ 10 Hz).
  - `/realsense/scan` at a stable rate (target ≥ 5 Hz).
  - Nav2 local costmap updates remain stable (target ≥ 5 Hz) and navigation remains controllable.
- Under `use_realsense:=true`, D435 contributes obstacles to local costmap (detect thin/low obstacles) without causing costmap lockups or controller oscillations.

### Must Have
- LiDAR remains the primary safety source; D435 is additive and can be disabled at runtime.
- Local costmap fuses LiDAR + D435 scan; global costmap remains LiDAR-only (static + LiDAR + inflation).
- Depth-derived scan is **marking-only** by default; clearing remains from LiDAR.

### Must NOT Have
- Do NOT add RGB camera perception into Nav2 collision-prevention loop.
- Do NOT enable D435 pointcloud / voxel-layer by default on Jetson 8GB.
- Do NOT change default behavior when `use_realsense:=false`.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after (runtime gates) — ROS2 runtime verification + topic/TF checks.
- Evidence policy: capture command outputs to `.sisyphus/evidence/` for each task.

## Execution Strategy
### Parallel Execution Waves
Wave 1: RealSense + depth->scan plumbing + params-file wiring
Wave 2: On-robot verification gates + tuning + documentation/rollback

### Dependency Matrix (full, all tasks)
- T1 blocks T3/T4/T5
- T2 blocks T4
- T3 blocks T5
- T4 blocks T6

### Agent Dispatch Summary
- Wave 1: 4 tasks (unspecified-high / deep)
- Wave 2: 4 tasks (unspecified-high)

## TODOs
> Implementation + Verification = ONE task.

- [ ] T1. Add `use_realsense` launch flag + RealSense URDF option

  **What to do**:
  - Add launch arg `use_realsense` (default `false`) in `go2_robot_sdk/launch/robot.launch.py`.
  - Add launch arg `use_realsense` (default `false`) in `go2_robot_sdk/launch/robot_cpp.launch.py`.
  - Add a new URDF path entry for `go2_with_realsense.urdf` (single-robot only).
  - In single-robot mode, launch **exactly one** `robot_state_publisher`:
    - `use_realsense=false` → load `go2_robot_sdk/urdf/go2.urdf`
    - `use_realsense=true` → load `go2_robot_sdk/urdf/go2_with_realsense.urdf`
  - Keep multi-robot behavior unchanged (`multi_go2.urdf`).

  **Must NOT do**:
  - Do not change default URDF when `use_realsense=false`.
  - Do not attempt multi-robot + RealSense in this iteration.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — launch logic across multiple files
  - Skills: []

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T2,T4 | Blocked By: —

  **References**:
  - Launch pattern: `go2_robot_sdk/launch/robot.launch.py`
  - Launch pattern: `go2_robot_sdk/launch/robot_cpp.launch.py`
  - URDF: `go2_robot_sdk/urdf/go2_with_realsense.urdf`
  - TF note (`front_camera` vs `camera_link`): `docs/setup/slam_nav/README.md`

  **Acceptance Criteria**:
  - [ ] `python3 -m py_compile go2_robot_sdk/launch/robot.launch.py` succeeds
  - [ ] `python3 -m py_compile go2_robot_sdk/launch/robot_cpp.launch.py` succeeds

  **QA Scenarios**:
  ```
  Scenario: URDF selection toggles as expected
    Tool: Bash
    Steps:
      1) Launch with use_realsense:=false and confirm TF does NOT include camera_link
      2) Launch with use_realsense:=true and confirm TF includes camera_link
    Expected:
      - camera_link appears only when use_realsense:=true
    Evidence: .sisyphus/evidence/task-T1-urdf-toggle.txt

  Scenario: Regression check for default behavior
    Tool: Bash
    Steps:
      1) Launch Gate C via scripts/start_nav2_localization.sh (baseline path)
    Expected:
      - Launch succeeds without requiring RealSense packages
    Evidence: .sisyphus/evidence/task-T1-baseline-launch.txt
  ```

  **Commit**: YES | Message: `feat(launch): add use_realsense flag and URDF toggle` | Files: `go2_robot_sdk/launch/robot.launch.py`, `go2_robot_sdk/launch/robot_cpp.launch.py`

- [ ] T2. Add optional RealSense D435 driver bringup (depth-only, compute-safe defaults)

  **What to do**:
  - Add a conditional RealSense bringup in `go2_robot_sdk/launch/robot.launch.py` guarded by `use_realsense`.
  - Add the same in `go2_robot_sdk/launch/robot_cpp.launch.py`.
  - Installation requirement (document + verify): `sudo apt install ros-humble-realsense2-camera`.
  - Default launch behavior target: depth stream enabled, pointcloud disabled.
  - After installation, verify the RealSense launch file exists at runtime:
    - `ros2 launch realsense2_camera rs_launch.py` must be launchable.

  **Must NOT do**:
  - Do not enable pointcloud output by default on Jetson 8GB.
  - Do not add image display / compression nodes (keep nav stack minimal).

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — ROS2 launch integration + dependency handling
  - Skills: []

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T3 | Blocked By: T1

  **References**:
  - RealSense example include: `ros-mcp-server/examples/8_images/ros_mcp_images_demo_realsense.launch.py`
  - Jetson gate execution patterns: `scripts/start_nav2_localization.sh`, `start_go2_wired_webrtc.sh`

  **Acceptance Criteria**:
  - [ ] `ros2 pkg prefix realsense2_camera` succeeds after installation
  - [ ] When `use_realsense:=true`, topic exists: `/camera/camera/depth/image_rect_raw`
  - [ ] `timeout 10s zsh scripts/ros2w.sh topic hz /camera/camera/depth/image_rect_raw` reports a stable rate (target ≥ 10 Hz)

  **QA Scenarios**:
  ```
  Scenario: RealSense depth stream comes up
    Tool: Bash
    Steps:
      1) Install driver package (apt)
      2) Launch go2_robot_sdk with use_realsense:=true (Nav2 off for isolation)
      3) Check /camera/camera/depth/image_rect_raw exists and has Hz
    Expected:
      - Depth image publishes at ≥ 10 Hz with no repeated driver restarts
    Evidence: .sisyphus/evidence/task-T2-realsense-depth-hz.txt

  Scenario: No RealSense dependency when disabled
    Tool: Bash
    Steps:
      1) Launch with use_realsense:=false on a system without realsense2_camera installed
    Expected:
      - Launch succeeds; no import/package errors
    Evidence: .sisyphus/evidence/task-T2-disabled-no-deps.txt
  ```

  **Commit**: YES | Message: `feat(realsense): optional D435 bringup for nav stack` | Files: `go2_robot_sdk/launch/robot.launch.py`, `go2_robot_sdk/launch/robot_cpp.launch.py`

- [ ] T3. Add `depthimage_to_laserscan` node producing `/realsense/scan`

  **What to do**:
  - Add a `depthimage_to_laserscan` Node in `go2_robot_sdk/launch/robot.launch.py` guarded by `use_realsense`.
  - Add the same in `go2_robot_sdk/launch/robot_cpp.launch.py`.
  - Remap inputs to match RealSense depth topics:
    - `depth` → `/camera/camera/depth/image_rect_raw`
    - `depth_camera_info` → `/camera/camera/depth/camera_info`
  - Remap output:
    - `scan` → `/realsense/scan`
  - Use Humble-known parameters (from installed package cfg):
    - `scan_time`, `range_min`, `range_max`, `scan_height`, `output_frame`
  - Set `output_frame` to `camera_link` (so TF lookup is consistent with URDF when enabled).

  **Must NOT do**:
  - Do not publish to `/scan` (avoid clobbering LiDAR scan).

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — ROS2 node wiring + remaps
  - Skills: []

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T4 | Blocked By: T2

  **References**:
  - depthimage_to_laserscan default params: `/opt/ros/humble/share/depthimage_to_laserscan/cfg/param.yaml`
  - depthimage_to_laserscan remap names: `/opt/ros/humble/share/depthimage_to_laserscan/launch/depthimage_to_laserscan-launch.py`

  **Acceptance Criteria**:
  - [ ] When `use_realsense:=true`, topic exists: `/realsense/scan`
  - [ ] `timeout 10s zsh scripts/ros2w.sh topic hz /realsense/scan` reports a stable rate (target ≥ 5 Hz)

  **QA Scenarios**:
  ```
  Scenario: Depth converts to LaserScan
    Tool: Bash
    Steps:
      1) Launch with use_realsense:=true (Nav2 off for isolation)
      2) Verify /realsense/scan exists
      3) Verify /realsense/scan ranges are finite near obstacles (not all inf)
    Expected:
      - LaserScan publishes at ≥ 5 Hz and shows obstacle ranges
    Evidence: .sisyphus/evidence/task-T3-depth-scan.txt

  Scenario: TF frame is resolvable
    Tool: Bash
    Steps:
      1) ros2 run tf2_ros tf2_echo base_link camera_link
    Expected:
      - Transform available (no repeated lookup failures)
    Evidence: .sisyphus/evidence/task-T3-tf-camera-link.txt
  ```

  **Commit**: YES | Message: `feat(nav2): add depthimage_to_laserscan as /realsense/scan` | Files: `go2_robot_sdk/launch/robot.launch.py`, `go2_robot_sdk/launch/robot_cpp.launch.py`

- [ ] T4. Add Nav2 params variant for dual-scan local costmap fusion (LiDAR + D435)

  **What to do**:
  - Create a new params file: `go2_robot_sdk/config/nav2_params_with_realsense.yaml`.
  - Base it on `go2_robot_sdk/config/nav2_params.yaml` but change costmap obstacle ingestion as follows:
    - Replace `voxel_layer` with `obstacle_layer` (2D) in *local* costmap plugins.
    - Keep global costmap LiDAR-only (static + obstacle + inflation).
    - Configure local `obstacle_layer.observation_sources: scan realsense_scan`.
    - LiDAR source (`scan`): topic `/scan`, `clearing: True`, `marking: True`.
    - D435 source (`realsense_scan`): topic `/realsense/scan`, `clearing: False`, `marking: True`.
  - Wire params selection in launch:
    - `use_realsense=false` → existing `go2_robot_sdk/config/nav2_params.yaml`
    - `use_realsense=true` → `go2_robot_sdk/config/nav2_params_with_realsense.yaml`
    - Implement by duplicating Nav2 include blocks with mutually exclusive conditions (same as URDF strategy).

  **Must NOT do**:
  - Do not feed D435 scan into global costmap.
  - Do not change controller tuning beyond what is required to keep stability.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — YAML + launch wiring across modules
  - Skills: []

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T5,T6 | Blocked By: T1,T3

  **References**:
  - Existing params baseline: `go2_robot_sdk/config/nav2_params.yaml`
  - Existing Gate C launcher: `scripts/start_nav2_localization.sh`
  - Nav2 costmap docs (authoritative): https://docs.nav2.org/configuration/packages/configuring-costmaps.html

  **Acceptance Criteria**:
  - [ ] YAML loads: `python3 -c "import yaml; yaml.safe_load(open('go2_robot_sdk/config/nav2_params_with_realsense.yaml'))"`
  - [ ] With `use_realsense:=true`, Nav2 launches without parameter errors
  - [ ] `/local_costmap/costmap` publishes and updates (target ≥ 5 Hz)

  **QA Scenarios**:
  ```
  Scenario: Dual-scan observation sources are active
    Tool: Bash
    Steps:
      1) Launch Gate C with use_realsense:=true
      2) Confirm /scan and /realsense/scan both publish
      3) Confirm /local_costmap/costmap updates and obstacles appear when either sensor sees an object
    Expected:
      - Costmap updates continuously; obstacles appear without freezing
    Evidence: .sisyphus/evidence/task-T4-dual-scan-costmap.txt

  Scenario: Depth cannot clear LiDAR obstacles (safety guard)
    Tool: Bash
    Steps:
      1) Place obstacle detectable by LiDAR
      2) Occlude depth camera so it cannot see it
      3) Ensure obstacle remains in costmap until LiDAR clears
    Expected:
      - No false clearing from depth source
    Evidence: .sisyphus/evidence/task-T4-mark-only-safety.txt
  ```

  **Commit**: YES | Message: `chore(nav2): add dual-scan params and wire use_realsense` | Files: `go2_robot_sdk/config/nav2_params_with_realsense.yaml`, `go2_robot_sdk/launch/robot.launch.py`, `go2_robot_sdk/launch/robot_cpp.launch.py`

- [ ] T5. Jetson runtime guardrails (rates + compute) and rollback procedure

  **What to do**:
  - Extend `docs/refactor/slam-nav2.md` with a new section: “D435 depth->scan local obstacle fusion (Gate C extension)”.
  - Add a deterministic rollback:
    - Disable RealSense by setting `use_realsense:=false` (and/or `ENABLE_VIDEO=false` remains unaffected).
  - Add a runtime guardrail checklist (all command-based):
    - `timeout 10s zsh scripts/ros2w.sh topic hz /scan`
    - `timeout 10s zsh scripts/ros2w.sh topic hz /realsense/scan`
    - `timeout 10s zsh scripts/ros2w.sh topic hz /local_costmap/costmap`
    - `timeout 10s tegrastats`
  - Define pass thresholds (Jetson 8GB):
    - `/scan` ≥ 5 Hz
    - `/realsense/scan` ≥ 5 Hz
    - `local_costmap` ≥ 5 Hz
    - RAM < 7.0 GB sustained, no single CPU core pegged for >30s

  **Must NOT do**:
  - Do not add new monitoring daemons; keep as documented commands.

  **Recommended Agent Profile**:
  - Category: `writing` — doc update with precise commands
  - Skills: []

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T6 | Blocked By: T4

  **References**:
  - Existing gate doc: `docs/refactor/slam-nav2.md`
  - Existing rate expectations: `scripts/check_gate_c_rates.sh`

  **Acceptance Criteria**:
  - [ ] Doc section contains exact commands + thresholds + rollback steps

  **QA Scenarios**:
  ```
  Scenario: Rollback is one toggle
    Tool: Bash
    Steps:
      1) Launch with use_realsense:=true (verify /realsense/scan exists)
      2) Relaunch with use_realsense:=false
    Expected:
      - /realsense/scan disappears; Nav2 continues LiDAR-only
    Evidence: .sisyphus/evidence/task-T5-rollback.txt

  Scenario: Guardrail checks are copy-paste runnable
    Tool: Bash
    Steps:
      1) Execute each command block exactly as documented
    Expected:
      - Commands succeed without edits (paths valid)
    Evidence: .sisyphus/evidence/task-T5-commands-runnable.txt
  ```

  **Commit**: YES | Message: `docs(nav2): add gate C realsense fusion guardrails` | Files: `docs/refactor/slam-nav2.md`

- [ ] T6. On-robot validation: “low/thin obstacle” improvement without destabilizing Nav2

  **What to do**:
  - Run A/B validation on Jetson:
    - A: LiDAR-only (use_realsense:=false)
    - B: LiDAR + D435 scan (use_realsense:=true)
  - Test setup must include at least one thin/low obstacle that LiDAR tends to miss (e.g., chair leg cluster or thin pole) and one normal obstacle (box).
  - For each run: send the same short navigation goals (repeatable) and record:
    - success/failure
    - max observed `cmd_vel` spikes
    - whether local costmap shows obstacle from the thin object

  **Must NOT do**:
  - Do not increase speed beyond current safety limits for these tests.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — runtime QA + log capture
  - Skills: []

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: — | Blocked By: T5

  **References**:
  - Gate C launcher: `scripts/start_nav2_localization.sh`
  - Goal test helper: `scripts/nav2_goal_autotest.py`

  **Acceptance Criteria**:
  - [ ] In B (use_realsense:=true), local costmap registers the thin/low obstacle in ≥ 8/10 trials.
  - [ ] No regressions vs A in controller stability (no new oscillatory spinning; navigation success rate not worse).

  **QA Scenarios**:
  ```
  Scenario: A/B trial run
    Tool: Bash
    Steps:
      1) Launch Gate C use_realsense:=false, run 10 short-goal trials
      2) Launch Gate C use_realsense:=true, run the same 10 trials
      3) Capture hz + tegrastats for each run
    Expected:
      - B improves thin/low obstacle detection without destabilizing navigation
    Evidence: .sisyphus/evidence/task-T6-ab-results.md

  Scenario: Failure mode (D435 unplug)
    Tool: Bash
    Steps:
      1) Start use_realsense:=true, then disconnect D435
      2) Observe whether the system remains controllable (LiDAR still runs)
    Expected:
      - LiDAR topics continue; operator can rollback by relaunching with use_realsense:=false
    Evidence: .sisyphus/evidence/task-T6-unplug-behavior.txt
  ```

  **Commit**: NO

- [ ] T7. Final cleanup: ensure configs remain minimal and defaults stable

  **What to do**:
  - Ensure `scripts/start_nav2_localization.sh` and `start_go2_wired_webrtc.sh` do not change behavior unless explicitly enabled.
  - Optionally add documented example commands (not new defaults):
    - `use_realsense:=true rviz2:=false foxglove:=false` for headless Jetson.

  **Must NOT do**:
  - Do not change existing Gate C defaults unless required for correctness.

  **Recommended Agent Profile**:
  - Category: `writing` — minimal doc touch-ups
  - Skills: []

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: — | Blocked By: T6

  **References**:
  - `scripts/start_nav2_localization.sh`
  - `start_go2_wired_webrtc.sh`

  **Acceptance Criteria**:
  - [ ] Baseline commands in docs remain valid and unchanged

  **QA Scenarios**:
  ```
  Scenario: Default Gate C still works
    Tool: Bash
    Steps:
      1) Run scripts/start_nav2_localization.sh without RealSense
    Expected:
      - System launches and publishes /scan and /amcl_pose
    Evidence: .sisyphus/evidence/task-T7-baseline-still-works.txt
  ```

  **Commit**: YES | Message: `docs(nav2): document use_realsense launch examples` | Files: `docs/refactor/slam-nav2.md`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Runtime QA (Jetson) — unspecified-high
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Prefer 3 commits:
  1) `feat(nav2): add optional realsense depth->scan pipeline`
  2) `chore(nav2): add dual-scan params variant and defaults`
  3) `docs(nav2): add jetson realsense obstacle-avoidance gates`

## Success Criteria
- Jetson Orin Nano 8GB runs Gate C navigation with stable LiDAR rates, and with `use_realsense:=true` also avoids low/thin obstacles more reliably than LiDAR-only, without destabilizing control.
