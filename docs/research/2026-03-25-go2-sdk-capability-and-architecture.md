# go2_robot_sdk 能力總覽 & 專案 Clean Architecture 藍圖

**文件類型**：技術參考 + 架構設計
**建立日期**：2026-03-25
**作者**：PawAI System Architecture
**狀態**：ACTIVE — 專案架構方向的 single source of truth
**適用範圍**：全專案所有 ROS2 package

---

## 1. 摘要

本文件包含兩大部分：

1. **go2_robot_sdk 完整能力參考** — 42 個 Sport Mode 指令、5 個 AudioHub 指令、6 類感測器、完整 ROS2 Topic/Subscriber/Service 清單，以及 WebRtcReq 訊息格式。
2. **專案 Clean Architecture 藍圖** — 定義 domain/application/infrastructure/presentation 四層分離原則、各 package 現狀評估、目標模組結構，以及漸進式遷移路徑。

### 核心發現

| 面向 | 狀態 |
|------|------|
| go2_robot_sdk | 已實作 Clean Architecture 四層分離，是專案標竿 |
| Sport Mode API | 42 個 api_id（含重複 StandUp/Standup），涵蓋姿勢/移動/表演/特技/查詢 |
| AudioHub API | 5 個指令（4001-4005），Megaphone DataChannel 播放已驗證穩定 |
| 感測器 | LiDAR (<2Hz)、前鏡頭 (WebRTC)、IMU、12 關節、里程計、Robot State |
| 7 大功能 SDK 支持度 | 語音 100%、人臉 80%、手勢 70%、姿勢 70%、物件偵測 60%、避障 40%、導航 30% |
| 其他 package 架構 | speech_processor/face_perception/vision_perception 均為 flat 結構，存在 god file |
| interaction_executive | 未建立，事件路由分散在 llm_bridge + interaction_router 兩條獨立路徑 |
| 硬編碼路徑 | 41 個檔案含 `/home/jetson/` 共 169 處 |

---

## 2. go2_robot_sdk 完整 API 參考

### 2.1 Sport Mode 動作指令（42 個 api_id）

所有 Sport Mode 指令透過 `rt/api/sport/request` topic 發送，api_id 定義於 `go2_robot_sdk/domain/constants/robot_commands.py`（`ROBOT_CMD` dict）。

#### 2.1.1 基礎姿勢控制（9 個）

| 指令名稱 | api_id | 說明 | 參數 |
|-----------|:------:|------|------|
| Damp | 1001 | 阻尼模式（軟停） | 無 |
| BalanceStand | 1002 | 平衡站立 | 無 |
| StopMove | 1003 | 停止移動 | 無 |
| StandUp | 1004 | 站起 | 無 |
| StandDown | 1005 | 蹲下 | 無 |
| RecoveryStand | 1006 | 恢復站立（倒地自救） | 無 |
| Sit | 1009 | 坐下 | 無 |
| RiseSit | 1010 | 從坐姿起身 | 無 |
| StandOut | 1039 | 伸展站立 | 無 |

#### 2.1.2 基礎移動控制（5 個）

| 指令名稱 | api_id | 說明 | 參數 |
|-----------|:------:|------|------|
| Move | 1008 | 移動 | `{"x": float, "y": float, "z": float}` |
| SpeedLevel | 1015 | 速度等級 | 等級值 |
| BodyHeight | 1013 | 身體高度 | 高度值 |
| FootRaiseHeight | 1014 | 抬腳高度 | 高度值 |
| Standup | 1050 | 站起（替代指令） | 無 |

> **注意**：`StandUp`(1004) 與 `Standup`(1050) 為兩個不同的 api_id，行為可能略有差異。SDK 主線使用 1004。

#### 2.1.3 表演動作（11 個）

| 指令名稱 | api_id | 說明 |
|-----------|:------:|------|
| Hello | 1016 | 打招呼（揮手） |
| Content | 1020 | 開心搖尾巴 |
| Stretch | 1017 | 伸懶腰 |
| Wallow | 1021 | 撒嬌打滾 |
| Dance1 | 1022 | 舞蹈 1 |
| Dance2 | 1023 | 舞蹈 2 |
| WiggleHips | 1033 | 搖屁股 |
| Pose | 1028 | 擺 Pose |
| Scrape | 1029 | 刨地 |
| FingerHeart | 1036 | 比愛心 |
| CrossWalk | 1051 | 交叉步行走 |

#### 2.1.4 特技動作（6 個）

| 指令名稱 | api_id | 說明 | 安全性 |
|-----------|:------:|------|:------:|
| FrontFlip | 1030 | 前空翻 | BANNED |
| FrontJump | 1031 | 前跳 | BANNED |
| FrontPounce | 1032 | 前撲 | 允許 |
| Handstand | 1301 | 倒立 | BANNED |
| CrossStep | 1302 | 交叉步 | 允許 |
| OnesidedStep | 1303 | 單側步 | 允許 |

> **BANNED 指令**：`llm_contract.py` 定義 `BANNED_API_IDS = {1030, 1031, 1301}`，LLM 不得透過語音觸發這三個高危動作。

#### 2.1.5 進階步態控制（7 個）

| 指令名稱 | api_id | 說明 |
|-----------|:------:|------|
| Euler | 1007 | 歐拉角姿態控制（roll/pitch/yaw） |
| SwitchGait | 1011 | 切換步態模式 |
| Trigger | 1012 | 觸發動作 |
| ContinuousGait | 1019 | 連續步態 |
| SwitchJoystick | 1027 | 切換搖桿模式 |
| EconomicGait | 1035 | 省電步態 |
| FreeWalk | 1045 | 自由行走模式 |

