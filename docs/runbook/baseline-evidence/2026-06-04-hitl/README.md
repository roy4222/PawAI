# 2026-06-04 HITL Capability Baseline — Evidence

**Run**: `hitl-0604` · **demo SHA**: `78fbf36` · **snapshot**: `run_trusted=True`, `version_mismatch=False`
**Method**: demo (`pawai demo start`, 13-window full stack) → `capture_baseline_round.py` (fixed-window, SSH-driven) + voice `run_speech_test.sh` → WSL `build_scoreboard --preflight` (built at checkout `78fbf36` to match Jetson deploy manifest) → `pawai readiness`.
**Operator**: Roy (HITL, present at Go2+Jetson). **Go2 motion**: none (nav live dry-run aborted at AMCL gate, actual_distance=0.0).
**Provenance note**: snapshot `wsl_dirty=true` / `jetson_dirty=true` = **untracked files present** (slide PDFs, `.tmp/`), NOT tracked-code changes; SHA `78fbf36` is the clean tracked-tree commit. Reproducibility is weaker than a fully-clean freeze — **next freeze should attach `git status --short` or rerun/freeze from a clean checkout**.

## Capability grades (15)

| capability | grade | n | key metric |
|---|---|---|---|
| **face.recognition** | 🟢 pass | 9 | registered_recall=1.0, unknown_false_accept=0.0, wrong_person=0 |
| **voice.command** | 🟢 pass | 24 | success_rate=0.875 |
| **object.cup** | 🟢 pass (close-range) | 7 | cup recall=1.0 @ ~1m, idle false-pos=0.0 |
| **gesture.wave** | 🔴 fail | 9 | registered_recall=0.0 (wave_pub=False; dynamic detector not triggering) |
| **voice.stop** | 🔴 fail | 6 | success_rate=0.667, FN=2 (R16 no-ack, R18→come_here) |
| pose.basic / pose.fall | ⚪ insufficient_data | 0 | no pose observer in tooling |
| nav.safe_stop / no_auto_resume / short_move / dynamic_avoidance | ⚪ insufficient_data | 0 | no observer; §7 iron rule; live dry-run aborted (amcl_lost, 0 motion) |
| brain.skill_gate / brain.trace / cli.readiness / studio.evidence | ⚪ insufficient_data | 0 | not measured this round |

**readiness verdict**: `not_ready` (correct fail-closed — most capabilities not pass), no `sha_mismatch`.

## Honesty caveats (do NOT overclaim)

- **face**: idle = empty-frame only; **real stranger rejection unverified** (evidence_only, no guardian/stranger-alert claim — North Star §5).
- **object.cup**: pass only at **close range (~1m)**; recall drops with distance (operator-observed); not quantified at 2m. cup-only, not general object recognition.
- **gesture.wave**: fail is real — node log `wave_pub=False` throughout; hand detection intermittent at 1.5m; static gestures (thumbs_up/ok) work but are not this capability.
- **voice.stop**: FN=2 → fail; R18「欸等一下先停住」misclassified as come_here (clear miss). voice e2e is **VAD-era** (mic_stop unwired) — do NOT claim mic_stop latency.
- **voice CSV**: `run_speech_test.sh` observer report ack timed out → no CSV; records **reconstructed from terminal intent results** (real data; latency/play_ok unmeasured, grading uses success_rate only).
- **brain LLM persona hallucination** (operator-observed): TTS replies invented unsensed world state (rain / "saw the cup" / posture). Brain-persona follow-up — do not present as real perception.
- **nav**: all nav.* insufficient_data. Supervised live action-chain dry-run **completed** (Roy confirmed "go2 nav"): `/nav/goto_relative {distance:0.3}` accepted → AMCL gate aborted (`amcl_lost`), `actual_distance=0.0`, Go2 **zero motion** → proves action chain wired + fail-closed. **Grade unchanged** (no real-motion measurement; not localized — no `/initialpose` set). No nav navigation claim.

## Files

- `baseline_result.jsonl` — 55 raw records (face 9 + gesture.wave 9 + object.cup 7 + voice.command 24 + voice.stop 6).
- `baseline_snapshot.json` — trusted scoreboard (15 capabilities).
- `preflight_result.json` — GATE-0 preflight (9 pass / 0 warn / 0 fail).
- `jetson_manifest.json` — deploy manifest (`git_sha=78fbf36`).
- `readiness_output.json` — `pawai readiness --json` (not_ready).
