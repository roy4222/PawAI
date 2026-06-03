# First Trusted Baseline Evidence — 2026-06-03 (face)

專案第一份 **trusted** capability baseline 證據。這份資料夾把當天 HITL run 的 artifacts 永久固定進 git（`artifacts/baseline/` 本身是 gitignore，不可靠），讓今天的結果**可重現、可被 6/18 報告引用**。

> 完整工程敘事（含上機坑、6/18 報告寫法、follow-up）見 [`../../2026-06-03-first-trusted-baseline-evidence.md`](../../2026-06-03-first-trusted-baseline-evidence.md)。

## 一句話結論

整條鏈路 `demo → preflight → observer → baseline_result.jsonl → build_scoreboard → trusted snapshot → readiness` **端到端打通並用真人驗證**。第一份 trusted snapshot：`run_trusted=True` / `version_mismatch=False` / `face.recognition=fail`（誠實揭露）/ readiness=`not_ready`（正確 fail-closed）。

## 檔案清單

| 檔案 | 內容 |
|------|------|
| `preflight_result.json` | Layer-0 preflight **pass** 案例（demo 起來、9/9 checks、warn=0） |
| `preflight_result.fail.json` | Layer-0 preflight **fail** 案例（demo 沒開 → 3 blocking fail → snapshot 全 insufficient，驗 fail-closed） |
| `baseline_result.jsonl` | 3 筆真 face record（roy_1m_01 positive→fail、roy_1m_02 positive→pass@1.67m、idle_01 idle→false-accept） |
| `baseline_snapshot.json` | build_scoreboard 產出的 trusted snapshot（15 能力；face=fail，其餘 14 insufficient_data） |
| `readiness_output.json` | `pawai readiness --json` 輸出（verdict=`not_ready`，誠實 fail-closed） |
| `jetson_manifest.json` | 當次 Jetson `.pawai-last-deploy`（git_sha 對齊 WSL，version_mismatch=False 的依據） |

## 為什麼 `face.recognition=fail` 也是可信證據

`fail`（`registered_recall=0.5`、`unknown_false_accept_rate=1.0`、n=3）不是失敗，是**能力分級制度在運作的證明**：scoreboard 誠實標出「這項還不能進 Brain 主線」，Brain 依 §4 demo promise 對 fail 能力**不觸發、不宣稱**。6/18 的可信度來自 scoreboard 的誠實，不是嘴上說「我們有做」。

## 重現指令

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

# 4) readiness（pawai 在 WSL /home/roy422/.venv/bin/pawai，不在 PATH）
PAWAI_SCOREBOARD_PATH=baseline_snapshot.json /home/roy422/.venv/bin/pawai readiness --json
```

## 已知關鍵坑（寫進工程筆記）

- **build_scoreboard 必須在 WSL 跑**：Jetson git 在 rsync 後 `fatal: not a git repository` → version_mismatch 永遠 True → 全 insufficient。流程：observer 在 Jetson 產 JSONL → `scp` 回 WSL → WSL build。
- **相機角度/距離是 face 偵測關鍵**（Go2/D435 移近 ~1.6m 才穩定認 roy）。
- **face idle round**：round 前需離開鏡頭並等 5–8s 清 track（tracker 有 2.5s grace + hold，否則 idle false-accept 被汙染）。
