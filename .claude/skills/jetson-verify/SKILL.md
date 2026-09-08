---
name: jetson-verify
description: 驗證 PawAI 部署後的 Jetson 環境與 ROS 2 smoke checks。
---

# Jetson 部署驗證

從 repo root 使用 `python3 .claude/skills/jetson-verify/scripts/verify.py --profile smoke`。其他 flags 與 profile 先查 runner、`--help` 及本技能 `profiles/` 中實存 YAML；不要執行預留 profile。

Runner 會輸出 JSON、terminal 摘要與 output directory 的 artifact。核對實際 target：非 Jetson 平台可能會走遠端 SSH，不是本機 dry-run。

- PASS：已執行的 blocking checks 通過；不等於功能或 motion-ready。
- FAIL：檢查有效但必要條件失敗；修復相關原因後重驗。
- ERROR：檢查本身因 transport、timeout 或設定失效，不能據此判功能。
- SKIP／WARN：回報略過或警告及對本輪驗證的影響。

修改 profile 時保留 id、command、expect、blocking、timeout_sec、message_template。基礎 transport／ROS2 檢查不能用 precondition 隱藏；只有不適用的模組檢查可 SKIP。shell、timeout 與結果判讀見 [gotchas](references/gotchas.md)。
