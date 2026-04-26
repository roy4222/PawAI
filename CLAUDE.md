# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 語言與工具約定

- **一律用繁體中文回答**
- **pip install 一律改成用 uv pip install**（專案使用 uv 管理 Python 依賴）
- Code Review 角色設定：Linus Torvalds 風格，嚴格審核程式碼品質與潛在風險

## 工作紀律（基於 51 sessions 的摩擦分析）

- **不要擴張 scope**：只做我要求的，不要提議額外清理、重構、或「順便改」。我會主動擴張
- **寫完 Python 後自我檢查**：確認所有 import 存在、沒有 hardcoded 測試值、boolean casting 正確、timestamp 用真實來源
- **指定 skill 就用那個 skill**：不要替換成其他 skill、不要手動探索檔案、不要自行 brainstorm。先執行指令，再問問題
- **每個任務完成後停下來確認**，不要連續做多個任務

## Jetson 環境硬規則

- source 時用 `setup.zsh`（不是 `setup.bash`），兩者不可混用
- tmux 不繼承 `LD_LIBRARY_PATH` — 啟動腳本中必須 export
- Jetson CUDA int8 支援有限 — 走 CUDA 路徑時 Whisper 必須用 `cuda` + `float16`;CPU 路徑的 int8 量化可用(`speech_processor.yaml` 預設 `device: cpu` + `compute_type: int8`),Demo 啟動腳本 `scripts/start_full_demo_tmux.sh` 會覆寫為 `cuda + float16` 以提升速度
- bash-specific 腳本用 `bash -c`，不要假設 zsh 相容

---

## 專案概述

**專題名稱：老人與狗 / PawAI**
**硬底線：2026/4/13 文件繳交（週日初版、週一繳交），五月展示／驗收**
**當前日期：2026-04-11（互動主軸定位收斂，PawAI Brain 命名定案）**

以 Unitree Go2 Pro 為載體的**居家互動機器狗（兼具守護能力）**。互動 70% / 守護 30%。

**核心**：PawAI Brain（三層決策引擎：Safety → Policy → Expression）+ 多模態感知（人臉/語音/手勢/姿勢/物體）+ 實體反應。

**互動主軸（70%）**：手勢 / 姿勢 / 語音 / 物體辨識 → 觸發動作 or 移動（細節下週四人回報後定）
**守護輔助（30%）**：陌生人警告、巡邏（需雷達）、跟隨（文件級 future work）

> 完整專案定位見 [`docs/mission/README.md`](docs/mission/README.md)
> **系統設計規格（current）**：[`docs/superpowers/specs/2026-04-11-pawai-home-interaction-design.md`](docs/superpowers/specs/2026-04-11-pawai-home-interaction-design.md)
> 4/10 守護犬 spec 已 superseded（保留作歷史）：[`docs/superpowers/specs/2026-04-10-guardian-dog-design.md`](docs/superpowers/specs/2026-04-10-guardian-dog-design.md)

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

### P0 導航避障：建圖（cartographer + RPLIDAR）

```bash
# 5-window tmux: tf + sllidar + carto + carto_grid + foxglove（無 Go2 driver）
bash scripts/build_map.sh home_living_room
# → 走完客廳一圈後存圖（3 步驟 prompt）：
#   ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory "{trajectory_id: 0}"
#   ros2 service call /write_state cartographer_ros_msgs/srv/WriteState "{filename: '/home/jetson/maps/home_living_room.pbstream', include_unfinished_submaps: true}"
#   ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/home_living_room --ros-args -p map_subscribe_transient_local:=true
```

### P0 導航避障：Demo（cartographer mapping 已存圖後）

```bash
# 5-window tmux: tf + sllidar + driver + nav2_bringup(amcl+map_server+nav) + foxglove
bash scripts/start_nav2_amcl_demo_tmux.sh
# 等 ~30s lifecycle active 後：
# - Foxglove/RViz 設 /initialpose（Go2 真實位置 + 朝向）
# - 發 goal: ros2 topic pub /goal_pose geometry_msgs/PoseStamped ... -r 2  (BEST_EFFORT sub 要多次發)
```

