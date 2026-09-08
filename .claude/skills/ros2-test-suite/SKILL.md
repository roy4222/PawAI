---
name: ros2-test-suite
description: 選擇並執行 PawAI 套件的 Python 測試，判讀測試與環境失敗。
---

# PawAI 套件測試

依本次變更選受影響套件；可用套件、quick 組合與排除項以 `scripts/run_all_tests.py` 的 PACKAGES 為準。從 repo root 執行：

```bash
python3 .claude/skills/ros2-test-suite/scripts/run_all_tests.py --packages pawai_contracts
```

需要完整 suite 才省略 `--packages`；`--quick` 不保證涵蓋本次變更。不要為純文件修字啟動 ROS2／全套 runtime。

保留 runner 對 `nav_capability/test/integration` 的排除：fake mux 測試可能發布速度並接到真狗，不能當一般自動測試。CLI 測試也可能有 real SSH；擴大測試前核對隔離與副作用。

依 pytest 輸出與 exit status 判斷 executed、failed、error、skipped。Runner 的摘要與診斷只是提示：零測試或 collection error 不能算通過；ModuleNotFoundError 需查依賴、import path、ROS overlay 與 install 狀態，不一律 colcon build。source／install 是否需 rebuild 由實際 package 安裝方式決定。

若 runner 沒有保留原始 pytest 輸出與 exit code，不能只靠摘要宣稱通過。從 PACKAGES 取得該套件的 test_dir、extra_args 與 pythonpath，在相同隔離環境直接執行對應 pytest 並保存原始輸出及 exit code；完整保留 nav integration 等排除項，不用無範圍 pytest 取代。

在已授權的隔離環境修復本次造成的問題並重跑受影響測試；實際執行與結果如實回報。
