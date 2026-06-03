# 第一份可信 Baseline Evidence（2026-06-03）

> **性質**：記錄 capability baseline 第一次上機實測產出**可信工程證據**的里程碑。
> **證據檔（git-tracked 副本）**：`docs/runbook/baseline-evidence/2026-06-03-first-trusted-face/`
> **工作副本（gitignore）**：`artifacts/baseline/2026-06-03-first-trusted-face/`
> 相關：Spec `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`｜Runbook `docs/runbook/2026-06-18-baseline-runbook.md`

## 達成了什麼

整條鏈路**端到端打通並用真人驗證**：

```
demo entrypoint → observer(capture) → baseline_result.jsonl
  → build_scoreboard(--preflight --manifest) → trusted baseline_snapshot.json
  → pawai readiness --json → verdict
```

這比 face 分數本身更重要——它證明專案**不是用口頭宣稱能力，而是用 preflight、manifest、
scoreboard、readiness 產出可重現的工程證據**。

## 三份 artifacts（全部真實）

| Artifact | 內容 |
|---|---|
| `preflight_result.json` | **pass**（demo 全起 9/9 checks）+ **fail**（demo 沒開 → 3 blocking fail）|
| `baseline_result.jsonl` | 3 筆真 face record（含 D435 深度量測）|
| `baseline_snapshot.json` | **trusted**：`run_trusted=True` / `version_mismatch=False`（wsl 2e00914 == jetson 2e00914）|
| `readiness_output.json` | verdict **`not_ready`**（fail-closed：只測 face、其餘無數據）|

### face.recognition 真實 grade

| metric | 值 |
|---|---|
| grade | **fail** |
| registered_recall | 0.5（2 positive：roy_1m_01 fail / roy_1m_02 pass）|
| unknown_false_accept_rate | 1.0（1 idle round false-accept）|
| sample_count | 3（positive 2 / idle 1）|
| 其餘 14 能力 | insufficient_data（無數據）|

`roy_1m_02` pass：sim 0.45、313ms 鎖定、D435 深度 **1.67m**。

## 6/18 報告寫法（工程挑戰與突破）

> 我們不是直接宣稱模型可用，而是建立 preflight、baseline observer、scoreboard 與 readiness。
> 第一次實測中，人臉辨識鏈路成功產生可信 snapshot，但分數仍顯示 fail，代表系統會**誠實揭露
> 不足，而不是過度宣稱能力**。

face=fail、readiness=not_ready 都是**正確**行為——誠實層如實運作，不吹。

## 上機踩到的坑（runbook 補充）

1. **Jetson python 缺 jsonschema** → `run_preflight.py` 頂部 import 直接掛。修：`ssh jetson-nano 'python3 -m pip install --user jsonschema'`（Jetson 無 uv）。**應加進 deploy 依賴**。
2. **Jetson git 在 rsync sync 後是壞的**（`fatal: not a git repository`）→ 在 Jetson 跑 `build_scoreboard` 時 `_git_short()`=unknown → version_mismatch 永遠 True → 全 insufficient。**所以 trusted snapshot 的 `build_scoreboard` 必須在 WSL 跑**（WSL git=main，對得上 manifest）。流程：observer 在 Jetson 產 JSONL → 拉回 WSL → WSL build_scoreboard。
3. **SSH 一行指令驅動 windowed capture 一直被引號/時序搞** → 改用 `benchmarks/scripts/capture_baseline_round.py`（固定時間窗、非互動、複用測過的 observer 邏輯）。

## 待修 follow-up（readiness 揭露，非阻塞）

1. `schema_validator_unavailable:ModuleNotFoundError` — WSL `.venv` 缺 jsonschema（readiness 跳過 schema 驗證）→ `uv pip install jsonschema` 進該 venv。
2. `mainline_failure_reason_missing` — `scoreboard.to_snapshot` 只在 trust-override 時填 `failure_reason`；**grade=fail/degraded/insufficient 的能力沒 reason** → readiness 要求 mainline 非 pass 要有 reason。應補：grader 判非 pass 時也帶 reason。

## 下次計畫（Roy 排序）

1. **face idle 重測**：這次 idle false-accept 可能被 tracker hold/grace 汙染。idle protocol 要加：round 開始前等 5-8s 清空上一個 track，或重啟 `face_identity_node`，或 idle 前確認 `/state/perception/face` 無 `stable_name=roy`。
2. **voice.stop**（安全語意、快速增 demo 說服力）：先 3-5 筆，不求 pass，重點是讓 scoreboard 出現真資料。⚠️ `run_speech_test.sh` 與 demo 的 asr 不可並存（同時只一套 speech session）。
3. object.cup + gesture.wave + 更多 face round 充實 snapshot。

## 重現指令

```bash
# Jetson：起 demo + 跑 capture（face 例）
bash scripts/start_full_demo_tmux.sh          # session 'demo'
python3 benchmarks/scripts/capture_baseline_round.py face \
  --capability face.recognition --scenario-id roy_1m_01 --expected roy \
  --kind positive --distance 1.0 --window 8 --out artifacts/baseline/baseline_result.jsonl

# 拉回 WSL build snapshot（必須 WSL：Jetson git 壞）
scp jetson-nano:'~/elder_and_dog/artifacts/baseline/baseline_result.jsonl' /tmp/
scp jetson-nano:'~/elder_and_dog/.pawai-last-deploy' /tmp/jetson_manifest.json
python3 -m benchmarks.core.build_scoreboard /tmp/baseline_result.jsonl \
  --manifest /tmp/jetson_manifest.json --preflight /tmp/preflight_result.json \
  --out /tmp/baseline_snapshot.json
PAWAI_SCOREBOARD_PATH=/tmp/baseline_snapshot.json /home/roy422/.venv/bin/pawai readiness --json
```
