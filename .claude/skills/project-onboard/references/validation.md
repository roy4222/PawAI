# 驗證入口

依變更查相關 package 的 test 目錄、`.github/workflows/` 和 repo 的 `scripts/ci/check_topic_contracts.py`。套件 runner 見 `ros2-test-suite`；部署環境見 `jetson-verify`；展示情境見 `demo-preflight`。

測試名稱與數量不是能力證據。區分本機、REPLAY／SIM、真機靜止資料、真機動作與人類驗收，保存足以核對結果的 artifact。nav integration 可能經 fake mux 驅動真機，不能為追求全綠擅自解除排除；CLI 測試也需查 SSH 副作用。
