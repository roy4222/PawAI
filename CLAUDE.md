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
**當前日期：2026-03-11（Phase 1 基礎建設期尾端）**

以 Unitree Go2 Pro 為載體的 **embodied AI 互動陪伴平台**。核心是「人臉辨識 + 中文語音互動 + AI 大腦決策」，不是導航或尋物。

### 優先序

| P0（必交） | P1（展示亮點） | P2（加分） |
|------------|---------------|-----------|
| 人臉辨識 (YuNet+SFace) | 手勢辨識 | 基礎導航/避障 |
| 中文語音互動 (ASR+TTS) | 姿勢辨識 | 喚醒詞 |
| AI 大腦 (Interaction Executive v1) | | |
| 展示網站 (FastAPI+Next.js) | | |

### 硬體配置

| 設備 | 用途 |
|------|------|
| Unitree Go2 Pro | 運動執行、LiDAR/IMU |
| NVIDIA Jetson Orin Nano 8GB | 邊緣運算、ROS2 runtime |
| Intel RealSense D435 | RGB-D 深度攝影機（**無內建麥克風**） |
| USB 麥克風 | 語音輸入 |
| 5×RTX 8000 (遠端) | ASR/LLM/TTS 雲端推理 |

---

## 建構與執行

### 基本建構

```bash
source /opt/ros/humble/setup.bash   # 或 setup.zsh（Jetson 用 zsh）
colcon build                                        # 全部
colcon build --packages-select go2_robot_sdk        # 單一套件
colcon build --packages-select speech_processor     # 語音模組
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
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx
```

### 快速驗證 TTS → Go2 播放

```bash
ros2 topic pub --once /tts std_msgs/msg/String '{data: "測試播放"}'
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

```
Layer 3: Interaction Executive v1（中控層，Jetson）
  ├─ 事件聚合 → 狀態機 → 技能分派 → 安全仲裁
  └─ 訂閱 Layer 2 事件，發布動作指令

Layer 2: Perception / Interaction（Jetson + 雲端混合）
  ├─ 人臉模組 → /event/face_detected, /state/perception/face
  ├─ 語音模組 → /event/speech_intent_recognized
  └─ 手勢模組 → /event/gesture_detected (P1)

Layer 1: Device / Runtime（Jetson + Go2）
  ├─ go2_robot_sdk (Go2 驅動)
  ├─ realsense2_camera (D435)
  ├─ ALSA/PulseAudio (音訊)
  └─ ROS2 Humble
```

---

## ROS2 套件與節點

### go2_robot_sdk（主驅動）

Clean Architecture 分層：
- `presentation/go2_driver_node.py` — 節點入口，ROS2 訂閱/發布
- `application/services/robot_control_service.py` — 動作命令處理
- `infrastructure/webrtc/webrtc_adapter.py` — WebRTC 通訊層
- `infrastructure/webrtc/go2_connection.py` — DataChannel 實際收發
- `application/utils/command_generator.py` — Go2 WebRTC 命令格式生成
- `domain/constants/webrtc_topics.py` — API ID 常數（4001-4005 音訊、1008 運動等）

**WebRTC 音訊播放協議（api_id）**：
| api_id | 動作 | parameter |
|--------|------|-----------|
| 4004 | 設定音量 | `"80"` (0-100) |
| 4001 | 開始播放 | `""` |
| 4003 | 音訊資料塊 | `{"current_block_index":N, "total_block_number":M, "block_content":"base64..."}` |
| 4002 | 停止播放 | `""` |

所有命令走 topic `rt/api/audiohub/request`，透過 WebRTC DataChannel 發送。

### speech_processor（語音模組）

**節點清單**：
| 節點 | 用途 |
|------|------|
| `stt_intent_node` | **整合型**：音訊錄製 + ASR + Intent（no-VAD 主線用） |
| `vad_node` | Silero VAD 語音活動偵測 |
| `asr_node` | 獨立 ASR（搭配 vad_node 用） |
| `intent_node` | 獨立 Intent 規則匹配 |
| `intent_tts_bridge_node` | Intent → 模板回覆 → `/tts` |
| `tts_node` | TTS 合成 + Go2 播放（支援 ElevenLabs/Piper/MeloTTS） |

**語音管線（no-VAD 主線，展示用）**：
```
USB 麥克風 → stt_intent_node (Whisper Tiny ASR + 規則 Intent)
  → /event/speech_intent_recognized
  → intent_tts_bridge_node (模板回覆)
  → /tts
  → tts_node (Piper 本地合成)
  → /webrtc_req
  → go2_driver_node → DataChannel → Go2 喇叭