#### 2.1.6 特殊動作（2 個）

| 指令名稱 | api_id | 說明 |
|-----------|:------:|------|
| Bound | 1304 | 彈跳 |
| MoonWalk | 1305 | 月球漫步 |

#### 2.1.7 軌跡追蹤（1 個）

| 指令名稱 | api_id | 說明 |
|-----------|:------:|------|
| TrajectoryFollow | 1018 | 軌跡追蹤 |

#### 2.1.8 查詢指令（4 個）

| 指令名稱 | api_id | 說明 | 回傳 |
|-----------|:------:|------|------|
| GetBodyHeight | 1024 | 查詢身體高度 | float |
| GetFootRaiseHeight | 1025 | 查詢抬腳高度 | float |
| GetSpeedLevel | 1026 | 查詢速度等級 | int |
| GetState | 1034 | 查詢機器人狀態 | JSON |

### 2.2 AudioHub 音訊指令（5 個）

透過 `rt/api/audiohub/request` topic 發送，msg type 必須為 `"req"`（不是 `"msg"`）。

| 指令名稱 | api_id | 說明 | 關鍵參數 |
|-----------|:------:|------|----------|
| START_AUDIO | 4001 | 開啟 Megaphone 音訊通道 | ENTER 階段 |
| STOP_AUDIO | 4002 | 關閉 Megaphone 音訊通道 | EXIT 階段，後需 0.5s cooldown |
| SEND_AUDIO_BLOCK | 4003 | 發送音訊片段 | chunk_size=4096 base64 chars，含 `current_block_size` |
| SET_VOLUME | 4004 | 設定音量 | volume 值 |
| GET_AUDIO_STATUS | 4005 | 查詢音訊狀態 | 回傳播放狀態 |

**Megaphone 播放流程**：

```
ENTER(4001) → UPLOAD(4003) x N → EXIT(4002) → cooldown 0.5s
                  ↑ 每個 chunk 間隔 70ms
```

**已知限制**：
- Go2 Megaphone 硬體限制 16kHz 取樣率
- mid-session 重啟 tts_node 會導致 Megaphone silent fail，須連 Go2 driver 一起重啟
- Go2 對音訊 API 錯誤 silent ignore，不回傳錯誤碼

### 2.3 感測器能力

| 感測器 | 資料來源 | RTC Topic | 頻率 | 限制 |
|--------|---------|-----------|:----:|------|
| LiDAR | UTLiDAR | `rt/utlidar/voxel_map_compressed` | <2 Hz | 頻率過低，無法用於即時避障（需 >=10Hz） |
| 前置攝影機 | WebRTC Video Track | — | ~30 FPS | 需 `enable_video:=true`，佔 CPU/記憶體 |
| IMU | Sport Mode State | `rt/lf/sportmodestate` | ~50 Hz | 含 quaternion/accelerometer/gyroscope/rpy/temperature |
| 12 關節馬達 | Low State | `rt/lf/lowstate` | ~50 Hz | 含 q(位置)/dq(速度)/ddq(加速度)/tau(力矩) |
| 里程計 | UTLiDAR Pose | `rt/utlidar/robot_pose` | ~10 Hz | 含 position + orientation (quaternion) |
| Robot State | Sport Mode State | `rt/lf/sportmodestate` | ~50 Hz | 含 mode/velocity/foot_force/body_height/range_obstacle |

**Robot State 欄位完整清單**（`RobotState` dataclass）：

```python
@dataclass
class RobotState:
    mode: int                       # 運動模式
    progress: float                 # 動作進度
    gait_type: int                  # 步態類型
    position: List[float]           # 位置 [x, y, z]
    body_height: float              # 身體高度
    velocity: List[float]           # 速度 [vx, vy, vz]
    range_obstacle: List[float]     # 障礙物距離感測
    foot_force: List[float]         # 四足壓力
    foot_position_body: List[float] # 四足相對身體位置
    foot_speed_body: List[float]    # 四足相對身體速度
```

### 2.4 ROS2 Topic/Service 完整清單

#### 2.4.1 Publishers（go2_driver_node 發布）

| Topic | Message Type | QoS | 條件 |
|-------|-------------|:---:|------|
| `joint_states` | `sensor_msgs/JointState` | Reliable(10) | 永遠啟用 |
| `go2_states` | `go2_interfaces/Go2State` | Reliable(10) | 永遠啟用 |
| `point_cloud2` | `sensor_msgs/PointCloud2` | BestEffort(5) | `decode_lidar:=true` |
| `odom` | `nav_msgs/Odometry` | Reliable(10) | 永遠啟用 |
| `imu` | `go2_interfaces/IMU` | Reliable(10) | `minimal_state_topics:=false` |
| `camera/image_raw` | `sensor_msgs/Image` | BestEffort(5) | `enable_video:=true` + `publish_raw_image:=true` |
| `camera/image_raw/compressed` | `sensor_msgs/CompressedImage` | BestEffort(5) | `enable_video:=true` + `publish_compressed_image:=true` |
| `camera/camera_info` | `sensor_msgs/CameraInfo` | BestEffort(5) | 有 raw 或 compressed 影像時 |
| `utlidar/voxel_map_compressed` | `go2_interfaces/VoxelMapCompressed` | BestEffort(5) | `publish_raw_voxel:=true` |

> **Multi-robot 模式**：所有 topic 前綴加 `robot{i}/`（如 `robot0/joint_states`）。

> **TF**：同時發布 `odom` → `base_link` transform（z 偏移 +0.07m）。

#### 2.4.2 Subscribers（go2_driver_node 訂閱）

