# 測試與驗收 Reference

## 定位

CI 自動測試 + Jetson 上機驗收 + 30 輪語音測試。

## 權威文件

- **CI 配置**：`.github/workflows/ros_build.yaml`
- **審查報告**：`docs/archive/2026-05-docs-reorg/audit/2026-03-23-full-audit.md`
- **30 輪測試定義**：`test_scripts/speech_30round.yaml`

## CI 架構（3/23 更新）

**Fast Gate**（< 1 min，無 ROS2）：
- flake8 lint（report-only，不 block）
- 14 個 pure Python test files，198 cases
- pytest-cov coverage + artifact 上傳
- PYTHONPATH: `speech_processor:vision_perception:benchmarks`
- 安裝：pytest pytest-cov flake8 numpy opencv-python-headless

**ROS2 Build**（有 ROS2 container）：
- `ros-tooling/action-ros-ci@v0.3`（已 pin 版本）
- colcon build 全套件

## 測試檔案清單

### speech_processor
- `test/test_speech_test_observer.py`
- `test/test_intent_classifier.py`
- `test/test_llm_contract.py`

### vision_perception
- `test/test_gesture_classifier.py`
- `test/test_gesture_recognizer_backend.py`
- `test/test_pose_classifier.py`
- `test/test_event_builder.py`
- `test/test_interaction_rules.py`
- `test/test_mediapipe_pose_mapping.py`

### benchmarks
- `test/test_criteria.py`
- `test/test_base_adapter.py`
- `test/test_reporter.py`
- `test/test_runner.py`
- `test/test_monitor.py`

## Jetson 驗收腳本

| 腳本 | 用途 |
|------|------|
| `scripts/smoke_test_e2e.sh` | 5 輪 E2E smoke test |
| `scripts/run_speech_test.sh` | 30 輪驗收測試 |
| `scripts/start_stress_test_tmux.sh` | 三感知壓力測試 |
| `scripts/run_vision_case.sh` | 手勢/姿勢半自動測試 |
| `scripts/clean_speech_env.sh` | 語音環境清理 |
| `scripts/clean_face_env.sh` | 人臉環境清理 |
| `scripts/clean_all.sh` | 全環境清理 |

## 測試規範

- 同時間只允許一套 speech session（禁止多 tmux 混跑）
- 測試前必須 clean-start：`bash scripts/clean_speech_env.sh`
- 修改 Python 後必須 `colcon build` 再 `source install/setup.zsh`

## 待改善

- CI 沒有 required status checks（紅燈也能 merge）
- Flake8 425 違規（report-only，不 block）
- 無整合測試（需 ROS2 runtime 的測試目前只在 Jetson 跑）