```

**TTS Provider 切換**：透過 `-p provider:=piper|melotts|elevenlabs` 參數

**配置檔**：`speech_processor/config/speech_processor.yaml`

### go2_interfaces（訊息定義）

自訂 ROS2 訊息，關鍵型別：
- `WebRtcReq.msg`：`{id, topic, api_id, parameter, priority}` — 所有 Go2 WebRTC 命令的統一格式

### 其他套件

- `coco_detector`：COCO 物件檢測（P2，非主線）
- `lidar_processor` / `lidar_processor_cpp`：LiDAR 點雲處理
- `search_logic`：尋物狀態機（P2）

---

## 關鍵 ROS2 Topic

**語音鏈路**：
```
/event/speech_activity          ← VAD 事件 (speech_start/speech_end)
/asr_result                     ← ASR 文字輸出
/intent                         ← Intent 標籤
/event/speech_intent_recognized ← 詳細 Intent 事件 (JSON)
/tts                            ← TTS 輸入文字
/webrtc_req                     ← Go2 WebRTC 命令
/state/interaction/speech       ← 語音狀態監控
```

**感測器**：
```
/joint_states (1 Hz)  /imu (50 Hz)  /point_cloud2 (7 Hz)  /camera/image_raw (10 Hz)
/scan (~5 Hz)  /tf  /tf_static
```

---

## 開發環境

### 雙平台架構

- **Windows/Mac（開發機）**：VS Code SSH → Jetson，程式碼編輯、文件撰寫
- **Jetson Orin Nano（邊緣端）**：ROS2 runtime、模型推理、Go2 連線
- **Go2 Pro**：192.168.12.1（Wi-Fi AP）或 192.168.123.161（Ethernet）

### Jetson 操作要點

- Shell 用 **zsh**：source 時用 `setup.zsh` 而非 `setup.bash`
- 麥克風 default 裝置常漂移，啟動時需指定 `input_device:=0`
- 麥克風原生 44.1kHz，node 內重取樣至 16kHz：`capture_sample_rate:=44100`
- zsh 的 glob 會炸掉陣列參數：用 `'["whisper_local"]'` 加引號，或 `setopt nonomatch`
- `setup.bash` / `setup.zsh` 不可混用，否則環境不完整

### Jetson 測試規範

- 同時間只允許一套 speech session（禁止多 tmux 混跑）
- 測試前必須 clean-start：`tmux kill-session` + `pkill` 舊 process
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

---

## 關鍵文件索引

### Mission（專案方向，最新來源）
- `docs/mission/README.md` — 入口頁，三層架構、Demo 定義、團隊分工
- `docs/mission/vision.md` — 願景
- `docs/mission/roadmap.md` — 時程與里程碑
- `docs/mission/meeting_notes_supplement.md` — 會議未定事項

### 架構與契約
- `docs/architecture/interaction_contract.md` — 介面契約（3/9 凍結）
- `docs/architecture/brain_v1.md` — AI 大腦設計

### 語音功能
- `docs/語音功能/README.md` — 語音模組設計
- `docs/語音功能/jetson-MVP測試.md` — Jetson 語音 MVP 測試手冊（Phase 1-6 + 踩坑記錄）

### 配置檔
- `go2_robot_sdk/config/` — SLAM/Nav2/CycloneDDS/Joystick 參數
- `speech_processor/config/speech_processor.yaml` — 語音模組參數
- `go2_robot_sdk/launch/robot.launch.py` — 主 launch（修改後不需 rebuild）

### 測試腳本
- `scripts/start_asr_tts_no_vad_tmux.sh` — 語音 MVP no-VAD 主線一鍵啟動
- `scripts/start_speech_e2e_tmux.sh` — 端到端語音測試
- `phase1_test.sh` — SLAM/Nav2 Phase 1 測試

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