| Topic | Message Type | 說明 |
|-------|-------------|------|
| `cmd_vel` | `geometry_msgs/Twist` | 移動速度指令 |
| `webrtc_req` | `go2_interfaces/WebRtcReq` | WebRTC 通用指令（Sport/Audio/SLAM 等） |
| `joy` | `sensor_msgs/Joy` | 搖桿輸入 |
| `/tts_audio_raw` | `std_msgs/UInt8MultiArray` | 實驗性：raw WAV → WebRTC audio track 播放 |
| `lowstate` | `go2_interfaces/LowState` | CycloneDDS 模式專用 |
| `/utlidar/robot_pose` | `geometry_msgs/PoseStamped` | CycloneDDS 模式專用 |
| `/utlidar/cloud` | `sensor_msgs/PointCloud2` | CycloneDDS 模式專用 |

#### 2.4.3 WebRTC 訂閱 Topics（go2_driver_node → Go2）

連線驗證後自動訂閱（透過 DataChannel subscribe 訊息）：

| RTC Topic | 用途 | 條件 |
|-----------|------|------|
| `rt/utlidar/robot_pose` | 里程計 | 永遠啟用 |
| `rt/lf/lowstate` | 關節狀態 | `minimal_state_topics:=false` |
| `rt/lf/sportmodestate` | Sport Mode 狀態 | `minimal_state_topics:=false` |
| `rt/utlidar/voxel_map_compressed` | LiDAR 體素圖 | `enable_lidar:=true` 或相關參數 |
| `rt/audiohub/player/state` | 音訊播放狀態 | 永遠啟用（觀測性） |

#### 2.4.4 Launch 參數（robot.launch.py）

| 參數 | 預設值 | 說明 |
|------|:------:|------|
| `rviz2` | true | 啟動 RViz2 |
| `nav2` | true | 啟動 Nav2 導航 |
| `slam` | true | 啟動 SLAM Toolbox |
| `foxglove` | true | 啟動 Foxglove Bridge |
| `joystick` | true | 啟動搖桿控制 |
| `teleop` | true | 啟動遙控操作 |
| `mcp_mode` | false | MCP 模式（停用 SLAM/Nav2，啟用 snapshot_service） |
| `enable_video` | false | 啟用攝影機串流 |
| `decode_lidar` | true | 解碼 LiDAR 資料 |
| `publish_raw_image` | false | 發布原始影像 |
| `publish_compressed_image` | false | 發布壓縮影像 |
| `publish_raw_voxel` | false | 發布原始體素圖 |
| `lidar_processing` | false | 啟用 LiDAR 後處理 |
| `enable_tts` | false | 啟用 TTS 節點 |
| `minimal_state_topics` | false | 僅訂閱 odometry + lidar |
| `lidar_point_stride` | 1 | LiDAR 降取樣率（每 N 個點取 1 個） |
| `map` | `/home/jetson/go2_map.yaml` | Nav2 地圖路徑 |
| `autostart` | true | Nav2 lifecycle 自動啟動 |
| `pcl2ls_*` | 各異 | pointcloud_to_laserscan 參數組 |

### 2.5 WebRtcReq 訊息格式

定義於 `go2_interfaces/msg/WebRtcReq.msg`：

```
int64  id          # 訊息 ID（0 = 自動產生）
string topic       # Go2 側 RTC topic（含 rt/ 前綴）
int64  api_id      # API 指令 ID
string parameter   # JSON 格式 payload
uint8  priority    # 0 = 一般, 1 = 優先
```

**DataChannel 傳輸格式**（`command_generator.py` 產生）：

```json
{
  "type": "msg",
  "topic": "rt/api/sport/request",
  "data": {
    "header": {
      "identity": {
        "id": 1711234567890,
        "api_id": 1016
      }
    },
    "parameter": "1016"
  }
}
```

**關鍵差異**：
- Sport/SLAM/一般指令：`type: "msg"`
- AudioHub 指令：`type: "req"`（由 `command_generator.py` 根據 topic 含 `"audiohub"` 自動判斷）

---

## 3. 七大功能 SDK 支持度矩陣

### 3.1 總覽

| # | 功能 | SDK 提供 | SDK 缺少 | 整合狀態 | 支持度 |
|:-:|------|---------|----------|:--------:|:------:|
| 1 | 語音互動 | AudioHub API, WebRTC DataChannel | 無 | 完成 | 100% |
| 2 | 人臉辨識 | 前鏡頭 (WebRTC)、Robot State | D435 深度 | 外接 D435 | 80% |
| 3 | 手勢辨識 | 前鏡頭 (WebRTC) | D435 高畫質 | 外接 D435 | 70% |
| 4 | 姿勢辨識 | 前鏡頭 (WebRTC) | D435 高畫質 | 外接 D435 | 70% |
| 5 | 物件偵測 | 前鏡頭 (WebRTC)、D435 深度 | YOLO 模型整合 | 未建立 | 60% |
| 6 | 安全避障 | LiDAR、range_obstacle、D435 深度 | 高頻深度感測 | 未建立 | 40% |
| 7 | 自主導航 | LiDAR、Odometry、Nav2 整合 | 高頻 LiDAR (>=10Hz) | 受限 | 30% |

### 3.2 各功能詳細分析

#### 3.2.1 語音互動（100%）

**SDK 提供**：
- AudioHub Megaphone API（4001/4003/4002）透過 WebRTC DataChannel 播放音訊
- `/webrtc_req` subscriber 接受外部 TTS 指令
- `/tts_audio_raw` 實驗性 audio track 路徑

