# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 語言與工具約定

- **一律用繁體中文回答**
- **pip install 一律改成用 uv pip install**（專案使用 uv 管理 Python 依賴）
- Code Review 角色設定：Linus Torvalds 風格，嚴格審核程式碼品質與潛在風險

---

## 專案概述

**專題名稱：老人與狗 / PawAI**
**硬底線：2026/4/13 展示**
**當前日期：2026-03-18（語音 E2E demo 已錄，人臉辨識 scaffold 完成）**

以 Unitree Go2 Pro 為載體的 **embodied AI 互動陪伴平台**。核心是「人臉辨識 + 中文語音互動 + AI 大腦決策」，不是導航或尋物。

> 完整專案定位、P0/P1/P2、硬體配置見 [`docs/mission/README.md`](docs/mission/README.md)

---

## 建構與執行

### 基本建構

```bash
source /opt/ros/humble/setup.bash   # 或 setup.zsh（Jetson 用 zsh）
colcon build                                        # 全部
colcon build --packages-select go2_robot_sdk        # 單一套件
colcon build --packages-select speech_processor     # 語音模組
colcon build --packages-select face_perception      # 人臉辨識模組
source install/setup.bash                           # build 後必須重新 source
```

### 啟動 Go2 驅動（最小模式）

```bash
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

### 語音 MVP 測試（Jetson 上，no-VAD 主線）

```bash
# 一鍵啟動（推薦）
./scripts/start_asr_tts_no_vad_tmux.sh

# 或分別啟動：
ros2 run speech_processor stt_intent_node --ros-args \
  -p provider_order:='["whisper_local"]' \
  -p input_device:=0 -p sample_rate:=16000 -p capture_sample_rate:=44100
ros2 run speech_processor intent_tts_bridge_node
ros2 run speech_processor tts_node --ros-args -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx \
  -p playback_method:=datachannel
```

### 語音 + LLM 主線（2026-03-17 晚更新）

```bash
# 一鍵啟動（推薦）— 含 LLM preflight check + Megaphone 播放
bash scripts/start_llm_e2e_tmux.sh
# 預設模型：Qwen2.5-7B-Instruct（純文字，啟動 ~100s）
# 覆蓋模型：LLM_MODEL="Qwen/Qwen2.5-3B-Instruct" bash scripts/start_llm_e2e_tmux.sh

# 或手動啟動：
# 1. SSH tunnel 到 RTX 8000（Cloud LLM）
ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5
# 2. llm_bridge_node
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_endpoint:="http://localhost:8000/v1/chat/completions" \
  -p llm_model:="Qwen/Qwen2.5-7B-Instruct"
# 3. 強制走 RuleBrain fallback（debug 用）
ros2 run speech_processor llm_bridge_node --ros-args -p force_fallback:=true
```

### PawAI Studio（前端開發用）

```bash
# 從 repo 根目錄一鍵啟動
bash pawai-studio/start.sh
# → http://localhost:3000/studio
# → Mock Server: http://localhost:8001
```

### 快速驗證 TTS → Go2 播放

```bash
ros2 topic pub --once /tts std_msgs/msg/String '{data: "測試播放"}'
```

### 5 輪 E2E Smoke Test

```bash
# 前提：llm-e2e tmux session 已在跑
bash scripts/smoke_test_e2e.sh      # 預設 5 輪
bash scripts/smoke_test_e2e.sh 3    # 指定輪數
```

### 30 輪驗收測試

```bash
# 完整流程
bash scripts/run_speech_test.sh

# 跳過 build + driver（最常用）
bash scripts/run_speech_test.sh --skip-driver --skip-build
```

### 人臉辨識 pipeline（Jetson 上）

```bash
# 一鍵啟動（推薦）— D435 + face_identity_node + foxglove_bridge
bash scripts/start_face_identity_tmux.sh

# 或手動啟動：
ros2 launch face_perception face_perception.launch.py

# 環境清理
bash scripts/clean_face_env.sh --all
```

### 手勢+姿勢 pipeline（vision_perception）

```bash
# Phase 1 mock mode（不需相機，開發機或 Jetson 都可）
colcon build --packages-select vision_perception
source install/setup.zsh
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=mock use_camera:=false mock_scenario:=stop

# Mock event publisher（給前端用，持續循環發事件）
ros2 launch vision_perception mock_publisher.launch.py

# 狀態儀表板（Foxglove Image panel 可視化）
ros2 run vision_perception vision_status_display

