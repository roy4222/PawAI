# jetson-verify Gotchas

Known pitfalls — add new entries as they surface.

1. **check commands 一律用 `setup.bash`，不可用 `setup.zsh`**：transport.py 強制 `bash -lc`，在 bash shell 裡 source zsh script 會出錯。雖然 Jetson 日常用 zsh，但 verify 的 transport 走 bash。

2. **`system.gpu_temp` 的 thermal zone 路徑**：`thermal_zone1` 在 Jetson Orin Nano 上指向 GPU-therm，但不保證跨 Jetson 型號一致。換硬體時需要用 `cat /sys/class/thermal/thermal_zone*/type` 確認。

3. **`ros2 topic hz` 是永不退出的命令**：`module.vision.node_alive` 用 `timeout 8` 包在命令內部，讓它在 8s 後自行終止，避免 transport timeout (-2) 把它升級為 ERROR。`timeout_sec: 12` 比內部 timeout 寬裕，確保 transport 不會先殺掉命令。

4. **`detect_target_env()` 的假設**：非 Jetson 環境一律視為 `remote_jetson`，假設 SSH 到 jetson-nano 可用。這包含 WSL、macOS、CI container 等所有非 Jetson 平台。

5. **`grep -c` 和其他可能回非零的命令必須尾綴 `|| true`**：因為 `rc > 0` → ERROR，check commands 必須確保正常情境下 rc=0。`grep -c 'pattern' || true` 讓 grep 無匹配時回 rc=0 + stdout="0"，由 expect parser 判斷 PASS/FAIL。

6. **precondition 的 `grep -q` 不需要 `|| true`**：precondition 語意是 rc==0 → run，rc==1 → SKIP。`grep -q` 的 rc=1（無匹配）正好是「條件不成立」= SKIP，不需要強制 rc=0。

7. **v1 考慮加 `--dry-run` 參數**：載入 YAML 並印出 check 列表但不執行，方便開發和測試新 profile。