**整合現狀**：
- stt_intent_node → llm_bridge_node → tts_node → go2_driver_node 全鏈路通
- Megaphone 20/20 穩定性測試通過
- Edge-TTS (Cloud) + Piper (本地 fallback) 雙 provider
- 外接 USB 喇叭繞過 16kHz 限制，清晰度大幅改善

**下一步**：無阻塞項目，功能凍結中。

#### 3.2.2 人臉辨識（80%）

**SDK 提供**：
- Go2 前鏡頭可透過 WebRTC Video Track 取得影像
- Robot State 提供機器人姿態（用於估算人臉方向）

**SDK 缺少**：
- Go2 前鏡頭無深度資訊，距離估算需外接 D435

**整合現狀**：
- face_identity_node：YuNet 偵測(71.3 FPS CPU) + SFace 識別 + IOU 追蹤
- 使用外接 Intel RealSense D435（非 Go2 內建鏡頭）
- `/state/perception/face` 10Hz 狀態發布 + `/event/face_identity` 事件觸發
- interaction_router 消費 face_identity → welcome 事件

**下一步**：人臉觸發語音問候整合（interaction_executive 統一仲裁）。

#### 3.2.3 手勢辨識（70%）

**SDK 提供**：
- 前鏡頭影像來源（WebRTC 或 D435）

**SDK 缺少**：
- Go2 前鏡頭品質不足，需 D435
- 無內建手勢辨識能力

**整合現狀**：
- Gesture Recognizer（MediaPipe，7.2 FPS CPU）
- 白名單手勢：stop / ok / thumbs_up
- interaction_router → event_action_bridge → Go2 動作

**下一步**：手勢直接觸發 Go2 表演動作的映射擴充。

#### 3.2.4 姿勢辨識（70%）

**SDK 提供**：
- 前鏡頭影像來源

**SDK 缺少**：
- 無內建姿態估測，需外部模型（MediaPipe Pose / RTMPose）

**整合現狀**：
- MediaPipe Pose（18.5 FPS CPU 主線）/ RTMPose（GPU 備援）
- 姿勢分類：standing / sitting / crouching / lying / fallen
- fallen 持續 2s → fall_alert 事件 → TTS 通報

**下一步**：fallen → 自動走近 + 語音關懷（需 interaction_executive 整合移動 + 語音）。

#### 3.2.5 物件偵測（60%）

**SDK 提供**：
- 前鏡頭影像（WebRTC Video Track）
- D435 可提供 RGB + 深度
- Go2 Robot State 的 range_obstacle 提供粗略障礙物距離

**SDK 缺少**：
- 無內建物件偵測，需整合 YOLO 等模型
- 物件 3D 定位需深度對齊

**整合現狀**：
- 尚未建立 `object_perception` package
- D435 + YOLO 方案已納入藍圖

**下一步**：Phase 2 新建 object_perception，直接用 Clean Architecture。

#### 3.2.6 安全避障（40%）

**SDK 提供**：
- LiDAR 體素圖（但 <2Hz）
- Robot State 的 `range_obstacle` 四方向障礙物距離
- Go2 內建 `rt/api/obstacles_avoid/request` 避障 API

**SDK 缺少**：
- LiDAR 頻率過低（<2Hz），無法做即時避障（需 >=10Hz）
- 內建避障 API 可靠性未驗證

**整合現狀**：
- 尚未建立 `obstacle_guard` package
- D435 深度 + 軟體避障方案已納入藍圖

**下一步**：Phase 2 新建 obstacle_guard，D435 近距離深度替代 LiDAR。

#### 3.2.7 自主導航（30%）

**SDK 提供**：
- LiDAR → PointCloud2 → LaserScan（pointcloud_to_laserscan）
- Odometry（~10Hz）
- Nav2 + SLAM Toolbox 完整 launch 整合
- AMCL 定位可用

**SDK 缺少**：
- LiDAR <2Hz 嚴重不足，SLAM 地圖品質差
- 缺乏 costmap 即時更新能力
- 導航路徑規劃精度受限

**整合現狀**：
- Nav2 launch 已整合但列為 P2
- 定位(AMCL)可用，導航避障不可行

**下一步**：4/13 後評估，非展示核心功能。

---

## 4. 當前系統架構分析

### 4.1 go2_robot_sdk 的 Clean Architecture（標竿）

go2_robot_sdk 是專案中唯一實現完整 Clean Architecture 的 package：

```
go2_robot_sdk/
├── domain/                          # 核心業務邏輯，純 Python
│   ├── constants/
│   │   ├── robot_commands.py        # ROBOT_CMD: 42 個 api_id
│   │   └── webrtc_topics.py         # RTC_TOPIC + DATA_CHANNEL_TYPE + AUDIO_HUB_COMMANDS
│   ├── entities/
│   │   ├── robot_data.py            # RobotData, RobotState, IMUData 等 dataclass
│   │   └── robot_config.py          # RobotConfig dataclass
│   ├── interfaces/
│   │   ├── robot_controller.py      # IRobotController (ABC)
│   │   ├── robot_data_publisher.py  # IRobotDataPublisher (ABC)
│   │   └── robot_data_receiver.py   # IRobotDataReceiver (ABC)
│   └── math/
│       ├── geometry.py              # Quaternion, Vector3
│       └── kinematics.py            # 逆運動學（IK）
├── application/                     # 用例層，協調 domain 和 infrastructure
│   ├── services/
│   │   ├── robot_control_service.py # RobotControlService — cmd_vel/webrtc_req/joy 處理
│   │   └── robot_data_service.py    # RobotDataService — WebRTC 訊息解碼 → 發布
│   └── utils/
│       └── command_generator.py     # gen_command / gen_mov_command
├── infrastructure/                  # 外部系統適配層
│   ├── ros2/
│   │   └── ros2_publisher.py        # ROS2Publisher (implements IRobotDataPublisher)
│   ├── webrtc/
│   │   ├── webrtc_adapter.py        # WebRTCAdapter (implements IRobotDataReceiver + IRobotController)
│   │   ├── go2_connection.py        # Go2Connection — WebRTC peer connection
│   │   ├── http_client.py           # HTTP token 交換
│   │   ├── data_decoder.py          # WebRTC 訊息解碼
│   │   ├── tts_audio_track.py       # TTS → WebRTC audio track（實驗性）
│   │   └── crypto/
│   │       └── encryption.py        # Go2 WebRTC 驗證加密
│   └── sensors/
│       ├── lidar_decoder.py         # LiDAR 點雲解碼
│       ├── lidar_decoder_lz4.py     # LZ4 壓縮 LiDAR 解碼
│       └── camera_config.py         # 相機內參載入
└── presentation/                    # ROS2 Node 接線層
    └── go2_driver_node.py           # Go2DriverNode — 唯一 ROS2 Node
```

