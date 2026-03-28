# Baseline Contract

**建立日期：** 2026-03-28（Sprint B-prime Day 1）
**最後更新：** 2026-03-28

## 文件狀態

| 區塊 | 狀態 |
|------|------|
| 1. 啟動順序 | 已填（靜態基線）|
| 2. QoS 配置表 | 2a 靜態推導已填 / 2b Runtime 已填 |
| 3. Device Mapping | 已填（2026-03-28 實測）|
| 4. Topic Graph | 已填（2026-03-28 實測）|
| 5. Crash Recovery SOP | 已填 |
| 6. 驗收結果 | 已填（3/3 cold start PASS + 1/1 crash recovery PASS）|

---

## 1. 啟動順序

來源：`scripts/start_full_demo_tmux.sh`

### 前置條件

1. Go2 已開機，等 30s WebRTC ready
2. Jetson 已開機
3. SSH tunnel 到 RTX 8000（Cloud LLM）：`ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5`

### 啟動命令

```bash
source /opt/ros/humble/setup.zsh
source ~/elder_and_dog/install/setup.zsh
source scripts/device_detect.sh
INPUT_DEVICE="$DETECTED_MIC_INDEX" \
  CHANNELS="$DETECTED_MIC_CHANNELS" \
  CAPTURE_SAMPLE_RATE="$DETECTED_CAPTURE_RATE" \
  LOCAL_OUTPUT_DEVICE="$DETECTED_SPK_DEVICE" \
  bash scripts/start_full_demo_tmux.sh
```

### Window 啟動順序

| Phase | Window | Name | 啟動命令 | Sleep | Ready 判定 |
|:-----:|:------:|------|---------|:-----:|-----------|
| 基礎設施 | 0 | go2 | `ros2 launch go2_robot_sdk robot.launch.py` | 10s | WebRTC ICE connected（log 中出現 "connected"）|
| 基礎設施 | 1 | camera | `ros2 launch realsense2_camera rs_launch.py` | 5s | `/camera/camera/color/image_raw` 有發布 |
| 感知 | 2 | face | `ros2 launch face_perception face_perception.launch.py` | 5s | `/state/perception/face` 有發布 |
| 感知 | 3 | vision | `ros2 launch vision_perception vision_perception.launch.py` | 5s | `/event/gesture_detected` topic 存在 |
| 感知 | 4 | router | `ros2 launch vision_perception interaction_router.launch.py` | 2s | `/event/interaction/welcome` topic 存在 |
| 語音 | 5 | asr | `ros2 run speech_processor stt_intent_node` | 15s | log 出現 "warmup_done" 或 "Whisper model loaded" |
| 決策 | 6 | tts | `ros2 run speech_processor tts_node` | 3s | `/state/tts_playing` 有發布 |
| 決策 | 7 | llm | `ros2 run speech_processor llm_bridge_node` | 3s | log 出現 "LLM bridge ready" |
| 決策 | 8 | bridge | `ros2 launch vision_perception event_action_bridge.launch.py` | 2s | 無特殊判定 |
| 輔助 | 9 | fox | `ros2 launch foxglove_bridge foxglove_bridge_launch.xml` | — | Foxglove 可連線 |

**總啟動時間：** ~50 秒（含 15s Whisper CUDA warmup）

### 環境變數（可覆寫預設值）

| 變數 | 預設值 | 用途 |
|------|--------|------|
| `ROBOT_IP` | 192.168.123.161 | Go2 IP |
| `CONN_TYPE` | webrtc | 連線方式 |
| `INPUT_DEVICE` | 24 | 麥克風 ALSA card number |
| `CHANNELS` | 1 | 麥克風聲道（USB mono=1, HyperX stereo=2）|
| `CAPTURE_SAMPLE_RATE` | 48000 | 麥克風原生取樣率 |
| `MIC_GAIN` | 4.0 | 麥克風增益 |
| `TTS_PROVIDER` | edge_tts | TTS 引擎（edge_tts / piper）|
| `LOCAL_PLAYBACK` | true | true=USB 喇叭, false=Go2 Megaphone |
| `LOCAL_OUTPUT_DEVICE` | plughw:3,0 | 喇叭 ALSA 裝置 |
| `LLM_ENDPOINT` | http://localhost:8000/v1/chat/completions | 雲端 LLM |
| `LLM_MODEL` | Qwen/Qwen2.5-7B-Instruct | 雲端模型 |
| `ENABLE_LOCAL_LLM` | true | 本地 LLM fallback |
| `LOCAL_LLM_MODEL` | qwen2.5:1.5b | 本地模型（Ollama）|

