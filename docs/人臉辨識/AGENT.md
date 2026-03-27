# 人臉辨識 — 介面契約

> 任何 agent 或接手者，讀這份就知道怎麼跟這個模組互動。

## 模組邊界

- **所屬 package**：`face_perception`
- **上游**：D435 RealSense（RGB + Depth）
- **下游**：interaction_executive_node

## 輸出 Topic

| Topic | 類型 | 頻率 | Schema |
|-------|------|------|--------|
| `/state/perception/face` | String (JSON) | 10 Hz | `{"stamp": float, "face_count": int, "tracks": [{"track_id": int, "stable_name": str, "sim": float, "distance_m": float, "bbox": [4], "mode": str}]}` |
| `/event/face_identity` | String (JSON) | 事件式 | `{"event_type": "track_started\|identity_stable\|identity_changed\|track_lost", "track_id": int, "identity": str, "sim": float}` |
| `/face_identity/debug_image` | Image | ~6.6 Hz | Debug 影像帶框 |

## 輸入

- `/camera/camera/color/image_raw`（D435 RGB）
- `/camera/aligned_depth_to_color/image_raw`（D435 Depth，用於距離估計）

## 依賴

- OpenCV 4.5.4+（YuNet + SFace）
- D435 RealSense + realsense2_camera_node
- face_db：`/home/jetson/face_db/`

## 事件流

```
D435 RGB+Depth → face_identity_node (YuNet→SFace→IOU tracker)
    → /state/perception/face (10Hz)
    → /event/face_identity (identity_stable)
    → executive → WELCOME → TTS 問候
```

## 接手確認清單

- [ ] D435 有在發布？`ros2 topic hz /camera/camera/color/image_raw`
- [ ] face node 有在跑？`ros2 topic echo /state/perception/face --once`
- [ ] face_db 有資料？`ls /home/jetson/face_db/`
- [ ] debug image 有畫面？Foxglove 看 `/face_identity/debug_image`