**依賴方向**（嚴格遵守）：

```
presentation → application → domain ← infrastructure
     │              │           ↑           │
     │              │           │           │
     │              └───────────┘           │
     │                                      │
     └──────────────── infrastructure ──────┘
```

- `domain` 層不依賴任何外部 library（純 Python + numpy）
- `application` 層只知道 `domain` 的 interface 和 entity
- `infrastructure` 層實作 `domain` 的 interface
- `presentation` 層組裝所有元件，是唯一知道 ROS2 的地方（除了 `ros2_publisher.py`）

**接口定義**：

| 接口 | 職責 | 實作者 |
|------|------|--------|
| `IRobotController` | 動作控制（movement/stand/webrtc_req） | `WebRTCAdapter` |
| `IRobotDataPublisher` | 感測器資料發布（odom/joint/state/lidar/camera/voxel） | `ROS2Publisher` |
| `IRobotDataReceiver` | 與機器人連線、接收資料 | `WebRTCAdapter` |

### 4.2 其他 package 的架構現狀

#### 4.2.1 speech_processor — flat 結構，存在 god file

```
speech_processor/
├── stt_intent_node.py      # 1016 行 — GOD FILE
│   └── 內含：ASRResult, ASRProvider, QwenASRProvider,
│        WhisperLocalProvider, SttIntentNode（全部一個檔案）
├── tts_node.py             # 1008 行 — GOD FILE
│   └── 內含：TTSProvider, PiperTTSProvider, EdgeTTSProvider,
│        ElevenLabsTTSProvider, TTSNode（全部一個檔案）
├── llm_bridge_node.py      # 624 行
├── intent_tts_bridge_node.py  # 舊版 bridge（被 llm_bridge 取代）
├── intent_classifier.py    # ✅ 已抽取，純 Python，可獨立測試
├── llm_contract.py         # ✅ 已抽取，純 Python，可獨立測試
└── speech_test_observer.py # 測試觀察者
```

**評估**：
- `intent_classifier.py` 和 `llm_contract.py` 已是良好的 domain 層候選
- `stt_intent_node.py` 混合了 domain（ASR providers）、application（intent 分類流程）、infrastructure（ROS2 node）、外部 API 呼叫
- `tts_node.py` 同樣混合了多個 TTS provider 實作 + ROS2 node + 快取機制 + Megaphone 播放邏輯

#### 4.2.2 face_perception — single file

```
face_perception/
├── face_identity_node.py   # 680 行 — SINGLE FILE
│   └── 內含：YuNet 載入、SFace 識別、IOU 追蹤、
│        DB 管理、ROS2 Node、debug image 繪製（全部一個 class）
└── (no other source files)
```

**評估**：
- 功能完整但耦合度高
- YuNet/SFace 模型可抽取為 `IFaceDetector` / `IFaceRecognizer` interface
- D435 相機存取可抽取為 `ICameraProvider` interface
- IOU 追蹤邏輯是純數學，適合進 domain 層

#### 4.2.3 vision_perception — flat 但有良好抽取

```
vision_perception/
├── vision_perception_node.py     # 442 行 — 主節點
├── gesture_classifier.py         # 手勢分類（純邏輯）
├── pose_classifier.py            # 姿勢分類（純邏輯）
├── event_builder.py              # ✅ 事件建構（純函式）
├── interaction_rules.py          # ✅ 互動規則（純函式，無 ROS2 依賴）
├── interaction_router.py         # 事件路由（ROS2 Node）
├── event_action_bridge.py        # 事件 → 動作（ROS2 Node）
├── gesture_recognizer_backend.py # Gesture Recognizer 後端
├── mediapipe_hands.py            # MediaPipe Hands 後端
├── mediapipe_pose.py             # MediaPipe Pose 後端
├── rtmpose_inference.py          # RTMPose 推理
├── inference_adapter.py          # 推理適配器
├── mock_inference.py             # Mock 推理（測試用）
├── mock_event_publisher.py       # Mock 事件發布者
└── vision_status_display.py      # 狀態儀表板
```

**評估**：
- `interaction_rules.py` 和 `event_builder.py` 是優秀的 domain 層元件（無 ROS2 依賴）
- `gesture_classifier.py` 和 `pose_classifier.py` 也是純邏輯，可進 domain
- 後端切換（MediaPipe/RTMPose/Mock）已有 adapter pattern 雛形
- 相較其他 package，這是架構最接近 Clean Architecture 的（除了 go2_robot_sdk）

#### 4.2.4 interaction_executive — 空殼

```
interaction_executive/
└── (directory does not exist)
```