---

## 2. QoS 配置表

### 2a. 靜態推導（從程式碼提取）

| Topic | Publisher | QoS | Depth | Durability | 備註 |
|-------|-----------|-----|:-----:|------------|------|
| `/camera/camera/color/image_raw` | realsense2_camera | BEST_EFFORT | 5 | VOLATILE | D435 driver 預設 |
| `/camera/camera/depth/image_rect_raw` | realsense2_camera | BEST_EFFORT | 5 | VOLATILE | D435 driver 預設 |
| `/state/perception/face` | face_identity_node | RELIABLE | 10 | VOLATILE | 10Hz JSON |
| `/event/face_identity` | face_identity_node | RELIABLE | 10 | VOLATILE | 偵測到已知人臉 |
| `/event/gesture_detected` | vision_perception_node | RELIABLE | 10 | VOLATILE | 手勢事件 |
| `/event/pose_detected` | vision_perception_node | RELIABLE | 10 | VOLATILE | 姿勢事件 |
| `/vision_perception/debug_image` | vision_perception_node | RELIABLE | 1 | VOLATILE | Foxglove 用 |
| `/event/interaction/welcome` | interaction_router | RELIABLE | 10 | VOLATILE | 歡迎事件 |
| `/event/interaction/gesture_command` | interaction_router | RELIABLE | 10 | VOLATILE | 手勢命令 |
| `/event/interaction/fall_alert` | interaction_router | RELIABLE | 10 | VOLATILE | 跌倒警報 |
| `/event/speech_intent_recognized` | stt_intent_node | RELIABLE | 10 | VOLATILE | 語音 intent |
| `/state/tts_playing` | tts_node | RELIABLE | 1 | **TRANSIENT_LOCAL** | Latched 狀態 |
| `/tts` | 多個 publisher | RELIABLE | 10 | VOLATILE | TTS 文字 |
| `/webrtc_req` | 多個 publisher | RELIABLE | 10 | VOLATILE | Go2 動作 |
| `/tts_audio_raw` | tts_node | RELIABLE | 10 | VOLATILE | 音訊串流 |

**特殊 QoS 注意：**
- 相機 image 訂閱者（face_identity_node, vision_perception_node）使用 **BEST_EFFORT + depth=1** 匹配 D435 driver
- `/state/tts_playing` 使用 **TRANSIENT_LOCAL** — 訂閱者連上後會收到最後一次值（echo gate 機制）
- Go2 driver 的感測器 topic（point_cloud2, camera/image_raw）使用 **BEST_EFFORT + depth=5**

### 2b. Runtime 實測（2026-03-28）

所有 topic 的 negotiated QoS 與靜態推導一致，無意外。

| Topic | Pub → Sub | Reliability | Durability | 驗證 |
|-------|-----------|:-----------:|:----------:|:----:|
| `/state/perception/face` | face_identity → interaction_router, llm_bridge | RELIABLE | VOLATILE | ✅ |
| `/event/face_identity` | face_identity → interaction_router, llm_bridge | RELIABLE | VOLATILE | ✅ |
| `/event/gesture_detected` | vision_perception → interaction_router | RELIABLE | VOLATILE | ✅ |
| `/event/pose_detected` | vision_perception → interaction_router | RELIABLE | VOLATILE | ✅ |
| `/event/speech_intent_recognized` | stt_intent → llm_bridge | RELIABLE | VOLATILE | ✅ |
| `/state/tts_playing` | tts_node → event_action_bridge, stt_intent | RELIABLE | **TRANSIENT_LOCAL** | ✅ |
| `/tts` | event_action_bridge, llm_bridge → tts_node | RELIABLE | VOLATILE | ✅ |
| `/webrtc_req` | tts_node, llm_bridge, event_action_bridge → go2_driver | RELIABLE | VOLATILE | ✅ |

---

## 3. Device Mapping（2026-03-28 實測）