**已知陷阱**：
- **Go2 sport mode cmd_vel 門檻 MIN_X = 0.50 m/s**（4/25 實機 calibration 確認）— DWB `min_vel_x` 必須 ≥ 0.45，否則 Go2 拒抬腳。詳 `docs/導航避障/research/2026-04-25-rplidar-a2m12-integration-log.md` §Step 0
- **Go2 driver `_publish_transform` env 開關**：`GO2_PUBLISH_ODOM_TF=0` 跳 odom→base_link TF 給 cartographer own（建圖階段用）；預設 1（Nav2 demo 階段用，AMCL 需要 driver odom）
- **slam_toolbox 在 ARM64 + Humble + RPLIDAR 永久棄用**（Mapper FATAL ERROR known bug）
- **不要 `ros2 topic pub --once /goal_pose`**：bt_navigator subscriber 是 BEST_EFFORT，會 race 沒收到。改 `-r 2 --times 5` 多次發

### 語音 MVP 測試（Jetson 上，no-VAD 主線）

```bash
# 一鍵啟動（推薦）
bash scripts/start_llm_e2e_tmux.sh

# 或分別啟動：
ros2 run speech_processor stt_intent_node --ros-args \
  -p provider_order:='["whisper_local"]' \
  -p input_device:=0 -p sample_rate:=16000 -p capture_sample_rate:=44100
ros2 run speech_processor intent_tts_bridge_node
ros2 run speech_processor tts_node --ros-args -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx \
  -p playback_method:=datachannel
```

### 語音 + LLM 主線（2026-03-29 更新：SenseVoice ASR 三級 fallback）

```bash
# 一鍵啟動（推薦）— SenseVoice cloud ASR + edge-tts + USB 外接設備
bash scripts/start_llm_e2e_tmux.sh
# 全離線模式（Piper TTS）：TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh
# 只用本地 ASR（不需 tunnel）：
# ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_llm_e2e_tmux.sh

# SSH tunnel（Cloud ASR + Cloud LLM）
ssh -f -N -L 8001:localhost:8001 -L 8000:localhost:8000 $USER@<server>

# ASR provider 順序：sensevoice_cloud → sensevoice_local → whisper_local
# Cloud ASR server（RTX 8000）：scripts/sensevoice_server.py（port 8001）
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
# Gesture Recognizer 模式（推薦，3/23 場景驗證通過）
colcon build --packages-select vision_perception
source install/setup.zsh
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe gesture_backend:=recognizer max_hands:=2

# 全 MediaPipe 模式（備用，GPU 0%，但只有 3 種手勢且 point 不穩）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe gesture_backend:=mediapipe

# 效能調參（3/22 新增 launch args）
# pose_complexity:=0 (lite,快) / 1 (full)
# hands_complexity:=0 (lite) / 1 (full)
# max_hands:=1 (單手,快) / 2 (雙手)
# publish_fps:=15 (debug 用高 FPS)
# gesture_every_n_ticks:=3 (mediapipe backend 專用，recognizer 每 tick 都跑)

# RTMPose + MediaPipe 混合（pose 走 GPU，gesture 走 CPU）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true rtmpose_mode:=lightweight \
  gesture_backend:=mediapipe

# Phase 1 mock mode（不需相機，開發機或 Jetson 都可）
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=mock use_camera:=false mock_scenario:=stop

# Mock event publisher（給前端用，持續循環發事件）
ros2 launch vision_perception mock_publisher.launch.py

# 狀態儀表板（Foxglove Image panel 可視化）
ros2 run vision_perception vision_status_display

# Event → Go2 動作橋接
ros2 launch vision_perception event_action_bridge.launch.py

# 高層互動事件路由（3/23 新增，訂閱 face+gesture+pose → welcome/gesture_cmd/fall_alert）
ros2 launch vision_perception interaction_router.launch.py

# 三感知壓力測試（face+vision+camera 同跑 60s，含 monitor）
bash scripts/start_stress_test_tmux.sh        # 預設 60s
bash scripts/start_stress_test_tmux.sh 120    # 指定時間
```

