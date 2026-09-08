# Jetson verify gotchas

- transport 使用 bash -lc 時，check command 用 setup.bash；互動 shell 若為 zsh 才用對應 setup.zsh，不能混用。
- thermal zone 隨硬體改變，核對 type 再解讀溫度，不能固定舊 zone 路徑。
- ros2 topic hz 不會自行退出；使用 bounded inner timeout，且 transport outer timeout 要留收尾時間。因 deadline 結束與 transport 失效需分開判讀。
- 非 Jetson 環境可能被 runner 當成 remote_jetson，核對 SSH target；macOS 或 CI 執行不代表 dry-run。
- 只有「無匹配是預期資料」的命令才單獨處理該 exit code；不要用通用 || true 掩蓋 SSH、權限或指令失敗。precondition 的無匹配可代表 SKIP，但基礎 transport／ROS2 checks 不應被它略過。
- 未在 runner 實作的 dry-run 或 profile 不可當可用功能。