```
DETECTED_MIC_INDEX=0
DETECTED_MIC_CHANNELS=1
DETECTED_CAPTURE_RATE=48000
DETECTED_SPK_DEVICE=plughw:3,0
D435=yes (6 video devices)
```

| 裝置 | lsusb ID | ALSA Card | 備註 |
|------|----------|:---------:|------|
| USB Mic (UACDemoV1.0) | `4c4a:4155` Jieli Technology | card 0 | mono, 48kHz |
| USB Speaker (CD002-AUDIO) | `e2b8:0811` Jieli Technology | card 3 | — |
| Intel RealSense D435 | `8086:0b07` Intel Corp. | — | 6 video devices |
| Jetson HDA (HDMI) | — | card 1 | 不使用 |
| Jetson APE | — | card 2 | 不使用 |

**啟動前必須：** `source scripts/device_detect.sh`（mic 從預設 24 飄到 0）

### 已知問題

- USB device index **重開機後會漂移**（mic 24→0, speaker hw:3,0→hw:1,0）
- 解法：啟動前先 `source scripts/device_detect.sh`，用偵測到的值覆寫 env vars

---

## 4. Topic Graph（2026-03-28 實測）

### Node List（16 nodes）

```
/camera/camera
/event_action_bridge
/face_identity_node
/foxglove_bridge
/go2_driver_node
/go2_pointcloud_to_laserscan
/go2_robot_state_publisher
/go2_teleop_node
/interaction_router
/joy_node
/llm_bridge_node
/stt_intent_node
/transform_listener_impl_aaaac6b4fbe0
/tts_node
/twist_mux
/vision_perception_node
```

### Topic List（51 topics）

```
/asr_result
/camera/camera/aligned_depth_to_color/camera_info
/camera/camera/aligned_depth_to_color/image_raw
/camera/camera/aligned_depth_to_color/image_raw/compressed
/camera/camera/color/camera_info
/camera/camera/color/image_raw
/camera/camera/color/image_raw/compressed
/camera/camera/color/metadata
/camera/camera/depth/camera_info
/camera/camera/depth/image_rect_raw
/camera/camera/depth/image_rect_raw/compressed
/camera/camera/depth/metadata
/camera/camera/extrinsics/depth_to_color
/camera/camera/extrinsics/depth_to_depth
/cmd_vel
/cmd_vel_joy
/cmd_vel_out
/diagnostics
/event/face_identity
/event/gesture_detected
/event/interaction/fall_alert
/event/interaction/gesture_command
/event/interaction/welcome
/event/pose_detected
/event/speech_activity
/event/speech_intent_recognized
/face_identity/compare_image
/face_identity/debug_image
/go2_states
/imu
/intent
/joint_states
/joy
/joy/set_feedback
/odom
/parameter_events
/point_cloud2
/robot_description
/rosout
/scan
/speech/text_input
/state/interaction/llm_bridge
/state/interaction/speech
/state/perception/face
/state/tts_playing
/tf
/tf_static
/tts
/tts_audio_raw
/vision_perception/debug_image
/webrtc_req
```

---

## 5. Crash Recovery SOP

**目標：** 從任意 crash 到系統恢復 < 3 分鐘。

### 標準恢復流程

```bash
# Step 1: 全清
bash scripts/clean_full_demo.sh
ros2 daemon stop 2>/dev/null; sleep 3

# Step 2: 確認乾淨
ros2 node list    # 應該是空的

# Step 3: 重啟（用 device_detect 偵測音訊裝置）
source scripts/device_detect.sh
INPUT_DEVICE="$DETECTED_MIC_INDEX" \
  CHANNELS="$DETECTED_MIC_CHANNELS" \
  CAPTURE_SAMPLE_RATE="$DETECTED_CAPTURE_RATE" \
  LOCAL_OUTPUT_DEVICE="$DETECTED_SPK_DEVICE" \
  bash scripts/start_full_demo_tmux.sh

# Step 4: 驗證（等 ~50s）
ros2 topic list | wc -l    # 應 >= 15
ros2 topic echo /state/perception/face --once    # 應看到 JSON
```

### 特殊情況