**RTMPose 已知狀況**（3/18 實測）：
- balanced mode, GPU 91-99% 滿載，debug_image ~3.8 Hz
- 溫度 66°C 安全，RAM 餘 2.4GB
- 若需更快可切 `rtmpose_mode:=lightweight`（未測）
- onnxruntime-gpu 安裝：`pip install onnxruntime-gpu==1.23.0 --index-url https://pypi.jetson-ai-lab.io/jp6/cu126 --extra-index-url https://pypi.org/simple/`
- rtmlib 安裝：`pip install --no-deps rtmlib`（避免拉回 CPU onnxruntime）

### 物體辨識 pipeline（object_perception，Jetson 上）

```bash
# 前提：D435 camera 已啟動
ros2 launch realsense2_camera rs_launch.py enable_depth:=false pointcloud.enable:=false

# 啟動物體辨識 node（COCO 80 class 全開，YOLO26n ONNX + TensorRT EP FP16）
colcon build --packages-select object_perception
source install/setup.zsh
ros2 launch object_perception object_perception.launch.py

# 縮減為原 P0 6 類（person/dog/bottle/cup/chair/dining_table）
ros2 launch object_perception object_perception.launch.py \
  class_whitelist:='[0, 16, 39, 41, 56, 60]'

# 驗證 topic
ros2 topic hz /perception/object/debug_image        # ~6-8 Hz
ros2 topic echo /event/object_detected --once       # JSON event
```

**已知陷阱**（見 `docs/辨識物體/CLAUDE.md`）：
- **不要 `pip install ultralytics`**（會破壞 Jetson torch wheel）
- TRT provider 參數值必須 `"True"`/`"False"` 字串，非 `"1"`/`"0"`
- `class_whitelist` 空 list 需用 `ParameterDescriptor(INTEGER_ARRAY)`，yaml 不要寫 `: []`
- 模型路徑：`/home/jetson/models/yolo26n.onnx`（9.5MB, output `(1,300,6)` NMS-free）
- TRT cache：`/home/jetson/trt_cache/`（首次啟動 3-10 分鐘）

### 模型選型 Benchmark（2026-03-19 新建）

```bash
# 單一模型 benchmark（headless mode，不需 ROS2）
python3 benchmarks/scripts/bench_single.py \
  --config benchmarks/configs/face_candidates.yaml \
  --model yunet_2023mar --level 1

# Jetson 環境鎖定（benchmark 前必做）
sudo bash benchmarks/scripts/prepare_env.sh          # nvpmodel + jetson_clocks
sudo bash benchmarks/scripts/prepare_env.sh --drop-cache  # 含清 page cache
```

**制度流程**：Research Brief (`docs/research/{task}.md`) → Candidate Shortlist (`benchmarks/configs/{task}_candidates.yaml`) → Benchmark → Decision

**Spec**：[`docs/superpowers/specs/2026-03-19-unified-benchmark-framework-design.md`](docs/superpowers/specs/2026-03-19-unified-benchmark-framework-design.md)

**3/21 決策摘要**（完整數據見 `benchmarks/results/archive/` + `docs/research/`）：

| Task | 主線 | FPS | Decision | 備援 | Decision |
|------|------|:---:|:--------:|------|:--------:|
| face | YuNet 2023mar | 71.3 (CPU) | JETSON_LOCAL | SCRFD-500M | JETSON_LOCAL |
| pose | MediaPipe Pose | 18.5 (CPU) | JETSON_LOCAL | RTMPose lw | JETSON_LOCAL |
| gesture | Gesture Recognizer | 7.2 (CPU) | JETSON_LOCAL | MediaPipe Hands | JETSON_LOCAL |
| stt | SenseVoice cloud (FunASR) | ~600ms | CLOUD | SenseVoice local (sherpa-onnx int8) | JETSON_LOCAL |
| tts | edge-tts | P50 1.13s | CLOUD | Piper huayan | JETSON_LOCAL |
| llm (local) | Qwen2.5-0.5B | P50 0.8s, 139MB | JETSON_LOCAL | Qwen2.5-1.5B | HYBRID |

