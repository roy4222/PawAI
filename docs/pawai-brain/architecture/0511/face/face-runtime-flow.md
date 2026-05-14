# Face Runtime Flow

## 模組定位

`face_perception` 是身份感知層。它接 RealSense D435 的 RGB 與 aligned depth，輸出兩條 ROS2 介面：

- `/state/perception/face`：連續狀態，給 Brain / Studio / bridge 查「現在看到誰」。
- `/event/face_identity`：離散事件，給 Executive 觸發歡迎、陌生人、跌倒名稱補齊。

核心節點是：

```text
face_perception/face_perception/face_identity_node.py
```

Launch 入口是：

```text
face_perception/launch/face_perception.launch.py
```

Jetson 實機參數是：

```text
face_perception/config/face_perception.yaml
```

## Runtime 架構圖

```text
Intel RealSense D435
  /camera/camera/color/image_raw
  /camera/camera/aligned_depth_to_color/image_raw
          │
          │ BEST_EFFORT, depth=1
          ▼
┌────────────────────────────────────────────────────────────┐
│ face_identity_node                                          │
│                                                            │
│  color/depth callback                                      │
│    └─ copy latest frame under lock                         │
│                                                            │
│  20Hz tick                                                 │
│    ├─ YuNet face detection                                 │
│    ├─ SFace aligned crop + embedding                       │
│    ├─ face DB cosine similarity                            │
│    ├─ IOU track assignment                                 │
│    ├─ stable identity hysteresis                           │
│    └─ depth ROI median distance                            │
│                                                            │
│  publishers                                                │
│    ├─ /state/perception/face                               │
│    ├─ /event/face_identity                                 │
│    ├─ /face_identity/debug_image                           │
│    └─ /face_identity/compare_image                         │
└────────────────────────────────────────────────────────────┘
          │
          ├─ Brain: current_speaker prompt grounding
          ├─ Executive: greet / stranger / fallen name cache
          ├─ Studio Gateway: face panel pass-through
          └─ Vision bridge/router: legacy/demo enrichment
```

## Node 初始化順序

`FaceIdentityNode.__init__()` 做這些事：

1. 宣告參數：DB、模型路徑、threshold、topic、publish fps。
2. 載入 OpenCV `FaceDetectorYN` 和 `FaceRecognizerSF`。
3. 檢查 `/home/jetson/face_db` 的 PNG 數量。
4. 若 `model_sface.pkl` 不存在或 counts 不一致，重新訓練模型。
5. 建立四個 publisher。
6. 訂閱 color/depth topic。
7. 建立 20Hz timer，執行 `tick()`。

## Topic Schema

### `/state/perception/face`

用途：給任何模組查目前畫面上的臉。這是快照，不代表有新事件。

```json
{
  "stamp": 1773561600.789,
  "face_count": 2,
  "tracks": [
    {
      "track_id": 1,
      "stable_name": "roy",
      "sim": 0.42,
      "distance_m": 1.25,
      "bbox": [120, 80, 250, 260],
      "mode": "stable"
    }
  ]
}
```

注意：
- `stable_name` 可能是 `"unknown"`。
- `distance_m` 可能是 `null`，代表深度 ROI 沒有效值。
- `mode` 目前實作上 known face 多為 `"stable"`，unknown 或無本幀資訊多為 `"hold"`。
- `face_count` 是目前 tracks 數，不一定等於本幀 raw detection 數。

### `/event/face_identity`

用途：給 Executive 做互動規則。這是轉換事件，不是固定頻率。

```json
{
  "stamp": 1773561600.789,
  "event_type": "identity_stable",
  "track_id": 1,
  "stable_name": "roy",
  "sim": 0.42,
  "distance_m": 1.25
}
```

事件種類：

| event_type | 來源 |
|------------|------|
| `track_started` | 新 bbox 無法匹配舊 track |
| `identity_stable` | track 從 unknown 鎖定成已知身份 |
| `identity_changed` | track 已知身份切換成另一個穩定身份 |
| `track_lost` | track 連續 miss 超過 `track_max_misses` |

## 啟動方式

推薦：

```bash
bash scripts/start_face_identity_tmux.sh
```

手動：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch face_perception face_perception.launch.py
```

可指定 config：

```bash
ros2 launch face_perception face_perception.launch.py \
  config_file:=/home/jetson/elder_and_dog/install/face_perception/share/face_perception/config/face_perception.yaml
```

## 現場觀測指令

```bash
ros2 topic echo /state/perception/face
ros2 topic echo /event/face_identity
ros2 topic hz /state/perception/face
ros2 topic hz /face_identity/debug_image
```

Studio 端會透過 `pawai-studio/gateway/studio_gateway.py` 收 `/state/perception/face`，並將 8-10Hz face state throttle 成較低頻率送到前端面板。
