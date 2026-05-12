# Pose Runtime Flow

這份文件只看姿勢辨識在系統中的 runtime：相機進來、哪個 backend 抽骨架、誰發 `/event/pose_detected`、誰消費。

## 1. 系統位置

姿勢辨識住在 `vision_perception`，和 gesture 共用 `VisionPerceptionNode`。它不是 LLM 做的，也不是 Brain 直接看影像，而是先把人體骨架轉成離散 pose event。

主要檔案：

| 角色 | 檔案 |
| --- | --- |
| perception orchestrator | `vision_perception/vision_perception/vision_perception_node.py` |
| pose rule classifier | `vision_perception/vision_perception/pose_classifier.py` |
| MediaPipe Pose wrapper | `vision_perception/vision_perception/mediapipe_pose.py` |
| RTMPose adapter | `vision_perception/vision_perception/rtmpose_inference.py` |
| event schema | `vision_perception/vision_perception/event_builder.py` |
| runtime config | `vision_perception/config/vision_perception.yaml` |
| launch defaults | `vision_perception/launch/vision_perception.launch.py` |
| executive consumer | `interaction_executive/interaction_executive/brain_node.py` |
| brain context consumer | `pawai_brain/pawai_brain/conversation_graph_node.py` |

## 2. Runtime 架構圖

```text
D435 RGB
  /camera/camera/color/image_raw
        |
        v
vision_perception_node.py
  - 讀 image frame
  - pose_backend=mediapipe: MediaPipePose.detect()
  - pose_backend=rtmpose: RTMPoseInference.infer()
  - body_kps/body_scores -> classify_pose()
  - pose_buffer majority vote
  - 只在 pose_vote != last_pose 時 publish event
        |
        v
/event/pose_detected
  std_msgs/String JSON:
  {
    "event_type": "pose_detected",
    "pose": "sitting",
    "confidence": 0.85,
    "track_id": 0,
    "stamp": ...
  }
        |
        +-----------------------+----------------------+
        |                       |                      |
        v                       v                      v
interaction_executive        pawai_brain           event_action_bridge
brain_node.py                conversation_graph    demo pose->/tts
  - fallen_alert               - cache latest pose     - sitting/crouching/
  - sit_along                  - world_state             bending/akimbo/
  - careful_remind             - scene_hint              knee_kneel TTS
```

## 3. Backend 現況

目前 config/launch 預設：

| 來源 | 現況 |
| --- | --- |
| `vision_perception/config/vision_perception.yaml` | `inference_backend: "mock"`, `use_camera: false`, `pose_backend: "rtmpose"` |
| `vision_perception/launch/vision_perception.launch.py` | launch arg default `pose_backend="rtmpose"` |
| `scripts/start_vision_debug_tmux.sh` | 實際 debug 常用 `pose_backend:=mediapipe` |

所以明天不要只看文件說「MediaPipe 主線」。實機到底跑哪條要用 ROS param 查：

```bash
ros2 param get /vision_perception_node pose_backend
ros2 param get /vision_perception_node inference_backend
ros2 param get /vision_perception_node use_camera
```

如果 node 名稱不同，用：

```bash
ros2 node list
ros2 param list /vision_perception_node
```

## 4. Event 是 state transition，不是 continuous stream

`vision_perception_node.py` 只在投票後姿勢改變時發事件：

```text
if pose_vote is not None and pose_vote != self.last_pose:
    publish /event/pose_detected
```

這代表：

- 人一直坐著，只會在剛變成 `sitting` 時發一次 event。
- Brain 如果把 pose 設太短 stale，過幾秒就會「忘記」你還坐著。
- Executive 裡的 `fallen/sitting/bending` 累積 timer 依賴重複 event，但上游 event 又是 state transition，這是目前 pose 最微妙的地方。

目前 Brain `world_state_builder.py` 對 pose 設 10 秒 stale：

```text
_POSE_STALE_S = 10.0
```

這可以回答短時間內的「我在幹嘛」，但如果坐著 1 分鐘都沒有新 event，Brain 可能又答不出來。

## 5. Pose event schema

由 `event_builder.build_pose_event()` 建立：

```json
{
  "stamp": 1773561601.234,
  "event_type": "pose_detected",
  "pose": "fallen",
  "confidence": 0.95,
  "track_id": 0
}
```

欄位說明：

| 欄位 | 意義 |
| --- | --- |
| `pose` | `standing/sitting/crouching/fallen/bending/akimbo/knee_kneel` |
| `confidence` | pose buffer 多數投票比例，不是模型原始 confidence |
| `track_id` | Phase 1 固定 0，不能拿來做人臉關聯 |
| `stamp` | event builder 產生時間 |

## 6. 明天第一個判斷

如果使用者問「我在幹嘛」答不出來，先分三層查：

1. `/event/pose_detected` 有沒有發。
2. `pawai_brain` 有沒有把 pose 存進 `world_state.current_pose`。
3. `_POSE_ZH` 是否支援該 pose 名稱。

目前本地程式碼裡 `_POSE_ZH` 只支援：

```text
standing, sitting, crouching, fallen
```

缺：

```text
bending, akimbo, knee_kneel
```

這是「姿勢辨識有事件，但 Brain 答不出」的直接原因之一。