**L2 共存**：face(CPU)+pose(CUDA) = -6%、SCRFD(GPU)+pose = -10%、whisper(CUDA)+pose = -20%

**L3 三感知壓測**（3/23）：face(CPU)+pose(CPU)+gesture(CPU) 同跑 60s → RAM 1.2GB, temp 52°C, GPU 0% ✅

### 環境清理

```bash
bash scripts/clean_full_demo.sh              # 清 demo 全環境（10 window + Go2 + camera）
bash scripts/clean_speech_env.sh              # 只清語音，不碰 go2_driver_node
bash scripts/clean_speech_env.sh --with-go2-driver  # 診斷用：連 driver 一起清
```

### USB 裝置偵測

```bash
source scripts/device_detect.sh   # !! 必須用 source，不能用 bash !!
# exports: DETECTED_MIC_INDEX, DETECTED_MIC_CHANNELS, DETECTED_CAPTURE_RATE, DETECTED_SPK_DEVICE
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

> 完整節點清單與參數見 [`docs/architecture/contracts/interaction_contract.md`](docs/architecture/contracts/interaction_contract.md)

**核心套件速查**：
- `go2_robot_sdk` — Go2 驅動，Clean Architecture 分層，WebRTC DataChannel 通訊
- `speech_processor` — 語音模組（stt_intent_node / tts_node / llm_bridge_node / intent_tts_bridge_node）
- `face_perception` — 人臉辨識模組（face_identity_node：YuNet 偵測 + SFace 識別 + IOU 追蹤）
- `vision_perception` — 手勢+姿勢模組（vision_perception_node / mock_event_publisher / event_action_bridge / interaction_router）
- `interaction_executive` — 統一中控（interaction_executive_node：state machine + event routing，Day 6 起取代 router+bridge）
- `go2_interfaces` — 自訂 ROS2 訊息（`WebRtcReq.msg`）

**WebRTC 音訊播放速查**：
- **現行方式**：Megaphone DataChannel — `4001`(enter) → `4003`(upload chunks) → `4002`(exit)
- chunk_size = 4096 base64 chars，payload 須含 `current_block_size`，msg type 須為 `"req"`
- **Megaphone cooldown**：4002 EXIT 後 sleep 0.5s，防止 Go2 狀態機未重置導致 silent fail
- **LLM 模型**：Qwen2.5-7B-Instruct（純文字 CausalLM），max_tokens 120，reply ≤ 25 字
- **LLM fallback**：雲端優先 → 本地 Qwen2.5-0.8B 作為備援（智商待測）
- **ASR warmup**：stt_intent_node 啟動時 daemon thread 預熱 Whisper CUDA（~12s）
- **RuleBrain fallback**：LLM 失敗自動 fallback，`force_fallback:=true` 可強制測試
- 詳見 [`docs/語音功能/README.md`](docs/語音功能/README.md) 的「Go2 音訊播放」章節

---

## 關鍵 ROS2 Topic

> 完整 Topic 列表見 [`docs/architecture/contracts/interaction_contract.md`](docs/architecture/contracts/interaction_contract.md)

**語音主線**：`/event/speech_intent_recognized`（Intent 事件 JSON）
**人臉主線**：`/state/perception/face`（人臉狀態 10Hz JSON）
**手勢主線**：`/event/gesture_detected`（手勢事件 JSON，v2.0 凍結）
**姿勢主線**：`/event/pose_detected`（姿勢事件 JSON，v2.0 凍結）
**視覺儀表板**：`/vision_perception/status_image`（Foxglove 狀態圖 8Hz）
**互動事件**：`/event/interaction/welcome` | `/event/interaction/gesture_command` | `/event/interaction/fall_alert`（interaction_router 發布）

---

## 開發環境

### 品質閘門（三層）

```bash
# 1. 安裝 git pre-commit hook（clone 後一次性）
ln -sf ../../scripts/hooks/git-pre-commit.sh .git/hooks/pre-commit