**影響**：
- 缺乏統一中控，事件路由分散：
  - 語音路徑：`stt_intent_node` → `llm_bridge_node` → `tts_node` + `webrtc_req`
  - 視覺路徑：`interaction_router` → `event_action_bridge` → `tts` + `webrtc_req`
- 兩條路徑可能同時對 `/webrtc_req` 發指令，產生動作 interleave
- TTS guard 僅在 event_action_bridge 實作，llm_bridge 無此保護

### 4.3 事件流現狀

```
┌─────────────────────── Layer 2: 感知 ───────────────────────┐
│                                                              │
│  face_identity_node ──→ /state/perception/face (10Hz)        │
│                    ──→ /event/face_identity (觸發式)          │
│                                                              │
│  stt_intent_node ──→ /event/speech_intent_recognized         │
│                                                              │
│  vision_perception_node ──→ /event/gesture_detected          │
│                         ──→ /event/pose_detected             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
┌──── 語音決策路徑 ────┐ ┌── 視覺決策路徑 ──┐ │
│                      │ │                  │ │
│  llm_bridge_node     │ │ interaction_     │ │
│  (LLM/RuleBrain)     │ │ router           │ │
│   ↓                  │ │  ↓               │ │
│  /tts + /webrtc_req  │ │ /event/inter-    │ │
│                      │ │  action/*        │ │
└──────────────────────┘ │  ↓               │ │
                         │ event_action_    │ │
                         │ bridge           │ │
                         │  ↓               │ │
                         │ /tts + /webrtc   │ │
                         │ _req             │ │
                         └──────────────────┘ │
                                              │
                ┌─────────────────────────────┘
                ▼
┌──────── Layer 1: 驅動 ────────┐
│                                │
│  go2_driver_node               │
│   ├── /webrtc_req → Go2 動作   │
│   └── /tts_audio_raw → 播放    │
│                                │
│  tts_node                      │
│   ├── /tts → 合成語音          │
│   └── /webrtc_req → Megaphone  │
│                                │
└────────────────────────────────┘
```

**核心問題**：兩條決策路徑無仲裁機制，`/webrtc_req` 是共享的「最終執行通道」。

---

## 5. Clean Architecture 目標藍圖

### 5.1 設計原則

| 原則 | 說明 |
|------|------|
| **依賴規則** | 外層依賴內層，內層不知道外層。domain 永遠不 import infrastructure。 |
| **domain 層純 Python** | 無 ROS2、無 OpenCV、無 HTTP、無 model framework 依賴。僅允許 numpy（用於數值計算）。 |
| **interface 在 domain 層定義** | ABC 抽象類定義在 domain，infrastructure 負責實作。 |
| **infrastructure 封裝外部系統** | ROS2、WebRTC、D435 SDK、ML models、HTTP API 全部在此層。 |
| **presentation 只做接線** | ROS2 Node 只負責 DI（依賴注入）、subscription/publisher 接線、參數宣告。不含業務邏輯。 |
| **可測試性** | domain + application 層可純 pytest 測試，不需 ROS2 runtime。 |

### 5.2 目標模組結構

```
elder_and_dog/
│
├── go2_robot_sdk/              # Layer 1: 驅動（已完成 Clean Architecture）
│   ├── domain/                 # IRobotController, IRobotDataPublisher, IRobotDataReceiver
│   ├── application/            # RobotControlService, RobotDataService
│   ├── infrastructure/         # WebRTCAdapter, ROS2Publisher, Go2Connection
│   └── presentation/           # Go2DriverNode
│
├── go2_interfaces/             # Layer 0: ROS2 訊息定義
│   └── msg/                    # WebRtcReq, Go2State, IMU 等 31 個 .msg
│
├── face_perception/            # Layer 2: 感知 — 人臉
│   ├── domain/                 # FaceEntity, IFaceDetector, IFaceRecognizer, ITracker
│   ├── application/            # FaceIdentityService（偵測→識別→追蹤流程）
│   ├── infrastructure/         # YuNetAdapter, SFaceAdapter, D435CameraProvider, IOUTracker
│   └── presentation/           # FaceIdentityNode（ROS2 接線）
│
├── speech_processor/           # Layer 2: 感知 + 決策 — 語音
│   ├── domain/                 # Intent, ASRResult, TTSRequest, IntentClassifier, LLMContract
│   ├── application/            # STTService, TTSService, LLMBridgeService
│   ├── infrastructure/         # WhisperAdapter, EdgeTTSAdapter, PiperAdapter, OllamaClient
│   └── presentation/           # SttIntentNode, TTSNode, LLMBridgeNode
│
├── vision_perception/          # Layer 2: 感知 — 視覺（手勢+姿勢）
│   ├── domain/                 # Gesture, Pose, InteractionEvent, GestureClassifier, PoseClassifier
│   │                           # InteractionRules, EventBuilder（已有，搬入）
│   ├── application/            # GestureService, PoseService
│   ├── infrastructure/         # MediaPipeGestureAdapter, MediaPipePoseAdapter, RTMPoseAdapter
│   └── presentation/           # VisionPerceptionNode, InteractionRouter, EventActionBridge
│
├── object_perception/          # Layer 2: 感知 — 物件偵測（新建）
│   ├── domain/                 # DetectedObject, IObjectDetector
│   ├── application/            # ObjectDetectionService
│   ├── infrastructure/         # YOLO26Adapter, D435DepthProvider
│   └── presentation/           # ObjectPerceptionNode
│
├── obstacle_guard/             # Layer 2: 安全 — 避障（新建）
│   ├── domain/                 # ObstacleZone, SafetyPolicy, IDepthSensor
│   ├── application/            # ObstacleGuardService（安全停止決策）
│   ├── infrastructure/         # D435DepthAdapter, LiDARAdapter
│   └── presentation/           # ObstacleGuardNode
│
├── interaction_executive/      # Layer 3: 中控（未來核心）
│   ├── domain/                 # BehaviorTree/FSM, Skill, Priority, ConflictPolicy
│   ├── application/            # ExecutiveService（事件仲裁 + 技能調度）
│   ├── infrastructure/         # ROS2EventBridge, GoalDispatcher, SkillRegistry
│   └── presentation/           # InteractionExecutiveNode
│
└── pawai-studio/               # Layer 4: 前端監控
    ├── src/                    # React + TypeScript
    └── mock-server/            # Mock ROS2 bridge
```

