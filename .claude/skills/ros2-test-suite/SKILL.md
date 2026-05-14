---
name: ros2-test-suite
description: >
  一鍵跑全部 ROS2 套件的 Python 測試。減少每天手動 4 次 pytest 的摩擦。
  觸發詞："跑測試"、"run tests"、"全套測試"、"test suite"、"測試"、"/test"。
  在修改 Python 程式碼後、commit 前、或需要確認測試狀態時應主動建議。
  不要在純文件編輯、shell script 修改、或不涉及 Python 程式碼的場景觸發。
---

# ros2-test-suite

一鍵跑 PawAI 全部 ROS2 套件的 Python 測試。

## 使用方式

使用者說「跑測試」或「run tests」時，在 repo root 執行：

```bash
# 全套測試（4 packages）
python3 .claude/skills/ros2-test-suite/scripts/run_all_tests.py

# 快速模式（只跑 speech + face，最穩定的兩個）
python3 .claude/skills/ros2-test-suite/scripts/run_all_tests.py --quick

# 指定 package
python3 .claude/skills/ros2-test-suite/scripts/run_all_tests.py --packages speech_processor face_perception
```

## 測試範圍

| Package | 測試目錄 | 預期數量 | 備註 |
|---------|---------|:--------:|------|
| speech_processor | `speech_processor/test/` | ~121 | 最穩定，不需 colcon build |
| face_perception | `face_perception/test/` | ~13 | 穩定 |
| vision_perception | `vision_perception/test/` | ~44 | 部分需 colcon build（import error） |
| go2_robot_sdk | `go2_robot_sdk/test/` | 視情況 | 可能無測試或需特殊環境 |

## 輸出格式

```
========== PawAI Test Suite ==========
speech_processor:   121 passed, 0 failed, 0 skipped  ✅
face_perception:     13 passed, 0 failed, 0 skipped  ✅
vision_perception:    0 passed, 44 failed, 0 skipped  ❌ (需 colcon build)
go2_robot_sdk:        — skipped (無測試目錄)           ⏭️
==========================================
總計: 134 passed, 44 failed
結論: PARTIAL PASS — vision 需 colcon build 後重跑
```

## 失敗分析

腳本自動分析失敗原因：

| 錯誤模式 | 診斷 | 建議 |
|---------|------|------|
| `ModuleNotFoundError: No module named 'xxx'` | 需要 colcon build | `colcon build --packages-select xxx && source install/setup.zsh` |
| `AssertionError` / `assert` | 真正的測試失敗 | 需要修 bug |
| `ImportError: cannot import name` | API 變更 | 檢查最近的 refactor |
| `FileNotFoundError` | 缺少模型或資料檔 | 檢查 Jetson 環境 |

## Gotchas

- vision_perception 的大部分測試需要 `colcon build` + `source install/setup.zsh` 才能跑，因為 ROS2 package import 機制
- 在 WSL 開發機上跑測試不需要 ROS2 runtime（純 Python unit tests）
- `--quick` 模式只跑 speech + face，這兩個不依賴 colcon build
- go2_robot_sdk 的測試可能需要特殊 mock（WebRTC, asyncio），暫時跳過
