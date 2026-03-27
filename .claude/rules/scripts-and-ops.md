---
paths:
  - "scripts/**"
  - "docs/operations/**"
---

# 腳本與運維規則

## 關鍵腳本
- `scripts/start_full_demo_tmux.sh` — 10 window cold start（Sprint Day 5 後含 executive v0）
- `scripts/clean_full_demo.sh` — 清理所有 demo 進程和 tmux sessions
- `scripts/clean_speech_env.sh` — 語音環境清理
- `scripts/clean_face_env.sh` — 人臉環境清理
- `scripts/device_detect.sh` — USB 設備自動偵測
- `scripts/smoke_test_e2e.sh` — 5 輪 E2E 快速測試
- `scripts/run_speech_test.sh` — 30 輪驗收測試

## 腳本慣例
- `#!/usr/bin/env bash` + `set -euo pipefail`
- grep 空結果會觸發 pipefail → 尾端加 `|| true`
- tmux session 名稱要可識別（`full-demo`、`llm-e2e` 等）
- 所有 cleanup 腳本要列出被殺的 process（echo feedback）

## Jetson 操作
- Shell 用 zsh：`source install/setup.zsh`（不是 .bash）
- SSH：`ssh jetson-nano`（Tailscale IP 100.83.109.89）
- Jetson repo 路徑：`~/elder_and_dog`（不是 `~/newLife/elder_and_dog`）
- 同時間只允許一套 speech session（禁止多 tmux 混跑）
- 修改 Python 後必須 `colcon build` + `source install/setup.zsh`
