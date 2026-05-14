# 測試與驗收

## 這個模組是什麼

PawAI 的三層品質閘門：pre-commit 即時檢查、git commit 自動測試、GitHub Actions CI。
日常驗收入口是 `ros2-test-suite` skill（改完 code 後跑）+ `demo-preflight` skill（上台前跑）。
`pawai contract check` 確保 ROS2 topic schema 不漂移。

## 權威文件

| 文件 | 用途 |
|------|------|
| `test_scripts/speech_30round.yaml` | 30 輪語音驗收定義（15 固定 + 15 自由）|
| `scripts/run_speech_test.sh` | 30 輪驗收 orchestration（7 階段）|
| `scripts/smoke_test_e2e.sh` | 5 輪 E2E smoke test（快速）|
| `docs/contracts/interaction_contract.md` | ROS2 介面契約真相（pawai contract check 的基準）|
| `.github/workflows/ros_build.yaml` | GitHub Actions CI（16 tests + contract check + colcon build）|
| `.github/workflows/studio-ci.yml` | Studio CI（lint + build + backend import check）|

## 主要 skills

### ros2-test-suite skill
改完 Python 後、commit 前跑：

```bash
# 快速（只跑 speech + face，3 秒）
/ros2-test-suite --quick

# 完整（含 vision + go2）
/ros2-test-suite
```

### demo-preflight skill
部署到 Jetson 後、上台前跑：

```bash
# 核心 5 項（2 分鐘）
/demo-preflight --quick

# 完整 15+ 項（5 分鐘）
/demo-preflight --full
```

### pawai contract check
確認 ROS2 topic schema 符合 `interaction_contract.md`：

```bash
pawai contract check
```

## 30 輪語音驗收（完整流程）

```bash
# 完整流程（build + driver + 30 輪）
bash scripts/run_speech_test.sh

# 跳過 build + driver（最常用）
bash scripts/run_speech_test.sh --skip-driver --skip-build
```

**通過門檻**：
- Fixed round 命中率 ≥ 80%
- E2E 中位數延遲 ≤ 3500ms
- Go2 播放成功率 ≥ 80%

## 5 輪 E2E Smoke Test

```bash
# 前提：llm-e2e tmux session 已在跑
bash scripts/smoke_test_e2e.sh      # 預設 5 輪
bash scripts/smoke_test_e2e.sh 3    # 指定輪數
```

## GitHub Actions CI 摘要

**ROS2 主專案**（`.github/workflows/ros_build.yaml`）：
- fast-gate：16 個 test files（py_compile + 核心 unit tests）
- blocking contract check：topic schema 不符 → CI 失敗
- colcon build：ARM64 容器 build

**PawAI Studio**（`.github/workflows/studio-ci.yml`）：
- lint（ESLint）+ TypeScript build（tsc 0 errors）
- backend import check（mock_server + gateway）

## 品質閘門三層架構

| 觸發時機 | 工具 | 檢查項目 |
|---------|------|---------|
| Edit/Write 後即時 | Claude Code hook | py_compile（Python 語法）|
| `git commit` | pre-commit hook | py_compile + contract check + affected package tests |
| `git push` / PR | GitHub Actions | flake8 + 16 tests + contract check + colcon build |

**安裝 pre-commit hook**（clone 後一次性）：
```bash
ln -sf ../../scripts/hooks/git-pre-commit.sh .git/hooks/pre-commit
```

## 已知陷阱

- **PulseAudio device lock**：`clean_speech_env.sh` 會 mask PA socket，避免占用 `/dev/snd/pcmC0D0c`
- **Whisper CUDA 首次載入 ~12s**：health check 需 60s 寬限
- **zsh glob 炸陣列**：`'["whisper_local"]'` 加引號
- **HyperX stereo-only**：`channels:=2` + 手動 downmix，不然 ASR 靜音
- **mock 模式下 speech test**：必須先 `clean_speech_env.sh`，同時間只允許一套 session