# Event → Go2 動作橋接
ros2 launch vision_perception event_action_bridge.launch.py
```

### 環境清理（語音模組）

```bash
bash scripts/clean_speech_env.sh              # 預設：不碰 go2_driver_node
bash scripts/clean_speech_env.sh --with-go2-driver  # 診斷用：連 driver 一起清
```

### 常用除錯

```bash
ros2 topic list
ros2 topic echo /event/speech_intent_recognized
ros2 topic echo /asr_result
ros2 topic echo /tts
ros2 topic echo /webrtc_req
ros2 topic info /webrtc_req -v   # 確認訂閱者包含 go2_driver_node
```

---

## 三層系統架構

> 詳見 [`docs/mission/README.md`](docs/mission/README.md) §5

Layer 3（中控）→ Layer 2（感知）→ Layer 1（驅動/硬體）。事件驅動、單一控制權。

---

## ROS2 套件與節點

> 完整節點清單與參數見 [`docs/architecture/interaction_contract.md`](docs/architecture/interaction_contract.md)

**核心套件速查**：
- `go2_robot_sdk` — Go2 驅動，Clean Architecture 分層，WebRTC DataChannel 通訊
- `speech_processor` — 語音模組（stt_intent_node / tts_node / intent_tts_bridge_node / speech_test_observer）
- `face_perception` — 人臉辨識模組（face_identity_node：YuNet 偵測 + SFace 識別 + IOU 追蹤）
- `vision_perception` — 手勢+姿勢模組（vision_perception_node / mock_event_publisher / event_action_bridge / vision_status_display）
- `go2_interfaces` — 自訂 ROS2 訊息（`WebRtcReq.msg`）

**WebRTC 音訊播放速查**：
- **現行方式**：Megaphone DataChannel — `4001`(enter) → `4003`(upload chunks) → `4002`(exit)
- chunk_size = 4096 base64 chars，payload 須含 `current_block_size`，msg type 須為 `"req"`
- **Megaphone cooldown**：4002 EXIT 後 sleep 0.5s，防止 Go2 狀態機未重置導致 silent fail
- **LLM 模型**：Qwen2.5-7B-Instruct（純文字 CausalLM），max_tokens 120，reply ≤ 25 字
- **ASR warmup**：stt_intent_node 啟動時 daemon thread 預熱 Whisper CUDA（~12s）
- **RuleBrain fallback**：LLM 失敗自動 fallback，`force_fallback:=true` 可強制測試
- 詳見 [`docs/語音功能/README.md`](docs/語音功能/README.md) 的「Go2 音訊播放」章節

---

## 關鍵 ROS2 Topic

> 完整 Topic 列表見 [`docs/architecture/interaction_contract.md`](docs/architecture/interaction_contract.md)

**語音主線**：`/event/speech_intent_recognized`（Intent 事件 JSON）
**人臉主線**：`/state/perception/face`（人臉狀態 10Hz JSON）
**手勢主線**：`/event/gesture_detected`（手勢事件 JSON，v2.0 凍結）
**姿勢主線**：`/event/pose_detected`（姿勢事件 JSON，v2.0 凍結）
**視覺儀表板**：`/vision_perception/status_image`（Foxglove 狀態圖 8Hz）

---

## 開發環境

### 雙平台架構

- **Windows/Mac（開發機）**：VS Code SSH → Jetson，程式碼編輯、文件撰寫
- **Jetson Orin Nano（邊緣端）**：ROS2 runtime、模型推理、Go2 連線
- **Go2 Pro**：192.168.12.1（Wi-Fi AP）或 192.168.123.161（Ethernet）

### Jetson 操作要點

- Shell 用 **zsh**：source 時用 `setup.zsh` 而非 `setup.bash`
- 麥克風 default 裝置常漂移，啟動時需指定 `input_device:=0`
- **HyperX SoloCast 是 stereo-only**（硬體 `CHANNELS: 2`），`stt_intent_node` 預設 `channels:=2` + callback 內手動 stereo→mono downmix。不要用 `channels:=1`，PortAudio 在 Jetson 上的 auto-downmix 不可靠（會撞 `-9985` / `-9998`）
- 麥克風原生 44.1kHz，node 內重取樣至 16kHz：`capture_sample_rate:=44100`
- zsh 的 glob 會炸掉陣列參數：用 `'["whisper_local"]'` 加引號，或 `setopt nonomatch`
- `setup.bash` / `setup.zsh` 不可混用，否則環境不完整

### Jetson 測試規範

- 同時間只允許一套 speech session（禁止多 tmux 混跑）
- 測試前必須 clean-start：`bash scripts/clean_speech_env.sh`
- 修改 Python 程式碼後必須 `colcon build` 再 `source install/setup.zsh`

---

## 已知陷阱與設計決策

### WebRTC 音訊發送的執行緒模型

`go2_driver_node` 有兩個執行緒：
1. **ROS2 executor 執行緒**：處理 `/webrtc_req` callback
2. **asyncio event loop 執行緒**：管理 WebRTC DataChannel

音訊命令從 ROS2 callback → `send_command()` → `run_coroutine_threadsafe()` → DataChannel.send()。
`send_command` 已正確處理跨執行緒，其他動作命令（movement/stand）也用此路徑。

### Jetson 記憶體預算（8GB 統一記憶體）

同時跑 D435 + YuNet + ASR + TTS + ROS2 時，需保留 ≥0.8GB 餘量。
展示模式應關閉 RViz/Foxglove/Nav2/SLAM 以釋放資源。

### Go2 LiDAR 頻率過低（<2Hz）

導航避障技術上不可行（需 ≥10Hz），因此列為 P2。定位（AMCL）可用。

### Go2 DataChannel Megaphone API 格式（v1.1.7 已驗證）

Megaphone API (4001/4003/4002) **可正常播放**，之前判定「失效」是因為 payload 格式錯誤。正確格式：chunk_size=4096、payload 含 `current_block_size` 欄位、DataChannel msg type 為 `"req"`（不是 `"msg"`）。詳見語音模組 README。

### 多 driver instance 殘留

`ros2 launch` 啟動後，`killall python3` 只殺 launch parent，C++ 子 process（robot_state_publisher、pointcloud、joy 等）會殘留。下次 launch 會再生一組，導致多 instance 搶 WebRTC 連線和 topic。**必須用 `pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud; pkill -9 joy_node; pkill -9 teleop; pkill -9 twist_mux` 逐一清除。**

### clean_all.sh 的 pipefail + grep 空結果

`clean_all.sh` 使用 `set -euo pipefail`。驗證段 `RESIDUAL=$(ps aux | grep -E ... | grep -v grep | wc -l)` 在無殘留 process 時，`grep` 回傳 1（no match），`pipefail` 傳播非零，`set -e` 中斷腳本。修復：尾端加 `|| true`。

### Go2 OTA 自動更新

Go2 連上有外網的 Wi-Fi 會自動背景更新韌體。建議用 Ethernet 直連模式（192.168.123.161）開發，避免 Go2 連上外網被更新。

---

## 關鍵文件索引

| 領域 | 真相來源 |
|------|---------|
| 專案方向、分工、Demo | [`docs/mission/README.md`](docs/mission/README.md) |
| 3/16 交付清單 | [`docs/mission/handoff_316.md`](docs/mission/handoff_316.md) |
| ROS2 介面契約 | [`docs/architecture/interaction_contract.md`](docs/architecture/interaction_contract.md) |
| PawAI Studio 設計 | [`docs/Pawai-studio/README.md`](docs/Pawai-studio/README.md) |
| 語音模組 | [`docs/語音功能/README.md`](docs/語音功能/README.md) |
| 人臉模組 | [`docs/人臉辨識/README.md`](docs/人臉辨識/README.md) |
| 手勢辨識 | [`docs/手勢辨識/README.md`](docs/手勢辨識/README.md) |
| 姿勢辨識 | [`docs/姿勢辨識/README.md`](docs/姿勢辨識/README.md) |
| 環境建置 | [`docs/setup/README.md`](docs/setup/README.md) |

### 配置檔
- `go2_robot_sdk/config/` — SLAM/Nav2/CycloneDDS/Joystick 參數
- `speech_processor/config/speech_processor.yaml` — 語音模組參數
- `face_perception/config/face_perception.yaml` — 人臉辨識參數（Jetson 路徑、閾值）
- `vision_perception/config/vision_perception.yaml` — 手勢+姿勢參數（mock mode 預設）
- `go2_robot_sdk/launch/robot.launch.py` — 主 launch（修改後不需 rebuild）
- `face_perception/launch/face_perception.launch.py` — 人臉辨識 launch
- `vision_perception/launch/vision_perception.launch.py` — 手勢+姿勢 launch（含 use_camera 開關）

### 測試腳本
- `scripts/start_asr_tts_no_vad_tmux.sh` — 語音 MVP no-VAD 主線一鍵啟動
- `scripts/start_speech_e2e_tmux.sh` — 端到端語音測試
- `scripts/start_face_identity_tmux.sh` — 人臉辨識 pipeline 一鍵啟動
- `scripts/run_speech_test.sh` — 30 輪驗收測試 orchestration
- `scripts/clean_speech_env.sh` — 語音環境清理（被其他腳本呼叫）
- `scripts/clean_face_env.sh` — 人臉辨識環境清理
- `test_scripts/speech_30round.yaml` — 30 輪測試定義（15 固定 + 15 自由）

---

## 常見開發情境

### 新增 ROS2 節點

1. 建立節點檔案（例如 `speech_processor/speech_processor/my_node.py`）
2. 更新 `setup.py` 的 `entry_points`
3. `colcon build --packages-select speech_processor`
4. `source install/setup.bash`（或 `.zsh`）
5. `ros2 run speech_processor my_node`

### 新增 Intent 規則

編輯 `speech_processor/speech_processor/stt_intent_node.py` 中的 `intent_rules` 字典，
加入關鍵字與權重。同步更新 `intent_tts_bridge_node.py` 的 `reply_templates`。

### 切換 TTS Provider

```bash
# Piper（本地，低延遲）
ros2 run speech_processor tts_node --ros-args -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx

# ElevenLabs（雲端，高品質）
ros2 run speech_processor tts_node --ros-args -p provider:=elevenlabs \
  -p api_key:="$ELEVENLABS_API_KEY"

# MeloTTS（本地）
ros2 run speech_processor tts_node --ros-args -p provider:=melotts
```
