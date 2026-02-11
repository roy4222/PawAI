# 專案技術分析：老人與狗 (Elder and Dog)

**文件版本：** v1.0  
**分析日期：** 2026/01/09  
**分析範圍：** go2_robot_sdk, go2_interfaces, lidar_processor, lidar_processor_cpp, speech_processor, coco_detector

---

## 目錄

1. [概述](#概述)
2. [go2_robot_sdk — 核心機器狗驅動](#go2_robot_sdk--核心機器狗驅動)
3. [go2_interfaces — 自定義訊息與服務](#go2_interfaces--自定義訊息與服務)
4. [lidar_processor — LiDAR 點雲處理](#lidar_processor--lidar-點雲處理)
5. [speech_processor — 語音處理](#speech_processor--語音處理)
6. [coco_detector — 物件偵測](#coco_detector--物件偵測)
7. [系統整合架構](#系統整合架構)
8. [與評審回饋對齊分析](#與評審回饋對齊分析)
9. [下一步開發建議](#下一步開發建議)

---

## 概述

本專案「老人與狗」基於 ROS2 Humble 開發，整合 Unitree Go2 四足機器人、SLAM/Nav2 導航、AI 感知（YOLO-World + Depth Anything）與 MCP 協定，實現「聽得懂人話」的智能居家陪伴機器狗。

### 技術棧總覽

| 層級 | 技術 |
|------|------|
| **AI 大腦** | Claude 3.5 / GPT-4o (透過 MCP 協定) |
| **通訊橋接** | ros-mcp-server + rosbridge (WebSocket) |
| **機器人框架** | ROS2 Humble |
| **導航** | Nav2 + slam_toolbox |
| **感知** | YOLO-World + Depth Anything V2 (DA3) |
| **語音** | ElevenLabs TTS |
| **連線** | WebRTC (WiFi) / CycloneDDS (有線) |

---

## go2_robot_sdk — 核心機器狗驅動

### 架構設計

採用 **Clean Architecture** 分層設計：

```
go2_robot_sdk/
├── domain/           # 純業務邏輯 (無 ROS2 依賴)
│   ├── entities/     # RobotState, IMUData, CameraData
│   ├── interfaces/   # IRobotController, IRobotDataPublisher
│   ├── constants/    # ROBOT_CMD, RTC_TOPIC
│   └── math/         # 運動學、幾何計算
├── application/      # 應用服務層
│   ├── services/     # RobotDataService, RobotControlService
│   └── utils/        # CommandGenerator
├── infrastructure/   # 外部適配器
│   ├── webrtc/       # WebRTC 連線實作
│   ├── sensors/      # LiDAR/Camera 解碼器
│   └── ros2/         # ROS2Publisher
└── presentation/     # ROS2 節點入口
    └── go2_driver_node.py
```

### ROS2 Nodes

| Node 名稱 | Entry Point | 功能說明 |
|-----------|-------------|----------|
| `go2_driver_node` | `go2_robot_sdk.main:main` | 主驅動節點，處理所有感測器資料與控制指令 |
| `snapshot_service` | `go2_robot_sdk.snapshot_service:main` | 相機截圖服務，回傳 Base64 JPEG (MCP 整合用) |
| `move_service` | `go2_robot_sdk.move_service:main` | 定時移動服務，含 Safety Layer |

### 發布的 Topics

| Topic 名稱 | 訊息類型 | QoS | 說明 |
|------------|----------|-----|------|
| `/joint_states` | `sensor_msgs/JointState` | RELIABLE | 12 個關節狀態 |
| `/go2_states` | `go2_interfaces/Go2State` | RELIABLE | 機器狗完整狀態 |
| `/point_cloud2` | `sensor_msgs/PointCloud2` | BEST_EFFORT | LiDAR 點雲資料 |
| `/odom` | `nav_msgs/Odometry` | RELIABLE | 里程計資料 |
| `/imu` | `go2_interfaces/IMU` | RELIABLE | IMU 感測器資料 |
| `/camera/image_raw` | `sensor_msgs/Image` | BEST_EFFORT | 前置相機影像 |
| `/camera/camera_info` | `sensor_msgs/CameraInfo` | BEST_EFFORT | 相機內參 |
| `/utlidar/voxel_map_compressed` | `go2_interfaces/VoxelMapCompressed` | BEST_EFFORT | 體素地圖 (選用) |

### 訂閱的 Topics

| Topic 名稱 | 訊息類型 | 說明 |
|------------|----------|------|
| `/cmd_vel` | `geometry_msgs/Twist` | 移動控制指令 |
| `/webrtc_req` | `go2_interfaces/WebRtcReq` | WebRTC 請求 (執行動作) |
| `/joy` | `sensor_msgs/Joy` | 搖桿控制 |
| `/lowstate` | `go2_interfaces/LowState` | CycloneDDS 底層狀態 |
| `/utlidar/robot_pose` | `geometry_msgs/PoseStamped` | CycloneDDS 機器人位姿 |
| `/utlidar/cloud` | `sensor_msgs/PointCloud2` | CycloneDDS LiDAR 資料 |

### Services

| Service 名稱 | 類型 | 說明 |
|--------------|------|------|
| `/capture_snapshot` | `std_srvs/Trigger` | 擷取相機影像，回傳 Base64 JPEG |
| `/move_for_duration` | `go2_interfaces/MoveForDuration` | 定時移動 (含安全限制) |
| `/stop_movement` | `std_srvs/Trigger` | 緊急停止 |

### 連線模式

#### WebRTC 模式 (預設)

```bash
export ROBOT_IP="192.168.12.1"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py
```

- 透過 WiFi 連接機器狗
- 適合無線操控場景
- 延遲較高 (~50-100ms)

#### CycloneDDS 模式 (有線)

```bash
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="cyclonedds"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 launch go2_robot_sdk robot.launch.py
```

- 透過乙太網線直連 MCU
- 延遲極低 (<1ms)
- 適合 Demo 展示與精確控制

### Safety Layer (安全層)

`move_service` 內建安全限制：

| 參數 | 限制值 | 說明 |
|------|--------|------|
| `MAX_LINEAR` | 0.3 m/s | 最大線速度 |
| `MAX_ANGULAR` | 0.5 rad/s | 最大角速度 |
| `MAX_DURATION` | 10.0 秒 | 最大持續時間 |
| `PUBLISH_RATE` | 10 Hz | 指令發布頻率 |

### 可用動作指令 (ROBOT_CMD)

共 **45+ 個動作**，透過 `/webrtc_req` 發送：

#### 安全互動動作

| 動作名稱 | Command ID | 說明 |
|----------|------------|------|
| `Hello` | 1016 | 打招呼 |
| `Stretch` | 1017 | 伸懶腰 |
| `Dance1` | 1022 | 跳舞 1 |
| `Dance2` | 1023 | 跳舞 2 |
| `FingerHeart` | 1036 | 比愛心 |
| `WiggleHips` | 1033 | 扭屁股 |
| `Wallow` | 1021 | 打滾 |
| `Scrape` | 1029 | 刨地 |
| `Content` | 1020 | 滿足表情 |

#### 基礎控制動作

| 動作名稱 | Command ID | 說明 |
|----------|------------|------|
| `StandUp` | 1004 | 站立 |
| `StandDown` | 1005 | 趴下 |
| `Sit` | 1009 | 坐下 |
| `RiseSit` | 1010 | 從坐姿起身 |
| `RecoveryStand` | 1006 | 恢復站立 |
| `BalanceStand` | 1002 | 平衡站立 |
| `StopMove` | 1003 | 停止移動 |
| `Damp` | 1001 | 阻尼模式 |

#### 步態切換

| 動作名稱 | Command ID | 說明 |
|----------|------------|------|
| `EconomicGait` | 1035 | 經濟步態 |
| `FreeWalk` | 1045 | 自由行走 |
| `CrossWalk` | 1051 | 交叉步態 |
| `SwitchGait` | 1011 | 切換步態 |
| `ContinuousGait` | 1019 | 連續步態 |

#### 進階/危險動作

| 動作名稱 | Command ID | 說明 | 風險等級 |
|----------|------------|------|----------|
| `FrontFlip` | 1030 | 前空翻 | 🔴 高 |
| `FrontJump` | 1031 | 前跳 | 🟡 中 |
| `FrontPounce` | 1032 | 前撲 | 🟡 中 |
| `Handstand` | 1301 | 倒立 | 🔴 高 |
| `MoonWalk` | 1305 | 月球漫步 | 🟡 中 |
| `Bound` | 1304 | 彈跳 | 🟡 中 |
| `OnesidedStep` | 1303 | 單側步 | 🟡 中 |
| `CrossStep` | 1302 | 交叉步 | 🟡 中 |

#### 參數調整

| 動作名稱 | Command ID | 說明 |
|----------|------------|------|
| `BodyHeight` | 1013 | 調整身體高度 |
| `FootRaiseHeight` | 1014 | 調整抬腳高度 |
| `SpeedLevel` | 1015 | 調整速度等級 |
| `Euler` | 1007 | 調整姿態角 |
| `Pose` | 1028 | 調整姿勢 |
| `Move` | 1008 | 移動指令 |
| `TrajectoryFollow` | 1018 | 軌跡跟隨 |
| `Trigger` | 1012 | 觸發器 |
| `SwitchJoystick` | 1027 | 切換搖桿 |

---

## go2_interfaces — 自定義訊息與服務

### Messages (訊息)

| 訊息名稱 | 說明 | 主要欄位 |
|----------|------|----------|
| `Go2State.msg` | 機器狗完整狀態 | mode, gait_type, velocity[3], foot_force[4], position[3] |
| `Go2Cmd.msg` | 動作指令 | cmd (uint16) |
| `SportModeCmd.msg` | 運動模式控制 | mode, gait_type, speed_level, body_height, path_point[30] |
| `WebRtcReq.msg` | WebRTC 請求 | id, topic, api_id, parameter, priority |
| `IMU.msg` | IMU 資料 | 加速度、角速度、姿態 |
| `LowState.msg` | 底層狀態 | 馬達狀態、電池狀態 |
| `MotorState.msg` | 單馬達狀態 | 位置、速度、力矩 |
| `MotorCmd.msg` | 馬達控制指令 | 目標位置、速度、力矩 |
| `MotorStates.msg` | 所有馬達狀態 | 12 個馬達陣列 |
| `MotorCmds.msg` | 所有馬達指令 | 12 個馬達陣列 |
| `BmsState.msg` | 電池狀態 | 電量、電壓、電流、溫度 |
| `BmsCmd.msg` | 電池控制 | 充電/放電指令 |
| `LidarState.msg` | LiDAR 狀態 | 掃描資訊 |
| `VoxelMapCompressed.msg` | 壓縮體素地圖 | 3D 環境資料 |
| `VoxelHeightMapState.msg` | 高度圖狀態 | 地形資訊 |
| `HeightMap.msg` | 高度地圖 | 網格高度資料 |
| `PathPoint.msg` | 路徑點 | 位置、速度、時間 |
| `WirelessController.msg` | 無線控制器 | 搖桿輸入 |
| `AudioData.msg` | 音訊資料 | PCM 資料 |
| `Go2FrontVideoData.msg` | 前置影像資料 | 影像封包 |
| `Go2Move.msg` | 移動指令 | 速度向量 |
| `Go2RpyCmd.msg` | Roll-Pitch-Yaw 控制 | 姿態角指令 |
| `UwbState.msg` | UWB 狀態 | 定位資訊 |
| `UwbSwitch.msg` | UWB 開關 | 啟用/停用 |
| `InterfaceConfig.msg` | 介面配置 | 通訊設定 |
| `TimeSpec.msg` | 時間規格 | 時間戳 |
| `Req.msg` / `Res.msg` | 請求/回應 | 通用格式 |
| `Error.msg` | 錯誤訊息 | 錯誤碼、描述 |

### Services (服務)

| 服務名稱 | 說明 | Request | Response |
|----------|------|---------|----------|
| `MoveForDuration.srv` | 定時移動 | linear_x, angular_z, duration | success, message, actual_duration |

---

## lidar_processor — LiDAR 點雲處理

提供 Python 與 C++ 兩種實作，功能相同但 C++ 版本效能更高。

### Python 版本 (`lidar_processor`)

#### Nodes

| Node 名稱 | Entry Point | 功能 |
|-----------|-------------|------|
| `lidar_to_pointcloud` | `lidar_processor.lidar_to_pointcloud_node:main` | 點雲聚合與地圖存檔 |
| `pointcloud_aggregator` | `lidar_processor.pointcloud_aggregator_node:main` | 進階濾波與降採樣 |

#### Topics

| Topic | 類型 | 方向 | 說明 |
|-------|------|------|------|
| `/robot{i}/point_cloud2` | PointCloud2 | 訂閱 | 原始 LiDAR 資料 |
| `/pointcloud/aggregated` | PointCloud2 | 發布 | 聚合後點雲 |
| `/pointcloud/filtered` | PointCloud2 | 發布 | 濾波後點雲 |
| `/pointcloud/downsampled` | PointCloud2 | 發布 | 降採樣點雲 |

#### Parameters

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `robot_ip_lst` | [] | 機器人 IP 列表 |
| `map_name` | "3d_map" | 地圖檔案名稱 |
| `map_save` | "true" | 是否自動存檔 |
| `save_interval` | 10.0 | 存檔間隔 (秒) |
| `max_points` | 1000000 | 最大點數 |
| `voxel_size` | 0.01 | Voxel 降採樣大小 (公尺) |
| `max_range` | 20.0 | 最大範圍 (公尺) |
| `min_range` | 0.1 | 最小範圍 (公尺) |
| `height_filter_min` | -2.0 | 最小高度濾波 |
| `height_filter_max` | 3.0 | 最大高度濾波 |
| `downsample_rate` | 10 | 降採樣率 (1/N) |
| `publish_rate` | 5.0 | 發布頻率 (Hz) |

#### 處理功能

1. **點雲聚合** - 將多幀點雲合併成完整地圖
2. **記憶體管理** - 超過 `max_points` 時自動移除遠點
3. **範圍濾波** - 依據 `min_range` / `max_range` 過濾
4. **高度濾波** - 依據 Z 軸座標過濾
5. **統計離群值移除** - k-NN 統計分析移除雜訊
6. **Voxel 降採樣** - 使用 Open3D 進行體素降採樣
7. **自動存檔** - 定期將地圖存為 PLY 格式

### C++ 版本 (`lidar_processor_cpp`)

使用 **PCL (Point Cloud Library)** 實作，效能更高：

- 相同的 Topics 與 Parameters
- 使用 `pcl::VoxelGrid` 進行降採樣
- 使用 `pcl::StatisticalOutlierRemoval` 進行離群值移除
- 支援 PLY 格式存檔

---

## speech_processor — 語音處理

### Nodes

| Node 名稱 | Entry Point | 功能 |
|-----------|-------------|------|
| `tts_node` | `speech_processor.tts_node:main` | ElevenLabs TTS 語音合成 |
| `speech_synthesizer` | `speech_processor.speech_synthesizer_node:main` | 替代合成節點 |
| `audio_manager` | `speech_processor.audio_manager_node:main` | 音訊狀態管理 |

### Topics

| Topic | 類型 | 方向 | 說明 |
|-------|------|------|------|
| `/tts` | `std_msgs/String` | 訂閱 | 接收要說的文字 |
| `/webrtc_req` | `go2_interfaces/WebRtcReq` | 發布 | 送音訊到機器狗 |

### TTS 流程

```
1. 接收 /tts Topic (文字)
       ↓
2. 檢查快取 (AudioCache)
       ↓ (快取未命中)
3. 呼叫 ElevenLabs API 合成 MP3
       ↓
4. 轉換為 WAV 格式 (pydub)
       ↓
5. Base64 編碼並切分為 16KB chunks
       ↓
6. 透過 WebRTC 送到機器狗播放
   - API 4001: 開始
   - API 4003: 資料 (多個 chunks)
   - API 4002: 結束
```

### Parameters

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `api_key` | "" | ElevenLabs API Key |
| `provider` | "elevenlabs" | TTS 供應商 (elevenlabs/google/amazon/openai) |
| `voice_name` | "XrExE9yKIg1WjnnlVkGX" | 語音 ID |
| `model_id` | "eleven_turbo_v2_5" | 模型 ID |
| `local_playback` | false | 本地播放 (true) 或機器狗播放 (false) |
| `use_cache` | true | 啟用快取 |
| `cache_dir` | "tts_cache" | 快取目錄 |
| `chunk_size` | 16384 | 音訊分片大小 (bytes) |
| `audio_quality` | "standard" | 音質 (standard/high) |
| `language` | "en" | 語言 |
| `stability` | 0.5 | ElevenLabs 穩定度 |
| `similarity_boost` | 0.5 | ElevenLabs 相似度增強 |

### 支援的 TTS Provider

| Provider | 狀態 | 說明 |
|----------|------|------|
| ElevenLabs | ✅ 已實作 | 主要使用 |
| Google | 🔲 待實作 | 需整合 Google Cloud TTS |
| Amazon | 🔲 待實作 | 需整合 Amazon Polly |
| OpenAI | 🔲 待實作 | 需整合 OpenAI TTS |

---

## coco_detector — 物件偵測

### Node

| Node 名稱 | Entry Point | 功能 |
|-----------|-------------|------|
| `coco_detector_node` | `coco_detector.coco_detector_node` | COCO 物件偵測 |

### 模型

- **模型**: `FasterRCNN_MobileNet_V3_Large_320_FPN`
- **權重**: `COCO_V1` (預訓練於 COCO 資料集)
- **類別數**: 80 類 (人、車、動物、家具等)
- **框架**: PyTorch TorchVision

### Topics

| Topic | 類型 | 方向 | 說明 |
|-------|------|------|------|
| `/camera/image_raw` | `sensor_msgs/Image` | 訂閱 | 相機影像輸入 |
| `/detected_objects` | `vision_msgs/Detection2DArray` | 發布 | 偵測結果 (bbox + label) |
| `/annotated_image` | `sensor_msgs/Image` | 發布 | 標註後影像 (選用) |

### Parameters

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `device` | "cpu" | 運算裝置 (cpu/cuda) |
| `detection_threshold` | 0.9 | 偵測閾值 (0.0-1.0) |
| `publish_annotated_image` | true | 是否發布標註影像 |

### 輸出格式

```python
# Detection2DArray 內容
{
    "header": {...},
    "detections": [
        {
            "bbox": {
                "center": {"x": 320.0, "y": 240.0},
                "size_x": 100.0,
                "size_y": 150.0
            },
            "results": [
                {
                    "class_id": "chair",
                    "score": 0.95
                }
            ]
        }
    ]
}
```

### 與 YOLO-World 的比較

| 項目 | coco_detector | YOLO-World (GPU Server) |
|------|---------------|-------------------------|
| 模型 | FasterRCNN-MobileNet | YOLO-World-L |
| 類別 | 固定 80 類 | 開放詞彙 (任意物體) |
| 速度 | ~100ms (CPU) | ~50ms (GPU) |
| 深度 | ❌ 無 | ✅ 整合 DA3 |
| 部署 | 本地 | 遠端 GPU Server |

> **注意**: 專案目前使用 YOLO-World + DA3 融合架構作為主要感知方案，`coco_detector` 作為備案。

---

## 系統整合架構

### Launch 檔案

主要 Launch 檔案: `go2_robot_sdk/launch/robot.launch.py`

#### Launch Arguments

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `rviz2` | true | 啟動 RViz2 |
| `nav2` | true | 啟動 Nav2 導航 |
| `slam` | true | 啟動 SLAM |
| `foxglove` | true | 啟動 Foxglove Bridge |
| `joystick` | true | 啟動搖桿控制 |
| `teleop` | true | 啟動遙控 |
| `mcp_mode` | false | MCP 模式 (啟用 snapshot_service，停用 SLAM/Nav2) |

#### 啟動命令

```bash
# 完整系統 (SLAM + Nav2 + RViz)
ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=true

# MCP 模式 (用於 LLM 控制)
ros2 launch go2_robot_sdk robot.launch.py mcp_mode:=true

# 純驅動模式
ros2 launch go2_robot_sdk robot.launch.py slam:=false nav2:=false rviz2:=false

# 有線模式
export CONN_TYPE=cyclonedds
export ROBOT_IP=192.168.123.161
ros2 launch go2_robot_sdk robot.launch.py
```

### 節點通訊架構

```
┌─────────────────────────────────────────────────────────────────┐
│                        Host (Windows/Mac)                        │
├─────────────────────────────────────────────────────────────────┤
│  Claude/GPT ←→ ros-mcp-server ←→ rosbridge (WebSocket:9090)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Ubuntu VM (ROS2 Core)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │go2_driver_   │    │lidar_        │    │speech_       │      │
│  │node          │    │processor     │    │processor     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         ↓                   ↓                   ↓               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │snapshot_     │    │pointcloud_   │    │tts_node      │      │
│  │service       │    │aggregator    │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         ↓                   ↓                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │move_service  │    │slam_toolbox  │    │coco_detector │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                             ↓                                   │
│                      ┌──────────────┐                          │
│                      │    Nav2      │                          │
│                      └──────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Unitree Go2 (Robot)                          │
├─────────────────────────────────────────────────────────────────┤
│  MCU (192.168.123.161) ←→ WebRTC/CycloneDDS                     │
│  LiDAR, Camera, IMU, Motors                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 座標系統

| 座標框架 | 說明 | 使用場景 |
|----------|------|----------|
| `map` | SLAM 世界座標系 | Nav2 目標點 |
| `odom` | 里程計座標系 | 相對位移追蹤 |
| `base_link` | 機器狗本體中心 | 運動控制參考點 |
| `front_camera` | 前置相機 | ⚠️ 不是 `camera_link`! |
| `lidar_link` | LiDAR 座標系 | 點雲資料來源 |

---

## 與評審回饋對齊分析

根據 2026-01-07 評審回饋，分析現有能力與缺口：

### 一、技術架構與效能優化

| 評審建議 | 現有能力 | 缺口 | 解決方案 |
|----------|----------|------|----------|
| 避障不應交給 LLM | ✅ 有 Nav2 + LiDAR 處理 | 🔄 LLM 仍參與避障決策 | 解耦 LLM 與 Nav2，LLM 僅下達目標 |
| 使用深度相機 | ⚠️ DA3 單目深度估計 | 🔧 物理上不穩定 | 考慮加裝 RealSense 深度相機 |
| 本地化部署 | ❌ 依賴雲端 GPU Server | 🔧 網路延遲問題 | Go2 CPU 可跑 YOLOv8n (~10-20 FPS) |

### 二、應用場景與目標設定

| 評審建議 | 現有能力 | 缺口 | 解決方案 |
|----------|----------|------|----------|
| 物件尺寸限制 | ⚠️ 偵測大物體 OK | 🔧 小物體 (手機/鑰匙) 困難 | 明確定義可找物體範圍 |
| 環境強健性 | ⚠️ 理想環境 OK | 🔧 遮擋/光照變化 | 提升系統 Robustness |

### 三、系統安全性與防護層

| 評審建議 | 現有能力 | 缺口 | 解決方案 |
|----------|----------|------|----------|
| LLM 直接控制危險 | ✅ move_service 有 Safety Layer | 🔧 缺語音確認機制 | 執行前先說明動作意圖 |
| 速度限制 | ✅ MAX_LINEAR = 0.3 m/s | ✅ 已實作 | - |

### 四、未來創意與亮點發揮

| 評審建議 | 現有能力 | 缺口 | 解決方案 |
|----------|----------|------|----------|
| Skills 模組化 | ⚠️ 動作分散各處 | 🔧 需整合成 Skills | 將動作打包成 MCP Skills |
| IoT 整合 | ❌ 未實作 | 🔧 可結合智慧手環 | 透過 MQTT 整合 |

### 五、有線連接優勢

| 項目 | WiFi (WebRTC) | 有線 (CycloneDDS) |
|------|---------------|-------------------|
| 延遲 | ~50-100ms | <1ms |
| 穩定性 | 易受干擾 | 極穩定 |
| Nav2 效能 | 一般 | 優秀 |
| Demo 適用 | ⚠️ 風險較高 | ✅ 推薦 |

---

## 下一步開發建議

### 優先順序 1：解耦 LLM 與 Nav2

```
現狀: LLM → 拍照 → 決策 → cmd_vel (慢)
目標: LLM → 設定目標 → Nav2 自動導航 (快)
```

**實作要點**:
1. LLM 僅呼叫 `/navigate_to_pose` Action
2. Nav2 負責避障與路徑規劃
3. LLM 專注於語意理解與高階任務

### 優先順序 2：語音回饋機制

**實作要點**:
1. 執行動作前透過 TTS 說明意圖
2. 給使用者確認或喊停的機會
3. 例：「我看到椅子在右邊，我現在要轉過去囉」

### 優先順序 3：Skills 模組化

將以下功能封裝為 MCP Skills:

| Skill 名稱 | 功能 | 包含動作 |
|------------|------|----------|
| `greet` | 打招呼 | Hello, Dance1 |
| `search_object` | 尋物 | 移動 + 拍照 + 偵測 |
| `patrol` | 巡邏 | Nav2 + 定期拍照 |
| `perform_trick` | 表演 | Dance1, FingerHeart, WiggleHips |
| `follow_me` | 跟隨 | 持續追蹤人物 |

### 優先順序 4：本地化部署

**選項 A**: Go2 CPU 運行 YOLOv8n
- 優點：完全離線
- 缺點：準確率較低

**選項 B**: 本地 GPU PC
- 優點：高準確率
- 缺點：需額外設備

---

## 附錄：快速參考

### 常用指令

```bash
# 環境設定
source /opt/ros/humble/setup.bash
source install/setup.bash

# 建置
colcon build
colcon build --packages-select go2_robot_sdk

# 啟動 (WiFi)
export ROBOT_IP=192.168.12.1
export CONN_TYPE=webrtc
ros2 launch go2_robot_sdk robot.launch.py

# 啟動 (有線)
export ROBOT_IP=192.168.123.161
export CONN_TYPE=cyclonedds
ros2 launch go2_robot_sdk robot.launch.py

# MCP 模式
ros2 launch go2_robot_sdk robot.launch.py mcp_mode:=true

# 測試 TTS
ros2 topic pub /tts std_msgs/String "data: '你好，我是小狗'"

# 執行動作
ros2 topic pub /webrtc_req go2_interfaces/WebRtcReq \
  "{api_id: 1016, topic: 1001, parameter: '', priority: 0}"
```

### 關鍵檔案路徑

| 檔案 | 路徑 |
|------|------|
| 主驅動節點 | `go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py` |
| 動作指令定義 | `go2_robot_sdk/go2_robot_sdk/domain/constants/robot_commands.py` |
| 截圖服務 | `go2_robot_sdk/go2_robot_sdk/snapshot_service.py` |
| 移動服務 | `go2_robot_sdk/go2_robot_sdk/move_service.py` |
| 主 Launch 檔 | `go2_robot_sdk/launch/robot.launch.py` |
| TTS 節點 | `speech_processor/speech_processor/tts_node.py` |
| 物件偵測 | `coco_detector/coco_detector/coco_detector_node.py` |
| LiDAR 處理 | `lidar_processor/lidar_processor/lidar_to_pointcloud_node.py` |

---

**文件維護者**: Elder and Dog 專案團隊  
**最後更新**: 2026/01/09
