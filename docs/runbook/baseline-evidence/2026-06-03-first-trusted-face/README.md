# First Trusted Baseline Evidence — 2026-06-03 (face)

**English** | [中文](./README.zh.md)

The project's first **trusted** capability baseline evidence. This folder permanently pins that day's HITL run artifacts into git (`artifacts/baseline/` is itself gitignored and unreliable), making today's results **reproducible and citable by the 6/18 report**.

> For the full engineering narrative (including on-device pitfalls, how to write the 6/18 report, and follow-ups), see [`../../2026-06-03-first-trusted-baseline-evidence.md`](../../2026-06-03-first-trusted-baseline-evidence.md).

## One-Line Conclusion

The entire chain `demo → preflight → observer → baseline_result.jsonl → build_scoreboard → trusted snapshot → readiness` is **wired up end-to-end and verified with a real person**. The first trusted snapshot: `run_trusted=True` / `version_mismatch=False` / `face.recognition=fail` (honestly disclosed) / readiness=`not_ready` (correctly fail-closed).

## File List

| File | Contents |
|------|------|
| `preflight_result.json` | Layer-0 preflight **pass** case (demo up, 9/9 checks, warn=0) |
| `preflight_result.fail.json` | Layer-0 preflight **fail** case (demo not started → 3 blocking fail → snapshot all insufficient, verifying fail-closed) |
| `baseline_result.jsonl` | 3 real face records (roy_1m_01 positive→fail, roy_1m_02 positive→pass@1.67m, idle_01 idle→false-accept) |
| `baseline_snapshot.json` | The trusted snapshot produced by build_scoreboard (15 capabilities; face=fail, the other 14 insufficient_data) |
| `readiness_output.json` | `pawai readiness --json` output (verdict=`not_ready`, honest fail-closed) |
| `jetson_manifest.json` | That run's Jetson `.pawai-last-deploy` (git_sha aligned with WSL, the basis for version_mismatch=False) |

## Why `face.recognition=fail` Is Also Trustworthy Evidence

`fail` (`registered_recall=0.5`, `unknown_false_accept_rate=1.0`, n=3) is not a failure — it is **proof that the capability-grading system is working**: the scoreboard honestly marks "this one cannot yet enter the Brain main line", and per the §4 demo promise the Brain **does not trigger or claim** capabilities that are fail. The 6/18 credibility comes from the scoreboard's honesty, not from verbally claiming "we have it".

## Reproduction Commands

```bash
# 1) 工具（非互動固定時間窗 capture helper，取代 SSH 一行 capture 的引號/時序惡夢）
benchmarks/scripts/capture_baseline_round.py        # 由 /tmp/bcap.py 正式化（PR #113）
#   face  吃 /state/perception/face；percep 吃 gesture+object event

# 2) Jetson 端產 JSONL（demo 起著、相機拉近 ~1.6m）
python3 benchmarks/scripts/capture_baseline_round.py face \
  --capability face.recognition --scenario-id roy_1m_02 \
  --expected roy --kind positive --window 8 \
  --out artifacts/baseline/baseline_result.jsonl

# 3) 拉回 WSL 跑 build_scoreboard（必須在 WSL：Jetson git 在 rsync 後是壞的）
python3 -m benchmarks.core.build_scoreboard <jsonl> \
  --manifest <jetson .pawai-last-deploy> \
  --preflight artifacts/baseline/preflight_result.json \
  --out artifacts/baseline/baseline_snapshot.json

# 4) readiness（pawai 在 WSL $HOME/.venv/bin/pawai，不在 PATH）
PAWAI_SCOREBOARD_PATH=baseline_snapshot.json $HOME/.venv/bin/pawai readiness --json
```

## Known Critical Pitfalls (Recorded in the Engineering Notes)

- **build_scoreboard must run on WSL**: Jetson git after rsync is `fatal: not a git repository` → version_mismatch is always True → everything insufficient. Flow: observer produces JSONL on Jetson → `scp` back to WSL → build on WSL.
- **Camera angle/distance is key to face detection** (Go2/D435 must move in to ~1.6m before it stably recognizes roy).
- **face idle round**: before the round you must leave the camera frame and wait 5–8s to clear the track (the tracker has a 2.5s grace + hold, otherwise the idle false-accept is contaminated).