# 觸發時機：每次 git commit
# 檢查：py_compile → topic contract → affected package tests
# 跳過：git commit --no-verify
```

- **Claude Code hooks**：Edit/Write 後即時 py_compile + commit 時 colcon build 提醒
- **Git pre-commit**：commit 時 py_compile + contract check + smart-scope tests
- **GitHub Actions**：push/PR 時 flake8 + 16 test files + contract check（blocking）+ colcon build

### 雙平台架構

- **Windows/Mac（開發機）**：VS Code SSH → Jetson，程式碼編輯、文件撰寫
- **Jetson Orin Nano（邊緣端）**：ROS2 runtime、模型推理、Go2 連線
- **Go2 Pro**：192.168.12.1（Wi-Fi AP）或 192.168.123.161（Ethernet）
- **所有設備已上機**（4/8 確認）：Jetson + D435 + 外接喇叭 + XL4015 降壓板
- ⚠️ **供電不穩**：XL4015 在 Go2 運行中反覆斷電（8+ 次），20V 已是安全極限
- **機身 USB 麥克風已廢棄**：Go2 風扇噪音導致 ~20% 辨識率，Demo 改用筆電 Studio 收音

### Jetson 操作要點

- Shell 用 **zsh**：source 時用 `setup.zsh` 而非 `setup.bash`
- **主線麥克風**：USB UACDemoV1.0（device 24，mono，48kHz）— `input_device:=24 channels:=1 capture_sample_rate:=48000 mic_gain:=4.0`
- **主線喇叭**：USB CD002-AUDIO（`plughw:3,0`）— `local_playback:=true local_output_device:=plughw:3,0`
- **備用麥克風 HyperX SoloCast 是 stereo-only**（硬體 `CHANNELS: 2`），需 `channels:=2` + 手動 downmix
- **Whisper 在 Jetson 走 CUDA 時必須用 `float16`**(`cuda + int8` 不支援會 silent fail);`speech_processor.yaml` 預設為 `cpu + int8` 可用但速度較慢,Demo 啟動腳本覆寫為 `cuda + float16`
- `LD_LIBRARY_PATH` 必須含 `/home/jetson/.local/ctranslate2-cuda/lib`（啟動腳本已處理）
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

Go2 內建 LiDAR 導航不可行（覆蓋率 18%），D435 避障因鏡頭角度限制上機全失敗（4/3 停用）。外接 RPLIDAR A2M12 評估中（4/14 定案），可行性研究結論：RAM 安全、CPU 風險需管理。

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
| ROS2 介面契約 | [`docs/architecture/contracts/interaction_contract.md`](docs/architecture/contracts/interaction_contract.md) |
| PawAI Studio 設計 | [`docs/Pawai-studio/README.md`](docs/Pawai-studio/README.md) |
| 語音模組 | [`docs/語音功能/README.md`](docs/語音功能/README.md) |
| 人臉模組 | [`docs/人臉辨識/README.md`](docs/人臉辨識/README.md) |
| 手勢辨識 | [`docs/手勢辨識/README.md`](docs/手勢辨識/README.md) |
| 姿勢辨識 | [`docs/姿勢辨識/README.md`](docs/姿勢辨識/README.md) |
| 環境建置 | [`docs/setup/README.md`](docs/setup/README.md) |
| 模型選型調查 | `docs/research/{task}.md`（face 已建） |
| Benchmark 框架規格 | [`docs/superpowers/specs/2026-03-19-unified-benchmark-framework-design.md`](docs/superpowers/specs/2026-03-19-unified-benchmark-framework-design.md) |

### 配置檔
- `go2_robot_sdk/config/` — SLAM/Nav2/CycloneDDS/Joystick 參數
- `speech_processor/config/speech_processor.yaml` — 語音模組參數
- `face_perception/config/face_perception.yaml` — 人臉辨識參數（Jetson 路徑、閾值）
- `vision_perception/config/vision_perception.yaml` — 手勢+姿勢參數（mock mode 預設）
- `benchmarks/configs/face_candidates.yaml` — 人臉 benchmark 候選模型（Batch 1）
- `go2_robot_sdk/launch/robot.launch.py` — 主 launch（修改後不需 rebuild）
- `face_perception/launch/face_perception.launch.py` — 人臉辨識 launch
- `vision_perception/launch/vision_perception.launch.py` — 手勢+姿勢 launch（含 use_camera 開關）

### 測試腳本
- `scripts/start_llm_e2e_tmux.sh` — 語音+LLM 主線一鍵啟動（edge-tts + USB 外接）
- `scripts/start_full_demo_tmux.sh` — 四功能整合 Demo 一鍵啟動
- `scripts/start_face_identity_tmux.sh` — 人臉辨識 pipeline 一鍵啟動
- `scripts/start_vision_debug_tmux.sh` — 手勢+姿勢 debug 環境（全 MediaPipe + Foxglove）
- `scripts/build_map.sh` — P0 導航 cartographer 建圖（呼叫 `start_lidar_slam_tmux.sh`）
- `scripts/start_lidar_slam_tmux.sh` — P0 導航建圖 5-window（無 Go2 driver）
- `scripts/start_nav2_amcl_demo_tmux.sh` — P0 導航 demo 5-window（含 Go2 driver + nav2 + amcl）
- `scripts/start_nav2_demo_tmux.sh` — v3.6 cartographer pure-loc archive，**不再啟用**
- `scripts/start_reactive_stop_tmux.sh` — P0 反應式停障 fallback 4-window（5/13 demo 備援，與 nav2-amcl 互斥）
- `scripts/send_relative_goal.py` — 讀 `/amcl_pose` 算前方相對 goal（QoS BEST_EFFORT 配 bt_navigator）
- `scripts/run_vision_case.sh` — 手勢/姿勢半自動測試（宣告 case → 錄 event → 產生 log）
- `scripts/run_speech_test.sh` — 30 輪驗收測試 orchestration
- `scripts/clean_full_demo.sh` — Demo 全環境清理（10 window + Go2 + camera）
- `scripts/clean_speech_env.sh` — 語音環境清理（被其他腳本呼叫）
- `scripts/clean_face_env.sh` — 人臉辨識環境清理
- `scripts/device_detect.sh` — USB 音訊裝置自動偵測（必須用 `source`）
- `test_scripts/speech_30round.yaml` — 30 輪測試定義（15 固定 + 15 自由）

---

## 專案 Skills 使用時機

- **`demo-preflight`**：部署到 Jetson 後、Demo 展示前跑。`--quick` 5 項核心（2 分鐘），`--full` 15+ 項（5 分鐘）
- **`ros2-test-suite`**：改完 Python 後、commit 前跑。`--quick` 只跑 speech+face（3 秒），全套含 vision+go2
- **`meeting-sync`**：收到會議紀錄後，列出該更新哪些文件 + 產生 diff 建議
- **`jetson-deploy`**：程式碼改動要上 Jetson 時觸發
- **`jetson-verify`**：部署後跑 smoke test
- **`update-docs`**：每日收工前同步文件

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
# edge-tts（雲端主線，推薦）— 速度快、音質佳
ros2 run speech_processor tts_node --ros-args -p provider:=edge_tts

# Piper（本地離線 fallback）— 不依賴網路
ros2 run speech_processor tts_node --ros-args -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx
```

> MeloTTS、ElevenLabs 已淘汰（3/26 會議確認），不再支援。