### 5.3 模組間通訊契約

#### 5.3.1 Layer 2 → Layer 3（感知 → 中控）

| Topic 類型 | 命名規則 | 範例 |
|-----------|---------|------|
| Event（觸發式） | `/event/{source}/{event_type}` | `/event/face_identity`, `/event/gesture_detected` |
| State（持續式） | `/state/{layer}/{source}` | `/state/perception/face`, `/state/interaction/speech` |

所有 Event/State Topic 使用 `std_msgs/String`（JSON payload）。

> **已知技術債**：String+JSON 繞過 ROS2 type system，喪失編譯期型別檢查。長期應遷移至自訂 .msg 定義。短期透過 `interaction_contract.md` 凍結 schema 來管控。

#### 5.3.2 Layer 3 → Layer 1（中控 → 驅動）

| Topic | Message Type | 用途 |
|-------|-------------|------|
| `/webrtc_req` | `go2_interfaces/WebRtcReq` | Go2 動作指令（Sport + Audio） |
| `/tts` | `std_msgs/String` | TTS 文字輸入 |
| `/cmd_vel` | `geometry_msgs/Twist` | 移動速度指令 |

#### 5.3.3 Layer 3 → Layer 4（中控 → 前端）

| 通道 | 協定 | 狀態 |
|------|------|:----:|
| Foxglove Bridge | WebSocket (Foxglove) | 已運作 |
| PawAI Studio | WebSocket (自訂) | Mock Server 已建 |

#### 5.3.4 interaction_executive 仲裁設計（目標）

```
                    ┌─────────────────────────┐
                    │  interaction_executive   │
                    │                          │
  /event/*  ───────→│  Priority Queue          │
  /state/*  ───────→│    ↓                     │
                    │  Conflict Resolution     │
                    │    ↓                     │
                    │  Skill Executor          │──→ /webrtc_req
                    │    ↓                     │──→ /tts
                    │  State Machine / BT      │──→ /cmd_vel
                    │                          │
                    └─────────────────────────┘
```

**優先權設計**（由高到低）：

| 優先權 | 類別 | 範例 |
|:------:|------|------|
| 0 | 安全 | fall_alert, obstacle_stop |
| 1 | 語音指令 | 使用者明確語音命令 |
| 2 | 手勢指令 | stop, thumbs_up |
| 3 | 自動行為 | welcome, idle_dance |

### 5.4 遷移路徑（漸進式，不是一次重構）

#### Phase 1：抽取純函式（已完成）

已完成的抽取：

| 原始檔案 | 抽取物 | 位置 | 測試 |
|----------|--------|------|:----:|
| stt_intent_node.py | `IntentClassifier` | `intent_classifier.py` | CI |
| llm_bridge_node.py | `parse_llm_response`, `SKILL_TO_CMD` | `llm_contract.py` | CI |
| interaction_router.py | `should_welcome`, `should_gesture_command`, `should_fall_alert` | `interaction_rules.py` | CI |
| vision_perception_node.py | `build_gesture_event`, `build_pose_event` | `event_builder.py` | CI |

**效果**：核心決策邏輯可用 pytest 獨立測試，不需 ROS2 runtime。

#### Phase 2：新模組直接用 Clean Architecture（建議，4/13 前）

**目標**：`object_perception` 和 `obstacle_guard` 從建立第一天就遵循四層結構。

**範本**：以 go2_robot_sdk 為模板：
1. 先定義 domain interface（如 `IObjectDetector`）
2. 再實作 infrastructure adapter（如 `YOLO26Adapter`）
3. application 層協調流程
4. presentation 層只做 ROS2 接線

**預期收益**：
- 新成員可照模板開發，降低溝通成本
- 測試可在開發機（無 ROS2）上跑，加速迭代

#### Phase 3：重構 face_perception（4/13 後）

```
face_perception/
├── face_identity_node.py (680 行，all-in-one)
│
▼ 拆分為
│
├── domain/
│   ├── face_entity.py          # FaceTrack, FaceDB dataclass
│   ├── i_face_detector.py      # IFaceDetector (ABC)
│   ├── i_face_recognizer.py    # IFaceRecognizer (ABC)
│   └── i_tracker.py            # ITracker (ABC)
├── application/
│   └── face_identity_service.py  # 偵測→識別→追蹤→穩定化流程
├── infrastructure/
│   ├── yunet_adapter.py        # YuNet 偵測器
│   ├── sface_adapter.py        # SFace 識別器
│   ├── iou_tracker.py          # IOU 追蹤
│   └── d435_camera.py          # D435 影像來源
└── presentation/
    └── face_identity_node.py   # ROS2 Node（僅接線+參數）
```

**估計工時**：2-3 天（含測試遷移）。

#### Phase 4：重構 speech_processor 的 god files（更遠期）

