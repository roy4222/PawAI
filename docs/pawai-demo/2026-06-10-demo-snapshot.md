# 2026-06-10 Demo Snapshot

## Purpose

This document freezes the current PawAI demo baseline before the post-demo refactor
program starts. The goal is to preserve a known demo recovery point, not to claim the
whole system is production-ready.

Snapshot commit target: `main` after the 2026-06-10 demo-blocking fixes and this
document are committed and pushed.

Primary status source: `references/project-status.md` 2026-06-10 section.

## Snapshot Scope

This baseline covers the 6/18 demo recording flow:

1. S1 movement / navigation scene.
2. S2 face greeting.
3. S3 cup / object reminder.
4. S4 gesture two-step confirmation.
5. S5 safety refusal.

It also includes the tooling created for immediate follow-up validation:

- Studio operator navigation controls.
- Studio gesture toggle.
- object model A/B helpers.
- pose backend probe.
- full-stack under-load probe.

## Recorded / Verified Status

| Segment | Status | Evidence / Notes |
| --- | --- | --- |
| S1 movement | Not recorded yet | Blocked by AMCL covariance gate around the yellow band. Studio nav control exists, but the dog did not move for the desired distance because `/nav/goto_relative` rejected the goal. |
| S2 face greeting | Recorded | Roy-facing interaction segment recorded as part of S2-S5. Current greeting text no longer depends on sitting. |
| S3 cup reminder | Recorded | Cup segment recorded. Demo claim should stay near-range and controlled; do not claim general far-distance object recognition. |
| S4 gesture confirmation | Recorded | Gesture segment recorded after moving to controlled two-step flow and Studio gesture toggle. |
| S5 safety refusal | Recorded / verified | "翻跟斗" refusal path verified via safety block; Go2 does not execute unsafe motion. |

## Current Demo Fixes Included

The snapshot includes these already-committed local fixes:

- Brain demo controls: `demo_phase`, `gesture_enabled`, `stranger_alert_enabled`,
  `greet_require_sitting`, `peace_wego_confirm`, and reset cleanup for object/cup dedup.
- Interaction Executive NAV executor for `/nav/goto_relative`, default-off through
  `nav_executor_enabled=false`.
- `move_forward` skill contract, not LLM-proposable and not demo-claimed until HITL.
- Studio gesture toggle and mock support.
- Studio operator navigation control for S1: initial pose, start/resume/stop controls,
  cancel-on-danger behavior, and map/pose/status display.
- object perception model switch support through `OBJECT_MODEL` and `OBJECT_INPUT_SIZE`.
- object model contract and A/B helper scripts.
- vision pose two-class mode and gesture confidence/vote gates.
- full-stack under-load probe script.

## Fallbacks

- S1 movement fallback: remote-control Go2 into position and present Studio map/status
  as evidence of operator-assisted positioning. Do not imply voice-to-autonomous approach.
- S1 short autonomous fallback: use a shorter 0.5 m movement if AMCL remains in yellow.
- Object fallback: use controlled near-range cup footage or swap to a more reliable
  object if the cup fails under venue lighting.
- Gesture fallback: keep Studio gesture toggle off outside the gesture segment; if
  confidence/vote gates fail, record a Studio-only trace or skip gesture motion.
- Speech/LLM fallback: use rule-based or pre-scripted lines for the demo if network
  latency or remote model availability becomes unstable.

## Demo-Only Hacks / Temporary Controls

- `demo_phase` is a minimal phase gate for recording. It is not the long-term Brain
  architecture.
- `gesture_enabled` is an operator toggle to prevent gesture pollution during other
  segments.
- `stranger_alert_enabled=false` is a demo stabilization setting; stranger alert needs
  a redesign before being claimed.
- `greet_require_sitting=false` is a recording-safe fallback because sitting events
  were not reliable enough during HITL.
- `nav_executor_enabled=false` keeps Brain-to-navigation execution disabled by default.
  It must remain off unless a dedicated HITL test is being run.
- Studio operator navigation is for controlled demo operation. It is not autonomous
  "come to Roy" behavior.

## Forbidden Claims

Do not claim the following from this snapshot:

- PawAI can autonomously hear "come here", find Roy, and walk to Roy.
- PawAI has dynamic obstacle avoidance or can reliably detour around moving people.
- D435 depth is fused with RPLIDAR in the Nav2 costmap.
- The object detector reliably sees cups at 2 m or under arbitrary lighting.
- Studio navigation buttons prove autonomous navigation.
- `move_forward` is demo-ready before `nav_executor_enabled=true` has passed HITL.
- Safety refusal has been tested for every unsafe command, only the demonstrated
  refusal class is verified.

## Known Open Items

1. S1 movement recording still needs one of these decisions:
   - shorten to 0.5 m,
   - set a better initial pose until AMCL covariance is green,
   - or treat movement as operator-assisted.
2. Studio should show goal rejection reasons instead of silently returning to idle.
3. Full-stack performance with vision + object + face + pose/gesture + Studio + nav +
   RPLIDAR + D435 still needs a dedicated under-load run.
4. YOLO26s / larger model A/B remains a measurement task, not a current demo claim.
5. Post-demo refactor should start from the preserved snapshot, not from ad-hoc live
   edits.

## Next Refactor Workflow

After this snapshot is pushed and tagged:

1. Fable performs read-only architecture research and produces a markdown spec.
2. The spec is converted into a WritingPlan with tests, build commands, HITL gates,
   forbidden scope, and rollback notes.
3. Codex executes the plan.
4. Fable reviews the implementation against the spec and plan.
5. Codex fixes blocking review findings only.
6. Final verification runs tests, build/typecheck, git status, and HITL where needed.

The first refactor research request should be the full PawAI architecture audit, followed
by Brain v2, Studio v2, and CLI v2 as separate specs.
