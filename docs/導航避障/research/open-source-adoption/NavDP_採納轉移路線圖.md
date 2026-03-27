# NavDP Transfer Roadmap (Keep ROS2 Humble Nav2 Stable)

Updated: 2026-03-02

## Goal and Guardrails

This roadmap introduces NavDP capabilities into the current project **without replacing** the existing ROS2 Humble Nav2 stack.

Non-negotiables:
- Keep `Nav2 + AMCL + DWB` as primary control path.
- Introduce NavDP in shadow/candidate mode first.
- Promote only after measurable gates pass.
- Any regression triggers immediate rollback to current stable Nav2 path.

Repo baseline references:
- Current Nav2 runtime: `go2_robot_sdk/config/nav2_params.yaml`
- Current localization launch flow: `scripts/start_nav2_localization.sh`
- Existing gate/rate checks: `scripts/check_gate_c_rates.sh`
- Existing short-distance repeat test: `scripts/nav2_goal_autotest.py`
- Existing stability plan style: `docs/導航避障/落地計畫_v2.md`

## Phase 0 (Immediate, 2-3 days): Integration Safety Shell

Objective: make NavDP testable without touching the primary control loop.

Scope:
- Add a NavDP adapter boundary (input/output contract only):
  - Inputs: RGB, depth, optional point-goal.
  - Outputs: candidate trajectory + confidence/score + inference latency.
- Keep Nav2 as sole `/cmd_vel` owner in production mode.
- Add mode switch policy:
  - `nav_mode=nav2_primary` (default)
  - `nav_mode=navdp_shadow` (observe only, no actuation)

Measurable gate (G0):
- 100% of field runs remain in `nav2_primary` by default.
- Shadow logs captured for at least 30 runs with no impact on Nav2 success rate.
- Added adapter path causes <= 5% CPU increase during localization runs.

Rollback:
- Disable NavDP process/service and keep launch command unchanged.
- If resource pressure appears, stop NavDP sidecar first; do not modify Nav2 params.

## Phase 1 (Near-term, week 1): Shadow Benchmark Against Real Runs

Objective: compare NavDP proposals against what Nav2 actually executed.

Scope:
- Run NavDP server independently (`NavDP/baselines/navdp/navdp_server.py`) and consume outputs in shadow mode.
- Record per-run metrics:
  - inference latency p50/p95
  - candidate trajectory feasibility vs local costmap
  - disagreement rate with executed Nav2 path
  - near-obstacle risk proxy (minimum projected clearance)
- Keep existing test cadence (0.5m/0.8m repeats) and current gate scripts.

Measurable gate (G1):
- Nav2 safety baseline preserved: 0 collision across 50 short-range runs.
- NavDP shadow latency p95 <= 250 ms on target runtime profile.
- >= 80% of NavDP candidate trajectories are feasibility-valid in current local costmap.
- No increase in ABORT rate vs last stable week.

Rollback:
- If any G1 metric fails, freeze NavDP at shadow-only and continue Nav2 tuning.
- Archive failed traces for offline analysis; no online behavior change.

## Phase 2 (Near-term, week 2-3): Guarded Assist Mode (Not Replacement)

Objective: allow NavDP to assist only in bounded scenarios.

Scope:
- Introduce "assist" policy:
  - NavDP suggests short horizon waypoint/heading.
  - Nav2 still performs planning/control and can reject unsafe hints.
- Activation constraints:
  - only in mapped, low-dynamic test zones
  - speed cap unchanged from stable Nav2 profile
  - watchdog timeout and freshness gate active
- Recovery policy fixed:
  - stop -> clear costmap -> rotate -> retry once -> fail-safe stop

Measurable gate (G2):
- 0 collision across 100 short-range runs.
- Success rate >= 95%, ABORT <= 5% (same acceptance as stable plan).
- Assist acceptance ratio >= 60% (otherwise no practical value).
- On watchdog/freshness failure, stop reaction <= 300 ms.

Rollback:
- Single flag switches assist off (`nav_mode=nav2_primary`).
- Revert to last-known-good launch/params package (tag each test day).

## Phase 3 (Long-term, month 2+): Limited Production Pilot

Objective: deploy NavDP-assisted navigation in constrained real tasks.

Scope:
- Use NavDP assist only for approved task classes (e.g., corridor traversal / simple point-goal).
- Keep Nav2 deterministic safety envelope and final motion authority.
- Add weekly drift checks:
  - latency drift
  - success/abort drift
  - resource drift (CPU/RAM/GPU)

Measurable gate (G3):
- 10 hours cumulative pilot runtime with 0 collision.
- Weekly success >= 95%, ABORT <= 5% sustained for 2 consecutive weeks.
- No persistent thermal throttling or control frequency collapse.

Rollback:
- Immediate downgrade policy: if any weekly gate is breached, switch all robots to `nav2_primary`.
- Keep NavDP data logging active for diagnosis, but no control influence.

## Phase 4 (Long-term, optional): Architecture Upgrade Decision

Decision criteria before broader adoption:
- NavDP assist demonstrates consistent advantage in safety or completion time.
- Operations overhead remains acceptable (on-call burden, debugging complexity).
- Deterministic safety layer remains independent from model quality.

If criteria are unmet:
- Keep NavDP as research/shadow tool.
- Continue production on Nav2 core with incremental controller/costmap improvements.

## Daily Execution Rhythm (Field-Test Friendly)

1. Preflight (`scripts/go2_ros_preflight.sh prelaunch`) and baseline launch.
2. Run stable Nav2 test block first (establish daily baseline).
3. Run NavDP shadow/assist block with same route set.
4. Evaluate gates same day (success, ABORT, latency, resource).
5. Promote only if gate passes; otherwise rollback same day.

## Why This Is Low-Risk

- It respects current validated stack (`Nav2 + AMCL + DWB`) as control backbone.
- It introduces NavDP by evidence gates, not by architecture replacement.
- It keeps rollback cheap (mode flag + known-good config), aligned with active field testing.