```
speech_processor/
├── stt_intent_node.py (1016 行) → 拆分為：
│   ├── domain/asr_result.py
│   ├── domain/i_asr_provider.py
│   ├── infrastructure/whisper_adapter.py
│   ├── infrastructure/qwen_asr_adapter.py
│   ├── application/stt_service.py
│   └── presentation/stt_intent_node.py
│
├── tts_node.py (1008 行) → 拆分為：
│   ├── domain/tts_request.py
│   ├── domain/i_tts_provider.py
│   ├── infrastructure/piper_adapter.py
│   ├── infrastructure/edge_tts_adapter.py
│   ├── infrastructure/elevenlabs_adapter.py
│   ├── infrastructure/megaphone_player.py
│   ├── application/tts_service.py（含快取）
│   └── presentation/tts_node.py
│
├── llm_bridge_node.py (624 行) → 拆分為：
│   ├── domain/llm_contract.py（已抽取）
│   ├── infrastructure/openai_compatible_client.py
│   ├── infrastructure/ollama_client.py
│   ├── application/llm_bridge_service.py（含 fallback chain）
│   └── presentation/llm_bridge_node.py
```

**估計工時**：4-5 天（最大 package，provider 多）。
**風險**：語音功能已凍結並穩定運行，重構需保證零功能回歸。

---

## 6. 已知架構風險

### 6.1 事件雙重消費（嚴重度：高）

**現象**：`llm_bridge_node` 和 `event_action_bridge` 都可發 `/webrtc_req` 和 `/tts`，無仲裁。
**場景**：使用者說「停」的同時手勢也比了 stop → 兩個 StopMove(1003) 同時發送。
**影響**：動作 interleave、TTS 重疊。
**緩解**：`event_action_bridge` 有 TTS guard（TTS 播放中跳過非安全動作），但 `llm_bridge_node` 無此保護。
**根治**：建立 `interaction_executive` 統一仲裁所有事件。

### 6.2 /webrtc_req 無仲裁（嚴重度：中）

**現象**：多個 node 同時 publish 到 `/webrtc_req`，go2_driver_node 照單全收。
**場景**：TTS Megaphone 音訊(4003)發送中，同時收到 Hello(1016) 動作指令。
**影響**：Go2 DataChannel 可能 interleave 音訊和動作指令。
**緩解**：tts_node 播放期間發 `/state/tts_playing` 讓 bridge 跳過。
**根治**：go2_driver_node 內建 command queue + priority arbitration。

### 6.3 String+JSON 繞過 ROS2 type system（嚴重度：中）

**現象**：所有 Event/State Topic 使用 `std_msgs/String`（JSON payload），非 typed message。
**影響**：無編譯期檢查、JSON parse 失敗 silent fail、schema drift 風險。
**緩解**：`interaction_contract.md` v2.1 凍結 schema，CI 有 JSON schema 驗證。
**根治**：將常用 event schema 定義為 `.msg`（需 go2_interfaces 擴充）。

### 6.4 硬編碼路徑（嚴重度：低）

**現象**：41 個檔案含 `/home/jetson/` 硬編碼，共 169 處。
**影響**：開發機無法直接執行，CI 測試受限。
**根治**：統一改用 ROS2 parameter + 環境變數 + `ament_index_python`。

### 6.5 God File 維護風險（嚴重度：中）

| 檔案 | 行數 | 職責數 |
|------|:----:|:-----:|
| `stt_intent_node.py` | 1016 | 5+（ASR providers, intent classification, VAD, ROS2 node, warmup） |
| `tts_node.py` | 1008 | 5+（TTS providers, cache, Megaphone, local playback, ROS2 node） |
| `face_identity_node.py` | 680 | 4+（detection, recognition, tracking, ROS2 node） |

**影響**：新成員上手困難、合併衝突頻繁、單元測試覆蓋率低。

---

## 7. 參考資料

### 7.1 程式碼權威來源

| 項目 | 路徑 |
|------|------|
| Robot Command 定義 | `go2_robot_sdk/go2_robot_sdk/domain/constants/robot_commands.py` |
| WebRTC Topic 定義 | `go2_robot_sdk/go2_robot_sdk/domain/constants/webrtc_topics.py` |
| Domain Interface | `go2_robot_sdk/go2_robot_sdk/domain/interfaces/` |
| Domain Entity | `go2_robot_sdk/go2_robot_sdk/domain/entities/` |
| WebRtcReq Message | `go2_interfaces/msg/WebRtcReq.msg` |
| Command Generator | `go2_robot_sdk/go2_robot_sdk/application/utils/command_generator.py` |
| LLM Contract | `speech_processor/speech_processor/llm_contract.py` |
| Interaction Rules | `vision_perception/vision_perception/interaction_rules.py` |

### 7.2 文件參考

| 文件 | 路徑 |
|------|------|
| 專案總覽 | `docs/mission/README.md` |
| ROS2 介面契約 | `docs/architecture/contracts/interaction_contract.md` |
| 語音模組 | `docs/語音功能/README.md` |
| 人臉模組 | `docs/人臉辨識/README.md` |
| 手勢模組 | `docs/手勢辨識/README.md` |
| 姿勢模組 | `docs/姿勢辨識/README.md` |
| Benchmark 框架 | `docs/superpowers/specs/2026-03-19-unified-benchmark-framework-design.md` |

### 7.3 外部參考

| 項目 | 連結 |
|------|------|
| Go2 WebRTC API Wiki | https://wiki.theroboverse.com/en/unitree-go2-app-console-commands |
| RoboVerse go2_webrtc_connect | https://github.com/legion1581/go2_webrtc_connect |
| Clean Architecture (Uncle Bob) | https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html |

---

*本文件由 PawAI System Architecture 維護。架構決策變更需更新本文件。*