| 症狀 | 處理 |
|------|------|
| Go2 WebRTC 斷線 | Power cycle Go2（等 30s）→ 重啟 demo |
| tts_node 重啟後 Megaphone 靜音 | 必須一併重啟 Go2 driver，甚至 Go2 重開機 |
| 多個 driver instance 殘留 | `pkill -9 -f go2_driver; pkill -9 -f robot_state` |
| Jetson OOM | `sudo systemctl restart nvargus-daemon` → 重啟 demo |
| USB device index 飄移 | `source scripts/device_detect.sh` → 用新值重啟 |
| Go2 WebRTC ICE FROZEN→FAILED | 等第二個 candidate（~10s），或重啟 Go2 |

### 清理腳本

```bash
bash scripts/clean_full_demo.sh    # 清 demo 全環境
bash scripts/clean_speech_env.sh   # 只清語音
bash scripts/clean_face_env.sh     # 只清人臉
bash scripts/clean_all.sh          # 清語音 + Go2 driver（不含 vision/face）
```

---

## 6. 驗收結果

### 必要 Topics Checklist

驗收時，以下 9 個 topic 必須全部存在：

| # | Topic | Publisher |
|:-:|-------|-----------|
| 1 | `/state/perception/face` | face_identity_node |
| 2 | `/event/face_identity` | face_identity_node |
| 3 | `/event/gesture_detected` | vision_perception_node |
| 4 | `/event/pose_detected` | vision_perception_node |
| 5 | `/event/speech_intent_recognized` | stt_intent_node |
| 6 | `/event/interaction/welcome` | interaction_router |
| 7 | `/event/interaction/gesture_command` | interaction_router |
| 8 | `/tts` | llm_bridge_node / event_action_bridge |
| 9 | `/webrtc_req` | tts_node / llm_bridge_node / event_action_bridge → go2_driver_node (sub) |

### Pass 標準

- **Cold start：** 9 個必要 topic 全部存在 + 8 個具名 node 全部活著（go2_driver_node, face_identity_node, vision_perception_node, interaction_router, stt_intent_node, tts_node, llm_bridge_node, event_action_bridge）
- **Crash recovery：** 從 kill node 到上述 topic + node 全部恢復 < 3 分鐘

---

### Cold Start #1（即 Step 2 首次啟動）

- 開始時間：~21:30
- 完成時間：~21:31
- 存活 nodes：16/16
- 必要 topics 檢查：
  - [x] /state/perception/face
  - [x] /event/face_identity
  - [x] /event/gesture_detected
  - [x] /event/pose_detected
  - [x] /event/speech_intent_recognized
  - [x] /event/interaction/welcome
  - [x] /event/interaction/gesture_command
  - [x] /tts
  - [x] /webrtc_req
- 必要 nodes 檢查：8/8（go2_driver, face_identity, vision_perception, interaction_router, stt_intent, tts, llm_bridge, event_action_bridge）
- 需人工介入：否
- 結果：**PASS**

---

### Cold Start #2

- 開始時間：~21:36
- 完成時間：~21:37
- 存活 nodes：16/16
- 必要 topics：9/9 ✅
- 必要 nodes：8/8 ✅
- 需人工介入：否
- 結果：**PASS**
- 備註：clean 後 ros2 node list 有 DDS cache 殘留，等 3s + daemon stop 後清除

---

### Cold Start #3

- 開始時間：~21:40
- 完成時間：~21:41
- 存活 nodes：16/16
- 必要 topics：9/9 ✅
- 必要 nodes：8/8 ✅
- 需人工介入：否
- 結果：**PASS**

---

### Crash Recovery #1

- 被殺的 node：face_identity_node
- Kill 時間：21:45:36
- clean_full_demo.sh 完成時間：21:45:54
- 重啟完成時間：21:47:02
- **恢復耗時：1 分 26 秒**
- 存活 nodes：16/16
- 必要 topics：9/9 ✅
- 必要 nodes：8/8 ✅
- 需人工介入：否
- 結果：**PASS**（1m26s < 3 分鐘）

---

### 已知發現

- `clean_full_demo.sh` 殺完 process 後，`ros2 node list` 仍有 DDS discovery cache 殘留（~3-5 秒後自動消失）
- 建議：clean script 加 `ros2 daemon stop && sleep 3` 再驗證，或驗收時用 `ps aux` 而非 `ros2 node list`
- USB mic device index 從預設 24 飄到 0（device_detect.sh 正確偵測）
