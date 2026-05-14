# Pose Debug Runbook

這份是明天到學校現場排查姿勢用的順序。Pose 問題最多，排查時先分層，不要一開始就改 threshold。

## 1. 確認 backend 和相機

```bash
ros2 node list
ros2 param get /vision_perception_node use_camera
ros2 param get /vision_perception_node inference_backend
ros2 param get /vision_perception_node pose_backend
ros2 param get /vision_perception_node pose_vote_frames
```

如果 param 查不到，先用：

```bash
ros2 param list /vision_perception_node
```

目前常見現況：

| 值 | 意義 |
| --- | --- |
| `use_camera=false` | 沒有實際看鏡頭，可能在 mock |
| `inference_backend=mock` | 不會用真影像 |
| `pose_backend=mediapipe` | CPU MediaPipe Pose |
| `pose_backend=rtmpose` | RTMPose wholebody |

## 2. 看 pose event

```bash
ros2 topic echo /event/pose_detected
```

注意：這不是 continuous stream。姿勢不變時不會一直刷。

如果你站著後看到一次：

```json
{"pose": "standing", "confidence": 1.0}
```

之後沒有新訊息，這是正常的 transition 行為，不代表 node 停了。

## 3. 看 vision node debug log

`vision_perception_node.py` 每約 1 秒會印：

```text
pose: raw=sitting hip=... knee=... trunk=... bbox_r=... torso_vis=... arm_vis=... vote=...
```

判斷方式：

| 欄位 | 用途 |
| --- | --- |
| `raw` | 單幀 classifier 結果 |
| `vote` | buffer 多數決結果，真正 publish 用這個 |
| `hip/knee/trunk` | 判斷 standing/sitting/crouching/bending/fallen 的主角度 |
| `bbox_r` | fallen bonus / bending guard / knee_kneel guard |
| `torso_vis` | fallen 是否可信 |
| `arm_vis` | akimbo 失敗時看手臂可見度 |

## 4. 現場症狀對照

| 症狀 | 先查 |
| --- | --- |
| 坐下要很前傾才觸發 | `sitting` 的 y-geometry 是否不成立、knee_angle 是否太大、trunk 是否超過 35 |
| 蹲下常被當坐下 | `knee.y` 和 `hip.y` 是否接近，sitting 因順序先吃掉 |
| 彎腰被當跌倒 | deep-bending guard 是否因 bbox_r > 1.0 沒啟動 |
| 跌倒角度不夠明顯 | trunk_angle 是否沒超過 60，或 ankle_y/image_height 沒超過 0.6 |
| 叉腰完全測不出來 | 是否先被 standing return；看 elbow outward、arm_vis、wrist score |
| 單膝跪完全測不出來 | standing-side ankle 是否低於 0.5，或雙膝 y 差不足 |
| Brain 答不出「我在幹嘛」 | `/event/pose_detected` 有無、Brain `_POSE_ZH` 是否支援該 pose、pose 是否超過 10s stale |

## 5. Brain 綁定檢查

問：

```text
我現在在幹嘛？
你看到我的姿勢嗎？
```

同時看 Brain trace 或 log 是否有：

```text
world_state ... pose=sitting
```

如果 `/event/pose_detected` 有 `bending/akimbo/knee_kneel`，但 Brain trace 是 `pose=none` 或回答沒有提到，優先補：

```text
pawai_brain/pawai_brain/conversation_graph_node.py::_POSE_ZH
```

## 6. Executive 檢查

```bash
ros2 topic echo /event/skill_request
ros2 topic echo /tts
```

預期：

| pose | 預期 |
| --- | --- |
| `fallen` | 2 秒穩定後 `fallen_alert` |
| `sitting` | 1 秒穩定後 `sit_along`，也可能 demo bridge TTS |
| `bending` | 1 秒穩定後 `careful_remind`，也可能 demo bridge TTS |
| `crouching` | 目前主要是 demo bridge TTS，不是 Executive rule |
| `akimbo` | 目前主要是 demo bridge TTS |
| `knee_kneel` | 目前主要是 demo bridge TTS |

如果 `sitting/bending` 重複說話，檢查 `event_action_bridge` 是否和 `interaction_executive` 同時處理同一個 pose。

## 7. 建議明天優先修

P0：補 Brain `_POSE_ZH`：

```text
bending: 彎腰
akimbo: 雙手叉腰
knee_kneel: 單膝跪地
```

P0：釐清 pose event/state 模型。

目前 event 是 transition，但 pose 是 state。建議新增：

```text
/state/perception/pose
```

週期 publish 目前穩定姿勢，讓 Brain 和 Executive 不用靠 sparse event 猜「現在」。

P1：把 `crouching/akimbo/knee_kneel` 決定要走正式 skill 還是只保留 demo TTS。

P1：現場錄 5 種失敗姿勢的 debug log：

```text
sitting 失敗
crouching 失敗
bending vs fallen
akimbo 失敗
knee_kneel 失敗
```

P2：再調 classifier threshold。沒有 log 直接調，很容易修一個壞三個。

## 8. 可跑測試

```bash
pytest vision_perception/test/test_pose_classifier.py
pytest vision_perception/test/test_mediapipe_pose_mapping.py
pytest vision_perception/test/test_event_builder.py
pytest interaction_executive/test/test_brain_rules.py
```

如果改 fallen gate，至少跑完整 `test_pose_classifier.py`。如果改 Executive pose 行為，跑 `test_brain_rules.py`。
